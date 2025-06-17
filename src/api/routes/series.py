"""
Series API routes for Crash Monitor.

This module defines API endpoints for fetching series of games without
crash points above certain thresholds.
"""

from ...utils.redis_keys import get_cache_version
import logging
import time
from typing import Dict, Any, Tuple
from aiohttp import web

from ..utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ...utils.redis_cache import cached_endpoint, build_key_from_match_info, build_key_with_query_param
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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            value = req.match_info['value']
            limit = req.query.get('limit', '1000')
            sort_by = req.query.get('sort_by', 'time')
            return f"analytics:series:min:{value}:limit:{limit}:sort_by:{sort_by}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get minimum crash point value from the path parameter
                value_str = req.match_info['value']
                try:
                    value = float(value_str)
                except ValueError:
                    return {"status": "error", "message": f"Invalid crash point value: {value_str}. Must be a numeric value."}, False

                # Get query parameters with defaults
                try:
                    limit = int(req.query.get('limit', '1000'))
                    if limit <= 0:
                        return {"status": "error", "message": f"Invalid limit: {limit}. Must be a positive integer."}, False
                except ValueError:
                    return {"status": "error", "message": f"Invalid limit: {req.query.get('limit')}. Must be a positive integer."}, False

                sort_by = req.query.get('sort_by', 'time')
                if sort_by not in ['time', 'length']:
                    return {"status": "error", "message": f"Invalid sort_by value: {sort_by}. Must be 'time' or 'length'."}, False

                # Get database and session
                db = Database()
                async with db as session:
                    # Get series data
                    series_list = await db.run_sync(
                        analytics.get_series_without_min_crash_point_by_games,
                        value, limit, sort_by
                    )

                    # Get timezone from request header
                    timezone_name = req.headers.get(TIMEZONE_HEADER)

                    # Convert datetime values to the requested timezone
                    for series in series_list:
                        series['start_time'] = convert_datetime_to_timezone(
                            series['start_time'], timezone_name)
                        series['end_time'] = convert_datetime_to_timezone(
                            series['end_time'], timezone_name)


                    # Return the response
                    response_data = {
                        'status': 'success',
                        'data': {
                            'min_value': value,
                            'limit': limit,
                            'sort_by': sort_by,
                            'count': len(series_list),
                            'series': series_list
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.exception(
                    f"Error in get_series_without_min_crash_point data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with a longer TTL as series analysis is computationally expensive
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            value = req.match_info['value']
            hours = req.query.get('hours', '24')
            sort_by = req.query.get('sort_by', 'time')
            return f"analytics:series:min:time:{value}:hours:{hours}:sort_by:{sort_by}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get minimum crash point value from the path parameter
                value_str = req.match_info['value']
                try:
                    value = float(value_str)
                except ValueError:
                    return {"status": "error", "message": f"Invalid crash point value: {value_str}. Must be a numeric value."}, False

                # Get query parameters with defaults
                try:
                    hours = int(req.query.get('hours', '24'))
                    if hours <= 0:
                        return {"status": "error", "message": f"Invalid hours: {hours}. Must be a positive integer."}, False
                except ValueError:
                    return {"status": "error", "message": f"Invalid hours: {req.query.get('hours')}. Must be a positive integer."}, False

                sort_by = req.query.get('sort_by', 'time')
                if sort_by not in ['time', 'length']:
                    return {"status": "error", "message": f"Invalid sort_by value: {sort_by}. Must be 'time' or 'length'."}, False

                # Get database and session
                db = Database()
                async with db as session:
                    # Get series data
                    series_list = await db.run_sync(
                        analytics.get_series_without_min_crash_point_by_time,
                        value, hours, sort_by
                    )

                    # Get timezone from request header
                    timezone_name = req.headers.get(TIMEZONE_HEADER)

                    # Convert datetime values to the requested timezone
                    for series in series_list:
                        series['start_time'] = convert_datetime_to_timezone(
                            series['start_time'], timezone_name)
                        series['end_time'] = convert_datetime_to_timezone(
                            series['end_time'], timezone_name)

                        # No need to convert follow_streak times anymore since we simplified the structure

                    # Return the response
                    response_data = {
                        'status': 'success',
                        'data': {
                            'min_value': value,
                            'hours': hours,
                            'sort_by': sort_by,
                            'count': len(series_list),
                            'series': series_list
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.exception(
                    f"Error in get_series_without_min_crash_point_by_time data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with a longer TTL as series analysis is computationally expensive
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.exception(
            f"Error in get_series_without_min_crash_point_by_time: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")

# Import at the end to avoid circular import issues
