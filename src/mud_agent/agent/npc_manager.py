"""
NPC Manager for MUD Agent.

This module handles NPC/mob tracking, hunting, and related functionality.
"""

import asyncio
import logging
import re

import litellm

logger = logging.getLogger(__name__)


class NPCManager:
    """Manages NPC/mob tracking and hunting for the MUD agent."""

    def __init__(self, agent):
        """Initialize the NPC manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

    def extract_npcs_from_response(self, response: str) -> None:
        """Extract NPCs/mobs from the room description.

        Args:
            response: The response from the MUD server
        """
        try:
            # Clear the NPCs list in state manager
            if hasattr(self.agent, "state_manager"):
                self.agent.state_manager.npcs = []

            # Common patterns for NPCs/mobs in MUD games
            # 1. Lines that start with "A" or "An" or "The" followed by a name (common for mobs)
            # 2. Lines with "is here" or "are here" (common for NPCs and mobs)
            # 3. Lines with "stands here" or "sitting here" (common for NPCs)

            # Split the response into lines
            lines = response.strip().split("\n")

            # Skip the first line (room name) and any empty lines
            content_lines = [line.strip() for line in lines[1:] if line.strip()]

            # Common NPC/mob patterns
            npc_patterns = [
                r"^(?:A|An|The)\s+(.+?)\s+(?:is|are)\s+(?:standing|sitting|lying|floating|hovering|waiting|guarding|fighting|sleeping)\s+(?:here|nearby)",
                r"^(?:A|An|The)\s+(.+?)\s+(?:stands|sits|lies|floats|hovers|waits|guards|fights|sleeps)\s+(?:here|nearby)",
                r"^(.+?)\s+(?:is|are)\s+(?:standing|sitting|lying|floating|hovering|waiting|guarding|fighting|sleeping)\s+(?:here|nearby)",
                r"^(.+?)\s+(?:stands|sits|lies|floats|hovers|waits|guards|fights|sleeps)\s+(?:here|nearby)",
            ]

            for line in content_lines:
                # Skip lines that are likely part of the room description
                if line.startswith("[") or "Exits:" in line:
                    continue

                # Check each pattern
                for pattern in npc_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        npc_name = match.group(1).strip()
                        # Avoid duplicates
                        extracted_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                        if npc_name and npc_name not in extracted_npcs:
                            extracted_npcs.append(npc_name)
                            if hasattr(self.agent, "state_manager"):
                                self.agent.state_manager.npcs = extracted_npcs
                            self.logger.debug(f"Detected NPC/mob: {npc_name}")
                        break

            # If we couldn't extract NPCs with patterns, try using LiteLLM if available
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            if (
                not current_npcs
                and hasattr(self.agent, "model")
                and self.agent.model
            ):
                asyncio.create_task(self._extract_npcs_with_llm(response))

            self.logger.debug(
                f"Extracted NPCs/mobs: {current_npcs}"
            )
        except Exception as e:
            self.logger.error(f"Error extracting NPCs/mobs: {e}", exc_info=True)

    async def _extract_npcs_with_llm(self, response: str) -> None:
        """Use LiteLLM to extract NPCs/mobs from the room description.

        Args:
            response: The response from the MUD server
        """
        try:
            # Prepare a prompt for the LLM
            prompt = f"""
            Extract the names of all NPCs, monsters, or mobs from the following MUD game room description.
            Only return a comma-separated list of names, nothing else. If there are no NPCs or mobs, return "None".
            Do not include any thinking, reasoning, or explanations in your response.

            MUD ROOM DESCRIPTION:
            {response[:1000]}  # Limit to first 1000 chars to avoid token limits

            NPCs/MOBS:
            """

            # Call LiteLLM with the configured model
            llm_response = litellm.completion(
                model=self.agent.config.model.model_id,
                api_base=self.agent.config.model.api_base,
                api_key=self.agent.config.model.api_key,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
            )

            # Extract the NPCs from the response
            if (
                llm_response
                and hasattr(llm_response, "choices")
                and len(llm_response.choices) > 0
            ):
                npc_text = llm_response.choices[0].message.content.strip()

                # If the response is "None", there are no NPCs
                if npc_text.lower() == "none":
                    self.logger.debug("LLM found no NPCs/mobs in the room")
                    return

                # Check for thinking or explanations in the response
                if (
                    len(npc_text) > 100
                    or "<think>" in npc_text.lower()
                    or "let" in npc_text.lower()
                    or "\n" in npc_text
                ):
                    self.logger.warning(
                        f"LLM response appears to contain thinking rather than just NPC names: {npc_text[:100]}..."
                    )
                    return

                # Split by commas and clean up
                npc_names = [
                    name.strip() for name in npc_text.split(",") if name.strip()
                ]

                # Validate each NPC name - they should be relatively short and not contain sentences
                valid_npc_names = []
                for npc_name in npc_names:
                    # Skip if it's too long to be a name or contains sentence-like structures
                    if (
                        len(npc_name) > 50
                        or "." in npc_name
                        or len(npc_name.split()) > 5
                    ):
                        self.logger.warning(f"Skipping invalid NPC name: {npc_name}")
                        continue
                    valid_npc_names.append(npc_name)

                # Add to the NPCs list in state manager
                current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                for npc_name in valid_npc_names:
                    if npc_name and npc_name not in current_npcs:
                        current_npcs.append(npc_name)
                        if hasattr(self.agent, "state_manager"):
                            self.agent.state_manager.npcs = current_npcs
                        self.logger.debug(f"LLM extracted NPC/mob: {npc_name}")

                if valid_npc_names:
                    self.logger.debug(f"LLM extracted NPCs/mobs: {valid_npc_names}")
                else:
                    self.logger.debug("No valid NPCs/mobs extracted after validation")
        except Exception as e:
            self.logger.error(
                f"Error extracting NPCs/mobs with LLM: {e}", exc_info=True
            )

    async def find_and_hunt_npcs(
        self, npc_pattern: str, use_speedwalk: bool = False
    ) -> bool:
        """Find and hunt NPCs/mobs matching a pattern.

        This method searches for rooms containing NPCs/mobs matching the pattern,
        navigates to the closest one, and initiates combat.

        Args:
            npc_pattern: A substring to match in NPC/mob names
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if at least one NPC was found and hunted, False otherwise
        """
        try:
            self.logger.info(f"Searching for NPCs matching pattern: {npc_pattern}")

            # First check if there are any matching NPCs in the current room
            # Use room number if available, otherwise fall back to room name
            room_identifier = (
                str(self.agent.state_manager.room_num)
                if hasattr(self.agent, 'state_manager') and self.agent.state_manager.room_num != 0
                else (
                    self.agent.room_manager.current_room
                    if isinstance(self.agent.room_manager.current_room, str)
                    else (
                        (self.agent.room_manager.current_room or {}).get("name", "")
                    )
                )
            )
            npcs_in_current_room = (
                await self.agent.knowledge_graph.find_npcs_in_room(
                    room_identifier
                )
            )
            for npc in npcs_in_current_room:
                npc_name = npc.get("name", "")
                if npc_pattern.lower() in npc_name.lower():
                    self.logger.info(f"Found matching NPC '{npc_name}' in current room")
                    # Attack the NPC
                    await self.agent.send_command(f"kill {npc_name}")
                    return True

            # Try using MUD-specific commands to find the NPC
            return await self._find_npc_with_mud_commands(
                npc_pattern, use_speedwalk
            )
        except Exception as e:
            self.logger.error(f"Error hunting NPCs: {e}", exc_info=True)
            return False

    async def _find_npc_with_mud_commands(
        self, npc_pattern: str, use_speedwalk: bool = False
    ) -> bool:
        """Use MUD-specific commands to find and hunt NPCs when the knowledge graph doesn't have enough information.

        This method uses commands like 'hunt', 'where', and 'scan' to locate NPCs/mobs.

        Args:
            npc_pattern: A substring to match in NPC/mob names
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if at least one NPC was found and hunted, False otherwise
        """
        try:
            self.logger.info(
                f"Using MUD commands to find NPC matching pattern: {npc_pattern}"
            )

            # Try the 'where' command first to get a list of matching NPCs and their locations
            self.logger.info(f"Using 'where {npc_pattern}' command to locate NPCs")
            where_response = await self.agent.send_command(f"where {npc_pattern}")

            # Check if the 'where' command was successful and provided useful information
            if (
                "No one by that name" not in where_response
                and "not found" not in where_response.lower()
            ):
                # Extract location information from the 'where' response
                # This is MUD-specific and may need to be adjusted based on the MUD's output format
                locations = self._extract_locations_from_where(where_response)

                if locations:
                    self.logger.info(
                        f"Found potential locations from 'where' command: {locations}"
                    )

                    # Try to navigate to the first location
                    for location in locations:
                        # Try to find a path to the location
                        # This might involve using 'goto' or 'run' commands if the MUD supports them
                        if "in " in location.lower():
                            # Extract the area name
                            area = location.split("in ", 1)[1].strip()
                            self.logger.info(f"Attempting to navigate to area: {area}")

                            # Try using a 'goto' or 'run' command if the MUD supports it
                            if use_speedwalk:
                                goto_response = await self.agent.send_command(
                                    f"goto {area}"
                                )
                                if (
                                    "You can't go that way" not in goto_response
                                    and "What?" not in goto_response
                                ):
                                    self.logger.info(
                                        f"Successfully navigated to area: {area}"
                                    )
                                    # Look around to update room information
                                    await self.agent.send_command("look")

                                    # Check if there are matching NPCs in this room
                                    if await self._check_and_attack_matching_npc(
                                        npc_pattern
                                    ):
                                        return True

                            # If we couldn't navigate directly, try using the 'hunt' command
                            hunt_response = await self.agent.send_command(
                                f"hunt {npc_pattern}"
                            )
                            if (
                                "You can't find a trail" not in hunt_response
                                and "You can't hunt" not in hunt_response
                            ):
                                # The hunt command was successful, follow the direction
                                direction = self._extract_direction_from_hunt(
                                    hunt_response
                                )
                                if direction:
                                    self.logger.info(
                                        f"Hunt indicates NPC is {direction}"
                                    )
                                    # Move in that direction
                                    await self.agent.send_command(direction)
                                    # Look around to update room information
                                    await self.agent.send_command("look")

                                    # Check if there are matching NPCs in this room
                                    if await self._check_and_attack_matching_npc(
                                        npc_pattern
                                    ):
                                        return True

                                    # If not, try hunting again (up to 5 times)
                                    return await self._follow_hunt_trail(npc_pattern, 5)

            # If 'where' didn't work, try the 'hunt' command directly
            self.logger.info(f"Using 'hunt {npc_pattern}' command to track NPCs")
            hunt_response = await self.agent.send_command(f"hunt {npc_pattern}")

            if (
                "You can't find a trail" not in hunt_response
                and "You can't hunt" not in hunt_response
            ):
                # The hunt command was successful, follow the direction
                direction = self._extract_direction_from_hunt(hunt_response)
                if direction:
                    self.logger.info(f"Hunt indicates NPC is {direction}")
                    # Move in that direction
                    await self.agent.send_command(direction)
                    # Look around to update room information
                    await self.agent.send_command("look")

                    # Check if there are matching NPCs in this room
                    if await self._check_and_attack_matching_npc(npc_pattern):
                        return True

                    # If not, try hunting again (up to 10 times)
                    return await self._follow_hunt_trail(npc_pattern, 10)

            # If hunt didn't work, try the 'scan' command to look for NPCs in adjacent rooms
            self.logger.info("Using 'scan' command to look for NPCs in adjacent rooms")
            scan_response = await self.agent.send_command("scan")

            # Extract directions where NPCs matching the pattern might be
            directions = self._extract_directions_from_scan(scan_response, npc_pattern)

            if directions:
                self.logger.info(
                    f"Scan found potential NPCs in directions: {directions}"
                )

                # Try each direction
                for direction in directions:
                    self.logger.info(f"Moving {direction} based on scan results")
                    await self.agent.send_command(direction)
                    # Look around to update room information
                    await self.agent.send_command("look")

                    # Check if there are matching NPCs in this room
                    if await self._check_and_attack_matching_npc(npc_pattern):
                        return True

                    # If not, go back to the original room
                    opposite_direction = self._get_opposite_direction(direction)
                    if opposite_direction:
                        await self.agent.send_command(opposite_direction)
                        await self.agent.send_command("look")

            # If all else fails, try random exploration (up to 5 rooms)
            self.logger.info("No specific location found, trying random exploration")
            return await self._explore_randomly(npc_pattern, 5)

        except Exception as e:
            self.logger.error(
                f"Error finding NPC with MUD commands: {e}", exc_info=True
            )
            return False

    async def _check_and_attack_matching_npc(self, npc_pattern: str) -> bool:
        """Check if there are NPCs matching the pattern in the current room and attack if found.

        Args:
            npc_pattern: A substring to match in NPC/mob names

        Returns:
            bool: True if a matching NPC was found and attacked, False otherwise
        """
        try:
            # Check current room NPCs from state manager
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            for npc in current_npcs:
                if npc_pattern.lower() in npc.lower():
                    self.logger.info(f"Found matching NPC '{npc}' in room, attacking")
                    await self.agent.send_command(f"kill {npc}")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking and attacking NPC: {e}", exc_info=True)
            return False

    async def _follow_hunt_trail(self, npc_pattern: str, max_steps: int) -> bool:
        """Follow a hunt trail to find an NPC.

        Args:
            npc_pattern: A substring to match in NPC/mob names
            max_steps: Maximum number of steps to follow the trail

        Returns:
            bool: True if the NPC was found and attacked, False otherwise
        """
        try:
            steps_taken = 0

            while steps_taken < max_steps:
                # Check if we've found the NPC in the current room
                if await self._check_and_attack_matching_npc(npc_pattern):
                    return True

                # Try hunting again
                hunt_response = await self.agent.send_command(f"hunt {npc_pattern}")

                # Check if hunt was successful
                if (
                    "You can't find a trail" in hunt_response
                    or "You can't hunt" in hunt_response
                ):
                    self.logger.warning("Lost the trail while hunting")
                    return False

                # Extract direction from hunt response
                direction = self._extract_direction_from_hunt(hunt_response)
                if not direction:
                    self.logger.warning(
                        "Could not determine direction from hunt response"
                    )
                    return False

                # Move in the indicated direction
                self.logger.info(f"Following hunt trail: moving {direction}")
                move_response = await self.agent.send_command(direction)

                # Check if movement was successful
                if "You can't go that way" in move_response or "What?" in move_response:
                    self.logger.warning(f"Failed to move {direction}: {move_response}")
                    return False

                # Look around to update room information
                await self.agent.send_command("look")

                steps_taken += 1

            # Check one last time if we've found the NPC
            return await self._check_and_attack_matching_npc(npc_pattern)

        except Exception as e:
            self.logger.error(f"Error following hunt trail: {e}", exc_info=True)
            return False

    async def _explore_randomly(self, npc_pattern: str, max_rooms: int) -> bool:
        """Explore randomly to find NPCs matching the pattern.

        Args:
            npc_pattern: A substring to match in NPC/mob names
            max_rooms: Maximum number of rooms to explore

        Returns:
            bool: True if a matching NPC was found and attacked, False otherwise
        """
        try:
            import random

            rooms_explored = 0
            path_taken = []  # Track the path to be able to return

            while rooms_explored < max_rooms:
                # Check if we've found the NPC in the current room
                if await self._check_and_attack_matching_npc(npc_pattern):
                    return True

                # Get available exits
                if not self.agent.room_manager.current_exits:
                    self.logger.warning("No exits available for random exploration")
                    break

                # Choose a random exit
                direction = random.choice(self.agent.room_manager.current_exits)
                self.logger.info(f"Random exploration: moving {direction}")

                # Move in the chosen direction
                move_response = await self.agent.send_command(direction)

                # Check if movement was successful
                if "You can't go that way" in move_response or "What?" in move_response:
                    self.logger.warning(f"Failed to move {direction}: {move_response}")
                    continue

                # Record the direction taken
                path_taken.append(direction)

                # Look around to update room information
                await self.agent.send_command("look")

                rooms_explored += 1

            # Return to the starting point
            for direction in reversed(path_taken):
                opposite = self._get_opposite_direction(direction)
                if opposite:
                    await self.agent.send_command(opposite)

            return False

        except Exception as e:
            self.logger.error(f"Error during random exploration: {e}", exc_info=True)
            return False

    def _extract_locations_from_where(self, where_response: str) -> list[str]:
        """Extract location information from the 'where' command response.

        Args:
            where_response: The response from the 'where' command

        Returns:
            List[str]: A list of location descriptions
        """
        try:
            locations = []

            # Split the response into lines
            lines = where_response.strip().split("\n")

            for line in lines:
                # Skip header lines or empty lines
                if (
                    not line.strip()
                    or "Players near you" in line
                    or "----------------" in line
                ):
                    continue

                # Look for location patterns like "Name is in Location"
                if " is in " in line or ("(" in line and ")" in line):
                    locations.append(line.strip())

            return locations

        except Exception as e:
            self.logger.error(
                f"Error extracting locations from 'where' response: {e}", exc_info=True
            )
            return []

    def _extract_direction_from_hunt(self, hunt_response: str) -> str | None:
        """Extract the direction from a hunt command response.

        Args:
            hunt_response: The response from the hunt command

        Returns:
            Optional[str]: The direction to move, or None if not found
        """
        try:
            # Common direction patterns in hunt responses
            direction_patterns = [
                r"leads (north|south|east|west|northeast|northwest|southeast|southwest|up|down)",
                r"track leads (north|south|east|west|northeast|northwest|southeast|southwest|up|down)",
                r"trail leads (north|south|east|west|northeast|northwest|southeast|southwest|up|down)",
                r"tracks? (?:go|goes|lead|leads) (north|south|east|west|northeast|northwest|southeast|southwest|up|down)",
                r"You sense .+ is (north|south|east|west|northeast|northwest|southeast|southwest|up|down)",
            ]

            for pattern in direction_patterns:
                match = re.search(pattern, hunt_response, re.IGNORECASE)
                if match:
                    return match.group(1).lower()

            return None

        except Exception as e:
            self.logger.error(
                f"Error extracting direction from hunt response: {e}", exc_info=True
            )
            return None

    def _extract_directions_from_scan(
        self, scan_response: str, npc_pattern: str
    ) -> list[str]:
        """Extract directions from a scan command response where NPCs matching the pattern might be.

        Args:
            scan_response: The response from the scan command
            npc_pattern: A substring to match in NPC/mob names

        Returns:
            List[str]: A list of directions where matching NPCs might be
        """
        try:
            directions = []

            # Split the response into sections by direction
            direction_sections = re.split(
                r"\b(north|south|east|west|northeast|northwest|southeast|southwest|up|down):",
                scan_response,
                flags=re.IGNORECASE,
            )

            # Process each section
            for i in range(1, len(direction_sections), 2):
                if i + 1 < len(direction_sections):
                    direction = direction_sections[i].lower()
                    content = direction_sections[i + 1]

                    # Check if the content contains the NPC pattern
                    if npc_pattern.lower() in content.lower():
                        directions.append(direction)

            return directions

        except Exception as e:
            self.logger.error(
                f"Error extracting directions from scan response: {e}", exc_info=True
            )
            return []

    def _get_opposite_direction(self, direction: str) -> str | None:
        """Get the opposite direction.

        Args:
            direction: The original direction

        Returns:
            Optional[str]: The opposite direction, or None if not found
        """
        direction_map = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
            "northeast": "southwest",
            "southwest": "northeast",
            "northwest": "southeast",
            "southeast": "northwest",
            "up": "down",
            "down": "up",
            "n": "s",
            "s": "n",
            "e": "w",
            "w": "e",
            "ne": "sw",
            "sw": "ne",
            "nw": "se",
            "se": "nw",
            "u": "d",
            "d": "u",
        }

        return direction_map.get(direction.lower())
