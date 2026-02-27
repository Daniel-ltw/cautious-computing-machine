# Combat Skill Rotation Design

## Goal

Auto-fire configurable attack skills/spells during combat, with opener/rotation categories and an HP-based flee safety threshold.

## Architecture

A new `CombatSkillManager` class following the existing `BuffManager` pattern:

- **Lifecycle:** `setup()` subscribes to client data events, `start()` activates, `stop()` cleans up
- **Event-driven:** Listens to `client.events.on("data", ...)` to detect combat rounds
- **Config-driven:** Reads skill lists and thresholds from `AgentConfig` via environment variables
- **Sends commands via:** `agent.mud_tool.forward()`

Wired into `MUDAgent.__init__()` and `setup_managers()` like other managers.

## Configuration

New fields on `AgentConfig`:

| Field | Type | Default | Env Var |
|-------|------|---------|---------|
| `combat_opener_skills` | `list[str]` | `[]` | `COMBAT_OPENER_SKILLS` |
| `combat_rotation_skills` | `list[str]` | `[]` | `COMBAT_ROTATION_SKILLS` |
| `combat_flee_threshold` | `float` | `0.25` | `COMBAT_FLEE_THRESHOLD` |
| `combat_flee_command` | `str` | `"flee"` | `COMBAT_FLEE_COMMAND` |

Example `.env`:
```
COMBAT_OPENER_SKILLS=backstab
COMBAT_ROTATION_SKILLS=circle,dirt kick,kick
COMBAT_FLEE_THRESHOLD=0.25
COMBAT_FLEE_COMMAND=flee
```

Empty skill lists = feature disabled (no auto-combat).

## Combat Round Detection

The manager detects a new combat round by checking incoming server data for combat indicators (hit/miss/dodge/parry messages — the same patterns `CombatManager` already uses). On each detected round:

1. Check HP threshold via `state_manager.hp_current / state_manager.hp_max`
2. If below threshold -> send flee command, transition to FLEEING
3. If openers remain -> send next opener
4. Otherwise -> send next rotation skill (cycling with an index)

## State Machine

```
IDLE  --(combat detected)-->  OPENING
OPENING  --(all openers sent or none configured)-->  ROTATING
ROTATING  --(combat ends)-->  IDLE
ROTATING  --(HP below threshold)-->  FLEEING
FLEEING  --(combat ends)-->  IDLE
ANY  --(stop() called)-->  IDLE
```

## Error Handling

- Debounce: max one skill per ~1 second to prevent spam from multiple round messages arriving close together
- Combat end: reset to IDLE when `combat_manager.in_combat == False`
- Disabled gracefully: if both skill lists are empty, manager does nothing

## Testing

- State transitions: IDLE -> OPENING -> ROTATING -> IDLE
- HP threshold triggers flee
- Rotation cycling wraps around
- Openers fire once then transition to rotation
- Disabled when config lists are empty
- Debounce prevents duplicate fires
