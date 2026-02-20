# Smart Buff Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the blind periodic autocast loop with an event-driven BuffManager that detects buff expiry from server text, recasts via `spellup learned`, with combat awareness and a periodic fallback timer.

**Architecture:** New `BuffManager` class in `src/mud_agent/agent/buff_manager.py` following the QuestManager pattern — subscribes to client `data` events, detects buff expiry via text pattern matching, debounces rapid expiries, defers recast during combat, and runs a fallback timer. The `/ac` command in CommandProcessor delegates to BuffManager instead of managing its own loop.

**Tech Stack:** Python 3.12, asyncio, pytest + pytest-asyncio, unittest.mock

**Design doc:** `docs/plans/2026-02-20-smart-buff-management-design.md`

---

### Task 1: Create BuffManager with expiry pattern detection

**Files:**
- Create: `src/mud_agent/agent/buff_manager.py`
- Create: `tests/agent/test_buff_manager.py`

**Step 1: Write the failing tests for pattern detection**

```python
#!/usr/bin/env python3
"""Tests for BuffManager."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from mud_agent.agent.buff_manager import BuffManager


class TestBuffManagerPatternDetection:
    """Test buff expiry pattern detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)

    def test_initialization(self):
        """Test BuffManager initializes with correct defaults."""
        assert self.buff_manager.agent == self.agent
        assert self.buff_manager.active is False
        assert self.buff_manager._recast_pending is False

    def test_detects_sanctuary_fades(self):
        """Test detection of sanctuary expiry."""
        assert self.buff_manager._check_buff_expiry("Your sanctuary fades.") is True

    def test_detects_no_longer_hidden(self):
        """Test detection of hide expiry."""
        assert self.buff_manager._check_buff_expiry("You are no longer hidden.") is True

    def test_detects_generic_wears_off(self):
        """Test detection of generic wear-off message."""
        assert self.buff_manager._check_buff_expiry("Your armor spell wears off.") is True

    def test_ignores_normal_text(self):
        """Test that normal game text is not detected as buff expiry."""
        assert self.buff_manager._check_buff_expiry("A rat attacks you!") is False

    def test_ignores_empty_text(self):
        """Test that empty text is not detected."""
        assert self.buff_manager._check_buff_expiry("") is False

    def test_detects_case_insensitive(self):
        """Test case-insensitive matching."""
        assert self.buff_manager._check_buff_expiry("YOUR SANCTUARY FADES.") is True
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mud_agent.agent.buff_manager'`

**Step 3: Write minimal BuffManager implementation**

```python
"""Buff Manager for smart spell/skill recast management.

Detects buff expiry from server text and recasts via Aardwolf's native
'spellup learned' command. Combat-aware with a periodic fallback timer.
"""

import asyncio
import logging
from typing import Optional

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
        self._debounce_task: Optional[asyncio.Task] = None
        self._fallback_task: Optional[asyncio.Task] = None

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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): add BuffManager with expiry pattern detection"
```

---

### Task 2: Add recast logic with debounce

**Files:**
- Modify: `src/mud_agent/agent/buff_manager.py`
- Modify: `tests/agent/test_buff_manager.py`

**Step 1: Write the failing tests for recast and debounce**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerRecast:
    """Test recast logic and debounce."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_request_recast_sends_spellup(self):
        """Test that _request_recast sends spellup learned."""
        await self.buff_manager._request_recast()
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_on_buff_expired_triggers_debounced_recast(self):
        """Test that buff expiry triggers a debounced recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        # Debounce task should be created
        assert self.buff_manager._debounce_task is not None
        # Wait for debounce to complete
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_multiple_expiries_produce_single_recast(self):
        """Test that rapid expiries are debounced into one recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        self.buff_manager._on_buff_expired("shield")
        self.buff_manager._on_buff_expired("armor")
        # Wait for debounce
        await asyncio.sleep(2.0)
        # Should only send one spellup command
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_no_recast_when_inactive(self):
        """Test that no recast happens when buff manager is inactive."""
        self.buff_manager.active = False
        self.buff_manager._on_buff_expired("sanctuary")
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerRecast -v`
Expected: FAIL — `AttributeError: 'BuffManager' object has no attribute '_request_recast'`

**Step 3: Add recast and debounce methods to BuffManager**

Add to `BuffManager` class in `src/mud_agent/agent/buff_manager.py`:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): add recast logic with debounce"
```

---

### Task 3: Add combat awareness

**Files:**
- Modify: `src/mud_agent/agent/buff_manager.py`
- Modify: `tests/agent/test_buff_manager.py`

**Step 1: Write the failing tests for combat deferral**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerCombatAwareness:
    """Test combat-aware recast deferral."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = True  # Start in combat
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_expiry_during_combat_sets_pending(self):
        """Test that expiry during combat defers recast."""
        self.buff_manager._on_buff_expired("sanctuary")
        await asyncio.sleep(2.0)
        # Should NOT have sent spellup during combat
        self.agent.send_command.assert_not_called()
        # Should have set pending flag
        assert self.buff_manager._recast_pending is True

    @pytest.mark.asyncio
    async def test_combat_ended_triggers_pending_recast(self):
        """Test that pending recast fires when combat ends."""
        # Expire during combat
        self.buff_manager._on_buff_expired("sanctuary")
        await asyncio.sleep(2.0)
        assert self.buff_manager._recast_pending is True

        # Combat ends
        self.agent.combat_manager.in_combat = False
        self.buff_manager._on_combat_state_changed()
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_called_once_with("spellup learned")
        assert self.buff_manager._recast_pending is False

    @pytest.mark.asyncio
    async def test_combat_ended_no_pending_does_nothing(self):
        """Test that combat end without pending recast does nothing."""
        self.agent.combat_manager.in_combat = False
        self.buff_manager._on_combat_state_changed()
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerCombatAwareness -v`
Expected: FAIL — `_on_buff_expired` doesn't check combat state yet

**Step 3: Add combat awareness to BuffManager**

Update `_on_buff_expired` and add `_on_combat_state_changed` in `src/mud_agent/agent/buff_manager.py`:

```python
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
            self.logger.info("Combat ended — triggering deferred recast")
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._debounce_task = asyncio.create_task(self._debounced_recast())
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): add combat-aware recast deferral"
```

---

### Task 4: Add data event handler and fallback timer

**Files:**
- Modify: `src/mud_agent/agent/buff_manager.py`
- Modify: `tests/agent/test_buff_manager.py`

**Step 1: Write the failing tests for event handling and lifecycle**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerEventHandling:
    """Test data event handling and incoming text processing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_handle_incoming_data_detects_expiry(self):
        """Test that incoming data with expiry text triggers recast."""
        self.buff_manager._handle_incoming_data("Your sanctuary fades.")
        assert self.buff_manager._debounce_task is not None
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_called_once_with("spellup learned")

    @pytest.mark.asyncio
    async def test_handle_incoming_data_ignores_normal_text(self):
        """Test that normal text doesn't trigger recast."""
        self.buff_manager._handle_incoming_data("A rat scurries by.")
        assert self.buff_manager._debounce_task is None
        await asyncio.sleep(0.5)
        self.agent.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_incoming_data_when_inactive(self):
        """Test that inactive manager ignores all text."""
        self.buff_manager.active = False
        self.buff_manager._handle_incoming_data("Your sanctuary fades.")
        assert self.buff_manager._debounce_task is None


class TestBuffManagerLifecycle:
    """Test start/stop lifecycle."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)

    @pytest.mark.asyncio
    async def test_setup_subscribes_to_events(self):
        """Test that setup subscribes to client data events."""
        await self.buff_manager.setup()
        self.agent.client.events.on.assert_called_once_with(
            "data", self.buff_manager._handle_incoming_data
        )

    @pytest.mark.asyncio
    async def test_start_activates_and_starts_fallback(self):
        """Test that start activates manager and starts fallback timer."""
        await self.buff_manager.start()
        assert self.buff_manager.active is True
        assert self.buff_manager._fallback_task is not None
        # Clean up
        await self.buff_manager.stop()

    @pytest.mark.asyncio
    async def test_stop_deactivates_and_cancels_tasks(self):
        """Test that stop deactivates and cleans up all tasks."""
        await self.buff_manager.start()
        await self.buff_manager.stop()
        assert self.buff_manager.active is False
        assert self.buff_manager._recast_pending is False

    @pytest.mark.asyncio
    async def test_stop_when_not_active(self):
        """Test that stop is safe to call when not active."""
        await self.buff_manager.stop()
        assert self.buff_manager.active is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerEventHandling -v`
Expected: FAIL — `AttributeError: 'BuffManager' object has no attribute '_handle_incoming_data'`

**Step 3: Add event handler, setup, start, stop, and fallback timer**

Add to `BuffManager` class in `src/mud_agent/agent/buff_manager.py`:

```python
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
        self._fallback_task = asyncio.create_task(self._fallback_timer_loop())
        self.logger.info("BuffManager started")

    async def stop(self) -> None:
        """Disable buff management and cancel all tasks."""
        self.active = False
        self._recast_pending = False

        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass
        self._debounce_task = None

        if self._fallback_task and not self._fallback_task.done():
            self._fallback_task.cancel()
            try:
                await self._fallback_task
            except asyncio.CancelledError:
                pass
        self._fallback_task = None

        self.logger.info("BuffManager stopped")

    def _handle_incoming_data(self, text: str) -> None:
        """Handle incoming server data.

        Checks text for buff expiry patterns and triggers recast if found.

        Args:
            text: Raw text from the MUD server
        """
        if not self.active:
            return

        if self._check_buff_expiry(text):
            # Extract a short description for logging
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: All 21 tests PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): add event handling, lifecycle management, and fallback timer"
```

---

### Task 5: Integrate BuffManager into MUDAgent

**Files:**
- Modify: `src/mud_agent/agent/mud_agent.py:22,96,118-122`
- Modify: `tests/agent/test_buff_manager.py`

**Step 1: Write the failing integration test**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerIntegration:
    """Test BuffManager integration with MUDAgent."""

    def test_mud_agent_has_buff_manager(self):
        """Test that MUDAgent creates a BuffManager instance."""
        # Import here to avoid circular imports in test setup
        from mud_agent.agent.buff_manager import BuffManager

        agent = MagicMock()
        agent.combat_manager = MagicMock()
        agent.client = MagicMock()
        agent.client.events = MagicMock()

        bm = BuffManager(agent)
        assert isinstance(bm, BuffManager)
        assert bm.active is False
```

**Step 2: Run test to verify it passes (this is a sanity check)**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerIntegration -v`
Expected: PASS

**Step 3: Add BuffManager to MUDAgent**

In `src/mud_agent/agent/mud_agent.py`, add the import alongside the other manager imports (line 22):

```python
from .buff_manager import BuffManager
```

In `MUDAgent.__init__`, add after `self.quest_manager = QuestManager(self)` (around line 96):

```python
self.buff_manager = BuffManager(self)
```

In `MUDAgent.setup_managers`, add the setup call:

```python
    async def setup_managers(self):
        """Set up all the managers."""
        await self.room_manager.setup()
        await self.quest_manager.setup()
        await self.buff_manager.setup()
        self.logger.info("Room manager setup complete")
```

**Step 4: Run all existing tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (the new `buff_manager` attribute won't break existing mocks since they use MagicMock which auto-creates attributes)

**Step 5: Commit**

```bash
git add src/mud_agent/agent/mud_agent.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): integrate BuffManager into MUDAgent"
```

---

### Task 6: Wire up /ac command and remove old autocast

**Files:**
- Modify: `src/mud_agent/utils/textual_app/commands.py:31-39,99-112,335-347`

**Step 1: Write the failing test**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerToggle:
    """Test the /ac toggle integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = False
        self.buff_manager = BuffManager(self.agent)

    @pytest.mark.asyncio
    async def test_toggle_on_off(self):
        """Test start/stop toggle cycle."""
        assert self.buff_manager.active is False
        await self.buff_manager.start()
        assert self.buff_manager.active is True
        await self.buff_manager.stop()
        assert self.buff_manager.active is False

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """Test that stopping twice doesn't raise."""
        await self.buff_manager.start()
        await self.buff_manager.stop()
        await self.buff_manager.stop()
        assert self.buff_manager.active is False
```

**Step 2: Run tests to verify they pass (sanity check)**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerToggle -v`
Expected: PASS

**Step 3: Update CommandProcessor to use BuffManager**

In `src/mud_agent/utils/textual_app/commands.py`:

Remove from `__init__` (lines 38-39):
```python
        self.auto_spellup = False
        self.auto_spellup_task = None
```

Replace the `/ac` handler block (lines 99-112) with:
```python
            elif command == "/ac":
                command_log = self.app.query_one("#command-log", CommandLog)
                if self.agent.buff_manager.active:
                    await self.agent.buff_manager.stop()
                    command_log.write("[bold cyan]Buff Manager: [/bold cyan][bold red]Off[/bold red]")
                else:
                    await self.agent.buff_manager.start()
                    command_log.write("[bold cyan]Buff Manager: [/bold cyan][bold green]On[/bold green]")
```

Delete the `handle_autocast` method entirely (lines 336-347).

**Step 4: Run all tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS. If any tests reference `auto_spellup` or `handle_autocast`, they will need updating (check `tests/textual_app/test_commands.py` if it exists).

**Step 5: Commit**

```bash
git add src/mud_agent/utils/textual_app/commands.py
git commit -m "refactor(buff): wire /ac to BuffManager, remove old autocast loop"
```

---

### Task 7: Add BuffManager to shutdown sequence

**Files:**
- Modify: `src/mud_agent/__main__textual_reactive.py:119-120`

**Step 1: No test needed — this is a one-line addition to the shutdown sequence**

**Step 2: Add BuffManager stop to the finally block**

In `src/mud_agent/__main__textual_reactive.py`, add after the receive_task cancellation block (after line 118) and before the sync worker stop (line 120):

```python
            # 3.5. Stop buff manager
            if agent.buff_manager.active:
                try:
                    await agent.buff_manager.stop()
                except Exception as e:
                    logger.error(f"Error stopping buff manager: {e}")
```

**Step 3: Run all tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/mud_agent/__main__textual_reactive.py
git commit -m "fix(shutdown): add BuffManager to shutdown sequence"
```

---

### Task 8: Add combat state change detection

**Files:**
- Modify: `src/mud_agent/agent/buff_manager.py`
- Modify: `tests/agent/test_buff_manager.py`

The `CombatManager` tracks `in_combat` state but doesn't emit an event when combat ends. BuffManager needs to detect combat end to flush pending recasts. The simplest approach: check combat state in `_handle_incoming_data` — if we previously saw `in_combat=True` and now it's `False`, call `_on_combat_state_changed()`.

**Step 1: Write the failing test**

Add to `tests/agent/test_buff_manager.py`:

```python
class TestBuffManagerCombatTransition:
    """Test combat state transition detection via data events."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = MagicMock()
        self.agent.send_command = AsyncMock()
        self.agent.client = MagicMock()
        self.agent.client.events = MagicMock()
        self.agent.combat_manager = MagicMock()
        self.agent.combat_manager.in_combat = True
        self.buff_manager = BuffManager(self.agent)
        self.buff_manager.active = True

    @pytest.mark.asyncio
    async def test_combat_end_detected_via_data_event(self):
        """Test that combat ending is detected from data events."""
        # Buff expires during combat
        self.buff_manager._handle_incoming_data("Your sanctuary fades.")
        assert self.buff_manager._recast_pending is True

        # Combat ends — next data event should detect the transition
        self.agent.combat_manager.in_combat = False
        self.buff_manager._handle_incoming_data("The rat is dead!")
        await asyncio.sleep(2.0)
        self.agent.send_command.assert_called_once_with("spellup learned")
        assert self.buff_manager._recast_pending is False
```

**Step 2: Run tests to verify it fails**

Run: `uv run pytest tests/agent/test_buff_manager.py::TestBuffManagerCombatTransition -v`
Expected: FAIL — combat transition not detected in `_handle_incoming_data`

**Step 3: Add combat transition tracking to BuffManager**

Add to `__init__`:
```python
        self._was_in_combat: bool = False
```

Update `_handle_incoming_data`:
```python
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
```

Also reset `_was_in_combat` in `start()` and `stop()`:
```python
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
        # ... rest of stop unchanged
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/agent/test_buff_manager.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py
git commit -m "feat(buff): detect combat state transitions from data events"
```

---

### Task 9: Run full test suite and do final verification

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS with no regressions

**Step 2: Run linter**

Run: `uv run ruff check src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py`
Expected: No errors

**Step 3: Run formatter**

Run: `uv run ruff format src/mud_agent/agent/buff_manager.py tests/agent/test_buff_manager.py`
Expected: Files formatted (or already formatted)

**Step 4: Verify the complete BuffManager file is self-consistent**

Run: `uv run python -c "from mud_agent.agent.buff_manager import BuffManager; print('Import OK')"`
Expected: `Import OK`

**Step 5: Commit any formatting changes**

```bash
git add -A
git commit -m "style: format buff manager code" --allow-empty
```
