"""
State listener widget for the MUD agent.

This module provides a base widget that listens for state events and updates accordingly.
"""

import logging
from typing import Any

from textual.widget import Widget

logger = logging.getLogger(__name__)


class StateListener(Widget):
    """Base widget that listens for state events.

    This widget provides a base class for widgets that need to listen for state events.
    It handles registering for events and provides methods for handling different types
    of state events.
    """

    def on_mount(self) -> None:
        """Called when the widget is mounted.

        This method registers for state events from the state manager.
        """

        # Register for state events if the app and state manager are available
        if hasattr(self, "app"):
            # Try to find the state manager in different places
            state_manager = None

            # First check if it's directly in the app
            if hasattr(self.app, "state_manager"):
                state_manager = self.app.state_manager
                logger.debug(f"{self.__class__.__name__} found state_manager in app")

            # Then check if it's in the agent
            elif hasattr(self.app, "agent") and hasattr(
                self.app.agent, "state_manager"
            ):
                state_manager = self.app.agent.state_manager
                logger.debug(
                    f"{self.__class__.__name__} found state_manager in app.agent"
                )

            # If we found a state manager, register for events
            if state_manager and hasattr(state_manager, "events"):
                # Register for state events
                self._register_state_events(state_manager)
                logger.debug(f"{self.__class__.__name__} registered for state events")
            else:
                logger.warning(
                    f"{self.__class__.__name__}: State manager not found or does not have events property"
                )
        else:
            logger.warning(f"{self.__class__.__name__}: App not available")

    def _register_state_events(self, state_manager) -> None:
        """Register for state events.

        This method registers for state events from the state manager.
        Override this method in subclasses to register for specific events.

        Args:
            state_manager: The state manager to register with
        """
        # Register for general state update event
        state_manager.events.on("state_update", self._on_state_update)

        # Register for specific state events based on the widget type
        if (
            hasattr(self, "register_for_character_events")
            and self.register_for_character_events
        ):
            state_manager.events.on("character_update", self._on_character_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on(
                    "character_update", self._on_character_update
                )

        if (
            hasattr(self, "register_for_vitals_events")
            and self.register_for_vitals_events
        ):
            state_manager.events.on("vitals_update", self._on_vitals_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on(
                    "vitals_update", self._on_vitals_update
                )

        if (
            hasattr(self, "register_for_stats_events")
            and self.register_for_stats_events
        ):
            state_manager.events.on("stats_update", self._on_stats_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on("stats_update", self._on_stats_update)

        if (
            hasattr(self, "register_for_maxstats_events")
            and self.register_for_maxstats_events
        ):
            state_manager.events.on("maxstats_update", self._on_maxstats_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on(
                    "maxstats_update", self._on_maxstats_update
                )

        if (
            hasattr(self, "register_for_worth_events")
            and self.register_for_worth_events
        ):
            state_manager.events.on("worth_update", self._on_worth_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on("worth_update", self._on_worth_update)

        if hasattr(self, "register_for_room_events") and self.register_for_room_events:
            logger.debug(f"{self.__class__.__name__} registering for room_update events")
            state_manager.events.on("room_update", self._on_room_update)
            # Also register with room component if available
            if hasattr(state_manager, "room") and hasattr(state_manager.room, "events"):
                state_manager.room.events.on("room_update", self._on_room_update)
                logger.debug(f"{self.__class__.__name__} also registered with room component events")
            logger.debug(f"{self.__class__.__name__} room event registration completed")

        if hasattr(self, "register_for_map_events") and self.register_for_map_events:
            state_manager.events.on("map_update", self._on_map_update)
            # Also register with room component if available
            if hasattr(state_manager, "room") and hasattr(state_manager.room, "events"):
                state_manager.room.events.on("map_update", self._on_map_update)

        # Quest events removed

        if (
            hasattr(self, "register_for_status_events")
            and self.register_for_status_events
        ):
            state_manager.events.on("status_update", self._on_status_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on(
                    "status_update", self._on_status_update
                )

        if (
            hasattr(self, "register_for_combat_events")
            and self.register_for_combat_events
        ):
            state_manager.events.on("combat_update", self._on_combat_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on(
                    "combat_update", self._on_combat_update
                )

        if (
            hasattr(self, "register_for_needs_events")
            and self.register_for_needs_events
        ):
            state_manager.events.on("needs_update", self._on_needs_update)
            # Also register with character component if available
            if hasattr(state_manager, "character") and hasattr(
                state_manager.character, "events"
            ):
                state_manager.character.events.on("needs_update", self._on_needs_update)

    def _on_state_update(self, updates: dict[str, Any]) -> None:
        """Handle a general state update event.

        Args:
            updates: Dictionary of updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle state updates
        pass

    def _on_character_update(self, updates: dict[str, Any]) -> None:
        """Handle a character update event.

        Args:
            updates: Dictionary of character updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle character updates
        pass

    def _on_vitals_update(self, updates: dict[str, Any]) -> None:
        """Handle a vitals update event.

        Args:
            updates: Dictionary of vitals updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle vitals updates
        pass

    def _on_stats_update(self, updates: dict[str, Any]) -> None:
        """Handle a stats update event.

        Args:
            updates: Dictionary of stats updates
        """
        logger.info(f"{self.__class__.__name__} received stats update: {updates}")
        # Default implementation does nothing
        # Override this method in subclasses to handle stats updates
        pass

    def _on_maxstats_update(self, updates: dict[str, Any]) -> None:
        """Handle a maxstats update event.

        Args:
            updates: Dictionary of maxstats updates
        """
        logger.info(f"{self.__class__.__name__} received maxstats update: {updates}")
        # Default implementation does nothing
        # Override this method in subclasses to handle maxstats updates
        pass

    def _on_worth_update(self, updates: dict[str, Any]) -> None:
        """Handle a worth update event.

        Args:
            updates: Dictionary of worth updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle worth updates
        pass

    def _on_room_update(self, updates: dict[str, Any]) -> None:
        """Handle a room update event.

        Args:
            updates: Dictionary of room updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle room updates
        pass

    def _on_map_update(self, map_data: str) -> None:
        """Handle a map update event.

        Args:
            map_data: Map data
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle map updates
        pass

    # Quest update method removed

    def _on_status_update(self, updates: dict[str, Any]) -> None:
        """Handle a status update event.

        Args:
            updates: Dictionary of status updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle status updates
        pass

    def _on_combat_update(self, in_combat: bool) -> None:
        """Handle a combat update event.

        Args:
            in_combat: Whether the character is in combat
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle combat updates
        pass

    def _on_needs_update(self, updates: dict[str, Any]) -> None:
        """Handle a needs update event.

        Args:
            updates: Dictionary of needs updates
        """
        # Default implementation does nothing
        # Override this method in subclasses to handle needs updates
        pass
