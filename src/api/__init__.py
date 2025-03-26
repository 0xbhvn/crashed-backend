"""
API package for Crash Monitor.

This package provides the HTTP API and WebSocket access to the crash data.
"""

import logging
from aiohttp import web
from .routes import setup_api_routes
from .ws import setup_websocket

# Configure logging
logger = logging.getLogger(__name__)


def setup_api(app: web.Application) -> None:
    """
    Setup the API and WebSocket routes.

    Args:
        app: The web application instance
    """
    # Setup API routes
    setup_api_routes(app)

    # Setup WebSocket
    setup_websocket(app)

    logger.info("API routes and WebSocket set up successfully")
