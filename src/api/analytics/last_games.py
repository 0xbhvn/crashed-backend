"""
Last games analytics functions.

This module contains functions for analyzing the most recent games
with specific crash point criteria.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


def get_last_min_crash_point_games(session: Session, min_value: float, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent games with crash points greater than or equal to the specified value.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point value to filter by
        limit: Maximum number of games to return (default: 10)

    Returns:
        List of dictionaries containing game data for matching games
    """
    try:
        # Query the most recent games with crash point >= min_value
        games = session.query(CrashGame)\
            .filter(CrashGame.crashPoint >= min_value)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Convert games to dictionaries
        return [game.to_dict() for game in games]

    except Exception as e:
        logger.error(
            f"Error getting last games with min crash point {min_value}: {str(e)}")
        raise


def get_last_max_crash_point_games(session: Session, max_value: float, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent games with crash points less than or equal to the specified value.

    Args:
        session: SQLAlchemy session
        max_value: Maximum crash point value to filter by
        limit: Maximum number of games to return (default: 10)

    Returns:
        List of dictionaries containing game data for matching games
    """
    try:
        # Query the most recent games with crash point <= max_value
        games = session.query(CrashGame)\
            .filter(CrashGame.crashPoint <= max_value)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Convert games to dictionaries
        return [game.to_dict() for game in games]

    except Exception as e:
        logger.error(
            f"Error getting last games with max crash point {max_value}: {str(e)}")
        raise


def get_last_exact_floor_games(session: Session, floor_value: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent games with crash point floor exactly matching the specified value.

    Args:
        session: SQLAlchemy session
        floor_value: Exact floor value to filter by
        limit: Maximum number of games to return (default: 10)

    Returns:
        List of dictionaries containing game data for matching games
    """
    try:
        # Query the most recent games with floor matching exactly
        games = session.query(CrashGame)\
            .filter(CrashGame.crashedFloor == floor_value)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Convert games to dictionaries
        return [game.to_dict() for game in games]

    except Exception as e:
        logger.error(
            f"Error getting last games with exact floor {floor_value}: {str(e)}")
        raise


def get_last_game_min_crash_point(session: Session, min_value: float) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Get the most recent game with a crash point greater than or equal to the specified value.
    Also returns the count of games since this game.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point value to search for

    Returns:
        Tuple of (game_dict, games_since_count) if found, None otherwise
        game_dict: Dictionary containing game data
        games_since_count: Number of games since this game
    """
    try:
        # Query the most recent game with crash point >= min_value
        game = session.query(CrashGame)\
            .filter(CrashGame.crashPoint >= min_value)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        if game:
            # Get the latest game's ID to calculate games since
            latest_game = session.query(CrashGame)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            # Count games between the found game and the latest game
            games_since = session.query(func.count(CrashGame.gameId))\
                .filter(CrashGame.endTime > game.endTime)\
                .scalar()

            return game.to_dict(), games_since

        return None

    except Exception as e:
        logger.error(
            f"Error getting last game with min crash point {min_value}: {str(e)}")
        raise


def get_last_game_exact_floor(session: Session, floor_value: int) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Get the most recent game with a crash point floor exactly matching the specified value.
    Also returns the count of games since this game.

    Args:
        session: SQLAlchemy session
        floor_value: Exact floor value to search for

    Returns:
        Tuple of (game_dict, games_since_count) if found, None otherwise
        game_dict: Dictionary containing game data
        games_since_count: Number of games since this game
    """
    try:
        # Query the most recent game with crashed floor exact match
        game = session.query(CrashGame)\
            .filter(CrashGame.crashedFloor == floor_value)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        if game:
            # Get the latest game's ID to calculate games since
            latest_game = session.query(CrashGame)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            # Count games between the found game and the latest game
            games_since = session.query(func.count(CrashGame.gameId))\
                .filter(CrashGame.endTime > game.endTime)\
                .scalar()

            return game.to_dict(), games_since

        return None

    except Exception as e:
        logger.error(
            f"Error getting last game with exact floor {floor_value}: {str(e)}")
        raise


def get_last_games_min_crash_points(session: Session, values: List[float]) -> Dict[float, Optional[Tuple[Dict[str, Any], int]]]:
    """
    Get the most recent games with crash points greater than or equal to each specified value.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point values to search for

    Returns:
        Dictionary mapping each value to its result tuple (game_dict, games_since_count) if found,
        or None if no matching game was found
    """
    try:
        results = {}
        latest_game = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        for value in values:
            # Query the most recent game with crash point >= value
            game = session.query(CrashGame)\
                .filter(CrashGame.crashPoint >= value)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            if game:
                # Count games between the found game and the latest game
                games_since = session.query(func.count(CrashGame.gameId))\
                    .filter(CrashGame.endTime > game.endTime)\
                    .scalar()
                results[value] = (game.to_dict(), games_since)
            else:
                results[value] = None

        return results

    except Exception as e:
        logger.error(
            f"Error getting last games with min crash points: {str(e)}")
        raise


def get_last_games_exact_floors(session: Session, values: List[int]) -> Dict[int, Optional[Tuple[Dict[str, Any], int]]]:
    """
    Get the most recent games with crash point floors exactly matching each specified value.

    Args:
        session: SQLAlchemy session
        values: List of floor values to search for

    Returns:
        Dictionary mapping each value to its result tuple (game_dict, games_since_count) if found,
        or None if no matching game was found
    """
    try:
        results = {}
        latest_game = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        for value in values:
            # Query the most recent game with exact floor
            game = session.query(CrashGame)\
                .filter(CrashGame.crashedFloor == value)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            if game:
                # Count games between the found game and the latest game
                games_since = session.query(func.count(CrashGame.gameId))\
                    .filter(CrashGame.endTime > game.endTime)\
                    .scalar()
                results[value] = (game.to_dict(), games_since)
            else:
                results[value] = None

        return results

    except Exception as e:
        logger.error(
            f"Error getting last games with exact floors: {str(e)}")
        raise


def get_last_game_max_crash_point(session: Session, max_value: float) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Get the most recent game with a crash point less than or equal to the specified value.
    Also returns the count of games since this game.

    Args:
        session: SQLAlchemy session
        max_value: Maximum crash point value to search for

    Returns:
        Tuple of (game_dict, games_since_count) if found, None otherwise
        game_dict: Dictionary containing game data
        games_since_count: Number of games since this game
    """
    try:
        # Query the most recent game with crash point <= max_value
        game = session.query(CrashGame)\
            .filter(CrashGame.crashPoint <= max_value)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        if game:
            # Get the latest game's ID to calculate games since
            latest_game = session.query(CrashGame)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            # Count games between the found game and the latest game
            games_since = session.query(func.count(CrashGame.gameId))\
                .filter(CrashGame.endTime > game.endTime)\
                .scalar()

            return game.to_dict(), games_since

        return None

    except Exception as e:
        logger.error(
            f"Error getting last game with max crash point {max_value}: {str(e)}")
        raise


def get_last_games_max_crash_points(session: Session, values: List[float]) -> Dict[float, Optional[Tuple[Dict[str, Any], int]]]:
    """
    Get the most recent games with crash points less than or equal to each specified value.

    Args:
        session: SQLAlchemy session
        values: List of maximum crash point values to search for

    Returns:
        Dictionary mapping each value to its result tuple (game_dict, games_since_count) if found,
        or None if no matching game was found
    """
    try:
        results = {}
        latest_game = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .first()

        for value in values:
            # Query the most recent game with crash point <= value
            game = session.query(CrashGame)\
                .filter(CrashGame.crashPoint <= value)\
                .order_by(desc(CrashGame.endTime))\
                .first()

            if game:
                # Count games between the found game and the latest game
                games_since = session.query(func.count(CrashGame.gameId))\
                    .filter(CrashGame.endTime > game.endTime)\
                    .scalar()
                results[value] = (game.to_dict(), games_since)
            else:
                results[value] = None

        return results

    except Exception as e:
        logger.error(
            f"Error getting last games with max crash points: {str(e)}")
        raise
