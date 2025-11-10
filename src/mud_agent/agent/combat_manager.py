"""
Combat Manager for MUD Agent.

This module handles combat detection, tracking, and related functionality.
"""

import logging
import re
import time

# Constants for combat management
COMBAT_TIMEOUT_SECONDS = (
    5.0  # Time in seconds to consider still in combat after last indicator
)

logger = logging.getLogger(__name__)


class CombatManager:
    """Manages combat-related functionality for the MUD agent."""

    def __init__(self, agent):
        """Initialize the combat manager.

        Args:
            agent: The parent MUD agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

        # Combat information
        self.in_combat = False
        self.combat_target = ""
        self.combat_round = 0
        self.last_combat_time = 0

    def is_in_combat(self, response: str) -> bool:
        """Detect if the character is currently in combat based on the response.

        Args:
            response: The response from the MUD server

        Returns:
            bool: True if in combat, False otherwise
        """
        try:
            # Check for common combat indicators in the response
            combat_indicators = [
                "You hit",
                "hits you",
                "misses you",
                "You miss",
                "You dodge",
                "dodges your",
                "You parry",
                "parries your",
                "Your attack",
                "attacks you",
                "You are fighting",
                "You are engaged in combat",
                "You are in combat",
                "You are battling",
                "You are dueling",
                "You are locked in combat",
                "You are locked in battle",
                "You are locked in mortal combat",
                "You are locked in mortal battle",
                "You are locked in a duel",
                "You are locked in a fight",
                "You are locked in a struggle",
                "You are locked in a conflict",
                "You are locked in a contest",
                "You are locked in a match",
                "You are locked in a war",
                "You are locked in a skirmish",
                "You are locked in a clash",
                "You are locked in a confrontation",
                "You are locked in a melee",
                "You are locked in a fray",
                "You are locked in a brawl",
                "You are locked in a scuffle",
                "You are locked in a tussle",
                "You are locked in a fracas",
                "You are locked in a scrimmage",
                "You are locked in a scrap",
                "You are locked in a battle royal",
                "You are locked in a free-for-all",
                "You are locked in a death match",
                "You are locked in a death struggle",
                "You are locked in a death battle",
                "You are locked in a death duel",
                "You are locked in a death fight",
                "You are locked in a death conflict",
                "You are locked in a death contest",
                "You are locked in a death match",
                "You are locked in a death war",
                "You are locked in a death skirmish",
                "You are locked in a death clash",
                "You are locked in a death confrontation",
                "You are locked in a death melee",
                "You are locked in a death fray",
                "You are locked in a death brawl",
                "You are locked in a death scuffle",
                "You are locked in a death tussle",
                "You are locked in a death fracas",
                "You are locked in a death scrimmage",
                "You are locked in a death scrap",
                "You are locked in a death battle royal",
                "You are locked in a death free-for-all",
            ]

            # Check if any combat indicator is in the response
            for indicator in combat_indicators:
                if indicator in response:
                    # Update combat state
                    self.in_combat = True
                    self.last_combat_time = time.time()

                    # Try to extract combat target
                    target_match = re.search(r"You are fighting (\w+)", response)
                    if target_match:
                        self.combat_target = target_match.group(1)
                        self.logger.debug(
                            f"Combat target detected: {self.combat_target}"
                        )

                    self.logger.debug("Combat detected")
                    return True

            # Check if we were recently in combat (within the timeout period)
            if (
                self.in_combat
                and time.time() - self.last_combat_time < COMBAT_TIMEOUT_SECONDS
            ):
                # Still consider in combat for a short time after last combat indicator
                return True

            # No combat indicators found
            self.in_combat = False
            self.combat_target = ""
            return False
        except Exception as e:
            self.logger.error(f"Error detecting combat status: {e}", exc_info=True)
            return False

    def extract_combat_status(self, response: str) -> None:
        """Extract combat-specific status effects from the response.

        Args:
            response: The response from the MUD server
        """
        try:
            # Combat-specific status effects
            combat_status_effects = {
                "stunned": ["you are stunned", "you have been stunned", "stuns you"],
                "bleeding": [
                    "you are bleeding",
                    "you begin to bleed",
                    "blood flows from your wounds",
                ],
                "poisoned": [
                    "you are poisoned",
                    "poison courses through your veins",
                    "you feel poison",
                ],
                "blind": [
                    "you are blinded",
                    "you can't see",
                    "your vision is obscured",
                ],
                "confused": [
                    "you are confused",
                    "you feel confused",
                    "confusion clouds your mind",
                ],
                "weakened": [
                    "you are weakened",
                    "your strength is sapped",
                    "you feel weak",
                ],
                "slowed": [
                    "you are slowed",
                    "your movements are slowed",
                    "you move more slowly",
                ],
                "paralyzed": [
                    "you are paralyzed",
                    "you can't move",
                    "your muscles won't respond",
                ],
                "feared": ["you are afraid", "fear grips you", "you are terrified"],
                "charmed": [
                    "you are charmed",
                    "you feel charmed",
                    "you are under a charm",
                ],
                "silenced": [
                    "you are silenced",
                    "you can't cast spells",
                    "your magic is blocked",
                ],
                "disarmed": [
                    "you are disarmed",
                    "your weapon is knocked from your hand",
                    "you lose your grip",
                ],
                "rooted": ["you are rooted", "you can't move", "your feet are stuck"],
                "burning": ["you are burning", "flames engulf you", "you are on fire"],
                "frozen": ["you are frozen", "ice encases you", "you are chilled"],
                "shocked": [
                    "you are shocked",
                    "electricity courses through you",
                    "lightning strikes you",
                ],
                "cursed": ["you are cursed", "a curse afflicts you", "you feel cursed"],
                "diseased": [
                    "you are diseased",
                    "disease afflicts you",
                    "you feel sick",
                ],
                "exhausted": [
                    "you are exhausted",
                    "fatigue overwhelms you",
                    "you feel tired",
                ],
                "enraged": ["you are enraged", "rage fills you", "you feel angry"],
                "berserk": [
                    "you go berserk",
                    "berserker rage fills you",
                    "you feel berserk",
                ],
                "protected": [
                    "you are protected",
                    "a shield surrounds you",
                    "you feel protected",
                ],
                "invisible": [
                    "you are invisible",
                    "you fade from view",
                    "you can't be seen",
                ],
                "hasted": ["you are hasted", "you move faster", "your speed increases"],
                "regenerating": [
                    "you are regenerating",
                    "your wounds close",
                    "you heal quickly",
                ],
                "invulnerable": [
                    "you are invulnerable",
                    "you can't be harmed",
                    "damage is reduced",
                ],
                "flying": [
                    "you are flying",
                    "you take to the air",
                    "you float above the ground",
                ],
                "sanctuary": [
                    "sanctuary protects you",
                    "you are sanctified",
                    "divine protection surrounds you",
                ],
            }

            # Check for each combat status effect
            response_lower = response.lower()
            for status, indicators in combat_status_effects.items():
                for indicator in indicators:
                    if indicator in response_lower:
                        # Add the status effect if not already present
                        status_capitalized = status.capitalize()
                        if status_capitalized not in self.agent.state_manager.status:
                            self.agent.state_manager.status.append(status_capitalized)
                            self.logger.debug(
                                f"Combat status detected: {status_capitalized}"
                            )
                        break

            # Check for status removal
            status_removal_indicators = {
                "no longer stunned": ["Stunned"],
                "bleeding stops": ["Bleeding"],
                "poison wears off": ["Poisoned"],
                "vision returns": ["Blind"],
                "mind clears": ["Confused"],
                "strength returns": ["Weakened"],
                "speed returns": ["Slowed"],
                "can move again": ["Paralyzed", "Rooted"],
                "fear subsides": ["Feared"],
                "charm breaks": ["Charmed"],
                "silence ends": ["Silenced"],
                "retrieve your weapon": ["Disarmed"],
                "flames die out": ["Burning"],
                "ice melts": ["Frozen"],
                "electricity dissipates": ["Shocked"],
                "curse is lifted": ["Cursed"],
                "disease is cured": ["Diseased"],
                "feel refreshed": ["Exhausted"],
                "calm down": ["Enraged", "Berserk"],
                "protection fades": ["Protected"],
                "become visible": ["Invisible"],
                "slow down": ["Hasted"],
                "regeneration ends": ["Regenerating"],
                "vulnerability returns": ["Invulnerable"],
                "return to the ground": ["Flying"],
                "sanctuary fades": ["Sanctuary"],
            }

            # Check for status removal indicators
            for indicator, statuses in status_removal_indicators.items():
                if indicator in response_lower:
                    for status in statuses:
                        if status in self.agent.state_manager.status:
                            self.agent.state_manager.status.remove(status)
                            self.logger.debug(f"Combat status removed: {status}")

        except Exception as e:
            self.logger.error(f"Error extracting combat status: {e}", exc_info=True)
