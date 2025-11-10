"""
Main entry point for the MUD agent with reactive Textual UI.

This version uses the Textual UI directly in the main thread and uses reactive attributes
to automatically update the UI when the state changes.
"""

import asyncio
import logging
import sys

from rich.console import Console

from .agent.mud_agent import MUDAgent
from .config.config import Config
from .utils.logging import setup_logging
from .utils.textual_app import MUDTextualApp
from .utils.textual_integration import TextualIntegration
from .utils.command_log_handler import CommandLogHandler

logger = logging.getLogger(__name__)
console = Console()


async def main() -> int:
    """Main entry point for the application with reactive Textual UI."""
    try:
        # Load configuration
        config = Config.load()

        # Set up logging with a more compact format for startup
        setup_logging(
            level=config.log.level,
            format_str="%(asctime)s - %(levelname)s - %(message)s",
            log_file=config.log.file,
            consolidate_startup=True,  # Consolidate startup logs
        )

        # Add the CommandLogHandler to the root logger
        root_logger = logging.getLogger()
        command_log_handler = CommandLogHandler()
        command_log_handler.setLevel(logging.INFO)
        root_logger.addHandler(command_log_handler)

        # Create the agent
        agent = MUDAgent(config)

        # Enable threaded updates for room and status managers
        agent.enable_threaded_updates(True)

        # Create the integration
        integration = TextualIntegration(agent)

        # Load credentials from .env file if available
        from .utils.env_loader import load_env_file

        env_vars = load_env_file()

        # Get character name from .env (required)
        character_name = env_vars.get("MUD_USERNAME", "")
        if not character_name:
            logger.error("MUD_USERNAME not found in .env file. Please set it and restart.")
            return 1
        else:
            logger.info(f"Using username from .env file: {character_name}")

        # Get password from .env (required)
        password = env_vars.get("MUD_PASSWORD", "")
        if not password:
            logger.error("MUD_PASSWORD not found in .env file. Please set it and restart.")
            return 1
        else:
            logger.info("Using password from .env file")

        # Create the Textual app first so we can show the loading screen immediately
        app = MUDTextualApp(agent, agent.state_manager, agent.room_manager)

        # Create a connection task that will run in the background
        connection_task = asyncio.create_task(
            connect_and_initialize(agent, character_name, password, config)
        )

        # Start the agent with context manager
        async with agent:
            try:
                # Run the app - this will show the loading screen immediately
                # while the connection happens in the background
                logger.info("Starting Textual UI with loading screen...")
                logger.info("About to call app.run_async()...")
                await app.run_async()
                logger.info("app.run_async() completed")
            except Exception as e:
                logger.error(f"Error running Textual app: {e}", exc_info=True)
                return 1

            # Clean up
            await agent.disconnect()

            # Cancel the connection task if it's still running
            if not connection_task.done():
                connection_task.cancel()
                try:
                    await connection_task
                except asyncio.CancelledError:
                    pass

            # Cancel the receive task if it exists
            if (
                hasattr(agent.mud_tool.client, "receive_task")
                and agent.mud_tool.client.receive_task
            ):
                agent.mud_tool.client.receive_task.cancel()
                try:
                    await agent.mud_tool.client.receive_task
                except asyncio.CancelledError:
                    pass

        return 0

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return 1


async def connect_and_initialize(agent, character_name, password, config):
    """Connect to the MUD server and initialize the agent in the background.

    This function runs as a background task while the loading screen is displayed.
    """
    try:
        # Connect to the MUD server
        connect_result = await agent.connect_to_mud()
        # Check if connect_result is a string and contains "Failed"
        if (isinstance(connect_result, str) and "Failed" in connect_result) or (
            isinstance(connect_result, bool) and not connect_result
        ):
            logger.error("Failed to connect to MUD server")
            return False

        # Log in
        if not await agent.login(character_name, password):
            logger.error("Failed to login")
            return False

        # Start receiving data in a background task
        agent.mud_tool.client.receive_task = asyncio.create_task(
            agent.mud_tool.client.receive_data()
        )

        # Wait for the welcome banner with intelligent detection
        from .utils.initialization import detect_welcome_banner

        await detect_welcome_banner(agent)

        # Print startup message
        logger.info("=== Connection Established ===")
        logger.info(
            "MUD Agent connected to %s as %s",
            f"{config.mud.host}:{config.mud.port}",
            character_name,
        )

        # Set a flag in the agent to indicate that connection is complete
        agent.connection_complete = True

        return True

    except Exception as e:
        logger.error(f"Error in connect_and_initialize: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
