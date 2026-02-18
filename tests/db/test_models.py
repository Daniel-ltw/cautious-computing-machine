import tempfile
from pathlib import Path

import pytest

from mud_agent.db.models import (
    ALL_MODELS,
    NPC,
    Entity,
    Observation,
    Relation,
    Room,
    RoomExit,
    db,
    find_path_between_rooms,
    get_database_stats,
    get_entity_by_name,
    get_room_by_number,
    get_room_exits,
)


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    db.init(test_db_path)
    db.connect()
    db.create_tables(ALL_MODELS)
    yield
    db.drop_tables(ALL_MODELS)
    db.close()
    Path(test_db_path).unlink()



def test_entity_creation(test_db):
    """Test Entity creation."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    assert room_entity.name == "Test Room"
    npc_entity = Entity.create(name="Test NPC", entity_type="NPC")
    assert npc_entity.name == "Test NPC"

def test_room_creation(test_db):
    """Test Room creation."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    test_room = Room.create(
        entity=room_entity,
        room_number=1001,
        terrain="inside",
        zone="Test Zone",
        full_name="A Test Room",
        outside=False,
        coord_x=10, coord_y=20, coord_z=0
    )
    assert test_room.room_number == 1001

def test_room_exit_creation(test_db):
    """Test RoomExit creation."""
    room_entity1 = Entity.create(name="Test Room 1", entity_type="Room")
    test_room1 = Room.create(entity=room_entity1, room_number=1001)
    room_entity2 = Entity.create(name="Test Room 2", entity_type="Room")
    test_room2 = Room.create(entity=room_entity2, room_number=1002)
    room_exit = RoomExit.create(
        from_room=test_room1,
        direction="north",
        to_room_number=1002,
        to_room=test_room2,
        details='{"door": "open"}'
    )
    assert room_exit.direction == "north"

def test_npc_creation(test_db):
    """Test NPC creation."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    test_room = Room.create(entity=room_entity, room_number=1001)
    npc_entity = Entity.create(name="Test NPC", entity_type="NPC")
    test_npc = NPC.create(
        entity=npc_entity,
        current_room=test_room,
        npc_type="questor"
    )
    assert test_npc.npc_type == "questor"

def test_observation_creation(test_db):
    """Test Observation creation."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    observation = Observation.create(
        entity=room_entity,
        observation_text="This is a test observation",
        observation_type="description"
    )
    assert observation.observation_type == "description"

def test_relation_creation(test_db):
    """Test Relation creation."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    npc_entity = Entity.create(name="Test NPC", entity_type="NPC")
    relation = Relation.create(
        from_entity=room_entity,
        to_entity=npc_entity,
        relation_type="contains",
        metadata='{"visible": true}'
    )
    assert relation.relation_type == "contains"

def test_query_functions(test_db):
    """Test query functions."""
    room_entity1 = Entity.create(name="Test Room 1", entity_type="Room")
    test_room1 = Room.create(entity=room_entity1, room_number=1001)
    room_entity2 = Entity.create(name="Test Room 2", entity_type="Room")
    test_room2 = Room.create(entity=room_entity2, room_number=1002)
    RoomExit.create(from_room=test_room1, direction="north", to_room_number=1002, to_room=test_room2)

    found_room = get_room_by_number(1001)
    assert found_room is not None
    assert found_room.room_number == 1001

    found_entity = get_entity_by_name("Test Room 1", "Room")
    assert found_entity is not None
    assert found_entity.name == "Test Room 1"

    exits = get_room_exits(1001)
    assert len(exits) == 1
    assert exits[0].direction == "north"

    path = find_path_between_rooms(1001, 1002)
    assert len(path) == 1
    assert path[0] == "north"

def test_database_stats(test_db):
    """Test database statistics."""
    room_entity = Entity.create(name="Test Room", entity_type="Room")
    Room.create(entity=room_entity, room_number=1001)
    npc_entity = Entity.create(name="Test NPC", entity_type="NPC")
    NPC.create(entity=npc_entity)
    Observation.create(entity=room_entity, observation_text="text")
    Relation.create(from_entity=room_entity, to_entity=npc_entity, relation_type="contains")

    stats = get_database_stats()
    assert stats['Entity'] >= 2
    assert stats['Room'] >= 1
    assert stats['NPC'] >= 1
    assert stats['Observation'] >= 1
    assert stats['Relation'] >= 1


def test_record_exit_success_with_enter_variations(test_db):
    room_entity1 = Entity.create(name="Room A", entity_type="Room")
    room_entity2 = Entity.create(name="Room B", entity_type="Room")
    room_a = Room.create(entity=room_entity1, room_number=2001)
    room_b = Room.create(entity=room_entity2, room_number=2002)

    exit_obj = RoomExit.create(from_room=room_a, direction="enter gate", to_room_number=2002, to_room=room_b)

    exit_obj.record_exit_success(move_command="enter portal", pre_commands=["unlock portal"])

    details = exit_obj.get_command_details()
    assert details["move_command"] == "enter portal"
    assert details["pre_commands"] == ["unlock portal"]


def test_record_exit_success_updates_latest_commands(test_db):
    room_entity1 = Entity.create(name="Room A", entity_type="Room")
    room_entity2 = Entity.create(name="Room B", entity_type="Room")
    room_a = Room.create(entity=room_entity1, room_number=3001)
    room_b = Room.create(entity=room_entity2, room_number=3002)

    exit_obj = RoomExit.create(from_room=room_a, direction="north", to_room_number=3002, to_room=room_b)

    exit_obj.record_exit_success(move_command="north", pre_commands=["open north"])
    first_details = exit_obj.get_command_details()
    assert first_details["pre_commands"] == ["open north"]

    exit_obj.record_exit_success(move_command="north", pre_commands=["unlock north"])
    second_details = exit_obj.get_command_details()
    assert second_details["pre_commands"] == ["unlock north"]
    assert second_details["last_success_at"] != first_details["last_success_at"]


def test_record_exit_success_cardinal_synonyms(test_db):
    room_entity1 = Entity.create(name="Room A", entity_type="Room")
    room_entity2 = Entity.create(name="Room B", entity_type="Room")
    room_a = Room.create(entity=room_entity1, room_number=3101)
    room_b = Room.create(entity=room_entity2, room_number=3102)

    exit_obj = RoomExit.create(from_room=room_a, direction="n", to_room_number=3102, to_room=room_b)

    exit_obj.record_exit_success(move_command="north", pre_commands=[])
    details = exit_obj.get_command_details()
    assert details["move_command"] == "north"


def test_record_exit_success_with_say_variations(test_db):
    room_entity1 = Entity.create(name="Room A", entity_type="Room")
    room_entity2 = Entity.create(name="Room B", entity_type="Room")
    room_a = Room.create(entity=room_entity1, room_number=4001)
    room_b = Room.create(entity=room_entity2, room_number=4002)

    exit_obj = RoomExit.create(from_room=room_a, direction="say xyzzy", to_room_number=4002, to_room=room_b)

    exit_obj.record_exit_success(move_command="say abracadabra", pre_commands=[])
    details = exit_obj.get_command_details()
    assert details["move_command"] == "say abracadabra"
    assert details["pre_commands"] == []


def test_sync_status_defaults_to_dirty(test_db):
    """New records should default to sync_status='dirty'."""
    entity = Entity.create(name="Sync Test", entity_type="Room")
    assert entity.sync_status == "dirty"
    assert entity.remote_updated_at is None


def test_record_exit_success_distinct_enter_commands(test_db):
    """Different 'enter X' commands in the same zone should NOT collide."""
    entity1 = Entity.create(name="1", entity_type="Room")
    room1 = Room.create(entity=entity1, room_number=1, zone="TestZone", terrain="city")

    entity2 = Entity.create(name="2", entity_type="Room")
    room2 = Room.create(entity=entity2, room_number=2, zone="TestZone", terrain="city")

    entity3 = Entity.create(name="3", entity_type="Room")
    room3 = Room.create(entity=entity3, room_number=3, zone="TestZone", terrain="city")

    # Create two exits from room1 with different enter commands
    exit_hut = RoomExit.create(from_room=room1, direction="enter hut", to_room=room2, to_room_number=2)
    exit_rubble = RoomExit.create(from_room=room1, direction="enter rubble", to_room=room3, to_room_number=3)

    # Record success for "enter hut"
    exit_hut.record_exit_success(move_command="enter hut")
    details_hut = exit_hut.get_command_details()
    assert details_hut["move_command"] == "enter hut"

    # Record success for "enter rubble" — should NOT be blocked by collision with "enter hut"
    exit_rubble.record_exit_success(move_command="enter rubble")
    details_rubble = exit_rubble.get_command_details()
    assert details_rubble["move_command"] == "enter rubble"


def test_save_sets_sync_status_dirty(test_db):
    """Saving a synced record should mark it dirty again."""
    entity = Entity.create(name="Sync Test", entity_type="Room")
    Entity.update(sync_status="synced").where(Entity.id == entity.id).execute()
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "synced"

    entity.name = "Updated Name"
    entity.save()
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "dirty"

