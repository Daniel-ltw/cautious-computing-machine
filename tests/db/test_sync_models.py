import tempfile
from pathlib import Path

import pytest
from peewee import SqliteDatabase

from mud_agent.db.sync_models import (
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
    REMOTE_ALL_MODELS,
    create_remote_db,
)


@pytest.fixture
def remote_test_db():
    """Create a temporary database simulating a remote DB."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        path = tmp.name
    test_db = SqliteDatabase(path)
    for model in REMOTE_ALL_MODELS:
        model._meta.database = test_db
    test_db.connect()
    test_db.create_tables(REMOTE_ALL_MODELS)
    yield test_db
    test_db.drop_tables(REMOTE_ALL_MODELS)
    test_db.close()
    Path(path).unlink()


def test_remote_models_have_sync_columns(remote_test_db):
    """Remote models should have sync_status and remote_updated_at."""
    entity = RemoteEntity.create(name="Test", entity_type="Room", sync_status="synced")
    assert entity.sync_status == "synced"


def test_create_remote_db_returns_database():
    """create_remote_db should return a Peewee database instance."""
    db = create_remote_db("sqlite:///tmp/test_remote.db")
    assert db is not None


def test_remote_room_schema(remote_test_db):
    """Remote Room model should have all expected fields."""
    entity = RemoteEntity.create(name="100", entity_type="Room")
    room = RemoteRoom.create(
        entity=entity, room_number=100, terrain="city", zone="Midgaard"
    )
    assert room.room_number == 100
    assert room.zone == "Midgaard"
