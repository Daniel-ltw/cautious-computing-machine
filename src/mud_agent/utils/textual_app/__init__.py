"""MUD Textual App package.

This package provides a modular, maintainable implementation of the MUD client
Textual application, split into focused components for better organization.

Main Components:
- core: Main MUDTextualApp class
- styles: CSS styles and layout configuration
- commands: Command processing and routing
- gmcp_manager: GMCP polling and data management
- widget_updater: Widget update logic
- events: Event handling and callbacks
- server_comm: Server communication and message display

Usage:
    from mud_agent.utils.textual_app import MUDTextualApp
    
    app = MUDTextualApp(agent, state_manager, room_manager)
    await app.run_async()
"""

from .core import MUDTextualApp

__all__ = ["MUDTextualApp"]

# Version information
__version__ = "1.0.0"
__author__ = "MUD Agent Team"
__description__ = "Modular MUD client Textual application"
