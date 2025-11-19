"""Core MUD Textual App implementation.

This module contains the main MUDTextualApp class that integrates
all the separated components for a clean, maintainable architecture.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

if TYPE_CHECKING:
    from mud_agent.agent import MUDAgent
    from mud_agent.room_manager import RoomManager
    from mud_agent.state_manager import StateManager

from ...utils.command_log_handler import CommandLogHandler
from ..textual_widgets import CommandInput
from ..widgets.command_log import CommandLog
from ..widgets.containers import (
    RoomInfoMapContainer,
    StatusContainer,
)
from ..widgets.status_widgets import StatusEffectsWidget
from .commands import CommandProcessor
from .events import EventHandler
from .gmcp_manager import GMCPManager
from .server_comm import ServerCommunicator
from .styles import STYLES
from .widget_updater import WidgetUpdater

logger = logging.getLogger(__name__)


class MUDTextualApp(App):
    """Main MUD Textual Application.

    This is the primary application class that coordinates all components
    of the MUD client interface.
    """

    CSS = STYLES

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+r", "reconnect", "Reconnect"),
        ("f1", "toggle_debug", "Debug"),
        ("f2", "show_help", "Help"),
    ]

    def __init__(
        self,
        agent: "MUDAgent",
        state_manager: "StateManager",
        room_manager: "RoomManager",
        **kwargs: Any,
    ):
        """Initialize the MUD Textual App.

        Args:
            agent: The MUD agent instance
            state_manager: The state manager instance
            room_manager: The room manager instance
            **kwargs: Additional keyword arguments for the App
        """
        super().__init__(**kwargs)

        # Core dependencies
        self.agent = agent
        self.state_manager = state_manager
        self.room_manager = room_manager

        # Register this app with the state manager for GMCP forwarding
        if hasattr(state_manager, '_textual_app'):
            state_manager._textual_app = self
        else:
            state_manager._textual_app = self

        # Component managers
        self.command_processor = CommandProcessor(self)
        self.gmcp_manager = GMCPManager(self)
        self.widget_updater = WidgetUpdater(self)
        self.event_handler = EventHandler(self)
        self.server_communicator = ServerCommunicator(self)

        # Application state
        self._initialized = False
        self._loading = True
        self._debug_mode = False

        # Widget references (populated during compose)
        self._widgets = {}

        logger.info("MUDTextualApp initialized")

    def compose(self) -> ComposeResult:
        """Compose the app layout - restored to original simple structure."""
        logger.info("Starting UI composition")

        try:
            yield Header(show_clock=True)

            # Status container (top) - matches original layout
            with Container(id="status-container"):
                # Use the StatusContainer which includes all status widgets
                yield StatusContainer(id="status-widget")

            # Main container (horizontal split) - matches original
            with Container(id="main-container"):
                # Map container (left side) - 40% width like original
                with Container(id="map-container"):
                    yield RoomInfoMapContainer(id="room-info-map-container")

                # Command container (right side) - 60% width like original
                with Container(id="command-container"):
                    yield CommandLog(id="command-log", highlight=True, markup=True)
                    yield CommandInput(
                        self._handle_command_submit,
                        id="command-input",
                        placeholder="Enter command..."
                    )

            # Loading overlay (initially hidden)
            with Container(id="loading-overlay", classes="loading-overlay"):
                yield Static("●", id="loading-indicator")
                yield Static("Loading...", id="loading-text")

            yield Footer()

            logger.info("UI composition complete - using original layout structure")

        except Exception as e:
            logger.error(f"Error during UI composition: {e}", exc_info=True)
            # Fallback minimal UI
            yield Static(f"Error initializing UI: {e}", id="error-display")

    async def on_mount(self) -> None:
        """Handle the mount event."""
        try:
            logger.info("App mounted, command log handler set up.")

            # Set the command log for the handler
            command_log = self.query_one(CommandLog)
            command_log_handler = CommandLogHandler()
            command_log_handler.set_command_log(command_log)

        except Exception as e:
            logger.error(f"Error during mount: {e}", exc_info=True)

    async def on_ready(self) -> None:
        """Called when the app is ready to run."""
        try:
            await self._initialize_with_loading_screen()
        except Exception as e:
            logger.error(f"Initialization failed in on_ready: {e}", exc_info=True)
            await self._handle_initialization_error(e)

    async def _initialize_with_loading_screen(self) -> None:
        """Initialize the application with a loading screen."""
        try:
            loading_overlay = None
            loading_indicator = None
            loading_text = None

            try:
                loading_overlay = self.query_one("#loading-overlay")
                loading_indicator = self.query_one("#loading-indicator", Static)
                loading_text = self.query_one("#loading-text", Static)
            except Exception:
                try:
                    loading_overlay = Container(id="loading-overlay", classes="loading-overlay")
                    loading_indicator = Static("●", id="loading-indicator")
                    loading_text = Static("Loading...", id="loading-text")
                    await self.mount(loading_overlay)
                    await loading_overlay.mount(loading_indicator)
                    await loading_overlay.mount(loading_text)
                except Exception as mount_err:
                    logger.warning(f"Unable to create loading overlay: {mount_err}")

            if loading_overlay:
                loading_overlay.display = True

            # Update loading text and perform initialization steps
            steps = [
                ("Registering with integration...", self._register_with_integration),
                ("Setting up event handlers...", self.event_handler.setup),
                ("Initializing GMCP manager...", self.gmcp_manager.setup),
                ("Setting up server communication...", self.server_communicator.setup_server_message_display),
                ("Updating initial widgets...", self.widget_updater.update_all_widgets),
                ("Starting integration...", self._start_integration),
                ("Finalizing initialization...", self._finish_initialization),
            ]

            for step_text, step_func in steps:
                try:
                    if loading_text:
                        loading_text.update(step_text)
                    await asyncio.sleep(0.1)
                    result = step_func()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as step_err:
                    logger.error(f"Initialization step failed: {step_text}: {step_err}", exc_info=True)
                    raise

            if loading_overlay:
                loading_overlay.display = False
            self._loading = False
            self._initialized = True

            logger.info("Application initialization complete")

        except Exception as e:
            logger.error(f"Error during initialization: {e}", exc_info=True)
            await self._handle_initialization_error(e)

    async def _register_with_integration(self) -> None:
        """Register the app and widgets with the integration."""
        try:
            if hasattr(self.agent, "integration"):
                self.agent.integration.register_app(self)

                status_widget = None
                map_widget = None
                command_log = None

                try:
                    status_widget = self.query_one("#status-widget", StatusContainer)
                    self._widgets["status-widget"] = status_widget
                except Exception as e:
                    logger.warning(f"Could not find status widget: {e}")

                try:
                    map_widget = self.query_one("#room-info-map-container", RoomInfoMapContainer)
                    self._widgets["room-info-map-container"] = map_widget
                except Exception as e:
                    logger.warning(f"Could not find map widget: {e}")

                try:
                    command_log = self.query_one("#command-log", CommandLog)
                    self._widgets["command-log"] = command_log
                except Exception as e:
                    logger.warning(f"Could not find command log: {e}")

                if status_widget and map_widget and command_log:
                    try:
                        self.agent.integration.register_widgets(status_widget, map_widget, command_log)
                        logger.info("Registered widgets with integration")
                    except Exception as e:
                        logger.warning(f"Integration registration failed: {e}")

                try:
                    effects = self.query_one("#status-effects-widget", StatusEffectsWidget)
                    if hasattr(effects, "register_with_state_manager"):
                        effects.register_with_state_manager(self.state_manager)
                        self._widgets["status-effects-widget"] = effects
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error registering with integration: {e}", exc_info=True)

    async def _start_integration(self) -> None:
        """Start the integration."""
        try:
            if hasattr(self.agent, "integration"):
                await self.agent.integration.start()
                logger.info("Integration started")

        except Exception as e:
            logger.error(f"Error starting integration: {e}", exc_info=True)

    async def _finish_initialization(self) -> None:
        """Finish the initialization process."""
        try:
            # Set default values for widgets
            await self.widget_updater.set_default_widget_values()

            try:
                for node in self.query("*"):
                    if hasattr(node, "register_with_state_manager"):
                        node.register_with_state_manager(self.state_manager)
            except Exception as e:
                logger.debug(f"Bulk widget registration skipped: {e}")

            # Start GMCP polling
            await self.gmcp_manager.start_gmcp_polling()

            # Focus on command input
            try:
                command_input = self.query_one("#command-input", CommandInput)
                command_input.focus()
            except Exception as e:
                logger.warning(f"Could not focus command input: {e}")

            logger.info("Initialization finished")

        except Exception as e:
            logger.error(f"Error finishing initialization: {e}", exc_info=True)

    def _handle_command_submit(self, command: str) -> None:
        try:
            import asyncio
            asyncio.create_task(self.command_processor.submit_command(command))
        except Exception as e:
            try:
                log = self.query_one("#command-log", CommandLog)
                log.write(f"[bold red]Error submitting command: {e}[/bold red]")
            except Exception:
                pass

    async def _handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors.

        Args:
            error: The error that occurred
        """
        try:
            try:
                loading_overlay = self.query_one("#loading-overlay")
                loading_overlay.display = False
            except Exception:
                pass

            # Show error message
            error_msg = f"Initialization failed: {error}"
            logger.error(error_msg)

            # Try to display error in command log if available
            try:
                command_log = self.query_one("#command-log", CommandLog)
                command_log.write(f"[bold red]{error_msg}[/bold red]")
            except Exception:
                try:
                    error_display = Static(error_msg, id="init-error")
                    await self.mount(error_display)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error handling initialization error: {e}", exc_info=True)



    # Event handler removed; command submission is routed exclusively via
    # the CommandInput callback `_handle_command_submit` to prevent duplicates.

    # Action handlers
    async def action_quit(self) -> None:
        """Handle quit action."""
        await self._cleanup()
        await super().action_quit()

    async def action_reconnect(self) -> None:
        """Handle reconnect action."""
        await self.server_communicator.reconnect_to_server()

    async def action_toggle_debug(self) -> None:
        """Toggle debug mode."""
        self._debug_mode = not self._debug_mode
        logger.info(f"Debug mode: {'enabled' if self._debug_mode else 'disabled'}")

        # Display debug status
        try:
            command_log = self.query_one("#command-log", CommandLog)
            status = "enabled" if self._debug_mode else "disabled"
            command_log.write(f"[bold blue]Debug mode {status}[/bold blue]")
        except Exception:
            pass

    async def action_show_help(self) -> None:
        """Show help information."""
        await self.command_processor.handle_help_command()

    # Public API methods
    def get_widget(self, widget_id: str) -> Any | None:
        """Get a widget by ID.

        Args:
            widget_id: The widget ID

        Returns:
            The widget instance or None if not found
        """
        return self._widgets.get(widget_id)

    def is_initialized(self) -> bool:
        """Check if the app is fully initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def is_loading(self) -> bool:
        """Check if the app is currently loading.

        Returns:
            True if loading, False otherwise
        """
        return self._loading

    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if debug mode is enabled, False otherwise
        """
        return self._debug_mode

    async def _update_widgets_manually(self) -> None:
        """Update widgets manually without using the worker.

        This is a non-worker version of update_reactive_widgets that can be awaited.
        """
        # Prevent concurrent widget updates
        if hasattr(self, '_updating_widgets') and self._updating_widgets:
            logger.debug("Widget update already in progress, skipping")
            return

        try:
            self._updating_widgets = True

            # Check if the app is mounted
            if not self.is_mounted:
                logger.debug("App not mounted yet, deferring manual widget update")
                return

            # Try to query the widgets, but handle the case where they might not be mounted yet
            try:
                status_widget = self.query_one("#status-widget")
                map_widget = self.query_one(RoomInfoMapContainer)
            except Exception as e:
                logger.debug(f"Widgets not available yet, deferring manual update: {e}")
                return

            # Set default values for vitals widgets
            try:
                if (
                    hasattr(status_widget, "vitals_container")
                    and status_widget.vitals_container
                ):
                    vitals_container = status_widget.vitals_container

                    # Initialize vitals widgets without setting default values
                    # Let the widgets display their actual values from the state manager
                    if (
                        hasattr(vitals_container, "hp_widget")
                        and vitals_container.hp_widget
                    ):
                        if (
                            hasattr(vitals_container.hp_widget, "hp_current_widget")
                            and vitals_container.hp_widget.hp_current_widget
                        ):
                            vitals_container.hp_widget.hp_current_widget.update_content()
                            logger.info(
                                "Updated HP current widget content in _update_widgets_manually"
                            )

                        if (
                            hasattr(vitals_container.hp_widget, "hp_max_widget")
                            and vitals_container.hp_widget.hp_max_widget
                        ):
                            vitals_container.hp_widget.hp_max_widget.update_content()
                            logger.info(
                                "Updated HP max widget content in _update_widgets_manually"
                            )

                    # Initialize MP widgets without setting default values
                    if (
                        hasattr(vitals_container, "mp_widget")
                        and vitals_container.mp_widget
                    ):
                        if (
                            hasattr(vitals_container.mp_widget, "mp_current_widget")
                            and vitals_container.mp_widget.mp_current_widget
                        ):
                            vitals_container.mp_widget.mp_current_widget.update_content()
                            logger.info(
                                "Updated MP current widget content in _update_widgets_manually"
                            )

                        if (
                            hasattr(vitals_container.mp_widget, "mp_max_widget")
                            and vitals_container.mp_widget.mp_max_widget
                        ):
                            vitals_container.mp_widget.mp_max_widget.update_content()
                            logger.info(
                                "Updated MP max widget content in _update_widgets_manually"
                            )

                    # Initialize MV widgets without setting default values
                    if (
                        hasattr(vitals_container, "mv_widget")
                        and vitals_container.mv_widget
                    ):
                        if (
                            hasattr(vitals_container.mv_widget, "mv_current_widget")
                            and vitals_container.mv_widget.mv_current_widget
                        ):
                            vitals_container.mv_widget.mv_current_widget.update_content()
                            logger.info(
                                "Updated MV current widget content in _update_widgets_manually"
                            )

                        if (
                            hasattr(vitals_container.mv_widget, "mv_max_widget")
                            and vitals_container.mv_widget.mv_max_widget
                        ):
                            vitals_container.mv_widget.mv_max_widget.update_content()
                            logger.info(
                                "Updated MV max widget content in _update_widgets_manually"
                            )
            except Exception as vitals_err:
                logger.error(
                    f"Error setting default values for vitals widgets: {vitals_err}",
                    exc_info=True,
                )

            # GMCP data will be received automatically from the server
            if hasattr(self.agent, "aardwolf_gmcp") and self.agent.aardwolf_gmcp:
                logger.info("GMCP data will be received automatically from server")

        except Exception as e:
            logger.error(f"Error updating widgets manually: {e}", exc_info=True)
        finally:
            self._updating_widgets = False

    async def update_reactive_widgets(self) -> None:
        """Update the reactive widgets with the latest data from the agent."""
        try:
            # Check if the app is mounted
            if not self.is_mounted:
                logger.debug("App not mounted yet, deferring widget update")
                return

            # Add throttling to prevent excessive updates
            import time
            current_time = time.time()
            if hasattr(self, '_last_reactive_update'):
                if current_time - self._last_reactive_update < 0.1:  # 100ms throttle
                    logger.debug("Throttling reactive widget update")
                    return
            self._last_reactive_update = current_time

            # Try to query the widgets, but handle the case where they might not be mounted yet
            try:
                status_widget = self.query_one("#status-widget")
                map_widget = self.query_one(RoomInfoMapContainer)
            except Exception as e:
                logger.debug(f"Widgets not available yet, deferring update: {e}")
                return

            # GMCP data will be received automatically from the server
            if hasattr(self.agent, "aardwolf_gmcp") and self.agent.aardwolf_gmcp:
                logger.debug("GMCP data will be received automatically from server")

            # Update the status widget
            if hasattr(status_widget, "update_from_state_manager"):
                await status_widget.update_from_state_manager(self.state_manager)
                logger.debug("Updated status widget from state manager")
            else:
                logger.warning(
                    "Status widget does not have update_from_state_manager method"
                )
        except Exception as e:
            logger.error(f"Error updating reactive widgets: {e}", exc_info=True)

        # Log the current GMCP data in the state manager
        if hasattr(self.agent, "state_manager"):
            state_manager = self.agent.state_manager
            logger.debug("State Manager GMCP Data:")
            if hasattr(state_manager, "area_name"):
                logger.debug(f"  area_name: {state_manager.area_name}")
            if hasattr(state_manager, "room_terrain"):
                logger.debug(f"  room_terrain: {state_manager.room_terrain}")
            if hasattr(state_manager, "room_coords"):
                logger.debug(f"  room_coords: {state_manager.room_coords}")
            if hasattr(state_manager, "status"):
                logger.debug(f"  status: {state_manager.status}")

        # Log the current GMCP data in the map widget
        try:
            logger.debug("Map Widget GMCP Data:")
            logger.debug(f"  area_name: {map_widget.area_name}")
            logger.debug(f"  room_terrain: {map_widget.room_terrain}")
            logger.debug(f"  room_coords: {map_widget.room_coords}")
            logger.debug(f"  room_details: {map_widget.room_details}")
            logger.debug(f"  room_num: {map_widget.room_num}")
        except Exception as e:
            logger.debug(f"Could not log map widget data: {e}")

        # If GMCP data is not available in the status manager, try to get it directly from GMCP
        if hasattr(self.agent, "aardwolf_gmcp") and self.agent.client.gmcp_enabled:
            # Update from Aardwolf GMCP data
            updates = self.agent.aardwolf_gmcp.update_from_gmcp()

            # Log what was updated
            if updates:
                logger.debug(
                    f"Updated from GMCP in update_reactive_widgets: {', '.join(updates.keys())}"
                )

                # If room data was updated, update the map widget with it
                if "room" in updates:
                    room_info = self.agent.aardwolf_gmcp.get_room_info()
                    logger.debug(f"Got room info from GMCP: {room_info}")

    async def on_unmount(self) -> None:
        """Handle the unmount event."""
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        try:
            logger.info("Starting application cleanup")

            # Stop GMCP polling
            await self.gmcp_manager.stop_gmcp_polling()

            # Clean up event handler
            await self.event_handler.cleanup()

            # Clean up server communication
            await self.server_communicator.cleanup()

            # Clean up widget updater
            await self.widget_updater.cleanup()

            logger.info("Application cleanup complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    def get_status(self) -> dict:
        """Get the current application status.

        Returns:
            Dictionary containing status information
        """
        return {
            'initialized': self._initialized,
            'loading': self._loading,
            'debug_mode': self._debug_mode,
            'connection_status': self.server_communicator.get_connection_status(),
            'gmcp_polling': self.gmcp_manager.is_polling(),
            'widget_count': len(self._widgets),
        }
