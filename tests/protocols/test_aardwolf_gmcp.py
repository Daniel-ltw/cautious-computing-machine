"""Tests for the Aardwolf GMCP manager."""

from unittest.mock import MagicMock, patch

import pytest

from mud_agent.protocols.aardwolf.gmcp_manager import AardwolfGMCPManager


@pytest.fixture
def gmcp_manager():
    """Create a GMCP manager for testing."""
    client = MagicMock()
    client.gmcp_enabled = True
    client.gmcp = MagicMock()
    event_manager = MagicMock()
    return AardwolfGMCPManager(client, event_manager)


def test_gmcp_manager_initialization(gmcp_manager):
    """Test that the GMCP manager initializes correctly."""
    # Check that the components are initialized
    assert hasattr(gmcp_manager, "character_processor")
    assert hasattr(gmcp_manager, "room_processor")
    assert hasattr(gmcp_manager, "map_processor")

    # Check that the data dictionaries are initialized
    assert hasattr(gmcp_manager, "char_data")
    assert hasattr(gmcp_manager, "room_data")
    assert hasattr(gmcp_manager, "map_data")

    # Check that the last update timestamps are initialized
    assert hasattr(gmcp_manager, "last_update")
    assert "char" in gmcp_manager.last_update
    assert "room" in gmcp_manager.last_update
    assert "map" in gmcp_manager.last_update


def test_update_from_gmcp(gmcp_manager):
    """Test updating from GMCP data."""
    # Mock the client's get_module_data method
    gmcp_manager.client.gmcp.get_module_data.side_effect = lambda module: {
        "char": {"name": "TestChar", "vitals": {"hp": 100, "maxhp": 100}},
        "room": {"info": {"name": "Test Room", "exits": {"north": 1, "south": 2}}},
        "room.map": "Test Map",
    }.get(module, {})

    # Mock the processors' process_data methods
    gmcp_manager.character_processor.process_data = MagicMock(
        return_value={"combined": {"name": "TestChar"}}
    )
    gmcp_manager.room_processor.process_data = MagicMock(
        return_value={"name": "Test Room"}
    )
    gmcp_manager.map_processor.process_data = MagicMock(
        return_value={"map": "Test Map"}
    )

    # Call the method
    with patch('asyncio.create_task') as mock_create_task:
        updates = gmcp_manager.update_from_gmcp()

    # Check that the client's get_module_data method was called for each module
    gmcp_manager.client.gmcp.get_module_data.assert_any_call("char")
    gmcp_manager.client.gmcp.get_module_data.assert_any_call("room")
    gmcp_manager.client.gmcp.get_module_data.assert_any_call("room.map")

    # Check that the processors' process_data methods were called
    gmcp_manager.character_processor.process_data.assert_called_once()
    gmcp_manager.room_processor.process_data.assert_called_once()
    gmcp_manager.map_processor.process_data.assert_called_once()
    mock_create_task.assert_called()

    # Check that the updates dictionary contains the expected keys
    assert "char" in updates
    assert "room" in updates
    assert "map" in updates


def test_get_character_data(gmcp_manager):
    """Test getting character data."""
    # Mock the character processor's get_character_data method
    gmcp_manager.character_processor.get_character_data = MagicMock(
        return_value={
            "vitals": {"hp": 100, "maxhp": 100},
            "stats": {"str": 18, "int": 18},
            "maxstats": {"maxstr": 18, "maxint": 18},
            "combined": {
                "name": "TestChar",
                "hp": 100,
                "maxhp": 100,
                "str": 18,
                "int": 18,
                "maxstr": 18,
                "maxint": 18,
            },
        }
    )

    # Call the method
    char_data = gmcp_manager.get_character_data()

    # Check that the character processor's get_character_data method was called
    gmcp_manager.character_processor.get_character_data.assert_called_once()

    # Check that the returned data contains the expected keys
    assert "vitals" in char_data
    assert "stats" in char_data
    assert "maxstats" in char_data
    assert "combined" in char_data

    # Check that the combined data contains the expected keys
    assert "name" in char_data["combined"]
    assert "hp" in char_data["combined"]
    assert "maxhp" in char_data["combined"]
    assert "str" in char_data["combined"]
    assert "int" in char_data["combined"]
    assert "maxstr" in char_data["combined"]
    assert "maxint" in char_data["combined"]


def test_get_room_info(gmcp_manager):
    """Test getting room information."""
    # Set the room_data['info'] directly
    gmcp_manager.room_data["info"] = {
        "name": "Test Room",
        "num": 1234,
        "area": "Test Area",
        "exits": {"north": 1, "south": 2},
        "terrain": "indoors",
        "coordinates": {"x": 10, "y": 20, "z": 0},
    }

    # Call the method
    room_info = gmcp_manager.get_room_info()

    # Check that the returned data contains the expected keys
    assert "name" in room_info
    assert "num" in room_info
    assert "area" in room_info
    assert "exits" in room_info
    assert "terrain" in room_info
    assert "coordinates" in room_info

    # Check that the values are as expected
    assert room_info["name"] == "Test Room"
    assert room_info["num"] == 1234
    assert room_info["area"] == "Test Area"
    assert room_info["exits"] == {"north": 1, "south": 2}
    assert room_info["terrain"] == "indoors"
    assert room_info["coordinates"] == {"x": 10, "y": 20, "z": 0}


def test_get_map_data(gmcp_manager):
    """Test getting map data."""
    # Call the method
    map_data = gmcp_manager.get_map_data()

    # Check that the returned data is as expected (empty string)
    assert map_data == ""
