"""
Database operations for BC Game Crash Monitor.

This module provides high-level database operations for storing and retrieving
crash game data. It builds on the core database engine to provide convenient
functions for application code.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
import json

from .. import config
from .engine import get_database
from .models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)

# Define timezone from configuration
app_timezone = pytz.timezone(config.TIMEZONE)


def unix_to_datetime(unix_ms: int) -> datetime:
    """Convert Unix timestamp in milliseconds to datetime with configured timezone"""
    # Create datetime with the configured timezone from unix timestamp
    return datetime.fromtimestamp(unix_ms / 1000, tz=app_timezone)


async def init_database():
    """Initialize database connection"""
    try:
        # Get database instance
        db = get_database()

        # Create tables if they don't exist
        db.create_tables()

        # Log successful initialization
        logger.info("Database initialized successfully with SQLAlchemy")
        return db
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise


async def close_database():
    """Close database connection"""
    try:
        db = get_database()
        db.close()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {str(e)}")


async def store_crash_game(
    game_id: str,
    hash_value: str,
    crash_point: float,
    calculated_point: float,
    game_detail: Optional[Dict[str, Any]] = None,
) -> CrashGame:
    """Store crash game result in database"""
    logger.debug(
        f"Storing crash game {game_id} with crash point {crash_point}x")

    try:
        # Create game data dictionary
        game_data = {
            "gameId": game_id,
            "hashValue": hash_value,
            "crashPoint": crash_point,
            "calculatedPoint": calculated_point,
        }

        # If game detail is provided, extract timing information
        if game_detail and isinstance(game_detail, dict):
            if 'endTime' in game_detail and game_detail['endTime']:
                game_data["endTime"] = unix_to_datetime(game_detail['endTime'])

            if 'prepareTime' in game_detail and game_detail['prepareTime']:
                game_data["prepareTime"] = unix_to_datetime(
                    game_detail['prepareTime'])

            if 'beginTime' in game_detail and game_detail['beginTime']:
                game_data["beginTime"] = unix_to_datetime(
                    game_detail['beginTime'])

        # Get database instance
        db = get_database()

        # Check if game already exists
        existing_game = db.get_crash_game_by_id(game_id)

        if existing_game:
            logger.debug(f"Game {game_id} already exists, updating")
            # Update existing game
            updated_game = db.update_crash_game(game_id, game_data)
            return updated_game
        else:
            # Add new game
            new_game = db.add_crash_game(game_data)
            return new_game

    except Exception as e:
        logger.error(f"Error storing crash game: {str(e)}")
        raise


async def bulk_store_crash_games(games_data: List[Dict[str, Any]]) -> List[str]:
    """Store multiple crash games in the database in a single transaction.

    Args:
        games_data: List of dictionaries with game data

    Returns:
        List of game IDs that were successfully stored

    Raises:
        Exception: If there's an error during database operation
    """
    if not games_data:
        logger.debug("No games to bulk store")
        return []

    try:
        # Prepare game data with proper timestamp conversions
        prepared_games = []

        for game_data in games_data:
            try:
                # Extract required fields
                game_id = game_data.get('game_id')
                hash_value = game_data.get('hash')
                crash_point = game_data.get('crash_point')
                calculated_point = game_data.get('calculated_point')

                # Skip if missing required fields
                if not game_id or not hash_value or not crash_point:
                    logger.warning(
                        f"Skipping game with incomplete data: {game_data}")
                    continue

                # Prepare data for database
                db_game_data = {
                    "gameId": game_id,
                    "hashValue": hash_value,
                    "crashPoint": crash_point,
                    "calculatedPoint": calculated_point,
                }

                # Extract timing info if available
                game_detail = {}
                if 'game_detail' in game_data and game_data['game_detail']:
                    if isinstance(game_data['game_detail'], str):
                        try:
                            game_detail = json.loads(game_data['game_detail'])
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse game_detail for game {game_id}")
                    else:
                        game_detail = game_data['game_detail']

                # Process end time
                if 'endTime' in game_data and game_data['endTime']:
                    db_game_data["endTime"] = unix_to_datetime(
                        game_data['endTime'])
                elif 'endTime' in game_detail and game_detail['endTime']:
                    db_game_data["endTime"] = unix_to_datetime(
                        game_detail['endTime'])

                # Process prepare time
                if 'prepareTime' in game_data and game_data['prepareTime']:
                    db_game_data["prepareTime"] = unix_to_datetime(
                        game_data['prepareTime'])
                elif 'prepareTime' in game_detail and game_detail['prepareTime']:
                    db_game_data["prepareTime"] = unix_to_datetime(
                        game_detail['prepareTime'])

                # Process begin time
                if 'beginTime' in game_data and game_data['beginTime']:
                    db_game_data["beginTime"] = unix_to_datetime(
                        game_data['beginTime'])
                elif 'beginTime' in game_detail and game_detail['beginTime']:
                    db_game_data["beginTime"] = unix_to_datetime(
                        game_detail['beginTime'])

                # Set crashed floor if crash point is available
                if 'crashPoint' in db_game_data and db_game_data['crashPoint'] is not None:
                    db_game_data["crashedFloor"] = int(
                        db_game_data['crashPoint'])

                prepared_games.append(db_game_data)
            except Exception as e:
                logger.warning(f"Error preparing game data: {e}")
                continue

        # Get database instance
        db = get_database()

        # Use bulk insert
        try:
            stored_game_ids = db.bulk_add_crash_games(prepared_games)
            logger.info(f"Bulk stored {len(stored_game_ids)} crash games")
            return stored_game_ids
        except Exception as e:
            logger.error(f"Error bulk storing crash games: {str(e)}")
            # Return an empty list instead of raising to prevent the entire process from failing
            return []

    except Exception as e:
        logger.error(f"Error bulk storing crash games: {str(e)}")
        # Return empty list instead of raising
        return []


async def get_recent_games(limit: int = 10) -> List[CrashGame]:
    """Get recent crash games from database"""
    logger.debug(f"Getting {limit} recent crash games")

    try:
        db = get_database()
        games = db.get_latest_crash_games(limit)
        return games
    except Exception as e:
        logger.error(f"Error getting recent games: {str(e)}")
        return []


async def get_game_by_id(game_id: str) -> Optional[CrashGame]:
    """Get a specific crash game by ID"""
    logger.debug(f"Getting crash game with ID {game_id}")

    try:
        db = get_database()
        game = db.get_crash_game_by_id(game_id)
        return game
    except Exception as e:
        logger.error(f"Error getting game by ID: {str(e)}")
        return None


async def check_game_exists(db_engine, game_id: str) -> bool:
    """
    Check if a game exists in the database.

    Args:
        db_engine: The database engine to use
        game_id: The ID of the game to check

    Returns:
        bool: True if the game exists, False otherwise
    """
    try:
        db = get_database()
        game = db.get_crash_game_by_id(game_id)
        return game is not None
    except Exception as e:
        logger.error(f"Error checking if game exists: {str(e)}")
        return False


async def process_game_data_for_storage(db_engine, game_data: Dict[str, Any]) -> Optional[CrashGame]:
    """
    Process game data and store it in the database.

    Args:
        db_engine: The database engine to use
        game_data: Dictionary containing game data

    Returns:
        Optional[CrashGame]: The stored crash game, or None if an error occurred
    """
    try:
        game_id = game_data.get('gameId')
        hash_value = game_data.get('hashValue')
        crash_point = game_data.get('crashPoint')
        calculated_point = game_data.get('calculatedPoint', crash_point)

        return await store_crash_game(
            game_id=game_id,
            hash_value=hash_value,
            crash_point=crash_point,
            calculated_point=calculated_point,
            game_detail=game_data
        )
    except Exception as e:
        logger.error(f"Error processing game data for storage: {str(e)}")
        return None
