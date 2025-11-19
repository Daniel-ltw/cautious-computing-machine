"""Layout configuration system for MUD Agent UI.

Provides configurable layout options and backward compatibility.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class LayoutMode(Enum):
    """Available layout modes."""
    CLASSIC = "classic"  # Original simple layout
    MODERN = "modern"   # New grid-based layout
    COMPACT = "compact" # Minimal layout for small screens


@dataclass
class LayoutDimensions:
    """Layout dimension configuration."""
    status_height: int = 10
    command_input_height: int = 3
    map_width_percent: int = 40
    command_width_percent: int = 60
    widget_spacing: int = 1
    container_padding: int = 1


@dataclass
class LayoutConfig:
    """Complete layout configuration."""
    mode: LayoutMode = LayoutMode.CLASSIC
    dimensions: LayoutDimensions = None
    enable_responsive: bool = True
    mobile_breakpoint: int = 80
    show_header: bool = False
    show_footer: bool = False
    theme: str = "tokyo-night"

    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = LayoutDimensions()


class LayoutManager:
    """Manages layout configuration and preferences."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize layout manager.
        
        Args:
            config_dir: Directory to store configuration files
        """
        self.config_dir = config_dir or Path.home() / ".mud_agent"
        self.config_file = self.config_dir / "layout_config.json"
        self._config = self._load_config()

    def _load_config(self) -> LayoutConfig:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    data = json.load(f)
                return self._dict_to_config(data)
            except (json.JSONDecodeError, KeyError) as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Invalid layout config file, using defaults: {e}"
                )

        return LayoutConfig()

    def _dict_to_config(self, data: dict[str, Any]) -> LayoutConfig:
        """Convert dictionary to LayoutConfig."""
        dimensions_data = data.get('dimensions', {})
        dimensions = LayoutDimensions(**dimensions_data)

        config_data = data.copy()
        config_data['mode'] = LayoutMode(data.get('mode', 'classic'))
        config_data['dimensions'] = dimensions

        return LayoutConfig(**config_data)

    def _config_to_dict(self, config: LayoutConfig) -> dict[str, Any]:
        """Convert LayoutConfig to dictionary."""
        return {
            'mode': config.mode.value,
            'dimensions': {
                'status_height': config.dimensions.status_height,
                'command_input_height': config.dimensions.command_input_height,
                'map_width_percent': config.dimensions.map_width_percent,
                'command_width_percent': config.dimensions.command_width_percent,
                'widget_spacing': config.dimensions.widget_spacing,
                'container_padding': config.dimensions.container_padding,
            },
            'enable_responsive': config.enable_responsive,
            'mobile_breakpoint': config.mobile_breakpoint,
            'show_header': config.show_header,
            'show_footer': config.show_footer,
            'theme': config.theme,
        }

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_dir.mkdir(exist_ok=True)

        with open(self.config_file, 'w') as f:
            json.dump(self._config_to_dict(self._config), f, indent=2)

    @property
    def config(self) -> LayoutConfig:
        """Get current configuration."""
        return self._config

    def set_layout_mode(self, mode: LayoutMode) -> None:
        """Set layout mode and save."""
        self._config.mode = mode
        self.save_config()

    def set_dimensions(self, **kwargs) -> None:
        """Update layout dimensions."""
        for key, value in kwargs.items():
            if hasattr(self._config.dimensions, key):
                setattr(self._config.dimensions, key, value)
        self.save_config()

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = LayoutConfig()
        self.save_config()

    def get_css_variables(self) -> dict[str, str]:
        """Get CSS variables for current configuration."""
        dims = self._config.dimensions
        return {
            '--status-height': str(dims.status_height),
            '--command-input-height': str(dims.command_input_height),
            '--map-width': f"{dims.map_width_percent}%",
            '--command-width': f"{dims.command_width_percent}%",
            '--widget-spacing': str(dims.widget_spacing),
            '--container-padding': str(dims.container_padding),
        }

    def is_classic_layout(self) -> bool:
        """Check if using classic layout mode."""
        return self._config.mode == LayoutMode.CLASSIC

    def is_responsive_enabled(self) -> bool:
        """Check if responsive design is enabled."""
        return self._config.enable_responsive

    def get_mobile_breakpoint(self) -> int:
        """Get mobile breakpoint width."""
        return self._config.mobile_breakpoint


# Global layout manager instance
_layout_manager = None


def get_layout_manager() -> LayoutManager:
    """Get global layout manager instance."""
    global _layout_manager
    if _layout_manager is None:
        _layout_manager = LayoutManager()
    return _layout_manager


def set_layout_mode(mode: LayoutMode) -> None:
    """Convenience function to set layout mode."""
    get_layout_manager().set_layout_mode(mode)


def get_current_layout() -> LayoutConfig:
    """Convenience function to get current layout config."""
    return get_layout_manager().config


def is_classic_layout() -> bool:
    """Convenience function to check if using classic layout."""
    return get_layout_manager().is_classic_layout()
