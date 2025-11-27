"""
Tests for the AgentConfig class.
"""

import os
from unittest.mock import patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.config.config import AgentConfig, Config


class TestAgentConfig:
    """Tests for the AgentConfig class."""

    def test_default_values(self):
        """Test that the default values are set correctly."""
        config = AgentConfig()
        assert config.autocast_commands == ["nimble", "hide", "sneak", "cast under"]

    def test_from_env(self):
        """Test creating an AgentConfig from environment variables."""
        with patch.dict(
            os.environ,
            {
                "AUTOCAST_COMMANDS": "spell1, spell2,  spell3 ",
            },
        ):
            config = AgentConfig.from_env()

            assert config.autocast_commands == ["spell1", "spell2", "spell3"]

    def test_from_env_empty(self):
        """Test creating an AgentConfig from empty environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            config = AgentConfig.from_env()
            assert config.autocast_commands == ["nimble", "hide", "sneak", "cast under"]

    def test_from_dict(self):
        """Test creating an AgentConfig from a dictionary."""
        config_dict = {
            "autocast_commands": ["custom1", "custom2"],
        }

        config = AgentConfig.from_dict(config_dict)

        assert config.autocast_commands == ["custom1", "custom2"]


class TestConfigWithAgent:
    """Tests for the Config class including AgentConfig."""

    def test_load_includes_agent(self):
        """Test loading the configuration includes agent config."""
        config = Config.load()
        assert isinstance(config.agent, AgentConfig)

    def test_from_dict_includes_agent(self):
        """Test creating a Config from a dictionary includes agent config."""
        config_dict = {
            "agent": {"autocast_commands": ["test"]}
        }

        # Mock other config loads to avoid env var issues
        with patch("mud_agent.config.config.MUDConfig.from_env"), \
             patch("mud_agent.config.config.LogConfig.from_env"), \
             patch("mud_agent.config.config.GMCPConfig.from_dict"):

            config = Config.from_dict(config_dict)
            assert config.agent.autocast_commands == ["test"]
