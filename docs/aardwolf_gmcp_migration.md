# Aardwolf GMCP Manager Migration Guide

This guide explains how to migrate from the old monolithic `AardwolfGMCPManager` to the new component-based `AardwolfGMCPManager`.

## Overview

The `AardwolfGMCPManager` has been refactored to use a component-based architecture, which provides several benefits:

- **Modularity**: Each component is responsible for a specific aspect of GMCP data processing
- **Maintainability**: Smaller, focused components are easier to understand and maintain
- **Testability**: Components can be tested in isolation
- **Extensibility**: New components can be added without modifying existing code

The refactored `AardwolfGMCPManager` uses composition to delegate functionality to specialized processors:

- `CharacterDataProcessor`: Processes character-related GMCP data
- `RoomDataProcessor`: Processes room-related GMCP data
- `MapDataProcessor`: Processes map-related GMCP data
- `QuestDataProcessor`: Processes quest-related GMCP data

## Backward Compatibility

The refactored `AardwolfGMCPManager` maintains backward compatibility through:

1. **Method delegation**: All public methods from the old `AardwolfGMCPManager` are available and delegate to the appropriate processor
2. **Data structure compatibility**: The data structures returned by the methods are compatible with the old implementation

## Migration Steps

### Step 1: Update Imports

If you're importing directly from `aardwolf_gmcp.py`, update your imports:

```python
# Old import
from mud_agent.protocols.aardwolf_gmcp import AardwolfGMCPManager

# New import
from mud_agent.protocols.aardwolf import AardwolfGMCPManager
```

### Step 2: Update Direct Attribute Access

If you're accessing attributes directly, consider using the getter methods instead:

```python
# Old approach (direct attribute access)
char_data = gmcp_manager.char_data
room_data = gmcp_manager.room_data

# New approach (getter methods)
char_data = gmcp_manager.get_character_data()
room_data = gmcp_manager.get_room_info()
```

### Step 3: Access Processor-Specific Functionality

If you need to access processor-specific functionality, use the processor directly:

```python
# Access character processor
char_data = gmcp_manager.character_processor.get_character_data()

# Access room processor
room_data = gmcp_manager.room_processor.get_room_info()

# Access map processor
map_data = gmcp_manager.map_processor.get_map_data()
```

## Method Reference

The following methods are available on the `AardwolfGMCPManager` class:

### Core Methods

- `initialize()`: Initialize GMCP support for Aardwolf
- `update_from_gmcp()`: Update all data from GMCP
- `is_data_fresh(module, max_age=5.0)`: Check if data for a module is fresh

### Character Data Methods

- `get_character_data()`: Get comprehensive character data from GMCP
- `get_all_character_data()`: Get all character data in a single call

### Room Data Methods

- `get_room_info()`: Get room information from GMCP data
- `get_exits()`: Get available exits from the current room
- `get_room_name()`: Get the name of the current room
- `get_area_name()`: Get the name of the current area
- `get_room_coords()`: Get the coordinates of the current room

### Map Data Methods

- `get_map_data()`: Get map data from GMCP

### GMCP Command Methods

- `send_gmcp_command(command, args=None)`: Send a GMCP command to the server
- `request_gmcp_data(data_type)`: Request specific GMCP data from the server
- `toggle_gmcp_option(option, enable=True)`: Toggle a GMCP option in Aardwolf
- `get_gmcp_status()`: Get the status of GMCP options in Aardwolf

## Extending the GMCP Manager

To add new functionality to the `AardwolfGMCPManager`, create a new processor:

1. Create a new processor class
2. Implement the required methods
3. Add an instance of your processor to the `AardwolfGMCPManager`

Example:

```python
class MyCustomProcessor:
    def __init__(self, gmcp_manager):
        self.gmcp_manager = gmcp_manager
        self.logger = logging.getLogger(__name__)

    def process_data(self, data):
        # Process the data
        pass

    def get_custom_data(self):
        # Return the processed data
        pass

# Add your processor to the GMCP manager
gmcp_manager.custom_processor = MyCustomProcessor(gmcp_manager)
```

## Conclusion

The refactored `AardwolfGMCPManager` provides a more modular and maintainable architecture while maintaining backward compatibility. By using the component-based approach, you can create more robust and flexible code that is easier to test and extend.
