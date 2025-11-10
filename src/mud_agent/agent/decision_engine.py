"""
Decision Engine for MUD Agent.

This module handles decision-making logic for the MUD agent.
"""

import logging
import random
import re

from smolagents import CodeAgent, LogLevel

# Constants for decision making
ZERO = 0
CRITICAL_HEALTH_THRESHOLD = 25
LOW_HEALTH_THRESHOLD = 40
MODERATE_HEALTH_THRESHOLD = 70
HIGH_MANA_THRESHOLD = 50
MIN_LEVEL_FOR_SPELLS = 5
MAX_COMMAND_LENGTH = 50
MAX_RECENT_COMMANDS = 5
MIN_COMMANDS_FOR_LOOP_DETECTION = 3
RESPONSE_EXCERPT_LENGTH = 500
HEALTH_RECOVERY_THRESHOLD = 0.7

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Manages decision-making for the MUD agent."""

    def __init__(self, event_manager, client):
        """Initialize the decision engine.

        Args:
            event_manager: The event manager for event handling.
            client: The MUD client for sending commands.
        """
        self.events = event_manager
        self.client = client
        self.logger = logging.getLogger(__name__)

        # Recent commands tracking
        self.recent_commands = []
        self.last_room_checked_for_exits = None

    async def initialize_code_agent(self) -> None:
        """Initialize the CodeAgent for advanced reasoning tasks.

        This method initializes the CodeAgent with the MCP tools.
        """
        if self.agent.code_agent is not None:
            # Agent is already initialized
            return

        try:
            if not self.agent.model:
                self.logger.warning("Cannot initialize CodeAgent: No model configured")
                return

            # Create a list of tools for the agent
            tools = []

            # Add the Sequential Thinking tool
            tools.append(self.agent.sequential_thinking_tool)

            # Initialize the CodeAgent
            self.agent.code_agent = CodeAgent(
                tools=tools,
                model=self.agent.model,
                add_base_tools=False,  # We only want our specific tools
                verbosity_level=LogLevel.OFF,
            )

            self.logger.info("CodeAgent initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing CodeAgent: {e}", exc_info=True)

    async def decide_next_action(self) -> str | None:
        """Decide the next action to take based on the current state and automation context.

        Returns:
            Optional[str]: The next action to take, or None if no action
        """
        try:
            # Check for exits if we are in a new room
            current_room_name = self.agent.room_manager.current_room
            if (
                current_room_name != "Unknown"
                and current_room_name != self.last_room_checked_for_exits
            ):
                self.last_room_checked_for_exits = current_room_name
                self.logger.info(f"New room '{current_room_name}', checking for exits.")
                return "exits"

            # Get the automation context if available
            context = getattr(self.agent.automation_manager, "automation_context", None)
            context_str = f" with context: '{context}'" if context else ""

            # We need to get the current state. This would ideally be passed in or retrieved from a shared state object.
            # For now, we'll assume we can get it from an event or a direct call to a state manager if we had a reference.
            # This part of the refactoring will require a bigger change to how state is managed and accessed.
            # For now, we will emit an event to request the state.

            # Let's assume we have a way to get the state.
            # state = self.get_current_state() # This function doesn't exist yet

            # The following is placeholder logic until state management is fully decoupled.
            # For the purpose of this refactoring, we'll log a message.
            self.logger.debug("DecisionEngine is deciding next action. State access needs to be refactored.")

            # Check if we're in combat using our combat detection method
            # This also needs refactoring to not depend on the agent
            # in_combat = self.combat_manager.is_in_combat(self.client.last_response)
            in_combat = False # Placeholder

            if in_combat:
                self.logger.info("Combat detected, using Sequential Thinking directly")

            # Initialize the CodeAgent if needed and we're not in combat
            if not in_combat and self.agent.code_agent is None:
                await self.initialize_code_agent()

            # If we have a CodeAgent and we're not in combat, use it to decide the next action
            if not in_combat and self.agent.code_agent is not None:
                self.logger.info("Using CodeAgent to decide next action")

                # Prepare a detailed state description for the CodeAgent
                state_description = {
                    "room": self.agent.room_manager.current_room,
                    "exits": self.agent.room_manager.current_exits,
                    "npcs": getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else [],
                    "health": f"{self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}"
                    if self.agent.state_manager.health["max"] > ZERO
                    else "Unknown",
                    "mana": f"{self.agent.state_manager.mana['current']}/{self.agent.state_manager.mana['max']}"
                    if self.agent.state_manager.mana["max"] > ZERO
                    else "Unknown",
                    "movement": f"{self.agent.state_manager.movement['current']}/{self.agent.state_manager.movement['max']}"
                    if self.agent.state_manager.movement["max"] > ZERO
                    else "Unknown",
                    "level": self.agent.state_manager.level,
                    "experience": self.agent.state_manager.experience,
                    "gold": self.agent.state_manager.gold,
                    "status_effects": self.agent.state_manager.status,
                }

                # Get the last response from the server (truncated if too long)
                last_response_excerpt = (
                    self.agent.last_response[:RESPONSE_EXCERPT_LENGTH] + "..."
                    if len(self.agent.last_response) > RESPONSE_EXCERPT_LENGTH
                    else self.agent.last_response
                )

                # Check for closed doors
                if re.search(r"the door is closed|it is closed|you cannot go that way", self.agent.last_response, re.IGNORECASE):
                    direction_match = re.search(r"\b(north|south|east|west|up|down|n|s|e|w|u|d)\b", self.agent.last_command, re.IGNORECASE)
                    if direction_match:
                        direction = direction_match.group(1)
                        return f"open {direction}"

                # Create a prompt for the CodeAgent
                prompt = f"""
                I need to decide what to do next in the MUD game{context_str}.

                Current state:
                - Room: {state_description["room"]}
                - Available exits: {", ".join(state_description["exits"]) if state_description["exits"] else "None"}
                - NPCs/mobs in room: {", ".join(state_description["npcs"]) if state_description["npcs"] else "None"}
                - Health: {state_description["health"]}
                - Mana: {state_description["mana"]}
                - Movement: {state_description["movement"]}
                - Level: {state_description["level"]}
                - Status effects: {", ".join(state_description["status_effects"]) if state_description["status_effects"] else "None"}

                Last command: {self.agent.last_command}

                Last server response:
                ```
                {last_response_excerpt}
                ```

                {f"Instructions: {context}" if context else ""}

                Use the Sequential Thinking tool to analyze the situation and decide on the best action to take.
                Consider the last server response carefully to understand what's happening in the game.

                If you encounter a closed door, try 'open door' or 'open <direction>'.

                It's okay to repeat commands when it makes sense (like repeatedly attacking during combat),
                but avoid getting stuck in loops of the same commands when they don't produce progress.

                Return only the command I should execute (a single word or short phrase) as the final answer.
                """

                try:
                    # Run the CodeAgent to decide the next action
                    result = self.agent.code_agent.run(prompt)

                    # Process the result
                    if result and isinstance(result, str):
                        # Clean up the result - remove quotes and extra whitespace
                        action = result.strip().strip("\"'").strip()

                        # Basic validation - actions should be reasonably short
                        if action and len(action) < MAX_COMMAND_LENGTH:
                            # Update recent commands list
                            self.recent_commands.append(action)
                            # Keep only the last N commands
                            if len(self.recent_commands) > MAX_RECENT_COMMANDS:
                                self.recent_commands = self.recent_commands[
                                    -MAX_RECENT_COMMANDS:
                                ]

                            # Check for repetitive patterns that might indicate being stuck
                            if (
                                len(self.recent_commands)
                                >= MIN_COMMANDS_FOR_LOOP_DETECTION
                            ):
                                # Check if the last N commands are identical and not combat-related
                                last_three = self.recent_commands[-3:]
                                if last_three.count(last_three[0]) == 3 and not any(
                                    combat_cmd in last_three[0].lower()
                                    for combat_cmd in ["kill", "attack", "cast", "get"]
                                ):
                                    # We might be stuck in a loop
                                    self.logger.warning(
                                        f"Detected potential command loop: '{last_three[0]}' repeated 3 times"
                                    )
                                    # If we're stuck with the same command and the last response contains "nothing special"
                                    # or similar indications of no progress, try a different approach
                                    if (
                                        "nothing special"
                                        in self.agent.last_response.lower()
                                        or "you can't"
                                        in self.agent.last_response.lower()
                                        or "what?" in self.agent.last_response.lower()
                                    ):
                                        self.logger.info(
                                            "Detected lack of progress, trying 'look' to reassess"
                                        )
                                        return "look"

                            self.logger.info(f"CodeAgent decided action: '{action}'")
                            return action
                except Exception as code_agent_error:
                    self.logger.error(
                        f"Error using CodeAgent to decide action: {code_agent_error}",
                        exc_info=True,
                    )
                    self.logger.info(
                        "Falling back to Sequential Thinking tool directly"
                    )

            # Use Sequential Thinking tool directly if CodeAgent fails, is not available, or we're in combat
            return await self._use_sequential_thinking(in_combat, context, context_str)

        except Exception as e:
            self.logger.error(f"Error deciding next action: {e}", exc_info=True)
            # Default to a safe action
            return "look"

    async def _use_sequential_thinking(
        self, in_combat: bool, context: str | None, context_str: str
    ) -> str | None:
        """Use the Sequential Thinking tool to decide the next action.

        Args:
            in_combat: Whether the character is currently in combat
            context: The automation context
            context_str: Formatted context string for prompts

        Returns:
            Optional[str]: The next action to take, or None if no action
        """
        try:
            if in_combat:
                self.logger.info(
                    "Using Sequential Thinking tool directly for combat decision"
                )
            else:
                self.logger.info(
                    "Using Sequential Thinking tool directly to decide next action"
                )

            # Use sequential thinking to decide what to do
            if in_combat:
                initial_thought = f"I am in combat in the MUD game and need to decide on my next combat action{context_str}."
                if context:
                    initial_thought += f" While following these instructions: {context}"
                # Add combat-specific information
                initial_thought += f" My health is {self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']} and my mana is {self.agent.state_manager.mana['current']}/{self.agent.state_manager.mana['max']}."
            else:
                initial_thought = (
                    f"I need to decide what to do next in the MUD game{context_str}."
                )
                if context:
                    initial_thought += f" I should follow these instructions: {context}"

            thought_result = await self.agent.sequential_thinking_tool.forward(
                thought=initial_thought,
                nextThoughtNeeded=True,
                thoughtNumber=1,
                totalThoughts=4,  # Increased to allow for more complex reasoning
            )

            # Process the first thought
            if thought_result and "thought" in thought_result:
                thought = thought_result["thought"]
                self.logger.debug(f"Thought 1: {thought}")

                # Continue with the second thought - analyze current state
                second_thought = self._generate_second_thought(in_combat, context)

                thought_result = await self.agent.sequential_thinking_tool.forward(
                    thought=second_thought,
                    nextThoughtNeeded=True,
                    thoughtNumber=2,
                    totalThoughts=4,
                )

                # Process the second thought
                if thought_result and "thought" in thought_result:
                    thought = thought_result["thought"]
                    self.logger.debug(f"Thought 2: {thought}")

                    # Third thought - evaluate options based on context
                    third_thought = await self._generate_third_thought(
                        in_combat, context
                    )

                    thought_result = await self.agent.sequential_thinking_tool.forward(
                        thought=third_thought,
                        nextThoughtNeeded=True,
                        thoughtNumber=3,
                        totalThoughts=4,
                    )

                    # Process the third thought
                    if thought_result and "thought" in thought_result:
                        thought = thought_result["thought"]
                        self.logger.debug(f"Thought 3: {thought}")

                        # Final thought - decide on action
                        final_thought, default_action = self._generate_final_thought(
                            in_combat, context
                        )

                        thought_result = (
                            await self.agent.sequential_thinking_tool.forward(
                                thought=final_thought,
                                nextThoughtNeeded=False,
                                thoughtNumber=4,
                                totalThoughts=4,
                            )
                        )

                        # Extract the action from the final thought
                        if thought_result and "thought" in thought_result:
                            final_thought = thought_result["thought"]
                            self.logger.debug(f"Final thought: {final_thought}")

                            # Extract the action from the final thought
                            action_match = re.search(
                                r"action:?\s*([a-zA-Z0-9\s]+)",
                                final_thought,
                                re.IGNORECASE,
                            )
                            if action_match:
                                action = action_match.group(1).strip()
                                self.logger.info(
                                    f"Decided action based on context: {action}"
                                )
                                return action

                            # Look for the last sentence that might contain the action
                            sentences = final_thought.split(".")
                            for sentence in reversed(sentences):
                                if "will" in sentence and "take" in sentence:
                                    words = sentence.strip().split()
                                    # Get the last word or phrase that might be the action
                                    potential_action = words[-1].strip()
                                    if potential_action and len(potential_action) > 1:
                                        self.logger.info(
                                            f"Extracted action from final thought: {potential_action}"
                                        )
                                        return potential_action

                            # If we still don't have an action, use the default
                            self.logger.info(f"Using default action: {default_action}")
                            return default_action

            # Default action if all methods fail
            default_action = "look"
            if self.agent.room_manager.current_exits:
                default_action = random.choice(self.agent.room_manager.current_exits)

            self.logger.info(f"Using fallback default action: {default_action}")
            return default_action

        except Exception as e:
            self.logger.error(f"Error using Sequential Thinking: {e}", exc_info=True)
            return "look"

    def _generate_second_thought(self, in_combat: bool, context: str | None) -> str:
        """Generate the second thought for sequential thinking.

        Args:
            in_combat: Whether the character is currently in combat
            context: The automation context

        Returns:
            str: The second thought
        """
        if in_combat:
            second_thought = (
                f"I'm in combat in {self.agent.room_manager.current_room}. "
            )

            # Add detailed combat analysis
            if self.agent.state_manager.health["max"] > 0:
                health_percent = (
                    self.agent.state_manager.health["current"]
                    / self.agent.state_manager.health["max"]
                ) * 100
                if health_percent < LOW_HEALTH_THRESHOLD:
                    second_thought += f"My health is CRITICALLY LOW ({self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}), I may need to flee or heal. "
                elif health_percent < MODERATE_HEALTH_THRESHOLD:
                    second_thought += f"My health is moderate ({self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}), I should be cautious. "
                else:
                    second_thought += f"My health is good ({self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}). "

            # Add mana analysis for spellcasters
            if self.agent.state_manager.mana["max"] > 0:
                mana_percent = (
                    self.agent.state_manager.mana["current"]
                    / self.agent.state_manager.mana["max"]
                ) * 100
                if mana_percent < LOW_HEALTH_THRESHOLD:
                    second_thought += f"My mana is very low ({self.agent.state_manager.mana['current']}/{self.agent.state_manager.mana['max']}), I should conserve spells. "
                elif mana_percent < MODERATE_HEALTH_THRESHOLD:
                    second_thought += f"My mana is moderate ({self.agent.state_manager.mana['current']}/{self.agent.state_manager.mana['max']}). "
                else:
                    second_thought += f"My mana is good ({self.agent.state_manager.mana['current']}/{self.agent.state_manager.mana['max']}). "

            # Add context-specific combat analysis
            if context:
                second_thought += f"Considering my instructions to '{context}', "

            second_thought += "I need to decide on the best combat action."
        else:
            second_thought = f"Based on my current location ({self.agent.room_manager.current_room}) with exits {self.agent.room_manager.current_exits}, "

            # Add information about NPCs/mobs in the room
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            if current_npcs:
                second_thought += f"and NPCs/mobs in the room ({', '.join(current_npcs)}), "

            # Add health status if available
            if self.agent.state_manager.health["max"] > 0:
                health_percent = (
                    self.agent.state_manager.health["current"]
                    / self.agent.state_manager.health["max"]
                ) * 100
                if health_percent < LOW_HEALTH_THRESHOLD:
                    second_thought += f"my health is critically low ({self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}), "
                elif health_percent < MODERATE_HEALTH_THRESHOLD:
                    second_thought += f"my health is moderate ({self.agent.state_manager.health['current']}/{self.agent.state_manager.health['max']}), "

            # Add context-specific analysis
            if context:
                second_thought += f"and considering my instructions to '{context}', "

            second_thought += "I should consider my next action carefully."

        return second_thought

    async def _generate_third_thought(
        self, in_combat: bool, context: str | None
    ) -> str:
        """Generate the third thought for sequential thinking.

        Args:
            in_combat: Whether the character is currently in combat
            context: The automation context

        Returns:
            str: The third thought
        """
        if in_combat:
            third_thought = "In this combat situation, my options are:"

            # Add combat-specific options
            health_percent = (
                (
                    self.agent.state_manager.health["current"]
                    / self.agent.state_manager.health["max"]
                )
                * 100
                if self.agent.state_manager.health["max"] > ZERO
                else 100
            )

            # Critical health - consider fleeing or healing
            if health_percent < LOW_HEALTH_THRESHOLD:
                third_thought += " I could flee using an exit if available, use a healing potion or spell, or continue fighting cautiously."
            # Moderate health - consider combat tactics
            elif health_percent < MODERATE_HEALTH_THRESHOLD:
                third_thought += " I could use special attacks, cast offensive spells, or use items to gain an advantage."
            # Good health - consider aggressive tactics
            else:
                third_thought += " I can fight aggressively, use powerful attacks or spells, or try special combat maneuvers."

            # Add context-specific combat options
            if context:
                if "flee" in context.lower() or "retreat" in context.lower():
                    third_thought += " Since my instructions mention fleeing, I should prioritize finding an exit."
                elif "kill" in context.lower() or "fight" in context.lower():
                    third_thought += " Since my instructions mention fighting, I should focus on defeating my opponent."
        else:
            third_thought = "Based on my analysis, I have several options:"

            # Consider NPCs/mobs in the room
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            if current_npcs:
                third_thought += f" There are NPCs/mobs in this room ({', '.join(current_npcs)}) that I could interact with or fight."

            # Add context-specific options
            if context:
                if "explore" in context.lower():
                    third_thought += " I should prioritize exploring new areas."
                elif "train" in context.lower() or "level" in context.lower():
                    current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                    if current_npcs:
                        third_thought += " Since I'm looking to train/level and there are mobs here, I could fight them."
                    else:
                        third_thought += " I should look for training opportunities or monsters to fight."
                elif "heal" in context.lower() or "rest" in context.lower():
                    third_thought += " I should find a safe place to rest and recover."
                elif "quest" in context.lower() or "mission" in context.lower():
                    # Check if we have an active quest
                    has_quest, quest_status = await self.agent.check_quest_status()
                    if has_quest:
                        third_thought += f" I have an active quest: {quest_status}. I should focus on completing it."
                        # Check if we know the quest target
                        if self.agent.quest_manager.quest_target:
                            third_thought += f" I need to find and kill {self.agent.quest_manager.quest_target}."
                    else:
                        third_thought += (
                            " I should find a questor and request a new quest."
                        )
                elif "hunt" in context.lower() or "kill" in context.lower():
                    current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                    if current_npcs:
                        third_thought += f" Since I'm hunting and there are mobs here ({', '.join(current_npcs)}), I should attack one of them."
                    else:
                        third_thought += " I should search for monsters to hunt."
            elif current_npcs:
                third_thought += (
                    " I could interact with the NPCs/mobs here or continue exploring."
                )
            else:
                third_thought += " Since I have no specific instructions, I should explore and gather information."

        return third_thought

    def _generate_final_thought(self, in_combat: bool, context: str | None) -> tuple:
        """Generate the final thought and default action for sequential thinking.

        Args:
            in_combat: Whether the character is currently in combat
            context: The automation context

        Returns:
            tuple: (final_thought, default_action)
        """
        final_thought_prefix = "After careful consideration, "

        if context:
            final_thought_prefix += f"and keeping my instructions '{context}' in mind, "

        final_thought = final_thought_prefix + "I will take the following action: "

        # Determine a reasonable default action based on context
        if in_combat:
            # Default combat action
            default_action = "kill"  # Basic attack command

            # Adjust based on health
            health_percent = (
                (
                    self.agent.state_manager.health["current"]
                    / self.agent.state_manager.health["max"]
                )
                * 100
                if self.agent.state_manager.health["max"] > ZERO
                else 100
            )

            # Critical health - consider fleeing
            if (
                health_percent < CRITICAL_HEALTH_THRESHOLD
                and self.agent.room_manager.current_exits
            ):
                default_action = random.choice(
                    self.agent.room_manager.current_exits
                )  # Flee in a random direction
                final_thought = (
                    final_thought_prefix
                    + f"I will flee to the {default_action} because my health is critical. "
                )
            # Low health - consider healing
            elif health_percent < LOW_HEALTH_THRESHOLD:
                if (
                    self.agent.state_manager.mana["current"] > HIGH_MANA_THRESHOLD
                ):  # If we have some mana
                    default_action = "cast 'cure light'"  # Basic healing spell
                    final_thought = (
                        final_thought_prefix
                        + f"I will {default_action} to recover some health. "
                    )
                else:
                    default_action = "kill"  # Continue fighting if we can't heal
                    final_thought = (
                        final_thought_prefix
                        + f"I will continue to {default_action} my opponent. "
                    )
            # Good health - attack
            elif (
                self.agent.state_manager.mana["current"] > HIGH_MANA_THRESHOLD
                and self.agent.state_manager.level > MIN_LEVEL_FOR_SPELLS
            ):  # If we have good mana and are higher level
                default_action = "cast 'fireball'"  # Example offensive spell
                final_thought = (
                    final_thought_prefix + f"I will {default_action} at my opponent. "
                )
            else:
                default_action = "kill"  # Basic attack
                final_thought = (
                    final_thought_prefix + f"I will {default_action} my opponent. "
                )

            # Override with context if relevant
            if context:
                context_lower = context.lower()
                if "flee" in context_lower and self.agent.room_manager.current_exits:
                    default_action = random.choice(
                        self.agent.room_manager.current_exits
                    )
                    final_thought = (
                        final_thought_prefix
                        + f"Following instructions to flee, I will go {default_action}. "
                    )
        else:
            default_action = "look"  # Safe default

            # Consider NPCs/mobs in the room
            current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
            if current_npcs and (
                "kill" in context.lower()
                if context
                else False or "hunt" in context.lower()
                if context
                else False or "train" in context.lower()
                if context
                else False or "fight" in context.lower()
                if context
                else False
            ):
                # Attack the first NPC/mob in the room
                default_action = f"kill {current_npcs[0]}"
            elif self.agent.room_manager.current_exits and context:
                context_lower = context.lower()
                if (
                    "explore" in context_lower
                    and len(self.agent.room_manager.current_exits) > 0
                ):
                    # Choose a random exit for exploration
                    default_action = random.choice(
                        self.agent.room_manager.current_exits
                    )
                elif "train" in context_lower or "fight" in context_lower:
                    current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                    if current_npcs:
                        # Attack the first NPC/mob in the room
                        default_action = (
                            f"kill {current_npcs[0]}"
                        )
                    else:
                        default_action = "scan"  # Look for enemies
                elif (
                    "heal" in context_lower
                    and self.agent.state_manager.health["current"]
                    < self.agent.state_manager.health["max"] * HEALTH_RECOVERY_THRESHOLD
                ):
                    default_action = "rest"  # Rest to recover
                elif "quest" in context_lower:
                    # If we're in quest mode, prioritize quest-related actions
                    current_npcs = getattr(self.agent.state_manager, 'npcs', []) if hasattr(self.agent, 'state_manager') else []
                    if (
                        self.agent.quest_manager.quest_target
                        and current_npcs
                    ):
                        # Check if the quest target is in this room
                        for npc in current_npcs:
                            if (
                                self.agent.quest_manager.quest_target.lower()
                                in npc.lower()
                            ):
                                default_action = f"kill {npc}"
                                final_thought = (
                                    final_thought_prefix
                                    + f"I will attack the quest target {npc}. "
                                )
                                break

            final_thought += default_action

        return final_thought, default_action
