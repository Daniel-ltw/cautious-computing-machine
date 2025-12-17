"""
Command log widget for the MUD agent.

This module contains the command log widget implementation for the MUD agent UI.
"""

import logging
import os
import subprocess
import sys

from textual.widgets import RichLog

logger = logging.getLogger(__name__)


class CommandLog(RichLog):
    """Log widget for displaying command history and server messages.

    This widget displays commands sent to the server and messages received from the server.
    It uses the event system to receive messages and commands.
    """

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Register event listeners if the app and agent are available
        if (
            hasattr(self, "app")
            and hasattr(self.app, "agent")
            and hasattr(self.app.agent, "client")
        ):
            client = self.app.agent.client
            if hasattr(client, "events"):
                # Register for command events
                client.events.on("command_sent", self._on_command_sent)
                client.events.on("command_error", self._on_command_error)

                # Register for data events
                client.events.on("data", self._on_server_data)

                # Register for connection events
                client.events.on("connected", self._on_connected)
                client.events.on("connection_error", self._on_connection_error)
                client.events.on("disconnected", self._on_disconnected)

                logger.debug("CommandLog registered for client events")
            else:
                logger.warning(
                    "Client does not have events property, cannot register for events"
                )
        else:
            logger.warning(
                "App, agent, or client not available, cannot register for events"
            )

    def _on_command_sent(self, command: str) -> None:
        """Handle command sent event.

        Args:
            command: The command that was sent
        """
        # Skip initialization commands
        if self._is_initialization_command(command):
            return

        self.write(f"[bold cyan]COMMAND: {command}[/bold cyan]")

    def _on_command_error(self, command: str, error: str) -> None:
        """Handle command error event.

        Args:
            command: The command that caused the error
            error: The error message
        """
        self.write(f"[bold red]ERROR sending command '{command}': {error}[/bold red]")

    def _on_server_data(self, data: str) -> None:
        """Handle server data event.

        Args:
            data: The data received from the server
        """
        # Skip GMCP-related messages
        if self._is_gmcp_message(data):
            return

        # Skip background commands and their responses
        if self._is_background_command(data):
            return

        # Skip empty messages
        if not data.strip():
            return

        # Skip messages that are just separators or formatting
        if (
            data.strip() in ["=", "-", "=====", "-----", "======", "------"]
            or data.strip().startswith("===")
            or data.strip().startswith("---")
        ):
            return

        # Skip messages that are just command prompts
        if data.strip() in [">", ">>", ">>>", "$ ", "# "]:
            return

        # Skip messages that are just newlines or whitespace
        if all(c.isspace() for c in data):
            return

        # Skip GMCP protocol messages
        if "GMCP" in data or "gmcp" in data or "protocols" in data:
            return

        # Skip only specific mapper-related messages
        mapper_commands = [
            "mapper set",
            "mapper status",
            "mapper find",
            "mapper goto",
            "mapper areas",
            "mapper shops",
            "mapper quest",
            "mapper automap",
            "mapper autolink",
            "mapper automappercolor",
        ]
        if any(cmd in data.lower() for cmd in mapper_commands):
            return

        # Only skip messages with JSON-like content if they match GMCP patterns
        if "{" in data and "}" in data and (":" in data or "," in data):
            # Check if this looks like GMCP data
            gmcp_terms = [
                "gmcp",
                "char",
                "room",
                "map",
                "vitals",
                "stats",
                "exits",
                "terrain",
                "coord",
                "num",
                "zone",
                "area",
                "name",
                "level",
                "hp",
                "mana",
                "moves",
                "maxhp",
                "maxmana",
                "maxmoves",
                "gold",
                "bank",
                "qp",
                "tp",
                "worth",
                "maxstats",
                "base",
                "status",
                "quest",
            ]
            if any(
                f'"{term}"' in data.lower() or f'"{term}":' in data.lower()
                for term in gmcp_terms
            ):
                return

        # Only skip messages with array-like content if they match GMCP patterns
        if "[" in data and "]" in data and (":" in data or "," in data):
            # Check if this looks like GMCP data
            gmcp_terms = [
                "gmcp",
                "char",
                "room",
                "map",
                "vitals",
                "stats",
                "exits",
                "terrain",
                "coord",
                "num",
                "zone",
                "area",
                "name",
                "level",
                "hp",
                "mana",
                "moves",
                "maxhp",
                "maxmana",
                "maxmoves",
                "gold",
                "bank",
                "qp",
                "tp",
                "worth",
                "maxstats",
                "base",
                "status",
                "quest",
            ]
            if any(
                f'"{term}"' in data.lower() or f'"{term}":' in data.lower()
                for term in gmcp_terms
            ):
                return

        # Check if this is an error message
        is_error = any(
            error_term in data.lower()
            for error_term in [
                "error:",
                "exception:",
                "failed:",
                "cannot:",
                "unable to:",
            ]
        )

        if is_error:
            # Format error messages with red text
            self.write(f"[bold red]{data}[/bold red]")
        else:
            # Format regular messages
            self.write(data)

        # Add a separator after significant messages
        if len(data.strip()) > 20:  # Only add separator for substantial messages
            self.write("=" * 80)

        # check for quest alert
        if "You may quest again" in data:
            self._play_alert_sound()

    def _play_alert_sound(self) -> None:
        """Play a system alert sound in a non-blocking way."""
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
            elif sys.platform == "win32":  # Windows
                # Use PowerShell to play a system sound
                subprocess.Popen(["powershell", "-c", "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync();"])
            elif sys.platform.startswith("linux"):  # Linux
                # Try common players
                try:
                    subprocess.Popen(["aplay", "/usr/share/sounds/alsa/Front_Center.wav"], stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    try:
                        subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        logger.warning("No suitable audio player (aplay/paplay) found for Linux alert.")
        except Exception as e:
            logger.error(f"Failed to play alert sound: {e}")

    def _on_connected(self, host: str, port: int) -> None:
        """Handle connected event.

        Args:
            host: The host that was connected to
            port: The port that was connected to
        """
        self.write(f"[bold green]Connected to {host}:{port}[/bold green]")

    def _on_connection_error(self, error: str) -> None:
        """Handle connection error event.

        Args:
            error: The error message
        """
        self.write(f"[bold red]Connection error: {error}[/bold red]")

    def _on_disconnected(self, *args) -> None:
        """Handle disconnected event.

        Args:
            *args: Any arguments passed with the event (ignored)
        """
        try:
            # Check if the app is still active before trying to write to the widget
            if self.is_mounted and hasattr(self, 'app') and self.app is not None:
                try:
                    # Test if the app context is still valid
                    _ = self.app.console
                    self.write("[bold yellow]Disconnected from server[/bold yellow]")
                except Exception:
                    # App context is gone, fall back to print
                    print("Disconnected from server")
            else:
                print("Disconnected from server")
        except Exception as e:
            # Handle any other unexpected errors silently during shutdown
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Disconnected event handler called during shutdown: {e}")

    def _is_gmcp_message(self, message: str) -> bool:
        """Check if a message is a GMCP message.

        Args:
            message: The message to check

        Returns:
            bool: True if the message is a GMCP message, False otherwise
        """
        # Check for common GMCP protocol messages
        gmcp_protocol_terms = [
            "GMCP Error",
            "Invalid GMCP tag",
            "GMCP Option",
            "GMCP Config",
            "protocols gmcp",
            "char.request",
            "room.request",
            "map.request",
            "char.quest.request",
            "protocols gmcp restart",
            "protocols gmcp Room",
            "protocols gmcp Char",
            "protocols gmcp Debug",
            "protocols gmcp rawcolor",
            "mapper set automap",
            "mapper set autolink",
            "mapper set automappercolor",
            "mapper status",
            "request gmcp",
            "request room",
            "request char",
            "request map",
            "request quest",
            "request mapper",
            "request room.map",
            "request mapper.map",
            "Char.Request",
            "Room.Request",
            "Char.Quest.Request",
            "Core.Supports.Set",
            "Char.Vitals",
            "Char.Stats",
            "Char.Status",
            "Char.Base",
            "Char.Worth",
            "Char.Maxstats",
            "Room.Info",
            "Room.Map",
            "Comm.Channel",
            "Group",
            "Debug",
            "mapper find",
            "mapper goto",
            "mapper areas",
            "mapper shops",
            "mapper quest",
            "toggle gmcp",
            "gmcp restart",
            "gmcp Room",
            "gmcp Char",
            "gmcp Debug",
            "gmcp rawcolor",
        ]

        if any(term.lower() in message.lower() for term in gmcp_protocol_terms):
            return True

        # Check for JSON-like structure
        if (message.startswith("{") and message.endswith("}")) or (
            message.startswith("[") and message.endswith("]")
        ):
            # Check for common GMCP terms
            gmcp_terms = [
                "gmcp",
                "char",
                "room",
                "map",
                "vitals",
                "stats",
                "exits",
                "terrain",
                "coord",
                "num",
                "zone",
                "area",
                "name",
                "level",
                "hp",
                "mana",
                "moves",
                "maxhp",
                "maxmana",
                "maxmoves",
                "gold",
                "bank",
                "qp",
                "tp",
                "worth",
                "maxstats",
                "base",
                "status",
                "quest",
            ]
            return any(term in message.lower() for term in gmcp_terms)

        # Check for GMCP error messages
        if "GMCP Error:" in message or "Invalid GMCP tag:" in message:
            return True

        # Check for GMCP command patterns
        if "COMMAND:" in message and any(
            term.lower() in message.lower()
            for term in [
                "protocols gmcp",
                "request gmcp",
                "request room",
                "request char",
                "request map",
                "request quest",
                "request mapper",
                "request room.map",
                "request mapper.map",
            ]
        ):
            return True

        return False

    def _is_initialization_command(self, command: str) -> bool:
        """Check if a command is an initialization command.

        Args:
            command: The command to check

        Returns:
            bool: True if the command is an initialization command, False otherwise
        """
        # List of exact initialization commands
        exact_initialization_commands = [
            # GMCP protocol commands
            "protocols gmcp",
            "request gmcp",
            "toggle gmcp",
            "gmcp restart",
            # Login-related commands
            os.environ.get("MUD_USERNAME", ""),
            os.environ.get("MUD_PASSWORD", ""),
            "login",
            "connect",
            "character",
            "profile",
        ]

        # List of initialization command prefixes
        prefix_initialization_commands = [
            # GMCP protocol commands
            "protocols gmcp",
            # Mapper commands
            "mapper set",
            "mapper status",
            "mapper find",
            "mapper goto",
            "mapper areas",
            "mapper shops",
            "mapper quest",
        ]

        # Check for exact matches first
        command_lower = command.lower().strip()
        if command_lower in [cmd.lower() for cmd in exact_initialization_commands]:
            return True

        # Then check for prefix matches
        return any(
            command_lower.startswith(pattern.lower())
            for pattern in prefix_initialization_commands
        )

    def _is_background_command(self, message: str) -> bool:
        """Check if a message is related to a background command.

        Args:
            message: The message to check

        Returns:
            bool: True if the message is related to a background command, False otherwise
        """
        # We no longer filter out user commands, but we still filter out responses
        # to background commands that are sent automatically by the system

        # User-initiated commands should never be considered background commands
        # We only filter out commands that are sent automatically by the system
        # If the message starts with "COMMAND:", it's a user command and should always be shown
        if message.startswith("COMMAND:"):
            # Check if it's an initialization command
            command = message[len("COMMAND:") :].strip()
            if self._is_initialization_command(command):
                return True

            # Don't filter out other user commands
            return False

        # Check for responses to background commands
        background_response_patterns = [
            # GMCP-related responses
            "GMCP Error",
            "Invalid GMCP tag",
            "GMCP Option",
            "GMCP Config",
            "protocols gmcp",
            "char.request",
            "room.request",
            "map.request",
            "char.quest.request",
            "protocols gmcp restart",
            "protocols gmcp Room",
            "protocols gmcp Char",
            "protocols gmcp Debug",
            "protocols gmcp rawcolor",
            "mapper set automap",
            "mapper set autolink",
            "mapper set automappercolor",
            "mapper status",
            "GMCP",
            "gmcp",
            "Char.",
            "Room.",
            "Map.",
            # Background initialization messages
            "Initializing",
            "Initialization",
            "Loading",
            "Updating",
            # GMCP error messages
            "GMCP Error:",
            "Invalid GMCP tag:",
            "Failed to parse GMCP",
        ]

        # Check if any of the background response patterns are in the message
        for pattern in background_response_patterns:
            if pattern in message:
                return True

        # Check for JSON-like responses (common in GMCP and quest info)
        if (message.startswith("{") and message.endswith("}")) or (
            message.startswith("[") and message.endswith("]")
        ):
            return True

        return False

    # Legacy methods for backward compatibility

    def add_command(self, command: str) -> None:
        """Add a command to the log.

        This method is kept for backward compatibility.

        Args:
            command: The command to add
        """
        self._on_command_sent(command)

    def add_server_message(self, message: str) -> None:
        """Add a raw server message to the log.

        This method is kept for backward compatibility.

        Args:
            message: The raw message from the server
        """
        self._on_server_data(message)

    def add_response(self, response: str) -> None:
        """Add a response to the log.

        This method is kept for backward compatibility.

        Args:
            response: The response to add
        """
        self._on_server_data(response)
