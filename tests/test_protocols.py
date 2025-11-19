"""
Tests for the protocol handlers.
"""

import pytest

# Import helper to add src to Python path
from test_helper import *

from mud_agent.protocols import ColorHandler, GMCPHandler, MSDPHandler, TelnetBytes


class TestTelnetBytes:
    """Tests for the TelnetBytes class."""

    def test_constants(self):
        """Test that the constants are defined correctly."""
        assert TelnetBytes.IAC == 255
        assert TelnetBytes.WILL == 251
        assert TelnetBytes.WONT == 252
        assert TelnetBytes.DO == 253
        assert TelnetBytes.DONT == 254
        assert TelnetBytes.SB == 250
        assert TelnetBytes.SE == 240
        assert TelnetBytes.GMCP == 201


class TestGMCPHandler:
    """Tests for the GMCPHandler class."""

    @pytest.fixture
    def gmcp_handler(self):
        """Create a GMCPHandler instance for testing."""
        return GMCPHandler()

    def test_initialization(self, gmcp_handler):
        """Test that the handler is initialized correctly."""
        assert gmcp_handler.enabled is True
        assert isinstance(gmcp_handler.data, dict)
        assert isinstance(gmcp_handler.callbacks, list)
        assert isinstance(gmcp_handler.module_callbacks, dict)
        assert isinstance(gmcp_handler.supported_modules, set)

    def test_handle_message(self, gmcp_handler):
        """Test handling a GMCP message."""
        # Test with a simple message
        gmcp_handler.handle_message('char.base {"name": "Test", "level": 1}')

        # Check that the data was stored correctly
        assert "char" in gmcp_handler.data
        assert "base" in gmcp_handler.data["char"]
        assert gmcp_handler.data["char"]["base"]["name"] == "Test"
        assert gmcp_handler.data["char"]["base"]["level"] == 1

        # Test with a message without data
        gmcp_handler.handle_message("room.info")

        # Check that the module was stored
        assert "room" in gmcp_handler.data
        assert "info" in gmcp_handler.data["room"]
        assert gmcp_handler.data["room"]["info"] == {}

        # Check that the modules were added to supported_modules
        assert "char.base" in gmcp_handler.supported_modules
        assert "room.info" in gmcp_handler.supported_modules

    def test_get_module_data(self, gmcp_handler):
        """Test getting module data."""
        # Set up test data
        gmcp_handler.data = {"char": {"base": {"name": "Test", "level": 1}}}

        # Test getting existing data
        result = gmcp_handler.get_module_data("char.base")
        assert result == {"name": "Test", "level": 1}

        # Test getting non-existent data
        result = gmcp_handler.get_module_data("char.stats")
        assert result is None

    def test_register_callback(self, gmcp_handler):
        """Test registering a callback."""

        def callback(module, data):
            pass

        # Register the callback
        gmcp_handler.register_callback(callback)

        # Check that the callback was registered
        assert callback in gmcp_handler.callbacks

        # Register the same callback again
        gmcp_handler.register_callback(callback)

        # Check that the callback was not registered twice
        assert len(gmcp_handler.callbacks) == 1

    def test_register_module_callback(self, gmcp_handler):
        """Test registering a module-specific callback."""

        def callback(module, data):
            pass

        # Register the callback for a specific module
        gmcp_handler.register_module_callback("char.base", callback)

        # Check that the callback was registered
        assert "char.base" in gmcp_handler.module_callbacks
        assert callback in gmcp_handler.module_callbacks["char.base"]

        # Register the same callback again
        gmcp_handler.register_module_callback("char.base", callback)

        # Check that the callback was not registered twice
        assert len(gmcp_handler.module_callbacks["char.base"]) == 1

    def test_unregister_callback(self, gmcp_handler):
        """Test unregistering a callback."""

        def callback(module, data):
            pass

        # Register the callback
        gmcp_handler.register_callback(callback)

        # Unregister the callback
        gmcp_handler.unregister_callback(callback)

        # Check that the callback was unregistered
        assert callback not in gmcp_handler.callbacks

    def test_unregister_module_callback(self, gmcp_handler):
        """Test unregistering a module-specific callback."""

        def callback(module, data):
            pass

        # Register the callback for a specific module
        gmcp_handler.register_module_callback("char.base", callback)

        # Unregister the callback
        gmcp_handler.unregister_module_callback("char.base", callback)

        # Check that the callback was unregistered
        assert callback not in gmcp_handler.module_callbacks["char.base"]

    def test_callback_execution(self, gmcp_handler):
        """Test that callbacks are executed when data changes."""
        # Set up test data
        called = {"general": False, "module": False, "parent": False}

        def general_callback(module, data):
            called["general"] = True

        def module_callback(module, data):
            called["module"] = True

        def parent_callback(module, data):
            called["parent"] = True

        # Register callbacks
        gmcp_handler.register_callback(general_callback)
        gmcp_handler.register_module_callback("char.base", module_callback)
        gmcp_handler.register_module_callback("char", parent_callback)

        # Handle a message that should trigger all callbacks
        gmcp_handler.handle_message('char.base {"name": "Test", "level": 1}')

        # Check that all callbacks were called
        assert called["general"] is True
        assert called["module"] is True
        assert called["parent"] is True

    def test_convenience_methods(self, gmcp_handler):
        """Test convenience methods for accessing common GMCP data."""
        # Set up test data
        gmcp_handler.data = {
            "char": {
                "base": {"name": "Test", "level": 1},
                "vitals": {"hp": 100, "mana": 100},
                "stats": {"str": 10, "int": 10},
            },
            "room": {"info": {"name": "Test Room", "exits": ["north", "south"]}},
        }

        # Test convenience methods
        assert gmcp_handler.get_char_data() == {
            "base": {"name": "Test", "level": 1},
            "vitals": {"hp": 100, "mana": 100},
            "stats": {"str": 10, "int": 10},
        }
        assert gmcp_handler.get_room_data() == {
            "info": {"name": "Test Room", "exits": ["north", "south"]}
        }
        assert gmcp_handler.get_vitals() == {"hp": 100, "mana": 100}
        assert gmcp_handler.get_stats() == {"str": 10, "int": 10}
        assert gmcp_handler.get_room_info() == {
            "name": "Test Room",
            "exits": ["north", "south"],
        }


class TestMSDPHandler:
    """Tests for the MSDPHandler class."""

    @pytest.fixture
    def msdp_handler(self):
        """Create a MSDPHandler instance for testing."""
        return MSDPHandler()

    def test_initialization(self, msdp_handler):
        """Test that the handler is initialized correctly."""
        assert msdp_handler.enabled is True
        assert isinstance(msdp_handler.data, dict)


class TestColorHandler:
    """Tests for the ColorHandler class."""

    @pytest.fixture
    def color_handler(self):
        """Create a ColorHandler instance for testing."""
        return ColorHandler()

    def test_initialization(self, color_handler):
        """Test that the handler is initialized correctly."""
        assert color_handler.enabled is True

    def test_strip_color(self, color_handler):
        """Test stripping color codes."""
        # Test with a string containing color codes
        result = color_handler.strip_color("\x1b[31mRed text\x1b[0m")

        # Check that the color codes were removed
        assert result == "Red text"

    def test_colorize(self, color_handler):
        """Test adding color codes."""
        # Test adding color to a string
        result = color_handler.colorize("Test", "31")

        # Check that the color codes were added
        assert result == "\x1b[31mTest\x1b[0m"
