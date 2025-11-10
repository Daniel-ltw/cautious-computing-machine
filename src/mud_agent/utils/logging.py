"""
Logging utilities for the MUD agent.
"""

import logging


class StartupLogFilter(logging.Filter):
    """Filter to consolidate startup logs."""

    def __init__(self):
        super().__init__()
        self.startup_logs = []
        self.enabled = True
        self.startup_categories = {
            "initialization": [],
            "connection": [],
            "threads": [],
            "knowledge_graph": [],
            "map": [],
            "other": [],
        }

    def filter(self, record):
        """Filter startup log messages."""
        if not self.enabled:
            return True

        message = record.getMessage().lower()

        # Check if this is a startup-related log
        startup_keywords = [
            "initialized",
            "started",
            "loaded",
            "manager thread",
            "tick manager",
            "saving",
            "saved",
            "loading",
            "loaded",
            "connecting",
            "connected",
            "knowledge graph",
            "map",
            "room",
            "status",
            "threaded",
            "thread",
            "waiting for",
            "getting",
            "processing",
            "extracting",
            "updating",
        ]

        if any(keyword in message for keyword in startup_keywords):
            # Store the message for later consolidation
            full_message = record.getMessage()
            self.startup_logs.append(full_message)

            # Categorize the message
            if any(kw in message for kw in ["initialized", "loaded", "init"]):
                self.startup_categories["initialization"].append(full_message)
            elif any(kw in message for kw in ["connect", "login", "mud server"]):
                self.startup_categories["connection"].append(full_message)
            elif any(kw in message for kw in ["thread", "tick manager"]):
                self.startup_categories["threads"].append(full_message)
            elif any(kw in message for kw in ["knowledge graph", "entity", "relation"]):
                self.startup_categories["knowledge_graph"].append(full_message)
            elif any(kw in message for kw in ["map", "room", "extracting"]):
                self.startup_categories["map"].append(full_message)
            else:
                self.startup_categories["other"].append(full_message)

            # Don't log it now
            return False
        return True

    def get_consolidated_logs(self) -> list[str]:
        """Get the consolidated startup logs."""
        return self.startup_logs

    def get_categorized_logs(self) -> dict:
        """Get the categorized startup logs."""
        return self.startup_categories

    def disable(self):
        """Disable the filter after startup is complete."""
        self.enabled = False


# Global startup filter instance
startup_filter = StartupLogFilter()


def setup_logging(
    level: str = "INFO",
    format_str: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_file: str | None = "mud_agent.log",
    consolidate_startup: bool = True,
) -> None:
    """Configure logging for the MUD agent.

    Args:
        level: The logging level (e.g., "INFO", "DEBUG", "WARNING")
        format_str: The format string for log messages
        log_file: Optional path to a log file
        consolidate_startup: Whether to consolidate startup logs
    """
    # Convert string level to logging level
    if isinstance(level, str) and level.isdigit():
        # Handle numeric levels passed as strings
        numeric_level = int(level)
    else:
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {level}")

    # Create a root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatter
    formatter = logging.Formatter(format_str)

    # Create file handler if log_file is specified
    if log_file:
        file_handler = logging.FileHandler(log_file, mode="a")
        file_handler.setLevel(numeric_level)  # Use the same level for file logging
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Create console handler for ERROR and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Only show ERROR and CRITICAL in console
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set specific loggers to higher levels to reduce noise
    if level.upper() != "DEBUG":
        # Reduce protocol negotiation noise
        logging.getLogger("src.mud_agent.client.mud_client").setLevel(logging.WARNING)
        logging.getLogger("src.mud_agent.protocols.mccp_handler").setLevel(
            logging.WARNING
        )

        # Only show important protocol messages
        for protocol in [
            "msdp_handler",
            "mccp_handler",
            "color_handler",
        ]:
            logging.getLogger(f"src.mud_agent.protocols.{protocol}").setLevel(
                logging.WARNING
            )

    # Always set GMCP-related loggers to DEBUG level to ensure they're logged to file
    # but not displayed in the command log
    logging.getLogger("src.mud_agent.protocols.gmcp_handler").setLevel(logging.DEBUG)
    logging.getLogger("src.mud_agent.protocols.aardwolf_gmcp").setLevel(logging.DEBUG)

    # Add startup filter if consolidation is enabled
    if consolidate_startup:
        root_logger.addFilter(startup_filter)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging configured with level={level}, format={format_str}, file={log_file}"
    )

    return root_logger


def print_consolidated_startup_logs():
    """Print the consolidated startup logs."""
    if startup_filter.startup_logs:
        logger = logging.getLogger(__name__)
        logger.info("=== Startup Summary ===")

        # Get categorized logs
        categories = startup_filter.get_categorized_logs()

        # Print summary counts by category
        logger.info(
            f"Initialized MUD agent with {len(startup_filter.startup_logs)} operations:"
        )
        for category, logs in categories.items():
            if logs:  # Only show categories with logs
                logger.info(
                    f"- {category.replace('_', ' ').title()}: {len(logs)} operations"
                )

        # Print detailed logs only at DEBUG level
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("=== Detailed Startup Logs ===")
            for category, logs in categories.items():
                if logs:
                    logger.debug(f"--- {category.replace('_', ' ').title()} ---")
                    for log in logs:
                        logger.debug(f"  {log}")

        # Disable the filter now that startup is complete
        startup_filter.disable()


def disable_startup_consolidation():
    """Disable startup log consolidation."""
    startup_filter.disable()
