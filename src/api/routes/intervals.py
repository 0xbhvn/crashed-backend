"""
Interval API routes for BC Game Crash Monitor.

This module defines API endpoints for analyzing game data in intervals
to identify patterns and occurrences.
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


@routes.get('/api/analytics/intervals/min-crash-point/{value}')
async def get_min_crash_point_intervals(request: web.Request) -> web.Response:
    """
    Get occurrences of >= X crash point in time intervals.

    Path parameters:
        value (float): Minimum crash point threshold

    Query parameters:
        interval_minutes (int, optional): Size of each interval in minutes (default: 10)
        hours (int, optional): Total hours to analyze (default: 24)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
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
            interval_minutes = int(request.query.get('interval_minutes', '10'))
            if interval_minutes <= 0:
                return error_response(
                    f"Invalid interval_minutes: {interval_minutes}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid interval_minutes: {request.query.get('interval_minutes')}. Must be a positive integer.",
                status=400
            )

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

        # Get database session
        async with Database() as session:
            # Get interval data
            intervals = await session.run_sync(
                analytics.get_min_crash_point_intervals_by_time,
                value, interval_minutes, hours
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for interval in intervals:
                interval['interval_start'] = convert_datetime_to_timezone(
                    interval['interval_start'], timezone_name)
                interval['interval_end'] = convert_datetime_to_timezone(
                    interval['interval_end'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'interval_minutes': interval_minutes,
                    'hours': hours,
                    'count': len(intervals),
                    'intervals': intervals
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_intervals: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.get('/api/analytics/intervals/min-crash-point/{value}/game-sets')
async def get_min_crash_point_intervals_by_sets(request: web.Request) -> web.Response:
    """
    Get occurrences of >= X crash point in game set intervals.

    Path parameters:
        value (float): Minimum crash point threshold

    Query parameters:
        games_per_set (int, optional): Number of games in each set (default: 10)
        total_games (int, optional): Total games to analyze (default: 1000)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
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
            games_per_set = int(request.query.get('games_per_set', '10'))
            if games_per_set <= 0:
                return error_response(
                    f"Invalid games_per_set: {games_per_set}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid games_per_set: {request.query.get('games_per_set')}. Must be a positive integer.",
                status=400
            )

        try:
            total_games = int(request.query.get('total_games', '1000'))
            if total_games <= 0:
                return error_response(
                    f"Invalid total_games: {total_games}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid total_games: {request.query.get('total_games')}. Must be a positive integer.",
                status=400
            )

        # Get database session
        async with Database() as session:
            # Get interval data
            intervals = await session.run_sync(
                analytics.get_min_crash_point_intervals_by_game_sets,
                value, games_per_set, total_games
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for interval in intervals:
                interval['start_time'] = convert_datetime_to_timezone(
                    interval['start_time'], timezone_name)
                interval['end_time'] = convert_datetime_to_timezone(
                    interval['end_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'games_per_set': games_per_set,
                    'total_games': total_games,
                    'count': len(intervals),
                    'intervals': intervals
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_intervals_by_sets: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/intervals/min-crash-points')
async def get_min_crash_point_intervals_batch(request: web.Request) -> web.Response:
    """
    Get occurrences of >= X crash points in time intervals.

    Request Body:
        values (List[float]): List of minimum crash point thresholds
        interval_minutes (int, optional): Size of each interval in minutes (default: 10)
        hours (int, optional): Total hours to analyze (default: 24)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get request data
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return error_response(
                "Invalid JSON in request body.",
                status=400
            )

        # Validate required fields
        if 'values' not in data:
            return error_response(
                "Missing required field: 'values'.",
                status=400
            )

        values = data['values']
        if not isinstance(values, list) or not values:
            return error_response(
                "Field 'values' must be a non-empty list of float values.",
                status=400
            )

        # Validate and convert values to floats
        try:
            values = [float(v) for v in values]
        except (ValueError, TypeError):
            return error_response(
                "Field 'values' must contain numeric values.",
                status=400
            )

        # Get optional parameters with defaults
        interval_minutes = data.get('interval_minutes', 10)
        hours = data.get('hours', 24)

        # Validate optional parameters
        try:
            interval_minutes = int(interval_minutes)
            if interval_minutes <= 0:
                return error_response(
                    f"Invalid interval_minutes: {interval_minutes}. Must be a positive integer.",
                    status=400
                )
        except (ValueError, TypeError):
            return error_response(
                f"Invalid interval_minutes: {interval_minutes}. Must be a positive integer.",
                status=400
            )

        try:
            hours = int(hours)
            if hours <= 0:
                return error_response(
                    f"Invalid hours: {hours}. Must be a positive integer.",
                    status=400
                )
        except (ValueError, TypeError):
            return error_response(
                f"Invalid hours: {hours}. Must be a positive integer.",
                status=400
            )

        # Get database session
        async with Database() as session:
            # Get interval data
            intervals_by_value = await session.run_sync(
                analytics.get_min_crash_point_intervals_by_time_batch,
                values, interval_minutes, hours
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for value, intervals in intervals_by_value.items():
                for interval in intervals:
                    interval['interval_start'] = convert_datetime_to_timezone(
                        interval['interval_start'], timezone_name)
                    interval['interval_end'] = convert_datetime_to_timezone(
                        interval['interval_end'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'values': values,
                    'interval_minutes': interval_minutes,
                    'hours': hours,
                    'intervals_by_value': intervals_by_value
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_intervals_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/intervals/min-crash-points/game-sets')
async def get_min_crash_point_intervals_by_sets_batch(request: web.Request) -> web.Response:
    """
    Get occurrences of >= X crash points in game set intervals.

    Request Body:
        values (List[float]): List of minimum crash point thresholds
        games_per_set (int, optional): Number of games in each set (default: 10)
        total_games (int, optional): Total games to analyze (default: 1000)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get request data
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return error_response(
                "Invalid JSON in request body.",
                status=400
            )

        # Validate required fields
        if 'values' not in data:
            return error_response(
                "Missing required field: 'values'.",
                status=400
            )

        values = data['values']
        if not isinstance(values, list) or not values:
            return error_response(
                "Field 'values' must be a non-empty list of float values.",
                status=400
            )

        # Validate and convert values to floats
        try:
            values = [float(v) for v in values]
        except (ValueError, TypeError):
            return error_response(
                "Field 'values' must contain numeric values.",
                status=400
            )

        # Get optional parameters with defaults
        games_per_set = data.get('games_per_set', 10)
        total_games = data.get('total_games', 1000)

        # Validate optional parameters
        try:
            games_per_set = int(games_per_set)
            if games_per_set <= 0:
                return error_response(
                    f"Invalid games_per_set: {games_per_set}. Must be a positive integer.",
                    status=400
                )
        except (ValueError, TypeError):
            return error_response(
                f"Invalid games_per_set: {games_per_set}. Must be a positive integer.",
                status=400
            )

        try:
            total_games = int(total_games)
            if total_games <= 0:
                return error_response(
                    f"Invalid total_games: {total_games}. Must be a positive integer.",
                    status=400
                )
        except (ValueError, TypeError):
            return error_response(
                f"Invalid total_games: {total_games}. Must be a positive integer.",
                status=400
            )

        # Get database session
        async with Database() as session:
            # Get interval data
            intervals_by_value = await session.run_sync(
                analytics.get_min_crash_point_intervals_by_game_sets_batch,
                values, games_per_set, total_games
            )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for value, intervals in intervals_by_value.items():
                for interval in intervals:
                    interval['start_time'] = convert_datetime_to_timezone(
                        interval['start_time'], timezone_name)
                    interval['end_time'] = convert_datetime_to_timezone(
                        interval['end_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'values': values,
                    'games_per_set': games_per_set,
                    'total_games': total_games,
                    'intervals_by_value': intervals_by_value
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_intervals_by_sets_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")
