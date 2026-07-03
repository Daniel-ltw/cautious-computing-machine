# Design: Local SQLite + Async Background Sync to Supabase

**Date:** 2026-02-16
**Status:** Approved

## Problem

Switching from local SQLite to remote Supabase (PostgreSQL) introduced latency (50-200ms+ per query) that breaks the mapper widget. The mapper performs 10-30+ DB queries per room change (current room + depth-3 adjacency traversal), making it freeze or lag significantly. Additionally, room writes in `RoomManager` block the event pipeline since they `await` remote DB calls before emitting events.

## Goal

- **Primary:** Eliminate Supabase latency from the gameplay hot path (mapper reads, room writes, exit recording)
- **Secondary:** Use Supabase as a shared "GitHub for game data" where multiple players can contribute and consume room/exit discoveries

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  MUD Agent App                   │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │  Mapper   │   │  Room    │   │  Knowledge  │  │
│  │Container  │   │ Manager  │   │   Graph     │  │
│  └────┬──────┘   └────┬─────┘   └──────┬──────┘  │
│       │               │                │         │
│       └───────────────┼────────────────┘         │
│                       │                          │
│                ┌──────▼──────┐                   │
│                │   SQLite    │  ← all reads/     │
│                │  (local)    │    writes go here  │
│                └──────┬──────┘                   │
│                       │                          │
│                ┌──────▼──────┐                   │
│                │  SyncWorker │  ← background     │
│                │  (async)    │    task            │
│                └──────┬──────┘                   │
└───────────────────────┼──────────────────────────┘
                        │
                  ┌─────▼─────┐
                  │ Supabase  │  ← shared remote
                  │ (Postgres)│    source of truth
                  └───────────┘
```

**Key invariant:** The hot path (mapper reads, room writes, exit recording) **never** touches Supabase. Only the SyncWorker does, in a background task.

## Change Tracking

- Add `sync_status` column to `BaseModel` — values: `synced`, `dirty`, `conflict`
- Add `remote_updated_at` column to track the last known Supabase timestamp
- `BaseModel.save()` override: automatically set `sync_status = 'dirty'` on every local save

## Sync Mechanism

### Push (local → Supabase)
1. SyncWorker queries all records where `sync_status = 'dirty'`
2. Batches them into upserts against Supabase (using `ON CONFLICT ... DO UPDATE`)
3. On success, marks them `synced` locally
4. Uses `updated_at` for last-write-wins on individual fields

### Pull (Supabase → local)
1. SyncWorker queries Supabase for records with `updated_at > last_pull_timestamp`
2. For each incoming record:
   - If local record doesn't exist → insert locally
   - If local record exists and is `synced` → overwrite with remote data
   - If local record exists and is `dirty` → **merge** (see below)
3. Update `last_pull_timestamp`

### Merge Strategy (for rooms)
- **Room fields** (name, terrain, zone, coords): latest `updated_at` wins
- **Exits**: union — if friend discovered an exit, add it locally even if you haven't seen it
- **NPCs**: union — combine NPC lists from all players
- **Exit details** (pre_commands, move_command): latest `last_success_at` wins

### Sync Interval
- Configurable, default 30 seconds
- Adjustable via `SYNC_INTERVAL` env var

## Implementation Components

### New Files

1. **`src/mud_agent/db/sync_worker.py`** — `SyncWorker` class
   - Manages the background sync loop (`asyncio.Task`)
   - Handles push/pull/merge logic
   - Holds a separate Peewee `PostgresqlDatabase` connection for Supabase
   - Configurable interval, graceful shutdown

2. **`src/mud_agent/db/sync_models.py`** — Remote-bound model mirrors
   - Identical schema to `models.py` but bound to the Supabase `PostgresqlDatabase`
   - Used only by `SyncWorker` for remote reads/writes

### Modified Files

3. **`src/mud_agent/db/models.py`**
   - `BaseModel`: add `sync_status` and `remote_updated_at` columns
   - `BaseModel.save()`: set `sync_status = 'dirty'` on every local save
   - Database init: **always** use SQLite, regardless of `DATABASE_URL`
   - Remove `psycopg2` retry decorator — no longer needed

4. **`src/mud_agent/mcp/game_knowledge_graph.py`**
   - Remove `retry_on_timeout` decorator
   - Clean up imports (remove `psycopg2`)

5. **`src/mud_agent/agent/mud_agent.py`**
   - Initialize `SyncWorker` alongside `knowledge_graph`
   - Start sync on `__aenter__`, stop on `__aexit__`

6. **`src/mud_agent/config/config.py`**
   - `DatabaseConfig`: add `sync_interval`, `sync_enabled` fields

### Unchanged Files
- `MapperContainer` — reads from `knowledge_graph` which is now local SQLite
- `RoomManager` — no changes needed
- `AardwolfGMCPManager` — no changes needed
- All event flows — unchanged

## Data Flow Example

**Player moves north:**
1. GMCP fires `room_update` → `RoomManager._on_room_update()`
2. `knowledge_graph.add_entity()` → writes to local SQLite (~0.1ms) → `sync_status='dirty'`
3. `knowledge_graph.record_exit_success()` → writes to local SQLite (~0.1ms) → `sync_status='dirty'`
4. Events emitted → `MapperContainer._rebuild_widgets()`
5. Mapper reads from local SQLite (~0.1ms per room) — depth-3 traversal completes in <5ms total
6. 30 seconds later: SyncWorker pushes dirty records to Supabase, pulls friends' changes

**Friend explores new area:**
1. Friend's SyncWorker pushes discoveries to Supabase
2. Your SyncWorker pulls on next cycle → inserts new rooms/exits into local SQLite
3. Next time you visit that area, mapper shows rooms your friend discovered

## Error Handling

- **Supabase unreachable:** SyncWorker logs warning, retries next cycle. App works offline.
- **Schema mismatch:** SyncWorker validates schema version before sync. Logs error if remote is ahead.
- **Large initial pull:** Full pull from Supabase in chunks on first run.
- **Concurrent writes:** `db.atomic()` protects local SQLite. Supabase upserts use `ON CONFLICT`.
- **Graceful degradation:** If `DATABASE_URL` is not set, SyncWorker doesn't start. Pure local mode.

## Testing Strategy

- **Unit tests for SyncWorker:** Mock Supabase connection, test push/pull/merge logic
- **Integration tests:** Two local SQLite DBs simulating "local + remote"
- **Existing tests:** Pass unchanged (no Supabase in test env)
- **Merge tests:** Union of exits, latest-wins for room fields, conflict detection
