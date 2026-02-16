# Design: Exit Recording Fixes

**Date:** 2026-02-17
**Status:** Approved

## Problem

The exit recording system has three interrelated bugs that prevent correct capture of command-specific exits and cause wrong recordings during speedwalk navigation.

### Context: Aardwolf Exit Types

- **Directional exits**: Standard `n/s/e/w/u/d` — included in GMCP room data
- **Command exits**: `enter portal`, `enter hut`, `climb rope` — NOT in GMCP data, only discoverable by observing successful room transitions after sending a command
- A single room can have multiple command exits to different destinations (rare but possible)
- GMCP always fires a room update on the destination room regardless of exit type

## Bug 1: Collision Detection Blocks Distinct Command Exits

**Location:** `RoomExit.record_exit_success()` in `src/mud_agent/db/models.py`

**Root cause:** The `_norm()` function normalizes `"enter portal"` and `"enter hut"` both to `"enter"`. The zone-level collision check then compares normalized forms, incorrectly blocking the second exit as a duplicate.

**Fix:** Compare full raw command strings in the collision check instead of normalized forms. `"enter portal"` and `"enter hut"` are distinct commands — only block when the exact same full command is already recorded for another exit in the same zone.

## Bug 2: Speedwalk Commands Cause Wrong Exit Recording

**Location:** `RoomManager._handle_command_sent()`, `CommandProcessor._process_single_command()`, `command_sent` event

**Root cause:** When pathfinding sends `"run 2n;open door;n;run 3e"`:
1. `process_command` splits by `;` and processes each sub-command individually
2. Each emits `command_sent` → `room_manager._handle_command_sent()` fires
3. `"run 2n"` isn't recognized as movement, doesn't set pending_exit
4. But Aardwolf processes it and sends GMCP room updates for each intermediate room
5. Those room updates can match against stale `pending_exit_command` from prior commands

**Fix:**
- Propagate `is_speedwalk` flag through `command_sent` event payload
- When `room_manager` sees `is_speedwalk=True`, suppress exit recording for the entire sequence
- When `_handle_command_sent` encounters a `run ` token, clear pending state as safety net

Speedwalk uses already-known paths — we don't need to re-record exits during navigation.

## Bug 3: Test DB Fixtures Broken

**Location:** `tests/test_pathfinding_fixes.py`, `tests/mcp/test_game_knowledge_graph.py`, `tests/test_room_manager.py`, `tests/reproduction/test_enter_portal_real_kg.py`

**Root cause:** Tests use `db.init(":memory:")` or patch `db` but don't call `db.create_tables()` with the full model list, so tables don't exist at test time.

**Fix:** Ensure every test fixture that initializes or patches the DB also creates all required tables via `db.create_tables(ALL_MODELS)`.

## Approach

Minimal fix (Approach A): fix the actual bugs without schema changes. The `RoomExit.direction` field's dual-purpose storage (standard directions like `"n"` and full commands like `"enter portal"`) works correctly in practice.

## Non-Goals

- No schema migration or new fields
- No refactoring of the direction/command storage model
- No changes to pathfinding or navigation logic
