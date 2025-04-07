"""
Game API routes for Crash Monitor.

This module defines API endpoints for fetching crash game data.
"""

import logging
import time
from typing import Dict, Any, Tuple
from aiohttp import web

from ..utils import convert_datetime_to_timezone, json_response, error_response, TIMEZONE_HEADER
from ...utils.redis_cache import cached_endpoint, build_key_with_query_param, build_key_from_match_info
from ...utils.redis_keys import get_cache_version
from ...db.engine import Database
from ...db.models import CrashGame

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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            page = req.query.get('page', '1')
            per_page = req.query.get('per_page', '10')
            return f"games:list:page:{page}:per_page:{per_page}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get query parameters
                page = int(req.query.get('page', '1'))
                per_page = int(req.query.get('per_page', '10'))

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

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
                db: Database = req.app['db']

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
                    'data': games_data,
                    'cached_at': int(time.time())
                }

                return response_data, True
            except Exception as e:
                logger.exception(f"Error in get_games data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with short TTL for non-analytics endpoints
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_SHORT)
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
        # Define key builder function
        def key_builder(req: web.Request) -> str:
            game_id = req.match_info['game_id']
            return f"games:single:{game_id}:{get_cache_version()}"

        # Define data fetcher function
        async def data_fetcher(req: web.Request) -> Tuple[Dict[str, Any], bool]:
            try:
                # Get game ID from path
                game_id = req.match_info['game_id']

                # Get timezone from header (if provided)
                timezone_name = req.headers.get(TIMEZONE_HEADER)

                # Get database from app
                db: Database = req.app['db']

                # Get game
                game = db.get_crash_game_by_id(game_id)

                if game is None:
                    return {"status": "error", "message": f"Game with ID {game_id} not found"}, False

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
                    'data': game_data,
                    'cached_at': int(time.time())
                }

                return response_data, True
            except Exception as e:
                logger.exception(
                    f"Error in get_game_by_id data_fetcher: {str(e)}")
                return {"status": "error", "message": f"An error occurred: {str(e)}"}, False

        # Use cached_endpoint utility with short TTL for non-analytics endpoints
        from ...utils.redis_cache import config
        return await cached_endpoint(request, key_builder, data_fetcher, ttl=config.REDIS_CACHE_TTL_SHORT)
    except Exception as e:
        logger.error(f"Error in get_game_by_id: {e}")
        return error_response(str(e), 500)
