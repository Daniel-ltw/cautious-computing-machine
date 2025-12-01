"""
Tests for the GameKnowledgeGraph enter command exclusion.
"""

import pytest
from unittest.mock import MagicMock, patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph


@pytest.mark.asyncio
class TestGameKnowledgeGraphEnter:
    """Tests for the GameKnowledgeGraph enter command exclusion."""

    async def test_record_exit_success_ignores_enter(self):
        """Test that record_exit_success ignores the 'enter' command."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock the database context manager
        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="enter",
                move_cmd="enter",
            )

            # verify that logger.debug was called with the skip message
            kg.logger.debug.assert_called_with("Skipping exit recording for ambiguous move command: enter")

    async def test_record_exit_success_allows_enter_portal(self):
        """Test that record_exit_success allows 'enter portal'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock Room.get_or_none to return None so we don't hit DB logic
        # We just want to verify it doesn't return early
        with patch("mud_agent.mcp.game_knowledge_graph.Room.get_or_none", return_value=None):
            with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
                await kg.record_exit_success(
                    from_room_num=1,
                    to_room_num=2,
                    direction="enter portal",
                    move_cmd="enter portal",
                )

                # Verify that it did NOT log the skip message
                # It will log a warning about room not found, which is expected given our mocks
                # But crucially, it passed the check
                call_args_list = kg.logger.debug.call_args_list
                skip_calls = [
                    call for call in call_args_list
                    if "Skipping exit recording for ambiguous move command" in str(call)
                ]
                assert len(skip_calls) == 0
