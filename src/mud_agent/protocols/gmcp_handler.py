"""
Handler for Generic MUD Communication Protocol (GMCP).

This module provides a handler for the Generic MUD Communication Protocol (GMCP),
which is used by many MUDs to provide structured data to clients.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class GMCPHandler:
    """Handler for Generic MUD Communication Protocol (GMCP).

    This class handles GMCP messages from the server, stores the data,
    and provides methods to access it. It also supports callbacks for
    when GMCP data is received or updated.

    Attributes:
        enabled: Whether GMCP is enabled
        data: Dictionary of GMCP data, organized by module
        callbacks: List of callback functions for all GMCP messages
        module_callbacks: Dictionary of callback functions for specific modules
        supported_modules: Set of GMCP modules supported by the server
    """

    def __init__(self):
        """Initialize the GMCP handler."""
        self.enabled = True
        self.data: dict[str, Any] = {}
        self.callbacks: list[Callable[[str, Any], None]] = []
        self.module_callbacks: dict[str, list[Callable[[str, Any], None]]] = {}
        self.supported_modules: set[str] = set()
        logger.debug("GMCP handler initialized")

    def register_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback for all GMCP messages.

        Args:
            callback: Function to call when any GMCP message is received.
                     The function should accept module (str) and data (Any) parameters.
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            logger.debug(f"Registered GMCP callback: {callback.__name__}")

    def register_module_callback(
        self, module: str, callback: Callable[[str, Any], None]
    ) -> None:
        """Register a callback for a specific GMCP module.

        Args:
            module: The module name (e.g. 'char.vitals')
            callback: Function to call when a message for this module is received.
                     The function should accept module (str) and data (Any) parameters.
        """
        if module not in self.module_callbacks:
            self.module_callbacks[module] = []

        if callback not in self.module_callbacks[module]:
            self.module_callbacks[module].append(callback)
            logger.debug(
                f"Registered GMCP callback for module {module}: {callback.__name__}"
            )

    def unregister_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Unregister a callback.

        Args:
            callback: The callback to unregister
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Unregistered GMCP callback: {callback.__name__}")

    def unregister_module_callback(
        self, module: str, callback: Callable[[str, Any], None]
    ) -> None:
        """Unregister a module-specific callback.

        Args:
            module: The module name
            callback: The callback to unregister
        """
        if (
            module in self.module_callbacks
            and callback in self.module_callbacks[module]
        ):
            self.module_callbacks[module].remove(callback)
            logger.debug(
                f"Unregistered GMCP callback for module {module}: {callback.__name__}"
            )

    def handle_message(self, message: str) -> tuple[str | None, Any | None]:
        """Handle a GMCP message.

        Args:
            message: The GMCP message string

        Returns:
            tuple: (module, data) if successful, (None, None) if there was an error
        """
        try:
            # Skip known problematic GMCP messages
            problematic_prefixes = [
                "char.quest.request",
                "comm.quest",
                "char.quest.request (data:[])",
                "char.quest.request (data:{})",
            ]

            if any(
                message.lower().startswith(prefix.lower())
                for prefix in problematic_prefixes
            ):
                logger.debug(
                    f"Skipping known problematic GMCP message: {message[:50]}..."
                )
                return None, None

            # Also skip if the message contains invalid JSON
            if " " in message:
                try:
                    # Try to parse the JSON part
                    space_idx = message.find(" ")
                    json.loads(message[space_idx + 1 :])
                except json.JSONDecodeError:
                    logger.warning(
                        f"Skipping GMCP message with invalid JSON: {message[:50]}..."
                    )
                    return None, None

            # Split module and data
            space_idx = message.find(" ")
            if space_idx == -1:
                module = message
                data = {}
            else:
                module = message[:space_idx]
                data = json.loads(message[space_idx + 1 :])

            # Check if this is a new module
            if module not in self.supported_modules:
                self.supported_modules.add(module)

            # Store previous data for change detection
            old_data = self.get_module_data(module)

            # Store in module data
            module_parts = module.split(".")
            current_dict = self.data
            for part in module_parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]

            # Update the data
            current_dict[module_parts[-1]] = data

            # Call callbacks if data changed
            if old_data != data:
                self._call_callbacks(module, data)

            logger.debug(f"GMCP message handled: {module}")

            # Return the module and data
            return module, data

        except json.JSONDecodeError as e:
            # For JSON decode errors, log at debug level since these are often expected
            # for certain GMCP messages like char.quest.request
            logger.debug(f"Invalid GMCP JSON data in message '{message[:50]}...': {e}")
            return None, None
        except Exception as e:
            logger.error(
                f"Error handling GMCP message '{message[:50]}...': {e}", exc_info=True
            )
            return None, None

    def _call_callbacks(self, module: str, data: Any) -> None:
        """Call registered callbacks for a GMCP message.

        Args:
            module: The GMCP module name
            data: The GMCP data
        """
        # Call general callbacks
        for callback in self.callbacks:
            try:
                callback(module, data)
            except Exception as e:
                logger.error(
                    f"Error in GMCP callback {callback.__name__}: {e}", exc_info=True
                )

        # Call module-specific callbacks
        if module in self.module_callbacks:
            for callback in self.module_callbacks[module]:
                try:
                    callback(module, data)
                except Exception as e:
                    logger.error(
                        f"Error in GMCP module callback {callback.__name__} for {module}: {e}",
                        exc_info=True,
                    )

        # Call parent module callbacks (e.g. 'char' for 'char.vitals')
        parent_module = ".".join(module.split(".")[:-1])
        if parent_module and parent_module in self.module_callbacks:
            for callback in self.module_callbacks[parent_module]:
                try:
                    callback(module, data)
                except Exception as e:
                    logger.error(
                        f"Error in GMCP parent module callback {callback.__name__} for {parent_module}: {e}",
                        exc_info=True,
                    )

    def get_module_data(self, module: str) -> dict[str, Any] | None:
        """Get data for a specific GMCP module.

        Args:
            module: The module name (e.g. 'char.base' or 'room')

        Returns:
            The module data if available, None otherwise
        """
        try:
            current_dict = self.data
            for part in module.split("."):
                current_dict = current_dict[part]
            return current_dict
        except KeyError:
            return None

    def get_supported_modules(self) -> set[str]:
        """Get the set of GMCP modules supported by the server.

        Returns:
            Set of supported module names
        """
        return self.supported_modules

    def is_module_supported(self, module: str) -> bool:
        """Check if a GMCP module is supported by the server.

        Args:
            module: The module name to check

        Returns:
            True if the module is supported, False otherwise
        """
        return module in self.supported_modules

    def clear_data(self) -> None:
        """Clear all stored GMCP data."""
        self.data = {}
        logger.debug("Cleared all GMCP data")

    # Convenience methods for common GMCP data

    def get_char_data(self) -> dict[str, Any] | None:
        """Get character data from GMCP.

        Returns:
            Character data if available, None otherwise
        """
        return self.get_module_data("char")

    def get_room_data(self) -> dict[str, Any] | None:
        """Get room data from GMCP.

        Returns:
            Room data if available, None otherwise
        """
        return self.get_module_data("room")

    def get_vitals(self) -> dict[str, Any] | None:
        """Get character vitals from GMCP.

        Returns:
            Character vitals if available, None otherwise
        """
        return self.get_module_data("char.vitals")

    def get_stats(self) -> dict[str, Any] | None:
        """Get character stats from GMCP.

        Returns:
            Character stats if available, None otherwise
        """
        return self.get_module_data("char.stats")

    def get_room_info(self) -> dict[str, Any] | None:
        """Get room information from GMCP.

        Returns:
            Room information if available, None otherwise
        """
        return self.get_module_data("room.info")
