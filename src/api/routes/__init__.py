"""
API routes package for Crash Monitor.

This package contains all the route handlers for the application's API endpoints.
"""

import logging
from aiohttp import web
import platform
import sys
import os
import time
import redis

# Import route handlers from submodules
from .games import routes as games_routes
from .last_games import routes as last_games_routes
from .occurrences import routes as occurrences_routes
from .series import routes as series_routes
from .intervals import routes as intervals_routes

# Import Redis utilities
from ...utils.redis import is_redis_available, get_redis_client
from ... import config

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


@basic_routes.get('/status')
async def system_status(request: web.Request) -> web.Response:
    """
    Detailed system status endpoint that returns information about the application,
    including Redis connection status and memory usage.
    """
    # Basic application info
    status_data = {
        "app": {
            "name": config.APP_NAME,
            "version": config.APP_VERSION,
            "environment": os.environ.get("ENVIRONMENT", "unknown"),
            "uptime": time.time() - request.app.get("start_time", time.time())
        },
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor()
        },
        "database": {
            "enabled": config.DATABASE_ENABLED,
            "connected": request.app.get("db") is not None
        },
        "redis": {
            "enabled": config.REDIS_ENABLED,
            "connected": False,
            "info": {}
        }
    }

    # Redis status information
    if config.REDIS_ENABLED:
        redis_available = is_redis_available()
        status_data["redis"]["connected"] = redis_available

        if redis_available:
            try:
                with get_redis_client() as client:
                    # Get memory info
                    memory_info = client.info("memory")
                    # Get server info
                    server_info = client.info("server")

                    status_data["redis"]["info"] = {
                        "version": server_info.get("redis_version", "unknown"),
                        "used_memory": memory_info.get("used_memory_human", "unknown"),
                        "peak_memory": memory_info.get("used_memory_peak_human", "unknown"),
                        "memory_policy": memory_info.get("maxmemory_policy", "unknown"),
                        "total_connections_received": server_info.get("total_connections_received", 0),
                        "connected_clients": server_info.get("connected_clients", 0)
                    }
            except redis.RedisError as e:
                status_data["redis"]["error"] = str(e)

    return web.json_response(status_data)


def setup_api_routes(app: web.Application) -> None:
    """
    Setup all API routes for the application.

    Args:
        app: The web application instance
    """
    # Store start time for uptime calculation
    app["start_time"] = time.time()

    # Add the basic routes first (includes healthcheck and status)
    app.add_routes(basic_routes)

    # Add all other route tables to the app
    app.add_routes(games_routes)
    app.add_routes(last_games_routes)
    app.add_routes(occurrences_routes)
    app.add_routes(series_routes)
    app.add_routes(intervals_routes)

    logger.info("API routes configured")
