"""Tests for textual_app events module."""

from textual.events import Event

from mud_agent.utils.textual_app.events import (
    CommandEvent,
    GMCPEvent,
    ServerMessageEvent,
    StateUpdateEvent,
)


class TestStateUpdateEvent:
    """Tests for the StateUpdateEvent class."""

    def test_init_with_data(self) -> None:
        """Test that the event can be initialized with data."""
        event = StateUpdateEvent(data={"key": "value"})
        assert event.data == {"key": "value"}
        assert isinstance(event, Event)

    def test_init_with_no_data(self) -> None:
        """Test that the event can be initialized with no data."""
        event = StateUpdateEvent()
        assert event.data is None
        assert isinstance(event, Event)


class TestCommandEvent:
    """Tests for the CommandEvent class."""

    def test_init(self) -> None:
        """Test that the event can be initialized with a command."""
        event = CommandEvent(command="test command")
        assert event.command == "test command"
        assert isinstance(event, Event)


class TestServerMessageEvent:
    """Tests for the ServerMessageEvent class."""

    def test_init(self) -> None:
        """Test that the event can be initialized with a message."""
        event = ServerMessageEvent(message="test message")
        assert event.message == "test message"
        assert isinstance(event, Event)


class TestGMCPEvent:
    """Tests for the GMCPEvent class."""

    def test_init_with_data(self) -> None:
        """Test that the event can be initialized with a package and data."""
        event = GMCPEvent(package="test.package", data={"key": "value"})
        assert event.package == "test.package"
        assert event.data == {"key": "value"}
        assert isinstance(event, Event)

    def test_init_with_no_data(self) -> None:
        """Test that the event can be initialized with a package and no data."""
        event = GMCPEvent(package="test.package")
        assert event.package == "test.package"
        assert event.data is None
        assert isinstance(event, Event)
