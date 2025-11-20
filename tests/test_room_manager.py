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


# ============================================================================
# Edge Case Tests for record_exit_success
# ============================================================================

@pytest.mark.asyncio
async def test_say_command_triggers_room_change(manager, mock_agent):
    """Test that a 'say' command that causes a room change records the exit."""
    import asyncio
    manager.current_room = {"num": 10, "name": "Magic Room"}

    # Trigger force exit check
    task = asyncio.create_task(manager._handle_force_exit_check("say abracadabra"))

    # Simulate room change during the sleep
    await asyncio.sleep(0.1)
    manager.current_room = {"num": 20, "name": "Secret Room"}

    # Wait for the check to complete
    await task

    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=10,
        to_room_num=20,
        direction="say abracadabra",
        move_cmd="say abracadabra",
        pre_cmds=[],
    )


@pytest.mark.asyncio
async def test_say_command_no_room_change(manager, mock_agent):
    """Test that a 'say' command without room change doesn't record exit."""
    manager.current_room = {"num": 10, "name": "Magic Room"}

    await manager._handle_force_exit_check("say hello")

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_force_exit_check_no_initial_room(manager, mock_agent):
    """Test force exit check when current_room is None."""
    manager.current_room = None

    await manager._handle_force_exit_check("say xyzzy")

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_force_exit_check_room_becomes_none(manager, mock_agent):
    """Test force exit check when room becomes None after command."""
    import asyncio
    manager.current_room = {"num": 10, "name": "Room"}

    task = asyncio.create_task(manager._handle_force_exit_check("say test"))
    await asyncio.sleep(0.1)
    manager.current_room = None
    await task

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_room_update_with_incomplete_data(manager, mock_agent):
    """Test room update with missing 'num' field."""
    manager.current_room = {"num": 1, "name": "Room"}
    await manager._handle_command_sent("north")

    # Room update with incomplete data should not crash
    await manager._on_room_update(room_data={"name": "Incomplete Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_room_update_with_none_data(manager, mock_agent):
    """Test room update with None as room data."""
    manager.current_room = {"num": 1, "name": "Room"}
    await manager._handle_command_sent("north")

    # Room update with None should not crash
    await manager._on_room_update(room_data=None)

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_room_update_without_pending_exit(manager, mock_agent):
    """Test room update when no movement command was sent."""
    manager.current_room = {"num": 1, "name": "Room"}

    # Room update without pending exit command
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Should not record exit since no movement command was sent
    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_room_update_with_none_from_room(manager, mock_agent):
    """Test room update when from_room_num_on_exit is None."""
    manager.current_room = {"num": 1, "name": "Room"}
    manager.pending_exit_command = "north"
    manager.from_room_num_on_exit = None

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Should not record exit when from_room_num is None
    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_pre_commands_cleared_after_successful_move(manager, mock_agent):
    """Test that pre-commands are cleared after a successful move."""
    manager.current_room = {"num": 1, "name": "Room"}

    await manager._handle_command_sent("unlock north")
    await manager._handle_command_sent("open north")
    await manager._handle_command_sent("north")

    # Verify pre-commands were set
    assert len(manager.pending_pre_commands) > 0

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Pre-commands should be cleared after successful move
    assert len(manager.pending_pre_commands) == 0
    assert manager.pending_exit_command is None
    assert manager.from_room_num_on_exit is None


@pytest.mark.asyncio
async def test_pre_commands_persist_on_failed_move(manager, mock_agent):
    """Test that pre-commands persist when move fails (room doesn't change)."""
    manager.current_room = {"num": 1, "name": "Room"}

    await manager._handle_command_sent("unlock north")
    await manager._handle_command_sent("north")

    initial_pre_cmds = manager.pending_pre_commands.copy()

    # Room doesn't change - failed move
    await manager._on_room_update(room_data={"num": 1, "name": "Room"})

    # Pre-commands should still be present (not cleared on failed move)
    assert manager.pending_pre_commands == initial_pre_cmds


@pytest.mark.asyncio
async def test_multiple_pre_commands_same_direction(manager, mock_agent):
    """Test multiple pre-commands for the same direction."""
    manager.current_room = {"num": 1, "name": "Room"}

    await manager._handle_command_sent("unlock north")
    await manager._handle_command_sent("open north")
    await manager._handle_command_sent("kick north")
    await manager._handle_command_sent("north")

    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    call_args = mock_agent.knowledge_graph.record_exit_success.call_args
    assert set(call_args.kwargs["pre_cmds"]) == {"unlock north", "open north", "kick north"}


@pytest.mark.asyncio
async def test_exception_in_record_exit_success_handled(manager, mock_agent):
    """Test that exceptions in record_exit_success are handled gracefully."""
    manager.current_room = {"num": 1, "name": "Room"}

    # Make record_exit_success raise an exception
    mock_agent.knowledge_graph.record_exit_success.side_effect = Exception("Database error")

    await manager._handle_command_sent("north")

    # Should not crash even if record_exit_success fails
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    # Verify the method was called despite the exception
    mock_agent.knowledge_graph.record_exit_success.assert_called_once()


@pytest.mark.asyncio
async def test_non_movement_command_clears_pending_exit(manager, mock_agent):
    """Test that non-movement commands clear pending exit."""
    manager.current_room = {"num": 1, "name": "Room"}

    await manager._handle_command_sent("north")
    assert manager.pending_exit_command == "north"

    # Send non-movement command
    await manager._handle_command_sent("look")

    # Room update should not record exit
    await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

    mock_agent.knowledge_graph.record_exit_success.assert_not_called()


@pytest.mark.asyncio
async def test_all_cardinal_directions(manager, mock_agent):
    """Test that all cardinal directions are properly detected."""
    directions = ["n", "s", "e", "w", "u", "d", "north", "south", "east", "west", "up", "down"]

    for direction in directions:
        manager.current_room = {"num": 1, "name": "Room"}
        mock_agent.knowledge_graph.record_exit_success.reset_mock()

        await manager._handle_command_sent(direction)
        await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

        mock_agent.knowledge_graph.record_exit_success.assert_called_once()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs["direction"] == direction
        assert call_args.kwargs["move_cmd"] == direction


@pytest.mark.asyncio
async def test_all_directionless_commands(manager, mock_agent):
    """Test that all directionless movement commands are detected."""
    commands = [
        ("enter portal", "enter portal"),
        ("board ship", "board ship"),
        ("escape", "escape"),
        ("climb ladder", "climb ladder"),
    ]

    for command, expected in commands:
        manager.current_room = {"num": 1, "name": "Room"}
        mock_agent.knowledge_graph.record_exit_success.reset_mock()

        await manager._handle_command_sent(command)
        await manager._on_room_update(room_data={"num": 2, "name": "New Room"})

        mock_agent.knowledge_graph.record_exit_success.assert_called_once()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs["direction"] == expected
        assert call_args.kwargs["move_cmd"] == expected


@pytest.mark.asyncio
async def test_room_update_updates_knowledge_graph(manager, mock_agent):
    """Test that room updates are added to knowledge graph."""
    room_data = {"num": 1, "name": "Test Room", "terrain": "inside", "exits": {"n": 2}}

    await manager._on_room_update(room_data=room_data)

    # Verify knowledge graph add_entity was called
    mock_agent.knowledge_graph.add_entity.assert_called_once()
    call_args = mock_agent.knowledge_graph.add_entity.call_args[0][0]
    assert call_args["entityType"] == "Room"
    assert call_args["num"] == 1


@pytest.mark.asyncio
async def test_exception_in_knowledge_graph_add_entity(manager, mock_agent):
    """Test that exceptions in add_entity are handled gracefully."""
    mock_agent.knowledge_graph.add_entity.side_effect = Exception("Database error")

    room_data = {"num": 1, "name": "Test Room"}

    # Should not crash
    await manager._on_room_update(room_data=room_data)

    # Verify it was attempted
    mock_agent.knowledge_graph.add_entity.assert_called_once()


@pytest.mark.asyncio
async def test_rapid_room_changes(manager, mock_agent):
    """Test rapid sequence of room changes."""
    manager.current_room = {"num": 1, "name": "Room 1"}

    await manager._handle_command_sent("north")
    await manager._on_room_update(room_data={"num": 2, "name": "Room 2"})

    await manager._handle_command_sent("east")
    await manager._on_room_update(room_data={"num": 3, "name": "Room 3"})

    await manager._handle_command_sent("south")
    await manager._on_room_update(room_data={"num": 4, "name": "Room 4"})

    # Should have recorded 3 exits
    assert mock_agent.knowledge_graph.record_exit_success.call_count == 3

