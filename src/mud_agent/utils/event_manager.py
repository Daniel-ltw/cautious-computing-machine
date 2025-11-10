"""
Event Manager for MUD Agent.

This module provides a simple event bus for decoupled communication between components.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventManager:
    """A simple event manager for asynchronous applications."""

    def __init__(self):
        self._listeners: defaultdict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = defaultdict(list)
        self._waiting: defaultdict[str, list[asyncio.Future]] = defaultdict(list)

    def on(self, event_name: str, listener: Callable[..., Coroutine[Any, Any, None]]) -> None:
        """Register an event listener."""
        self._listeners[event_name].append(listener)
        logger.debug(f"Listener {listener.__name__} registered for event '{event_name}'")

    def off(self, event_name: str, listener: Callable[..., Coroutine[Any, Any, None]]) -> None:
        """Unregister an event listener."""
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(listener)
                logger.debug(f"Listener {listener.__name__} unregistered from event '{event_name}'")
            except ValueError:
                logger.warning(
                    f"Attempted to unregister a non-existent listener "
                    f"{listener.__name__} from event '{event_name}'"
                )

    async def emit(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """Emit an event and call all registered listeners."""
        if event_name in self._listeners:
            logger.debug(f"Emitting event '{event_name}' with args: {args}, kwargs: {kwargs}")
            tasks = [
                listener(*args, **kwargs) for listener in self._listeners[event_name]
            ]
            await asyncio.gather(*tasks)

        if event_name in self._waiting:
            for future in self._waiting[event_name]:
                if not future.done():
                    future.set_result(args or kwargs or True)
            self._waiting[event_name].clear()

    async def wait(self, event_name: str) -> Any:
        """Wait for an event to be emitted."""
        future = asyncio.get_running_loop().create_future()
        self._waiting[event_name].append(future)
        logger.debug(f"Waiting for event '{event_name}'")
        return await future