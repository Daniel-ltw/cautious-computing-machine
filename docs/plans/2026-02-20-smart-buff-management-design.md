# Smart Buff Management Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the blind periodic autocast loop with an event-driven buff manager that detects buff expiry from server text and recasts via Aardwolf's native `spellup learned` command.

**Architecture:** A new `BuffManager` class following the existing manager pattern (like QuestManager, CombatManager). It subscribes to the client's `data` event to detect buff expiry messages, debounces rapid expiries, defers recast during combat, and runs a periodic fallback timer. It uses `spellup learned` as the recast mechanism, leveraging the server's built-in intelligence (skip active buffs, check mana, respect recovery).

**Tech Stack:** Python 3.12, asyncio, Aardwolf MUD event system (EventManager pub/sub)

---

## Context

### Current Implementation

The `/ac` command in `CommandProcessor` toggles a simple loop (`handle_autocast`) that fires every command in `AUTOCAST_COMMANDS` (default: `nimble,hide,sneak,cast under`) every 15-60 seconds at random, regardless of whether the buff is active. This wastes commands and doesn't react to actual buff expiry.

### Aardwolf's Native `spellup` Command

Aardwolf has a built-in `spellup` command with significant intelligence:
- `spellup learned` casts all practiced spells AND skills (nimble, hide, sneak included)
- Won't recast if the affect is already active
- Skips spells in recovery (cooldown)
- Won't cast if insufficient mana/moves
- Respects nomagic rooms
- Won't queue combat-incompatible spells during fights
- Handles mutually exclusive spells (e.g., sanctuary vs biofeedback)

Related commands: `forgetskill` (exclude from spellup), `quickskill` (custom ordered list for `spellup quick`).

### Future: Telnet Spell Tags

Aardwolf supports telopt 7 (spellup tags) which provides structured notifications:
- `{affon}spell_number-duration` — spell landed, with duration in seconds
- `{affoff}spell_number` — spell wore off
- `{sfail}spell_number,target,reason,recovery` — cast failure with reason code

The codebase does not currently parse these tags. Phase 2 will add tag support as a more reliable detection mechanism alongside text patterns.

---

## Design

### BuffManager Class

**File:** `src/mud_agent/agent/buff_manager.py`

**Pattern:** Same as QuestManager — owned by MUDAgent, subscribes to client data events, manages its own async tasks.

```
BuffManager
├── setup()                        # Subscribe to client data events
├── start()                        # Enable buff management, start fallback timer
├── stop()                         # Disable, cancel tasks, unsubscribe
├── _handle_incoming_data(text)    # Parse text for buff expiry patterns
├── _on_buff_expired(buff_name)    # React to a single buff expiry
├── _request_recast()              # Send "spellup learned" (debounced)
├── _on_combat_state_changed()     # Flush pending recast after combat
├── _fallback_timer_loop()         # Periodic recast (every ~120s)
│
├── active: bool                   # Whether buff management is enabled
├── _recast_pending: bool          # Deferred recast waiting for combat end
├── _recast_debounce_task          # Prevents spamming spellup on multiple expiries
└── _fallback_task                 # The periodic timer task
```

### Buff Expiry Detection

Text pattern matching against incoming server data. Initial pattern set:

```python
BUFF_EXPIRY_PATTERNS = [
    # Skills
    "You are no longer hidden.",
    "You step out of the shadows.",
    "You feel less nimble.",
    # Spells - common spellups
    "Your sanctuary fades.",
    "Your shield fades.",
    "Your armor fades.",
    "You feel less protected.",
    "You slow down.",
    "Your protection fades.",
    "You become visible.",
    # Generic catch-alls
    "has worn off.",
    "wears off.",
    "spell fades.",
]
```

The `_handle_incoming_data(text)` method checks incoming text against these patterns using case-insensitive substring matching. When a match is found, it calls `_on_buff_expired()`.

This list will be refined over time based on actual in-game messages. The generic catch-alls ("has worn off.", "wears off.") should catch most spells we don't have specific patterns for.

### Recast Logic

When a buff expiry is detected:

1. **Check combat state** — if `combat_manager.in_combat` is True, set `_recast_pending = True` and return.
2. **Debounce** — multiple buffs often expire simultaneously (e.g., after death). Wait 1.5 seconds after the first expiry before recasting. If more expiries arrive within the window, the timer resets. Implemented as an `asyncio.Task` with `asyncio.sleep(1.5)`.
3. **Send command** — `await agent.send_command("spellup learned")`.

When combat ends (detected by polling `combat_manager.in_combat` becoming False):
- If `_recast_pending` is True, trigger the debounced recast.
- Clear the pending flag.

### Fallback Timer

A periodic loop that runs `spellup learned` every ~120 seconds as a safety net:

```python
async def _fallback_timer_loop(self):
    while self.active:
        await asyncio.sleep(120)
        if self.active and not self.agent.combat_manager.in_combat:
            await self.agent.send_command("spellup learned")
```

This catches missed expiry events: death (all buffs drop at once), dispel by mob, login (no buffs active), or any expiry message we don't have a pattern for. The `spellup learned` command is a no-op if all buffs are active, so the only cost is one command to the server every 2 minutes.

### Threading Model

Everything runs on the main asyncio event loop — no separate threads needed. All operations are lightweight:
- Event handler: microseconds of string matching
- Debounce: `asyncio.sleep()` yields to event loop
- Recast: async socket write
- Fallback timer: `asyncio.sleep()` in a loop

This matches the pattern used by QuestManager, CombatManager, and the periodic GMCP update task.

---

## Integration

### MUDAgent

```python
# __init__:
self.buff_manager = BuffManager(self)

# setup_managers():
await self.buff_manager.setup()
```

### CommandProcessor

The `/ac` toggle delegates to BuffManager:

```python
if command == "/ac":
    if self.agent.buff_manager.active:
        await self.agent.buff_manager.stop()
        command_log.write("[bold cyan]Buff Manager: [/bold cyan][bold red]Off[/bold red]")
    else:
        await self.agent.buff_manager.start()
        command_log.write("[bold cyan]Buff Manager: [/bold cyan][bold red]On[/bold red]")
```

### Removals

- Delete `CommandProcessor.handle_autocast()`
- Delete `CommandProcessor.auto_spellup` and `auto_spellup_task` fields
- `AUTOCAST_COMMANDS` config remains but is no longer used by BuffManager (backward compat; can deprecate later)

### Shutdown

Add to the shutdown sequence in `__main__textual_reactive.py`:

```python
# In the finally block, before tick manager stop:
if agent.buff_manager.active:
    await agent.buff_manager.stop()
```

---

## Configuration

No new configuration for v1. The manager uses `spellup learned` as the recast command.

Future config options (not for v1):
- Custom spellup command (e.g., `spellup quick` instead of `spellup learned`)
- Fallback timer interval
- Additional expiry patterns via config file

---

## Testing Strategy

- **Pattern detection tests** — feed known expiry messages to `_handle_incoming_data`, verify detection. Feed non-expiry text, verify no false positives.
- **Debounce tests** — rapid consecutive expiries produce only one `spellup learned` command.
- **Combat deferral tests** — expiry during combat sets `_recast_pending`, recast fires after combat state clears.
- **Start/stop lifecycle tests** — verify tasks are created on start, cancelled on stop, no leaks.
- **Fallback timer tests** — verify periodic recast fires, respects combat state, stops when deactivated.

---

## Future: Phase 2 — Telnet Spell Tags

When adding `{affon}`/`{affoff}` support:

1. Enable telopt 7 (spellup tags) via IAC SB 102 7 1 IAC SE during connection setup.
2. Parse `{affon}spell_number-duration` and `{affoff}spell_number` tags in the telnet processing layer (`_process_telnet` or a new tag parser).
3. Emit structured events: `buff_applied(spell_num, duration)` and `buff_expired(spell_num)`.
4. BuffManager subscribes to these events alongside text patterns — tags become the primary detection, text patterns become fallback.
5. Duration data from `{affon}` enables UI features: display remaining buff timers, show active buff list.

The BuffManager's recast logic (debounce, combat awareness, `spellup learned`) remains unchanged — only the detection source changes.
