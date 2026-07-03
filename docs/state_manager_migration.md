# StateManager Migration Guide

This guide explains how to migrate from the old monolithic `StateManager` to the new component-based `StateManager`.

## Overview

The `StateManager` has been refactored to use a component-based architecture, which provides several benefits:

- **Modularity**: Each component is responsible for a specific aspect of state management
- **Maintainability**: Smaller, focused components are easier to understand and maintain
- **Testability**: Components can be tested in isolation
- **Extensibility**: New components can be added without modifying existing code

The refactored `StateManager` uses composition to delegate functionality to specialized components:

- `CharacterStateComponent`: Manages character-related state (stats, vitals, etc.)
- `RoomStateComponent`: Manages room-related state (room info, exits, map, etc.)
- `EventHandlersComponent`: Handles events (connection, command, GMCP, etc.)
- `ObserversComponent`: Provides backward compatibility for the observer pattern

## Backward Compatibility

The refactored `StateManager` maintains backward compatibility through:

1. **Property accessors**: All reactive attributes from the old `StateManager` are available as properties that delegate to the appropriate component
2. **Observer methods**: The observer pattern methods are delegated to the `ObserversComponent`
3. **Event system**: The event system works the same way as before

## Migration Steps

### Step 1: Update Imports

If you're importing directly from `state_manager.py`, update your imports:

```python
# Old import
from mud_agent.state.state_manager import StateManager

# New import
from mud_agent.state.refactored_state_manager import StateManager
```

### Step 2: Update Direct Attribute Access

If you're accessing attributes directly, consider using the event system instead:

```python
# Old approach (direct attribute access)
hp = state_manager.hp_current
max_hp = state_manager.hp_max

# New approach (event-based)
def on_vitals_update(vitals):
    hp = vitals.get("hp", 0)
    max_hp = vitals.get("maxhp", 0)
    # Do something with the updated vitals

state_manager.events.on("vitals_update", on_vitals_update)
```

### Step 3: Update Observer Pattern Usage

If you're using the observer pattern, consider using the event system instead:

```python
# Old approach (observer pattern)
def update_status():
    # Update UI with new status
    pass

state_manager.register_status_observer(update_status)

# New approach (event-based)
def on_state_update(updates):
    # Update UI with new status
    pass

state_manager.events.on("state_update", on_state_update)
```

### Step 4: Access Component-Specific Functionality

If you need to access component-specific functionality, use the component directly:

```python
# Access character state
character_state = state_manager.character.get_state()

# Access room state
room_state = state_manager.room.get_state()

# Access quest state
quest_state = state_manager.quest.get_state()
```

## Event System

The event system is the recommended way to interact with the `StateManager`. Here are the events you can subscribe to:

- `character_update`: Emitted when character information changes
- `vitals_update`: Emitted when HP, MP, or MV changes
- `stats_update`: Emitted when character stats change
- `maxstats_update`: Emitted when max stats change
- `worth_update`: Emitted when gold, bank, XP, QP, or TP changes
- `room_update`: Emitted when room information changes
- `map_update`: Emitted when the map changes
- `quest_update`: Emitted when quest information changes
- `status_update`: Emitted when status effects change
- `combat_update`: Emitted when combat status changes
- `state_update`: Emitted for any state change, with a summary of all changes
- `state_error`: Emitted when an error occurs during state update

Example usage:

```python
def on_vitals_update(vitals):
    print(f"HP: {vitals.get('hp', 0)}/{vitals.get('maxhp', 0)}")
    print(f"MP: {vitals.get('mana', 0)}/{vitals.get('maxmana', 0)}")
    print(f"MV: {vitals.get('moves', 0)}/{vitals.get('maxmoves', 0)}")

state_manager.events.on("vitals_update", on_vitals_update)
```

## Extending the StateManager

To add new functionality to the `StateManager`, create a new component:

1. Create a new component class that inherits from `BaseStateComponent`
2. Implement the required methods (`update_from_gmcp`, `get_state`, etc.)
3. Add an instance of your component to the `StateManager`

Example:

```python
from mud_agent.state.components.base_component import BaseStateComponent

class MyCustomComponent(BaseStateComponent):
    def __init__(self, state_manager=None):
        super().__init__(state_manager)
        # Initialize your component

    def update_from_gmcp(self, data):
        # Update your component from GMCP data
        pass

    def get_state(self):
        # Return the current state of your component
        pass

# Add your component to the StateManager
state_manager.my_custom = MyCustomComponent(state_manager)
```

## Conclusion

The refactored `StateManager` provides a more modular and maintainable architecture while maintaining backward compatibility. By using the event system and component-based approach, you can create more robust and flexible code that is easier to test and extend.
