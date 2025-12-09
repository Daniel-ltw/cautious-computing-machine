
import pytest
from unittest.mock import MagicMock, patch
from mud_agent.mcp.game_knowledge_graph import GameKnowledgeGraph

@pytest.mark.asyncio
class TestGameKnowledgeGraphEnterCollision:
    """Tests for collision handling of 'enter' commands."""

    async def test_record_exit_success_collision(self):
        """Test that 'enter portal' is created even if 'enter hut' exists pointing to a different room."""
        kg = GameKnowledgeGraph()
        kg._initialized = True
        kg.logger = MagicMock()

        with patch("mud_agent.mcp.game_knowledge_graph.db.atomic"), \
             patch("mud_agent.mcp.game_knowledge_graph.Room") as MockRoom, \
             patch("mud_agent.mcp.game_knowledge_graph.RoomExit") as MockRoomExit, \
             patch("mud_agent.mcp.game_knowledge_graph.Entity") as MockEntity, \
             patch("mud_agent.mcp.game_knowledge_graph.DoesNotExist", Exception):

            # Setup mock rooms
            mock_from_room = MagicMock()
            mock_from_room.room_number = 1

            # Existing exit: "enter hut" -> Room 2
            mock_exit_hut = MagicMock()
            mock_exit_hut.direction = "enter hut"
            mock_exit_hut.to_room_number = 2

            mock_exits = MagicMock()
            mock_exits.__iter__.return_value = [mock_exit_hut]
            mock_from_room.exits = mock_exits

            mock_to_room_3 = MagicMock()
            mock_to_room_3.room_number = 3

            MockRoom.get_or_none.side_effect = [mock_from_room, mock_to_room_3]

            # Setup mock exit creation
            kg.get_or_create_exit = MagicMock()

            # Call record_exit_success with "enter jet" -> Room 3
            await kg.record_exit_success(
                from_room_num=1,
                to_room_num=3,
                direction="enter jet",
                move_cmd="enter jet",
            )

            # It SHOULD call get_or_create_exit for "enter jet" -> Room 3
            # Because "enter hut" -> Room 2 is NOT the correct exit.
            kg.get_or_create_exit.assert_called_with(
                mock_from_room, "enter jet", to_room=mock_to_room_3, to_room_number=3
            )
