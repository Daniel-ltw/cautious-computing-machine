"""Tests for layout configuration system."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mud_agent.utils.textual_app.layout_config import (
    LayoutConfig,
    LayoutDimensions,
    LayoutManager,
    LayoutMode,
    get_current_layout,
    get_layout_manager,
    is_classic_layout,
    set_layout_mode,
)


class TestLayoutMode:
    """Test cases for LayoutMode enum."""

    def test_layout_mode_values(self):
        """Test LayoutMode enum values."""
        assert LayoutMode.CLASSIC.value == "classic"
        assert LayoutMode.MODERN.value == "modern"
        assert LayoutMode.COMPACT.value == "compact"

    def test_layout_mode_from_string(self):
        """Test creating LayoutMode from string."""
        assert LayoutMode("classic") == LayoutMode.CLASSIC
        assert LayoutMode("modern") == LayoutMode.MODERN
        assert LayoutMode("compact") == LayoutMode.COMPACT


class TestLayoutDimensions:
    """Test cases for LayoutDimensions dataclass."""

    def test_default_dimensions(self):
        """Test default dimension values."""
        dims = LayoutDimensions()
        assert dims.status_height == 10
        assert dims.command_input_height == 3
        assert dims.map_width_percent == 40
        assert dims.command_width_percent == 60
        assert dims.widget_spacing == 1
        assert dims.container_padding == 1

    def test_custom_dimensions(self):
        """Test custom dimension values."""
        dims = LayoutDimensions(
            status_height=15,
            command_input_height=5,
            map_width_percent=50,
            command_width_percent=50,
            widget_spacing=2,
            container_padding=2
        )
        assert dims.status_height == 15
        assert dims.command_input_height == 5
        assert dims.map_width_percent == 50
        assert dims.command_width_percent == 50
        assert dims.widget_spacing == 2
        assert dims.container_padding == 2


class TestLayoutConfig:
    """Test cases for LayoutConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LayoutConfig()
        assert config.mode == LayoutMode.CLASSIC
        assert isinstance(config.dimensions, LayoutDimensions)
        assert config.enable_responsive is True
        assert config.mobile_breakpoint == 80
        assert config.show_header is False
        assert config.show_footer is False
        assert config.theme == "tokyo-night"

    def test_custom_config(self):
        """Test custom configuration values."""
        dims = LayoutDimensions(status_height=20)
        config = LayoutConfig(
            mode=LayoutMode.MODERN,
            dimensions=dims,
            enable_responsive=False,
            mobile_breakpoint=100,
            show_header=True,
            show_footer=True,
            theme="dark"
        )
        assert config.mode == LayoutMode.MODERN
        assert config.dimensions == dims
        assert config.enable_responsive is False
        assert config.mobile_breakpoint == 100
        assert config.show_header is True
        assert config.show_footer is True
        assert config.theme == "dark"

    def test_post_init_creates_dimensions(self):
        """Test that __post_init__ creates default dimensions if None."""
        config = LayoutConfig(dimensions=None)
        assert isinstance(config.dimensions, LayoutDimensions)


class TestLayoutManager:
    """Test cases for LayoutManager class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def layout_manager(self, temp_config_dir):
        """Create a LayoutManager with temporary config directory."""
        return LayoutManager(config_dir=temp_config_dir)

    def test_init_with_custom_config_dir(self, temp_config_dir):
        """Test initialization with custom config directory."""
        manager = LayoutManager(config_dir=temp_config_dir)
        assert manager.config_dir == temp_config_dir
        assert manager.config_file == temp_config_dir / "layout_config.json"

    def test_init_with_default_config_dir(self):
        """Test initialization with default config directory."""
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = Path("/mock/home")
            manager = LayoutManager()
            assert manager.config_dir == Path("/mock/home") / ".mud_agent"

    def test_load_config_no_file(self, layout_manager):
        """Test loading config when no file exists."""
        config = layout_manager.config
        assert isinstance(config, LayoutConfig)
        assert config.mode == LayoutMode.CLASSIC

    def test_load_config_with_file(self, temp_config_dir):
        """Test loading config from existing file."""
        config_file = temp_config_dir / "layout_config.json"
        config_data = {
            "mode": "modern",
            "dimensions": {
                "status_height": 15,
                "command_input_height": 5,
                "map_width_percent": 50,
                "command_width_percent": 50,
                "widget_spacing": 2,
                "container_padding": 2
            },
            "enable_responsive": False,
            "mobile_breakpoint": 100,
            "show_header": True,
            "show_footer": True,
            "theme": "dark"
        }

        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        manager = LayoutManager(config_dir=temp_config_dir)
        config = manager.config

        assert config.mode == LayoutMode.MODERN
        assert config.dimensions.status_height == 15
        assert config.enable_responsive is False
        assert config.theme == "dark"

    def test_load_config_invalid_json(self, temp_config_dir):
        """Test loading config with invalid JSON."""
        config_file = temp_config_dir / "layout_config.json"

        with open(config_file, 'w') as f:
            f.write("invalid json")

        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            manager = LayoutManager(config_dir=temp_config_dir)
            config = manager.config

            # Should fall back to default config
            assert config.mode == LayoutMode.CLASSIC
            mock_logger.warning.assert_called()

    def test_save_config(self, layout_manager, temp_config_dir):
        """Test saving configuration to file."""
        layout_manager.save_config()

        config_file = temp_config_dir / "layout_config.json"
        assert config_file.exists()

        with open(config_file) as f:
            data = json.load(f)

        assert data["mode"] == "classic"
        assert "dimensions" in data

    def test_set_layout_mode(self, layout_manager):
        """Test setting layout mode."""
        layout_manager.set_layout_mode(LayoutMode.MODERN)
        assert layout_manager.config.mode == LayoutMode.MODERN

    def test_set_dimensions(self, layout_manager):
        """Test setting layout dimensions."""
        layout_manager.set_dimensions(
            status_height=20,
            command_input_height=5
        )

        assert layout_manager.config.dimensions.status_height == 20
        assert layout_manager.config.dimensions.command_input_height == 5
        # Other dimensions should remain unchanged
        assert layout_manager.config.dimensions.map_width_percent == 40

    def test_set_dimensions_invalid_attribute(self, layout_manager):
        """Test setting invalid dimension attribute."""
        original_height = layout_manager.config.dimensions.status_height

        # Should not raise error, just ignore invalid attributes
        layout_manager.set_dimensions(
            invalid_attribute=100,
            status_height=25
        )

        assert layout_manager.config.dimensions.status_height == 25

    def test_reset_to_defaults(self, layout_manager):
        """Test resetting configuration to defaults."""
        # Modify config first
        layout_manager.set_layout_mode(LayoutMode.MODERN)
        layout_manager.set_dimensions(status_height=20)

        # Reset to defaults
        layout_manager.reset_to_defaults()

        assert layout_manager.config.mode == LayoutMode.CLASSIC
        assert layout_manager.config.dimensions.status_height == 10

    def test_get_css_variables(self, layout_manager):
        """Test getting CSS variables."""
        css_vars = layout_manager.get_css_variables()

        expected_vars = {
            '--status-height': '10',
            '--command-input-height': '3',
            '--map-width': '40%',
            '--command-width': '60%',
            '--widget-spacing': '1',
            '--container-padding': '1',
        }

        assert css_vars == expected_vars

    def test_is_classic_layout(self, layout_manager):
        """Test checking if using classic layout."""
        assert layout_manager.is_classic_layout() is True

        layout_manager.set_layout_mode(LayoutMode.MODERN)
        assert layout_manager.is_classic_layout() is False

    def test_is_responsive_enabled(self, layout_manager):
        """Test checking if responsive design is enabled."""
        assert layout_manager.is_responsive_enabled() is True

        layout_manager._config.enable_responsive = False
        assert layout_manager.is_responsive_enabled() is False

    def test_get_mobile_breakpoint(self, layout_manager):
        """Test getting mobile breakpoint."""
        assert layout_manager.get_mobile_breakpoint() == 80

        layout_manager._config.mobile_breakpoint = 100
        assert layout_manager.get_mobile_breakpoint() == 100


class TestGlobalFunctions:
    """Test cases for global convenience functions."""

    def test_get_layout_manager_singleton(self):
        """Test that get_layout_manager returns singleton instance."""
        manager1 = get_layout_manager()
        manager2 = get_layout_manager()
        assert manager1 is manager2

    def test_set_layout_mode_global(self):
        """Test global set_layout_mode function."""
        with patch('mud_agent.utils.textual_app.layout_config.get_layout_manager') as mock_get:
            mock_manager = mock_get.return_value

            set_layout_mode(LayoutMode.MODERN)

            mock_get.assert_called_once()
            mock_manager.set_layout_mode.assert_called_once_with(LayoutMode.MODERN)

    def test_get_current_layout_global(self):
        """Test global get_current_layout function."""
        with patch('mud_agent.utils.textual_app.layout_config.get_layout_manager') as mock_get:
            mock_manager = mock_get.return_value
            mock_config = LayoutConfig()
            mock_manager.config = mock_config

            result = get_current_layout()

            assert result is mock_config
            mock_get.assert_called_once()

    def test_is_classic_layout_global(self):
        """Test global is_classic_layout function."""
        with patch('mud_agent.utils.textual_app.layout_config.get_layout_manager') as mock_get:
            mock_manager = mock_get.return_value
            mock_manager.is_classic_layout.return_value = True

            result = is_classic_layout()

            assert result is True
            mock_get.assert_called_once()
            mock_manager.is_classic_layout.assert_called_once()
