"""Buff Manager for smart spell/skill recast management.

Detects buff expiry from server text and recasts via Aardwolf's native
'spellup learned' command. Combat-aware with a periodic fallback timer.
"""

import asyncio
import contextlib
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
        self._was_in_combat: bool = False

    async def setup(self) -> None:
        """Subscribe to client data events.

        Called during agent setup_managers(). Subscribes to the data stream
        but does not start active buff management — call start() for that.
        """
        if hasattr(self.agent, "client") and hasattr(self.agent.client, "events"):
            self.agent.client.events.on("data", self._handle_incoming_data)
            self.logger.info("BuffManager subscribed to client data events")
        else:
            self.logger.warning("Agent client or events not available for subscription")

    async def start(self) -> None:
        """Enable buff management and start the fallback timer."""
        self.active = True
        self._recast_pending = False
        self._was_in_combat = False
        self._fallback_task = asyncio.create_task(self._fallback_timer_loop())
        self.logger.info("BuffManager started")

    async def stop(self) -> None:
        """Disable buff management and cancel all tasks."""
        self.active = False
        self._recast_pending = False
        self._was_in_combat = False

        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._debounce_task
        self._debounce_task = None

        if self._fallback_task and not self._fallback_task.done():
            self._fallback_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fallback_task
        self._fallback_task = None

        self.logger.info("BuffManager stopped")

    def _handle_incoming_data(self, text: str) -> None:
        """Handle incoming server data.

        Checks for combat state transitions and buff expiry patterns.

        Args:
            text: Raw text from the MUD server
        """
        if not self.active:
            return

        # Check for combat state transition
        currently_in_combat = self.agent.combat_manager.in_combat
        if self._was_in_combat and not currently_in_combat:
            self._on_combat_state_changed()
        self._was_in_combat = currently_in_combat

        # Check for buff expiry
        if self._check_buff_expiry(text):
            buff_desc = text.strip()[:60]
            self._on_buff_expired(buff_desc)

    async def _fallback_timer_loop(self) -> None:
        """Periodic fallback recast loop.

        Runs 'spellup learned' every FALLBACK_INTERVAL seconds to catch
        missed expiry events (death, dispel, login, unknown patterns).
        """
        try:
            while self.active:
                await asyncio.sleep(FALLBACK_INTERVAL)
                if self.active and not self.agent.combat_manager.in_combat:
                    self.logger.debug("Fallback timer: sending spellup")
                    await self._request_recast()
        except asyncio.CancelledError:
            self.logger.debug("Fallback timer cancelled")

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
            self.logger.error(f"Error sending spellup command: {e}", exc_info=True)

    def _on_buff_expired(self, buff_name: str) -> None:
        """Handle a detected buff expiry.

        If in combat, defers recast until combat ends. Otherwise triggers
        a debounced recast.

        Args:
            buff_name: Name/description of the expired buff (for logging)
        """
        if not self.active:
            return

        self.logger.debug(f"Buff expired: {buff_name}")

        # Defer during combat
        if self.agent.combat_manager.in_combat:
            self._recast_pending = True
            self.logger.debug("In combat — deferring recast")
            return

        # Cancel existing debounce task and start a new one
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounced_recast())

    def _on_combat_state_changed(self) -> None:
        """Handle combat state change.

        If combat just ended and there's a pending recast, trigger it.
        """
        if self.agent.combat_manager.in_combat:
            return

        if self._recast_pending:
            self._recast_pending = False
            if not self.active:
                return
            self.logger.info("Combat ended — triggering deferred recast")
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
