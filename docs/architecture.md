# MUD Agent Architecture

This document provides an overview of the MUD Agent architecture, focusing on the component-based design pattern used throughout the codebase.

## Overview

The MUD Agent is built using a component-based architecture, where functionality is organized into specialized components that work together. This approach provides several benefits:

- **Modularity**: Each component is responsible for a specific aspect of functionality
- **Maintainability**: Smaller, focused components are easier to understand and maintain
- **Testability**: Components can be tested in isolation
- **Extensibility**: New components can be added without modifying existing code

## Core Components

### StateManager

The StateManager is the central state repository for the MUD agent. It uses composition to delegate functionality to specialized components:

- **CharacterStateComponent**: Manages character-related state (stats, vitals, etc.)
- **RoomStateComponent**: Manages room-related state (room info, exits, map, etc.)
- **EventHandlersComponent**: Handles events (connection, command, GMCP, etc.)
- **ObserversComponent**: Provides backward compatibility for the observer pattern

The StateManager uses an event-driven architecture to notify components of state changes. Components can subscribe to specific events using the events.on() method:

```python
# Register for state events
state_manager.events.on("state_update", handler)
state_manager.events.on("character_update", handler)
state_manager.events.on("vitals_update", handler)
# etc.
```

### AardwolfGMCPManager

The AardwolfGMCPManager handles GMCP data processing for Aardwolf MUD. It uses composition to delegate functionality to specialized processors:

- **CharacterDataProcessor**: Processes character-related GMCP data
- **RoomDataProcessor**: Processes room-related GMCP data
- **MapDataProcessor**: Processes map-related GMCP data
- **QuestDataProcessor**: Processes quest-related GMCP data

The AardwolfGMCPManager provides methods for requesting and processing GMCP data:

```python
# Request GMCP data
await gmcp_manager.request_gmcp_data("char")
await gmcp_manager.request_gmcp_data("room")
await gmcp_manager.request_gmcp_data("quest")

# Process GMCP data
updates = gmcp_manager.update_from_gmcp()

# Get processed data
char_data = gmcp_manager.get_character_data()
room_info = gmcp_manager.get_room_info()
map_data = gmcp_manager.get_map_data()
```

### MUDAgent

The MUDAgent is the main agent class that coordinates between the various specialized managers. It uses composition to delegate functionality to specialized components:

- **ConnectionComponent**: Manages the connection to the MUD server
- **CommandComponent**: Processes commands sent to the MUD server

The MUDAgent also manages various specialized managers:

- **StateManager**: Manages the agent's state
- **RoomManager**: Manages room-related functionality
- **CombatManager**: Manages combat-related functionality
- **KnowledgeGraphManager**: Manages the knowledge graph
- **AutomationManager**: Manages automation functionality
- **NPCManager**: Manages NPC-related functionality
- **DecisionEngine**: Manages decision-making functionality
- **QuestManager**: Manages quest-related functionality

## UI Components

The UI is built using the Textual framework and follows a reactive pattern where UI components react to state changes. The key components are:

### StateListener

The StateListener is a base class for widgets that need to listen for state events. It registers for events from the StateManager and its components, and provides methods for handling those events.

```python
# Register for state events
state_manager.events.on("state_update", self._on_state_update)
state_manager.events.on("character_update", self._on_character_update)
# etc.

# Also register for component-specific events
state_manager.character.events.on("character_update", self._on_character_update)
state_manager.room.events.on("room_update", self._on_room_update)
# etc.
```

### Vital Widgets

The vital widgets display character vitals (HP, MP, MV) and react to state changes. They use the StateListener to register for events and update their display accordingly.

- **BaseVitalWidget**: Base class for all vital widgets
- **CurrentVitalWidget**: Base class for widgets that display current vital values
- **MaxVitalWidget**: Base class for widgets that display maximum vital values
- **HPCurrentWidget**, **HPMaxWidget**, etc.: Specific vital widgets

## Event System

The event system is used throughout the codebase to notify components of state changes. The key events are:

- **state_update**: Emitted for any state change, with a summary of all changes
- **character_update**: Emitted when character information changes
- **vitals_update**: Emitted when HP, MP, or MV changes
- **stats_update**: Emitted when character stats change
- **maxstats_update**: Emitted when max stats change
- **worth_update**: Emitted when gold, bank, XP, QP, or TP changes
- **room_update**: Emitted when room information changes
- **map_update**: Emitted when the map changes
- **quest_update**: Emitted when quest information changes
- **status_update**: Emitted when status effects change
- **combat_update**: Emitted when combat status changes
- **state_error**: Emitted when an error occurs during state update

## Extending the Architecture

To add new functionality to the MUD Agent, you can create new components:

1. Create a new component class that inherits from the appropriate base class
2. Implement the required methods
3. Add an instance of your component to the appropriate manager

For example, to add a new state component:

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

The component-based architecture of the MUD Agent provides a flexible and maintainable foundation for building a complex MUD client. By organizing functionality into specialized components, the codebase is easier to understand, maintain, and extend.
