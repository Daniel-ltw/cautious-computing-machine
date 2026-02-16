
import tempfile
from pathlib import Path

import pytest
from mud_agent.db.models import Room, RoomExit, Entity, ALL_MODELS
from mud_agent.db.models import db as peewee_db


@pytest.fixture
def test_database():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name
    peewee_db.init(test_db_path)
    peewee_db.connect()
    peewee_db.create_tables(ALL_MODELS)
    yield peewee_db
    peewee_db.drop_tables(ALL_MODELS)
    peewee_db.close()
    Path(test_db_path).unlink(missing_ok=True)

def test_multiple_exits_to_same_room(test_database):
    """Test that multiple exits to the same destination are correctly handled via upsert/update."""

    # Create Room 1
    r1_entity = Entity.create(name="1", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=1, zone="Test")

    # Create Room 2
    r2_entity = Entity.create(name="2", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=2, zone="Test")

    # Create first exit "north" -> Room 2
    exit1 = RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="north"
    )

    # Try to create second exit "enter portal" -> Room 2
    # This should SUCCEED now that we allow multiple exits to the same room (aliases)
    # as long as the direction string is different.
    exit2 = RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="enter portal"
    )

    assert exit2.id != exit1.id
    assert exit2.direction == "enter portal"
    assert exit2.to_room_number == 2
