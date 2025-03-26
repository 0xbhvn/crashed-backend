"""
Last game API routes for Crash Monitor.

This module defines API endpoints for fetching information about the most
recent games that match specific criteria.
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
    """
    try:
        # Get value from path parameter and convert to float
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the game
        with db.get_session() as session:
            result = analytics.get_last_game_min_crash_point(session, value)

            if result is None:
                return error_response(f"No games found with crash point >= {value}", status=404)

            game_data, games_since = result

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                game_data['endTime'] = convert_datetime_to_timezone(
                    game_data['endTime'], timezone_name)
                game_data['prepareTime'] = convert_datetime_to_timezone(
                    game_data['prepareTime'], timezone_name)
                game_data['beginTime'] = convert_datetime_to_timezone(
                    game_data['beginTime'], timezone_name)

            return json_response({
                'status': 'success',
                'data': {
                    'game': game_data,
                    'games_since': games_since
                }
            })

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
    """
    try:
        # Get value from path parameter and convert to int
        try:
            value = int(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be an integer.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the game
        with db.get_session() as session:
            result = analytics.get_last_game_exact_floor(session, value)

            if result is None:
                return error_response(f"No games found with floor value = {value}", status=404)

            game_data, games_since = result

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                game_data['endTime'] = convert_datetime_to_timezone(
                    game_data['endTime'], timezone_name)
                game_data['prepareTime'] = convert_datetime_to_timezone(
                    game_data['prepareTime'], timezone_name)
                game_data['beginTime'] = convert_datetime_to_timezone(
                    game_data['beginTime'], timezone_name)

            return json_response({
                'status': 'success',
                'data': {
                    'game': game_data,
                    'games_since': games_since
                }
            })

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
        JSON response containing results for each value in the input list
    """
    try:
        # Get request body
        try:
            body = await request.json()
            values = body.get('values', [])
            if not isinstance(values, list):
                return error_response("Invalid request body. 'values' must be a list.", status=400)
            if not values:
                return error_response("No values provided.", status=400)
            # Convert all values to float
            values = [float(v) for v in values]
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

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
                    processed_results[str(value)] = {
                        'game': game_data,
                        'games_since': games_since
                    }
                else:
                    processed_results[str(value)] = None

            return json_response({
                'status': 'success',
                'data': processed_results
            })

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
        # Get request body
        try:
            body = await request.json()
            values = body.get('values', [])
            if not isinstance(values, list):
                return error_response("Invalid request body. 'values' must be a list.", status=400)
            if not values:
                return error_response("No values provided.", status=400)
            # Convert all values to int
            values = [int(v) for v in values]
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the games
        with db.get_session() as session:
            results = analytics.get_last_games_exact_floors(session, values)

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

            return json_response({
                'status': 'success',
                'data': processed_results
            })

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
        # Get value from path parameter and convert to float
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the game
        with db.get_session() as session:
            result = analytics.get_last_game_max_crash_point(session, value)

            if result is None:
                return error_response(f"No games found with crash point <= {value}", status=404)

            game_data, games_since = result

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                game_data['endTime'] = convert_datetime_to_timezone(
                    game_data['endTime'], timezone_name)
                game_data['prepareTime'] = convert_datetime_to_timezone(
                    game_data['prepareTime'], timezone_name)
                game_data['beginTime'] = convert_datetime_to_timezone(
                    game_data['beginTime'], timezone_name)

            return json_response({
                'status': 'success',
                'data': {
                    'game': game_data,
                    'games_since': games_since
                }
            })

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
        # Get request body
        try:
            body = await request.json()
            values = body.get('values', [])
            if not isinstance(values, list):
                return error_response("Invalid request body. 'values' must be a list.", status=400)
            if not values:
                return error_response("No values provided.", status=400)
            # Convert all values to float
            values = [float(v) for v in values]
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

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
                    processed_results[str(value)] = {
                        'game': game_data,
                        'games_since': games_since
                    }
                else:
                    processed_results[str(value)] = None

            return json_response({
                'status': 'success',
                'data': processed_results
            })

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
        # Get value from path parameter and convert to float
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get limit from query parameters
        try:
            limit = int(request.query.get('limit', '10'))
            if limit <= 0:
                return error_response("Limit must be a positive integer.", status=400)
        except ValueError:
            return error_response("Invalid limit parameter. Must be an integer.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

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

            return json_response({
                'status': 'success',
                'data': {
                    'min_value': value,
                    'limit': limit,
                    'count': len(games),
                    'games': games
                }
            })

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
        # Get value from path parameter and convert to float
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get limit from query parameters
        try:
            limit = int(request.query.get('limit', '10'))
            if limit <= 0:
                return error_response("Limit must be a positive integer.", status=400)
        except ValueError:
            return error_response("Invalid limit parameter. Must be an integer.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

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

            return json_response({
                'status': 'success',
                'data': {
                    'max_value': value,
                    'limit': limit,
                    'count': len(games),
                    'games': games
                }
            })

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
        # Get value from path parameter and convert to int
        try:
            value = int(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be an integer.", status=400)

        # Get limit from query parameters
        try:
            limit = int(request.query.get('limit', '10'))
            if limit <= 0:
                return error_response("Limit must be a positive integer.", status=400)
        except ValueError:
            return error_response("Invalid limit parameter. Must be an integer.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the games
        with db.get_session() as session:
            games = analytics.get_last_exact_floor_games(session, value, limit)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                for game in games:
                    game['endTime'] = convert_datetime_to_timezone(
                        game['endTime'], timezone_name)
                    game['prepareTime'] = convert_datetime_to_timezone(
                        game['prepareTime'], timezone_name)
                    game['beginTime'] = convert_datetime_to_timezone(
                        game['beginTime'], timezone_name)

            return json_response({
                'status': 'success',
                'data': {
                    'floor_value': value,
                    'limit': limit,
                    'count': len(games),
                    'games': games
                }
            })

    except Exception as e:
        logger.error(f"Error in get_last_exact_floor_games_handler: {str(e)}")
        return error_response("Internal server error", status=500)
