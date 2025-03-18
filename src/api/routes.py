"""
API routes for BC Game Crash Monitor.

This module defines the API endpoints for the BC Game Crash Monitor application.
"""

import logging
from typing import Dict, List, Any, Optional
from aiohttp import web
import json

from .utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ..db.engine import Database
from ..db.models import CrashGame
from . import analytics

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()


@routes.get('/api/games')
async def get_games(request: web.Request) -> web.Response:
    """
    Get crash games with pagination.

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 10, max: 100)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get query parameters
        page = int(request.query.get('page', '1'))
        per_page = int(request.query.get('per_page', '10'))

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Validate page and per_page
        if page < 1:
            page = 1

        if per_page < 1:
            per_page = 1
        elif per_page > 100:
            per_page = 100

        # Calculate offset
        offset = (page - 1) * per_page

        # Get database from app
        db: Database = request.app['db']

        # Get games with pagination
        with db.get_session() as session:
            # Query total count first for pagination metadata
            total_count = session.query(CrashGame).count()

            # Query the games ordered by begin_time (most recent first) with pagination
            games = session.query(CrashGame).order_by(
                CrashGame.beginTime.desc()
            ).offset(offset).limit(per_page).all()

            # Convert to dictionaries with manual datetime handling and timezone conversion
            games_data = []
            for game in games:
                game_dict = {
                    'gameId': game.gameId,
                    'hashValue': game.hashValue,
                    'crashPoint': float(game.crashPoint) if game.crashPoint is not None else None,
                    'calculatedPoint': float(game.calculatedPoint) if game.calculatedPoint is not None else None,
                    'crashedFloor': int(game.crashedFloor) if game.crashedFloor else None,
                    'endTime': convert_datetime_to_timezone(game.endTime, timezone_name),
                    'prepareTime': convert_datetime_to_timezone(game.prepareTime, timezone_name),
                    'beginTime': convert_datetime_to_timezone(game.beginTime, timezone_name)
                }
                games_data.append(game_dict)

            # Calculate pagination metadata
            total_pages = (total_count + per_page -
                           1) // per_page  # Ceiling division

            # Create pagination object
            pagination = {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }

        response_data = {
            'status': 'success',
            'count': len(games_data),
            'pagination': pagination,
            'data': games_data
        }

        return json_response(response_data)
    except Exception as e:
        logger.error(f"Error in get_games: {e}")
        return error_response(str(e), 500)


@routes.get('/api/games/{game_id}')
async def get_game_by_id(request: web.Request) -> web.Response:
    """
    Get a specific crash game by ID.

    Path parameters:
        game_id: Game ID

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'America/New_York')
    """
    try:
        # Get game ID from path
        game_id = request.match_info['game_id']

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Get game
        game = db.get_crash_game_by_id(game_id)

        if game is None:
            return error_response(f'Game with ID {game_id} not found', 404)

        # Convert to dictionary with manual datetime handling and timezone conversion
        game_data = {
            'gameId': game.gameId,
            'hashValue': game.hashValue,
            'crashPoint': float(game.crashPoint) if game.crashPoint is not None else None,
            'calculatedPoint': float(game.calculatedPoint) if game.calculatedPoint is not None else None,
            'crashedFloor': int(game.crashedFloor) if game.crashedFloor else None,
            'endTime': convert_datetime_to_timezone(game.endTime, timezone_name),
            'prepareTime': convert_datetime_to_timezone(game.prepareTime, timezone_name),
            'beginTime': convert_datetime_to_timezone(game.beginTime, timezone_name)
        }

        response_data = {
            'status': 'success',
            'data': game_data
        }

        return json_response(response_data)
    except Exception as e:
        logger.error(f"Error in get_game_by_id: {e}")
        return error_response(str(e), 500)


# Analytics Routes

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


@routes.get('/api/analytics/occurrences/min-crash-point/{value}')
async def get_min_crash_point_occurrences_by_games(request: web.Request) -> web.Response:
    """
    Get total occurrences of crash points >= specified value in the last N games.

    Path parameters:
        value (float): Minimum crash point value

    Query parameters:
        limit (int, optional): Number of games to analyze (default: 100)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get limit from query parameter
        try:
            limit = int(request.query.get('limit', '100'))
            if limit < 1:
                return error_response("Limit must be greater than 0.", status=400)
        except ValueError:
            return error_response("Invalid limit parameter.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            result = analytics.get_min_crash_point_occurrences_by_games(
                session, value, limit)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                result['first_game_time'] = convert_datetime_to_timezone(
                    result['first_game_time'], timezone_name)
                result['last_game_time'] = convert_datetime_to_timezone(
                    result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_occurrences_by_games: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/occurrences/min-crash-point/{value}/time')
async def get_min_crash_point_occurrences_by_time(request: web.Request) -> web.Response:
    """
    Get total occurrences of crash points >= specified value in the last N hours.

    Path parameters:
        value (float): Minimum crash point value

    Query parameters:
        hours (int, optional): Hours to look back (default: 1)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get hours from query parameter
        try:
            hours = int(request.query.get('hours', '1'))
            if hours < 1:
                return error_response("Hours must be greater than 0.", status=400)
        except ValueError:
            return error_response("Invalid hours parameter.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            result = analytics.get_min_crash_point_occurrences_by_time(
                session, value, hours)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                result['start_time'] = convert_datetime_to_timezone(
                    result['start_time'], timezone_name)
                result['end_time'] = convert_datetime_to_timezone(
                    result['end_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_occurrences_by_time: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/occurrences/exact-floor/{value}')
async def get_exact_floor_occurrences_by_games(request: web.Request) -> web.Response:
    """
    Get total occurrences of exact floor value in the last N games.

    Path parameters:
        value (int): Exact floor value

    Query parameters:
        limit (int, optional): Number of games to analyze (default: 100)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get value from path parameter
        try:
            value = int(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be an integer.", status=400)

        # Get limit from query parameter
        try:
            limit = int(request.query.get('limit', '100'))
            if limit < 1:
                return error_response("Limit must be greater than 0.", status=400)
        except ValueError:
            return error_response("Invalid limit parameter.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            result = analytics.get_exact_floor_occurrences_by_games(
                session, value, limit)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                result['first_game_time'] = convert_datetime_to_timezone(
                    result['first_game_time'], timezone_name)
                result['last_game_time'] = convert_datetime_to_timezone(
                    result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(
            f"Error in get_exact_floor_occurrences_by_games: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.get('/api/analytics/occurrences/exact-floor/{value}/time')
async def get_exact_floor_occurrences_by_time(request: web.Request) -> web.Response:
    """
    Get total occurrences of exact floor value in the last N hours.

    Path parameters:
        value (int): Exact floor value

    Query parameters:
        hours (int, optional): Hours to look back (default: 1)

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
    """
    try:
        # Get value from path parameter
        try:
            value = int(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be an integer.", status=400)

        # Get hours from query parameter
        try:
            hours = int(request.query.get('hours', '1'))
            if hours < 1:
                return error_response("Hours must be greater than 0.", status=400)
        except ValueError:
            return error_response("Invalid hours parameter.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            result = analytics.get_exact_floor_occurrences_by_time(
                session, value, hours)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                result['start_time'] = convert_datetime_to_timezone(
                    result['start_time'], timezone_name)
                result['end_time'] = convert_datetime_to_timezone(
                    result['end_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(f"Error in get_exact_floor_occurrences_by_time: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/occurrences/min-crash-points')
async def get_min_crash_point_occurrences_by_games_batch(request: web.Request) -> web.Response:
    """
    Get total occurrences of crash points >= specified values in the last N games.

    Request body:
        {
            "values": [float],  // List of minimum crash point values
            "limit": int,  // Optional, number of games to analyze (default: 100)
            "comparison": bool  // Optional, whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
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
            # Get optional limit
            limit = int(body.get('limit', 100))
            if limit < 1:
                return error_response("Limit must be greater than 0.", status=400)
            # Get optional comparison flag
            comparison = bool(body.get('comparison', True))
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            results = analytics.get_min_crash_point_occurrences_by_games_batch(
                session, values, limit, comparison)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                if comparison:
                    for result in results.values():
                        # We don't need to convert here since we're converting in the analytics function
                        pass
                else:
                    for result in results.values():
                        result['first_game_time'] = convert_datetime_to_timezone(
                            result['first_game_time'], timezone_name)
                        result['last_game_time'] = convert_datetime_to_timezone(
                            result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_occurrences_by_games_batch: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/occurrences/min-crash-points/time')
async def get_min_crash_point_occurrences_by_time_batch(request: web.Request) -> web.Response:
    """
    Get total occurrences of crash points >= specified values in the last N hours.

    Request body:
        {
            "values": [float],  // List of minimum crash point values
            "hours": int,  // Optional, hours to look back (default: 1)
            "comparison": bool  // Optional, whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
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
            # Get optional hours
            hours = int(body.get('hours', 1))
            if hours < 1:
                return error_response("Hours must be greater than 0.", status=400)
            # Get optional comparison flag
            comparison = bool(body.get('comparison', True))
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            results = analytics.get_min_crash_point_occurrences_by_time_batch(
                session, values, hours, comparison)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                if comparison:
                    for result in results.values():
                        # We don't need to convert here since we're converting in the analytics function
                        pass
                else:
                    for result in results.values():
                        result['start_time'] = convert_datetime_to_timezone(
                            result['start_time'], timezone_name)
                        result['end_time'] = convert_datetime_to_timezone(
                            result['end_time'], timezone_name)
                        if 'first_game_time' in result and result['first_game_time']:
                            result['first_game_time'] = convert_datetime_to_timezone(
                                result['first_game_time'], timezone_name)
                        if 'last_game_time' in result and result['last_game_time']:
                            result['last_game_time'] = convert_datetime_to_timezone(
                                result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_occurrences_by_time_batch: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/occurrences/exact-floors')
async def get_exact_floor_occurrences_by_games_batch(request: web.Request) -> web.Response:
    """
    Get total occurrences of exact floor values in the last N games.

    Request body:
        {
            "values": [int],  // List of floor values
            "limit": int,  // Optional, number of games to analyze (default: 100)
            "comparison": bool  // Optional, whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
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
            # Get optional limit
            limit = int(body.get('limit', 100))
            if limit < 1:
                return error_response("Limit must be greater than 0.", status=400)
            # Get optional comparison flag
            comparison = bool(body.get('comparison', True))
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            results = analytics.get_exact_floor_occurrences_by_games_batch(
                session, values, limit, comparison)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                if comparison:
                    for result in results.values():
                        # Convert current period timestamps
                        result['current_period']['start_time'] = convert_datetime_to_timezone(
                            result['current_period']['start_time'], timezone_name)
                        result['current_period']['end_time'] = convert_datetime_to_timezone(
                            result['current_period']['end_time'], timezone_name)
                        if result['current_period']['first_game_time']:
                            result['current_period']['first_game_time'] = convert_datetime_to_timezone(
                                result['current_period']['first_game_time'], timezone_name)
                        if result['current_period']['last_game_time']:
                            result['current_period']['last_game_time'] = convert_datetime_to_timezone(
                                result['current_period']['last_game_time'], timezone_name)

                        # Convert previous period timestamps
                        result['previous_period']['start_time'] = convert_datetime_to_timezone(
                            result['previous_period']['start_time'], timezone_name)
                        result['previous_period']['end_time'] = convert_datetime_to_timezone(
                            result['previous_period']['end_time'], timezone_name)
                        if result['previous_period']['first_game_time']:
                            result['previous_period']['first_game_time'] = convert_datetime_to_timezone(
                                result['previous_period']['first_game_time'], timezone_name)
                        if result['previous_period']['last_game_time']:
                            result['previous_period']['last_game_time'] = convert_datetime_to_timezone(
                                result['previous_period']['last_game_time'], timezone_name)
                else:
                    for result in results.values():
                        result['first_game_time'] = convert_datetime_to_timezone(
                            result['first_game_time'], timezone_name)
                        result['last_game_time'] = convert_datetime_to_timezone(
                            result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(
            f"Error in get_exact_floor_occurrences_by_games_batch: {str(e)}")
        return error_response("Internal server error", status=500)


@routes.post('/api/analytics/occurrences/exact-floors/time')
async def get_exact_floor_occurrences_by_time_batch(request: web.Request) -> web.Response:
    """
    Get total occurrences of exact floor values in the last N hours.

    Request body:
        {
            "values": [int],  // List of floor values
            "hours": int,  // Optional, hours to look back (default: 1)
            "comparison": bool  // Optional, whether to include comparison with previous period (default: true)
        }

    Headers:
        X-Timezone: Optional timezone for datetime values (e.g., 'Asia/Kolkata')
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
            # Get optional hours
            hours = int(body.get('hours', 1))
            if hours < 1:
                return error_response("Hours must be greater than 0.", status=400)
            # Get optional comparison flag
            comparison = bool(body.get('comparison', True))
        except (json.JSONDecodeError, ValueError):
            return error_response("Invalid request body or values.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the occurrences
        with db.get_session() as session:
            results = analytics.get_exact_floor_occurrences_by_time_batch(
                session, values, hours, comparison)

            # Convert datetime values to specified timezone if provided
            if timezone_name:
                if comparison:
                    for result in results.values():
                        # We don't need to convert here since we're converting in the analytics function
                        pass
                else:
                    for result in results.values():
                        result['start_time'] = convert_datetime_to_timezone(
                            result['start_time'], timezone_name)
                        result['end_time'] = convert_datetime_to_timezone(
                            result['end_time'], timezone_name)
                        if 'first_game_time' in result and result['first_game_time']:
                            result['first_game_time'] = convert_datetime_to_timezone(
                                result['first_game_time'], timezone_name)
                        if 'last_game_time' in result and result['last_game_time']:
                            result['last_game_time'] = convert_datetime_to_timezone(
                                result['last_game_time'], timezone_name)

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(
            f"Error in get_exact_floor_occurrences_by_time_batch: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get query parameters
        try:
            limit = int(request.query.get('limit', '1000'))
            if limit < 1:
                return error_response("Limit must be greater than 0.", status=400)

            sort_by = request.query.get('sort_by', 'time')
            if sort_by not in ['time', 'length']:
                return error_response("sort_by must be either 'time' or 'length'.", status=400)
        except ValueError:
            return error_response("Invalid query parameters.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the series
        with db.get_session() as session:
            result = analytics.get_series_without_min_crash_point_by_games(
                session=session,
                min_value=value,
                limit=limit,
                sort_by=sort_by
            )

            # Convert datetime values to specified timezone if provided, or to ISO format
            for series in result:
                if timezone_name:
                    series['start_time'] = convert_datetime_to_timezone(
                        series['start_time'], timezone_name)
                    series['end_time'] = convert_datetime_to_timezone(
                        series['end_time'], timezone_name)
                else:
                    # If no timezone provided, just convert to ISO format string
                    series['start_time'] = series['start_time'].isoformat()
                    series['end_time'] = series['end_time'].isoformat()

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(f"Error in get_series_without_min_crash_point: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get query parameters
        try:
            hours = int(request.query.get('hours', '24'))
            if hours < 1:
                return error_response("Hours must be greater than 0.", status=400)

            sort_by = request.query.get('sort_by', 'time')
            if sort_by not in ['time', 'length']:
                return error_response("sort_by must be either 'time' or 'length'.", status=400)
        except ValueError:
            return error_response("Invalid query parameters.", status=400)

        # Get timezone from header (if provided)
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the series
        with db.get_session() as session:
            result = analytics.get_series_without_min_crash_point_by_time(
                session=session,
                min_value=value,
                hours=hours,
                sort_by=sort_by
            )

            # Convert datetime values to specified timezone if provided, or to ISO format
            for series in result:
                if timezone_name:
                    series['start_time'] = convert_datetime_to_timezone(
                        series['start_time'], timezone_name)
                    series['end_time'] = convert_datetime_to_timezone(
                        series['end_time'], timezone_name)
                else:
                    # If no timezone provided, just convert to ISO format string
                    series['start_time'] = series['start_time'].isoformat()
                    series['end_time'] = series['end_time'].isoformat()

            return json_response({
                'status': 'success',
                'data': result
            })

    except Exception as e:
        logger.error(
            f"Error in get_series_without_min_crash_point_by_time: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get query parameters
        try:
            interval_minutes = int(request.query.get('interval_minutes', 10))
            hours = int(request.query.get('hours', 24))
            if interval_minutes <= 0 or hours <= 0:
                raise ValueError
        except ValueError:
            return error_response("Invalid interval_minutes or hours parameter. Must be positive integers.", status=400)

        # Get timezone from header
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the intervals
        with db.get_session() as session:
            intervals = analytics.get_min_crash_point_intervals_by_time(
                session, value, interval_minutes, hours)

            # Convert datetime objects to timezone-adjusted strings
            if timezone_name:
                for interval in intervals:
                    # Convert datetime objects to strings with timezone adjustment
                    # The convert_datetime_to_timezone function expects a datetime object
                    interval['interval_start'] = convert_datetime_to_timezone(
                        interval['interval_start'], timezone_name)
                    interval['interval_end'] = convert_datetime_to_timezone(
                        interval['interval_end'], timezone_name)
            else:
                # If no timezone specified, just convert to ISO format strings
                for interval in intervals:
                    interval['interval_start'] = interval['interval_start'].isoformat()
                    interval['interval_end'] = interval['interval_end'].isoformat()

            return json_response({
                'status': 'success',
                'data': intervals
            })

    except Exception as e:
        logger.error(f"Error in get_min_crash_point_intervals: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get value from path parameter
        try:
            value = float(request.match_info['value'])
        except ValueError:
            return error_response("Invalid value parameter. Must be a number.", status=400)

        # Get query parameters
        try:
            games_per_set = int(request.query.get('games_per_set', 10))
            total_games = int(request.query.get('total_games', 1000))
            if games_per_set <= 0 or total_games <= 0:
                raise ValueError
        except ValueError:
            return error_response("Invalid games_per_set or total_games parameter. Must be positive integers.", status=400)

        # Get timezone from header
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the intervals
        with db.get_session() as session:
            intervals = analytics.get_min_crash_point_intervals_by_game_sets(
                session, value, games_per_set, total_games)

            # Convert datetime objects to timezone-adjusted strings
            if timezone_name:
                for interval in intervals:
                    # Convert datetime objects to strings with timezone adjustment
                    interval['start_time'] = convert_datetime_to_timezone(
                        interval['start_time'], timezone_name)
                    interval['end_time'] = convert_datetime_to_timezone(
                        interval['end_time'], timezone_name)
            else:
                # If no timezone specified, just convert to ISO format strings
                for interval in intervals:
                    interval['start_time'] = interval['start_time'].isoformat()
                    interval['end_time'] = interval['end_time'].isoformat()

            return json_response({
                'status': 'success',
                'data': intervals
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_intervals_by_sets: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get request body
        try:
            body = await request.json()
            values = body.get('values', [])
            if not isinstance(values, list) or not values:
                return error_response("Invalid or missing 'values' in request body", status=400)
            values = [float(v) for v in values]

            interval_minutes = int(body.get('interval_minutes', 10))
            hours = int(body.get('hours', 24))
            if interval_minutes <= 0 or hours <= 0:
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return error_response("Invalid request body parameters", status=400)

        # Get timezone from header
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the intervals
        with db.get_session() as session:
            results = analytics.get_min_crash_point_intervals_by_time_batch(
                session, values, interval_minutes, hours)

            # Convert datetime objects to strings
            if timezone_name:
                for value_intervals in results.values():
                    for interval in value_intervals:
                        interval['interval_start'] = convert_datetime_to_timezone(
                            interval['interval_start'], timezone_name)
                        interval['interval_end'] = convert_datetime_to_timezone(
                            interval['interval_end'], timezone_name)
            else:
                # If no timezone specified, just convert to ISO format strings
                for value_intervals in results.values():
                    for interval in value_intervals:
                        interval['interval_start'] = interval['interval_start'].isoformat()
                        interval['interval_end'] = interval['interval_end'].isoformat()

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(f"Error in get_min_crash_point_intervals_batch: {str(e)}")
        return error_response("Internal server error", status=500)


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
        # Get request body
        try:
            body = await request.json()
            values = body.get('values', [])
            if not isinstance(values, list) or not values:
                return error_response("Invalid or missing 'values' in request body", status=400)
            values = [float(v) for v in values]

            games_per_set = int(body.get('games_per_set', 10))
            total_games = int(body.get('total_games', 1000))
            if games_per_set <= 0 or total_games <= 0:
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return error_response("Invalid request body parameters", status=400)

        # Get timezone from header
        timezone_name = request.headers.get(TIMEZONE_HEADER)

        # Get database from app
        db: Database = request.app['db']

        # Query the intervals
        with db.get_session() as session:
            results = analytics.get_min_crash_point_intervals_by_game_sets_batch(
                session, values, games_per_set, total_games)

            # Convert datetime objects to strings
            if timezone_name:
                for value_intervals in results.values():
                    for interval in value_intervals:
                        interval['start_time'] = convert_datetime_to_timezone(
                            interval['start_time'], timezone_name)
                        interval['end_time'] = convert_datetime_to_timezone(
                            interval['end_time'], timezone_name)
            else:
                # If no timezone specified, just convert to ISO format strings
                for value_intervals in results.values():
                    for interval in value_intervals:
                        interval['start_time'] = interval['start_time'].isoformat()
                        interval['end_time'] = interval['end_time'].isoformat()

            return json_response({
                'status': 'success',
                'data': results
            })

    except Exception as e:
        logger.error(
            f"Error in get_min_crash_point_intervals_by_sets_batch: {str(e)}")
        return error_response("Internal server error", status=500)


def setup_api_routes(app: web.Application) -> None:
    """
    Set up API routes for the application.

    Args:
        app: The aiohttp application.
    """
    app.add_routes(routes)
    logger.info("API routes configured")
