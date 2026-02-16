"""
Tests for limiting implicit room change commands in RoomManager.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Import helper to add src to Python path
from test_helper import *

from mud_agent.agent.room_manager import RoomManager


@pytest.mark.asyncio
class TestRoomManagerImplicitLimit:
    """Tests for limiting implicit room change commands."""

    async def test_handle_command_sent_triggers_check_for_whitelisted_cmd(self):
        """Test that whitelisted commands set pending_exit_command directly via startswith_commands."""
        agent = MagicMock()
        events = MagicMock()
        events.emit = AsyncMock()

        manager = RoomManager(agent)
        manager.events = events
        manager.logger = MagicMock()

        # Mock _get_current_room_num
        manager._get_current_room_num = MagicMock(return_value=1)

        # Test "enter portal"
        await manager._handle_command_sent("enter portal")

        # After startswith_commands expansion, "enter portal" is now caught in the
        # token loop and sets pending_exit_command directly instead of going through
        # force_exit_check
        assert manager.pending_exit_command == "enter portal"
        assert manager.from_room_num_on_exit == 1

    async def test_handle_command_sent_ignores_non_whitelisted_cmd(self):
        """Test that non-whitelisted commands do NOT trigger force_exit_check."""
        agent = MagicMock()
        events = MagicMock()
        events.emit = AsyncMock()

        manager = RoomManager(agent)
        manager.events = events
        manager.logger = MagicMock()

        # Mock _get_current_room_num
        manager._get_current_room_num = MagicMock(return_value=1)

        # Test "look"
        await manager._handle_command_sent("look")

        # Verify force_exit_check was NOT emitted
        events.emit.assert_not_called()

        # Verify debug log
        manager.logger.debug.assert_any_call("Command 'look' not in implicit exit whitelist - ignoring")

    async def test_handle_command_sent_ignores_unknown_cmd(self):
        """Test that completely unknown commands do NOT trigger force_exit_check."""
        agent = MagicMock()
        events = MagicMock()
        events.emit = AsyncMock()

        manager = RoomManager(agent)
        manager.events = events
        manager.logger = MagicMock()

        # Mock _get_current_room_num
        manager._get_current_room_num = MagicMock(return_value=1)

        # Test "xyz123"
        await manager._handle_command_sent("xyz123")

        # Verify force_exit_check was NOT emitted
        events.emit.assert_not_called()

        # Verify debug log
        manager.logger.debug.assert_any_call("Command 'xyz123' not in implicit exit whitelist - ignoring")
