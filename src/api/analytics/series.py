"""
Series analytics functions.

This module contains functions for analyzing series of games
without crash points above certain thresholds.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


def _extend_games_for_complete_streaks(
    session: Session,
    games: List[CrashGame],
    min_value: float,
    max_extension: int = 500
) -> List[CrashGame]:
    """
    Extend the games list backwards to ensure any partial streak at the beginning is complete.

    Args:
        session: SQLAlchemy session
        games: List of games (should be ordered from oldest to newest)
        min_value: Minimum crash point threshold
        max_extension: Maximum number of additional games to fetch (safety limit)

    Returns:
        Extended list of games with complete streaks
    """
    if not games:
        return games

    # Check if the oldest game is part of an incomplete streak
    oldest_game = games[0]
    if oldest_game.crashPoint >= min_value:
        # No extension needed - the oldest game ends a streak
        return games

    # Need to extend backwards to find the start of this streak
    extended_games = []
    current_oldest_time = oldest_game.endTime
    extension_count = 0

    while extension_count < max_extension:
        # Fetch older games in batches
        batch_size = min(100, max_extension - extension_count)
        older_games = session.query(CrashGame)\
            .filter(CrashGame.endTime < current_oldest_time)\
            .order_by(desc(CrashGame.endTime))\
            .limit(batch_size)\
            .all()

        if not older_games:
            # No more older games available
            break

        # Reverse to get oldest first
        older_games.reverse()

        # Check each game from newest to oldest in this batch
        for game in reversed(older_games):
            extended_games.insert(0, game)
            extension_count += 1

            if game.crashPoint >= min_value:
                # Found the end of the previous streak, we can stop extending
                logger.info(
                    f"Extended games list by {extension_count} games to complete partial streak")
                return extended_games + games

        # Update current_oldest_time for next iteration
        current_oldest_time = older_games[0].endTime

    # If we reach here, we hit the max_extension limit
    logger.warning(
        f"Hit max extension limit of {max_extension} games while completing streak")
    return extended_games + games


def get_series_without_min_crash_point_by_games(
    session: Session,
    min_value: float,
    limit: int = 1000,
    sort_by: str = 'time'  # Options: 'time', 'length'
) -> List[Dict[str, Any]]:
    """
    Find series of consecutive games without crash points >= specified value
    in the most recent N games.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        limit: Number of most recent games to analyze (default: 1000)
        sort_by: How to sort results - 'time' (default) or 'length'

    Returns:
        List of dictionaries containing series data, each with:
        - length: Number of games in the series (including the following crash)
        - start_time: Start time of the series
        - end_time: End time of the series
        - start_game_id: ID of the first game in the series
        - end_game_id: ID of the last game in the series
        - crash_point: The crash point value that terminated the series (None if series is incomplete)
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Reverse the list to process from oldest to newest
        games.reverse()

        # Extend games backwards to complete any partial streaks
        games = _extend_games_for_complete_streaks(session, games, min_value)

        series_list = []
        current_series = None

        for game in games:
            if game.crashPoint < min_value:
                # Game is part of a streak (crash point < min_value)
                if current_series is None:
                    # Start a new series
                    current_series = {
                        'start_game_id': game.gameId,
                        'start_time': game.endTime,
                        'end_game_id': game.gameId,
                        'end_time': game.endTime,
                        'length': 1
                    }
                else:
                    # Continue the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # Game has crash point >= min_value
                if current_series is not None:
                    # This game terminates the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
                    current_series['crash_point'] = game.crashPoint

                    series_list.append(current_series)
                    current_series = None
                else:
                    # This is a standalone high crash point game (no series below min_value before it)
                    # Create a length-1 series for tracking purposes
                    standalone_series = {
                        'start_game_id': game.gameId,
                        'start_time': game.endTime,
                        'end_game_id': game.gameId,
                        'end_time': game.endTime,
                        'length': 1,
                        'crash_point': game.crashPoint
                    }
                    series_list.append(standalone_series)

        # Handle case where the last games are all < min_value (incomplete series)
        if current_series is not None:
            # No crash_point since series wasn't terminated by a high crash
            current_series['crash_point'] = None
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
    Find series of consecutive games without crash points >= specified value
    in the last N hours.

    Args:
        session: SQLAlchemy session
        min_value: Minimum crash point threshold
        hours: Number of hours to look back (default: 24)
        sort_by: How to sort results - 'time' (default) or 'length'

    Returns:
        List of dictionaries containing series data, each with:
        - length: Number of games in the series (including the following crash)
        - start_time: Start time of the series
        - end_time: End time of the series
        - games: List of games in the series
        - follow_streak: Information about games after the series with crash points >= min_value
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

        # Extend games backwards to complete any partial streaks
        games = _extend_games_for_complete_streaks(session, games, min_value)

        series_list = []
        current_series = None

        for game in games:
            if game.crashPoint < min_value:
                # Game is part of a streak (crash point < min_value)
                if current_series is None:
                    # Start a new series
                    current_series = {
                        'start_game_id': game.gameId,
                        'start_time': game.endTime,
                        'end_game_id': game.gameId,
                        'end_time': game.endTime,
                        'length': 1,
                        'follow_streak': {
                            'count': 0,
                            'games': []
                        }
                    }
                else:
                    # Continue the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # Game has crash point >= min_value
                if current_series is not None:
                    # This game terminates the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
                    current_series['follow_streak'] = {
                        'count': 1,
                        'games': [{
                            'game_id': game.gameId,
                            'crash_point': game.crashPoint,
                            'time': game.endTime
                        }]
                    }

                    series_list.append(current_series)
                    current_series = None
                # If current_series is None, this is just a standalone high crash point game
                # We don't create a series for standalone high crash point games

        # Handle case where the last games are all < min_value (incomplete series)
        if current_series is not None:
            current_series['follow_streak'] = {
                'count': 0,
                'games': []
            }
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
