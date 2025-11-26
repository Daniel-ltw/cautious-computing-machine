#!/usr/bin/env python3
"""
Tests for MudClient keep-alive functionality and connection management.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from mud_agent.client.mud_client import MudClient, KEEP_ALIVE_INTERVAL, KEEP_ALIVE_TIMEOUT


class TestMudClientKeepAlive:
    """Test suite for MudClient keep-alive functionality."""

    def test_keep_alive_interval_constant(self):
        """Test that KEEP_ALIVE_INTERVAL is set to 30 seconds."""
        assert KEEP_ALIVE_INTERVAL == 10.0, "Keep-alive interval should be 10 seconds"

    def test_keep_alive_timeout_constant(self):
        """Test that KEEP_ALIVE_TIMEOUT is set to 180 seconds."""
        assert KEEP_ALIVE_TIMEOUT == 180.0, "Keep-alive timeout should be 180 seconds"

    def test_client_initialization_with_keep_alive_enabled(self):
        """Test that MudClient initializes with keep-alive enabled by default."""
        client = MudClient(host="test.server.com", port=4000)

        assert client.keep_alive_enabled is True
        assert client.keep_alive_interval == KEEP_ALIVE_INTERVAL
        assert client.last_data_time > 0
        assert client.last_sent_time > 0

    def test_client_initialization_with_custom_keep_alive_interval(self):
        """Test that MudClient can be initialized with a custom keep-alive interval."""
        custom_interval = 15.0
        client = MudClient(
            host="test.server.com",
            port=4000,
            keep_alive_interval=custom_interval
        )

        assert client.keep_alive_enabled is True
        assert client.keep_alive_interval == custom_interval

    def test_client_initialization_with_keep_alive_disabled(self):
        """Test that MudClient can be initialized with keep-alive disabled."""
        client = MudClient(
            host="test.server.com",
            port=4000,
            keep_alive_enabled=False
        )

        assert client.keep_alive_enabled is False

    @pytest.mark.asyncio
    async def test_keep_alive_task_starts_on_connect(self):
        """Test that keep-alive task starts when client connects."""
        client = MudClient(host="test.server.com", port=4000)

        # Mock the connection
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock protocol negotiation
            with patch.object(client, '_negotiate_protocols', new_callable=AsyncMock):
                await client.connect("test.server.com", 4000)

            # Verify keep-alive task was created
            assert client.keep_alive_task is not None
            assert not client.keep_alive_task.done()

            # Clean up
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_keep_alive_task_does_not_start_when_disabled(self):
        """Test that keep-alive task doesn't start when keep-alive is disabled."""
        client = MudClient(
            host="test.server.com",
            port=4000,
            keep_alive_enabled=False
        )

        # Mock the connection
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock protocol negotiation
            with patch.object(client, '_negotiate_protocols', new_callable=AsyncMock):
                await client.connect("test.server.com", 4000)

            # Verify keep-alive task was not created
            assert client.keep_alive_task is None

            # Clean up
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_send_nop_command(self):
        """Test that _send_nop sends the correct NOP telnet command."""
        client = MudClient(host="test.server.com", port=4000)

        # Mock the writer
        mock_writer = AsyncMock()
        mock_writer.drain = AsyncMock()
        client.writer = mock_writer
        client.connected = True

        # Call _send_nop
        await client._send_nop()

        # Verify NOP command was written (IAC NOP = bytes([255, 241]))
        assert mock_writer.write.called
        written_data = mock_writer.write.call_args[0][0]
        assert written_data == bytes([255, 241])
        assert mock_writer.drain.called

    @pytest.mark.asyncio
    async def test_send_nop_raises_when_not_connected(self):
        """Test that _send_nop raises ConnectionError when not connected."""
        client = MudClient(host="test.server.com", port=4000)
        client.connected = False
        client.writer = None

        with pytest.raises(ConnectionError, match="Not connected to server"):
            await client._send_nop()

    @pytest.mark.asyncio
    async def test_last_sent_time_updated_on_send_command(self):
        """Test that last_sent_time is updated when sending commands."""
        client = MudClient(host="test.server.com", port=4000)

        # Mock the writer
        mock_writer = AsyncMock()
        mock_writer.drain = AsyncMock()
        client.writer = mock_writer
        client.connected = True

        # Record time before sending
        time_before = time.time()

        # Send a command
        await client.send_command("test command")

        # Verify last_sent_time was updated
        assert client.last_sent_time >= time_before
        assert client.last_sent_time <= time.time()

    @pytest.mark.asyncio
    async def test_keep_alive_task_stops_on_disconnect(self):
        """Test that keep-alive task is cancelled when disconnecting."""
        client = MudClient(host="test.server.com", port=4000)

        # Mock the connection
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_writer.wait_closed = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock protocol negotiation
            with patch.object(client, '_negotiate_protocols', new_callable=AsyncMock):
                await client.connect("test.server.com", 4000)

            # Verify keep-alive task exists
            assert client.keep_alive_task is not None
            keep_alive_task = client.keep_alive_task

            # Disconnect
            await client.disconnect()

            # Give the task a moment to cancel
            await asyncio.sleep(0.1)

            # Try to wait for the task to complete (with cancellation)
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass

            # Verify keep-alive task was cancelled or completed
            assert keep_alive_task.done()
            assert client.keep_alive_task is None


class TestMudClientConnectionManagement:
    """Test suite for MudClient connection management."""

    def test_client_tracks_last_data_time(self):
        """Test that client tracks when data was last received."""
        client = MudClient(host="test.server.com", port=4000)

        # last_data_time should be initialized
        assert hasattr(client, 'last_data_time')
        assert client.last_data_time > 0

    def test_client_tracks_last_sent_time(self):
        """Test that client tracks when data was last sent."""
        client = MudClient(host="test.server.com", port=4000)

        # last_sent_time should be initialized
        assert hasattr(client, 'last_sent_time')
        assert client.last_sent_time > 0

    @pytest.mark.asyncio
    async def test_connection_event_emitted_on_connect(self):
        """Test that 'connected' event is emitted when connecting."""
        client = MudClient(host="test.server.com", port=4000)

        # Set up event listener
        connected_event_called = False

        def on_connected(host, port):
            nonlocal connected_event_called
            connected_event_called = True

        client.events.on("connected", on_connected)

        # Mock the connection
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock protocol negotiation
            with patch.object(client, '_negotiate_protocols', new_callable=AsyncMock):
                await client.connect("test.server.com", 4000)

            # Verify event was emitted
            assert connected_event_called

            # Clean up
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_disconnected_event_emitted_on_disconnect(self):
        """Test that 'disconnected' event is emitted when disconnecting."""
        client = MudClient(host="test.server.com", port=4000)

        # Set up event listener
        disconnected_event_called = False

        def on_disconnected():
            nonlocal disconnected_event_called
            disconnected_event_called = True

        client.events.on("disconnected", on_disconnected)

        # Mock the connection
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.drain = AsyncMock()
            mock_writer.wait_closed = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)

            # Mock protocol negotiation
            with patch.object(client, '_negotiate_protocols', new_callable=AsyncMock):
                await client.connect("test.server.com", 4000)

            # Disconnect
            await client.disconnect()

            # Verify event was emitted
            assert disconnected_event_called
