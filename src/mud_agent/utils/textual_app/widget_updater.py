"""Widget update management for the MUD Textual App.

This module handles updating all widgets with data from GMCP,
state manager, and other sources.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional



from ..widgets.vitals_static_widgets import HPStaticWidget, MPStaticWidget, MVStaticWidget
from ..widgets.status_widgets import StatusEffectsWidget
from ..widgets.containers import StatusContainer
from ..widgets.mapper_container import MapperContainer

logger = logging.getLogger(__name__)


class WidgetUpdater:
    """Handles updating widgets with data from various sources."""

    def __init__(self, app):
        self.app = app
        self.agent = app.agent
        self.state_manager = app.state_manager
        self.logger = logger

        # Update throttling
        self._updating_widgets = False
        self._last_widget_update = 0
        self._widget_update_throttle = 0.1  # 100ms throttle

    async def update_all_widgets(self) -> None:
        """Update all widgets with current data."""
        try:
            # Throttle updates to avoid excessive calls
            current_time = asyncio.get_event_loop().time()
            if current_time - self._last_widget_update < self._widget_update_throttle:
                return

            if self._updating_widgets:
                return

            self._updating_widgets = True
            self._last_widget_update = current_time

            # Update all widget types
            await self._update_vitals_widgets()
            await self._update_status_widget()
            await self._update_map_widget()

        except Exception as e:
            logger.error(f"Error updating all widgets: {e}", exc_info=True)
        finally:
            self._updating_widgets = False

    async def _update_vitals_widgets(self) -> None:
        """Update vitals widgets (HP, MP, MV) with current data."""
        try:
            # Get character data from GMCP
            char_data = {}
            if hasattr(self.agent, "aardwolf_gmcp"):
                char_data = self.agent.aardwolf_gmcp.get_character_data()

            # Update HP widget
            await self._update_hp_widget(char_data)

            # Update MP widget
            await self._update_mp_widget(char_data)

            # Update MV widget
            await self._update_mv_widget(char_data)

        except Exception as e:
            logger.error(f"Error updating vitals widgets: {e}", exc_info=True)

    async def _update_hp_widget(self, char_data: Dict[str, Any]) -> None:
        """Update HP widget with current data.

        Args:
            char_data: Character data from GMCP
        """
        try:
            hp_widget = self.app.query_one("#hp-widget", HPStaticWidget)

            # Get HP data from GMCP or state manager
            hp_current = 0
            hp_max = 0

            if "vitals" in char_data and "hp" in char_data["vitals"]:
                hp_current = char_data["vitals"]["hp"]
            elif hasattr(self.state_manager, 'hp'):
                hp_current = self.state_manager.hp

            if "vitals" in char_data and "maxhp" in char_data["vitals"]:
                hp_max = char_data["vitals"]["maxhp"]
            elif hasattr(self.state_manager, 'max_hp'):
                hp_max = self.state_manager.max_hp

            # Use values from state manager (no hardcoded defaults)

            # Update the widget
            hp_widget.current_value = hp_current
            hp_widget.max_value = hp_max
            hp_widget.update_display()
            logger.debug(f"Updated HP widget: {hp_current}/{hp_max}")

        except Exception as e:
            logger.error(f"Error updating HP widget: {e}", exc_info=True)
            # Widget might not be available yet, which is normal during startup
            if "not found" not in str(e).lower():
                logger.error(f"HP widget error details: {e}", exc_info=True)

    async def _update_mp_widget(self, char_data: Dict[str, Any]) -> None:
        """Update MP widget with current data.

        Args:
            char_data: Character data from GMCP
        """
        try:
            mp_widget = self.app.query_one("#mp-widget", MPStaticWidget)

            # Get MP data from GMCP or state manager
            mp_current = 0
            mp_max = 0

            if "vitals" in char_data and "mp" in char_data["vitals"]:
                mp_current = char_data["vitals"]["mp"]
            elif hasattr(self.state_manager, 'mp'):
                mp_current = self.state_manager.mp

            if "vitals" in char_data and "maxmp" in char_data["vitals"]:
                mp_max = char_data["vitals"]["maxmp"]
            elif hasattr(self.state_manager, 'max_mp'):
                mp_max = self.state_manager.max_mp

            # Use values from state manager (no hardcoded defaults)

            # Update the widget
            mp_widget.current_value = mp_current
            mp_widget.max_value = mp_max
            mp_widget.update_display()
            logger.debug(f"Updated MP widget: {mp_current}/{mp_max}")

        except Exception as e:
            logger.error(f"Error updating MP widget: {e}", exc_info=True)
            # Widget might not be available yet, which is normal during startup
            if "not found" not in str(e).lower():
                logger.error(f"MP widget error details: {e}", exc_info=True)

    async def _update_mv_widget(self, char_data: Dict[str, Any]) -> None:
        """Update MV widget with current data.

        Args:
            char_data: Character data from GMCP
        """
        try:
            mv_widget = self.app.query_one("#mv-widget", MVStaticWidget)

            # Get MV data from GMCP or state manager
            mv_current = 0
            mv_max = 0

            if "vitals" in char_data and "mv" in char_data["vitals"]:
                mv_current = char_data["vitals"]["mv"]
            elif hasattr(self.state_manager, 'mv'):
                mv_current = self.state_manager.mv

            if "vitals" in char_data and "maxmv" in char_data["vitals"]:
                mv_max = char_data["vitals"]["maxmv"]
            elif hasattr(self.state_manager, 'max_mv'):
                mv_max = self.state_manager.max_mv

            # Use values from state manager (no hardcoded defaults)

            # Update the widget
            mv_widget.current_value = mv_current
            mv_widget.max_value = mv_max
            mv_widget.update_display()
            logger.debug(f"Updated MV widget: {mv_current}/{mv_max}")

        except Exception as e:
            logger.error(f"Error updating MV widget: {e}", exc_info=True)
            # Widget might not be available yet, which is normal during startup
            if "not found" not in str(e).lower():
                logger.error(f"MV widget error details: {e}", exc_info=True)

    async def _update_status_widget(self) -> None:
        """Update status widget with current data."""
        try:
            status_widget = self.app.query_one("#status-widget", StatusContainer)

            # Get current status from state manager
            room_name = getattr(self.state_manager, 'room_name', 'Unknown')
            room_num = getattr(self.state_manager, 'room_num', 0)
            exits = getattr(self.state_manager, 'exits', [])

            # Get character data from GMCP
            char_data = {}
            if hasattr(self.agent, "aardwolf_gmcp"):
                char_data = self.agent.aardwolf_gmcp.get_character_data()

            # Update the status widget
            status_widget.update_status(
                room_name=room_name,
                room_number=room_num,
                exits=exits,
                character_data=char_data
            )

            logger.debug(f"Updated status widget: {room_name} ({room_num})")

        except Exception as e:
            logger.error(f"Error updating status widget: {e}", exc_info=True)
            # Widget might not be available yet, which is normal during startup
            if "not found" not in str(e).lower():
                logger.error(f"Status widget error details: {e}", exc_info=True)

    async def _update_map_widget(self) -> None:
        """Update map widget with current room data."""
        try:
            # Get the parent container first, then access the mapper_container
            room_info_map_container = self.app.query_one("#room-info-map-container")
            if not hasattr(room_info_map_container, 'mapper_container') or room_info_map_container.mapper_container is None:
                logger.debug("Mapper container not yet available")
                return
            map_widget = room_info_map_container.mapper_container

            # Get room data from GMCP
            room_data = {}
            if hasattr(self.agent, "aardwolf_gmcp"):
                room_data = self.agent.aardwolf_gmcp.get_room_info()

            # Get room data from state manager as fallback
            if not room_data:
                room_data = {
                    'name': getattr(self.state_manager, 'room_name', 'Unknown'),
                    'num': getattr(self.state_manager, 'room_num', 0),
                    'exits': getattr(self.state_manager, 'exits', [])
                }

            # Update the map widget
            if hasattr(map_widget, 'update_room_data'):
                map_widget.update_room_data(room_data)
            elif hasattr(map_widget, 'update_map'):
                map_widget.update_map(room_data)

            logger.debug(f"Updated map widget with room: {room_data.get('name', 'Unknown')}")

        except Exception as e:
            logger.error(f"Error updating map widget: {e}", exc_info=True)
            # Widget might not be available yet, which is normal during startup
            if "not found" not in str(e).lower():
                logger.error(f"Map widget error details: {e}", exc_info=True)

    async def update_vitals_from_gmcp(self, gmcp_data: Dict[str, Any]) -> None:
        """Update vitals widgets directly from GMCP data.

        Args:
            gmcp_data: GMCP data containing vitals information
        """
        try:
            # Get comprehensive character data from the GMCP manager
            # This ensures we have both vitals and maxstats data
            char_data = {}
            if hasattr(self.app, 'agent') and self.app.agent and hasattr(self.app.agent, 'gmcp_manager'):
                char_data = self.app.agent.gmcp_manager.get_character_data()

            # If we have comprehensive data, use the combined section
            if char_data and "combined" in char_data:
                combined_data = char_data["combined"]

                # Update HP widget
                if "hp" in combined_data and "maxhp" in combined_data:
                    try:
                        hp_widget = self.app.query_one("#hp-widget", HPStaticWidget)
                        hp_widget.current_value = combined_data["hp"]
                        hp_widget.max_value = combined_data["maxhp"]
                        hp_widget.update_display()
                        logger.debug(f"Updated HP from GMCP: {combined_data['hp']}/{combined_data['maxhp']}")
                    except Exception as e:
                        logger.debug(f"HP widget not available: {e}")

                # Update MP widget (check for both mana and mp aliases)
                mana_current = combined_data.get("mana") or combined_data.get("mp")
                mana_max = combined_data.get("maxmana") or combined_data.get("maxmp")
                if mana_current is not None and mana_max is not None:
                    try:
                        mp_widget = self.app.query_one("#mp-widget", MPStaticWidget)
                        mp_widget.current_value = mana_current
                        mp_widget.max_value = mana_max
                        mp_widget.update_display()
                        logger.debug(f"Updated MP from GMCP: {mana_current}/{mana_max}")
                    except Exception as e:
                        logger.debug(f"MP widget not available: {e}")

                # Update MV widget (check for both moves and mv aliases)
                moves_current = combined_data.get("moves") or combined_data.get("mv")
                moves_max = combined_data.get("maxmoves") or combined_data.get("maxmv")
                if moves_current is not None and moves_max is not None:
                    try:
                        mv_widget = self.app.query_one("#mv-widget", MVStaticWidget)
                        mv_widget.current_value = moves_current
                        mv_widget.max_value = moves_max
                        mv_widget.update_display()
                        logger.debug(f"Updated MV from GMCP: {moves_current}/{moves_max}")
                    except Exception as e:
                        logger.debug(f"MV widget not available: {e}")

            else:
                # Fallback to raw vitals data if comprehensive data not available
                if "vitals" not in gmcp_data:
                    return

                vitals = gmcp_data["vitals"]

                # Update HP widget
                if "hp" in vitals and "maxhp" in vitals:
                    try:
                        hp_widget = self.app.query_one("#hp-widget", HPStaticWidget)
                        hp_widget.current_value = vitals["hp"]
                        hp_widget.max_value = vitals["maxhp"]
                        hp_widget.update_display()
                        logger.debug(f"Updated HP from GMCP (fallback): {vitals['hp']}/{vitals['maxhp']}")
                    except Exception as e:
                        logger.debug(f"HP widget not available: {e}")

                # Update MP widget (Aardwolf GMCP uses 'mana' not 'mp')
                if "mana" in vitals:
                    try:
                        mp_widget = self.app.query_one("#mp-widget", MPStaticWidget)
                        mp_widget.current_value = vitals["mana"]
                        # Get max mana from maxstats if available, otherwise use a default
                        max_mana = vitals.get("maxmana", vitals["mana"])  # fallback to current if max not available
                        mp_widget.max_value = max_mana
                        mp_widget.update_display()
                        logger.debug(f"Updated MP from GMCP (fallback): {vitals['mana']}/{max_mana}")
                    except Exception as e:
                        logger.debug(f"MP widget not available: {e}")

                # Update MV widget (Aardwolf GMCP uses 'moves' not 'mv')
                if "moves" in vitals:
                    try:
                        mv_widget = self.app.query_one("#mv-widget", MVStaticWidget)
                        mv_widget.current_value = vitals["moves"]
                        # Get max moves from maxstats if available, otherwise use a default
                        max_moves = vitals.get("maxmoves", vitals["moves"])  # fallback to current if max not available
                        mv_widget.max_value = max_moves
                        mv_widget.update_display()
                        logger.debug(f"Updated MV from GMCP (fallback): {vitals['moves']}/{max_moves}")
                    except Exception as e:
                        logger.debug(f"MV widget not available: {e}")

        except Exception as e:
            logger.error(f"Error updating vitals from GMCP: {e}", exc_info=True)

    async def refresh_status_widget(self) -> None:
        """Refresh the status widget with current data."""
        try:
            status_widget = self.app.query_one("#status-widget", StatusContainer)

            # Get current data from state manager
            room_name = getattr(self.state_manager, 'room_name', 'Unknown')
            room_num = getattr(self.state_manager, 'room_num', 0)
            exits = getattr(self.state_manager, 'exits', [])

            # Get character data from GMCP
            char_data = {}
            if hasattr(self.agent, "aardwolf_gmcp"):
                char_data = self.agent.aardwolf_gmcp.get_character_data()

            # Refresh the widget
            if hasattr(status_widget, 'refresh'):
                status_widget.refresh()
            else:
                status_widget.update_status(
                    room_name=room_name,
                    room_num=room_num,
                    exits=exits,
                    char_data=char_data
                )

            logger.debug("Refreshed status widget")

        except Exception as e:
            logger.error(f"Error refreshing status widget: {e}", exc_info=True)

    async def update_map_from_room_manager(self) -> None:
        """Update map widget with data from room manager."""
        try:
            # Get the parent container first, then access the mapper_container
            room_info_map_container = self.app.query_one("#room-info-map-container")
            if not hasattr(room_info_map_container, 'mapper_container') or room_info_map_container.mapper_container is None:
                logger.debug("Mapper container not yet available")
                return
            map_widget = room_info_map_container.mapper_container

            # Get room data from room manager
            room_data = {
                'name': self.agent.room_manager.current_room,
                'exits': self.agent.room_manager.current_exits.copy()
            }

            # Add room number if available
            if hasattr(self.state_manager, 'room_num'):
                room_data['num'] = self.state_manager.room_num

            # Update the map widget
            if hasattr(map_widget, 'update_room_data'):
                map_widget.update_room_data(room_data)
            elif hasattr(map_widget, 'update_map'):
                map_widget.update_map(room_data)

            logger.debug(f"Updated map from room manager: {room_data['name']}")

        except Exception as e:
            logger.error(f"Error updating map from room manager: {e}", exc_info=True)

    async def set_default_widget_values(self) -> None:
        """Initialize widgets without setting hardcoded default values."""
        try:
            # Initialize HP widget
            try:
                hp_widget = self.app.query_one("#hp-widget", HPStaticWidget)
                hp_widget.update_display()
                logger.debug("Initialized HP widget")
            except Exception:
                pass

            # Initialize MP widget
            try:
                mp_widget = self.app.query_one("#mp-widget", MPStaticWidget)
                mp_widget.update_display()
                logger.debug("Initialized MP widget")
            except Exception:
                pass

            # Initialize MV widget
            try:
                mv_widget = self.app.query_one("#mv-widget", MVStaticWidget)
                mv_widget.update_display()
                logger.debug("Initialized MV widget")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error initializing widget values: {e}", exc_info=True)

    def is_updating(self) -> bool:
        """Check if widgets are currently being updated.

        Returns:
            True if widgets are being updated, False otherwise
        """
        return self._updating_widgets

    def get_update_status(self) -> Dict[str, Any]:
        """Get current update status information.

        Returns:
            Dictionary containing update status
        """
        return {
            'updating': self._updating_widgets,
            'last_update': self._last_widget_update,
            'throttle': self._widget_update_throttle
        }

    async def cleanup(self) -> None:
        """Clean up resources and stop any ongoing operations.

        This method is called during application shutdown to ensure
        proper cleanup of the widget updater.
        """
        try:
            # Stop any ongoing updates
            self._updating_widgets = False

            # Reset state
            self._last_widget_update = 0

            logger.debug("WidgetUpdater cleanup completed")

        except Exception as e:
            logger.error(f"Error during WidgetUpdater cleanup: {e}", exc_info=True)
