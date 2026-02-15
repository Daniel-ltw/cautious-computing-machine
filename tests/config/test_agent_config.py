"""
Tests for the AgentConfig class.
"""

import os
from unittest.mock import patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.config.config import AgentConfig, Config, DatabaseConfig


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


class TestDatabaseConfig:
    """Tests for the DatabaseConfig class."""

    def test_database_config_defaults(self):
        """DatabaseConfig should have sync settings with sensible defaults."""
        config = DatabaseConfig()
        assert config.sync_enabled is False
        assert config.sync_interval == 30.0
        assert config.url is None

    def test_database_config_from_env(self):
        """DatabaseConfig should load sync settings from environment."""
        env = {
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
            "SYNC_ENABLED": "true",
            "SYNC_INTERVAL": "15",
        }
        with patch.dict(os.environ, env):
            config = DatabaseConfig.from_env()
            assert config.url == "postgresql://user:pass@host:5432/db"
            assert config.sync_enabled is True
            assert config.sync_interval == 15.0
