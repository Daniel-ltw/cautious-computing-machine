"""
Tool for interacting with the MUD client.
"""

import asyncio
import logging
import re
from unittest.mock import AsyncMock

from smolagents import Tool

from ..mud_client import MudClient

logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_LENGTH = 10  # Minimum length for valid text responses


class MUDClientTool(Tool):
    """Tool for interacting with the MUD client."""

    name = "mud_client"
    description = "Interact with the MUD client to send commands and receive responses"
    output_type = "string"  # Output will be a string containing the response

    def __init__(self, client: MudClient | None = None):
        """Initialize the MUD client tool.

        Args:
            client: Optional MUD client instance. If not provided, a new one will be created.
        """
        self.client = client or MudClient()
        self.inputs = {
            "command": {
                "type": "string",
                "description": "The command to send to the MUD server",
            },
            "is_user_command": {
                "type": "boolean",
                "description": "Whether this command was initiated by the user (high priority)",
                "default": False,
                "nullable": True,
            },
        }
        # Store the last room description and exits for get_room_description and get_exits
        self.last_room_description = "Unknown room"
        self.last_exits = "No visible exits"
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        super().__init__()

    async def connect(self, host: str, port: int) -> str:
        """Connect to the MUD server.

        Args:
            host: The hostname or IP address of the MUD server
            port: The port number of the MUD server

        Returns:
            str: Connection status message
        """
        try:
            await self.client.connect(host, port)
            return f"Connected to {host}:{port}"
        except Exception as e:
            logger.error(f"Error connecting to MUD server: {e}", exc_info=True)
            return f"Error: {e!s}"

    async def login(self, username: str, password: str) -> bool:
        """Login to the MUD server.

        Args:
            username: The username to login with
            password: The password to login with

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            return await self.client.login(username, password)
        except Exception as e:
            logger.error(f"Error logging in to MUD server: {e}", exc_info=True)
            return False

    async def forward(self, command: str, is_user_command: bool = False) -> str:
        """Forwards a command to the MUD server, handling multiple commands separated by semicolons."""
        try:
            # Check if the command contains semicolons (multiple commands)
            if ";" in command:
                # Split the command by semicolons and process each one
                commands = [cmd.strip() for cmd in command.split(";") if cmd.strip()]
                self.logger.info(f"Processing multiple commands: {commands}")

                # Process each command sequentially and collect responses
                combined_response = ""
                for cmd in commands:
                    # Process the individual command with priority flag
                    cmd_response = await self._forward_single_command(
                        cmd, is_user_command
                    )

                    # Update room info after each command
                    self._update_room_info(cmd_response)

                    # Add a separator between command responses for clarity
                    if combined_response:
                        combined_response += f"\n\n--- COMMAND: {cmd} ---\n\n"
                    else:
                        combined_response += f"--- COMMAND: {cmd} ---\n\n"

                    # Add the response
                    combined_response += cmd_response

                return combined_response
            else:
                # Process a single command with priority flag
                response = await self._forward_single_command(command, is_user_command)
                self._update_room_info(response)
                return response
        except Exception as e:
            logger.error(f"Error processing commands: {e}", exc_info=True)
            return f"Error: {e!s}"

    async def _forward_single_command(
        self, command: str, is_user_command: bool = False
    ) -> str:
        """Send a single command to the MUD server.

        Args:
            command: The single command to send
            is_user_command: Whether this command was initiated by the user (high priority)

        Returns:
            str: The response from the MUD server
        """
        try:
            # Log that we're sending the command
            self.logger.debug(f"Sending command to MUD server: '{command}'")

            # Send the command and wait for response
            await self._send_command_and_wait(command, is_user_command)

            # Get the response from the client
            response = self._get_response_from_client()
            self.logger.debug(
                f"Initial response length: {len(response) if response else 0}"
            )

            # Determine expected response size based on command type
            expected_size = 100  # Default expected size

            # Commands that typically return larger responses
            if command.lower() in [
                "scan",
                "where",
                "equipment",
                "eq",
                "inventory",
                "i",
                "help",
                "who",
            ]:
                expected_size = 200  # Larger expected size for these commands
                max_retries = 4  # More retries for these commands
                base_wait = 0.5  # Longer initial wait
            elif command.lower() in ["look", "l", "score", "map"]:
                # For these commands, we also use GMCP data, so we can use fewer retries
                expected_size = 150  # Medium expected size for these commands
                max_retries = 2  # Fewer retries for commands with GMCP support
                base_wait = 0.3  # Medium initial wait
            else:
                max_retries = 3  # Standard number of retries
                base_wait = 0.1  # Standard initial wait

            # Retry logic for all commands
            retry_count = 0
            while (
                not response or len(response.strip()) < expected_size
            ) and retry_count < max_retries:
                retry_count += 1
                wait_time = (
                    base_wait * retry_count
                )  # Increase wait time with each retry

                # Wait for the response with increasing delay
                await asyncio.sleep(wait_time)

                # Try to get the response again
                response = self._get_response_from_client()

                # Log the response length for debugging
                self.logger.debug(
                    f"Retry {retry_count} response length: {len(response) if response else 0}"
                )

            # If we still have no response after all retries
            if not response or response.strip() == "":
                logger.warning(
                    f"No response received for '{command}' after {max_retries} retries"
                )

                # Try one more time with direct access to command_responses
                if (
                    hasattr(self.client, "command_responses")
                    and self.client.command_responses
                ):
                    direct_response = "\n".join(self.client.command_responses)
                    if direct_response and len(direct_response.strip()) > 10:
                        logger.info(
                            f"Retrieved response directly from command_responses: {len(direct_response)} chars"
                        )
                        return direct_response

                # If we still don't have a response, check if the command is a special case
                if command.lower() in ["look", "l", "scan", "where"]:
                    # For these commands, we should always get a response
                    # Try sending a follow-up command to force a response
                    logger.info("Sending follow-up 'look' command to force a response")
                    await self._send_command_and_wait("look")
                    await asyncio.sleep(2.0)
                    response = self._get_response_from_client()
                    if response and len(response.strip()) > 10:
                        logger.info(
                            f"Got response after follow-up command: {len(response)} chars"
                        )
                        return response

                return "Command sent, but no response captured."

            return response
        except Exception as e:
            logger.error(f"Error sending command to MUD server: {e}", exc_info=True)
            return f"Error: {e!s}"

    async def _send_command_and_wait(
        self, command: str, is_user_command: bool = False
    ) -> None:
        """Send a command to the server and wait for response.

        Args:
            command: The command to send
            is_user_command: Whether this command was initiated by the user (high priority)
        """
        # Send the command to the server
        # Handle both regular coroutines and AsyncMock objects
        send_command_result = self.client.send_command(command, is_user_command)
        if send_command_result is not None:
            await send_command_result

        # Wait for the server to respond (in a real environment)
        if not isinstance(self.client, AsyncMock):
            # Use a longer wait time for commands that might take longer to process
            if command.lower() in [
                "quest",
                "quest info",
                "quest list",
                "show all",
                "scan",
                "where",
            ]:
                # These commands might take longer to process
                logger.debug(f"Using longer wait time for command: {command}")
                await asyncio.sleep(3.5)  # Longer wait time for complex commands
            elif command.lower() in ["look", "l", "map", "score"]:
                # For these commands, we also use GMCP data, so we can use a shorter wait time
                logger.debug(
                    f"Using medium wait time for command with GMCP support: {command}"
                )
                await asyncio.sleep(
                    2.0
                )  # Medium wait time for commands with GMCP support
            else:
                # Standard wait time for regular commands
                await asyncio.sleep(1.5)

            # After waiting, check if we have any responses
            if hasattr(self.client, "command_responses"):
                response_count = len(self.client.command_responses)
                logger.debug(
                    f"After initial wait, command '{command}' has {response_count} responses"
                )

                # If we don't have any responses yet, wait a bit longer
                if response_count == 0:
                    await asyncio.sleep(2.0)  # Additional wait time

    def _get_response_from_client(self) -> str:
        """Get the response from the client.

        Returns:
            str: The response from the MUD server
        """
        # First, try to get the collected responses (new method)
        response = self._get_collected_responses()
        if response:
            logger.debug(
                f"Got response from collected responses: {len(response)} chars"
            )
            return response

        # Log that we're falling back to debug capture
        logger.debug("No collected responses, falling back to debug capture")

        # Fall back to debug capture if collected responses are not available
        response = self._get_response_from_debug_capture()
        if response:
            logger.debug(f"Got response from debug capture: {len(response)} chars")
            return response

        # If no response was found, return a default message
        return "Command sent, but no response captured."

    def _get_collected_responses(self) -> str:
        """Get responses from the client's collected responses.

        Returns:
            str: The collected responses or empty string if none available
        """
        if hasattr(self.client, "get_collected_responses"):
            collected_responses = self.client.get_collected_responses()
            if collected_responses:
                self.logger.debug(
                    f"Using collected responses ({len(collected_responses)} chars)"
                )
                self._update_room_info(collected_responses)
                return collected_responses
            else:

                # Try to get responses directly from command_responses
                if (
                    hasattr(self.client, "command_responses")
                    and self.client.command_responses
                ):
                    direct_responses = "\n".join(self.client.command_responses)
                    if direct_responses:
                        self.logger.debug(
                            f"Using direct command_responses ({len(direct_responses)} chars)"
                        )
                        self._update_room_info(direct_responses)
                        return direct_responses

        return ""

    def _get_response_from_debug_capture(self) -> str:
        """Get responses from the client's debug capture.

        Returns:
            str: The response from debug capture or empty string if none available
        """
        if not (hasattr(self.client, "debug_capture") and self.client.debug_capture):
            return ""

        # Make a copy of the debug capture to work with
        debug_entries = list(self.client.debug_capture)

        # Clear the debug capture for the next command
        self.client.debug_capture = []

        # Try different methods to extract text from debug entries
        response = self._extract_full_text_entries(debug_entries)
        if response:
            return response

        response = self._extract_text_entries(debug_entries)
        if response:
            return response

        response = self._extract_any_text(debug_entries)
        if response:
            return response

        return "Command sent, but no readable response captured."

    def _extract_full_text_entries(self, debug_entries: list) -> str:
        """Extract FULL TEXT entries from debug capture.

        Args:
            debug_entries: List of debug entries

        Returns:
            str: The extracted text or empty string if none available
        """
        full_text_entries = []
        for entry in debug_entries:
            if entry.startswith("DEBUG FULL TEXT:"):
                text = entry[len("DEBUG FULL TEXT:"):].strip()
                if text and len(text) > MIN_TEXT_LENGTH:
                    full_text_entries.append(text)

        if full_text_entries:
            response = max(full_text_entries, key=len)
            self._update_room_info(response)
            return response

        return ""

    def _extract_text_entries(selfself, debug_entries: list) -> str:
        """Extract TEXT entries from debug capture.

        Args:
            debug_entries: List of debug entries

        Returns:
            str: The extracted text or empty string if none available
        """
        text_entries = []
        for entry in debug_entries:
            if entry.startswith("DEBUG TEXT:"):
                text = entry[len("DEBUG TEXT:"):].strip()
                if text and len(text) > MIN_TEXT_LENGTH:
                    text_entries.append(text)

        if text_entries:
            response = max(text_entries, key=len)
            self._update_room_info(response)
            return response

        return ""

    def _extract_any_text(self, debug_entries: list) -> str:
        """Extract any text from debug entries.

        Args:
            debug_entries: List of debug entries

        Returns:
            str: The extracted text or empty string if none available
        """
        for entry in debug_entries:
            # Extract the content part after the first colon
            if ":" in entry:
                text = entry.split(":", 1)[1].strip()
                if text and len(text) > MIN_TEXT_LENGTH:
                    # Clean up the text - remove non-printable characters
                    cleaned_text = "".join(
                        c for c in text if c.isprintable() or c in ("\n", "\r", "\t")
                    )
                    if cleaned_text and len(cleaned_text) > MIN_TEXT_LENGTH:
                        return cleaned_text
        return ""

    def _update_room_info(self, response: str) -> None:
        """Update room description and exits from response.

        Args:
            response: The response text
        """
        # Store the response as the last room description
        self.last_room_description = response

        # Try to extract exits from the response
        exits_match = re.search(r"\s*Exits:\s*([^]]+)\]", response)
        if exits_match:
            self.last_exits = exits_match.group(1).strip()
