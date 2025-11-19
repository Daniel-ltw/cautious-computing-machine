"""
Tests for the MCPManager class.
"""

from unittest.mock import MagicMock, mock_open, patch

import pytest

# Import helper to add src to Python path
from test_helper import *

from mud_agent.mcp.manager import MCPManager


@pytest.fixture
def mcp_manager():
    """Create an MCPManager instance for testing."""
    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs"):
            with patch("builtins.open", mock_open(read_data="{}")):
                manager = MCPManager()
                yield manager


@pytest.mark.asyncio
async def test_start_server(mcp_manager):
    """Test starting the MCP server."""
    # Call start_server
    await mcp_manager.start_server()

    # Check that the config was loaded
    assert isinstance(mcp_manager.config, dict)


@pytest.mark.asyncio
async def test_stop_server(mcp_manager):
    """Test stopping the MCP server."""
    # Mock the cleanup method
    mcp_manager.knowledge_graph.cleanup = MagicMock()

    # Call stop_server
    await mcp_manager.stop_server()

    # Check that cleanup was called
    mcp_manager.knowledge_graph.cleanup.assert_called_once()
