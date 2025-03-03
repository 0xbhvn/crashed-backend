#!/usr/bin/env python3
"""
BC Game Crash Monitor Launcher

This script loads environment variables from .env file and runs the monitor.
"""
import os
import sys
import logging

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)


def load_env(env_file='.env'):
    """Load environment variables from .env file."""
    if not os.path.exists(env_file):
        logger.warning(f"{env_file} not found. Using default values.")
        return

    logger.info(f"Loading environment from {env_file}")

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=', 1)
            os.environ[key] = value

    # Verify PostgreSQL connection - set to default if not available
    if 'DATABASE_URL' not in os.environ:
        logger.warning(
            "DATABASE_URL not found in environment. Using default PostgreSQL connection.")
        os.environ['DATABASE_URL'] = "postgresql://postgres:password@localhost:5432/bc_crash_db"

    # Check if the database is available - this doesn't actually verify connection
    # just ensures the URL is set for SQLAlchemy to attempt connection later
    logger.info(f"Database URL: {os.environ['DATABASE_URL']}")


def setup_database():
    """Set up database tables if needed."""
    try:
        # Import SQLAlchemy database module
        from src.sqlalchemy_db import get_database

        logger.info("Checking database tables...")

        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.warning(
                "DATABASE_URL not set. Database functionality will be disabled.")
            return False

        # Initialize database and create tables if they don't exist
        db = get_database()
        db.create_tables()

        logger.info("Database tables verified successfully.")
        return True
    except ImportError as e:
        logger.warning(
            f"SQLAlchemy import error: {e}. Database functionality will be disabled.")
        return False
    except Exception as e:
        logger.warning(f"Could not setup database: {e}")
        logger.warning("Database functionality may be limited.")
        return False


def main():
    """Main entry point for the application."""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)

        # Load environment variables
        load_env()

        # Set up database
        database_ready = setup_database()

        # Set database enabled flag based on setup result
        if 'DATABASE_ENABLED' not in os.environ:
            os.environ['DATABASE_ENABLED'] = str(database_ready).lower()

        # Import after environment is loaded
        from src.main import run_monitor
        import asyncio

        logger.info("Starting BC Game Crash Monitor...")
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running monitor: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
