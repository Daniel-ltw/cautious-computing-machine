"""
Integration module for connecting the Textual UI with the MUD agent.

This module provides the necessary integration between the Textual UI and the MUD agent,
ensuring proper data flow and event handling.
"""

import asyncio
import logging

from rich.console import Console
from textual.app import App
from textual.widget import Widget
from textual.widgets import Static

# Constants for status thresholds
FULL_THRESHOLD = 90
SATIATED_THRESHOLD = 70
HUNGRY_THRESHOLD = 30
MIN_MAP_CHARS = 1  # More lenient threshold for map characters
MIN_MAP_SECTION_SIZE = 2  # Minimum number of lines for a valid map section
ZERO = 0
ONE_HUNDRED_PERCENT = 100
DEFAULT_UPDATE_INTERVAL = 0.5
MAP_PLAYER_POSITION_BONUS = 5

logger = logging.getLogger(__name__)
console = Console()


class TextualIntegration:
    """Integration class for connecting the Textual UI with the MUD agent.

    This class is non-threaded and simply accesses the shared state from the MUD agent
    to update the UI. It uses Textual's reactive attributes and workers to automatically
    update the UI when the state changes.
    """

    def __init__(self, agent):
        """Initialize the integration.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)
        self.app = None
        self.status_widget = None
        self.map_widget = None
        self.command_log = None

        # Status update interval (in seconds)
        self.update_interval = DEFAULT_UPDATE_INTERVAL

        # Flag to track if the integration is running
        self.running = False

    def register_app(self, app: App):
        """Register the Textual app with the integration.

        Args:
            app: The Textual app instance
        """
        self.app = app
        self.logger.info("Registered Textual app with integration")

    def register_widgets(
        self, status_widget: Static, map_widget: Static, command_log: Static
    ):
        """Register the widgets with the integration.

        Args:
            status_widget: The status widget
            map_widget: The map widget
            command_log: The command log widget
        """
        self.status_widget = status_widget
        self.map_widget = map_widget
        self.command_log = command_log
        self.logger.info("Registered widgets with integration")

    def start(self):
        """Start the integration."""
        try:
            console.print("[bold green]Starting Textual integration...[/]")
            self.running = True

            # Set up a timer to update the UI periodically using Textual's built-in timer
            if self.app:
                self.app.set_interval(self.update_interval, self.update_ui)
                console.print("[bold green]Set up UI update timer[/]")

            self.logger.info("Textual integration started")

        except Exception as e:
            console.print(f"[bold red]Error starting textual integration: {e}[/]")
            self.logger.error(f"Error starting textual integration: {e}", exc_info=True)

    def stop(self):
        """Stop the integration."""
        try:
            self.running = False
            self.logger.info("Textual integration stopped")

        except Exception as e:
            self.logger.error(f"Error stopping textual integration: {e}", exc_info=True)

    async def update_ui(self):
        """Update the UI with the latest information from the agent."""
        if not self.running:
            return

        try:
            # Update widgets that have update_from_state_manager method
            if self.status_widget and hasattr(self.status_widget, "update_from_state_manager"):
                await self.status_widget.update_from_state_manager(self.agent.state_manager)

            if self.map_widget and hasattr(self.map_widget, "update_from_state_manager"):
                self.map_widget.update_from_state_manager(self.agent.room_manager)

        except Exception as e:
            self.logger.error(f"Error updating UI: {e}", exc_info=True)

    def process_command(self, command: str):
        """Process a command through the agent.

        This method is called when a command is submitted through the UI.
        It creates an asyncio task to process the command.

        Args:
            command: The command to process
        """
        # Create an asyncio task to process the command
        task = asyncio.create_task(self._process_command(command))
        # You can add error handling or task tracking here if needed
        return task

    async def _process_command(self, command: str):
        """Process a command through the agent asynchronously.

        Args:
            command: The command to process
        """
        try:
            # Process the command through the agent
            response = await self.agent.send_command(command)

            # Add the response to the command log
            if self.command_log:
                self.command_log.add_response(response)

            # Special handling for map command
            if command.lower() == "map" and self.map_widget:
                # Update the map widget with the response
                self.map_widget.map_text = response
                self.map_widget.update_content()
                self.logger.debug("Updated map widget with map command response")

                # If we have a current room name, queue the map for adding to the knowledge graph
                if (
                    hasattr(self.agent, "room_manager")
                    and self.agent.room_manager.current_room != "Unknown"
                ):
                    # Queue the map for adding to the knowledge graph
                    if not hasattr(self.agent.room_manager, "map_queue"):
                        self.agent.room_manager.map_queue = []
                    self.agent.room_manager.map_queue.append(
                        (self.agent.room_manager.current_room, response)
                    )
                    self.logger.info(
                        f"Queued map for knowledge graph: {self.agent.room_manager.current_room}"
                    )

                    # Process the map queue
                    asyncio.create_task(self.agent.room_manager.process_map_queue())
                    self.logger.info("Created task to process map queue")

            # Update the UI immediately after processing a command
            await self.update_ui()

        except Exception as e:
            self.logger.error(f"Error processing command: {e}", exc_info=True)
            if self.command_log:
                self.command_log.add_response(f"Error: {e!s}")


                if len(status_line) > 70:
                    status_line = status_line[:67] + "..."
                    self.write(f"[bold]Status:[/] {status_line}")
                else:
                    # If we only have raw data values, don't display the status line
                    pass

        except Exception as e:
            # Fallback if there's an error formatting the stats
            logger.error(f"Error formatting status widget: {e}", exc_info=True)
            self.write("[bold red]Error displaying status information[/bold red]")

        # Force a refresh of the widget
        self.refresh()

    # Watch methods for ReactiveStatusWidget have been removed

    # The update_from_state_manager method has been removed as it was redundant.
    # Widget-specific update_from_state_manager methods are now handled
    # directly by the individual widgets in the widgets/ directory.
    # The TextualIntegration class now only coordinates updates between
    # the agent and the widgets, rather than duplicating widget logic.


class CommandInput(Widget):
    """A command input widget for the MUD client.

    This widget provides a text input field for entering commands.
    """

    def __init__(self, callback, *args, **kwargs):
        """Initialize the widget.

        Args:
            callback: The callback to call when a command is submitted
            *args: Additional arguments to pass to the parent class
            **kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__(*args, **kwargs)
        self.callback = callback
        self.command_history = []
        self.history_index = 0
        self.current_command = ""

    def on_mount(self):
        """Called when the widget is mounted."""
        # Create a text input
        from textual.widgets import Input

        self.input = Input(placeholder="Enter command...")
        self.mount(self.input)
        self.input.focus()

    def on_input_submitted(self, event):
        """Called when the input is submitted.

        Args:
            event: The input submitted event
        """
        # Get the command
        command = event.value.strip()

        # Clear the input
        self.input.value = ""

        # Skip empty commands
        if not command:
            return

        # Add the command to the history
        self.command_history.append(command)
        self.history_index = len(self.command_history)

        # Call the callback
        self.callback(command)
