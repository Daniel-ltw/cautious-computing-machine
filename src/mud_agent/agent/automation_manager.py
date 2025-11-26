"""
Automation Manager for MUD Agent.

This module handles automation functionality for the MUD agent.
"""

import asyncio
import logging
import random
import time

logger = logging.getLogger(__name__)


class AutomationManager:
    """Manages automation functionality for the MUD agent."""

    def __init__(self, agent):
        """Initialize the automation manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        # Automation state
        self.automation_enabled = False
        self.automation_context = None
        self.automation_task = None
        self.interrupt_requested = False

        # Quest automation state
        self.quest_mode = False
        self.quest_state = (
            "idle"  # idle, finding_questor, requesting_quest, hunting, completing
        )
        self.last_quest_check_time = 0
        self.quest_cooldown_wait_start = 0

    async def enable_automation(self, context: str | None = None) -> None:
        """Enable automation mode.

        Args:
            context: Optional context or instructions for the automation
        """
        if self.automation_enabled:
            self.logger.info("Automation already enabled")
            return

        # Initialize the CodeAgent if needed
        if self.agent.code_agent is None:
            await self.agent.decision_engine.initialize_code_agent()

        self.automation_enabled = True
        self.automation_context = context
        self.logger.info(f"Automation enabled with context: {context}")

        # Check if this is quest automation
        if context and "quest" in context.lower():
            self.quest_mode = True
            self.quest_state = "idle"
            self.logger.info("Quest automation mode enabled")
        else:
            self.quest_mode = False

        # Start automation task
        self.automation_task = asyncio.create_task(self._run_automation())

    def disable_automation(self) -> None:
        """Disable automation mode."""
        if not self.automation_enabled:
            self.logger.info("Automation already disabled")
            return

        self.automation_enabled = False
        self.automation_context = None
        self.logger.info("Automation disabled")

        # Reset quest state
        self.quest_mode = False
        self.quest_state = "idle"

        # Cancel automation task if running
        if self.automation_task and not self.automation_task.done():
            self.automation_task.cancel()

    async def _run_automation(self) -> None:
        """Run the automation loop."""
        try:
            context = getattr(self, "automation_context", None)
            context_msg = f" with context: '{context}'" if context else ""
            self.logger.info(f"Starting automation loop{context_msg}")

            # Initial commands to gather information
            await self.agent.send_command("look")

            # Get character stats if we don't have them yet
            if self.agent.state_manager.health["max"] == 0:
                await self.agent.send_command("score")

            # If in quest mode, check quest status
            if self.quest_mode:
                self.logger.info("Starting quest automation cycle")
                has_quest, status = await self.agent.check_quest_status()
                self.logger.info(f"Initial quest status: {status}")

                if has_quest:
                    self.quest_state = "hunting"
                else:
                    self.quest_state = "finding_questor"

                self.last_quest_check_time = time.time()

            # Main automation loop
            while self.automation_enabled:
                try:
                    # Handle quest automation if enabled
                    if self.quest_mode:
                        action = await self._handle_quest_automation()
                    else:
                        # Use sequential thinking to decide what to do next
                        action = await self.agent.decision_engine.decide_next_action()

                    # Execute the action
                    if action:
                        self.logger.info(f"Executing action: {action}")
                        await self.agent.send_command(action)

                        # Check if we're in combat
                        in_combat = self.agent.combat_manager.is_in_combat(
                            self.agent.last_response
                        )

                        # If in combat, check status more frequently
                        if in_combat:
                            # In combat, we want to update stats more frequently
                            # but don't want to waste a turn with 'score' command
                            # Stats should be updated from combat messages
                            self.logger.debug(
                                "In combat - stats updated from combat messages"
                            )
                        # If we're exploring, occasionally check our status
                        elif (
                            action in self.agent.room_manager.current_exits
                            and random.random() < 0.2
                        ) or random.random() < 0.1:  # 20% chance after movement
                            await self.agent.send_command("score")

                    # Wait a bit to avoid flooding the server
                    # Vary the wait time slightly to seem more human-like
                    # Use shorter wait times during combat
                    if self.agent.combat_manager.in_combat:
                        wait_time = 1 + random.random()  # 1-2 seconds in combat
                    else:
                        wait_time = 2 + random.random()  # 2-3 seconds normally
                    await asyncio.sleep(wait_time)

                except asyncio.CancelledError:
                    self.logger.info("Automation task cancelled")
                    break
                except Exception as e:
                    self.logger.error(f"Error in automation loop: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Wait a bit longer after an error

        except asyncio.CancelledError:
            self.logger.info("Automation task cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in automation loop: {e}", exc_info=True)
            self.disable_automation()

    async def _handle_quest_automation(self) -> str:
        """Handle quest automation logic.

        Returns:
            str: The next action to take
        """
        try:
            # Check if we're in combat - if so, handle combat normally
            if self.agent.combat_manager.is_in_combat(self.agent.last_response):
                self.logger.info("In combat during quest automation - handling combat")
                return await self.agent.decision_engine.decide_next_action()

            # Handle different quest states
            if self.quest_state == "idle":
                # Check if we have an active quest
                has_quest, status = await self.agent.check_quest_status()
                self.logger.info(f"Quest status check: {status}")

                if has_quest:
                    self.quest_state = "hunting"
                    self.logger.info("Active quest found, switching to hunting state")
                    return "look"  # Look around to get our bearings
                # Check if we're in cooldown
                elif "cooldown" in status.lower():
                    self.logger.info("Quest cooldown active, waiting...")
                    self.quest_state = "cooldown_wait"
                    self.quest_cooldown_wait_start = time.time()
                    return "score"  # Just check score while waiting
                else:
                    self.quest_state = "finding_questor"
                    self.logger.info("No active quest, switching to finding questor")
                    return "look"  # Look around to get our bearings

            elif self.quest_state == "cooldown_wait":
                # Check if we've waited long enough (at least 2 minutes)
                if time.time() - self.quest_cooldown_wait_start > 120:
                    self.logger.info(
                        "Cooldown wait complete, checking quest status again"
                    )
                    self.quest_state = "idle"
                    return "quest"
                else:
                    # While waiting, just explore or train
                    self.logger.info("Still in cooldown wait, exploring or training")
                    return await self.agent.decision_engine.decide_next_action()

            elif self.quest_state == "finding_questor":
                # Try to find and navigate to the questor
                self.logger.info("Finding questor...")
                success = await self.agent.find_questor()

                if success:
                    self.logger.debug("Found questor, switching to requesting quest")
                    self.quest_state = "requesting_quest"
                    return "look"  # Look around to confirm we're in the right place
                else:
                    self.logger.warning("Failed to find questor, trying again")
                    # Try to recall to town first
                    return "recall"

            elif self.quest_state == "requesting_quest":
                # Request a quest from the questor
                self.logger.info("Requesting quest...")
                success = await self.agent.request_quest()

                if success:
                    self.logger.info("Quest accepted, switching to hunting state")
                    self.quest_state = "hunting"
                    return "look"  # Look around to get our bearings
                # If we couldn't get a quest, check if it's due to cooldown
                elif "cooldown" in self.agent.last_response.lower():
                    self.logger.info("Quest cooldown active, waiting...")
                    self.quest_state = "cooldown_wait"
                    self.quest_cooldown_wait_start = time.time()
                    return "score"  # Just check score while waiting
                else:
                    self.logger.warning("Failed to request quest, trying again")
                    self.quest_state = "finding_questor"
                    return "look"

            elif self.quest_state == "hunting":
                # Check if the quest target is already dead
                if "quest completed" in self.agent.last_response.lower():
                    self.logger.info(
                        "Quest completed detected in response, switching to completing state"
                    )
                    self.quest_state = "completing"
                    return "recall"  # Recall to town to complete the quest

                # Hunt the quest target
                self.logger.info("Hunting quest target...")
                success = await self.agent.hunt_quest_target()

                if success:
                    self.logger.info("Successfully engaged quest target")
                    # Let the combat system handle the fight
                    return await self.agent.decision_engine.decide_next_action()
                else:
                    self.logger.warning("Failed to find quest target, trying again")
                    # Check if the quest is still active
                    has_quest, status = await self.agent.check_quest_status()

                    if has_quest:
                        # Try again with the hunt
                        return "look"  # Look around to get our bearings
                    else:
                        # If we don't have a quest anymore, it might have been completed
                        self.logger.info(
                            "No active quest found, may have been completed"
                        )
                        self.quest_state = "completing"
                        return "recall"  # Recall to town to complete the quest

            elif self.quest_state == "completing":
                # Complete the quest by returning to the questor
                self.logger.info("Completing quest...")
                success = await self.agent.complete_quest()

                if success:
                    self.logger.info(
                        "Quest completed successfully, returning to idle state"
                    )
                    self.quest_state = "idle"
                    return "score"  # Check our score to see rewards
                else:
                    self.logger.warning("Failed to complete quest, trying again")
                    # Try to find the questor again
                    self.quest_state = "finding_questor"
                    return "recall"  # Recall to town to try again

            # Default action if something goes wrong
            self.logger.warning(
                f"Unhandled quest state: {self.quest_state}, resetting to idle"
            )
            self.quest_state = "idle"
            return "look"

        except Exception as e:
            self.logger.error(f"Error in quest automation: {e}", exc_info=True)
            # Reset to a safe state
            self.quest_state = "idle"
            return "look"
