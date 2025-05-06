"""
Last games analytics functions.

This module contains functions for analyzing the most recent games
with specific crash point criteria.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import math

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


def calculate_crash_probability(crash_point: float, games_since: int = 0) -> float:
    """
    Calculate the cumulative probability of a crash point occurring on the next game,
    based on the BC.games distribution and the number of games since it last occurred.

    The formula uses a geometric distribution model:
    - Base probability (p) for crash point X is 99/X (BC.games distribution)
    - Probability of occurrence by the nth game is 1-(1-p)^n
    - We calculate for the next game (games_since + 1)

    Args:
        crash_point: The crash point to calculate probability for (e.g., 10x)
        games_since: Number of games since this crash point was last seen

    Returns:
        Probability as a percentage (0-100) of seeing this crash point on the next game
    """
    try:
        # Calculate base probability (p) using BC.games distribution formula
        # For crash points ≥ X, probability is roughly 99/X percent
        base_prob = min(99.0, 99.0 / crash_point) / \
            100  # Convert to decimal (0-1)

        # Calculate probability for the next game (games_since + 1)
        # Using cumulative geometric distribution formula: 1-(1-p)^n
        n = games_since + 1  # Next game will be n games after the last occurrence

        # Calculate cumulative probability
        cumulative_prob = 1 - ((1 - base_prob) ** n)

        # Convert to percentage (0-100) and round to 2 decimal places
        return round(cumulative_prob * 100, 2)
    except Exception as e:
        logger.error(f"Error calculating crash probability: {str(e)}")
        return 0.0


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

            game_dict = game.to_dict()

            # Add probability information
            game_dict['probability'] = {
                'value': calculate_crash_probability(min_value, games_since),
                'games_since': games_since
            }

            return game_dict, games_since

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

            game_dict = game.to_dict()

            # Add probability information for exact floors
            # The probability range is between floor_value and floor_value+1
            lower_bound = float(floor_value)
            upper_bound = lower_bound + 1.0

            # Calculate probability for this range
            probability = calculate_crash_probability(lower_bound, games_since)

            game_dict['probability'] = {
                'value': probability,
                'games_since': games_since
            }

            return game_dict, games_since

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

                game_dict = game.to_dict()

                # Add probability information
                game_dict['probability'] = {
                    'value': calculate_crash_probability(value, games_since),
                    'games_since': games_since
                }

                results[value] = (game_dict, games_since)
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

                game_dict = game.to_dict()

                # Add probability information for exact floors
                lower_bound = float(value)
                probability = calculate_crash_probability(
                    lower_bound, games_since)

                game_dict['probability'] = {
                    'value': probability,
                    'games_since': games_since
                }

                results[value] = (game_dict, games_since)
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

            game_dict = game.to_dict()

            # Add probability information using max crash probability calculation
            game_dict['probability'] = {
                'value': calculate_max_crash_probability(max_value, games_since),
                'games_since': games_since
            }

            return game_dict, games_since

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

                game_dict = game.to_dict()

                # Add probability information
                game_dict['probability'] = {
                    'value': calculate_max_crash_probability(value, games_since),
                    'games_since': games_since
                }

                results[value] = (game_dict, games_since)
            else:
                results[value] = None

        return results

    except Exception as e:
        logger.error(
            f"Error getting last games with max crash points: {str(e)}")
        raise


def calculate_max_crash_probability(max_value: float, games_since: int = 0) -> float:
    """
    Calculate a simple probability estimate for a max crash point.

    For max crash points (e.g., ≤ 2x), we use a simpler model since 
    the geometric distribution isn't as applicable.

    Args:
        max_value: The maximum crash point to calculate probability for
        games_since: Number of games since this crash point was last seen

    Returns:
        Probability as a percentage (0-100)
    """
    try:
        # For max crash points, the probability is roughly:
        # 1 - (99/X)/100 = (100 - 99/X)/100
        base_prob = min(99.0, (100.0 - (99.0 / max_value))
                        ) if max_value > 1 else 1.0

        # Apply a small adjustment based on games_since
        adjustment = min(10.0, games_since * 0.5)  # Maximum 10% adjustment

        # Calculate final probability with adjustment
        final_prob = min(99.0, base_prob + adjustment)

        return round(final_prob, 2)
    except Exception as e:
        logger.error(f"Error calculating max crash probability: {str(e)}")
        return 0.0
