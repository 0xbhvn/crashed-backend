"""
Interval analytics functions.

This module contains functions for analyzing game data in time
and game count intervals to identify patterns and occurrences.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

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


def get_min_crash_point_intervals_by_date_range(
    session: Session,
    min_value: float,
    start_date: datetime,
    end_date: datetime,
    interval_minutes: int = 10
) -> List[Dict[str, Any]]:
    """
    Count occurrences of crash points >= specified value in time intervals between two dates.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        start_date: Start date for analysis (inclusive)
        end_date: End date for analysis (inclusive)
        interval_minutes: Size of each interval in minutes (default: 10)

    Returns:
        List of dictionaries containing interval data, each with:
        - interval_start: Start time of the interval
        - interval_end: End time of the interval
        - count: Number of occurrences in this interval
        - total_games: Total games in this interval
        - percentage: Percentage of games with crash point >= min_value
    """
    try:
        logger.info(f"Starting interval analysis by date range: min_value={min_value}, "
                    f"start_date={start_date}, end_date={end_date}, interval_minutes={interval_minutes}")

        # Limit the date range to a maximum of 7 days to prevent excessive processing
        date_range_days = (end_date - start_date).days
        if date_range_days > 7:
            logger.warning(
                f"Date range too large ({date_range_days} days). Limiting to 7 days.")
            end_date = start_date + timedelta(days=7)

        # Normalize start date to beginning of day
        normalized_start_date = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0)

        # Normalize end date to end of day
        normalized_end_date = end_date.replace(
            hour=23, minute=59, second=59, microsecond=999999)

        logger.info(
            f"Normalized date range: {normalized_start_date} to {normalized_end_date}")

        # Calculate interval boundaries
        interval_delta = timedelta(minutes=interval_minutes)

        # Get all games in the date range with a single query
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= normalized_start_date)\
            .filter(CrashGame.endTime <= normalized_end_date)\
            .order_by(CrashGame.endTime)\
            .all()

        logger.info(f"Retrieved {len(games)} games from the database")

        # Process all intervals with in-memory data
        intervals = []
        current_interval_start = normalized_start_date

        while current_interval_start <= normalized_end_date:
            current_interval_end = current_interval_start + interval_delta

            # Filter games in this interval using Python instead of database queries
            interval_games = [
                g for g in games
                if current_interval_start <= g.endTime < current_interval_end
            ]

            total_games = len(interval_games)

            # Only include intervals that have games
            if total_games > 0:
                # Count games with crash point >= min_value
                matching_games = len(
                    [g for g in interval_games if g.crashPoint >= min_value]
                )

                percentage = (matching_games / total_games) * 100

                intervals.append({
                    'interval_start': current_interval_start,
                    'interval_end': current_interval_end,
                    'count': matching_games,
                    'total_games': total_games,
                    'percentage': percentage
                })

            current_interval_start = current_interval_end

            # Progress logging for long operations
            if len(intervals) % 100 == 0 and len(intervals) > 0:
                logger.info(f"Processed {len(intervals)} intervals so far")

        logger.info(
            f"Completed interval analysis: found {len(intervals)} intervals with game data")
        return intervals

    except Exception as e:
        logger.error(f"Error analyzing intervals by date range: {str(e)}")
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

        # If there are fewer games than expected, adjust total_games
        if len(games) < total_games:
            total_games = len(games)

        # Calculate how many complete sets we can make
        num_sets = total_games // games_per_set

        intervals = []

        # Process each complete set
        for i in range(num_sets):
            # Get the games for this set
            start_idx = i * games_per_set
            end_idx = start_idx + games_per_set
            set_games = games[start_idx:end_idx]

            # Get the start and end times for this set
            start_time = set_games[-1].endTime  # Latest game in this set
            end_time = set_games[0].endTime     # Earliest game in this set

            # Count games with crash point >= min_value
            matching_games = len(
                [g for g in set_games if g.crashPoint >= min_value])

            percentage = (matching_games / games_per_set) * 100

            # Add the interval data
            intervals.append({
                'set_id': i,
                'start_time': start_time,
                'end_time': end_time,
                'count': matching_games,
                'total_games': games_per_set,
                'percentage': percentage
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
        Dictionary mapping each value to its corresponding interval data
    """
    try:
        # Process each value
        result = {}
        for value in values:
            # Get intervals for this value
            intervals = get_min_crash_point_intervals_by_time(
                session, value, interval_minutes, hours)
            # Add to result
            result[str(value)] = intervals

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing intervals by time batch: {str(e)}")
        raise


def get_min_crash_point_intervals_by_date_range_batch(
    session: Session,
    values: List[float],
    start_date: datetime,
    end_date: datetime,
    interval_minutes: int = 10
) -> Dict[float, List[Dict[str, Any]]]:
    """
    Count occurrences of crash points >= specified values in time intervals between two dates.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        start_date: Start date for analysis
        end_date: End date for analysis
        interval_minutes: Size of each interval in minutes (default: 10)

    Returns:
        Dictionary mapping each value to its corresponding interval data
    """
    try:
        logger.info(
            f"Starting batch interval analysis for {len(values)} values")

        # Limit the date range to a maximum of 7 days to prevent excessive processing
        date_range_days = (end_date - start_date).days
        if date_range_days > 7:
            logger.warning(
                f"Date range too large ({date_range_days} days). Limiting to 7 days.")
            end_date = start_date + timedelta(days=7)

        # Process each value
        result = {}
        for i, value in enumerate(values):
            logger.info(f"Processing value {i+1}/{len(values)}: {value}")
            # Get intervals for this value
            intervals = get_min_crash_point_intervals_by_date_range(
                session, value, start_date, end_date, interval_minutes)
            # Add to result
            result[str(value)] = intervals

        logger.info(
            f"Completed batch interval analysis for {len(values)} values")
        return result

    except Exception as e:
        logger.error(
            f"Error analyzing intervals by date range batch: {str(e)}")
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
        Dictionary mapping each value to its corresponding interval data
    """
    try:
        # Process each value
        result = {}
        for value in values:
            # Get intervals for this value
            intervals = get_min_crash_point_intervals_by_game_sets(
                session, value, games_per_set, total_games)
            # Add to result
            result[str(value)] = intervals

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing intervals by game sets batch: {str(e)}")
        raise
