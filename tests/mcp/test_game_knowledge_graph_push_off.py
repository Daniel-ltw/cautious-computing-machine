
import pytest
from unittest.mock import MagicMock, patch
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph

@pytest.mark.asyncio
class TestGameKnowledgeGraphPushOff:
    """Tests for recording 'push off' command."""

    async def test_record_exit_success_records_push_off(self):
        """Test that record_exit_success records 'push off'."""
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
            # We mock get_or_create_exit to verify it's called
            kg.get_or_create_exit = MagicMock()

            # Call record_exit_success
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=2,
                direction="push off",
                move_cmd="push off",
            )

            # Verify that get_or_create_exit was called
            # It should try to create an exit with direction="push off"
            kg.get_or_create_exit.assert_called_with(
                mock_from_room, "push off", to_room=mock_to_room, to_room_number=2
            )
