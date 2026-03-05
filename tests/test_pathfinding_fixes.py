
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


@pytest.mark.asyncio
async def test_find_path_with_zone_filter(knowledge_graph, test_database):
    """Zone filter constrains room lookup by name to rooms in the specified zone."""

    # Create Room 100 in ZoneA
    r1_entity = Entity.create(name="100", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=100, zone="ZoneA", full_name="Market Square")

    # Create Room 200 in ZoneB with the SAME room name
    r2_entity = Entity.create(name="200", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=200, zone="ZoneB", full_name="Market Square")

    # Create Room 101 in ZoneA connected to Room 100
    r3_entity = Entity.create(name="101", entity_type="Room")
    r3 = Room.create(entity=r3_entity, room_number=101, zone="ZoneA")
    RoomExit.create(from_room=r3, to_room=r1, to_room_number=100, direction="n")

    # Without zone filter — could match either room (nondeterministic)
    # With zone filter "ZoneA" — must match room 100
    result = await knowledge_graph.find_path_between_rooms(
        start_room_id=101, end_room_identifier="Market Square", zone="ZoneA"
    )
    assert result is not None
    assert result["path"] == ["n"]

    # With zone filter "ZoneB" — must match room 200 (no path from 101)
    result_b = await knowledge_graph.find_path_between_rooms(
        start_room_id=101, end_room_identifier="Market Square", zone="ZoneB"
    )
    assert result_b is None  # No path from 101 to 200


@pytest.mark.asyncio
async def test_find_path_without_zone_filter(knowledge_graph, test_database):
    """Without zone filter, room lookup by name finds any matching room."""

    r1_entity = Entity.create(name="300", entity_type="Room")
    r1 = Room.create(entity=r1_entity, room_number=300, zone="SomeZone", full_name="Tavern")

    r2_entity = Entity.create(name="301", entity_type="Room")
    r2 = Room.create(entity=r2_entity, room_number=301, zone="SomeZone")
    RoomExit.create(from_room=r2, to_room=r1, to_room_number=300, direction="e")

    # No zone filter — should still find the room
    result = await knowledge_graph.find_path_between_rooms(
        start_room_id=301, end_room_identifier="Tavern"
    )
    assert result is not None
    assert result["path"] == ["e"]
