"""
Tests for the logging utility.
"""

import logging

import pytest

# Import helper to add src to Python path
from test_helper import *

from mud_agent.utils.logging import setup_logging


class TestLogging:
    """Tests for the logging utility."""

    def test_setup_logging_with_defaults(self):
        """Test setting up logging with default values."""
        # Remove all handlers before test
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
        # Call setup_logging with default values
        setup_logging()
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)

    def test_setup_logging_with_custom_values(self):
        """Test setting up logging with custom values."""
        # Remove all handlers before test
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
        # Call setup_logging with custom values
        setup_logging(level="DEBUG", format_str="%(message)s", log_file="test.log")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)

    def test_setup_logging_with_invalid_level(self):
        """Test setting up logging with an invalid level."""
        from mud_agent.utils.logging import setup_logging

        with pytest.raises(ValueError):
            setup_logging(level="INVALID")

    def test_setup_logging_with_numeric_level(self):
        """Test setting up logging with a numeric level."""
        # Remove all handlers before test
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
        # Call setup_logging with a numeric level
        setup_logging(level="10")  # DEBUG level
        root_logger = logging.getLogger()
        assert root_logger.level == 10
        assert not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers)
