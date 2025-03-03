"""
Database module for BC Game Crash Monitor.

This module provides database connectivity and operations for the BC Game Crash Monitor.
It uses SQLAlchemy ORM for database interactions through the sqlalchemy_db module.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import statistics
import pytz

from . import config

# Import our SQLAlchemy database module
from src.sqlalchemy_db import get_database
from src.models import CrashGame, CrashStats

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
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning(
            "DATABASE_URL not set. Using default connection string.")
        database_url = "postgresql://postgres:postgres@localhost:5432/bc_crash_db"

    try:
        # Get database instance
        db = get_database()

        # Create tables if they don't exist
        db.create_tables()

        # Log successful initialization
        logger.info(f"Database initialized successfully with SQLAlchemy")
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
        # Calculate deviation between actual and calculated points
        deviation = crash_point - calculated_point if calculated_point else None

        # Create game data dictionary
        game_data = {
            "gameId": game_id,
            "hashValue": hash_value,
            "crashPoint": crash_point,
            "calculatedPoint": calculated_point,
            "verified": calculated_point == crash_point,
            "deviation": deviation,
        }

        # If game detail is provided, extract timing information
        if game_detail and isinstance(game_detail, dict):
            if 'endTime' in game_detail and game_detail['endTime']:
                game_data["endTimeUnix"] = game_detail['endTime']
                game_data["endTime"] = unix_to_datetime(game_detail['endTime'])

            if 'prepareTime' in game_detail and game_detail['prepareTime']:
                game_data["prepareTimeUnix"] = game_detail['prepareTime']
                game_data["prepareTime"] = unix_to_datetime(
                    game_detail['prepareTime'])

            if 'beginTime' in game_detail and game_detail['beginTime']:
                game_data["beginTimeUnix"] = game_detail['beginTime']
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


async def update_daily_stats():
    """Update daily stats for crash games"""
    logger.debug("Updating daily stats")

    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        db = get_database()

        # Get games from today using a session
        session = db.get_session()
        try:
            games = session.query(CrashGame).filter(
                CrashGame.createdAt >= today
            ).all()

            if not games:
                logger.debug("No games found for today, skipping stats update")
                return

            # Calculate stats
            crash_points = [game.crashPoint for game in games]
            games_count = len(crash_points)
            average_crash = sum(crash_points) / games_count
            median_crash = statistics.median(crash_points)
            max_crash = max(crash_points)
            min_crash = min(crash_points)
            std_dev = statistics.stdev(crash_points) if games_count > 1 else 0

            # Create stats data dictionary
            stats_data = {
                "gamesCount": games_count,
                "averageCrash": average_crash,
                "medianCrash": median_crash,
                "maxCrash": max_crash,
                "minCrash": min_crash,
                "standardDeviation": std_dev
            }

            # Update or create stats
            db.update_or_create_crash_stats(today, stats_data)

            logger.info(
                f"Updated stats for {today.date()}: {games_count} games, avg={average_crash:.2f}x")
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Error updating daily stats: {str(e)}")
