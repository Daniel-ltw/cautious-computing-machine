#!/usr/bin/env python3
"""
Tests for CommandProcessor.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from mud_agent.agent.command_processor import CommandProcessor


class TestCommandProcessor:
    """Test suite for CommandProcessor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.room_manager = MagicMock()
        self.agent.room_manager = self.room_manager
        self.room_manager._handle_command_sent = AsyncMock()
        self.room_manager._get_current_room_num = MagicMock(return_value=None)
        self.agent.mud_tool = MagicMock()
        self.agent.mud_tool.forward = AsyncMock(return_value="Test response")
        self.agent.events = MagicMock()
        self.agent.events.emit = AsyncMock()
        self.agent.tick_manager = MagicMock()
        self.agent.tick_manager.process_server_response = MagicMock()
        self.agent.tick_manager.get_async_operations = MagicMock(return_value=[])
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.is_in_combat = MagicMock(return_value=False)
        self.agent.state_manager = MagicMock()
        self.agent.use_threaded_updates = False
        self.agent.handle_async_tick = AsyncMock()

        self.processor = CommandProcessor(self.agent, self.room_manager)

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test CommandProcessor initialization."""
        assert self.processor.agent == self.agent
        assert self.processor.room_manager == self.room_manager
        assert self.processor.logger is not None

    @pytest.mark.asyncio
    async def test_process_command_simple(self):
        """Test processing a simple command."""
        result = await self.processor.process_command("north")

        assert result == "Test response"
        self.agent.mud_tool.forward.assert_called_once_with("north")
        # Direct call to room_manager removed, event emission handles it now

    @pytest.mark.asyncio
    async def test_process_command_speedwalk_flag(self):
        """Test that speedwalk flag is passed through to event emission."""
        result = await self.processor.process_command("run 2n", is_speedwalk=True)

        assert result == "Test response"
        self.agent.events.emit.assert_called_with("command_sent", command="run 2n", from_room_num=None, is_speedwalk=True)

    @pytest.mark.asyncio
    async def test_process_command_emits_event(self):
        """Test that command_sent event is emitted."""
        await self.processor.process_command("south")

        self.agent.events.emit.assert_called_with("command_sent", command="south", from_room_num=None, is_speedwalk=False)

    @pytest.mark.asyncio
    async def test_process_command_stores_last_command(self):
        """Test that last command is stored on agent."""
        await self.processor.process_command("east")

        assert self.agent.last_command == "east"

    @pytest.mark.asyncio
    async def test_process_command_stores_last_response(self):
        """Test that last response is stored on agent."""
        self.agent.mud_tool.forward.return_value = "You go east"

        await self.processor.process_command("east")

        assert self.agent.last_response == "You go east"

    @pytest.mark.asyncio
    async def test_process_command_processes_tick(self):
        """Test that server response is processed for tick detection."""
        response = "The tick has arrived!"
        self.agent.mud_tool.forward.return_value = response

        await self.processor.process_command("look")

        self.agent.tick_manager.process_server_response.assert_called_once_with(response)

    @pytest.mark.asyncio
    async def test_process_command_checks_combat(self):
        """Test that combat status is checked."""
        response = "You hit the goblin!"
        self.agent.mud_tool.forward.return_value = response
        self.agent.combat_manager.is_in_combat.return_value = True

        await self.processor.process_command("kill goblin")

        self.agent.combat_manager.is_in_combat.assert_called_once_with(response)

    @pytest.mark.asyncio
    async def test_look_command_waits_for_response(self):
        """Test that look command waits for additional responses."""
        self.agent.mud_tool.forward.return_value = "Short response"

        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await self.processor.process_command("look")

            # Should wait 0.5 seconds for additional responses
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_look_command_gets_complete_response(self):
        """Test that look command retrieves complete response from client."""
        short_response = "Quest info only"
        complete_response = "A large room\nYou see a goblin here\nExits: north south"

        self.agent.mud_tool.forward.return_value = short_response
        self.agent.client = MagicMock()
        self.agent.client.command_responses = [
            "A large room",
            "You see a goblin here",
            "Exits: north south"
        ]

        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await self.processor.process_command("look")

            # Should get the complete response
            assert "A large room" in result
            assert "goblin" in result

    @pytest.mark.asyncio
    async def test_threaded_updates_mode(self):
        """Test command processing with threaded updates enabled."""
        self.agent.use_threaded_updates = True
        response = "Test response"
        self.agent.mud_tool.forward.return_value = response

        await self.processor.process_command("north")

        self.agent.state_manager.update_room_info.assert_called_once_with(response, "north")
        self.agent.state_manager.update_status_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_gmcp_updates_mode(self):
        """Test command processing with GMCP updates."""
        self.agent.use_threaded_updates = False
        self.agent.aardwolf_gmcp = MagicMock()
        self.agent.aardwolf_gmcp.update_from_gmcp.return_value = {
            "room": {"num": 1234, "name": "Test Room"},
            "char": {"hp": 100, "mp": 50}
        }
        self.agent.aardwolf_gmcp.get_room_info.return_value = {"num": 1234}
        self.agent.aardwolf_gmcp.get_character_stats.return_value = {"hp": 100}
        self.room_manager.update_from_aardwolf_gmcp = AsyncMock()

        await self.processor.process_command("north")

        # Verify GMCP was updated
        assert self.agent.aardwolf_gmcp.update_from_gmcp.called
        # Verify room and character updates were retrieved
        assert self.agent.aardwolf_gmcp.get_room_info.called or self.room_manager.update_from_aardwolf_gmcp.called

    @pytest.mark.asyncio
    async def test_async_operations_processing(self):
        """Test that async operations are processed."""
        self.agent.tick_manager.get_async_operations.return_value = [1, 2, 3]

        await self.processor.process_command("rest")

        # Should process each tick
        assert self.agent.handle_async_tick.call_count == 3
        self.agent.handle_async_tick.assert_has_calls([
            call(1),
            call(2),
            call(3)
        ])

    @pytest.mark.asyncio
    async def test_command_processor_error_handling(self):
        """Test that errors are caught and returned as error messages."""
        self.agent.mud_tool.forward.side_effect = Exception("Connection lost")

        result = await self.processor.process_command("north")

        assert "Error processing command" in result
        assert "Connection lost" in result

    @pytest.mark.asyncio
    async def test_process_single_command_error_recovery(self):
        """Test error recovery in single command processing."""
        self.agent.mud_tool.forward.side_effect = Exception("Test error")

        result = await self.processor._process_single_command("test")

        assert "Error processing command" in result

    @pytest.mark.asyncio
    async def test_case_insensitive_look_detection(self):
        """Test that look command detection is case-insensitive."""
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await self.processor.process_command("LOOK")
            assert mock_sleep.called

            mock_sleep.reset_mock()
            await self.processor.process_command("L")
            assert mock_sleep.called

    @pytest.mark.asyncio
    async def test_captures_room_num_before_event(self):
        """Test that room number is captured and passed to event."""
        self.room_manager._get_current_room_num.return_value = 12345

        await self.processor.process_command("north")

        self.room_manager._get_current_room_num.assert_called()
        self.agent.events.emit.assert_called_with("command_sent", command="north", from_room_num=12345, is_speedwalk=False)

    @pytest.mark.asyncio
    async def test_queued_commands_processing(self):
        """Test processing of queued commands from state manager."""
        self.agent.use_threaded_updates = True
        self.agent.state_manager.process_mud_commands = MagicMock(
            return_value=["look", "score"]
        )
        self.agent.send_command = AsyncMock()

        await self.processor.process_command("rest")

        # Should process queued commands
        assert self.agent.send_command.call_count == 2
        self.agent.send_command.assert_has_calls([
            call("look"),
            call("score")
        ])

    @pytest.mark.asyncio
    async def test_no_gmcp_updates_doesnt_crash(self):
        """Test that missing GMCP doesn't cause errors."""
        self.agent.use_threaded_updates = False
        # No aardwolf_gmcp attribute

        result = await self.processor.process_command("north")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_empty_gmcp_updates(self):
        """Test handling of empty GMCP updates."""
        self.agent.use_threaded_updates = False
        self.agent.aardwolf_gmcp = MagicMock()
        self.agent.aardwolf_gmcp.update_from_gmcp.return_value = {}

        result = await self.processor.process_command("north")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_async_operations_exception_handling(self):
        """Test that exceptions in async operations are handled."""
        self.agent.tick_manager.get_async_operations.side_effect = Exception("Tick error")

        # Should not raise, error should be logged
        result = await self.processor.process_command("rest")

        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_process_command_intercepts_recall(self):
        """Test that recall command is intercepted and replaced if configured."""
        self.agent.config = MagicMock()
        self.agent.config.agent.recall_command = "wear amu;enter;dual sun"

        await self.processor.process_command("recall")

        # verify that the command sent was the replaced one
        self.agent.mud_tool.forward.assert_called_once_with("wear amu;enter;dual sun")

    @pytest.mark.asyncio
    async def test_process_command_no_recall_interception(self):
        """Test that recall command is NOT intercepted if not configured."""
        self.agent.config = MagicMock()
        self.agent.config.agent.recall_command = None

        await self.processor.process_command("recall")

        # verify that the command sent was original "recall"
        self.agent.mud_tool.forward.assert_called_once_with("recall")
