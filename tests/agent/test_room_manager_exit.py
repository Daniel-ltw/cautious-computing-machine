import pytest
from unittest.mock import AsyncMock, MagicMock
from mud_agent.agent.room_manager import RoomManager

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.events = AsyncMock()
    agent.knowledge_graph = AsyncMock()
    agent.state_manager = MagicMock()
    agent.state_manager.room_num = None
    return agent

@pytest.fixture
def manager(mock_agent):
    return RoomManager(mock_agent)

@pytest.mark.asyncio
async def test_exit_recording_with_captured_from_room(manager, mock_agent):
    """Test that exit recording works when from_room_num is captured in the command_sent event."""
    # Setup initial state
    manager.current_room = {"num": 100, "name": "Start Room"}

    # Simulate command_sent event with captured from_room_num (as sent by command_processor)
    await manager._handle_command_sent(command="w", from_room_num=100)

    # Verify pending state is set correctly
    assert manager.pending_exit_command == "w"
    assert manager.from_room_num_on_exit == 100

    # Simulate room_update event with new room
    await manager._on_room_update(room_data={"num": 101, "name": "West Room"})

    # Verify exit was recorded with correct from/to rooms
    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=100,
        to_room_num=101,
        direction="w",
        move_cmd="w",
        pre_cmds=[]
    )

@pytest.mark.asyncio
async def test_exit_recording_fallback_no_captured_room(manager, mock_agent):
    """Test fallback to _get_current_room_num when from_room_num is missing in event."""
    # Setup initial state
    manager.current_room = {"num": 200, "name": "Start Room"}

    # Simulate command_sent event WITHOUT captured from_room_num (old format or direct call)
    await manager._handle_command_sent(command="n")

    # Verify pending state used current room
    assert manager.pending_exit_command == "n"
    assert manager.from_room_num_on_exit == 200

    # Simulate room_update event
    await manager._on_room_update(room_data={"num": 201, "name": "North Room"})

    # Verify exit recorded
    mock_agent.knowledge_graph.record_exit_success.assert_called_once_with(
        from_room_num=200,
        to_room_num=201,
        direction="n",
        move_cmd="n",
        pre_cmds=[]
    )

@pytest.mark.asyncio
async def test_stale_update_does_not_clear_pending(manager, mock_agent):
    """Test that a room update with the SAME room number doesn't clear pending exit state prematurely."""
    # Setup initial state
    manager.current_room = {"num": 300, "name": "Start Room"}

    # Command sent
    await manager._handle_command_sent(command="e", from_room_num=300)

    # Room update with SAME room number (e.g. just a look or description update)
    await manager._on_room_update(room_data={"num": 300, "name": "Start Room"})

    # Should NOT have recorded an exit
    mock_agent.knowledge_graph.record_exit_success.assert_not_called()

    # Pending state should still be active (waiting for actual room change)
    # Note: In the current implementation, _on_room_update doesn't clear pending state if room num is same
    assert manager.pending_exit_command == "e"
    assert manager.from_room_num_on_exit == 300

    # Now simulate actual room change
    await manager._on_room_update(room_data={"num": 301, "name": "East Room"})

    # Now it should record
    mock_agent.knowledge_graph.record_exit_success.assert_called_once()
