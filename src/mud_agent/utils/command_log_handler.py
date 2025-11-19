"""
Logging handler that forwards error logs to the command log.
"""

import logging
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..widgets.command_log import CommandLog


class CommandLogHandler(logging.Handler):
    """A logging handler that forwards messages to the Textual command log.

    This handler is designed to be used with the Python logging module to route
    log messages to the CommandLog widget in the Textual UI.
    """

    _instance = None
    _command_log: Optional["CommandLog"] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, command_log: Optional["CommandLog"] = None):
        """Initialize the handler.

        Args:
            command_log: The CommandLog widget to write to.
        """
        super().__init__()
        if command_log and not self._command_log:
            self._command_log = command_log

        # Define filter patterns for GMCP and other debug messages
        self.gmcp_pattern = re.compile(r"Received GMCP message: Core\\.Hello")
        self.debug_patterns = [
            re.compile(r"Received data: .*"),
            re.compile(r"Processing line: .*"),
            re.compile(r"Updating vitals:.*|Updating stats:.*|Updating needs:.*|Updating worth:.*"),
            re.compile(r"(HP|MP|MV) changed from .* to .*"),
            re.compile(r"(STR|INT|WIS|DEX|CON) changed from .* to .*"),
            re.compile(r"(Hunger|Thirst) changed from .* to .*"),
            re.compile(r"(Gold|Bank) changed from .* to .*"),
            re.compile(r"Received GMCP message: Room\\.Info"),
            re.compile(r"Received GMCP message: Char\\.Vitals"),
            re.compile(r"Received GMCP message: Char\\.Needs"),
            re.compile(r"Received GMCP message: Char\\.Worth"),
            re.compile(r"Received GMCP message: Char\\.Stats"),
            re.compile(r"Received GMCP message: Char\\.StatusVars"),
            re.compile(r"Received GMCP message: Char\\.Items\\.Update"),
            re.compile(r"Received GMCP message: Char\\.Skills\\.Update"),
            re.compile(r"Received GMCP message: Comm\\.Channel"),
            re.compile(r"Received GMCP message: IRE\\.Target\\.Set"),
            re.compile(r"Received GMCP message: IRE\\.Rift\\.List"),
            re.compile(r"Received GMCP message: IRE\\.Rift\\.Change"),
            re.compile(r"Received GMCP message: IRE\\.Time"),
            re.compile(r"Received GMCP message: Client\\.GUI"),
            re.compile(r"Processed comprehensive character data with sections: .*"),
            re.compile(r"Updated static widget to .*"),
            re.compile(r"GMCP Vitals: .*"),
            re.compile(r"GMCP Combined: .*"),
            re.compile(r"State manager .*"),
            re.compile(r"Updating widget at \(.*"),
            re.compile(r"Room update received: .*"),
        ]
        self.gcmp_terms = [
            "GMCP"
        ]

    def set_command_log(self, command_log: "CommandLog") -> None:
        """Set the CommandLog widget for the handler.

        Args:
            command_log: The CommandLog widget to write to.
        """
        self._command_log = command_log

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record.

        This method is called by the logging framework for each log record.
        It formats the message and writes it to the command log, filtering
        out noisy debug messages.
        """
        if not self._command_log:
            return

        # Filter out noisy debug messages
        if record.levelno == logging.DEBUG or record.levelno == logging.INFO:
            log_message = record.getMessage()
            if self.gmcp_pattern.search(log_message):
                return  # Skip Core.Hello messages

            for pattern in self.debug_patterns:
                if pattern.search(log_message):
                    return  # Skip other noisy debug messages

        try:
            # Write to the CommandLog widget using its supported API
            # CommandLog extends Textual's RichLog, which provides `write(...)`
            # if not self._should_filter_message(self.format(record), record):
            self._command_log.write(self.format(record))
        except Exception:
            self.handleError(record)

    def _should_filter_message(self, msg, record):
        """Determine if a message should be filtered out.

        Args:
            msg: The formatted message string
            record: The log record

        Returns:
            bool: True if the message should be filtered, False otherwise
        """
        # Always filter GMCP-related messages
        if self._is_gmcp_message(msg):
            return True

        # Filter debug messages if debug filtering is enabled
        if self.filter_debug and self._is_debug_message(msg, record):
            return True

        return False

    def _is_gmcp_message(self, msg):
        """Check if a message is GMCP-related.

        Args:
            msg: The message to check

        Returns:
            bool: True if the message is GMCP-related, False otherwise
        """
        # Check for GMCP protocol terms
        if any(term.lower() in msg.lower() for term in self.gmcp_terms):
            return True

        # Check if the message is a raw JSON dump or GMCP data structure
        if (
            msg.startswith("{")
            and msg.endswith("}")
            and any(json_term in msg for json_term in self.json_gmcp_terms)
        ):
            return True

        # Check if it's a raw GMCP protocol message
        if (
            msg.startswith("GMCP: ")
            or "GMCP Error:" in msg
            or "Invalid GMCP tag:" in msg
        ):
            return True

        # Check for JSON-like content (likely GMCP data)
        if (
            "{" in msg
            and "}" in msg
            and (":" in msg or "," in msg)
            and any(term in msg.lower() for term in ["char", "room", "map", "quest"])
        ):
            return True

        # Check for array-like content (likely GMCP data)
        if (
            "[" in msg
            and "]" in msg
            and (":" in msg or "," in msg)
            and any(term in msg.lower() for term in ["char", "room", "map", "quest"])
        ):
            return True

        return False

    def _is_debug_message(self, msg, record):
        """Check if a message is a debug/verbose message that should be filtered.

        Args:
            msg: The message to check
            record: The log record

        Returns:
            bool: True if the message should be filtered as debug, False otherwise
        """
        # Don't filter ERROR or CRITICAL level messages (they're important)
        if record.levelno >= logging.ERROR:
            return False

        # Check for debug patterns
        msg_lower = msg.lower()
        for pattern in self.debug_patterns:
            if pattern.lower() in msg_lower:
                return True

        # Filter messages that look like debug output (contain specific debug indicators)
        debug_indicators = [
            "debug:", "[debug]", "debugging", "trace:", "[trace]",
            "verbose:", "[verbose]", "info:", "[info]",
        ]

        for indicator in debug_indicators:
            if indicator in msg_lower:
                return True

        return False

    # Note: Older duplicate set_command_log removed; use the method above

    def configure_filtering(self, filter_debug=None, min_level=None):
        """Configure filtering behavior at runtime.

        Args:
            filter_debug: Whether to filter debug messages (None to keep current)
            min_level: Minimum log level to handle (None to keep current)
        """
        if filter_debug is not None:
            self.filter_debug = filter_debug
        if min_level is not None:
            self.setLevel(min_level)

    def add_debug_pattern(self, pattern):
        """Add a custom debug pattern to filter.

        Args:
            pattern: String pattern to add to debug filtering
        """
        if pattern not in self.debug_patterns:
            self.debug_patterns.append(pattern)

    def remove_debug_pattern(self, pattern):
        """Remove a debug pattern from filtering.

        Args:
            pattern: String pattern to remove from debug filtering
        """
        if pattern in self.debug_patterns:
            self.debug_patterns.remove(pattern)

    def get_filter_status(self):
        """Get current filtering configuration.

        Returns:
            dict: Current filtering settings
        """
        return {
            'filter_debug': self.filter_debug,
            'min_level': self.level,
            'debug_patterns_count': len(self.debug_patterns),
            'gmcp_terms_count': len(self.gmcp_terms)
        }
