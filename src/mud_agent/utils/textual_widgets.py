"""
Custom Textual widgets for the MUD agent UI.

This module contains custom Textual widgets used in the MUD agent UI.
"""

import logging

from textual.widgets import Input, RichLog

logger = logging.getLogger(__name__)


class CommandInput(Input):
    """Input widget for entering commands with command history support."""

    def __init__(self, on_submit, **kwargs):
        """Initialize the command input.

        Args:
            on_submit: Callback function to call when a command is submitted
            **kwargs: Additional keyword arguments to pass to the parent class
        """
        super().__init__(**kwargs)
        self.on_submit_callback = on_submit

        # Command history support
        self.command_history = []
        self.history_max_size = 50
        self.history_index = -1
        self.current_input = ""  # Store current input when navigating history

    def on_input_submitted(self, event) -> None:
        """Called when the user submits input.

        Args:
            event: The input submitted event
        """
        command = event.value.strip()
        if command:
            # Add command to history
            if not self.command_history or command != self.command_history[-1]:
                # Only add if different from the last command
                self.command_history.append(command)
                logger.debug(
                    f"Added command to history: '{command}', history size: {len(self.command_history)}"
                )
                # Trim history if it exceeds max size
                if len(self.command_history) > self.history_max_size:
                    self.command_history.pop(0)
                    logger.debug(
                        f"Trimmed history to max size: {self.history_max_size}"
                    )

            # Reset history index
            self.history_index = -1
            self.current_input = ""

            # Call the callback
            self.on_submit_callback(command)
            self.value = ""

    def on_key(self, event) -> None:
        """Handle key events for command history navigation.

        Args:
            event: The key event
        """
        key = event.key

        if key == "up":
            # Navigate backward in history
            if self.command_history:
                if self.history_index == -1:
                    # Save current input before navigating history
                    self.current_input = self.value
                    self.history_index = len(self.command_history) - 1
                    logger.debug(
                        f"Starting history navigation, saved current input: '{self.current_input}'"
                    )
                elif self.history_index > 0:
                    self.history_index -= 1
                    logger.debug(f"Moving up in history to index {self.history_index}")

                # Set input value to the historical command
                self.value = self.command_history[self.history_index]
                logger.debug(
                    f"Set input to historical command: '{self.value}' (index {self.history_index})"
                )
                # Move cursor to end of input
                self.cursor_position = len(self.value)

            # Prevent default handling
            event.prevent_default()
            event.stop()

        elif key == "down":
            # Navigate forward in history
            if self.history_index != -1:
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    self.value = self.command_history[self.history_index]
                    logger.debug(
                        f"Moving down in history to index {self.history_index}, command: '{self.value}'"
                    )
                else:
                    # Reached the end of history, restore current input
                    self.history_index = -1
                    self.value = self.current_input
                    logger.debug(
                        f"Reached end of history, restored current input: '{self.current_input}'"
                    )

                # Move cursor to end of input
                self.cursor_position = len(self.value)

            # Prevent default handling
            event.prevent_default()
            event.stop()


class CommandLog(RichLog):
    """Log widget for displaying command history."""

    def add_command(self, command: str) -> None:
        """Add a command to the log.

        Args:
            command: The command to add
        """
        self.write(f"[bold cyan]COMMAND: {command}[/bold cyan]")

    def add_server_message(self, message: str) -> None:
        """Add a raw server message to the log.

        This method is called directly by the MUD client's data callback
        to display all server messages, not just command responses.

        Args:
            message: The raw message from the server
        """
        # Skip GMCP-related messages
        if self._is_gmcp_message(message):
            return

        # Skip empty messages
        if not message.strip():
            return

        # Skip messages that are just separators or formatting
        if (
            message.strip() in ["=", "-", "=====", "-----", "======", "------"]
            or message.strip().startswith("===")
            or message.strip().startswith("---")
        ):
            return

        # Skip messages that are just command prompts
        if message.strip() in [">", ">>", ">>>", "$ ", "# "]:
            return

        # Skip messages that are just newlines or whitespace
        if all(c.isspace() for c in message):
            return

        # Format the message with a subtle prefix to distinguish it from command responses
        # Use a dim green color to make it less intrusive but still visible
        self.write(f"[dim green]»[/dim green] {message}")

    def add_response(self, response: str) -> None:
        """Add a response to the log.

        Args:
            response: The response to add
        """
        # Skip GMCP-related messages
        if self._is_gmcp_message(response):
            return

        # Check if this is an error message
        is_error = any(
            error_term in response
            for error_term in [
                "[bold red]",
                "[red]",
                "ERROR:",
                "Error:",
                "error:",
                "Exception:",
                "exception:",
            ]
        )

        # Check if this is a JSON response and format it nicely
        if response.strip().startswith("{") and response.strip().endswith("}"):
            try:
                import json
                import re

                # Try to parse as JSON
                # First, extract the JSON part if it's mixed with other text
                json_match = re.search(r"({.*})", response)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        # Parse the JSON
                        data = json.loads(json_str)

                        # Format it nicely
                        self.write("[bold]JSON Response:[/bold]")

                        # Format each key-value pair
                        for key, value in data.items():
                            if isinstance(value, dict):
                                self.write(f"[bold]{key}:[/bold]")
                                for sub_key, sub_value in value.items():
                                    self.write(f"  [dim]{sub_key}:[/dim] {sub_value}")
                            else:
                                self.write(f"[bold]{key}:[/bold] {value}")

                        self.write("=" * 80)
                        return
                    except json.JSONDecodeError:
                        # Not valid JSON, continue with normal formatting
                        pass
            except Exception:
                # If any error occurs during JSON parsing, fall back to normal display
                pass

        # Check for GMCP error messages and format them better
        if "GMCP Error:" in response or "Invalid GMCP tag:" in response:
            # Format GMCP errors in a more readable way
            self.write("[bold yellow]GMCP Warning:[/bold yellow]")
            self.write(
                response.replace("GMCP Error:", "")
                .replace("Invalid GMCP tag:", "")
                .strip()
            )
            self.write("=" * 80)
            return

        # If it's an error, make sure it's visible by adding extra spacing
        if is_error:
            self.write("")  # Add a blank line before error
            self.write(response)
            # Only add separator if it's not already a separator
            if not response.startswith("[red]---") and "Stack Trace" not in response:
                self.write("-" * 80)
        else:
            # Format quest timer messages specially, but don't return early for commands that might have more content
            if "minutes remaining until you can go on another quest" in response:
                parts = response.split("There are ")
                if len(parts) > 1:
                    time_part = parts[1].split("minutes")[0].strip()
                    quest_timer_msg = f"[bold green]Quest Timer:[/bold green] {time_part} minutes remaining until you can quest again"

                    # Check if this is part of a larger command response
                    # Since we can't get the content directly, we'll use the response length as a heuristic
                    # If the response is long enough, it's likely part of a larger command
                    is_part_of_larger_response = len(response) > 200

                    if is_part_of_larger_response:
                        # This is likely part of a larger command response, so add the quest timer but continue processing
                        self.write(quest_timer_msg)
                    else:
                        # This is a standalone quest timer message, so add it and return
                        self.write(quest_timer_msg)
                        self.write("=" * 80)
                        return

            # Check for "Command sent, but no response captured" message
            if response == "Command sent, but no response captured.":
                # Check if we've already shown a waiting message recently
                import time

                current_time = time.time()

                # Only show the waiting message if we haven't shown one in the last 5 seconds
                if (
                    not hasattr(self, "_last_waiting_message_time")
                    or current_time - getattr(self, "_last_waiting_message_time", 0)
                    > 5.0
                ):
                    self._last_waiting_message_time = current_time
                    self.write("")  # Add a blank line for visibility
                    self.write(
                        "[bold yellow on black]⏳ WAITING FOR RESPONSE FROM THE MUD SERVER...[/]"
                    )
                    self.write("=" * 80)

                    # Schedule a refresh after a short delay to clear the waiting message
                    # This is a workaround to handle cases where the response might come in later
                    try:
                        import asyncio

                        # Store the last time we scheduled a refresh
                        if (
                            not hasattr(self, "_last_refresh_time")
                            or current_time - getattr(self, "_last_refresh_time", 0)
                            > 5.0
                        ):
                            # Only schedule a refresh if we haven't done so in the last 5 seconds
                            self._last_refresh_time = current_time
                            # Use a longer delay to avoid multiple refreshes
                            asyncio.create_task(self._delayed_refresh(5.0))
                            logger.debug(
                                "Scheduled delayed refresh for waiting message"
                            )
                        else:
                            logger.debug(
                                "Skipped scheduling refresh, too soon since last refresh"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error scheduling delayed refresh: {e}", exc_info=True
                        )
                else:
                    # We've already shown a waiting message recently, so just log it
                    logger.debug(
                        "Skipped showing waiting message, too soon since last one"
                    )
                    # Don't write anything to the command log to avoid duplicate messages
            else:
                # Normal response
                self.write(response)
                self.write("=" * 80)

    async def _delayed_refresh(self, delay_seconds: float) -> None:
        """Refresh the command log after a delay.

        Args:
            delay_seconds: The number of seconds to delay before refreshing
        """
        try:
            import asyncio
            import time

            # Wait for the specified delay
            await asyncio.sleep(delay_seconds)

            # Check if we're still mounted
            if hasattr(self, "is_mounted") and self.is_mounted:
                try:
                    # Check if there are any new responses from the client
                    has_new_responses = False
                    if (
                        hasattr(self, "app")
                        and hasattr(self.app, "agent")
                        and hasattr(self.app.agent, "client")
                    ):
                        client = self.app.agent.client
                        if (
                            hasattr(client, "command_responses")
                            and client.command_responses
                        ):
                            # There are new responses, so add them to the log
                            responses = "\n".join(client.command_responses)
                            if (
                                responses and len(responses) > 10
                            ):  # Only if there's meaningful content
                                has_new_responses = True
                                self.write(
                                    "[bold green]Received delayed response:[/bold green]"
                                )
                                self.write(responses)
                                self.write("=" * 80)
                                logger.debug(
                                    f"Added delayed responses to command log: {len(responses)} chars"
                                )

                    # If there are no new responses, just refresh the log
                    if not has_new_responses:
                        # Refresh the command log
                        self.refresh()
                        logger.debug(
                            f"Refreshed command log after {delay_seconds}s delay"
                        )

                        # Check if we've already added a refresh message recently
                        current_time = time.time()
                        if (
                            not hasattr(self, "_last_refresh_message_time")
                            or current_time
                            - getattr(self, "_last_refresh_message_time", 0)
                            > 10.0
                        ):
                            # Only add the message if we haven't done so in the last 10 seconds
                            self._last_refresh_message_time = current_time
                            # Use the write method which is definitely available on RichLog
                            self.write("[dim]Command log refreshed after timeout[/dim]")
                            logger.debug("Added refresh message to command log")
                except AttributeError as e:
                    # If there's an AttributeError, log it but don't crash
                    logger.error(
                        f"AttributeError in delayed refresh: {e}", exc_info=True
                    )
                except Exception as e:
                    # If there's any other error, log it but don't crash
                    logger.error(f"Error refreshing command log: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in delayed refresh: {e}", exc_info=True)

    def _is_gmcp_message(self, msg: str) -> bool:
        """Check if a message is GMCP-related.

        Args:
            msg: The message to check

        Returns:
            bool: True if the message is GMCP-related, False otherwise
        """
        # AGGRESSIVE GMCP FILTERING
        # This method should catch all GMCP-related messages and filter them out

        # Skip empty messages
        if not msg or not msg.strip():
            return False

        # 1. Check if it's a JSON object or array
        stripped_msg = msg.strip()
        if (stripped_msg.startswith("{") and stripped_msg.endswith("}")) or (
            stripped_msg.startswith("[") and stripped_msg.endswith("]")
        ):
            # If it's a JSON structure, check if it contains GMCP-related fields
            gmcp_json_fields = [
                "terrain",
                "mapsterrain",
                "outside",
                "details",
                "exits",
                "coord",
                "id",
                "x",
                "y",
                "cont",
                "n",
                "e",
                "s",
                "w",
                "u",
                "d",
                "num",
                "name",
                "area",
                "zone",
                "coords",
                "trains",
                "pracs",
                "spearned",
            ]

            # Check for both quoted and unquoted field names
            for field in gmcp_json_fields:
                if f'"{field}":' in stripped_msg or f"{field}:" in stripped_msg:
                    return True

            # If it's a short array with mostly numbers, it's likely GMCP data
            if stripped_msg.startswith("[") and stripped_msg.endswith("]"):
                content = stripped_msg[1:-1]  # Remove the brackets
                parts = [p.strip() for p in content.split(",")]
                if len(parts) <= 10 and all(
                    p.isdigit() or p in ["true", "false", "null", "0", "1"] or ":" in p
                    for p in parts
                    if p
                ):
                    return True

        # 2. Check for specific GMCP protocol messages
        if msg.startswith("GMCP:") or "char." in msg.lower() or "room." in msg.lower():
            return True

        # 3. Check for messages with multiple key-value pairs that look like GMCP data
        if "," in msg and ":" in msg and msg.count(":") >= 2:
            # This is likely a GMCP data structure
            gmcp_fields = [
                "terrain",
                "mapsterrain",
                "outside",
                "details",
                "exits",
                "num",
                "name",
                "area",
                "zone",
                "coords",
                "trains",
                "pracs",
                "spearned",
            ]

            # Check if any GMCP fields are present
            for field in gmcp_fields:
                if field in msg.lower():
                    return True

        # 4. Check for lines that start with "num" or other GMCP indicators
        if stripped_msg.startswith('"num":') or stripped_msg.startswith("num:"):
            return True

        # 5. Check for specific patterns in the message that indicate GMCP data
        gmcp_patterns = [
            '"terrain":',
            '"mapsterrain":',
            '"outside":',
            '"details":',
            '"exits":',
            '"e":',
            '"w":',
            '"n":',
            '"s":',
            '"u":',
            '"d":',
            '"num":',
            '"name":',
            '"area":',
            '"zone":',
            '"coords":',
            '"trains":',
            '"pracs":',
            '"spearned":',
            "terrain:",
            "mapsterrain:",
            "outside:",
            "details:",
            "exits:",
            "num:",
            "name:",
            "area:",
            "zone:",
            "coords:",
            # Add specific patterns from the screenshot
            "There are",
            "minutes remaining until you can go on another quest",
        ]

        # 5.5. Check specifically for quest timer messages
        if "minutes remaining until you can go on another quest" in msg:
            return True

        # 5.6. Check for the specific pattern in the screenshot
        if msg.strip().startswith('"num":') or msg.strip().startswith("num:"):
            return True

        # 5.7. Check for messages that contain both "terrain" and "details" keywords
        if "terrain" in msg and "details" in msg:
            return True

        # 5.8. Check for the specific "safe,trainer" pattern in the screenshot
        if "safe,trainer" in msg or '"details": "safe,trainer"' in msg:
            return True

        if any(pattern in msg for pattern in gmcp_patterns):
            return True

        # Don't filter out GMCP error messages that might be important
        if "GMCP Error:" in msg or "Invalid GMCP tag:" in msg:
            return False

        # Don't filter out normal game responses
        return False
