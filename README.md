# MUD Agent

An intelligent agent for playing MUD games with MCP (Multi-Context Protocol) integration.

## Features

- Connects to MUD servers using telnet protocols
- Supports multiple telnet protocols:
  - GMCP (Generic MUD Communication Protocol)
  - MSDP (MUD Server Data Protocol)
  - MCCP (MUD Client Compression Protocol)
  - ANSI color codes
- Integrates with Sequential Thinking MCP for decision making
- Uses Knowledge Graph Memory MCP for storing game knowledge
- Provides automation capabilities with context-aware exploration
- Asynchronous I/O for efficient communication
- Modular, component-based architecture with each class in its own file
- Event-driven design with reactive state management
- Two UI options:
  - Terminal-based UI with live status display
  - Textual-based UI with reactive widgets for status, map, and command input/output

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd mud_agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e .
```

This will install the package and its dependencies, making it available for import in your Python environment.

## Usage

1. (Optional) Set up your credentials in a `.env` file:
   - Copy the `.env.example` file to `.env`
   - Fill in your MUD username and password
   ```
   MUD_USERNAME=your_username
   MUD_PASSWORD=your_password
   ```

2. Run the agent:

For the terminal-based UI:
```bash
python -m src.mud_agent
```

For the Textual-based UI:
```bash
./run_textual_reactive.py
```

3. If credentials are not found in the `.env` file, you'll be prompted to enter your character name and password.

4. Enter commands to interact with the MUD server:
   - Regular MUD commands: `look`, `north`, `examine blackboard`, etc.
   - Special commands:
     - `auto [context]`: Enable automation mode with optional context
     - `quit`: Exit the program

5. When automation is enabled:
   - The agent will explore the game world automatically
   - Press Ctrl+C to disable automation and return to manual mode

## Textual UI

The Textual UI provides a more modern, interactive interface with the following features:

- Split-pane layout with dedicated areas for:
  - Status display (showing character stats, room info, and quest status)
  - Mini-map display (showing the current room's map)
  - Command input and output

To use the Textual UI:

```bash
./run_textual_reactive.py
```

The Textual UI uses reactive attributes to automatically update the display when the game state changes, providing a more responsive and visually appealing experience.

## Project Structure

```
mud_agent/
├── src/
│   └── mud_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── __main__textual_reactive.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── mud_agent.py
│       │   ├── refactored_mud_agent.py
│       │   ├── automation_manager.py
│       │   ├── combat_manager.py
│       │   ├── decision_engine.py
│       │   ├── knowledge_graph_manager.py
│       │   ├── npc_manager.py
│       │   ├── quest_manager.py
│       │   ├── room_manager.py
│       │   └── components/
│       │       ├── __init__.py
│       │       ├── base_component.py
│       │       ├── connection.py
│       │       └── command.py
│       ├── client/
│       │   ├── __init__.py
│       │   ├── mud_client.py
│       │   └── tools/
│       │       ├── __init__.py
│       │       └── mud_client_tool.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── config.py
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── create_entities_wrapper.py
│       │       ├── create_relations_wrapper.py
│       │       └── sequential_thinking_wrapper.py
│       ├── protocols/
│       │   ├── __init__.py
│       │   ├── telnet_bytes.py
│       │   ├── aardwolf_gmcp.py
│       │   ├── msdp_handler.py
│       │   ├── mccp_handler.py
│       │   ├── color_handler.py
│       │   └── aardwolf/
│       │       ├── __init__.py
│       │       ├── gmcp_manager.py
│       │       ├── character_data.py
│       │       ├── room_data.py
│       │       ├── map_data.py
│       │       ├── quest_data.py
│       │       └── utils.py
│       ├── state/
│       │   ├── __init__.py
│       │   ├── state_manager.py
│       │   └── components/
│       │       ├── __init__.py
│       │       ├── base_component.py
│       │       ├── character_state.py
│       │       ├── room_state.py
│       │       ├── quest_state.py
│       │       ├── event_handlers.py
│       │       └── observers.py
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           ├── env_loader.py
│           ├── tick_manager.py
│           ├── live_status_display.py
│           ├── map_storage.py
│           ├── textual_integration.py
│           ├── event_emitter.py
│           └── widgets/
│               ├── __init__.py
│               ├── base.py
│               ├── state_listener.py
│               ├── vitals_widgets.py
│               ├── status_widgets.py
│               └── map_widgets.py
├── tests/
│   ├── test_config.py
│   ├── test_logging.py
│   ├── test_mcp_manager.py
│   ├── test_mcp_tools.py
│   ├── test_mud_agent.py
│   ├── test_mud_client.py
│   ├── test_mud_client_tool.py
│   └── test_protocols.py
├── pytest.ini
├── requirements.txt
└── README.md
```

## Architecture

The MUD Agent uses a component-based architecture to organize functionality into specialized components that work together. This approach provides several benefits:

- **Modularity**: Each component is responsible for a specific aspect of functionality
- **Maintainability**: Smaller, focused components are easier to understand and maintain
- **Testability**: Components can be tested in isolation
- **Extensibility**: New components can be added without modifying existing code

Key architectural components include:

### StateManager

The StateManager is the central state repository that uses composition to delegate functionality to specialized components:

- **CharacterStateComponent**: Manages character-related state (stats, vitals, etc.)
- **RoomStateComponent**: Manages room-related state (room info, exits, map, etc.)

### AardwolfGMCPManager

The AardwolfGMCPManager handles GMCP data processing using specialized processors:

- **CharacterDataProcessor**: Processes character-related GMCP data
- **RoomDataProcessor**: Processes room-related GMCP data
- **MapDataProcessor**: Processes map-related GMCP data
- **QuestDataProcessor**: Processes quest-related GMCP data

### MUDAgent

The MUDAgent coordinates between various specialized managers and components:

- **ConnectionComponent**: Manages the connection to the MUD server
- **CommandComponent**: Processes commands sent to the MUD server

For more details, see the [Architecture Documentation](docs/architecture.md).

## Development

- Use `ruff` for code formatting and linting
- Write tests using `pytest`
- Follow the component-based architecture pattern
- Keep files under 300 lines for better maintainability

## Testing

To run the tests, you need to make sure the `src` directory is in your Python path. Here are several ways to do this:

### Option 1: Set the PYTHONPATH environment variable

```bash
# On Unix/Linux/macOS
export PYTHONPATH=$PYTHONPATH:$(pwd)/src

# On Windows
set PYTHONPATH=%PYTHONPATH%;%CD%\src
```

Then run the tests:
```bash
pytest
```

### Option 2: Use the run_tests.py script

This script automatically adds the src directory to the Python path:
```bash
python run_tests.py
```

### Option 3: Install the package in development mode

```bash
pip install -e .
```

Then run the tests:
```bash
pytest
```

### Running tests with coverage

```bash
# With PYTHONPATH set
pytest --cov=mud_agent

# Using the run_tests.py script
python run_tests.py --cov=mud_agent
```

### Running specific tests

```bash
# Run a specific test file
pytest tests/test_config.py

# Run a specific test class
pytest tests/test_config.py::TestModelConfig

# Run a specific test method
pytest tests/test_config.py::TestModelConfig::test_default_values
```

### Troubleshooting

If you encounter issues with the tests:

1. Make sure the `src` directory is in your Python path
2. Check that all dependencies are installed
3. Try running a specific test file to isolate the issue
4. Look for import errors or missing dependencies
5. If tests seem to hang, it might be due to asyncio event loop issues. Try running with:
   ```bash
   pytest --asyncio-mode=auto
   ```
6. For tests involving AsyncMock objects, make sure to await any coroutine methods

## License

MIT License
