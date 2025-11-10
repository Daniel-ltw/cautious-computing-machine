# MUD Agent Knowledge Graph - SQLite Implementation

This directory contains the SQLite-based knowledge graph implementation for the MUD Agent project, providing a robust, scalable alternative to the JSON-based storage system.

## Overview

The SQLite knowledge graph system offers:
- **Performance**: Faster queries and reduced memory usage
- **Scalability**: Handles large datasets efficiently
- **Relationships**: Proper foreign key relationships and joins
- **Indexing**: Optimized queries with strategic indexes
- **Migrations**: Version-controlled schema changes
- **ACID Compliance**: Reliable data integrity

## Architecture

### Core Components

1. **`models.py`** - Peewee ORM models and utility functions
2. **`migrations.py`** - Database schema migration system
3. **`migrate_db.py`** - Command-line migration utility
4. **`test_models.py`** - Comprehensive test suite

### Database Schema

The schema consists of six main tables:

#### Entity Table
- **Purpose**: Central registry of all game entities
- **Fields**: `id`, `name`, `entity_type`, `created_at`, `updated_at`
- **Types**: Room, NPC, Item, Player, etc.

#### Room Table
- **Purpose**: Game room/location data
- **Fields**: `entity_id`, `room_number`, `terrain`, `zone`, `full_name`, `outside`, coordinates
- **Relationships**: Links to Entity table

#### RoomExit Table
- **Purpose**: Connections between rooms
- **Fields**: `from_room`, `direction`, `to_room_number`, `to_room`, `details`
- **Relationships**: Links rooms together for navigation

#### NPC Table
- **Purpose**: Non-player character data
- **Fields**: `entity_id`, `current_room`, `npc_type`
- **Relationships**: Links to Entity and Room tables

#### Observation Table
- **Purpose**: Historical observations and descriptions
- **Fields**: `entity_id`, `observation_text`, `observation_type`, `created_at`
- **Use Cases**: Room descriptions, NPC behaviors, item details

#### Relation Table
- **Purpose**: Generic relationships between entities
- **Fields**: `from_entity`, `to_entity`, `relation_type`, `metadata`, `created_at`
- **Examples**: "contains", "near", "hostile_to", "owns"

## Getting Started

### 1. Initialize the Database

```bash
# Initialize a new database with default path
python3 src/mud_agent/mcp/migrate_db.py

# Or specify a custom path
python3 src/mud_agent/mcp/migrate_db.py --db-path /path/to/your/database.db
```

### 2. Run Tests

```bash
# Run the comprehensive test suite
python3 src/mud_agent/mcp/test_models.py
```

### 3. Basic Usage

```python
from src.mud_agent.mcp.models import (
    db, Entity, Room, RoomExit, NPC, Observation, Relation,
    get_room_by_number, get_entity_by_name, DatabaseContext
)

# Initialize database connection
db.init('/path/to/knowledge_graph.db')

# Use context manager for operations
with DatabaseContext():
    # Create an entity
    room_entity = Entity.create(
        name="Temple Entrance",
        entity_type="Room"
    )
    
    # Create a room
    room = Room.create(
        entity=room_entity,
        room_number=3001,
        terrain="inside",
        zone="Temple",
        full_name="The Grand Temple Entrance",
        outside=False,
        coord_x=100,
        coord_y=200,
        coord_z=0
    )
    
    # Query utilities
    found_room = get_room_by_number(3001)
    found_entity = get_entity_by_name("Temple Entrance", "Room")
```

## Migration System

### Migration Commands

```bash
# Check migration status
python3 src/mud_agent/mcp/migrations.py status

# Apply all pending migrations
python3 src/mud_agent/mcp/migrations.py migrate

# Rollback to specific version
python3 src/mud_agent/mcp/migrations.py rollback 0

# Initialize new database
python3 src/mud_agent/mcp/migrations.py init
```

### Creating New Migrations

1. Add your migration functions to `migrations.py`:

```python
def _migration_002_up(db):
    """Add new feature."""
    # Your migration code here
    pass

def _migration_002_down(db):
    """Rollback new feature."""
    # Your rollback code here
    pass
```

2. Register the migration in the `MIGRATIONS` list:

```python
MIGRATIONS = [
    Migration(1, "Create initial schema", _migration_001_up, _migration_001_down),
    Migration(2, "Add new feature", _migration_002_up, _migration_002_down),
]
```

## Utility Functions

### Database Operations

```python
# Get database statistics
stats = get_database_stats()
print(f"Total entities: {stats['Entity']}")

# Find rooms
room = get_room_by_number(1001)
rooms_in_zone = Room.select().where(Room.zone == "Temple")

# Find paths between rooms
path = find_path_between_rooms(1001, 1002)
print(f"Path: {' -> '.join(path)}")

# Get room exits
exits = get_room_exits(1001)
for exit in exits:
    print(f"{exit.direction} -> Room {exit.to_room_number}")
```

### Entity Management

```python
# Create relationships
relation = Relation.create(
    from_entity=room_entity,
    to_entity=npc_entity,
    relation_type="contains",
    metadata='{"visible": true, "permanent": false}'
)

# Add observations
observation = Observation.create(
    entity=room_entity,
    observation_text="A grand entrance with marble columns",
    observation_type="description"
)
```

## Performance Considerations

### Indexes

The system includes strategic indexes for common queries:
- Entity type and name lookups
- Room number searches
- Exit direction and room relationships
- Observation and relation timestamps

### Query Optimization

```python
# Efficient room queries
rooms = Room.select().where(Room.zone == "Temple").order_by(Room.room_number)

# Batch operations
with db.atomic():
    for room_data in room_list:
        Room.create(**room_data)

# Prefetch related data
rooms_with_entities = Room.select().join(Entity)
```

## Migration from JSON System

### Migration Strategy

1. **Parallel Implementation**: Run both systems side-by-side initially
2. **Data Import**: Create scripts to import existing JSON data
3. **Gradual Transition**: Move components one at a time
4. **Validation**: Compare results between systems
5. **Cutover**: Switch to SQLite as primary system

### Data Import Example

```python
import json
from src.mud_agent.mcp.models import Entity, Room, DatabaseContext

def import_json_data(json_file_path):
    """Import data from existing JSON knowledge graph."""
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    with DatabaseContext():
        with db.atomic():
            # Import entities
            for entity_data in data.get('entities', []):
                Entity.create(
                    name=entity_data['name'],
                    entity_type=entity_data['type']
                )
            
            # Import rooms
            for room_data in data.get('rooms', []):
                entity = Entity.get(Entity.name == room_data['name'])
                Room.create(
                    entity=entity,
                    room_number=room_data['number'],
                    # ... other fields
                )
```

## Best Practices

### Database Connections

- Always use `DatabaseContext()` for operations
- Close connections when done
- Use `db.atomic()` for batch operations

### Error Handling

```python
try:
    with DatabaseContext():
        # Your database operations
        pass
except Exception as e:
    logger.error(f"Database operation failed: {e}")
    # Handle error appropriately
```

### Performance

- Use indexes for frequently queried fields
- Batch operations when possible
- Avoid N+1 query problems with proper joins
- Monitor query performance with `EXPLAIN QUERY PLAN`

## Troubleshooting

### Common Issues

1. **Connection Errors**: Ensure database file permissions are correct
2. **Migration Failures**: Check migration logs and rollback if needed
3. **Performance Issues**: Review query patterns and indexes
4. **Data Integrity**: Use foreign key constraints and validation

### Debugging

```python
# Enable SQL logging
import logging
logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# Check query plans
cursor = db.execute_sql("EXPLAIN QUERY PLAN SELECT * FROM room WHERE room_number = ?")
print(cursor.fetchall())
```

## Future Enhancements

- **Full-text search** for observations and descriptions
- **Spatial indexing** for coordinate-based queries
- **Caching layer** for frequently accessed data
- **Backup and replication** strategies
- **API endpoints** for external access
- **Real-time synchronization** with game events

## Contributing

When adding new features:
1. Create appropriate migrations
2. Add comprehensive tests
3. Update documentation
4. Consider performance implications
5. Maintain backward compatibility

---

*This SQLite implementation provides a solid foundation for the MUD Agent's knowledge graph, offering improved performance, scalability, and maintainability over the previous JSON-based system.*