"""
Command processor for the MUD agent.

This module contains the command processing logic for the MUD agent.
"""

import logging

logger = logging.getLogger(__name__)


class CommandProcessor:
    """Command processor for the MUD agent.

    This class handles the processing of commands sent to the MUD server.
    """

    def __init__(self, agent, room_manager):
        """Initialize the command processor.

        Args:
            agent: The parent MUD agent
            room_manager: The room manager instance
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)
        self.room_manager = room_manager

    async def process_command(self, command: str, is_speedwalk: bool = False) -> str:
        """Process a command and return the response.

        Args:
            command: The command to process. Can contain multiple commands separated by semicolons.
            is_speedwalk: Whether this command is part of a speedwalk sequence

        Returns:
            str: The response from the MUD server
        """
        try:
            if ";" in command:
                # Split by semicolon, respecting that some might be empty if multiple ; are used
                sub_commands = [cmd.strip() for cmd in command.split(";") if cmd.strip()]
                responses = []
                for sub_cmd in sub_commands:
                    response = await self._process_single_command(sub_cmd, is_speedwalk=is_speedwalk)
                    responses.append(response)
                return "\n".join(responses)
            else:
                return await self._process_single_command(command, is_speedwalk=is_speedwalk)

        except Exception as e:
            error_msg = f"Error processing command: {e}"
            self.logger.error(error_msg, exc_info=True)
            return error_msg

    async def _process_single_command(
        self, command: str, is_speedwalk: bool = False
    ) -> str:
        """Process a single command and return the response.

        Args:
            command: The single command to process
            is_speedwalk: Whether this command is part of a speedwalk sequence

        Returns:
            str: The response from the MUD server
        """
        try:
            # Intercept recall command if a custom one is configured
            if (
                command.lower() == "recall"
                and hasattr(self.agent.config, "agent")
                and self.agent.config.agent.recall_command
            ):
                self.logger.info(f"Intercepting recall command, replacing with: {self.agent.config.agent.recall_command}")
                command = self.agent.config.agent.recall_command

            # Capture the current room number BEFORE sending the command to avoid race condition
            # where GMCP updates arrive before the command_sent handler runs
            from_room_num = None
            if hasattr(self.agent, 'room_manager'):
                from_room_num = self.agent.room_manager._get_current_room_num()
                self.logger.debug(f"Captured from_room_num={from_room_num} BEFORE sending command '{command}'")

            # Emit the command_sent event before processing
            if hasattr(self.agent, "events"):
                await self.agent.events.emit("command_sent", command=command, from_room_num=from_room_num, is_speedwalk=is_speedwalk)

            # Store the last command
            self.agent.last_command = command

            # The room_manager now listens for the `command_sent` event, so the direct
            # call to `capture_outgoing_command` is no longer needed and has been removed
            # to prevent a race condition that was clearing pre-commands.

            # Send the command to the MUD server
            response = await self.agent.mud_tool.forward(command)

            # After sending the command, the 'command_sent' event (with from_room_num) has already been emitted.
            # The RoomManager will handle the command via the event listener, so no direct call is needed.
            # No direct call to room_manager._handle_command_sent here anymore.

            # For look commands, room data will be sent automatically by the server
            if command.lower() == "look" or command.lower() == "l":
                self.logger.debug(
                    "Look command detected, room data will be received automatically"
                )
                # Wait a moment for any additional responses to come in
                import asyncio

                await asyncio.sleep(0.5)

                # Check if the response is too short or only contains quest timer info
                if (
                    len(response) < 100
                    or "minutes remaining until you can go on another quest" in response
                ):
                    self.logger.debug(
                        f"Look response may be incomplete, length: {len(response)}"
                    )
                    # Try to get a more complete response from the client's command responses
                    if (
                        hasattr(self.agent.client, "command_responses")
                        and self.agent.client.command_responses
                    ):
                        full_response = "\n".join(self.agent.client.command_responses)
                        if len(full_response) > len(response):
                            self.logger.debug(
                                f"Using more complete response from client, length: {len(full_response)}"
                            )
                            response = full_response

            # Store the last response
            self.agent.last_response = response

            # Process the response for tick detection
            self.agent.tick_manager.process_server_response(response)

            # Process any pending async operations
            await self._process_async_operations()

            # Check if we're in combat to prioritize status updates
            in_combat = self.agent.combat_manager.is_in_combat(response)

            # If using threaded updates, send updates to the state manager
            if self.agent.use_threaded_updates:
                # Send updates to the state manager
                self.agent.state_manager.update_room_info(response, command)
                self.agent.state_manager.update_status_info(
                    response, command, in_combat
                )
            # Process GMCP updates directly
            elif hasattr(self.agent, "aardwolf_gmcp"):
                updates = self.agent.aardwolf_gmcp.update_from_gmcp()
                if updates:
                    self.logger.debug(f"Updated from GMCP: {', '.join(updates.keys())}")

                    # Process room updates
                    if "room" in updates:
                        room_info = self.agent.aardwolf_gmcp.get_room_info()
                        await self.agent.room_manager.update_from_aardwolf_gmcp(
                            room_info
                        )

                    # Process character updates
                    if "char" in updates:
                        char_stats = self.agent.aardwolf_gmcp.get_character_stats()
                        self.agent.state_manager.update_from_aardwolf_gmcp(char_stats)
            return response
        except Exception as e:
            error_msg = f"Error processing command: {e}"
            self.logger.error(error_msg, exc_info=True)
            return error_msg



    async def _process_async_operations(self) -> None:
        """Process any pending async operations from the tick manager.

        This is called after each command to process any pending async operations.
        """
        try:
            # Get all pending async operations
            operations = self.agent.tick_manager.get_async_operations()

            # Process each operation
            for tick_count in operations:
                self.logger.debug(f"Processing async operation for tick {tick_count}")
                await self.agent.handle_async_tick(tick_count)

            # Process any queued MUD commands from the state manager
            if self.agent.use_threaded_updates and hasattr(
                self.agent.state_manager, "process_mud_commands"
            ):
                for command in self.agent.state_manager.process_mud_commands():
                    self.logger.debug(
                        f"Processing queued command from state manager: {command}"
                    )
                    await self.agent.send_command(command)

            # Map updates are now handled by the knowledge graph

            # Room updates are now handled by the knowledge graph

            # Map processing is now handled by the knowledge graph



        except Exception as e:
            self.logger.error(f"Error processing async operations: {e}", exc_info=True)
