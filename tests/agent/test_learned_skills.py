"""Tests for the learned skills provider."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from mud_agent.agent.learned_skills import LearnedSkillsProvider, parse_learned_output


class TestParseLearnedOutput:
    """Test parsing of the 'learned' command output."""

    def test_extracts_skill_names(self):
        """Skill names are extracted from typical learned output."""
        output = (
            "------------------------------------------------------------\n"
            "backstab            123    85%     10\n"
            "circle              124    90%     15\n"
            "dirt kick           125    75%     20\n"
            "kick                126    80%     5\n"
            "sneak               127    95%     1\n"
            "------------------------------------------------------------\n"
        )
        result = parse_learned_output(output)
        assert result == {"backstab", "circle", "dirt kick", "kick", "sneak"}

    def test_empty_response(self):
        """Empty or blank input returns empty set."""
        assert parse_learned_output("") == set()
        assert parse_learned_output("   \n\n  ") == set()

    def test_ignores_header_and_separator_lines(self):
        """Header lines and separators are not included as skills."""
        output = (
            "------------------------------------------------------------\n"
            "Skill Name          Spell#  Practice  Level Learned\n"
            "------------------------------------------------------------\n"
            "backstab            123    85%     10\n"
            "------------------------------------------------------------\n"
            "You have 5 training sessions remaining.\n"
            "Total skills learned: 1\n"
        )
        result = parse_learned_output(output)
        assert result == {"backstab"}

    def test_case_insensitive(self):
        """Skill names are stored lowercase."""
        output = "Backstab            123    85%     10\n"
        result = parse_learned_output(output)
        assert "backstab" in result


class TestLearnedSkillsProvider:
    """Test the provider class."""

    @pytest.mark.asyncio
    async def test_fetch_calls_process_command(self):
        """fetch() sends 'learned' command."""
        agent = MagicMock()
        agent.command_processor = MagicMock()
        agent.command_processor.process_command = AsyncMock(
            return_value="kick                126    80%     5\n"
        )
        provider = LearnedSkillsProvider(agent)
        await provider.fetch()
        agent.command_processor.process_command.assert_called_once_with("learned")

    @pytest.mark.asyncio
    async def test_skills_stored(self):
        """Parsed skills are stored on the provider."""
        agent = MagicMock()
        agent.command_processor = MagicMock()
        agent.command_processor.process_command = AsyncMock(
            return_value=(
                "kick                126    80%     5\n"
                "backstab            123    85%     10\n"
            )
        )
        provider = LearnedSkillsProvider(agent)
        result = await provider.fetch()
        assert provider.skills == {"kick", "backstab"}
        assert result == {"kick", "backstab"}

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Errors during fetch don't crash the provider."""
        agent = MagicMock()
        agent.command_processor = MagicMock()
        agent.command_processor.process_command = AsyncMock(
            side_effect=Exception("Connection lost")
        )
        provider = LearnedSkillsProvider(agent)
        result = await provider.fetch()
        assert provider.skills == set()
        assert result == set()
