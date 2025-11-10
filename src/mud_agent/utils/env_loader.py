"""Utility for loading environment variables from a .env file."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env_file(env_path: str | None = None) -> dict[str, str]:
    """Load environment variables from a .env file.

    Args:
        env_path: Path to the .env file. If None, looks for .env in the current directory
                 and the project root directory.

    Returns:
        Dict of environment variables loaded from the .env file
    """
    # If no path is provided, look for .env in current directory and project root
    if env_path is None:
        # Try current directory first
        env_file = Path(".env")
        if env_file.exists():
            env_path = str(env_file)
        else:
            # Try to find the project root (where the src directory is)
            current_dir = Path.cwd()
            while current_dir.name and not (current_dir / "src").exists():
                current_dir = current_dir.parent

            # If we found the project root, look for .env there
            if (current_dir / "src").exists():
                potential_env_path = current_dir / ".env"
                if potential_env_path.exists():
                    env_path = str(potential_env_path)

    # If we still don't have a path, return empty dict
    if env_path is None or not Path(env_path).exists():
        logger.debug("No .env file found")
        return {}

    # Load the .env file
    env_vars = {}
    try:
        with Path(env_path).open() as f:
            for line_content in f:
                line_stripped = line_content.strip()
                # Skip empty lines and comments
                if not line_stripped or line_stripped.startswith("#"):
                    continue

                # Parse key-value pairs
                if "=" in line_stripped:
                    key, value = line_stripped.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    env_vars[key] = value

        logger.debug(f"Loaded {len(env_vars)} environment variables from {env_path}")
        return env_vars
    except Exception as e:
        logger.error(f"Error loading .env file: {e}", exc_info=True)
        return {}
