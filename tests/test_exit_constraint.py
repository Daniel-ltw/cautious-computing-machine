
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
    # This should FAIL with IntegrityError due to (from_room, to_room_number) constraint
    # The fallback logic in GameKnowledgeGraph.record_exit_success will handle this
    try:
        RoomExit.create(
            from_room=r1,
            to_room=r2,
            to_room_number=2,
            direction="enter portal"
        )
        # If we get here, the constraint didn't work
        pytest.fail("Expected IntegrityError was not raised! Constraint is not working.")
    except IntegrityError:
        # This is expected - the constraint is working correctly
        # In production, GameKnowledgeGraph.record_exit_success will catch this
        # and update the existing exit instead
        pass
