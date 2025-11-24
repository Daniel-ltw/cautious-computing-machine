
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from peewee import SqliteDatabase
from mud_agent.db.models import Room, RoomExit, Entity, find_path_between_rooms, ALL_MODELS
# Import GameKnowledgeGraph but we will patch the db it uses
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph

# Use an in-memory database for testing
test_db_instance = SqliteDatabase(':memory:')

@pytest.fixture
def test_database():
    # Bind models to test database
    test_db_instance.bind(ALL_MODELS, bind_refs=False, bind_backrefs=False)
    test_db_instance.connect()
    test_db_instance.create_tables(ALL_MODELS)

    # Patch db in models and game_knowledge_graph
    # We need to patch where it is imported/used
    p1 = patch('mud_agent.db.models.db', test_db_instance)
    p2 = patch('mud_agent.mcp.game_knowledge_graph.db', test_db_instance)

    # Patch DatabaseContext to prevent closing the in-memory db
    class MockContext:
        def __enter__(self):
            return None
        def __exit__(self, *args):
            pass

    p3 = patch('mud_agent.db.models.DatabaseContext', MockContext)

    p1.start()
    p2.start()
    p3.start()

    yield test_db_instance

    p1.stop()
    p2.stop()
    p3.stop()

    test_db_instance.drop_tables(ALL_MODELS)
    test_db_instance.close()

@pytest.fixture
def knowledge_graph(test_database):
    # We don't need async fixture here if we just instantiate it
    kg = GameKnowledgeGraph()
    kg._initialized = True
    return kg

def test_pathfinding_uses_move_command(test_database):
    """Test that pathfinding uses the recorded move_command."""

    # Create Room 1
    r1_entity = Entity.create(name="1", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=1, zone="Test")

    # Create Room 2
    r2_entity = Entity.create(name="2", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=2, zone="Test")

    # Create Exit from 1 to 2 with direction "portal"
    exit_obj = RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="portal"
    )

    # Record a successful move with "enter portal"
    # This sets the move_command in the details JSON
    exit_obj.record_exit_success(move_command="enter portal", pre_commands=["unlock portal"])

    # Find path
    path = find_path_between_rooms(from_room=1, to_room_number=2)

    # Verify path uses "enter portal" (and pre-commands)
    assert "enter portal" in path
    assert "unlock portal" in path
    assert path == ["unlock portal", "enter portal"]

@pytest.mark.asyncio
async def test_record_exit_success_matches_portal(knowledge_graph, test_database):
    """Test that record_exit_success matches 'enter portal' to exit 'portal'."""

    # Create Room 1
    r1_entity = Entity.create(name="1", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=1, zone="Test")

    # Create Room 2
    r2_entity = Entity.create(name="2", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=2, zone="Test")

    # Create Exit from 1 to 2 with direction "portal" (simulating what the mapper might see)
    exit_obj = RoomExit.create(
        from_room=r1,
        to_room=r2,
        to_room_number=2,
        direction="portal"
    )

    # Record success with "enter portal"
    await knowledge_graph.record_exit_success(
        from_room_num=1,
        to_room_num=2,
        direction="enter portal",
        move_cmd="enter portal",
        pre_cmds=[]
    )

    # Verify we didn't create a duplicate exit
    exits = list(r1.exits)
    assert len(exits) == 1

    # Verify the exit details were updated
    updated_exit = exits[0]
    details = updated_exit.get_command_details()
    assert details["move_command"] == "enter portal"
