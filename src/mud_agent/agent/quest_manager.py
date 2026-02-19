"""
Quest Manager for MUD Agent.

This module handles quest-related functionality for the MUD agent, including
quest acceptance, tracking, and completion.
"""

import asyncio
import logging
import re
import subprocess
import sys
import time

# Constants for quest management
DEFAULT_QUEST_COOLDOWN = 120  # Default 2 minutes cooldown in seconds
MOVEMENT_DELAY = 1.0  # Delay between movement commands in seconds
SECONDS_PER_MINUTE = 60  # Number of seconds in a minute
ZERO = 0  # Zero constant for comparisons

logger = logging.getLogger(__name__)


class QuestManager:
    """Manages quest-related functionality for the MUD agent."""

    def __init__(self, agent):
        """Initialize the quest manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        # Quest state
        self.current_quest = None
        self.quest_target = None
        self.quest_area = None
        self.quest_timer = 0
        self.quest_completed = False

        # Questor information
        self.questor_name = "questor"  # Default name, can be updated
        self.questor_room = None

        # Quest cooldown tracking
        self.last_quest_time = ZERO
        self.quest_cooldown = (
            DEFAULT_QUEST_COOLDOWN  # Default cooldown, can be adjusted
        )
        self.next_quest_available_time = ZERO
        self.quest_time_checked = False

    async def setup(self) -> None:
        """Set up the quest manager."""
        # Subscribe to incoming data events from the client
        if hasattr(self.agent, "client") and hasattr(self.agent.client, "events"):
            self.agent.client.events.on("data", self._handle_incoming_data)
            self.logger.info("QuestManager subscribed to client data events")
        else:
            self.logger.warning("Agent client or events not available for subscription")

    async def _handle_incoming_data(self, data: str) -> None:
        """Handle incoming data from the MUD."""
        try:
            # Strip ANSI codes for clean matching
            clean_data = re.sub(r'\x1b\[[0-9;]*m', '', data)

            # Log that we received data (for debugging "not used" claims)
            if len(clean_data) > 0:
                 # Only log first 50 chars to avoid spam, but prove life
                self.logger.debug(f"QuestManager received data: {clean_data[:50]}...")

            if "You may quest again" in clean_data:
                self.logger.info("Quest available alert triggered!")
                self._play_alert_sound()
        except Exception as e:
            self.logger.error(f"Error handling incoming data in QuestManager: {e}")

    def _play_alert_sound(self) -> None:
        """Play a system alert sound in a non-blocking way."""
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
            elif sys.platform == "win32":  # Windows
                # Use PowerShell to play a system sound
                subprocess.Popen(["powershell", "-c", "(New-Object Media.SoundPlayer 'C:\\Windows\\Media\\notify.wav').PlaySync();"])
            elif sys.platform.startswith("linux"):  # Linux
                # Try common players
                try:
                    subprocess.Popen(["aplay", "/usr/share/sounds/alsa/Front_Center.wav"], stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    try:
                        subprocess.Popen(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        self.logger.warning("No suitable audio player (aplay/paplay) found for Linux alert.")
        except Exception as e:
            self.logger.error(f"Failed to play alert sound: {e}")

    async def find_questor(self, use_speedwalk: bool = True) -> bool:
        """Find and navigate to the questor NPC.

        Args:
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if successfully navigated to questor, False otherwise
        """
        try:
            self.logger.info(
                f"Attempting to find and navigate to questor '{self.questor_name}'"
            )

            # First check if we already know where the questor is
            if not self.questor_room:
                # Try to find the questor in the knowledge graph
                questor_room = (
                    await self.agent.knowledge_graph.find_room_with_npc(
                        self.questor_name
                    )
                )
                if questor_room:
                    self.questor_room = questor_room.get("name")
                    self.logger.info(f"Found questor in room: {self.questor_room}")

            # If we know the questor's room, navigate there
            if self.questor_room:
                path_info = await self.agent.knowledge_graph.find_path_between_rooms(
                    start_room_id=self.agent.state_manager.room_num,
                    end_room_identifier=self.questor_room
                )

                if not path_info or not path_info.get("path"):
                    self.logger.warning(
                        f"Could not find path to questor room '{self.questor_room}'"
                    )
                    return False

                path = path_info["path"]
                self.logger.info(f"Found path to questor: {path}")

                # Navigate to the questor's room
                if use_speedwalk:
                    speedwalk_cmd = self.agent.room_manager.generate_speedwalk_command(
                        path
                    )
                    if speedwalk_cmd:
                        self.logger.info(f"Using speedwalk command: {speedwalk_cmd}")
                        response = await self.agent.send_command(speedwalk_cmd)

                        # Check if the speedwalk was successful
                        if "You can't go that way" in response or "What?" in response:
                            self.logger.warning(f"Speedwalk failed: {response}")
                            self.logger.info("Falling back to step-by-step navigation")
                            use_speedwalk = False
                        else:
                            # We've reached the room, now look around
                            await self.agent.send_command("look")

                # Navigate step by step if speedwalk is not used or failed
                if not use_speedwalk:
                    for direction in path:
                        self.logger.info(f"Moving {direction}")
                        response = await self.agent.send_command(direction)

                        # Check if the movement was successful
                        if "You can't go that way" in response or "What?" in response:
                            self.logger.warning(
                                f"Failed to move {direction}: {response}"
                            )
                            return False

                        # Wait a bit between movements to avoid flooding the server
                        await asyncio.sleep(MOVEMENT_DELAY)

                    # Make sure we have the latest room info
                    await self.agent.send_command("look")

                # Verify we're in the right room
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
                npcs_in_room = (
                    await self.agent.knowledge_graph.find_npcs_in_room(
                        room_identifier
                    )
                )
                for npc in npcs_in_room:
                    if npc.get("name", "").lower() == self.questor_name.lower():
                        self.logger.info(
                            f"Successfully navigated to questor '{self.questor_name}'"
                        )
                        return True

                self.logger.warning(
                    f"Reached the room but questor '{self.questor_name}' is not here"
                )
                return False
            else:
                # If we don't know where the questor is, try to find them using the NPC manager
                return await self.agent.find_and_navigate_to_npc(
                    self.questor_name, use_speedwalk
                )

        except Exception as e:
            self.logger.error(f"Error finding questor: {e}", exc_info=True)
            return False

    async def request_quest(self) -> bool:
        """Request a new quest from the questor.

        Returns:
            bool: True if a quest was successfully obtained, False otherwise
        """
        try:
            self.logger.info("Requesting a new quest from questor")

            # First check if we're in the same room as the questor
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
            npcs_in_room = await self.agent.knowledge_graph.find_npcs_in_room(
                room_identifier
            )
            questor_present = False

            for npc in npcs_in_room:
                if npc.get("name", "").lower() == self.questor_name.lower():
                    questor_present = True
                    break

            if not questor_present:
                self.logger.warning(
                    f"Questor '{self.questor_name}' is not in the current room"
                )
                return False

            # Request a quest
            response = await self.agent.send_command("quest")

            # Check if we got a quest
            if "You are already on a quest" in response:
                self.logger.info("Already on a quest")
                # Extract quest details from the response
                await self._extract_quest_details(response)
                return True
            elif "You may not go on another quest yet" in response:
                self.logger.info(
                    "Quest cooldown active, cannot request a new quest yet"
                )
                # Try to extract the cooldown time
                cooldown_match = re.search(
                    r"You may not go on another quest for (\d+) minutes", response
                )
                if cooldown_match:
                    minutes = int(cooldown_match.group(1))
                    self.quest_cooldown = (
                        minutes * SECONDS_PER_MINUTE
                    )  # Convert to seconds
                    self.logger.info(f"Quest cooldown: {minutes} minutes")
                return False
            elif (
                "quest accepted" in response.lower()
                or "you have accepted the quest" in response.lower()
            ):
                self.logger.info("New quest accepted")
                # Extract quest details from the response
                await self._extract_quest_details(response)
                return True
            else:
                # Try the quest request command
                response = await self.agent.send_command("quest request")

                if (
                    "quest accepted" in response.lower()
                    or "you have accepted the quest" in response.lower()
                ):
                    self.logger.info("New quest accepted")
                    # Extract quest details from the response
                    await self._extract_quest_details(response)
                    return True
                else:
                    self.logger.warning("Failed to get a quest")
                    return False

        except Exception as e:
            self.logger.error(f"Error requesting quest: {e}", exc_info=True)
            return False

    async def _extract_quest_details(self, response: str) -> None:
        """Extract quest details from the quest response.

        Args:
            response: The response from the quest command
        """
        try:
            # Extract quest name/description
            quest_match = re.search(r"quest:?\s+([^\.]+)", response, re.IGNORECASE)
            if quest_match:
                self.current_quest = quest_match.group(1).strip()
                self.logger.info(f"Current quest: {self.current_quest}")

            # Extract quest target (mob to kill)
            target_match = re.search(
                r"kill\s+(?:the\s+)?([^\.]+)", response, re.IGNORECASE
            )
            if target_match:
                self.quest_target = target_match.group(1).strip()
                self.logger.info(f"Quest target: {self.quest_target}")

            # Extract quest area if mentioned
            area_match = re.search(r"in\s+(?:the\s+)?([^\.]+)", response, re.IGNORECASE)
            if area_match:
                self.quest_area = area_match.group(1).strip()
                self.logger.info(f"Quest area: {self.quest_area}")

            # Reset quest completion flag
            self.quest_completed = False

        except Exception as e:
            self.logger.error(f"Error extracting quest details: {e}", exc_info=True)

    async def hunt_quest_target(self, use_speedwalk: bool = True) -> bool:
        """Find and hunt the quest target.

        Args:
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if the target was successfully hunted, False otherwise
        """
        try:
            if not self.quest_target:
                self.logger.warning("No quest target to hunt")
                return False

            self.logger.info(f"Hunting quest target: {self.quest_target}")

            # First check if we're already in the same room as the quest target
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            for npc in current_npcs:
                if self.quest_target.lower() in npc.lower():
                    self.logger.info(f"Found quest target '{npc}' in current room")
                    # Attack the target
                    await self.agent.send_command(f"kill {npc}")
                    return True

            # If we have quest area information, try to navigate there first
            if self.quest_area:
                self.logger.info(
                    f"Attempting to navigate to quest area: {self.quest_area}"
                )

                # Try using a 'goto' or 'run' command if the MUD supports it
                if use_speedwalk:
                    goto_response = await self.agent.send_command(
                        f"goto {self.quest_area}"
                    )
                    if (
                        "You can't go that way" not in goto_response
                        and "What?" not in goto_response
                    ):
                        self.logger.info(
                            f"Successfully navigated to quest area: {self.quest_area}"
                        )
                        # Look around to update room information
                        await self.agent.send_command("look")

                        # Check if the quest target is in this room
                        current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                        for npc in current_npcs:
                            if self.quest_target.lower() in npc.lower():
                                self.logger.info(f"Found quest target '{npc}' in room")
                                # Attack the target
                                await self.agent.send_command(f"kill {npc}")
                                return True

            # Use the NPC manager to find and hunt the target
            # This will use both knowledge graph and MUD-specific commands
            return await self.agent.find_and_hunt_npcs(self.quest_target, use_speedwalk)

        except Exception as e:
            self.logger.error(f"Error hunting quest target: {e}", exc_info=True)
            return False

    async def complete_quest(self) -> bool:
        """Complete the current quest by returning to the questor.

        Returns:
            bool: True if the quest was successfully completed, False otherwise
        """
        try:
            self.logger.info("Attempting to complete the current quest")

            # First navigate to the questor
            if not await self.find_questor():
                self.logger.warning("Failed to find questor to complete quest")
                return False

            # Complete the quest
            response = await self.agent.send_command("quest complete")

            # Check if the quest was completed
            if (
                "quest completed" in response.lower()
                or "you have completed the quest" in response.lower()
            ):
                self.logger.info("Quest completed successfully")
                self.current_quest = None
                self.quest_target = None
                self.quest_area = None
                self.quest_completed = True
                return True
            else:
                self.logger.warning("Failed to complete quest")
                return False

        except Exception as e:
            self.logger.error(f"Error completing quest: {e}", exc_info=True)
            return False

    async def check_quest_status(self) -> tuple[bool, str]:
        """Check the status of the current quest.

        Returns:
            Tuple[bool, str]: (has_active_quest, status_message)
        """
        try:
            # Check if we have quest information already
            if self.current_quest:
                return True, f"Active quest: {self.current_quest}"

            # Request quest information
            response = await self.agent.send_command("quest")

            if "You are not currently on a quest" in response:
                self.logger.info("No active quest")
                return False, "No active quest"
            elif "You are already on a quest" in response:
                self.logger.info("Active quest found")
                # Extract quest details
                await self._extract_quest_details(response)
                return True, f"Active quest: {self.current_quest}"
            else:
                self.logger.warning("Unclear quest status")
                return False, "Unclear quest status"

        except Exception as e:
            self.logger.error(f"Error checking quest status: {e}", exc_info=True)
            return False, f"Error: {e!s}"

    async def recall_to_town(self) -> bool:
        """Use the recall command to return to town.

        Returns:
            bool: True if recall was successful, False otherwise
        """
        try:
            self.logger.info("Recalling to town")

            # Use the recall command
            response = await self.agent.send_command("recall")

            # Check if recall was successful
            if "You close your eyes" in response or "You are engulfed" in response:
                self.logger.info("Recall successful")
                # Look around to update room information
                await self.agent.send_command("look")
                return True
            else:
                self.logger.warning("Recall failed")
                return False

        except Exception as e:
            self.logger.error(f"Error recalling to town: {e}", exc_info=True)
            return False

    async def check_quest_time(self) -> tuple[bool, int, str]:
        """Check the time until the next quest is available.

        Returns:
            Tuple[bool, int, str]: (can_quest_now, seconds_until_available, status_message)
        """
        try:
            self.logger.debug("Checking quest time")

            # If we already know we're in cooldown and have a calculated time
            current_time = time.time()
            if (
                self.next_quest_available_time > ZERO
                and current_time < self.next_quest_available_time
            ):
                seconds_remaining = int(self.next_quest_available_time - current_time)
                minutes_remaining = seconds_remaining // SECONDS_PER_MINUTE
                seconds_mod = seconds_remaining % SECONDS_PER_MINUTE

                status_message = (
                    f"Next quest available in {minutes_remaining}m {seconds_mod}s"
                )
                self.logger.debug(status_message)
                return False, seconds_remaining, status_message

            # If we think we can quest now based on our tracking, or we haven't checked yet
            if (
                not self.quest_time_checked
                or current_time >= self.next_quest_available_time
            ):
                # Send the quest time command to check
                response = await self.agent.send_command("quest time")
                self.quest_time_checked = True

                # Log the full response for debugging
                self.logger.debug(f"Quest time response: {response}")

                # Check if we can quest now
                if "You may go on another quest now" in response:
                    self.logger.info("Quest is available now")
                    self.next_quest_available_time = ZERO
                    return True, ZERO, "Quest available now"

                # Check for the specific format we're seeing: "There are X minutes remaining until you can go on another quest."
                specific_match = re.search(
                    r"There are (\d+) minutes remaining until you can go on another quest",
                    response,
                )
                if specific_match:
                    minutes = int(specific_match.group(1))
                    seconds = minutes * SECONDS_PER_MINUTE

                    # Update our tracking
                    self.next_quest_available_time = current_time + seconds

                    status_message = f"Next quest in {minutes}m"
                    self.logger.info(status_message)
                    return False, seconds, status_message

                # Check for cooldown time (standard format)
                cooldown_match = re.search(
                    r"You may go on another quest in (\d+) minutes", response
                )
                if cooldown_match:
                    minutes = int(cooldown_match.group(1))
                    seconds = minutes * SECONDS_PER_MINUTE

                    # Update our tracking
                    self.next_quest_available_time = current_time + seconds

                    status_message = f"Next quest in {minutes}m"
                    self.logger.info(status_message)
                    return False, seconds, status_message

                # Check for more precise cooldown time (some MUDs show minutes and seconds)
                precise_match = re.search(
                    r"You may go on another quest in (\d+) minutes and (\d+) seconds",
                    response,
                )
                if precise_match:
                    minutes = int(precise_match.group(1))
                    seconds = int(precise_match.group(2)) + (
                        minutes * SECONDS_PER_MINUTE
                    )

                    # Update our tracking
                    self.next_quest_available_time = current_time + seconds

                    status_message = (
                        f"Next quest in {minutes}m {seconds % SECONDS_PER_MINUTE}s"
                    )
                    self.logger.info(status_message)
                    return False, seconds, status_message

                # If we couldn't parse the response but it contains "another quest" and a time reference
                if "another quest" in response and (
                    "minute" in response or "second" in response
                ):
                    # Use a default cooldown time
                    self.logger.warning(
                        f"Could not parse quest time from response: {response}"
                    )
                    self.next_quest_available_time = current_time + self.quest_cooldown

                    minutes = self.quest_cooldown // SECONDS_PER_MINUTE
                    seconds_mod = self.quest_cooldown % SECONDS_PER_MINUTE
                    status_message = f"Next quest available in approximately {minutes}m {seconds_mod}s"
                    return False, self.quest_cooldown, status_message

                # If the response doesn't match any expected patterns
                self.logger.warning(f"Unexpected response to quest time: {response}")
                return True, ZERO, "Quest status unclear, assuming available"

            # Default case - if we've reached here, we should be able to quest
            return True, ZERO, "Quest should be available now"

        except Exception as e:
            self.logger.error(f"Error checking quest time: {e}", exc_info=True)
            return False, self.quest_cooldown, f"Error checking quest time: {e!s}"

    def force_quest_time_check(self) -> None:
        """Force a quest time check by resetting the quest_time_checked flag.

        This will cause the next call to check_quest_time to actually send the quest time command.
        """
        self.quest_time_checked = False
        self.logger.debug(
            "Forced quest time check by resetting quest_time_checked flag"
        )

    async def check_quest_info(self) -> tuple[bool, str, dict]:
        """Check detailed information about the current quest.

        This sends the 'quest info' command to get detailed information about the current quest.

        Returns:
            Tuple[bool, str, dict]: (has_quest_info, message, quest_details)
                has_quest_info: True if quest info was found, False otherwise
                message: A status message
                quest_details: A dictionary with quest details (name, target, area, timer, etc.)
        """
        try:
            self.logger.debug("Checking quest info")

            # Send the quest info command
            response = await self.agent.send_command("quest info")

            # Log the full response for debugging
            self.logger.debug(f"Quest info response: {response}")

            # Check if we're on a quest
            if "You are not currently on a quest" in response:
                self.logger.info("Not currently on a quest")
                return False, "Not on a quest", {}

            # Extract quest details
            quest_details = {}

            # Try to extract quest name
            quest_name_match = re.search(r"Quest:\s+([^\n]+)", response)
            if quest_name_match:
                quest_details["name"] = quest_name_match.group(1).strip()
                self.current_quest = quest_details["name"]
                self.logger.debug(f"Extracted quest name: {quest_details['name']}")

            # Try to extract quest target
            target_match = re.search(r"Target:\s+([^\n]+)", response)
            if target_match:
                quest_details["target"] = target_match.group(1).strip()
                self.quest_target = quest_details["target"]
                self.logger.debug(f"Extracted quest target: {quest_details['target']}")

            # Try to extract quest area
            area_match = re.search(r"Area:\s+([^\n]+)", response)
            if area_match:
                quest_details["area"] = area_match.group(1).strip()
                self.quest_area = quest_details["area"]
                self.logger.debug(f"Extracted quest area: {quest_details['area']}")

            # Try to extract quest timer
            timer_match = re.search(r"Time remaining:\s+([^\n]+)", response)
            if timer_match:
                quest_details["timer"] = timer_match.group(1).strip()
                # Try to convert timer to seconds
                timer_parts = quest_details["timer"].split()
                total_seconds = 0
                for i in range(0, len(timer_parts), 2):
                    if i + 1 < len(timer_parts):
                        value = int(timer_parts[i])
                        unit = timer_parts[i + 1].lower()
                        if "hour" in unit:
                            total_seconds += value * 3600  # 60 minutes * 60 seconds
                        elif "minute" in unit:
                            total_seconds += value * SECONDS_PER_MINUTE
                        elif "second" in unit:
                            total_seconds += value
                quest_details["timer_seconds"] = total_seconds
                self.quest_timer = total_seconds
                self.logger.debug(
                    f"Extracted quest timer: {quest_details['timer']} ({total_seconds} seconds)"
                )

            # Try to extract quest description
            desc_match = re.search(r"Description:\s+([^\n]+)", response)
            if desc_match:
                quest_details["description"] = desc_match.group(1).strip()
                self.logger.debug(
                    f"Extracted quest description: {quest_details['description']}"
                )

            # Check if we extracted any quest details
            if quest_details:
                self.logger.info(f"Successfully extracted quest info: {quest_details}")
                return (
                    True,
                    f"Quest: {quest_details.get('name', 'Unknown')}",
                    quest_details,
                )
            else:
                self.logger.warning("Could not extract quest details from response")
                return False, "Could not extract quest details", {}

        except Exception as e:
            self.logger.error(f"Error checking quest info: {e}", exc_info=True)
            return False, f"Error checking quest info: {e!s}", {}

    def on_tick(self, tick_count: int) -> None:
        """Handle a game tick event.

        This is called by the tick manager when a game tick occurs.

        Args:
            tick_count: The current tick count
        """
        try:
            # Reset the quest time checked flag periodically to force a fresh check
            if (
                tick_count % 12 == 0
            ):  # Check approximately every 12 ticks (about 1 minute with 5-second ticks)
                self.quest_time_checked = False
                self.logger.debug(f"Reset quest time checked flag on tick {tick_count}")

                # Check if we're on a quest and need to update quest info
                if self.current_quest:
                    self.logger.debug(
                        f"On tick {tick_count}: Currently on quest '{self.current_quest}', will check quest info soon"
                    )
                    # We'll check quest info in the next async tick handler

                # Update quest time info in state manager if available
                if hasattr(self.agent, "state_manager") and hasattr(
                    self.agent.state_manager, "quest_time_info"
                ):
                    # Calculate time remaining
                    current_time = time.time()
                    if (
                        self.next_quest_available_time > ZERO
                        and current_time < self.next_quest_available_time
                    ):
                        seconds_remaining = int(
                            self.next_quest_available_time - current_time
                        )
                        minutes_remaining = seconds_remaining // SECONDS_PER_MINUTE
                        seconds_mod = seconds_remaining % SECONDS_PER_MINUTE

                        # Log the current quest time info for debugging
                        self.logger.debug(
                            f"Quest time info: next_quest_available_time={self.next_quest_available_time}, current_time={current_time}, seconds_remaining={seconds_remaining}"
                        )

                        message = f"Next quest in {minutes_remaining}m {seconds_mod}s"
                        self.agent.state_manager.quest_time_info = {
                            "can_quest": False,
                            "time_remaining": seconds_remaining,
                            "message": message,
                        }
                        self.logger.debug(
                            f"Updated state manager quest time info: {message}"
                        )
                    else:
                        # We can quest now
                        self.agent.state_manager.quest_time_info = {
                            "can_quest": True,
                            "time_remaining": ZERO,
                            "message": "Quest available now",
                        }
                        self.logger.debug(
                            "Updated state manager quest time info: Quest available now"
                        )

            # If we're close to the next quest time, reset the flag to ensure we check
            current_time = time.time()
            if (
                self.next_quest_available_time > ZERO
                and current_time >= self.next_quest_available_time - 30
            ):
                self.quest_time_checked = False
                self.logger.debug(
                    "Reset quest time checked flag as we're approaching quest availability"
                )

                # Update quest time info in state manager if available
                if hasattr(self.agent, "state_manager") and hasattr(
                    self.agent.state_manager, "quest_time_info"
                ):
                    seconds_remaining = max(
                        ZERO, int(self.next_quest_available_time - current_time)
                    )

                    # Log the current quest time info for debugging
                    self.logger.debug(
                        f"Quest time info (approaching): next_quest_available_time={self.next_quest_available_time}, current_time={current_time}, seconds_remaining={seconds_remaining}"
                    )

                    if seconds_remaining <= ZERO:
                        # We can quest now
                        self.agent.state_manager.quest_time_info = {
                            "can_quest": True,
                            "time_remaining": ZERO,
                            "message": "Quest available now",
                        }
                        self.logger.debug(
                            "Updated state manager quest time info: Quest available now"
                        )
                    else:
                        minutes_remaining = seconds_remaining // SECONDS_PER_MINUTE
                        seconds_mod = seconds_remaining % SECONDS_PER_MINUTE

                        message = f"Next quest in {minutes_remaining}m {seconds_mod}s"
                        self.agent.state_manager.quest_time_info = {
                            "can_quest": False,
                            "time_remaining": seconds_remaining,
                            "message": message,
                        }
                        self.logger.debug(
                            f"Updated state manager quest time info: {message}"
                        )

        except Exception as e:
            self.logger.error(
                f"Error in quest manager tick handler: {e}", exc_info=True
            )

    async def async_tick_handler(self, tick_count: int) -> None:
        """Handle async operations on game ticks.

        This is called by the MUD agent to handle async operations that need to be performed on ticks.

        Args:
            tick_count: The current tick count
        """
        try:
            # Only run every 60 ticks (about once every 5 minutes with 5-second ticks)
            # This significantly reduces the frequency of quest info commands
            if tick_count % 60 == 0:
                # Check if we're on a quest and need to update quest info
                if self.current_quest:
                    self.logger.debug(
                        f"Async tick {tick_count}: Checking quest info for '{self.current_quest}'"
                    )

                    # Instead of sending a quest info command directly, use GMCP if available
                    if (
                        hasattr(self.agent, "aardwolf_gmcp")
                        and self.agent.client.gmcp_enabled
                    ):
                        # Quest data will be sent automatically by the server
                        self.logger.debug(
                            "Quest data will be received automatically from server"
                        )

                        # Fall back to sending a command if GMCP is not available
                        has_info, message, quest_details = await self.check_quest_info()

                        if has_info:
                            self.logger.info(f"Updated quest info: {message}")

                            # Update the state manager's quest list if available
                            if hasattr(self.agent, "state_manager") and hasattr(
                                self.agent.state_manager, "quests"
                            ):
                                # Check if the quest is already in the list
                                quest_name = quest_details.get(
                                    "name", self.current_quest
                                )
                                if quest_name not in self.agent.state_manager.quests:
                                    self.agent.state_manager.quests.append(quest_name)
                                    self.logger.debug(
                                        f"Added quest '{quest_name}' to state manager quest list"
                                    )
                        else:
                            self.logger.warning(
                                f"Failed to update quest info: {message}"
                            )

        except Exception as e:
            self.logger.error(
                f"Error in quest manager async tick handler: {e}", exc_info=True
            )
