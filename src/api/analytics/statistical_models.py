"""
Enhanced statistical models analytics for BC.game crash game analysis.

This module provides advanced statistical analysis specifically designed for crash game mechanics:
- Risk-adjusted performance metrics (Sharpe ratio, drawdown analysis, VaR)
- Pattern recognition and anomaly detection
- Expected value calculations for different strategies
- Market psychology indicators
"""

import logging
import statistics
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from collections import deque
import math
from scipy import stats
from scipy.signal import find_peaks

from ...db.models import CrashGame

# Configure logging
logger = logging.getLogger(__name__)

# Constants for BC.game crash mechanics
HOUSE_EDGE = 0.03  # 3% house edge
BASE_PROBABILITY = 0.97  # Base probability before house edge


def calculate_risk_adjusted_metrics(
    session: Session,
    target_multipliers: List[float] = [2.0, 3.0, 5.0, 10.0],
    limit: int = 1000,
    risk_free_rate: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate risk-adjusted performance metrics for different betting strategies.
    
    Args:
        session: SQLAlchemy session
        target_multipliers: List of target cash-out multipliers to analyze
        limit: Number of most recent games to analyze
        risk_free_rate: Risk-free rate for Sharpe ratio calculation (default: 0)
    
    Returns:
        Dictionary containing risk-adjusted metrics for each strategy
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
            "analysis_period": {
                "start": games[0].endTime.isoformat() if games[0].endTime else None,
                "end": games[-1].endTime.isoformat() if games[-1].endTime else None
            },
            "strategies": {}
        }
        
        for target in target_multipliers:
            # Simulate returns for this strategy
            returns = []
            cumulative_balance = 1000  # Starting balance
            balance_history = [cumulative_balance]
            peak_balance = cumulative_balance
            max_drawdown = 0
            drawdown_periods = []
            current_drawdown_start = None
            
            for i, crash_point in enumerate(crash_points):
                if crash_point >= target:
                    # Win - cash out at target
                    profit = target - 1
                    returns.append(profit)
                    cumulative_balance *= (1 + profit)
                else:
                    # Loss - lose entire bet
                    returns.append(-1)
                    cumulative_balance *= 0
                    cumulative_balance = balance_history[-1] * 0.9  # Assume 10% bet size
                
                balance_history.append(cumulative_balance)
                
                # Track drawdowns
                if cumulative_balance > peak_balance:
                    peak_balance = cumulative_balance
                    if current_drawdown_start is not None:
                        drawdown_periods.append({
                            "start": current_drawdown_start,
                            "end": i,
                            "duration": i - current_drawdown_start,
                            "depth": max_drawdown
                        })
                        current_drawdown_start = None
                        max_drawdown = 0
                else:
                    drawdown = (peak_balance - cumulative_balance) / peak_balance
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
                    if current_drawdown_start is None:
                        current_drawdown_start = i
            
            # Calculate metrics
            if returns:
                avg_return = statistics.mean(returns)
                std_return = statistics.stdev(returns) if len(returns) > 1 else 0
                
                # Sharpe ratio
                sharpe_ratio = (avg_return - risk_free_rate) / std_return if std_return > 0 else 0
                
                # Sortino ratio (only downside volatility)
                negative_returns = [r for r in returns if r < 0]
                downside_std = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 0
                sortino_ratio = (avg_return - risk_free_rate) / downside_std if downside_std > 0 else 0
                
                # Win rate and profit factor
                wins = sum(1 for r in returns if r > 0)
                win_rate = wins / len(returns) * 100
                
                total_wins = sum(r for r in returns if r > 0)
                total_losses = abs(sum(r for r in returns if r < 0))
                profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
                
                # Value at Risk (VaR) - 95% confidence
                var_95 = float(np.percentile(returns, 5))
                
                # Conditional Value at Risk (CVaR)
                returns_below_var = [r for r in returns if r <= var_95]
                cvar_95 = float(statistics.mean(returns_below_var)) if returns_below_var else var_95
                
                # Maximum consecutive losses
                max_consecutive_losses = 0
                current_losses = 0
                for r in returns:
                    if r < 0:
                        current_losses += 1
                        max_consecutive_losses = max(max_consecutive_losses, current_losses)
                    else:
                        current_losses = 0
                
                result["strategies"][f"{target}x"] = {
                    "target_multiplier": target,
                    "performance": {
                        "total_bets": len(returns),
                        "wins": wins,
                        "win_rate": win_rate,
                        "average_return": avg_return,
                        "total_return": sum(returns),
                        "final_balance": balance_history[-1],
                        "roi": (balance_history[-1] - 1000) / 1000 * 100
                    },
                    "risk_metrics": {
                        "sharpe_ratio": sharpe_ratio,
                        "sortino_ratio": sortino_ratio,
                        "standard_deviation": std_return,
                        "downside_deviation": downside_std,
                        "value_at_risk_95": var_95,
                        "conditional_var_95": cvar_95,
                        "profit_factor": profit_factor,
                        "max_consecutive_losses": max_consecutive_losses
                    },
                    "drawdown_analysis": {
                        "max_drawdown_percent": max([d["depth"] for d in drawdown_periods]) * 100 if drawdown_periods else 0,
                        "drawdown_periods": len(drawdown_periods),
                        "avg_drawdown_duration": statistics.mean([d["duration"] for d in drawdown_periods]) if drawdown_periods else 0,
                        "longest_drawdown": max([d["duration"] for d in drawdown_periods]) if drawdown_periods else 0
                    }
                }
        
        # Add comparison metrics
        result["optimal_strategy"] = _find_optimal_strategy(result["strategies"])
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating risk-adjusted metrics: {str(e)}")
        raise


def detect_patterns_and_anomalies(
    session: Session,
    limit: int = 1000,
    anomaly_threshold: float = 3.0
) -> Dict[str, Any]:
    """
    Detect patterns and anomalies in crash game data using statistical methods.
    
    Args:
        session: SQLAlchemy session
        limit: Number of most recent games to analyze
        anomaly_threshold: Z-score threshold for anomaly detection
    
    Returns:
        Dictionary containing pattern and anomaly analysis
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
        
        # Calculate entropy
        entropy = _calculate_entropy(crash_points)
        
        # Autocorrelation analysis
        autocorr_results = _calculate_autocorrelation(crash_points, max_lag=20)
        
        # Anomaly detection using multiple methods
        anomalies = _detect_anomalies(crash_points, games, anomaly_threshold)
        
        # Pattern detection
        patterns = _detect_patterns(crash_points, games)
        
        # Clustering analysis
        clusters = _perform_clustering(crash_points)
        
        result = {
            "total_games": len(games),
            "analysis_period": {
                "start": games[0].endTime.isoformat() if games[0].endTime else None,
                "end": games[-1].endTime.isoformat() if games[-1].endTime else None
            },
            "randomness_metrics": {
                "entropy": entropy,
                "entropy_ratio": entropy / math.log2(len(set(crash_points))) if len(set(crash_points)) > 1 else 0,
                "interpretation": _interpret_entropy(entropy)
            },
            "autocorrelation": autocorr_results,
            "anomalies": anomalies,
            "patterns": patterns,
            "clustering": clusters,
            "summary": {
                "total_anomalies": len(anomalies["anomalous_games"]),
                "anomaly_rate": len(anomalies["anomalous_games"]) / len(games) * 100,
                "dominant_pattern": patterns["dominant_pattern"],
                "randomness_score": _calculate_randomness_score(entropy, autocorr_results)
            }
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error detecting patterns and anomalies: {str(e)}")
        raise


def calculate_expected_values(
    session: Session,
    target_multipliers: List[float] = [1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0],
    limit: int = 10000
) -> Dict[str, Any]:
    """
    Calculate expected values and optimal strategies for different target multipliers.
    
    Args:
        session: SQLAlchemy session
        target_multipliers: List of target multipliers to analyze
        limit: Number of most recent games to analyze
    
    Returns:
        Dictionary containing expected value analysis
    """
    try:
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
                "start": games[-1].endTime.isoformat() if games[-1].endTime else None,
                "end": games[0].endTime.isoformat() if games[0].endTime else None
            },
            "target_analysis": {},
            "survival_probabilities": {},
            "optimal_targets": {}
        }
        
        # Analyze each target multiplier
        for target in target_multipliers:
            # Empirical probability of reaching target
            successes = sum(1 for cp in crash_points if cp >= target)
            empirical_prob = successes / total_games
            
            # Theoretical probability using BC.game formula
            theoretical_prob = _calculate_theoretical_probability(target)
            
            # Expected value calculation
            ev = (target - 1) * empirical_prob - (1 - empirical_prob)
            theoretical_ev = (target - 1) * theoretical_prob - (1 - theoretical_prob)
            
            # Kelly criterion for optimal bet sizing
            kelly_fraction = (empirical_prob * target - 1) / (target - 1) if target > 1 else 0
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25% for safety
            
            result["target_analysis"][f"{target}x"] = {
                "target": target,
                "empirical_probability": empirical_prob * 100,
                "theoretical_probability": theoretical_prob * 100,
                "probability_deviation": (empirical_prob - theoretical_prob) * 100,
                "expected_value": ev,
                "theoretical_ev": theoretical_ev,
                "ev_per_100_bets": ev * 100,
                "kelly_criterion": kelly_fraction * 100,
                "breakeven_probability": 1 / target * 100,
                "edge": (empirical_prob - 1/target) * 100 if target > 0 else 0,
                "recommendation": _get_ev_recommendation(ev, kelly_fraction)
            }
        
        # Calculate survival probabilities
        survival_points = [1.1, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0]
        for i, point in enumerate(survival_points[:-1]):
            next_point = survival_points[i + 1]
            
            # P(crash >= next | crash >= current)
            games_above_current = sum(1 for cp in crash_points if cp >= point)
            games_above_next = sum(1 for cp in crash_points if cp >= next_point)
            
            conditional_prob = games_above_next / games_above_current if games_above_current > 0 else 0
            
            result["survival_probabilities"][f"{point}x_to_{next_point}x"] = {
                "from": point,
                "to": next_point,
                "conditional_probability": conditional_prob * 100,
                "interpretation": _interpret_survival_probability(conditional_prob)
            }
        
        # Find optimal targets based on different criteria
        result["optimal_targets"] = {
            "max_expected_value": _find_max_ev_target(result["target_analysis"]),
            "max_kelly_criterion": _find_max_kelly_target(result["target_analysis"]),
            "best_risk_adjusted": _find_best_risk_adjusted_target(result["target_analysis"])
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating expected values: {str(e)}")
        raise


def calculate_market_psychology_indicators(
    session: Session,
    limit: int = 1000,
    short_window: int = 50,
    long_window: int = 200
) -> Dict[str, Any]:
    """
    Calculate market psychology indicators adapted for crash games.
    
    Args:
        session: SQLAlchemy session
        limit: Number of most recent games to analyze
        short_window: Short-term window for indicators
        long_window: Long-term window for indicators
    
    Returns:
        Dictionary containing market psychology indicators
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
        
        # Calculate various indicators
        bust_frequency = _calculate_bust_frequency_index(crash_points, threshold=2.0)
        volatility_regime = _detect_volatility_regime(crash_points, short_window, long_window)
        momentum = _calculate_crash_momentum(crash_points, period=14)
        fear_greed = _calculate_fear_greed_index(crash_points, games)
        
        result = {
            "total_games": len(games),
            "latest_update": games[-1].endTime.isoformat() if games[-1].endTime else None,
            "bust_frequency_index": bust_frequency,
            "volatility_regime": volatility_regime,
            "momentum_indicators": momentum,
            "fear_greed_index": fear_greed,
            "market_state": _determine_market_state(bust_frequency, volatility_regime, momentum, fear_greed),
            "trading_recommendations": _generate_trading_recommendations(
                bust_frequency, volatility_regime, momentum, fear_greed
            )
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating market psychology indicators: {str(e)}")
        raise


# Helper functions

def _calculate_theoretical_probability(multiplier: float) -> float:
    """Calculate theoretical probability for a multiplier using BC.game formula."""
    if multiplier <= 1:
        return 1.0
    # Inverse of the crash formula: P(X >= m) = 1 - (1 - 99/m)
    return max(0, 1 - (1 - 99 / (multiplier * 100))) * BASE_PROBABILITY


def _find_optimal_strategy(strategies: Dict[str, Any]) -> Dict[str, Any]:
    """Find the optimal strategy based on multiple criteria."""
    best_sharpe = max(strategies.items(), key=lambda x: x[1]["risk_metrics"]["sharpe_ratio"])
    best_roi = max(strategies.items(), key=lambda x: x[1]["performance"]["roi"])
    best_win_rate = max(strategies.items(), key=lambda x: x[1]["performance"]["win_rate"])
    
    return {
        "best_sharpe_ratio": best_sharpe[0],
        "best_roi": best_roi[0],
        "best_win_rate": best_win_rate[0],
        "recommendation": _get_strategy_recommendation(best_sharpe[0], best_roi[0], best_win_rate[0])
    }


def _calculate_entropy(data: List[float], bins: int = 50) -> float:
    """Calculate Shannon entropy of the data."""
    # Create histogram
    hist, _ = np.histogram(data, bins=bins)
    # Normalize to get probabilities
    probs = hist / hist.sum()
    # Remove zero probabilities
    probs = probs[probs > 0]
    # Calculate entropy
    return float(-np.sum(probs * np.log2(probs)))


def _calculate_autocorrelation(data: List[float], max_lag: int = 20) -> Dict[str, Any]:
    """Calculate autocorrelation for different lags."""
    correlations = {}
    significant_lags = []
    
    for lag in range(1, min(max_lag + 1, len(data) // 2)):
        if len(data) > lag:
            correlation = np.corrcoef(data[:-lag], data[lag:])[0, 1]
            correlations[lag] = float(correlation) if not np.isnan(correlation) else 0.0
            
            # Check if significant (rough approximation)
            if abs(correlations[lag]) > 2 / math.sqrt(len(data)):
                significant_lags.append(lag)
    
    return {
        "correlations": correlations,
        "significant_lags": significant_lags,
        "interpretation": "No significant autocorrelation" if not significant_lags else f"Significant correlation at lags: {significant_lags}"
    }


def _detect_anomalies(crash_points: List[float], games: List[CrashGame], threshold: float) -> Dict[str, Any]:
    """Detect anomalies using multiple methods."""
    # Z-score method
    mean = statistics.mean(crash_points)
    std = statistics.stdev(crash_points) if len(crash_points) > 1 else 0
    
    anomalous_games = []
    for i, (cp, game) in enumerate(zip(crash_points, games)):
        z_score = (cp - mean) / std if std > 0 else 0
        if abs(z_score) > threshold:
            anomalous_games.append({
                "index": i,
                "game_id": game.gameId,
                "crash_point": cp,
                "z_score": z_score,
                "time": game.endTime.isoformat() if game.endTime else None
            })
    
    # IQR method
    q1 = float(np.percentile(crash_points, 25))
    q3 = float(np.percentile(crash_points, 75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    iqr_anomalies = sum(1 for cp in crash_points if cp < lower_bound or cp > upper_bound)
    
    return {
        "anomalous_games": anomalous_games,
        "z_score_threshold": threshold,
        "iqr_bounds": {"lower": float(lower_bound), "upper": float(upper_bound)},
        "iqr_anomaly_count": iqr_anomalies,
        "anomaly_rate": len(anomalous_games) / len(crash_points) * 100
    }


def _detect_patterns(crash_points: List[float], games: List[CrashGame]) -> Dict[str, Any]:
    """Detect various patterns in the data."""
    # Detect peaks
    peaks, properties = find_peaks(crash_points, height=10, distance=10)
    
    # Detect trends
    trend = np.polyfit(range(len(crash_points)), crash_points, 1)[0]
    
    # Detect cycles
    fft = np.fft.fft(crash_points)
    frequencies = np.fft.fftfreq(len(crash_points))
    dominant_frequency_idx = np.argmax(np.abs(fft[1:len(fft)//2])) + 1
    dominant_period = 1 / frequencies[dominant_frequency_idx] if frequencies[dominant_frequency_idx] != 0 else 0
    
    return {
        "peaks": {
            "count": int(len(peaks)),
            "positions": [int(p) for p in peaks.tolist()],
            "average_height": float(np.mean(properties["peak_heights"])) if len(peaks) > 0 else 0.0
        },
        "trend": {
            "slope": float(trend),
            "direction": "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable"
        },
        "periodicity": {
            "dominant_period": float(abs(dominant_period)),
            "has_cycle": bool(abs(dominant_period) > 2 and abs(dominant_period) < len(crash_points) / 2)
        },
        "dominant_pattern": _identify_dominant_pattern(trend, len(peaks), dominant_period)
    }


def _perform_clustering(crash_points: List[float]) -> Dict[str, Any]:
    """Perform simple clustering analysis."""
    # Define crash point categories
    categories = {
        "bust": (1.0, 2.0),
        "low": (2.0, 5.0),
        "medium": (5.0, 10.0),
        "high": (10.0, 50.0),
        "moon": (50.0, float('inf'))
    }
    
    clusters = {}
    for name, (min_val, max_val) in categories.items():
        count = sum(1 for cp in crash_points if min_val <= cp < max_val)
        clusters[name] = {
            "count": count,
            "percentage": count / len(crash_points) * 100,
            "range": f"{min_val}x-{max_val}x" if max_val != float('inf') else f"{min_val}x+"
        }
    
    return clusters


def _interpret_entropy(entropy: float) -> str:
    """Interpret entropy value."""
    if entropy < 2:
        return "Very low randomness - highly predictable"
    elif entropy < 3:
        return "Low randomness - somewhat predictable"
    elif entropy < 4:
        return "Moderate randomness - balanced"
    elif entropy < 5:
        return "High randomness - unpredictable"
    else:
        return "Very high randomness - extremely unpredictable"


def _calculate_randomness_score(entropy: float, autocorr: Dict[str, Any]) -> float:
    """Calculate overall randomness score."""
    entropy_score = min(entropy / 5, 1) * 50  # Normalize to 0-50
    autocorr_score = (1 - len(autocorr["significant_lags"]) / 20) * 50  # Normalize to 0-50
    return entropy_score + autocorr_score


def _get_ev_recommendation(ev: float, kelly: float) -> str:
    """Get recommendation based on expected value and Kelly criterion."""
    if ev > 0.05 and kelly > 0.1:
        return "Strongly favorable - consider betting"
    elif ev > 0 and kelly > 0.05:
        return "Favorable - moderate opportunity"
    elif ev > -0.02:
        return "Neutral - marginal edge"
    else:
        return "Unfavorable - avoid betting"


def _interpret_survival_probability(prob: float) -> str:
    """Interpret conditional survival probability."""
    if prob > 0.7:
        return "Very high continuation probability"
    elif prob > 0.5:
        return "High continuation probability"
    elif prob > 0.3:
        return "Moderate continuation probability"
    else:
        return "Low continuation probability"


def _find_max_ev_target(target_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Find target with maximum expected value."""
    max_ev = max(target_analysis.items(), key=lambda x: x[1]["expected_value"])
    return {
        "target": max_ev[0],
        "expected_value": max_ev[1]["expected_value"],
        "probability": max_ev[1]["empirical_probability"]
    }


def _find_max_kelly_target(target_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Find target with maximum Kelly criterion."""
    max_kelly = max(target_analysis.items(), key=lambda x: x[1]["kelly_criterion"])
    return {
        "target": max_kelly[0],
        "kelly_criterion": max_kelly[1]["kelly_criterion"],
        "expected_value": max_kelly[1]["expected_value"]
    }


def _find_best_risk_adjusted_target(target_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Find best risk-adjusted target."""
    # Balance between EV and probability
    best = max(target_analysis.items(), 
               key=lambda x: x[1]["expected_value"] * math.sqrt(x[1]["empirical_probability"] / 100))
    return {
        "target": best[0],
        "expected_value": best[1]["expected_value"],
        "probability": best[1]["empirical_probability"],
        "risk_adjusted_score": best[1]["expected_value"] * math.sqrt(best[1]["empirical_probability"] / 100)
    }


def _calculate_bust_frequency_index(crash_points: List[float], threshold: float = 2.0) -> Dict[str, Any]:
    """Calculate bust frequency index."""
    recent_games = 100
    long_term_games = len(crash_points)
    
    recent_busts = sum(1 for cp in crash_points[-recent_games:] if cp < threshold)
    total_busts = sum(1 for cp in crash_points if cp < threshold)
    
    recent_rate = recent_busts / recent_games * 100
    long_term_rate = total_busts / long_term_games * 100
    
    index = recent_rate / long_term_rate * 100 if long_term_rate > 0 else 100
    
    return {
        "index": index,
        "recent_bust_rate": recent_rate,
        "long_term_bust_rate": long_term_rate,
        "interpretation": _interpret_bust_frequency(index)
    }


def _detect_volatility_regime(crash_points: List[float], short_window: int, long_window: int) -> Dict[str, Any]:
    """Detect current volatility regime."""
    if len(crash_points) < long_window:
        return {"error": "Insufficient data for volatility regime detection"}
    
    # Calculate rolling standard deviations
    short_vol = float(np.std(crash_points[-short_window:]))
    long_vol = float(np.std(crash_points[-long_window:]))
    
    vol_ratio = short_vol / long_vol if long_vol > 0 else 1.0
    
    # Historical volatility percentiles
    rolling_vols = []
    for i in range(long_window, len(crash_points)):
        window = crash_points[i-short_window:i]
        rolling_vols.append(float(np.std(window)))
    
    current_percentile = float(stats.percentileofscore(rolling_vols, short_vol)) if rolling_vols else 50.0
    
    return {
        "current_volatility": short_vol,
        "average_volatility": long_vol,
        "volatility_ratio": float(vol_ratio),
        "percentile_rank": current_percentile,
        "regime": _classify_volatility_regime(vol_ratio, current_percentile)
    }


def _calculate_crash_momentum(crash_points: List[float], period: int = 14) -> Dict[str, Any]:
    """Calculate momentum indicators adapted for crash games."""
    if len(crash_points) < period:
        return {"error": "Insufficient data for momentum calculation"}
    
    # RSI-like indicator for crash points
    gains = []
    losses = []
    
    for i in range(1, min(period, len(crash_points))):
        change = crash_points[-i] - crash_points[-i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))
    
    # Momentum score
    recent_avg = float(np.mean(crash_points[-period:]))
    longer_avg = float(np.mean(crash_points[-period*3:])) if len(crash_points) >= period*3 else recent_avg
    momentum_score = (recent_avg / longer_avg - 1) * 100 if longer_avg > 0 else 0
    
    return {
        "rsi": float(rsi),
        "momentum_score": float(momentum_score),
        "recent_average": recent_avg,
        "trend": "bullish" if momentum_score > 5 else "bearish" if momentum_score < -5 else "neutral",
        "interpretation": _interpret_momentum(rsi, momentum_score)
    }


def _calculate_fear_greed_index(crash_points: List[float], games: List[CrashGame]) -> Dict[str, Any]:
    """Calculate a fear & greed index for crash games."""
    # Components:
    # 1. Recent performance vs average
    # 2. Volatility
    # 3. High multiplier frequency
    # 4. Bust frequency
    
    recent_100 = crash_points[-100:] if len(crash_points) >= 100 else crash_points
    
    # Performance component (0-100)
    recent_avg = float(np.mean(recent_100))
    total_avg = float(np.mean(crash_points))
    performance_score = min(100, max(0, 50 + (recent_avg - total_avg) / total_avg * 50))
    
    # Volatility component (inverted, 0-100)
    recent_vol = float(np.std(recent_100))
    vol_score = max(0, 100 - recent_vol * 10)  # Lower volatility = higher score
    
    # High multiplier component (0-100)
    high_mult_recent = sum(1 for cp in recent_100 if cp >= 10) / len(recent_100)
    high_mult_total = sum(1 for cp in crash_points if cp >= 10) / len(crash_points)
    high_mult_score = min(100, max(0, 50 + (high_mult_recent - high_mult_total) / high_mult_total * 50)) if high_mult_total > 0 else 50
    
    # Bust frequency component (inverted, 0-100)
    bust_recent = sum(1 for cp in recent_100 if cp < 2) / len(recent_100)
    bust_total = sum(1 for cp in crash_points if cp < 2) / len(crash_points)
    bust_score = min(100, max(0, 50 + (bust_total - bust_recent) / bust_total * 50)) if bust_total > 0 else 50
    
    # Weighted average
    fear_greed_index = float(
        performance_score * 0.3 +
        vol_score * 0.2 +
        high_mult_score * 0.3 +
        bust_score * 0.2
    )
    
    return {
        "index": fear_greed_index,
        "components": {
            "performance": float(performance_score),
            "volatility": float(vol_score),
            "high_multipliers": float(high_mult_score),
            "bust_frequency": float(bust_score)
        },
        "sentiment": _classify_sentiment(fear_greed_index)
    }


def _interpret_bust_frequency(index: float) -> str:
    """Interpret bust frequency index."""
    if index > 120:
        return "Very high bust frequency - extreme caution"
    elif index > 110:
        return "High bust frequency - caution advised"
    elif index > 90:
        return "Normal bust frequency"
    elif index > 80:
        return "Low bust frequency - favorable conditions"
    else:
        return "Very low bust frequency - highly favorable"


def _classify_volatility_regime(ratio: float, percentile: float) -> str:
    """Classify volatility regime."""
    if percentile > 80:
        return "High volatility regime"
    elif percentile > 60:
        return "Elevated volatility"
    elif percentile > 40:
        return "Normal volatility"
    elif percentile > 20:
        return "Low volatility"
    else:
        return "Very low volatility regime"


def _interpret_momentum(rsi: float, momentum: float) -> str:
    """Interpret momentum indicators."""
    if rsi > 70 and momentum > 10:
        return "Strong bullish momentum - overbought"
    elif rsi > 50 and momentum > 0:
        return "Bullish momentum"
    elif rsi < 30 and momentum < -10:
        return "Strong bearish momentum - oversold"
    elif rsi < 50 and momentum < 0:
        return "Bearish momentum"
    else:
        return "Neutral momentum"


def _classify_sentiment(index: float) -> str:
    """Classify market sentiment based on fear & greed index."""
    if index >= 75:
        return "Extreme Greed"
    elif index >= 60:
        return "Greed"
    elif index >= 40:
        return "Neutral"
    elif index >= 25:
        return "Fear"
    else:
        return "Extreme Fear"


def _identify_dominant_pattern(trend: float, peak_count: int, period: float) -> str:
    """Identify the dominant pattern in the data."""
    if abs(trend) > 0.1:
        return f"Trending {'up' if trend > 0 else 'down'}"
    elif period > 2 and period < 100:
        return f"Cyclical with period ~{int(period)} games"
    elif peak_count > 10:
        return "Volatile with frequent spikes"
    else:
        return "Random walk pattern"


def _determine_market_state(bust_freq: Dict, volatility: Dict, momentum: Dict, fear_greed: Dict) -> Dict[str, Any]:
    """Determine overall market state."""
    states = []
    
    if bust_freq["index"] > 110:
        states.append("High Risk")
    if volatility.get("percentile_rank", 50) > 70:
        states.append("Volatile")
    if momentum.get("rsi", 50) > 70:
        states.append("Overbought")
    elif momentum.get("rsi", 50) < 30:
        states.append("Oversold")
    if fear_greed["index"] > 70:
        states.append("Greedy")
    elif fear_greed["index"] < 30:
        states.append("Fearful")
    
    return {
        "states": states if states else ["Normal"],
        "risk_level": _calculate_risk_level(bust_freq, volatility, fear_greed),
        "opportunity_score": _calculate_opportunity_score(bust_freq, volatility, momentum, fear_greed)
    }


def _calculate_risk_level(bust_freq: Dict, volatility: Dict, fear_greed: Dict) -> str:
    """Calculate overall risk level."""
    risk_score = 0
    
    # Bust frequency contribution
    if bust_freq["index"] > 120:
        risk_score += 40
    elif bust_freq["index"] > 110:
        risk_score += 20
    
    # Volatility contribution
    vol_percentile = volatility.get("percentile_rank", 50)
    risk_score += vol_percentile / 100 * 30
    
    # Sentiment contribution
    if fear_greed["index"] > 75 or fear_greed["index"] < 25:
        risk_score += 30
    elif fear_greed["index"] > 65 or fear_greed["index"] < 35:
        risk_score += 15
    
    if risk_score > 70:
        return "Very High"
    elif risk_score > 50:
        return "High"
    elif risk_score > 30:
        return "Medium"
    else:
        return "Low"


def _calculate_opportunity_score(bust_freq: Dict, volatility: Dict, momentum: Dict, fear_greed: Dict) -> float:
    """Calculate opportunity score (0-100)."""
    score = 50  # Base score
    
    # Favorable bust frequency
    if bust_freq["index"] < 90:
        score += 20
    elif bust_freq["index"] > 110:
        score -= 20
    
    # Moderate volatility is good
    vol_percentile = volatility.get("percentile_rank", 50)
    if 30 < vol_percentile < 70:
        score += 10
    else:
        score -= 10
    
    # Momentum alignment
    if momentum.get("trend") == "bullish" and momentum.get("rsi", 50) < 70:
        score += 15
    elif momentum.get("trend") == "bearish" and momentum.get("rsi", 50) < 30:
        score += 10  # Oversold bounce opportunity
    
    # Sentiment extremes can be opportunities
    if fear_greed["index"] < 25:
        score += 10  # Extreme fear = opportunity
    elif fear_greed["index"] > 75:
        score -= 10  # Extreme greed = caution
    
    return max(0, min(100, score))


def _generate_trading_recommendations(bust_freq: Dict, volatility: Dict, momentum: Dict, fear_greed: Dict) -> List[str]:
    """Generate specific trading recommendations."""
    recommendations = []
    
    # Risk management
    if bust_freq["index"] > 110:
        recommendations.append("Reduce bet sizes due to high bust frequency")
    if volatility.get("percentile_rank", 50) > 80:
        recommendations.append("Use tighter stop-losses in high volatility")
    
    # Strategy suggestions
    if momentum.get("trend") == "bullish" and fear_greed["index"] < 60:
        recommendations.append("Consider aggressive targets (5x-10x) in bullish conditions")
    elif momentum.get("trend") == "bearish" or fear_greed["index"] > 70:
        recommendations.append("Focus on conservative targets (1.5x-2x) in current conditions")
    
    # Timing
    if momentum.get("rsi", 50) < 30:
        recommendations.append("Potential bounce opportunity - monitor for trend reversal")
    elif momentum.get("rsi", 50) > 70:
        recommendations.append("Overbought conditions - wait for pullback")
    
    # General advice
    opportunity = _calculate_opportunity_score(bust_freq, volatility, momentum, fear_greed)
    if opportunity > 70:
        recommendations.append("High opportunity score - favorable conditions for betting")
    elif opportunity < 30:
        recommendations.append("Low opportunity score - consider waiting for better conditions")
    
    return recommendations if recommendations else ["Maintain normal betting strategy"]


def _get_strategy_recommendation(sharpe: str, roi: str, win_rate: str) -> str:
    """Get strategy recommendation based on optimal metrics."""
    if sharpe == roi == win_rate:
        return f"Target {sharpe} dominates all metrics"
    elif sharpe == roi:
        return f"Target {sharpe} offers best risk-adjusted returns"
    else:
        return f"Consider {sharpe} for risk-adjusted returns or {roi} for maximum ROI"


def get_combined_statistical_analysis(
    session: Session,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Get comprehensive statistical analysis including all enhanced models.
    
    Args:
        session: SQLAlchemy session
        limit: Number of most recent games to analyze
    
    Returns:
        Dictionary containing all statistical analyses
    """
    try:
        result = {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "games_analyzed": limit
            }
        }
        
        # Get risk-adjusted metrics
        result["risk_adjusted_metrics"] = calculate_risk_adjusted_metrics(session, limit=limit)
        
        # Get pattern and anomaly detection
        result["pattern_analysis"] = detect_patterns_and_anomalies(session, limit=limit)
        
        # Get expected value analysis
        result["expected_values"] = calculate_expected_values(session, limit=limit)
        
        # Get market psychology indicators
        result["market_psychology"] = calculate_market_psychology_indicators(session, limit=limit)
        
        return result
    
    except Exception as e:
        logger.error(f"Error in combined statistical analysis: {str(e)}")
        raise