"""Game Knowledge Graph Manager using SQLite and Peewee ORM.

This module provides a dedicated class for managing the game's knowledge graph,
leveraging an SQLite database via the Peewee ORM for robust and efficient data storage.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from peewee import DoesNotExist, IntegrityError, fn

from ..db.migrate_db import DatabaseMigrator
from ..db.models import (
    NPC,
    Entity,
    Relation,
    Room,
    RoomExit,
    db,
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

    async def _run_db(self, func, *args, **kwargs):
        """Run a blocking database function in a separate thread.

        Each call gets its own connection context so threads don't collide
        on SQLite's single-writer lock.
        """
        def _wrapper():
            with db.connection_context():
                return func(*args, **kwargs)
        return await asyncio.to_thread(_wrapper)

    async def initialize(self) -> None:
        """Initialize the database connection and run migrations."""
        try:
            if db.is_closed():
                db.connect()
                self.logger.info("Database connection opened.")

            DatabaseMigrator.run_migrations()
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

    async def get_exit_command_details(self, from_room_number: int, direction: str) -> dict[str, Any]:
        """Retrieve stored command sequence details for a room exit.

        Args:
            from_room_number: Source room number.
            direction: Exit direction (supports full or shorthand).

        Returns:
            Dict with keys: move_command, pre_commands, last_success_at, source. Empty if none.
        """
        return await self._run_db(self._get_exit_command_details_sync, from_room_number, direction)

    def _get_exit_command_details_sync(self, from_room_number: int, direction: str) -> dict[str, Any]:
        """Synchronous implementation of get_exit_command_details."""
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

            room = self.get_room_by_number_sync(int(from_room_number))
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

    async def add_entity(self, entity_data: dict[str, Any]) -> Entity | None:
        """Add or update an entity in the knowledge graph.

        Args:
            entity_data: A dictionary containing the entity's data.

        Returns:
            The created or updated Entity object, or None if data is invalid.
        """
        return await self._run_db(self._add_entity_sync, entity_data)

    def _add_entity_sync(self, entity_data: dict[str, Any]) -> Entity | None:
        """Synchronous implementation of add_entity."""
        if not self._initialized:
            # We can't await initialize() here because we are in a sync wrapper running in a thread.
            # However, logic calling this should ensure initialization or we assume init is done.
            # For robustness, we check the flag.
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

    async def add_relation(
        self, from_entity: Entity, to_entity: Entity, relation_type: str
    ) -> Relation | None:
        """Add a directional relation between two entities.

        Args:
            from_entity: The source entity of the relation.
            to_entity: The target entity of the relation.
            relation_type: The type of the relation (e.g., 'has exit n to').

        Returns:
            The created Relation object, or None on failure.
        """
        return await self._run_db(self._add_relation_sync, from_entity, to_entity, relation_type)

    def _add_relation_sync(
        self, from_entity: Entity, to_entity: Entity, relation_type: str
    ) -> Relation | None:
        """Synchronous implementation of add_relation."""
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

    async def get_entity(self, name: str) -> Entity | None:
        """Retrieve an entity by its name.

        Args:
            name: The name of the entity to retrieve.

        Returns:
            The Entity object if found, otherwise None.
        """
        return await self._run_db(self._get_entity_sync, name)

    def _get_entity_sync(self, name: str) -> Entity | None:
        """Synchronous implementation of get_entity."""
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

    async def get_room_info(self, room_number: int) -> dict[str, Any] | None:
        """Get room information as a dictionary, preventing lazy loading issues."""
        return await self._run_db(self._get_room_info_sync, room_number)

    def _get_room_info_sync(self, room_number: int) -> dict[str, Any] | None:
        """Synchronous implementation of get_room_info."""
        room = self.get_room_by_number_sync(room_number)
        if room:
            return room.to_info()
        return None

    async def get_room_by_number(self, room_number: int) -> Room | None:
        """Retrieve a room by its number.

        Args:
            room_number: The number of the room to retrieve.

        Returns:
            The Room object if found, otherwise None.
        """
        return await self._run_db(self.get_room_by_number_sync, room_number)

    def get_room_by_number_sync(self, room_number: int) -> Room | None:
        """Synchronous implementation of get_room_by_number.
        Publicly accessible (but technically should be private) as helper for other sync methods.
        Identified as 'get_room_by_number_sync' to clarify it blocks.
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

    async def get_rooms_by_area(self, area_name: str) -> list[Room]:
        """Retrieve all rooms within a specific area.

        Args:
            area_name: The name of the area to retrieve rooms from.

        Returns:
            A list of Room objects in the specified area.
        """
        return await self._run_db(self._get_rooms_by_area_sync, area_name)

    def _get_rooms_by_area_sync(self, area_name: str) -> list[Room]:
        """Synchronous implementation of get_rooms_by_area."""
        if not self._initialized:
            self.logger.error("Cannot get rooms by area: Knowledge graph not initialized.")
            return []

        try:
            return list(Room.select().where(Room.zone == area_name))
        except Exception as e:
            self.logger.error(f"Error retrieving rooms for area '{area_name}': {e}", exc_info=True)
            return []

    async def get_room_with_unexplored_exits(self, area_name: str, visited_rooms: set) -> Room | None:
        """Get a room in the specified area with at least one unexplored exit."""
        return await self._run_db(self._get_room_with_unexplored_exits_sync, area_name, visited_rooms)

    def _get_room_with_unexplored_exits_sync(self, area_name: str, visited_rooms: set) -> Room | None:
        """Synchronous implementation of get_room_with_unexplored_exits."""
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

    async def get_rooms_with_unexplored_exits(self, area_name: str) -> list[Room]:
        """Get a list of rooms in the specified area with at least one unexplored exit."""
        return await self._run_db(self._get_rooms_with_unexplored_exits_sync, area_name)

    def _get_rooms_with_unexplored_exits_sync(self, area_name: str) -> list[Room]:
        """Synchronous implementation of get_rooms_with_unexplored_exits."""
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

    # Mapping for direction normalization
    DIRECTION_MAPPING = {
        "n": "north", "north": "north",
        "s": "south", "south": "south",
        "e": "east", "east": "east",
        "w": "west", "west": "west",
        "u": "up", "up": "up",
        "d": "down", "down": "down",
        "ne": "northeast", "northeast": "northeast",
        "nw": "northwest", "northwest": "northwest",
        "se": "southeast", "southeast": "southeast",
        "sw": "southwest", "southwest": "southwest",
    }

    async def record_exit_success(
        self,
        from_room_num: int,
        to_room_num: int,
        direction: str,
        move_cmd: str,
        pre_cmds: list[str] | None = None,
    ) -> None:
        """Records a successful exit from one room to another."""
        return await self._run_db(
            self._record_exit_success_sync,
            from_room_num,
            to_room_num,
            direction,
            move_cmd,
            pre_cmds,
        )

    def _record_exit_success_sync(
        self,
        from_room_num: int,
        to_room_num: int,
        direction: str,
        move_cmd: str,
        pre_cmds: list[str] | None = None,
    ) -> None:
        """Synchronous implementation of record_exit_success."""
        # Skip recording for commands that are runs or chained (contain ';')
        if move_cmd.strip().lower().startswith('run') or direction.strip().lower().startswith('run') or ';' in direction or ';' in move_cmd:
            self.logger.debug(f"Skipping exit recording for disallowed move command: {move_cmd}")
            return

        # Skip recording for simple 'enter' command as it is ambiguous
        if move_cmd.strip().lower() == 'enter':
            self.logger.debug(f"Skipping exit recording for ambiguous move command: {move_cmd}")
            return

        # Skip recording for 'scan' command as it is not a movement command
        if move_cmd.strip().lower() == 'scan':
            self.logger.debug(f"Skipping exit recording for non-movement command: {move_cmd}")
            return

        # Skip recording for 'where' command as it is not a movement command
        if 'where' in move_cmd.strip().lower():
            self.logger.debug(f"Skipping exit recording for non-movement command: {move_cmd}")
            return

        # Validate that move_cmd direction matches exit direction if both are standard directions
        normalized_move = self.DIRECTION_MAPPING.get(move_cmd.strip().lower())
        normalized_dir = self.DIRECTION_MAPPING.get(direction.strip().lower())

        if normalized_move and normalized_dir and normalized_move != normalized_dir:
            self.logger.debug(
                f"Skipping exit recording due to direction mismatch: "
                f"move_cmd='{move_cmd}' ({normalized_move}) != direction='{direction}' ({normalized_dir})"
            )
            return

        # Filter pre_commands to exclude run or chained commands
        if pre_cmds:
            pre_cmds = [cmd for cmd in pre_cmds if not (cmd.strip().lower().startswith('run') or ';' in cmd)]

        if not self._initialized:
            # Cannot await inside sync implementation. Assume checked or fail.
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

                # Normalize the direction to match stored exit keys
                dir_in = (direction or "").strip().lower()
                # Handle command-based exits and synonyms
                mapping = {
                    "north": "n", "south": "s", "east": "e", "west": "w", "up": "u", "down": "d",
                    "n": "n", "s": "s", "e": "e", "w": "w", "u": "u", "d": "d",
                    "enter": "enter", "board": "board", "escape": "escape",
                }
                # Reduce phrase commands like 'enter gate' to 'enter'
                if dir_in.startswith("say "):
                    dir_key = "say"
                elif dir_in.startswith("enter "):
                    dir_key = "enter"
                elif dir_in.startswith("board"):
                    dir_key = "board"
                elif dir_in.startswith("escape"):
                    dir_key = "escape"
                else:
                    dir_key = mapping.get(dir_in, dir_in)

                # Find the matching exit robustly, comparing normalized forms
                exit_obj = None
                for ex in from_room.exits:
                    stored = (ex.direction or "").strip().lower()
                    if stored.startswith("say "):
                        stored_norm = "say"
                    elif stored.startswith("enter "):
                        stored_norm = "enter"
                    elif stored.startswith("board"):
                        stored_norm = "board"
                    elif stored.startswith("escape"):
                        stored_norm = "escape"
                    else:
                        stored_norm = mapping.get(stored, stored)

                    # Direct match on stored direction name
                    if stored == dir_in:
                         exit_obj = ex
                         break

                    # Also match if the normalized directions are identical AND the stored direction
                    # is NOT a generic verb like 'enter' that might be used for multiple exits.
                    # e.g. 'n' vs 'north' is fine to match.
                    # 'enter hut' vs 'enter rubble' -> both norm to 'enter' -> should NOT match.
                    if stored_norm == dir_key and stored_norm not in ["enter", "board", "escape", "say"]:
                        exit_obj = ex
                        break

                    # Check if the command contains the stored direction (e.g. "enter portal" matches "portal")
                    # This handles cases where the exit is named "portal" but the command is "enter portal"
                    if len(stored) > 2 and dir_in.endswith(stored):
                         # Verify destination matching if we have that info, to prevent bad matches?
                         # Actually, without unique constraint on (from, to), multiple exits can go to same place.
                         # If 'enter portal' goes to same room as 'portal' exit, we should match.
                         # If we don't know destination of stored exit, we assume match based on name.
                         exit_obj = ex
                         break

                self.logger.debug(
                    f"Recording exit success: {from_room_num} -> {to_room_num} ({direction} -> {dir_key})"
                    f" with move command '{move_cmd}'"
                    f" pre-commands: {pre_cmds}"
                )

                if exit_obj is None:
                    try:
                        # With the new unique constraint on (from_room, direction), we can trust get_or_create
                        # to create a new exit if the direction string is different (e.g. "enter rubble" vs "enter hut")
                        exit_obj = self.get_or_create_exit(from_room, dir_in, to_room=to_room, to_room_number=to_room_num)
                    except Exception as e:
                        self.logger.error(f"Failed to record new exit {dir_in} -> {to_room_num}: {e}")
                        return

                self.logger.debug(f"Updating exit {exit_obj.direction} -> {to_room_num}")
                exit_obj.to_room = to_room
                exit_obj.to_room_number = to_room_num
                exit_obj.save()

                # Check if details are already fully populated - skip if so
                existing_details = exit_obj.get_command_details()
                if (existing_details.get("move_command") == move_cmd):
                    self.logger.debug(f"Exit {exit_obj.direction} already has correct details, skipping update.")
                else:
                    exit_obj.record_exit_success(
                        move_command=move_cmd, pre_commands=pre_cmds or [], force=False
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

        try:
            # Try to find an exit by its direction from the source room
            exit_obj = from_room.exits.where(RoomExit.direction == direction).get()

            # Exit exists, so update it if the destination has changed
            if to_room_number is not None and exit_obj.to_room_number != to_room_number:
                exit_obj.to_room_number = to_room_number
                if to_room:
                    exit_obj.to_room = to_room
                exit_obj.save()
            elif to_room and exit_obj.to_room != to_room:
                exit_obj.to_room = to_room
                if to_room.room_number:
                    exit_obj.to_room_number = to_room.room_number
                exit_obj.save()

            return exit_obj

        except DoesNotExist:
            # Exit does not exist, so create a new one
            try:
                return RoomExit.create(
                    from_room=from_room,
                    direction=direction,
                    to_room=to_room,
                    to_room_number=to_room_number,
                )
            except IntegrityError:
                # Race condition or case sensitivity issue - the exit was just created
                # or already exists but wasn't found. Try to get it again.
                self.logger.warning(f"IntegrityError creating exit {direction}, retrying get")
                try:
                    return from_room.exits.where(RoomExit.direction == direction).get()
                except DoesNotExist:
                    # Still not found - this is a real problem
                    self.logger.error(f"Failed to get or create exit {direction} even after IntegrityError")
                    raise



    async def query_entities_by_type(self, entity_type: str) -> list[dict[str, Any]]:
        """Query entities by type from the knowledge graph.

        Args:
            entity_type: The type of entities to query (e.g., "Room", "NPC")

        Returns:
            List[Dict[str, Any]]: List of entities matching the type
        """
        return await self._run_db(self._query_entities_by_type_sync, entity_type)

    def _query_entities_by_type_sync(self, entity_type: str) -> list[dict[str, Any]]:
        """Synchronous implementation of query_entities_by_type."""
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
        return await self._run_db(self._query_entity_by_name_sync, name)

    def _query_entity_by_name_sync(self, name: str) -> dict[str, Any] | None:
        """Synchronous implementation of query_entity_by_name."""
        # Using the sync get_entity helper
        entity = self._get_entity_sync(name)
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
        return await self._run_db(self._find_npcs_in_room_sync, room_identifier)

    def _find_npcs_in_room_sync(self, room_identifier: str) -> list[dict[str, Any]]:
        """Synchronous implementation of find_npcs_in_room."""
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
        return await self._run_db(self._find_room_with_npc_sync, npc_name)

    def _find_room_with_npc_sync(self, npc_name: str) -> dict[str, Any] | None:
        """Synchronous implementation of find_room_with_npc."""
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

    async def find_path_between_rooms(
        self, start_room_id: int, end_room_identifier: int | str, max_depth: int = 1000
    ) -> dict[str, Any] | None:
        return await self._run_db(self._find_path_between_rooms_sync, start_room_id, end_room_identifier, max_depth)

    def _find_path_between_rooms_sync(
        self, start_room_id: int, end_room_identifier: int | str, max_depth: int = 1000
    ) -> dict[str, Any] | None:
        if not self._initialized:
             self.logger.error("Cannot find path: Knowledge graph not initialized.")
             return None

        try:
            if isinstance(end_room_identifier, int):
                end_room_id = end_room_identifier
            else:
                try:
                    end_room_id = int(end_room_identifier)
                except (ValueError, TypeError):
                    room = Room.get(fn.LOWER(Room.full_name).contains(str(end_room_identifier).lower()))
                    end_room_id = room.room_number

            path = find_path_between_rooms(from_room=start_room_id, to_room_number=end_room_id, max_depth=max_depth)
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

    async def get_knowledge_graph_summary(self) -> dict[str, Any]:
        """Get a summary of the knowledge graph.

        This method provides a high-level overview of the knowledge graph contents,
        including counts of entities by type and relations by type.

        Returns:
            Dict[str, Any]: A summary of the knowledge graph
        """
        return await self._run_db(self._get_knowledge_graph_summary_sync)

    def _get_knowledge_graph_summary_sync(self) -> dict[str, Any]:
        """Synchronous implementation of get_knowledge_graph_summary."""
        if not self._initialized:
             return {
                "error": "Knowledge graph not initialized",
                "total_entities": 0,
                "total_relations": 0,
                "entity_types": {},
                "relation_types": {},
            }

        try:
            # Count entities by type using SQL
            entity_counts = {}
            query = Entity.select(Entity.entity_type, fn.COUNT(Entity.id).alias('count')).group_by(Entity.entity_type)
            for row in query:
                entity_counts[row.entity_type] = row.count

            # Count relations by type using SQL
            relation_counts = {}
            query = Relation.select(Relation.relation_type, fn.COUNT(Relation.id).alias('count')).group_by(Relation.relation_type)
            for row in query:
                relation_counts[row.relation_type] = row.count

            total_entities = sum(entity_counts.values())
            total_relations = sum(relation_counts.values())

            # Create summary
            summary = {
                "total_entities": total_entities,
                "total_relations": total_relations,
                "entity_types": entity_counts,
                "relation_types": relation_counts,
            }

            self.logger.info(
                f"Knowledge graph summary: {total_entities} entities, "
                f"{total_relations} relations"
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
        return await self._run_db(self._search_nodes_sync, query)

    def _search_nodes_sync(self, search_query: str) -> dict[str, Any]:
        """Synchronous implementation of search_nodes."""
        if not self._initialized:
             self.logger.error("Cannot search nodes: Knowledge graph not initialized.")
             return {"nodes": []}

        try:
            # Search entity names and types
            results = []
            # Use ILIKE for case-insensitive search if Postgres, else LIKE
            # Peewee handles generic 'contains' which maps to LIKE/GLOB usually
            # We use fn.LOWER for cross-db case-insensitive check
            entities = Entity.select().where(
                (fn.LOWER(Entity.name).contains(search_query.lower())) |
                (fn.LOWER(Entity.entity_type).contains(search_query.lower()))
            )

            for entity in entities:
                obs_list = [obs.observation_text for obs in entity.observations]
                results.append(
                    {
                        "name": entity.name,
                        "entityType": entity.entity_type,
                        "observations": obs_list,
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
        return await self._run_db(self._open_nodes_sync, names)

    def _open_nodes_sync(self, names: list[str]) -> dict[str, Any]:
        """Synchronous implementation of open_nodes."""
        if not self._initialized:
             self.logger.error("Cannot open nodes: Knowledge graph not initialized.")
             return {"nodes": []}

        try:
            results = []
            entities = Entity.select().where(Entity.name.in_(names))

            for entity in entities:
                obs_list = [obs.observation_text for obs in entity.observations]
                results.append(
                    {
                        "name": entity.name,
                        "entityType": entity.entity_type,
                        "observations": obs_list,
                    }
                )

            return {"nodes": results}
        except Exception as e:
            self.logger.error(f"Error opening nodes: {e}", exc_info=True)
            return {"nodes": []}

    # Legacy/unused methods removed or stubbed
    async def get_world_map(self) -> str:
        """Get a merged map of all explored rooms.
        Not implemented for DB yet.
        """
        return "World map generation from DB Not Implemented Yet."

    async def add_observations(self, data: dict[str, Any]) -> dict[str, Any]:
        self.logger.warning("add_observations not implemented for DB")
        return {"success": False}

    async def delete_observations(self, data: dict[str, Any]) -> dict[str, Any]:
        self.logger.warning("delete_observations not implemented for DB")
        return {"success": False}

    async def delete_entities(self, data: dict[str, Any]) -> dict[str, Any]:
        self.logger.warning("delete_entities not implemented for DB")
        return {"success": False}

    async def delete_relations(self, data: dict[str, Any]) -> dict[str, Any]:
        self.logger.warning("delete_relations not implemented for DB")
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
