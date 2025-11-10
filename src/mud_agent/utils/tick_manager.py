"""
Tick manager for MUD Agent.

This module provides a tick manager that synchronizes updates with the game's tick system.
"""

import logging
import queue
import re
import threading
import time
from collections.abc import Callable

# Constants for tick management
DEFAULT_TICK_INTERVAL = 5.0  # Default tick interval in seconds
TICK_INTERVAL_WEIGHT_OLD = 0.8  # Weight for old tick interval in weighted average
TICK_INTERVAL_WEIGHT_NEW = 0.2  # Weight for new tick interval in weighted average
TICK_DETECTION_THRESHOLD = (
    0.5  # Threshold for detecting new ticks (fraction of interval)
)
SYNTHETIC_TICK_THRESHOLD = (
    1.5  # Threshold for generating synthetic ticks (multiple of interval)
)
THREAD_JOIN_TIMEOUT = 2.0  # Timeout for joining the tick thread when stopping
THREAD_SLEEP_INTERVAL = 0.01  # Sleep interval to avoid high CPU usage
ZERO = 0.0  # Zero constant for comparisons


class TickManager:
    """Manages game ticks and synchronizes updates with the game's tick system."""

    def __init__(self, config, event_manager):
        """Initialize the tick manager.

        Args:
            config: The application configuration.
            event_manager: The event manager for decoupled communication.
        """
        self.config = config
        self.events = event_manager
        self.logger = logging.getLogger(__name__)

        # Tick tracking
        self.tick_interval = (
            DEFAULT_TICK_INTERVAL  # Will be adjusted based on observations
        )
        self.last_tick_time = ZERO
        self.tick_count = 0
        self.tick_pattern = []  # Will be set based on the MUD
        self.tick_detected = False

        # Tick detection patterns for different MUDs
        self.tick_patterns = {
            "aardmud": [
                r"(?:Tick|TICK)!",
                r"It is now the (?:hour|minute) of .*",
                r"Time passes...",
                r"The clock strikes .*",
            ],
            "generic": [
                r"(?:Tick|TICK)!",
                r"Time passes...",
                r"A new (?:hour|minute|day) begins",
                r"The clock strikes .*",
                r"You feel refreshed as a new (?:hour|minute|day) begins",
            ],
        }

        # Queue for tick notifications
        self.tick_queue = queue.Queue()

        # Queue for async operations
        self.async_queue = queue.Queue()

        # Thread
        self.tick_thread = None
        self.running = False

        # Callbacks to execute on tick
        self.tick_callbacks = []

        # Thread lock
        self.lock = threading.Lock()

    def start(self):
        """Start the tick manager thread."""
        try:
            self.running = True

            # Determine the tick pattern based on the MUD
            mud_type = getattr(self.config.mud, "type", "generic").lower()
            self.tick_pattern = self.tick_patterns.get(
                mud_type, self.tick_patterns["generic"]
            )
            self.logger.debug(f"Using tick pattern for MUD type: {mud_type}")

            # Start the tick thread
            self.tick_thread = threading.Thread(
                target=self._run_tick_manager, daemon=True
            )
            self.tick_thread.start()
            self.logger.info("Tick manager thread started")
        except Exception as e:
            self.logger.error(f"Error starting tick manager thread: {e}", exc_info=True)

    def stop(self):
        """Stop the tick manager thread."""
        try:
            self.running = False

            # Wait for the thread to terminate
            if self.tick_thread and self.tick_thread.is_alive():
                self.tick_thread.join(timeout=THREAD_JOIN_TIMEOUT)

            self.logger.info("Tick manager thread stopped")
        except Exception as e:
            self.logger.error(f"Error stopping tick manager thread: {e}", exc_info=True)

    def register_tick_callback(self, callback: Callable):
        """Register a callback to be executed on tick.

        Args:
            callback: The callback function to execute on tick
        """
        with self.lock:
            self.tick_callbacks.append(callback)

    def unregister_tick_callback(self, callback: Callable):
        """Unregister a tick callback.

        Args:
            callback: The callback function to unregister
        """
        with self.lock:
            if callback in self.tick_callbacks:
                self.tick_callbacks.remove(callback)

    def process_server_response(self, response: str):
        """Process a server response to detect ticks.

        Args:
            response: The response from the MUD server
        """
        try:
            # Check for tick indicators in the response
            for pattern in self.tick_pattern:
                if re.search(pattern, response, re.IGNORECASE):
                    self._handle_tick_detected()
                    break
        except Exception as e:
            self.logger.error(
                f"Error processing server response for ticks: {e}", exc_info=True
            )

    def _handle_tick_detected(self):
        """Handle a detected tick."""
        try:
            current_time = time.time()

            # Only process if this is a new tick (not a duplicate detection)
            if (
                current_time - self.last_tick_time
                > self.tick_interval * TICK_DETECTION_THRESHOLD
            ):
                with self.lock:
                    # Update tick tracking
                    if self.last_tick_time > ZERO:
                        # Calculate the new tick interval based on the time since the last tick
                        new_interval = current_time - self.last_tick_time

                        # Use a weighted average to smooth out variations
                        self.tick_interval = (
                            self.tick_interval * TICK_INTERVAL_WEIGHT_OLD
                        ) + (new_interval * TICK_INTERVAL_WEIGHT_NEW)
                        self.logger.debug(
                            f"Updated tick interval: {self.tick_interval:.2f} seconds"
                        )

                    self.last_tick_time = current_time
                    self.tick_count += 1
                    self.tick_detected = True

                    # Add to the tick queue
                    self.tick_queue.put(self.tick_count)

                    self.logger.debug(
                        f"Tick detected! Count: {self.tick_count}, Interval: {self.tick_interval:.2f}s"
                    )

                    # Emit a tick event instead of directly calling a handler
                    self.events.emit("tick", self.tick_count)
                    self.logger.debug(
                        f"Emitted tick event for tick {self.tick_count}"
                    )
        except Exception as e:
            self.logger.error(f"Error handling tick detection: {e}", exc_info=True)

    def get_async_operations(self):
        """Get all pending async operations from the queue.

        Returns:
            list: A list of tick counts for which async operations are pending
        """
        operations = []
        try:
            # Get all items from the queue without blocking
            while not self.async_queue.empty():
                operations.append(self.async_queue.get_nowait())
        except queue.Empty:
            pass

        return operations

    def _run_tick_manager(self):
        """Run the tick manager thread."""
        try:
            self.logger.debug("Tick manager thread started")

            # Initialize the last tick time
            self.last_tick_time = time.time()

            # Main loop
            while self.running:
                try:
                    # Check for ticks in the queue
                    try:
                        tick_count = self.tick_queue.get_nowait()

                        # Execute callbacks
                        with self.lock:
                            for callback in self.tick_callbacks:
                                try:
                                    callback(tick_count)
                                except Exception as e:
                                    self.logger.error(
                                        f"Error executing tick callback: {e}",
                                        exc_info=True,
                                    )
                    except queue.Empty:
                        pass

                    # If no tick has been detected for a while, generate a synthetic tick
                    current_time = time.time()
                    if (
                        self.last_tick_time > ZERO
                        and current_time - self.last_tick_time
                        > self.tick_interval * SYNTHETIC_TICK_THRESHOLD
                    ):
                        self.logger.debug("Generating synthetic tick due to timeout")
                        self._handle_tick_detected()

                    # Sleep a bit to avoid high CPU usage
                    time.sleep(THREAD_SLEEP_INTERVAL)

                except Exception as e:
                    self.logger.error(
                        f"Error in tick manager thread: {e}", exc_info=True
                    )

            self.logger.debug("Tick manager thread stopped")

        except Exception as e:
            self.logger.error(f"Fatal error in tick manager thread: {e}", exc_info=True)
