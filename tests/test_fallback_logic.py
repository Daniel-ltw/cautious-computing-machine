
import pytest
from unittest.mock import MagicMock, patch
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph
from mud_agent.db.models import Room, RoomExit, Entity, ALL_MODELS
from peewee import SqliteDatabase, IntegrityError

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

@pytest.mark.asyncio
@patch('mud_agent.mcp.game_knowledge_graph.db', new=test_db)
@patch('mud_agent.db.models.db', new=test_db)
async def test_record_exit_success_fallback(test_database):
    """Test that record_exit_success falls back to updating existing exit on error."""

    graph = GameKnowledgeGraph()
    graph._initialized = True # Skip async init

    # Create Room 1
    r1_entity = Entity.create(name="1", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=1, zone="Test")

    # Create Room 2
    r2_entity = Entity.create(name="2", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=2, zone="Test")

    # Create existing exit "north" -> Room 2
    exit_north = RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="north"
    )

    # Mock get_or_create_exit to raise IntegrityError
    # This simulates the scenario where creating "enter portal" fails
    with patch.object(graph, 'get_or_create_exit', side_effect=IntegrityError("Mocked IntegrityError")):
        # Try to record "enter portal" -> Room 2
        # This should trigger the fallback and update "north" exit
        await graph.record_exit_success(
            from_room_num=1,
            to_room_num=2,
            direction="enter portal",
            move_cmd="enter portal"
        )

    # Verify that "north" exit was updated
    exit_north = RoomExit.get_by_id(exit_north.id)
    details = exit_north.get_command_details()
    assert details.get("move_command") == "enter portal"
    assert "north" == exit_north.direction # Direction should NOT change
