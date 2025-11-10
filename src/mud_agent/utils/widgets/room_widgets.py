"""
Room widgets for the MUD agent.

This module contains widgets related to room information.
"""

import logging
from typing import Any

from rich.console import Console
from textual.reactive import reactive
from textual.widgets import RichLog

from .state_listener import StateListener

logger = logging.getLogger(__name__)
console = Console()

class RoomWidget(StateListener, RichLog):
    """Widget that displays room information only (no map)."""

    # Reactive attributes for the room details
    room_name = reactive("Unknown")
    room_num = reactive(0)
    area_name = reactive("Unknown")
    room_terrain = reactive("Unknown")
    room_details = reactive("")
    room_coords = reactive({})
    exits = reactive([])
    npcs = reactive([])
    register_for_room_events = True
    register_for_map_events = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.markup = True
        self.highlight = True
        self.last_room_num = 0
        self.first_update = True
        logger.debug(f"RoomWidget initialized with id: {getattr(self, 'id', 'no-id')}")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        logger.debug(f"RoomWidget on_mount called for widget id: {getattr(self, 'id', 'no-id')}")
        super().on_mount()
        logger.debug(f"RoomWidget on_mount completed for widget id: {getattr(self, 'id', 'no-id')}")

    def update_content(self):
        import time
        start_time = time.time()
        logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} update_content() started at {start_time}")

        self.clear()
        if (
            self.room_name
            and self.room_name != "Unknown"
            and self.room_name != "Command sent, but no response captured."
        ):
            self.write(f"[bold cyan]{self.room_name}[/bold cyan]")
        elif self.area_name and self.area_name != "Unknown":
            self.write(f"[bold cyan]{self.area_name}[/bold cyan]")
        else:
            self.write("[bold red]Unknown Location[/bold red]")
        if self.room_num:
            self.write(f"[dim]Room #: {self.room_num}[/dim]")
        if (
            self.area_name
            and self.area_name != "Unknown"
            and self.area_name != self.room_name
        ):
            self.write(f"[bold green]Area: {self.area_name}[/bold green]")
        if self.room_terrain and self.room_terrain != "Unknown":
            self.write(f"[dim]Terrain: {self.room_terrain}[/dim]")
        if self.room_coords:
            if isinstance(self.room_coords, dict):
                coord_parts = []
                if "x" in self.room_coords:
                    coord_parts.append(f"X={self.room_coords['x']}")
                if "y" in self.room_coords:
                    coord_parts.append(f"Y={self.room_coords['y']}")
                if "cont" in self.room_coords:
                    coord_parts.append(f"Cont={self.room_coords['cont']}")
                if coord_parts:
                    coords_str = ", ".join(coord_parts)
                    self.write(f"[dim]Coords: {coords_str}[/dim]")
            else:
                self.write(f"[dim]Coords: {self.room_coords}[/dim]")
        if self.room_details:
            self.write(f"[dim]Details: {self.room_details}[/dim]")
        if self.exits:
            if isinstance(self.exits, dict):
                exits_str = ", ".join(self.exits.keys())
            elif isinstance(self.exits, list):
                exits_str = ", ".join(self.exits)
            else:
                exits_str = str(self.exits)
            self.write(f"[bold yellow]Exits: {exits_str}[/bold yellow]")
        else:
            self.write("[bold red]No visible exits[/bold red]")

        # Display NPCs if any are present
        if self.npcs:
            if isinstance(self.npcs, list):
                npcs_str = ", ".join(self.npcs)
            else:
                npcs_str = str(self.npcs)
            self.write(f"[bold magenta]NPCs: {npcs_str}[/bold magenta]")
        else:
            self.write("[dim]No NPCs present[/dim]")

        end_time = time.time()
        duration = end_time - start_time
        logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} update_content() completed in {duration:.4f}s")

    def _on_room_update(self, **kwargs) -> None:
        """Handle a room update event.

        Args:
            updates: Dictionary of room updates (raw GMCP data)
        """
        updates = kwargs.get("room_data", {})
        try:
            import time
            start_time = time.time()
            logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} received room_update at {start_time}: {updates}")

            # Check if room number has changed
            if updates.get("num"):
                current_room_num = updates["num"]
                if self.last_room_num != current_room_num and self.last_room_num != 0:
                    logger.debug(
                        f"Room number changed from {self.last_room_num} to {current_room_num}"
                    )
                    # Request room info if the room has changed
                    self._request_room_update()
                # Update the last room number
                self.last_room_num = current_room_num
                self.room_num = current_room_num

            # Update room information - handle both GMCP field names and normalized names
            # GMCP uses 'brief' for room name
            if "brief" in updates:
                self.room_name = updates["brief"]
            elif "name" in updates:
                self.room_name = updates["name"]

            # GMCP uses 'zone' for area name
            if "zone" in updates:
                self.area_name = updates["zone"]
            elif "area" in updates:
                self.area_name = updates["area"]

            # GMCP uses 'sector' for terrain
            if "sector" in updates:
                self.room_terrain = updates["sector"]
            elif "terrain" in updates:
                self.room_terrain = updates["terrain"]

            # Handle other fields
            if "flags" in updates:
                self.room_details = updates["flags"]
            elif "details" in updates:
                self.room_details = updates["details"]

            # GMCP uses 'coord' for coordinates
            if "coord" in updates:
                self.room_coords = updates["coord"]
            elif "coords" in updates:
                self.room_coords = updates["coords"]

            if "exits" in updates:
                self.exits = updates["exits"]
            if "npcs" in updates:
                self.npcs = updates["npcs"]

            # Update the widget content
            logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} calling update_content()")
            self.update_content()
            logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} calling refresh()")
            # Force a refresh to ensure the widget is visible
            self.refresh()

            end_time = time.time()
            duration = end_time - start_time
            logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} room_update completed in {duration:.4f}s - room: {self.room_name} (#{self.room_num})")
        except Exception as e:
            logger.error(
                f"Error handling room update in RoomWidget: {e}", exc_info=True
            )

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        # This method is called when the state changes. We need to update the
        # widget with the new information.
        if "room" in updates:
            self._on_room_update(room_data=updates["room"])

    def _handle_state_update(self, updates: dict[str, Any]) -> None:
        try:
            import time
            start_time = time.time()
            logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} received state_update at {start_time}")

            # Check for room updates
            if "room" in updates:
                room_updates = updates["room"]

                # Update room information
                if "name" in room_updates:
                    self.room_name = room_updates["name"]
                if "num" in room_updates:
                    current_room_num = room_updates["num"]
                    # Check if room number has changed
                    if (
                        self.last_room_num != current_room_num
                        and self.last_room_num != 0
                    ):
                        logger.debug(
                            f"Room number changed from {self.last_room_num} to {current_room_num}"
                        )
                        # Request room info if the room has changed
                        self._request_room_update()
                    # Update the last room number
                    self.last_room_num = current_room_num
                    self.room_num = current_room_num
                if "area" in room_updates:
                    self.area_name = room_updates["area"]
                if "terrain" in room_updates:
                    self.room_terrain = room_updates["terrain"]
                if "details" in room_updates:
                    self.room_details = room_updates["details"]
                if "coords" in room_updates:
                    self.room_coords = room_updates["coords"]
                if "exits" in room_updates:
                    self.exits = room_updates["exits"]
                if "npcs" in room_updates:
                    self.npcs = room_updates["npcs"]

                # Update the widget content
                logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} state_update calling update_content()")
                self.update_content()
                logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} state_update calling refresh()")
                # Force a refresh to ensure the widget is visible
                self.refresh()

                end_time = time.time()
                duration = end_time - start_time
                logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} state_update completed in {duration:.4f}s")
            else:
                logger.debug(f"[FREEZE_DEBUG] RoomWidget {getattr(self, 'id', 'no-id')} state_update has no room data")
        except Exception as e:
            logger.error(
                f"Error handling state update in RoomWidget: {e}", exc_info=True
            )

    def _request_room_update(self):
        """Room data will be received automatically from the server."""
        try:
            # Get the agent from the app
            agent = getattr(self.app, "agent", None)
            if not agent:
                logger.warning("No agent available for room update request")
                return

            # Room data will be sent automatically by the server
            logger.debug("Room data will be received automatically from server")

        except Exception as e:
            logger.error(f"Error in room update handler: {e}", exc_info=True)

    # Legacy methods for backward compatibility

    def bind_to_state_manager(self):
        """Bind widget to state manager reactive attributes.

        This method is kept for backward compatibility.
        The StateListener now handles event registration.
        """
        pass

    def update_from_state_manager(self, room_manager):
        """Update the widget from the room manager's state.

        This method is used by the TextualIntegration class.

        Args:
            room_manager: The room manager containing the state
        """
        try:
            # Update room information
            if hasattr(room_manager, "current_room"):
                self.room_name = room_manager.current_room or "Unknown"

            if hasattr(room_manager, "current_exits"):
                self.exits = room_manager.current_exits

            # Update NPCs from state manager
            self.npcs = getattr(room_manager.agent.state_manager, 'npcs', []) if hasattr(room_manager, 'agent') and hasattr(room_manager.agent, 'state_manager') else []

            # Get GMCP room data if available
            if hasattr(room_manager.agent, "state_manager"):
                state_manager = room_manager.agent.state_manager

                # Update area name
                if hasattr(state_manager, "area_name") and state_manager.area_name:
                    self.area_name = state_manager.area_name

                # Update terrain
                if (
                    hasattr(state_manager, "room_terrain")
                    and state_manager.room_terrain
                ):
                    self.room_terrain = state_manager.room_terrain

                # Update room details
                if (
                    hasattr(state_manager, "room_details")
                    and state_manager.room_details
                ):
                    self.room_details = state_manager.room_details

                # Update room number
                if hasattr(state_manager, "room_num") and state_manager.room_num:
                    current_room_num = state_manager.room_num
                    self.room_num = current_room_num

                    # Check if we've moved to a new room
                    if (
                        self.last_room_num != current_room_num
                        and self.last_room_num != 0
                    ):
                        self._request_room_update()

                    # Update the last room number
                    self.last_room_num = current_room_num

                # Update coordinates
                if hasattr(state_manager, "room_coords") and state_manager.room_coords:
                    self.room_coords = state_manager.room_coords

            # If GMCP data is not in state_manager, try to get it directly from GMCP
            if hasattr(room_manager.agent, "aardwolf_gmcp"):
                gmcp = room_manager.agent.aardwolf_gmcp
                room_info = gmcp.get_room_info()

                if room_info:
                    # Check if room number has changed
                    if room_info.get("num"):
                        current_room_num = room_info["num"]
                        if (
                            self.last_room_num != current_room_num
                            and self.last_room_num != 0
                        ):
                            self._request_room_update()

                        # Update the last room number
                        self.last_room_num = current_room_num
                        self.room_num = current_room_num

                    # Update area name if not already set
                    if (
                        self.area_name == "Unknown"
                        and "area" in room_info
                        and room_info["area"]
                    ):
                        self.area_name = room_info["area"]

                    # Update terrain if not already set
                    if (
                        self.room_terrain == "Unknown"
                        and "terrain" in room_info
                        and room_info["terrain"]
                    ):
                        self.room_terrain = room_info["terrain"]

                    # Update room details if not already set
                    if (
                        not self.room_details
                        and "details" in room_info
                        and room_info["details"]
                    ):
                        self.room_details = room_info["details"]

                    # Update coordinates if not already set
                    if (
                        not self.room_coords
                        and "coords" in room_info
                        and room_info["coords"]
                    ):
                        self.room_coords = room_info["coords"]

            # Update the widget content
            self.update_content()
        except Exception as e:
            logger.error(f"Error updating from state manager: {e}", exc_info=True)
