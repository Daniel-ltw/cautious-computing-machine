"""
MUD agent implementation.

This is the core agent class that coordinates between the various specialized managers.
"""

import asyncio
import logging

from smolagents import LiteLLMModel

from ..client import MudClient
from ..client.tools import MUDClientTool
from ..config import Config
from ..db.sync_worker import SyncWorker
from ..mcp import MCPManager
from ..mcp.game_knowledge_graph import GameKnowledgeGraph
from ..protocols.aardwolf import AardwolfGMCPManager
from ..state import StateManager
from ..utils.event_manager import EventManager
from ..utils.tick_manager import TickManager
from .automation_manager import AutomationManager
from .buff_manager import BuffManager
from .combat_manager import CombatManager
from .decision_engine import DecisionEngine
from .npc_manager import NPCManager
from .quest_manager import QuestManager
from .room_manager import RoomManager


class MUDAgent:
    """MUD agent implementation.

    This class provides the main interface for interacting with the MUD server
    and automating gameplay. It coordinates between various specialized managers
    for different aspects of functionality.
    """

    def __init__(self, config: Config):
        """Initialize the MUD agent.

        Args:
            config: The configuration object
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.events = EventManager()

        # Create MUD client with 10-second keep-alive to prevent idle timeout
        self.client = MudClient(
            host=config.mud.host,
            port=config.mud.port,
            debug_mode=False,
            keep_alive_enabled=True,
            keep_alive_interval=10.0,  # Send keep-alive every 10 seconds
        )

        # Create MUD client tool
        self.mud_tool = MUDClientTool(self.client)

        # Create Aardwolf GMCP manager with configuration
        self.aardwolf_gmcp = AardwolfGMCPManager(
            self.client,
            kg_update_interval=self.config.gmcp.kg_update_interval,
            max_kg_failures=self.config.gmcp.max_kg_failures,
            event_manager=self.events,  # Pass the event manager
        )
        self.aardwolf_gmcp.agent = self

        # Create MCP manager
        self.mcp_manager = MCPManager()

        # The knowledge_graph is now a separate, dedicated manager
        self.knowledge_graph = GameKnowledgeGraph()
        # Use a single shared knowledge graph instance across the agent and MCP manager
        self.mcp_manager.knowledge_graph = self.knowledge_graph

        # Initialize the LiteLLM model for the CodeAgent
        self.model = None
        self.code_agent = None
        if hasattr(self.config, "model") and self.config.model:
            self.model = LiteLLMModel(
                model_id=self.config.model.model_id,
                api_key=self.config.model.api_key,
                api_base=self.config.model.api_base,
            )
            self.logger.info(f"Initialized LiteLLM model: {self.config.model.model_id}")

        # Initialize the state manager first (it replaces the status manager)
        self.state_manager = StateManager(self.events)

        # Initialize all the other managers
        self.room_manager = RoomManager(self)
        self.combat_manager = CombatManager(self.events)
        self.automation_manager = AutomationManager(self.events)
        self.npc_manager = NPCManager(self.events)
        self.decision_engine = DecisionEngine(self.events, self.client)
        self.quest_manager = QuestManager(self)
        self.buff_manager = BuffManager(self)

        # For backward compatibility, alias state_manager as status_manager
        self.status_manager = self.state_manager

        # Initialize the tick manager
        self.tick_manager = TickManager(self.config, self.events)

        # Flag to indicate whether to use threaded updates
        self.use_threaded_updates = False

        # Guard to prevent double setup_managers() calls
        self._managers_setup = False

        # Initialize command processor to None for lazy loading
        self._command_processor = None

        # Initialize sync worker if configured
        self.sync_worker = None
        if config.database.sync_enabled and config.database.url:
            self.sync_worker = SyncWorker(sync_interval=config.database.sync_interval)
            self.logger.info("SyncWorker configured for background sync")

        self.logger.debug("MUD agent initialized")

    async def setup_managers(self):
        """Set up all the managers.

        Idempotent — safe to call multiple times. Event subscriptions are
        only registered on the first call.
        """
        if self._managers_setup:
            self.logger.debug("setup_managers() already called, skipping")
            return
        await self.room_manager.setup()
        await self.quest_manager.setup()
        await self.buff_manager.setup()
        self._managers_setup = True
        self.logger.info("Agent managers setup complete")

    @property
    def command_processor(self):
        """Lazy load the command processor."""
        if self._command_processor is None:
            from .command_processor import CommandProcessor

            self._command_processor = CommandProcessor(self, self.room_manager)
        return self._command_processor

    async def _periodic_gmcp_update(self):
        """Periodically request GMCP updates to ensure UI is fresh."""
        while True:
            try:
                if self.client and self.client.connected:
                    # Request a GMCP update
                    await self.aardwolf_gmcp.request_all_data()
                    self.logger.debug("Periodic GMCP update requested.")
                await asyncio.sleep(5)  # Update every 5 seconds
            except asyncio.CancelledError:
                self.logger.info("Periodic GMCP update task cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error in periodic GMCP update: {e}", exc_info=True)
                await asyncio.sleep(15)  # Wait longer after an error

    async def __aenter__(self):
        """Start the agent when entering context."""
        await self.setup_managers()
        await self.knowledge_graph.initialize()
        await self.mcp_manager.start_server()

        # Start the state manager if threaded updates are enabled
        if self.use_threaded_updates:
            self.state_manager.start_threads()
            self.logger.debug("Started state manager (tick manager thread)")

        # Start the tick manager and register tick handlers
        self.tick_manager.start()
        self.tick_manager.register_tick_callback(self.quest_manager.on_tick)
        self.tick_manager.register_tick_callback(self.state_manager.on_tick)
        self.logger.debug("Started tick manager and registered tick handlers")

        # Start the periodic GMCP update task
        self.gmcp_update_task = asyncio.create_task(self._periodic_gmcp_update())

        # Start background sync if configured
        if self.sync_worker and self.config.database.url:
            await self.sync_worker.start(self.config.database.url)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the agent when exiting context."""
        # Cancel automation task if running
        if (
            self.automation_manager.automation_task
            and not self.automation_manager.automation_task.done()
        ):
            self.automation_manager.automation_task.cancel()
            try:
                await self.automation_manager.automation_task
            except asyncio.CancelledError:
                pass

        # Stop the state manager if enabled
        if self.use_threaded_updates:
            self.state_manager.stop_threads()
            self.logger.info("Stopped state manager (tick thread)")

        # Stop the periodic GMCP update task
        if hasattr(self, "gmcp_update_task") and self.gmcp_update_task:
            self.gmcp_update_task.cancel()
            try:
                await self.gmcp_update_task
            except asyncio.CancelledError:
                pass

        # Stop the tick manager
        self.tick_manager.stop()
        self.logger.info("Stopped tick manager")

        # Stop sync worker
        if self.sync_worker:
            await self.sync_worker.stop()
            self.logger.info("Stopped SyncWorker")

        # Stop MCP manager
        await self.mcp_manager.stop_server()

        # Disconnect from MUD server
        await self.disconnect()

    async def connect_to_mud(self) -> bool | str:
        """Connect to the MUD server.

        Returns:
            Union[bool, str]: True if successful, error message otherwise
        """
        try:
            connected = await self.client.connect(
                host=self.config.mud.host, port=self.config.mud.port
            )

            if connected:
                self.logger.info(
                    f"Connected to {self.config.mud.host}:{self.config.mud.port}"
                )
                # Set the connected flag in the state manager
                if self.use_threaded_updates:
                    self.state_manager.set_connected(True)
                return True
            else:
                error_msg = f"Failed to connect to {self.config.mud.host}:{self.config.mud.port}"
                self.logger.error(error_msg)
                if self.use_threaded_updates:
                    self.state_manager.set_connected(False)
                return error_msg
        except Exception as e:
            error_msg = f"Error connecting to MUD: {e}"
            self.logger.error(error_msg, exc_info=True)
            if self.use_threaded_updates:
                self.state_manager.set_connected(False)
            return error_msg

    async def login(self, character_name: str, password: str) -> bool:
        """Login to the MUD server.

        Args:
            character_name: The character name to login with
            password: The password to login with

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            result = await self.mud_tool.login(character_name, password)
            if result:
                self.state_manager.character_name = character_name
                self.logger.info(f"Logged in as {character_name}")

                # Initialize the knowledge graph before enabling GMCP updates
                try:
                    await self.knowledge_graph.initialize()
                except Exception:
                    self.logger.exception("Failed to initialize knowledge graph")

                # Initialize GMCP support for Aardwolf
                if self.client.gmcp_enabled:
                    await self.aardwolf_gmcp.initialize()
                    self.logger.info("Initialized Aardwolf GMCP support")

                    # Get GMCP status to verify options
                    await self.aardwolf_gmcp.get_gmcp_status()

                    # GMCP initialization already requests all necessary data
                    # No need to send additional requests here
                    self.logger.info("Using GMCP for all game state initialization")
                else:
                    self.logger.warning(
                        "GMCP not enabled - this is required for proper operation"
                    )

                # No need for an initial look command - GMCP provides all room information
                self.logger.debug(
                    "Skipping initial look command - using GMCP for room information"
                )
            else:
                self.logger.error("Failed to login")
            return result
        except Exception as e:
            self.logger.error(f"Error logging in: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """Disconnect from the MUD server."""
        if self.client.connected:
            await self.client.disconnect()
            self.logger.info("Disconnected from MUD server")
            # Set the connected flag in the state manager
            if self.use_threaded_updates:
                self.state_manager.set_connected(False)

    async def send_command(self, command: str, is_speedwalk: bool = False):
        """Send a command to the MUD server.

        Args:
            command: The command to send
            is_speedwalk: Whether the command is a speedwalk command
        """
        await self.command_processor.process_command(command, is_speedwalk)

    def setup_logging(self, debug: bool = False):
        """Set up logging for the agent."""
        level = logging.DEBUG if debug else logging.INFO

    async def enable_automation(self, context: str | None = None) -> None:
        """Enable automation mode.

        Args:
            context: Optional context or instructions for the automation
        """
        await self.automation_manager.enable_automation(context)

    def disable_automation(self) -> None:
        """Disable automation mode."""
        self.automation_manager.disable_automation()

    def get_status_prompt(self) -> str:
        """Generate a formatted status prompt with character information.

        Returns:
            str: A formatted status prompt string
        """
        return self.state_manager.get_status_prompt()

    async def find_and_hunt_npcs(
        self, npc_pattern: str, use_speedwalk: bool = False
    ) -> bool:
        """Find and hunt NPCs/mobs matching a pattern.

        Args:
            npc_pattern: A substring to match in NPC/mob names
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if at least one NPC was found and hunted, False otherwise
        """
        return await self.npc_manager.find_and_hunt_npcs(npc_pattern, use_speedwalk)

    async def find_and_navigate_to_npc(
        self, npc_name: str, use_speedwalk: bool = False
    ) -> bool:
        """Find a path to a specific NPC/mob and navigate there.

        Args:
            npc_name: The name of the NPC/mob to find
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if navigation was successful, False otherwise
        """
        return await self.npc_manager.find_and_navigate_to_npc(npc_name, use_speedwalk)

    async def get_knowledge_graph_summary(self) -> str:
        """Get a formatted summary of the knowledge graph.

        Returns:
            str: A formatted summary of the knowledge graph
        """
        return await self.mcp_manager.get_knowledge_graph_summary_formatted()

    async def get_world_map(self) -> str:
        """Get a merged map of all explored rooms.

        Returns:
            str: A merged map of all explored rooms, or a message if no maps found
        """
        # Map processing is now handled by the knowledge graph
        return await self.mcp_manager.get_world_map()

    def enable_threaded_updates(self, enable: bool = True) -> None:
        """Enable or disable the use of threaded updates for room and status managers.

        This should be called before entering the context manager.

        Args:
            enable: Whether to enable threaded updates
        """
        self.use_threaded_updates = enable
        self.logger.debug(
            f"{'Enabled' if enable else 'Disabled'} threaded updates for room and status managers"
        )

    # Quest-related convenience methods

    async def find_questor(self, use_speedwalk: bool = True) -> bool:
        """Find and navigate to the questor NPC.

        Args:
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if successfully navigated to questor, False otherwise
        """
        return await self.quest_manager.find_questor(use_speedwalk)

    async def request_quest(self) -> bool:
        """Request a new quest from the questor.

        Returns:
            bool: True if a quest was successfully obtained, False otherwise
        """
        return await self.quest_manager.request_quest()

    async def hunt_quest_target(self, use_speedwalk: bool = True) -> bool:
        """Find and hunt the quest target.

        Args:
            use_speedwalk: Whether to use speedwalk commands for faster navigation

        Returns:
            bool: True if the target was successfully hunted, False otherwise
        """
        return await self.quest_manager.hunt_quest_target(use_speedwalk)

    async def complete_quest(self) -> bool:
        """Complete the current quest by returning to the questor.

        Returns:
            bool: True if the quest was successfully completed, False otherwise
        """
        return await self.quest_manager.complete_quest()

    async def check_quest_status(self) -> tuple:
        """Check the status of the current quest.

        Returns:
            tuple: (has_active_quest, status_message)
        """
        return await self.quest_manager.check_quest_status()

    async def check_quest_info(self) -> tuple:
        """Check detailed information about the current quest.

        Returns:
            tuple: (has_quest_info, message, quest_details)
        """
        return await self.quest_manager.check_quest_info()

    async def recall_to_town(self) -> bool:
        """Use the recall command to return to town.

        Returns:
            bool: True if recall was successful, False otherwise
        """
        return await self.quest_manager.recall_to_town()

    async def check_quest_time(self) -> tuple:
        """Check the time until the next quest is available.

        Returns:
            tuple: (can_quest_now, seconds_until_available, status_message)
        """
        return await self.quest_manager.check_quest_time()

    def force_quest_time_check(self) -> None:
        """Force a quest time check by resetting the quest_time_checked flag.

        This will cause the next call to check_quest_time to actually send the quest time command.
        """
        self.quest_manager.force_quest_time_check()

    async def handle_async_tick(self, tick_count: int) -> None:
        """Handle async operations on game ticks.

        This is called by the tick manager to handle async operations that need to be performed on ticks.

        Args:
            tick_count: The current tick count
        """
        try:
            # Call the quest manager's async tick handler
            await self.quest_manager.async_tick_handler(tick_count)

            # Add other async tick handlers here as needed

        except Exception as e:
            self.logger.error(f"Error in async tick handler: {e}", exc_info=True)
