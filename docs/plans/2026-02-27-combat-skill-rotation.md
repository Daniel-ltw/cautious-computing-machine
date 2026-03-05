# Combat Skill Rotation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-fire configurable attack skills/spells during combat with opener/rotation categories and HP-based flee safety.

**Architecture:** A new `CombatSkillManager` class follows the `BuffManager` pattern — event-driven, lifecycle-managed, config-driven. It subscribes to incoming server data, detects combat rounds, and sends one skill per round cycling through openers then rotation. HP monitoring triggers a flee command when below a configurable threshold.

**Tech Stack:** Python 3.12, asyncio, peewee (existing), pytest + unittest.mock

---

### Task 1: Add combat config fields to AgentConfig

**Files:**
- Modify: `src/mud_agent/config/config.py`
- Modify: `.env.example`
- Test: `tests/config/test_agent_config.py`

**Step 1: Write the failing tests**

Add these tests to `tests/config/test_agent_config.py` inside `TestAgentConfig`:

```python
def test_combat_defaults(self):
    """Test that combat config defaults are set correctly."""
    config = AgentConfig()
    assert config.combat_opener_skills == []
    assert config.combat_rotation_skills == []
    assert config.combat_flee_threshold == 0.25
    assert config.combat_flee_command == "flee"

def test_combat_from_env(self):
    """Test creating combat config from environment variables."""
    with patch.dict(
        os.environ,
        {
            "COMBAT_OPENER_SKILLS": "backstab",
            "COMBAT_ROTATION_SKILLS": "circle,dirt kick,kick",
            "COMBAT_FLEE_THRESHOLD": "0.3",
            "COMBAT_FLEE_COMMAND": "recall",
        },
    ):
        config = AgentConfig.from_env()
        assert config.combat_opener_skills == ["backstab"]
        assert config.combat_rotation_skills == ["circle", "dirt kick", "kick"]
        assert config.combat_flee_threshold == 0.3
        assert config.combat_flee_command == "recall"

def test_combat_from_env_empty(self):
    """Test that missing combat env vars use defaults."""
    with patch.dict(os.environ, {}, clear=True):
        config = AgentConfig.from_env()
        assert config.combat_opener_skills == []
        assert config.combat_rotation_skills == []
        assert config.combat_flee_threshold == 0.25
        assert config.combat_flee_command == "flee"

def test_combat_from_dict(self):
    """Test creating combat config from a dictionary."""
    config_dict = {
        "combat_opener_skills": ["backstab"],
        "combat_rotation_skills": ["circle", "kick"],
        "combat_flee_threshold": 0.5,
        "combat_flee_command": "recall",
    }
    config = AgentConfig.from_dict(config_dict)
    assert config.combat_opener_skills == ["backstab"]
    assert config.combat_rotation_skills == ["circle", "kick"]
    assert config.combat_flee_threshold == 0.5
    assert config.combat_flee_command == "recall"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/config/test_agent_config.py -v -x`
Expected: FAIL — `AgentConfig` has no `combat_opener_skills` attribute

**Step 3: Implement the config changes**

In `src/mud_agent/config/config.py`, modify `AgentConfig`:

- Add fields to the dataclass:
  ```python
  combat_opener_skills: list[str]
  combat_rotation_skills: list[str]
  combat_flee_threshold: float
  combat_flee_command: str
  ```

- Update `__init__` to accept and default the new fields:
  ```python
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
      self.combat_opener_skills = combat_opener_skills or []
      self.combat_rotation_skills = combat_rotation_skills or []
      self.combat_flee_threshold = combat_flee_threshold
      self.combat_flee_command = combat_flee_command
  ```

- Update `from_env`:
  ```python
  opener_env = os.getenv("COMBAT_OPENER_SKILLS")
  opener_skills = (
      [cmd.strip() for cmd in opener_env.split(",") if cmd.strip()]
      if opener_env else None
  )
  rotation_env = os.getenv("COMBAT_ROTATION_SKILLS")
  rotation_skills = (
      [cmd.strip() for cmd in rotation_env.split(",") if cmd.strip()]
      if rotation_env else None
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
  ```

- Update `from_dict`:
  ```python
  return cls(
      autocast_commands=config.get("autocast_commands"),
      recall_command=config.get("recall_command"),
      combat_opener_skills=config.get("combat_opener_skills"),
      combat_rotation_skills=config.get("combat_rotation_skills"),
      combat_flee_threshold=config.get("combat_flee_threshold", 0.25),
      combat_flee_command=config.get("combat_flee_command", "flee"),
  )
  ```

Update `.env.example` — add below the `RECALL` line:
```
# Combat Skill Rotation (optional)
# COMBAT_OPENER_SKILLS=backstab
# COMBAT_ROTATION_SKILLS=circle,dirt kick,kick
# COMBAT_FLEE_THRESHOLD=0.25
# COMBAT_FLEE_COMMAND=flee
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/config/test_agent_config.py tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/mud_agent/config/config.py .env.example tests/config/test_agent_config.py
git commit -m "feat(config): add combat skill rotation config fields"
```

---

### Task 2: Create CombatSkillManager with state machine and round detection

**Files:**
- Create: `src/mud_agent/agent/combat_skill_manager.py`
- Create: `tests/agent/test_combat_skill_manager.py`

**Step 1: Write the failing tests**

Create `tests/agent/test_combat_skill_manager.py`:

```python
"""Tests for CombatSkillManager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from mud_agent.agent.combat_skill_manager import CombatSkillManager


def make_agent(
    opener_skills=None,
    rotation_skills=None,
    flee_threshold=0.25,
    flee_command="flee",
    in_combat=False,
    hp_current=100,
    hp_max=100,
):
    """Create a mock agent with configurable combat settings."""
    agent = MagicMock()
    agent.send_command = AsyncMock()
    agent.client = MagicMock()
    agent.client.events = MagicMock()
    agent.combat_manager = MagicMock()
    agent.combat_manager.in_combat = in_combat
    agent.state_manager = MagicMock()
    agent.state_manager.hp_current = hp_current
    agent.state_manager.hp_max = hp_max
    agent.config = MagicMock()
    agent.config.agent = MagicMock()
    agent.config.agent.combat_opener_skills = opener_skills or []
    agent.config.agent.combat_rotation_skills = rotation_skills or []
    agent.config.agent.combat_flee_threshold = flee_threshold
    agent.config.agent.combat_flee_command = flee_command
    return agent


class TestCombatSkillManagerInit:
    """Test initialization and defaults."""

    def test_initializes_idle(self):
        agent = make_agent()
        mgr = CombatSkillManager(agent)
        assert mgr.state == "IDLE"
        assert mgr.active is False

    def test_disabled_when_no_skills_configured(self):
        agent = make_agent(opener_skills=[], rotation_skills=[])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is False

    def test_enabled_when_rotation_configured(self):
        agent = make_agent(rotation_skills=["circle", "kick"])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is True

    def test_enabled_when_only_openers_configured(self):
        agent = make_agent(opener_skills=["backstab"])
        mgr = CombatSkillManager(agent)
        assert mgr.enabled is True


class TestCombatSkillManagerLifecycle:
    """Test setup/start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_setup_subscribes_to_events(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.setup()
        agent.client.events.on.assert_called_once_with(
            "data", mgr._handle_incoming_data
        )

    @pytest.mark.asyncio
    async def test_setup_skips_when_disabled(self):
        agent = make_agent()
        mgr = CombatSkillManager(agent)
        await mgr.setup()
        agent.client.events.on.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_activates(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.start()
        assert mgr.active is True

    @pytest.mark.asyncio
    async def test_stop_deactivates_and_resets(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        await mgr.start()
        await mgr.stop()
        assert mgr.active is False
        assert mgr.state == "IDLE"


class TestCombatSkillManagerRoundDetection:
    """Test combat round detection from server text."""

    def test_detects_you_hit(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr._is_combat_round("Your slash hits a goblin.") is True

    def test_detects_hits_you(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr._is_combat_round("A goblin hits you.") is True

    def test_detects_dodge(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr._is_combat_round("You dodge the attack.") is True

    def test_ignores_normal_text(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr._is_combat_round("A rat scurries by.") is False

    def test_ignores_empty_text(self):
        agent = make_agent(rotation_skills=["kick"])
        mgr = CombatSkillManager(agent)
        assert mgr._is_combat_round("") is False


class TestCombatSkillManagerStateTransitions:
    """Test the state machine transitions."""

    @pytest.mark.asyncio
    async def test_idle_to_opening_on_combat(self):
        """First combat round with openers transitions IDLE -> OPENING."""
        agent = make_agent(
            opener_skills=["backstab"],
            rotation_skills=["kick"],
            in_combat=True,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()
        assert mgr.state == "OPENING"
        agent.send_command.assert_called_once_with("backstab")

    @pytest.mark.asyncio
    async def test_idle_to_rotating_when_no_openers(self):
        """First combat round without openers transitions IDLE -> ROTATING."""
        agent = make_agent(rotation_skills=["kick", "circle"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_once_with("kick")

    @pytest.mark.asyncio
    async def test_opening_to_rotating_after_all_openers(self):
        """After all openers sent, transitions OPENING -> ROTATING."""
        agent = make_agent(
            opener_skills=["backstab"],
            rotation_skills=["kick"],
            in_combat=True,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        # Round 1: opener
        await mgr._on_combat_round()
        assert mgr.state == "OPENING"
        agent.send_command.assert_called_with("backstab")

        # Round 2: rotation starts
        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"
        agent.send_command.assert_called_with("kick")

    @pytest.mark.asyncio
    async def test_rotation_cycles(self):
        """Rotation skills cycle through the list and wrap around."""
        agent = make_agent(rotation_skills=["kick", "circle"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()  # kick
        await mgr._on_combat_round()  # circle
        await mgr._on_combat_round()  # kick (wraps)

        calls = [c.args[0] for c in agent.send_command.call_args_list]
        assert calls == ["kick", "circle", "kick"]

    @pytest.mark.asyncio
    async def test_combat_end_resets_to_idle(self):
        """Combat ending resets state to IDLE."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()
        assert mgr.state == "ROTATING"

        # Combat ends
        agent.combat_manager.in_combat = False
        mgr._on_combat_ended()
        assert mgr.state == "IDLE"
        assert mgr._opener_index == 0
        assert mgr._rotation_index == 0


class TestCombatSkillManagerFleeThreshold:
    """Test HP-based flee behavior."""

    @pytest.mark.asyncio
    async def test_flee_when_hp_below_threshold(self):
        """Should send flee command when HP% is below threshold."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            flee_command="flee",
            in_combat=True,
            hp_current=20,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()
        assert mgr.state == "FLEEING"
        agent.send_command.assert_called_once_with("flee")

    @pytest.mark.asyncio
    async def test_no_flee_when_hp_above_threshold(self):
        """Should not flee when HP% is above threshold."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            in_combat=True,
            hp_current=80,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()
        assert mgr.state != "FLEEING"
        agent.send_command.assert_called_once_with("kick")

    @pytest.mark.asyncio
    async def test_fleeing_does_not_fire_skills(self):
        """Once fleeing, no more skills should fire."""
        agent = make_agent(
            rotation_skills=["kick"],
            flee_threshold=0.25,
            in_combat=True,
            hp_current=20,
            hp_max=100,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()  # flee
        agent.send_command.reset_mock()

        await mgr._on_combat_round()  # should not fire anything
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_flee_with_zero_max_hp_does_not_crash(self):
        """Edge case: zero max HP should not divide by zero."""
        agent = make_agent(
            rotation_skills=["kick"],
            in_combat=True,
            hp_current=0,
            hp_max=0,
        )
        mgr = CombatSkillManager(agent)
        mgr.active = True

        await mgr._on_combat_round()  # should not crash
        # Should flee as a safety measure when we can't compute HP%
        assert mgr.state == "FLEEING"


class TestCombatSkillManagerDebounce:
    """Test debounce behavior."""

    @pytest.mark.asyncio
    async def test_rapid_rounds_debounced(self):
        """Multiple round messages within debounce window should fire once."""
        agent = make_agent(rotation_skills=["kick", "circle"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        # Simulate two rapid combat messages
        mgr._handle_incoming_data("Your slash hits a goblin.")
        mgr._handle_incoming_data("A goblin misses you.")

        # Wait for debounce to settle
        await asyncio.sleep(0.2)
        if mgr._pending_round_task and not mgr._pending_round_task.done():
            await mgr._pending_round_task

        # Should only fire one skill
        assert agent.send_command.call_count == 1


class TestCombatSkillManagerEventHandling:
    """Test incoming data event processing end-to-end."""

    @pytest.mark.asyncio
    async def test_incoming_combat_text_triggers_skill(self):
        """Combat text while active should fire a skill."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        mgr._handle_incoming_data("Your slash hits a goblin.")
        await asyncio.sleep(0.2)
        if mgr._pending_round_task and not mgr._pending_round_task.done():
            await mgr._pending_round_task

        agent.send_command.assert_called_once_with("kick")

    @pytest.mark.asyncio
    async def test_incoming_text_when_inactive(self):
        """Combat text when inactive should not fire anything."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = False

        mgr._handle_incoming_data("Your slash hits a goblin.")
        await asyncio.sleep(0.2)
        agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_combat_end_detected_from_data(self):
        """Combat ending should be detected and reset state."""
        agent = make_agent(rotation_skills=["kick"], in_combat=True)
        mgr = CombatSkillManager(agent)
        mgr.active = True

        mgr._handle_incoming_data("Your slash hits a goblin.")
        await asyncio.sleep(0.2)
        if mgr._pending_round_task and not mgr._pending_round_task.done():
            await mgr._pending_round_task
        assert mgr.state == "ROTATING"

        # Combat ends
        agent.combat_manager.in_combat = False
        mgr._handle_incoming_data("The goblin is dead!")
        assert mgr.state == "IDLE"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/test_combat_skill_manager.py -v -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'mud_agent.agent.combat_skill_manager'`

**Step 3: Implement CombatSkillManager**

Create `src/mud_agent/agent/combat_skill_manager.py`:

```python
"""Combat Skill Manager — auto-fires attack skills during combat.

Follows the BuffManager pattern: event-driven, lifecycle-managed, config-driven.
Subscribes to incoming server data, detects combat rounds, and sends one skill
per round cycling through openers then rotation. HP monitoring triggers flee.
"""

import asyncio
import logging
import time


# Minimum interval between skill fires (seconds)
DEBOUNCE_INTERVAL = 0.1

# Combat round indicators — subset of CombatManager's patterns
ROUND_INDICATORS = [
    "You hit",
    "hits you",
    "misses you",
    "You miss",
    "You dodge",
    "dodges your",
    "You parry",
    "parries your",
    "Your attack",
    "attacks you",
]


class CombatSkillManager:
    """Fires configured combat skills automatically during combat rounds.

    State machine:
        IDLE -> OPENING -> ROTATING -> IDLE
        ROTATING -> FLEEING -> IDLE
    """

    def __init__(self, agent):
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        self.active: bool = False
        self.state: str = "IDLE"
        self._opener_index: int = 0
        self._rotation_index: int = 0
        self._last_fire_time: float = 0
        self._pending_round_task: asyncio.Task | None = None
        self._was_in_combat: bool = False

    @property
    def enabled(self) -> bool:
        """Whether combat skills are configured."""
        cfg = self.agent.config.agent
        return bool(cfg.combat_opener_skills or cfg.combat_rotation_skills)

    async def setup(self) -> None:
        """Subscribe to client data events."""
        if not self.enabled:
            self.logger.info("CombatSkillManager disabled — no skills configured")
            return
        if hasattr(self.agent, "client") and hasattr(self.agent.client, "events"):
            self.agent.client.events.on("data", self._handle_incoming_data)
            self.logger.info("CombatSkillManager subscribed to client data events")
        else:
            self.logger.warning("Agent client or events not available for subscription")

    async def start(self) -> None:
        """Activate combat skill rotation."""
        self.active = True
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
        self._was_in_combat = False
        self.logger.info("CombatSkillManager started")

    async def stop(self) -> None:
        """Deactivate and clean up."""
        self.active = False
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
        self._was_in_combat = False

        if self._pending_round_task and not self._pending_round_task.done():
            self._pending_round_task.cancel()
            try:
                await self._pending_round_task
            except asyncio.CancelledError:
                pass
        self._pending_round_task = None
        self.logger.info("CombatSkillManager stopped")

    def _handle_incoming_data(self, text: str) -> None:
        """Handle incoming server data."""
        if not self.active:
            return

        # Detect combat end transition
        currently_in_combat = self.agent.combat_manager.in_combat
        if self._was_in_combat and not currently_in_combat:
            self._on_combat_ended()
        self._was_in_combat = currently_in_combat

        # Only process during combat
        if not currently_in_combat:
            return

        # Check for combat round
        if self._is_combat_round(text):
            self._schedule_round()

    def _is_combat_round(self, text: str) -> bool:
        """Check if text indicates a new combat round."""
        if not text:
            return False
        for indicator in ROUND_INDICATORS:
            if indicator.lower() in text.lower():
                return True
        return False

    def _schedule_round(self) -> None:
        """Schedule a combat round action with debounce."""
        now = time.monotonic()
        if now - self._last_fire_time < DEBOUNCE_INTERVAL:
            return
        # Cancel any pending round task and schedule a new one
        if self._pending_round_task and not self._pending_round_task.done():
            return  # Already pending
        self._pending_round_task = asyncio.create_task(self._debounced_round())

    async def _debounced_round(self) -> None:
        """Wait briefly then fire the next skill."""
        await asyncio.sleep(DEBOUNCE_INTERVAL)
        try:
            await self._on_combat_round()
        except Exception as e:
            self.logger.error(f"Error in combat round: {e}", exc_info=True)

    async def _on_combat_round(self) -> None:
        """Process a single combat round — fire next skill or flee."""
        if not self.active or not self.agent.combat_manager.in_combat:
            return

        if self.state == "FLEEING":
            return

        self._last_fire_time = time.monotonic()

        # Check HP threshold
        cfg = self.agent.config.agent
        hp_current = self.agent.state_manager.hp_current
        hp_max = self.agent.state_manager.hp_max

        if hp_max <= 0 or (hp_current / hp_max) < cfg.combat_flee_threshold:
            self.state = "FLEEING"
            self.logger.info(
                f"HP {hp_current}/{hp_max} below threshold "
                f"{cfg.combat_flee_threshold}, fleeing"
            )
            await self.agent.send_command(cfg.combat_flee_command)
            return

        # Fire openers first
        if self.state == "IDLE" and cfg.combat_opener_skills:
            self.state = "OPENING"

        if self.state == "OPENING":
            if self._opener_index < len(cfg.combat_opener_skills):
                skill = cfg.combat_opener_skills[self._opener_index]
                self._opener_index += 1
                await self.agent.send_command(skill)
                return
            else:
                # All openers done, transition to rotating
                self.state = "ROTATING"

        # Transition IDLE -> ROTATING if no openers
        if self.state == "IDLE":
            self.state = "ROTATING"

        # Fire rotation skill
        if self.state == "ROTATING" and cfg.combat_rotation_skills:
            skill = cfg.combat_rotation_skills[self._rotation_index]
            self._rotation_index = (
                (self._rotation_index + 1) % len(cfg.combat_rotation_skills)
            )
            await self.agent.send_command(skill)

    def _on_combat_ended(self) -> None:
        """Reset state when combat ends."""
        self.state = "IDLE"
        self._opener_index = 0
        self._rotation_index = 0
        self.logger.debug("Combat ended, skill rotation reset")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agent/test_combat_skill_manager.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/combat_skill_manager.py tests/agent/test_combat_skill_manager.py
git commit -m "feat(combat): add CombatSkillManager with state machine and tests"
```

---

### Task 3: Wire CombatSkillManager into MUDAgent

**Files:**
- Modify: `src/mud_agent/agent/mud_agent.py`
- Modify: `src/mud_agent/__main__textual_reactive.py`

**Step 1: Add import and instantiation in MUDAgent.__init__**

In `src/mud_agent/agent/mud_agent.py`:

Add import at top:
```python
from mud_agent.agent.combat_skill_manager import CombatSkillManager
```

In `__init__`, after `self.buff_manager = BuffManager(self)`:
```python
self.combat_skill_manager = CombatSkillManager(self)
```

**Step 2: Add to setup_managers**

In `setup_managers()`, after `await self.buff_manager.setup()`:
```python
await self.combat_skill_manager.setup()
```

**Step 3: Start in connect_and_initialize**

In `src/mud_agent/__main__textual_reactive.py`, in `connect_and_initialize()`, after the `agent.connection_complete = True` line (or near `buff_manager.start()` if it's there — check the file), add:

```python
# Start combat skill rotation if configured
if agent.combat_skill_manager.enabled:
    await agent.combat_skill_manager.start()
```

Note: `buff_manager.start()` is called from the Textual app's loading screen callback. Check where that happens and add `combat_skill_manager.start()` next to it. If it's in `connect_and_initialize`, add it there.

**Step 4: Add stop to shutdown sequence**

In `src/mud_agent/__main__textual_reactive.py`, in the shutdown `finally` block, before `await agent.buff_manager.stop()` (step 6 in the shutdown sequence), add:

```python
# Stop combat skill manager
try:
    await agent.combat_skill_manager.stop()
except Exception as e:
    logger.error(f"Error stopping combat skill manager: {e}")
```

**Step 5: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/mud_agent/agent/mud_agent.py src/mud_agent/__main__textual_reactive.py
git commit -m "feat(combat): wire CombatSkillManager into agent lifecycle"
```

---

### Task 4: Update .env.example and verify full integration

**Step 1: Run the full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: ALL PASS (440+ tests)

**Step 2: Commit any remaining changes**

```bash
git add -A
git commit -m "chore: final integration cleanup"
```

**Step 3: Push and create PR**

```bash
git push -u origin feat/combat-skill-rotation
gh pr create --title "feat: add combat skill rotation" \
  --assignee Daniel-ltw --label enhancement \
  --body "$(cat <<'EOF'
## Summary
- New `CombatSkillManager` that auto-fires attack skills during combat
- Opener skills (fired once at combat start) + rotation skills (cycled repeatedly)
- HP-based flee threshold with configurable flee command
- Follows existing `BuffManager` event-driven pattern
- Configured via env vars: `COMBAT_OPENER_SKILLS`, `COMBAT_ROTATION_SKILLS`, `COMBAT_FLEE_THRESHOLD`, `COMBAT_FLEE_COMMAND`

## Test plan
- [ ] Unit tests for state machine transitions
- [ ] Unit tests for HP threshold / flee behavior
- [ ] Unit tests for debounce
- [ ] Unit tests for config loading
- [ ] Manual test: configure skills in .env and verify they fire during combat
EOF
)"
```
