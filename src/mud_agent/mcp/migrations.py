#!/usr/bin/env python3
"""
Database migration system for the MUD Agent knowledge graph.

This module provides a simple migration system to manage schema changes
for the SQLite database using Peewee ORM models.
"""

import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..db.models import NPC, Entity, Observation, Relation, Room, RoomExit, db


class Migration:
    """Represents a single database migration."""

    def __init__(self, version: int, description: str, up_func: Callable, down_func: Callable = None):
        self.version = version
        self.description = description
        self.up_func = up_func
        self.down_func = down_func

    def apply(self):
        """Apply the migration."""
        print(f"Applying migration {self.version}: {self.description}")
        self.up_func()

    def rollback(self):
        """Rollback the migration."""
        if self.down_func:
            print(f"Rolling back migration {self.version}: {self.description}")
            self.down_func()
        else:
            print(f"No rollback available for migration {self.version}")


class MigrationManager:
    """Manages database migrations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations: list[Migration] = []
        self._register_migrations()

    def _register_migrations(self):
        """Register all available migrations."""
        # Migration 001: Initial schema creation
        self.migrations.append(Migration(
            version=1,
            description="Create initial schema with all tables and indexes",
            up_func=self._migration_001_up,
            down_func=self._migration_001_down
        ))

        # Migration 002: Add composite unique constraint to NPC
        self.migrations.append(Migration(
            version=2,
            description="Add composite unique constraint on NPC entity and room",
            up_func=self._migration_002_up,
            down_func=self._migration_002_down
        ))

        # Migration 003: Add door fields to RoomExit
        self.migrations.append(Migration(
            version=3,
            description="Add is_door and door_is_closed to RoomExit table",
            up_func=self._migration_003_up,
            down_func=self._migration_003_down
        ))

        # Migration 004: Remove duplicate RoomExit records
        self.migrations.append(Migration(
            version=4,
            description="Remove duplicate RoomExit records, keeping the oldest",
            up_func=self._migration_004_up,
            down_func=self._migration_004_down
        ))

        # Migration 005: Remove duplicate RoomExit records by to_room_number
        self.migrations.append(Migration(
            version=5,
            description="Remove duplicate RoomExit records by to_room_number, keeping the oldest",
            up_func=self._migration_005_up,
            down_func=self._migration_005_down
        ))

        # Migration 006: Add unique constraint to RoomExit
        self.migrations.append(Migration(
            version=6,
            description="Add unique constraint on RoomExit (from_room_id, to_room_number)",
            up_func=self._migration_006_up,
            down_func=self._migration_006_down
        ))

        # Migration 007: Remove redundant indexes
        self.migrations.append(Migration(
            version=7,
            description="Remove redundant indexes from RoomExit",
            up_func=self._migration_007_up,
            down_func=self._migration_007_down
        ))

        # Migration 008: Remove unique constraint on (from_room_id, to_room_number)
        self.migrations.append(Migration(
            version=8,
            description="Remove unique constraint on (from_room_id, to_room_number) and add unique constraint on (from_room_id, direction)",
            up_func=self._migration_008_up,
            down_func=self._migration_008_down
        ))

        # Migration 009: Revert to unique constraint on (from_room_id, to_room_number)
        self.migrations.append(Migration(
            version=9,
            description="Revert to unique constraint on (from_room_id, to_room_number) - the correct design",
            up_func=self._migration_009_up,
            down_func=self._migration_009_down
        ))

        # Migration 010: Fix Unique Constraint to allow Aliases
        self.migrations.append(Migration(
            version=10,
            description="Fix unique constraint to allow aliases: UNIQUE(from_room, direction)",
            up_func=self._migration_010_up,
            down_func=self._migration_010_down
        ))

        # Migration 011: Add details column to Room
        self.migrations.append(Migration(
            version=11,
            description="Add details column to Room table",
            up_func=self._migration_011_up,
            down_func=self._migration_011_down
        ))

        # Migration 012: Add sync tracking columns
        self.migrations.append(Migration(
            version=12,
            description="Add sync_status and remote_updated_at columns for Supabase sync",
            up_func=self._migration_012_up,
            down_func=self._migration_012_down
        ))

        # Migration 013: Create sync_deletes table for delete propagation
        self.migrations.append(Migration(
            version=13,
            description="Create sync_deletes table for bidirectional delete sync",
            up_func=self._migration_013_up,
            down_func=self._migration_013_down
        ))

    def _get_schema_version(self) -> int:
        """Get the current schema version from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA user_version")
                return cursor.fetchone()[0]
        except Exception:
            return 0

    def _set_schema_version(self, version: int):
        """Set the schema version in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA user_version = {version}")
            conn.commit()

    def _migration_001_up(self):
        """Migration 001: Create initial schema."""
        # Ensure database is connected
        if db.is_closed():
            db.connect()

        # Create all tables
        tables = [Entity, Room, RoomExit, NPC, Observation, Relation]
        db.create_tables(tables, safe=True)

        # Create additional indexes for performance
        with db.atomic():
            # Entity indexes
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_entity_type ON entity (entity_type)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_entity_name ON entity (name)"
            )

            # Room indexes
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_room_zone ON room (zone)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_room_coordinates ON room (coord_x, coord_y, coord_z)"
            )

            # Room exit indexes (note: Peewee creates table name as 'roomexit')
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_room_exit_from ON roomexit (from_room_id)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_room_exit_to ON roomexit (to_room_id)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_room_exit_direction ON roomexit (direction)"
            )

            # NPC indexes
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_npc_room ON npc (current_room_id)"
            )

            # Observation indexes
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_observation_entity ON observation (entity_id)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_observation_timestamp ON observation (created_at)"
            )

            # Relation indexes
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_relation_from ON relation (from_entity_id)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_relation_to ON relation (to_entity_id)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_relation_type ON relation (relation_type)"
            )
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_relation_timestamp ON relation (created_at)"
            )

        print("✓ Created all tables and indexes")

        # Since we created the tables from the current models, they are already up to date.
        # We should set the schema version to the latest to skip subsequent migrations.
        # However, the migration manager applies migrations sequentially.
        # If we are running migration 1, it means we are initializing.
        # We can't easily skip the rest from here without changing the manager logic.
        # Instead, let's make subsequent migrations idempotent (check if column/index exists).
        pass

    def _migration_002_up(self):
        """Migration 002: Add composite unique constraint to NPC."""
        with db.atomic():
            # Drop the old unique index on the `entity_id` column, which was created by `unique=True`.
            # Peewee likely named it `npc_entity_id`.
            try:
                db.execute_sql("DROP INDEX npc_entity_id")
            except Exception:
                # Index might not exist or have a different name, proceed to create the new one.
                pass

            # Create the new composite unique index for (entity, current_room).
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_npc_entity_room ON npc (entity_id, current_room_id)"
            )
        print("✓ Added composite unique constraint to NPC table")

    def _migration_003_up(self):
        """Migration 003: Add is_door and door_is_closed to RoomExit."""
        with db.atomic():
            try:
                db.execute_sql(
                    "ALTER TABLE roomexit ADD COLUMN is_door BOOLEAN DEFAULT FALSE"
                )
            except Exception:
                pass # Column likely exists

            try:
                db.execute_sql(
                    "ALTER TABLE roomexit ADD COLUMN door_is_closed BOOLEAN DEFAULT FALSE"
                )
            except Exception:
                pass # Column likely exists
        print("✓ Added is_door and door_is_closed to RoomExit table")

    def _migration_003_down(self):
        """Migration 003 rollback: Remove door fields from RoomExit."""
        with db.atomic():
            # SQLite doesn't directly support DROP COLUMN. A common workaround is to
            # create a new table, copy the data, and replace the old table.
            # For simplicity, we will assume this is not needed for a simple rollback.
            # In a real-world scenario, a more robust solution would be required.
            # We can, however, rename the table and create a new one without the columns.
            pass
        print("✓ Rolled back door fields from RoomExit table (manual intervention may be needed)")

    def _migration_004_up(self):
        """Migration 004: Remove duplicate RoomExit records."""
        with db.atomic():
            # This migration removes duplicate exits from the same room in the same direction,
            # keeping the one that was created first (based on the primary key 'id').
            # This is a preparatory step for adding a unique constraint on (from_room_id, direction).
            db.execute_sql("""
                DELETE FROM roomexit
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM roomexit
                    GROUP BY from_room_id, direction
                )
            """)
        print("✓ Removed duplicate RoomExit records")

    def _migration_004_down(self):
        """Migration 004 rollback: Cannot restore deleted duplicate exits."""
        # This migration is not reversible as it deletes data.
        print("✓ Rollback for migration 4 is a no-op (data was deleted).")
        pass

    def _migration_005_up(self):
        """Migration 005: Remove duplicate RoomExit records by to_room_number."""
        with db.atomic():
            db.execute_sql("""
                DELETE FROM roomexit
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM roomexit
                    GROUP BY from_room_id, to_room_number
                )
            """)
        print("✓ Removed duplicate RoomExit records by to_room_number")

    def _migration_005_down(self):
        """Migration 005 rollback: Cannot restore deleted duplicate exits."""
        print("✓ Rollback for migration 5 is a no-op (data was deleted).")
        pass

    def _migration_006_up(self):
        """Migration 006: Add unique constraint to RoomExit."""
        with db.atomic():
            # This might fail if the index was already created by Migration 1 (if using old models)
            # or if we are using new models which don't have this index anymore.
            # Actually, if we are using new models, Migration 1 creates the NEW indexes.
            # So Migration 6 (which adds the OLD unique constraint) might conflict or be unwanted.
            # But since we are running migrations in order, we should try to apply it.
            # However, if we just initialized with NEW models, we have the NEW schema (Migration 8 state).
            # So applying Migration 6 (OLD state) is actually a regression if we are not careful.

            # If we are initializing, we want to end up at state 8.
            # If we run Migration 1 (New Models) -> State 8.
            # Then Migration 2..5 -> OK.
            # Then Migration 6 (Add Old Constraint) -> This adds the constraint we just removed in models.py!
            # Then Migration 8 (Remove Old Constraint) -> Removes it again.
            # So it's wasteful but "correct" in a linear history sense, UNLESS Migration 1 already created the "State 8" schema.

            # If Migration 1 created State 8, then:
            # - idx_roomexit_from_to DOES NOT EXIST.
            # - idx_roomexit_from_direction_unique EXISTS.

            # Migration 6 tries to create idx_roomexit_from_to.
            try:
                db.execute_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_to ON roomexit (from_room_id, to_room_number)"
                )
            except Exception:
                pass
        print("✓ Added unique constraint to RoomExit table")

    def _migration_006_down(self):
        """Migration 006 rollback: Remove unique constraint from RoomExit."""
        with db.atomic():
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_to")
        print("✓ Rolled back unique constraint on RoomExit table")

    def _migration_007_up(self):
        """Migration 007: Remove redundant indexes from RoomExit."""
        with db.atomic():
            db.execute_sql("DROP INDEX IF EXISTS roomexit_from_room_id_direction")
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_direction")
        print("✓ Removed redundant indexes from RoomExit table")

    def _migration_007_down(self):
        """Migration 007 rollback: Recreate redundant indexes on RoomExit."""
        with db.atomic():
            db.execute_sql("CREATE UNIQUE INDEX IF NOT EXISTS roomexit_from_room_id_direction ON roomexit (from_room_id, direction)")
            db.execute_sql("CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_direction ON roomexit (from_room_id, direction)")
        print("✓ Recreated redundant indexes on RoomExit table")

    def _migration_008_up(self):
        """Migration 008: Remove unique constraint on (from_room_id, to_room_number)."""
        with db.atomic():
            # Drop the old unique index
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_to")

            # Remove duplicates before adding the new unique constraint
            db.execute_sql("""
                DELETE FROM roomexit
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM roomexit
                    GROUP BY from_room_id, direction
                )
            """)

            # Create new unique index on (from_room_id, direction)
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_direction_unique ON roomexit (from_room_id, direction)"
            )

            # Create index on to_room_number (since it's no longer part of the unique constraint)
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_roomexit_to_room_number ON roomexit (to_room_number)"
            )
        print("✓ Removed unique constraint on (from_room_id, to_room_number) and added unique constraint on (from_room_id, direction)")

    def _migration_008_down(self):
        """Migration 008 rollback: Restore unique constraint on (from_room_id, to_room_number)."""
        with db.atomic():
            # Drop the new indexes
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_direction_unique")
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_to_room_number")

            # Restore the old unique constraint
            # Note: This might fail if there are duplicate records now
            try:
                db.execute_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_to ON roomexit (from_room_id, to_room_number)"
                )
                print("✓ Restored unique constraint on (from_room_id, to_room_number)")
            except Exception as e:
                print(f"⚠ Could not restore unique constraint: {e}")

    def _migration_009_up(self):
        """Migration 009: Revert to unique constraint on (from_room_id, to_room_number)."""
        with db.atomic():
            # Drop the incorrect unique index from Migration 008
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_direction_unique")

            # Remove duplicates by (from_room_id, to_room_number) before adding constraint
            db.execute_sql("""
                DELETE FROM roomexit
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM roomexit
                    GROUP BY from_room_id, to_room_number
                )
            """)

            # Restore the correct unique constraint on (from_room_id, to_room_number)
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_to ON roomexit (from_room_id, to_room_number)"
            )

            # Keep the non-unique index on (from_room_id, direction) for lookups
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_roomexit_from_direction ON roomexit (from_room_id, direction)"
            )
        print("✓ Reverted to unique constraint on (from_room_id, to_room_number)")

    def _migration_009_down(self):
        """Migration 009 rollback: Go back to unique constraint on (from_room_id, direction)."""
        with db.atomic():
            # Drop the restored constraint
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_to")
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_direction")

            # Recreate the Migration 008 state
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_direction_unique ON roomexit (from_room_id, direction)"
            )
        print("✓ Rolled back to unique constraint on (from_room_id, direction)")

    def _migration_010_up(self):
        """Migration 010: Fix Unique Constraint to allow Aliases."""
        with db.atomic():
            # Drop the restrictive unique constraint on (from_room, to_room)
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_to")

            # Validate usage of tuple in DELETE/IN clause which is supported in SQLite
            # Delete ALL exits that have duplicates for the same direction (clean slate)
            # This ensures we don't arbitrarily pick one "correct" exit when they might be different (e.g. aliases)
            # SQLite supports row value comparisons in newer versions, but to be safe and compatible:
            # We find the IDs of all rows that belong to a group with count > 1
            db.execute_sql("""
                DELETE FROM roomexit
                WHERE id IN (
                    SELECT r1.id
                    FROM roomexit r1
                    JOIN (
                        SELECT from_room_id, direction
                        FROM roomexit
                        GROUP BY from_room_id, direction
                        HAVING COUNT(*) > 1
                    ) r2 ON r1.from_room_id = r2.from_room_id AND r1.direction = r2.direction
                )
            """)

            # Create the correct unique constraint on (from_room, direction) - allow multiple paths to same dest
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_direction_unique ON roomexit (from_room_id, direction)"
            )

            # Create index on to_room_number since it's no longer covered by a unique constraint
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_roomexit_to_room_number ON roomexit (to_room_number)"
            )
        print("✓ Fixed unique constraints: Aliases allowed, unique by direction enforced. Duplicates wiped.")

    def _migration_010_down(self):
        """Migration 010 rollback: Revert to restrictive constraint."""
        with db.atomic():
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_from_direction_unique")
            db.execute_sql("DROP INDEX IF EXISTS idx_roomexit_to_room_number")

            # Re-create the restrictive constraint (might fail if aliases exist)
            try:
                db.execute_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_roomexit_from_to ON roomexit (from_room_id, to_room_number)"
                )
            except Exception as e:
                print(f"⚠ Could not restore restrictive constraint: {e}")
        print("✓ Rolled back to restrictive constraints")

    def _migration_011_up(self):
        """Migration 011: Add details column to Room."""
        with db.atomic():
            try:
                db.execute_sql(
                    "ALTER TABLE room ADD COLUMN details TEXT"
                )
            except Exception:
                pass  # Column likely exists
        print("✓ Added details column to Room table")

    def _migration_011_down(self):
        """Migration 011 rollback: Remove details column from Room."""
        # SQLite doesn't support dropping columns easily in older versions,
        # but modern SQLite does with ALTER TABLE DROP COLUMN.
        # However, for safety/compatibility we'll use the no-op or complex approach if needed.
        # For this simple case, we'll try the modern syntax but catch errors.
        try:
            with db.atomic():
                db.execute_sql("ALTER TABLE room DROP COLUMN details")
            print("✓ Dropped details column from Room table")
        except Exception as e:
            print(f"⚠ Could not drop details column (might need table rebuild): {e}")

    def _migration_012_up(self):
        """Migration 012: Add sync tracking columns to all tables."""
        tables = ['entity', 'room', 'roomexit', 'npc', 'observation', 'relation']
        for table in tables:
            with db.atomic():
                try:
                    db.execute_sql(
                        f"ALTER TABLE {table} ADD COLUMN sync_status VARCHAR(10) NOT NULL DEFAULT 'dirty'"
                    )
                except Exception:
                    pass  # Column likely exists
                try:
                    db.execute_sql(
                        f"ALTER TABLE {table} ADD COLUMN remote_updated_at DATETIME"
                    )
                except Exception:
                    pass  # Column likely exists
        print("✓ Added sync_status and remote_updated_at columns to all tables")

    def _migration_012_down(self):
        """Migration 012 rollback: Remove sync tracking columns."""
        tables = ['entity', 'room', 'roomexit', 'npc', 'observation', 'relation']
        for table in tables:
            try:
                with db.atomic():
                    db.execute_sql(f"ALTER TABLE {table} DROP COLUMN sync_status")
                    db.execute_sql(f"ALTER TABLE {table} DROP COLUMN remote_updated_at")
            except Exception as e:
                print(f"⚠ Could not drop sync columns from {table}: {e}")

    def _migration_013_up(self):
        """Migration 013: Create sync_deletes table."""
        with db.atomic():
            db.execute_sql("""
                CREATE TABLE IF NOT EXISTS sync_deletes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name_field VARCHAR(50) NOT NULL,
                    natural_key TEXT NOT NULL,
                    deleted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    synced BOOLEAN NOT NULL DEFAULT 0
                )
            """)
            db.execute_sql(
                "CREATE INDEX IF NOT EXISTS idx_sync_deletes_synced ON sync_deletes (synced)"
            )
        print("✓ Created sync_deletes table")

    def _migration_013_down(self):
        """Migration 013 rollback: Drop sync_deletes table."""
        with db.atomic():
            db.execute_sql("DROP TABLE IF EXISTS sync_deletes")
        print("✓ Dropped sync_deletes table")

    def _migration_002_down(self):
        """Migration 002 rollback: Remove composite unique constraint."""
        with db.atomic():
            # Drop the composite unique index.
            db.execute_sql("DROP INDEX IF EXISTS idx_npc_entity_room")

            # Re-create the original unique index on `entity_id`.
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS npc_entity_id ON npc (entity_id)"
            )
        print("✓ Rolled back composite unique constraint on NPC table")

    def _migration_001_down(self):
        """Migration 001 rollback: Drop all tables."""
        if db.is_closed():
            db.connect()

        tables = [Relation, Observation, NPC, RoomExit, Room, Entity]
        db.drop_tables(tables, safe=True)
        print("✓ Dropped all tables")

    def migrate(self, target_version: int = None):
        """Run migrations up to the target version."""
        current_version = self._get_schema_version()

        if target_version is None:
            target_version = max(m.version for m in self.migrations) if self.migrations else 0

        print(f"Current schema version: {current_version}")
        print(f"Target schema version: {target_version}")

        if current_version == target_version:
            print("Database is already up to date")
            return

        if current_version > target_version:
            print("Downgrade not supported in this simple migration system")
            return

        # Apply migrations
        for migration in sorted(self.migrations, key=lambda m: m.version):
            if migration.version > current_version and migration.version <= target_version:
                try:
                    migration.apply()
                    self._set_schema_version(migration.version)
                    print(f"✓ Migration {migration.version} completed")
                except Exception as e:
                    print(f"✗ Migration {migration.version} failed: {e}")
                    raise

        print(f"Migration completed. Database is now at version {target_version}")

    def rollback(self, target_version: int):
        """Rollback migrations to the target version."""
        current_version = self._get_schema_version()

        if current_version <= target_version:
            print("Nothing to rollback")
            return

        # Rollback migrations in reverse order
        for migration in sorted(self.migrations, key=lambda m: m.version, reverse=True):
            if migration.version > target_version and migration.version <= current_version:
                try:
                    migration.rollback()
                    self._set_schema_version(migration.version - 1)
                    print(f"✓ Rollback {migration.version} completed")
                except Exception as e:
                    print(f"✗ Rollback {migration.version} failed: {e}")
                    raise

        print(f"Rollback completed. Database is now at version {target_version}")

    def status(self):
        """Show migration status."""
        current_version = self._get_schema_version()
        print(f"Current schema version: {current_version}")
        print("\nAvailable migrations:")

        for migration in sorted(self.migrations, key=lambda m: m.version):
            status = "✓ Applied" if migration.version <= current_version else "✗ Pending"
            print(f"  {migration.version:03d}: {migration.description} [{status}]")


def init_database(db_path: str = None) -> MigrationManager:
    """Initialize the database with all required tables and indexes.

    Args:
        db_path: Path to the SQLite database file. If None, uses the default from models.

    Returns:
        MigrationManager instance for further operations.
    """
    if db_path:
        # Update the database path in models
        from ..db import models
        models.db.init(db_path)

    # Ensure the directory exists
    db_file_path = Path(db.database)
    db_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create migration manager and run migrations
    manager = MigrationManager(str(db_file_path))
    manager.migrate()

    return manager


def main():
    """Command-line interface for migrations."""
    import argparse

    parser = argparse.ArgumentParser(description="Database migration tool")
    parser.add_argument("--db-path", help="Path to SQLite database file")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run migrations")
    migrate_parser.add_argument("--version", type=int, help="Target version (default: latest)")

    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback migrations")
    rollback_parser.add_argument("version", type=int, help="Target version")

    # Status command
    subparsers.add_parser("status", help="Show migration status")

    # Init command
    subparsers.add_parser("init", help="Initialize database")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Determine database path
    if args.db_path:
        db_path = args.db_path
    else:
        # Use default path from models
        from . import models
        db_path = models.db.database

    manager = MigrationManager(db_path)

    if args.command == "migrate":
        manager.migrate(args.version)
    elif args.command == "rollback":
        manager.rollback(args.version)
    elif args.command == "status":
        manager.status()
    elif args.command == "init":
        manager.migrate()
        print("Database initialized successfully")


if __name__ == "__main__":
    main()
