"""
Tests for the GameKnowledgeGraph direction mismatch validation.
"""

import pytest
from unittest.mock import MagicMock, patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph


@pytest.mark.asyncio
class TestGameKnowledgeGraphDirectionMismatch:
    """Tests for the GameKnowledgeGraph direction mismatch validation."""

    async def test_record_exit_success_ignores_mismatch(self):
        """Test that record_exit_success ignores mismatched directions."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock the database context manager
        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            # Mismatch: move="s", direction="n"
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n",
                move_cmd="s",
            )

            # verify that logger.debug was called with the skip message
            kg.logger.debug.assert_called_with(
                "Skipping exit recording due to direction mismatch: move_cmd='s' (south) != direction='n' (north)"
            )

    async def test_record_exit_success_allows_match_short_short(self):
        """Test that record_exit_success allows matching short directions."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock Room.get_or_none to return None so we don't hit DB logic
        with patch("mud_agent.mcp.game_knowledge_graph.Room.get_or_none", return_value=None):
            with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
                # Match: move="n", direction="n"
                await kg.record_exit_success(
                    from_room_num=1,
                    to_room_num=2,
                    direction="n",
                    move_cmd="n",
                )

                # Verify NO skip message
                call_args_list = kg.logger.debug.call_args_list
                skip_calls = [
                    call for call in call_args_list
                    if "Skipping exit recording due to direction mismatch" in str(call)
                ]
                assert len(skip_calls) == 0

    async def test_record_exit_success_allows_match_short_long(self):
        """Test that record_exit_success allows matching short/long directions."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock Room.get_or_none to return None so we don't hit DB logic
        with patch("mud_agent.mcp.game_knowledge_graph.Room.get_or_none", return_value=None):
            with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
                # Match: move="n", direction="north"
                await kg.record_exit_success(
                    from_room_num=1,
                    to_room_num=2,
                    direction="north",
                    move_cmd="n",
                )

                # Verify NO skip message
                call_args_list = kg.logger.debug.call_args_list
                skip_calls = [
                    call for call in call_args_list
                    if "Skipping exit recording due to direction mismatch" in str(call)
                ]
                assert len(skip_calls) == 0

    async def test_record_exit_success_allows_non_direction_command(self):
        """Test that record_exit_success allows non-direction commands."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock Room.get_or_none to return None so we don't hit DB logic
        with patch("mud_agent.mcp.game_knowledge_graph.Room.get_or_none", return_value=None):
            with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
                # Non-direction command: move="enter portal", direction="n"
                # "enter portal" is not in DIRECTION_MAPPING, so check should be skipped
                await kg.record_exit_success(
                    from_room_num=1,
                    to_room_num=2,
                    direction="n",
                    move_cmd="enter portal",
                )

                # Verify NO skip message
                call_args_list = kg.logger.debug.call_args_list
                skip_calls = [
                    call for call in call_args_list
                    if "Skipping exit recording due to direction mismatch" in str(call)
                ]
                assert len(skip_calls) == 0
