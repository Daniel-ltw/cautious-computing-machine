"""Combat Skill Manager for automated skill rotation during combat.

Implements a state machine (IDLE -> OPENING -> ROTATING) that fires opener
skills followed by a cycling rotation of combat skills each round. Includes
HP-based flee logic with a configurable threshold and command.
"""

import asyncio
import contextlib
import logging

logger = logging.getLogger(__name__)

# Combat round indicator patterns (case-insensitive substring matching)
COMBAT_ROUND_PATTERNS = [
    "you hit",
    "hits you",
    "misses you",
    "you miss",
    "you dodge",
    "dodges your",
    "you parry",
    "parries your",
    "your attack",
    "attacks you",
]

# Debounce window in seconds — multiple round indicators within this window
# trigger only one skill fire
DEBOUNCE_SECONDS = 0.1


class CombatSkillManager:
    """Manages automated combat skill rotation based on round detection.

    Subscribes to client data events to detect combat round indicators,
    then fires skills according to a configurable opener + rotation sequence.
    Monitors HP and triggers flee when below threshold.

    State machine: IDLE -> OPENING -> ROTATING -> IDLE
    FLEEING can be entered from any combat state.
    """

    def __init__(self, agent):
        """Initialize the combat skill manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        self.active: bool = False
        self.state: str = "IDLE"
        self._opener_index: int = 0
        self._rotation_index: int = 0
        self._pending_round_task: asyncio.Task | None = None
        self._was_in_combat: bool = False

    @property
    def enabled(self) -> bool:
        """Whether the manager is enabled (any combat skills configured)."""
        return bool(
            self.agent.config.agent.combat_opener_skills
            or self.agent.config.agent.combat_rotation_skills
        )

    async def setup(self) -> None:
        """Subscribe to client data events.

        Called during agent setup_managers(). Subscribes to the data stream
        but does not start active combat management -- call start() for that.
        Skips subscription if not enabled (no skills configured).
        """
        if not self.enabled:
            self.logger.debug("CombatSkillManager disabled (no skills configured)")
            return

        if hasattr(self.agent, "client") and hasattr(self.agent.client, "events"):
            self.agent.client.events.on("data", self._handle_incoming_data)
            self.logger.info("CombatSkillManager subscribed to client data events")
        else:
            self.logger.warning(
                "Agent client or events not available for subscription"
            )

    async def start(self) -> None:
        """Enable combat skill management."""
        self.active = True
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
        self._was_in_combat = False
        self.logger.info("CombatSkillManager started")

    async def stop(self) -> None:
        """Disable combat skill management and cancel pending tasks."""
        self.active = False
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
        self._was_in_combat = False

        if self._pending_round_task and not self._pending_round_task.done():
            self._pending_round_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pending_round_task
        self._pending_round_task = None

        self.logger.info("CombatSkillManager stopped")

    def _handle_incoming_data(self, text: str) -> None:
        """Handle incoming server data.

        Checks for combat state transitions and combat round indicators.

        Args:
            text: Raw text from the MUD server
        """
        if not self.active:
            return

        # Check for combat state transition (was in combat -> no longer)
        currently_in_combat = self.agent.combat_manager.in_combat
        if self._was_in_combat and not currently_in_combat:
            self._on_combat_ended()
        self._was_in_combat = currently_in_combat

        # If in combat, check for round indicators
        if currently_in_combat and self._is_combat_round(text):
            self._schedule_round()

    def _is_combat_round(self, text: str) -> bool:
        """Check if text contains a combat round indicator.

        Args:
            text: Incoming server text

        Returns:
            True if a combat round pattern was detected
        """
        if not text:
            return False

        text_lower = text.lower()
        return any(pattern in text_lower for pattern in COMBAT_ROUND_PATTERNS)

    def _schedule_round(self) -> None:
        """Schedule a debounced combat round handler.

        If a pending round task already exists, does nothing (debounce).
        Otherwise creates a new task for the debounced round.
        """
        if self._pending_round_task and not self._pending_round_task.done():
            return  # Debounce: already scheduled

        self._pending_round_task = asyncio.create_task(self._debounced_round())

    async def _debounced_round(self) -> None:
        """Wait for the debounce window, then fire the combat round."""
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            if self.active:
                await self._on_combat_round()
        except asyncio.CancelledError:
            pass  # Task was cancelled during stop()

    async def _on_combat_round(self) -> None:
        """Handle a combat round. Main state machine logic.

        Steps:
        1. Guard: not active, not in combat, or fleeing -> return
        2. Check HP against flee threshold
        3. State transitions: IDLE -> OPENING/ROTATING, OPENING -> ROTATING
        4. Send the appropriate skill command
        """
        if not self.active:
            return
        if not self.agent.combat_manager.in_combat:
            return
        if self.state == "FLEEING":
            return

        # Check HP for flee
        hp_max = self.agent.state_manager.hp_max
        hp_current = self.agent.state_manager.hp_current
        flee_threshold = self.agent.config.agent.combat_flee_threshold
        flee_command = self.agent.config.agent.combat_flee_command

        if hp_max <= 0 or (hp_current / hp_max) < flee_threshold:
            self.state = "FLEEING"
            self.logger.warning(
                f"HP critical ({hp_current}/{hp_max}), fleeing with '{flee_command}'"
            )
            await self.agent.send_command(flee_command)
            return

        openers = self.agent.config.agent.combat_opener_skills
        rotation = self.agent.config.agent.combat_rotation_skills

        # State transitions and skill firing
        if self.state == "IDLE" and openers:
            self.state = "OPENING"

        if self.state == "OPENING":
            if self._opener_index < len(openers):
                skill = openers[self._opener_index]
                self._opener_index += 1
                self.logger.debug(f"Opening skill: {skill}")
                await self.agent.send_command(skill)
                # Check if all openers are done
                if self._opener_index >= len(openers):
                    self.state = "ROTATING"
                return
            else:
                # All openers done, transition to rotating
                self.state = "ROTATING"

        if self.state == "IDLE" and not openers:
            self.state = "ROTATING"

        if self.state == "ROTATING" and rotation:
            skill = rotation[self._rotation_index % len(rotation)]
            self._rotation_index += 1
            self.logger.debug(f"Rotation skill: {skill}")
            await self.agent.send_command(skill)

    def _on_combat_ended(self) -> None:
        """Handle combat ending. Resets state machine."""
        self.logger.info("Combat ended, resetting skill rotation state")
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
