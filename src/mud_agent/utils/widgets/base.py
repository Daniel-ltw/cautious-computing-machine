"""
Base widget classes for the MUD agent.

This module contains the base widget classes used by the MUD agent UI.
"""

import logging

from rich.console import Console
from textual.widgets import Static

# Constants for status thresholds
FULL_THRESHOLD = 90
SATIATED_THRESHOLD = 70
HUNGRY_THRESHOLD = 30
ZERO = 0
ONE_HUNDRED_PERCENT = 100

logger = logging.getLogger(__name__)
console = Console()


class BaseWidget(Static):
    """Base class for all MUD agent widgets."""

    def __init__(self, *args, **kwargs):
        """Initialize the widget."""
        super().__init__(*args, **kwargs)
        # Enable markup and highlighting
        self.markup = True
        self.highlight = True

    def on_mount(self):
        """Called when the widget is mounted."""
        # Update the widget with the current data
        self.update_content()

        # Bind to state manager if the method exists
        if hasattr(self, "bind_to_state_manager"):
            self.bind_to_state_manager()
            logger.debug(f"{self.__class__.__name__} bound to state manager")

    def update_content(self):
        """Update the widget content with the current data.

        This method should be overridden by subclasses.
        """
        pass
