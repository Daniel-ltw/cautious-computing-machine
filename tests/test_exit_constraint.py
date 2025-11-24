
import pytest
from peewee import SqliteDatabase, IntegrityError
from mud_agent.db.models import Room, RoomExit, Entity, ALL_MODELS

# Use an in-memory database for testing
test_db = SqliteDatabase(':memory:')

@pytest.fixture
def test_database():
    test_db.bind(ALL_MODELS, bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables(ALL_MODELS)
    yield test_db
    test_db.drop_tables(ALL_MODELS)
    test_db.close()

def test_multiple_exits_to_same_room(test_database):
    """Test creating multiple exits to the same room with different directions."""

    # Create Room 1
    r1_entity = Entity.create(name="1", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=1, zone="Test")

    # Create Room 2
    r2_entity = Entity.create(name="2", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=2, zone="Test")

    # Create first exit "north" -> Room 2
    RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="north"
    )

    # Create second exit "enter portal" -> Room 2
    # This should FAIL if there is a unique constraint on (from_room, to_room_number)
    try:
        RoomExit.create(
            from_room=r1,
            to_room=r2,
            to_room_number=2,
            direction="enter portal"
        )
    except IntegrityError:
        pytest.fail("IntegrityError raised! Cannot create multiple exits to the same room.")
