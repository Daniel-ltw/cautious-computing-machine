"""
Room Manager for MUD Agent.

This module handles room tracking, navigation, and related functionality.
"""

import asyncio
import logging
import re
import time
import json
from typing import Dict, List, Optional, Set
from ..mcp.models import RoomExit, Room



logger = logging.getLogger(__name__)


class RoomManager:
    """Manages room tracking and navigation for the MUD agent."""

    def __init__(self, agent):
        self.agent = agent
        self.events = agent.events
        self.knowledge_graph = agent.knowledge_graph
        self.logger = logging.getLogger(__name__)
        self.pending_exit_command: Optional[str] = None
        # Commands that should be executed before movement (e.g., opening/unlocking doors)
        self.pending_pre_commands: Set[str] = set()
        self.from_room_num_on_exit: Optional[int] = None
        self.current_room: Optional[dict] = None
        self.current_exits: Optional[dict] = {}

    async def setup(self):
        """Subscribe to relevant events."""
        self.logger.info("Setting up RoomManager")
        self.events.on("command_sent", self._handle_command_sent)
        self.events.on("room_update", self._on_room_update)
        self.events.on("force_exit_check", self._handle_force_exit_check)

    async def _handle_command_sent(self, command: str) -> None:
        """Handle the command_sent event."""
        if ";" in command:
            self.logger.debug(f"Ignoring chained command for movement tracking: {command}")
            return
        # TODO: Make this more robust, using a list of aliases for movement commands
        cmd_lower = command.lower()
        movement_commands = [
            "n", "s", "e", "w", "u", "d",
            "north", "south", "east", "west", "up", "down",
        ]
        startswith_commands = ["enter ", "board", "escape", "say "]

        # Pre-commands typically required before movement (e.g., opening closed doors)
        pre_command_verbs = [
            "open", "unlock", "pick", "bash", "break", "kick", "force", "unbar", "unlatch",
        ]

        # Detect and record pre-commands (do not wait for room update for these)
        if any(cmd_lower.startswith(v) for v in pre_command_verbs):
            self.pending_pre_commands.add(command.strip())
            # Remember the room we initiated the sequence from, if not already set
            if self.from_room_num_on_exit is None:
                self.from_room_num_on_exit = (
                    self.current_room.get("num") if self.current_room else None
                )
            self.logger.debug(f"Recorded pre-command `{command}` in room {self.from_room_num_on_exit}.")
            return

        if cmd_lower.startswith("say "):
            asyncio.create_task(self.events.emit("force_exit_check", command=command))

        if cmd_lower in movement_commands or any(cmd_lower.startswith(c) for c in startswith_commands):
            self.pending_exit_command = command.strip()
            from_room_num = self.current_room.get("num") if self.current_room else None
            self.from_room_num_on_exit = from_room_num

            self.logger.debug(
                f"Movement command `{command}` sent from room {from_room_num}."
            )
            # Wait for the room to change
            try:
                await asyncio.wait_for(self.events.wait("room_update"), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout waiting for room update after command: {command}")
                # Movement attempt failed or timed out; clear pending movement and any pre-commands
                self.pending_exit_command = None
                self.from_room_num_on_exit = None
                self.pending_pre_commands.clear()
        else:
            # Non-movement command; do not clear recorded pre-commands as they may precede a later movement
            # We only clear the pending exit command itself, if one was somehow pending.
            self.pending_exit_command = None

    async def _handle_force_exit_check(self, command: str) -> None:
        """Wait and check if a room change occurred after a command."""
        from_room_num = self.current_room.get("num") if self.current_room else None
        if not from_room_num:
            return

        await asyncio.sleep(2.0)

        new_room_num = self.current_room.get("num") if self.current_room else None
        if new_room_num and new_room_num != from_room_num:
            self.logger.info(f"Implicit room change detected after command: {command}")
            await self.knowledge_graph.record_exit_success(
                from_room_num=from_room_num,
                to_room_num=new_room_num,
                direction=command,
                move_cmd=command,
                pre_cmds=[],
            )

    async def _on_room_update(self, **kwargs):
        """Handles the room_update event from the StateManager."""
        room_data = kwargs.get("room_data", kwargs)
        if not room_data or not room_data.get("num"):
            self.logger.warning(f"Received incomplete room data: {room_data}")
            return

        try:
            incoming_room_num = room_data.get("num")
            previous_room_num_on_exit = self.from_room_num_on_exit

            self.logger.debug(
                f"Room update event. Incoming: {incoming_room_num}. Pending exit from: {previous_room_num_on_exit}."
            )

            # Check if we were expecting a room change
            if self.pending_exit_command:
                # This is the key logic: only act if the room number has actually changed.
                if previous_room_num_on_exit is not None and previous_room_num_on_exit != incoming_room_num:
                    self.logger.debug(
                        f"Successful move detected. Recording exit: from {previous_room_num_on_exit} to {incoming_room_num} "
                        f"cmd='{self.pending_exit_command}' pre_cmds={self.pending_pre_commands}"
                    )
                    try:
                        await self.knowledge_graph.record_exit_success(
                            from_room_num=previous_room_num_on_exit,
                            to_room_num=incoming_room_num,
                            direction=self.pending_exit_command,
                            move_cmd=self.pending_exit_command,
                            pre_cmds=list(self.pending_pre_commands),
                        )
                    except Exception:
                        self.logger.exception("Error recording exit success in knowledge graph.")
                    finally:
                        # A successful move was recorded, so we can safely reset the pending state.
                        self.pending_exit_command = None
                        self.from_room_num_on_exit = None
                        self.pending_pre_commands.clear()

                elif previous_room_num_on_exit is not None and previous_room_num_on_exit == incoming_room_num:
                    # This is the stale update or a failed move. The room hasn't changed.
                    # We do NOT reset the pending state. We let the timeout in _handle_command_sent handle it.
                    self.logger.debug(
                        "Room number unchanged after move command; likely a stale update or failed move. Waiting for new room data or timeout."
                    )

            # Always update the current room state and knowledge graph
            self.current_room = room_data
            self.current_exits = room_data.get("exits", {})

            self.logger.debug(f"Updating knowledge graph with room data: {room_data}")
            await self.knowledge_graph.add_entity(
                {"entityType": "Room", **room_data}
            )

            # Emit events for other components to consume
            asyncio.create_task(self.events.emit("state_update", update_type="room", data=room_data))
            asyncio.create_task(self.events.emit("ui_update", update_type="map"))
        except Exception as e:
            self.logger.error(f"Error in _on_room_update: {e}", exc_info=True)
