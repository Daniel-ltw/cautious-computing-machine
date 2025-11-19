"""Tests for textual_app widget_updater module."""

from unittest.mock import AsyncMock, Mock

import pytest

from mud_agent.utils.textual_app.widget_updater import WidgetUpdater


class TestWidgetUpdater:
    """Test cases for WidgetUpdater class."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app for testing."""
        app = Mock()
        app.query = Mock()
        app.query.return_value = []
        return app

    @pytest.fixture
    def widget_updater(self, mock_app):
        """Create a WidgetUpdater instance for testing."""
        return WidgetUpdater(mock_app)

    def test_init(self, mock_app):
        """Test WidgetUpdater initialization."""
        updater = WidgetUpdater(mock_app)
        assert updater.app == mock_app
        assert hasattr(updater, '_updating_widgets')
        assert hasattr(updater, '_last_widget_update')
        assert updater._updating_widgets is False

























    @pytest.mark.asyncio
    async def test_update_all_widgets(self, widget_updater):
        """Test that update_all_widgets calls the individual updaters."""
        widget_updater._update_vitals_widgets = AsyncMock()
        widget_updater._update_status_widget = AsyncMock()
        widget_updater._update_map_widget = AsyncMock()

        await widget_updater.update_all_widgets()

        widget_updater._update_vitals_widgets.assert_called_once()
        widget_updater._update_status_widget.assert_called_once()
        widget_updater._update_map_widget.assert_called_once()
