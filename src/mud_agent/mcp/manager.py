"""MCP Manager for handling Multi-Context Protocol operations.

This module provides a simplified interface for working with MCP servers
and tools, using on-demand context managers for tool execution.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles



# MCP Server configuration constants
ZERO = 0
DEFAULT_THOUGHT_NUMBER = 1
DEFAULT_TOTAL_THOUGHTS = 3
DEFAULT_NEXT_THOUGHT_NEEDED = True
DEFAULT_IS_REVISION = False
logger = logging.getLogger(__name__)





class MCPManager:
    """Manager for Multi-Context Protocol operations.

    This class provides methods for interacting with MCP servers through on-demand
    tool creation. Knowledge graph operations are delegated to GameKnowledgeGraph.
    """

    def __init__(self, config_path: str = ".mcp/config.json"):
        from .game_knowledge_graph import GameKnowledgeGraph
        """Initialize the MCP Manager.

        Args:
            config_path: Path to the MCP configuration file
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self.config = {}  # Will be loaded in start_server

        # Game knowledge graph manager
        self.knowledge_graph = GameKnowledgeGraph()

    async def start_server(self) -> None:
        """Initialize the MCP Manager.

        This method loads the configuration and initializes the knowledge graph.
        """
        try:
            # Load MCP configuration
            await self._load_config()

            # Initialize the game knowledge graph
            await self.knowledge_graph.initialize()

            self.logger.info("MCP server started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}", exc_info=True)

    async def _load_config(self) -> None:
        """Load MCP configuration from file."""
        try:
            # Ensure config directory exists
            config_path = Path(self.config_path)
            config_dir = config_path.parent
            config_dir.mkdir(parents=True, exist_ok=True)

            # Check if config file exists
            if not config_path.exists():
                self.logger.warning(
                    f"Config file {self.config_path} not found. Using default configuration."
                )
                # Create a default config
                default_config = {
                    "Knowledge Graph Memory Server": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-memory"],
                        "env": {},
                    },
                    "Sequential Thinking MCP Server": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-sequential-thinking"],
                        "env": {},
                    },
                }

                # Save default config
                async with aiofiles.open(config_path, "w") as f:
                    await f.write(json.dumps(default_config, indent=2))

                self.config = default_config
            else:
                # Load existing config
                async with aiofiles.open(config_path) as f:
                    config_content = await f.read()
                    self.config = json.loads(config_content)

            # Log the configuration
            self.logger.info(
                f"Loaded MCP configuration with {len(self.config)} servers"
            )
        except Exception as e:
            self.logger.error(f"Failed to load MCP configuration: {e}", exc_info=True)
            self.logger.info("Will use local storage for all functionality")

    async def stop_server(self) -> None:
        """Clean up resources.

        This method cleans up the knowledge graph before exiting.
        """
        try:
            await self.knowledge_graph.cleanup()
            self.logger.debug("Cleaned up resources and stopped MCP server")
        except Exception as e:
            self.logger.error(f"Error stopping MCP server: {e}")

    # Context manager support
    async def __aenter__(self):
        """Async context manager entry."""
        try:
            await self.start_server()
            return self
        except Exception as e:
            self.logger.error(f"Error starting MCP manager: {e}", exc_info=True)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        try:
            await self.stop_server()
        except Exception as e:
            self.logger.error(f"Error stopping MCP manager: {e}", exc_info=True)
            # Don't re-raise exceptions during cleanup
