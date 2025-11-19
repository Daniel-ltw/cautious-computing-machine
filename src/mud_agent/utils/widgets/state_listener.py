"""
State listener widget for the MUD agent.

This module provides a base widget that listens for state events and updates accordingly.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StateListener:
    """Base widget that listens for state events.

    This widget provides a base class for widgets that need to listen for state events.
    It handles registering for events and provides methods for handling different types
    of state events.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscribed_keys = set()
        self.state_manager = None

    def subscribe_to_state(self, state_key: str) -> None:
        """Subscribes to a state key."""
        self.subscribed_keys.add(state_key)

    def unsubscribe_from_state(self, state_key: str) -> None:
        """Unsubscribes from a state key."""
        self.subscribed_keys.discard(state_key)

    def clear_subscriptions(self) -> None:
        """Clears all state subscriptions."""
        self.subscribed_keys.clear()

    def on_state_update(self, state_key: str, data: Any) -> None:
        """Handle state updates synchronously with async compatibility."""
        if state_key in self.subscribed_keys:
            update = getattr(self, "update_display", None)
            if update:
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(update):
                        try:
                            asyncio.get_running_loop()
                            import contextlib
                            _task = asyncio.create_task(update(data))
                            with contextlib.suppress(Exception):
                                self._update_task = _task
                        except RuntimeError:
                            pass
                    else:
                        update(data)
                except Exception:
                    pass

    async def on_state_update_async(self, state_key: str, data: Any) -> None:
        """Async variant for tests and async listeners."""
        if state_key in self.subscribed_keys:
            await self.update_display(data)

    def get_state_data(self, state_key: str) -> Any:
        """Gets the current state data for a key."""
        if self.state_manager:
            return self.state_manager.get_state(state_key)
        return None

    def register_with_state_manager(self, state_manager: Any | None = None) -> None:
        """Register the widget with the state manager."""
        if state_manager is not None:
            self.state_manager = state_manager
        if self.state_manager:
            self.state_manager.register_listener(self.id, self.on_state_update)
            try:
                events = getattr(self.state_manager, "events", None)
                if events:
                    if hasattr(self, "_on_state_update"):
                        events.on("state_update", lambda updates: self._on_state_update(updates))
                    if hasattr(self, "_on_room_update") or getattr(self, "register_for_room_events", False):
                        events.on(
                            "room_update",
                            lambda *args, **kwargs: self._dispatch_room_update(*args, **kwargs),
                        )
                    if getattr(self, "register_for_worth_events", False) and hasattr(self, "_on_worth_update"):
                        events.on("worth_update", lambda updates: self._on_worth_update(updates))
                    if getattr(self, "register_for_stats_events", False) and hasattr(self, "_on_stats_update"):
                        events.on("stats_update", lambda updates: self._on_stats_update(updates))
                    if getattr(self, "register_for_maxstats_events", False) and hasattr(self, "_on_maxstats_update"):
                        events.on("maxstats_update", lambda updates: self._on_maxstats_update(updates))
                    if getattr(self, "register_for_status_events", False):
                        events.on(
                            "status_update",
                            lambda payload: self.on_state_update("status_effects", payload.get("status_effects", payload)),
                        )
                    if getattr(self, "register_for_needs_events", False) and hasattr(self, "_on_needs_update"):
                        events.on("needs_update", lambda updates: self._on_needs_update(updates))
            except Exception:
                pass

    def unregister_from_state_manager(self) -> None:
        """Unregisters the widget from the state manager."""
        if self.state_manager:
            self.state_manager.unregister_listener(self.id)

    def is_subscribed_to(self, state_key: str) -> bool:
        """Checks if the widget is subscribed to a state key."""
        return state_key in self.subscribed_keys

    def get_subscribed_keys(self) -> list[str]:
        """Gets the list of subscribed keys."""
        return list(self.subscribed_keys)







    def update_display(self, data: Any) -> None:
        """Updates the display with the new data.

        This method should be implemented by subclasses to update the display
        with the new data.

        Args:
            data: The new data
        """
        raise NotImplementedError("update_display must be implemented by subclasses")

    def _dispatch_room_update(self, *args: Any, **kwargs: Any) -> None:
        handler = getattr(self, "_on_room_update", None)
        if not handler:
            return
        room_data = None
        if "room_data" in kwargs:
            room_data = kwargs["room_data"]
        elif args and isinstance(args[0], dict):
            room_data = args[0]
        elif kwargs:
            room_data = kwargs
        if room_data is not None:
            handler(room_data=room_data)
