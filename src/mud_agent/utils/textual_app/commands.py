"""Command processing and routing for the MUD Textual App.

This module handles all command submission, routing, and processing,
including internal commands and special debug commands.
"""

import asyncio
import collections
import logging
import random
import re

from ...mcp.game_knowledge_graph import PathfindingError
from ..textual_widgets import CommandInput
from ..widgets.command_log import CommandLog

logger = logging.getLogger(__name__)


class CommandProcessor:
    """Handles command processing and routing for the MUD application."""

    OPPOSITE_DIRECTIONS = {
        "north": "south",
        "south": "north",
        "east": "west",
        "west": "east",
        "up": "down",
        "down": "up",
    }

    def __init__(self, app):
        self.app = app
        self.agent = app.agent
        self.state_manager = app.state_manager
        self.logger = logger
        self.exploring = False
        self.exploration_task = None
        self.auto_spellup = False
        self.auto_spellup_task = None

    async def submit_command(self, command: str) -> None:
        """Submit a command for processing.

        Args:
            command: The command to submit
        """
        try:
            command_log = self.app.query_one("#command-log", CommandLog)

            # Log the command
            command_log.write(f"[bold cyan]> {command}[/bold cyan]")

            # Handle internal commands (starting with '/')
            if command.startswith("/"):
                await self.handle_internal_command(command)
                return

            # Handle special debug commands
            if command.lower() in ["debug", "reconnect"]:
                if command.lower() == "debug":
                    command_log.write("[bold yellow]Debug mode activated[/bold yellow]")
                    # Add debug functionality here
                elif command.lower() == "reconnect":
                    command_log.write("[bold yellow]Reconnecting...[/bold yellow]")
                    asyncio.create_task(self._reconnect())
                return

            # Process the command through the agent for proper handling
            if hasattr(self.agent, "client") and self.agent.client.connected:
                asyncio.create_task(self.agent.send_command(command))
            else:
                command_log.write("[bold red]Not connected to server[/bold red]")

        except Exception as e:
            logger.error(f"Error in submit_command: {e}", exc_info=True)

    async def handle_internal_command(self, command: str) -> None:
        """Handle internal '/'-prefixed commands.

        Args:
            command: The internal command to handle
        """
        command_log = self.app.query_one("#command-log", CommandLog)

        try:
            if command.startswith("/sw "):
                area = command[4:].strip()
                if not area:
                    command_log.write("[bold red]Usage: /sw <area>[/bold red]")
                    return
                await self.handle_speedwalk(area)

            elif command.startswith("/mh "):
                area = command[4:].strip()
                if not area:
                    command_log.write("[bold red]Usage: /mh <area>[/bold red]")
                    return
                await self.handle_mobhunt(area)

            elif command == "/ac":
                self.auto_spellup = not self.auto_spellup
                command_log = self.app.query_one("#command-log", CommandLog)
                if self.auto_spellup:
                    command_log.write("[bold cyan]Autocast: [/bold cyan][bold red]On[/bold red]")
                    if not self.auto_spellup_task or self.auto_spellup_task.done():
                        self.auto_spellup_task = asyncio.create_task(self.handle_autocast())
                else:
                    command_log.write("[bold cyan]Autocast: [/bold cyan][bold red]Off[/bold red]")
                    if self.auto_spellup_task and not self.auto_spellup_task.done():
                        self.auto_spellup_task.cancel()
                    self.auto_spellup_task = None

            elif command.startswith("/rf "):
                room_name = command[4:].strip()
                if not room_name:
                    command_log.write("[bold red]Usage: /rf <room_name>[/bold red]")
                    return
                await self.find_direction_and_walk_to_room(room_name)

            elif command.startswith("/atk "):
                mob = command[4:].strip()
                if not mob:
                    command_log.write("[bold red]Usage: /atk <mob>[/bold red]")
                    return
                await self.handle_atk(mob)

            elif command.startswith("/auto "):
                context = command[6:].strip()
                if not context:
                    command_log.write("[bold red]Usage: /auto <context>|off[/bold red]")
                    return
                if context.lower() == "off":
                    self.agent.automation_manager.disable_automation()
                    command_log.write("[bold yellow]Automation disabled[/bold yellow]")
                else:
                    await self.agent.automation_manager.enable_automation(context)
                    command_log.write(f"[bold green]Automation enabled with context:[/bold green] {context}")

            elif command.startswith("/ur"):
                # Extract optional NPC name parameter
                parts = command.split(" ", 1)
                npc_name = parts[1].strip() if len(parts) > 1 else None
                await self.handle_update_room_command(npc_name)

            elif command.startswith("/xa"):
                await self.handle_explore_area()

            elif command == "/scan":
                await self.handle_scan_command()

            elif command == "/help" or command == "/?":
                await self.show_internal_commands_help()

            elif command.startswith("/filter "):
                await self.handle_filter_command(command[8:].strip())

            elif command == "/filter":
                await self.show_filter_status()

            elif command == "/testalert":
                command_log.write("[bold cyan]Testing quest alert sound...[/bold cyan]")
                if hasattr(self.agent, "quest_manager"):
                    self.agent.quest_manager._play_alert_sound()
                    command_log.write("[bold green]Alert sound triggered.[/bold green]")
                else:
                    command_log.write("[bold red]QuestManager not found on agent.[/bold red]")

            else:
                command_log.write(f"[bold yellow]Unknown internal command: {command}[/bold yellow]")
                command_log.write("[bold cyan]Type /help for available commands[/bold cyan]")

        except Exception as e:
            logger.error(f"Error handling internal command '{command}': {e}", exc_info=True)
            command_log.write(f"[bold red]Error executing command: {e}[/bold red]")

    async def handle_speedwalk(self, area: str) -> None:
        """Handle the /sw <area> command: send speedwalk, extract run command, pre-fill input.

        Args:
            area: The area to speedwalk to
        """
        command_log = self.app.query_one("#command-log", CommandLog)
        command_log.write(f"[bold cyan]Looking for speedwalk to: {area}[/bold cyan]")

        if (self.state_manager.room_name == "The Aardwolf Plaza Hotel" or
            self.state_manager.room_num == 26151):
                await self.agent.send_command("d")
        elif (self.state_manager.room_name == "The Grand City of Aylor" or
            self.state_manager.room_num == 32418):
            pass
        else:
            # Use the knowledge graph to find the path
            path_info = await self.agent.knowledge_graph.find_path_between_rooms(
                start_room_id=self.state_manager.room_num,
                end_room_identifier=32418
            )

            if path_info and path_info.get("path"):
                path = path_info["path"]
                cost = path_info.get("cost", "N/A")
                run_command_str = self._compress_path(path)

                command_log.write(f"[bold green]Path found to 'The Grand City of Aylor' (cost: {cost}):[/bold green]")
                command_log.write(f"[cyan]{run_command_str}[/cyan]")
                await self.agent.send_command(run_command_str)

        await self.agent.send_command(f"runto {area}")

    async def handle_mobhunt(self, mob: str) -> None:
        """Handle the /mh <mob> command: send where, extract room name, pre-fill input.

        Args:
            mob: The mob to mobhunt to
        """
        command_log = self.app.query_one("#command-log", CommandLog)
        command_log.write(f"[bold cyan]Looking for mob to: {mob}[/bold cyan]")

        try:
            await self.agent.send_command(f"where {mob}")
            response_text = command_log.lines[-10:]

            response_line = None

            if response_text:
                for line in response_text:
                    if mob.lower() in line.text.lower() and re.search(r'\s{2,}', line.text):
                        response_line = line.text
                        break

            room_name = None
            if response_line:
                # Using a more specific regex to separate mob from room, assuming room name starts with a capital
                match = re.search(r'^(.*?)\s{2,}([A-Z].*)$', response_line)
                if not match:
                    # Fallback to the original less specific regex if the above fails
                    match = re.search(r'^(.*)\s{2,}(.+)$', response_line)

                if match:
                    mob_desc = match.group(1).strip()
                    room = match.group(2).strip()

                    # Aggressive cleanup of room name
                    # First, remove common patterns like (details) or , 123 from the end
                    room = re.sub(r"\s*\([^)]*\)\s*$", "", room).strip()
                    room = re.sub(r",\s*\d+\s*$", "", room).strip()
                    # Then, remove any remaining non-alphanumeric characters from the end (except apostrophe)
                    room = re.sub(r"[^a-zA-Z0-9\s']+$", "", room).strip()

                    # Verify that the mob we searched for is in the description part
                    query_words = set(mob.lower().split())
                    desc_words = set(mob_desc.lower().split())
                    if query_words.issubset(desc_words):
                        room_name = room

            if room_name:
                command_log.write(f"[bold green]Room found: {room_name}[/bold green]")
                await self.find_direction_and_walk_to_room(room_name)
            else:
                command_log.write(f"[bold red]No room found for mob: {mob}[/bold red]")
        except Exception as e:
            logger.error(f"Error in handle_mobhunt: {e}", exc_info=True)
            command_log.write(f"[bold red]Error processing mobhunt: {e}[/bold red]")

    def _compress_path(self, path: list[str]) -> str:
        """
        Compresses a list of directions into a compact string, handling multi-word commands.
        e.g., ['n', 'n', 'w', 'open door', 'w', 'w', 'open s', 's'] -> 'run 2nw;open door;run 2w;open s;s'
        """
        if not path:
            return ""

        # First, compress consecutive single-letter directions
        compressed_path = []
        i = 0
        while i < len(path):
            command = path[i]
            if command and re.match(r'^[neswud]$', command):
                count = 1
                j = i + 1
                while j < len(path) and path[j] == command:
                    count += 1
                    j += 1

                if count > 1:
                    compressed_path.append(f"{count}{command}")
                else:
                    compressed_path.append(command)
                i = j
            else:
                if command:
                    compressed_path.append(command)
                i += 1

        # Now, group consecutive movements and prepend 'run'
        final_commands = []
        movement_group = []
        for cmd in compressed_path:
            if re.match(r'^\d*[neswud]$', cmd):
                movement_group.append(cmd)
            else:
                if movement_group:
                    moves = "".join(movement_group)
                    num_moves = 0
                    for move in movement_group:
                        if len(move) > 1 and move[:-1].isdigit():
                            num_moves += int(move[:-1])
                        else:
                            num_moves += 1

                    if num_moves > 1:
                        final_commands.append("run " + moves)
                    else:
                        final_commands.append(moves)
                    movement_group = []

                if cmd:
                    final_commands.append(cmd)

        if movement_group:
            moves = "".join(movement_group)
            num_moves = 0
            for move in movement_group:
                if len(move) > 1 and move[:-1].isdigit():
                    num_moves += int(move[:-1])
                else:
                    num_moves += 1

            if num_moves > 1:
                final_commands.append("run " + moves)
            else:
                final_commands.append(moves)

        return ";".join(final_commands)

    async def handle_autocast(self):
        while True:
            if not self.auto_spellup:
                return

            # Use configured autocast commands or fallback to default
            skills_spells = ["nimble", "hide", "sneak", "cast under"]
            if hasattr(self.agent, "config") and hasattr(self.agent.config, "agent"):
                skills_spells = self.agent.config.agent.autocast_commands

            for cmd in skills_spells:
                await self.agent.send_command(cmd)
            await asyncio.sleep(random.uniform(15.0, 60.0))

    async def find_direction_and_walk_to_room(self, room_name: str) -> None:
        """Find a path to the specified room using the knowledge graph and pre-fill the run command.

        Args:
            room_name: The name of the room to find.
        """
        command_log = self.app.query_one("#command-log", CommandLog)
        command_log.write(f"[bold cyan]Finding path to room: {room_name}[/bold cyan]")

        try:
            current_room_num = self.state_manager.room_num
            if not current_room_num:
                command_log.write("[bold red]Error: Current room number is unknown. Cannot find path.[/bold red]")
                return

            # Use the knowledge graph to find the path
            path_info = await self.agent.knowledge_graph.find_path_between_rooms(
                start_room_id=current_room_num,
                end_room_identifier=room_name,
                max_depth=1000
            )

            if path_info and path_info.get("path"):
                path = path_info["path"]
                cost = path_info.get("cost", "N/A")
                run_command_str = self._compress_path(path)

                command_log.write(f"[bold green]Path found to '{room_name}' (cost: {cost}):[/bold green]")
                command_log.write(f"[cyan]{run_command_str}[/cyan]")

                # Pre-fill the command input
                self.prefill_command_input(run_command_str)
            else:
                command_log.write(f"[bold red]No path found to room: {room_name}[/bold red]")
                command_log.write("[dim]The room may not be in the knowledge graph, or there is no known path.[/dim]")

        except PathfindingError as e:
            command_log.write(f"[bold red]{e}[/bold red]")
        except Exception as e:
            logger.error(f"Error in find_direction_and_walk_to_room: {e}", exc_info=True)
            command_log.write(f"[bold red]Error finding path: {e}[/bold red]")

    async def handle_update_room_command(self, npc_name: str = None) -> None:
        """Handle the /ur command: update knowledge graph with current room and mob data.

        Args:
            npc_name: Optional NPC/mob name to add to the current room
        """
        command_log = self.app.query_one("#command-log", CommandLog)

        try:
            if npc_name:
                command_log.write(f"[bold cyan]Updating room data with NPC '{npc_name}'...[/bold cyan]")
            else:
                command_log.write("[bold cyan]Updating room data...[/bold cyan]")

            # Get current room information from GMCP
            room_data = self.agent.aardwolf_gmcp.get_room_info() if hasattr(self.agent, 'aardwolf_gmcp') else {}

            if not room_data or not room_data.get('name') or not room_data.get('num'):
                command_log.write("[bold red]Error: Current room is unknown. Try 'look' first.[/bold red]")
                return

            # Prepare the data for the knowledge graph
            entity_data = {
                "room_number": room_data.get('num'),
                "entityType": "Room",
                "name": room_data.get('name'),
                "description": room_data.get('desc', ''),
                "exits": room_data.get('exits', {}),
                "area": room_data.get('zone', 'Unknown'),
                "coordinates": room_data.get('coord', {}),
                "npcs": room_data.get('npcs', [])
            }

            # Convert NPC names to the format expected by add_entity
            if room_data.get('npcs'):
                entity_data['npcs'] = [{"name": name} for name in room_data['npcs']]

            # If an NPC was manually added, add it to the room's NPC list
            if npc_name:
                if 'npcs' not in entity_data:
                    entity_data['npcs'] = []
                # Check if npc is already in the list by name
                if not any(npc.get('name') == npc_name for npc in entity_data['npcs']):
                    entity_data['npcs'].append({"name": npc_name})
                    command_log.write(f"[bold yellow]Added '{npc_name}' to current room NPCs[/bold yellow]")

            # Update the knowledge graph
            entity = await self.agent.knowledge_graph.add_entity(entity_data)

            if entity:
                response = await self.agent.send_command('exits')
                if response:
                    command_log.write("[bold green]Picked up exits response[/bold green]")
                    command_log.write(f"[bold green]{response}[/bold green]")
                    await self.agent.room_manager.update_exits_from_command(response)
                command_log.write("[bold green]Room data updated successfully in knowledge graph[/bold green]")
            else:
                command_log.write("[bold red]Room data error updating.[/bold red]")

        except Exception as e:
            command_log.write(f"[bold red]Error updating room data: {e}[/bold red]")
            self.logger.error(f"Error in handle_update_room_command: {e}", exc_info=True)

    async def handle_explore_area(self):
        """Handle the /xa command to toggle exploration of the current area."""
        command_log = self.app.query_one("#command-log", CommandLog)

        if self.exploring:
            # If exploration is running, stop it
            if self.exploration_task and not self.exploration_task.done():
                self.exploration_task.cancel()
                self.exploring = False
                command_log.write("[bold yellow]Area exploration stopping...[/bold yellow]")
            else:
                command_log.write("[bold yellow]Exploration was not running.[/bold yellow]")
        else:
            # If exploration is not running, start it
            self.exploring = True
            command_log.write("[bold cyan]Starting area exploration...[/bold cyan]")
            self.exploration_task = asyncio.create_task(self._exploration_loop())

    async def _exploration_loop(self):
        """The main loop for the area exploration task."""
        command_log = self.app.query_one("#command-log", CommandLog)
        try:
            command_log.write("[bold]Starting area exploration...[/bold]")

            start_room_num = self.state_manager.room_num
            if not start_room_num:
                command_log.write(
                    "[bold red]Error: Current room is unknown. Cannot start exploration.[/bold red]"
                )
                self.exploring = False
                return

            start_room = self.agent.knowledge_graph.get_room_by_number(start_room_num)
            if not start_room or not start_room.zone:
                command_log.write(
                    "[bold red]Error: Current area is unknown. Cannot start exploration.[/bold red]"
                )
                self.exploring = False
                return

            target_area = start_room.zone
            command_log.write(f"[bold]Exploring area: {target_area}[/bold]")

            visited_rooms = set()

            while self.exploring:
                # Find a room at the edge of the explored area with unexplored exits
                edge_room = self.agent.knowledge_graph.get_room_with_unexplored_exits(target_area, visited_rooms)

                if not edge_room:
                    command_log.write("[bold green]No more unexplored rooms found in the area.[/bold green]")
                    break

                # Navigate to the edge room
                if self.state_manager.room_num != edge_room.room_number:
                    path_info = await self.agent.knowledge_graph.find_path_between_rooms(
                        self.state_manager.room_num, edge_room.room_number, max_depth=250
                    )
                    if not path_info or not path_info.get("path"):
                        command_log.write(
                            f"[bold red]Cannot find path to edge room {edge_room.room_number}. Skipping.[/bold red]"
                        )
                        visited_rooms.add(edge_room.room_number)
                        continue

                    path_commands = path_info["path"]
                    command_log.write(f"Moving to edge room: {edge_room.room_number}")
                    run_command_str = self._compress_path(path_commands)
                    await self.agent.send_command(run_command_str)
                    await asyncio.sleep(random.uniform(0.7, 1.3) * len(run_command_str.split(";")))

                # Explore the branch starting from the edge room
                await self._explore_branch(edge_room, target_area, visited_rooms)

            command_log.write("[bold green]Exploration complete.[/bold green]")

        except asyncio.CancelledError:
            command_log.write("[bold yellow]Exploration task cancelled.[/bold yellow]")
        except Exception as e:
            command_log.write(f"[bold red]An error occurred during exploration: {e}[/bold red]")
            self.logger.error(f"Error in exploration loop: {e}", exc_info=True)
        finally:
            self.exploring = False
            self.exploration_task = None

    async def _explore_branch(self, start_room, target_area, visited_rooms):
        """Explore a branch of rooms starting from a given room."""
        command_log = self.app.query_one("#command-log", CommandLog)
        queue = collections.deque([start_room])
        branch_visited = set()

        while self.exploring and queue:
            current_room = queue.popleft()
            if current_room.room_number in visited_rooms:
                continue

            visited_rooms.add(current_room.room_number)
            branch_visited.add(current_room.room_number)

            # Navigate to the current room in the branch
            if self.state_manager.room_num != current_room.room_number:
                path_info = await self.agent.knowledge_graph.find_path_between_rooms(
                    self.state_manager.room_num, current_room.room_number, max_depth=250
                )
                if not path_info or not path_info.get("path"):
                    command_log.write(
                        f"[bold red]Cannot find path to room {current_room.room_number} in branch. Skipping.[/bold red]"
                    )
                    continue
                path_commands = path_info["path"]
                command_log.write(f"Exploring branch, moving to room: {current_room.room_number}")
                run_command_str = self._compress_path(path_commands)
                if len(run_command_str) > 1:
                    await self.agent.send_command(run_command_str)
                else:
                    await self.agent.send_command(run_command_str)
                await asyncio.sleep(random.uniform(0.7, 1.3) * len(run_command_str.split(";")))

            # Explore exits of the current room
            await self.handle_update_room_command()
            current_room_node = self.agent.knowledge_graph.get_room_by_number(self.state_manager.room_num)
            if not current_room_node:
                continue

            exits = {exit.direction: exit for exit in current_room_node.exits if exit.to_room is None}

            for direction, exit_info in exits.items():
                if not self.exploring:
                    break

                room_num_before_move = self.state_manager.room_num
                command_log.write(f"Exploring direction: {direction}")

                # Attempt to move
                await self.agent.send_command(direction)
                await asyncio.sleep(random.uniform(0.7, 1.3))

                # Handle closed doors
                if self.state_manager.room_num == room_num_before_move:
                    command_log.write(f"Found a door at {direction}. Attempting to open.")
                    await self.agent.send_command(f"open {direction}")
                    await asyncio.sleep(random.uniform(0.7, 1.3))
                    await self.agent.send_command(direction)
                    await asyncio.sleep(random.uniform(0.7, 1.3))

                if self.state_manager.room_num != room_num_before_move:
                    command_log.write(f"[green]Moved {direction} to room {self.state_manager.room_num}.[/green]")
                    await self.handle_update_room_command()
                    new_room_num = self.state_manager.room_num
                    new_room_data = self.agent.aardwolf_gmcp.get_room_info()
                    if new_room_data.get('zone') == target_area:
                        new_room_node = self.agent.knowledge_graph.get_room_by_number(new_room_num)
                        if new_room_node and new_room_num not in visited_rooms:
                            queue.append(new_room_node)
                    else:
                        command_log.write(f"[yellow]Room {new_room_num} is in a different area. Not adding to branch queue.[/yellow]")

                    # Go back to the previous room to continue exploring other exits
                    opposite_direction = self._get_opposite_direction(direction)
                    if opposite_direction:
                        await self.agent.send_command(opposite_direction)
                        await asyncio.sleep(random.uniform(0.7, 1.3))
                else:
                    command_log.write(f"[yellow]Could not move {direction}. It might be a locked door.[/yellow]")

    def _get_opposite_direction(self, direction: str) -> str | None:
        """Get the opposite direction for a given cardinal direction."""
        opposites = {
            "n": "s", "s": "n", "e": "w", "w": "e",
            "u": "d", "d": "u", "ne": "sw", "sw": "ne",
            "nw": "se", "se": "nw"
        }
        return opposites.get(direction.lower())


    async def handle_scan_command(self) -> None:
        """Handle the /scan command."""
        try:
            command_log = self.app.query_one("#command-log", CommandLog)
            response = await self.agent.send_command("scan here")

            command_log.write(f"[bold cyan]Scan command done with: [/bold cyan]{response}")

            # Parse the response to extract NPC names
            npc_set = set()
            lines = response.splitlines()
            if lines[0].startswith("Right here you see:"):
                for line in lines:
                    # Aardwolf scan output for NPCs is often prefixed with "- "
                    line = line.strip()
                    if line.startswith("- "):
                        npc_name = line[2:].strip()
                        if npc_name:
                            npc_set.add(npc_name)

            npcs = list(npc_set)

            if len(npcs) == 0:
                command_log.write("[bold cyan]No NPCs found in scan response.[/bold cyan]")
                return

            # Get the current room information
            room_num = self.agent.state_manager.room_num
            if not room_num:
                command_log.write("[bold red]Cannot update NPCs: Current room number is unknown.[/bold red]")
                return

            # Get existing room data from the state manager
            room_data = self.agent.state_manager.get_current_room_data()
            if not room_data:
                command_log.write("[bold red]Cannot update NPCs: Failed to get current room data.[/bold red]")
                return

            # Add the scanned NPCs to the room data
            room_data["room_number"] = room_data.pop("num")
            room_data["scan_npcs"] = [{"name": name} for name in npcs]
            room_data["entityType"] = "Room"  # Ensure entityType is set

            # Update the knowledge graph
            entity = await self.agent.knowledge_graph.add_entity(room_data)
            if entity:
                command_log.write(f"[bold green]Updated room {room_num} with {len(npcs)} NPCs from scan: [/bold green]{', '.join(npcs)}")
            else:
                command_log.write(f"[bold red]Scan room update failed: [/bold red]{room_data}")

        except Exception as e:
            command_log.write(f"[bold red]Error capturing NPCs via scan: [/bold red]{e}", exc_info=True)


    async def handle_atk(self, mob: str) -> None:
        """Handle the /atk command."""
        try:
            command_log = self.app.query_one("#command-log", CommandLog)
            skills = ["kob", "kick", "circle"]
            for i, skill in enumerate(skills):
                if i == 0:
                    await self.agent.send_command(f"{skill} {mob}")
                    command_log.write(f"[bold cyan]Attack command done with: [/bold cyan]{skill} {mob}")
                else:
                    await self.agent.send_command(skill)
                    command_log.write(f"[bold cyan]Attack command done with: [/bold cyan]{skill}")
        except Exception as e:
            command_log.write(f"[bold red]Error attacking mob: [/bold red]{e}", exc_info=True)


    async def show_internal_commands_help(self) -> None:
        """Show help for available internal commands."""
        command_log = self.app.query_one("#command-log", CommandLog)
        command_log.write("[bold cyan]Available Internal Commands:[/bold cyan]")
        command_log.write("[bold white]/sw <area>[/bold white] - Find speedwalk to area and pre-fill input")
        command_log.write("[bold white]/mh <mob>[/bold white] - Find mob and pre-fill input with direction to mob")
        command_log.write("[bold white]/rf <room_name>[/bold white] - Find direction and walk to specific room")
        command_log.write("[bold white]/atk <mob>[/bold white] - Attack mob")
        command_log.write("[bold white]/auto <context>|off[/bold white] - Enable/disable automation with context")
        command_log.write("[bold white]/ur [npc_name][/bold white] - Update knowledge graph with current room and mob data")
        command_log.write("[bold white]/scan[/bold white] - Scan current room for NPCs and update knowledge graph")
        command_log.write("[bold white]/filter[/bold white] - Show current log filtering status")
        command_log.write("[bold white]/filter level <ERROR|WARNING|INFO|DEBUG>[/bold white] - Set minimum log level")
        command_log.write("[bold white]/filter debug <on|off>[/bold white] - Enable/disable debug message filtering")
        command_log.write("[bold white]/filter add <pattern>[/bold white] - Add custom debug filter pattern")
        command_log.write("[bold white]/filter remove <pattern>[/bold white] - Remove custom debug filter pattern")
        command_log.write("[bold white]/help or /?[/bold white] - Show this help message")
        command_log.write("[dim]Note: All internal commands start with '/'[/dim]")

    def prefill_command_input(self, text: str) -> None:
        """Pre-fill the command input widget with the given text.

        Args:
            text: The text to pre-fill
        """
        try:
            command_input = self.app.query_one("#command-input", CommandInput)
            # The CommandInput widget may have an 'input' attribute (textual.widgets.Input)
            if hasattr(command_input, "input"):
                command_input.input.value = text
                command_input.input.focus()
            # Fallback: try setting value directly if possible
            elif hasattr(command_input, "value"):
                command_input.value = text
                command_input.focus()
        except Exception as e:
            logger.error(f"Error pre-filling command input: {e}", exc_info=True)



    async def _reconnect(self) -> None:
        """Reconnect to the server."""
        try:
            command_log = self.app.query_one("#command-log", CommandLog)

            # Disconnect first if connected
            if self.agent.client.connected:
                await self.agent.client.disconnect()

            # Wait a moment
            await asyncio.sleep(1)

            # Connect again
            await self.agent.client.connect()

            # Initialize GMCP
            if hasattr(self.agent, "aardwolf_gmcp"):
                await self.agent.aardwolf_gmcp.initialize()

            # Update the command log
            command_log.write("[bold green]Reconnected to server[/bold green]")
        except Exception as e:
            logger.error(f"Error reconnecting: {e}", exc_info=True)
            # Update the command log
            command_log = self.app.query_one("#command-log", CommandLog)
            command_log.write(f"[bold red]Error reconnecting: {e}[/bold red]")

    async def process_command(self, command: str) -> None:
        """Process a command through the agent.

        Args:
            command: The command to process
        """
        try:
            command_log = self.app.query_one("#command-log", CommandLog)

            # Check for special commands
            if command.lower() == "quit":
                self.app.exit()
                return

            # Handle special debug commands
            if await self._handle_special_commands(command):
                return

            # Add a debug message to confirm command processing
            logger.debug(f"Processing command: {command}")

            # Process the command through the agent
            # The response will be displayed automatically via the event system
            response = await self.agent.send_command(command)

            # Log the response length for debugging
            logger.debug(f"Received response for '{command}', length: {len(response)}")

            # Store the last response for map extraction
            if not hasattr(self.agent, "last_response"):
                self.agent.last_response = response
                logger.debug(f"Added last_response attribute to agent, length: {len(response)}")
            else:
                self.agent.last_response = response
                logger.debug(f"Updated agent.last_response, length: {len(response)}")

            # Force a GMCP update after each command to ensure stats are updated
            if hasattr(self.agent, "aardwolf_gmcp"):
                updates = self.agent.aardwolf_gmcp.update_from_gmcp()
                if updates:
                    logger.debug(f"GMCP updates after command: {', '.join(updates.keys())}")

                    # Force an immediate update of the widgets (with throttling)
                    if not getattr(self.app, '_updating_widgets', False):
                        asyncio.create_task(self.app._update_widgets_manually())

        except Exception as e:
            logger.error(f"Error processing command: {e}", exc_info=True)
            # The error will be displayed by the command log handler, but we'll also add it directly
            # to ensure it's displayed even if the handler isn't working
            command_log = self.app.query_one("#command-log", CommandLog)
            command_log.write(f"[bold red]Error: {e!s}[/bold red]")

    async def _handle_special_commands(self, command: str) -> bool:
        """Handle special debug and utility commands.

        Args:
            command: The command to check

        Returns:
            True if the command was handled, False otherwise
        """
        command_log = self.app.query_one("#command-log", CommandLog)

        # Check for "show all" command - GMCP data is received automatically
        if command.lower() == "show all":
            logger.info("Executing special 'show all' command - GMCP data is automatic")
            command_log.write("[dim]GMCP data is received automatically from server...[/dim]")

            # GMCP data is sent automatically by the server
            if hasattr(self.agent, "aardwolf_gmcp"):
                command_log.write("[bold green]GMCP data is received automatically[/bold green]")
                await asyncio.sleep(0.5)

                # Wait a moment for the data to be processed
                await asyncio.sleep(0.5)

                # Update the widgets
                await self.app.update_reactive_widgets()
                command_log.write("[bold green]Widgets updated with GMCP data[/bold green]")
            return True

        # Check for "debug gmcp" command to show raw GMCP data
        if command.lower() == "debug gmcp":
            logger.info("Executing special 'debug gmcp' command to show raw GMCP data")
            command_log.write("[bold]Showing raw GMCP data:[/bold]")

            if hasattr(self.agent, "aardwolf_gmcp"):
                # Get the raw GMCP data
                char_data = self.agent.aardwolf_gmcp.char_data
                room_data = self.agent.aardwolf_gmcp.room_data
                map_data = self.agent.aardwolf_gmcp.map_data

                # Display the data
                import json

                command_log.write("[bold]Character Data:[/bold]")
                command_log.write(json.dumps(char_data, indent=2))

                command_log.write("[bold]Room Data:[/bold]")
                command_log.write(json.dumps(room_data, indent=2))

                command_log.write("[bold]Map Data:[/bold]")
                command_log.write(json.dumps(map_data, indent=2))

                # Also show character data specifically
                char_data = self.agent.aardwolf_gmcp.get_character_data()
                command_log.write("[bold]Character Data:[/bold]")
                command_log.write(json.dumps(char_data, indent=2))

                # Force a GMCP update
                updates = self.agent.aardwolf_gmcp.update_from_gmcp()
                command_log.write(f"[bold]GMCP Updates:[/bold] {', '.join(updates.keys()) if updates else 'None'}")

                # Force an immediate update of the widgets (with throttling)
                if not getattr(self.app, '_updating_widgets', False):
                    asyncio.create_task(self.app._update_widgets_manually())
            else:
                command_log.write("[bold red]GMCP not available[/bold red]")
            return True

        # Check for "update stats" command to force a stats update
        if command.lower() == "update stats":
            logger.info("Executing special 'update stats' command to force a stats update")
            command_log.write("[bold]Forcing stats update via GMCP...[/bold]")

            # GMCP data is received automatically, just force widget update
            if hasattr(self.agent, "aardwolf_gmcp"):
                command_log.write("[dim]GMCP data is received automatically[/dim]")
                await asyncio.sleep(0.5)

            # Force a GMCP update
            if hasattr(self.agent, "aardwolf_gmcp"):
                updates = self.agent.aardwolf_gmcp.update_from_gmcp()
                command_log.write(f"[dim]GMCP updates: {', '.join(updates.keys()) if updates else 'None'}[/dim]")

                # Get the character data
                char_data = self.agent.aardwolf_gmcp.get_character_data()
                if "stats" in char_data:
                    command_log.write(f"[bold]Stats data: {char_data['stats']}[/bold]")

                # Force an immediate update of the widgets
                await self.app._update_widgets_manually()
                command_log.write("[bold green]Widgets updated[/bold green]")
            else:
                command_log.write("[bold red]GMCP not available[/bold red]")
            return True

        return False

    async def handle_filter_command(self, args: str) -> None:
        """Handle filter configuration commands.

        Args:
            args: The filter command arguments
        """
        command_log = self.app.query_one("#command-log", CommandLog)

        try:
            # Get the command log handler from the app
            handler = getattr(self.app, 'log_handler', None)
            if not handler:
                command_log.write("[bold red]Command log handler not found[/bold red]")
                return

            parts = args.split()
            if not parts:
                await self.show_filter_status()
                return

            subcommand = parts[0].lower()

            if subcommand == "level" and len(parts) == 2:
                level_name = parts[1].upper()
                level_map = {
                    'DEBUG': logging.DEBUG,
                    'INFO': logging.INFO,
                    'WARNING': logging.WARNING,
                    'ERROR': logging.ERROR,
                    'CRITICAL': logging.CRITICAL
                }

                if level_name in level_map:
                    handler.configure_filtering(min_level=level_map[level_name])
                    command_log.write(f"[bold green]Log level set to {level_name}[/bold green]")
                else:
                    command_log.write(f"[bold red]Invalid log level: {level_name}[/bold red]")
                    command_log.write("[bold cyan]Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL[/bold cyan]")

            elif subcommand == "debug" and len(parts) == 2:
                setting = parts[1].lower()
                if setting in ['on', 'true', 'yes', '1']:
                    handler.configure_filtering(filter_debug=True)
                    command_log.write("[bold green]Debug filtering enabled[/bold green]")
                elif setting in ['off', 'false', 'no', '0']:
                    handler.configure_filtering(filter_debug=False)
                    command_log.write("[bold green]Debug filtering disabled[/bold green]")
                else:
                    command_log.write(f"[bold red]Invalid setting: {setting}[/bold red]")
                    command_log.write("[bold cyan]Use: on/off, true/false, yes/no, 1/0[/bold cyan]")

            elif subcommand == "add" and len(parts) >= 2:
                pattern = " ".join(parts[1:])
                handler.add_debug_pattern(pattern)
                command_log.write(f"[bold green]Added debug filter pattern: {pattern}[/bold green]")

            elif subcommand == "remove" and len(parts) >= 2:
                pattern = " ".join(parts[1:])
                if handler.remove_debug_pattern(pattern):
                    command_log.write(f"[bold green]Removed debug filter pattern: {pattern}[/bold green]")
                else:
                    command_log.write(f"[bold yellow]Pattern not found: {pattern}[/bold yellow]")

            else:
                command_log.write("[bold red]Invalid filter command[/bold red]")
                command_log.write("[bold cyan]Usage:[/bold cyan]")
                command_log.write("  /filter level <ERROR|WARNING|INFO|DEBUG>")
                command_log.write("  /filter debug <on|off>")
                command_log.write("  /filter add <pattern>")
                command_log.write("  /filter remove <pattern>")

        except Exception as e:
            logger.error(f"Error handling filter command: {e}", exc_info=True)
            command_log.write(f"[bold red]Error executing filter command: {e}[/bold red]")

    async def show_filter_status(self) -> None:
        """Show current filter status."""
        command_log = self.app.query_one("#command-log", CommandLog)

        try:
            handler = getattr(self.app, 'log_handler', None)
            if not handler:
                command_log.write("[bold red]Command log handler not found[/bold red]")
                return

            status = handler.get_filter_status()

            command_log.write("[bold cyan]Current Log Filter Status:[/bold cyan]")
            command_log.write(f"  Minimum Level: [bold white]{status['min_level']}[/bold white]")
            command_log.write(f"  Debug Filtering: [bold white]{'Enabled' if status['filter_debug'] else 'Disabled'}[/bold white]")

            if status['custom_patterns']:
                command_log.write("  Custom Debug Patterns:")
                for pattern in status['custom_patterns']:
                    command_log.write(f"    - [dim]{pattern}[/dim]")
            else:
                command_log.write("  Custom Debug Patterns: [dim]None[/dim]")

        except Exception as e:
            logger.error(f"Error showing filter status: {e}", exc_info=True)
            command_log.write(f"[bold red]Error getting filter status: {e}[/bold red]")
