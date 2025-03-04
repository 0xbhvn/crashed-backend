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
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
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

    # Get all config variables
    config_dict = get_config()

    # Mask sensitive values
    masked_config = config_dict.copy()

    # Mask database URL if it contains password
    if 'DATABASE_URL' in masked_config:
        db_url = masked_config['DATABASE_URL']
        if '@' in db_url:
            # Simple masking - replace everything between :// and @ with :*****@
            parts = db_url.split('@')
            protocol_parts = parts[0].split('://')

            if len(protocol_parts) > 1:
                masked_db_url = f"{protocol_parts[0]}://***** and password *****@{parts[1]}"
                masked_config['DATABASE_URL'] = masked_db_url

    # Mask other sensitive values (add as needed)
    sensitive_keys = ['BC_GAME_SALT']
    for key in sensitive_keys:
        if key in masked_config and masked_config[key]:
            masked_config[key] = '***** MASKED *****'

    # Log each configuration value
    logger.info("Current configuration:")
    for key, value in sorted(masked_config.items()):
        logger.info(f"  {key}: {value}")
