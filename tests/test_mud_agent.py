"""
Tests for the MUDAgent class.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import helper to add src to Python path
from test_helper import *

from mud_agent.agent import MUDAgent
from mud_agent.config import Config


@pytest.fixture
def config():
    """Create a Config instance for testing."""
    return Config.load()


@pytest.fixture
def mud_agent(config):
    """Create a MUDAgent instance for testing."""
    # Patch the MUD client
    with patch("mud_agent.client.mud_client.MudClient") as mock_client_class:
        # Create a mock client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Patch the MUDClientTool
        with patch(
            "mud_agent.client.tools.mud_client_tool.MUDClientTool"
        ) as mock_tool_class:
            mock_tool = AsyncMock()
            mock_tool_class.return_value = mock_tool
            mock_tool.client = mock_client

            # Patch the MCPManager
            with patch("mud_agent.mcp.manager.MCPManager") as mock_mcp_class:
                mock_mcp = AsyncMock()
                mock_mcp_class.return_value = mock_mcp

                # Patch the LiteLLMModel
                with patch("smolagents.LiteLLMModel"):
                    # Patch the __aenter__ method to avoid asyncio issues
                    with patch.object(MUDAgent, "__aenter__", return_value=AsyncMock()):
                        # Create the agent
                        agent = MUDAgent(config)

                        # Set up the mocks
                        agent.client = mock_client
                        agent.mud_tool = mock_tool
                        agent.mcp_manager = mock_mcp

                        # Mock the managers
                        agent.room_manager = MagicMock()
                        agent.combat_manager = MagicMock()
                        agent.state_manager = MagicMock()
                        agent.knowledge_graph_manager = MagicMock()
                        agent.automation_manager = MagicMock()
                        agent.npc_manager = MagicMock()
                        agent.decision_engine = MagicMock()

                        yield agent


@pytest.mark.asyncio
async def test_connect_to_mud(mud_agent):
    """Test connecting to a MUD server."""
    # Set up the mock client to return True
    mud_agent.client.connect.return_value = True

    # Call connect_to_mud
    result = await mud_agent.connect_to_mud()

    # Check that the client was called with the right arguments
    mud_agent.client.connect.assert_called_once_with(
        host=mud_agent.config.mud.host, port=mud_agent.config.mud.port
    )

    # Check that the connection was successful
    assert result is True


@pytest.mark.asyncio
async def test_login(mud_agent):
    """Test logging in to a MUD server."""
    # Set up the mock tool to return True
    mud_agent.mud_tool.login.return_value = True

    # Call login
    result = await mud_agent.login("test_user", "test_password")

    # Check that the tool was called with the right arguments
    mud_agent.mud_tool.login.assert_called_once_with("test_user", "test_password")

    # Check that the login was successful
    assert result is True


@pytest.mark.asyncio
async def test_process_command(mud_agent):
    """Test processing a command."""
    # Set up the mock tool to return a response
    mud_agent.command_processor.process_command = AsyncMock(return_value="Test response")

    # Call process_command
    result = await mud_agent.send_command("look")

    # Check that the tool was called with the right arguments
    mud_agent.command_processor.process_command.assert_called_once_with("look", False)

    # send_command does not return the response; it forwards and returns None
    assert result is None


@pytest.mark.asyncio
async def test_enable_automation(mud_agent):
    """Test enabling automation."""
    # Set up the mock automation manager
    mud_agent.automation_manager.enable_automation = AsyncMock()

    # Enable automation
    await mud_agent.enable_automation("test context")

    # Verify automation was enabled
    mud_agent.automation_manager.enable_automation.assert_called_once_with(
        "test context"
    )


def test_disable_automation(mud_agent):
    """Test disabling automation."""
    # Disable automation
    mud_agent.disable_automation()

    # Verify automation was disabled
    mud_agent.automation_manager.disable_automation.assert_called_once()


def test_get_status_prompt(mud_agent):
    """Test getting the status prompt."""
    # Mock the status manager
    mud_agent.state_manager.get_status_prompt = MagicMock(return_value="Test prompt")

    # Get the status prompt
    prompt = mud_agent.get_status_prompt()

    # Verify the status prompt was returned
    assert prompt == "Test prompt"
    mud_agent.state_manager.get_status_prompt.assert_called_once()


@pytest.mark.asyncio
async def test_find_and_hunt_npcs(mud_agent):
    """Test finding and hunting NPCs."""
    # Mock the NPC manager
    mud_agent.npc_manager.find_and_hunt_npcs = AsyncMock(return_value=True)

    # Find and hunt NPCs
    result = await mud_agent.find_and_hunt_npcs("goblin", True)

    # Verify the NPC manager was called
    mud_agent.npc_manager.find_and_hunt_npcs.assert_called_once_with("goblin", True)
    assert result is True


@pytest.mark.asyncio
async def test_find_and_navigate_to_npc(mud_agent):
    """Test finding and navigating to an NPC."""
    # Mock the NPC manager
    mud_agent.npc_manager.find_and_navigate_to_npc = AsyncMock(return_value=True)

    # Find and navigate to an NPC
    result = await mud_agent.find_and_navigate_to_npc("shopkeeper", True)

    # Verify the NPC manager was called
    mud_agent.npc_manager.find_and_navigate_to_npc.assert_called_once_with(
        "shopkeeper", True
    )
    assert result is True





@pytest.mark.asyncio
async def test_get_knowledge_graph_summary(mud_agent):
    """Test getting the knowledge graph summary."""
    # Mock the knowledge graph manager
    mud_agent.mcp_manager.get_knowledge_graph_summary_formatted = AsyncMock(
        return_value="Test summary"
    )

    # Get the knowledge graph summary
    result = await mud_agent.get_knowledge_graph_summary()

    # Verify the knowledge graph manager was called
    mud_agent.mcp_manager.get_knowledge_graph_summary_formatted.assert_called_once()
    assert result == "Test summary"


def test_sync_worker_created_when_enabled(config):
    """SyncWorker should be created when sync_enabled is True and DATABASE_URL is set."""
    config.database.sync_enabled = True
    config.database.url = "postgresql://user:pass@host/db"
    config.database.sync_interval = 10.0

    with patch("mud_agent.agent.mud_agent.SyncWorker") as MockSyncWorker:
        mock_worker = MagicMock()
        MockSyncWorker.return_value = mock_worker

        with patch("smolagents.LiteLLMModel"):
            agent = MUDAgent(config)

        assert agent.sync_worker is not None
        MockSyncWorker.assert_called_once_with(sync_interval=10.0)


def test_sync_worker_not_created_when_disabled(config):
    """SyncWorker should not be created when sync_enabled is False."""
    config.database.sync_enabled = False

    with patch("smolagents.LiteLLMModel"):
        agent = MUDAgent(config)

    assert agent.sync_worker is None
