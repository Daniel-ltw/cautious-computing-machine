"""
Tests for command splitting in CommandProcessor.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from mud_agent.agent.command_processor import CommandProcessor

@pytest.mark.asyncio
class TestCommandProcessorSplitting:
    """Tests for splitting chain commands in CommandProcessor."""

    async def test_process_command_splits_chain(self):
        """Test that process_command splits commands by semicolon."""
        agent = MagicMock()
        room_manager = MagicMock()
        processor = CommandProcessor(agent, room_manager)

        # Mock _process_single_command to return a dummy response
        processor._process_single_command = AsyncMock(side_effect=["Response 1", "Response 2"])

        # Test "n;s"
        response = await processor.process_command("n;s")

        # Verify _process_single_command was called twice
        assert processor._process_single_command.call_count == 2
        processor._process_single_command.assert_any_call("n", is_speedwalk=False)
        processor._process_single_command.assert_any_call("s", is_speedwalk=False)

        # Verify response is joined
        assert response == "Response 1\nResponse 2"

    async def test_process_command_handles_single_command(self):
        """Test that process_command handles single commands correctly."""
        agent = MagicMock()
        room_manager = MagicMock()
        processor = CommandProcessor(agent, room_manager)

        # Mock _process_single_command
        processor._process_single_command = AsyncMock(return_value="Response")

        # Test "look"
        response = await processor.process_command("look")

        # Verify _process_single_command was called once
        processor._process_single_command.assert_called_once_with("look", is_speedwalk=False)

        # Verify response
        assert response == "Response"
