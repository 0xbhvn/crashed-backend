"""
API endpoints for BC Game Crash Monitor.

This module defines the API endpoints for the BC Game Crash Monitor application.
"""

import logging
import json
from datetime import datetime
import pytz
from typing import Dict, List, Any, Optional
from aiohttp import web
from .db.engine import Database
from .db.models import CrashGame
from . import config

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()

# Define default timezone for API responses (overrides config.TIMEZONE if it's UTC)
DEFAULT_API_TIMEZONE = 'Asia/Kolkata'

# Header name for timezone configuration
TIMEZONE_HEADER = 'X-Timezone'


def convert_datetime_to_timezone(dt, timezone_name=None):
    """
    Convert UTC datetime to the specified timezone.

    Args:
        dt: Datetime object to convert
        timezone_name: Optional timezone name from request header

    Returns:
        ISO formatted datetime string in the target timezone
    """
    if dt is None:
        return None

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
                    'crashPoint': float(game.crashPoint),
                    'calculatedPoint': float(game.calculatedPoint),
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

        # Convert to JSON manually
        response_json = json.dumps(response_data)

        return web.Response(
            body=response_json.encode('utf-8'),
            content_type='application/json'
        )
    except Exception as e:
        logger.error(f"Error in get_games: {e}")
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        return web.Response(
            body=json.dumps(error_response).encode('utf-8'),
            status=500,
            content_type='application/json'
        )


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
            error_response = {
                'status': 'error',
                'message': f'Game with ID {game_id} not found'
            }
            return web.Response(
                body=json.dumps(error_response).encode('utf-8'),
                status=404,
                content_type='application/json'
            )

        # Convert to dictionary with manual datetime handling and timezone conversion
        game_data = {
            'gameId': game.gameId,
            'hashValue': game.hashValue,
            'crashPoint': float(game.crashPoint),
            'calculatedPoint': float(game.calculatedPoint),
            'crashedFloor': int(game.crashedFloor) if game.crashedFloor else None,
            'endTime': convert_datetime_to_timezone(game.endTime, timezone_name),
            'prepareTime': convert_datetime_to_timezone(game.prepareTime, timezone_name),
            'beginTime': convert_datetime_to_timezone(game.beginTime, timezone_name)
        }

        response_data = {
            'status': 'success',
            'data': game_data
        }

        # Convert to JSON manually
        response_json = json.dumps(response_data)

        return web.Response(
            body=response_json.encode('utf-8'),
            content_type='application/json'
        )
    except Exception as e:
        logger.error(f"Error in get_game_by_id: {e}")
        error_response = {
            'status': 'error',
            'message': str(e)
        }
        return web.Response(
            body=json.dumps(error_response).encode('utf-8'),
            status=500,
            content_type='application/json'
        )


def setup_api_routes(app: web.Application, db: Database) -> None:
    """
    Set up API routes for the application.

    Args:
        app: Web application
        db: Database instance
    """
    # Store database in app
    app['db'] = db

    # Add routes with names for reverse URL construction
    app.router.add_route('GET', '/api/games', get_games, name='get_games')
    app.router.add_route('GET', '/api/games/{game_id}', get_game_by_id)

    logger.info("API routes configured")
    logger.info(
        f"Default API timezone: {DEFAULT_API_TIMEZONE} (can be overridden with {TIMEZONE_HEADER} header)")
