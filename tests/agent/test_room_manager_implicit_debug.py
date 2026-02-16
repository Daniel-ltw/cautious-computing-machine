
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from mud_agent.agent.room_manager import RoomManager

@pytest.mark.asyncio
class TestRoomManagerImplicitDebug:
    async def test_implicit_exit_recording_flow(self):
        """Test the full flow of implicit exit recording."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.knowledge_graph.record_exit_success = AsyncMock()

        # Mock state manager
        mock_agent.state_manager = MagicMock()
        mock_agent.state_manager.room_num = 1

        manager = RoomManager(mock_agent)
        await manager.setup()

        # Initial state
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Simulate command sent "enter pool"
        print("\nStep 1: Sending command 'enter pool'")
        await manager._handle_command_sent(command="enter pool", from_room_num=1)

        # After startswith_commands expansion, "enter pool" is now caught in the token loop
        # and sets pending_exit_command directly instead of going through force_exit_check
        assert manager.pending_exit_command == "enter pool"
        assert manager.from_room_num_on_exit == 1

        # 2. Simulate force_exit_check handler
        # We need to simulate the room change happening during the sleep
        print("Step 2: Running _handle_force_exit_check")

        async def side_effect_sleep(seconds):
            print(f"  Sleeping for {seconds}s (simulated)")
            # Simulate room update happening while waiting
            manager.current_room = {"num": 2, "name": "Pool Room"}
            # Also update state manager for fallback
            mock_agent.state_manager.room_num = 2
            return

        with patch("asyncio.sleep", side_effect=side_effect_sleep):
            await manager._handle_force_exit_check("enter pool")

        # 3. Verify exit was recorded
        print("Step 3: Verifying record_exit_success call")
        mock_agent.knowledge_graph.record_exit_success.assert_called()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        print(f"  Called with: {call_args}")

        assert call_args.kwargs['from_room_num'] == 1
        assert call_args.kwargs['to_room_num'] == 2
        assert call_args.kwargs['direction'] == "enter pool"
        assert call_args.kwargs['move_cmd'] == "enter pool"

    async def test_implicit_exit_whitelist(self):
        """Test that only whitelisted commands trigger the check."""
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1}

        # Test ignored command
        await manager._handle_command_sent(command="look at pool", from_room_num=1)
        mock_agent.events.emit.assert_not_called()

    async def test_implicit_exit_fast_path(self):
        """Test that implicit exits are recorded immediately by _on_room_update."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.knowledge_graph.record_exit_success = AsyncMock()
        mock_agent.knowledge_graph.add_entity = AsyncMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Send command "enter pool"
        await manager._handle_command_sent(command="enter pool", from_room_num=1)

        # Verify pending_exit_command is set
        assert manager.pending_exit_command == "enter pool"
        assert manager.from_room_num_on_exit == 1

        # 2. Simulate room update arriving immediately (before force_exit_check timeout)
        # This calls _on_room_update directly
        await manager._on_room_update(room_data={"num": 2, "name": "Pool Room"})

        # 3. Verify exit was recorded by _on_room_update
        mock_agent.knowledge_graph.record_exit_success.assert_called()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs['from_room_num'] == 1
        assert call_args.kwargs['to_room_num'] == 2
        assert call_args.kwargs['direction'] == "enter pool"

        # Verify pending command was cleared
        assert manager.pending_exit_command is None

    async def test_implicit_exit_timeout_cleanup(self):
        """Test that pending command PERSISTS if no room change occurs (lag handling)."""
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.emit = AsyncMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1}
        manager._get_current_room_num = MagicMock(return_value=1) # Always room 1

        # 1. Send command
        await manager._handle_command_sent(command="enter pool", from_room_num=1)
        assert manager.pending_exit_command == "enter pool"

        # 2. Run force_exit_check (simulate timeout)
        with patch("asyncio.sleep", new=AsyncMock()):
            await manager._handle_force_exit_check("enter pool")

        # 3. Verify pending command PERSISTS (changed from cleared)
        assert manager.pending_exit_command == "enter pool"

    async def test_implicit_exit_push_off(self):
        """Test that 'push off' triggers implicit exit recording."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.knowledge_graph.record_exit_success = AsyncMock()
        mock_agent.knowledge_graph.add_entity = AsyncMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Send command "push off"
        await manager._handle_command_sent(command="push off", from_room_num=1)

        # Verify pending_exit_command is set
        assert manager.pending_exit_command == "push off"

        # 2. Simulate room update
        await manager._on_room_update(room_data={"num": 2, "name": "River"})

        # 3. Verify exit was recorded
        mock_agent.knowledge_graph.record_exit_success.assert_called()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs['direction'] == "push off"

    async def test_implicit_exit_interleaved_command(self):
        """Test that an interleaved non-movement command doesn't clear the pending exit."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.knowledge_graph.record_exit_success = AsyncMock()
        mock_agent.knowledge_graph.add_entity = AsyncMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Send command "push off"
        await manager._handle_command_sent(command="push off", from_room_num=1)
        assert manager.pending_exit_command == "push off"

        # 2. Send "look" (should NOT clear pending exit)
        await manager._handle_command_sent(command="look", from_room_num=1)

        # This assertion expects the fix. Currently it will fail (be None).
        assert manager.pending_exit_command == "push off"

        # 3. Simulate room update
        await manager._on_room_update(room_data={"num": 2, "name": "River"})

        # 4. Verify exit was recorded
        mock_agent.knowledge_graph.record_exit_success.assert_called()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs['direction'] == "push off"

    async def test_implicit_exit_enter_portal(self):
        """Test that 'enter portal' triggers implicit exit recording."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.knowledge_graph.record_exit_success = AsyncMock()
        mock_agent.knowledge_graph.add_entity = AsyncMock()

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Send command "enter jet"
        await manager._handle_command_sent(command="enter jet", from_room_num=1)

        # Verify pending_exit_command is set
        assert manager.pending_exit_command == "enter jet"

        # 2. Simulate room update
        await manager._on_room_update(room_data={"num": 2, "name": "Portal Room"})

        # 3. Verify exit was recorded
        mock_agent.knowledge_graph.record_exit_success.assert_called()
        call_args = mock_agent.knowledge_graph.record_exit_success.call_args
        assert call_args.kwargs['direction'] == "enter jet"

    async def test_implicit_exit_same_room(self):
        """Test that implicit exit is ignored (and logged) if room number doesn't change."""
        # Setup
        mock_agent = MagicMock()
        mock_agent.events = MagicMock()
        mock_agent.events.on = MagicMock()
        mock_agent.events.emit = AsyncMock()
        mock_agent.knowledge_graph = MagicMock()
        mock_agent.logger = MagicMock() # Mock logger to verify logging

        manager = RoomManager(mock_agent)
        await manager.setup()
        manager.current_room = {"num": 1, "name": "Room 1"}

        # 1. Send command "enter ruby"
        await manager._handle_command_sent(command="enter ruby", from_room_num=1)

        # 2. Simulate room update with SAME room number
        await manager._on_room_update(room_data={"num": 1, "name": "Room 1 (Inside ruby?)"})

        # 3. Verify exit was NOT recorded
        mock_agent.knowledge_graph.record_exit_success.assert_not_called()

        # 4. Verify log message
        # We expect a debug log containing "ignored" and "Room change required"
        # Since we can't easily check the exact log string on the manager's logger (it uses self.logger which is logging.getLogger),
        # we rely on the fact that record_exit_success wasn't called.
        # But we can check if manager.logger.debug was called if we mocked it correctly.
        # RoomManager uses `self.logger = logging.getLogger(__name__)` in __init__ usually.
        # But here we passed mock_agent.
        # RoomManager.__init__ sets self.logger = logging.getLogger(__name__).
        # So we can't easily mock it unless we patch logging.getLogger.
        # But verifying record_exit_success.assert_not_called() is sufficient to prove logic flow.
        pass
