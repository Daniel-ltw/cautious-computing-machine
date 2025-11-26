from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from peewee import DoesNotExist

from mud_agent.db.models import Entity, Room, RoomExit
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph


@pytest.fixture
def mock_db():
    """Fixture to mock the database."""
    with patch('mud_agent.mcp.game_knowledge_graph.db') as mock_db_obj:
        mock_db_obj.is_closed.return_value = True
        mock_db_obj.connect = MagicMock()
        mock_db_obj.close = MagicMock()
        atomic_mock = MagicMock()
        atomic_mock.__enter__ = MagicMock()
        atomic_mock.__exit__ = MagicMock()
        mock_db_obj.atomic.return_value = atomic_mock
        yield mock_db_obj

@pytest_asyncio.fixture
async def knowledge_graph(mock_db):
    """Fixture to create and initialize a GameKnowledgeGraph instance."""
    kg = GameKnowledgeGraph()
    with patch('mud_agent.mcp.game_knowledge_graph.DatabaseMigrator.run_migrations') as mock_run_migrations:
        await kg.initialize()
        mock_run_migrations.assert_called_once()
    return kg

@pytest.mark.asyncio
async def test_initialize(mock_db):
    """Test the initialize method creates a connection and runs migrations."""
    kg = GameKnowledgeGraph()
    assert not kg._initialized
    with patch('mud_agent.mcp.game_knowledge_graph.DatabaseMigrator.run_migrations') as mock_run_migrations:
        await kg.initialize()
        mock_db.connect.assert_called_once()
        mock_run_migrations.assert_called_once()
        assert kg._initialized is True

@pytest.mark.asyncio
async def test_cleanup(knowledge_graph, mock_db):
    """Test the cleanup method closes the database connection."""
    mock_db.is_closed.return_value = False
    await knowledge_graph.cleanup()
    mock_db.close.assert_called_once()



@pytest.mark.asyncio
async def test_add_entity_room(knowledge_graph):
    """Test adding a Room entity."""
    entity_data = {"entityType": "Room", "name": "Test Room", "room_number": 123}
    with patch('mud_agent.db.models.Room.create_or_update_from_dict') as mock_room_create_update:
        mock_room = MagicMock()
        mock_room.entity = MagicMock()
        mock_room_create_update.return_value = mock_room

        result = await knowledge_graph.add_entity(entity_data)

        mock_room_create_update.assert_called_once()
        assert result is mock_room.entity

@pytest.mark.asyncio
async def test_add_entity_npc(knowledge_graph):
    """Test adding an NPC entity."""
    entity_data = {"entityType": "NPC", "name": "Test NPC"}
    with patch('mud_agent.db.models.NPC.create_or_update_from_dict') as mock_npc_create_update:
        mock_npc = MagicMock()
        mock_npc.entity = MagicMock()
        mock_npc_create_update.return_value = mock_npc

        result = await knowledge_graph.add_entity(entity_data)
        mock_npc_create_update.assert_called_once()
        assert result is mock_npc.entity

@pytest.mark.asyncio
async def test_add_relation(knowledge_graph):
    """Test adding a relation between entities."""
    from_entity = Entity(name="Room")
    to_entity = Entity(name="NPC")
    with patch('mud_agent.db.models.Relation.get_or_create') as mock_get_or_create:
        knowledge_graph.add_relation(from_entity, to_entity, "contains")
        mock_get_or_create.assert_called_once_with(
            from_entity=from_entity, to_entity=to_entity, relation_type="contains"
        )

@pytest.mark.asyncio
async def test_get_entity(knowledge_graph):
    """Test retrieving an entity."""
    with patch('mud_agent.db.models.Entity.get') as mock_get:
        knowledge_graph.get_entity("Test Entity")
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_exit_creates_new_exit(knowledge_graph):
    from_room = Room(room_number=1)
    to_room_number = 2
    direction = "north"

    with patch('mud_agent.db.models.RoomExit.create') as mock_create:
        mock_exit = MagicMock()
        mock_create.return_value = mock_exit
        exit_obj = knowledge_graph.get_or_create_exit(from_room, direction, to_room_number=to_room_number)
        mock_create.assert_called_once_with(
            from_room=from_room,
            direction=direction,
            to_room=None,
            to_room_number=to_room_number,
        )
        assert exit_obj is mock_exit

@pytest.mark.asyncio
async def test_get_or_create_exit_updates_existing_exit(knowledge_graph):
    from_room = Room(room_number=1)
    to_room_number = 2
    direction = "north"
    existing_exit = MagicMock()
    existing_exit.direction = "south"

    # Simulate existing exit found via from_room.exits.where(...).get()
    from_room.exits = MagicMock()
    where_mock = MagicMock()
    where_mock.get.return_value = existing_exit
    from_room.exits.where.return_value = where_mock

    exit_obj = knowledge_graph.get_or_create_exit(from_room, direction, to_room_number=to_room_number)
    assert exit_obj.direction == "south"
    existing_exit.save.assert_called_once()

@pytest.mark.asyncio
async def test_get_knowledge_graph_summary_formatted(knowledge_graph):
    """Test formatted knowledge graph summary method exists and returns a string."""
    # Mock internal knowledge_graph structure for summary
    knowledge_graph.knowledge_graph = {
        "entities": {
            "Room1": {"entityType": "Room"},
            "NPC1": {"entityType": "NPC"},
        },
        "relations": [
            {"relationType": "contains"},
            {"relationType": "has exit"},
        ],
    }

    summary = await knowledge_graph.get_knowledge_graph_summary_formatted()
    assert isinstance(summary, str)


@pytest.mark.asyncio
async def test_initialize_and_cleanup_alternative(mock_db):
    """Initialize and cleanup paths work with patched migrator."""
    graph = GameKnowledgeGraph()
    with patch('mud_agent.mcp.game_knowledge_graph.DatabaseMigrator.run_migrations') as mock_run_migrations:
        await graph.initialize()
        mock_db.connect.assert_called()
        mock_run_migrations.assert_called()
    mock_db.is_closed.return_value = False
    await graph.cleanup()
    mock_db.close.assert_called()

@pytest.mark.asyncio
async def test_record_enter_exit_records_details(knowledge_graph, test_db):
    from_entity = Entity.create(name="10", entity_type="Room")
    to_entity = Entity.create(name="20", entity_type="Room")
    from_room = Room.create(entity=from_entity, room_number=10)
    to_room = Room.create(entity=to_entity, room_number=20)

    RoomExit.create(from_room=from_room, direction="enter gate", to_room_number=None)

    await knowledge_graph.record_exit_success(
        from_room_num=10,
        to_room_num=20,
        direction="enter portal",
        move_cmd="enter portal",
        pre_cmds=["unlock portal"],
    )

    exit_obj = from_room.exits.where(RoomExit.direction == "enter gate").get()
    details = exit_obj.get_command_details()
    assert details["move_command"] == "enter portal"
    assert details["pre_commands"] == ["unlock portal"]

    # Remove outdated src.mud_agent path-based tests


@pytest.mark.asyncio
async def test_get_or_create_exit_creates_new_exit(knowledge_graph):
    from_room = MagicMock()
    # Simulate no existing exit
    where_mock = MagicMock()
    where_mock.get.side_effect = DoesNotExist
    from_room.exits = MagicMock()
    from_room.exits.where.return_value = where_mock
    to_room_number = 2
    direction = "north"

    with patch('mud_agent.db.models.RoomExit.create') as mock_create:
        mock_exit = MagicMock()
        mock_create.return_value = mock_exit
        exit_obj = knowledge_graph.get_or_create_exit(from_room, direction, to_room_number=to_room_number)
        mock_create.assert_called_once_with(
            from_room=from_room,
            direction=direction,
            to_room=None,
            to_room_number=to_room_number,
        )
        assert exit_obj is mock_exit

@pytest.mark.asyncio
async def test_get_or_create_exit_updates_existing_exit(knowledge_graph):
    from_room = MagicMock()
    to_room_number = 2
    direction = "north"
    existing_exit = MagicMock()
    existing_exit.direction = "south"

    # Simulate existing exit found via from_room.exits.where(...).get()
    from_room.exits = MagicMock()
    where_mock = MagicMock()
    where_mock.get.return_value = existing_exit
    from_room.exits.where.return_value = where_mock

    exit_obj = knowledge_graph.get_or_create_exit(from_room, direction, to_room_number=to_room_number)
    assert exit_obj.direction == "south"
    existing_exit.save.assert_called_once()

# Removed obsolete get_stats test; GameKnowledgeGraph provides formatted summary instead


@pytest.mark.asyncio
async def test_record_exit_handles_existing_exit_with_different_destination(knowledge_graph, test_db):
    # Create initial rooms and exit
    from_room_entity = Entity.create(name="1", entity_type="Room")
    from_room = Room.create(entity=from_room_entity, room_number=1)

    to_room_entity_1 = Entity.create(name="2", entity_type="Room")
    to_room_1 = Room.create(entity=to_room_entity_1, room_number=2)

    to_room_entity_2 = Entity.create(name="3", entity_type="Room")
    to_room_2 = Room.create(entity=to_room_entity_2, room_number=3)

    # Create an initial exit from room 1 to room 2 in the 'north' direction
    RoomExit.create(from_room=from_room, to_room=to_room_1, direction='north', to_room_number=2)

    # Now, record a successful exit from room 1 'north' but this time to room 3
    await knowledge_graph.record_exit_success(
        from_room_num=1,
        to_room_num=3,
        direction='north',
        move_cmd='north',
        pre_cmds=[]
    )

    # Verify that the exit was updated, not duplicated
    exits = list(from_room.exits.where(RoomExit.direction == 'north'))
    assert len(exits) == 1
    assert exits[0].to_room_number == 3
    assert exits[0].to_room.room_number == 3
@pytest.fixture(scope="function")
def test_db():
    """Create a temporary database for testing Peewee models."""
    import tempfile
    from pathlib import Path

    from mud_agent.db.models import NPC, Observation, Relation
    from mud_agent.db.models import Entity as E
    from mud_agent.db.models import Room as R
    from mud_agent.db.models import RoomExit as RX
    from mud_agent.db.models import db as peewee_db
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    peewee_db.init(test_db_path)
    peewee_db.connect()
    peewee_db.create_tables([E, R, RX, NPC, Observation, Relation])
    yield
    peewee_db.drop_tables([E, R, RX, NPC, Observation, Relation])
    peewee_db.close()
    Path(test_db_path).unlink()


@pytest.mark.asyncio
async def test_record_exit_skips_run_commands(knowledge_graph, test_db):
    """Test that record_exit_success skips 'run' commands and chained commands."""
    from mud_agent.db.models import Entity, Room, RoomExit

    # Create rooms
    from_entity = Entity.create(name="100", entity_type="Room")
    to_entity = Entity.create(name="200", entity_type="Room")
    from_room = Room.create(entity=from_entity, room_number=100)
    to_room = Room.create(entity=to_entity, room_number=200)

    # 1. Test 'run' command
    await knowledge_graph.record_exit_success(
        from_room_num=100,
        to_room_num=200,
        direction="north",
        move_cmd="run 5n",
        pre_cmds=[]
    )
    # Verify no exit created
    assert RoomExit.select().count() == 0

    # 2. Test chained command
    await knowledge_graph.record_exit_success(
        from_room_num=100,
        to_room_num=200,
        direction="north",
        move_cmd="open door;north",
        pre_cmds=[]
    )
    # Verify no exit created
    assert RoomExit.select().count() == 0

    # 3. Test valid command with 'run' in pre_cmds (should be filtered)
    await knowledge_graph.record_exit_success(
        from_room_num=100,
        to_room_num=200,
        direction="north",
        move_cmd="north",
        pre_cmds=["run setup", "unlock door"]
    )
    # Verify exit created
    assert RoomExit.select().count() == 1
    exit_obj = RoomExit.get()
    details = exit_obj.get_command_details()
    # 'run setup' should be filtered out
    assert details["pre_commands"] == ["unlock door"]
