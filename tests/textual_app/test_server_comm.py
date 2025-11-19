"""Tests for textual_app server_comm module."""

from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from mud_agent.utils.textual_app.server_comm import ServerCommunicator


@pytest.fixture
def mock_app():
    """Create a mock app with necessary components for testing."""
    app = Mock()
    app.agent = Mock()
    app.agent.client = Mock()
    app.agent.client.connected = False
    app.agent.client.send_command = AsyncMock()
    app.agent.client.connect = AsyncMock()
    app.agent.client.disconnect = AsyncMock()
    app.agent.logger = Mock()
    app.state_manager = Mock()
    app.query_one = Mock()
    return app


@pytest.fixture
def server_communicator(mock_app):
    """Create a ServerCommunicator instance for testing."""
    return ServerCommunicator(mock_app)


class TestServerCommunicator:
    """Test cases for ServerCommunicator class."""

    def test_init(self, server_communicator, mock_app):
        """Test ServerCommunicator initialization."""
        assert server_communicator.app == mock_app
        assert server_communicator.agent == mock_app.agent
        assert server_communicator.state_manager == mock_app.state_manager
        assert hasattr(server_communicator, '_server_message_queue')

    @pytest.mark.asyncio
    async def test_send_command_to_server_when_connected(self, server_communicator):
        """Test sending command when connected."""
        server_communicator.agent.client.connected = True
        command = "look"
        await server_communicator.send_command_to_server(command)
        server_communicator.agent.client.send_command.assert_called_once_with(command, is_user_command=False)

    @pytest.mark.asyncio
    async def test_send_command_to_server_when_disconnected(self, server_communicator):
        """Test sending command when disconnected."""
        server_communicator.agent.client.connected = False
        command = "look"
        await server_communicator.send_command_to_server(command)
        server_communicator.agent.client.send_command.assert_not_called()
        server_communicator.app.query_one.assert_called_with("#command-log", ANY)

    @pytest.mark.asyncio
    async def test_connect_to_server_success(self, server_communicator):
        """Test successful connection to the server."""
        server_communicator.agent.client.connect.return_value = None
        # Mock the aardwolf_gmcp attribute
        server_communicator.agent.aardwolf_gmcp = AsyncMock()
        server_communicator.agent.aardwolf_gmcp.initialize = AsyncMock()

        result = await server_communicator.connect_to_server()

        assert result is True
        server_communicator.agent.client.connect.assert_called_once()
        server_communicator.agent.aardwolf_gmcp.initialize.assert_called_once()
        server_communicator.app.query_one.return_value.write.assert_called_with("[bold green]Connected to server[/bold green]")

    @pytest.mark.asyncio
    async def test_connect_to_server_failure(self, server_communicator):
        """Test failed connection to the server."""
        server_communicator.agent.client.connect.side_effect = Exception("Connection failed")
        result = await server_communicator.connect_to_server()
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_from_server(self, server_communicator):
        """Test disconnecting from the server."""
        server_communicator.agent.client.connected = True
        await server_communicator.disconnect_from_server()
        server_communicator.agent.client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_display_server_message(self, server_communicator):
        """Test displaying a server message."""
        with patch('asyncio.create_task') as mock_create_task:
            message = "Hello, world!"
            await server_communicator.display_server_message(message)
            assert not server_communicator._server_message_queue.empty()
            assert await server_communicator._server_message_queue.get() == message
            mock_create_task.assert_called_once()
