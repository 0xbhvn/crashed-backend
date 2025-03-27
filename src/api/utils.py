"""
Utility functions for the Crash Monitor API.

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


def parse_datetime(date_str: str, timezone_name: Optional[str] = None) -> datetime:
    """
    Parse a date string into a datetime object with timezone information.

    Args:
        date_str: Date string in ISO format (YYYY-MM-DD or full ISO datetime)
        timezone_name: Optional timezone name to use when parsing the date

    Returns:
        Datetime object with timezone information

    Raises:
        ValueError: If the date string cannot be parsed
    """
    try:
        # Try to parse as full ISO datetime first
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt
        except ValueError:
            pass

        # Try to parse as date only (YYYY-MM-DD)
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            # Parse as date only (defaults to midnight)
            dt = datetime.strptime(date_str, '%Y-%m-%d')

            # Determine timezone to use
            try:
                if timezone_name:
                    # Use timezone from header
                    tz = pytz.timezone(timezone_name)
                elif config.TIMEZONE == 'UTC':
                    # Default to Asia/Kolkata if config is UTC
                    tz = pytz.timezone(DEFAULT_API_TIMEZONE)
                else:
                    # Use configured timezone
                    tz = pytz.timezone(config.TIMEZONE)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(
                    f"Unknown timezone: {timezone_name}, using UTC instead")
                tz = pytz.utc

            # Localize the datetime to the specified timezone then convert to UTC
            dt = tz.localize(dt).astimezone(pytz.utc)
            return dt

        raise ValueError(f"Unsupported date format: {date_str}")
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {str(e)}")
        raise ValueError(
            f"Invalid date format: {date_str}. Expected ISO format.")


def convert_datetime_to_timezone(dt: Optional[Union[datetime, str]], timezone_name: Optional[str] = None) -> Optional[str]:
    """
    Convert UTC datetime to the specified timezone.

    Args:
        dt: Datetime object or ISO formatted string to convert
        timezone_name: Optional timezone name from request header

    Returns:
        ISO formatted datetime string in the target timezone or None if dt is None
    """
    if dt is None:
        return None

    # If dt is already a string (ISO format), try to parse it
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            logger.error(f"Failed to parse datetime string: {dt}")
            return dt  # Return original string if parsing fails

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
