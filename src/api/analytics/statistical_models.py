"""
Statistical models analytics functions.

This module contains functions for advanced statistical analysis including:
- Moving averages (5, 10, 20 game windows)
- Volatility indicators (standard deviation, variance)
- Probability distribution analysis for different crash point ranges
- Streak analysis (hot/cold streaks detection)
"""

import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from collections import deque
import math

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)


def calculate_moving_averages(
    session: Session,
    window_sizes: List[int] = [5, 10, 20],
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Calculate moving averages for crash points over specified window sizes.
    
    Args:
        session: SQLAlchemy session
        window_sizes: List of window sizes for moving averages (default: [5, 10, 20])
        limit: Number of most recent games to analyze (default: 1000)
    
    Returns:
        Dictionary containing moving averages for each window size
    """
    try:
        # Get the most recent games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()
        
        if not games:
            return {"error": "No games found"}
        
        # Reverse to get chronological order
        games.reverse()
        
        result = {
            "total_games": len(games),
            "latest_game_time": games[-1].endTime.isoformat() if games[-1].endTime else None,
            "moving_averages": {}
        }
        
        for window_size in window_sizes:
            if len(games) < window_size:
                result["moving_averages"][f"ma_{window_size}"] = {
                    "error": f"Not enough games for window size {window_size}"
                }
                continue
            
            moving_averages = []
            crash_points = [game.crashPoint for game in games]
            
            # Calculate moving averages
            for i in range(window_size - 1, len(crash_points)):
                window = crash_points[i - window_size + 1:i + 1]
                ma_value = sum(window) / window_size
                moving_averages.append({
                    "game_index": i,
                    "game_id": games[i].gameId,
                    "crash_point": games[i].crashPoint,
                    "moving_average": ma_value,
                    "time": games[i].endTime.isoformat() if games[i].endTime else None
                })
            
            # Calculate overall statistics for this window
            ma_values = [ma["moving_average"] for ma in moving_averages]
            result["moving_averages"][f"ma_{window_size}"] = {
                "window_size": window_size,
                "data_points": len(moving_averages),
                "current_ma": ma_values[-1] if ma_values else None,
                "average_ma": statistics.mean(ma_values) if ma_values else None,
                "min_ma": min(ma_values) if ma_values else None,
                "max_ma": max(ma_values) if ma_values else None,
                "std_dev_ma": statistics.stdev(ma_values) if len(ma_values) > 1 else None,
                "recent_data": moving_averages[-10:] if len(moving_averages) >= 10 else moving_averages
            }
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating moving averages: {str(e)}")
        raise


def calculate_volatility_indicators(
    session: Session,
    window_sizes: List[int] = [10, 20, 50],
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Calculate volatility indicators including standard deviation and variance.
    
    Args:
        session: SQLAlchemy session
        window_sizes: List of window sizes for volatility calculation (default: [10, 20, 50])
        limit: Number of most recent games to analyze (default: 1000)
    
    Returns:
        Dictionary containing volatility indicators for each window size
    """
    try:
        # Get the most recent games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()
        
        if not games:
            return {"error": "No games found"}
        
        # Reverse to get chronological order
        games.reverse()
        crash_points = [game.crashPoint for game in games]
        
        result = {
            "total_games": len(games),
            "latest_game_time": games[-1].endTime.isoformat() if games[-1].endTime else None,
            "overall_statistics": {
                "mean": statistics.mean(crash_points),
                "std_dev": statistics.stdev(crash_points) if len(crash_points) > 1 else None,
                "variance": statistics.variance(crash_points) if len(crash_points) > 1 else None,
                "min": min(crash_points),
                "max": max(crash_points),
                "median": statistics.median(crash_points)
            },
            "rolling_volatility": {}
        }
        
        for window_size in window_sizes:
            if len(games) < window_size:
                result["rolling_volatility"][f"window_{window_size}"] = {
                    "error": f"Not enough games for window size {window_size}"
                }
                continue
            
            rolling_data = []
            
            # Calculate rolling volatility
            for i in range(window_size - 1, len(crash_points)):
                window = crash_points[i - window_size + 1:i + 1]
                
                window_mean = statistics.mean(window)
                window_std = statistics.stdev(window) if len(window) > 1 else 0
                window_var = statistics.variance(window) if len(window) > 1 else 0
                
                # Calculate coefficient of variation (relative volatility)
                cv = (window_std / window_mean) * 100 if window_mean != 0 else 0
                
                rolling_data.append({
                    "game_index": i,
                    "game_id": games[i].gameId,
                    "crash_point": games[i].crashPoint,
                    "window_mean": window_mean,
                    "window_std_dev": window_std,
                    "window_variance": window_var,
                    "coefficient_of_variation": cv,
                    "time": games[i].endTime.isoformat() if games[i].endTime else None
                })
            
            # Calculate statistics for the rolling volatility
            std_devs = [data["window_std_dev"] for data in rolling_data]
            variances = [data["window_variance"] for data in rolling_data]
            cvs = [data["coefficient_of_variation"] for data in rolling_data]
            
            result["rolling_volatility"][f"window_{window_size}"] = {
                "window_size": window_size,
                "data_points": len(rolling_data),
                "current_std_dev": std_devs[-1] if std_devs else None,
                "current_variance": variances[-1] if variances else None,
                "current_cv": cvs[-1] if cvs else None,
                "avg_std_dev": statistics.mean(std_devs) if std_devs else None,
                "avg_variance": statistics.mean(variances) if variances else None,
                "avg_cv": statistics.mean(cvs) if cvs else None,
                "volatility_trend": "high" if (cvs[-1] if cvs else 0) > (statistics.mean(cvs) if cvs else 0) else "low",
                "recent_data": rolling_data[-10:] if len(rolling_data) >= 10 else rolling_data
            }
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating volatility indicators: {str(e)}")
        raise


def analyze_probability_distribution(
    session: Session,
    crash_point_ranges: List[Tuple[float, float]] = None,
    limit: int = 10000
) -> Dict[str, Any]:
    """
    Analyze probability distribution for different crash point ranges.
    
    Args:
        session: SQLAlchemy session
        crash_point_ranges: List of tuples defining ranges (min, max). If None, uses default ranges.
        limit: Number of most recent games to analyze (default: 10000)
    
    Returns:
        Dictionary containing probability distribution analysis
    """
    try:
        if crash_point_ranges is None:
            crash_point_ranges = [
                (1.0, 1.5),   # Very low
                (1.5, 2.0),   # Low
                (2.0, 3.0),   # Medium-low
                (3.0, 5.0),   # Medium
                (5.0, 10.0),  # High
                (10.0, 20.0), # Very high
                (20.0, 50.0), # Extremely high
                (50.0, float('inf'))  # Moon
            ]
        
        # Get the most recent games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()
        
        if not games:
            return {"error": "No games found"}
        
        crash_points = [game.crashPoint for game in games]
        total_games = len(crash_points)
        
        result = {
            "total_games": total_games,
            "analysis_period": {
                "start_time": games[-1].endTime.isoformat() if games[-1].endTime else None,
                "end_time": games[0].endTime.isoformat() if games[0].endTime else None
            },
            "overall_statistics": {
                "mean": statistics.mean(crash_points),
                "median": statistics.median(crash_points),
                "mode": statistics.mode(crash_points) if len(set(crash_points)) < len(crash_points) else None,
                "std_dev": statistics.stdev(crash_points) if len(crash_points) > 1 else None,
                "variance": statistics.variance(crash_points) if len(crash_points) > 1 else None,
                "skewness": calculate_skewness(crash_points),
                "kurtosis": calculate_kurtosis(crash_points)
            },
            "range_distribution": {},
            "percentiles": {
                "p10": calculate_percentile(crash_points, 10),
                "p25": calculate_percentile(crash_points, 25),
                "p50": calculate_percentile(crash_points, 50),
                "p75": calculate_percentile(crash_points, 75),
                "p90": calculate_percentile(crash_points, 90),
                "p95": calculate_percentile(crash_points, 95),
                "p99": calculate_percentile(crash_points, 99)
            }
        }
        
        # Analyze each range
        for min_val, max_val in crash_point_ranges:
            range_name = f"{min_val}-{max_val if max_val != float('inf') else 'inf'}"
            
            if max_val == float('inf'):
                count = sum(1 for cp in crash_points if cp >= min_val)
            else:
                count = sum(1 for cp in crash_points if min_val <= cp < max_val)
            
            probability = (count / total_games) * 100
            
            # Calculate expected frequency based on theoretical probability
            theoretical_prob = calculate_theoretical_probability(min_val, max_val)
            expected_count = theoretical_prob * total_games / 100
            
            # Chi-square goodness of fit component
            chi_square_component = ((count - expected_count) ** 2) / expected_count if expected_count > 0 else 0
            
            result["range_distribution"][range_name] = {
                "min_value": min_val,
                "max_value": "∞" if max_val == float('inf') else max_val,
                "count": count,
                "probability_percent": probability,
                "theoretical_probability_percent": theoretical_prob,
                "expected_count": expected_count,
                "deviation_from_expected": count - expected_count,
                "chi_square_component": chi_square_component
            }
        
        return result
    
    except Exception as e:
        logger.error(f"Error analyzing probability distribution: {str(e)}")
        raise


def detect_streaks(
    session: Session,
    threshold_high: float = 5.0,
    threshold_low: float = 2.0,
    min_streak_length: int = 3,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Detect hot and cold streaks in crash game data.
    
    Args:
        session: SQLAlchemy session
        threshold_high: Threshold for hot streaks (default: 5.0)
        threshold_low: Threshold for cold streaks (default: 2.0)
        min_streak_length: Minimum length to consider a streak (default: 3)
        limit: Number of most recent games to analyze (default: 1000)
    
    Returns:
        Dictionary containing streak analysis
    """
    try:
        # Get the most recent games
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(limit)\
            .all()
        
        if not games:
            return {"error": "No games found"}
        
        # Reverse to get chronological order
        games.reverse()
        
        hot_streaks = []
        cold_streaks = []
        current_hot_streak = None
        current_cold_streak = None
        
        for i, game in enumerate(games):
            crash_point = game.crashPoint
            
            # Hot streak detection (crash points >= threshold_high)
            if crash_point >= threshold_high:
                if current_hot_streak is None:
                    current_hot_streak = {
                        "start_index": i,
                        "start_game_id": game.gameId,
                        "start_time": game.endTime.isoformat() if game.endTime else None,
                        "games": [game.gameId],
                        "crash_points": [crash_point]
                    }
                else:
                    current_hot_streak["games"].append(game.gameId)
                    current_hot_streak["crash_points"].append(crash_point)
                
                # End any current cold streak
                if current_cold_streak is not None and len(current_cold_streak["games"]) >= min_streak_length:
                    current_cold_streak["end_index"] = i - 1
                    current_cold_streak["end_game_id"] = games[i - 1].gameId
                    current_cold_streak["end_time"] = games[i - 1].endTime.isoformat() if games[i - 1].endTime else None
                    current_cold_streak["length"] = len(current_cold_streak["games"])
                    current_cold_streak["average_crash_point"] = statistics.mean(current_cold_streak["crash_points"])
                    cold_streaks.append(current_cold_streak)
                current_cold_streak = None
            
            # Cold streak detection (crash points <= threshold_low)
            elif crash_point <= threshold_low:
                if current_cold_streak is None:
                    current_cold_streak = {
                        "start_index": i,
                        "start_game_id": game.gameId,
                        "start_time": game.endTime.isoformat() if game.endTime else None,
                        "games": [game.gameId],
                        "crash_points": [crash_point]
                    }
                else:
                    current_cold_streak["games"].append(game.gameId)
                    current_cold_streak["crash_points"].append(crash_point)
                
                # End any current hot streak
                if current_hot_streak is not None and len(current_hot_streak["games"]) >= min_streak_length:
                    current_hot_streak["end_index"] = i - 1
                    current_hot_streak["end_game_id"] = games[i - 1].gameId
                    current_hot_streak["end_time"] = games[i - 1].endTime.isoformat() if games[i - 1].endTime else None
                    current_hot_streak["length"] = len(current_hot_streak["games"])
                    current_hot_streak["average_crash_point"] = statistics.mean(current_hot_streak["crash_points"])
                    hot_streaks.append(current_hot_streak)
                current_hot_streak = None
            
            # Neither hot nor cold - end both streaks if they exist
            else:
                if current_hot_streak is not None and len(current_hot_streak["games"]) >= min_streak_length:
                    current_hot_streak["end_index"] = i - 1
                    current_hot_streak["end_game_id"] = games[i - 1].gameId
                    current_hot_streak["end_time"] = games[i - 1].endTime.isoformat() if games[i - 1].endTime else None
                    current_hot_streak["length"] = len(current_hot_streak["games"])
                    current_hot_streak["average_crash_point"] = statistics.mean(current_hot_streak["crash_points"])
                    hot_streaks.append(current_hot_streak)
                current_hot_streak = None
                
                if current_cold_streak is not None and len(current_cold_streak["games"]) >= min_streak_length:
                    current_cold_streak["end_index"] = i - 1
                    current_cold_streak["end_game_id"] = games[i - 1].gameId
                    current_cold_streak["end_time"] = games[i - 1].endTime.isoformat() if games[i - 1].endTime else None
                    current_cold_streak["length"] = len(current_cold_streak["games"])
                    current_cold_streak["average_crash_point"] = statistics.mean(current_cold_streak["crash_points"])
                    cold_streaks.append(current_cold_streak)
                current_cold_streak = None
        
        # Handle ongoing streaks at the end
        if current_hot_streak is not None and len(current_hot_streak["games"]) >= min_streak_length:
            current_hot_streak["end_index"] = len(games) - 1
            current_hot_streak["end_game_id"] = games[-1].gameId
            current_hot_streak["end_time"] = games[-1].endTime.isoformat() if games[-1].endTime else None
            current_hot_streak["length"] = len(current_hot_streak["games"])
            current_hot_streak["average_crash_point"] = statistics.mean(current_hot_streak["crash_points"])
            current_hot_streak["is_ongoing"] = True
            hot_streaks.append(current_hot_streak)
        
        if current_cold_streak is not None and len(current_cold_streak["games"]) >= min_streak_length:
            current_cold_streak["end_index"] = len(games) - 1
            current_cold_streak["end_game_id"] = games[-1].gameId
            current_cold_streak["end_time"] = games[-1].endTime.isoformat() if games[-1].endTime else None
            current_cold_streak["length"] = len(current_cold_streak["games"])
            current_cold_streak["average_crash_point"] = statistics.mean(current_cold_streak["crash_points"])
            current_cold_streak["is_ongoing"] = True
            cold_streaks.append(current_cold_streak)
        
        # Calculate statistics
        hot_streak_lengths = [streak["length"] for streak in hot_streaks]
        cold_streak_lengths = [streak["length"] for streak in cold_streaks]
        
        result = {
            "analysis_parameters": {
                "threshold_high": threshold_high,
                "threshold_low": threshold_low,
                "min_streak_length": min_streak_length,
                "total_games_analyzed": len(games)
            },
            "hot_streaks": {
                "count": len(hot_streaks),
                "streaks": hot_streaks,
                "statistics": {
                    "average_length": statistics.mean(hot_streak_lengths) if hot_streak_lengths else 0,
                    "longest_streak": max(hot_streak_lengths) if hot_streak_lengths else 0,
                    "shortest_streak": min(hot_streak_lengths) if hot_streak_lengths else 0,
                    "total_games_in_hot_streaks": sum(hot_streak_lengths)
                }
            },
            "cold_streaks": {
                "count": len(cold_streaks),
                "streaks": cold_streaks,
                "statistics": {
                    "average_length": statistics.mean(cold_streak_lengths) if cold_streak_lengths else 0,
                    "longest_streak": max(cold_streak_lengths) if cold_streak_lengths else 0,
                    "shortest_streak": min(cold_streak_lengths) if cold_streak_lengths else 0,
                    "total_games_in_cold_streaks": sum(cold_streak_lengths)
                }
            },
            "current_state": {
                "is_hot_streak": current_hot_streak is not None,
                "is_cold_streak": current_cold_streak is not None,
                "last_game_crash_point": games[-1].crashPoint if games else None
            }
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error detecting streaks: {str(e)}")
        raise


# Helper functions

def calculate_skewness(data: List[float]) -> Optional[float]:
    """Calculate skewness of the data."""
    try:
        if len(data) < 3:
            return None
        
        mean = statistics.mean(data)
        std_dev = statistics.stdev(data)
        
        if std_dev == 0:
            return None
        
        n = len(data)
        skewness = (n / ((n - 1) * (n - 2))) * sum(((x - mean) / std_dev) ** 3 for x in data)
        return skewness
    except:
        return None


def calculate_kurtosis(data: List[float]) -> Optional[float]:
    """Calculate kurtosis of the data."""
    try:
        if len(data) < 4:
            return None
        
        mean = statistics.mean(data)
        std_dev = statistics.stdev(data)
        
        if std_dev == 0:
            return None
        
        n = len(data)
        kurtosis = (n * (n + 1) / ((n - 1) * (n - 2) * (n - 3))) * sum(((x - mean) / std_dev) ** 4 for x in data) - (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))
        return kurtosis
    except:
        return None


def calculate_percentile(data: List[float], percentile: float) -> float:
    """Calculate percentile of the data."""
    try:
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = math.floor(k)
        c = math.ceil(k)
        
        if f == c:
            return sorted_data[int(k)]
        
        d0 = sorted_data[int(f)] * (c - k)
        d1 = sorted_data[int(c)] * (k - f)
        return d0 + d1
    except:
        return 0.0


def calculate_theoretical_probability(min_val: float, max_val: float) -> float:
    """
    Calculate theoretical probability for crash game based on house edge.
    This is a simplified model - adjust based on actual game mechanics.
    """
    try:
        if max_val == float('inf'):
            # For ranges like 50+, use exponential decay
            return max(0.1, 100 / (min_val ** 1.5))
        else:
            # For finite ranges, use inverse relationship
            avg_val = (min_val + max_val) / 2
            return max(0.1, 100 / avg_val)
    except:
        return 1.0


def get_combined_statistical_analysis(
    session: Session,
    ma_windows: List[int] = [5, 10, 20],
    volatility_windows: List[int] = [10, 20, 50],
    streak_thresholds: Tuple[float, float] = (5.0, 2.0),
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Get combined statistical analysis including all statistical models.
    
    Args:
        session: SQLAlchemy session
        ma_windows: Moving average window sizes
        volatility_windows: Volatility calculation window sizes
        streak_thresholds: Tuple of (hot_threshold, cold_threshold)
        limit: Number of most recent games to analyze
    
    Returns:
        Dictionary containing all statistical analyses
    """
    try:
        result = {
            "analysis_timestamp": datetime.now(timezone.utc),
            "parameters": {
                "games_analyzed": limit,
                "ma_windows": ma_windows,
                "volatility_windows": volatility_windows,
                "streak_thresholds": streak_thresholds
            }
        }
        
        # Get moving averages
        result["moving_averages"] = calculate_moving_averages(session, ma_windows, limit)
        
        # Get volatility indicators
        result["volatility_indicators"] = calculate_volatility_indicators(session, volatility_windows, limit)
        
        # Get probability distribution
        result["probability_distribution"] = analyze_probability_distribution(session, limit=limit)
        
        # Get streak analysis
        result["streak_analysis"] = detect_streaks(
            session, 
            threshold_high=streak_thresholds[0],
            threshold_low=streak_thresholds[1],
            limit=limit
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error in combined statistical analysis: {str(e)}")
        raise