#!/usr/bin/env python
"""
Development server with hot reload and full application functionality.

This module provides the app factory for use with adev command.
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiohttp import web
from src import config
from src.api import setup_api
from src.utils.env import load_env
from src.utils import configure_logging
from src.utils.redis import setup_redis, is_redis_available
from src.db.engine import Database
from src.app import run_catchup


# Global variable to store skip_catchup preference
SKIP_CATCHUP = os.environ.get('SKIP_CATCHUP', 'false').lower() == 'true'


async def create_app():
    """
    Create the aiohttp application with full functionality for development.
    This function is called by adev.
    """
    # Load environment variables
    load_env()
    config.reload_config()
    
    # Configure logging
    configure_logging("app", config.LOG_LEVEL)
    logger = logging.getLogger("app")
    
    # Create the app
    app = web.Application()
    
    # Initialize database if enabled
    db = None
    if config.DATABASE_ENABLED:
        try:
            db = Database(connection_string=config.DATABASE_URL)
            app['db'] = db
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Continuing without database support")
    
    # Initialize Redis if enabled
    if config.REDIS_ENABLED:
        try:
            setup_redis()
            if is_redis_available():
                logger.info("Redis connection established")
                app['redis_available'] = True
            else:
                logger.warning("Redis is enabled but not available")
                app['redis_available'] = False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Continuing without Redis support")
            app['redis_available'] = False
    else:
        logger.info("Redis is disabled")
        app['redis_available'] = False
    
    # Setup API routes
    setup_api(app)
    
    # Run catchup if not skipped
    if not SKIP_CATCHUP and config.CATCHUP_ENABLED:
        try:
            logger.info("Running initial catchup process...")
            # Run catchup synchronously to avoid event loop issues
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(run_catchup(
                pages=config.CATCHUP_PAGES,
                batch_size=config.CATCHUP_BATCH_SIZE
            ))
            logger.info("Initial catchup process scheduled")
        except Exception as e:
            logger.error(f"Error scheduling initial catchup process: {e}")
            logger.warning("Continuing despite catchup failure")
    
    # Log startup info
    port = int(config.get_env_var('API_PORT', '8000'))
    logger.info(f"Development server configured for port {port} with hot reload")
    logger.info("Note: Polling is disabled in development mode. Use production mode for full monitoring.")
    
    return app