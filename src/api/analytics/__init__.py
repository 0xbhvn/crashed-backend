"""
Analytics package for Crash Monitor.

This package contains all the analytical functions for processing game data.
"""

# Import all analytics functions to expose them at the package level
from .last_games import (
    get_last_game_min_crash_point,
    get_last_game_max_crash_point,
    get_last_game_exact_floor,
    get_last_min_crash_point_games,
    get_last_max_crash_point_games,
    get_last_exact_floor_games,
    get_last_games_min_crash_points,
    get_last_games_max_crash_points,
    get_last_games_exact_floors
)

from .occurrences import (
    get_min_crash_point_occurrences_by_games,
    get_min_crash_point_occurrences_by_time,
    get_exact_floor_occurrences_by_games,
    get_exact_floor_occurrences_by_time,
    get_min_crash_point_occurrences_by_games_batch,
    get_min_crash_point_occurrences_by_time_batch,
    get_exact_floor_occurrences_by_games_batch,
    get_exact_floor_occurrences_by_time_batch,
    get_max_crash_point_occurrences_by_games,
    get_max_crash_point_occurrences_by_time,
    get_max_crash_point_occurrences_by_games_batch,
    get_max_crash_point_occurrences_by_time_batch
)

from .series import (
    get_series_without_min_crash_point_by_games,
    get_series_without_min_crash_point_by_time
)

from .intervals import (
    get_min_crash_point_intervals_by_time,
    get_min_crash_point_intervals_by_game_sets,
    get_min_crash_point_intervals_by_time_batch,
    get_min_crash_point_intervals_by_game_sets_batch,
    get_min_crash_point_intervals_by_date_range,
    get_min_crash_point_intervals_by_date_range_batch
)

from .statistical_models import (
    calculate_risk_adjusted_metrics,
    detect_patterns_and_anomalies,
    calculate_expected_values,
    calculate_market_psychology_indicators,
    get_combined_statistical_analysis
)

# Export all imported functions
__all__ = [
    # Last games analytics
    'get_last_game_min_crash_point',
    'get_last_game_max_crash_point',
    'get_last_game_exact_floor',
    'get_last_min_crash_point_games',
    'get_last_max_crash_point_games',
    'get_last_exact_floor_games',
    'get_last_games_min_crash_points',
    'get_last_games_max_crash_points',
    'get_last_games_exact_floors',

    # Occurrences analytics
    'get_min_crash_point_occurrences_by_games',
    'get_min_crash_point_occurrences_by_time',
    'get_exact_floor_occurrences_by_games',
    'get_exact_floor_occurrences_by_time',
    'get_min_crash_point_occurrences_by_games_batch',
    'get_min_crash_point_occurrences_by_time_batch',
    'get_exact_floor_occurrences_by_games_batch',
    'get_exact_floor_occurrences_by_time_batch',
    'get_max_crash_point_occurrences_by_games',
    'get_max_crash_point_occurrences_by_time',
    'get_max_crash_point_occurrences_by_games_batch',
    'get_max_crash_point_occurrences_by_time_batch',

    # Series analytics
    'get_series_without_min_crash_point_by_games',
    'get_series_without_min_crash_point_by_time',

    # Intervals analytics
    'get_min_crash_point_intervals_by_time',
    'get_min_crash_point_intervals_by_game_sets',
    'get_min_crash_point_intervals_by_time_batch',
    'get_min_crash_point_intervals_by_game_sets_batch',
    'get_min_crash_point_intervals_by_date_range',
    'get_min_crash_point_intervals_by_date_range_batch',

    # Statistical models analytics
    'calculate_risk_adjusted_metrics',
    'detect_patterns_and_anomalies',
    'calculate_expected_values',
    'calculate_market_psychology_indicators',
    'get_combined_statistical_analysis'
]
