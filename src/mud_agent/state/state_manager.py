"""State manager for the MUD agent.

This module provides a central state manager that holds all reactive attributes
and allows widgets to bind to them for automatic updates. It also handles character
stats, status effects, and other game state information.

The StateManager uses an event-driven architecture to notify components of state changes.
Components can subscribe to specific events like "character_update", "vitals_update", etc.
to receive notifications when the state changes.

This is the single source of truth for all game state in the MUD agent.
"""

import asyncio
import ast
import logging
from collections.abc import Callable
from typing import Any

from rich.console import Console
from textual.reactive import reactive
from textual.widget import Widget

from ..utils.event_emitter import EventEmitter


# Constants for status thresholds
ONE_HUNDRED_PERCENT = 100
SECONDS_PER_MINUTE = 60
DEFAULT_MAX_HUNGER = 100  # Hunger scale is 0-100
DEFAULT_MAX_THIRST = 100  # Thirst scale is 0-100
GOOD_ALIGNMENT_THRESHOLD = 300
EVIL_ALIGNMENT_THRESHOLD = -300
STARVING_HUNGER_VALUE = 0
HUNGRY_HUNGER_VALUE = 30
SATIATED_HUNGER_VALUE = 70
FULL_HUNGER_VALUE = 90
BLOATED_HUNGER_VALUE = 100
PARCHED_THIRST_VALUE = 0
THIRSTY_THIRST_VALUE = 30
NOT_THIRSTY_VALUE = 70
QUENCHED_THIRST_VALUE = 100

# Thresholds for text descriptions
FULL_THRESHOLD = 90
SATIATED_THRESHOLD = 70
HUNGRY_THRESHOLD = 30
STARVING_THRESHOLD = 0
DAY_NIGHT_CHECK_INTERVAL = 60  # seconds
QUEST_TIME_CHECK_INTERVAL = 60  # seconds
TICK_UPDATE_INTERVAL = 12  # Update every 12th tick


class StateManager(Widget):
    """Central state manager for the MUD agent.

    This class is the single source of truth for all game state in the MUD agent.
    It combines the functionality of the previous StatusManager and StateManager classes.

    It holds all reactive attributes that can be bound to widgets for automatic updates
    when the state changes, and also handles character stats, status effects, and other
    game state information.

    The StateManager uses an event-driven architecture to notify components of state changes.
    Components can subscribe to specific events using the events.on() method:

    - "character_update": Emitted when character information changes
    - "vitals_update": Emitted when HP, MP, or MV changes
    - "stats_update": Emitted when character stats change
    - "maxstats_update": Emitted when max stats change
    - "worth_update": Emitted when gold, bank, XP, QP, or TP changes
    - "room_update": Emitted when room information changes

    - "status_update": Emitted when status effects change
    - "combat_update": Emitted when combat status changes
    - "state_update": Emitted for any state change, with a summary of all changes
    - "state_error": Emitted when an error occurs during state update
    """

    # Character information
    character_name = reactive("")
    level = reactive(0)
    race = reactive("")
    character_class = reactive("")
    subclass = reactive("")
    alignment = reactive("")
    clan = reactive("")
    remorts = reactive(0)
    tier = reactive(0)

    # Vitals
    hp_current = reactive(0)
    hp_max = reactive(0)
    mp_current = reactive(0)
    mp_max = reactive(0)
    mv_current = reactive(0)
    mv_max = reactive(0)

    # Needs
    hunger_current = reactive(DEFAULT_MAX_HUNGER)  # Start with full hunger
    hunger_max = reactive(DEFAULT_MAX_HUNGER)
    thirst_current = reactive(DEFAULT_MAX_THIRST)  # Start with full thirst
    thirst_max = reactive(DEFAULT_MAX_THIRST)

    # Worth
    gold = reactive(0)
    bank = reactive(0)
    experience = reactive(0)
    quest_points = reactive(0)
    trivia_points = reactive(0)

    # Stats
    stats = reactive({})
    str_value = reactive(0)
    str_max = reactive(0)
    int_value = reactive(0)
    int_max = reactive(0)
    wis_value = reactive(0)
    wis_max = reactive(0)
    dex_value = reactive(0)
    dex_max = reactive(0)
    con_value = reactive(0)
    con_max = reactive(0)
    luck_value = reactive(0)
    luck_max = reactive(0)
    hr_value = reactive(0)
    dr_value = reactive(0)

    # Room information
    room_name = reactive("Unknown")
    room_num = reactive(0)
    area_name = reactive("")
    room_terrain = reactive("")
    room_details = reactive("")
    room_coords = reactive((0, 0, 0))
    exits = reactive([])
    npcs = reactive([])

    # Map
    map_text = reactive("")

    # Status effects
    status_effects = reactive([])

    # Combat
    in_combat = reactive(False)

    def __init__(self, agent=None, event_manager=None):
        """Initialize the state manager.

        Args:
            agent: The parent MUD agent.
            event_manager: An optional external event manager. If not provided,
                a new one will be created.
        """
        # Call the parent class's __init__ method
        super().__init__(name="state_manager")

        self.logger = logging.getLogger(__name__)
        self.logger.debug("StateManager initialized with agent: %s", agent)
        self.agent = agent

        # Initialize the event emitter
        if event_manager:
            self.events = event_manager
            self.logger.debug("Using external EventEmitter for StateManager.")
        else:
            self.events = EventEmitter()
            self.logger.debug("Created new EventEmitter for StateManager.")

        # Store the current event loop for use in threaded contexts
        try:
            self.event_loop = asyncio.get_event_loop()
            self.logger.debug("Stored event loop reference for threaded operations")
        except RuntimeError:
            self.event_loop = None
            self.logger.warning("No event loop available during initialization")

        # Initialize dictionaries for easier access
        self.health = {
            "current": 0,
            "max": 0,
        }
        self.mana = {
            "current": 0,
            "max": 0,
        }
        self.movement = {
            "current": 0,
            "max": 0,
        }
        self.hunger = {
            "current": DEFAULT_MAX_HUNGER,  # Start with full hunger
            "max": DEFAULT_MAX_HUNGER,
        }  # Hunger level (0-100, 0 = starving, 100 = full)
        self.thirst = {
            "current": DEFAULT_MAX_THIRST,  # Start with full thirst
            "max": DEFAULT_MAX_THIRST,
        }  # Thirst level (0-100, 0 = dehydrated, 100 = quenched)

        # Additional character info from GMCP
        self.status = []  # List of status effects (e.g., "poisoned", "invisible")
        self.stats = {}  # Dictionary for character stats (str, int, wis, etc.)
        self.bank = 0
        self.quest_points = 0
        self.trivia_points = 0

        # GMCP-specific data
        self.area_name = ""
        self.room_terrain = ""
        self.room_coords = {}
        self.room_details = ""
        self.room_num = 0

        # Day/night cycle tracking
        self.day_night_cycle = (
            "unknown"  # Can be "day", "night", "dawn", "dusk", or "unknown"
        )
        self.last_day_night_check = 0  # Timestamp of last day/night check

        # Rich console for formatted output
        self.console = Console()

        # Flag for update tracking
        self.update_needed = False

        # Thread control
        self.running = False
        self.connected = False  # Flag to indicate when connection is established

        # Observer pattern has been replaced with the event system

        # Tick manager is now managed by the MUDAgent and communicates via events.

        self.events.on("state_update", self.handle_state_update)

    def handle_state_update(self, updates: dict) -> None:
        """Handle state updates from events."""
        if "room" in updates:
            data = updates["room"]
            if isinstance(data, dict):
                self.area_name = data.get("area", self.area_name)
                self.room_terrain = data.get("terrain", self.room_terrain)
                self.room_coords = data.get("coords", self.room_coords)
                self.room_details = data.get("details", self.room_details)
                self.room_num = data.get("num", self.room_num)
                # No need to call emit_status_update() here, as it will be handled by the main update loop

    def get_current_room_data(self) -> dict[str, Any]:
        """Return the current room's data as a dictionary."""
        return {
            "name": self.room_name,
            "num": self.room_num,
            "area": self.area_name,
            "terrain": self.room_terrain,
            "description": self.room_details,
            "details": self.room_details,
            "coords": self.room_coords,
            "exits": self.exits,
            "npcs": self.npcs,
        }

    def update_from_gmcp(self, gmcp_manager) -> None:
        """Update state from GMCP data.

        This method handles all GMCP data updates in a unified way, using the
        update_from_aardwolf_gmcp method for character data and directly updating
        room data.

        Args:
            gmcp_manager: The GMCP manager containing the data
        """
        try:
            # Track what was updated for event emission
            updates = {}

            # Get all character data
            all_data = None
            if hasattr(gmcp_manager, "get_all_character_data"):
                all_data = gmcp_manager.get_all_character_data()

            # Update character data if available
            if all_data and "combined" in all_data:
                # Use the unified method to update character data
                self.update_from_aardwolf_gmcp(all_data["combined"])
                updates["character"] = all_data["combined"]

            # Update room info
            room_info = gmcp_manager.get_room_info()
            if room_info:
                # Update room info directly
                if "name" in room_info:
                    self.room_name = room_info["name"]
                if "area" in room_info:
                    self.area_name = room_info["area"]
                if "exits" in room_info:
                    self.exits = room_info["exits"]
                if "description" in room_info:
                    self.room_details = room_info["description"]
                if "coords" in room_info:
                    self.room_coords = room_info["coords"]
                if "terrain" in room_info:
                    self.room_terrain = room_info["terrain"]
                if "details" in room_info:
                    self.room_details = room_info["details"]
                if "num" in room_info:
                    self.room_num = room_info["num"]

                updates["room"] = room_info
                self.handle_state_update(updates)
                self.logger.debug("Updated state from GMCP room info")

                # Emit room update event
                logging.debug(f"Emitting room_update with data: {room_info}")
                self.events.emit("room_update", **room_info)

            # Emit a general state update event with all updates
            if updates:
                self.logger.debug(
                    f"Emitting state_update event with keys: {list(updates.keys())}"
                )
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(self.events.emit, "state_update", updates)
                else:
                    self.events.emit("state_update", updates)

        except Exception as e:
            self.logger.error(f"Error updating state from GMCP: {e}", exc_info=True)
            # Emit an error event
            self.events.emit("state_error", str(e))

    def update_from_aardwolf_gmcp(self, data: dict[str, Any]) -> None:
        """Update state from Aardwolf GMCP data.

        This method updates the state from Aardwolf-specific GMCP data,
        including character information, vitals, stats, and worth.

        Args:
            data: The GMCP data to update from
        """
        try:
            # Track what was updated for event emission
            updates = {}

            # Update character information
            if data.get("name"):
                self.character_name = data["name"]
                updates["character_name"] = data["name"]

            if data.get("level"):
                self.level = int(data["level"])
                updates["level"] = int(data["level"])

            if data.get("race"):
                self.race = data["race"]
                updates["race"] = data["race"]

            if data.get("class"):
                self.character_class = data["class"]
                updates["character_class"] = data["class"]

            if data.get("subclass"):
                self.subclass = data["subclass"]
                updates["subclass"] = data["subclass"]

            if data.get("alignment"):
                self.alignment = data["alignment"]
                updates["alignment"] = data["alignment"]

            if data.get("clan"):
                self.clan = data["clan"]
                updates["clan"] = data["clan"]

            if data.get("remorts"):
                self.remorts = int(data["remorts"])
                updates["remorts"] = int(data["remorts"])

            if data.get("tier"):
                self.tier = int(data["tier"])
                updates["tier"] = int(data["tier"])

            # Update vitals
            if "hp" in data and data["hp"] is not None:
                hp_value = int(data["hp"])
                self.hp_current = hp_value
                self.health["current"] = hp_value
                updates["hp_current"] = hp_value

            if "maxhp" in data and data["maxhp"] is not None:
                hp_max_value = int(data["maxhp"])
                self.hp_max = hp_max_value
                self.health["max"] = hp_max_value
                updates["hp_max"] = hp_max_value

            if "mana" in data and data["mana"] is not None:
                mana_value = int(data["mana"])
                self.mp_current = mana_value
                self.mana["current"] = mana_value
                updates["mp_current"] = mana_value

            if "maxmana" in data and data["maxmana"] is not None:
                mana_max_value = int(data["maxmana"])
                self.mp_max = mana_max_value
                self.mana["max"] = mana_max_value
                updates["mp_max"] = mana_max_value

            if "moves" in data and data["moves"] is not None:
                moves_value = int(data["moves"])
                self.mv_current = moves_value
                self.movement["current"] = moves_value
                updates["mv_current"] = moves_value

            if "maxmoves" in data and data["maxmoves"] is not None:
                moves_max_value = int(data["maxmoves"])
                self.mv_max = moves_max_value
                self.movement["max"] = moves_max_value
                updates["mv_max"] = moves_max_value

            # Update needs
            if "hunger" in data and data["hunger"] is not None:
                try:
                    hunger_data = data["hunger"]
                    if isinstance(hunger_data, str):
                        try:
                            hunger_data = ast.literal_eval(hunger_data)
                        except (ValueError, SyntaxError):
                            pass  # Fallback to direct int conversion

                    if hasattr(hunger_data, 'get'):  # Duck-typing for dict-like objects
                        hunger_value = int(hunger_data.get("current", 0))
                    else:
                        hunger_value = int(hunger_data)

                    self.hunger_current = hunger_value
                    self.hunger["current"] = hunger_value
                    updates["hunger"] = hunger_value
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not parse hunger value: {data['hunger']}")

            if "thirst" in data and data["thirst"] is not None:
                try:
                    thirst_data = data["thirst"]
                    if isinstance(thirst_data, str):
                        try:
                            thirst_data = ast.literal_eval(thirst_data)
                        except (ValueError, SyntaxError):
                            pass  # Fallback to direct int conversion

                    if hasattr(thirst_data, 'get'):  # Duck-typing for dict-like objects
                        thirst_value = int(thirst_data.get("current", 0))
                    else:
                        thirst_value = int(thirst_data)

                    self.thirst_current = thirst_value
                    self.thirst["current"] = thirst_value
                    updates["thirst"] = thirst_value
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not parse thirst value: {data['thirst']}")

            # Update stats
            for stat_name in ["str", "int", "wis", "dex", "con", "luck", "hr", "dr"]:
                if stat_name in data and data[stat_name] is not None:
                    stat_value = int(data[stat_name])
                    self.stats[stat_name] = stat_value
                    updates[f"{stat_name}_value"] = stat_value

                    # Update reactive attributes
                    if stat_name == "str":
                        self.str_value = stat_value
                    elif stat_name == "int":
                        self.int_value = stat_value
                    elif stat_name == "wis":
                        self.wis_value = stat_value
                    elif stat_name == "dex":
                        self.dex_value = stat_value
                    elif stat_name == "con":
                        self.con_value = stat_value
                    elif stat_name == "luck":
                        self.luck_value = stat_value
                    elif stat_name == "hr":
                        self.hr_value = stat_value
                    elif stat_name == "dr":
                        self.dr_value = stat_value

            # Update max stats
            for stat_name in ["str", "int", "wis", "dex", "con", "luck"]:
                max_stat_name = f"max{stat_name}"
                if max_stat_name in data and data[max_stat_name] is not None:
                    max_stat_value = int(data[max_stat_name])
                    self.stats[max_stat_name] = max_stat_value
                    updates[f"{stat_name}_max"] = max_stat_value

                    # Update reactive attributes
                    if stat_name == "str":
                        self.str_max = max_stat_value
                    elif stat_name == "int":
                        self.int_max = max_stat_value
                    elif stat_name == "wis":
                        self.wis_max = max_stat_value
                    elif stat_name == "dex":
                        self.dex_max = max_stat_value
                    elif stat_name == "con":
                        self.con_max = max_stat_value
                    elif stat_name == "luck":
                        self.luck_max = max_stat_value

            # Update worth
            if "gold" in data and data["gold"] is not None:
                gold_value = int(data["gold"])
                self.gold = gold_value
                updates["gold"] = gold_value

            if "bank" in data and data["bank"] is not None:
                bank_value = int(data["bank"])
                self.bank = bank_value
                updates["bank"] = bank_value

            if "qp" in data and data["qp"] is not None:
                qp_value = int(data["qp"])
                self.quest_points = qp_value
                updates["quest_points"] = qp_value

            if "tp" in data and data["tp"] is not None:
                tp_value = int(data["tp"])
                self.trivia_points = tp_value
                updates["trivia_points"] = tp_value

            if "xp" in data and data["xp"] is not None:
                xp_value = int(data["xp"])
                self.experience = xp_value
                updates["experience"] = xp_value

            # Update status effects
            if "status" in data and isinstance(data["status"], list):
                self.status_effects = data["status"]
                self.status = data["status"]  # For backward compatibility
                updates["status_effects"] = data["status"]

            # Emit events
            if any(
                k in updates
                for k in [
                    "character_name",
                    "level",
                    "race",
                    "character_class",
                    "subclass",
                    "alignment",
                    "clan",
                    "remorts",
                    "tier",
                ]
            ):
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit,
                        "character_update",
                        {
                            k: v
                            for k, v in updates.items()
                            if k
                            in [
                                "character_name",
                                "level",
                                "race",
                                "character_class",
                                "subclass",
                                "alignment",
                                "clan",
                                "remorts",
                                "tier",
                            ]
                        },
                    )
                else:
                    self.events.emit(
                        "character_update",
                        {
                            k: v
                            for k, v in updates.items()
                            if k
                            in [
                                "character_name",
                                "level",
                                "race",
                                "character_class",
                                "subclass",
                                "alignment",
                                "clan",
                                "remorts",
                                "tier",
                            ]
                        },
                    )

            # Check if any vitals were updated
            if any(
                k in updates
                for k in [
                    "hp_current",
                    "hp_max",
                    "mp_current",
                    "mp_max",
                    "mv_current",
                    "mv_max",
                ]
            ):
                # Format vitals in the structure expected by the widgets
                vitals_update = {
                    "hp": {"current": self.hp_current, "max": self.hp_max},
                    "mp": {"current": self.mp_current, "max": self.mp_max},
                    "mv": {"current": self.mv_current, "max": self.mv_max},
                }

                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit, "vitals_update", vitals_update
                    )
                else:
                    self.events.emit("vitals_update", vitals_update)

            # Check if any needs were updated (hunger, thirst)
            if any(k in updates for k in ["hunger", "thirst"]):
                # Format needs in the structure expected by the widgets
                needs_update = {}

                if (
                    "hunger" in updates
                    or "hunger_current" in updates
                    or "hunger_max" in updates
                ):
                    needs_update["hunger"] = {
                        "current": self.hunger["current"],
                        "maximum": self.hunger["max"],
                        "text": self._get_hunger_text(self.hunger["current"]),
                    }

                if (
                    "thirst" in updates
                    or "thirst_current" in updates
                    or "thirst_max" in updates
                ):
                    needs_update["thirst"] = {
                        "current": self.thirst["current"],
                        "maximum": self.thirst["max"],
                        "text": self._get_thirst_text(self.thirst["current"]),
                    }

                if needs_update:
                    if self.agent and hasattr(self.agent, "app"):
                        self.agent.app.call_from_thread(
                            self.events.emit, "needs_update", needs_update
                        )
                    else:
                        self.events.emit("needs_update", needs_update)

            if any(k.endswith("_value") for k in updates):
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit,
                        "stats_update",
                        {k: v for k, v in updates.items() if k.endswith("_value")},
                    )
                else:
                    self.events.emit(
                        "stats_update",
                        {k: v for k, v in updates.items() if k.endswith("_value")},
                    )

            if any(k.endswith("_max") for k in updates):
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit,
                        "maxstats_update",
                        {k: v for k, v in updates.items() if k.endswith("_max")},
                    )
                else:
                    self.events.emit(
                        "maxstats_update",
                        {k: v for k, v in updates.items() if k.endswith("_max")},
                    )

            # Prepare worth update with correct field names for widgets
            worth_updates = {}
            if "gold" in updates:
                worth_updates["gold"] = updates["gold"]
            if "bank" in updates:
                worth_updates["bank"] = updates["bank"]
            if "quest_points" in updates:
                worth_updates["qp"] = updates[
                    "quest_points"
                ]  # Map quest_points to qp for widgets
            if "trivia_points" in updates:
                worth_updates["tp"] = updates[
                    "trivia_points"
                ]  # Map trivia_points to tp for widgets
            if "experience" in updates:
                worth_updates["xp"] = updates[
                    "experience"
                ]  # Map experience to xp for widgets

            # Emit worth update event if we have any worth updates
            if worth_updates:
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit, "worth_update", worth_updates
                    )
                else:
                    self.events.emit("worth_update", worth_updates)

            if "status_effects" in updates:
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit,
                        "status_update",
                        {"status_effects": updates["status_effects"]},
                    )
                else:
                    self.events.emit(
                        "status_update", {"status_effects": updates["status_effects"]}
                    )

            # Emit a general state update event with all updates
            if updates:
                if self.agent and hasattr(self.agent, "app"):
                    self.agent.app.call_from_thread(
                        self.events.emit, "state_update", updates
                    )
                else:
                    self.events.emit("state_update", updates)

        except Exception as e:
            self.logger.error(
                f"Error updating state from Aardwolf GMCP: {e}", exc_info=True
            )
            # Emit an error event
            self.events.emit("state_error", str(e))

    def update_room_info(self, response: str, command: str):
        """Process room updates from text responses for tick detection only.

        Args:
            response: The response from the MUD server
            command: The command that generated the response
        """
        try:
            if self.connected:
                # Store the last response and command
                self.last_response = response
                self.last_command = command

                # Tick detection is now handled by the TickManager via events.

                # Emit an event for room info update
                self.events.emit(
                    "room_text_update", {"response": response, "command": command}
                )
        except Exception as e:
            self.logger.error(f"Error processing room update: {e}", exc_info=True)

    def update_status_info(self, response: str, command: str, in_combat: bool):
        """Store status information for reference.

        Args:
            response: The response from the MUD server
            command: The command that generated the response
            in_combat: Whether the character is currently in combat
        """
        try:
            if self.connected:
                # Store the last response, command, and combat status
                self.last_response = response
                self.last_command = command
                self.in_combat = in_combat

                # Emit an event for status info update
                self.events.emit(
                    "status_text_update",
                    {"response": response, "command": command, "in_combat": in_combat},
                )
        except Exception as e:
            self.logger.error(f"Error processing status update: {e}", exc_info=True)

    def start_threads(self):
        """Start the tick manager thread."""
        try:
            self.running = True

            # The tick manager is now handled by the MUDAgent.
            self.logger.debug("State manager started")

            # Register for client events
            if hasattr(self.agent, "client") and hasattr(self.agent.client, "events"):
                self.agent.client.events.on("connected", self._on_connected)
                self.agent.client.events.on("disconnected", self._on_disconnected)
                self.agent.client.events.on("command_sent", self._on_command_sent)
                self.agent.client.events.on(
                    "command_response", self._on_command_response
                )
                self.agent.client.events.on(
                    "connection_error", self._on_connection_error
                )
                self.agent.client.events.on(
                    "gmcp_data_processed", self._on_gmcp_data_processed
                )
                self.logger.debug("Registered for client events")
        except Exception as e:
            self.logger.error(f"Error starting state manager: {e}", exc_info=True)

    def stop_threads(self):
        """Stop the tick manager thread."""
        try:
            self.running = False

            # The tick manager is now handled by the MUDAgent.
            self.logger.info("State manager stopped")
        except Exception as e:
            self.logger.error(f"Error stopping state manager: {e}", exc_info=True)

    def _on_connected(self, *_):
        """Handle connected events."""
        self.logger.info("Connected to MUD server")
        self.connected = True

    def _on_disconnected(self, *_):
        """Handle disconnected events."""
        self.logger.info("Disconnected from MUD server")
        self.connected = False

    def _on_command_sent(self, command):
        """Handle command sent events.

        Args:
            command: The command that was sent
        """
        self.logger.debug(f"Command sent: {command}")

    def _on_command_response(self, response, *_):
        """Handle command response events.

        Args:
            response: The response from the server
        """
        self.logger.debug(f"Command response received: {len(response)} chars")

    def _on_connection_error(self, error_message):
        """Handle connection error events.

        Args:
            error_message: The error message
        """
        self.logger.error(f"Connection error: {error_message}")
        self.connected = False

    def _on_gmcp_data_processed(self, data):
        """Handle GMCP data processed events.

        Args:
            data: The processed GMCP data
        """
        try:
            self.logger.debug(
                f"GMCP data processed: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
            )

            # If we have a textual app with a GMCP manager, forward the data
            if hasattr(self, '_textual_app') and self._textual_app and hasattr(self._textual_app, 'gmcp_manager'):
                # Extract package and data from the GMCP event
                if isinstance(data, dict) and 'package' in data and 'data' in data:
                    package = data['package']
                    gmcp_data = data['data']
                    self._textual_app.call_from_thread(self._textual_app.gmcp_manager.handle_gmcp_package, package, gmcp_data)
                    self.logger.debug(f"Forwarded GMCP package {package} to textual app GMCP manager")
                elif isinstance(data, dict):
                    # Try to infer package from data structure
                    for key, value in data.items():
                        if key.startswith('gmcp.'):
                            package = key.replace('gmcp.', '')
                            self._textual_app.call_from_thread(self._textual_app.gmcp_manager.handle_gmcp_package, package, value)
                            self.logger.debug(f"Inferred and forwarded GMCP package {package} to textual app")

            # Continue with existing GMCP processing via aardwolf_gmcp manager
            # This ensures compatibility with existing code

        except Exception as e:
            self.logger.error(f"Error processing GMCP data: {e}", exc_info=True)

    def set_connected(self, connected: bool):
        """Set the connected flag.

        Args:
            connected: Whether the MUD client is connected
        """
        self.connected = connected
        self.logger.debug(f"Connection state set to: {connected}")

    def on_tick(self, tick_count: int) -> None:
        """Handle tick events.

        Args:
            tick_count: The current tick count
        """
        # This method is called by the tick manager on each tick
        pass

    # Event-based notification methods
    def emit_status_update(self):
        """Emit status update events using the modern event system."""
        # Prepare status data and emit event
        status_data = {
            "character": {
                "name": self.character_name,
                "level": self.level,
                "race": self.race,
                "class": self.character_class,
                "subclass": self.subclass,
                "alignment": self.alignment,
                "clan": self.clan,
                "remorts": self.remorts,
                "tier": self.tier,
            },
            "vitals": {
                "hp": {"current": self.hp_current, "max": self.hp_max},
                "mp": {"current": self.mp_current, "max": self.mp_max},
                "mv": {"current": self.mv_current, "max": self.mv_max},
            },
            "stats": self.stats,
            "status": self.status_effects,
        }

        # Also emit a specific vitals update event with the same structure
        vitals_update = {
            "hp": {"current": self.hp_current, "max": self.hp_max},
            "mp": {"current": self.mp_current, "max": self.mp_max},
            "mv": {"current": self.mv_current, "max": self.mv_max},
        }
        self.events.emit("vitals_update", vitals_update)

        # Also emit a specific needs update event
        needs_update = {
            "hunger": {
                "current": self.hunger["current"],
                "maximum": self.hunger["max"],
                "text": self._get_hunger_text(self.hunger["current"]),
            },
            "thirst": {
                "current": self.thirst["current"],
                "maximum": self.thirst["max"],
                "text": self._get_thirst_text(self.thirst["current"]),
            },
        }
        self.events.emit("needs_update", needs_update)

        # Emit state update event
        self.events.emit("state_update", status_data)

    def emit_map_update(self):
        """Emit map update events using the modern event system."""
        # Prepare map data and emit event
        map_data = {
            "map": self.map_text if hasattr(self, "map_text") else "",
            "coords": self.room_coords if hasattr(self, "room_coords") else {},
        }

        # Emit map update event
        self.events.emit("map_update", map_data)



    def _get_hunger_text(self, value: int) -> str:
        """Convert a hunger value to a text description.

        Args:
            value: The hunger value (0-100)

        Returns:
            str: Text description of hunger level
        """
        if value >= FULL_THRESHOLD:  # 90+
            return "Full"
        elif value >= SATIATED_THRESHOLD:  # 70+
            return "Satiated"
        elif value >= HUNGRY_THRESHOLD:  # 30+
            return "Hungry"
        else:  # 0-29
            return "Starving"

    def _get_thirst_text(self, value: int) -> str:
        """Convert a thirst value to a text description.

        Args:
            value: The thirst value (0-100)

        Returns:
            str: Text description of thirst level
        """
        if value >= FULL_THRESHOLD:  # 90+
            return "Quenched"
        elif value >= SATIATED_THRESHOLD:  # 70+
            return "Not Thirsty"
        elif value >= HUNGRY_THRESHOLD:  # 30+
            return "Thirsty"
        else:  # 0-29
            return "Parched"

    def get_status_prompt(self) -> str:
        """Generate a formatted status prompt with character information.

        Returns:
            str: A formatted status prompt string
        """
        # Format the status prompt
        status = f"{self.character_name} [{self.level}] "
        status += f"HP:{self.hp_current}/{self.hp_max} "
        status += f"MP:{self.mp_current}/{self.mp_max} "
        status += f"MV:{self.mv_current}/{self.mv_max}"

        return status
