"""
Configuration management for the MUD agent.
"""

import os
from dataclasses import dataclass
from typing import Any

@dataclass
class DatabaseConfig:
    """Configuration for the database."""

    url: str | None = None
    sync_enabled: bool = False
    sync_interval: float = 30.0

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create a DatabaseConfig from environment variables.

        Returns:
            DatabaseConfig: A new DatabaseConfig instance.
        """
        sync_enabled_raw = os.getenv("SYNC_ENABLED", "false").strip().lower()
        return cls(
            url=os.getenv("DATABASE_URL"),
            sync_enabled=sync_enabled_raw in {"true", "1", "yes"},
            sync_interval=float(os.getenv("SYNC_INTERVAL", "30")),
        )


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
    file: str | None = None

    @classmethod
    def from_env(cls) -> "LogConfig":
        """Create a LogConfig from environment variables.

        Returns:
            LogConfig: A new LogConfig instance.
        """
        raw_file = os.getenv("LOG_FILE", "none")
        file = None if str(raw_file).strip().lower() in {"", "none", "false"} else raw_file
        return cls(
            level=os.getenv("LOG_LEVEL", cls.level),
            format=os.getenv("LOG_FORMAT", cls.format),
            file=file,
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
class AgentConfig:
    """Configuration for the agent behavior."""

    autocast_commands: list[str]
    recall_command: str | None
    combat_opener_skills: list[str]
    combat_rotation_skills: list[str]
    combat_flee_threshold: float
    combat_flee_command: str

    def __init__(
        self,
        autocast_commands: list[str] | None = None,
        recall_command: str | None = None,
        combat_opener_skills: list[str] | None = None,
        combat_rotation_skills: list[str] | None = None,
        combat_flee_threshold: float = 0.25,
        combat_flee_command: str = "flee",
    ):
        self.autocast_commands = autocast_commands or ["nimble", "hide", "sneak", "cast under"]
        self.recall_command = recall_command
        self.combat_opener_skills = combat_opener_skills if combat_opener_skills is not None else []
        self.combat_rotation_skills = combat_rotation_skills if combat_rotation_skills is not None else []
        self.combat_flee_threshold = combat_flee_threshold
        self.combat_flee_command = combat_flee_command

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Create an AgentConfig from environment variables.

        Returns:
            AgentConfig: A new AgentConfig instance.
        """
        autocast_env = os.getenv("AUTOCAST_COMMANDS")
        recall_command = os.getenv("RECALL")

        commands = None
        if autocast_env:
            # Split by comma and strip whitespace
            commands = [cmd.strip() for cmd in autocast_env.split(",") if cmd.strip()]

        opener_env = os.getenv("COMBAT_OPENER_SKILLS")
        opener_skills = (
            [s.strip() for s in opener_env.split(",") if s.strip()] if opener_env else None
        )

        rotation_env = os.getenv("COMBAT_ROTATION_SKILLS")
        rotation_skills = (
            [s.strip() for s in rotation_env.split(",") if s.strip()] if rotation_env else None
        )

        flee_threshold_env = os.getenv("COMBAT_FLEE_THRESHOLD")
        flee_threshold = float(flee_threshold_env) if flee_threshold_env else 0.25

        flee_command = os.getenv("COMBAT_FLEE_COMMAND", "flee")

        return cls(
            autocast_commands=commands,
            recall_command=recall_command,
            combat_opener_skills=opener_skills,
            combat_rotation_skills=rotation_skills,
            combat_flee_threshold=flee_threshold,
            combat_flee_command=flee_command,
        )

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "AgentConfig":
        """Create an AgentConfig from a dictionary.

        Args:
            config: Dictionary containing agent configuration.

        Returns:
            AgentConfig: A new AgentConfig instance.
        """
        return cls(
            autocast_commands=config.get("autocast_commands"),
            recall_command=config.get("recall_command"),
            combat_opener_skills=config.get("combat_opener_skills"),
            combat_rotation_skills=config.get("combat_rotation_skills"),
            combat_flee_threshold=config.get("combat_flee_threshold", 0.25),
            combat_flee_command=config.get("combat_flee_command", "flee"),
        )



@dataclass
class Config:
    """Main configuration class."""

    model: ModelConfig
    mud: MUDConfig
    log: LogConfig
    gmcp: GMCPConfig
    agent: AgentConfig
    database: DatabaseConfig

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
            gmcp=GMCPConfig.from_env(),
            agent=AgentConfig.from_env(),
            database=DatabaseConfig.from_env(),
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
            agent=AgentConfig.from_dict(config.get("agent", {})),
            database=DatabaseConfig.from_env(),  # Always load DB config from env for security
        )
