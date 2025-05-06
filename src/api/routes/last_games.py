"""
Last game API routes for Crash Monitor.

This module defines API endpoints for fetching information about the most
recent games that match specific criteria.
"""

import logging
import json
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


@routes.get('/api/analytics/last-game/min-crash-point/{value}')
async def get_last_game_min_crash_point(request: web.Request) -> web.Response:
    """
    Get the most recent game with a crash point greater than or equal to the specified value.

    Path parameters:
        value (float): Minimum crash point value

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing:
        - game data
        - count of games since this game
        - probability of getting this crash point next
    """
    try:
        # Define key builder function
        key_builder = build_key_from_match_info("last_game:min:v2", "value")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to float
                try:
                    value = float(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be a number."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the game
                with db.get_session() as session:
                    result = analytics.get_last_game_min_crash_point(
                        session, value)

                    if result is None:
                        return {"status": "error", "message": f"No games found with crash point >= {value}"}, False

                    game_data, games_since = result

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        game_data['endTime'] = convert_datetime_to_timezone(
                            game_data['endTime'], timezone_name)
                        game_data['prepareTime'] = convert_datetime_to_timezone(
                            game_data['prepareTime'], timezone_name)
                        game_data['beginTime'] = convert_datetime_to_timezone(
                            game_data['beginTime'], timezone_name)

                    response_data = {
                        'status': 'success',
                        'data': {
                            'game': game_data,
                            'games_since': games_since,
                            'probability': {
                                'value': game_data.get('probability', {}).get('value', 0),
                                'formatted': f"{game_data.get('probability', {}).get('value', 0):.2f}%",
                                'description': f"Estimated probability of a crash point ≥ {value}x occurring next"
                            }
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_game_min_crash_point data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(f"Error in get_last_game_min_crash_point: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/last-game/exact-floor/{value}')
async def get_last_game_exact_floor(request: web.Request) -> web.Response:
    """
    Get the most recent game with a crash point floor exactly matching the specified value.

    Path parameters:
        value (int): Exact floor value to match

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing:
        - game data
        - count of games since this game
        - probability of getting this floor value next
    """
    try:
        # Define key builder function
        key_builder = build_key_from_match_info("last_game:floor", "value")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to int
                try:
                    value = int(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be an integer."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the game
                with db.get_session() as session:
                    result = analytics.get_last_game_exact_floor(
                        session, value)

                    if result is None:
                        return {"status": "error", "message": f"No games found with floor value = {value}"}, False

                    game_data, games_since = result

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        game_data['endTime'] = convert_datetime_to_timezone(
                            game_data['endTime'], timezone_name)
                        game_data['prepareTime'] = convert_datetime_to_timezone(
                            game_data['prepareTime'], timezone_name)
                        game_data['beginTime'] = convert_datetime_to_timezone(
                            game_data['beginTime'], timezone_name)

                    response_data = {
                        'status': 'success',
                        'data': {
                            'game': game_data,
                            'games_since': games_since,
                            'probability': {
                                'value': game_data.get('probability', {}).get('value', 0),
                                'formatted': f"{game_data.get('probability', {}).get('value', 0):.2f}%",
                                'description': f"Estimated probability of a crash point with floor {value} occurring next"
                            }
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_game_exact_floor data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(f"Error in get_last_game_exact_floor: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/last-games/min-crash-points')
async def get_last_games_min_crash_points(request: web.Request) -> web.Response:
    """
    Get the most recent games with crash points greater than or equal to each specified value.

    Request body:
        {
            "values": [float]  // List of minimum crash point values
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing results for each value in the input list,
        including probability information
    """
    try:
        # Use our new body-aware key builder
        from ...utils.redis_cache import build_hash_based_key_with_body
        key_builder = build_hash_based_key_with_body(
            "last_games:min:batch:v3")  # Add version to force cache refresh

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get request body
                try:
                    body = await req.json()
                    values = body.get('values', [])
                    if not isinstance(values, list):
                        return {"status": "error", "message": "Invalid request body. 'values' must be a list."}, False
                    if not values:
                        return {"status": "error", "message": "No values provided."}, False
                    # Convert all values to float
                    values = [float(v) for v in values]
                except (json.JSONDecodeError, ValueError):
                    return {"status": "error", "message": "Invalid request body or values."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    results = analytics.get_last_games_min_crash_points(
                        session, values)

                    # Process results and convert timezones if needed
                    processed_results = {}
                    for value, result in results.items():
                        if result is not None:
                            game_data, games_since = result
                            if timezone_name:
                                game_data['endTime'] = convert_datetime_to_timezone(
                                    game_data['endTime'], timezone_name)
                                game_data['prepareTime'] = convert_datetime_to_timezone(
                                    game_data['prepareTime'], timezone_name)
                                game_data['beginTime'] = convert_datetime_to_timezone(
                                    game_data['beginTime'], timezone_name)

                            # Extract probability value from game data
                            probability_value = game_data.get(
                                'probability', {}).get('value', 0)

                            # Remove probability from game_data to avoid duplication
                            if 'probability' in game_data:
                                del game_data['probability']

                            processed_results[str(value)] = {
                                'game': game_data,
                                'games_since': games_since,
                                'probability': probability_value
                            }
                        else:
                            processed_results[str(value)] = None

                    response_data = {
                        'status': 'success',
                        'data': processed_results,
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_games_min_crash_points data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility with longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.error(f"Error in get_last_games_min_crash_points: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/last-games/exact-floors')
async def get_last_games_exact_floors(request: web.Request) -> web.Response:
    """
    Get the most recent games with crash point floors exactly matching each specified value.

    Request body:
        {
            "values": [int]  // List of floor values
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing results for each value in the input list
    """
    try:
        # Use our new utility function for hash-based keys
        from ...utils.redis_cache import build_hash_based_key
        key_builder = build_hash_based_key("last_games:floor:batch")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get request body
                try:
                    body = await req.json()
                    values = body.get('values', [])
                    if not isinstance(values, list):
                        return {"status": "error", "message": "Invalid request body. 'values' must be a list."}, False
                    if not values:
                        return {"status": "error", "message": "No values provided."}, False
                    # Convert all values to int
                    values = [int(v) for v in values]
                except (json.JSONDecodeError, ValueError):
                    return {"status": "error", "message": "Invalid request body or values."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    results = analytics.get_last_games_exact_floors(
                        session, values)

                    # Process results and convert timezones if needed
                    processed_results = {}
                    for value, result in results.items():
                        if result is not None:
                            game_data, games_since = result
                            if timezone_name:
                                game_data['endTime'] = convert_datetime_to_timezone(
                                    game_data['endTime'], timezone_name)
                                game_data['prepareTime'] = convert_datetime_to_timezone(
                                    game_data['prepareTime'], timezone_name)
                                game_data['beginTime'] = convert_datetime_to_timezone(
                                    game_data['beginTime'], timezone_name)
                            processed_results[str(value)] = {
                                'game': game_data,
                                'games_since': games_since
                            }
                        else:
                            processed_results[str(value)] = None

                    response_data = {
                        'status': 'success',
                        'data': processed_results,
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_games_exact_floors data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility with longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.error(f"Error in get_last_games_exact_floors: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/last-game/max-crash-point/{value}')
async def get_last_game_max_crash_point(request: web.Request) -> web.Response:
    """
    Get the most recent game with a crash point less than or equal to the specified value.

    Path parameters:
        value (float): Maximum crash point value

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing:
        - game data
        - count of games since this game
    """
    try:
        # Define key builder function
        key_builder = build_key_from_match_info("last_game:max:v2", "value")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to float
                try:
                    value = float(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be a number."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the game
                with db.get_session() as session:
                    result = analytics.get_last_game_max_crash_point(
                        session, value)

                    if result is None:
                        return {"status": "error", "message": f"No games found with crash point <= {value}"}, False

                    game_data, games_since = result

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        game_data['endTime'] = convert_datetime_to_timezone(
                            game_data['endTime'], timezone_name)
                        game_data['prepareTime'] = convert_datetime_to_timezone(
                            game_data['prepareTime'], timezone_name)
                        game_data['beginTime'] = convert_datetime_to_timezone(
                            game_data['beginTime'], timezone_name)

                    # Extract probability value from game data
                    probability_value = game_data.get(
                        'probability', {}).get('value', 0)

                    # Remove probability from game_data to avoid duplication
                    if 'probability' in game_data:
                        del game_data['probability']

                    response_data = {
                        'status': 'success',
                        'data': {
                            'game': game_data,
                            'games_since': games_since,
                            'probability': probability_value
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_game_max_crash_point data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(f"Error in get_last_game_max_crash_point: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/last-games/max-crash-points')
async def get_last_games_max_crash_points(request: web.Request) -> web.Response:
    """
    Get the most recent games with crash points less than or equal to each specified value.

    Request body:
        {
            "values": [float]  // List of maximum crash point values
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing results for each value in the input list
    """
    try:
        # Use our new body-aware key builder
        from ...utils.redis_cache import build_hash_based_key_with_body
        key_builder = build_hash_based_key_with_body(
            "last_games:max:batch:v3")  # Add version to force cache refresh

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get request body
                try:
                    body = await req.json()
                    values = body.get('values', [])
                    if not isinstance(values, list):
                        return {"status": "error", "message": "Invalid request body. 'values' must be a list."}, False
                    if not values:
                        return {"status": "error", "message": "No values provided."}, False
                    # Convert all values to float
                    values = [float(v) for v in values]
                except (json.JSONDecodeError, ValueError):
                    return {"status": "error", "message": "Invalid request body or values."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    results = analytics.get_last_games_max_crash_points(
                        session, values)

                    # Process results and convert timezones if needed
                    processed_results = {}
                    for value, result in results.items():
                        if result is not None:
                            game_data, games_since = result
                            if timezone_name:
                                game_data['endTime'] = convert_datetime_to_timezone(
                                    game_data['endTime'], timezone_name)
                                game_data['prepareTime'] = convert_datetime_to_timezone(
                                    game_data['prepareTime'], timezone_name)
                                game_data['beginTime'] = convert_datetime_to_timezone(
                                    game_data['beginTime'], timezone_name)

                            # Extract probability value from game data
                            probability_value = game_data.get(
                                'probability', {}).get('value', 0)

                            # Remove probability from game_data to avoid duplication
                            if 'probability' in game_data:
                                del game_data['probability']

                            processed_results[str(value)] = {
                                'game': game_data,
                                'games_since': games_since,
                                'probability': probability_value
                            }
                        else:
                            processed_results[str(value)] = None

                    response_data = {
                        'status': 'success',
                        'data': processed_results,
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_games_max_crash_points data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility with longer TTL for batch requests
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_LONG)

    except Exception as e:
        logger.error(f"Error in get_last_games_max_crash_points: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/last-games/min-crash-point/{value}')
async def get_last_min_crash_point_games_handler(request: web.Request) -> web.Response:
    """
    Get a list of the most recent games with crash points >= the specified value.

    Path parameters:
        value (float): Minimum crash point value

    Query parameters:
        limit (int, optional): Maximum number of games to return (default: 10)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing a list of games matching the criteria
    """
    try:
        # Define key builder function
        key_builder = build_key_with_query_param(
            "last_games:min", "value", "limit")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to float
                try:
                    value = float(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be a number."}, False

                # Get limit from query parameters
                try:
                    limit = int(req.query.get('limit', '10'))
                    if limit <= 0:
                        return {"status": "error", "message": "Limit must be a positive integer."}, False
                except ValueError:
                    return {"status": "error", "message": "Invalid limit parameter. Must be an integer."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    games = analytics.get_last_min_crash_point_games(
                        session, value, limit)

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        for game in games:
                            game['endTime'] = convert_datetime_to_timezone(
                                game['endTime'], timezone_name)
                            game['prepareTime'] = convert_datetime_to_timezone(
                                game['prepareTime'], timezone_name)
                            game['beginTime'] = convert_datetime_to_timezone(
                                game['beginTime'], timezone_name)

                    response_data = {
                        'status': 'success',
                        'data': {
                            'min_value': value,
                            'limit': limit,
                            'count': len(games),
                            'games': games
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_min_crash_point_games_handler data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(
            f"Error in get_last_min_crash_point_games_handler: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/last-games/max-crash-point/{value}')
async def get_last_max_crash_point_games_handler(request: web.Request) -> web.Response:
    """
    Get a list of the most recent games with crash points <= the specified value.

    Path parameters:
        value (float): Maximum crash point value

    Query parameters:
        limit (int, optional): Maximum number of games to return (default: 10)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing a list of games matching the criteria
    """
    try:
        # Define key builder function
        key_builder = build_key_with_query_param(
            "last_games:max", "value", "limit")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to float
                try:
                    value = float(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be a number."}, False

                # Get limit from query parameters
                try:
                    limit = int(req.query.get('limit', '10'))
                    if limit <= 0:
                        return {"status": "error", "message": "Limit must be a positive integer."}, False
                except ValueError:
                    return {"status": "error", "message": "Invalid limit parameter. Must be an integer."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    games = analytics.get_last_max_crash_point_games(
                        session, value, limit)

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        for game in games:
                            game['endTime'] = convert_datetime_to_timezone(
                                game['endTime'], timezone_name)
                            game['prepareTime'] = convert_datetime_to_timezone(
                                game['prepareTime'], timezone_name)
                            game['beginTime'] = convert_datetime_to_timezone(
                                game['beginTime'], timezone_name)

                    response_data = {
                        'status': 'success',
                        'data': {
                            'max_value': value,
                            'limit': limit,
                            'count': len(games),
                            'games': games
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_max_crash_point_games_handler data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(
            f"Error in get_last_max_crash_point_games_handler: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/last-games/exact-floor/{value}')
async def get_last_exact_floor_games_handler(request: web.Request) -> web.Response:
    """
    Get a list of the most recent games with crash point floor exactly matching the specified value.

    Path parameters:
        value (int): Exact floor value

    Query parameters:
        limit (int, optional): Maximum number of games to return (default: 10)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')

    Returns:
        JSON response containing a list of games matching the criteria
    """
    try:
        # Define key builder function
        key_builder = build_key_with_query_param(
            "last_games:floor", "value", "limit")

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get value from path parameter and convert to int
                try:
                    value = int(req.match_info['value'])
                except ValueError:
                    return {"status": "error", "message": "Invalid value parameter. Must be an integer."}, False

                # Get limit from query parameters
                try:
                    limit = int(req.query.get('limit', '10'))
                    if limit <= 0:
                        return {"status": "error", "message": "Limit must be a positive integer."}, False
                except ValueError:
                    return {"status": "error", "message": "Invalid limit parameter. Must be an integer."}, False

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Query the games
                with db.get_session() as session:
                    games = analytics.get_last_exact_floor_games(
                        session, value, limit)

                    # Convert datetime values to specified timezone if provided
                    if timezone_name:
                        for game in games:
                            game['endTime'] = convert_datetime_to_timezone(
                                game['endTime'], timezone_name)
                            game['prepareTime'] = convert_datetime_to_timezone(
                                game['prepareTime'], timezone_name)
                            game['beginTime'] = convert_datetime_to_timezone(
                                game['beginTime'], timezone_name)

                    response_data = {
                        'status': 'success',
                        'data': {
                            'floor_value': value,
                            'limit': limit,
                            'count': len(games),
                            'games': games
                        },
                        'cached_at': int(time.time())
                    }
                    return response_data, True

            except Exception as e:
                logger.error(
                    f"Error in get_last_exact_floor_games_handler data_fetcher: {str(e)}")
                return {"status": "error", "message": "Internal server error"}, False

        # Use cached_endpoint utility
        return await cached_endpoint(request, key_builder, data_fetcher)

    except Exception as e:
        logger.error(f"Error in get_last_exact_floor_games_handler: {str(e)}")
        return error_response("Internal server error", status=500)
