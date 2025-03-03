#!/usr/bin/env python3
"""
BC Game Crash Monitor - Main Module

This is the main entry point for the BC Game Crash Monitor when run directly.
It sets up the database connection, initializes components, and starts the monitoring loop.
"""

import src.history as history
import src.database as database
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('main')

# Import after path setup


async def setup_database():
    """Initialize the database connection."""
    if os.environ.get('DATABASE_ENABLED', 'true').lower() != 'true':
        logger.info("Database is disabled, skipping initialization")
        return False

    try:
        # Initialize database connection
        await database.init_database()
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Continuing without database functionality")
        return False


async def main():
    """Main entry point for the monitor."""
    try:
        # Setup database
        db_initialized = await setup_database()

        # Start the monitoring loop
        logger.info("Starting BC Game Crash Monitor")
        await history.main()

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        # Clean up database connection if it was initialized
        if 'db_initialized' in locals() and db_initialized:
            logger.info("Closing database connection")
            await database.close_database()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
