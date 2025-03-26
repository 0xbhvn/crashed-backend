"""
Occurrences analytics functions.

This module contains functions for analyzing the frequency of games
meeting various crash point criteria.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, select

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


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
        - first_game_time: First game in the analyzed set
        - last_game_time: Last game in the analyzed set
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "first_game_time": None,
                "last_game_time": None
            }

        # Count games with crash point >= min_value
        matching_games = sum(
            1 for game in games if game.crashPoint >= min_value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        # Get the first and last game times (reverse chronological order)
        first_game_time = games[-1].endTime
        last_game_time = games[0].endTime

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "first_game_time": first_game_time,
            "last_game_time": last_game_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing min crash point occurrences by games: {str(e)}")
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
        # Calculate the time threshold
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get games in the time range
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "start_time": start_time,
                "end_time": end_time
            }

        # Count games with crash point >= value
        matching_games = sum(1 for game in games if game.crashPoint >= value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "start_time": start_time,
            "end_time": end_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing min crash point occurrences by time: {str(e)}")
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
        Dictionary containing occurrences data
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "first_game_time": None,
                "last_game_time": None
            }

        # Count games with floor(crashPoint) == floor_value
        matching_games = sum(1 for game in games if int(
            game.crashPoint) == floor_value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        # Get the first and last game times (reverse chronological order)
        first_game_time = games[-1].endTime
        last_game_time = games[0].endTime

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "first_game_time": first_game_time,
            "last_game_time": last_game_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing exact floor occurrences by games: {str(e)}")
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
        # Calculate the time threshold
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get games in the time range
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "start_time": start_time,
                "end_time": end_time
            }

        # Count games with floor(crashPoint) == value
        matching_games = sum(
            1 for game in games if int(game.crashPoint) == value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "start_time": start_time,
            "end_time": end_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing exact floor occurrences by time: {str(e)}")
        raise


def get_max_crash_point_occurrences_by_games(
    session: Session,
    max_value: float,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get the total occurrences of crash points <= specified value in the last N games.

    Args:
        session: SQLAlchemy session
        max_value: Maximum crash point value to count
        limit: Number of most recent games to analyze (default: 100)

    Returns:
        Dictionary containing occurrences data
    """
    try:
        # Get the most recent 'limit' games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "first_game_time": None,
                "last_game_time": None
            }

        # Count games with crashPoint <= max_value
        matching_games = sum(
            1 for game in games if game.crashPoint <= max_value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        # Get the first and last game times (reverse chronological order)
        first_game_time = games[-1].endTime
        last_game_time = games[0].endTime

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "first_game_time": first_game_time,
            "last_game_time": last_game_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing max crash point occurrences by games: {str(e)}")
        raise


def get_max_crash_point_occurrences_by_time(
    session: Session,
    max_value: float,
    hours: int = 1
) -> Dict[str, Any]:
    """
    Get the total occurrences of crash points <= specified value in the last N hours.

    Args:
        session: SQLAlchemy session
        max_value: Maximum crash point value to count
        hours: Number of hours to look back (default: 1)

    Returns:
        Dictionary with count, total games, percentage, and time range
    """
    try:
        # Calculate the time threshold
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get games in the time range
        games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # No games found
        if not games:
            return {
                "count": 0,
                "total_games": 0,
                "percentage": 0,
                "start_time": start_time,
                "end_time": end_time
            }

        # Count games with crash point <= max_value
        matching_games = sum(
            1 for game in games if game.crashPoint <= max_value)

        # Calculate the percentage
        percentage = (matching_games / len(games)) * 100 if games else 0

        return {
            "count": matching_games,
            "total_games": len(games),
            "percentage": percentage,
            "start_time": start_time,
            "end_time": end_time
        }

    except Exception as e:
        logger.error(
            f"Error analyzing max crash point occurrences by time: {str(e)}")
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
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Get games for current period
        current_games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison and current_games:
            oldest_current_game_time = current_games[-1].endTime

            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime < oldest_current_game_time)\
                .order_by(desc(CrashGame.endTime))\
                .limit(limit)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if game.crashPoint >= value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "first_game_time": current_games[-1].endTime if current_games else None,
                "last_game_time": current_games[0].endTime if current_games else None
            }

            # Add comparison data if requested
            if comparison and previous_games:
                previous_count = sum(
                    1 for game in previous_games if game.crashPoint >= value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "first_game_time": previous_games[-1].endTime if previous_games else None,
                    "last_game_time": previous_games[0].endTime if previous_games else None,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing min crash point occurrences by games batch: {str(e)}")
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
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Calculate time ranges
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Previous period
        previous_end_time = start_time
        previous_start_time = previous_end_time - timedelta(hours=hours)

        # Get games for current period
        current_games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.endTime <= end_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison:
            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime >= previous_start_time)\
                .filter(CrashGame.endTime < start_time)\
                .order_by(CrashGame.endTime)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if game.crashPoint >= value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "start_time": start_time,
                "end_time": end_time
            }

            # Add comparison data if requested
            if comparison:
                previous_count = sum(
                    1 for game in previous_games if game.crashPoint >= value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "start_time": previous_start_time,
                    "end_time": previous_end_time,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing min crash point occurrences by time batch: {str(e)}")
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
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Get games for current period
        current_games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison and current_games:
            oldest_current_game_time = current_games[-1].endTime

            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime < oldest_current_game_time)\
                .order_by(desc(CrashGame.endTime))\
                .limit(limit)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if int(game.crashPoint) == value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "first_game_time": current_games[-1].endTime if current_games else None,
                "last_game_time": current_games[0].endTime if current_games else None
            }

            # Add comparison data if requested
            if comparison and previous_games:
                previous_count = sum(
                    1 for game in previous_games if int(game.crashPoint) == value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "first_game_time": previous_games[-1].endTime if previous_games else None,
                    "last_game_time": previous_games[0].endTime if previous_games else None,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing exact floor occurrences by games batch: {str(e)}")
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
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Calculate time ranges
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Previous period
        previous_end_time = start_time
        previous_start_time = previous_end_time - timedelta(hours=hours)

        # Get games for current period
        current_games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.endTime <= end_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison:
            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime >= previous_start_time)\
                .filter(CrashGame.endTime < start_time)\
                .order_by(CrashGame.endTime)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if int(game.crashPoint) == value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "start_time": start_time,
                "end_time": end_time
            }

            # Add comparison data if requested
            if comparison:
                previous_count = sum(
                    1 for game in previous_games if int(game.crashPoint) == value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "start_time": previous_start_time,
                    "end_time": previous_end_time,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing exact floor occurrences by time batch: {str(e)}")
        raise


def get_max_crash_point_occurrences_by_games_batch(
    session: Session,
    values: List[float],
    limit: int = 100,
    comparison: bool = True
) -> Dict[float, Dict[str, Any]]:
    """
    Get the total occurrences of crash points <= specified values in the last N games,
    and compare with the previous N games.

    Args:
        session: SQLAlchemy session
        values: List of maximum crash point values to count
        limit: Number of most recent games to analyze (default: 100)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Get games for current period
        current_games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison and current_games:
            oldest_current_game_time = current_games[-1].endTime

            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime < oldest_current_game_time)\
                .order_by(desc(CrashGame.endTime))\
                .limit(limit)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if game.crashPoint <= value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "first_game_time": current_games[-1].endTime if current_games else None,
                "last_game_time": current_games[0].endTime if current_games else None
            }

            # Add comparison data if requested
            if comparison and previous_games:
                previous_count = sum(
                    1 for game in previous_games if game.crashPoint <= value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "first_game_time": previous_games[-1].endTime if previous_games else None,
                    "last_game_time": previous_games[0].endTime if previous_games else None,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing max crash point occurrences by games batch: {str(e)}")
        raise


def get_max_crash_point_occurrences_by_time_batch(
    session: Session,
    values: List[float],
    hours: int = 1,
    comparison: bool = True
) -> Dict[float, Dict[str, Any]]:
    """
    Get the total occurrences of crash points <= specified values in the last N hours,
    and compare with the previous N hours.

    Args:
        session: SQLAlchemy session
        values: List of maximum crash point values to count
        hours: Number of hours to look back (default: 1)
        comparison: Whether to include comparison with previous period (default: True)

    Returns:
        Dictionary mapping each value to its occurrence statistics
    """
    try:
        # Calculate time ranges
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Previous period
        previous_end_time = start_time
        previous_start_time = previous_end_time - timedelta(hours=hours)

        # Get games for current period
        current_games = session.query(CrashGame)\
            .filter(CrashGame.endTime >= start_time)\
            .filter(CrashGame.endTime <= end_time)\
            .order_by(CrashGame.endTime)\
            .all()

        # Get games for previous period if comparison is needed
        previous_games = []
        if comparison:
            previous_games = session.query(CrashGame)\
                .filter(CrashGame.endTime >= previous_start_time)\
                .filter(CrashGame.endTime < start_time)\
                .order_by(CrashGame.endTime)\
                .all()

        result = {}

        # Process each value
        for value in values:
            current_count = sum(
                1 for game in current_games if game.crashPoint <= value)
            current_percentage = (
                current_count / len(current_games)) * 100 if current_games else 0

            current_data = {
                "count": current_count,
                "total_games": len(current_games),
                "percentage": current_percentage,
                "start_time": start_time,
                "end_time": end_time
            }

            # Add comparison data if requested
            if comparison:
                previous_count = sum(
                    1 for game in previous_games if game.crashPoint <= value)
                previous_percentage = (
                    previous_count / len(previous_games)) * 100 if previous_games else 0

                # Calculate change
                count_change = current_count - previous_count
                percentage_change = current_percentage - previous_percentage

                current_data["comparison"] = {
                    "count": previous_count,
                    "total_games": len(previous_games),
                    "percentage": previous_percentage,
                    "start_time": previous_start_time,
                    "end_time": previous_end_time,
                    "count_change": count_change,
                    "percentage_change": percentage_change
                }

            result[value] = current_data

        return result

    except Exception as e:
        logger.error(
            f"Error analyzing max crash point occurrences by time batch: {str(e)}")
        raise
