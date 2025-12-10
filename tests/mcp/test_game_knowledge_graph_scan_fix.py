"""
Tests for the GameKnowledgeGraph scan fix and IntegrityError handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from peewee import IntegrityError, DoesNotExist

# Import helper to add src to Python path
from test_helper import *

from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph, RoomExit


@pytest.mark.asyncio
class TestGameKnowledgeGraphScanFix:
    """Tests for the GameKnowledgeGraph scan fix and IntegrityError handling."""

    async def test_record_exit_success_ignores_scan(self):
        """Test that record_exit_success ignores the 'scan' command."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock the database context manager
        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="n",
                move_cmd="scan",
            )

            # verify that logger.debug was called with the skip message
            kg.logger.debug.assert_called_with("Skipping exit recording for non-movement command: scan")

    def test_get_or_create_exit_handles_integrity_error(self):
        """Test that get_or_create_exit handles IntegrityError."""
        kg = GameKnowledgeGraph()
        kg.logger = MagicMock()

        from_room = MagicMock()
        from_room.exits.where.return_value.get.side_effect = [DoesNotExist, MagicMock()] # Fail first get, succeed second

        # Mock RoomExit.create to raise IntegrityError
        with patch("mud_agent.mcp.game_knowledge_graph.RoomExit.create", side_effect=IntegrityError):
            kg.get_or_create_exit(from_room, "n")

            # Verify warning was logged
            kg.logger.warning.assert_called_with("IntegrityError creating exit n, retrying get")

            # Verify it tried to get the exit again (implied by the side_effect sequence)
            assert from_room.exits.where.return_value.get.call_count == 2


