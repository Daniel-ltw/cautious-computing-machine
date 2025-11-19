"""
Stats static widgets for the MUD agent.

This module contains static widgets for character stats (STR, INT, WIS, DEX, CON, LUCK, HR, DR).
"""

import logging
from typing import Any

from textual.reactive import reactive
from textual.widgets import Static

from .base import BaseWidget
from .state_listener import StateListener

logger = logging.getLogger(__name__)


class BaseStatStaticWidget(StateListener, BaseWidget):
    """Base class for all stat static widgets."""

    # Register for stats events
    register_for_stats_events = True
    register_for_maxstats_events = True

    # CSS for styling
    CSS = """
    BaseStatStaticWidget {
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
    stat_name: str = ""  # Override in subclasses: "str", "int", "wis", etc.
    stat_aliases: tuple = ()  # Override in subclasses with alternative names
    max_key: str = ""  # Override in subclasses if needed

    # Display configuration
    text_color: str = "white"  # Override in subclasses

    def __init__(self, *args, **kwargs):
        """Initialize the widget."""
        super().__init__(*args, **kwargs)
        if not self.stat_name:
            raise ValueError(f"{self.__class__.__name__} must define stat_name")

        # Create the static widget
        self.static_widget = Static(
            f"[{self.text_color}]{self.stat_name.upper()}: {self.current_value}/{self.max_value}[/{self.text_color}]",
            id=f"{self.stat_name}-static",
        )

    def compose(self):
        """Compose the widget."""
        yield self.static_widget

    def on_mount(self):
        """Called when the widget is mounted."""
        logger.info(f"{self.__class__.__name__} mounted")

        # Set initial values
        self.update_display()

        # Ensure the widget is visible
        self.styles.display = "block"
        self.styles.visibility = "visible"
        self.styles.opacity = 1.0
        logger.info(
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
            current_formatted = (
                f"{self.current_value:,}"
                if isinstance(self.current_value, (int, float))
                else str(self.current_value)
            )
            max_formatted = (
                f"{self.max_value:,}"
                if isinstance(self.max_value, (int, float))
                else str(self.max_value)
            )

            # Update the static widget with formatted values and appropriate color
            if self.max_value > 0:
                self.static_widget.update(
                    f"[{self.text_color}]{self.stat_name.upper()}: {current_formatted}/{max_formatted}[/]"
                )
            else:
                self.static_widget.update(
                    f"[{self.text_color}]{self.stat_name.upper()}: {current_formatted}[/]"
                )

            logger.info(
                f"Updated static widget to {self.current_value}/{self.max_value}"
            )
        except Exception as e:
            logger.error(f"Error updating static widget: {e}", exc_info=True)

    def _on_stats_update(self, updates: dict[str, Any]) -> None:
        """Handle a stats update event."""
        logger.debug(f"{self.__class__.__name__} handling stats update: {updates}")
        stat_name_lower = f"{self.stat_name.lower()}_value"
        if stat_name_lower in updates:
            self.current_value = updates[stat_name_lower]
            self.update_display()

    def _on_maxstats_update(self, updates: dict[str, Any]) -> None:
        """Handle a maxstats update event."""
        logger.debug(f"{self.__class__.__name__} handling maxstats update: {updates}")
        stat_name_lower = f"{self.stat_name.lower()}_max"
        if stat_name_lower in updates:
            self.max_value = updates[stat_name_lower]
        self.update_display()


class StrStaticWidget(BaseStatStaticWidget):
    """Static widget for STR stat."""

    stat_name = "str"
    stat_aliases = ("strength",)
    max_key = "maxstr"

    # Display configuration
    text_color = "white 90%"


class IntStaticWidget(BaseStatStaticWidget):
    """Widget that displays INT as static text."""

    # CSS for styling
    CSS = """
    IntStaticWidget {
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
    """

    # Configuration
    stat_name = "int"
    stat_aliases = ("intelligence",)
    max_key = "maxint"

    # Display configuration
    text_color = "white 90%"


class WisStaticWidget(BaseStatStaticWidget):
    """Widget that displays WIS as static text."""

    # CSS for styling
    CSS = """
    WisStaticWidget {
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
    """

    # Configuration
    stat_name = "wis"
    stat_aliases = ("wisdom",)
    max_key = "maxwis"

    # Display configuration
    text_color = "white 90%"


class DexStaticWidget(BaseStatStaticWidget):
    """Widget that displays DEX as static text."""

    # CSS for styling
    CSS = """
    DexStaticWidget {
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
    """

    # Configuration
    stat_name = "dex"
    stat_aliases = ("dexterity",)
    max_key = "maxdex"

    # Display configuration
    text_color = "white 90%"


class ConStaticWidget(BaseStatStaticWidget):
    """Widget that displays CON as static text."""

    # CSS for styling
    CSS = """
    ConStaticWidget {
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
    """

    # Configuration
    stat_name = "con"
    stat_aliases = ("constitution",)
    max_key = "maxcon"

    # Display configuration
    text_color = "white 90%"


class LuckStaticWidget(BaseStatStaticWidget):
    """Widget that displays LUCK as static text."""

    # CSS for styling
    CSS = """
    LuckStaticWidget {
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
    """

    # Configuration
    stat_name = "luck"
    stat_aliases = ("lck",)
    max_key = "maxluck"

    # Display configuration
    text_color = "white 90%"


class HRStaticWidget(BaseStatStaticWidget):
    """Widget that displays HR as static text."""

    # CSS for styling
    CSS = """
    HRStaticWidget {
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
    """

    # Configuration
    stat_name = "hr"
    stat_aliases = ("hitroll",)

    # Display configuration
    text_color = "bold cyan 80%"


class DRStaticWidget(BaseStatStaticWidget):
    """Widget that displays DR as static text."""

    # CSS for styling
    CSS = """
    DRStaticWidget {
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
    """

    # Configuration
    stat_name = "dr"
    stat_aliases = ("damroll",)

    # Display configuration
    text_color = "bold magenta 80%"
