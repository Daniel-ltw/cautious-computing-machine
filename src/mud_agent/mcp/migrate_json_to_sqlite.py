#!/usr/bin/env python3
"""
Data migration script to transfer data from game.json to SQLite database.

This script imports all entities, relations, and observations from the existing
JSON knowledge graph into the new SQLite database using Peewee ORM models.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from mud_agent.db.models import NPC, Entity, Observation, Relation, Room, RoomExit, db
from mud_agent.mcp.migrations import init_database
from mud_agent.mcp.models import (
    NPC,
    Entity,
    Observation,
    Relation,
    Room,
    RoomExit,
    db,  # Import the db instance
)

# Define the path to the JSON file and the SQLite database

class JSONToSQLiteMigrator:
    """Handles migration from JSON knowledge graph to SQLite database."""

    def __init__(self, json_file_path: str, db_path: str):
        self.json_file_path = Path(json_file_path)
        self.db_path = Path(db_path)
        self.stats = {
            'entities_created': 0,
            'rooms_created': 0,
            'npcs_created': 0,
            'exits_created': 0,
            'observations_created': 0,
            'relations_created': 0,
            'errors': []
        }
        self.entity_id_map = {}  # Maps JSON entity IDs to SQLite entity IDs

    def load_json_data(self) -> dict[str, Any]:
        """Load and parse the JSON knowledge graph file."""
        print(f"Loading JSON data from {self.json_file_path}...")

        if not self.json_file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {self.json_file_path}")

        with open(self.json_file_path, encoding='utf-8') as f:
            data = json.load(f)

        print(f"Loaded {len(data.get('entities', {}))} entities and {len(data.get('relations', []))} relations")
        return data

    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object."""
        try:
            # Handle various timestamp formats
            if '.' in timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(timestamp_str + '+00:00')
        except Exception:
            # Fallback to current time if parsing fails
            return datetime.now()

    def migrate_entities(self, entities_data: dict[str, Any]) -> None:
        """Migrate all entities from JSON to SQLite."""
        print("\nMigrating entities...")

        for entity_id, entity_data in entities_data.items():
            try:
                self.migrate_single_entity(entity_id, entity_data)
            except Exception as e:
                error_msg = f"Failed to migrate entity {entity_id}: {e}"
                print(f"ERROR: {error_msg}")
                self.stats['errors'].append(error_msg)

        print(f"Entities migration complete: {self.stats['entities_created']} entities created")

    def migrate_single_entity(self, entity_id: str, entity_data: dict[str, Any]) -> None:
        """Migrate a single entity and its associated data."""
        name = entity_data.get('name', f'Entity {entity_id}')
        entity_type = entity_data.get('entityType', 'Unknown')
        metadata = entity_data.get('metadata', {})
        observations = entity_data.get('observations', [])

        # Parse timestamps
        created_at = self.parse_timestamp(metadata.get('last_updated', datetime.now().isoformat()))

        # Create the base entity
        entity = Entity.create(
            name=name,
            entity_type=entity_type,
            created_at=created_at,
            updated_at=created_at
        )

        # Store mapping for relations
        self.entity_id_map[entity_id] = entity.id
        self.stats['entities_created'] += 1

        # Create observations
        for obs_text in observations:
            if obs_text.strip():  # Skip empty observations
                Observation.create(
                    entity=entity,
                    observation_text=obs_text,
                    observation_type='general',
                    created_at=created_at
                )
                self.stats['observations_created'] += 1

        # Handle entity-specific data
        if entity_type == 'Room':
            self.migrate_room_data(entity, entity_id, metadata)
        elif entity_type == 'NPC':
            self.migrate_npc_data(entity, entity_id, metadata)

    def migrate_room_data(self, entity: Entity, room_id: str, metadata: dict[str, Any]) -> None:
        """Migrate room-specific data."""
        try:
            room_number = int(metadata.get('room_number', room_id))
        except (ValueError, TypeError):
            room_number = int(room_id) if room_id.isdigit() else 0

        # Extract room details
        terrain = metadata.get('terrain', 'unknown')
        zone = metadata.get('zone', 'unknown')
        full_name = metadata.get('full_name', entity.name)
        outside = metadata.get('outside', '0') == '1'
        details = metadata.get('details', '')

        # Handle coordinates (if available)
        coord_x = metadata.get('coord_x', 0)
        coord_y = metadata.get('coord_y', 0)
        coord_z = metadata.get('coord_z', 0)

        # Create room record
        room = Room.create(
            entity=entity,
            room_number=room_number,
            terrain=terrain,
            zone=zone,
            full_name=full_name,
            outside=outside,
            coord_x=coord_x,
            coord_y=coord_y,
            coord_z=coord_z
        )

        self.stats['rooms_created'] += 1

        # Create room exits
        exits = metadata.get('exits', [])
        exit_details = metadata.get('exit_details', {})

        for direction in exits:
            if direction in exit_details:
                try:
                    to_room_number = int(exit_details[direction])

                    # Create exit record
                    RoomExit.create(
                        from_room=room,
                        direction=direction,
                        to_room_number=to_room_number,
                        to_room=None,  # Will be linked later
                        details='{}'
                    )

                    self.stats['exits_created'] += 1

                except (ValueError, TypeError) as e:
                    error_msg = f"Invalid exit data for room {room_number}, direction {direction}: {e}"
                    self.stats['errors'].append(error_msg)

        # Handle NPCs in room
        npcs_in_room = metadata.get('npcs', []) + metadata.get('manual_npcs', []) + metadata.get('scan_npcs', [])
        for npc_name in npcs_in_room:
            if npc_name.strip():
                # Create observation about NPC presence
                Observation.create(
                    entity=entity,
                    observation_text=f"NPC present: {npc_name}",
                    observation_type='npc_presence',
                    created_at=entity.created_at
                )
                self.stats['observations_created'] += 1

    def migrate_npc_data(self, entity: Entity, npc_id: str, metadata: dict[str, Any]) -> None:
        """Migrate NPC-specific data."""
        # For NPCs, we might not have room information in the entity data
        # We'll create the NPC record and link it to rooms later if needed
        npc = NPC.create(
            entity=entity,
            current_room=None,  # Will be linked based on observations
            npc_type='unknown'
        )

        self.stats['npcs_created'] += 1

    def link_room_exits(self) -> None:
        """Link room exits to their destination rooms."""
        print("\nLinking room exits...")

        exits_linked = 0
        exits_failed = 0

        for exit in RoomExit.select():
            try:
                # Find the destination room
                dest_room = Room.select().where(Room.room_number == exit.to_room_number).first()
                if dest_room:
                    exit.to_room = dest_room
                    exit.save()
                    exits_linked += 1
                else:
                    exits_failed += 1

            except Exception as e:
                error_msg = f"Failed to link exit {exit.id}: {e}"
                self.stats['errors'].append(error_msg)
                exits_failed += 1

        print(f"Room exits linking complete: {exits_linked} linked, {exits_failed} failed")

    def migrate_relations(self, relations_data: list[dict[str, Any]]) -> None:
        """Migrate relations from JSON to SQLite."""
        print("\nMigrating relations...")

        for relation_data in relations_data:
            try:
                self.migrate_single_relation(relation_data)
            except Exception as e:
                error_msg = f"Failed to migrate relation {relation_data}: {e}"
                print(f"ERROR: {error_msg}")
                self.stats['errors'].append(error_msg)

        print(f"Relations migration complete: {self.stats['relations_created']} relations created")

    def migrate_single_relation(self, relation_data: dict[str, Any]) -> None:
        """Migrate a single relation."""
        from_id = relation_data.get('from')
        to_id = relation_data.get('to')
        relation_type = relation_data.get('relationType', 'unknown')
        timestamp_str = relation_data.get('timestamp', datetime.now().isoformat())

        # Get entity IDs from mapping
        from_entity_id = self.entity_id_map.get(from_id)
        to_entity_id = self.entity_id_map.get(to_id)

        if not from_entity_id or not to_entity_id:
            # Skip relations where entities don't exist
            return

        # Parse timestamp
        created_at = self.parse_timestamp(timestamp_str)

        # Create relation
        Relation.create(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            relation_type=relation_type,
            metadata='{}',
            created_at=created_at
        )

        self.stats['relations_created'] += 1

    def run_migration(self) -> None:
        """Run the complete migration process."""
        print(f"Starting migration from {self.json_file_path} to {self.db_path}")
        print("=" * 60)

        # Initialize database
        print("Initializing SQLite database...")
        init_database(str(self.db_path))

        # Load JSON data
        json_data = self.load_json_data()

        # Initialize database connection
        db.init(str(self.db_path))

        try:
            with DatabaseContext():
                with db.atomic():
                    # Migrate entities first
                    self.migrate_entities(json_data.get('entities', {}))

                    # Link room exits
                    self.link_room_exits()

                    # Migrate relations
                    self.migrate_relations(json_data.get('relations', []))

        except Exception as e:
            print(f"CRITICAL ERROR during migration: {e}")
            raise

        # Print final statistics
        self.print_migration_stats()

    def print_migration_stats(self) -> None:
        """Print migration statistics."""
        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"Entities created: {self.stats['entities_created']}")
        print(f"Rooms created: {self.stats['rooms_created']}")
        print(f"NPCs created: {self.stats['npcs_created']}")
        print(f"Room exits created: {self.stats['exits_created']}")
        print(f"Observations created: {self.stats['observations_created']}")
        print(f"Relations created: {self.stats['relations_created']}")

        if self.stats['errors']:
            print(f"\nErrors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
        else:
            print("\n✅ Migration completed successfully with no errors!")


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate data from game.json to SQLite database"
    )
    parser.add_argument(
        '--json-file',
        default='.mcp/game.json',
        help='Path to the JSON knowledge graph file (default: .mcp/game.json)'
    )
    parser.add_argument(
        '--db-path',
        default='.mcp/knowledge_graph.db',
        help='Path to the SQLite database file (default: .mcp/knowledge_graph.db)'
    )
    parser.add_argument(
        '--backup-existing',
        action='store_true',
        help='Backup existing database before migration'
    )

    args = parser.parse_args()

    # Convert to absolute paths
    json_file = Path(args.json_file).resolve()
    db_path = Path(args.db_path).resolve()

    # Backup existing database if requested
    if args.backup_existing and db_path.exists():
        backup_path = db_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        print(f"Backing up existing database to {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)

    # Run migration
    migrator = JSONToSQLiteMigrator(str(json_file), str(db_path))
    migrator.run_migration()

    print(f"\nDatabase ready at: {db_path}")
    print("You can now use the SQLite knowledge graph system!")


if __name__ == "__main__":
    main()
