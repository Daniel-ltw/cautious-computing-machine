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
from .utils.command_log_handler import CommandLogHandler
from .utils.logging import setup_logging
from .utils.textual_app import MUDTextualApp
from .utils.textual_integration import TextualIntegration

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
            consolidate_startup=True,
            to_console=False,
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
            logger.error(
                "MUD_USERNAME not found in .env file. Please set it and restart."
            )
            return 1
        else:
            logger.info(f"Using username from .env file: {character_name}")

        # Get password from .env (required)
        password = env_vars.get("MUD_PASSWORD", "")
        if not password:
            logger.error(
                "MUD_PASSWORD not found in .env file. Please set it and restart."
            )
            return 1
        else:
            logger.info("Using password from .env file")

        # Create the Textual app first so we can show the loading screen immediately
        app = MUDTextualApp(agent, agent.state_manager, agent.room_manager)

        # Run the app and the connection logic concurrently
        try:
            # Start the connection and initialization in the background
            init_task = asyncio.create_task(
                connect_and_initialize(agent, character_name, password, config)
            )

            # Run the Textual app (blocks until user quits)
            await app.run_async()

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return 1
        finally:
            # Clean up everything so the process can exit.
            # Order matters: stop data sources first, then consumers,
            # then background workers.
            logger.info("Shutting down...")

            # 1. Disconnect from MUD server — sets client.connected=False
            #    which causes receive_data() loop to exit naturally.
            #    Also cancels the keep-alive task internally.
            try:
                await agent.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

            # 2. Cancel any pending fire-and-forget event tasks on the client
            try:
                await agent.mud_tool.client.events.cancel_pending_tasks()
            except Exception as e:
                logger.error(f"Error cancelling pending event tasks: {e}")

            # 3. Cancel the periodic GMCP update task early — it depends on
            #    the client connection which is now closed.
            gmcp_task = getattr(agent, "gmcp_update_task", None)
            if gmcp_task and not gmcp_task.done():
                gmcp_task.cancel()
                try:
                    await gmcp_task
                except (asyncio.CancelledError, Exception):
                    pass

            # 4. Cancel the init task (may still be connecting/waiting for banner)
            if not init_task.done():
                init_task.cancel()
                try:
                    await init_task
                except (asyncio.CancelledError, Exception):
                    pass

            # 5. Cancel the receive_data task if it was started
            receive_task = getattr(agent.mud_tool.client, "receive_task", None)
            if receive_task and not receive_task.done():
                receive_task.cancel()
                try:
                    await receive_task
                except (asyncio.CancelledError, Exception):
                    pass

            # 6. Stop buff manager
            try:
                await agent.buff_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping buff manager: {e}")

            # 7. Stop tick manager BEFORE state manager — tick callbacks
            #    invoke state_manager.on_tick, so tick must stop first.
            try:
                agent.tick_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping tick manager: {e}")

            # 8. Stop state manager
            if agent.use_threaded_updates:
                try:
                    agent.state_manager.stop_threads()
                except Exception as e:
                    logger.error(f"Error stopping state manager: {e}")

            # 9. Stop the sync worker (cancels _sync_loop task, closes remote DB)
            if agent.sync_worker:
                try:
                    await agent.sync_worker.stop()
                except Exception as e:
                    logger.error(f"Error stopping sync worker: {e}")

            logger.info("Shutdown complete.")

        return 0

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return 1


async def connect_and_initialize(agent, character_name, password, config):
    """Connect to the MUD server and initialize the agent in the background.

    This function runs as a background task while the loading screen is displayed.
    """
    try:
        # Set up managers (including room_manager event subscriptions)
        await agent.setup_managers()
        logger.info("Agent managers initialized")

        # Start background sync if configured
        if agent.sync_worker and agent.config.database.url:
            await agent.sync_worker.start(agent.config.database.url)

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

        return agent.mud_tool.client.receive_task

    except Exception as e:
        logger.error(f"Error in connect_and_initialize: {e}", exc_info=True)
        return False


def main_sync() -> None:
    """Synchronous entry point for console_scripts."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    main_sync()
