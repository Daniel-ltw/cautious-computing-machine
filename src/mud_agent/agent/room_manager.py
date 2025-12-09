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
        self.previous_room_num: int | None = None  # Track the last known room number before an update
        # Commands that should be executed before movement (e.g., opening/unlocking doors)
        self.pending_pre_commands: set[str] = set()
        self.pending_exit_command: str | None = None  # The current pending movement command
        self.from_room_num_on_exit: int | None = None
        self.current_room: dict | None = None
        self.current_exits: dict | None = {}

    async def setup(self):
        """Subscribe to relevant events."""
        self.logger.info("Setting up RoomManager")
        self.events.on("command_sent", self._handle_command_sent)
        self.events.on("room_update", self._on_room_update)
        self.events.on("force_exit_check", self._handle_force_exit_check)
        self.logger.info(f"✓ RoomManager subscribed to events. EventManager ID: {id(self.events)}")
        self.logger.info(f"  Subscribed handlers: command_sent={self._handle_command_sent}, room_update={self._on_room_update}")

    def _get_current_room_num(self) -> int | None:
        """Get the current room number, with fallback to state_manager."""
        # Try to get from our tracked room data first
        if self.current_room and self.current_room.get("num"):
            room_num = self.current_room.get("num")
            self.logger.debug(f"_get_current_room_num: Using current_room.num = {room_num}")
            return room_num
        # Fallback to state_manager
        if hasattr(self.agent, 'state_manager') and self.agent.state_manager.room_num:
            room_num = self.agent.state_manager.room_num
            self.logger.debug(f"_get_current_room_num: Using state_manager.room_num = {room_num} (current_room not available)")
            return room_num
        self.logger.warning("_get_current_room_num: No room number available from any source!")
        return None

    async def _handle_command_sent(self, *args, **kwargs) -> None:
        """Handle the command_sent event.

        Args:
            *args: Positional arguments, first may be the command string.
            **kwargs: Event data, may contain 'command' and 'from_room_num'.
        """
        # Determine command from positional args or kwargs for backward compatibility
        if args and isinstance(args[0], str):
            command = args[0]
        else:
            command = kwargs.get('command')
        from_room_num_captured = kwargs.get('from_room_num')

        if not command:
            self.logger.warning("command_sent event received with no command")
            return

        cmd_lower = command.lower().strip()

        self.logger.debug(f"Handling command_sent: '{cmd_lower}', from_room_num={from_room_num_captured}")

        movement_commands = [
            "n", "s", "e", "w", "u", "d",
            "north", "south", "east", "west", "up", "down",
        ]
        startswith_commands = ["escape"]
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
                    self.from_room_num_on_exit = self._get_current_room_num()
                continue

            if pending_exit is None and (
                tok in movement_commands or any(tok.startswith(c) for c in startswith_commands)
            ):
                pending_exit = tok
                break

        if pending_exit:
            self.pending_exit_command = pending_exit
            # Use the captured from_room_num from the event (if available) to avoid race conditions
            # where GMCP updates arrive before we can read the current room
            if from_room_num_captured is not None:
                from_room_num = from_room_num_captured
                self.logger.debug(f"Using captured from_room_num={from_room_num} (before GMCP update)")
            else:
                from_room_num = self._get_current_room_num()
                self.logger.warning(f"No captured from_room_num, falling back to _get_current_room_num()={from_room_num}")

            self.from_room_num_on_exit = from_room_num
            self.logger.debug(
                f"✓ Movement command `{self.pending_exit_command}` detected from room {from_room_num}."
            )
            self.logger.debug(
                f"  current_room data: {self.current_room.get('num') if self.current_room else 'None'}, "
                f"state_manager.room_num: {self.agent.state_manager.room_num if hasattr(self.agent, 'state_manager') else 'N/A'}"
            )
            # After detecting movement command, we set pending state and let _on_room_update handle the exit when it arrives.
            # No need to explicitly wait here; the room_update event may have already been emitted.
            # The pending state will be cleared by _on_room_update after successful recording or by timeout logic elsewhere.
        else:
            # Command not recognized as a known movement command
            # Check if it's a pre-command (already handled above)
            is_pre_command = any(cmd_lower.startswith(v) for v in pre_command_verbs)
            if not is_pre_command:
                # Only trigger force exit check for whitelisted commands
                # This prevents accidental exit recording from commands like "look", "inventory", or typos
                implicit_exit_verbs = [
                    "enter ", "board", "climb", "crawl", "leave", "descend", "ascend", "give ", "kill ", "push ", "catch "
                ]
                is_allowed_implicit = any(cmd_lower.startswith(v) for v in implicit_exit_verbs)

                if is_allowed_implicit:
                    # Trigger force exit check to catch any unrecognized movement commands
                    self.logger.debug(f"Command '{cmd_lower}' recognized as potential implicit exit - triggering force exit check")

                    # Set pending exit command so _on_room_update can handle it immediately if a room update arrives
                    self.pending_exit_command = cmd_lower

                    # Ensure from_room_num is available
                    if from_room_num_captured is not None:
                        from_room_num = from_room_num_captured
                    else:
                        from_room_num = self._get_current_room_num()

                    self.from_room_num_on_exit = from_room_num

                    await self.events.emit("force_exit_check", command=cmd_lower)
                else:
                    self.logger.debug(f"Command '{cmd_lower}' not in implicit exit whitelist - ignoring")
                    # Do NOT clear pending_exit_command here. If the user types "look" or another command
                    # while waiting for the room update, we don't want to cancel the pending exit.
                    # It will be cleared by _on_room_update (if successful) or _handle_force_exit_check (timeout).

    async def _handle_force_exit_check(self, command: str) -> None:
        """Wait and check if a room change occurred after a command."""
        from_room_num = self._get_current_room_num()
        if not from_room_num:
            self.logger.debug(f"Force exit check skipped - no current room for command: {command}")
            return

        self.logger.debug(f"Force exit check: waiting 2s to detect room change after '{command}' from room {from_room_num}")
        await asyncio.sleep(2.0)

        # Check if the pending command was already handled (cleared) by _on_room_update
        if self.pending_exit_command != command:
            self.logger.debug(f"Force exit check: pending command '{self.pending_exit_command}' != '{command}', assuming handled or superseded.")
            return

        new_room_num = self._get_current_room_num()
        if new_room_num and new_room_num != from_room_num:
            # Collect any pending pre-commands that were set
            pre_cmds = list(self.pending_pre_commands) if self.pending_pre_commands else []
            self.logger.info(
                f"✓ Implicit room change detected! '{command}' moved from room {from_room_num} → {new_room_num}"
                + (f" (with pre-commands: {pre_cmds})" if pre_cmds else "")
            )
            await self.knowledge_graph.record_exit_success(
                from_room_num=from_room_num,
                to_room_num=new_room_num,
                direction=command,
                move_cmd=command,
                pre_cmds=pre_cmds,
            )
            # Clear pre-commands after recording
            self.pending_pre_commands.clear()
            self.from_room_num_on_exit = None
            self.pending_exit_command = None
        else:
            self.logger.debug(f"No room change detected after '{command}' (from: {from_room_num}, after: {new_room_num}). Clearing pending command.")
            self.pending_exit_command = None

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
        self.logger.debug(f"🔔 _on_room_update called with kwargs keys: {list(kwargs.keys())}")

        room_data = kwargs.get("room_data", kwargs)
        if not room_data or not room_data.get("num"):
            self.logger.warning(f"Received incomplete room data: {room_data}")
            return

        # Track previous room number before updating
        previous_num = self.current_room.get('num') if self.current_room else None
        if previous_num is not None:
            self.previous_room_num = previous_num
            self.logger.debug(f"_on_room_update: previous_room_num stored as {previous_num}")
        else:
            self.logger.debug("_on_room_update: No previous room number to store")

        # Update current room data
        self.current_room = room_data
        self.current_exits = room_data.get("exits", {})

        self.logger.debug(f"_on_room_update: current_room updated to num={room_data.get('num')}")
        # Update knowledge graph with new room data
        self.logger.debug(f"Updating knowledge graph with room data: {room_data}")
        try:
            await self.knowledge_graph.add_entity({"entityType": "Room", **room_data})
        except Exception:
            self.logger.exception("Error adding room entity to knowledge graph")

        self.logger.debug(f"Room data received: num={room_data.get('num')}, name={room_data.get('name', 'N/A')}")

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
                    move_direction = self._get_direction_from_command(self.pending_exit_command)
                    valid_pre_commands = []
                    if move_direction:
                        for pre_cmd in self.pending_pre_commands:
                            pre_cmd_direction = self._get_direction_from_command(pre_cmd)
                            if pre_cmd_direction and pre_cmd_direction == move_direction:
                                valid_pre_commands.append(pre_cmd)
                            else:
                                self.logger.warning(f"Invalid pre-command '{pre_cmd}' does not match move direction '{move_direction}'.")
                    else:
                        # Directionless move command (e.g., enter portal) - all pre-commands are valid
                        self.logger.info(f"Directionless move command '{self.pending_exit_command}' detected. All pre-commands are valid.")
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

                else:
                    # This covers the case where previous_room_num_on_exit == incoming_room_num
                    # This is the stale update or a failed move. The room hasn't changed.
                    self.logger.debug(
                        f"Implicit exit '{self.pending_exit_command}' ignored. "
                        f"prev={previous_room_num_on_exit}, incoming={incoming_room_num}. "
                        f"Room change required."
                    )
                    # We do NOT reset the pending state. We let the timeout in _handle_command_sent handle it.
                    self.logger.debug(
                        "Room number unchanged after move command; likely a stale update or failed move. Waiting for new room data or timeout."
                    )

            # Emit events for other components to consume
            asyncio.create_task(self.events.emit("state_update", update_type="room", data=room_data))
            asyncio.create_task(self.events.emit("ui_update", update_type="map"))
        except Exception as e:
            self.logger.error(f"Error in _on_room_update: {e}", exc_info=True)
