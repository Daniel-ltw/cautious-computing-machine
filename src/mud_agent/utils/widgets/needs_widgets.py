"""
Needs widgets for the MUD agent.

This module contains widgets related to character needs (hunger, thirst).
"""

import logging
from typing import Any

from rich.console import Console
from textual.reactive import reactive

from .base import BaseWidget

# Constants for hunger/thirst thresholds (0-100 scale)
FULL_THRESHOLD = 90
SATIATED_THRESHOLD = 70
HUNGRY_THRESHOLD = 30
STARVING_THRESHOLD = 0
from .state_listener import StateListener

logger = logging.getLogger(__name__)
console = Console()


class HungerWidget(StateListener, BaseWidget):
    """Widget that displays character hunger.

    This widget uses the StateListener to listen for needs events.
    """

    # Reactive attributes
    current = reactive(0)
    maximum = reactive(0)
    text = reactive("Unknown")

    # Register for specific event types
    register_for_needs_events = True

    def watch_current(self, new_value: int) -> None:
        """Watch for changes to the current value and update the widget."""
        self.update_content()

    def watch_maximum(self, new_value: int) -> None:
        """Watch for changes to the maximum value and update the widget."""
        self.update_content()

    def watch_text(self, new_text: str) -> None:
        """Watch for changes to the text value and update the widget."""
        self.update_content()

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            # If we have raw values, calculate the text
            if self.maximum > 0 and isinstance(self.current, (int, float)):
                # Use direct value comparison for 0-100 scale
                hunger_text = (
                    "Full"
                    if self.current >= FULL_THRESHOLD
                    else "Satiated"
                    if self.current >= SATIATED_THRESHOLD
                    else "Hungry"
                    if self.current >= HUNGRY_THRESHOLD
                    else "Starving"
                )
            else:
                # Use the provided text if available
                hunger_text = (
                    self.text if self.text and self.text != "Unknown" else "Unknown"
                )

            # Add color formatting based on hunger level
            if hunger_text == "Starving":
                hunger_text = "[red]Starving[/]"
            elif hunger_text == "Hungry":
                hunger_text = "[yellow]Hungry[/]"
            elif hunger_text == "Satiated":
                hunger_text = "[green]Satiated[/]"
            elif hunger_text == "Full":
                hunger_text = "[bright_green]Full[/]"

            # Create the hunger line
            self.update(f"[bold]Hunger:[/] {hunger_text}")

        except Exception as e:
            logger.error(f"Error updating hunger widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying hunger[/bold red]")

    def _on_needs_update(self, updates: dict[str, Any]) -> None:
        """Handle a needs update event.

        Args:
            updates: Dictionary of needs updates
        """
        try:
            # Update hunger values if present
            if "hunger" in updates:
                hunger_data = updates["hunger"]
                if isinstance(hunger_data, dict):
                    if "current" in hunger_data:
                        self.current = hunger_data["current"]
                    if "maximum" in hunger_data:
                        self.maximum = hunger_data["maximum"]
                    if "text" in hunger_data:
                        self.text = hunger_data["text"]
                elif isinstance(hunger_data, str):
                    self.text = hunger_data
        except Exception as e:
            logger.error(
                f"Error handling needs update in HungerWidget: {e}", exc_info=True
            )

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        try:
            # Check for needs updates
            if "needs" in updates:
                needs_updates = updates["needs"]
                self._on_needs_update(needs_updates)
        except Exception as e:
            logger.error(
                f"Error handling state update in HungerWidget: {e}", exc_info=True
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug(
            "HungerWidget using event-based updates instead of reactive binding"
        )


class ThirstWidget(StateListener, BaseWidget):
    """Widget that displays character thirst.

    This widget uses the StateListener to listen for needs events.
    """

    # Reactive attributes
    current = reactive(0)
    maximum = reactive(0)
    text = reactive("Unknown")

    # Register for specific event types
    register_for_needs_events = True

    def watch_current(self, new_value: int) -> None:
        """Watch for changes to the current value and update the widget."""
        self.update_content()

    def watch_maximum(self, new_value: int) -> None:
        """Watch for changes to the maximum value and update the widget."""
        self.update_content()

    def watch_text(self, new_text: str) -> None:
        """Watch for changes to the text value and update the widget."""
        self.update_content()

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            # If we have raw values, calculate the text
            if self.maximum > 0 and isinstance(self.current, (int, float)):
                # Use direct value comparison for 0-100 scale
                thirst_text = (
                    "Quenched"
                    if self.current >= FULL_THRESHOLD
                    else "Not Thirsty"
                    if self.current >= SATIATED_THRESHOLD
                    else "Thirsty"
                    if self.current >= HUNGRY_THRESHOLD
                    else "Parched"
                )
            else:
                # Use the provided text if available
                thirst_text = (
                    self.text if self.text and self.text != "Unknown" else "Unknown"
                )

            # Add color formatting based on thirst level
            if thirst_text == "Parched":
                thirst_text = "[red]Parched[/]"
            elif thirst_text == "Thirsty":
                thirst_text = "[yellow]Thirsty[/]"
            elif thirst_text == "Not Thirsty":
                thirst_text = "[green]Not Thirsty[/]"
            elif thirst_text == "Quenched":
                thirst_text = "[bright_green]Quenched[/]"

            # Create the thirst line
            self.update(f"[bold]Thirst:[/] {thirst_text}")

        except Exception as e:
            logger.error(f"Error updating thirst widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying thirst[/bold red]")

    def _on_needs_update(self, updates: dict[str, Any]) -> None:
        """Handle a needs update event.

        Args:
            updates: Dictionary of needs updates
        """
        try:
            # Update thirst values if present
            if "thirst" in updates:
                thirst_data = updates["thirst"]
                if isinstance(thirst_data, dict):
                    if "current" in thirst_data:
                        self.current = thirst_data["current"]
                    if "maximum" in thirst_data:
                        self.maximum = thirst_data["maximum"]
                    if "text" in thirst_data:
                        self.text = thirst_data["text"]
                elif isinstance(thirst_data, str):
                    self.text = thirst_data
        except Exception as e:
            logger.error(
                f"Error handling needs update in ThirstWidget: {e}", exc_info=True
            )

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        try:
            # Check for needs updates
            if "needs" in updates:
                needs_updates = updates["needs"]
                self._on_needs_update(needs_updates)
        except Exception as e:
            logger.error(
                f"Error handling state update in ThirstWidget: {e}", exc_info=True
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug(
            "ThirstWidget using event-based updates instead of reactive binding"
        )
