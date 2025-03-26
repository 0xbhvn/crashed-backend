"""
WebSocket handling for BC Game Crash Monitor.

This module provides real-time updates to connected clients when new games are added.
"""

import json
import logging
from typing import Dict, Set, Any, List
import aiohttp
from aiohttp import web
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class WebSocketManager:
    """
    Manager for WebSocket connections that handles broadcasting updates to all clients.
    """

    def __init__(self):
        """Initialize the websocket manager."""
        self.connections: Set[web.WebSocketResponse] = set()
        logger.info("WebSocket manager initialized")

    async def handle_connection(self, request: web.Request) -> web.WebSocketResponse:
        """
        Handle incoming WebSocket connections.

        Args:
            request: The incoming HTTP request.

        Returns:
            The WebSocket response object.
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Add the connection to our set
        self.connections.add(ws)
        client_id = id(ws)
        logger.info(
            f"WebSocket client connected: {client_id} (Total: {len(self.connections)})")

        try:
            # Send connection confirmation message
            await ws.send_json({
                "type": "connection_established",
                "message": "Connected to BC Game Crash Monitor WebSocket"
            })

            # Listen for messages from client
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                    else:
                        # Just echo back any message received (could implement commands here)
                        await ws.send_json({
                            "type": "echo",
                            "message": msg.data
                        })
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(
                        f"WebSocket connection closed with exception: {ws.exception()}")
        finally:
            # Remove the connection when it's closed
            self.connections.remove(ws)
            logger.info(
                f"WebSocket client disconnected: {client_id} (Total: {len(self.connections)})")

        return ws

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            data: The data to broadcast.
        """
        if not self.connections:
            return

        # Add message type if not present
        if "type" not in data:
            data["type"] = "update"

        # Convert to JSON string using custom encoder for datetime objects
        message = json.dumps(data, cls=DateTimeEncoder)

        # Keep track of closed connections to remove
        closed_connections = set()

        # Send to all connections
        for ws in self.connections:
            if ws.closed:
                closed_connections.add(ws)
                continue

            try:
                await ws.send_str(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                closed_connections.add(ws)

        # Remove any closed connections
        for ws in closed_connections:
            if ws in self.connections:
                self.connections.remove(ws)

        if closed_connections:
            logger.info(
                f"Removed {len(closed_connections)} closed connections. Total connections: {len(self.connections)}")

    async def broadcast_new_game(self, game_data: Dict[str, Any]) -> None:
        """
        Broadcast a new game to all connected clients.

        Args:
            game_data: The new game data to broadcast.
        """
        await self.broadcast({
            "type": "new_game",
            "data": game_data
        })

    async def broadcast_multiple_games(self, games_data: List[Dict[str, Any]]) -> None:
        """
        Broadcast multiple games to all connected clients.

        Args:
            games_data: The list of game data to broadcast.
        """
        await self.broadcast({
            "type": "games_update",
            "data": games_data
        })


# Create a singleton instance
manager = WebSocketManager()


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """
    Handle WebSocket connections.

    Args:
        request: The incoming request.

    Returns:
        The WebSocket response.
    """
    return await manager.handle_connection(request)


def setup_websocket(app: web.Application) -> None:
    """
    Setup WebSocket routes for the application.

    Args:
        app: The web application instance.
    """
    app.router.add_get('/ws', websocket_handler)

    # Store the manager in the app for access elsewhere
    app['websocket_manager'] = manager

    logger.info("WebSocket configured")
