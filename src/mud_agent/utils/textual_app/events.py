"""Event handling for the MUD Textual App.

This module handles all event processing, callbacks, and reactive
updates for the application.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .core import MUDTextualApp

from textual.events import Mount
from textual.events import Event
from textual.message import Message

logger = logging.getLogger(__name__)


class StateUpdateEvent(Event):
    """Event to signal a state update."""

    def __init__(self, data: dict | None = None) -> None:
        self.data = data
        super().__init__()


class CommandEvent(Event):
    """Event to signal a command to be sent."""

    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__()


class ServerMessageEvent(Event):
    """Event to signal a message from the server."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()


class GMCPEvent(Event):
    """Event to signal a GMCP message."""

    def __init__(self, package: str, data: dict | None = None) -> None:
        self.package = package
        self.data = data
        super().__init__()


class EventHandler:
    """Handles events and callbacks for the MUD application."""

    def __init__(self, app: "MUDTextualApp"):
        self.app = app
        self.agent = app.agent
        self.state_manager = app.state_manager
        self.logger = logger

        # Event state
        self._event_queue = asyncio.Queue()
        self._processing_events = False

    async def setup(self) -> None:
        """Set up the event handler and any necessary subscriptions."""
        try:
            logger.info("Setting up EventHandler")

            # Subscribe to state manager events if available
            if hasattr(self.state_manager, 'events'):
                self.state_manager.events.on('room_update', self._on_state_room_update)
                self.state_manager.events.on('vitals_update', self._on_state_vitals_update)
                self.state_manager.events.on('character_update', self._on_state_character_update)
                self.state_manager.events.on('combat_update', self._on_state_combat_update)
                logger.debug("Subscribed to state manager events")

            # Subscribe to agent events if available
            if hasattr(self.agent, 'events'):
                self.agent.events.on('connection_status_changed', self._on_agent_connection_status)
                logger.debug("Subscribed to agent events")

            logger.info("EventHandler setup completed")

        except Exception as e:
            logger.error(f"Error setting up EventHandler: {e}", exc_info=True)

    def _on_state_room_update(self, **kwargs) -> None:
        """Handle room update events from state manager."""
        room_data = kwargs.get("room_data", {})
        try:
            asyncio.create_task(self.on_room_changed(room_data))
        except Exception as e:
            logger.error(f"Error handling state room update: {e}", exc_info=True)

    def _on_state_vitals_update(self, vitals_data: dict) -> None:
        """Handle vitals update events from state manager."""
        try:
            asyncio.create_task(self.on_vitals_changed(vitals_data))
        except Exception as e:
            logger.error(f"Error handling state vitals update: {e}", exc_info=True)

    def _on_state_character_update(self, char_data: dict) -> None:
        """Handle character update events from state manager."""
        try:
            asyncio.create_task(self.on_character_data_changed(char_data))
        except Exception as e:
            logger.error(f"Error handling state character update: {e}", exc_info=True)

    def _on_state_combat_update(self, combat_data: dict) -> None:
        """Handle combat update events from state manager."""
        try:
            in_combat = combat_data.get('in_combat', False)
            asyncio.create_task(self.on_combat_status_changed(in_combat))
        except Exception as e:
            logger.error(f"Error handling state combat update: {e}", exc_info=True)

    def _on_agent_connection_status(self, connected: bool) -> None:
        """Handle connection status events from agent."""
        try:
            asyncio.create_task(self.on_connection_status_changed(connected))
        except Exception as e:
            logger.error(f"Error handling agent connection status: {e}", exc_info=True)

    async def on_mount(self, event: Mount) -> None:
        """Handle the mount event when the app starts.

        Args:
            event: The mount event
        """
        try:
            logger.info("MUD Textual App mounted, starting initialization")

            # Start initialization with loading screen
            asyncio.create_task(self.app._initialize_with_loading_screen())

        except Exception as e:
            logger.error(f"Error in on_mount: {e}", exc_info=True)

    async def on_combat_status_changed(self, in_combat: bool) -> None:
        """Handle combat status changes.

        Args:
            in_combat: Whether the character is currently in combat
        """
        try:
            logger.info(f"Combat status changed: {'in combat' if in_combat else 'out of combat'}")

            # Update any combat-related UI elements
            # This could include changing colors, showing/hiding combat info, etc.

            # Trigger a widget update to reflect combat status
            await self.app.update_reactive_widgets()

        except Exception as e:
            logger.error(f"Error handling combat status change: {e}", exc_info=True)

    async def on_gmcp_polling_status_changed(self, enabled: bool) -> None:
        """Handle GMCP polling status changes.

        Args:
            enabled: Whether GMCP polling is enabled
        """
        try:
            logger.info(f"GMCP polling status changed: {'enabled' if enabled else 'disabled'}")

            # Update any polling-related UI elements
            # This could include status indicators, etc.

        except Exception as e:
            logger.error(f"Error handling GMCP polling status change: {e}", exc_info=True)

    async def on_knowledge_graph_queue_size_changed(self, queue_size: int) -> None:
        """Handle knowledge graph queue size changes.

        Args:
            queue_size: Current size of the knowledge graph update queue
        """
        try:
            logger.debug(f"Knowledge graph queue size changed: {queue_size}")

            # Update any queue-related UI elements
            # This could include progress indicators, etc.

        except Exception as e:
            logger.error(f"Error handling knowledge graph queue size change: {e}", exc_info=True)

    async def on_room_changed(self, room_data: Dict[str, Any]) -> None:
        """Handle room changes.

        Args:
            room_data: Data about the new room
        """
        try:
            room_name = room_data.get('name', 'Unknown')
            room_num = room_data.get('num', 0)

            # Update widgets with new room data
            await self.app.update_reactive_widgets()

            # Update map widget specifically
            if hasattr(self.app, 'widget_updater'):
                await self.app.widget_updater.update_map_from_room_manager()

        except Exception as e:
            logger.error(f"Error handling room change: {e}", exc_info=True)

    async def on_vitals_changed(self, vitals_data: Dict[str, Any]) -> None:
        """Handle vitals changes.

        Args:
            vitals_data: Data about the changed vitals
        """
        try:
            logger.debug(f"Vitals changed: {vitals_data}")

            # Update vitals widgets directly
            if hasattr(self.app, 'widget_updater'):
                await self.app.widget_updater.update_vitals_from_gmcp({'vitals': vitals_data})

        except Exception as e:
            logger.error(f"Error handling vitals change: {e}", exc_info=True)

    async def on_character_data_changed(self, char_data: Dict[str, Any]) -> None:
        """Handle character data changes.

        Args:
            char_data: Updated character data
        """
        try:
            logger.debug(f"Character data changed: {list(char_data.keys())}")

            # Update all widgets with new character data
            await self.app.update_reactive_widgets()

        except Exception as e:
            logger.error(f"Error handling character data change: {e}", exc_info=True)

    async def on_server_message_received(self, message: str) -> None:
        """Handle server messages.

        Args:
            message: The message received from the server
        """
        try:
            # Process the message through the command log
            if hasattr(self.app, 'server_comm'):
                await self.app.server_comm.display_server_message(message)

        except Exception as e:
            logger.error(f"Error handling server message: {e}", exc_info=True)

    async def on_command_submitted(self, command: str) -> None:
        """Handle command submission.

        Args:
            command: The command that was submitted
        """
        try:
            logger.debug(f"Command submitted: {command}")

            # Process the command through the command processor
            if hasattr(self.app, 'command_processor'):
                await self.app.command_processor.submit_command(command)

        except Exception as e:
            logger.error(f"Error handling command submission: {e}", exc_info=True)

    async def on_connection_status_changed(self, connected: bool) -> None:
        """Handle connection status changes.

        Args:
            connected: Whether the client is connected
        """
        try:
            logger.info(f"Connection status changed: {'connected' if connected else 'disconnected'}")

            # Update any connection-related UI elements
            # This could include status indicators, enabling/disabling controls, etc.

            # Update status widget
            if hasattr(self.app, 'widget_updater'):
                await self.app.widget_updater.refresh_status_widget()

        except Exception as e:
            logger.error(f"Error handling connection status change: {e}", exc_info=True)

    async def on_error_occurred(self, error: Exception, context: str = "") -> None:
        """Handle errors that occur in the application.

        Args:
            error: The error that occurred
            context: Additional context about where the error occurred
        """
        try:
            error_msg = f"Error in {context}: {error}" if context else f"Error: {error}"
            logger.error(error_msg, exc_info=True)

            # Display error in command log if available
            try:
                from ..widgets.command_log import CommandLog
                command_log = self.app.query_one("#command-log", CommandLog)
                command_log.write(f"[bold red]{error_msg}[/bold red]")
            except Exception:
                # Command log might not be available
                pass

        except Exception as e:
            logger.error(f"Error handling error event: {e}", exc_info=True)

    async def on_widget_error(self, widget_id: str, error: Exception) -> None:
        """Handle widget-specific errors.

        Args:
            widget_id: ID of the widget that had an error
            error: The error that occurred
        """
        try:
            logger.error(f"Widget error in {widget_id}: {error}", exc_info=True)

            # Handle specific widget errors
            if "vitals" in widget_id.lower():
                # Try to recover vitals widgets by setting default values
                if hasattr(self.app, 'widget_updater'):
                    await self.app.widget_updater.set_default_widget_values()

        except Exception as e:
            logger.error(f"Error handling widget error: {e}", exc_info=True)

    async def queue_event(self, event_type: str, event_data: Any = None) -> None:
        """Queue an event for processing.

        Args:
            event_type: Type of the event
            event_data: Data associated with the event
        """
        try:
            await self._event_queue.put((event_type, event_data))

            # Start event processing if not already running
            if not self._processing_events:
                asyncio.create_task(self._process_event_queue())

        except Exception as e:
            logger.error(f"Error queuing event: {e}", exc_info=True)

    async def _process_event_queue(self) -> None:
        """Process events from the event queue."""
        if self._processing_events:
            return

        self._processing_events = True

        try:
            while not self._event_queue.empty():
                try:
                    event_type, event_data = await asyncio.wait_for(
                        self._event_queue.get(), timeout=0.1
                    )

                    # Process the event based on its type
                    await self._handle_queued_event(event_type, event_data)

                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Error processing queued event: {e}", exc_info=True)

        finally:
            self._processing_events = False

    async def _handle_queued_event(self, event_type: str, event_data: Any) -> None:
        """Handle a queued event.

        Args:
            event_type: Type of the event
            event_data: Data associated with the event
        """
        try:
            if event_type == "combat_status_changed":
                await self.on_combat_status_changed(event_data)
            elif event_type == "room_changed":
                await self.on_room_changed(event_data)
            elif event_type == "vitals_changed":
                await self.on_vitals_changed(event_data)
            elif event_type == "character_data_changed":
                await self.on_character_data_changed(event_data)
            elif event_type == "server_message_received":
                await self.on_server_message_received(event_data)
            elif event_type == "command_submitted":
                await self.on_command_submitted(event_data)
            elif event_type == "connection_status_changed":
                await self.on_connection_status_changed(event_data)
            elif event_type == "error_occurred":
                error, context = event_data if isinstance(event_data, tuple) else (event_data, "")
                await self.on_error_occurred(error, context)
            elif event_type == "widget_error":
                widget_id, error = event_data
                await self.on_widget_error(widget_id, error)
            else:
                logger.warning(f"Unknown event type: {event_type}")

        except Exception as e:
            logger.error(f"Error handling queued event '{event_type}': {e}", exc_info=True)

    def get_event_queue_size(self) -> int:
        """Get the current size of the event queue.

        Returns:
            Number of events in the queue
        """
        return self._event_queue.qsize()

    def is_processing_events(self) -> bool:
        """Check if events are currently being processed.

        Returns:
            True if events are being processed, False otherwise
        """
        return self._processing_events

    async def clear_event_queue(self) -> None:
        """Clear all events from the event queue."""
        try:
            while not self._event_queue.empty():
                try:
                    self._event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            logger.debug("Event queue cleared")

        except Exception as e:
            logger.error(f"Error clearing event queue: {e}", exc_info=True)

    async def cleanup(self) -> None:
        """Clean up the event handler resources."""
        try:
            logger.debug("Cleaning up EventHandler")

            # Clear any remaining events
            await self.clear_event_queue()

            # Stop event processing
            self._processing_events = False

            logger.debug("EventHandler cleanup completed")

        except Exception as e:
            logger.error(f"Error during EventHandler cleanup: {e}", exc_info=True)


class AppMessage(Message):
    """Base class for application-specific messages."""
    pass


class CombatStatusChanged(AppMessage):
    """Message sent when combat status changes."""

    def __init__(self, in_combat: bool) -> None:
        super().__init__()
        self.in_combat = in_combat


class RoomChanged(AppMessage):
    """Message sent when the current room changes."""

    def __init__(self, room_data: Dict[str, Any]) -> None:
        super().__init__()
        self.room_data = room_data


class VitalsChanged(AppMessage):
    """Message sent when character vitals change."""

    def __init__(self, vitals_data: Dict[str, Any]) -> None:
        super().__init__()
        self.vitals_data = vitals_data


class ServerMessageReceived(AppMessage):
    """Message sent when a server message is received."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message


class CommandSubmitted(AppMessage):
    """Message sent when a command is submitted."""

    def __init__(self, command: str) -> None:
        super().__init__()
        self.command = command


class ConnectionStatusChanged(AppMessage):
    """Message sent when connection status changes."""

    def __init__(self, connected: bool) -> None:
        super().__init__()
        self.connected = connected


class ErrorOccurred(AppMessage):
    """Message sent when an error occurs."""

    def __init__(self, error: Exception, context: str = "") -> None:
        super().__init__()
        self.error = error
        self.context = context
