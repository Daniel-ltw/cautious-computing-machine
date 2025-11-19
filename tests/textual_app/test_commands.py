"""Tests for textual_app commands module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from mud_agent.utils.textual_app.commands import CommandProcessor
from mud_agent.utils.widgets.command_log import CommandLog


class TestCommandProcessor:
    """Test cases for CommandProcessor class."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app for testing."""
        app = Mock()
        app.agent = Mock()
        app.agent.client = Mock()
        app.agent.client.connected = True
        app.agent.client.send = AsyncMock()
        app.agent.send_command = AsyncMock(return_value="")
        app.state_manager = Mock()
        app.query_one = Mock(return_value=Mock(spec=CommandLog))
        return app

    @pytest.fixture
    def command_processor(self, mock_app):
        """Create a CommandProcessor instance for testing."""
        return CommandProcessor(mock_app)

    def test_init(self, command_processor, mock_app):
        """Test CommandProcessor initialization."""
        assert command_processor.app == mock_app
        assert command_processor.agent == mock_app.agent
        assert command_processor.state_manager == mock_app.state_manager

    @pytest.mark.asyncio
    async def test_submit_command_basic(self, command_processor):
        """Test basic command submission."""
        command = "look"
        with patch('asyncio.create_task') as mock_create_task:
            await command_processor.submit_command(command)
            # Current implementation creates a single task for processing
            assert mock_create_task.call_count == 1

    @pytest.mark.asyncio
    async def test_submit_command_internal(self, command_processor):
        """Test internal command submission."""
        command = "/help"
        with patch.object(command_processor, 'handle_internal_command', new_callable=AsyncMock) as mock_handle:
            await command_processor.submit_command(command)
            mock_handle.assert_called_once_with(command)

    @pytest.mark.asyncio
    async def test_submit_command_not_connected(self, command_processor):
        """Test submitting a command when not connected to the server."""
        command_processor.agent.client.connected = False
        command = "look"
        await command_processor.submit_command(command)
        command_processor.app.query_one.return_value.write.assert_any_call("[bold red]Not connected to server[/bold red]")

    @pytest.mark.asyncio
    async def test_handle_internal_command_unknown(self, command_processor):
        """Test handling an unknown internal command."""
        command = "/unknown"
        await command_processor.handle_internal_command(command)
        command_processor.app.query_one.return_value.write.assert_any_call(f"[bold yellow]Unknown internal command: {command}[/bold yellow]")
