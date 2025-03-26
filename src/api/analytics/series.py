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
        - length: Number of games in the series
        - start_time: Start time of the series
        - end_time: End time of the series
        - games: List of games in the series
        - follow_streak: Information about games after the series with crash points >= min_value
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
        current_follow_games = []
        in_follow_streak = False

        for i, game in enumerate(games):
            # If game has crash point < min_value, it's part of a series
            if game.crashPoint < min_value:
                # If we were collecting follow streak games for a previous series
                if in_follow_streak and current_follow_games and series_list:
                    # Add the collected follow streak to the most recent series
                    series_list[-1]['follow_streak'] = {
                        'count': len(current_follow_games),
                        'games': current_follow_games
                    }
                    current_follow_games = []
                    in_follow_streak = False

                # Start a new series if needed
                if current_series is None:
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
                    # Extend the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # Game with crash point >= min_value
                if current_series is not None:
                    # End the current series and start collecting follow streak games
                    in_follow_streak = True
                    current_follow_games = [{
                        'game_id': game.gameId,
                        'crash_point': game.crashPoint,
                        'time': game.endTime
                    }]

                    # Set an empty follow_streak as a placeholder
                    current_series['follow_streak'] = {
                        'count': 0,
                        'games': []
                    }

                    series_list.append(current_series)
                    current_series = None
                elif in_follow_streak:
                    # Continue collecting follow streak games for the previous series
                    current_follow_games.append({
                        'game_id': game.gameId,
                        'crash_point': game.crashPoint,
                        'time': game.endTime
                    })

        # Add the last series if it exists
        if current_series is not None:
            current_series['follow_streak'] = {
                'count': 0,
                'games': []
            }
            series_list.append(current_series)

        # Add any remaining follow streak games to the last series
        if in_follow_streak and current_follow_games and series_list:
            series_list[-1]['follow_streak'] = {
                'count': len(current_follow_games),
                'games': current_follow_games
            }

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
        - length: Number of games in the series
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

        series_list = []
        current_series = None
        current_follow_games = []
        in_follow_streak = False

        for i, game in enumerate(games):
            # If game has crash point < min_value, it's part of a series
            if game.crashPoint < min_value:
                # If we were collecting follow streak games for a previous series
                if in_follow_streak and current_follow_games and series_list:
                    # Add the collected follow streak to the most recent series
                    series_list[-1]['follow_streak'] = {
                        'count': len(current_follow_games),
                        'games': current_follow_games
                    }
                    current_follow_games = []
                    in_follow_streak = False

                # Start a new series if needed
                if current_series is None:
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
                    # Extend the current series
                    current_series['end_game_id'] = game.gameId
                    current_series['end_time'] = game.endTime
                    current_series['length'] += 1
            else:
                # Game with crash point >= min_value
                if current_series is not None:
                    # End the current series and start collecting follow streak games
                    in_follow_streak = True
                    current_follow_games = [{
                        'game_id': game.gameId,
                        'crash_point': game.crashPoint,
                        'time': game.endTime
                    }]

                    # Set an empty follow_streak as a placeholder
                    current_series['follow_streak'] = {
                        'count': 0,
                        'games': []
                    }

                    series_list.append(current_series)
                    current_series = None
                elif in_follow_streak:
                    # Continue collecting follow streak games for the previous series
                    current_follow_games.append({
                        'game_id': game.gameId,
                        'crash_point': game.crashPoint,
                        'time': game.endTime
                    })

        # Add the last series if it exists
        if current_series is not None:
            current_series['follow_streak'] = {
                'count': 0,
                'games': []
            }
            series_list.append(current_series)

        # Add any remaining follow streak games to the last series
        if in_follow_streak and current_follow_games and series_list:
            series_list[-1]['follow_streak'] = {
                'count': len(current_follow_games),
                'games': current_follow_games
            }

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
