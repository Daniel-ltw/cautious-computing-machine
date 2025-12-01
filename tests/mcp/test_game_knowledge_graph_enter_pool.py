"""
Tests for recording 'enter pool' command in GameKnowledgeGraph.
"""

import pytest
from unittest.mock import MagicMock, patch
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph

@pytest.mark.asyncio
class TestGameKnowledgeGraphEnterPool:
    """Tests for recording 'enter pool' command."""

    async def test_record_exit_success_records_enter_pool(self):
        """Test that record_exit_success records 'enter pool'."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock database interactions
        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"), \
             patch("mud_agent.mcp.game_knowledge_graph.Room") as MockRoom, \
             patch("mud_agent.mcp.game_knowledge_graph.RoomExit") as MockRoomExit, \
             patch("mud_agent.mcp.game_knowledge_graph.Entity") as MockEntity, \
             patch("mud_agent.mcp.game_knowledge_graph.DoesNotExist", Exception):

            # Setup mock rooms
            mock_from_room = MagicMock()
            mock_from_room.room_number = 1

            # Mock exits to be iterable (empty list) AND have where method that raises DoesNotExist
            mock_exits = MagicMock()
            mock_exits.__iter__.return_value = []
            # where().get() should raise DoesNotExist (which we mocked as Exception)
            mock_query = MagicMock()
            mock_query.get.side_effect = Exception("DoesNotExist")
            mock_exits.where.return_value = mock_query

            mock_from_room.exits = mock_exits

            mock_to_room = MagicMock()
            mock_to_room.room_number = 2

            MockRoom.get_or_none.side_effect = [mock_from_room, mock_to_room]

            # Setup mock exit creation
            MockRoomExit.create = MagicMock()

            # Call record_exit_success
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="enter pool",
                move_cmd="enter pool",
            )

            # Verify that RoomExit.create was called
            # It should try to create an exit with direction="enter pool"
            MockRoomExit.create.assert_called()
            call_args = MockRoomExit.create.call_args
            assert call_args.kwargs['direction'] == "enter pool"
            assert call_args.kwargs['from_room'] == mock_from_room
            assert call_args.kwargs['to_room'] == mock_to_room

    async def test_record_exit_success_records_enter_pool_fallback(self):
        """Test that record_exit_success records 'enter pool' via fallback."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        # Mock database interactions
        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"), \
             patch("mud_agent.mcp.game_knowledge_graph.Room") as MockRoom, \
             patch("mud_agent.mcp.game_knowledge_graph.RoomExit") as MockRoomExit, \
             patch("mud_agent.mcp.game_knowledge_graph.Entity") as MockEntity, \
             patch("mud_agent.mcp.game_knowledge_graph.DoesNotExist", Exception):

            # Setup mock rooms
            mock_from_room = MagicMock()
            mock_from_room.room_number = 1

            # Mock exits to be iterable (empty list) AND have where method that raises DoesNotExist
            mock_exits = MagicMock()
            mock_exits.__iter__.return_value = []
            # where().get() should raise DoesNotExist (which we mocked as Exception)
            mock_query = MagicMock()
            mock_query.get.side_effect = Exception("DoesNotExist")
            mock_exits.where.return_value = mock_query

            mock_from_room.exits = mock_exits

            mock_to_room = MagicMock()
            mock_to_room.room_number = 2

            MockRoom.get_or_none.side_effect = [mock_from_room, mock_to_room]

            # Setup mock exit creation for fallback
            # We mock get_or_create_exit to verify it's called
            kg.get_or_create_exit = MagicMock()

            # Call record_exit_success
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="enter pool",
                move_cmd="enter pool",
            )

            # Verify that get_or_create_exit was called as fallback
            kg.get_or_create_exit.assert_called_with(
                mock_from_room, "enter pool", to_room=mock_to_room, to_room_number=2
            )
