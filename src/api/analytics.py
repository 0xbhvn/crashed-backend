"""
Analytics module for BC Game Crash Monitor.

This module provides functions for analyzing crash game data and computing various metrics.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, select
from datetime import datetime, timedelta, timezone

from ..db.models import CrashGame
from .. import config

# Configure logging
logger = logging.getLogger(__name__)


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
        floor_value: Exact floor value to match

    Returns:
        Tuple of (game_dict, games_since_count) if found, None otherwise
        game_dict: Dictionary containing game data
        games_since_count: Number of games since this game
    """
    try:
        # Query the most recent game with crashed floor == floor_value
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
        values: List of floor values to match

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
            # Query the most recent game with crashed floor == value
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
        logger.error(f"Error getting last games with exact floors: {str(e)}")
        raise


def get_min_crash_point_occurrences_by_games(
    session: Session,
    min_value: float,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get the total occurrences of crash points >= specified value in the last N games.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point value to count
        limit: Number of most recent games to analyze (default: 100)

    Returns:
        Dictionary containing:
        - count: Number of occurrences
        - total_games: Total games analyzed
        - percentage: Percentage of games with crash point >= min_value
        - first_game: First game in the analyzed set
        - last_game: Last game in the analyzed set
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Count occurrences within these games
        count = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.gameId.in_(select(current_subquery.c.gameId)))\
            .filter(CrashGame.crashPoint >= min_value)\
            .scalar()

        # Get first and last games in the set for reference
        first_last_games = session.query(
            func.min(CrashGame.endTime).label('first_time'),
            func.max(CrashGame.endTime).label('last_time')
        ).filter(CrashGame.gameId.in_(select(current_subquery.c.gameId))).first()

        return {
            'count': count,
            'total_games': limit,
            'percentage': (count / limit) * 100 if limit > 0 else 0,
            'first_game_time': first_last_games.first_time,
            'last_game_time': first_last_games.last_time
        }

    except Exception as e:
        logger.error(
            f"Error getting min crash point occurrences by games: {str(e)}")
        raise


def get_min_crash_point_occurrences_by_time(
    session: Session,
    value: float,
    hours: int = 1
) -> Dict[str, Any]:
    """
    Get the total occurrences of crash points >= specified value in the last N hours.

    Args:
        session: SQLAlchemy session
        value: Minimum crash point value to count
        hours: Number of hours to look back (default: 1)

    Returns:
        Dictionary with count, total games, percentage, and time range
    """
    try:
        # Calculate the time threshold in UTC
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get total games in the time period
        total_games = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.endTime >= start_time)\
            .scalar()

        # Count occurrences within the time period
        count = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.crashPoint >= value)\
            .scalar()

        return {
            'count': count,
            'total_games': total_games,
            'percentage': (count / total_games) * 100 if total_games > 0 else 0,
            'start_time': start_time,
            'end_time': end_time
        }

    except Exception as e:
        logger.error(
            f"Error getting min crash point occurrences by time: {str(e)}")
        raise


def get_exact_floor_occurrences_by_games(
    session: Session,
    floor_value: int,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get the total occurrences of exact floor value in the last N games.

    Args:
        session: SQLAlchemy session
        floor_value: Exact floor value to count
        limit: Number of most recent games to analyze (default: 100)

    Returns:
        Dictionary containing:
        - count: Number of occurrences
        - total_games: Total games analyzed
        - percentage: Percentage of games with exact floor value
        - first_game: First game in the analyzed set
        - last_game: Last game in the analyzed set
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Count occurrences within these games
        count = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.gameId.in_(select(current_subquery.c.gameId)))\
            .filter(CrashGame.crashedFloor == floor_value)\
            .scalar()

        # Get first and last games in the set for reference
        first_last_games = session.query(
            func.min(CrashGame.endTime).label('first_time'),
            func.max(CrashGame.endTime).label('last_time')
        ).filter(CrashGame.gameId.in_(select(current_subquery.c.gameId))).first()

        return {
            'count': count,
            'total_games': limit,
            'percentage': (count / limit) * 100 if limit > 0 else 0,
            'first_game_time': first_last_games.first_time,
            'last_game_time': first_last_games.last_time
        }

    except Exception as e:
        logger.error(
            f"Error getting exact floor occurrences by games: {str(e)}")
        raise


def get_exact_floor_occurrences_by_time(
    session: Session,
    value: int,
    hours: int = 1
) -> Dict[str, Any]:
    """
    Get the total occurrences of exact floor value in the last N hours.

    Args:
        session: SQLAlchemy session
        value: Floor value to count
        hours: Number of hours to look back (default: 1)

    Returns:
        Dictionary with count, total games, percentage, and time range
    """
    try:
        # Calculate the time threshold in UTC
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get total games in the time period
        total_games = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.endTime >= start_time)\
            .scalar()

        # Count occurrences within the time period
        count = session.query(func.count(CrashGame.gameId))\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.crashedFloor == value)\
            .scalar()

        return {
            'count': count,
            'total_games': total_games,
            'percentage': (count / total_games) * 100 if total_games > 0 else 0,
            'start_time': start_time,
            'end_time': end_time
        }

    except Exception as e:
        logger.error(
            f"Error getting exact floor occurrences by time: {str(e)}")
        raise


def get_min_crash_point_occurrences_by_games_batch(
    session: Session,
    values: List[float],
    limit: int = 100,
    comparison: bool = True
) -> Dict[float, Dict[str, Any]]:
    """
    Get the total occurrences of crash points >= specified values in the last N games,
    and compare with the previous N games.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point values to count
        limit: Number of most recent games to analyze (default: 100)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics, optionally including comparison
        with the previous set of games
    """
    try:
        results = {}

        # Get the most recent 'limit' games (current period)
        current_subquery = session.query(CrashGame.gameId, CrashGame.endTime)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .subquery()

        # Count the actual number of games in the current subquery
        actual_game_count = session.query(
            func.count()).select_from(current_subquery).scalar()

        # Get first and last games in the current set for reference
        current_first_last_games = session.query(
            func.min(CrashGame.endTime).label('first_time'),
            func.max(CrashGame.endTime).label('last_time')
        ).select_from(CrashGame).filter(CrashGame.gameId.in_(select(current_subquery.c.gameId))).first()

        # Convert datetime objects to ISO string format for current period
        current_first_time_iso = current_first_last_games.first_time.isoformat(
        ) if current_first_last_games.first_time else None
        current_last_time_iso = current_first_last_games.last_time.isoformat(
        ) if current_first_last_games.last_time else None

        # Only get previous period data if comparison is enabled
        if comparison:
            # Get the oldest game from current period to use as cutoff for previous period
            oldest_current_game = session.query(CrashGame.endTime)\
                .order_by(desc(CrashGame.endTime))\
                .offset(limit-1)\
                .limit(1)\
                .first()

            if oldest_current_game:
                cutoff_time = oldest_current_game.endTime

                # Get the previous 'limit' games
                prev_subquery = session.query(CrashGame.gameId, CrashGame.endTime)\
                    .filter(CrashGame.endTime < cutoff_time)\
                    .order_by(desc(CrashGame.endTime))\
                    .limit(limit)\
                    .subquery()

                # Count the actual number of games in the previous subquery
                prev_game_count = session.query(
                    func.count()).select_from(prev_subquery).scalar()

                # Get first and last games in the previous set for reference
                prev_first_last_games = session.query(
                    func.min(CrashGame.endTime).label('first_time'),
                    func.max(CrashGame.endTime).label('last_time')
                ).select_from(CrashGame).filter(CrashGame.gameId.in_(select(prev_subquery.c.gameId))).first()

                # Convert datetime objects to ISO string format for previous period
                prev_first_time_iso = prev_first_last_games.first_time.isoformat(
                ) if prev_first_last_games.first_time else None
                prev_last_time_iso = prev_first_last_games.last_time.isoformat(
                ) if prev_first_last_games.last_time else None
            else:
                prev_game_count = 0
                prev_first_time_iso = None
                prev_last_time_iso = None
                prev_subquery = None

        for value in values:
            # Count occurrences within current games
            current_count = session.query(func.count(CrashGame.gameId))\
                .filter(CrashGame.gameId.in_(select(current_subquery.c.gameId)))\
                .filter(CrashGame.crashPoint >= value)\
                .scalar()

            current_percentage = (
                current_count / actual_game_count) * 100 if actual_game_count > 0 else 0

            if comparison:
                # Count occurrences within previous games
                if 'prev_subquery' in locals() and prev_game_count > 0:
                    prev_count = session.query(func.count(CrashGame.gameId))\
                        .filter(CrashGame.gameId.in_(select(prev_subquery.c.gameId)))\
                        .filter(CrashGame.crashPoint >= value)\
                        .scalar()
                    prev_percentage = (prev_count / prev_game_count) * \
                        100 if prev_game_count > 0 else 0

                    # Calculate differences
                    count_diff = current_count - prev_count
                    percentage_diff = current_percentage - prev_percentage

                    # Calculate percent change (as a percentage of the previous value)
                    count_percent_change = (
                        (current_count - prev_count) / prev_count) * 100 if prev_count > 0 else None
                else:
                    prev_count = 0
                    prev_percentage = 0
                    count_diff = None
                    percentage_diff = None
                    count_percent_change = None

                results[value] = {
                    'current_period': {
                        'count': current_count,
                        'total_games': actual_game_count,
                        'percentage': current_percentage,
                        'first_game_time': current_first_time_iso,
                        'last_game_time': current_last_time_iso
                    },
                    'previous_period': {
                        'count': prev_count,
                        'total_games': prev_game_count,
                        'percentage': prev_percentage,
                        'first_game_time': prev_first_time_iso,
                        'last_game_time': prev_last_time_iso
                    },
                    'comparison': {
                        'count_diff': count_diff,
                        'percentage_diff': percentage_diff,
                        'count_percent_change': count_percent_change
                    }
                }
            else:
                # Return the original, simpler structure without comparison
                results[value] = {
                    'count': current_count,
                    'total_games': actual_game_count,
                    'percentage': current_percentage,
                    'first_game_time': current_first_time_iso,
                    'last_game_time': current_last_time_iso
                }

        return results

    except Exception as e:
        logger.error(
            f"Error getting min crash point occurrences by games batch: {str(e)}")
        raise


def get_min_crash_point_occurrences_by_time_batch(
    session: Session,
    values: List[float],
    hours: int = 1,
    comparison: bool = True
) -> Dict[float, Dict[str, Any]]:
    """
    Get the total occurrences of crash points >= specified values in the last N hours,
    and compare with the previous N hours.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point values to count
        hours: Number of hours to look back (default: 1)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics, optionally including comparison
        with the previous time period
    """
    try:
        results = {}
        now = datetime.now(timezone.utc)

        # Current interval
        start_time = now - timedelta(hours=hours)
        end_time = now

        # Previous interval (only if comparison is enabled)
        if comparison:
            prev_start_time = start_time - timedelta(hours=hours)
            prev_end_time = start_time

        for value in values:
            # Current interval query
            current_stats = session.query(
                func.count(CrashGame.gameId).label('count'),
                func.min(CrashGame.endTime).label('first_time'),
                func.max(CrashGame.endTime).label('last_time')
            ).filter(
                CrashGame.endTime >= start_time,
                CrashGame.endTime <= end_time,
                CrashGame.crashPoint >= value
            ).first()

            # Total games in current interval
            total_games = session.query(func.count(CrashGame.gameId))\
                .filter(
                    CrashGame.endTime >= start_time,
                    CrashGame.endTime <= end_time
            ).scalar()

            # Calculate occurrence counts and percentages
            count = current_stats.count if current_stats else 0
            percentage = (count / total_games) * 100 if total_games > 0 else 0

            # Format datetime objects as ISO strings for current period
            first_time_iso = current_stats.first_time.isoformat(
            ) if current_stats and current_stats.first_time else None
            last_time_iso = current_stats.last_time.isoformat(
            ) if current_stats and current_stats.last_time else None

            if comparison:
                # Previous interval query
                prev_stats = session.query(
                    func.count(CrashGame.gameId).label('count'),
                    func.min(CrashGame.endTime).label('first_time'),
                    func.max(CrashGame.endTime).label('last_time')
                ).filter(
                    CrashGame.endTime >= prev_start_time,
                    CrashGame.endTime <= prev_end_time,
                    CrashGame.crashPoint >= value
                ).first()

                # Total games in previous interval
                prev_total_games = session.query(func.count(CrashGame.gameId))\
                    .filter(
                        CrashGame.endTime >= prev_start_time,
                        CrashGame.endTime <= prev_end_time
                ).scalar()

                prev_count = prev_stats.count if prev_stats else 0
                prev_percentage = (prev_count / prev_total_games) * \
                    100 if prev_total_games > 0 else 0

                # Calculate differences
                count_diff = count - prev_count
                percentage_diff = percentage - prev_percentage

                # Calculate percent change (as a percentage of the previous value)
                count_percent_change = (
                    (current_count - prev_count) / prev_count) * 100 if prev_count > 0 else None

                # Format datetime objects as ISO strings for previous period
                prev_first_time_iso = prev_stats.first_time.isoformat(
                ) if prev_stats and prev_stats.first_time else None
                prev_last_time_iso = prev_stats.last_time.isoformat(
                ) if prev_stats and prev_stats.last_time else None

                results[value] = {
                    'current_period': {
                        'count': count,
                        'total_games': total_games,
                        'percentage': percentage,
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'first_game_time': first_time_iso,
                        'last_game_time': last_time_iso
                    },
                    'previous_period': {
                        'count': prev_count,
                        'total_games': prev_total_games,
                        'percentage': prev_percentage,
                        'start_time': prev_start_time.isoformat(),
                        'end_time': prev_end_time.isoformat(),
                        'first_game_time': prev_first_time_iso,
                        'last_game_time': prev_last_time_iso
                    },
                    'comparison': {
                        'count_diff': count_diff,
                        'percentage_diff': percentage_diff,
                        'count_percent_change': count_percent_change
                    }
                }
            else:
                # Return the original, simpler structure without comparison
                results[value] = {
                    'count': count,
                    'total_games': total_games,
                    'percentage': percentage,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'first_game_time': first_time_iso,
                    'last_game_time': last_time_iso
                }

        return results

    except Exception as e:
        logger.error(
            f"Error getting min crash point occurrences by time batch: {str(e)}")
        raise


def get_exact_floor_occurrences_by_games_batch(
    session: Session,
    values: List[int],
    limit: int = 100,
    comparison: bool = True
) -> Dict[int, Dict[str, Any]]:
    """
    Get the total occurrences of exact floor values in the last N games,
    and compare with the previous N games.

    Args:
        session: SQLAlchemy session
        values: List of floor values to count
        limit: Number of most recent games to analyze (default: 100)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics, optionally including comparison
        with the previous set of games
    """
    try:
        results = {}

        # Get the most recent 'limit' games (current period)
        current_subquery = session.query(CrashGame.gameId, CrashGame.endTime)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .subquery()

        # Count the actual number of games in the current subquery
        actual_game_count = session.query(
            func.count()).select_from(current_subquery).scalar()

        # Get first and last games in the current set for reference
        current_first_last_games = session.query(
            func.min(CrashGame.endTime).label('first_time'),
            func.max(CrashGame.endTime).label('last_time')
        ).select_from(CrashGame).filter(CrashGame.gameId.in_(select(current_subquery.c.gameId))).first()

        # Convert datetime objects to ISO string format for current period
        current_first_time_iso = current_first_last_games.first_time.isoformat(
        ) if current_first_last_games.first_time else None
        current_last_time_iso = current_first_last_games.last_time.isoformat(
        ) if current_first_last_games.last_time else None

        # Only get previous period data if comparison is enabled
        if comparison:
            # Get the oldest game from current period to use as cutoff for previous period
            oldest_current_game = session.query(CrashGame.endTime)\
                .order_by(desc(CrashGame.endTime))\
                .offset(limit-1)\
                .limit(1)\
                .first()

            if oldest_current_game:
                cutoff_time = oldest_current_game.endTime

                # Get the previous 'limit' games
                prev_subquery = session.query(
                    CrashGame.gameId, CrashGame.endTime)\
                    .filter(CrashGame.endTime < cutoff_time)\
                    .order_by(desc(CrashGame.endTime))\
                    .limit(limit)\
                    .subquery()

                # Count the actual number of games in the previous subquery
                prev_game_count = session.query(
                    func.count()).select_from(prev_subquery).scalar()

                # Get first and last games in the previous set for reference
                prev_first_last_games = session.query(
                    func.min(CrashGame.endTime).label('first_time'),
                    func.max(CrashGame.endTime).label('last_time')
                ).select_from(CrashGame).filter(CrashGame.gameId.in_(select(prev_subquery.c.gameId))).first()

                # Convert datetime objects to ISO string format for previous period
                prev_first_time_iso = prev_first_last_games.first_time.isoformat(
                ) if prev_first_last_games.first_time else None
                prev_last_time_iso = prev_first_last_games.last_time.isoformat(
                ) if prev_first_last_games.last_time else None
            else:
                prev_game_count = 0
                prev_first_time_iso = None
                prev_last_time_iso = None
                prev_subquery = None

        for value in values:
            # Count occurrences within current games
            current_count = session.query(func.count(CrashGame.gameId))\
                .filter(CrashGame.gameId.in_(select(current_subquery.c.gameId)))\
                .filter(CrashGame.crashedFloor == value)\
                .scalar()

            current_percentage = (
                current_count / actual_game_count) * 100 if actual_game_count > 0 else 0

            if comparison:
                # Count occurrences within previous games
                if 'prev_subquery' in locals() and prev_game_count > 0:
                    prev_count = session.query(func.count(CrashGame.gameId))\
                        .filter(CrashGame.gameId.in_(select(prev_subquery.c.gameId)))\
                        .filter(CrashGame.crashedFloor == value)\
                        .scalar()
                    prev_percentage = (prev_count / prev_game_count) * \
                        100 if prev_game_count > 0 else 0

                    # Calculate differences
                    count_diff = current_count - prev_count
                    percentage_diff = current_percentage - prev_percentage

                    # Calculate percent change (as a percentage of the previous value)
                    count_percent_change = (
                        (current_count - prev_count) / prev_count) * 100 if prev_count > 0 else None
                else:
                    prev_count = 0
                    prev_percentage = 0
                    count_diff = None
                    percentage_diff = None
                    count_percent_change = None

                results[value] = {
                    'current_period': {
                        'count': current_count,
                        'total_games': actual_game_count,
                        'percentage': current_percentage,
                        'first_game_time': current_first_time_iso,
                        'last_game_time': current_last_time_iso
                    },
                    'previous_period': {
                        'count': prev_count,
                        'total_games': prev_game_count,
                        'percentage': prev_percentage,
                        'first_game_time': prev_first_time_iso,
                        'last_game_time': prev_last_time_iso
                    },
                    'comparison': {
                        'count_diff': count_diff,
                        'percentage_diff': percentage_diff,
                        'count_percent_change': count_percent_change
                    }
                }
            else:
                # Return the original, simpler structure without comparison
                results[value] = {
                    'count': current_count,
                    'total_games': actual_game_count,
                    'percentage': current_percentage,
                    'first_game_time': current_first_time_iso,
                    'last_game_time': current_last_time_iso
                }

        return results

    except Exception as e:
        logger.error(
            f"Error getting exact floor occurrences by games batch: {str(e)}")
        raise


def get_exact_floor_occurrences_by_time_batch(
    session: Session,
    values: List[int],
    hours: int = 1,
    comparison: bool = True
) -> Dict[int, Dict[str, Any]]:
    """
    Get the total occurrences of exact floor values in the last N hours,
    and compare with the previous N hours.

    Args:
        session: SQLAlchemy session
        values: List of floor values to count
        hours: Number of hours to look back (default: 1)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics, optionally including comparison
        with the previous time period
    """
    try:
        results = {}
        now = datetime.now(timezone.utc)

        # Current interval
        start_time = now - timedelta(hours=hours)
        end_time = now

        # Previous interval (only if comparison is enabled)
        if comparison:
            prev_start_time = start_time - timedelta(hours=hours)
            prev_end_time = start_time

        for value in values:
            # Current interval query
            current_stats = session.query(
                func.count(CrashGame.gameId).label('count'),
                func.min(CrashGame.endTime).label('first_time'),
                func.max(CrashGame.endTime).label('last_time')
            ).filter(
                CrashGame.endTime >= start_time,
                CrashGame.endTime <= end_time,
                CrashGame.crashedFloor == value
            ).first()

            # Total games in current interval
            total_games = session.query(func.count(CrashGame.gameId))\
                .filter(
                    CrashGame.endTime >= start_time,
                    CrashGame.endTime <= end_time
            ).scalar()

            # Calculate occurrence counts and percentages
            count = current_stats.count if current_stats else 0
            percentage = (count / total_games) * 100 if total_games > 0 else 0

            # Format datetime objects as ISO strings for current period
            first_time_iso = current_stats.first_time.isoformat(
            ) if current_stats and current_stats.first_time else None
            last_time_iso = current_stats.last_time.isoformat(
            ) if current_stats and current_stats.last_time else None

            if comparison:
                # Previous interval query
                prev_stats = session.query(
                    func.count(CrashGame.gameId).label('count'),
                    func.min(CrashGame.endTime).label('first_time'),
                    func.max(CrashGame.endTime).label('last_time')
                ).filter(
                    CrashGame.endTime >= prev_start_time,
                    CrashGame.endTime <= prev_end_time,
                    CrashGame.crashedFloor == value
                ).first()

                # Total games in previous interval
                prev_total_games = session.query(func.count(CrashGame.gameId))\
                    .filter(
                        CrashGame.endTime >= prev_start_time,
                        CrashGame.endTime <= prev_end_time
                ).scalar()

                prev_count = prev_stats.count if prev_stats else 0
                prev_percentage = (prev_count / prev_total_games) * \
                    100 if prev_total_games > 0 else 0

                # Calculate differences
                count_diff = count - prev_count
                percentage_diff = percentage - prev_percentage

                # Calculate percent change (as a percentage of the previous value)
                count_percent_change = (
                    (current_count - prev_count) / prev_count) * 100 if prev_count > 0 else None

                # Format datetime objects as ISO strings for previous period
                prev_first_time_iso = prev_stats.first_time.isoformat(
                ) if prev_stats and prev_stats.first_time else None
                prev_last_time_iso = prev_stats.last_time.isoformat(
                ) if prev_stats and prev_stats.last_time else None

                results[value] = {
                    'current_period': {
                        'count': count,
                        'total_games': total_games,
                        'percentage': percentage,
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'first_game_time': first_time_iso,
                        'last_game_time': last_time_iso
                    },
                    'previous_period': {
                        'count': prev_count,
                        'total_games': prev_total_games,
                        'percentage': prev_percentage,
                        'start_time': prev_start_time.isoformat(),
                        'end_time': prev_end_time.isoformat(),
                        'first_game_time': prev_first_time_iso,
                        'last_game_time': prev_last_time_iso
                    },
                    'comparison': {
                        'count_diff': count_diff,
                        'percentage_diff': percentage_diff,
                        'count_percent_change': count_percent_change
                    }
                }
            else:
                # Return the original, simpler structure without comparison
                results[value] = {
                    'count': count,
                    'total_games': total_games,
                    'percentage': percentage,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'first_game_time': first_time_iso,
                    'last_game_time': last_time_iso
                }

        return results

    except Exception as e:
        logger.error(
            f"Error getting exact floor occurrences by time batch: {str(e)}")
        raise


def get_series_without_min_crash_point_by_games(
    session: Session,
    min_value: float,
    limit: int = 1000,
    sort_by: str = 'time'  # Options: 'time', 'length'
) -> List[Dict[str, Any]]:
    """
    Get series of games without crash points >= specified value in the last N games.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        limit: Number of most recent games to analyze (default: 1000)
        sort_by: How to sort results - 'time' (chronological) or 'length' (longest first)

    Returns:
        List of dictionaries, each containing information about a series of games
        without crash points >= min_value
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Reverse the list to process from oldest to newest
        games.reverse()

        series_list = []
        current_series = None

        for i, game in enumerate(games):
            # If game has crash point < min_value, it's part of a series
            if game.crashPoint < min_value:
                # Start a new series if needed
                if current_series is None:
                    current_series = {
                        'start_game_id': game.gameId,
                        'start_time': game.endTime,
                        'end_game_id': game.gameId,
                        'end_time': game.endTime,
                        'length': 1
                    }
                else:
                    # Extend the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # If we had a series going, save it
                if current_series is not None:
                    series_list.append(current_series)
                    current_series = None

        # Add the last series if it exists
        if current_series is not None:
            series_list.append(current_series)

        # Sort the series list based on the specified criterion
        if sort_by.lower() == 'length':
            # Sort by length (longest first)
            series_list.sort(key=lambda x: x['length'], reverse=True)
        else:
            # Default: Sort by time (most recent first)
            series_list.sort(key=lambda x: x['end_time'], reverse=True)

        return series_list

    except Exception as e:
        logger.error(
            f"Error analyzing series without min crash point by games: {str(e)}")
        raise


def get_series_without_min_crash_point_by_time(
    session: Session,
    min_value: float,
    hours: int = 24,
    sort_by: str = 'time'  # Options: 'time', 'length'
) -> List[Dict[str, Any]]:
    """
    Get series of games without crash points >= specified value in the last N hours.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        hours: Total hours to analyze (default: 24)
        sort_by: How to sort results - 'time' (chronological) or 'length' (longest first)

    Returns:
        List of dictionaries, each containing information about a series of games
        without crash points >= min_value
    """
    try:
        # Calculate the time threshold in UTC
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get games in the time period ordered by time
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .order_by(CrashGame.endTime)\
            .all()

        series_list = []
        current_series = None

        for i, game in enumerate(games):
            # If game has crash point < min_value, it's part of a series
            if game.crashPoint < min_value:
                # Start a new series if needed
                if current_series is None:
                    current_series = {
                        'start_game_id': game.gameId,
                        'start_time': game.endTime,
                        'end_game_id': game.gameId,
                        'end_time': game.endTime,
                        'length': 1
                    }
                else:
                    # Extend the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # If we had a series going, save it
                if current_series is not None:
                    series_list.append(current_series)
                    current_series = None

        # Add the last series if it exists
        if current_series is not None:
            series_list.append(current_series)

        # Sort the series list based on the specified criterion
        if sort_by.lower() == 'length':
            # Sort by length (longest first)
            series_list.sort(key=lambda x: x['length'], reverse=True)
        else:
            # Default: Sort by time (most recent first)
            series_list.sort(key=lambda x: x['end_time'], reverse=True)

        return series_list

    except Exception as e:
        logger.error(
            f"Error analyzing series without min crash point by time: {str(e)}")
        raise


def get_min_crash_point_intervals_by_time(
    session: Session,
    min_value: float,
    interval_minutes: int = 10,
    hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Analyze crash points >= specified value in fixed time intervals.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        interval_minutes: Size of each interval in minutes (default: 10)
        hours: Total hours to analyze (default: 24)

    Returns:
        List of dictionaries, each containing statistics for a time interval
    """
    try:
        # Calculate the end time in UTC
        end_time = datetime.now(timezone.utc)

        # Round the end time down to the nearest interval boundary
        minutes = end_time.minute
        floored_minutes = (minutes // interval_minutes) * interval_minutes

        # Create a clean end time at the interval boundary
        clean_end_time = end_time.replace(
            minute=floored_minutes,
            second=0,
            microsecond=0
        )

        # The actual end time for analysis (used for filtering games)
        analysis_end_time = end_time

        # Calculate the clean interval end time for the last interval
        # This is the next interval boundary after clean_end_time
        last_interval_end = clean_end_time + \
            timedelta(minutes=interval_minutes)

        # Calculate the start time by going back the requested number of hours
        # from the clean end time (keeping it on interval boundaries)
        start_time = clean_end_time - timedelta(hours=hours)

        interval_delta = timedelta(minutes=interval_minutes)

        # Get all games in the time period
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.endTime <= analysis_end_time)\
            .order_by(CrashGame.endTime)\
            .all()

        intervals = []
        current_interval_start = start_time

        # Process all intervals with standard boundaries
        while current_interval_start < last_interval_end:
            # Always use standard interval boundaries for all intervals
            current_interval_end = current_interval_start + interval_delta

            # Count games in this interval
            interval_games = [
                g for g in games if current_interval_start <= g.endTime < min(current_interval_end, analysis_end_time)]
            total_games = len(interval_games)

            # Count games with crash point >= min_value
            matching_games = len(
                [g for g in interval_games if g.crashPoint >= min_value])

            # Only include intervals that have games
            if total_games > 0:
                intervals.append({
                    'interval_start': current_interval_start,
                    'interval_end': current_interval_end,
                    'count': matching_games,
                    'total_games': total_games,
                    'percentage': (matching_games / total_games) * 100 if total_games > 0 else 0
                })

            current_interval_start = current_interval_end

        return intervals

    except Exception as e:
        logger.error(f"Error analyzing intervals by time: {str(e)}")
        raise


def get_min_crash_point_intervals_by_game_sets(
    session: Session,
    min_value: float,
    games_per_set: int = 10,
    total_games: int = 1000
) -> List[Dict[str, Any]]:
    """
    Analyze crash points >= specified value in fixed-size game sets.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        List of dictionaries, each containing statistics for a game set
    """
    try:
        # Get the most recent games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(total_games)\
            .all()

        # Reverse to process from oldest to newest
        games.reverse()

        intervals = []
        total_sets = (len(games) + games_per_set - 1) // games_per_set

        for set_number in range(total_sets):
            start_idx = set_number * games_per_set
            end_idx = min(start_idx + games_per_set, len(games))
            current_set = games[start_idx:end_idx]

            # Count games with crash point >= min_value
            matching_games = len(
                [g for g in current_set if g.crashPoint >= min_value])

            intervals.append({
                'set_number': set_number + 1,  # 1-based set numbering
                'start_game': current_set[0].gameId,
                'end_game': current_set[-1].gameId,
                'count': matching_games,
                'total_games': len(current_set),
                'percentage': (matching_games / len(current_set)) * 100,
                'start_time': current_set[0].endTime,
                'end_time': current_set[-1].endTime
            })

        return intervals

    except Exception as e:
        logger.error(f"Error analyzing intervals by game sets: {str(e)}")
        raise


def get_min_crash_point_intervals_by_time_batch(
    session: Session,
    values: List[float],
    interval_minutes: int = 10,
    hours: int = 24
) -> Dict[float, List[Dict[str, Any]]]:
    """
    Analyze crash points >= specified values in fixed time intervals.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        interval_minutes: Size of each interval in minutes (default: 10)
        hours: Total hours to analyze (default: 24)

    Returns:
        Dictionary mapping each value to its interval analysis results
    """
    try:
        results = {}
        for value in values:
            results[value] = get_min_crash_point_intervals_by_time(
                session, value, interval_minutes, hours)
        return results

    except Exception as e:
        logger.error(f"Error analyzing intervals by time batch: {str(e)}")
        raise


def get_min_crash_point_intervals_by_game_sets_batch(
    session: Session,
    values: List[float],
    games_per_set: int = 10,
    total_games: int = 1000
) -> Dict[float, List[Dict[str, Any]]]:
    """
    Analyze crash points >= specified values in fixed-size game sets.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        Dictionary mapping each value to its interval analysis results
    """
    try:
        results = {}
        for value in values:
            results[value] = get_min_crash_point_intervals_by_game_sets(
                session, value, games_per_set, total_games)
        return results

    except Exception as e:
        logger.error(f"Error analyzing intervals by game sets batch: {str(e)}")
        raise
