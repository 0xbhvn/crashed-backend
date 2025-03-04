"""
Environment variable handling utilities.

This module provides functions for loading environment variables from .env files
and managing configuration.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env(env_file='.env'):
    """
    Load environment variables from .env file.

    Args:
        env_file (str): Path to the .env file, relative to the current directory 
                        or absolute. Defaults to '.env'.

    Returns:
        bool: True if environment variables were loaded successfully, False otherwise.
    """
    # Handle both relative and absolute paths
    if os.path.isabs(env_file):
        env_path = env_file
    else:
        # If called from anywhere in the project, try to find the .env file
        # Go up two directories from utils/env.py
        project_root = Path(__file__).parents[2]
        env_path = os.path.join(project_root, env_file)

    if not os.path.exists(env_path):
        logger.warning(f"{env_file} not found. Using default values.")
        return False

    logger.info(f"Loading environment from {env_path}")

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Handle quoted values
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if they exist
                if value and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]

                os.environ[key] = value

        # Log database connection (with masked password)
        if 'DATABASE_URL' in os.environ:
            masked_url = os.environ['DATABASE_URL']
            if '@' in masked_url:
                # Mask password in the connection string for logging
                parts = masked_url.split('@')
                auth_parts = parts[0].split(':')
                if len(auth_parts) > 2:  # Has password
                    masked_url = f"{auth_parts[0]}:****@{parts[1]}"
            logger.info(f"Database URL loaded from .env: {masked_url}")

        return True
    except Exception as e:
        logger.error(f"Error loading environment: {str(e)}")
        return False


def get_env_var(key, default=None):
    """
    Get an environment variable, with a fallback default value.

    Args:
        key (str): Environment variable name
        default: Default value if the environment variable is not set

    Returns:
        The value of the environment variable, or the default value
    """
    return os.environ.get(key, default)
