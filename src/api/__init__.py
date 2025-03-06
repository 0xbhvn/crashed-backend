"""
API package for BC Game Crash Monitor.

This package provides the API endpoints and WebSocket functionality
for the BC Game Crash Monitor application.
"""

import logging
from aiohttp import web
from .routes import setup_api_routes
from .websocket import setup_websocket_routes, WebSocketManager

logger = logging.getLogger(__name__)


def setup_api(app: web.Application) -> None:
    """
    Set up the API and WebSocket routes for the application.

    This function should be called from the main application to initialize
    all API and WebSocket routes.

    Args:
        app: The aiohttp application.
    """
    # Set up API routes
    setup_api_routes(app)

    # Set up WebSocket routes
    setup_websocket_routes(app)

    logger.info("API and WebSocket routes configured")

    # Access the WebSocket manager from anywhere using app['websocket_manager']
