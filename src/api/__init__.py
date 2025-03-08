"""
API package for BC Game Crash Monitor.

This package provides the API endpoints and WebSocket functionality
for the BC Game Crash Monitor application.
"""

import logging
from aiohttp import web
from .routes import setup_api_routes
from .websocket import setup_websocket_routes, WebSocketManager
from .hash_verify import setup_hash_verify_routes

logger = logging.getLogger(__name__)

# CORS middleware function


@web.middleware
async def cors_middleware(request, handler):
    """Middleware to handle CORS (Cross-Origin Resource Sharing) headers."""
    # Process the request as normal
    resp = await handler(request)

    # Add CORS headers to all responses
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'

    # Handle CORS preflight requests (OPTIONS)
    if request.method == 'OPTIONS':
        return web.Response(headers=resp.headers)

    return resp


def setup_api(app: web.Application) -> None:
    """
    Set up the API routes for the application.

    This includes all REST endpoints and WebSocket handlers.

    This function should be called from the main application to initialize
    all API and WebSocket routes.

    Args:
        app: The aiohttp application.
    """
    # Add CORS middleware
    app.middlewares.append(cors_middleware)

    # Set up API routes
    setup_api_routes(app)

    # Set up hash verification routes
    setup_hash_verify_routes(app)

    # Set up WebSocket routes
    setup_websocket_routes(app)

    logger.info("API and WebSocket routes configured")

    # Access the WebSocket manager from anywhere using app['websocket_manager']
