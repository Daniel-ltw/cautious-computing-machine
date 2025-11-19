"""
Tests for the Config class.
"""

import os
from unittest.mock import patch

# Import helper to add src to Python path
from test_helper import *

from mud_agent.config.config import Config, LogConfig, ModelConfig, MUDConfig


class TestModelConfig:
    """Tests for the ModelConfig class."""

    def test_default_values(self):
        """Test that the default values are set correctly."""
        config = ModelConfig()
        assert config.model == "lm_studio/qwen3-8b-mlx"
        assert config.api_base == "http://localhost:1234/v1"
        assert config.max_tokens == 1000
        assert config.model_id == "lm_studio/qwen3-8b-mlx"
        assert config.api_key == "lm-studio"

    def test_from_dict(self):
        """Test creating a ModelConfig from a dictionary."""
        config_dict = {
            "model": "test_model",
            "api_base": "test_api_base",
            "max_tokens": 500,
            "model_id": "test_model_id",
            "api_key": "test_api_key",
        }

        config = ModelConfig.from_dict(config_dict)

        assert config.model == "test_model"
        assert config.api_base == "test_api_base"
        assert config.max_tokens == 500
        assert config.model_id == "test_model_id"
        assert config.api_key == "test_api_key"


class TestMUDConfig:
    """Tests for the MUDConfig class."""

    def test_default_values(self):
        """Test that the default values are set correctly."""
        config = MUDConfig()
        assert config.host == "aardmud.org"
        assert config.port == 4000
        assert config.character_name is None
        assert config.password is None

    def test_from_env(self):
        """Test creating a MUDConfig from environment variables."""
        with patch.dict(
            os.environ,
            {
                "MUD_HOST": "test_host",
                "MUD_PORT": "1234",
                "MUD_CHARACTER": "test_character",
                "MUD_PASSWORD": "test_password",
            },
        ):
            config = MUDConfig.from_env()

            assert config.host == "test_host"
            assert config.port == 1234
            assert config.character_name == "test_character"
            assert config.password == "test_password"


class TestLogConfig:
    """Tests for the LogConfig class."""

    def test_default_values(self):
        """Test that the default values are set correctly."""
        config = LogConfig()
        assert config.level == "INFO"
        assert config.format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert config.file is None

    def test_from_env(self):
        """Test creating a LogConfig from environment variables."""
        with patch.dict(
            os.environ,
            {
                "LOG_LEVEL": "DEBUG",
                "LOG_FORMAT": "test_format",
                "LOG_FILE": "test_file",
            },
        ):
            config = LogConfig.from_env()

            assert config.level == "DEBUG"
            assert config.format == "test_format"
            assert config.file == "test_file"


class TestConfig:
    """Tests for the Config class."""

    def test_load(self):
        """Test loading the configuration."""
        config = Config.load()

        assert isinstance(config.model, ModelConfig)
        assert isinstance(config.mud, MUDConfig)
        assert isinstance(config.log, LogConfig)

    def test_from_dict(self):
        """Test creating a Config from a dictionary."""
        config_dict = {"model": {"model": "test_model", "api_base": "test_api_base"}}

        with patch.object(MUDConfig, "from_env") as mock_mud_config:
            with patch.object(LogConfig, "from_env") as mock_log_config:
                mock_mud_config.return_value = MUDConfig()
                mock_log_config.return_value = LogConfig()

                config = Config.from_dict(config_dict)

                assert config.model.model == "test_model"
                assert config.model.api_base == "test_api_base"
                assert isinstance(config.mud, MUDConfig)
                assert isinstance(config.log, LogConfig)
