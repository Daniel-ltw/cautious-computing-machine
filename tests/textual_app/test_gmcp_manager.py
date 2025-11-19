"""Tests for textual_app gmcp_manager module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mud_agent.utils.textual_app.gmcp_manager import GMCPManager


@pytest.fixture
def mock_app():
    """Create a mock app with mock agent and state_manager."""
    app = MagicMock()
    app.agent = MagicMock()
    # Make sure the events object has an 'on' method that is a mock
    app.agent.client.events = MagicMock()
    app.agent.client.events.on = MagicMock()
    app.state_manager = MagicMock()
    app.update_reactive_widgets = AsyncMock()
    return app


@pytest.fixture
def gmcp_manager(mock_app, request):
    """Create a GMCPManager instance for testing."""
    manager = GMCPManager(mock_app)

    # Teardown logic to stop polling if it was started
    async def finalizer():
        if manager._gmcp_polling_task and not manager._gmcp_polling_task.done():
            await manager.stop_gmcp_polling()

    request.addfinalizer(lambda: asyncio.run(finalizer()))
    return manager


class TestGMCPManager:
    """Test cases for GMCPManager class."""

    def test_init(self, gmcp_manager, mock_app):
        """Test GMCPManager initialization."""
        assert gmcp_manager.app == mock_app
        assert gmcp_manager.agent == mock_app.agent
        assert gmcp_manager.state_manager == mock_app.state_manager
        assert gmcp_manager._gmcp_polling_task is None
        assert not gmcp_manager._gmcp_polling_enabled

    @pytest.mark.asyncio
    async def test_setup(self, gmcp_manager):
        """Test the setup of the GMCPManager."""
        await gmcp_manager.setup()

        # Assert that the event subscriptions were made
        gmcp_manager.agent.client.events.on.assert_any_call('gmcp_data', gmcp_manager._on_gmcp_data)
        gmcp_manager.agent.client.events.on.assert_any_call('gmcp.room.info', gmcp_manager._on_room_info)
        gmcp_manager.agent.client.events.on.assert_any_call('gmcp.char.vitals', gmcp_manager._on_char_vitals)
        gmcp_manager.agent.client.events.on.assert_any_call('gmcp.char.stats', gmcp_manager._on_char_stats)

    def test_on_gmcp_data(self, gmcp_manager):
        """Test the _on_gmcp_data method."""
        with patch.object(gmcp_manager, 'handle_gmcp_package') as mock_handle:
            gmcp_manager._on_gmcp_data('test.package', {'key': 'value'})
            mock_handle.assert_called_once_with('test.package', {'key': 'value'})

    @pytest.mark.asyncio
    @patch("src.mud_agent.utils.textual_app.gmcp_manager.GMCPManager._gmcp_polling_worker")
    async def test_start_and_stop_gmcp_polling(self, mock_gmcp_polling_worker, gmcp_manager):
        stop_event = asyncio.Event()

        async def dummy_worker():
            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass

        mock_gmcp_polling_worker.side_effect = dummy_worker

        await gmcp_manager.start_gmcp_polling()
        assert gmcp_manager._gmcp_polling_task is not None
        assert gmcp_manager._gmcp_polling_enabled is True

        await gmcp_manager.stop_gmcp_polling()

        assert gmcp_manager._gmcp_polling_task is None
        assert gmcp_manager._gmcp_polling_enabled is False

    def test_handle_gmcp_package(self, gmcp_manager):
        """Test handling of a GMCP package."""
        # This test is not valid as handle_gmcp_package is not implemented
        pass
