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

    async def test_fallback_does_not_overwrite_with_scan(self):
        """Test that fallback logic does not overwrite existing command with 'scan'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock Room.get_or_none
        mock_from_room = MagicMock()
        mock_to_room = MagicMock()

        # Setup existing exit
        mock_exit = MagicMock()
        mock_exit.to_room_number = 2
        mock_exit.direction = "n"
        mock_exit.command_details = '{"move_command": "original_cmd"}'
        mock_exit.get_command_details.return_value = {"move_command": "original_cmd"}

        mock_from_room.exits = [mock_exit]

        with patch("mud_agent.mcp.game_knowledge_graph.Room.get_or_none", side_effect=[mock_from_room, mock_to_room]):
            with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"):
                # Mock get_or_create_exit to fail so we hit fallback
                kg.get_or_create_exit = MagicMock(side_effect=Exception("Simulated failure"))

                # Call with a command that is NOT 'scan' but is in the ignored list for overwrite check
                # We use direction="enter" and existing exit="n" to ensure initial direction match fails
                # but fallback to_room_number match succeeds.
                await kg.record_exit_success(
                    from_room_num=1,
                    to_room_num=2,
                    direction="enter",
                    move_cmd="look",
                )

                # Verify fallback logic logged "Keeping existing command"
                kg.logger.info.assert_any_call("Fallback: Found existing exit to 2 (n). Keeping existing command.")

                # Verify record_exit_success was NOT called on the mock_exit because the command was kept
                mock_exit.record_exit_success.assert_not_called()
