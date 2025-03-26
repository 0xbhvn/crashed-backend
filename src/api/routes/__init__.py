"""
API routes package for BC Game Crash Monitor.

This package contains all the route handlers for the application's API endpoints.
"""

import logging
from aiohttp import web

# Import route handlers from submodules
from .games import routes as games_routes
from .last_games import routes as last_games_routes
from .occurrences import routes as occurrences_routes
from .series import routes as series_routes
from .intervals import routes as intervals_routes

# Configure logging
logger = logging.getLogger(__name__)


def setup_api_routes(app: web.Application) -> None:
    """
    Setup all API routes for the application.

    Args:
        app: The web application instance
    """
    # Add all route tables to the app
    app.add_routes(games_routes)
    app.add_routes(last_games_routes)
    app.add_routes(occurrences_routes)
    app.add_routes(series_routes)
    app.add_routes(intervals_routes)

    logger.info("API routes configured")
