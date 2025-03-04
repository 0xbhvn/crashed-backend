"""
Configuration module for BC Game Crash Monitor.
Provides default configuration values.
"""
import os
import logging

# API Settings
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://bc.game')
API_HISTORY_ENDPOINT = os.environ.get(
    'API_HISTORY_ENDPOINT', '/api/game/bet/multi/history')
GAME_URL = os.environ.get('GAME_URL', 'crash')
PAGE_SIZE = int(os.environ.get('PAGE_SIZE', '20'))

# Calculation Settings
BC_GAME_SALT = os.environ.get(
    'BC_GAME_SALT', '0000000000000000000301e2801a9a9598bfb114e574a91a887f2132f33047e6')

# Monitoring Settings
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '5'))
RETRY_INTERVAL = int(os.environ.get('RETRY_INTERVAL', '10'))
MAX_HISTORY_SIZE = int(os.environ.get('MAX_HISTORY_SIZE', '10'))

# Logging Settings
LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO')
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR)
VERBOSE_LOGGING = os.environ.get(
    'VERBOSE_LOGGING', 'false').lower() in ('true', 'yes', '1', 't')

# Database Settings
DATABASE_ENABLED = os.environ.get(
    'DATABASE_ENABLED', 'false').lower() in ('true', 'yes', '1', 't')
DATABASE_URL = os.environ.get(
    'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/bc_crash_db')

# Timezone Settings
TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Kolkata')

# HTTP Headers
DEFAULT_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en',
    'content-type': 'application/json',
    'origin': API_BASE_URL,
    'referer': f"{API_BASE_URL}/game/{GAME_URL}",
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
}
