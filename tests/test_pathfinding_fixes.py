
import tempfile
from pathlib import Path

import pytest
from mud_agent.db.models import Room, RoomExit, Entity, find_path_between_rooms, ALL_MODELS
from mud_agent.db.models import db as peewee_db
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph


@pytest.fixture
def test_database():
    # Use a temp file so that asyncio.to_thread can access the same DB
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    test_db_path = tmp.name
    tmp.close()

    peewee_db.init(test_db_path)
    peewee_db.connect()
    peewee_db.create_tables(ALL_MODELS)

    yield peewee_db

    peewee_db.drop_tables(ALL_MODELS)
    peewee_db.close()
    Path(test_db_path).unlink(missing_ok=True)

@pytest.fixture
def knowledge_graph(test_database):
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
