# MUD Agent

An intelligent agent for playing [Aardwolf MUD](http://www.aardwolf.com/) with automated exploration, mapping, and combat. Features a Textual-based terminal UI with live map, vitals, and command interface.

## Features

- Connects to Aardwolf MUD via telnet with GMCP, MSDP, MCCP, and ANSI support
- Textual-based terminal UI with split panes for map, vitals, and command I/O
- Automated exploration with breadth-first room discovery
- Local SQLite knowledge graph with optional Supabase background sync
- Room mapping, NPC tracking, quest management, and pathfinding
- Event-driven architecture with reactive state management

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Daniel-ltw/cautious-computing-machine.git
cd cautious-computing-machine

# Set up your environment
cp .env.example .env
# Edit .env with your MUD credentials (see Configuration below)

# Install dependencies and run
uv sync
uv run mud-agent
```

### Alternative: pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
mud-agent
```

### Alternative: run as module

```bash
uv run python -m mud_agent
```

## Configuration

Copy `.env.example` to `.env` and fill in your settings:

```bash
# Required: MUD server credentials
MUD_USERNAME=your_character_name
MUD_PASSWORD=your_password

# Optional: MUD server (defaults to aardmud.org:4000)
# MUD_HOST=aardmud.org
# MUD_PORT=4000

# Optional: Supabase sync for sharing map data across machines
# DATABASE_URL=postgresql://user:password@host:port/dbname
# SYNC_ENABLED=true
# SYNC_INTERVAL=30

# Optional: auto-cast commands on tick (comma-separated)
# AUTOCAST_COMMANDS=nimble,hide,sneak

# Optional: recall sequence
# RECALL="wear amu;enter"
```

If credentials are not in `.env`, you'll be prompted on startup.

## In-Game Commands

Standard MUD commands work as expected (`look`, `north`, `kill rat`, etc.). Additional agent commands:

| Command | Description |
|---------|-------------|
| `auto [context]` | Enable automated exploration with optional context |
| `Ctrl+C` | Disable automation, return to manual mode |
| `quit` | Exit the program |

## Database and Sync

The agent stores all discovered rooms, exits, NPCs, and observations in a **local SQLite database** (`knowledge_graph.db`). This works out of the box with no configuration.

### Optional: Supabase Sync

To share map data across machines, set `DATABASE_URL`, `SYNC_ENABLED=true`, and `SYNC_INTERVAL` in your `.env`. The agent runs a background sync worker that pushes local changes to Supabase and pulls remote changes (e.g., from a friend's session).

Delete sync is bidirectional: local deletes propagate to remote, and remote deletes (via Supabase dashboard or triggers) propagate back. See `docs/supabase_delete_triggers.sql` for the Postgres trigger setup.

## Development

```bash
# Install with dev and test dependencies
uv sync --extra dev --extra test

# Run tests
uv run pytest

# Run a specific test file
uv run pytest tests/db/test_models.py -v

# Lint and format
uv run ruff check .
uv run ruff format .
```

## Project Structure

```
src/mud_agent/
  __main__.py                    # Entry point (python -m mud_agent)
  __main__textual_reactive.py    # Textual UI app launcher
  agent/                         # Core agent logic
    mud_agent.py                 #   Main agent orchestrator
    automation_manager.py        #   Automated exploration
    combat_manager.py            #   Combat handling
    knowledge_graph_manager.py   #   Knowledge graph queries
    quest_manager.py             #   Quest tracking
    room_manager.py              #   Room processing
  client/                        # MUD client connection
  config/                        # Configuration loading
  db/                            # Database layer
    models.py                    #   Peewee models (Entity, Room, RoomExit, NPC, etc.)
    sync_models.py               #   Remote mirror models for Supabase sync
    sync_worker.py               #   Background push/pull sync worker
    migrations.py                #   SQLite schema migrations
  mcp/                           # MCP tool integrations
  protocols/                     # Telnet protocol handlers (GMCP, MSDP, MCCP)
  state/                         # Reactive state management
  utils/                         # UI widgets, logging, helpers
tests/                           # Test suite
```

## License

MIT License
