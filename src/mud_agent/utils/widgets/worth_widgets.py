"""
Worth widgets for the MUD agent.

This module contains widgets related to character worth (gold, bank, QP, TP).
"""

import logging
from typing import Any

from rich.console import Console
from textual.reactive import reactive

from .base import BaseWidget
from .state_listener import StateListener

logger = logging.getLogger(__name__)
console = Console()


class GoldWidget(StateListener, BaseWidget):
    """Widget that displays character gold.

    This widget uses the StateListener to listen for worth events.
    """

    # Reactive attributes
    value = reactive("Unknown")

    # Register for specific event types
    register_for_worth_events = True

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        try:
            # Update gold value if present
            if "gold" in updates:
                self.value = updates["gold"]
                self.update_content()
        except Exception as e:
            logger.error(
                f"Error handling worth update in GoldWidget: {e}", exc_info=True
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug("GoldWidget using event-based updates instead of reactive binding")

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            if self.value and str(self.value) != "Unknown" and str(self.value) != "0":
                # Format gold with commas for readability
                try:
                    gold_value = int(self.value)
                    formatted_gold = f"{gold_value:,}"
                except (ValueError, TypeError):
                    formatted_gold = str(self.value)

                self.update(f"Gold: [yellow 95%]{formatted_gold}[/]")
            else:
                self.update("Gold: [dim]0[/]")

        except Exception as e:
            logger.error(f"Error updating gold widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying gold[/bold red]")


class BankWidget(StateListener, BaseWidget):
    """Widget that displays character bank balance.

    This widget uses the StateListener to listen for worth events.
    """

    # Reactive attributes
    value = reactive(0)

    # Register for specific event types
    register_for_worth_events = True

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        try:
            # Update bank value if present
            if "bank" in updates:
                self.value = updates["bank"]
                self.update_content()
        except Exception as e:
            logger.error(
                f"Error handling worth update in BankWidget: {e}", exc_info=True
            )

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug("BankWidget using event-based updates instead of reactive binding")

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            if self.value and self.value > 0:
                # Format bank with commas for readability
                try:
                    bank_value = int(self.value)
                    formatted_bank = f"{bank_value:,}"
                except (ValueError, TypeError):
                    formatted_bank = str(self.value)

                self.update(f"Bank: [yellow 95%]{formatted_bank}[/]")
            else:
                self.update("Bank: [dim]0[/]")

        except Exception as e:
            logger.error(f"Error updating bank widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying bank[/bold red]")


class QPWidget(StateListener, BaseWidget):
    """Widget that displays character quest points.

    This widget uses the StateListener to listen for worth events.
    """

    # Reactive attributes
    value = reactive(0)

    # Register for specific event types
    register_for_worth_events = True

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        try:
            # Update QP value if present
            if "qp" in updates:
                self.value = updates["qp"]
                self.update_content()
        except Exception as e:
            logger.error(f"Error handling worth update in QPWidget: {e}", exc_info=True)

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug("QPWidget using event-based updates instead of reactive binding")

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            if self.value and self.value > 0:
                self.update(f"QP: [cyan 80%]{self.value}[/]")
            else:
                self.update("QP: [dim]0[/]")

        except Exception as e:
            logger.error(f"Error updating QP widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying QP[/bold red]")


class TPWidget(StateListener, BaseWidget):
    """Widget that displays character trivia points.

    This widget uses the StateListener to listen for worth events.
    """

    # Reactive attributes
    value = reactive(0)

    # Register for specific event types
    register_for_worth_events = True

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        try:
            # Update TP value if present
            if "tp" in updates:
                self.value = updates["tp"]
                self.update_content()
        except Exception as e:
            logger.error(f"Error handling worth update in TPWidget: {e}", exc_info=True)

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug("TPWidget using event-based updates instead of reactive binding")

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            if self.value and self.value > 0:
                self.update(f"TP: [magenta 80%]{self.value}[/]")
            else:
                self.update("TP: [dim]0[/]")

        except Exception as e:
            logger.error(f"Error updating TP widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying TP[/bold red]")


class XPWidget(StateListener, BaseWidget):
    """Widget that displays character experience.

    This widget uses the StateListener to listen for worth events.
    """

    # Reactive attributes
    value = reactive("Unknown")

    # Register for specific event types
    register_for_worth_events = True

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        try:
            # Update XP value if present
            if "xp" in updates:
                self.value = updates["xp"]
                self.update_content()
        except Exception as e:
            logger.error(f"Error handling worth update in XPWidget: {e}", exc_info=True)

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        logger.debug("XPWidget using event-based updates instead of reactive binding")

    def update_content(self):
        """Update the widget content."""
        # Clear the current content
        self.update("")

        try:
            if self.value and str(self.value) != "Unknown" and str(self.value) != "0":
                self.update(f"XP: [green]{self.value}[/]")
            else:
                self.update("XP: [dim]0[/]")

        except Exception as e:
            logger.error(f"Error updating XP widget: {e}", exc_info=True)
            self.update("[bold red]Error displaying XP[/bold red]")
