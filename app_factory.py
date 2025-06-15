"""
Application factory for development server.
This module creates the aiohttp app for use with aiohttp-devtools.
"""

import logging
from aiohttp import web
from src.api import setup_api
from src.utils.env import load_env, get_env_var
from src import config
from src.utils.redis import setup_redis, is_redis_available
from src.db.engine import Database
from src.utils import configure_logging


async def create_app():
    """Create and configure the aiohttp application with full functionality."""
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
    
    # Log startup info
    dev_mode = get_env_var('ENVIRONMENT', '').lower() == 'development'
    port = int(config.get_env_var('API_PORT', '8000' if dev_mode else '3000'))
    logger.info(f"API configured for port {port} (development mode with hot reload)")
    
    return app