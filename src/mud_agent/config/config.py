"""
Configuration management for the MUD agent.
"""

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ModelConfig:
    """Configuration for the LLM model."""

    model: str = "lm_studio/qwen3-8b-mlx"
    api_base: str = "http://localhost:1234/v1"
    max_tokens: int = 1000
    model_id: str | None = "lm_studio/qwen3-8b-mlx"
    api_key: str = "lm-studio"  # API key for LM Studio

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "ModelConfig":
        """Create a ModelConfig from a dictionary.

        Args:
            config: Dictionary containing model configuration.

        Returns:
            ModelConfig: A new ModelConfig instance.
        """
        return cls(
            model=config.get("model", cls.model),
            api_base=config.get("api_base", cls.api_base),
            max_tokens=config.get("max_tokens", cls.max_tokens),
            model_id=config.get("model_id", cls.model_id),
            api_key=config.get("api_key", cls.api_key),
        )


@dataclass
class MUDConfig:
    """Configuration for the MUD connection."""

    host: str = "aardmud.org"
    port: int = 4000
    character_name: str | None = None
    password: str | None = None

    @classmethod
    def from_env(cls) -> "MUDConfig":
        """Create a MUDConfig from environment variables.

        Returns:
            MUDConfig: A new MUDConfig instance.
        """
        return cls(
            host=os.getenv("MUD_HOST", cls.host),
            port=int(os.getenv("MUD_PORT", cls.port)),
            character_name=os.getenv("MUD_CHARACTER"),
            password=os.getenv("MUD_PASSWORD"),
        )


@dataclass
class LogConfig:
    """Configuration for logging."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str | None = "mud_agent.log"  # Default to a log file in the current directory

    @classmethod
    def from_env(cls) -> "LogConfig":
        """Create a LogConfig from environment variables.

        Returns:
            LogConfig: A new LogConfig instance.
        """
        return cls(
            level=os.getenv("LOG_LEVEL", cls.level),
            format=os.getenv("LOG_FORMAT", cls.format),
            file=os.getenv("LOG_FILE", cls.file),
        )


@dataclass
class GMCPConfig:
    """Configuration for GMCP processing."""

    kg_update_interval: float = 5.0  # Minimum interval between knowledge graph updates (seconds)
    max_kg_failures: int = 5  # Maximum consecutive failures before suspension

    @classmethod
    def from_env(cls) -> "GMCPConfig":
        """Create a GMCPConfig from environment variables.

        Returns:
            GMCPConfig: A new GMCPConfig instance.
        """
        return cls(
            kg_update_interval=float(os.getenv("GMCP_KG_UPDATE_INTERVAL", cls.kg_update_interval)),
            max_kg_failures=int(os.getenv("GMCP_MAX_KG_FAILURES", cls.max_kg_failures)),
        )

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "GMCPConfig":
        """Create a GMCPConfig from a dictionary.

        Args:
            config: Dictionary containing GMCP configuration.

        Returns:
            GMCPConfig: A new GMCPConfig instance.
        """
        return cls(
            kg_update_interval=config.get("kg_update_interval", cls.kg_update_interval),
            max_kg_failures=config.get("max_kg_failures", cls.max_kg_failures),
        )


@dataclass
class Config:
    """Main configuration class."""

    model: ModelConfig
    mud: MUDConfig
    log: LogConfig
    gmcp: GMCPConfig

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config: A new Config instance.
        """
        return cls(
            model=ModelConfig(),
            mud=MUDConfig.from_env(),
            log=LogConfig.from_env(),
            gmcp=GMCPConfig.from_env()
        )

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "Config":
        """Create a Config from a dictionary.

        Args:
            config: Dictionary containing configuration.

        Returns:
            Config: A new Config instance.
        """
        return cls(
            model=ModelConfig.from_dict(config.get("model", {})),
            mud=MUDConfig.from_env(),  # Always load MUD config from env for security
            log=LogConfig.from_env(),
            gmcp=GMCPConfig.from_dict(config.get("gmcp", {})),
        )
