"""
Tests for the RoomManager class.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mud_agent.agent.room_manager import RoomManager


@pytest.fixture
def mock_agent():
    """Create a mock agent with mock event bus and knowledge graph."""
    agent = MagicMock()
    agent.events = AsyncMock()
    agent.knowledge_graph = AsyncMock()
    return agent



@pytest.fixture
def manager(mock_agent):
    """Create a RoomManager instance with a mock agent."""
    return RoomManager(mock_agent)


@pytest.mark.asyncio
async def test_successful_move_records_exit(manager, mock_agent):
    """Test that a successful move correctly records an exit."""
    # Set initial room
    manager.current_room = {"num": 1, "name": "Starting Room"}

    # Simulate sending a movement command
    await manager._handle_command_sent("north")

    # Simulate the room update event
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Check that record_exit_success was called with the correct arguments
    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=[],
    )

@pytest.mark.asyncio
async def test_move_with_valid_pre_command(manager, mock_agent):
    """Test that a move with a valid pre-command is recorded correctly."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    # Simulate pre-command and move command
    await manager._handle_command_sent("open north")
    await manager._handle_command_sent("north")

    # Simulate room update
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=["open north"],
    )

@pytest.mark.asyncio
async def test_move_with_invalid_pre_command(manager, mock_agent):
    """Test that an invalid pre-command is not included in the exit record."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    # Simulate invalid pre-command and move command
    await manager._handle_command_sent("open south")
    await manager._handle_command_sent("north")

    # Simulate room update
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=[],
    )

@pytest.mark.asyncio
async def test_directionless_move_with_pre_commands(manager, mock_agent):
    """Test that pre-commands are considered valid for directionless moves."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    # Simulate pre-command and directionless move
    await manager._handle_command_sent("unlock portal")
    await manager._handle_command_sent("enter portal")

    # Simulate room update
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="enter portal",
        move_cmd="enter portal",
        pre_cmds=["unlock portal"],
    )



@pytest.mark.asyncio
async def test_move_with_multiple_valid_pre_commands(manager, mock_agent):
    """Test that a move with multiple valid pre-commands is recorded correctly."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock north")
    await manager._handle_command_sent("open north")
    await manager._handle_command_sent("north")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Verify call and ignore order of pre-commands
    mock_agent.knowledge_graph.record_exit_success.assert_called_once()
    _, kwargs = mock_agent.knowledge_graph.record_exit_success.call_args
    assert kwargs["from_room_num"] == 1
    assert kwargs["to_room_num"] == 2
    assert kwargs["direction"] == "north"
    assert kwargs["move_cmd"] == "north"
    assert set(kwargs["pre_cmds"]) == {"unlock north", "open north"}

@pytest.mark.asyncio
async def test_move_with_mixed_pre_commands(manager, mock_agent):
    """Test that only valid pre-commands are recorded."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock north")
    await manager._handle_command_sent("open south")
    await manager._handle_command_sent("north")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=["unlock north"],
    )

@pytest.mark.asyncio
async def test_directionless_move_with_multiple_pre_commands(manager, mock_agent):
    """Test that multiple pre-commands are valid for directionless moves."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock portal")
    await manager._handle_command_sent("recite spell")
    await manager._handle_command_sent("enter portal")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="enter portal",
        move_cmd="enter portal",
        pre_cmds=["unlock portal"],
    )

@pytest.mark.asyncio
async def test_move_with_no_room_change(manager, mock_agent):
    """Test that an exit is not recorded if the room does not change."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("north")

    await manager._on_room_update(room_data={"num": 1, "name": "Starting Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()

@pytest.mark.asyncio
async def test_move_with_semicolon_chain_records_exit(manager, mock_agent):
    """Test that semicolon-chained commands record movement and pre-commands."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("open north")
    await manager._handle_command_sent("north;look")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=["open north"],
    )

@pytest.mark.asyncio
async def test_directionless_move_with_semicolon_chain(manager, mock_agent):
    """Test that portal enter in a chained command is captured."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock portal; enter portal")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="enter portal",
        move_cmd="enter portal",
        pre_cmds=["unlock portal"],
    )

@pytest.mark.asyncio
async def test_climb_directionless_move_with_pre_commands(manager, mock_agent):
    """Test that 'climb' moves are captured with pre-commands."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock rope")
    await manager._handle_command_sent("climb rope")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="climb rope",
        move_cmd="climb rope",
        pre_cmds=["unlock rope"],
    )

@pytest.mark.asyncio
async def test_say_triggers_force_exit_check(manager, mock_agent):
    """Test that 'say' token triggers a force exit check emission."""
    import asyncio
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("say hello; enter portal")
    await asyncio.sleep(0)

    mock_agent.events.emit.assert_any_call("force_exit_check", command="say hello")

@pytest.mark.asyncio
async def test_first_movement_in_chain_is_recorded(manager, mock_agent):
    """Test that only the first movement in a chain is captured."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("open north; north; east")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="north",
        move_cmd="north",
        pre_cmds=["open north"],
    )

@pytest.mark.asyncio
async def test_board_directionless_move_with_pre_commands(manager, mock_agent):
    """Test that 'board' moves are captured with pre-commands."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("unlock ship")
    await manager._handle_command_sent("board ship")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="board ship",
        move_cmd="board ship",
        pre_cmds=["unlock ship"],
    )

@pytest.mark.asyncio
async def test_escape_directionless_move_without_pre_commands(manager, mock_agent):
    """Test that 'escape' moves are captured without pre-commands."""
    manager.current_room = {"num": 1, "name": "Starting Room"}

    await manager._handle_command_sent("escape")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=1,
        to_room_num=2,
        direction="escape",
        move_cmd="escape",
        pre_cmds=[],
    )

