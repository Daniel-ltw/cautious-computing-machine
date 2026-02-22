"""GMCP management and polling for the MUD Textual App.

This module handles all GMCP-related functionality including polling,
data processing, and widget updates based on GMCP data.
"""

import asyncio
import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class GMCPManager:
    """Manages GMCP polling and data processing for the MUD application."""

    def __init__(self, app):
        self.app = app
        self.agent = app.agent
        self.state_manager = app.state_manager
        self.logger = logger

        # GMCP polling state
        self._gmcp_polling_task: asyncio.Task | None = None
        self._gmcp_polling_enabled = False
        self._gmcp_poll_interval = 5.0  # Default 5 seconds
        self._in_combat = False
        self._last_gmcp_update = 0
        self._gmcp_update_debounce = 0.5  # 500ms debounce

    async def setup(self) -> None:
        """Set up the GMCP manager and subscribe to MUD client events."""
        try:
            # Subscribe to GMCP events from the MUD client
            if hasattr(self.agent, 'client') and self.agent.client:
                # Subscribe to generic gmcp_data events
                self.agent.client.events.on('gmcp_data', self._on_gmcp_data)

                # Subscribe to specific GMCP module events
                self.agent.client.events.on('gmcp.room.info', self._on_room_info)
                self.agent.client.events.on('gmcp.char.vitals', self._on_char_vitals)
                self.agent.client.events.on('gmcp.char.stats', self._on_char_stats)

                logger.info("GMCP manager subscribed to MUD client events")
            else:
                logger.warning("No MUD client available for GMCP event subscription")

        except Exception as e:
            logger.error(f"Error setting up GMCP manager: {e}", exc_info=True)

    def _on_gmcp_data(self, package: str, data: dict) -> None:
        """Handle generic GMCP data events from the MUD client.

        Args:
            package: The GMCP package name
            data: The GMCP data payload
        """
        try:
            self.handle_gmcp_package(package, data)
        except Exception as e:
            logger.error(f"Error handling GMCP data event: {e}", exc_info=True)

    def _on_room_info(self, data: dict) -> None:
        """Handle room.info GMCP events from the MUD client.

        Args:
            data: The room info data
        """
        logger.debug(f"_on_room_info received data: {json.dumps(data, indent=2)}")
        try:
            self.handle_gmcp_package('room.info', data)
        except Exception as e:
            logger.error(f"Error handling room.info event: {e}", exc_info=True)

    def _on_char_vitals(self, data: dict) -> None:
        """Handle char.vitals GMCP events from the MUD client.

        Args:
            data: The character vitals data
        """
        try:
            self.handle_gmcp_package('char.vitals', data)
        except Exception as e:
            logger.error(f"Error handling char.vitals event: {e}", exc_info=True)

    def _on_char_stats(self, data: dict) -> None:
        """Handle char.stats GMCP events from the MUD client.

        Args:
            data: The character stats data
        """
        try:
            self.handle_gmcp_package('char.stats', data)
        except Exception as e:
            logger.error(f"Error handling char.stats event: {e}", exc_info=True)

    async def start_gmcp_polling(self) -> None:
        """Start the GMCP polling worker."""
        if self._gmcp_polling_task and not self._gmcp_polling_task.done():
            logger.debug("GMCP polling already running")
            return

        self._gmcp_polling_enabled = True
        self._gmcp_polling_task = asyncio.create_task(self._gmcp_polling_worker())
        logger.info("Started GMCP polling worker")

    async def stop_gmcp_polling(self) -> None:
        """Stop the GMCP polling worker."""
        if self._gmcp_polling_task and not self._gmcp_polling_task.done():
            self._gmcp_polling_task.cancel()
            try:
                await self._gmcp_polling_task
            except asyncio.CancelledError:
                pass  # Expected on cancellation

        self._gmcp_polling_task = None
        self._gmcp_polling_enabled = False
        return None

        if self._gmcp_polling_task and not self._gmcp_polling_task.done():
            self._gmcp_polling_task.cancel()
            try:
                await self._gmcp_polling_task
            except asyncio.CancelledError:
                pass

        self._gmcp_polling_task = None
        logger.info("Stopped GMCP polling worker")

    async def _gmcp_polling_worker(self) -> None:
        """Background worker that polls GMCP data periodically."""
        logger.info("GMCP polling worker started")

        # Initial poll with a short delay to let the connection stabilize
        await asyncio.sleep(1.0)
        await self._perform_initial_gmcp_poll()

        # Start the main polling loop
        while self._gmcp_polling_enabled:
            try:
                await asyncio.sleep(self._gmcp_poll_interval)

                if not self._gmcp_polling_enabled:
                    break

                # Poll GMCP data
                await self._poll_gmcp_data()

                # Adjust polling interval based on combat status
                self._adjust_polling_interval()

            except asyncio.CancelledError:
                logger.info("GMCP polling worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in GMCP polling worker: {e}", exc_info=True)
                # Continue polling even if there's an error
                await asyncio.sleep(1.0)

        logger.info("GMCP polling worker stopped")

    async def _perform_initial_gmcp_poll(self) -> None:
        """GMCP data will be received automatically from the server."""
        try:
            if hasattr(self.agent, "aardwolf_gmcp"):
                # Wait a moment for GMCP to be fully initialized
                await asyncio.sleep(1.0)

                # Character and room data will be sent automatically by the server
                self.logger.debug("GMCP data will be received automatically from server")

                # Wait for data to be processed
                await asyncio.sleep(0.5)

                # Update widgets with initial data
                await self.app.update_reactive_widgets()

                logger.debug("Initial GMCP poll completed")
        except Exception as e:
            logger.error(f"Error in initial GMCP poll: {e}", exc_info=True)

    async def _poll_gmcp_data(self) -> None:
        """Poll GMCP data and update widgets if needed."""
        try:
            if not hasattr(self.agent, "aardwolf_gmcp"):
                return

            # Character data will be sent automatically by the server
            logger.debug("Character data will be received automatically from server")

            # Process any updates
            updates = self.agent.aardwolf_gmcp.update_from_gmcp()

            if updates:
                logger.debug(f"GMCP updates received: {', '.join(updates.keys())}")

                # Update widgets if we have vitals updates
                if any(key in updates for key in ['hp', 'mp', 'mv', 'stats']):
                    # Use debouncing to avoid too frequent updates
                    current_time = asyncio.get_event_loop().time()
                    if current_time - self._last_gmcp_update > self._gmcp_update_debounce:
                        await self.app.update_reactive_widgets()
                        self._last_gmcp_update = current_time

                # Check for combat status changes
                if 'combat' in updates:
                    await self._handle_combat_status_change(updates['combat'])

        except Exception as e:
            logger.error(f"Error polling GMCP data: {e}", exc_info=True)

    def _adjust_polling_interval(self) -> None:
        """Adjust polling interval based on combat status."""
        if self._in_combat:
            # Poll more frequently during combat
            self._gmcp_poll_interval = 0.5
        else:
            # Normal polling interval
            self._gmcp_poll_interval = 2.0

    async def _handle_combat_status_change(self, in_combat: bool) -> None:
        """Handle changes in combat status.

        Args:
            in_combat: Whether the character is currently in combat
        """
        if self._in_combat != in_combat:
            self._in_combat = in_combat
            logger.info(f"Combat status changed: {'in combat' if in_combat else 'out of combat'}")

            # Notify the app about combat status change
            if hasattr(self.app, '_on_combat_status_changed'):
                await self.app._on_combat_status_changed(in_combat)

    async def process_gmcp_update(self, gmcp_data: dict[str, Any]) -> None:
        """Process a GMCP update and queue widget updates.

        Args:
            gmcp_data: The GMCP data that was updated
        """
        try:
            # Update state manager from GMCP
            if hasattr(self.agent, "aardwolf_gmcp"):
                updates = self.agent.aardwolf_gmcp.update_from_gmcp()

                if updates:
                    logger.debug(f"Processing GMCP updates: {', '.join(updates.keys())}")

                    # Update state manager
                    await self._update_state_manager_from_gmcp(updates)

                    # Queue widget updates with debouncing
                    current_time = asyncio.get_event_loop().time()
                    if current_time - self._last_gmcp_update > self._gmcp_update_debounce:
                        await self.app.update_reactive_widgets()
                        self._last_gmcp_update = current_time

        except Exception as e:
            logger.error(f"Error processing GMCP update: {e}", exc_info=True)

    async def _update_state_manager_from_gmcp(self, updates: dict[str, Any]) -> None:
        """Update the state manager with GMCP data.

        Args:
            updates: Dictionary of GMCP updates
        """
        try:
            # Update vitals
            if 'hp' in updates:
                self.state_manager.hp = updates['hp']
            if 'mp' in updates:
                self.state_manager.mp = updates['mp']
            if 'mv' in updates:
                self.state_manager.mv = updates['mv']

            # Update room information
            if 'room' in updates:
                room_data = updates['room']
                if 'name' in room_data:
                    self.state_manager.room_name = room_data['name']
                if 'num' in room_data:
                    self.state_manager.room_num = room_data['num']
                if 'exits' in room_data:
                    self.state_manager.exits = room_data['exits']

            # Update character stats
            if 'stats' in updates:
                stats = updates['stats']
                # Update any relevant character stats
                for stat_name, stat_value in stats.items():
                    if hasattr(self.state_manager, stat_name):
                        setattr(self.state_manager, stat_name, stat_value)

            # Update combat status
            if 'combat' in updates:
                self._in_combat = updates['combat']

        except Exception as e:
            logger.error(f"Error updating state manager from GMCP: {e}", exc_info=True)

    # Removed request_gmcp_data method - relying on automatic server pushes

    def get_character_data(self) -> dict[str, Any]:
        """Get current character data from GMCP.

        Returns:
            Dictionary containing character data
        """
        try:
            if hasattr(self.agent, "aardwolf_gmcp"):
                return self.agent.aardwolf_gmcp.get_character_data()
            return {}
        except Exception as e:
            logger.error(f"Error getting character data: {e}", exc_info=True)
            return {}

    def get_room_data(self) -> dict[str, Any]:
        """Get current room data from GMCP.

        Returns:
            Dictionary containing room data
        """
        try:
            if hasattr(self.agent, "aardwolf_gmcp"):
                return self.agent.aardwolf_gmcp.get_room_info()
            return {}
        except Exception as e:
            logger.error(f"Error getting room data: {e}", exc_info=True)
            return {}

    def is_polling_enabled(self) -> bool:
        """Check if GMCP polling is currently enabled.

        Returns:
            True if polling is enabled, False otherwise
        """
        return self._gmcp_polling_enabled

    def get_polling_status(self) -> dict[str, Any]:
        """Get current polling status information.

        Returns:
            Dictionary containing polling status
        """
        return {
            'enabled': self._gmcp_polling_enabled,
            'interval': self._gmcp_poll_interval,
            'in_combat': self._in_combat,
            'task_running': self._gmcp_polling_task is not None and not self._gmcp_polling_task.done()
        }

    def handle_gmcp_package(self, package: str, data: dict[str, Any]) -> None:
        """Handle incoming GMCP packages and update the state manager.

        Args:
            package: The GMCP package name (e.g., 'room.info', 'char.vitals')
            data: The GMCP data payload
        """
        try:
            if not data:
                self.logger.debug(f"Received empty data for GMCP package: {package}")
                return

            self.logger.debug(f"Handling GMCP package: {package}")

            if package == "room.info":
                self._handle_room_info(data)
            elif package == "char.vitals":
                self._handle_char_vitals(data)
            elif package == "char.stats":
                self._handle_char_stats(data)
            elif package == "char.maxstats":
                self._handle_char_maxstats(data)
            else:
                self.logger.debug(f"Unhandled GMCP package: {package}")

        except Exception as e:
            self.logger.error(f"Error handling GMCP package {package}: {e}", exc_info=True)

    def _handle_room_info(self, data: dict[str, Any]) -> None:
        """Handle room.info GMCP data and update state manager.

        Args:
            data: Room information from GMCP
        """
        try:
            self.logger.debug(f"GMCPManager._handle_room_info: {json.dumps(data, indent=2)}")
            # Update state manager with room details according to Aardwolf GMCP spec
            if "num" in data:
                self.state_manager.room_num = data["num"]

            if "brief" in data:
                self.state_manager.room_name = data["brief"]

            if "zone" in data:
                self.state_manager.area_name = data["zone"]

            if "sector" in data:
                self.state_manager.room_terrain = data["sector"]

            self.state_manager.exits = data.get("exits", {})

            if "coord" in data:
                self.state_manager.room_coords = data["coord"]

            # Handle flags if present
            if "flags" in data:
                self.state_manager.room_details = data["flags"]

            # Emit room update event
            import time
            emit_time = time.time()
            self.logger.debug(f"[FREEZE_DEBUG] GMCPManager emitting room_update event at {emit_time} with data: {data}")
            if threading.current_thread() is threading.main_thread():
                self.state_manager.events.emit("room_update", room_data=data)
            else:
                self.app.call_from_thread(self.state_manager.events.emit, "room_update", room_data=data)
            self.logger.debug("[FREEZE_DEBUG] GMCPManager room_update event emitted successfully")

            self.logger.debug(f"Updated state manager from room.info: room {data.get('num', 'unknown')} - {data.get('brief', 'unknown')}")

        except Exception as e:
            self.logger.error(f"Error handling room.info data: {e}", exc_info=True)

    def _handle_char_vitals(self, data: dict[str, Any]) -> None:
        """Handle char.vitals GMCP data.

        Args:
            data: Character vitals from GMCP
        """
        try:
            # Map GMCP vitals data to state manager format
            vitals_data = {
                "hp": data.get("hp"),
                "maxhp": data.get("maxhp"),
                "mp": data.get("mp"),
                "maxmp": data.get("maxmp"),
                "mv": data.get("mv"),
                "maxmv": data.get("maxmv"),
            }

            # Only update if we have valid vitals data
            if vitals_data:
                self.state_manager.update_from_gmcp(self.agent.aardwolf_gmcp)

            self.logger.debug("Updated state manager from char.vitals")

        except Exception as e:
            self.logger.error(f"Error handling char.vitals data: {e}", exc_info=True)

    def _handle_char_stats(self, data: dict[str, Any]) -> None:
        """Handle char.stats GMCP data.

        Args:
            data: Character stats from GMCP
        """
        try:
            # Update character stats in state manager using update_from_gmcp
            # to ensure proper event emission
            self.state_manager.update_from_gmcp(self.agent.aardwolf_gmcp)

            self.logger.debug("Updated state manager from char.stats")

        except Exception as e:
            self.logger.error(f"Error handling char.stats data: {e}", exc_info=True)

    def _handle_char_maxstats(self, data: dict[str, Any]) -> None:
        """Handle char.maxstats GMCP data.

        Args:
            data: Character max stats from GMCP
        """
        try:
            # Update character max stats in state manager using update_from_gmcp
            # to ensure proper event emission
            self.state_manager.update_from_gmcp(self.agent.aardwolf_gmcp)

            self.logger.debug("Updated state manager from char.maxstats")

        except Exception as e:
            self.logger.error(f"Error handling char.maxstats data: {e}", exc_info=True)

    def parse_gmcp_message(self, package: str, json_data: str) -> tuple[str, dict[str, Any]]:
        """Parse a GMCP message into package and data.

        Args:
            package: The GMCP package name
            json_data: The JSON data string

        Returns:
            Tuple of (package, parsed_data)
        """
        try:
            if not json_data.strip():
                return package, {}

            data = json.loads(json_data) if json_data else {}
            return package, data

        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing GMCP JSON data: {e}")
            return package, {}

    def is_supported_package(self, package: str) -> bool:
        """Check if a GMCP package is supported.

        Args:
            package: The GMCP package name

        Returns:
            True if the package is supported
        """
        supported_packages = {
            "room.info",
            "char.vitals",
            "char.stats",
            "char.maxstats",
            "char.base",
            "char.worth",
            "char.status"
        }
        return package in supported_packages

    async def process_gmcp_data_async(self, package: str, data: dict[str, Any]) -> None:
        """Process GMCP data asynchronously.

        Args:
            package: The GMCP package name
            data: The GMCP data
        """
        try:
            self.handle_gmcp_package(package, data)

            # Update widgets if needed
            await self.app.update_reactive_widgets()

        except Exception as e:
            self.logger.error(f"Error processing GMCP data async: {e}", exc_info=True)
