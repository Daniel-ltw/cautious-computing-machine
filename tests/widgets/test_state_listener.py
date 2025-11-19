"""Tests for widgets state_listener module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from textual.widgets import Static

from mud_agent.utils.widgets.state_listener import StateListener


class TestStateListener:
    """Test cases for StateListener mixin class."""

    @pytest.fixture
    def mock_widget(self):
        """Create a mock widget with StateListener mixin."""
        class MockWidget(Static, StateListener):
            def __init__(self):
                super().__init__()
                StateListener.__init__(self)
                self.id = "test_widget"

            def update_display(self, data):
                """Mock update display method."""
                pass

        widget = MockWidget()
        widget.state_manager = Mock()
        return widget

    def test_state_listener_init(self, mock_widget):
        """Test StateListener initialization."""
        assert hasattr(mock_widget, 'state_manager')
        assert hasattr(mock_widget, 'subscribed_keys')
        assert isinstance(mock_widget.subscribed_keys, set)

    def test_subscribe_to_state(self, mock_widget):
        """Test subscribing to state updates."""
        state_key = "character.vitals"
        mock_widget.subscribe_to_state(state_key)
        assert state_key in mock_widget.subscribed_keys

    def test_subscribe_multiple_keys(self, mock_widget):
        """Test subscribing to multiple state keys."""
        keys = ["character.vitals", "character.stats", "room.info"]
        for key in keys:
            mock_widget.subscribe_to_state(key)

        for key in keys:
            assert key in mock_widget.subscribed_keys
        assert len(mock_widget.subscribed_keys) == 3

    def test_unsubscribe_from_state(self, mock_widget):
        """Test unsubscribing from state updates."""
        state_key = "character.vitals"
        mock_widget.subscribe_to_state(state_key)
        assert state_key in mock_widget.subscribed_keys

        mock_widget.unsubscribe_from_state(state_key)
        assert state_key not in mock_widget.subscribed_keys

    def test_unsubscribe_nonexistent_key(self, mock_widget):
        """Test unsubscribing from a key that wasn't subscribed."""
        state_key = "nonexistent.key"
        # Should not raise an error
        mock_widget.unsubscribe_from_state(state_key)
        assert state_key not in mock_widget.subscribed_keys

    def test_clear_subscriptions(self, mock_widget):
        """Test clearing all subscriptions."""
        keys = ["character.vitals", "character.stats", "room.info"]
        for key in keys:
            mock_widget.subscribe_to_state(key)

        assert len(mock_widget.subscribed_keys) == 3
        mock_widget.clear_subscriptions()
        assert len(mock_widget.subscribed_keys) == 0

    def test_on_state_update_subscribed_key(self, mock_widget):
        """Test handling state update for subscribed key."""
        state_key = "character.vitals"
        test_data = {"hp": 100, "mp": 50}

        mock_widget.subscribe_to_state(state_key)

        with patch.object(mock_widget, 'update_display') as mock_update:
            mock_widget.on_state_update(state_key, test_data)
            mock_update.assert_called_once_with(test_data)

    def test_on_state_update_unsubscribed_key(self, mock_widget):
        """Test handling state update for unsubscribed key."""
        state_key = "character.vitals"
        test_data = {"hp": 100, "mp": 50}

        # Don't subscribe to the key

        with patch.object(mock_widget, 'update_display') as mock_update:
            mock_widget.on_state_update(state_key, test_data)
            mock_update.assert_not_called()

    def test_on_state_update_with_none_data(self, mock_widget):
        """Test handling state update with None data."""
        state_key = "character.vitals"
        mock_widget.subscribe_to_state(state_key)

        with patch.object(mock_widget, 'update_display') as mock_update:
            mock_widget.on_state_update(state_key, None)
            mock_update.assert_called_once_with(None)

    def test_on_state_update_with_empty_data(self, mock_widget):
        """Test handling state update with empty data."""
        state_key = "character.vitals"
        empty_data = {}
        mock_widget.subscribe_to_state(state_key)

        with patch.object(mock_widget, 'update_display') as mock_update:
            mock_widget.on_state_update(state_key, empty_data)
            mock_update.assert_called_once_with(empty_data)

    def test_get_state_data(self, mock_widget):
        """Test getting current state data."""
        state_key = "character.vitals"
        expected_data = {"hp": 100, "mp": 50}

        mock_widget.state_manager.get_state.return_value = expected_data

        result = mock_widget.get_state_data(state_key)
        assert result == expected_data
        mock_widget.state_manager.get_state.assert_called_once_with(state_key)

    def test_get_state_data_no_state_manager(self, mock_widget):
        """Test getting state data when no state manager is available."""
        mock_widget.state_manager = None

        result = mock_widget.get_state_data("character.vitals")
        assert result is None



    def test_register_with_state_manager(self, mock_widget):
        """Test registering widget with state manager."""
        mock_widget.register_with_state_manager()
        mock_widget.state_manager.register_listener.assert_called_once_with(
            mock_widget.id, mock_widget.on_state_update
        )

    def test_register_with_state_manager_no_manager(self, mock_widget):
        """Test registering when no state manager is available."""
        # Should not raise an error
        mock_widget.register_with_state_manager()

    def test_unregister_from_state_manager(self, mock_widget):
        """Test unregistering widget from state manager."""
        mock_widget.unregister_from_state_manager()
        mock_widget.state_manager.unregister_listener.assert_called_once_with(
            mock_widget.id
        )

    def test_unregister_from_state_manager_no_manager(self, mock_widget):
        """Test unregistering when no state manager is available."""
        mock_widget.state_manager = None

        # Should not raise an error
        mock_widget.unregister_from_state_manager()

    def test_is_subscribed_to(self, mock_widget):
        """Test checking if subscribed to a state key."""
        state_key = "character.vitals"

        assert not mock_widget.is_subscribed_to(state_key)

        mock_widget.subscribe_to_state(state_key)
        assert mock_widget.is_subscribed_to(state_key)

        mock_widget.unsubscribe_from_state(state_key)
        assert not mock_widget.is_subscribed_to(state_key)

    def test_get_subscribed_keys(self, mock_widget):
        """Test getting list of subscribed keys."""
        keys = ["character.vitals", "character.stats", "room.info"]

        for key in keys:
            mock_widget.subscribe_to_state(key)

        subscribed = mock_widget.get_subscribed_keys()
        assert isinstance(subscribed, list)
        assert set(subscribed) == set(keys)

    def test_update_display_not_implemented(self):
        """Test that StateListener requires update_display to be implemented."""
        with pytest.raises(NotImplementedError):

            class IncompleteWidget(StateListener):

                def __init__(self):
                    self.id = "test_widget"
                    super().__init__()

            widget = IncompleteWidget()
            widget.update_display(None)

    @pytest.mark.asyncio
    async def test_async_state_update(self, mock_widget):
        """Test handling asynchronous state updates."""
        state_key = "character.vitals"
        test_data = {"hp": 100, "mp": 50}

        mock_widget.subscribe_to_state(state_key)

        # Mock async update_display
        mock_widget.update_display = AsyncMock()

        await mock_widget.on_state_update_async(state_key, test_data)
        mock_widget.update_display.assert_called_once_with(test_data)

    def test_state_listener_inheritance(self, mock_widget):
        """Test that StateListener can be properly inherited."""
        assert isinstance(mock_widget, StateListener)
        assert hasattr(mock_widget, 'subscribe_to_state')
        assert hasattr(mock_widget, 'unsubscribe_from_state')
        assert hasattr(mock_widget, 'on_state_update')
        assert hasattr(mock_widget, 'get_state_data')

    def test_multiple_inheritance_compatibility(self):
        """Test StateListener works with multiple inheritance."""
        class MockBase:
            def __init__(self):
                self.base_attr = "base"

        class MultipleInheritanceWidget(MockBase, StateListener):
            def __init__(self):
                super().__init__()
                self.id = "test_widget"
                self.app = Mock()
                self.app.state_manager = Mock()
                StateListener.__init__(self)

            def update_display(self, data):
                pass

        widget = MultipleInheritanceWidget()
        assert hasattr(widget, 'base_attr')
        assert hasattr(widget, 'subscribed_keys')
        assert isinstance(widget, StateListener)
        assert isinstance(widget, MockBase)
