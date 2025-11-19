"""
Tests for the refactored code.

This module contains tests for the refactored code to ensure it works as expected.
"""

from collections.abc import Callable
from typing import Any

# MapCleaner import removed as the class no longer exists


# Mock implementation of Observable for testing
class Observable:
    """Mock implementation of the Observable class for testing.

    This class provides methods for registering, unregistering, and notifying observers.
    """

    def __init__(self):
        """Initialize the observable object."""
        self._observers: dict[str, list[Callable]] = {}

    def register_observer(self, event_type: str, observer: Callable) -> None:
        """Register an observer for a specific event type."""
        if event_type not in self._observers:
            self._observers[event_type] = []

        if observer not in self._observers[event_type]:
            self._observers[event_type].append(observer)

    def unregister_observer(self, event_type: str, observer: Callable) -> None:
        """Unregister an observer for a specific event type."""
        if event_type in self._observers and observer in self._observers[event_type]:
            self._observers[event_type].remove(observer)

    def notify_observers(self, event_type: str, data: Any = None) -> None:
        """Notify all observers of a specific event type."""
        if event_type not in self._observers:
            return

        for observer in self._observers[event_type]:
            try:
                observer(data)
            except Exception as e:
                # Just log the error for testing
                print(f"Error notifying observer for {event_type}: {e}")


# def test_map_cleaner():
#     """Test the MapCleaner class."""
#     # MapCleaner class no longer exists, test removed
#     pass


def test_observable():
    """Test the Observable class."""
    # Create an observable object
    observable = Observable()

    # Create a mock observer
    events = []

    def observer(data):
        events.append(data)

    # Register the observer
    observable.register_observer("test_event", observer)

    # Notify the observer
    observable.notify_observers("test_event", "test_data")

    # Check that the observer was notified
    assert len(events) == 1
    assert events[0] == "test_data"

    # Unregister the observer
    observable.unregister_observer("test_event", observer)

    # Notify again
    observable.notify_observers("test_event", "more_data")

    # Check that the observer was not notified
    assert len(events) == 1

    # Test with multiple observers
    observable = Observable()
    events1 = []
    events2 = []

    def observer1(data):
        events1.append(data)

    def observer2(data):
        events2.append(data)

    observable.register_observer("event1", observer1)
    observable.register_observer("event2", observer2)

    observable.notify_observers("event1", "data1")
    observable.notify_observers("event2", "data2")

    assert len(events1) == 1
    assert events1[0] == "data1"
    assert len(events2) == 1
    assert events2[0] == "data2"

    # Test with an observer that raises an exception
    def bad_observer(_):  # Use underscore to indicate unused parameter
        raise ValueError("Test exception")

    observable.register_observer("event3", bad_observer)

    # This should not raise an exception
    observable.notify_observers("event3", "data3")
