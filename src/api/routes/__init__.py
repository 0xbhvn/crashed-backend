"""
API routes package for Crash Monitor.

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

# Create a route table for basic routes
basic_routes = web.RouteTableDef()


@basic_routes.get('/')
async def healthcheck(request: web.Request) -> web.Response:
    """
    Simple healthcheck endpoint that returns a 200 OK response.
    Used by deployment platforms to verify the application is running.
    """
    return web.json_response({
        "status": "ok",
        "message": "Crash Monitor is running"
    })


def setup_api_routes(app: web.Application) -> None:
    """
    Setup all API routes for the application.

    Args:
        app: The web application instance
    """
    # Add the basic routes first (includes healthcheck)
    app.add_routes(basic_routes)

    # Add all other route tables to the app
    app.add_routes(games_routes)
    app.add_routes(last_games_routes)
    app.add_routes(occurrences_routes)
    app.add_routes(series_routes)
    app.add_routes(intervals_routes)

    logger.info("API routes configured")
