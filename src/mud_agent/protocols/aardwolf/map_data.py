"""
Map data processor for Aardwolf GMCP.

This module handles processing of map-related GMCP data.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MapDataProcessor:
    """Processes map-related GMCP data."""

    def __init__(self, gmcp_manager):
        """Initialize the map data processor.

        Args:
            gmcp_manager: The parent GMCP manager
        """
        self.gmcp_manager = gmcp_manager
        self.logger = logger

    def process_data(self, map_data: Any) -> dict[str, Any]:
        """Process map data from GMCP.

        Args:
            map_data: The map data from GMCP

        Returns:
            dict: Processed map data
        """
        if not map_data:
            self.logger.debug("No map data to process")
            return {}

        # Log the raw map data for debugging
        if isinstance(map_data, dict):
            self.logger.debug(f"Map data keys: {list(map_data.keys())}")
        elif isinstance(map_data, str):
            self.logger.debug(f"Map data is a string, length: {len(map_data)}")
            if len(map_data) > 0:
                sample = map_data[: min(100, len(map_data))]
                self.logger.debug(f"Map sample: {sample}")

        # Extract map data
        map_str = self.get_map_data()
        return {"map": map_str}

    def get_map_data(self) -> str:
        """Get map data from GMCP.

        Returns:
            str: Map data or empty string if not available
        """
        map_data = self.gmcp_manager.map_data

        # Check if map data exists
        if not map_data:
            self.logger.debug("No GMCP map data available")
            return ""

        # Try to extract map data in different formats
        if isinstance(map_data, dict) and "map" in map_data:
            map_str = map_data["map"]
            self.logger.debug(f"Found map in map_data['map'], length: {len(map_str)}")
            # Log a sample of the map for debugging
            if len(map_str) > 0:
                sample = map_str[: min(100, len(map_str))]
                self.logger.debug(f"Map sample: {sample}")
            return map_str
        elif isinstance(map_data, dict) and "ascii" in map_data:
            map_str = map_data["ascii"]
            self.logger.debug(f"Found map in map_data['ascii'], length: {len(map_str)}")
            # Log a sample of the map for debugging
            if len(map_str) > 0:
                sample = map_str[: min(100, len(map_str))]
                self.logger.debug(f"Map sample: {sample}")
            return map_str
        elif isinstance(map_data, str):
            # Some MUDs might send the map directly as a string
            self.logger.debug(f"Map data is a string, length: {len(map_data)}")
            # Log a sample of the map for debugging
            if len(map_data) > 0:
                sample = map_data[: min(100, len(map_data))]
                self.logger.debug(f"Map sample: {sample}")
            return map_data

        # Check if we have room.info with a map
        room_data = self.gmcp_manager.room_data
        if "info" in room_data and isinstance(room_data["info"], dict):
            room_info = room_data["info"]
            if "map" in room_info:
                map_str = room_info["map"]
                self.logger.debug(
                    f"Found map in room_info['map'], length: {len(map_str)}"
                )
                return map_str

        # If we get here, we couldn't find a map in the expected formats
        self.logger.warning(f"Could not extract map from GMCP data: {map_data}")
        return ""

    async def request_map_for_room(self) -> None:
        """Map data is not available via GMCP in Aardwolf.

        Room data will be sent automatically by the server.
        """
        try:
            self.logger.info("Map data is not available via GMCP in Aardwolf")
        except Exception as e:
            self.logger.error(
                f"Error in map request handler: {e}", exc_info=True
            )

    async def request_map_data(self) -> None:
        """Map data is not available via GMCP in Aardwolf.

        This method is kept for compatibility but will log a warning.
        """
        try:
            self.logger.info("Map data is not available via GMCP in Aardwolf")

            # Wait a moment for data to be processed
            await asyncio.sleep(0.5)

            # Update from GMCP to get the latest data
            self.gmcp_manager.update_from_gmcp()

            # Debug log the GMCP data structure
            await self.gmcp_manager.debug_log_gmcp_data()

        except Exception as e:
            self.logger.error(f"Error requesting map data: {e}", exc_info=True)
