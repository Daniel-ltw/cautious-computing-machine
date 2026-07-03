# Local-First SQLite + Supabase Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore SQLite as the local working database for zero-latency gameplay, with a background SyncWorker that bidirectionally syncs data to/from Supabase so multiple players share room/exit discoveries.

**Architecture:** All hot-path reads/writes (mapper, room manager, knowledge graph) use local SQLite only. A `SyncWorker` background task periodically pushes dirty local records to Supabase and pulls remote changes, merging via union-of-exits and latest-timestamp-wins for scalar fields.

**Tech Stack:** Peewee ORM, SQLite (local), PostgreSQL/Supabase (remote), asyncio, psycopg2

**Design doc:** `docs/plans/2026-02-16-local-first-sync-design.md`

---

## Task 1: Force SQLite Locally & Add Sync Tracking Columns

**Context:** Currently `src/mud_agent/db/models.py` lines 36-51 check `DATABASE_URL` and connect to Supabase if set. We need to **always** use SQLite locally and add `sync_status` + `remote_updated_at` columns to `BaseModel` for change tracking.

**Files:**
- Modify: `src/mud_agent/db/models.py`
- Test: `tests/db/test_models.py`

**Step 1: Write the failing test**

Add to `tests/db/test_models.py`:

```python
def test_sync_status_defaults_to_dirty(test_db):
    """New records should default to sync_status='dirty'."""
    entity = Entity.create(name="Sync Test", entity_type="Room")
    assert entity.sync_status == "dirty"
    assert entity.remote_updated_at is None


def test_save_sets_sync_status_dirty(test_db):
    """Saving a synced record should mark it dirty again."""
    entity = Entity.create(name="Sync Test", entity_type="Room")
    # Simulate that sync worker marked it synced
    Entity.update(sync_status="synced").where(Entity.id == entity.id).execute()
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "synced"

    # Now modify and save
    entity.name = "Updated Name"
    entity.save()
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "dirty"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/db/test_models.py::test_sync_status_defaults_to_dirty tests/db/test_models.py::test_save_sets_sync_status_dirty -v`
Expected: FAIL — `sync_status` attribute does not exist.

**Step 3: Modify `src/mud_agent/db/models.py`**

3a. Replace the database initialization block (lines 35-51) to **always use SQLite**:

```python
# Database configuration
DB_PATH = Path.cwd() / ".mcp" / "knowledge_graph.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Always use local SQLite for speed. Supabase sync is handled by SyncWorker.
logger.info(f"Using SQLite database at {DB_PATH}")
db = SqliteDatabase(str(DB_PATH), pragmas={'journal_mode': 'wal'})
```

Remove the `database_url`, `connect_kwargs`, `PostgresqlDatabase`, `connect` imports, and the `psycopg2` conditional block. Remove unused imports: `PostgresqlDatabase` from peewee, `connect` from `playhouse.db_url`.

3b. Add sync tracking columns to `BaseModel` (after existing fields at line 55-56):

```python
class BaseModel(Model):
    """Base model with common fields and database configuration."""

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    sync_status = CharField(max_length=10, default="dirty")  # dirty, synced, conflict
    remote_updated_at = DateTimeField(null=True, default=None)

    class Meta:
        database = db

    def save(self, *args, **kwargs):
        """Override save to update timestamps and mark as dirty."""
        self.updated_at = datetime.now()
        self.sync_status = "dirty"
        return super().save(*args, **kwargs)
```

3c. Update the `test_db` fixture in `tests/db/test_models.py` — the existing fixture should still work since we're just adding columns to the same SQLite schema created by `db.create_tables`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/db/test_models.py -v`
Expected: All tests PASS including the two new ones.

**Step 5: Commit**

```bash
git add src/mud_agent/db/models.py tests/db/test_models.py
git commit -m "feat(db): force local SQLite, add sync_status tracking columns"
```

---

## Task 2: Add Migration for Sync Columns

**Context:** Existing databases need the new `sync_status` and `remote_updated_at` columns added via a migration. The migration system is in `src/mud_agent/db/migrations.py` using `MigrationManager`.

**Files:**
- Modify: `src/mud_agent/db/migrations.py`

**Step 1: Add a new migration to `MigrationManager._register_migrations`**

After the existing migration registration, add:

```python
# Migration 002: Add sync tracking columns
self.migrations.append(Migration(
    version=2,
    description="Add sync_status and remote_updated_at columns for Supabase sync",
    up_func=self._migration_002_up,
    down_func=self._migration_002_down
))
```

Add the migration methods to `MigrationManager`:

```python
def _migration_002_up(self):
    """Add sync tracking columns to all models."""
    from playhouse.migrate import SqliteMigrator, migrate
    migrator = SqliteMigrator(self.db)

    tables_to_update = ['entity', 'room', 'roomexit', 'npc', 'observation', 'relation']
    for table in tables_to_update:
        try:
            migrate(
                migrator.add_column(table, 'sync_status',
                    CharField(max_length=10, default='dirty')),
                migrator.add_column(table, 'remote_updated_at',
                    DateTimeField(null=True, default=None)),
            )
        except Exception as e:
            # Column may already exist
            logger.warning(f"Migration 002: Could not add columns to {table}: {e}")

def _migration_002_down(self):
    """Remove sync tracking columns."""
    from playhouse.migrate import SqliteMigrator, migrate
    migrator = SqliteMigrator(self.db)

    tables_to_update = ['entity', 'room', 'roomexit', 'npc', 'observation', 'relation']
    for table in tables_to_update:
        try:
            migrate(
                migrator.drop_column(table, 'sync_status'),
                migrator.drop_column(table, 'remote_updated_at'),
            )
        except Exception:
            pass
```

Add the needed imports at the top of the file if not already present:
```python
from peewee import CharField, DateTimeField
```

**Step 2: Run existing migration tests (if any) or verify manually**

Run: `pytest tests/db/ -v`
Expected: All PASS.

**Step 3: Commit**

```bash
git add src/mud_agent/db/migrations.py
git commit -m "feat(db): add migration 002 for sync tracking columns"
```

---

## Task 3: Remove Supabase Retry Logic from Knowledge Graph

**Context:** `src/mud_agent/mcp/game_knowledge_graph.py` has a `retry_on_timeout` decorator that catches `psycopg2` errors. With local SQLite, this is unnecessary and the `psycopg2` import will fail if the package isn't installed. Remove it.

**Files:**
- Modify: `src/mud_agent/mcp/game_knowledge_graph.py`
- Test: `tests/mcp/test_game_knowledge_graph.py`

**Step 1: Write the failing test**

Add to `tests/mcp/test_game_knowledge_graph.py`:

```python
@pytest.mark.asyncio
async def test_get_room_info_no_retry_decorator(knowledge_graph):
    """Verify get_room_info_sync is not wrapped in retry logic."""
    # The sync method should be a plain method, not wrapped
    assert not hasattr(knowledge_graph._get_room_info_sync, '__wrapped__')
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_game_knowledge_graph.py::test_get_room_info_no_retry_decorator -v`
Expected: FAIL — `__wrapped__` exists because of `functools.wraps` in the decorator.

**Step 3: Remove retry logic from `game_knowledge_graph.py`**

3a. Delete the entire `retry_on_timeout` function (lines 31-63) and its imports (`psycopg2`, `time`, `functools`). Keep `functools` only if used elsewhere.

3b. Remove `@retry_on_timeout(...)` decorators from all `_sync` methods:
- `_get_room_info_sync` (line 275)
- `get_room_by_number_sync` (line 294)
- `_add_entity_sync` (line 160)
- `_get_rooms_by_area_sync`
- `_record_exit_success_sync`
- Any other method decorated with `@retry_on_timeout`

Search the file for all occurrences of `@retry_on_timeout` and remove each one.

3c. Remove `import psycopg2` and `import time` if they are no longer used anywhere in the file.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/mcp/ -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/mud_agent/mcp/game_knowledge_graph.py tests/mcp/test_game_knowledge_graph.py
git commit -m "refactor(kg): remove psycopg2 retry logic, SQLite doesn't need it"
```

---

## Task 4: Update DatabaseConfig for Sync Settings

**Context:** `src/mud_agent/config/config.py` has `DatabaseConfig` with just `url`. We need to add `sync_enabled` and `sync_interval` fields.

**Files:**
- Modify: `src/mud_agent/config/config.py`
- Test: `tests/config/test_agent_config.py`

**Step 1: Write the failing test**

Add to `tests/config/test_agent_config.py`:

```python
import os
from unittest.mock import patch

from mud_agent.config.config import DatabaseConfig


def test_database_config_defaults():
    """DatabaseConfig should have sync settings with sensible defaults."""
    config = DatabaseConfig()
    assert config.sync_enabled is False
    assert config.sync_interval == 30.0
    assert config.url is None


def test_database_config_from_env():
    """DatabaseConfig should load sync settings from environment."""
    env = {
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "SYNC_ENABLED": "true",
        "SYNC_INTERVAL": "15",
    }
    with patch.dict(os.environ, env):
        config = DatabaseConfig.from_env()
        assert config.url == "postgresql://user:pass@host:5432/db"
        assert config.sync_enabled is True
        assert config.sync_interval == 15.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_agent_config.py::test_database_config_defaults tests/config/test_agent_config.py::test_database_config_from_env -v`
Expected: FAIL — `sync_enabled` and `sync_interval` don't exist.

**Step 3: Update `DatabaseConfig` in `src/mud_agent/config/config.py`**

```python
@dataclass
class DatabaseConfig:
    """Configuration for the database."""

    url: str | None = None
    sync_enabled: bool = False
    sync_interval: float = 30.0

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create a DatabaseConfig from environment variables."""
        sync_enabled_raw = os.getenv("SYNC_ENABLED", "false").strip().lower()
        return cls(
            url=os.getenv("DATABASE_URL"),
            sync_enabled=sync_enabled_raw in {"true", "1", "yes"},
            sync_interval=float(os.getenv("SYNC_INTERVAL", "30")),
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/config/ -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/mud_agent/config/config.py tests/config/test_agent_config.py
git commit -m "feat(config): add sync_enabled and sync_interval to DatabaseConfig"
```

---

## Task 5: Create Remote Sync Models

**Context:** The SyncWorker needs its own Peewee models bound to the remote Supabase PostgresqlDatabase, separate from the local SQLite models. These mirror the local schema exactly.

**Files:**
- Create: `src/mud_agent/db/sync_models.py`
- Test: `tests/db/test_sync_models.py`

**Step 1: Write the failing test**

Create `tests/db/test_sync_models.py`:

```python
import tempfile
from pathlib import Path

import pytest
from peewee import SqliteDatabase

from mud_agent.db.sync_models import (
    RemoteBaseModel,
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
    RemoteNPC,
    RemoteObservation,
    RemoteRelation,
    REMOTE_ALL_MODELS,
    create_remote_db,
)


@pytest.fixture
def remote_test_db():
    """Create a temporary database simulating a remote DB."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        path = tmp.name
    test_db = SqliteDatabase(path)
    # Bind all remote models to this test DB
    for model in REMOTE_ALL_MODELS:
        model._meta.database = test_db
    test_db.connect()
    test_db.create_tables(REMOTE_ALL_MODELS)
    yield test_db
    test_db.drop_tables(REMOTE_ALL_MODELS)
    test_db.close()
    Path(path).unlink()


def test_remote_models_have_sync_columns(remote_test_db):
    """Remote models should have sync_status and remote_updated_at."""
    entity = RemoteEntity.create(name="Test", entity_type="Room", sync_status="synced")
    assert entity.sync_status == "synced"


def test_create_remote_db_returns_database():
    """create_remote_db should return a Peewee database instance."""
    db = create_remote_db("sqlite:///tmp/test_remote.db")
    assert db is not None


def test_remote_room_schema(remote_test_db):
    """Remote Room model should have all expected fields."""
    entity = RemoteEntity.create(name="100", entity_type="Room")
    room = RemoteRoom.create(
        entity=entity, room_number=100, terrain="city", zone="Midgaard"
    )
    assert room.room_number == 100
    assert room.zone == "Midgaard"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/db/test_sync_models.py -v`
Expected: FAIL — `mud_agent.db.sync_models` does not exist.

**Step 3: Create `src/mud_agent/db/sync_models.py`**

```python
"""Remote (Supabase) database models for sync.

These models mirror the local SQLite schema exactly but are bound
to a remote PostgreSQL database. They are used exclusively by
the SyncWorker for push/pull operations.
"""

import logging
from datetime import datetime
from typing import Optional

from peewee import (
    SQL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)
from playhouse.db_url import connect

logger = logging.getLogger(__name__)

# Remote database instance — initialized lazily by create_remote_db()
_remote_db = None


def create_remote_db(database_url: str, **kwargs):
    """Create and return a Peewee database connection to the remote DB.

    Args:
        database_url: PostgreSQL connection string.
        **kwargs: Additional connection arguments.

    Returns:
        A Peewee Database instance.
    """
    global _remote_db
    connect_kwargs = kwargs.pop("connect_kwargs", {})
    connect_kwargs.setdefault("options", "-c statement_timeout=30000 -c lock_timeout=10000")
    _remote_db = connect(database_url, **connect_kwargs)

    # Bind all remote models to this database
    for model in REMOTE_ALL_MODELS:
        model._meta.database = _remote_db

    return _remote_db


class RemoteBaseModel(Model):
    """Base model for remote database."""

    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    sync_status = CharField(max_length=10, default="synced")
    remote_updated_at = DateTimeField(null=True, default=None)

    class Meta:
        # Database is set dynamically by create_remote_db()
        database = None

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)


class RemoteEntity(RemoteBaseModel):
    """Remote mirror of Entity."""

    name = CharField(max_length=200, index=True)
    entity_type = CharField(max_length=50, index=True)

    class Meta:
        table_name = "entity"


class RemoteRoom(RemoteBaseModel):
    """Remote mirror of Room."""

    entity = ForeignKeyField(RemoteEntity, backref="room_data", unique=True)
    room_number = IntegerField(unique=True, index=True)
    terrain = CharField(max_length=50, null=True, index=True)
    zone = CharField(max_length=100, null=True, index=True)
    full_name = CharField(max_length=200, null=True)
    outside = BooleanField(default=False, index=True)
    coord_x = IntegerField(null=True)
    coord_y = IntegerField(null=True)
    coord_z = IntegerField(null=True)
    details = TextField(null=True)

    class Meta:
        table_name = "room"
        indexes = (
            (("coord_x", "coord_y", "coord_z"), False),
            (("zone", "terrain"), False),
        )


class RemoteRoomExit(RemoteBaseModel):
    """Remote mirror of RoomExit."""

    from_room = ForeignKeyField(RemoteRoom, backref="exits")
    direction = CharField(max_length=20, index=True)
    to_room_number = IntegerField(index=True, null=True)
    is_door = BooleanField(default=False)
    door_is_closed = BooleanField(default=False)
    to_room = ForeignKeyField(RemoteRoom, backref="entrances", null=True)
    details = TextField(null=True)

    class Meta:
        table_name = "roomexit"
        indexes = (
            (("from_room", "direction"), True),
            (("to_room_number", "direction"), False),
        )


class RemoteNPC(RemoteBaseModel):
    """Remote mirror of NPC."""

    entity = ForeignKeyField(RemoteEntity, backref="npc_data", unique=True)
    level = IntegerField(null=True)
    is_aggressive = BooleanField(default=False)
    current_room = ForeignKeyField(RemoteRoom, backref="npcs", null=True)

    class Meta:
        table_name = "npc"


class RemoteObservation(RemoteBaseModel):
    """Remote mirror of Observation."""

    entity = ForeignKeyField(RemoteEntity, backref="observations")
    observation_type = CharField(max_length=50)
    content = TextField()
    source = CharField(max_length=100, null=True)

    class Meta:
        table_name = "observation"


class RemoteRelation(RemoteBaseModel):
    """Remote mirror of Relation."""

    from_entity = ForeignKeyField(RemoteEntity, backref="relations_from")
    to_entity = ForeignKeyField(RemoteEntity, backref="relations_to")
    relation_type = CharField(max_length=50)

    class Meta:
        table_name = "relation"


REMOTE_ALL_MODELS = [
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
    RemoteNPC,
    RemoteObservation,
    RemoteRelation,
]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/db/test_sync_models.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/mud_agent/db/sync_models.py tests/db/test_sync_models.py
git commit -m "feat(db): add remote sync models mirroring local schema"
```

---

## Task 6: Create SyncWorker — Push Logic

**Context:** The core sync worker that pushes dirty local records to Supabase. This is the first half of bidirectional sync.

**Files:**
- Create: `src/mud_agent/db/sync_worker.py`
- Create: `tests/db/test_sync_worker.py`

**Step 1: Write the failing tests**

Create `tests/db/test_sync_worker.py`:

```python
"""Tests for the SyncWorker push/pull logic.

Uses two SQLite databases to simulate local and remote.
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from peewee import SqliteDatabase

from mud_agent.db.models import (
    ALL_MODELS,
    Entity,
    Room,
    RoomExit,
    db as local_db,
)
from mud_agent.db.sync_models import (
    REMOTE_ALL_MODELS,
    RemoteEntity,
    RemoteRoom,
    RemoteRoomExit,
)
from mud_agent.db.sync_worker import SyncWorker


@pytest.fixture
def local_test_db():
    """Set up local SQLite DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    local_db.init(path)
    local_db.connect()
    local_db.create_tables(ALL_MODELS)
    yield local_db
    local_db.drop_tables(ALL_MODELS)
    local_db.close()
    Path(path).unlink()


@pytest.fixture
def remote_test_db():
    """Set up remote SQLite DB simulating Supabase."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    remote_db = SqliteDatabase(path)
    for model in REMOTE_ALL_MODELS:
        model._meta.database = remote_db
    remote_db.connect()
    remote_db.create_tables(REMOTE_ALL_MODELS)
    yield remote_db
    remote_db.drop_tables(REMOTE_ALL_MODELS)
    remote_db.close()
    Path(path).unlink()


@pytest.fixture
def sync_worker(local_test_db, remote_test_db):
    """Create a SyncWorker with test databases."""
    worker = SyncWorker(sync_interval=1.0)
    worker._remote_db = remote_test_db
    return worker


def test_push_dirty_entities(sync_worker, local_test_db, remote_test_db):
    """Dirty local entities should be pushed to remote."""
    # Create a dirty entity locally
    entity = Entity.create(name="100", entity_type="Room")
    assert entity.sync_status == "dirty"

    # Push
    sync_worker.push()

    # Verify it arrived remotely
    remote_entity = RemoteEntity.get_or_none(RemoteEntity.name == "100")
    assert remote_entity is not None
    assert remote_entity.entity_type == "Room"

    # Verify local is now synced
    entity = Entity.get_by_id(entity.id)
    assert entity.sync_status == "synced"


def test_push_dirty_rooms_with_exits(sync_worker, local_test_db, remote_test_db):
    """Dirty rooms and their exits should be pushed."""
    entity = Entity.create(name="200", entity_type="Room")
    room = Room.create(entity=entity, room_number=200, zone="TestArea", terrain="city")

    entity2 = Entity.create(name="201", entity_type="Room")
    room2 = Room.create(entity=entity2, room_number=201, zone="TestArea", terrain="city")

    RoomExit.create(from_room=room, direction="n", to_room=room2, to_room_number=201)

    sync_worker.push()

    remote_room = RemoteRoom.get_or_none(RemoteRoom.room_number == 200)
    assert remote_room is not None

    remote_exit = RemoteRoomExit.get_or_none(RemoteRoomExit.from_room == remote_room)
    assert remote_exit is not None
    assert remote_exit.direction == "n"
    assert remote_exit.to_room_number == 201


def test_push_skips_synced_records(sync_worker, local_test_db, remote_test_db):
    """Already-synced records should not be pushed again."""
    entity = Entity.create(name="300", entity_type="Room")
    Entity.update(sync_status="synced").where(Entity.id == entity.id).execute()

    sync_worker.push()

    remote_entity = RemoteEntity.get_or_none(RemoteEntity.name == "300")
    assert remote_entity is None  # Should not have been pushed
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/db/test_sync_worker.py -v`
Expected: FAIL — `mud_agent.db.sync_worker` does not exist.

**Step 3: Create `src/mud_agent/db/sync_worker.py`**

```python
"""SyncWorker: Background bidirectional sync between local SQLite and remote Supabase.

Push: Finds all local records with sync_status='dirty', upserts them to remote.
Pull: Finds all remote records newer than last_pull_timestamp, merges locally.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from peewee import DoesNotExist

from mud_agent.db.models import (
    ALL_MODELS,
    Entity,
    NPC,
    Observation,
    Relation,
    Room,
    RoomExit,
    db as local_db,
)
from mud_agent.db.sync_models import (
    REMOTE_ALL_MODELS,
    RemoteEntity,
    RemoteNPC,
    RemoteObservation,
    RemoteRelation,
    RemoteRoom,
    RemoteRoomExit,
    create_remote_db,
)

logger = logging.getLogger(__name__)

# Mapping from local models to remote models
LOCAL_TO_REMOTE = {
    Entity: RemoteEntity,
    Room: RemoteRoom,
    RoomExit: RemoteRoomExit,
    NPC: RemoteNPC,
    Observation: RemoteObservation,
    Relation: RemoteRelation,
}

# Push order: entities first, then rooms, then everything else
PUSH_ORDER = [Entity, Room, RoomExit, NPC, Observation, Relation]


class SyncWorker:
    """Background worker that syncs local SQLite with remote Supabase."""

    def __init__(self, sync_interval: float = 30.0):
        self.sync_interval = sync_interval
        self._task: Optional[asyncio.Task] = None
        self._remote_db = None
        self._last_pull_at: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)

    async def start(self, database_url: str) -> None:
        """Start the background sync loop."""
        try:
            self._remote_db = create_remote_db(database_url)
            if self._remote_db.is_closed():
                self._remote_db.connect()
            self._remote_db.create_tables(REMOTE_ALL_MODELS, safe=True)
            self.logger.info("SyncWorker connected to remote database.")
        except Exception as e:
            self.logger.error(f"SyncWorker failed to connect to remote DB: {e}")
            return

        self._task = asyncio.create_task(self._sync_loop())
        self.logger.info(f"SyncWorker started with interval={self.sync_interval}s")

    async def stop(self) -> None:
        """Stop the sync loop gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._remote_db and not self._remote_db.is_closed():
            self._remote_db.close()
        self.logger.info("SyncWorker stopped.")

    async def _sync_loop(self) -> None:
        """Main sync loop: push then pull on each cycle."""
        try:
            while True:
                try:
                    await asyncio.to_thread(self.push)
                    await asyncio.to_thread(self.pull)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.error(f"Sync cycle error: {e}", exc_info=True)
                await asyncio.sleep(self.sync_interval)
        except asyncio.CancelledError:
            self.logger.info("SyncWorker loop cancelled.")

    def push(self) -> None:
        """Push all dirty local records to the remote database."""
        for local_model in PUSH_ORDER:
            remote_model = LOCAL_TO_REMOTE[local_model]
            dirty_records = list(local_model.select().where(
                local_model.sync_status == "dirty"
            ))

            if not dirty_records:
                continue

            self.logger.debug(
                f"Pushing {len(dirty_records)} dirty {local_model.__name__} records"
            )

            for record in dirty_records:
                try:
                    self._push_record(record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to push {local_model.__name__} id={record.id}: {e}"
                    )

    def _push_record(self, record, local_model, remote_model) -> None:
        """Push a single local record to the remote database."""
        # Convert to dict, excluding internal Peewee fields
        data = {}
        for field in local_model._meta.sorted_fields:
            if field.name == "id":
                continue
            value = getattr(record, field.name)
            # Handle foreign keys: store the ID, not the object
            if hasattr(field, "rel_model"):
                fk_value = getattr(record, field.name + "_id", None)
                data[field.name] = fk_value
            else:
                data[field.name] = value

        data["sync_status"] = "synced"
        data["remote_updated_at"] = datetime.now(timezone.utc)

        # Upsert to remote: use local record's ID as the key
        with self._remote_db.atomic():
            # Try to find existing by matching natural key
            existing = self._find_remote_by_natural_key(record, local_model, remote_model)
            if existing:
                # Update
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.save()
            else:
                # Insert
                remote_model.create(**data)

        # Mark local as synced (bypass the save() override that sets dirty)
        local_model.update(
            sync_status="synced",
            remote_updated_at=datetime.now(timezone.utc),
        ).where(local_model.id == record.id).execute()

    def _find_remote_by_natural_key(self, record, local_model, remote_model):
        """Find the remote counterpart of a local record by natural key."""
        try:
            if local_model == Entity:
                return remote_model.get_or_none(
                    (remote_model.name == record.name)
                    & (remote_model.entity_type == record.entity_type)
                )
            elif local_model == Room:
                return remote_model.get_or_none(
                    remote_model.room_number == record.room_number
                )
            elif local_model == RoomExit:
                # Match by from_room's room_number + direction
                from_room = record.from_room
                remote_from = RemoteRoom.get_or_none(
                    RemoteRoom.room_number == from_room.room_number
                )
                if remote_from:
                    return remote_model.get_or_none(
                        (remote_model.from_room == remote_from)
                        & (remote_model.direction == record.direction)
                    )
                return None
            elif local_model == NPC:
                entity = record.entity
                remote_entity = RemoteEntity.get_or_none(
                    (RemoteEntity.name == entity.name)
                    & (RemoteEntity.entity_type == entity.entity_type)
                )
                if remote_entity:
                    return remote_model.get_or_none(
                        remote_model.entity == remote_entity
                    )
                return None
            else:
                # For Observation/Relation, use ID-based matching
                return remote_model.get_or_none(remote_model.id == record.id)
        except Exception:
            return None

    def pull(self) -> None:
        """Pull new/updated records from remote and merge locally."""
        for local_model in PUSH_ORDER:
            remote_model = LOCAL_TO_REMOTE[local_model]

            query = remote_model.select()
            if self._last_pull_at:
                query = query.where(remote_model.updated_at > self._last_pull_at)

            remote_records = list(query)
            if not remote_records:
                continue

            self.logger.debug(
                f"Pulling {len(remote_records)} {remote_model.__name__} records"
            )

            for remote_record in remote_records:
                try:
                    self._pull_record(remote_record, local_model, remote_model)
                except Exception as e:
                    self.logger.error(
                        f"Failed to pull {remote_model.__name__} id={remote_record.id}: {e}"
                    )

        self._last_pull_at = datetime.now(timezone.utc)

    def _pull_record(self, remote_record, local_model, remote_model) -> None:
        """Pull a single remote record and merge it locally."""
        local_record = self._find_local_by_natural_key(
            remote_record, local_model, remote_model
        )

        if local_record is None:
            # New record from remote — insert locally
            self._insert_local_from_remote(remote_record, local_model, remote_model)
            return

        if local_record.sync_status == "synced":
            # Local is clean — overwrite with remote data
            self._overwrite_local_from_remote(
                local_record, remote_record, local_model, remote_model
            )
        elif local_record.sync_status == "dirty":
            # Local has changes — merge
            self._merge_local_with_remote(
                local_record, remote_record, local_model, remote_model
            )

    def _find_local_by_natural_key(self, remote_record, local_model, remote_model):
        """Find the local counterpart of a remote record."""
        try:
            if local_model == Entity:
                return local_model.get_or_none(
                    (local_model.name == remote_record.name)
                    & (local_model.entity_type == remote_record.entity_type)
                )
            elif local_model == Room:
                return local_model.get_or_none(
                    local_model.room_number == remote_record.room_number
                )
            elif local_model == RoomExit:
                remote_from = remote_record.from_room
                local_from = Room.get_or_none(
                    Room.room_number == remote_from.room_number
                )
                if local_from:
                    return local_model.get_or_none(
                        (local_model.from_room == local_from)
                        & (local_model.direction == remote_record.direction)
                    )
                return None
            elif local_model == NPC:
                remote_entity = remote_record.entity
                local_entity = Entity.get_or_none(
                    (Entity.name == remote_entity.name)
                    & (Entity.entity_type == remote_entity.entity_type)
                )
                if local_entity:
                    return local_model.get_or_none(local_model.entity == local_entity)
                return None
            else:
                return local_model.get_or_none(local_model.id == remote_record.id)
        except Exception:
            return None

    def _insert_local_from_remote(self, remote_record, local_model, remote_model) -> None:
        """Insert a new local record from a remote record."""
        data = {}
        for field in remote_model._meta.sorted_fields:
            if field.name == "id":
                continue
            value = getattr(remote_record, field.name)
            if hasattr(field, "rel_model"):
                data[field.name] = getattr(remote_record, field.name + "_id", None)
            else:
                data[field.name] = value

        data["sync_status"] = "synced"
        data["remote_updated_at"] = remote_record.updated_at

        # Resolve foreign keys from remote IDs to local IDs
        if local_model == Room:
            remote_entity = remote_record.entity
            local_entity = Entity.get_or_none(
                (Entity.name == remote_entity.name)
                & (Entity.entity_type == remote_entity.entity_type)
            )
            if local_entity:
                data["entity"] = local_entity.id
            else:
                return  # Can't create room without entity

        elif local_model == RoomExit:
            remote_from = remote_record.from_room
            local_from = Room.get_or_none(Room.room_number == remote_from.room_number)
            if local_from:
                data["from_room"] = local_from.id
            else:
                return  # Can't create exit without from_room

            if remote_record.to_room:
                local_to = Room.get_or_none(
                    Room.room_number == remote_record.to_room.room_number
                )
                data["to_room"] = local_to.id if local_to else None

        with local_db.atomic():
            # Use update().execute() after create to avoid save() setting dirty
            new_record = local_model.create(**data)
            local_model.update(sync_status="synced").where(
                local_model.id == new_record.id
            ).execute()

    def _overwrite_local_from_remote(
        self, local_record, remote_record, local_model, remote_model
    ) -> None:
        """Overwrite a clean local record with remote data."""
        for field in remote_model._meta.sorted_fields:
            if field.name in ("id", "sync_status", "remote_updated_at"):
                continue
            if hasattr(field, "rel_model"):
                # Skip FK resolution for now — handled by natural keys
                continue
            value = getattr(remote_record, field.name)
            setattr(local_record, field, value)

        # Bypass save() override
        local_model.update(
            sync_status="synced",
            remote_updated_at=remote_record.updated_at,
            updated_at=remote_record.updated_at,
        ).where(local_model.id == local_record.id).execute()

    def _merge_local_with_remote(
        self, local_record, remote_record, local_model, remote_model
    ) -> None:
        """Merge a dirty local record with remote data (union strategy)."""
        if local_model == Room:
            # Scalar fields: latest updated_at wins
            if remote_record.updated_at and (
                not local_record.updated_at
                or remote_record.updated_at > local_record.updated_at
            ):
                for field_name in ("terrain", "zone", "full_name", "coord_x", "coord_y", "coord_z", "details"):
                    remote_val = getattr(remote_record, field_name)
                    if remote_val is not None:
                        setattr(local_record, field_name, remote_val)

        elif local_model == RoomExit:
            # Exit details: latest last_success_at wins
            import json
            local_details = json.loads(local_record.details) if local_record.details else {}
            remote_details = json.loads(remote_record.details) if remote_record.details else {}

            local_ts = local_details.get("last_success_at", "")
            remote_ts = remote_details.get("last_success_at", "")
            if remote_ts > local_ts:
                local_record.details = remote_record.details

        # Keep as dirty so next push cycle sends merged data
        local_record.save()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/db/test_sync_worker.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/mud_agent/db/sync_worker.py tests/db/test_sync_worker.py
git commit -m "feat(sync): create SyncWorker with push/pull/merge logic"
```

---

## Task 7: Create SyncWorker — Pull & Merge Tests

**Context:** Add dedicated tests for the pull and merge behavior to ensure friends' discoveries are correctly integrated.

**Files:**
- Modify: `tests/db/test_sync_worker.py`

**Step 1: Add pull and merge tests**

Append to `tests/db/test_sync_worker.py`:

```python
def test_pull_new_rooms_from_remote(sync_worker, local_test_db, remote_test_db):
    """Rooms created on remote (by a friend) should appear locally after pull."""
    # Simulate friend adding a room on remote
    remote_entity = RemoteEntity.create(name="500", entity_type="Room", sync_status="synced")
    RemoteRoom.create(
        entity=remote_entity, room_number=500, zone="FriendZone",
        terrain="forest", sync_status="synced"
    )

    sync_worker.pull()

    local_room = Room.get_or_none(Room.room_number == 500)
    assert local_room is not None
    assert local_room.zone == "FriendZone"
    assert local_room.sync_status == "synced"


def test_pull_new_exits_from_remote(sync_worker, local_test_db, remote_test_db):
    """Exits discovered by a friend should be merged locally."""
    # Set up local room (already exists)
    local_entity = Entity.create(name="600", entity_type="Room")
    local_room = Room.create(entity=local_entity, room_number=600, zone="Shared")
    Entity.update(sync_status="synced").where(Entity.id == local_entity.id).execute()
    Room.update(sync_status="synced").where(Room.id == local_room.id).execute()

    local_entity2 = Entity.create(name="601", entity_type="Room")
    local_room2 = Room.create(entity=local_entity2, room_number=601, zone="Shared")
    Entity.update(sync_status="synced").where(Entity.id == local_entity2.id).execute()
    Room.update(sync_status="synced").where(Room.id == local_room2.id).execute()

    # Friend discovers an exit on remote that we don't have
    remote_entity = RemoteEntity.create(name="600", entity_type="Room", sync_status="synced")
    remote_room = RemoteRoom.create(
        entity=remote_entity, room_number=600, zone="Shared", sync_status="synced"
    )
    remote_entity2 = RemoteEntity.create(name="601", entity_type="Room", sync_status="synced")
    remote_room2 = RemoteRoom.create(
        entity=remote_entity2, room_number=601, zone="Shared", sync_status="synced"
    )
    RemoteRoomExit.create(
        from_room=remote_room, direction="e", to_room=remote_room2,
        to_room_number=601, sync_status="synced"
    )

    sync_worker.pull()

    # Verify exit now exists locally
    local_exit = RoomExit.get_or_none(
        (RoomExit.from_room == local_room) & (RoomExit.direction == "e")
    )
    assert local_exit is not None
    assert local_exit.to_room_number == 601


def test_merge_dirty_local_with_remote_update(sync_worker, local_test_db, remote_test_db):
    """When local is dirty and remote has updates, merge should combine data."""
    # Local room with dirty status
    local_entity = Entity.create(name="700", entity_type="Room")
    local_room = Room.create(
        entity=local_entity, room_number=700, zone="LocalZone", terrain="city"
    )
    # It's dirty because save() sets it

    # Remote has newer terrain info
    remote_entity = RemoteEntity.create(name="700", entity_type="Room", sync_status="synced")
    from datetime import timedelta
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    RemoteRoom.create(
        entity=remote_entity, room_number=700, zone="LocalZone",
        terrain="forest", sync_status="synced", updated_at=future_time
    )

    sync_worker.pull()

    # Local should have merged — remote terrain wins (newer)
    local_room = Room.get(Room.room_number == 700)
    assert local_room.terrain == "forest"
    # But still dirty because local had changes
    assert local_room.sync_status == "dirty"
```

**Step 2: Run tests**

Run: `pytest tests/db/test_sync_worker.py -v`
Expected: All PASS.

**Step 3: Commit**

```bash
git add tests/db/test_sync_worker.py
git commit -m "test(sync): add pull and merge tests for SyncWorker"
```

---

## Task 8: Integrate SyncWorker into MUDAgent

**Context:** Wire the SyncWorker into the agent lifecycle so it starts/stops with the app.

**Files:**
- Modify: `src/mud_agent/agent/mud_agent.py`
- Modify: `tests/test_mud_agent.py`

**Step 1: Write the failing test**

Add to `tests/test_mud_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mud_agent.config.config import Config


@pytest.mark.asyncio
async def test_sync_worker_starts_when_enabled():
    """SyncWorker should start when sync_enabled is True and DATABASE_URL is set."""
    config = Config.load()
    config.database.sync_enabled = True
    config.database.url = "postgresql://user:pass@host/db"
    config.database.sync_interval = 10.0

    with patch("mud_agent.agent.mud_agent.SyncWorker") as MockSyncWorker:
        mock_worker = AsyncMock()
        MockSyncWorker.return_value = mock_worker

        from mud_agent.agent.mud_agent import MUDAgent
        agent = MUDAgent(config)

        assert agent.sync_worker is not None


@pytest.mark.asyncio
async def test_sync_worker_not_created_when_disabled():
    """SyncWorker should not be created when sync_enabled is False."""
    config = Config.load()
    config.database.sync_enabled = False

    from mud_agent.agent.mud_agent import MUDAgent
    agent = MUDAgent(config)

    assert agent.sync_worker is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mud_agent.py::test_sync_worker_starts_when_enabled tests/test_mud_agent.py::test_sync_worker_not_created_when_disabled -v`
Expected: FAIL — `agent.sync_worker` does not exist.

**Step 3: Modify `src/mud_agent/agent/mud_agent.py`**

3a. Add import at the top:
```python
from mud_agent.db.sync_worker import SyncWorker
```

3b. In `__init__`, after the `self.knowledge_graph` initialization (around line 73):
```python
# Initialize sync worker if configured
self.sync_worker = None
if config.database.sync_enabled and config.database.url:
    self.sync_worker = SyncWorker(sync_interval=config.database.sync_interval)
    self.logger.info("SyncWorker configured for background sync")
```

3c. In `__aenter__`, after `await self.knowledge_graph.initialize()` (line 144):
```python
# Start background sync if configured
if self.sync_worker and self.config.database.url:
    await self.sync_worker.start(self.config.database.url)
```

3d. In `__aexit__`, before `await self.disconnect()` (around line 195):
```python
# Stop sync worker
if self.sync_worker:
    await self.sync_worker.stop()
    self.logger.info("Stopped SyncWorker")
```

**Step 4: Run tests**

Run: `pytest tests/test_mud_agent.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add src/mud_agent/agent/mud_agent.py tests/test_mud_agent.py
git commit -m "feat(agent): integrate SyncWorker into MUDAgent lifecycle"
```

---

## Task 9: Update `.env.example` and Documentation

**Files:**
- Modify: `.env.example`

**Step 1: Update `.env.example`**

Add the sync configuration options:

```bash
# Supabase Sync Configuration
# Set DATABASE_URL to enable background sync to Supabase
# DATABASE_URL=postgresql://user:password@host:port/dbname
# SYNC_ENABLED=true
# SYNC_INTERVAL=30
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add sync configuration to .env.example"
```

---

## Task 10: Run Full Test Suite & Final Verification

**Step 1: Run the complete test suite**

Run: `pytest --tb=short -q`
Expected: All existing tests pass. No regressions.

**Step 2: Run linter**

Run: `ruff check .`
Expected: No errors (or only pre-existing ones).

**Step 3: Verify the hot path is SQLite-only**

Manually verify by reading `src/mud_agent/db/models.py` that the database initialization no longer references `DATABASE_URL` or `PostgresqlDatabase`.

**Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address test/lint issues from sync integration"
```
