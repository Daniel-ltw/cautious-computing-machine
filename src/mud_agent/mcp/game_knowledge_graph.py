"""Game Knowledge Graph Manager using SQLite and Peewee ORM.

This module provides a dedicated class for managing the game's knowledge graph,
leveraging an SQLite database via the Peewee ORM for robust and efficient data storage.
"""

import logging
from typing import Any, Dict, List, Optional

from peewee import DoesNotExist, fn

from ..db.migrate_db import run_migrations
from .models import (
    NPC,
    Entity,
    Relation,
    Room,
    RoomExit,
    db,
    get_db_stats,
    find_path_between_rooms,
)

logger = logging.getLogger(__name__)

class PathfindingError(Exception):
    """Custom exception for pathfinding errors."""
    pass


class GameKnowledgeGraph:
    """Manager for the game knowledge graph stored in an SQLite database.

    This class handles all operations related to the knowledge graph, including
    creating, retrieving, and relating entities (Rooms, NPCs) using a Peewee ORM.
    """

    def __init__(self):
        """Initialize the Game Knowledge Graph Manager."""
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database connection and run migrations."""
        try:
            if db.is_closed():
                db.connect()
                self.logger.info("Database connection opened.")

            run_migrations()
            self._initialized = True
            self.logger.info("Game knowledge graph initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize game knowledge graph: {e}", exc_info=True)
            self._initialized = False

    async def cleanup(self) -> None:
        """Clean up resources by closing the database connection."""
        if not db.is_closed():
            db.close()
            self.logger.info("Database connection closed.")

    def get_exit_command_details(self, from_room_number: int, direction: str) -> Dict[str, Any]:
        """Retrieve stored command sequence details for a room exit.

        Args:
            from_room_number: Source room number.
            direction: Exit direction (supports full or shorthand).

        Returns:
            Dict with keys: move_command, pre_commands, last_success_at, source. Empty if none.
        """
        try:
            if not self._initialized:
                self.logger.error("Cannot get exit details: Knowledge graph not initialized.")
                return {}

            # Normalize direction to lowercase
            dir_norm = direction.strip().lower()
            mapping = {
                "north": "n", "south": "s", "east": "e", "west": "w", "up": "u", "down": "d",
                "n": "n", "s": "s", "e": "e", "w": "w", "u": "u", "d": "d",
                # Special command-based exits
                "enter": "enter",
            }
            dir_key = mapping.get(dir_norm, dir_norm)

            room = self.get_room_by_number(int(from_room_number))
            if not room:
                return {}
            for exit_obj in room.exits:
                # Normalize stored direction which may be full word (e.g., 'east') or shorthand ('e')
                stored = exit_obj.direction.strip().lower()
                stored_norm = mapping.get(stored, stored)
                if stored_norm == dir_key:
                    return exit_obj.get_command_details()
            return {}
        except Exception as e:
            self.logger.error(f"Error retrieving exit command details for room {from_room_number} {direction}: {e}", exc_info=True)
            return {}

    async def add_entity(self, entity_data: Dict[str, Any]) -> Optional[Entity]:
        """Add or update an entity in the knowledge graph.

        Args:
            entity_data: A dictionary containing the entity's data.

        Returns:
            The created or updated Entity object, or None if data is invalid.
        """
        if not self._initialized:
            self.logger.error("Cannot add entity: Knowledge graph not initialized.")
            return None

        entity_type = entity_data.get("entityType")
        if not entity_type:
            self.logger.error("Failed to add entity: 'entityType' is missing.")
            return None

        try:
            if entity_type == "Room":
                # Separate NPC data from room data
                npcs = set([npc["name"] for npc in entity_data.pop("npcs", [])])
                npcs.update([npc["name"] for npc in entity_data.pop("manual_npcs", [])])
                npcs.update([npc["name"] for npc in entity_data.pop("scan_npcs", [])])
                npc_list = list([{"name": npc} for npc in npcs])

                # Create or update the room
                with db.atomic():
                    room = Room.create_or_update_from_dict(entity_data)
                    if not room:
                        self.logger.error(f"Room is None: {entity_data}")
                        return None

                with db.atomic():
                    # Create or update associated NPCs
                    for npc_data in npc_list:
                        NPC.create_or_update_from_dict(npc_data, current_room=room)

                return room.entity
            elif entity_type == "NPC":
                npc = NPC.create_or_update_from_dict(entity_data)
                return npc.entity if npc else None
            else:
                self.logger.warning(f"Unsupported entityType: {entity_type}")
                return None
        except Exception as e:
            self.logger.error(f"Error adding entity: {e}", exc_info=True)
            return None

    def add_relation(
        self, from_entity: Entity, to_entity: Entity, relation_type: str
    ) -> Optional[Relation]:
        """Add a directional relation between two entities.

        Args:
            from_entity: The source entity of the relation.
            to_entity: The target entity of the relation.
            relation_type: The type of the relation (e.g., 'has exit n to').

        Returns:
            The created Relation object, or None on failure.
        """
        if not self._initialized:
            self.logger.error("Cannot add relation: Knowledge graph not initialized.")
            return None

        try:
            with db.atomic():
                relation, created = Relation.get_or_create(
                    from_entity=from_entity,
                    to_entity=to_entity,
                    relation_type=relation_type,
                )
                if created:
                    self.logger.debug(
                        f"Created new relation: {from_entity.name} -> {to_entity.name} ({relation_type})"
                    )
                return relation
        except Exception as e:
            self.logger.error(f"Error adding relation: {e}", exc_info=True)
            return None

    def get_entity(self, name: str) -> Optional[Entity]:
        """Retrieve an entity by its name.

        Args:
            name: The name of the entity to retrieve.

        Returns:
            The Entity object if found, otherwise None.
        """
        if not self._initialized:
            self.logger.error("Cannot get entity: Knowledge graph not initialized.")
            return None

        try:
            return Entity.get(Entity.name == name)
        except DoesNotExist:
            self.logger.debug(f"Entity with name '{name}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving entity '{name}': {e}", exc_info=True)
            return None

    def get_room_by_number(self, room_number: int) -> Optional[Room]:
        """Retrieve a room by its number.

        Args:
            room_number: The number of the room to retrieve.

        Returns:
            The Room object if found, otherwise None.
        """
        if not self._initialized:
            self.logger.error("Cannot get room: Knowledge graph not initialized.")
            return None

        try:
            return Room.select().join(Entity).where(Room.room_number == room_number).get()
        except DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving room '{room_number}': {e}", exc_info=True)
            return None

    def get_rooms_by_area(self, area_name: str) -> List[Room]:
        """Retrieve all rooms within a specific area.

        Args:
            area_name: The name of the area to retrieve rooms from.

        Returns:
            A list of Room objects in the specified area.
        """
        if not self._initialized:
            self.logger.error("Cannot get rooms by area: Knowledge graph not initialized.")
            return []

        try:
            return list(Room.select().where(Room.zone == area_name))
        except Exception as e:
            self.logger.error(f"Error retrieving rooms for area '{area_name}': {e}", exc_info=True)
            return []

    def get_room_with_unexplored_exits(self, area_name: str, visited_rooms: set) -> Optional[Room]:
        """Get a room in the specified area with at least one unexplored exit."""
        if not self._initialized:
            self.logger.error("Cannot get room with unexplored exits: Knowledge graph not initialized.")
            return None

        try:
            # Find rooms in the target area that have not been visited yet
            # and have at least one exit leading to an unknown room (to_room_id is NULL).
            query = (
                Room.select()
                .join(RoomExit, on=(RoomExit.from_room == Room.id))
                .where(
                    (Room.zone == area_name) &
                    (Room.room_number.not_in(visited_rooms)) &
                    (RoomExit.to_room.is_null())
                )
                .group_by(Room.id)
                .order_by(fn.Random())
                .limit(1)
            )

            return query.get() if query else None
        except DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving room with unexplored exits for area '{area_name}': {e}", exc_info=True)
            return None

    def get_rooms_with_unexplored_exits(self, area_name: str) -> List[Room]:
        """Get a list of rooms in the specified area with at least one unexplored exit."""
        if not self._initialized:
            self.logger.error("Cannot get rooms with unexplored exits: Knowledge graph not initialized.")
            return []

        try:
            # Find rooms that have at least one exit leading to an unknown room (to_room_id is NULL).
            query = (
                Room.select()
                .join(RoomExit, on=(RoomExit.from_room == Room.id))
                .where((Room.zone == area_name) & (RoomExit.to_room.is_null()))
                .group_by(Room.id)
            )
            return list(query)
        except Exception as e:
            self.logger.error(f"Error retrieving rooms with unexplored exits for area '{area_name}': {e}", exc_info=True)
            return []

    async def record_exit_success(
        self,
        from_room_num: int,
        to_room_num: int,
        direction: str,
        move_cmd: str,
        pre_cmds: Optional[List[str]] = None,
    ) -> None:
        """Records a successful exit from one room to another."""
        if not self._initialized:
            self.logger.error("Cannot record exit success: Knowledge graph not initialized.")
            return

        try:
            with db.atomic():
                from_room = Room.get_or_none(Room.room_number == from_room_num)
                if not from_room:
                    self.logger.warning(f"Room {from_room_num} not found. Cannot record exit.")
                    return

                to_room = Room.get_or_none(Room.room_number == to_room_num)
                if not to_room:
                    # If the destination room doesn't exist, create it
                    to_room_entity, _ = Entity.get_or_create(
                        name=str(to_room_num), defaults={"entity_type": "Room"}
                    )
                    to_room = Room.create(entity=to_room_entity, room_number=to_room_num)

                exit_obj = self.get_or_create_exit(
                    from_room,
                    direction,
                    to_room=to_room,
                    to_room_number=to_room_num
                )

                exit_obj.record_exit_success(
                    move_command=move_cmd, pre_commands=pre_cmds or []
                )
        except DoesNotExist:
            # This case should ideally not be hit for from_room or to_room if they are managed correctly.
            self.logger.warning(
                f"Room not found when recording exit success. From: {from_room_num}, To: {to_room_num}"
            )
        except Exception as e:
            self.logger.error(f"Error recording exit success: {e}", exc_info=True)

    def get_or_create_exit(self, from_room, direction, to_room=None, to_room_number=None):
        if to_room and not to_room_number:
            to_room_number = to_room.room_number

        if not to_room_number:
            raise ValueError("to_room_number must be provided to get_or_create_exit")

        # New method using get_or_create
        exit_obj, created = RoomExit.get_or_create(
            from_room=from_room,
            to_room_number=to_room_number,
            defaults={'direction': direction, 'to_room': to_room}
        )

        if not created:
            # Update existing exit if needed
            if to_room and exit_obj.to_room != to_room:
                exit_obj.to_room = to_room
            if direction and exit_obj.direction != direction:
                exit_obj.direction = direction
            exit_obj.save()

        return exit_obj

        return exit_obj

    async def find_path_between_rooms(
        self, start_room_id: int, end_room_identifier: [int, str], max_depth: int = 350
    ) -> Optional[Dict[str, Any]]:
        """Find a path between two rooms using BFS.

        Args:
            start_room_id: The room number of the starting room.
            end_room_identifier: The room number or name of the destination room.
            max_depth: The maximum depth to search.

        Returns:
            A dictionary containing the path and cost, or None if no path is found.
        """
        if not self._initialized:
            self.logger.error("Cannot find path: Knowledge graph not initialized.")
            return None

        try:
            try:
                # If room identifier can be converted to int, then it is room number
                end_room_id = int(end_room_identifier)
            except (ValueError, TypeError):
                # Otherwise treat it as a room name
                room = Room.get(fn.LOWER(Room.full_name).contains(end_room_identifier.lower()))
                end_room_id = room.room_number

            path = find_path_between_rooms(
                from_room=start_room_id, to_room=end_room_id, max_depth=max_depth
            )

            if path:
                return {"path": path, "cost": len(path)}
            return None
        except DoesNotExist:
            self.logger.warning(f"Room with name or id '{end_room_identifier}' not found.")
            return None
        except Exception as e:
            self.logger.error(
                f"Error finding path from {start_room_id} to {end_room_identifier}: {e}",
                exc_info=True,
            )
            return None

    async def query_entities_by_type(self, entity_type: str) -> list[dict[str, Any]]:
        """Query entities by type from the knowledge graph.

        Args:
            entity_type: The type of entities to query (e.g., "Room", "NPC")

        Returns:
            List[Dict[str, Any]]: List of entities matching the type
        """
        if not self._initialized:
            self.logger.error("Cannot query entities: Knowledge graph not initialized.")
            return []

        try:
            entities = Entity.select().where(Entity.entity_type == entity_type)
            return [entity.to_dict() for entity in entities]
        except Exception as e:
            self.logger.error(f"Error querying entities by type: {e}", exc_info=True)
            return []

    async def query_entity_by_name(self, name: str) -> dict[str, Any] | None:
        """Query an entity by name from the knowledge graph.

        Args:
            name: The name of the entity to query

        Returns:
            Optional[Dict[str, Any]]: The entity if found, None otherwise
        """
        entity = self.get_entity(name)
        if entity:
            return entity.to_dict()
        return None

    async def find_npcs_in_room(self, room_identifier: str) -> list[dict[str, Any]]:
        """Find all NPCs/mobs in a specific room.

        Args:
            room_identifier: The room number or name to search in

        Returns:
            List[Dict[str, Any]]: List of NPC entities in the room
        """
        if not self._initialized:
            self.logger.error("Cannot find NPCs: Knowledge graph not initialized.")
            return []

        try:
            room = Room.select().join(Entity).where(Entity.name == room_identifier).get()
            npcs = NPC.select().where(NPC.current_room == room)
            return [npc.entity.to_dict() for npc in npcs]
        except DoesNotExist:
            self.logger.warning(f"Room '{room_identifier}' not found in knowledge graph")
            return []
        except Exception as e:
            self.logger.error(f"Error finding NPCs in room: {e}", exc_info=True)
            return []

    async def find_room_with_npc(self, npc_name: str) -> dict[str, Any] | None:
        """Find the room where a specific NPC/mob is located.

        Args:
            npc_name: The name of the NPC/mob to find

        Returns:
            Optional[Dict[str, Any]]: The room entity if found, None otherwise
        """
        if not self._initialized:
            self.logger.error("Cannot find room with NPC: Knowledge graph not initialized.")
            return None

        try:
            npc = NPC.select().join(Entity).where(Entity.name == npc_name).get()
            if npc.current_room:
                return npc.current_room.entity.to_dict()
            return None
        except DoesNotExist:
            self.logger.warning(f"NPC '{npc_name}' not found in knowledge graph")
            return None
        except Exception as e:
            self.logger.error(f"Error finding room with NPC: {e}", exc_info=True)
            return None

    async def get_knowledge_graph_summary(self) -> dict[str, Any]:
        """Get a summary of the knowledge graph.

        This method provides a high-level overview of the knowledge graph contents,
        including counts of entities by type and relations by type.

        Returns:
            Dict[str, Any]: A summary of the knowledge graph
        """
        try:
            # Count entities by type
            entity_counts = {}
            for entity in self.knowledge_graph["entities"].values():
                entity_type = entity.get("entityType", "Unknown")
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

            # Count relations by type
            relation_counts = {}
            for relation in self.knowledge_graph["relations"]:
                relation_type = relation.get("relationType", "Unknown")
                relation_counts[relation_type] = (
                    relation_counts.get(relation_type, 0) + 1
                )

            # Create summary
            summary = {
                "total_entities": len(self.knowledge_graph["entities"]),
                "total_relations": len(self.knowledge_graph["relations"]),
                "entity_types": entity_counts,
                "relation_types": relation_counts,
            }

            self.logger.info(
                f"Knowledge graph summary: {len(self.knowledge_graph['entities'])} entities, "
                f"{len(self.knowledge_graph['relations'])} relations"
            )

            return summary
        except Exception as e:
            self.logger.error(
                f"Error generating knowledge graph summary: {e}", exc_info=True
            )
            return {
                "error": str(e),
                "total_entities": 0,
                "total_relations": 0,
                "entity_types": {},
                "relation_types": {},
            }

    async def get_knowledge_graph_summary_formatted(self) -> str:
        """Get a formatted summary of the knowledge graph.

        Returns:
            str: A formatted summary of the knowledge graph
        """
        try:
            summary = await self.get_knowledge_graph_summary()

            if "error" in summary:
                return f"Error getting knowledge graph summary: {summary['error']}"

            # Format the summary as a string
            result = []
            result.append("Knowledge Graph Summary:")
            result.append(f"Total Entities: {summary['total_entities']}")
            result.append(f"Total Relations: {summary['total_relations']}")

            # Entity types
            result.append("\nEntity Types:")
            for entity_type, count in summary["entity_types"].items():
                result.append(f"  - {entity_type}: {count}")

            # Relation types
            result.append("\nRelation Types:")
            for relation_type, count in summary["relation_types"].items():
                result.append(f"  - {relation_type}: {count}")

            # Return the formatted summary
            return "\n".join(result)
        except Exception as e:
            self.logger.error(
                f"Error getting knowledge graph summary: {e}", exc_info=True
            )
            return f"Error getting knowledge graph summary: {e}"

    async def search_nodes(self, query: str) -> dict[str, Any]:
        """Search for nodes in the knowledge graph.

        Args:
            query: The search query

        Returns:
            Dict[str, Any]: The search results
        """
        try:
            # Simple implementation that searches entity names and types
            results = []

            for entity_name, entity_data in self.knowledge_graph["entities"].items():
                # Check if query matches entity name or type
                if (
                    query.lower() in entity_name.lower()
                    or query.lower() in entity_data.get("entityType", "").lower()
                ):
                    # Add entity to results
                    results.append(
                        {
                            "name": entity_name,
                            "entityType": entity_data.get("entityType", "Unknown"),
                            "observations": entity_data.get("observations", []),
                        }
                    )

            return {"nodes": results}
        except Exception as e:
            self.logger.error(f"Error searching nodes: {e}", exc_info=True)
            return {"nodes": []}

    async def open_nodes(self, names: list[str]) -> dict[str, Any]:
        """Open specific nodes in the knowledge graph by their names.

        Args:
            names: A list of entity names to retrieve

        Returns:
            Dict[str, Any]: The nodes that were found
        """
        try:
            results = []

            for name in names:
                if name in self.knowledge_graph["entities"]:
                    entity_data = self.knowledge_graph["entities"][name]
                    results.append(
                        {
                            "name": name,
                            "entityType": entity_data.get("entityType", "Unknown"),
                            "observations": entity_data.get("observations", []),
                        }
                    )

            return {"nodes": results}
        except Exception as e:
            self.logger.error(f"Error opening nodes: {e}", exc_info=True)
            return {"nodes": []}

    async def get_world_map(self) -> str:
        """Get a merged map of all explored rooms.

        Returns:
            str: A merged map of all explored rooms, or a message if no maps found
        """
        try:
            # Get all room entities from the knowledge graph
            room_entities = [
                entity for entity in self.knowledge_graph["entities"].values()
                if entity.get("entityType") == "Room"
            ]

            if not room_entities:
                return "No rooms found in knowledge graph"

            # Extract maps from room entities
            room_maps = {}
            for room in room_entities:
                # First check if map is in metadata
                if "metadata" in room and "map" in room["metadata"]:
                    map_text = room["metadata"]["map"]
                    room_maps[room["name"]] = map_text
                # Fall back to observations if not in metadata
                elif "observations" in room:
                    for observation in room["observations"]:
                        if observation.startswith("Map:"):
                            # Extract the map from the observation
                            map_text = observation[4:].strip()  # Remove 'Map:' prefix
                            room_maps[room["name"]] = map_text
                            break

            if not room_maps:
                return "No maps found in knowledge graph"

            # If we only have one map, just return it
            if len(room_maps) == 1:
                room_name = list(room_maps.keys())[0]
                return f"Map for {room_name}:\n\n{room_maps[room_name]}"

            # Basic map merging algorithm
            # For now, we'll just return the most detailed map (the one with the most lines)
            most_detailed_map = None
            most_detailed_room = None
            max_score = 0

            for room_name, map_text in room_maps.items():
                lines = map_text.count("\n") + 1
                map_chars = sum(
                    1
                    for c in map_text
                    if c
                    in [
                        "-",
                        "|",
                        "+",
                        "<",
                        ">",
                        "[",
                        "]",
                        "*",
                        ".",
                        "!",
                        "$",
                        "#",
                        "~",
                        "(",
                        ")",
                        "^",
                        "v",
                    ]
                )

                # Score based on number of lines and map characters
                score = lines * 2 + map_chars

                if score > max_score:
                    max_score = score
                    most_detailed_map = map_text
                    most_detailed_room = room_name

            if most_detailed_map:
                return f"Most detailed map (from {most_detailed_room}):\n\n{most_detailed_map}\n\nFound maps for {len(room_maps)} rooms."

            # If we couldn't find a good map to display, just list the rooms with maps
            result = [f"Found maps for {len(room_maps)} rooms:"]
            for room_name in sorted(room_maps.keys()):
                result.append(f"- {room_name}")

            return "\n".join(result)
        except Exception as e:
            self.logger.error(f"Error getting world map: {e}", exc_info=True)
            return f"Error getting world map: {e}"

    async def add_observations(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Add observations to existing entities in the knowledge graph.

        Args:
            data: A dictionary with the observations to add
                Format: {"observations": [{"entityName": "name", "contents": ["observation1", "observation2"]}]}

        Returns:
            Dict[str, Any]: The result of the operation
        """
        try:
            if "observations" not in data:
                self.logger.error("No observations provided", exc_info=True)
                return {"success": False}

            for observation_data in data["observations"]:
                entity_name = observation_data.get("entityName")
                contents = observation_data.get("contents", [])

                if not entity_name or not contents:
                    continue

                # Check if entity exists
                if entity_name not in self.knowledge_graph["entities"]:
                    self.logger.warning(f"Entity {entity_name} not found, creating it")
                    self.knowledge_graph["entities"][entity_name] = {
                        "name": entity_name,
                        "entityType": "Generic",
                        "observations": contents,
                        "metadata": {"last_updated": datetime.now().isoformat()},
                    }
                else:
                    # Add observations to existing entity
                    entity = self.knowledge_graph["entities"][entity_name]

                    # Ensure observations list exists
                    if "observations" not in entity:
                        entity["observations"] = []

                    # Add new observations, avoiding duplicates
                    for content in contents:
                        if content not in entity["observations"]:
                            entity["observations"].append(content)

                    # Update timestamp
                    if "metadata" not in entity:
                        entity["metadata"] = {}
                    entity["metadata"]["last_updated"] = datetime.now().isoformat()

            # Save changes
            await self.save_knowledge_graph()

            return {"success": True}
        except Exception as e:
            self.logger.error(f"Error adding observations: {e}", exc_info=True)
            return {"success": False}

    async def delete_observations(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Delete observations from entities in the knowledge graph.

        Args:
            data: A dictionary with the observations to delete
                Format: {"deletions": [{"entityName": "name", "observations": ["observation1", "observation2"]}]}

        Returns:
            Dict[str, Any]: The result of the operation
        """
        try:
            if "deletions" not in data:
                self.logger.error("No deletions provided", exc_info=True)
                return {"success": False}

            for deletion_data in data["deletions"]:
                entity_name = deletion_data.get("entityName")
                observations = deletion_data.get("observations", [])

                if not entity_name or not observations:
                    continue

                # Check if entity exists
                if entity_name not in self.knowledge_graph["entities"]:
                    self.logger.warning(
                        f"Entity {entity_name} not found, skipping deletion"
                    )
                    continue

                # Delete observations from entity
                entity = self.knowledge_graph["entities"][entity_name]

                # Ensure observations list exists
                if "observations" not in entity:
                    continue

                # Remove observations
                for observation in observations:
                    if observation in entity["observations"]:
                        entity["observations"].remove(observation)

                # Update timestamp
                if "metadata" not in entity:
                    entity["metadata"] = {}
                entity["metadata"]["last_updated"] = datetime.now().isoformat()

            # Save changes
            await self.save_knowledge_graph()

            return {"success": True}
        except Exception as e:
            self.logger.error(f"Error deleting observations: {e}", exc_info=True)
            return {"success": False}

    async def delete_entities(self, data: dict[str, Any]) -> dict[str, Any]:
        """Delete multiple entities and their associated relations from the knowledge graph.

        Args:
            data: A dictionary with the entity names to delete
                Format: {"entityNames": ["name1", "name2"]}

        Returns:
            Dict[str, Any]: The result of the operation
        """
        try:
            if "entityNames" not in data:
                self.logger.error("No entity names provided", exc_info=True)
                return {"success": False}

            entity_names = data["entityNames"]

            # Delete each entity
            for name in entity_names:
                if name in self.knowledge_graph["entities"]:
                    del self.knowledge_graph["entities"][name]

                    # Also delete any relations involving this entity
                    self.knowledge_graph["relations"] = [
                        relation
                        for relation in self.knowledge_graph["relations"]
                        if relation.get("from") != name and relation.get("to") != name
                    ]

            # Save changes
            await self.save_knowledge_graph()

            return {"success": True}
        except Exception as e:
            self.logger.error(f"Error deleting entities: {e}", exc_info=True)
            return {"success": False}

    async def delete_relations(self, data: dict[str, Any]) -> dict[str, Any]:
        """Delete multiple relations from the knowledge graph.

        Args:
            data: A dictionary with the relations to delete
                Format: {"relations": [{"from": "entity1", "to": "entity2", "relationType": "type"}]}

        Returns:
            Dict[str, Any]: The result of the operation
        """
        try:
            if "relations" not in data:
                self.logger.error("No relations provided", exc_info=True)
                return {"success": False}

            relations_to_delete = data["relations"]

            # Delete matching relations
            for relation_to_delete in relations_to_delete:
                from_entity = relation_to_delete.get("from")
                to_entity = relation_to_delete.get("to")
                relation_type = relation_to_delete.get("relationType")

                if not from_entity or not to_entity or not relation_type:
                    continue

                # Filter out the matching relations
                self.knowledge_graph["relations"] = [
                    relation
                    for relation in self.knowledge_graph["relations"]
                    if not (
                        relation.get("from") == from_entity
                        and relation.get("to") == to_entity
                        and relation.get("relationType") == relation_type
                    )
                ]

            # Save changes
            await self.save_knowledge_graph()

            return {"success": True}
        except Exception as e:
            self.logger.error(f"Error deleting relations: {e}", exc_info=True)
            return {"success": False}

    async def read_graph(self, _: dict[str, Any]) -> dict[str, Any]:
        """Read the entire knowledge graph.

        Args:
            _: An empty dictionary (not used)

        Returns:
            Dict[str, Any]: The entire knowledge graph
        """
        # Return a copy of the knowledge graph
        return {
            "entities": self.knowledge_graph.get("entities", {}),
            "relations": self.knowledge_graph.get("relations", []),
        }


    def _is_gmcp_observation(self, observation: str) -> bool:
        """Check if an observation contains GMCP data that should be in metadata.

        Args:
            observation: The observation string to check

        Returns:
            bool: True if this is GMCP data, False otherwise
        """
        gmcp_prefixes = [
            "Room Number:", "Zone:", "Terrain:", "Outside:", "Details:",
            "Coordinates:", "Exit Details:", "Full Name:", "Exits:"
        ]
        return any(observation.startswith(prefix) for prefix in gmcp_prefixes)

    async def _log_entity_results(
        self, created_entities: list[str], updated_entities: list[str]
    ) -> None:
        """Log the results of entity creation/update.

        Args:
            created_entities: List of created entity names
            updated_entities: List of updated entity names
        """
        if created_entities and updated_entities:
            self.logger.info(
                f"Created {len(created_entities)} entities: {created_entities}"
            )
            self.logger.info(
                f"Updated {len(updated_entities)} entities: {updated_entities}"
            )
        elif created_entities:
            self.logger.info(
                f"Created {len(created_entities)} entities: {created_entities}"
            )
        elif updated_entities:
            self.logger.info(
                f"Updated {len(updated_entities)} entities: {updated_entities}"
            )

    async def create_relations(self, relations: list[dict[str, Any]]) -> bool:
        """Create new relations between entities, avoiding duplicates.

        This method checks if a relation already exists before adding it to the knowledge graph.
        A relation is considered a duplicate if it has the same "from", "to", and "relationType".

        Args:
            relations: List of relation dictionaries to create

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Basic validation
            if not await self._validate_relations_input(relations):
                return False

            # Sanitize relations to ensure they are valid
            sanitized_relations = await self._sanitize_relations(relations)
            if not sanitized_relations:
                self.logger.warning(
                    "No valid relations after sanitization", exc_info=True
                )
                return False

            # Update knowledge graph, checking for duplicates
            new_relations, duplicate_relations = await self._merge_relations(
                sanitized_relations
            )

            # Save to disk
            await self.save_knowledge_graph()

            # Log results
            await self._log_relation_results(new_relations, duplicate_relations)

            return True

        except Exception as e:
            self.logger.error(f"Error in create_relations: {e}", exc_info=True)
            return False
