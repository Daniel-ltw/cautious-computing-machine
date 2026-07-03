# MUDAgent Migration Guide

This guide explains how to migrate from the old monolithic `MUDAgent` to the new component-based `MUDAgent`.

## Overview

The `MUDAgent` has been refactored to use a component-based architecture, which provides several benefits:

- **Modularity**: Each component is responsible for a specific aspect of agent functionality
- **Maintainability**: Smaller, focused components are easier to understand and maintain
- **Testability**: Components can be tested in isolation
- **Extensibility**: New components can be added without modifying existing code

The refactored `MUDAgent` uses composition to delegate functionality to specialized components:

- `ConnectionComponent`: Manages the connection to the MUD server
- `CommandComponent`: Processes commands sent to the MUD server

## Backward Compatibility

The refactored `MUDAgent` maintains backward compatibility through:

1. **Method delegation**: All public methods from the old `MUDAgent` are available and delegate to the appropriate component
2. **Manager references**: All managers are still available as properties on the `MUDAgent` class

## Migration Steps

### Step 1: Update Imports

If you're importing directly from `mud_agent.py`, update your imports:

```python
# Old import
from mud_agent.agent.mud_agent import MUDAgent

# New import
from mud_agent.agent.mud_agent import MUDAgent
```

### Step 2: Update Direct Attribute Access

If you're accessing attributes directly, consider using the getter methods instead:

```python
# Old approach (direct attribute access)
last_command = agent.last_command
last_response = agent.last_response

# New approach (getter methods)
last_command = agent.command.last_command
last_response = agent.command.last_response
```

### Step 3: Access Component-Specific Functionality

If you need to access component-specific functionality, use the component directly:

```python
# Access connection component
await agent.connection.connect_to_mud()

# Access command component
await agent.command.process_command("look")
```

## Method Reference

The following methods are available on the `MUDAgent` class:

### Connection Methods

- `connect_to_mud()`: Connect to the MUD server
- `login(character_name, password)`: Login to the MUD server
- `disconnect()`: Disconnect from the MUD server

### Command Methods

- `process_command(command)`: Process a command and return the response

### Automation Methods

- `enable_automation(context=None)`: Enable automation mode
- `disable_automation()`: Disable automation mode

### Status Methods

- `get_status_prompt()`: Generate a formatted status prompt with character information

### NPC Methods

- `find_and_hunt_npcs(npc_pattern, use_speedwalk=False)`: Find and hunt NPCs/mobs matching a pattern
- `find_and_navigate_to_npc(npc_name, use_speedwalk=False)`: Find a path to a specific NPC/mob and navigate there

### Knowledge Graph Methods


- `get_knowledge_graph_summary()`: Get a formatted summary of the knowledge graph
- `get_world_map()`: Get a merged map of all explored rooms
- `process_map_queue()`: Process any queued maps in the room manager

### Configuration Methods

- `enable_threaded_updates(enable=True)`: Enable or disable the use of threaded updates for room and status managers

### Quest Methods

- `find_questor(use_speedwalk=True)`: Find and navigate to the questor NPC
- `request_quest()`: Request a new quest from the questor
- `hunt_quest_target(use_speedwalk=True)`: Find and hunt the quest target
- `complete_quest()`: Complete the current quest by returning to the questor
- `check_quest_status()`: Check the status of the current quest
- `check_quest_info()`: Check detailed information about the current quest
- `recall_to_town()`: Use the recall command to return to town
- `check_quest_time()`: Check the time until the next quest is available
- `force_quest_time_check()`: Force a quest time check by resetting the quest_time_checked flag

## Extending the MUDAgent

To add new functionality to the `MUDAgent`, create a new component:

1. Create a new component class that inherits from `BaseAgentComponent`
2. Implement the required methods
3. Add an instance of your component to the `MUDAgent`

Example:

```python
from mud_agent.agent.components.base_component import BaseAgentComponent

class MyCustomComponent(BaseAgentComponent):
    def __init__(self, agent=None):
        super().__init__(agent)
        # Initialize your component

    async def initialize(self):
        # Initialize your component
        return True

    async def cleanup(self):
        # Clean up your component
        pass

    async def on_tick(self, tick_count):
        # Handle tick events
        pass

    async def my_custom_method(self):
        # Implement your custom functionality
        pass

# Add your component to the MUDAgent
agent.my_custom = MyCustomComponent(agent)
```

## Conclusion

The refactored `MUDAgent` provides a more modular and maintainable architecture while maintaining backward compatibility. By using the component-based approach, you can create more robust and flexible code that is easier to test and extend.
