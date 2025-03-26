"""
Occurrence API routes for BC Game Crash Monitor.

This module defines API endpoints for analyzing the frequency of games
meeting various crash point criteria.
"""

import logging
import json
from typing import Dict, Any, List
from aiohttp import web

from ..utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ...db.engine import Database
from ..analytics import occurrences

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()


@routes.get('/api/analytics/occurrences/min-crash-point/{value}')
async def get_min_crash_point_occurrences(request: web.Request) -> web.Response:
    """
    Get the total occurrences of crash points >= specified value.

    Path parameters:
        value (float): Minimum crash point value

    Query parameters:
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)

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

        # Check if analysis should be by time
        by_time_str = request.query.get('by_time', 'false').lower()
        by_time = by_time_str in ('true', '1', 'yes')

        # Get query parameters with defaults
        if by_time:
            try:
                hours = int(request.query.get('hours', '1'))
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
        else:
            try:
                games = int(request.query.get('games', '100'))
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except ValueError:
                return error_response(
                    f"Invalid games: {request.query.get('games')}. Must be a positive integer.",
                    status=400
                )

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                data = await session.run_sync(
                    occurrences.get_min_crash_point_occurrences_by_time,
                    value, hours
                )
            else:
                data = await session.run_sync(
                    occurrences.get_min_crash_point_occurrences_by_games,
                    value, games
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            if by_time:
                data['start_time'] = convert_datetime_to_timezone(
                    data['start_time'], timezone_name)
                data['end_time'] = convert_datetime_to_timezone(
                    data['end_time'], timezone_name)
            else:
                data['first_game_time'] = convert_datetime_to_timezone(
                    data['first_game_time'], timezone_name)
                data['last_game_time'] = convert_datetime_to_timezone(
                    data['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'occurrences': data
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_occurrences: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.get('/api/analytics/occurrences/max-crash-point/{value}')
async def get_max_crash_point_occurrences(request: web.Request) -> web.Response:
    """
    Get the total occurrences of crash points <= specified value.

    Path parameters:
        value (float): Maximum crash point value

    Query parameters:
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get maximum crash point value from the path parameter
        value_str = request.match_info['value']
        try:
            value = float(value_str)
        except ValueError:
            return error_response(
                f"Invalid crash point value: {value_str}. Must be a numeric value.",
                status=400
            )

        # Check if analysis should be by time
        by_time_str = request.query.get('by_time', 'false').lower()
        by_time = by_time_str in ('true', '1', 'yes')

        # Get query parameters with defaults
        if by_time:
            try:
                hours = int(request.query.get('hours', '1'))
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
        else:
            try:
                games = int(request.query.get('games', '100'))
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except ValueError:
                return error_response(
                    f"Invalid games: {request.query.get('games')}. Must be a positive integer.",
                    status=400
                )

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                data = await session.run_sync(
                    occurrences.get_max_crash_point_occurrences_by_time,
                    value, hours
                )
            else:
                data = await session.run_sync(
                    occurrences.get_max_crash_point_occurrences_by_games,
                    value, games
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            if by_time:
                data['start_time'] = convert_datetime_to_timezone(
                    data['start_time'], timezone_name)
                data['end_time'] = convert_datetime_to_timezone(
                    data['end_time'], timezone_name)
            else:
                data['first_game_time'] = convert_datetime_to_timezone(
                    data['first_game_time'], timezone_name)
                data['last_game_time'] = convert_datetime_to_timezone(
                    data['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'max_value': value,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'occurrences': data
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_max_crash_point_occurrences: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.get('/api/analytics/occurrences/exact-floor/{value}')
async def get_exact_floor_occurrences(request: web.Request) -> web.Response:
    """
    Get the total occurrences of exact floor value.

    Path parameters:
        value (int): Floor value

    Query parameters:
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get floor value from the path parameter
        value_str = request.match_info['value']
        try:
            value = int(value_str)
            if value < 1:
                return error_response(
                    f"Invalid floor value: {value}. Must be a positive integer.",
                    status=400
                )
        except ValueError:
            return error_response(
                f"Invalid floor value: {value_str}. Must be an integer.",
                status=400
            )

        # Check if analysis should be by time
        by_time_str = request.query.get('by_time', 'false').lower()
        by_time = by_time_str in ('true', '1', 'yes')

        # Get query parameters with defaults
        if by_time:
            try:
                hours = int(request.query.get('hours', '1'))
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
        else:
            try:
                games = int(request.query.get('games', '100'))
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except ValueError:
                return error_response(
                    f"Invalid games: {request.query.get('games')}. Must be a positive integer.",
                    status=400
                )

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                data = await session.run_sync(
                    occurrences.get_exact_floor_occurrences_by_time,
                    value, hours
                )
            else:
                data = await session.run_sync(
                    occurrences.get_exact_floor_occurrences_by_games,
                    value, games
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            if by_time:
                data['start_time'] = convert_datetime_to_timezone(
                    data['start_time'], timezone_name)
                data['end_time'] = convert_datetime_to_timezone(
                    data['end_time'], timezone_name)
            else:
                data['first_game_time'] = convert_datetime_to_timezone(
                    data['first_game_time'], timezone_name)
                data['last_game_time'] = convert_datetime_to_timezone(
                    data['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'floor_value': value,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'occurrences': data
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_exact_floor_occurrences: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/min-crash-points/batch')
async def get_min_crash_point_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get the total occurrences of crash points >= specified values.

    Request Body:
        values (List[float]): List of minimum crash point values
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)
        comparison (bool, optional): Whether to include comparison with previous period (default: true)

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
        by_time = data.get('by_time', False)
        comparison = data.get('comparison', True)

        # Check and validate parameters based on analysis type
        if by_time:
            hours = data.get('hours', 1)
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
            games = None
        else:
            games = data.get('games', 100)
            try:
                games = int(games)
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except (ValueError, TypeError):
                return error_response(
                    f"Invalid games: {games}. Must be a positive integer.",
                    status=400
                )
            hours = None

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                results = await session.run_sync(
                    occurrences.get_min_crash_point_occurrences_by_time_batch,
                    values, hours, comparison
                )
            else:
                results = await session.run_sync(
                    occurrences.get_min_crash_point_occurrences_by_games_batch,
                    values, games, comparison
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for value_data in results.values():
                if by_time:
                    value_data['start_time'] = convert_datetime_to_timezone(
                        value_data['start_time'], timezone_name)
                    value_data['end_time'] = convert_datetime_to_timezone(
                        value_data['end_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['start_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['start_time'], timezone_name)
                        value_data['comparison']['end_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['end_time'], timezone_name)
                else:
                    value_data['first_game_time'] = convert_datetime_to_timezone(
                        value_data['first_game_time'], timezone_name)
                    value_data['last_game_time'] = convert_datetime_to_timezone(
                        value_data['last_game_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['first_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['first_game_time'], timezone_name)
                        value_data['comparison']['last_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'values': values,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'comparison': comparison,
                    'occurrences': results
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/exact-floors/batch')
async def get_exact_floor_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get the total occurrences of exact floor values.

    Request Body:
        values (List[int]): List of floor values
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)
        comparison (bool, optional): Whether to include comparison with previous period (default: true)

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
                "Field 'values' must be a non-empty list of integer values.",
                status=400
            )

        # Validate and convert values to integers
        try:
            values = [int(v) for v in values]
            for v in values:
                if v < 1:
                    return error_response(
                        f"Invalid floor value: {v}. Must be a positive integer.",
                        status=400
                    )
        except (ValueError, TypeError):
            return error_response(
                "Field 'values' must contain integer values.",
                status=400
            )

        # Get optional parameters with defaults
        by_time = data.get('by_time', False)
        comparison = data.get('comparison', True)

        # Check and validate parameters based on analysis type
        if by_time:
            hours = data.get('hours', 1)
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
            games = None
        else:
            games = data.get('games', 100)
            try:
                games = int(games)
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except (ValueError, TypeError):
                return error_response(
                    f"Invalid games: {games}. Must be a positive integer.",
                    status=400
                )
            hours = None

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                results = await session.run_sync(
                    occurrences.get_exact_floor_occurrences_by_time_batch,
                    values, hours, comparison
                )
            else:
                results = await session.run_sync(
                    occurrences.get_exact_floor_occurrences_by_games_batch,
                    values, games, comparison
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for value_data in results.values():
                if by_time:
                    value_data['start_time'] = convert_datetime_to_timezone(
                        value_data['start_time'], timezone_name)
                    value_data['end_time'] = convert_datetime_to_timezone(
                        value_data['end_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['start_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['start_time'], timezone_name)
                        value_data['comparison']['end_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['end_time'], timezone_name)
                else:
                    value_data['first_game_time'] = convert_datetime_to_timezone(
                        value_data['first_game_time'], timezone_name)
                    value_data['last_game_time'] = convert_datetime_to_timezone(
                        value_data['last_game_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['first_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['first_game_time'], timezone_name)
                        value_data['comparison']['last_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'values': values,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'comparison': comparison,
                    'occurrences': results
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_exact_floor_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/max-crash-points/batch')
async def get_max_crash_point_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get the total occurrences of crash points <= specified values.

    Request Body:
        values (List[float]): List of maximum crash point values
        games (int, optional): Number of recent games to analyze (default: 100)
        hours (int, optional): Number of hours to analyze (default: 1)
        by_time (bool, optional): Whether to analyze by time (default: false)
        comparison (bool, optional): Whether to include comparison with previous period (default: true)

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
        by_time = data.get('by_time', False)
        comparison = data.get('comparison', True)

        # Check and validate parameters based on analysis type
        if by_time:
            hours = data.get('hours', 1)
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
            games = None
        else:
            games = data.get('games', 100)
            try:
                games = int(games)
                if games <= 0:
                    return error_response(
                        f"Invalid games: {games}. Must be a positive integer.",
                        status=400
                    )
            except (ValueError, TypeError):
                return error_response(
                    f"Invalid games: {games}. Must be a positive integer.",
                    status=400
                )
            hours = None

        # Get database session
        async with Database() as session:
            # Get occurrence data
            if by_time:
                results = await session.run_sync(
                    occurrences.get_max_crash_point_occurrences_by_time_batch,
                    values, hours, comparison
                )
            else:
                results = await session.run_sync(
                    occurrences.get_max_crash_point_occurrences_by_games_batch,
                    values, games, comparison
                )

            # Get timezone from request header
            timezone_name = request.headers.get(TIMEZONE_HEADER)

            # Convert datetime values to the requested timezone
            for value_data in results.values():
                if by_time:
                    value_data['start_time'] = convert_datetime_to_timezone(
                        value_data['start_time'], timezone_name)
                    value_data['end_time'] = convert_datetime_to_timezone(
                        value_data['end_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['start_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['start_time'], timezone_name)
                        value_data['comparison']['end_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['end_time'], timezone_name)
                else:
                    value_data['first_game_time'] = convert_datetime_to_timezone(
                        value_data['first_game_time'], timezone_name)
                    value_data['last_game_time'] = convert_datetime_to_timezone(
                        value_data['last_game_time'], timezone_name)

                    if comparison and 'comparison' in value_data:
                        value_data['comparison']['first_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['first_game_time'], timezone_name)
                        value_data['comparison']['last_game_time'] = convert_datetime_to_timezone(
                            value_data['comparison']['last_game_time'], timezone_name)

            # Return the response
            return json_response({
                'status': 'success',
                'data': {
                    'values': values,
                    'by_time': by_time,
                    'params': {'hours': hours} if by_time else {'games': games},
                    'comparison': comparison,
                    'occurrences': results
                }
            })

    except Exception as e:
        logger.exception(
            f"Error in get_max_crash_point_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")
