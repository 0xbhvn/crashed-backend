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


def setup_api_routes(app: web.Application) -> None:
    """
    Set up API routes for the application.

    Args:
        app: The aiohttp application.
    """
    app.add_routes(routes)
    logger.info("API routes configured")
