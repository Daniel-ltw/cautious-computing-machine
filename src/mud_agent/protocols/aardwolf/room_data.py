"""
Room data processor for Aardwolf GMCP.

This module handles processing of room-related GMCP data.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RoomDataProcessor:
    """Processes room-related GMCP data."""

    def __init__(self, gmcp_manager):
        """Initialize the room data processor.

        Args:
            gmcp_manager: The parent GMCP manager
        """
        self.gmcp_manager = gmcp_manager
        self.logger = logger

    def process_data(self, room_data: dict[str, Any]) -> dict[str, Any]:
        """Process room data from GMCP.

        Args:
            room_data: The room data from GMCP

        Returns:
            dict: Processed room data
        """
        if not room_data:
            self.logger.debug("No room data to process")
            return {}

        # Log detailed room data for debugging
        if "info" in room_data:
            info = room_data["info"]
            self.logger.debug(
                f"GMCP room info keys: {list(info.keys()) if isinstance(info, dict) else 'not a dict'}"
            )

            # Log specific fields for debugging
            if isinstance(info, dict):
                if "name" in info:
                    self.logger.debug(f"GMCP room name: {info['name']}")
                else:
                    self.logger.debug("No room name in GMCP room info")

                if "zone" in info:
                    self.logger.debug(f"GMCP zone/area name: {info['zone']}")
                else:
                    self.logger.debug("No zone/area name in GMCP room info")

                if "terrain" in info:
                    self.logger.debug(f"GMCP terrain: {info['terrain']}")
                else:
                    self.logger.debug("No terrain in GMCP room info")

                if "coord" in info:
                    self.logger.debug(f"GMCP coordinates: {info['coord']}")
                else:
                    self.logger.debug("No coordinates in GMCP room info")

                if "num" in info:
                    self.logger.debug(f"GMCP room number: {info['num']}")
                else:
                    self.logger.debug("No room number in GMCP room info")

                if "details" in info:
                    self.logger.debug(f"GMCP room details: {info['details']}")
                else:
                    self.logger.debug("No room details in GMCP room info")
        else:
            self.logger.debug("No 'info' key in GMCP room data")

        # Get room info
        room_info = self.get_room_info()
        return room_info

    def get_room_info(self) -> dict[str, Any]:
        """Get room information from GMCP data.

        Returns:
            dict: Room information or empty dict if not available
        """
        room_data = self.gmcp_manager.room_data
        room_info = {}

        if "info" in room_data:
            info = room_data["info"]
            room_info["name"] = info.get("name", "Unknown")
            room_info["num"] = info.get("num", 0)
            room_info["zone"] = info.get("zone", "Unknown")
            room_info["area"] = info.get(
                "zone", "Unknown"
            )  # For backward compatibility
            room_info["exits"] = info.get("exits", {})
            room_info["terrain"] = info.get("terrain", "Unknown")
            room_info["mapterrain"] = info.get("mapterrain", "")
            room_info["outside"] = info.get("outside", 0)
            room_info["details"] = info.get("details", "")
            room_info["racebonus"] = info.get("racebonus", 0)

            # Handle coordinates - in Aardwolf they're in the "coord" field (singular)
            if "coord" in info and isinstance(info["coord"], dict):
                room_info["coord"] = info["coord"]
                # Also store as "coords" for backward compatibility
                room_info["coords"] = info["coord"]
                # Also store as "coordinates" for newer code
                room_info["coordinates"] = info["coord"]
            else:
                room_info["coord"] = {}
                room_info["coords"] = {}
                room_info["coordinates"] = {}

        return room_info

    def get_exits(self) -> list[str]:
        """Get available exits from the current room.

        Returns:
            list: List of exit directions
        """
        room_info = self.get_room_info()
        exits = room_info.get("exits", {})

        if isinstance(exits, dict):
            return list(exits.keys())
        elif isinstance(exits, list):
            return exits
        else:
            return []

    def get_room_name(self) -> str:
        """Get the name of the current room.

        Returns:
            str: Room name or "Unknown" if not available
        """
        room_info = self.get_room_info()
        return room_info.get("name", "Unknown")

    def get_area_name(self) -> str:
        """Get the name of the current area.

        Returns:
            str: Area name or "Unknown" if not available
        """
        room_info = self.get_room_info()
        return room_info.get("area", "Unknown")

    def get_room_coords(self) -> tuple[int, int, int]:
        """Get the coordinates of the current room.

        Returns:
            tuple: (x, y, z) coordinates or (0, 0, 0) if not available
        """
        room_info = self.get_room_info()
        coords = room_info.get("coords", {})

        if isinstance(coords, dict):
            return (coords.get("x", 0), coords.get("y", 0), coords.get("z", 0))
        else:
            return (0, 0, 0)
