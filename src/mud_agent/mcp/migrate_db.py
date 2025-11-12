#!/usr/bin/env python3
"""
Simple database migration runner for the MUD Agent knowledge graph.

This script provides an easy way to initialize and migrate the SQLite database.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from mud_agent.mcp.migrations import init_database, MigrationManager


class DatabaseMigrator:
    """Main entry point for database migration."""
    print("MUD Agent Knowledge Graph Database Migration")
    print("=" * 50)
    
    # Default database path (same as in models.py)
    default_db_path = project_root / ".mcp" / "knowledge_graph.db"
    
    # Check if user wants to specify a custom path
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        db_path = default_db_path
    
    print(f"Database path: {db_path}")
    
    # Check if database already exists
    if db_path.exists():
        print("Database file already exists.")
        manager = MigrationManager(str(db_path))
        manager.status()
        
        response = input("\nDo you want to run migrations? (y/N): ")
        if response.lower() in ['y', 'yes']:
            manager.migrate()
        else:
            print("Migration cancelled.")
    else:
        print("Database file does not exist. Creating new database...")
        try:
            manager = init_database(str(db_path))
            print("\n✓ Database initialized successfully!")
            print(f"\nDatabase created at: {db_path}")
            print("\nYou can now use the Peewee models to interact with the knowledge graph.")
            
            # Show final status
            print("\nFinal migration status:")
            manager.status()
            
        except Exception as e:
            print(f"\n✗ Error initializing database: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()