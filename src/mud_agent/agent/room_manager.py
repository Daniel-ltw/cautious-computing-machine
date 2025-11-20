"""
Room Manager for MUD Agent.

This module handles room tracking, navigation, and related functionality.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class RoomManager:
    """Manages room tracking and navigation for the MUD agent."""

    def __init__(self, agent):
        self.agent = agent
        self.events = agent.events
        self.knowledge_graph = agent.knowledge_graph
        self.logger = logging.getLogger(__name__)
        self.pending_exit_command: str | None = None
        # Commands that should be executed before movement (e.g., opening/unlocking doors)
        self.pending_pre_commands: set[str] = set()
        self.from_room_num_on_exit: int | None = None
        self.current_room: dict | None = None
        self.current_exits: dict | None = {}

    async def setup(self):
        """Subscribe to relevant events."""
        self.logger.info("Setting up RoomManager")
        self.events.on("command_sent", self._handle_command_sent)
        self.events.on("room_update", self._on_room_update)
        self.events.on("force_exit_check", self._handle_force_exit_check)

    async def _handle_command_sent(self, command: str) -> None:
        """Handle the command_sent event."""
        cmd_lower = command.lower().strip()

        movement_commands = [
            "n", "s", "e", "w", "u", "d",
            "north", "south", "east", "west", "up", "down",
        ]
        startswith_commands = ["enter ", "board", "escape", "climb"]
        pre_command_verbs = [
            "open", "unlock", "pick", "bash", "break", "kick", "force", "unbar", "unlatch",
        ]

        tokens = [t.strip() for t in cmd_lower.split(";") if t.strip()] if ";" in cmd_lower else [cmd_lower]

        pending_exit = None
        for tok in tokens:
            if tok.startswith("say "):
                self.logger.info(f"Say command detected: '{tok}' - triggering force exit check from room {self.current_room.get('num') if self.current_room else 'unknown'}")
                asyncio.create_task(self.events.emit("force_exit_check", command=tok))

            if pending_exit is None and any(tok.startswith(v) for v in pre_command_verbs):
                self.pending_pre_commands.add(tok)
                if self.from_room_num_on_exit is None:
                    self.from_room_num_on_exit = (
                        self.current_room.get("num") if self.current_room else None
                    )
                continue

            if pending_exit is None and (
                tok in movement_commands or any(tok.startswith(c) for c in startswith_commands)
            ):
                pending_exit = tok
                break

        if pending_exit:
            self.pending_exit_command = pending_exit
            from_room_num = self.current_room.get("num") if self.current_room else None
            self.from_room_num_on_exit = from_room_num
            self.logger.debug(
                f"Movement command `{self.pending_exit_command}` sent from room {from_room_num}."
            )
            try:
                await asyncio.wait_for(self.events.wait("room_update"), timeout=5.0)
            except TimeoutError:
                self.logger.warning(f"Timeout waiting for room update after command: {command}")
                self.pending_exit_command = None
                self.from_room_num_on_exit = None
                self.pending_pre_commands.clear()
        else:
            self.pending_exit_command = None

    async def _handle_force_exit_check(self, command: str) -> None:
        """Wait and check if a room change occurred after a command."""
        from_room_num = self.current_room.get("num") if self.current_room else None
        if not from_room_num:
            self.logger.debug(f"Force exit check skipped - no current room for command: {command}")
            return

        self.logger.debug(f"Force exit check: waiting 2s to detect room change after '{command}' from room {from_room_num}")
        await asyncio.sleep(2.0)

        new_room_num = self.current_room.get("num") if self.current_room else None
        if new_room_num and new_room_num != from_room_num:
            self.logger.info(f"✓ Implicit room change detected! '{command}' moved from room {from_room_num} → {new_room_num}")
            await self.knowledge_graph.record_exit_success(
                from_room_num=from_room_num,
                to_room_num=new_room_num,
                direction=command,
                move_cmd=command,
                pre_cmds=[],
            )
        else:
            self.logger.debug(f"No room change detected after '{command}' (from: {from_room_num}, after: {new_room_num})")

    def _get_direction_from_command(self, command: str) -> str | None:
        """Extracts a direction from a command string."""
        parts = command.lower().split()
        direction_map = {
            "n": "north", "north": "north",
            "s": "south", "south": "south",
            "e": "east", "east": "east",
            "w": "west", "west": "west",
            "u": "up", "up": "up",
            "d": "down", "down": "down",
        }
        # Also check for abbreviated directions like 'n' as a whole word
        for part in reversed(parts):
            if part in direction_map:
                return direction_map[part]
        return None

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
                    self.logger.warning(
                        f"Successful move detected. Recording exit: from {previous_room_num_on_exit} to {incoming_room_num} "
                        f"cmd='{self.pending_exit_command}' pre_cmds={self.pending_pre_commands}"
                    )
                    move_direction = self._get_direction_from_command(self.pending_exit_command)
                    valid_pre_commands = []
                    if move_direction:
                        for pre_cmd in self.pending_pre_commands:
                            pre_cmd_direction = self._get_direction_from_command(pre_cmd)
                            if pre_cmd_direction and pre_cmd_direction == move_direction:
                                valid_pre_commands.append(pre_cmd)
                            else:
                                self.logger.warning("Invalid pre-command '{pre_cmd}' does not match move direction '{move_direction}'.")
                    else:
                        # Directionless move command (e.g., enter portal) - all pre-commands are valid
                        self.logger.info("Directionless move command '{self.pending_exit_command}' detected. All pre-commands are valid.")
                        valid_pre_commands = list(self.pending_pre_commands)

                    try:
                        await self.knowledge_graph.record_exit_success(
                            from_room_num=previous_room_num_on_exit,
                            to_room_num=incoming_room_num,
                            direction=self.pending_exit_command,
                            move_cmd=self.pending_exit_command,
                            pre_cmds=valid_pre_commands,
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
            try:
                await self.knowledge_graph.add_entity({"entityType": "Room", **room_data})
            except Exception:
                self.logger.exception("Failed to update knowledge graph with room data")

            # Emit events for other components to consume
            asyncio.create_task(self.events.emit("state_update", update_type="room", data=room_data))
            asyncio.create_task(self.events.emit("ui_update", update_type="map"))
        except Exception as e:
            self.logger.error(f"Error in _on_room_update: {e}", exc_info=True)
