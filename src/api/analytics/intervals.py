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
    min_crash_point: float,
    games_per_set: int = 10,
    total_games: int = 1000
) -> List[Dict[str, Any]]:
    """
    Count occurrences of crash points >= min_crash_point in game set intervals.

    Args:
        session: SQLAlchemy session
        min_crash_point: Minimum crash point threshold
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        List of intervals with occurrence data
    """
    try:
        # Ensure games_per_set is valid
        valid_set_sizes = [10, 20, 25, 50]
        if games_per_set not in valid_set_sizes:
            logger.warning(f"games_per_set={games_per_set} is not in valid set sizes. " +
                           f"Using closest valid value: {min(valid_set_sizes, key=lambda x: abs(x-games_per_set))}")
            games_per_set = min(
                valid_set_sizes, key=lambda x: abs(x-games_per_set))

        # Get the most recent games for analysis
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.gameId))\
            .limit(total_games)\
            .all()

        if not games:
            return []

        # Determine the highest and lowest game IDs
        highest_game_id = int(games[0].gameId)
        lowest_game_id = int(games[-1].gameId)

        # Helper function to calculate interval start ID for any game ID
        def get_interval_start_id(game_id):
            intervals_per_hundred = 100 // games_per_set
            game_offset_in_hundred = game_id % 100
            interval_index = game_offset_in_hundred // games_per_set
            interval_start_offset = interval_index * games_per_set
            return (game_id // 100) * 100 + interval_start_offset

        # Calculate the interval boundaries for highest game
        highest_interval_start = get_interval_start_id(highest_game_id)
        highest_interval_end = highest_interval_start + games_per_set - 1

        # Calculate the interval boundaries for lowest game
        lowest_interval_start = get_interval_start_id(lowest_game_id)
        lowest_interval_end = lowest_interval_start + games_per_set - 1

        # Create a mapping of intervals to store games
        game_intervals = {}

        # Initialize the set counter
        set_id = 1

        # Create intervals from highest to lowest, ensuring we include both boundary games
        current_interval_start = highest_interval_start

        while current_interval_start >= lowest_interval_start:
            interval_end = current_interval_start + games_per_set - 1
            interval_key = f"{current_interval_start}-{interval_end}"

            # Mark the current interval (containing highest_game_id) as in-progress
            is_current_interval = (
                highest_interval_start == current_interval_start)

            game_intervals[interval_key] = {
                'set_id': set_id,
                'start_game': current_interval_start,
                'end_game': interval_end,
                'games': [],
                'is_current_interval': is_current_interval
            }

            # Move to the previous interval
            if current_interval_start % 100 >= games_per_set:
                # Previous interval in the same hundred
                current_interval_start -= games_per_set
            else:
                # Last interval in the previous hundred
                intervals_per_hundred = 100 // games_per_set
                last_interval_offset = (
                    (intervals_per_hundred - 1) * games_per_set)
                current_interval_start = (
                    (current_interval_start // 100) - 1) * 100 + last_interval_offset

            set_id += 1

        # Assign games to intervals
        for game in games:
            game_id = int(game.gameId)
            interval_start = get_interval_start_id(game_id)
            interval_end = interval_start + games_per_set - 1
            interval_key = f"{interval_start}-{interval_end}"

            if interval_key in game_intervals:
                game_intervals[interval_key]['games'].append(game)

        # Find the earliest and latest times for reference (for intervals with no games)
        earliest_time = None
        latest_time = None
        for interval_data in game_intervals.values():
            if interval_data['games']:
                interval_games = sorted(
                    interval_data['games'], key=lambda g: g.endTime)
                if earliest_time is None or interval_games[0].endTime < earliest_time:
                    earliest_time = interval_games[0].endTime
                if latest_time is None or interval_games[-1].endTime > latest_time:
                    latest_time = interval_games[-1].endTime

        # If we couldn't find any time reference, use current time
        if earliest_time is None:
            earliest_time = datetime.now()
            latest_time = earliest_time

        # Create result intervals in sequential order (from highest to lowest)
        result = []

        # Sort intervals by set_id (which is sequential from highest to lowest)
        sorted_intervals = sorted(
            game_intervals.items(), key=lambda x: x[1]['set_id'])

        for interval_key, interval_data in sorted_intervals:
            # Calculate statistics for this interval
            interval_games = interval_data['games']
            matching_games = len(
                [g for g in interval_games if g.crashPoint >= min_crash_point])

            # For completed intervals, total_games should be the full interval size
            # For the current (most recent) interval, use actual count from the database
            if interval_data['is_current_interval']:
                total_interval_games = len(interval_games)
            else:
                # For past intervals that should be complete, use the full interval size
                total_interval_games = games_per_set

                # Calculate the adjusted matching_games based on percentage from actual data
                actual_games = len(interval_games)
                if actual_games > 0:
                    # Extrapolate the matching games to full interval size
                    matching_percentage = matching_games / actual_games
                    matching_games = round(matching_percentage * games_per_set)

            # Get the start and end times from the games in this interval
            if interval_games:
                # Sort games by time for time range calculation
                interval_games = sorted(
                    interval_games, key=lambda g: g.endTime)
                start_time = interval_games[0].endTime
                end_time = interval_games[-1].endTime
            else:
                # For intervals with no games, use estimated times
                time_diff = latest_time - earliest_time
                num_intervals = len(game_intervals)
                if num_intervals > 1:
                    relative_position = (
                        interval_data['set_id'] - 1) / (num_intervals - 1)
                    estimated_time = latest_time - \
                        (time_diff * relative_position)
                    # Offset slightly for start/end
                    start_time = estimated_time - timedelta(minutes=1)
                    end_time = estimated_time
                else:
                    start_time = earliest_time
                    end_time = latest_time

            result.append({
                'set_id': interval_data['set_id'],
                'start_time': start_time,
                'end_time': end_time,
                'start_game': interval_data['start_game'],
                'end_game': interval_data['end_game'],
                'count': matching_games,
                'total_games': total_interval_games,
                'percentage': (matching_games / total_interval_games) * 100 if total_interval_games > 0 else 0,
                'is_current_interval': interval_data['is_current_interval'],
                'actual_games': len(interval_games)  # For debugging
            })

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing intervals by game sets: {str(e)}")
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
    Count occurrences of crash points >= min_crash_point in game set intervals
    for multiple threshold values.

    Args:
        session: SQLAlchemy session
        values: List of minimum crash point thresholds
        games_per_set: Number of games in each set (default: 10)
        total_games: Total games to analyze (default: 1000)

    Returns:
        Dictionary mapping each value to its corresponding interval data
    """
    try:
        # Ensure games_per_set is a divisor of 100 for proper boundary alignment
        valid_set_sizes = [10, 20, 25, 50]
        if games_per_set not in valid_set_sizes:
            logger.warning(f"games_per_set={games_per_set} is not a divisor of 100. " +
                           f"Using closest valid value: {min(valid_set_sizes, key=lambda x: abs(x-games_per_set))}")
            games_per_set = min(
                valid_set_sizes, key=lambda x: abs(x-games_per_set))

        # Get the games once for all values to avoid multiple queries
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.gameId))\
            .limit(total_games)\
            .all()

        if not games:
            return {str(value): [] for value in values}

        # Determine the highest and lowest game IDs
        highest_game_id = int(games[0].gameId)
        lowest_game_id = int(games[-1].gameId)

        # Helper function to calculate interval start ID for any game ID
        def get_interval_start_id(game_id):
            intervals_per_hundred = 100 // games_per_set
            game_offset_in_hundred = game_id % 100
            interval_index = game_offset_in_hundred // games_per_set
            interval_start_offset = interval_index * games_per_set
            return (game_id // 100) * 100 + interval_start_offset

        # Calculate the interval boundaries for highest game
        highest_interval_start = get_interval_start_id(highest_game_id)
        highest_interval_end = highest_interval_start + games_per_set - 1

        # Calculate the interval boundaries for lowest game
        lowest_interval_start = get_interval_start_id(lowest_game_id)
        lowest_interval_end = lowest_interval_start + games_per_set - 1

        # Create a mapping of intervals to store games
        game_intervals = {}

        # Initialize the set counter
        set_id = 1

        # Create intervals from highest to lowest, ensuring we include both boundary games
        current_interval_start = highest_interval_start

        while current_interval_start >= lowest_interval_start:
            interval_end = current_interval_start + games_per_set - 1
            interval_key = f"{current_interval_start}-{interval_end}"

            # Mark the current interval (containing highest_game_id) as in-progress
            is_current_interval = (
                highest_interval_start == current_interval_start)

            game_intervals[interval_key] = {
                'set_id': set_id,
                'start_game': current_interval_start,
                'end_game': interval_end,
                'games': [],
                'is_current_interval': is_current_interval
            }

            # Move to the previous interval
            if current_interval_start % 100 >= games_per_set:
                # Previous interval in the same hundred
                current_interval_start -= games_per_set
            else:
                # Last interval in the previous hundred
                intervals_per_hundred = 100 // games_per_set
                last_interval_offset = (
                    (intervals_per_hundred - 1) * games_per_set)
                current_interval_start = (
                    (current_interval_start // 100) - 1) * 100 + last_interval_offset

            set_id += 1

        # Assign games to intervals
        for game in games:
            game_id = int(game.gameId)
            interval_start = get_interval_start_id(game_id)
            interval_end = interval_start + games_per_set - 1
            interval_key = f"{interval_start}-{interval_end}"

            if interval_key in game_intervals:
                game_intervals[interval_key]['games'].append(game)

        # Find the earliest and latest times for reference (for intervals with no games)
        earliest_time = None
        latest_time = None
        for interval_data in game_intervals.values():
            if interval_data['games']:
                interval_games = sorted(
                    interval_data['games'], key=lambda g: g.endTime)
                if earliest_time is None or interval_games[0].endTime < earliest_time:
                    earliest_time = interval_games[0].endTime
                if latest_time is None or interval_games[-1].endTime > latest_time:
                    latest_time = interval_games[-1].endTime

        # If we couldn't find any time reference, use current time
        if earliest_time is None:
            earliest_time = datetime.now()
            latest_time = earliest_time

        # Sort intervals by set_id (which is sequential from highest to lowest)
        sorted_intervals = sorted(
            game_intervals.items(), key=lambda x: x[1]['set_id'])
        num_intervals = len(game_intervals)

        # Process each value to calculate intervals
        result = {}
        for value in values:
            value_intervals = []

            # Create result intervals in sequential order (from highest to lowest)
            for interval_key, interval_data in sorted_intervals:
                # Calculate statistics for this interval and value
                interval_games = interval_data['games']
                matching_games = len(
                    [g for g in interval_games if g.crashPoint >= value])

                # For completed intervals, total_games should be the full interval size
                # For the current (most recent) interval, use actual count from the database
                if interval_data['is_current_interval']:
                    total_interval_games = len(interval_games)
                else:
                    # For past intervals that should be complete, use the full interval size
                    total_interval_games = games_per_set

                    # Calculate the adjusted matching_games based on percentage from actual data
                    actual_games = len(interval_games)
                    if actual_games > 0:
                        # Extrapolate the matching games to full interval size
                        matching_percentage = matching_games / actual_games
                        matching_games = round(
                            matching_percentage * games_per_set)

                # Get the start and end times from the games in this interval
                if interval_games:
                    # Sort games by time for time range calculation
                    interval_games = sorted(
                        interval_games, key=lambda g: g.endTime)
                    start_time = interval_games[0].endTime
                    end_time = interval_games[-1].endTime
                else:
                    # For intervals with no games, use estimated times
                    time_diff = latest_time - earliest_time
                    if num_intervals > 1:
                        relative_position = (
                            interval_data['set_id'] - 1) / (num_intervals - 1)
                        estimated_time = latest_time - \
                            (time_diff * relative_position)
                        # Offset slightly for start/end
                        start_time = estimated_time - timedelta(minutes=1)
                        end_time = estimated_time
                    else:
                        start_time = earliest_time
                        end_time = latest_time

                value_intervals.append({
                    'set_id': interval_data['set_id'],
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_game': interval_data['start_game'],
                    'end_game': interval_data['end_game'],
                    'count': matching_games,
                    'total_games': total_interval_games,
                    'percentage': (matching_games / total_interval_games) * 100 if total_interval_games > 0 else 0,
                    'is_current_interval': interval_data['is_current_interval'],
                    'actual_games': len(interval_games)  # For debugging
                })

            # Add to result dictionary
            result[str(value)] = value_intervals

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing intervals by game sets batch: {str(e)}")
        raise
