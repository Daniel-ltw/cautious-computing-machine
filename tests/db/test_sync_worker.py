"""Tests for the SyncWorker push/pull logic.

Uses two SQLite databases to simulate local and remote.
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from peewee import SqliteDatabase

from mud_agent.db.models import (
    ALL_MODELS,
    Entity,
    Room,
    RoomExit,
    db as local_db,
)
from mud_agent.db.sync_models import (
    REMOTE_ALL_MODELS,
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
)
from mud_agent.db.sync_worker import SyncWorker


@pytest.fixture
def local_test_db():
    """Set up local SQLite DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    local_db.init(path)
    local_db.connect()
    local_db.create_tables(ALL_MODELS)
    yield local_db
    local_db.drop_tables(ALL_MODELS)
    local_db.close()
    Path(path).unlink()


@pytest.fixture
def remote_test_db():
    """Set up remote SQLite DB simulating Supabase."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    remote_db = SqliteDatabase(path)
    for model in REMOTE_ALL_MODELS:
        model._meta.database = remote_db
    remote_db.connect()
    remote_db.create_tables(REMOTE_ALL_MODELS)
    yield remote_db
    remote_db.drop_tables(REMOTE_ALL_MODELS)
    remote_db.close()
    Path(path).unlink()


@pytest.fixture
def sync_worker(local_test_db, remote_test_db):
    """Create a SyncWorker with test databases."""
    worker = SyncWorker(sync_interval=1.0)
    worker._remote_db = remote_test_db
    return worker


def test_push_dirty_entities(sync_worker, local_test_db, remote_test_db):
    """Dirty local entities should be pushed to remote."""
    # Create a dirty entity locally
    entity = Entity.create(name="100", entity_type="Room")
    assert entity.sync_status == "dirty"

    # Push
    sync_worker.push()

    # Verify it arrived remotely
    remote_entity = RemoteEntity.get_or_none(RemoteEntity.name == "100")
    assert remote_entity is not None
    assert remote_entity.entity_type == "Room"

    # Verify local is now synced
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "synced"


def test_push_dirty_rooms_with_exits(sync_worker, local_test_db, remote_test_db):
    """Dirty rooms and their exits should be pushed."""
    entity = Entity.create(name="200", entity_type="Room")
    room = Room.create(entity=entity, room_number=200, zone="TestArea", terrain="city")

    entity2 = Entity.create(name="201", entity_type="Room")
    room2 = Room.create(entity=entity2, room_number=201, zone="TestArea", terrain="city")

    RoomExit.create(from_room=room, direction="n", to_room=room2, to_room_number=201)

    sync_worker.push()

    remote_room = RemoteRoom.get_or_none(RemoteRoom.room_number == 200)
    assert remote_room is not None

    remote_exit = RemoteRoomExit.get_or_none(RemoteRoomExit.from_room == remote_room)
    assert remote_exit is not None
    assert remote_exit.direction == "n"
    assert remote_exit.to_room_number == 201


def test_push_skips_synced_records(sync_worker, local_test_db, remote_test_db):
    """Already-synced records should not be pushed again."""
    entity = Entity.create(name="300", entity_type="Room")
    Entity.update(sync_status="synced").where(Entity.id == entity.id).execute()

    sync_worker.push()

    remote_entity = RemoteEntity.get_or_none(RemoteEntity.name == "300")
    assert remote_entity is None  # Should not have been pushed


def test_pull_new_rooms_from_remote(sync_worker, local_test_db, remote_test_db):
    """Rooms created on remote (by a friend) should appear locally after pull."""
    # Simulate friend adding a room on remote
    remote_entity = RemoteEntity.create(name="500", entity_type="Room", sync_status="synced")
    RemoteRoom.create(
        entity=remote_entity, room_number=500, zone="FriendZone",
        terrain="forest", sync_status="synced"
    )

    sync_worker.pull()

    local_entity = Entity.get_or_none(Entity.name == "500")
    assert local_entity is not None

    local_room = Room.get_or_none(Room.room_number == 500)
    assert local_room is not None
    assert local_room.zone == "FriendZone"
    assert local_room.sync_status == "synced"


def test_pull_new_exits_from_remote(sync_worker, local_test_db, remote_test_db):
    """Exits discovered by a friend should be merged locally."""
    # Set up local room (already exists)
    local_entity = Entity.create(name="600", entity_type="Room")
    local_room = Room.create(entity=local_entity, room_number=600, zone="Shared")
    Entity.update(sync_status="synced").where(Entity.id == local_entity.id).execute()
    Room.update(sync_status="synced").where(Room.id == local_room.id).execute()

    local_entity2 = Entity.create(name="601", entity_type="Room")
    local_room2 = Room.create(entity=local_entity2, room_number=601, zone="Shared")
    Entity.update(sync_status="synced").where(Entity.id == local_entity2.id).execute()
    Room.update(sync_status="synced").where(Room.id == local_room2.id).execute()

    # Friend discovers an exit on remote that we don't have
    remote_entity = RemoteEntity.create(name="600", entity_type="Room", sync_status="synced")
    remote_room = RemoteRoom.create(
        entity=remote_entity, room_number=600, zone="Shared", sync_status="synced"
    )
    remote_entity2 = RemoteEntity.create(name="601", entity_type="Room", sync_status="synced")
    remote_room2 = RemoteRoom.create(
        entity=remote_entity2, room_number=601, zone="Shared", sync_status="synced"
    )
    RemoteRoomExit.create(
        from_room=remote_room, direction="e", to_room=remote_room2,
        to_room_number=601, sync_status="synced"
    )

    sync_worker.pull()

    # Verify exit now exists locally
    local_exit = RoomExit.get_or_none(
        (RoomExit.from_room == local_room) & (RoomExit.direction == "e")
    )
    assert local_exit is not None
    assert local_exit.to_room_number == 601


def test_merge_dirty_local_with_remote_update(sync_worker, local_test_db, remote_test_db):
    """When local is dirty and remote has updates, merge should combine data."""
    # Local room with dirty status
    local_entity = Entity.create(name="700", entity_type="Room")
    local_room = Room.create(
        entity=local_entity, room_number=700, zone="LocalZone", terrain="city"
    )
    # It's dirty because save() sets it

    # Remote has newer terrain info
    remote_entity = RemoteEntity.create(name="700", entity_type="Room", sync_status="synced")
    from datetime import timedelta
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    RemoteRoom.create(
        entity=remote_entity, room_number=700, zone="LocalZone",
        terrain="forest", sync_status="synced", updated_at=future_time
    )

    sync_worker.pull()

    # Local should have merged — remote terrain wins (newer)
    local_room = Room.get(Room.room_number == 700)
    assert local_room.terrain == "forest"
    # But still dirty because local had changes
    assert local_room.sync_status == "dirty"
