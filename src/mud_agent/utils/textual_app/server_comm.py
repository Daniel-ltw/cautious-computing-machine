"""Server communication management for the MUD Textual App.

This module handles all server communication, message display,
and connection management.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .core import MUDTextualApp

from ..widgets.command_log import CommandLog
from ..command_log_handler import CommandLogHandler

logger = logging.getLogger(__name__)


class ServerCommunicator:
    """Handles server communication and message display."""
    
    def __init__(self, app: "MUDTextualApp"):
        self.app = app
        self.agent = app.agent
        self.state_manager = app.state_manager
        self.logger = logger
        
        # Communication state
        self._command_log_handler: Optional[logging.Handler] = None
        self._server_message_queue = asyncio.Queue()
        self._processing_messages = False
    
    async def setup_server_message_display(self) -> None:
        """Set up server message display in the command log."""
        try:
            command_log = self.app.query_one("#command-log", CommandLog)
            
            # Create a custom log handler with advanced filtering
            self._command_log_handler = CommandLogHandler(
                command_log=command_log
            )
            # Ensure INFO-level messages like RoomManager logs are shown
            self._command_log_handler.setLevel(logging.INFO)
            
            # Add the handler to the agent's logger if available
            if hasattr(self.agent, 'logger'):
                self.agent.logger.addHandler(self._command_log_handler)
            
            # Also add to the root logger for general messages
            root_logger = logging.getLogger()
            root_logger.addHandler(self._command_log_handler)
            
            logger.info("Server message display setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up server message display: {e}", exc_info=True)
    
    async def display_server_message(self, message: str) -> None:
        """Display a server message in the command log.
        
        Args:
            message: The message to display
        """
        try:
            # Queue the message for processing
            await self._server_message_queue.put(message)
            
            # Start message processing if not already running
            if not self._processing_messages:
                asyncio.create_task(self._process_message_queue())
            
        except Exception as e:
            logger.error(f"Error displaying server message: {e}", exc_info=True)
    
    async def _process_message_queue(self) -> None:
        """Process messages from the server message queue."""
        if self._processing_messages:
            return
        
        self._processing_messages = True
        
        try:
            command_log = self.app.query_one("#command-log", CommandLog)
            
            while not self._server_message_queue.empty():
                try:
                    message = await asyncio.wait_for(
                        self._server_message_queue.get(), timeout=0.1
                    )
                    
                    # Display the message in the command log
                    command_log.write(message)
                    
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Error processing server message: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error in message processing: {e}", exc_info=True)
        finally:
            self._processing_messages = False
    
    async def send_command_to_server(self, command: str, is_user_command: bool = False) -> None:
        """Send a command to the server.
        
        Args:
            command: The command to send
            is_user_command: Whether this is a user-initiated command
        """
        try:
            if hasattr(self.agent, "client") and self.agent.client.connected:
                await self.agent.client.send_command(command, is_user_command=is_user_command)
                logger.debug(f"Sent command to server: '{command}'")
            else:
                logger.warning(f"Cannot send command '{command}': not connected to server")
                
                # Display error in command log
                try:
                    command_log = self.app.query_one("#command-log", CommandLog)
                    command_log.write("[bold red]Not connected to server[/bold red]")
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Error sending command to server: {e}", exc_info=True)
            
            # Display error in command log
            try:
                command_log = self.app.query_one("#command-log", CommandLog)
                command_log.write(f"[bold red]Error sending command: {e}[/bold red]")
            except Exception:
                pass
    
    async def connect_to_server(self) -> bool:
        """Connect to the server.
        
        Returns:
            True if connection was successful, False otherwise
        """
        try:
            if hasattr(self.agent, "client"):
                await self.agent.client.connect()
                
                # Initialize GMCP if available
                if hasattr(self.agent, "aardwolf_gmcp"):
                    await self.agent.aardwolf_gmcp.initialize()
                
                logger.info("Connected to server")
                
                # Display success in command log
                try:
                    command_log = self.app.query_one("#command-log", CommandLog)
                    command_log.write("[bold green]Connected to server[/bold green]")
                except Exception:
                    pass
                
                return True
            else:
                logger.error("No client available for connection")
                return False
        
        except Exception as e:
            logger.error(f"Error connecting to server: {e}", exc_info=True)
            
            # Display error in command log
            try:
                command_log = self.app.query_one("#command-log", CommandLog)
                command_log.write(f"[bold red]Connection failed: {e}[/bold red]")
            except Exception:
                pass
            
            return False
    
    async def disconnect_from_server(self) -> None:
        """Disconnect from the server."""
        try:
            if hasattr(self.agent, "client") and self.agent.client.connected:
                await self.agent.client.disconnect()
                logger.info("Disconnected from server")
                
                # Display message in command log
                try:
                    command_log = self.app.query_one("#command-log", CommandLog)
                    command_log.write("[bold yellow]Disconnected from server[/bold yellow]")
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Error disconnecting from server: {e}", exc_info=True)
    
    async def reconnect_to_server(self) -> bool:
        """Reconnect to the server.
        
        Returns:
            True if reconnection was successful, False otherwise
        """
        try:
            # Display reconnection message
            try:
                command_log = self.app.query_one("#command-log", CommandLog)
                command_log.write("[bold yellow]Reconnecting to server...[/bold yellow]")
            except Exception:
                pass
            
            # Disconnect first if connected
            await self.disconnect_from_server()
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Connect again
            success = await self.connect_to_server()
            
            if success:
                # Display success message
                try:
                    command_log = self.app.query_one("#command-log", CommandLog)
                    command_log.write("[bold green]Reconnected to server[/bold green]")
                except Exception:
                    pass
            
            return success
        
        except Exception as e:
            logger.error(f"Error reconnecting to server: {e}", exc_info=True)
            
            # Display error in command log
            try:
                command_log = self.app.query_one("#command-log", CommandLog)
                command_log.write(f"[bold red]Reconnection failed: {e}[/bold red]")
            except Exception:
                pass
            
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to the server.
        
        Returns:
            True if connected, False otherwise
        """
        try:
            return hasattr(self.agent, "client") and self.agent.client.connected
        except Exception:
            return False
    
    def get_connection_status(self) -> dict:
        """Get current connection status information.
        
        Returns:
            Dictionary containing connection status
        """
        try:
            connected = self.is_connected()
            
            status = {
                'connected': connected,
                'client_available': hasattr(self.agent, "client"),
                'gmcp_available': hasattr(self.agent, "aardwolf_gmcp")
            }
            
            # Add additional client info if available
            if hasattr(self.agent, "client"):
                client = self.agent.client
                status.update({
                    'host': getattr(client, 'host', 'Unknown'),
                    'port': getattr(client, 'port', 'Unknown')
                })
            
            return status
        
        except Exception as e:
            logger.error(f"Error getting connection status: {e}", exc_info=True)
            return {'connected': False, 'error': str(e)}
    
    async def cleanup(self) -> None:
        """Clean up server communication resources."""
        try:
            # Remove command log handler
            if self._command_log_handler:
                # Remove from agent logger
                if hasattr(self.agent, 'logger'):
                    self.agent.logger.removeHandler(self._command_log_handler)
                
                # Remove from root logger
                root_logger = logging.getLogger()
                root_logger.removeHandler(self._command_log_handler)
                
                self._command_log_handler = None
            
            # Clear message queue
            while not self._server_message_queue.empty():
                try:
                    self._server_message_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            logger.info("Server communication cleanup complete")
        
        except Exception as e:
            logger.error(f"Error during server communication cleanup: {e}", exc_info=True)
    
    def get_message_queue_size(self) -> int:
        """Get the current size of the message queue.
        
        Returns:
            Number of messages in the queue
        """
        return self._server_message_queue.qsize()


# CommandLogHandler is now imported from command_log_handler.py
# which provides advanced filtering capabilities for debugging messages