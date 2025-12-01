"""
Tests for preventing recording of chain commands and other disallowed commands in GameKnowledgeGraph.
"""

import pytest
from unittest.mock import MagicMock, patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph


@pytest.mark.asyncio
class TestGameKnowledgeGraphChainCommand:
    """Tests for preventing recording of chain commands."""

    async def test_record_exit_success_ignores_chain_in_move_cmd(self):
        """Test that record_exit_success ignores move_cmd containing ';'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n",
                move_cmd="n;s",
            )

            # Verify debug log
            kg.logger.debug.assert_called_with("Skipping exit recording for disallowed move command: n;s")

    async def test_record_exit_success_ignores_chain_in_direction(self):
        """Test that record_exit_success ignores direction containing ';'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n;s",
                move_cmd="n",
            )

            # Verify debug log
            kg.logger.debug.assert_called_with("Skipping exit recording for disallowed move command: n")

    async def test_record_exit_success_ignores_run_command(self):
        """Test that record_exit_success ignores commands starting with 'run'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n",
                move_cmd="run 5n",
            )

            # Verify debug log
            kg.logger.debug.assert_called_with("Skipping exit recording for disallowed move command: run 5n")

    async def test_record_exit_success_ignores_where_command(self):
        """Test that record_exit_success ignores 'where' command."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n",
                move_cmd="where",
            )

            # Verify debug log
            kg.logger.debug.assert_called_with("Skipping exit recording for non-movement command: where")
