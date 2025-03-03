#!/usr/bin/env python3
"""
BC Game Crash Monitor - Main Module

This is the main entry point for the BC Game Crash Monitor when run directly.
It sets up the database connection, initializes components, and starts the monitoring loop.
"""

from .sqlalchemy_db import Database
from . import catchup
from . import database
from . import history
import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('main')

# Import internal modules


async def run_monitor(skip_catchup=False):
    """Run the BC Game Crash Monitor"""
    logger.info("Initializing BC Game Crash Monitor...")

    # Determine if database is enabled
    database_enabled = os.environ.get(
        'DATABASE_ENABLED', 'true').lower() == 'true'

    if database_enabled:
        # Connect to database
        logger.info("Connecting to database")
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.warning(
                "DATABASE_URL not set. Using default connection string.")
            database_url = "postgresql://postgres:postgres@localhost:5432/bc_crash_db"

        # Create database instance
        db = Database(database_url)

        # Create session factory
        session_factory = db.get_session

        # Initialize database if necessary
        db.create_tables()

        # Store engine for later cleanup
        engine = db.engine
    else:
        logger.warning(
            "Database storage is disabled. Running in monitoring-only mode.")
        db = None
        engine = None
        session_factory = None

    # Run catchup process if needed
    if not skip_catchup and os.environ.get('CATCHUP_ENABLED', 'true').lower() == 'true':
        # Get catchup parameters from environment
        catchup_pages = int(os.environ.get('CATCHUP_PAGES', '20'))
        catchup_batch_size = int(os.environ.get('CATCHUP_BATCH_SIZE', '20'))

        try:
            # Run catchup process to get missing games
            await catchup.run_catchup(
                database_enabled=database_enabled,
                session_factory=session_factory,
                max_pages=catchup_pages,
                batch_size=catchup_batch_size
            )
        except Exception as e:
            logger.error(f"Error during catchup process: {e}")
            # Continue with monitoring even if catchup fails

    # Create monitor instance
    try:
        monitor = history.BCCrashMonitor(
            database_enabled=database_enabled,
            session_factory=session_factory
        )

        # Run monitor
        logger.info("Starting monitor loop")
        await monitor.run()
    finally:
        # Close database connection
        if database_enabled and db:
            logger.info("Closing database connection")
            # No need to explicitly close with SQLAlchemy - engine disposal happens automatically


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='BC Game Crash Monitor')
    parser.add_argument('--skip-catchup', action='store_true',
                        help='Skip the catchup process on startup')
    return parser.parse_args()


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Run the monitor
    try:
        asyncio.run(run_monitor(skip_catchup=args.skip_catchup))
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
    except Exception as e:
        logger.error(f"Error running monitor: {e}")
        sys.exit(1)
