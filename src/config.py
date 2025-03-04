"""
Configuration module for BC Game Crash Monitor.

This module centralizes all configuration values and provides defaults.
It leverages the utils.env module for loading environment variables.
"""

import os
import logging
from typing import Any, Dict

# Try to import get_env_var from utils.env, but provide a fallback
# implementation to avoid circular imports
try:
    from .utils.env import get_env_var
except ImportError:
    # Fallback implementation if utils.env is not yet available
    def get_env_var(key, default=None):
        """Get environment variable with fallback default"""
        return os.environ.get(key, default)

# BC Game API configuration
API_BASE_URL = "https://bc.game"
API_HISTORY_ENDPOINT = "/api/game/bet/multi/history"
GAME_URL = "crash"  # Game URL path for crash game

# API request headers
API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en",
    "content-type": "application/json",
    "origin": "https://bc.game",
    "referer": "https://bc.game/game/crash",
    "user-agent": "Mozilla/5.0 (compatible; BC Game Crash Monitor Bot/0.2.0)"
}

# Page size for API requests (number of games per page)
PAGE_SIZE = int(get_env_var('PAGE_SIZE', '100'))

# Calculation settings
BC_GAME_SALT = get_env_var('BC_GAME_SALT', '')

# Monitoring settings
POLL_INTERVAL = int(get_env_var('POLL_INTERVAL', '5')
                    )  # Poll interval in seconds
RETRY_INTERVAL = int(get_env_var('RETRY_INTERVAL', '10')
                     )  # Retry interval in seconds
MAX_HISTORY_SIZE = int(get_env_var(
    'MAX_HISTORY_SIZE', '1000'))  # Max history size

# Logging settings
LOG_LEVEL = get_env_var('LOG_LEVEL', 'INFO').upper()

# Database settings
DATABASE_ENABLED = get_env_var('DATABASE_ENABLED', 'true').lower() == 'true'
DATABASE_URL = get_env_var(
    'DATABASE_URL', 'postgresql://postgres@localhost:5432/bc_crash_db')

# Catchup settings
CATCHUP_ENABLED = get_env_var('CATCHUP_ENABLED', 'true').lower() == 'true'
CATCHUP_PAGES = int(get_env_var('CATCHUP_PAGES', '20'))
CATCHUP_BATCH_SIZE = int(get_env_var('CATCHUP_BATCH_SIZE', '100'))

# Timezone settings
TIMEZONE = get_env_var('TIMEZONE', 'UTC')

# Application settings
APP_NAME = get_env_var('APP_NAME', 'BC Game Crash Monitor')
APP_VERSION = get_env_var('APP_VERSION', '0.2.0')


def get_config():
    """
    Get the full configuration as a dictionary.

    Returns:
        Dict containing all configuration variables
    """
    # Get all variables defined in this module that don't start with underscore and are uppercase
    return {k: v for k, v in globals().items()
            if not k.startswith('_') and k.isupper()}


def log_config():
    """
    Log the current configuration settings.

    This function masks sensitive values before logging.
    """
    logger = logging.getLogger('config')

    config_dict = get_config()

    # Create a copy to avoid modifying the original
    masked_config = config_dict.copy()

    # Mask sensitive values
    for key in ['DATABASE_URL', 'BC_GAME_SALT']:
        if key in masked_config and masked_config[key]:
            # Mask all but first and last few characters
            value = str(masked_config[key])
            if len(value) > 10:
                masked_config[key] = value[:4] + '****' + value[-4:]
            else:
                masked_config[key] = '****'

    logger.info(f"Configuration: {masked_config}")


def reload_config():
    """
    Reload configuration values from environment variables.

    This function should be called after environment variables
    have been loaded or changed to refresh the configuration.
    """
    global API_BASE_URL, API_HISTORY_ENDPOINT, API_HEADERS, GAME_URL, PAGE_SIZE
    global BC_GAME_SALT
    global POLL_INTERVAL, RETRY_INTERVAL, MAX_HISTORY_SIZE
    global LOG_LEVEL
    global DATABASE_ENABLED, DATABASE_URL
    global CATCHUP_ENABLED, CATCHUP_PAGES, CATCHUP_BATCH_SIZE
    global TIMEZONE
    global APP_NAME, APP_VERSION

    # API settings
    API_BASE_URL = get_env_var('API_BASE_URL', 'https://bc.game')
    API_HISTORY_ENDPOINT = get_env_var(
        'API_HISTORY_ENDPOINT', '/api/game/bet/multi/history')
    GAME_URL = get_env_var('GAME_URL', 'crash')
    PAGE_SIZE = int(get_env_var('PAGE_SIZE', '20'))

    # API headers for requests
    API_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://bc.game",
        "referer": "https://bc.game/game/crash",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }

    # Crash calculation
    BC_GAME_SALT = get_env_var(
        'BC_GAME_SALT', '0000000000000000000301e2801a9a9598bfb114e574a91a887f2132f33047e6')

    # Monitoring settings
    POLL_INTERVAL = int(get_env_var('POLL_INTERVAL', '5'))
    RETRY_INTERVAL = int(get_env_var('RETRY_INTERVAL', '10'))
    MAX_HISTORY_SIZE = int(get_env_var('MAX_HISTORY_SIZE', '100'))

    # Logging settings
    LOG_LEVEL = get_env_var('LOG_LEVEL', 'INFO').upper()

    # Database settings
    DATABASE_ENABLED = get_env_var(
        'DATABASE_ENABLED', 'true').lower() == 'true'
    DATABASE_URL = get_env_var(
        'DATABASE_URL', 'postgresql://postgres@localhost:5432/bc_crash_db')

    # Catchup settings
    CATCHUP_ENABLED = get_env_var('CATCHUP_ENABLED', 'true').lower() == 'true'
    CATCHUP_PAGES = int(get_env_var('CATCHUP_PAGES', '20'))
    CATCHUP_BATCH_SIZE = int(get_env_var('CATCHUP_BATCH_SIZE', '20'))

    # Timezone settings
    TIMEZONE = get_env_var('TIMEZONE', 'UTC')

    # Application settings
    APP_NAME = get_env_var('APP_NAME', 'BC Game Crash Monitor')
    APP_VERSION = get_env_var('APP_VERSION', '0.2.0')

    # Log that config was reloaded
    logger = logging.getLogger('config')
    logger.debug("Configuration reloaded from environment variables")
