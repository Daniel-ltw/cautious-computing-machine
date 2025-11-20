import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from mud_agent.state.state_manager import StateManager

class TestStateManager:
    @pytest.fixture
    def state_manager(self):
        """Create a StateManager instance with mocked dependencies."""
        agent = MagicMock()
        agent.app = MagicMock()
        # Mock call_from_thread to execute immediately
        agent.app.call_from_thread = MagicMock(side_effect=lambda func, *args, **kwargs: func(*args, **kwargs))

        event_manager = MagicMock()

        manager = StateManager(agent=agent, event_manager=event_manager)
        return manager

    def test_initialization(self, state_manager):
        """Test StateManager initialization."""
        assert state_manager.character_name == ""
        assert state_manager.level == 0
        assert state_manager.hp_current == 0
        assert state_manager.hunger_current == 100
        assert state_manager.room_name == "Unknown"
        assert state_manager.events is not None

    def test_update_character_info(self, state_manager):
        """Test updating character information from GMCP."""
        data = {
            "name": "Hero",
            "level": "50",
            "race": "Human",
            "class": "Warrior",
            "subclass": "Paladin",
            "alignment": "1000",
            "clan": "Guardians",
            "remorts": "2",
            "tier": "1"
        }

        state_manager.update_from_aardwolf_gmcp(data)

        assert state_manager.character_name == "Hero"
        assert state_manager.level == 50
        assert state_manager.race == "Human"
        assert state_manager.character_class == "Warrior"
        assert state_manager.subclass == "Paladin"
        assert state_manager.alignment == "1000"
        assert state_manager.clan == "Guardians"
        assert state_manager.remorts == 2
        assert state_manager.tier == 1

        # Verify event emission
        state_manager.events.emit.assert_called()
        call_args = state_manager.events.emit.call_args
        assert call_args[0][0] == "character_update"
        assert call_args[0][1]["character_name"] == "Hero"

    def test_update_vitals(self, state_manager):
        """Test updating vitals from GMCP."""
        data = {
            "hp": "1000",
            "maxhp": "1000",
            "mana": "500",
            "maxmana": "500",
            "moves": "200",
            "maxmoves": "200"
        }

        state_manager.update_from_aardwolf_gmcp(data)

        assert state_manager.hp_current == 1000
        assert state_manager.hp_max == 1000
        assert state_manager.mp_current == 500
        assert state_manager.mp_max == 500
        assert state_manager.mv_current == 200
        assert state_manager.mv_max == 200

        # Verify event emission
        state_manager.events.emit.assert_called()
        # Check for vitals_update event
        calls = [call for call in state_manager.events.emit.mock_calls if call.args[0] == "vitals_update"]
        assert len(calls) > 0
        vitals_data = calls[0].args[1]
        assert vitals_data["hp"]["current"] == 1000

    def test_update_stats(self, state_manager):
        """Test updating stats from GMCP."""
        data = {
            "str": "18",
            "int": "15",
            "wis": "14",
            "dex": "16",
            "con": "17",
            "luck": "12",
            "hr": "50",
            "dr": "20",
            "maxstr": "20",
            "maxint": "20"
        }

        state_manager.update_from_aardwolf_gmcp(data)

        assert state_manager.str_value == 18
        assert state_manager.int_value == 15
        assert state_manager.hr_value == 50
        assert state_manager.str_max == 20
        assert state_manager.int_max == 20

        # Verify event emission
        calls = [call for call in state_manager.events.emit.mock_calls if call.args[0] == "stats_update"]
        assert len(calls) > 0
        stats_data = calls[0].args[1]
        assert stats_data["str_value"] == 18

    def test_update_worth(self, state_manager):
        """Test updating worth (gold, xp, etc.) from GMCP."""
        data = {
            "gold": "5000",
            "bank": "100000",
            "xp": "123456",
            "qp": "50",
            "tp": "10"
        }

        state_manager.update_from_aardwolf_gmcp(data)

        assert state_manager.gold == 5000
        assert state_manager.bank == 100000
        assert state_manager.experience == 123456
        assert state_manager.quest_points == 50
        assert state_manager.trivia_points == 10

        # Verify event emission
        calls = [call for call in state_manager.events.emit.mock_calls if call.args[0] == "worth_update"]
        assert len(calls) > 0
        worth_data = calls[0].args[1]
        assert worth_data["gold"] == 5000
        assert worth_data["xp"] == 123456

    def test_update_needs(self, state_manager):
        """Test updating hunger and thirst."""
        # Test with simple integers
        data = {
            "hunger": "50",
            "thirst": "60"
        }
        state_manager.update_from_aardwolf_gmcp(data)
        assert state_manager.hunger_current == 50
        assert state_manager.thirst_current == 60

        # Test with dict-like string (common in some GMCP implementations)
        data_complex = {
            "hunger": "{'current': 20, 'max': 100}",
            "thirst": "{'current': 10, 'max': 100}"
        }
        state_manager.update_from_aardwolf_gmcp(data_complex)
        assert state_manager.hunger_current == 20
        assert state_manager.thirst_current == 10

    def test_update_room_info_gmcp(self, state_manager):
        """Test updating room info from GMCP manager."""
        gmcp_manager = MagicMock()
        gmcp_manager.get_all_character_data.return_value = {}
        gmcp_manager.get_room_info.return_value = {
            "name": "Town Square",
            "num": 12345,
            "area": "Midgaard",
            "terrain": "city",
            "coords": {"x": 0, "y": 0},
            "exits": {"n": 12346},
            "details": "A busy square."
        }

        state_manager.update_from_gmcp(gmcp_manager)

        assert state_manager.room_name == "Town Square"
        assert state_manager.room_num == 12345
        assert state_manager.area_name == "Midgaard"
        assert state_manager.room_terrain == "city"
        assert state_manager.exits == {"n": 12346}

        # Verify event emission
        calls = [call for call in state_manager.events.emit.mock_calls if call.args[0] == "room_update"]
        assert len(calls) > 0
        room_data = calls[0].args[1]
        assert room_data["name"] == "Town Square"

    def test_handle_state_update(self, state_manager):
        """Test handling state updates via event handler."""
        updates = {
            "room": {
                "area": "New Area",
                "terrain": "forest",
                "num": 999
            }
        }

        state_manager.handle_state_update(updates)

        assert state_manager.area_name == "New Area"
        assert state_manager.room_terrain == "forest"
        assert state_manager.room_num == 999

    @pytest.mark.asyncio
    async def test_listeners(self, state_manager):
        """Test registering and notifying listeners."""
        callback = AsyncMock()
        state_manager.register_listener("test_listener", callback)

        await state_manager.notify_listeners("test_key", "test_value")

        callback.assert_called_with("test_key", "test_value")

        state_manager.unregister_listener("test_listener")
        await state_manager.notify_listeners("test_key", "new_value")

        # Should not be called again
        assert callback.call_count == 1

    def test_get_current_room_data(self, state_manager):
        """Test retrieving current room data."""
        state_manager.room_name = "Test Room"
        state_manager.room_num = 100
        state_manager.area_name = "Test Area"

        data = state_manager.get_current_room_data()

        assert data["name"] == "Test Room"
        assert data["num"] == 100
        assert data["area"] == "Test Area"
