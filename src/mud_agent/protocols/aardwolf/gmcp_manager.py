"""
Aardwolf GMCP Manager for MUD Agent.

This module handles Aardwolf-specific GMCP data using a component-based architecture.
"""

import asyncio
import json
import logging
import time
from typing import Any

from .character_data import CharacterDataProcessor
from .map_data import MapDataProcessor
from .room_data import RoomDataProcessor
from .utils import deep_copy_dict, deep_update_dict

logger = logging.getLogger(__name__)


class AardwolfGMCPManager:
    """Manages Aardwolf-specific GMCP data using a component-based architecture."""

    # Configuration constants
    DEFAULT_KG_UPDATE_INTERVAL = 5.0  # seconds
    MAX_KG_UPDATE_FAILURES = 5

    def __init__(self, client, event_manager, kg_update_interval: float | None = None, max_kg_failures: int | None = None):
        """Initialize the GMCP manager.

        Args:
            client: The MUD client
            event_manager: The event manager for emitting events.
            kg_update_interval: Minimum interval between knowledge graph updates (seconds)
            max_kg_failures: Maximum consecutive failures before suspension
        """
        self.client = client
        self.events = event_manager
        self.logger = logger  # Use the module-level logger

        # Initialize data processors
        self.character_processor = CharacterDataProcessor(self)
        self.room_processor = RoomDataProcessor(self)
        self.map_processor = MapDataProcessor(self)

        # Character data
        self.char_data = {}
        self.room_data = {}
        self.map_data = {}

        # Last update timestamps
        self.last_update = {"char": 0, "room": 0, "map": 0}

        # Initialization status
        self.initialized = False

        # Knowledge graph update configuration
        self.kg_update_interval = (
            kg_update_interval if kg_update_interval is not None else self.DEFAULT_KG_UPDATE_INTERVAL
        )
        self.max_kg_failures = (
            max_kg_failures if max_kg_failures is not None else self.MAX_KG_UPDATE_FAILURES
        )
        self._kg_update_failures = 0
        self._kg_update_task: Any | None = None

        # Agent reference (set by the agent)
        self.agent: Any = None



    async def initialize(self):
        """Initialize GMCP support for Aardwolf.

        Returns:
            bool: True if initialization was successful
        """
        if not self.client.gmcp_enabled:
            self.logger.warning("GMCP not enabled, cannot initialize Aardwolf GMCP")
            return False

        try:
            # Request specific Aardwolf GMCP modules
            await self.client._send_gmcp(
                "Core.Supports.Set",
                [
                    "Char 1",
                    "Char.Vitals 1",
                    "Char.Stats 1",
                    "Char.Status 1",
                    "Char.Base 1",
                    "Char.Worth 1",
                    "Char.Maxstats 1",
                    "Room 1",
                    "Room.Info 1",
                    "Comm 1",
                    "Comm.Channel 1",
                    "Group 1",
                ],
            )

            # Enable GMCP options in Aardwolf
            # First, send the restart command to ensure GMCP is properly initialized
            await self.client.send_command("protocols gmcp restart")

            # Enable Room GMCP for map data
            await self.client.send_command("protocols gmcp Room on")

            # Enable Char GMCP for character data
            await self.client.send_command("protocols gmcp Char on")

            # Enable Debug for GMCP error messages
            await self.client.send_command("protocols gmcp Debug on")

            # Configure GMCP to use raw colors for better map display
            await self.client.send_command("protocols gmcp rawcolor on")

            # Enable mapper features
            await self.client.send_command("mapper set automap on")
            await self.client.send_command("mapper set autolink on")
            await self.client.send_command("mapper set automappercolor on")

            # Request mapper status
            await self.client.send_command("mapper status")

            # Request initial data with explicit commands
            await self.client._send_gmcp(
                "Char.Request",
                ["Vitals", "Stats", "Status", "Base", "Worth", "Maxstats"],
            )
 # Character and room data will be sent automatically by the server

            # Wait a moment for data to be processed
            await asyncio.sleep(0.5)

            # Update from GMCP to ensure we have the latest data
            self.update_from_gmcp()

            self.logger.debug("Aardwolf GMCP initialized and options enabled")
            self.initialized = True

            try:
                if self._kg_update_task is None:
                    import asyncio as _asyncio
                    self._kg_update_task = _asyncio.create_task(self._run_kg_update_loop())
            except Exception:
                pass
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Aardwolf GMCP: {e}", exc_info=True)
            return False

    def update_from_gmcp(self):
        """Update all data from GMCP.

        Returns:
            dict: Dictionary of updated modules
        """
        if not self.client.gmcp_enabled:
            self.logger.warning("GMCP not enabled, skipping update")
            return {}

        self.logger.debug("Updating data from GMCP")
        updates = {}

        # Update character data
        char_data = self.client.gmcp.get_module_data("char")
        if char_data:
            # Merge the new data with the existing data, preserving previous values
            # if they're not in the new data
            if self.char_data:
                # Create a deep copy of the existing data
                merged_char_data = deep_copy_dict(self.char_data)

                # Update with new data
                deep_update_dict(merged_char_data, char_data)

                # Set the merged data
                self.char_data = merged_char_data
            else:
                # If no previous data, just use the new data
                self.char_data = char_data

            self.last_update["char"] = time.time()
            updates["char"] = True
            self.logger.debug(
                f"Updated char data from GMCP with keys: {list(char_data.keys())}"
            )

            # Process character data
            char_updates = self.character_processor.process_data(self.char_data)

            # Update the state manager if available
            if hasattr(self, "agent") and self.agent is not None:
                if hasattr(self.agent, "state_manager"):
                    self.logger.debug("Updating state manager from GMCP")
                    self.agent.state_manager.update_from_aardwolf_gmcp(
                        char_updates.get("combined", {})
                    )
        else:
            self.logger.debug("No char data available from GMCP")

        # Update room data
        room_data = self.client.gmcp.get_module_data("room")
        if room_data:
            self.logger.debug("Got room data from GMCP")
            self.room_data = room_data
            self.last_update["room"] = time.time()
            updates["room"] = True

            # Process room data
            self.room_processor.process_data(self.room_data)

            # Emit an event with the room data
            room_data_to_emit = self.room_data.get("info", self.room_data)
            room_exits_to_emit = room_data_to_emit.get("exits", {})
            asyncio.create_task(
                self.events.emit(
                    "room_update",
                    room_data=room_data_to_emit,
                    room_exits=room_exits_to_emit,
                )
            )
            self.logger.debug("Emitted room_update event")
        else:
            self.logger.debug("No room data available from GMCP")

        # Update map data if available
        map_data = self.client.gmcp.get_module_data("room.map")
        if map_data:
            self.logger.debug("Got map data from GMCP")
            self.map_data = map_data
            self.last_update["map"] = time.time()
            updates["map"] = True

            # Process map data
            self.map_processor.process_data(self.map_data)
        else:
            self.logger.debug("No map data available from GMCP")

            # Try to get map data from room.info if available
            if "info" in self.room_data and "map" in self.room_data["info"]:
                self.logger.debug("Found map in room.info")
                self.map_data = self.room_data["info"]["map"]
                self.last_update["map"] = time.time()
                updates["map"] = True

                # Process map data
                self.map_processor.process_data(self.map_data)

        # Log a summary of what was updated
        if updates:
            self.logger.debug(f"GMCP updates received: {', '.join(updates.keys())}")


        else:
            self.logger.debug("No GMCP updates received")

        return updates

    async def _run_kg_update_loop(self) -> None:
        try:
            import asyncio as _asyncio
            while True:
                try:
                    if self.agent and hasattr(self.agent, "knowledge_graph"):
                        room_info = self.get_room_info()
                        if room_info and room_info.get("num") and room_info.get("name"):
                            entity_data = {
                                "entityType": "Room",
                                "room_number": room_info.get("num"),
                                "name": room_info.get("name"),
                                "description": room_info.get("desc", ""),
                                "exits": room_info.get("exits", {}),
                                "area": room_info.get("zone", room_info.get("area", "Unknown")),
                                "coordinates": room_info.get("coord", {}),
                                "npcs": room_info.get("npcs", []),
                            }
                            try:
                                await self.agent.knowledge_graph.add_entity(entity_data)
                                self._kg_update_failures = 0
                            except Exception:
                                self._kg_update_failures += 1
                                if self._kg_update_failures >= self.max_kg_failures:
                                    self.logger.error("Suspending KG updates due to repeated failures")
                                    break
                    await _asyncio.sleep(self.kg_update_interval)
                except _asyncio.CancelledError:
                    break
                except Exception as e:
                    self._kg_update_failures += 1
                    self.logger.error(f"KG update loop error: {e}", exc_info=True)
                    await _asyncio.sleep(self.kg_update_interval)
        finally:
            self._kg_update_task = None

    def stop_kg_update_loop(self) -> None:
        try:
            task = self._kg_update_task
            if task and not task.done():
                task.cancel()
        except Exception:
            pass
    def get_character_data(self) -> dict[str, Any]:
        """Get comprehensive character data from GMCP.

        Returns:
            dict: Combined character data or empty dict if not available
        """
        return self.character_processor.get_character_data()

    def get_room_info(self) -> dict[str, Any]:
        """Get room information from GMCP data.

        Returns:
            dict: Room information or empty dict if not available
        """
        return self.room_processor.get_room_info()

    def get_map_data(self) -> str:
        """Get map data from GMCP.

        Returns:
            str: Map data or empty string if not available
        """
        return self.map_processor.get_map_data()

    # Quest data method removed

    def get_all_character_data(self) -> dict[str, Any]:
        """Get all character data in a single call.

        This is a convenience method that combines all character data methods
        into a single call, returning a comprehensive dictionary with all
        character information.

        Returns:
            dict: All character data including vitals, stats, maxstats, and more
        """
        return self.character_processor.get_all_character_data()

    def get_worth_data(self) -> dict[str, Any]:
        """Get character worth data from GMCP.

        Returns:
            dict: Character worth data or empty dict if not available
        """
        char_data = self.character_processor.get_character_data()
        worth_data = char_data.get("worth", {})
        return worth_data

    def get_stats_data(self) -> dict[str, Any]:
        """Get character stats from GMCP data.

        Returns:
            dict: Character stats or empty dict if not available
        """
        char_data = self.character_processor.get_character_data()
        stats_data = char_data.get("stats", {})
        return stats_data

    def get_maxstats_data(self) -> dict[str, Any]:
        """Get character max stats from GMCP data.

        Returns:
            dict: Character max stats or empty dict if not available
        """
        char_data = self.character_processor.get_character_data()
        maxstats_data = char_data.get("maxstats", {})
        return maxstats_data

    def get_vitals_data(self) -> dict[str, Any]:
        """Get character vitals from GMCP data.

        Returns:
            dict: Character vitals or empty dict if not available
        """
        char_data = self.character_processor.get_character_data()
        vitals_data = char_data.get("vitals", {})
        combined_data = char_data.get("combined", {})

        # Extract values from combined data if available, otherwise use vitals data
        hp = combined_data.get("hp", vitals_data.get("hp", 0))
        maxhp = combined_data.get("maxhp", vitals_data.get("maxhp", 0))
        mana = combined_data.get("mana", vitals_data.get("mana", 0))
        maxmana = combined_data.get("maxmana", vitals_data.get("maxmana", 0))
        moves = combined_data.get("moves", vitals_data.get("moves", 0))
        maxmoves = combined_data.get("maxmoves", vitals_data.get("maxmoves", 0))

        # Also check for mp/mv aliases
        if "mp" in combined_data and not mana:
            mana = combined_data.get("mp", 0)
        if "maxmp" in combined_data and not maxmana:
            maxmana = combined_data.get("maxmp", 0)
        if "mv" in combined_data and not moves:
            moves = combined_data.get("mv", 0)
        if "maxmv" in combined_data and not maxmoves:
            maxmoves = combined_data.get("maxmv", 0)

        # Convert to integers if possible
        try:
            hp = int(hp) if hp else 0
            maxhp = int(maxhp) if maxhp else 0
            mana = int(mana) if mana else 0
            maxmana = int(maxmana) if maxmana else 0
            moves = int(moves) if moves else 0
            maxmoves = int(maxmoves) if maxmoves else 0
        except (ValueError, TypeError) as e:
            self.logger.error(
                f"Error converting vitals to integers: {e}", exc_info=True
            )

        # Return the flat structure used by the containers.py code
        flat_vitals = {
            "hp": hp,
            "maxhp": maxhp,
            "mana": mana,
            "maxmana": maxmana,
            "moves": moves,
            "maxmoves": maxmoves,
        }

        return flat_vitals

    def get_quest_data(self) -> dict[str, Any]:
        """Get quest information from GMCP.

        Returns:
            dict: Quest information or empty dict if not available
        """
        return {}

    def is_data_fresh(self, module: str, max_age: float = 5.0) -> bool:
        """Check if data for a module is fresh.

        Args:
            module: The module name (char, room, map, quest)
            max_age: Maximum age in seconds

        Returns:
            bool: True if data is fresh
        """
        if module not in self.last_update:
            return False

        return time.time() - self.last_update[module] < max_age

    async def send_gmcp_command(self, command: str, args: list = None) -> None:
        """Send a GMCP command to the server.

        Args:
            command: The GMCP command to send
            args: Optional arguments for the command
        """
        if not self.client.gmcp_enabled:
            self.logger.warning("GMCP not enabled, cannot send command")
            return

        try:
            # Format the command based on whether args are provided
            if args:
                formatted_command = f"{command} {json.dumps(args)}"
            else:
                formatted_command = command

            # Send the command
            await self.client._send_gmcp(formatted_command, None)
            self.logger.debug(f"Sent GMCP command: {command}")
        except Exception as e:
            self.logger.error(f"Error sending GMCP command: {e}", exc_info=True)

    # Removed request_gmcp_data method - relying on automatic server pushes

    async def toggle_gmcp_option(self, option: str, enable: bool = True) -> None:
        """Toggle a GMCP option in Aardwolf.

        Args:
            option: The GMCP option to toggle (Room, Char, Debug, etc.)
            enable: Whether to enable or disable the option
        """
        try:
            # Format the command
            command = f"protocols gmcp {option} {'on' if enable else 'off'}"

            # Send the command
            await self.client.send_command(command)
            self.logger.debug(
                f"Toggled GMCP option {option} {'on' if enable else 'off'}"
            )
        except Exception as e:
            self.logger.error(f"Error toggling GMCP option: {e}", exc_info=True)

    async def get_gmcp_status(self) -> None:
        """Get the status of GMCP options in Aardwolf.

        This sends the 'protocols gmcp' command to show GMCP options.
        """
        try:
            await self.client.send_command("protocols gmcp")
            self.logger.debug("Requested GMCP status")
        except Exception as e:
            self.logger.error(f"Error getting GMCP status: {e}", exc_info=True)

    async def request_all_data(self) -> None:
        """Request all character-related GMCP data from the server."""
        if not self.client.gmcp_enabled:
            self.logger.warning("GMCP not enabled, cannot request data")
            return

        try:
            self.logger.debug("Requesting all GMCP data from server")
            await self.client._send_gmcp(
                "Char.Request",
                ["Vitals", "Stats", "Status", "Base", "Worth", "Maxstats"],
            )
        except Exception as e:
            self.logger.error(f"Error requesting all GMCP data: {e}", exc_info=True)

    async def request_map_data(self) -> None:
        """Request map data specifically.

        Note: Map data is not available via GMCP in Aardwolf.
        The map is only displayed when the 'map' command is executed.
        This method is kept for backward compatibility.
        """
        try:
            # Make sure Room module is enabled
            await self.toggle_gmcp_option("Room", True)
            self.logger.debug("Ensured Room module is enabled")

            # Room data will be sent automatically by the server
            self.logger.debug("Room data will be received automatically from server")

            # Note: Map data is not available via GMCP in Aardwolf
            self.logger.debug("Note: Map data is not available via GMCP in Aardwolf")
        except Exception as e:
            self.logger.error(f"Error requesting map data: {e}", exc_info=True)

    def get_map_data(self) -> str:
        """Get the map data from GMCP.

        Note: Map data is not available via GMCP in Aardwolf.
        This method is kept for backward compatibility and will always return an empty string.

        Returns:
            str: Map data (empty string since map data is not available via GMCP)
        """
        # Map data is not available via GMCP in Aardwolf
        # This method is kept for backward compatibility
        return ""

    def get_room_info(self) -> dict:
        """Get the room information from GMCP.

        Returns:
            dict: Room information from GMCP
        """
        try:
            # Check if we have room data
            if "info" in self.room_data:
                return self.room_data["info"]
            return {}
        except Exception as e:
            self.logger.error(f"Error getting room info: {e}", exc_info=True)
            return {}
