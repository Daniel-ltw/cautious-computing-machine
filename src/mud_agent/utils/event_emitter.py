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
        self._pending_tasks: set[asyncio.Task] = set()
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

    def _schedule_coroutine(self, coro, event: str) -> None:
        """Schedule a coroutine as a tracked task.

        Args:
            coro: The coroutine to schedule
            event: The event name (for logging)
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)

        def _on_done(t: asyncio.Task, _event: str = event) -> None:
            self._pending_tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc:
                self.logger.error(
                    f"Error in async event listener for '{_event}': {exc}",
                    exc_info=exc,
                )

        task.add_done_callback(_on_done)

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
                    if asyncio.iscoroutine(result):
                        self._schedule_coroutine(result, event)
                except Exception as e:
                    self.logger.error(
                        f"Error in event listener for '{event}': {e}", exc_info=True
                    )

        # Call one-time listeners
        if event in self._once_listeners:
            listeners = self._once_listeners[event].copy()
            self._once_listeners[event] = []
            for callback in listeners:
                try:
                    result = callback(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        self._schedule_coroutine(result, event)
                except Exception as e:
                    self.logger.error(
                        f"Error in one-time event listener for '{event}': {e}",
                        exc_info=True,
                    )

        # Log the event if it's not a high-frequency event
        if event not in {"data", "tick", "gmcp_data"}:
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
        if event not in {"data", "tick", "gmcp_data"}:
            self.logger.debug(f"Emitted async event '{event}'")

    async def cancel_pending_tasks(self) -> None:
        """Cancel all pending async tasks created by emit().

        Call this during shutdown to ensure no orphaned tasks remain.
        """
        if not self._pending_tasks:
            return
        self.logger.debug(f"Cancelling {len(self._pending_tasks)} pending event tasks")
        for task in list(self._pending_tasks):
            if not task.done():
                task.cancel()
        # Wait briefly for cancellation to propagate
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        self._pending_tasks.clear()
