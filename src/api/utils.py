"""
Utility functions for the BC Game Crash Monitor API.

This module provides helper functions for the API.
"""

import logging
import json
import pytz
from datetime import datetime
from typing import Dict, Any, Optional, Union

from .. import config

# Configure logging
logger = logging.getLogger(__name__)

# Define default timezone for API responses (overrides config.TIMEZONE if it's UTC)
DEFAULT_API_TIMEZONE = 'Asia/Kolkata'

# Header name for timezone configuration
TIMEZONE_HEADER = 'X-Timezone'


def convert_datetime_to_timezone(dt: Optional[datetime], timezone_name: Optional[str] = None) -> Optional[str]:
    """
    Convert UTC datetime to the specified timezone.

    Args:
        dt: Datetime object to convert
        timezone_name: Optional timezone name from request header

    Returns:
        ISO formatted datetime string in the target timezone or None if dt is None
    """
    if dt is None:
        return None

    # Determine which timezone to use:
    # 1. Use timezone from header if provided and valid
    # 2. Use Asia/Kolkata if config.TIMEZONE is UTC
    # 3. Otherwise use the configured timezone
    try:
        if timezone_name:
            # Try to use the timezone from the header
            app_timezone = pytz.timezone(timezone_name)
        elif config.TIMEZONE == 'UTC':
            # If config is UTC, default to Asia/Kolkata
            app_timezone = pytz.timezone(DEFAULT_API_TIMEZONE)
        else:
            # Otherwise use the configured timezone
            app_timezone = pytz.timezone(config.TIMEZONE)
    except pytz.exceptions.UnknownTimeZoneError:
        # If timezone is invalid, log warning and use default
        logger.warning(
            f"Unknown timezone: {timezone_name}, using default instead")
        app_timezone = pytz.timezone(DEFAULT_API_TIMEZONE)

    # Ensure the datetime has timezone info (UTC)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)

    # Convert to configured timezone
    converted_dt = dt.astimezone(app_timezone)
    return converted_dt.isoformat()


def json_response(data: Dict[str, Any], status: int = 200) -> str:
    """
    Create a JSON response with the given data.

    Args:
        data: The data to convert to JSON
        status: The HTTP status code

    Returns:
        JSON string with the given data
    """
    from aiohttp import web

    # Convert to JSON manually
    response_json = json.dumps(data)

    return web.Response(
        body=response_json.encode('utf-8'),
        status=status,
        content_type='application/json'
    )


def error_response(message: str, status: int = 500) -> str:
    """
    Create an error response with the given message.

    Args:
        message: The error message
        status: The HTTP status code

    Returns:
        JSON string with the error message
    """
    error_data = {
        'status': 'error',
        'message': message
    }

    return json_response(error_data, status)
