"""
Interval analytics functions.

This module contains functions for analyzing game data in time
and game count intervals to identify patterns and occurrences.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


def get_min_crash_point_intervals_by_time(
    session: Session,
    min_value: float,
    interval_minutes: int = 10,
    hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Count occurrences of crash points >= specified value in time intervals.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        interval_minutes: Size of each interval in minutes (default: 10)
        hours: Total hours to analyze (default: 24)

    Returns:
        List of dictionaries containing interval data, each with:
        - interval_start: Start time of the interval
        - interval_end: End time of the interval
        - count: Number of occurrences in this interval
        - total_games: Total games in this interval
        - percentage: Percentage of games with crash point >= min_value
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
    Count occurrences of crash points >= specified value in game set intervals.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        List of dictionaries containing interval data, each with:
        - set_id: Identifier for the game set
        - start_time: Start time of the interval
        - end_time: End time of the interval
        - count: Number of occurrences in this set
        - percentage: Percentage of games with crash point >= min_value
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
    Count occurrences of crash points >= specified values in time intervals.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        interval_minutes: Size of each interval in minutes (default: 10)
        hours: Total hours to analyze (default: 24)

    Returns:
        Dictionary mapping each value to a list of interval data
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
    Count occurrences of crash points >= specified values in game set intervals.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        Dictionary mapping each value to a list of interval data
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
