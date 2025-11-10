"""
MUD agent package.

This package provides a MUD client and agent for interacting with MUD servers.
"""

from .agent.mud_agent import MUDAgent
from .client.mud_client import MudClient
from .client.tools.mud_client_tool import MUDClientTool
from .config.config import Config
from .mcp.manager import MCPManager

__version__ = "0.1.0"

__all__ = ["Config", "MCPManager", "MUDAgent", "MUDClientTool", "MudClient"]
