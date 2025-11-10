"""
Initialization functions for the MUD agent.

This module contains functions for initializing the MUD agent and game state.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def detect_welcome_banner(agent, timeout=5):
    """Detect when the welcome banner has completed.

    Args:
        agent: The MUD agent
        timeout: Maximum time to wait in seconds

    Returns:
        bool: True if welcome banner detected, False if timeout
    """
    start_time = time.time()
    banner_patterns = [
        "Welcome to Aardwolf",
        "Type 'help' for help",
        "Type 'news' for news",
        "Type 'who' to see who's online",
        "By what name do you wish to be known",  # Login prompt
        "Password:",  # Password prompt
        "Last login",  # Login success message
        "You were last logged in",  # Another login success message
        "Welcome back",  # Another login success message
    ]

    try:
        # Check if we've already received the welcome banner in the last response
        if hasattr(agent, "last_response") and agent.last_response:
            if any(
                pattern.lower() in agent.last_response.lower()
                for pattern in banner_patterns
            ):
                logger.debug("Welcome banner already detected in last response")
                return True

        # If we don't have a response yet, send a newline to trigger a response
        if not hasattr(agent, "last_response") or not agent.last_response:
            logger.debug("No response yet, sending newline to trigger response")
            try:
                await asyncio.wait_for(agent.send_command(""), timeout=2.0)
            except TimeoutError:
                logger.warning("Timeout sending newline, continuing anyway")
            except Exception as e:
                logger.error(f"Error sending newline: {e}", exc_info=True)

        # Wait for the welcome banner with timeout
        check_interval = 0.05  # Check more frequently for faster detection
        while time.time() - start_time < timeout:
            # Check if any of the banner patterns are in the last response
            if hasattr(agent, "last_response") and agent.last_response:
                if any(
                    pattern.lower() in agent.last_response.lower()
                    for pattern in banner_patterns
                ):
                    elapsed = time.time() - start_time
                    logger.debug(f"Welcome banner detected after {elapsed:.2f} seconds")
                    return True

            # Check if GMCP is enabled and we have character data
            if (
                hasattr(agent, "client")
                and hasattr(agent.client, "gmcp_enabled")
                and agent.client.gmcp_enabled
            ):
                if hasattr(agent, "aardwolf_gmcp"):
                    try:
                        # Update from GMCP
                        updates = agent.aardwolf_gmcp.update_from_gmcp()
                        if updates and "char" in updates:
                            logger.debug(
                                "GMCP character data received, assuming welcome banner complete"
                            )
                            return True
                    except Exception as e:
                        logger.error(f"Error updating from GMCP: {e}", exc_info=True)

            await asyncio.sleep(check_interval)

        # If we still don't have a banner, assume it's already passed
        logger.warning(
            f"Welcome banner not detected after {timeout} seconds, continuing anyway"
        )
        return True

    except Exception as e:
        logger.error(f"Error in detect_welcome_banner: {e}", exc_info=True)
        # Always return True to allow the application to continue
        return True


async def initialize_game_state(agent):
    """Initialize the game state with room info, map, and character stats.

    Args:
        agent: The MUD agent

    Returns:
        bool: True if initialization was successful
    """
    try:
        logger.debug("Initializing game state...")

        # Check if GMCP is enabled and we have character data
        if agent.client.gmcp_enabled and agent.aardwolf_gmcp:
            # Try to initialize using GMCP first (faster and more reliable)
            logger.debug("Attempting to initialize game state using GMCP...")

            # GMCP data will be received automatically from the server
            if agent.client.gmcp_enabled:
                logger.debug(
                    "GMCP data will be received automatically during initialization"
                )

            # Update from GMCP again to ensure we have the latest data
            updates = agent.aardwolf_gmcp.update_from_gmcp()

            # Check if we have the necessary data
            has_char_data = "char" in updates
            has_room_data = "room" in updates
            has_map_data = "map" in updates

            # Update state manager with GMCP data
            if has_char_data:
                char_stats = agent.aardwolf_gmcp.get_character_stats()
                agent.state_manager.update_from_aardwolf_gmcp(char_stats)
                logger.debug(
                    "Updated state manager with GMCP character data during initialization"
                )

            # GMCP data will be received automatically if missing
            if not (has_char_data and has_room_data):
                logger.debug("Missing some GMCP data, will be received automatically...")
                # Wait a moment for the data to be processed
                await asyncio.sleep(0.5)

                # Update from GMCP again
                updates = agent.aardwolf_gmcp.update_from_gmcp()
                has_char_data = has_char_data or "char" in updates
                has_room_data = has_room_data or "room" in updates
                has_map_data = has_map_data or "map" in updates

                # Update state manager again
                if "char" in updates:
                    char_stats = agent.aardwolf_gmcp.get_character_stats()
                    agent.state_manager.update_from_aardwolf_gmcp(char_stats)
                    logger.debug(
                        "Updated state manager with GMCP character data after second request"
                    )

            if has_char_data and has_room_data:
                logger.debug("Successfully initialized game state using GMCP")

                # With GMCP, we don't need to send look, map, or score commands
                # All the necessary data is already available through GMCP
                logger.debug(
                    "Using GMCP data for initialization - no need for look/map/score commands"
                )

                return True

        # If GMCP failed, log a warning but continue
        logger.warning("GMCP initialization failed, but continuing anyway")
        logger.info(
            "Note: We now rely entirely on GMCP for initialization - no fallback to command-based initialization"
        )

        # Return true to allow the application to continue
        return True
    except Exception as e:
        logger.error(f"Error initializing game state: {e}", exc_info=True)
        return False


# This function has been removed as we now rely entirely on GMCP for mapping
# No need to save map data to disk anymore
