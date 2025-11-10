# MUD Agent Entry Points

This document explains the different entry points available for the MUD Agent application.

## Entry Points

The MUD Agent has two main entry points:

1. **Textual UI (TUI)** - A rich, interactive terminal user interface with widgets for status, map, and command input/output.

## Textual UI (TUI)

The Textual UI provides a rich, interactive terminal interface with widgets for displaying character status, map, and command input/output. This is the primary interface for normal usage.

### Running the TUI

```bash
python -m src.mud_agent.__main__textual_reactive
```

or simply:

```bash
python -m src.mud_agent
```

### Features

- Status display with character stats, vitals, and other information
- Map display with room information
- Command input with history
- Command output with rich text formatting
- Automatic updates via GMCP

## Choosing the Right Entry Point

- Use the **Textual UI** for normal gameplay and when you want a rich, interactive interface.
- Use the **Text-based Interface** when you need to debug the core functionality with breakpoints.

## Debugging Tips

When debugging with the text-based interface:

1. You can set breakpoints in your IDE at key points in the code.
2. The text-based interface doesn't use the complex Textual UI framework, so it's easier to step through the code.
3. You can see the raw server responses without any formatting.
4. You can add print statements to debug specific parts of the code.

Example debugging session:

```python
# Add a breakpoint in the process_command method
async def process_command(self, command: str) -> str:
    # Breakpoint here
    response = await self.mud_tool.send_command(command)
    return response
```

Then run the text-based interface and enter commands to trigger the breakpoint.
