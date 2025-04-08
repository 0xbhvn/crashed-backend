"""
Occurrence API routes for Crash Monitor.

This module defines API endpoints for analyzing the frequency of games
meeting various crash point criteria.
"""

from ...utils.redis_keys import get_cache_version
import logging
import json
import time
from typing import Dict, Any, List, Tuple
from aiohttp import web

from ..utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ...utils.redis_cache import cached_endpoint, build_key_from_match_info, build_key_with_query_param, build_hash_based_key
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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            value = req.match_info['value']
            by_time = req.query.get(
                'by_time', 'false').lower() in ('true', '1', 'yes')
            if by_time:
                hours = req.query.get('hours', '1')
                return f"analytics:occurrences:min:{value}:by_time:true:hours:{hours}:{get_cache_version()}"
            else:
                games = req.query.get('games', '100')
                return f"analytics:occurrences:min:{value}:by_time:false:games:{games}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get minimum crash point value from the path parameter
                value_str = req.match_info['value']
                try:
                    value = float(value_str)
                except ValueError:
                    return {"status": "error", "message": f"Invalid crash point value: {value_str}. Must be a numeric value."}, False

                # Check if analysis should be by time
                by_time_str = req.query.get('by_time', 'false').lower()
                by_time = by_time_str in ('true', '1', 'yes')

                # Get query parameters with defaults
                if by_time:
                    try:
                        hours = int(req.query.get('hours', '1'))
                        if hours <= 0:
                            return {"status": "error", "message": f"Invalid hours: {hours}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid hours: {req.query.get('hours')}. Must be a positive integer."}, False
                else:
                    try:
                        games = int(req.query.get('games', '100'))
                        if games <= 0:
                            return {"status": "error", "message": f"Invalid games: {games}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid games: {req.query.get('games')}. Must be a positive integer."}, False

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrence data
                    if by_time:
                        data = await db.run_sync(
                            occurrences.get_min_crash_point_occurrences_by_time,
                            value, hours
                        )
                    else:
                        data = await db.run_sync(
                            occurrences.get_min_crash_point_occurrences_by_games,
                            value, games
                        )

                    # Get timezone from request header
                    timezone_name = req.headers.get(TIMEZONE_HEADER)

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'min_value': value,
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'occurrences': data
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.exception(
                    f"Error in get_min_crash_point_occurrences data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.exception(f"Error in get_min_crash_point_occurrences: {str(e)}")
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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            value = req.match_info['value']
            by_time = req.query.get(
                'by_time', 'false').lower() in ('true', '1', 'yes')
            if by_time:
                hours = req.query.get('hours', '1')
                return f"analytics:occurrences:max:{value}:by_time:true:hours:{hours}:{get_cache_version()}"
            else:
                games = req.query.get('games', '100')
                return f"analytics:occurrences:max:{value}:by_time:false:games:{games}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get maximum crash point value from the path parameter
                value_str = req.match_info['value']
                try:
                    value = float(value_str)
                except ValueError:
                    return {"status": "error", "message": f"Invalid crash point value: {value_str}. Must be a numeric value."}, False

                # Check if analysis should be by time
                by_time_str = req.query.get('by_time', 'false').lower()
                by_time = by_time_str in ('true', '1', 'yes')

                # Get query parameters with defaults
                if by_time:
                    try:
                        hours = int(req.query.get('hours', '1'))
                        if hours <= 0:
                            return {"status": "error", "message": f"Invalid hours: {hours}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid hours: {req.query.get('hours')}. Must be a positive integer."}, False
                else:
                    try:
                        games = int(req.query.get('games', '100'))
                        if games <= 0:
                            return {"status": "error", "message": f"Invalid games: {games}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid games: {req.query.get('games')}. Must be a positive integer."}, False

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrence data
                    if by_time:
                        data = await db.run_sync(
                            occurrences.get_max_crash_point_occurrences_by_time,
                            value, hours
                        )
                    else:
                        data = await db.run_sync(
                            occurrences.get_max_crash_point_occurrences_by_games,
                            value, games
                        )

                    # Get timezone from request header
                    timezone_name = req.headers.get(TIMEZONE_HEADER)

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'max_value': value,
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'occurrences': data
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.exception(
                    f"Error in get_max_crash_point_occurrences data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.exception(f"Error in get_max_crash_point_occurrences: {str(e)}")
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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            value = req.match_info['value']
            by_time = req.query.get(
                'by_time', 'false').lower() in ('true', '1', 'yes')
            if by_time:
                hours = req.query.get('hours', '1')
                return f"analytics:occurrences:floor:{value}:by_time:true:hours:{hours}:{get_cache_version()}"
            else:
                games = req.query.get('games', '100')
                return f"analytics:occurrences:floor:{value}:by_time:false:games:{games}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get floor value from the path parameter
                value_str = req.match_info['value']
                try:
                    value = int(value_str)
                except ValueError:
                    return {"status": "error", "message": f"Invalid floor value: {value_str}. Must be an integer."}, False

                # Check if analysis should be by time
                by_time_str = req.query.get('by_time', 'false').lower()
                by_time = by_time_str in ('true', '1', 'yes')

                # Get query parameters with defaults
                if by_time:
                    try:
                        hours = int(req.query.get('hours', '1'))
                        if hours <= 0:
                            return {"status": "error", "message": f"Invalid hours: {hours}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid hours: {req.query.get('hours')}. Must be a positive integer."}, False
                else:
                    try:
                        games = int(req.query.get('games', '100'))
                        if games <= 0:
                            return {"status": "error", "message": f"Invalid games: {games}. Must be a positive integer."}, False
                    except ValueError:
                        return {"status": "error", "message": f"Invalid games: {req.query.get('games')}. Must be a positive integer."}, False

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrence data
                    if by_time:
                        data = await db.run_sync(
                            occurrences.get_exact_floor_occurrences_by_time,
                            value, hours
                        )
                    else:
                        data = await db.run_sync(
                            occurrences.get_exact_floor_occurrences_by_games,
                            value, games
                        )

                    # Get timezone from request header
                    timezone_name = req.headers.get(TIMEZONE_HEADER)

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'floor_value': value,
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'occurrences': data
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.exception(
                    f"Error in get_exact_floor_occurrences data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.exception(f"Error in get_exact_floor_occurrences: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/min-crash-points/batch')
async def get_min_crash_point_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get occurrences for multiple minimum crash point values in a batch.

    Request body:
        {
            "values": [float, ...],  # List of minimum crash point values
            "games": int,            # Optional: Number of games to analyze (default: 100)
            "hours": int,            # Optional: Number of hours to analyze
            "by_time": bool          # Optional: Whether to analyze by time (default: false)
            "comparison": bool       # Optional: Whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Use our hash-based key builder for batch endpoints
        key_builder = build_hash_based_key("occurrences:min:batch")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Parse request body
                body = await req.json()

                # Validate values
                values = body.get('values', [])
                if not values:
                    return {"status": "error", "message": "No values provided"}, False

                try:
                    # Convert all values to float
                    values = [float(v) for v in values]
                except ValueError:
                    return {"status": "error", "message": "All values must be numeric"}, False

                # Check if analysis should be by time
                by_time = body.get('by_time', False)
                # Get comparison parameter
                comparison = body.get('comparison', True)

                # Get parameters with defaults
                if by_time:
                    hours = body.get('hours', 1)
                    if not isinstance(hours, int) or hours <= 0:
                        return {"status": "error", "message": "Hours must be a positive integer"}, False
                else:
                    games = body.get('games', 100)
                    if not isinstance(games, int) or games <= 0:
                        return {"status": "error", "message": "Games must be a positive integer"}, False

                # Get timezone from header
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrences for each value with comparison data
                    if by_time:
                        results = await db.run_sync(
                            occurrences.get_min_crash_point_occurrences_by_time_batch,
                            values, hours, comparison
                        )
                    else:
                        results = await db.run_sync(
                            occurrences.get_min_crash_point_occurrences_by_games_batch,
                            values, games, comparison
                        )

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'comparison': comparison,
                            'results': results
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except json.JSONDecodeError:
                return {"status": "error", "message": "Invalid JSON in request body"}, False
            except Exception as e:
                logger.exception(
                    f"Error in get_min_crash_point_occurrences_batch data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with a longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.exception(
            f"Error in get_min_crash_point_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/exact-floors/batch')
async def get_exact_floor_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get occurrences for multiple exact floor values in a batch.

    Request body:
        {
            "values": [int, ...],    # List of floor values
            "games": int,            # Optional: Number of games to analyze (default: 100)
            "hours": int,            # Optional: Number of hours to analyze
            "by_time": bool          # Optional: Whether to analyze by time (default: false)
            "comparison": bool       # Optional: Whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Use our hash-based key builder for batch endpoints
        key_builder = build_hash_based_key("occurrences:floor:batch")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Parse request body
                body = await req.json()

                # Validate values
                values = body.get('values', [])
                if not values:
                    return {"status": "error", "message": "No values provided"}, False

                try:
                    # Convert all values to int
                    values = [int(v) for v in values]
                except ValueError:
                    return {"status": "error", "message": "All values must be integers"}, False

                # Check if analysis should be by time
                by_time = body.get('by_time', False)
                # Get comparison parameter
                comparison = body.get('comparison', True)

                # Get parameters with defaults
                if by_time:
                    hours = body.get('hours', 1)
                    if not isinstance(hours, int) or hours <= 0:
                        return {"status": "error", "message": "Hours must be a positive integer"}, False
                else:
                    games = body.get('games', 100)
                    if not isinstance(games, int) or games <= 0:
                        return {"status": "error", "message": "Games must be a positive integer"}, False

                # Get timezone from header
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrences for each value with comparison data
                    if by_time:
                        results = await db.run_sync(
                            occurrences.get_exact_floor_occurrences_by_time_batch,
                            values, hours, comparison
                        )
                    else:
                        results = await db.run_sync(
                            occurrences.get_exact_floor_occurrences_by_games_batch,
                            values, games, comparison
                        )

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'comparison': comparison,
                            'results': results
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except json.JSONDecodeError:
                return {"status": "error", "message": "Invalid JSON in request body"}, False
            except Exception as e:
                logger.exception(
                    f"Error in get_exact_floor_occurrences_batch data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with a longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.exception(
            f"Error in get_exact_floor_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")


@routes.post('/api/analytics/occurrences/max-crash-points/batch')
async def get_max_crash_point_occurrences_batch(request: web.Request) -> web.Response:
    """
    Get occurrences for multiple maximum crash point values in a batch.

    Request body:
        {
            "values": [float, ...],  # List of maximum crash point values
            "games": int,            # Optional: Number of games to analyze (default: 100)
            "hours": int,            # Optional: Number of hours to analyze
            "by_time": bool          # Optional: Whether to analyze by time (default: false)
            "comparison": bool       # Optional: Whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Use our hash-based key builder for batch endpoints
        key_builder = build_hash_based_key("occurrences:max:batch")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Parse request body
                body = await req.json()

                # Validate values
                values = body.get('values', [])
                if not values:
                    return {"status": "error", "message": "No values provided"}, False

                try:
                    # Convert all values to float
                    values = [float(v) for v in values]
                except ValueError:
                    return {"status": "error", "message": "All values must be numeric"}, False

                # Check if analysis should be by time
                by_time = body.get('by_time', False)
                # Get comparison parameter
                comparison = body.get('comparison', True)

                # Get parameters with defaults
                if by_time:
                    hours = body.get('hours', 1)
                    if not isinstance(hours, int) or hours <= 0:
                        return {"status": "error", "message": "Hours must be a positive integer"}, False
                else:
                    games = body.get('games', 100)
                    if not isinstance(games, int) or games <= 0:
                        return {"status": "error", "message": "Games must be a positive integer"}, False

                # Get timezone from header
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database and session
                db = Database()
                async with db as session:
                    # Get occurrences for each value with comparison data
                    if by_time:
                        results = await db.run_sync(
                            occurrences.get_max_crash_point_occurrences_by_time_batch,
                            values, hours, comparison
                        )
                    else:
                        results = await db.run_sync(
                            occurrences.get_max_crash_point_occurrences_by_games_batch,
                            values, games, comparison
                        )

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
                    response_data = {
                        'status': 'success',
                        'data': {
                            'by_time': by_time,
                            'params': {'hours': hours} if by_time else {'games': games},
                            'comparison': comparison,
                            'results': results
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except json.JSONDecodeError:
                return {"status": "error", "message": "Invalid JSON in request body"}, False
            except Exception as e:
                logger.exception(
                    f"Error in get_max_crash_point_occurrences_batch data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with a longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.exception(
            f"Error in get_max_crash_point_occurrences_batch: {str(e)}")
        return error_response(f"An error occurred: {str(e)}")

# Import at the end to avoid circular import issues
