"""Buff Manager for smart spell/skill recast management.

Detects buff expiry from server text and recasts via Aardwolf's native
'spellup learned' command. Combat-aware with a periodic fallback timer.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Buff expiry text patterns (case-insensitive substring matching)
BUFF_EXPIRY_PATTERNS = [
    # Skills
    "you are no longer hidden.",
    "you step out of the shadows.",
    "you feel less nimble.",
    # Spells - common spellups
    "your sanctuary fades.",
    "your shield fades.",
    "your armor fades.",
    "you feel less protected.",
    "you slow down.",
    "your protection fades.",
    "you become visible.",
    # Generic catch-alls
    "has worn off.",
    "wears off.",
    "spell fades.",
]

# Debounce window in seconds — multiple expiries within this window
# trigger only one recast
DEBOUNCE_SECONDS = 1.5

# Fallback timer interval in seconds
FALLBACK_INTERVAL = 120.0

# The command to recast all buffs
SPELLUP_COMMAND = "spellup learned"


class BuffManager:
    """Manages buff/spellup recasting based on expiry detection.

    Subscribes to client data events to detect buff expiry messages,
    then recasts via 'spellup learned'. Defers recast during combat
    and runs a periodic fallback timer.
    """

    def __init__(self, agent):
        """Initialize the buff manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        self.active: bool = False
        self._recast_pending: bool = False
        self._debounce_task: asyncio.Task | None = None
        self._fallback_task: asyncio.Task | None = None

    def _check_buff_expiry(self, text: str) -> bool:
        """Check if text contains a buff expiry message.

        Args:
            text: Incoming server text

        Returns:
            True if a buff expiry pattern was detected
        """
        if not text:
            return False

        text_lower = text.lower()
        return any(pattern in text_lower for pattern in BUFF_EXPIRY_PATTERNS)

    async def _request_recast(self) -> None:
        """Send the spellup command to recast all buffs."""
        try:
            await self.agent.send_command(SPELLUP_COMMAND)
            self.logger.info("Sent spellup recast command")
        except Exception as e:
            self.logger.error(f"Error sending spellup command: {e}")

    def _on_buff_expired(self, buff_name: str) -> None:
        """Handle a detected buff expiry.

        Triggers a debounced recast. Multiple expiries within the debounce
        window produce only one recast command.

        Args:
            buff_name: Name/description of the expired buff (for logging)
        """
        if not self.active:
            return

        self.logger.debug(f"Buff expired: {buff_name}")

        # Cancel existing debounce task and start a new one
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounced_recast())

    async def _debounced_recast(self) -> None:
        """Wait for the debounce window, then recast."""
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            if self.active:
                await self._request_recast()
        except asyncio.CancelledError:
            pass  # Debounce was reset by another expiry
