"""
Handler for ANSI color codes.
"""

import logging

logger = logging.getLogger(__name__)


class ColorHandler:
    """Handler for ANSI color codes."""

    def __init__(self):
        # Set to False by default to preserve color codes
        self.enabled = True
        logger.debug("Color handler initialized (color preservation enabled)")

    def strip_color(self, text: str) -> str:
        """Remove ANSI color codes from text.

        Args:
            text: Text containing color codes

        Returns:
            Text with color codes removed
        """
        try:
            result = ""
            i = 0
            while i < len(text):
                if text[i] == "\x1b":
                    # Skip until 'm'
                    while i < len(text) and text[i] != "m":
                        i += 1
                    i += 1  # Skip 'm'
                else:
                    result += text[i]
                    i += 1
            return result
        except Exception as e:
            logger.error(f"Error stripping color codes: {e}")
            return text

    def colorize(self, text: str, color_code: str) -> str:
        """Add ANSI color to text.

        Args:
            text: Text to colorize
            color_code: ANSI color code

        Returns:
            Colorized text
        """
        try:
            return f"\x1b[{color_code}m{text}\x1b[0m"
        except Exception as e:
            logger.error(f"Error adding color: {e}")
            return text
