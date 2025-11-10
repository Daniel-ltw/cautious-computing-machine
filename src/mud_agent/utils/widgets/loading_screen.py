"""
Loading screen widget for the MUD agent.

This module contains the loading screen implementation for the MUD agent UI.
"""

import asyncio
import logging
from collections.abc import Callable

from rich.align import Align
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Static

logger = logging.getLogger(__name__)


class LoadingMessage(Static):
    """Widget for displaying loading messages with status."""

    def __init__(self, message: str = "Initializing...", **kwargs):
        """Initialize the loading message widget.

        Args:
            message: The initial message to display
            **kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__("", **kwargs)
        self.message = message

    def update_message(self, message: str) -> None:
        """Update the loading message.

        Args:
            message: The new message to display
        """
        self.message = message
        self.update(self.message)


class LoadingProgress(Static):
    """Widget for displaying loading progress."""

    def __init__(self, **kwargs):
        """Initialize the loading progress widget.

        Args:
            **kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__("", **kwargs)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        self.task_id = self.progress.add_task("Loading...", total=100)

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update(self.progress)

    def update_progress(self, value: float, description: str | None = None) -> None:
        """Update the progress bar.

        Args:
            value: The new progress value (0-100)
            description: Optional new description for the progress bar
        """
        if description:
            self.progress.update(self.task_id, description=description)
        self.progress.update(self.task_id, completed=value)
        self.update(self.progress)


class LoadingScreen(Screen):
    """Loading screen for the MUD agent."""

    BINDINGS = []  # No key bindings for the loading screen

    def __init__(self, **kwargs):
        """Initialize the loading screen.

        Args:
            **kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.steps: list[str] = []
        self.current_step = 0
        self.total_steps = 0
        self._on_complete_callback: Callable | None = None

    def compose(self) -> ComposeResult:
        """Compose the loading screen layout."""
        # Create a container for the loading screen content
        with Container(id="loading-container"):
            # Title
            yield Static(
                Align.center(
                    Panel(
                        Text("MUD Agent", style="bold white"),
                        title="Loading",
                        border_style="green",
                    ),
                    vertical="middle",
                ),
                id="loading-title",
            )

            # Progress bar - create an instance directly
            self.progress_bar = LoadingProgress(id="loading-progress")
            yield self.progress_bar

            # Status message - create an instance directly
            self.status_message = LoadingMessage(id="loading-message")
            yield self.status_message

            # Version info
            yield Static(
                Align.center(
                    Text("Connecting to MUD server...", style="dim"),
                    vertical="bottom",
                ),
                id="loading-info",
            )

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Initialize the loading screen
        self.steps = [
            "Connecting to server...",
            "Logging in...",
            "Initializing GMCP...",
            "Loading room information...",
            "Loading character stats...",
            "Initializing UI...",
        ]
        self.total_steps = len(self.steps)
        self.current_step = 0

        # Update the progress bar
        self.update_progress(0, self.steps[0])

    def update_progress(self, percentage: float, message: str) -> None:
        """Update the loading progress.

        Args:
            percentage: The progress percentage (0-100)
            message: The status message to display
        """
        try:
            # Update the progress bar using the instance variable
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.update_progress(percentage, description=message)

            # Update the status message using the instance variable
            if hasattr(self, "status_message") and self.status_message:
                self.status_message.update_message(message)

            # Log the progress
            logger.debug(f"Loading progress: {percentage:.1f}% - {message}")
        except Exception as e:
            logger.error(f"Error updating loading progress: {e}", exc_info=True)

    def next_step(self) -> None:
        """Advance to the next loading step."""
        self.current_step += 1
        if self.current_step < self.total_steps:
            # Calculate progress percentage
            progress = (self.current_step / self.total_steps) * 100
            # Update the progress with the next step message
            self.update_progress(progress, self.steps[self.current_step])
        else:
            # We've completed all steps
            self.update_progress(100, "Ready!")
            # Call the completion callback if set
            if self._on_complete_callback:
                asyncio.create_task(self._on_complete_callback())

    def set_on_complete(self, callback: Callable) -> None:
        """Set the callback to call when loading is complete.

        Args:
            callback: The callback function to call
        """
        self._on_complete_callback = callback

    def add_step(self, step: str) -> None:
        """Add a new step to the loading process.

        Args:
            step: The step description
        """
        self.steps.append(step)
        self.total_steps = len(self.steps)
        # Recalculate progress
        progress = (self.current_step / self.total_steps) * 100
        self.update_progress(progress, self.steps[self.current_step])
