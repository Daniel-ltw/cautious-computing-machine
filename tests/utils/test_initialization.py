#!/usr/bin/env python3
"""
Tests for initialization functions.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time

from mud_agent.utils.initialization import detect_welcome_banner, initialize_game_state


class TestDetectWelcomeBanner:
    """Test suite for detect_welcome_banner function."""

    @pytest.mark.asyncio
    async def test_banner_detected_in_last_response(self):
        """Test that banner is detected if already in last_response."""
        agent = MagicMock()
        agent.last_response = "Welcome to Aardwolf! Type 'help' for help."

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_banner_detected_password_prompt(self):
        """Test that password prompt is recognized as banner."""
        agent = MagicMock()
        agent.last_response = "Password: "

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_banner_detected_login_success(self):
        """Test that login success message is recognized."""
        agent = MagicMock()
        agent.last_response = "Welcome back! Last login was yesterday."

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_no_response_eventually_succeeds(self):
        """Test that function succeeds even if response comes late."""
        agent = MagicMock()
        agent.send_command = AsyncMock()
        agent.last_response = ""  # Empty initially

        # Start detection
        async def set_response_later():
            await asyncio.sleep(0.1)
            agent.last_response = "Welcome to Aardwolf"

        # Run both tasks
        task =asyncio.create_task(detect_welcome_banner(agent, timeout=1))
        asyncio.create_task(set_response_later())

        result = await task

        assert result is True

    @pytest.mark.asyncio
    async def test_gmcp_character_data_triggers_success(self):
        """Test that receiving GMCP character data indicates banner complete."""
        agent = MagicMock()
        agent.last_response = ""
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.return_value = {"char": {"name": "TestChar"}}

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_returns_true(self):
        """Test that timeout still returns True to allow continuation."""
        agent = MagicMock()
        agent.last_response = ""
        agent.send_command = AsyncMock()

        start = time.time()
        result = await detect_welcome_banner(agent, timeout=0.2)
        duration = time.time() - start

        assert result is True
        assert duration >= 0.2
        assert duration < 0.5  # Should not wait much longer than timeout

    @pytest.mark.asyncio
    async def test_exception_returns_true(self):
        """Test that exceptions don't break initialization flow."""
        agent = MagicMock()
        agent.send_command = AsyncMock(side_effect=Exception("Test error"))

        result = await detect_welcome_banner(agent, timeout=0.5)

        # Should still return True to allow continuation
        assert result is True

    @pytest.mark.asyncio
    async def test_case_insensitive_pattern_matching(self):
        """Test that banner patterns are case-insensitive."""
        agent = MagicMock()
        agent.last_response = "WELCOME TO AARDWOLF! type 'HELP' for help."

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_partial_pattern_matching(self):
        """Test that partial patterns in larger text are detected."""
        agent = MagicMock()
        agent.last_response = """
        Some text before
        Welcome to Aardwolf MUD
        Some text after
        """

        result = await detect_welcome_banner(agent, timeout=1)

        assert result is True


class TestInitializeGameState:
    """Test suite for initialize_game_state function."""

    @pytest.mark.asyncio
    async def test_successful_gmcp_initialization(self):
        """Test successful initialization using GMCP."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.return_value = {
            "char": {"name": "TestChar", "hp": 100},
            "room": {"num": 1234, "name": "Test Room"},
            "map": {"data": "test_map_data"}
        }
        agent.aardwolf_gmcp.get_character_stats.return_value = {
            "name": "TestChar",
            "hp": 100
        }
        agent.state_manager = MagicMock()

        result = await initialize_game_state(agent)

        assert result is True
        assert agent.aardwolf_gmcp.update_from_gmcp.called
        assert agent.state_manager.update_from_aardwolf_gmcp.called

    @pytest.mark.asyncio
    async def test_initialization_with_partial_gmcp_data(self):
        """Test initialization when some GMCP data is missing initially."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()

        # First call returns only char data
        # Second call (after sleep) returns complete data
        agent.aardwolf_gmcp.update_from_gmcp.side_effect = [
            {"char": {"name": "TestChar"}},
            {"char": {"name": "TestChar"}, "room": {"num": 1234}}
        ]
        agent.aardwolf_gmcp.get_character_stats.return_value = {"name": "TestChar"}
        agent.state_manager = MagicMock()

        result = await initialize_game_state(agent)

        assert result is True
        # Should be called twice (initial + retry)
        assert agent.aardwolf_gmcp.update_from_gmcp.call_count == 2

    @pytest.mark.asyncio
    async def test_initialization_without_gmcp(self):
        """Test initialization when GMCP is not enabled."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = False
        agent.aardwolf_gmcp = None

        result = await initialize_game_state(agent)

        # Should still return True to allow continuation
        assert result is True

    @pytest.mark.asyncio
    async def test_initialization_gmcp_exception(self):
        """Test that GMCP exceptions are handled gracefully."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.side_effect = Exception("GMCP error")

        result = await initialize_game_state(agent)

        # Should return False on exception
        assert result is False

    @pytest.mark.asyncio
    async def test_state_manager_update_with_char_data(self):
        """Test that state manager is updated when char data is present."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.return_value = {
            "char": {"name": "TestChar", "level": 10},
            "room": {"num": 1234}
        }
        char_stats = {"name": "TestChar", "level": 10}
        agent.aardwolf_gmcp.get_character_stats.return_value = char_stats
        agent.state_manager = MagicMock()

        result = await initialize_game_state(agent)

        assert result is True
        agent.state_manager.update_from_aardwolf_gmcp.assert_called_with(char_stats)

    @pytest.mark.asyncio
    async def test_initialization_logs_gmcp_usage(self):
        """Test that GMCP usage is logged correctly."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.return_value = {
            "char": {"name": "TestChar"},
            "room": {"num": 1234}
        }
        agent.aardwolf_gmcp.get_character_stats.return_value = {"name": "TestChar"}
        agent.state_manager = MagicMock()

        with patch('mud_agent.utils.initialization.logger') as mock_logger:
            result = await initialize_game_state(agent)

            assert result is True
            # Check that debug logging occurred
            assert mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_empty_gmcp_updates(self):
        """Test handling of empty GMCP updates."""
        agent = MagicMock()
        agent.client = MagicMock()
        agent.client.gmcp_enabled = True
        agent.aardwolf_gmcp = MagicMock()
        agent.aardwolf_gmcp.update_from_gmcp.return_value = {}
        agent.state_manager = MagicMock()

        result = await initialize_game_state(agent)

        # Should still return True even with empty updates
        assert result is True
