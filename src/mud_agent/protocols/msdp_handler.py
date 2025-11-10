"""
Handler for MUD Server Data Protocol (MSDP).
"""

import json
import logging
from typing import Any

# Constants for MSDP protocol
MSDP_VAL = 0x01  # MSDP value indicator
MSDP_VAR = 0x02  # MSDP variable indicator

logger = logging.getLogger(__name__)


class MSDPHandler:
    """Handler for MUD Server Data Protocol (MSDP)."""

    def __init__(self):
        self.enabled = True
        self.data: dict[str, Any] = {}
        logger.debug("MSDP handler initialized")

    def handle_message(self, data: bytes) -> tuple[str | None, Any | None]:
        """Handle an MSDP message.

        Args:
            data: Raw MSDP data bytes

        Returns:
            tuple: (module, data) if successful, (None, None) if there was an error
        """
        try:
            # Basic MSDP parsing - just store key/value pairs
            i = 0
            last_var_name = None
            last_value = None

            while i < len(data):
                # Get variable name
                var_start = i
                while i < len(data) and data[i] != MSDP_VAL:
                    i += 1
                if i >= len(data):
                    break
                var_name = data[var_start:i].decode("utf-8")
                i += 1  # Skip MSDP_VAL

                # Get value
                val_start = i
                while i < len(data) and data[i] != MSDP_VAR:
                    i += 1
                if i > val_start:
                    value = data[val_start:i].decode("utf-8")
                    try:
                        # Try to parse as JSON
                        parsed_value = json.loads(value)
                        self.data[var_name] = parsed_value
                    except json.JSONDecodeError:
                        # Store as string if not valid JSON
                        self.data[var_name] = value
                        parsed_value = value

                    # Store the last variable and value for return
                    last_var_name = var_name
                    last_value = parsed_value

                i += 1  # Skip MSDP_VAR

            logger.debug("MSDP message handled")

            # Return the last variable name and value processed
            # This is a simplification - in a real implementation, we might want to return all variables
            return last_var_name, last_value

        except Exception as e:
            logger.error(f"Error handling MSDP message: {e}", exc_info=True)
            return None, None
