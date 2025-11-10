"""
Vitals static widgets for the MUD agent.

This module contains static widgets for character vitals (HP, MP, MV).
"""

import logging
from typing import Any

from textual.reactive import reactive
from textual.widgets import Static

from .base import BaseWidget
from .state_listener import StateListener

logger = logging.getLogger(__name__)


class BaseVitalStaticWidget(StateListener, BaseWidget):
    """Base class for all vital static widgets."""

    # Enable vitals event registration
    register_for_vitals_events = True

    # CSS for styling
    CSS = """
    BaseVitalStaticWidget {
        width: 1fr;
        height: 1;
        padding: 0 1;
        margin: 0 1;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    Static {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        text-align: center;
        content-align: center middle;
    }
    """

    # Reactive attributes
    current_value = reactive(0)  # Default current value
    max_value = reactive(0)  # Default max value

    # Configuration for subclasses
    vital_name: str = ""  # Override in subclasses: "hp", "mp", "mv"
    vital_aliases: tuple[str, ...] = ()  # Override in subclasses with alternative names
    max_key: str = ""  # Override in subclasses: "maxhp", "maxmana", "maxmoves"

    # Display configuration
    text_color: str = "white"  # Override in subclasses

    def __init__(self, *args, **kwargs):
        """Initialize the widget."""
        super().__init__(*args, **kwargs)
        if not self.vital_name:
            raise ValueError(f"{self.__class__.__name__} must define vital_name")
        if not self.max_key:
            raise ValueError(f"{self.__class__.__name__} must define max_key")

        # Create the static widget
        self.static_widget = Static(
            f"[{self.text_color}]{self.vital_name.upper()}: {self.current_value}/{self.max_value}[/{self.text_color}]",
            id=f"{self.vital_name}-static",
        )

    def compose(self):
        """Compose the widget."""
        yield self.static_widget

    def watch_current_value(self, old_value: int, new_value: int) -> None:
        """Watch for changes in current_value and update display."""
        self.update_display()

    def watch_max_value(self, old_value: int, new_value: int) -> None:
        """Watch for changes in max_value and update display."""
        self.update_display()

    def on_mount(self):
        """Called when the widget is mounted."""
        logger.debug(f"{self.__class__.__name__} mounted")

        # Set initial values
        self.update_display()

        # Ensure the widget is visible
        self.styles.display = "block"
        self.styles.visibility = "visible"
        self.styles.opacity = 1.0
        logger.debug(
            f"{self.__class__.__name__} display: {self.styles.display}, visibility: {self.styles.visibility}, opacity: {self.styles.opacity}"
        )

    def update_display(self):
        """Update the display based on current and max values."""
        try:
            # Check if static_widget exists (widget might not be fully initialized yet)
            if not hasattr(self, 'static_widget') or self.static_widget is None:
                logger.debug(f"{self.__class__.__name__} static_widget not yet initialized, skipping update")
                return

            # Format the values with commas for better readability
            current_formatted = f"{self.current_value:,}"
            max_formatted = f"{self.max_value:,}"

            # Calculate percentage for color coding
            percentage = 100.0
            if self.max_value > 0:
                percentage = (self.current_value / self.max_value) * 100.0

            # Choose color based on percentage
            color = self.text_color
            if percentage <= 25:
                color = "bold red"
            elif percentage <= 50:
                color = "yellow"
            elif percentage <= 75:
                color = "green"

            # Update the static widget with formatted values and appropriate color
            self.static_widget.update(
                f"[{color}]{self.vital_name.upper()}: {current_formatted}/{max_formatted}[/{color}]"
            )

            logger.debug(
                f"Updated static widget to {self.current_value}/{self.max_value}"
            )
        except Exception as e:
            logger.error(f"Error updating static widget: {e}", exc_info=True)

    def _extract_value_from_dict(
        self, data: dict[str, Any], key: str, subkey: str | None = None
    ) -> int | float | None:
        """Extract a value from a dictionary, handling various data formats."""
        if key not in data:
            return None

        value = data[key]

        if subkey and isinstance(value, dict) and subkey in value:
            extracted = value[subkey]
            try:
                if isinstance(extracted, str) or isinstance(extracted, float):
                    return int(extracted)
                return extracted
            except (ValueError, TypeError):
                return extracted
        elif not subkey and isinstance(value, (int, float)):
            return value
        elif not subkey and isinstance(value, str):
            try:
                return int(value)
            except (ValueError, TypeError):
                return value

        return None

    def _update_current_value(
        self, value: int | float, source: str = "unknown"
    ) -> None:
        """Update the current value and refresh the display."""
        if value is not None:
            try:
                if isinstance(value, str) or isinstance(value, float):
                    value = int(value)
            except (ValueError, TypeError):
                pass

            self.current_value = value
            self.update_display()

    def _update_max_value(self, value: int | float, source: str = "unknown") -> None:
        """Update the max value and refresh the display."""
        if value is not None:
            try:
                if isinstance(value, str) or isinstance(value, float):
                    value = int(value)
            except (ValueError, TypeError):
                pass

            self.max_value = value
            self.update_display()

    def _on_vitals_update(self, updates: dict[str, Any]) -> None:
        """Handle a vitals update event."""
        try:
            # Check for current value
            current = self._extract_value_from_dict(updates, self.vital_name, "current")
            if current is not None:
                self._update_current_value(current, "vitals_update current")

            # Check for max value
            max_val = self._extract_value_from_dict(updates, self.vital_name, "max")
            if max_val is not None:
                self._update_max_value(max_val, "vitals_update max")
        except Exception as e:
            logger.error(f"Error in _on_vitals_update: {e}", exc_info=True)

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event."""
        try:
            # Check for vital in the vitals section
            if "vitals" in updates and self.vital_name in updates["vitals"]:
                vital_data = updates["vitals"][self.vital_name]
                if isinstance(vital_data, dict):
                    if "current" in vital_data:
                        self._update_current_value(
                            vital_data["current"], "state_update vitals current"
                        )
                    if "max" in vital_data:
                        self._update_max_value(
                            vital_data["max"], "state_update vitals max"
                        )
        except Exception as e:
            logger.error(f"Error in _on_state_update: {e}", exc_info=True)


class HPStaticWidget(BaseVitalStaticWidget):
    """Widget that displays HP as static text."""

    # CSS for styling
    CSS = """
    HPStaticWidget {
        width: 1fr;
        height: 1;
        padding: 0 1;
        margin: 0 1;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #hp-static {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        text-align: center;
        content-align: center middle;
    }
    """

    # Configuration
    vital_name = "hp"
    vital_aliases = ("health",)
    max_key = "maxhp"

    # Display configuration
    text_color = "#66BB6A 80%"


class MPStaticWidget(BaseVitalStaticWidget):
    """Widget that displays MP as static text."""

    # CSS for styling
    CSS = """
    MPStaticWidget {
        width: 1fr;
        height: 1;
        padding: 0 1;
        margin: 0 1;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #mp-static {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        text-align: center;
        content-align: center middle;
    }
    """

    # Configuration
    vital_name = "mp"
    vital_aliases = ("mana",)
    max_key = "maxmana"

    # Display configuration
    text_color = "#03A9F4 80%"


class MVStaticWidget(BaseVitalStaticWidget):
    """Widget that displays MV as static text."""

    # CSS for styling
    CSS = """
    MVStaticWidget {
        width: 1fr;
        height: 1;
        padding: 0 1;
        margin: 0 1;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    #mv-static {
        width: 100%;
        height: 1;
        padding: 0;
        margin: 0;
        border: none;
        background: transparent;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        text-align: center;
        content-align: center middle;
    }
    """

    # Configuration
    vital_name = "mv"
    vital_aliases = ("moves", "movement")
    max_key = "maxmoves"

    # Display configuration
    text_color = "#FFF176 80%"
