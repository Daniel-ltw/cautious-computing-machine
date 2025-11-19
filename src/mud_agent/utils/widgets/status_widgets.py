"""
Status widgets for the MUD agent.

This module contains widgets related to character status effects.
"""

import logging
from typing import Any

from rich.console import Console
from textual.reactive import reactive

from .base import BaseWidget
from .state_listener import StateListener

logger = logging.getLogger(__name__)
console = Console()


class StatusEffectsWidget(StateListener, BaseWidget):
    """Widget that displays character status effects.

    This widget uses the StateListener to listen for status events.
    """

    # Reactive attributes
    status_effects = reactive([])

    # Register for specific event types
    register_for_status_events = True

    def on_mount(self) -> None:
        """Mount the widget."""
        self.subscribe_to_state("status_effects")

    async def update_display(self, data: Any) -> None:
        """Updates the display with the new data."""
        logger.debug(f"StatusEffectsWidget received data: {data}")
        self.status_effects = data
        self.update_content()

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            # Sixth line: Status effects (if available)
            if (
                self.status_effects
                and isinstance(self.status_effects, list)
                and len(self.status_effects) > 0
            ):
                # Filter out empty or None values and raw data values
                valid_effects = []
                raw_data_patterns = [
                    "level",
                    "int",
                    "hunger",
                    "thirst",
                    "align",
                    "state",
                    "pos",
                ]

                for effect in self.status_effects:
                    if effect and not any(
                        pattern in effect.lower() for pattern in raw_data_patterns
                    ):
                        valid_effects.append(effect)

                if valid_effects:
                    status_line = ", ".join(valid_effects)
                    # Truncate if too long
                    if len(status_line) > 70:
                        status_line = status_line[:67] + "..."
                    self.update(f"[bold]Status:[/] {status_line}")
                else:
                    # If we only have raw data values, don't display the status line
                    self.update("[bold]Status:[/] [dim]None[/]")
            else:
                self.update("[bold]Status:[/] [dim]None[/]")

        except Exception as e:
            logger.error(f"Error updating status effects widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying status effects[/bold red]")

    def _on_status_update(self, updates: dict[str, Any]) -> None:
        """Handle a status update event.

        Args:
            updates: Dictionary of status updates
        """
        try:
            # Update status effects
            if "effects" in updates:
                self.status_effects = updates["effects"]
                self.update_content()
        except Exception as e:
            logger.error(
                f"Error handling status update in StatusEffectsWidget: {e}",
                exc_info=True,
            )

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        try:
            # Check for status updates
            if "status" in updates:
                status_updates = updates["status"]
                self._on_status_update(status_updates)
        except Exception as e:
            logger.error(
                f"Error handling state update in StatusEffectsWidget: {e}",
                exc_info=True,
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug(
            "StatusEffectsWidget using event-based updates instead of reactive binding"
        )
