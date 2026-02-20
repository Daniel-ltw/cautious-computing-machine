"""
MUD client implementation with proper telnet protocol support.
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from ..protocols import ColorHandler, GMCPHandler, MSDPHandler, TelnetBytes
from ..utils.event_emitter import EventEmitter

logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_LENGTH = 10  # Minimum length for valid text responses
ASCII_SPACE = 32  # ASCII code for space character
ASCII_TILDE = 126  # ASCII code for tilde character (end of printable ASCII)
ASCII_NEWLINE = 10  # ASCII code for newline
ASCII_CARRIAGE_RETURN = 13  # ASCII code for carriage return
ASCII_TAB = 9  # ASCII code for tab
MAX_SMALL_PACKET_SIZE = 100  # Maximum size for small packets (for full hex dump)
MAX_PREVIEW_TEXT_LENGTH = 200  # Maximum length for text preview in logs
MAX_RAW_BUFFER_SIZE = 20  # Maximum number of raw data packets to store
RESPONSE_COLLECTION_TIMEOUT = 2.0  # Seconds to wait for additional responses
PRINTABLE_THRESHOLD = 0.5  # Threshold for determining if text is mostly printable
SIGNIFICANT_TEXT_THRESHOLD = (
    0.3  # Threshold for determining if extracted text is significant
)
CONTROL_CHAR_THRESHOLD = (
    0.5  # Threshold for determining if text has too many control characters
)
HEX_PREVIEW_SIZE = 20  # Number of bytes to show in hex preview
NEGOTIATION_TIMEOUT = 10.0  # Timeout for protocol negotiation in seconds
LOGIN_PASSWORD_DELAY = 1.5  # Delay after sending username before sending password
LOGIN_RESPONSE_DELAY = 3.0  # Delay after sending password to wait for login response
SMALL_NEGOTIATION_DELAY = 0.1  # Small delay between protocol negotiations
KEEP_ALIVE_INTERVAL = 10.0  # Seconds between keep-alive packets
KEEP_ALIVE_TIMEOUT = 180.0  # Seconds of inactivity before connection is considered dead


class MudClient:
    """A MUD client implementation supporting various protocols."""

    def __init__(
        self,
        host: str = "aardmud.org",
        port: int = 4000,
        debug_mode: bool = False,
        keep_alive_enabled: bool = True,
        keep_alive_interval: float = KEEP_ALIVE_INTERVAL,
    ):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.data_callback: Callable[[str], None] | None = None
        self._receive_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()  # Protects connected/reader/writer
        self._negotiation_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)

        # Event emitter for event-driven architecture
        self.events = EventEmitter()

        # Debug mode for troubleshooting
        self.debug_mode = debug_mode

        # Last received data timestamp for timeout detection
        self.last_data_time = time.time()
        self.last_sent_time = time.time()

        # Keep-alive settings
        self.keep_alive_enabled = keep_alive_enabled
        self.keep_alive_interval = keep_alive_interval
        self.keep_alive_task = None

        # Raw data buffer for debugging
        self.raw_data_buffer = []
        self.max_raw_buffer_size = MAX_RAW_BUFFER_SIZE  # Keep last N raw data packets

        # Debug capture for storing debug output
        self.debug_capture = []

        # Response collection for commands
        self.current_command = None
        self.command_responses = []
        self.last_command_time = 0
        self.response_collection_timeout = RESPONSE_COLLECTION_TIMEOUT
        self._cleanup_task: asyncio.Task | None = None

        # Command queue for prioritizing user commands
        self.command_queue = []
        self.command_queue_lock = asyncio.Lock()

        # Protocol handlers
        self.gmcp = GMCPHandler()
        self.msdp = MSDPHandler()
        self.color = ColorHandler()

        # Buffer for incomplete telnet commands
        self.command_buffer = bytearray()

        # Supported features
        self.supported_features = {
            TelnetBytes.GMCP: False,
            TelnetBytes.MSDP: False,
            TelnetBytes.ECHO: False,
            TelnetBytes.SUPPRESS_GA: False,
            TelnetBytes.TERMINAL_TYPE: False,
            TelnetBytes.NAWS: False,
            TelnetBytes.CHARSET: False,
        }

        # Store reference to the last negotiation task
        self._last_negotiation_task = None

    @property
    def gmcp_enabled(self) -> bool:
        """Check if GMCP is enabled."""
        return self.gmcp.enabled

    @property
    def msdp_enabled(self) -> bool:
        """Check if MSDP is enabled."""
        return self.msdp.enabled

    @property
    def color_enabled(self) -> bool:
        """Check if color support is enabled."""
        return self.color.enabled

    def set_data_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for received data.

        This method is kept for backward compatibility.
        New code should use the events system instead.

        Args:
            callback: The callback function to call when data is received
        """
        self.data_callback = callback

        # Also register the callback as an event listener for the 'data' event
        self.events.on("data", lambda text: callback(text))

    def get_collected_responses(self, clear: bool = True) -> str:
        """Get all collected responses for the current command.

        Args:
            clear: Whether to clear the collected responses after returning them

        Returns:
            str: All collected responses joined together
        """
        if not self.command_responses:
            return ""

        # Join all responses with a newline
        result = "\n".join(self.command_responses)

        # For all commands, we'll keep responses in memory for a short time
        # This allows for retries and better response handling
        if clear:
            # Cancel any previous cleanup task to avoid wiping a future command's data
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                self._cleanup_task = None
            # Schedule cleanup after a delay instead of clearing immediately
            try:
                cmd_name = (
                    self.current_command.lower() if self.current_command else "unknown"
                )
                self.logger.debug(
                    f"Scheduling delayed cleanup for '{cmd_name}' command responses"
                )
                self._cleanup_task = asyncio.create_task(
                    self._delayed_response_cleanup(3.0)
                )
            except Exception as e:
                self.logger.error(
                    f"Error scheduling delayed response cleanup: {e}", exc_info=True
                )
                # If we can't schedule a delayed cleanup, clear immediately as a fallback
                self.command_responses = []
                self.current_command = None

        return result

    async def _delayed_response_cleanup(self, delay_seconds: float) -> None:
        """Clean up command responses after a delay.

        Args:
            delay_seconds: The number of seconds to delay before cleanup
        """
        try:
            await asyncio.sleep(delay_seconds)

            # Clear the command responses
            self.command_responses = []
            self.current_command = None
            self.logger.debug(f"Cleared command responses after {delay_seconds}s delay")
        except asyncio.CancelledError:
            pass  # Cancelled by a new command — expected
        except Exception as e:
            self.logger.error(f"Error in delayed response cleanup: {e}", exc_info=True)

    async def connect(self, host: str = "aardmud.org", port: int = 4000) -> bool:
        """Connect to the MUD server.

        Args:
            host: The hostname of the MUD server.
            port: The port number of the MUD server.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            # Emit a 'connecting' event
            self.logger.info(f"Emitting 'connecting' event for {host}:{port}")
            self.events.emit("connecting", host, port)

            # Store host and port for reconnection
            self.host = host
            self.port = port
            self.logger.info(f"Stored host={host}, port={port} for reconnection")

            # Close existing connection if any
            if self.writer is not None:
                try:
                    self.logger.info("Closing existing connection")
                    self.writer.close()
                    await self.writer.wait_closed()
                    self.logger.info("Existing connection closed")
                except Exception as e:
                    self.logger.warning(f"Error closing existing connection: {e}")

            self.logger.info(f"Opening connection to {host}:{port}")
            self.reader, self.writer = await asyncio.open_connection(host, port)
            self.connected = True
            self.logger.info(f"Connected to {host}:{port}")
            self.logger.info(
                f"Connection established: reader={self.reader}, writer={self.writer}"
            )

            # Emit a 'connected' event
            self.logger.info(f"Emitting 'connected' event for {host}:{port}")
            self.events.emit("connected", host, port)

            # Start protocol negotiation
            self.logger.info("Starting protocol negotiation")
            await self._negotiate_protocols()
            self.logger.info("Protocol negotiation completed")

            # Emit a 'ready' event after protocol negotiation
            self.logger.info("Emitting 'ready' event")
            self.events.emit("ready")
            self.logger.info("Client is now ready for commands")

            # Start the reader task if not already running
            if (
                hasattr(self, "reader_task")
                and self.reader_task is not None
                and not self.reader_task.done()
            ):
                self.logger.info(f"Reader task already running: {self.reader_task}")
            else:
                # Cancel any existing reader task
                if hasattr(self, "reader_task") and self.reader_task is not None:
                    try:
                        self.logger.info(
                            f"Cancelling existing reader task: {self.reader_task}"
                        )
                        self.reader_task.cancel()
                        self.logger.info("Existing reader task cancelled")
                    except Exception as e:
                        self.logger.warning(f"Error cancelling reader task: {e}")

                self.logger.info("Starting reader task")
                self.reader_task = asyncio.create_task(self._reader_task())
                self.logger.info(f"Reader task started: {self.reader_task}")

            # Start the keep-alive task if enabled
            if self.keep_alive_enabled:
                if (
                    hasattr(self, "keep_alive_task")
                    and self.keep_alive_task is not None
                    and not self.keep_alive_task.done()
                ):
                    self.logger.info(
                        f"Keep-alive task already running: {self.keep_alive_task}"
                    )
                else:
                    # Cancel any existing keep-alive task
                    if (
                        hasattr(self, "keep_alive_task")
                        and self.keep_alive_task is not None
                    ):
                        try:
                            self.logger.info(
                                f"Cancelling existing keep-alive task: {self.keep_alive_task}"
                            )
                            self.keep_alive_task.cancel()
                            self.logger.info("Existing keep-alive task cancelled")
                        except Exception as e:
                            self.logger.warning(
                                f"Error cancelling keep-alive task: {e}"
                            )

                    self.logger.info(
                        f"Starting keep-alive task with interval {self.keep_alive_interval}s"
                    )
                    self.keep_alive_task = asyncio.create_task(self._keep_alive_task())
                    self.logger.info(f"Keep-alive task started: {self.keep_alive_task}")

            return True
        except Exception as e:
            self.logger.error(f"Connection error: {e}", exc_info=True)
            self.connected = False

            # Emit a 'connection_error' event
            self.logger.info(f"Emitting 'connection_error' event: {e!s}")
            self.events.emit("connection_error", str(e))

            return False

    async def _negotiate_protocols(self) -> None:
        """Negotiate supported protocols with server.

        This method handles the negotiation of telnet options with the server.
        It follows the proper telnet negotiation protocol as defined in RFC 854 and RFC 855.
        """
        try:
            # Reset negotiation event
            self._negotiation_event.clear()

            # First, we'll send DO for options we want the server to enable
            server_options = [
                TelnetBytes.GMCP,  # We want the server to send GMCP data
                TelnetBytes.MSDP,  # We want the server to send MSDP data
            ]

            for option in server_options:
                await self._send_do(option)
                option_name = self._get_option_name(option)
                self.logger.debug(f"Sent DO {option_name} ({option})")
                await asyncio.sleep(
                    SMALL_NEGOTIATION_DELAY
                )  # Small delay between negotiations

            # Then, we'll send WILL for options we want to enable on our side
            client_options = [
                TelnetBytes.GMCP,  # We can receive GMCP data (bidirectional per spec)
                TelnetBytes.SUPPRESS_GA,  # We'll suppress GA
                TelnetBytes.NAWS,  # We'll negotiate about window size
            ]

            for option in client_options:
                await self._send_will(option)
                option_name = self._get_option_name(option)
                self.logger.debug(f"Sent WILL {option_name} ({option})")
                await asyncio.sleep(
                    SMALL_NEGOTIATION_DELAY
                )  # Small delay between negotiations

            # Set a timeout for negotiation completion
            try:
                # Wait for negotiation to complete or timeout
                await asyncio.wait_for(
                    self._negotiation_event.wait(), timeout=NEGOTIATION_TIMEOUT
                )
                self.logger.info("Protocol negotiation completed successfully")
            except TimeoutError:
                # Even if negotiation times out, we can still proceed
                # Some MUD servers don't respond to all negotiation requests
                self.logger.info(
                    f"Protocol negotiation timed out after {NEGOTIATION_TIMEOUT} seconds, proceeding with connection"
                )
                self._negotiation_event.set()  # Allow connection to proceed

            # Initialize enabled protocols
            await self._initialize_protocols()

        except Exception as e:
            self.logger.error(f"Protocol negotiation failed: {e}", exc_info=True)
            self._negotiation_event.set()  # Allow connection to proceed

    async def disconnect(self) -> None:
        """Disconnect from the MUD server."""
        try:
            # Emit a 'disconnecting' event
            self.events.emit("disconnecting")

            # Cancel keep-alive task if running
            if hasattr(self, "keep_alive_task") and self.keep_alive_task is not None:
                try:
                    self.logger.info("Cancelling keep-alive task")
                    self.keep_alive_task.cancel()
                    self.keep_alive_task = None
                except Exception as e:
                    self.logger.warning(f"Error cancelling keep-alive task: {e}")

            if self.writer is not None:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                except Exception as e:
                    self.logger.error(f"Error during disconnect: {e}")
                    # Emit a 'disconnect_error' event
                    self.events.emit("disconnect_error", str(e))
        finally:
            async with self._connection_lock:
                self.writer = None
                self.reader = None
                self.connected = False
            self.logger.info("Disconnected from server")

            # Emit a 'disconnected' event
            self.events.emit("disconnected")

    async def send_command(self, command: str, is_user_command: bool = False) -> None:
        """
        Send a command to the MUD server.

        Args:
            command: The command to send to the server
            is_user_command: Whether this command was initiated by the user (high priority)

        Raises:
            ConnectionError: If not connected or writer is None
            RuntimeError: If error occurs while sending command
        """
        async with self._connection_lock:
            if not self.connected or self.writer is None:
                self.logger.error("Cannot send command - not connected to server")
                self.logger.error(f"Connected: {self.connected}, Writer: {self.writer}")
                self.events.emit("connection_error", "Not connected to server")
                raise ConnectionError("Not connected to server")
            # Capture writer reference under the lock so a concurrent
            # disconnect() cannot null it between the check and the write.
            writer = self.writer

        try:
            # Ensure command ends with newline
            if not command.endswith("\n"):
                command += "\n"

            # Strip the command for storage and events
            stripped_command = command.strip()
            self.logger.info(
                f"Preparing to send command: '{stripped_command}' (user command: {is_user_command})"
            )

            # Check if this is a duplicate command (sent within the last second)
            current_time = time.time()
            if (
                hasattr(self, "last_command")
                and hasattr(self, "last_command_time")
                and self.last_command == stripped_command
                and current_time - self.last_command_time < 0.3
            ):
                self.logger.warning(
                    f"Skipping duplicate command: '{stripped_command}' (sent {current_time - self.last_command_time:.2f}s ago)"
                )
                return

            # Store this command to check for duplicates
            self.last_command = stripped_command
            self.last_command_time = current_time

            # NOTE: command_sent event is now emitted in command_processor.py with from_room_num
            # to avoid race condition. This emit is kept for backward compatibility but will
            # be redundant if using command_processor.
            # Emit a 'command_sent' event before sending (old format for backward compat)


            # Cancel any pending cleanup from the previous command
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                self._cleanup_task = None
            # Set the current command and reset response collection
            self.current_command = stripped_command
            self.command_responses = []

            # Encode and send command
            encoded_command = command.encode()
            writer.write(encoded_command)

            # Make sure to drain the writer to ensure the command is sent
            try:
                await asyncio.wait_for(writer.drain(), timeout=5.0)
                self.logger.info(f"Command '{stripped_command}' sent successfully")

                # Update last sent time for keep-alive tracking
                self.last_sent_time = time.time()

                # Emit a 'command_sent_success' event after sending
                self.events.emit("command_sent_success", stripped_command)
            except TimeoutError:
                self.logger.error(f"Timeout while sending command '{stripped_command}'")
                # Try to recover by resetting the writer
                if hasattr(writer, "transport"):
                    writer.transport.abort()
                    self.logger.info("Aborted writer transport due to timeout")
                # Emit a 'command_error' event
                self.events.emit(
                    "command_error", stripped_command, "Timeout while sending command"
                )
                raise RuntimeError(
                    f"Timeout while sending command: '{stripped_command}'"
                )

        except ConnectionError as e:
            self.logger.error(
                f"Connection lost while sending command '{command}': {e}", exc_info=True
            )
            self.connected = False
            # Emit a 'connection_error' event
            self.events.emit("connection_error", str(e))
            raise
        except Exception as e:
            self.logger.error(f"Error sending command '{command}': {e}", exc_info=True)
            # Emit a 'command_error' event
            self.events.emit("command_error", command.strip(), str(e))
            raise RuntimeError(f"Failed to send command: {e}") from e

    async def queue_command(self, command: str, is_user_command: bool = False) -> None:
        """
        Queue a command to be sent to the MUD server.
        User commands are prioritized over background commands.

        Args:
            command: The command to queue
            is_user_command: Whether this command was initiated by the user (high priority)
        """
        async with self.command_queue_lock:
            if is_user_command:
                # Insert user commands at the beginning of the queue
                self.command_queue.insert(0, (command, is_user_command))
                self.logger.debug(
                    f"Queued user command with high priority: '{command}'"
                )
            else:
                # Add background commands to the end of the queue
                self.command_queue.append((command, is_user_command))
                self.logger.debug(f"Queued background command: '{command}'")

            # If this is the first command in the queue, start processing the queue
            if len(self.command_queue) == 1:
                # Start processing the queue in a separate task
                asyncio.create_task(self._process_command_queue())

    async def _process_command_queue(self) -> None:
        """Process commands in the queue, prioritizing user commands."""
        try:
            while True:
                # Check if there are any commands in the queue
                async with self.command_queue_lock:
                    if not self.command_queue:
                        # No more commands to process
                        self.logger.debug(
                            "Command queue is empty, stopping queue processor"
                        )
                        return

                    # Get the next command from the queue (already prioritized)
                    command, is_user_command = self.command_queue[0]

                # Send the command
                try:
                    await self.send_command(command, is_user_command)
                    self.logger.debug(
                        f"Processed queued command: '{command}' (user command: {is_user_command})"
                    )
                except Exception as e:
                    self.logger.error(
                        f"Error processing queued command '{command}': {e}",
                        exc_info=True,
                    )

                # Remove the command from the queue
                async with self.command_queue_lock:
                    if self.command_queue and self.command_queue[0][0] == command:
                        self.command_queue.pop(0)

                # Add a small delay between commands to avoid flooding the server
                await asyncio.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error in command queue processor: {e}", exc_info=True)

    async def receive_data(self) -> None:
        """
        Continuously receive and process data from the MUD server.

        This method runs in a loop until the connection is closed or an error occurs.
        It handles:
        - Reading raw data from the server
        - Processing telnet negotiations
        - Handling compression
        - Invoking callbacks with processed data

        Raises:
            ConnectionError: If not connected or connection lost
            RuntimeError: For other errors during data processing
        """
        if not self.connected or self.reader is None:
            raise ConnectionError("Not connected to server")

        # Add a lock to prevent multiple coroutines from reading at the same time
        if not hasattr(self, "_reader_lock"):
            self._reader_lock = asyncio.Lock()

        self.logger.info("Starting receive_data loop")

        try:
            while self.connected:
                try:
                    # Read data from server with a lock to prevent multiple reads
                    self.logger.debug("Waiting for data from server...")

                    # Use the lock to prevent multiple coroutines from reading at the same time
                    async with self._reader_lock:
                        if not self.connected or self.reader is None:
                            self.logger.info("Connection lost while waiting for lock")
                            break

                        data = await self.reader.read(4096)
                        self.logger.debug(f"Received {len(data)} bytes from server")

                    # Update last data time for keep-alive tracking
                    self.last_data_time = time.time()
                    self.logger.debug(
                        f"Updated last_data_time to {self.last_data_time}"
                    )

                    if not data:
                        self.logger.info(
                            "Server closed connection (empty data received)"
                        )
                        await self.disconnect()
                        break

                    # Store raw data for debugging
                    if self.debug_mode:
                        # Store in raw buffer (limited size)
                        self.raw_data_buffer.append(data)
                        if len(self.raw_data_buffer) > self.max_raw_buffer_size:
                            self.raw_data_buffer.pop(0)

                        # Print first few bytes in hex for debugging
                        if len(data) > 0:
                            hex_preview = data[: min(HEX_PREVIEW_SIZE, len(data))].hex()

                    # Process telnet and get text
                    text = self._process_telnet(data)

                    # Strip colors if needed (disabled by default to preserve color codes)
                    if not self.color.enabled:
                        original_text = text
                        text = self.color.strip_color(text)
                        if self.debug_mode and original_text != text:
                            pass
                    elif self.debug_mode:
                        # Check if text contains color codes
                        if "\x1b[" in text:
                            pass

                    # Log received data with better details
                    if len(text) > MAX_PREVIEW_TEXT_LENGTH:
                        self.logger.debug(
                            f"Received raw data ({len(text)} chars): {text[:MAX_PREVIEW_TEXT_LENGTH]}..."
                        )
                    else:
                        self.logger.debug(
                            f"Received raw data ({len(text)} chars): {text}"
                        )

                    # Print processed data to console in debug mode
                    if self.debug_mode:
                        if text:
                            # Print full text in debug mode
                            debug_text = f"DEBUG TEXT: {text}"

                            # Store in debug capture
                            self.debug_capture.append(debug_text)

                            # Store full text in debug capture with a special marker
                            self.debug_capture.append(f"DEBUG FULL TEXT: {text}")
                        else:
                            pass

                    # We now handle response collection in the event handler

                    # Emit the 'data' event
                    try:
                        # Emit the event first (new approach)
                        self.events.emit("data", text)
                        self.logger.debug(
                            f"Emitted 'data' event with {len(text)} chars"
                        )

                        # Process the text for response collection
                        if text and text.strip():
                            # If we have a current command, collect this response
                            if self.current_command is not None:
                                current_time = time.time()
                                # Check if this response is still associated with the current command
                                if (
                                    current_time - self.last_command_time
                                    <= self.response_collection_timeout
                                ):
                                    self.command_responses.append(text)
                                    self.last_command_time = current_time  # Reset timeout for additional responses
                                    self.logger.debug(
                                        f"Collected response for command '{self.current_command}' ({len(text)} chars)"
                                    )

                                    # Emit a 'command_response' event
                                    self.events.emit(
                                        "command_response", self.current_command, text
                                    )

                                    if self.debug_mode:
                                        pass

                        # Invoke legacy callback with the processed text (old approach)
                        if self.data_callback:
                            try:
                                if self.debug_mode:
                                    pass
                                self.data_callback(text)
                                self.logger.debug(
                                    f"Legacy data callback invoked with {len(text)} chars"
                                )
                            except Exception as e:
                                self.logger.error(f"Legacy data callback failed: {e}")
                                if self.debug_mode:
                                    pass
                        elif self.debug_mode:
                            pass
                    except Exception as e:
                        self.logger.error(
                            f"Error processing received data: {e}", exc_info=True
                        )
                        if self.debug_mode:
                            pass

                except ConnectionError as e:
                    self.logger.error(f"Connection lost: {e}")
                    await self.disconnect()
                    raise

                except Exception as e:
                    self.logger.error(f"Error receiving data: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Fatal error in receive loop: {e}")
            await self.disconnect()
            raise RuntimeError(f"Failed to receive data: {e}") from e

    def _process_telnet(self, data: bytes) -> str:
        """
        Process telnet negotiations and commands in received data.

        Args:
            data: Raw bytes received from server

        Returns:
            str: Processed data with telnet negotiations removed, decoded to string

        This method handles:
        - Basic telnet negotiations (IAC sequences)
        - GMCP data
        - MSDP data
        """
        # Process raw data for telnet negotiations
        processed = bytearray()
        i = 0
        telnet_commands = []

        # Extract regular data and process telnet commands
        i, processed, telnet_commands = self._extract_and_process_telnet_commands(
            data, i, processed, telnet_commands
        )

        # Log telnet commands if any were found
        if telnet_commands:
            self.logger.debug(f"Telnet commands processed: {' '.join(telnet_commands)}")

        # If no regular data was processed but we had telnet commands
        if len(processed) == 0:
            if telnet_commands:
                self.logger.debug("Only telnet commands received, no regular data")
            return ""  # Return empty string for empty data

        # Decode the processed data to string
        return self._decode_processed_data(processed)

    def _extract_and_process_telnet_commands(
        self, data: bytes, i: int, processed: bytearray, telnet_commands: list
    ) -> tuple[int, bytearray, list]:
        """
        Extract regular data and process telnet commands.

        Args:
            data: Raw bytes received from server
            i: Current index in data
            processed: Bytearray to store regular data
            telnet_commands: List to store telnet command names

        Returns:
            tuple: Updated index, processed data, and telnet commands
        """
        while i < len(data):
            # Check for IAC
            if data[i] == TelnetBytes.IAC:
                i, telnet_commands = self._process_telnet_command(
                    data, i + 1, telnet_commands
                )
            else:
                # Regular data
                processed.append(data[i])
                i += 1

        return i, processed, telnet_commands

    def _process_telnet_command(
        self, data: bytes, i: int, telnet_commands: list
    ) -> tuple[int, list]:
        """
        Process a telnet command.

        Args:
            data: Raw bytes received from server
            i: Current index in data (after IAC)
            telnet_commands: List to store telnet command names

        Returns:
            tuple: Updated index and telnet commands
        """
        telnet_commands.append("IAC")

        if i >= len(data):
            return i, telnet_commands

        # Handle command
        cmd = data[i]
        i += 1

        cmd_name = self._get_telnet_command_name(cmd)
        telnet_commands.append(cmd_name)

        if cmd in (
            TelnetBytes.WILL,
            TelnetBytes.WONT,
            TelnetBytes.DO,
            TelnetBytes.DONT,
        ):
            i, telnet_commands = self._process_negotiation_command(
                data, i, cmd, cmd_name, telnet_commands
            )
        elif cmd == TelnetBytes.SB:
            i, telnet_commands = self._process_subnegotiation(data, i, telnet_commands)
        else:
            self.logger.debug(f"Unknown telnet command: {cmd}")
            telnet_commands.append(f"UNKNOWN:{cmd}")

        return i, telnet_commands

    def _get_telnet_command_name(self, cmd: int) -> str:
        """Get the name of a telnet command."""
        if cmd == TelnetBytes.WILL:
            return "WILL"
        elif cmd == TelnetBytes.WONT:
            return "WONT"
        elif cmd == TelnetBytes.DO:
            return "DO"
        elif cmd == TelnetBytes.DONT:
            return "DONT"
        elif cmd == TelnetBytes.SB:
            return "SB"
        return "UNKNOWN"

    def _process_negotiation_command(
        self, data: bytes, i: int, cmd: int, cmd_name: str, telnet_commands: list
    ) -> tuple[int, list]:
        """
        Process a telnet negotiation command (WILL, WONT, DO, DONT).

        Args:
            data: Raw bytes received from server
            i: Current index in data
            cmd: The command byte
            cmd_name: The command name
            telnet_commands: List to store telnet command names

        Returns:
            tuple: Updated index and telnet commands
        """
        if i < len(data):
            option = data[i]
            i += 1
            telnet_commands.append(f"OPTION:{option}")
            self.logger.debug(f"Telnet negotiation: {cmd_name} {option}")

            # Properly handle feature negotiation
            # Store task reference to prevent it from being garbage collected
            self._last_negotiation_task = asyncio.create_task(
                self._handle_feature_negotiation(cmd, option)
            )

        return i, telnet_commands

    def _process_subnegotiation(
        self, data: bytes, i: int, telnet_commands: list
    ) -> tuple[int, list]:
        """
        Process a telnet subnegotiation.

        Args:
            data: Raw bytes received from server
            i: Current index in data
            telnet_commands: List to store telnet command names

        Returns:
            tuple: Updated index and telnet commands
        """
        # Find end of subnegotiation
        end = i
        while end < len(data) - 1:
            if data[end] == TelnetBytes.IAC and data[end + 1] == TelnetBytes.SE:
                break
            end += 1

        if end < len(data) - 1:
            # Process subnegotiation
            option = data[i]
            payload = data[i + 1 : end]

            option_name = f"OPTION:{option}"
            if option == TelnetBytes.GMCP:
                option_name = "GMCP"
                self._process_gmcp_payload(payload)
            elif option == TelnetBytes.MSDP:
                option_name = "MSDP"
                self._process_msdp_payload(payload)

            telnet_commands.append(option_name)
            telnet_commands.append("SE")

            i = end + 2  # Skip to after SE
        else:
            # Incomplete subnegotiation
            telnet_commands.append("INCOMPLETE")
            i = end

        return i, telnet_commands

    def _process_gmcp_payload(self, payload: bytes) -> None:
        """Process GMCP payload."""
        try:
            # Convert payload to string for GMCP
            message = payload.decode("utf-8", errors="replace")

            # Parse the message to get module and data
            module, data = self.gmcp.handle_message(message)

            # Emit a 'gmcp_data' event with the module and data
            if module and data is not None:
                self.events.emit("gmcp_data", module, data)

                # Also emit a module-specific event
                self.events.emit(f"gmcp.{module}", data)

                # Emit parent module events (e.g., 'gmcp.char' for 'gmcp.char.vitals')
                parts = module.split(".")
                for i in range(1, len(parts)):
                    parent_module = ".".join(parts[:i])
                    self.events.emit(f"gmcp.{parent_module}", module, data)

            self.logger.debug(f"Processed GMCP message: {message[:50]}...")
        except Exception as e:
            self.logger.error(f"Error processing GMCP message: {e}", exc_info=True)
            # Emit a 'gmcp_error' event
            self.events.emit("gmcp_error", str(e))

    def _process_msdp_payload(self, payload: bytes) -> None:
        """Process MSDP payload."""
        try:
            # Process the MSDP message
            module, data = self.msdp.handle_message(payload)

            # Emit an 'msdp_data' event with the module and data
            if module and data is not None:
                self.events.emit("msdp_data", module, data)

                # Also emit a module-specific event
                self.events.emit(f"msdp.{module}", data)

            self.logger.debug("Processed MSDP message")
        except Exception as e:
            self.logger.error(f"Error processing MSDP message: {e}", exc_info=True)
            # Emit an 'msdp_error' event
            self.events.emit("msdp_error", str(e))

    def _decode_processed_data(self, processed: bytearray) -> str:
        """
        Decode processed data to string, handling various encodings.

        Args:
            processed: Processed data as bytearray

        Returns:
            str: Decoded string
        """
        try:
            # First, try to decode as UTF-8
            result = processed.decode("utf-8", errors="replace")

            # Check if the result contains mostly printable characters
            result = self._improve_text_quality(result, processed)

            # Debug: Print the first 100 chars of processed data
            if result:
                self.logger.debug(f"Processed data first 100 chars: {result[:100]}")

            return result
        except UnicodeDecodeError as e:
            self.logger.error(f"Failed to decode data: {e}", exc_info=True)
            return self._extract_printable_ascii(processed)

    def _improve_text_quality(self, result: str, processed: bytearray) -> str:
        """
        Improve the quality of decoded text.

        Args:
            result: Initial decoded result
            processed: Original processed data

        Returns:
            str: Improved text
        """
        # Check if the result contains mostly printable characters
        printable_count = sum(
            1 for c in result if c.isprintable() or c in ("\n", "\r", "\t")
        )

        # If less than threshold are printable, try to improve
        if printable_count < len(result) * PRINTABLE_THRESHOLD:
            # Try Latin-1 (ISO-8859-1) which is common in older MUDs
            result, printable_count = self._try_latin1_decoding(
                processed, result, printable_count
            )

            # If still not good enough, extract printable characters
            if printable_count < len(result) * PRINTABLE_THRESHOLD:
                result = self._extract_printable_characters(result)

        # Check for control characters and extract meaningful patterns if needed
        if len(result) > 0:
            result = self._extract_meaningful_patterns(result)

        return result

    def _try_latin1_decoding(
        self, processed: bytearray, result: str, printable_count: int
    ) -> tuple[str, int]:
        """
        Try decoding with Latin-1 encoding.

        Args:
            processed: Processed data
            result: Current result
            printable_count: Current printable character count

        Returns:
            tuple: Improved result and new printable count
        """
        try:
            latin1_result = processed.decode("latin-1", errors="replace")
            latin1_printable = sum(
                1 for c in latin1_result if c.isprintable() or c in ("\n", "\r", "\t")
            )

            # If Latin-1 gives better results, use it
            if latin1_printable > printable_count:
                self.logger.debug(
                    f"Latin-1 decoding improved printable characters from {printable_count} to {latin1_printable}"
                )
                return latin1_result, latin1_printable
        except Exception:
            pass

        return result, printable_count

    def _extract_printable_characters(self, result: str) -> str:
        """
        Extract only printable characters from text.

        Args:
            result: Text to process

        Returns:
            str: Text with only printable characters
        """
        self.logger.debug(
            "Result contains many non-printable characters, extracting printable text"
        )
        printable_text = "".join(
            c for c in result if c.isprintable() or c in ("\n", "\r", "\t")
        )

        # If we extracted a significant amount of text, use it
        if (
            len(printable_text) > MIN_TEXT_LENGTH
            and len(printable_text) > len(result) * SIGNIFICANT_TEXT_THRESHOLD
        ):
            self.logger.debug(
                f"Extracted {len(printable_text)} printable characters from {len(result)} total"
            )
            return printable_text

        return result

    def _extract_meaningful_patterns(self, result: str) -> str:
        """
        Extract meaningful patterns from text that has too many control characters.

        Args:
            result: Text to process

        Returns:
            str: Extracted meaningful text or original text
        """
        control_chars = sum(
            1 for c in result if not c.isprintable() and c not in ("\n", "\r", "\t")
        )

        # If more than threshold are control characters
        if control_chars > len(result) * CONTROL_CHAR_THRESHOLD:
            self.logger.debug(
                "Result contains too many control characters, trying to extract meaningful text"
            )

            # Try to extract meaningful text patterns
            import re

            # Look for common patterns in MUD output
            patterns = [
                r"You are in area\s*:.*",  # Where command output
                r"Level range is\s*:.*",  # Where command output
                r"Players near you:.*",  # Where command output
                r"Basic Training.*",  # Room name
                r"\[\s*Exits:.*\]",  # Exits
                r"The blackboard contains.*",  # Examine blackboard
                r"You scan the surroundings.*",  # Scan command
                r"You have scored \d+ exp.*",  # Score command
                r"You are carrying.*",  # Inventory
                r"You are wearing.*",  # Equipment
                r"You have \d+ hit points.*",  # Health
                r"You have \d+ mana.*",  # Mana
                r"You have \d+ movement.*",  # Movement
            ]

            extracted_text = []
            for pattern in patterns:
                matches = re.findall(pattern, result, re.DOTALL | re.MULTILINE)
                extracted_text.extend(matches)

            if extracted_text:
                self.logger.debug(
                    f"Extracted {len(extracted_text)} meaningful text patterns"
                )
                return "\n".join(extracted_text)

        return result

    def _extract_printable_ascii(self, processed: bytearray) -> str:
        """
        Extract printable ASCII characters from processed data.

        Args:
            processed: Processed data

        Returns:
            str: Extracted ASCII text or fallback
        """
        try:
            printable_bytes = bytes(
                b
                for b in processed
                if ASCII_SPACE <= b <= ASCII_TILDE
                or b in (ASCII_NEWLINE, ASCII_CARRIAGE_RETURN, ASCII_TAB)
            )

            if printable_bytes and len(printable_bytes) > MIN_TEXT_LENGTH:
                result = printable_bytes.decode("ascii", errors="ignore")
                self.logger.debug(f"Extracted {len(result)} printable ASCII characters")
                return result
        except Exception as extract_error:
            self.logger.error(
                f"Failed to extract printable characters: {extract_error}",
                exc_info=True,
            )

        # Fall back to ASCII decoding with ignore errors
        return processed.decode("ascii", errors="ignore")

    async def _handle_feature_negotiation(self, cmd: int, option: int) -> None:
        """Handle telnet feature negotiation according to RFC 854 and RFC 855.

        This method implements the proper telnet option negotiation state machine.
        It handles WILL, WONT, DO, and DONT commands for various telnet options.
        """
        try:
            if not self.writer:
                return

            # Check if we support this feature
            supported = option in self.supported_features

            # Get option name for better logging
            option_name = self._get_option_name(option)

            # Handle the command based on its type
            await self._handle_negotiation_by_command_type(
                cmd, option, supported, option_name
            )

            # Check if negotiation is complete
            self._check_negotiation_completion()

        except Exception as e:
            self.logger.error(f"Error in feature negotiation: {e}", exc_info=True)

    async def _handle_negotiation_by_command_type(
        self, cmd: int, option: int, supported: bool, option_name: str
    ) -> None:
        """Handle telnet negotiation based on command type.

        Args:
            cmd: The telnet command (WILL, WONT, DO, DONT)
            option: The telnet option
            supported: Whether we support this feature
            option_name: Human-readable name of the option
        """
        if cmd == TelnetBytes.WILL:
            # Server wants to enable a feature
            await self._handle_will_command(option, supported, option_name)
        elif cmd == TelnetBytes.WONT:
            # Server wants to disable a feature
            await self._handle_wont_command(option, option_name)
        elif cmd == TelnetBytes.DO:
            # Server asks us to enable a feature
            await self._handle_do_command(option, supported, option_name)
        elif cmd == TelnetBytes.DONT:
            # Server asks us to disable a feature
            await self._handle_dont_command(option, option_name)

    async def _handle_will_command(
        self, option: int, supported: bool, option_name: str
    ) -> None:
        """Handle WILL command from server.

        Args:
            option: The telnet option
            supported: Whether we support this feature
            option_name: Human-readable name of the option
        """
        if supported:
            # Accept supported features
            await self._send_do(option)
            self._enable_feature(option)
            self.logger.info(f"Accepted feature {option_name} ({option})")
        else:
            # Reject unsupported features
            await self._send_dont(option)
            self.logger.debug(f"Rejected unsupported feature {option_name} ({option})")

    async def _handle_wont_command(self, option: int, option_name: str) -> None:
        """Handle WONT command from server.

        Args:
            option: The telnet option
            option_name: Human-readable name of the option
        """
        self._disable_feature(option)
        await self._send_dont(option)
        self.logger.debug(f"Server disabled feature {option_name} ({option})")

    async def _handle_do_command(
        self, option: int, supported: bool, option_name: str
    ) -> None:
        """Handle DO command from server.

        Args:
            option: The telnet option
            supported: Whether we support this feature
            option_name: Human-readable name of the option
        """
        if supported:
            await self._send_will(option)
            self._enable_feature(option)
            self.logger.info(
                f"Enabled feature {option_name} ({option}) at server request"
            )
        else:
            await self._send_wont(option)
            self.logger.debug(
                f"Declined to enable unsupported feature {option_name} ({option})"
            )

    async def _handle_dont_command(self, option: int, option_name: str) -> None:
        """Handle DONT command from server.

        Args:
            option: The telnet option
            option_name: Human-readable name of the option
        """
        self._disable_feature(option)
        await self._send_wont(option)
        self.logger.debug(
            f"Disabled feature {option_name} ({option}) at server request"
        )

    def _check_negotiation_completion(self) -> None:
        """Check if protocol negotiation is complete and set event if it is."""
        # We consider negotiation complete if:
        # 1. GMCP is enabled, or
        # 2. MSDP is enabled
        if (
            self.gmcp.enabled or self.msdp.enabled
        ) and not self._negotiation_event.is_set():
            self._negotiation_event.set()
            self.logger.info(
                f"Protocol negotiation completed - GMCP: {self.gmcp.enabled}, MSDP: {self.msdp.enabled}"
            )

    def _get_option_name(self, option: int) -> str:
        """Get a human-readable name for a telnet option."""
        option_names = {
            TelnetBytes.ECHO: "ECHO",
            TelnetBytes.SUPPRESS_GA: "SUPPRESS_GA",
            TelnetBytes.TERMINAL_TYPE: "TERMINAL_TYPE",
            TelnetBytes.NAWS: "NAWS",
            TelnetBytes.CHARSET: "CHARSET",
            TelnetBytes.MSDP: "MSDP",
            TelnetBytes.GMCP: "GMCP",
        }
        return option_names.get(option, f"UNKNOWN({option})")

    def _enable_feature(self, option: int) -> None:
        """Enable a telnet feature."""
        self.supported_features[option] = True
        if option == TelnetBytes.GMCP:
            self.gmcp.enabled = True
        elif option == TelnetBytes.MSDP:
            self.msdp.enabled = True

    def _disable_feature(self, option: int) -> None:
        """Disable a telnet feature."""
        self.supported_features[option] = False
        if option == TelnetBytes.GMCP:
            self.gmcp.enabled = False
        elif option == TelnetBytes.MSDP:
            self.msdp.enabled = False

    async def _send_will(self, option: int) -> None:
        """Send WILL negotiation."""
        if self.writer:
            self.writer.write(bytes([TelnetBytes.IAC, TelnetBytes.WILL, option]))
            await self.writer.drain()

    async def _send_wont(self, option: int) -> None:
        """Send WONT negotiation."""
        if self.writer:
            self.writer.write(bytes([TelnetBytes.IAC, TelnetBytes.WONT, option]))
            await self.writer.drain()

    async def _send_do(self, option: int) -> None:
        """Send DO negotiation."""
        if self.writer:
            self.writer.write(bytes([TelnetBytes.IAC, TelnetBytes.DO, option]))
            await self.writer.drain()

    async def _send_dont(self, option: int) -> None:
        """Send DONT negotiation."""
        if self.writer:
            self.writer.write(bytes([TelnetBytes.IAC, TelnetBytes.DONT, option]))
            await self.writer.drain()

    async def _initialize_protocols(self) -> None:
        """Initialize enabled protocols after negotiation."""
        try:
            # Initialize GMCP if enabled
            if self.gmcp.enabled:
                # Send Core.Hello
                core_hello = {"client": "MUDAgent", "version": "1.0"}
                await self._send_gmcp("Core.Hello", core_hello)

                # Request initial data
                await self._send_gmcp(
                    "Core.Supports.Set", ["Char 1", "Room 1", "Comm 1"]
                )
                logger.info("GMCP initialized")

            # Initialize MSDP if enabled
            if self.msdp.enabled:
                # Request initial data
                # This would depend on the specific MUD's MSDP implementation
                logger.info("MSDP initialized")

            # Log protocol status
            logger.info(
                f"Protocol status - GMCP: {self.gmcp_enabled}, MSDP: {self.msdp_enabled}"
            )

        except Exception as e:
            logger.error(f"Error initializing protocols: {e}")

    async def _send_gmcp(self, module: str, data: Any) -> None:
        """Send a GMCP message to the server.

        Args:
            module: The GMCP module name
            data: The data to send (will be JSON encoded)
        """
        async with self._connection_lock:
            if not self.gmcp.enabled or not self.writer:
                return
            writer = self.writer

        try:
            # Format GMCP message
            if isinstance(data, dict | list):
                message = f"{module} {json.dumps(data)}"
            elif data is None:
                message = module
            else:
                message = f"{module} {data!s}"

            # Send as telnet subnegotiation
            payload = message.encode("utf-8")
            # Escape any IAC (0xFF) bytes in the payload per RFC 854
            payload = payload.replace(b"\xff", b"\xff\xff")
            command = (
                bytes([TelnetBytes.IAC, TelnetBytes.SB, TelnetBytes.GMCP])
                + payload
                + bytes([TelnetBytes.IAC, TelnetBytes.SE])
            )
            writer.write(command)
            await writer.drain()
            logger.debug(f"Sent GMCP: {module}")

        except Exception as e:
            logger.error(f"Error sending GMCP message: {e}")

    async def login(self, character_name: str, password: str) -> bool:
        """Login to the MUD server."""
        if not self.connected:
            logger.error("Not connected to MUD server")
            return False

        try:
            # Clear any existing debug capture
            if hasattr(self, "debug_capture"):
                self.debug_capture = []

            # Send character name
            await self.send_command(character_name)
            await asyncio.sleep(LOGIN_PASSWORD_DELAY)  # Wait for password prompt

            # Send password
            await self.send_command(password)
            await asyncio.sleep(LOGIN_RESPONSE_DELAY)  # Wait for login response

            # Check login success via GMCP if available
            if self.gmcp.enabled:
                char_data = self.gmcp.get_module_data("char")
                if char_data and char_data.get("name") == character_name:
                    logger.info(
                        f"Successfully logged in as {character_name} (verified via GMCP)"
                    )
                    return True

            # If we can't verify via GMCP, check if we received any data after login
            # which would indicate successful login
            if hasattr(self, "debug_capture") and self.debug_capture:
                logger.info(
                    f"Successfully logged in as {character_name} (assumed from server response)"
                )
                return True

            # If we get here, we can't verify login status but we'll assume success
            # Most MUDs will disconnect on failed login, so if we're still connected, login probably succeeded
            logger.info("Login status uncertain but assumed successful")
            return True

        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            return False

    def is_connected(self) -> bool:
        """Check if client is currently connected.

        Returns:
            bool: True if connected, False otherwise
        """
        return (
            self.connected
            and self.writer is not None
            and not self.writer.is_closing()
            and not self.writer.transport.is_closing()
        )

    async def _reader_task(self) -> None:
        """Continuously read and process data from the server.

        This is the main reader task that runs in the background to receive
        and process data from the server. It uses the receive_data method
        to handle the actual data processing.
        """
        self.logger.info("Reader task started")
        try:
            await self.receive_data()
        except asyncio.CancelledError:
            self.logger.info("Reader task cancelled")
        except Exception as e:
            self.logger.error(f"Error in reader task: {e}", exc_info=True)
        finally:
            self.logger.info("Reader task finished")

    async def _keep_alive_task(self) -> None:
        """Keep-alive task to maintain connection with the server.

        This task runs in the background and periodically sends a NOP (no operation)
        telnet command to keep the connection alive when there's no other activity.
        """
        self.logger.info(
            f"Keep-alive task started with interval {self.keep_alive_interval}s"
        )
        try:
            while self.connected and self.writer is not None:
                # Wait for the keep-alive interval
                await asyncio.sleep(self.keep_alive_interval)

                # Check if we're still connected
                if not self.connected or self.writer is None:
                    self.logger.info("Connection lost, stopping keep-alive task")
                    break

                # Check if we need to send a keep-alive packet
                current_time = time.time()
                time_since_last_sent = current_time - self.last_sent_time
                time_since_last_received = current_time - self.last_data_time

                # Only send keep-alive if there's been no activity in either direction
                if (
                    time_since_last_sent >= self.keep_alive_interval
                    and time_since_last_received >= self.keep_alive_interval
                ):
                    self.logger.info(
                        f"Sending keep-alive packet (no activity for {time_since_last_sent:.1f}s)"
                    )
                    try:
                        await self._send_nop()
                        self.last_sent_time = time.time()
                        self.logger.debug(
                            f"Keep-alive packet sent successfully, updated last_sent_time to {self.last_sent_time}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error sending keep-alive packet: {e}", exc_info=True
                        )
                else:
                    self.logger.debug(
                        f"Skipping keep-alive, recent activity detected (sent: {time_since_last_sent:.1f}s ago, received: {time_since_last_received:.1f}s ago)"
                    )

                # Check if the connection is dead (no data received for too long)
                if time_since_last_received > KEEP_ALIVE_TIMEOUT:
                    self.logger.warning(
                        f"Connection appears to be dead (no data received for {time_since_last_received:.1f}s)"
                    )
                    self.events.emit("connection_timeout", time_since_last_received)

                    # Try to reconnect
                    try:
                        self.logger.info("Attempting to reconnect...")
                        await self.disconnect()
                        reconnected = await self.connect(self.host, self.port)
                        if reconnected:
                            self.logger.info("Successfully reconnected")
                            self.events.emit("reconnected")
                        else:
                            self.logger.error("Failed to reconnect")
                            self.events.emit("reconnect_failed")
                            break
                    except Exception as e:
                        self.logger.error(
                            f"Error during reconnection attempt: {e}", exc_info=True
                        )
                        self.events.emit("reconnect_failed", str(e))
                        break
        except asyncio.CancelledError:
            self.logger.info("Keep-alive task cancelled")
        except Exception as e:
            self.logger.error(f"Error in keep-alive task: {e}", exc_info=True)
        finally:
            self.logger.info("Keep-alive task finished")

    async def _send_nop(self) -> None:
        """Send a NOP (no operation) telnet command.

        This is used as a keep-alive mechanism to maintain the connection.
        The NOP command is a harmless command that does nothing but confirms
        the connection is still active.
        """
        if not self.connected or self.writer is None:
            raise ConnectionError("Not connected to server")

        try:
            # IAC NOP sequence (255 241)
            nop_command = bytes([TelnetBytes.IAC, TelnetBytes.NOP])
            self.writer.write(nop_command)
            await asyncio.wait_for(self.writer.drain(), timeout=5.0)
            self.logger.debug("Sent NOP keep-alive command")
        except Exception as e:
            self.logger.error(f"Error sending NOP command: {e}", exc_info=True)
            raise
