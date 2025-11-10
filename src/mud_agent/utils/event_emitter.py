"""
Event emitter for the MUD agent.

This module provides a simple event emitter implementation for the MUD agent.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventEmitter:
    """Simple event emitter implementation.

    This class provides a way to emit events and register listeners for those events.
    It supports both synchronous and asynchronous listeners.
    """

    def __init__(self):
        """Initialize the event emitter."""
        self._listeners: dict[str, list[Callable]] = {}
        self._once_listeners: dict[str, list[Callable]] = {}
        self.logger = logging.getLogger(__name__)

    def on(self, event: str, callback: Callable) -> None:
        """Register a listener for an event.

        Args:
            event: The event to listen for
            callback: The callback function to call when the event is emitted
        """
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
        self.logger.debug(f"Registered listener for event '{event}'")

    def once(self, event: str, callback: Callable) -> None:
        """Register a one-time listener for an event.

        Args:
            event: The event to listen for
            callback: The callback function to call when the event is emitted
        """
        if event not in self._once_listeners:
            self._once_listeners[event] = []
        self._once_listeners[event].append(callback)
        self.logger.debug(f"Registered one-time listener for event '{event}'")

    def off(self, event: str, callback: Callable | None = None) -> None:
        """Remove a listener for an event.

        Args:
            event: The event to remove the listener from
            callback: The callback function to remove. If None, all listeners for the event are removed.
        """
        if callback is None:
            # Remove all listeners for the event
            if event in self._listeners:
                self._listeners[event] = []
            if event in self._once_listeners:
                self._once_listeners[event] = []
            self.logger.debug(f"Removed all listeners for event '{event}'")
        else:
            # Remove a specific listener
            if event in self._listeners and callback in self._listeners[event]:
                self._listeners[event].remove(callback)
                self.logger.debug(f"Removed listener for event '{event}'")
            if (
                event in self._once_listeners
                and callback in self._once_listeners[event]
            ):
                self._once_listeners[event].remove(callback)
                self.logger.debug(f"Removed one-time listener for event '{event}'")

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event.

        Args:
            event: The event to emit
            *args: Positional arguments to pass to the listeners
            **kwargs: Keyword arguments to pass to the listeners
        """
        # Call regular listeners
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    result = callback(*args, **kwargs)
                    # If the callback returns a coroutine, schedule it
                    if asyncio.iscoroutine(result):
                        # Create a task with proper error handling
                        task = asyncio.create_task(result)
                        # Add error handling for the task
                        task.add_done_callback(
                            lambda t: self.logger.error(
                                f"Error in async event listener for '{event}': {t.exception()}",
                                exc_info=t.exception(),
                            )
                            if t.exception()
                            else None
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error in event listener for '{event}': {e}", exc_info=True
                    )
                    # Continue processing other listeners even if one fails

        # Call one-time listeners
        if event in self._once_listeners:
            # Make a copy of the listeners to avoid modifying the list while iterating
            listeners = self._once_listeners[event].copy()
            # Clear the list before calling the listeners to prevent recursion issues
            self._once_listeners[event] = []
            for callback in listeners:
                try:
                    result = callback(*args, **kwargs)
                    # If the callback returns a coroutine, schedule it
                    if asyncio.iscoroutine(result):
                        # Create a task with proper error handling
                        task = asyncio.create_task(result)
                        # Add error handling for the task
                        task.add_done_callback(
                            lambda t: self.logger.error(
                                f"Error in async one-time event listener for '{event}': {t.exception()}",
                                exc_info=t.exception(),
                            )
                            if t.exception()
                            else None
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error in one-time event listener for '{event}': {e}",
                        exc_info=True,
                    )

        # Log the event if it's not a high-frequency event
        if event not in ["data", "tick", "gmcp_data"]:
            self.logger.debug(f"Emitted event '{event}'")

    async def emit_async(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event and wait for all async listeners to complete.

        Args:
            event: The event to emit
            *args: Positional arguments to pass to the listeners
            **kwargs: Keyword arguments to pass to the listeners
        """
        tasks = []

        # Call regular listeners
        if event in self._listeners:
            for callback in self._listeners[event]:
                try:
                    result = callback(*args, **kwargs)
                    # If the callback returns a coroutine, add it to the tasks
                    if asyncio.iscoroutine(result):
                        tasks.append(result)
                except Exception as e:
                    self.logger.error(
                        f"Error in event listener for '{event}': {e}", exc_info=True
                    )

        # Call one-time listeners
        if event in self._once_listeners:
            # Make a copy of the listeners to avoid modifying the list while iterating
            listeners = self._once_listeners[event].copy()
            # Clear the list before calling the listeners to prevent recursion issues
            self._once_listeners[event] = []
            for callback in listeners:
                try:
                    result = callback(*args, **kwargs)
                    # If the callback returns a coroutine, add it to the tasks
                    if asyncio.iscoroutine(result):
                        tasks.append(result)
                except Exception as e:
                    self.logger.error(
                        f"Error in one-time event listener for '{event}': {e}",
                        exc_info=True,
                    )

        # Wait for all async tasks to complete
        if tasks:
            await asyncio.gather(*tasks)

        # Log the event if it's not a high-frequency event
        if event not in ["data", "tick", "gmcp_data"]:
            self.logger.debug(f"Emitted async event '{event}'")
