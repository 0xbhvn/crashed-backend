#!/usr/bin/env python3
"""
BC Game Crash Monitor - Runner

This script ensures the proper setup of the Python path before running the application.
"""

import os
import sys
import logging
import asyncio

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('runner')

# Add the project directory to Python path to enable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

logger.info(f"Python path set up: {sys.path[0]}")

# Load environment variables from .env file


def load_env(env_file='.env'):
    """Load environment variables from .env file."""
    env_path = os.path.join(current_dir, env_file)
    if not os.path.exists(env_path):
        logger.warning(f"{env_file} not found. Using default values.")
        return

    logger.info(f"Loading environment from {env_file}")

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=', 1)
            os.environ[key] = value

    # Log database URL if present
    if 'DATABASE_URL' in os.environ:
        logger.info(f"Database URL loaded from .env")


# Load environment variables before importing main module
load_env()

# Import and run the main application
try:
    from src.main import run_monitor
    logger.info("Main module imported successfully")

    # Execute the main function
    if __name__ == "__main__":
        try:
            asyncio.run(run_monitor())
            logger.info("Application finished successfully")
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
        except Exception as e:
            logger.error(f"Application error: {e}")
            sys.exit(1)
except ImportError as e:
    logger.error(f"Failed to import main module: {e}")
    sys.exit(1)
