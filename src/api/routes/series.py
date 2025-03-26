"""
Series API routes for Crash Monitor.

This module defines API endpoints for fetching series of games without
crash points above certain thresholds.
"""

import logging
import json
from typing import Dict, Any
from aiohttp import web

from ..utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ...db.engine import Database
from .. import analytics

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()


@routes.get('/api/analytics/series/without-min-crash-point/{value}')
async def get_series_without_min_crash_point(request: web.Request) -> web.Response:
    """
    Get series of games without crash points >= specified value in the last N games.

    Path parameters:
        value (float): Minimum crash point threshold

    Query parameters:
        limit (int, optional): Number of games to analyze (default: 1000)
        sort_by (string, optional): How to sort results - 'time' (default) or 'length'

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get minimum crash point value from the path parameter
        value_str = request.match_info['value']
        try:
            value = float(value_str)
        except ValueError:
            return error_response(
                f"Invalid crash point value: {value_str}. Must be a numeric value.",
                status=400
            )

        # Get query parameters with defaults
        try:
            limit = int(request.query.get('limit', '1000'))
            if limit <= 0:
                return error_response(
                    f"Invalid limit: {limit}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid limit: {request.query.get('limit')}. Must be a positive integer.",
                status=400
            )

        sort_by = request.query.get('sort_by', 'time')
        if sort_by not in ['time', 'length']:
            return error_response(
                f"Invalid sort_by value: {sort_by}. Must be 'time' or 'length'.",
                status=400
            )

        # Get database and session
        db = Database()
        async with db as session:
            # Get series data
            series_list = await db.run_sync(
                analytics.get_series_without_min_crash_point_by_games,
                value, limit, sort_by
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for series in series_list:
                series['start_time'] = convert_datetime_to_timezone(
                    series['start_time'], timezone_name)
                series['end_time'] = convert_datetime_to_timezone(
                    series['end_time'], timezone_name)

                # Also convert time values in follow_streak.games if they exist
                if 'follow_streak' in series and 'games' in series['follow_streak']:
                    for game in series['follow_streak']['games']:
                        if 'time' in game:
                            game['time'] = convert_datetime_to_timezone(
                                game['time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'limit': limit,
                    'sort_by': sort_by,
                    'count': len(series_list),
                    'series': series_list
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_series_without_min_crash_point: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.get('/api/analytics/series/without-min-crash-point/{value}/time')
async def get_series_without_min_crash_point_by_time(request: web.Request) -> web.Response:
    """
    Get series of games without crash points >= specified value in the last N hours.

    Path parameters:
        value (float): Minimum crash point threshold

    Query parameters:
        hours (int, optional): Hours to look back (default: 24)
        sort_by (string, optional): How to sort results - 'time' (default) or 'length'

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get minimum crash point value from the path parameter
        value_str = request.match_info['value']
        try:
            value = float(value_str)
        except ValueError:
            return error_response(
                f"Invalid crash point value: {value_str}. Must be a numeric value.",
                status=400
            )

        # Get query parameters with defaults
        try:
            hours = int(request.query.get('hours', '24'))
            if hours <= 0:
                return error_response(
                    f"Invalid hours: {hours}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid hours: {request.query.get('hours')}. Must be a positive integer.",
                status=400
            )

        sort_by = request.query.get('sort_by', 'time')
        if sort_by not in ['time', 'length']:
            return error_response(
                f"Invalid sort_by value: {sort_by}. Must be 'time' or 'length'.",
                status=400
            )

        # Get database and session
        db = Database()
        async with db as session:
            # Get series data
            series_list = await db.run_sync(
                analytics.get_series_without_min_crash_point_by_time,
                value, hours, sort_by
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for series in series_list:
                series['start_time'] = convert_datetime_to_timezone(
                    series['start_time'], timezone_name)
                series['end_time'] = convert_datetime_to_timezone(
                    series['end_time'], timezone_name)

                # Also convert time values in follow_streak.games if they exist
                if 'follow_streak' in series and 'games' in series['follow_streak']:
                    for game in series['follow_streak']['games']:
                        if 'time' in game:
                            game['time'] = convert_datetime_to_timezone(
                                game['time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'hours': hours,
                    'sort_by': sort_by,
                    'count': len(series_list),
                    'series': series_list
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_series_without_min_crash_point_by_time: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")
