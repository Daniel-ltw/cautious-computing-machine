"""Peewee ORM models for the MUD Agent knowledge graph.

This module defines the database schema for migrating from JSON-based
knowledge graph to SQLite using Peewee ORM.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from peewee import (
    SQL,
    BooleanField,
    CharField,
    DateTimeField,
    DoesNotExist,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = Path.cwd() / ".mcp" / "knowledge_graph.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Always use local SQLite for speed. Supabase sync is handled by SyncWorker.
logger.info(f"Using SQLite database at {DB_PATH}")
db = SqliteDatabase(str(DB_PATH), pragmas={
    'journal_mode': 'wal',
    'busy_timeout': 30000,  # Wait up to 30s for locks (SyncWorker may hold writes)
})


class BaseModel(Model):
    """Base model with common fields and database configuration."""

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    sync_status = CharField(max_length=10, default="dirty")
    remote_updated_at = DateTimeField(null=True, default=None)

    class Meta:
        database = db

    def save(self, *args, **kwargs):
        """Override save to update the updated_at timestamp and mark as dirty."""
        self.updated_at = datetime.now()
        self.sync_status = "dirty"
        return super().save(*args, **kwargs)

    def get_natural_key(self) -> dict | None:
        """Return the natural key dict for this record, used for delete sync.

        Subclasses should override this if the default (id-based) is insufficient.
        Returns None if no natural key can be determined.
        """
        return None

    def delete_instance(self, *args, **kwargs):
        """Override to log the delete for sync before actually deleting."""
        natural_key = self.get_natural_key()
        if natural_key is not None:
            try:
                SyncDelete.create(
                    table_name_field=self._meta.table_name,
                    natural_key=json.dumps(natural_key),
                )
            except Exception as e:
                logger.warning(f"Failed to log delete for sync: {e}")
        return super().delete_instance(*args, **kwargs)


class Entity(BaseModel):
    """Core entity table for both rooms and NPCs."""

    name = CharField(max_length=200, index=True)
    entity_type = CharField(max_length=20, index=True)  # 'Room' or 'NPC'

    class Meta:
        indexes = (
            # Composite index for type-based queries
            (('entity_type', 'name'), False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the entity to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def get_natural_key(self) -> dict | None:
        return {"name": self.name, "entity_type": self.entity_type}

    def __str__(self):
        return f"{self.entity_type}: {self.name}"


class Room(BaseModel):
    """Room-specific data table."""

    entity = ForeignKeyField(Entity, backref='room_data', unique=True)
    room_number = IntegerField(unique=True, index=True)
    terrain = CharField(max_length=50, null=True, index=True)
    zone = CharField(max_length=100, null=True, index=True)
    full_name = CharField(max_length=200, null=True)
    outside = BooleanField(default=False, index=True)

    # Coordinates (if available)
    coord_x = IntegerField(null=True)
    coord_y = IntegerField(null=True)
    coord_z = IntegerField(null=True)

    # Room details (for shop detection, etc.)
    details = TextField(null=True)

    class Meta:
        indexes = (
            # Spatial index for coordinate-based queries
            (('coord_x', 'coord_y', 'coord_z'), False),
            # Zone-based queries
            (('zone', 'terrain'), False),
        )

    def get_natural_key(self) -> dict | None:
        return {"room_number": self.room_number}

    def __str__(self):
        return f"Room {self.room_number}: {self.entity.name}"

    @classmethod
    def create_or_update_from_dict(cls, data: dict[str, Any]) -> Optional["Room"]:
        """Create or update a room from a dictionary using a more robust method.

        Returns:
            The Room object if successful, otherwise None.
        """
        logger.debug(f"Attempting to create or update room with data: {data}")

        room_number = data.get("room_number") or data.get("num")
        if not room_number:
            logger.error("Failed to create or update room: 'num' is missing.")
            return None

        name = data.get("name")
        if not name:
            logger.error("Failed to create or update room: 'name' is missing.")
            return None

        # Transaction 1: upsert the room itself (short write lock)
        with db.atomic():
            entity, _ = Entity.get_or_create(
                name=str(room_number),
                defaults={"entity_type": "Room"}
            )

            room, created = cls.get_or_create(
                entity=entity,
                room_number=int(room_number),
            )

            room_data = {
                "terrain": data.get("terrain", room.terrain),
                "zone": data.get("zone", room.zone or "unknown"),
                "full_name": data.get("full_name", data.get("name")) or room.full_name,
                "outside": data.get("outside", False),
                "coord_x": data.get("coord", {"x": room.coord_x}).get("x"),
                "coord_y": data.get("coord", {"y": room.coord_y}).get("y"),
                "coord_z": data.get("coord", {"z": room.coord_z}).get("z", 0),
                "details": data.get("details"),
            }

            if not created:
                for key, value in room_data.items():
                    if value is not None:
                        setattr(room, key, value)
                room.save()

        # Transaction 2+: upsert each exit individually so the write lock
        # is held only briefly per exit rather than across all of them.
        exits = data.get("exits")
        logger.debug(f"Processing exits for room {room_number}: {exits}")
        if exits:
            for direction, exit_info in exits.items():
                with db.atomic():
                    is_door = isinstance(exit_info, dict)
                    to_room_num = exit_info.get("num") if is_door else exit_info

                    exit_instance, exit_created = RoomExit.get_or_create(
                        from_room=room,
                        to_room_number=to_room_num,
                        defaults={
                            "direction": direction,
                            "is_door": is_door,
                            "door_is_closed": exit_info.get("state") == "closed" if is_door else False,
                        }
                    )

                    if not exit_created:
                        if exit_instance.direction != direction:
                            exit_instance.direction = direction
                        if exit_instance.is_door != is_door:
                            exit_instance.is_door = is_door
                        if is_door and exit_instance.door_is_closed != (exit_info.get("state") == "closed"):
                            exit_instance.door_is_closed = exit_info.get("state") == "closed"
                        exit_instance.save()

                    if to_room_num is not None:
                        try:
                            target_room = Room.select().where(Room.room_number == int(to_room_num)).get()
                            if exit_instance.to_room != target_room:
                                exit_instance.to_room = target_room
                                exit_instance.save()
                        except DoesNotExist:
                            pass

        return room

    def to_info(self):
        exits = {exit.direction.lower(): exit.to_room_number for exit in self.exits}
        npcs = [npc.entity.name for npc in self.npcs]
        return {
            "num": self.room_number,
            "name": self.full_name or self.entity.name,
            "area": self.zone,
            "terrain": self.terrain,
            "symbol": "●",
            "exits": exits,
            "npcs": npcs,
            "details": self.details,
        }


class RoomExit(BaseModel):
    """Normalized room exit data."""

    from_room = ForeignKeyField(Room, backref='exits')
    direction = CharField(max_length=20, index=True)  # n, s, e, w, u, d
    to_room_number = IntegerField(index=True, null=True)
    is_door = BooleanField(default=False)
    door_is_closed = BooleanField(default=False)
    to_room = ForeignKeyField(Room, backref='entrances', null=True)  # May be null if target room not loaded

    # Exit details (door status, etc.)
    details = TextField(null=True)  # JSON string for additional exit info

    class Meta:
        indexes = (
            # Unique constraint on from_room + direction (correct MUD design)
            (('from_room', 'direction'), True),
            # Index for reverse lookups
            (('to_room_number', 'direction'), False),
        )

    def get_natural_key(self) -> dict | None:
        try:
            return {"from_room_number": self.from_room.room_number, "direction": self.direction}
        except Exception:
            return None

    def __str__(self):
        return f"Room {self.from_room.room_number} -> {self.direction} -> {self.to_room_number}"

    # --- Exit command memory helpers ---
    def get_command_details(self) -> dict[str, Any]:
        """Return parsed JSON details for exit command sequence.

        Keys:
        - move_command: str or None
        - pre_commands: list[str]
        - last_success_at: float (epoch seconds) or None
        - source: str (e.g., 'observed')
        """
        try:
            data = json.loads(self.details) if self.details else {}
            if not isinstance(data, dict):
                # If malformed, start fresh
                data = {}

            # Ensure all keys are present with sensible defaults
            return {
                "move_command": data.get("move_command"),
                "pre_commands": data.get("pre_commands") or [],
                "last_success_at": data.get("last_success_at"),
                "source": data.get("source"),
            }
        except (json.JSONDecodeError, TypeError):
            # If malformed or not a string, start fresh
            return {
                "move_command": None,
                "pre_commands": [],
                "last_success_at": None,
                "source": None,
            }

    def record_exit_success(
        self,
        move_command: str | None,
        pre_commands: list[str] | None = None,
        source: str = "observed",
        force: bool = False,
    ) -> None:
        """Record a successful traversal for this exit.

        Updates JSON details with the provided command sequence and timestamp.
        """
        details_dict = self.get_command_details()

        def _norm(s: str | None) -> str:
            s = (s or "").strip().lower()
            mapping = {
                "north": "n", "south": "s", "east": "e", "west": "w", "up": "u", "down": "d",
                "n": "n", "s": "s", "e": "e", "w": "w", "u": "u", "d": "d",
            }
            if s.startswith("say "):
                return "say"
            if s.startswith("enter "):
                return "enter"
            if s.startswith("board"):
                return "board"
            if s.startswith("escape"):
                return "escape"
            return mapping.get(s, s)

        norm_dir = _norm(self.direction)
        norm_cmd = _norm(move_command)

        # Allow match if normalized forms match OR if the command ends with the direction
        # e.g. direction="portal", move_command="enter portal" -> norm_dir="portal", norm_cmd="enter" -> mismatch
        # but "enter portal".endswith("portal") -> match
        if not force and norm_dir != norm_cmd and not move_command.strip().lower().endswith(self.direction.strip().lower()):
            return

        if self.from_room and self.from_room.zone:
            # Check if this command is already used by another exit in the same area
            try:
                # Define standard directions to exclude from collision checks
                STANDARD_DIRECTIONS = {
                    "n", "s", "e", "w", "u", "d",
                    "north", "south", "east", "west", "up", "down"
                }

                # We need to fetch all exits in the area and check in python to handle normalization logic correctly
                area_exits = (RoomExit
                            .select()
                            .join(Room, on=(RoomExit.from_room == Room.id))
                            .where(
                                (Room.zone == self.from_room.zone) &
                                (RoomExit.direction.not_in(STANDARD_DIRECTIONS))
                            ))

                for exit in area_exits:
                    if exit.id == self.id:
                        continue
                    other_details = exit.get_command_details()
                    other_move = other_details.get("move_command")
                    if other_move and other_move.strip().lower() == move_command.strip().lower():
                        logger.info(f"Skipping save: Command '{move_command}' already used in area '{self.from_room.zone}' by exit from room {exit.from_room.room_number}")
                        return
            except Exception as e:
                logger.error(f"Error checking for duplicate area commands: {e}", exc_info=True)

        details_dict["move_command"] = move_command
        details_dict["pre_commands"] = pre_commands or []
        details_dict["last_success_at"] = datetime.now(timezone.utc).isoformat()
        details_dict["source"] = source

        self.details = json.dumps(details_dict)
        logger.info(f"Saving details for exit {self.id}: {self.details}")
        self.save()


class NPC(BaseModel):
    """NPC-specific data table."""

    entity = ForeignKeyField(Entity, backref='npc_data')
    current_room = ForeignKeyField(Room, backref='npcs', null=True)

    # NPC classification
    npc_type = CharField(max_length=50, null=True, index=True)  # Questor, Shopkeeper, etc.

    # Additional NPC metadata can be added here as needed

    class Meta:
        indexes = (
            # Room-based NPC queries
            (('current_room', 'npc_type'), False),
        )
        constraints = [SQL('UNIQUE(entity_id, current_room_id)')]

    def get_natural_key(self) -> dict | None:
        try:
            room_number = self.current_room.room_number if self.current_room_id else None
            return {
                "entity_name": self.entity.name,
                "entity_type": self.entity.entity_type,
                "room_number": room_number,
            }
        except Exception:
            return None

    def __str__(self):
        room_info = f" in room {self.current_room.room_number}" if self.current_room else ""
        return f"NPC: {self.entity.name}{room_info}"

    @classmethod
    def create_or_update_from_dict(cls, data: dict[str, Any], current_room: Optional["Room"] = None) -> "NPC":
        """Create or update an NPC from a dictionary."""
        npc_name = data.get("name")
        if not npc_name:
            raise ValueError("name is required for NPC")

        with db.atomic():
            # Create or update the associated Entity
            entity, _ = Entity.get_or_create(
                name=npc_name,
                defaults={"entity_type": "NPC"}
            )

            npc_data = {
                "npc_type": data.get("npc_type", "unknown"),
            }

            # Try to get the NPC, if it exists, update it. Otherwise, create it.
            npc, created = cls.get_or_create(
                entity=entity,
                current_room=current_room,
                defaults=npc_data
            )

            return npc


class Observation(BaseModel):
    """Flexible observation storage for both rooms and NPCs."""

    entity = ForeignKeyField(Entity, backref='observations')
    observation_text = TextField()
    observation_type = CharField(max_length=50, default='general', index=True)

    class Meta:
        indexes = (
            # Entity-based observation queries
            (('entity', 'created_at'), False),
            # Type-based queries
            (('observation_type', 'created_at'), False),
        )

    def get_natural_key(self) -> dict | None:
        try:
            return {
                "entity_name": self.entity.name,
                "entity_type": self.entity.entity_type,
                "observation_type": self.observation_type,
                "observation_text": self.observation_text[:100],
            }
        except Exception:
            return None

    def __str__(self):
        return f"Observation for {self.entity.name}: {self.observation_text[:50]}..."


class Relation(BaseModel):
    """Generic relationship storage between entities."""

    from_entity = ForeignKeyField(Entity, backref='outgoing_relations')
    to_entity = ForeignKeyField(Entity, backref='incoming_relations')
    relation_type = CharField(max_length=100, index=True)

    # Additional relation metadata
    metadata = TextField(null=True)  # JSON string for additional relation info

    class Meta:
        indexes = (
            # Unique constraint on from_entity + to_entity + relation_type
            (('from_entity', 'to_entity', 'relation_type'), True),
            # Reverse lookup index
            (('to_entity', 'relation_type'), False),
            # Type-based queries
            (('relation_type', 'created_at'), False),
        )

    def get_natural_key(self) -> dict | None:
        try:
            return {
                "from_entity_name": self.from_entity.name,
                "from_entity_type": self.from_entity.entity_type,
                "to_entity_name": self.to_entity.name,
                "to_entity_type": self.to_entity.entity_type,
                "relation_type": self.relation_type,
            }
        except Exception:
            return None

    def __str__(self):
        return f"{self.from_entity.name} --{self.relation_type}--> {self.to_entity.name}"


class SyncDelete(Model):
    """Log of deleted records for bidirectional sync.

    When a record is deleted locally (via delete_instance), a row is inserted here
    so the SyncWorker can propagate the delete to the remote database.
    The remote side uses Postgres triggers to populate its own sync_deletes table.
    """

    table_name_field = CharField(max_length=50)
    natural_key = TextField()  # JSON string, e.g. {"room_number": 12345}
    deleted_at = DateTimeField(default=datetime.now)
    synced = BooleanField(default=False)

    class Meta:
        database = db
        table_name = "sync_deletes"


# Model registry for easy access
ALL_MODELS = [Entity, Room, RoomExit, NPC, Observation, Relation, SyncDelete]

def get_db_stats() -> dict[str, int]:
    """Get statistics about the database."""
    stats = {}
    for model in ALL_MODELS:
        stats[model.__name__] = model.select().count()
    return stats




def initialize_database():
    """Initialize the database and create all tables."""
    try:
        db.connect()
        db.create_tables(ALL_MODELS, safe=True)
        logger.info(f"Database initialized at {DB_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        return False
    finally:
        if not db.is_closed():
            db.close()


def get_database_stats() -> dict[str, int]:
    """Get statistics about the current database."""
    stats: dict[str, int] = {}
    try:
        for model in ALL_MODELS:
            stats[model.__name__] = model.select().count()
        return stats
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}", exc_info=True)
        return {}


def close_database():
    """Close the database connection."""
    if not db.is_closed():
        db.close()
        logger.debug("Database connection closed")


# Backward-compatible alias — use db.connection_context() instead, which
# reuses an already-open connection and only closes it if *it* opened one.
DatabaseContext = db.connection_context


# Utility functions for common queries
def get_room_by_number(room_number: int) -> Room | None:
    """Get a room by its room number."""
    try:
        with db.connection_context():
            return Room.select().join(Entity).where(Room.room_number == room_number).get()
    except DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error getting room {room_number}: {e}", exc_info=True)
        return None


def get_entity_by_name(name: str, entity_type: str = None) -> Entity | None:
    """Get an entity by name and optionally by type."""
    try:
        with db.connection_context():
            query = Entity.select().where(Entity.name == name)
            if entity_type:
                query = query.where(Entity.entity_type == entity_type)
            return query.get()
    except DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error getting entity {name}: {e}", exc_info=True)
        return None


def get_room_exits(room_number: int) -> list[RoomExit]:
    """Get all exits for a room."""
    try:
        with db.connection_context():
            room = get_room_by_number(room_number)
            if not room:
                return []
            return list(room.exits)
    except Exception as e:
        logger.error(f"Error getting exits for room {room_number}: {e}", exc_info=True)
        return []


def find_path_between_rooms(from_room: int, to_room_number: int, max_depth: int = 20) -> list[str]:
    """Find a path between two rooms using BFS.

    Args:
        from_room: The room number of the starting room.
        to_room_number: The room number of the destination room.
        max_depth: The maximum depth to search.

    Returns:
        A list of directions to take from from_room to reach to_room.
    """
    try:
        with db.connection_context():
            # Simple BFS implementation
            from collections import deque

            queue = deque([(from_room, [])])
            visited = {from_room}

            dest_room = Room.select().join(Entity).where(Room.room_number == to_room_number).get()

            while queue and len(queue[0][1]) < max_depth:
                current_room, path = queue.popleft()

                if current_room == dest_room.room_number:
                    return path

                # Get exits from current room
                exits = RoomExit.select().join(Room, on=(RoomExit.from_room == Room.id)).where(Room.room_number == current_room)

                for exit in exits:
                    next_room = exit.to_room_number
                    if next_room is not None and next_room not in visited:
                        visited.add(next_room)
                        new_path = path[:]
                        command_details = exit.get_command_details()
                        if len(command_details.get("pre_commands")) > 0:
                            new_path.extend(command_details["pre_commands"])

                        # Use the recorded move command if available, otherwise fallback to direction
                        move_cmd = command_details.get("move_command")
                        if move_cmd:
                            new_path.append(move_cmd)
                        else:
                            new_path.append(exit.direction)

                        queue.append((next_room, new_path))

            return []  # No path found
    except Exception as e:
        logger.error(f"Error finding path from {from_room} to {to_room_number}: {e}", exc_info=True)
        return []
