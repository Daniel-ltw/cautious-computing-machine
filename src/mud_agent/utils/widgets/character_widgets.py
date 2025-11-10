"""
Character widgets for the MUD agent.

This module contains widgets related to character information.
"""

import logging
from typing import Any

from rich.console import Console
from textual.reactive import reactive

from .base import BaseWidget
from .state_listener import StateListener

logger = logging.getLogger(__name__)
console = Console()


class CharacterHeaderWidget(StateListener, BaseWidget):
    """Widget that displays character header information.

    This widget uses the StateListener to listen for character events.
    """

    # Reactive attributes
    character_name = reactive("Unknown")
    level = reactive("Unknown")
    race = reactive("")
    character_class = reactive("")
    subclass = reactive("")
    alignment = reactive("Unknown")
    remorts = reactive(0)
    tier = reactive(0)
    clan = reactive("")

    # Register for specific event types
    register_for_character_events = True

    def on_mount(self):
        """Called when the widget is mounted."""
        # Call the parent class's on_mount method to ensure proper initialization
        super().on_mount()

    def _on_character_update(self, updates: dict[str, Any]) -> None:
        """Handle a character update event.

        Args:
            updates: Dictionary of character updates
        """
        try:
            # Update character information
            if "name" in updates:
                self.character_name = updates["name"] if updates["name"] else "Unknown"
            if "level" in updates:
                self.level = (
                    str(updates["level"])
                    if updates["level"] and updates["level"] > 0
                    else "Unknown"
                )
            if "race" in updates:
                self.race = updates["race"] if updates["race"] else ""
            if "class" in updates:
                self.character_class = updates["class"] if updates["class"] else ""
            if "subclass" in updates:
                self.subclass = updates["subclass"] if updates["subclass"] else ""
            if "alignment" in updates:
                self.alignment = (
                    updates["alignment"] if updates["alignment"] else "Unknown"
                )
            if "remorts" in updates:
                self.remorts = updates["remorts"] if updates["remorts"] else 0
            if "tier" in updates:
                self.tier = updates["tier"] if updates["tier"] else 0
            if "clan" in updates:
                self.clan = updates["clan"] if updates["clan"] else ""

            # Update the widget content
            self.update_content()
        except Exception as e:
            logger.error(
                f"Error handling character update in CharacterHeaderWidget: {e}",
                exc_info=True,
            )

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        try:
            # Check for character updates
            if "character" in updates:
                self._on_character_update(updates["character"])
        except Exception as e:
            logger.error(
                f"Error handling state update in CharacterHeaderWidget: {e}",
                exc_info=True,
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug(
            "CharacterHeaderWidget using event-based updates instead of reactive binding"
        )

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        # Create a header with character info
        # Handle the case when character_name is "Unknown" or empty
        if not self.character_name or self.character_name == "Unknown":
            character_header = "Character Info Not Available"
        else:
            character_header = f"{self.character_name} (Lvl {self.level}"

            # Add additional character info if available
            if self.race:
                character_header += f", {self.race}"
            if self.character_class:
                character_header += f", {self.character_class}"
            if self.subclass:
                character_header += f"/{self.subclass}"
            if self.alignment:
                character_header += f", {self.alignment}"
            if self.remorts and self.remorts > 0:
                character_header += f", R{self.remorts}"
            if self.tier and self.tier > 0:
                character_header += f", T{self.tier}"

            character_header += ")"

            # Add clan if available
            if self.clan:
                character_header += f" [{self.clan}]"

        self.update(f"[bold white on blue] {character_header} [/]")
