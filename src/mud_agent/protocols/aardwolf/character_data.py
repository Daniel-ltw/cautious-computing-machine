"""
Character data processor for Aardwolf GMCP.

This module handles processing of character-related GMCP data.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CharacterDataProcessor:
    """Processes character-related GMCP data."""

    def __init__(self, gmcp_manager):
        """Initialize the character data processor.

        Args:
            gmcp_manager: The parent GMCP manager
        """
        self.gmcp_manager = gmcp_manager
        self.logger = logger

    def process_data(self, char_data: dict[str, Any]) -> dict[str, Any]:
        """Process character data from GMCP.

        Args:
            char_data: The character data from GMCP

        Returns:
            dict: Processed character data
        """
        if not char_data:
            self.logger.debug("No character data to process")
            return {}

        # Get comprehensive character data
        comprehensive_data = self.get_character_data()
        self.logger.info(
            f"Processed comprehensive character data with sections: {list(comprehensive_data.keys())}"
        )

        # Log the vitals with their aliases for debugging
        if "combined" in comprehensive_data:
            combined = comprehensive_data["combined"]
            vitals_keys = [
                "hp",
                "maxhp",
                "mana",
                "mp",
                "maxmana",
                "maxmp",
                "moves",
                "mv",
                "maxmoves",
                "maxmv",
            ]
            vitals_values = {
                k: combined.get(k, "N/A") for k in vitals_keys if k in combined
            }
            self.logger.debug(f"Combined vitals data with aliases: {vitals_values}")

        # Log some key data for debugging
        if "vitals" in comprehensive_data:
            vitals = comprehensive_data["vitals"]
            self.logger.info(
                f"GMCP Vitals: HP={vitals.get('hp', 'N/A')}/{vitals.get('maxhp', 'N/A')}, MP={vitals.get('mana', 'N/A')}/{vitals.get('maxmana', 'N/A')}, MV={vitals.get('moves', 'N/A')}/{vitals.get('maxmoves', 'N/A')}"
            )

        if "combined" in comprehensive_data:
            combined = comprehensive_data["combined"]
            self.logger.info(
                f"GMCP Combined: Name={combined.get('name', 'N/A')}, Level={combined.get('level', 'N/A')}, Class={combined.get('class', 'N/A')}"
            )

        return comprehensive_data

    def get_character_data(self) -> dict[str, Any]:
        """Get comprehensive character data from GMCP including vitals, stats, and maxstats.

        Returns:
            dict: Combined character data or empty dict if not available
        """
        char_data = self.gmcp_manager.char_data
        if not char_data:
            self.logger.debug("No char data available in GMCP")
            return {}

        # Initialize result dictionary with separate sections
        result = {
            "vitals": {},
            "stats": {},
            "maxstats": {},
            "needs": {},  # For hunger and thirst
            "combined": {},  # For easy access to all data in a flat structure
        }

        # Process vitals data
        if "vitals" in char_data:
            vitals = char_data["vitals"]
            # Store the raw vitals data
            result["vitals"] = vitals.copy()

            # Add vitals to the combined section
            for key, value in vitals.items():
                result["combined"][key] = value

            # Add aliases for common vitals to ensure widgets can find them
            if "mana" in vitals:
                result["combined"]["mp"] = vitals["mana"]
            if "moves" in vitals:
                result["combined"]["mv"] = vitals["moves"]

            # Extract max values from vitals to maxstats
            if "maxhp" in vitals:
                result["maxstats"]["maxhp"] = vitals["maxhp"]
                result["combined"]["maxhp"] = vitals["maxhp"]
            if "maxmana" in vitals:
                result["maxstats"]["maxmana"] = vitals["maxmana"]
                result["combined"]["maxmana"] = vitals["maxmana"]
                # Add alias for maxmp
                result["combined"]["maxmp"] = vitals["maxmana"]
            if "maxmoves" in vitals:
                result["maxstats"]["maxmoves"] = vitals["maxmoves"]
                result["combined"]["maxmoves"] = vitals["maxmoves"]
                # Add alias for maxmv
                result["combined"]["maxmv"] = vitals["maxmoves"]
        else:
            self.logger.debug("No 'vitals' module found in char_data")

        # Process stats data
        stats = {}

        # Check for stats in the standard location
        if "stats" in char_data:
            stats.update(char_data["stats"])
            self.logger.debug(f"Got stats from char.stats: {char_data['stats']}")

            # Look for keys that start with "max" and add to maxstats
            for key, value in char_data["stats"].items():
                if key.startswith("max"):
                    result["maxstats"][key] = value
                    result["combined"][key] = value

        # Check for stats in the base char data (some MUDs put them here)
        for stat_name in ["str", "int", "wis", "dex", "con", "luck", "hr", "dr"]:
            if stat_name in char_data:
                stats[stat_name] = char_data[stat_name]
                self.logger.debug(
                    f"Got {stat_name} from base char data: {char_data[stat_name]}"
                )

        # Check for stats in the status section
        if "status" in char_data:
            status_data = char_data["status"]
            if isinstance(status_data, dict):
                for stat_name in [
                    "str",
                    "int",
                    "wis",
                    "dex",
                    "con",
                    "luck",
                    "hr",
                    "dr",
                ]:
                    if stat_name in status_data:
                        stats[stat_name] = status_data[stat_name]
                        self.logger.debug(
                            f"Got {stat_name} from status data: {status_data[stat_name]}"
                        )

        # If we still don't have stats, try to extract them from vitals
        if not stats and "vitals" in char_data:
            vitals = char_data["vitals"]
            if "stats" in vitals:
                stats.update(vitals["stats"])
                self.logger.debug(f"Got stats from vitals.stats: {vitals['stats']}")

        # For Aardwolf, try to extract stats from the base data
        if "base" in char_data:
            base_data = char_data["base"]
            self.logger.debug(f"Found base data: {base_data}")

            # Extract stats from base data
            if "stats" in base_data:
                base_stats = base_data["stats"]
                self.logger.debug(f"Found stats in base data: {base_stats}")
                stats.update(base_stats)

            # Also check for individual stats in base data
            for stat_name in ["str", "int", "wis", "dex", "con", "luck", "hr", "dr"]:
                if stat_name in base_data:
                    stats[stat_name] = base_data[stat_name]
                    self.logger.debug(
                        f"Got {stat_name} from base data: {base_data[stat_name]}"
                    )

        # Store the stats in the result
        result["stats"] = stats

        # Add stats to the combined section
        for key, value in stats.items():
            result["combined"][key] = value

        # Process maxstats data
        maxstats = {}

        # First check for dedicated maxstats module
        if "maxstats" in char_data:
            maxstats = char_data["maxstats"].copy()
            self.logger.debug(
                f"Got maxstats data from GMCP maxstats module: {maxstats}"
            )
        else:
            self.logger.debug("No 'maxstats' module found in char_data")

        # Also look for keys that might contain max values but don't start with "max"
        for key in ["str", "int", "wis", "dex", "con", "luck"]:
            max_key = f"max{key}"
            if max_key not in maxstats and key in stats:
                # If we don't have a max value for this stat, use the current value as max
                maxstats[max_key] = stats[key]
                self.logger.debug(f"Using current value as max for {key}: {stats[key]}")

        # Store the maxstats in the result
        result["maxstats"] = maxstats

        # Add maxstats to the combined section
        for key, value in maxstats.items():
            result["combined"][key] = value

        # Process combined format for stats (e.g., "21/18")
        for key in list(stats.keys()):
            value = stats[key]
            if isinstance(value, str) and "/" in value:
                parts = value.split("/")
                if len(parts) == 2:
                    try:
                        current = int(parts[0])
                        maximum = int(parts[1])

                        # Update the stats with the current value
                        stats[key] = current
                        result["stats"][key] = current
                        result["combined"][key] = current

                        # Add the max value to maxstats
                        max_key = f"max{key}"
                        maxstats[max_key] = maximum
                        result["maxstats"][max_key] = maximum
                        result["combined"][max_key] = maximum

                        self.logger.debug(
                            f"Processed combined format for {key}: current={current}, max={maximum}"
                        )
                    except ValueError:
                        # Not valid numbers, keep as is
                        pass

        # Add character base info to combined data
        if "base" in char_data:
            base = char_data["base"]
            for key in [
                "name",
                "level",
                "race",
                "class",
                "subclass",
                "clan",
                "pretitle",
                "alignment",
                "remorts",
                "tier",
            ]:
                if key in base:
                    result["combined"][key] = base[key]

        # Process hunger and thirst data if available
        # In Aardwolf, hunger and thirst are often in the status module
        needs = {}
        if "status" in char_data:
            status_data = char_data["status"]
            # Check for hunger
            if isinstance(status_data, dict) and "hunger" in status_data:
                hunger_value = status_data["hunger"]
                # Convert to a 0-100 scale if needed
                if isinstance(hunger_value, (int, float)):
                    needs["hunger"] = {
                        "current": hunger_value,
                        "maximum": 100,  # Assuming max is 100
                        "text": self._get_hunger_text(hunger_value),
                    }
                elif isinstance(hunger_value, str):
                    needs["hunger"] = {
                        "current": self._get_hunger_value(hunger_value),
                        "maximum": 100,
                        "text": hunger_value,
                    }
                self.logger.debug(
                    f"Got hunger data from status module: {needs.get('hunger')}"
                )

            # Check for thirst
            if isinstance(status_data, dict) and "thirst" in status_data:
                thirst_value = status_data["thirst"]
                # Convert to a 0-100 scale if needed
                if isinstance(thirst_value, (int, float)):
                    needs["thirst"] = {
                        "current": thirst_value,
                        "maximum": 100,  # Assuming max is 100
                        "text": self._get_thirst_text(thirst_value),
                    }
                elif isinstance(thirst_value, str):
                    needs["thirst"] = {
                        "current": self._get_thirst_value(thirst_value),
                        "maximum": 100,
                        "text": thirst_value,
                    }
                self.logger.debug(
                    f"Got thirst data from status module: {needs.get('thirst')}"
                )

        # Add needs to the result
        result["needs"] = needs
        # Also add to combined data
        for key, value in needs.items():
            result["combined"][key] = value

        # Add status effects to combined data
        if "status" in char_data:
            status_data = char_data["status"]
            if isinstance(status_data, list):
                result["combined"]["status"] = status_data
            elif isinstance(status_data, dict):
                result["combined"]["status"] = [
                    status for status, active in status_data.items() if active
                ]

        # Add worth data to combined data
        if "worth" in char_data:
            worth = char_data["worth"]
            for key, value in worth.items():
                result["combined"][key] = value

        return result

    def _get_hunger_text(self, value: int) -> str:
        """Convert a hunger value to a text description.

        Args:
            value: The hunger value (0-100)

        Returns:
            str: Text description of hunger level
        """
        if value > 90:
            return "Full"
        elif value > 70:
            return "Satiated"
        elif value > 30:
            return "Hungry"
        else:
            return "Starving"

    def _get_thirst_text(self, value: int) -> str:
        """Convert a thirst value to a text description.

        Args:
            value: The thirst value (0-100)

        Returns:
            str: Text description of thirst level
        """
        if value > 90:
            return "Quenched"
        elif value > 70:
            return "Not Thirsty"
        elif value > 30:
            return "Thirsty"
        else:
            return "Parched"

    def _get_hunger_value(self, text: str) -> int:
        """Convert a hunger text description to a value.

        Args:
            text: The hunger text description

        Returns:
            int: Hunger value (0-100)
        """
        text = text.lower()
        if "full" in text:
            return 95
        elif "satiated" in text:
            return 80
        elif "hungry" in text:
            return 50
        elif "starving" in text:
            return 15
        else:
            return 50  # Default to middle value

    def _get_thirst_value(self, text: str) -> int:
        """Convert a thirst text description to a value.

        Args:
            text: The thirst text description

        Returns:
            int: Thirst value (0-100)
        """
        text = text.lower()
        if "quenched" in text:
            return 95
        elif "not thirsty" in text:
            return 80
        elif "thirsty" in text:
            return 50
        elif "parched" in text:
            return 15
        else:
            return 50  # Default to middle value

    def get_all_character_data(self) -> dict[str, Any]:
        """Get all character data in a single call.

        Returns:
            dict: All character data including vitals, stats, maxstats, and more
        """
        # Initialize with default values to prevent NoneType errors
        result = {
            "vitals": {},
            "stats": {},
            "maxstats": {},
            "worth": {},
            "status": {},
            "combined": {},
        }

        # Get the comprehensive character data
        char_data = self.get_character_data()

        # Update the result with the character data
        result.update(char_data)

        # Add worth data if available
        if "worth" in self.gmcp_manager.char_data:
            result["worth"] = self.gmcp_manager.char_data["worth"]
            # Also add to combined data
            for key, value in self.gmcp_manager.char_data["worth"].items():
                result["combined"][key] = value

        # Add status data if available
        if "status" in self.gmcp_manager.char_data:
            status_data = self.gmcp_manager.char_data["status"]
            if isinstance(status_data, dict):
                result["status"] = {key: value for key, value in status_data.items()}
            else:
                result["status"] = status_data
            # Also add to combined data
            result["combined"]["status"] = status_data

        return result
