#!/usr/bin/env python3
"""
Database migration system for the MUD Agent knowledge graph.

This module provides a simple migration system to manage schema changes
for the SQLite database using Peewee ORM models.
"""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from peewee import CharField, DateTimeField

from .models import NPC, Entity, Observation, Relation, Room, RoomExit, db

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""

    def __init__(self, version: int, description: str, up_func: Callable, down_func: Callable = None):
        self.version = version
        self.description = description
        self.up_func = up_func
        self.down_func = down_func

    def apply(self):
        """Apply the migration."""
        logger.info(f"Applying migration {self.version}: {self.description}")
        self.up_func()

    def rollback(self):
        """Rollback the migration."""
        if self.down_func:
            logger.info(f"Rolling back migration {self.version}: {self.description}")
            self.down_func()
        else:
            logger.warning(f"No rollback available for migration {self.version}")


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

        # Migration 002: Add sync tracking columns
        self.migrations.append(Migration(
            version=2,
            description="Add sync_status and remote_updated_at columns for Supabase sync",
            up_func=self._migration_002_up,
            down_func=self._migration_002_down
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

        logger.info("Migration 001: Created all tables and indexes")

    def _migration_001_down(self):
        """Migration 001 rollback: Drop all tables."""
        if db.is_closed():
            db.connect()

        tables = [Relation, Observation, NPC, RoomExit, Room, Entity]
        db.drop_tables(tables, safe=True)
        print("✓ Dropped all tables")

    def _migration_002_up(self):
        """Add sync tracking columns to all models."""
        from playhouse.migrate import SqliteMigrator, migrate
        migrator = SqliteMigrator(db)

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
                if "duplicate column" in str(e).lower():
                    logger.debug(f"Migration 002: Columns already exist on {table}")
                else:
                    raise

    def _migration_002_down(self):
        """Remove sync tracking columns."""
        from playhouse.migrate import SqliteMigrator, migrate
        migrator = SqliteMigrator(db)

        tables_to_update = ['entity', 'room', 'roomexit', 'npc', 'observation', 'relation']
        for table in tables_to_update:
            try:
                migrate(
                    migrator.drop_column(table, 'sync_status'),
                    migrator.drop_column(table, 'remote_updated_at'),
                )
            except Exception:
                pass

    def migrate(self, target_version: int = None):
        """Run migrations up to the target version."""
        current_version = self._get_schema_version()

        if target_version is None:
            target_version = max(m.version for m in self.migrations) if self.migrations else 0

        logger.info(f"Current schema version: {current_version}")
        logger.info(f"Target schema version: {target_version}")

        if current_version == target_version:
            logger.info("Database is already up to date")
            return

        if current_version > target_version:
            # Legacy DB from old migration system (which used versions up to 13).
            # Reset to 0 and re-run all migrations; they are idempotent.
            logger.warning(
                f"Schema version {current_version} exceeds max migration version "
                f"{target_version} — assuming legacy database, re-running all migrations"
            )
            current_version = 0
            self._set_schema_version(0)

        # Apply migrations
        for migration in sorted(self.migrations, key=lambda m: m.version):
            if migration.version > current_version and migration.version <= target_version:
                try:
                    migration.apply()
                    self._set_schema_version(migration.version)
                    logger.info(f"Migration {migration.version} completed")
                except Exception as e:
                    logger.error(f"Migration {migration.version} failed: {e}")
                    raise

        logger.info(f"Migration completed. Database is now at version {target_version}")

    def rollback(self, target_version: int):
        """Rollback migrations to the target version."""
        current_version = self._get_schema_version()

        if current_version <= target_version:
            logger.info("Nothing to rollback")
            return

        # Rollback migrations in reverse order
        for migration in sorted(self.migrations, key=lambda m: m.version, reverse=True):
            if migration.version > target_version and migration.version <= current_version:
                try:
                    migration.rollback()
                    self._set_schema_version(migration.version - 1)
                    logger.info(f"Rollback {migration.version} completed")
                except Exception as e:
                    logger.error(f"Rollback {migration.version} failed: {e}")
                    raise

        logger.info(f"Rollback completed. Database is now at version {target_version}")

    def status(self):
        """Show migration status."""
        current_version = self._get_schema_version()
        logger.info(f"Current schema version: {current_version}")

        for migration in sorted(self.migrations, key=lambda m: m.version):
            status = "Applied" if migration.version <= current_version else "Pending"
            logger.info(f"  {migration.version:03d}: {migration.description} [{status}]")


def init_database(db_path: str = None) -> MigrationManager:
    """Initialize the database with all required tables and indexes.
    
    Args:
        db_path: Path to the SQLite database file. If None, uses the default from models.
    
    Returns:
        MigrationManager instance for further operations.
    """
    if db_path:
        # Update the database path in models
        from . import models
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
