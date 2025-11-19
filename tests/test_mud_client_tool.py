"""
Tests for the MUDClientTool class.
"""

from unittest.mock import AsyncMock, Mock

import pytest

# Import helper to add src to Python path
from test_helper import *

from mud_agent.client.tools.mud_client_tool import MUDClientTool


@pytest.fixture
def mud_client_mock():
    """Create a mock MudClient for testing."""
    client = AsyncMock()
    client.debug_capture = []
    client.send_command = AsyncMock()
    client.get_collected_responses = Mock(return_value="")
    client.command_responses = []
    return client


@pytest.fixture
def mud_client_tool(mud_client_mock):
    """Create a MUDClientTool instance for testing."""
    tool = MUDClientTool(mud_client_mock)
    # Make sure the tool's client is the mock
    assert tool.client is mud_client_mock
    return tool


@pytest.mark.asyncio
async def test_connect(mud_client_tool, mud_client_mock):
    """Test connecting to a MUD server."""
    # Set up the mock client to return True
    mud_client_mock.connect.return_value = True

    # Call connect
    result = await mud_client_tool.connect("test_host", 1234)

    # Check that the client was called with the right arguments
    mud_client_mock.connect.assert_called_once_with("test_host", 1234)

    # Check that the result is correct
    assert "Connected to test_host:1234" in result


@pytest.mark.asyncio
async def test_login(mud_client_tool, mud_client_mock):
    """Test logging in to a MUD server."""
    # Set up the mock client to return True
    mud_client_mock.login.return_value = True

    # Call login
    result = await mud_client_tool.login("test_user", "test_password")

    # Check that the client was called with the right arguments
    mud_client_mock.login.assert_called_once_with("test_user", "test_password")

    # Check that the result is correct
    assert result is True


@pytest.mark.asyncio
async def test_forward(mud_client_tool, mud_client_mock):
    """Test forwarding a command to the MUD server."""
    mud_client_mock.get_collected_responses.return_value = ""
    mud_client_mock.debug_capture = []
    mud_client_mock.command_responses = ["Test response is long enough"]

    # Call forward
    result = await mud_client_tool.forward("look", False)

    # Check that the client was called with the right arguments
    mud_client_mock.send_command.assert_called_once_with("look", False)

    # Check that the result is correct
    assert result == "Test response is long enough"


@pytest.mark.asyncio
async def test_forward_with_room_description(mud_client_tool, mud_client_mock):
    """Test forwarding a command that returns a room description."""
    mud_client_mock.get_collected_responses.return_value = ""
    mud_client_mock.debug_capture = []
    mud_client_mock.command_responses = [
        "The Void [Exits: north east south west] and some extra text"
    ]

    # Call forward
    result = await mud_client_tool.forward("look", False)

    # Check that the client was called with the right arguments
    mud_client_mock.send_command.assert_called_once_with("look", False)

    # Check that the result is correct
    assert result == "The Void [Exits: north east south west] and some extra text"

    # Check that the room description and exits were stored
    assert mud_client_tool.last_room_description == "The Void [Exits: north east south west] and some extra text"
    assert mud_client_tool.last_exits == "north east south west"


@pytest.mark.asyncio
async def test_forward_with_semicolon_in_command(mud_client_tool, mud_client_mock):
    """Test that the room description and exits are stored when the command contains a semicolon."""
    mud_client_mock.get_collected_responses.return_value = ""
    mud_client_mock.debug_capture = []
    mud_client_mock.command_responses = [
        "The Void [Exits: north east south west] and some extra text",
        "You smile.",
    ]

    # Set up the mock client to return different responses for each command
    mud_client_mock.get_collected_responses.side_effect = [
        # First command ('look') retrieval attempts
        "The Void [Exits: north east south west] and some extra text",
        "The Void [Exits: north east south west] and some extra text",
        "The Void [Exits: north east south west] and some extra text",
        "The Void [Exits: north east south west] and some extra text",
        "The Void [Exits: north east south west] and some extra text",
        # Second command ('smile') retrieval attempts
        "You smile.",
        "You smile.",
        "You smile.",
        "You smile.",
        "You smile.",
    ]

    # Call the forward method with a command containing a semicolon
    result = await mud_client_tool.forward("look; smile", is_user_command=False)

    # Check that send_command was called twice, once for each part of the command
    mud_client_mock.send_command.assert_any_call("look", False)
    mud_client_mock.send_command.assert_any_call("smile", False)
    assert mud_client_mock.send_command.call_count == 2

    # Check that the result is correct
    expected_result = (
        "--- COMMAND: look ---\n\n"
        "The Void [Exits: north east south west] and some extra text\n\n"
        "--- COMMAND: smile ---\n\n"
        "You smile."
    )
    assert result == expected_result

    # Check that the room description and exits were stored
    assert mud_client_tool.last_room_description == "You smile."
    assert mud_client_tool.last_exits == "north east south west"
