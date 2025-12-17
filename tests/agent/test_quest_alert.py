import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from mud_agent.agent.quest_manager import QuestManager

@pytest.mark.asyncio
class TestCommandLogAlert:
    async def test_alert_macos(self):
        """Test that the alert plays correctly on macOS."""
        from mud_agent.utils.widgets.command_log import CommandLog

        log = CommandLog()

        # Test alert trigger with macOS platform mock
        with patch("sys.platform", "darwin"):
            with patch("subprocess.Popen") as mock_popen:
                log._on_server_data("Some text\nYou may quest again\nMore text")
                mock_popen.assert_called_with(["afplay", "/System/Library/Sounds/Glass.aiff"])

    async def test_alert_ansi_stripping(self):
        """Test that the alert triggers even with ANSI color codes."""
        from mud_agent.utils.widgets.command_log import CommandLog

        log = CommandLog()

        # Test string with ANSI colors: \x1b[32mYou may quest again\x1b[0m
        # Note: CommandLog logic doesn't explicitly strip ANSI before check unless logic was added,
        # but typical 'in' check might fail if ANSI codes are inside the phrase.
        # However, the user request implied 'filtered' log. The CommandLog receives data.
        # If the data has ANSI, "You may quest again" might be broken up or surrounded.
        # The simple 'in' check works if the substring is intact.

        ansi_text = "\x1b[32mYou may quest again\x1b[0m"

        with patch("sys.platform", "darwin"):
            with patch("subprocess.Popen") as mock_popen:
                log._on_server_data(ansi_text)
                mock_popen.assert_called()

    async def test_alert_windows(self):
         """Test that the alert plays correctly on Windows."""
         from mud_agent.utils.widgets.command_log import CommandLog

         log = CommandLog()

         with patch("sys.platform", "win32"):
             with patch("subprocess.Popen") as mock_popen:
                 log._on_server_data("You may quest again")
                 mock_popen.assert_called_with(["powershell", "-c", "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync();"])
