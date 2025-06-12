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


def calculate_bayesian_probability_updates(
    session: Session,
    target_multipliers: List[float] = [2.0, 3.0, 5.0, 10.0],
    window_size: int = 100,
    limit: int = 1000
) -> Dict[str, Any]:
    """
    Calculate Bayesian updated probabilities for crash game outcomes.
    
    This function uses Bayesian inference to continuously update probability estimates
    based on recent game outcomes, providing more adaptive predictions.
    
    Args:
        session: SQLAlchemy session
        target_multipliers: List of target multipliers to track
        window_size: Size of rolling window for updates
        limit: Number of most recent games to analyze
    
    Returns:
        Dictionary containing Bayesian probability estimates and updates
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
            "window_size": window_size,
            "analysis_period": {
                "start": games[0].endTime.isoformat() if games[0].endTime else None,
                "end": games[-1].endTime.isoformat() if games[-1].endTime else None
            },
            "bayesian_estimates": {},
            "probability_evolution": {},
            "convergence_analysis": {}
        }
        
        # Initialize with theoretical priors
        priors = {}
        for target in target_multipliers:
            priors[target] = _calculate_theoretical_probability(target)
        
        # Track probability evolution over time
        evolution = {target: [] for target in target_multipliers}
        
        # Sliding window Bayesian updates
        for i in range(window_size, len(crash_points) + 1):
            window = crash_points[max(0, i - window_size):i]
            
            for target in target_multipliers:
                # Count successes in window
                successes = sum(1 for cp in window if cp >= target)
                failures = len(window) - successes
                
                # Beta distribution parameters (conjugate prior for Bernoulli)
                # Using informative prior based on theoretical probability
                prior_alpha = priors[target] * 100  # Prior successes
                prior_beta = (1 - priors[target]) * 100  # Prior failures
                
                # Posterior parameters
                post_alpha = prior_alpha + successes
                post_beta = prior_beta + failures
                
                # Posterior mean (updated probability)
                posterior_mean = post_alpha / (post_alpha + post_beta)
                
                # Store evolution
                evolution[target].append({
                    "game_index": i,
                    "probability": posterior_mean,
                    "confidence_interval": _calculate_beta_ci(post_alpha, post_beta),
                    "successes": successes,
                    "total": len(window)
                })
        
        # Analyze final estimates
        for target in target_multipliers:
            if evolution[target]:
                final_estimate = evolution[target][-1]
                
                # Calculate credible intervals
                alpha = final_estimate["confidence_interval"]["alpha"]
                beta = final_estimate["confidence_interval"]["beta"]
                
                # Convergence analysis
                probabilities = [e["probability"] for e in evolution[target]]
                convergence_rate = _calculate_convergence_rate(probabilities)
                
                result["bayesian_estimates"][f"{target}x"] = {
                    "target": target,
                    "prior_probability": priors[target] * 100,
                    "posterior_probability": final_estimate["probability"] * 100,
                    "credible_interval_95": {
                        "lower": final_estimate["confidence_interval"]["lower"] * 100,
                        "upper": final_estimate["confidence_interval"]["upper"] * 100
                    },
                    "probability_shift": (final_estimate["probability"] - priors[target]) * 100,
                    "evidence_strength": _calculate_evidence_strength(
                        priors[target], final_estimate["probability"], len(crash_points)
                    ),
                    "convergence_rate": convergence_rate,
                    "recommendation": _get_bayesian_recommendation(
                        priors[target], final_estimate["probability"], convergence_rate
                    )
                }
                
                # Store last few evolution points for visualization
                result["probability_evolution"][f"{target}x"] = evolution[target][-10:]
        
        # Model comparison using Bayesian Information Criterion
        result["model_comparison"] = _compare_bayesian_models(crash_points, target_multipliers, priors)
        
        # Predictive distributions
        result["predictive_distributions"] = _calculate_predictive_distributions(
            result["bayesian_estimates"], window_size
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating Bayesian probability updates: {str(e)}")
        raise


def run_monte_carlo_simulations(
    session: Session,
    num_simulations: int = 10000,
    games_per_simulation: int = 100,
    strategies: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulations to generate potential future scenarios.
    
    This function simulates thousands of possible game sequences to evaluate
    different betting strategies and estimate outcome distributions.
    
    Args:
        session: SQLAlchemy session
        num_simulations: Number of simulation runs
        games_per_simulation: Number of games per simulation
        strategies: List of betting strategies to evaluate
    
    Returns:
        Dictionary containing simulation results and strategy evaluations
    """
    try:
        # Get historical data for parameter estimation
        games = session.query(CrashGame)\
            .order_by(desc(CrashGame.endTime))\
            .limit(10000)\
            .all()
        
        if not games:
            return {"error": "No games found"}
        
        crash_points = [game.crashPoint for game in games]
        
        # Default strategies if none provided
        if strategies is None:
            strategies = [
                {"name": "Conservative", "target": 1.5, "bet_fraction": 0.02},
                {"name": "Moderate", "target": 2.0, "bet_fraction": 0.03},
                {"name": "Aggressive", "target": 3.0, "bet_fraction": 0.05},
                {"name": "High Risk", "target": 5.0, "bet_fraction": 0.10},
                {"name": "Martingale 2x", "type": "martingale", "target": 2.0, "base_bet": 0.01}
            ]
        
        # Estimate distribution parameters from historical data
        distribution_params = _estimate_crash_distribution(crash_points)
        
        result = {
            "num_simulations": num_simulations,
            "games_per_simulation": games_per_simulation,
            "distribution_params": distribution_params,
            "strategy_results": {},
            "outcome_distributions": {},
            "risk_analysis": {}
        }
        
        # Run simulations for each strategy
        for strategy in strategies:
            strategy_outcomes = []
            
            for sim in range(num_simulations):
                # Generate simulated crash points
                simulated_crashes = _generate_crash_sequence(
                    games_per_simulation, distribution_params
                )
                
                # Simulate strategy performance
                final_balance = _simulate_strategy(
                    simulated_crashes, strategy, initial_balance=1000
                )
                
                strategy_outcomes.append(final_balance)
            
            # Analyze outcomes
            outcomes_array = np.array(strategy_outcomes)
            
            result["strategy_results"][strategy["name"]] = {
                "mean_final_balance": float(np.mean(outcomes_array)),
                "median_final_balance": float(np.median(outcomes_array)),
                "std_deviation": float(np.std(outcomes_array)),
                "probability_of_profit": float(np.mean(outcomes_array > 1000) * 100),
                "probability_of_ruin": float(np.mean(outcomes_array < 100) * 100),
                "percentiles": {
                    "5th": float(np.percentile(outcomes_array, 5)),
                    "25th": float(np.percentile(outcomes_array, 25)),
                    "75th": float(np.percentile(outcomes_array, 75)),
                    "95th": float(np.percentile(outcomes_array, 95))
                },
                "max_balance": float(np.max(outcomes_array)),
                "min_balance": float(np.min(outcomes_array)),
                "sharpe_ratio": _calculate_mc_sharpe_ratio(outcomes_array, 1000),
                "expected_return": float((np.mean(outcomes_array) - 1000) / 1000 * 100)
            }
            
            # Store outcome distribution for visualization
            result["outcome_distributions"][strategy["name"]] = {
                "histogram": _create_outcome_histogram(outcomes_array, bins=50),
                "density_estimate": _estimate_outcome_density(outcomes_array)
            }
        
        # Overall risk analysis
        result["risk_analysis"] = _analyze_simulation_risks(result["strategy_results"])
        
        # Optimal strategy based on simulations
        result["optimal_strategy"] = _find_optimal_mc_strategy(result["strategy_results"])
        
        return result
    
    except Exception as e:
        logger.error(f"Error running Monte Carlo simulations: {str(e)}")
        raise


def backtest_strategies(
    session: Session,
    strategies: List[Dict[str, Any]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    initial_balance: float = 1000
) -> Dict[str, Any]:
    """
    Backtest different betting strategies on historical data.
    
    This function tests various betting strategies against actual historical
    crash game data to evaluate their performance.
    
    Args:
        session: SQLAlchemy session
        strategies: List of strategies to backtest
        start_date: Start date for backtesting period
        end_date: End date for backtesting period
        initial_balance: Starting balance for each strategy
    
    Returns:
        Dictionary containing backtest results for each strategy
    """
    try:
        # Build query with date filters
        query = session.query(CrashGame).order_by(CrashGame.endTime)
        
        if start_date:
            query = query.filter(CrashGame.endTime >= start_date)
        if end_date:
            query = query.filter(CrashGame.endTime <= end_date)
        
        games = query.all()
        
        if not games:
            return {"error": "No games found in specified date range"}
        
        # Default strategies if none provided
        if strategies is None:
            strategies = [
                {
                    "name": "Fixed Target 2x",
                    "type": "fixed",
                    "target": 2.0,
                    "bet_fraction": 0.05
                },
                {
                    "name": "Progressive 1.5x-3x",
                    "type": "progressive",
                    "targets": [1.5, 2.0, 2.5, 3.0],
                    "bet_fraction": 0.03
                },
                {
                    "name": "Martingale 2x",
                    "type": "martingale",
                    "target": 2.0,
                    "base_bet_fraction": 0.01,
                    "max_bet_fraction": 0.20
                },
                {
                    "name": "Kelly Criterion Dynamic",
                    "type": "kelly",
                    "kelly_fraction": 0.25
                },
                {
                    "name": "Momentum Based",
                    "type": "momentum",
                    "lookback": 50,
                    "bet_fraction": 0.04
                }
            ]
        
        crash_points = [game.crashPoint for game in games]
        timestamps = [game.endTime for game in games]
        
        result = {
            "backtest_period": {
                "start": games[0].endTime.isoformat() if games[0].endTime else None,
                "end": games[-1].endTime.isoformat() if games[-1].endTime else None,
                "total_games": len(games)
            },
            "initial_balance": initial_balance,
            "strategy_performance": {},
            "comparison_metrics": {},
            "detailed_analysis": {}
        }
        
        # Backtest each strategy
        for strategy in strategies:
            performance = _run_strategy_backtest(
                crash_points, timestamps, strategy, initial_balance
            )
            
            result["strategy_performance"][strategy["name"]] = performance
            
            # Detailed analysis for each strategy
            result["detailed_analysis"][strategy["name"]] = _analyze_backtest_performance(
                performance, crash_points, initial_balance
            )
        
        # Compare all strategies
        result["comparison_metrics"] = _compare_backtest_strategies(
            result["strategy_performance"], initial_balance
        )
        
        # Find best strategy for different objectives
        result["optimal_strategies"] = {
            "max_return": _find_best_return_strategy(result["strategy_performance"]),
            "min_risk": _find_lowest_risk_strategy(result["strategy_performance"]),
            "best_sharpe": _find_best_sharpe_strategy(result["strategy_performance"]),
            "most_consistent": _find_most_consistent_strategy(result["strategy_performance"])
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error backtesting strategies: {str(e)}")
        raise


def calculate_multiplier_correlations(
    session: Session,
    ranges: List[Tuple[float, float]] = None,
    limit: int = 5000
) -> Dict[str, Any]:
    """
    Analyze correlations between different multiplier ranges.
    
    This function examines how outcomes in different multiplier ranges
    correlate with each other and with subsequent games.
    
    Args:
        session: SQLAlchemy session
        ranges: List of multiplier ranges to analyze
        limit: Number of most recent games to analyze
    
    Returns:
        Dictionary containing correlation analysis
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
        
        # Default ranges if none provided
        if ranges is None:
            ranges = [
                (1.0, 1.5),
                (1.5, 2.0),
                (2.0, 3.0),
                (3.0, 5.0),
                (5.0, 10.0),
                (10.0, 50.0),
                (50.0, float('inf'))
            ]
        
        result = {
            "total_games": len(games),
            "analysis_period": {
                "start": games[0].endTime.isoformat() if games[0].endTime else None,
                "end": games[-1].endTime.isoformat() if games[-1].endTime else None
            },
            "multiplier_ranges": [
                {"min": r[0], "max": r[1] if r[1] != float('inf') else "∞"} 
                for r in ranges
            ],
            "range_correlations": {},
            "sequential_analysis": {},
            "transition_probabilities": {},
            "pattern_analysis": {}
        }
        
        # Convert crash points to range indicators
        range_indicators = []
        for cp in crash_points:
            indicators = []
            for i, (min_val, max_val) in enumerate(ranges):
                indicators.append(1 if min_val <= cp < max_val else 0)
            range_indicators.append(indicators)
        
        range_indicators = np.array(range_indicators)
        
        # Calculate correlation matrix
        correlation_matrix = np.corrcoef(range_indicators.T)
        
        # Store correlations
        for i, range1 in enumerate(ranges):
            for j, range2 in enumerate(ranges):
                if i < j:  # Upper triangle only
                    key = f"{range1[0]}-{range1[1]}x_vs_{range2[0]}-{range2[1]}x"
                    result["range_correlations"][key] = {
                        "correlation": float(correlation_matrix[i, j]),
                        "interpretation": _interpret_correlation(correlation_matrix[i, j])
                    }
        
        # Sequential correlation analysis (does one range predict the next?)
        for lag in [1, 2, 3, 5, 10]:
            lag_correlations = {}
            
            for i, range_name in enumerate(ranges):
                if lag < len(crash_points):
                    # Correlation between being in range and next game's outcome
                    current_in_range = range_indicators[:-lag, i]
                    future_values = crash_points[lag:]
                    
                    if len(current_in_range) > 0 and np.std(current_in_range) > 0:
                        correlation = np.corrcoef(current_in_range, future_values)[0, 1]
                        lag_correlations[f"{range_name[0]}-{range_name[1]}x"] = float(correlation)
            
            result["sequential_analysis"][f"lag_{lag}"] = lag_correlations
        
        # Transition probability matrix
        transition_matrix = _calculate_transition_matrix(crash_points, ranges)
        result["transition_probabilities"] = transition_matrix
        
        # Pattern analysis within ranges
        for i, (min_val, max_val) in enumerate(ranges):
            range_crashes = [cp for cp in crash_points if min_val <= cp < max_val]
            
            if len(range_crashes) > 10:
                result["pattern_analysis"][f"{min_val}-{max_val}x"] = {
                    "count": len(range_crashes),
                    "mean": float(np.mean(range_crashes)),
                    "std": float(np.std(range_crashes)),
                    "skewness": float(stats.skew(range_crashes)),
                    "kurtosis": float(stats.kurtosis(range_crashes)),
                    "trend": _detect_range_trend(range_crashes, crash_points)
                }
        
        # Add insights and recommendations
        result["insights"] = _generate_correlation_insights(result)
        
        return result
    
    except Exception as e:
        logger.error(f"Error calculating multiplier correlations: {str(e)}")
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


# Bayesian helper functions

def _calculate_beta_ci(alpha: float, beta: float, confidence: float = 0.95) -> Dict[str, float]:
    """Calculate confidence interval for beta distribution."""
    from scipy import stats as scipy_stats
    lower = scipy_stats.beta.ppf((1 - confidence) / 2, alpha, beta)
    upper = scipy_stats.beta.ppf(1 - (1 - confidence) / 2, alpha, beta)
    return {
        "alpha": alpha,
        "beta": beta,
        "lower": float(lower),
        "upper": float(upper)
    }


def _calculate_convergence_rate(probabilities: List[float]) -> float:
    """Calculate how quickly the probability estimates are converging."""
    if len(probabilities) < 10:
        return 0.0
    
    # Calculate variance of recent estimates vs older estimates
    recent = probabilities[-10:]
    older = probabilities[-20:-10] if len(probabilities) >= 20 else probabilities[:10]
    
    recent_var = np.var(recent)
    older_var = np.var(older)
    
    if older_var > 0:
        convergence_rate = 1 - (recent_var / older_var)
        return float(max(0, min(1, convergence_rate)))
    return 1.0 if recent_var == 0 else 0.0


def _calculate_evidence_strength(prior: float, posterior: float, n_samples: int) -> str:
    """Calculate strength of evidence for probability shift."""
    shift = abs(posterior - prior)
    relative_shift = shift / prior if prior > 0 else shift
    
    if n_samples < 100:
        return "Weak - insufficient data"
    elif relative_shift < 0.1:
        return "Weak - minimal change"
    elif relative_shift < 0.25:
        return "Moderate - notable change"
    elif relative_shift < 0.5:
        return "Strong - significant change"
    else:
        return "Very strong - major change"


def _get_bayesian_recommendation(prior: float, posterior: float, convergence: float) -> str:
    """Generate recommendation based on Bayesian analysis."""
    shift = posterior - prior
    
    if convergence < 0.5:
        return "Estimates still converging - wait for more data"
    elif abs(shift) < 0.05:
        return "Probabilities align with theoretical model"
    elif shift > 0.1:
        return "Higher probability than expected - favorable conditions"
    elif shift < -0.1:
        return "Lower probability than expected - exercise caution"
    else:
        return "Minor deviation from theoretical - normal variance"


def _compare_bayesian_models(crash_points: List[float], targets: List[float], priors: Dict[float, float]) -> Dict[str, Any]:
    """Compare different probability models using BIC."""
    n = len(crash_points)
    
    models = {
        "theoretical": 0,
        "empirical": 0,
        "bayesian": 0
    }
    
    for target in targets:
        successes = sum(1 for cp in crash_points if cp >= target)
        
        # Theoretical model log-likelihood
        p_theoretical = priors[target]
        ll_theoretical = successes * np.log(p_theoretical) + (n - successes) * np.log(1 - p_theoretical)
        
        # Empirical model log-likelihood
        p_empirical = successes / n
        if p_empirical > 0 and p_empirical < 1:
            ll_empirical = successes * np.log(p_empirical) + (n - successes) * np.log(1 - p_empirical)
        else:
            ll_empirical = 0
        
        models["theoretical"] += ll_theoretical
        models["empirical"] += ll_empirical
    
    # Calculate BIC (lower is better)
    bic_theoretical = -2 * models["theoretical"] + 0 * np.log(n)  # 0 parameters
    bic_empirical = -2 * models["empirical"] + len(targets) * np.log(n)  # k parameters
    
    return {
        "bic_scores": {
            "theoretical": float(bic_theoretical),
            "empirical": float(bic_empirical)
        },
        "best_model": "theoretical" if bic_theoretical < bic_empirical else "empirical",
        "interpretation": "Theoretical model fits better" if bic_theoretical < bic_empirical else "Empirical model fits better"
    }


def _calculate_predictive_distributions(estimates: Dict[str, Any], window_size: int) -> Dict[str, Any]:
    """Calculate predictive distributions for future outcomes."""
    predictions = {}
    
    for target_key, estimate in estimates.items():
        posterior_prob = estimate["posterior_probability"] / 100
        
        # Expected outcomes in next N games
        for n in [10, 50, 100]:
            expected = n * posterior_prob
            # Using normal approximation to binomial
            std = np.sqrt(n * posterior_prob * (1 - posterior_prob))
            
            predictions[f"{target_key}_next_{n}"] = {
                "expected_successes": float(expected),
                "std_deviation": float(std),
                "confidence_interval_95": {
                    "lower": float(max(0, expected - 1.96 * std)),
                    "upper": float(min(n, expected + 1.96 * std))
                }
            }
    
    return predictions


# Monte Carlo helper functions

def _estimate_crash_distribution(crash_points: List[float]) -> Dict[str, Any]:
    """Estimate distribution parameters from historical crash data."""
    log_crashes = np.log(crash_points)
    
    return {
        "type": "log-normal approximation",
        "mean": float(np.mean(crash_points)),
        "median": float(np.median(crash_points)),
        "std": float(np.std(crash_points)),
        "log_mean": float(np.mean(log_crashes)),
        "log_std": float(np.std(log_crashes)),
        "percentiles": {
            "10th": float(np.percentile(crash_points, 10)),
            "25th": float(np.percentile(crash_points, 25)),
            "75th": float(np.percentile(crash_points, 75)),
            "90th": float(np.percentile(crash_points, 90))
        }
    }


def _generate_crash_sequence(n_games: int, dist_params: Dict[str, Any]) -> List[float]:
    """Generate simulated crash points based on distribution parameters."""
    # Using the BC.game crash algorithm approximation
    crashes = []
    
    for _ in range(n_games):
        # Generate uniform random value
        h = np.random.uniform(0, 1)
        
        # Apply BC.game formula: crash = 99 / (1 - h)
        # With house edge adjustment
        if h < 0.97:  # 97% of the time, normal calculation
            crash = 0.99 / (1 - h)
        else:  # 3% house edge - instant crash
            crash = 1.0
        
        # Add small random variation to match empirical distribution
        crash *= np.random.normal(1.0, 0.02)
        crash = max(1.0, crash)
        
        crashes.append(crash)
    
    return crashes


def _simulate_strategy(crashes: List[float], strategy: Dict[str, Any], initial_balance: float) -> float:
    """Simulate a betting strategy over a sequence of crashes."""
    balance = initial_balance
    
    if strategy.get("type") == "martingale":
        base_bet = initial_balance * strategy.get("base_bet", 0.01)
        current_bet = base_bet
        target = strategy["target"]
        
        for crash in crashes:
            if balance < current_bet:
                break
                
            if crash >= target:
                # Win
                balance += current_bet * (target - 1)
                current_bet = base_bet
            else:
                # Loss
                balance -= current_bet
                current_bet = min(current_bet * 2, balance)  # Double or all-in
                
    elif strategy.get("type") == "progressive":
        # Implement progressive strategy
        targets = strategy.get("targets", [1.5, 2.0, 2.5, 3.0])
        current_target_idx = 0
        bet_fraction = strategy.get("bet_fraction", 0.03)
        
        for crash in crashes:
            if balance <= 0:
                break
                
            bet = balance * bet_fraction
            target = targets[current_target_idx]
            
            if crash >= target:
                balance += bet * (target - 1)
                # Move to next target
                current_target_idx = (current_target_idx + 1) % len(targets)
            else:
                balance -= bet
                # Reset to first target
                current_target_idx = 0
                
    else:
        # Default fixed target strategy
        target = strategy.get("target", 2.0)
        bet_fraction = strategy.get("bet_fraction", 0.05)
        
        for crash in crashes:
            if balance <= 0:
                break
                
            bet = balance * bet_fraction
            
            if crash >= target:
                balance += bet * (target - 1)
            else:
                balance -= bet
    
    return max(0, balance)


def _calculate_mc_sharpe_ratio(outcomes: np.ndarray, initial: float) -> float:
    """Calculate Sharpe ratio from Monte Carlo outcomes."""
    returns = (outcomes - initial) / initial
    
    if len(returns) > 1 and np.std(returns) > 0:
        return float(np.mean(returns) / np.std(returns) * np.sqrt(252))  # Annualized
    return 0.0


def _create_outcome_histogram(outcomes: np.ndarray, bins: int = 50) -> Dict[str, List[float]]:
    """Create histogram data for outcome distribution."""
    hist, edges = np.histogram(outcomes, bins=bins)
    
    return {
        "counts": [int(c) for c in hist],
        "edges": [float(e) for e in edges],
        "bin_centers": [float((edges[i] + edges[i+1]) / 2) for i in range(len(edges)-1)]
    }


def _estimate_outcome_density(outcomes: np.ndarray) -> Dict[str, Any]:
    """Estimate probability density of outcomes."""
    from scipy import stats as scipy_stats
    
    kde = scipy_stats.gaussian_kde(outcomes)
    x_range = np.linspace(outcomes.min(), outcomes.max(), 100)
    density = kde(x_range)
    
    return {
        "x": [float(x) for x in x_range],
        "density": [float(d) for d in density],
        "mode": float(x_range[np.argmax(density)])
    }


def _analyze_simulation_risks(strategy_results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze risk metrics across all simulated strategies."""
    risk_metrics = {}
    
    for strategy_name, results in strategy_results.items():
        var_95 = results["percentiles"]["5th"]
        cvar_95 = results["mean_final_balance"] - var_95
        
        risk_metrics[strategy_name] = {
            "downside_risk": float(max(0, 1000 - var_95)),
            "upside_potential": float(results["percentiles"]["95th"] - 1000),
            "risk_reward_ratio": float(results["percentiles"]["95th"] - 1000) / float(max(1, 1000 - var_95)),
            "tail_risk": float(results["probability_of_ruin"])
        }
    
    return risk_metrics


def _find_optimal_mc_strategy(strategy_results: Dict[str, Any]) -> Dict[str, Any]:
    """Find optimal strategy based on Monte Carlo results."""
    # Multi-criteria optimization
    scores = {}
    
    for strategy_name, results in strategy_results.items():
        # Weighted score based on multiple factors
        profit_score = (results["mean_final_balance"] - 1000) / 1000
        risk_score = 1 - results["probability_of_ruin"] / 100
        consistency_score = 1 - results["std_deviation"] / results["mean_final_balance"]
        
        scores[strategy_name] = (
            0.4 * profit_score +
            0.4 * risk_score +
            0.2 * consistency_score
        )
    
    best_strategy = max(scores.items(), key=lambda x: x[1])
    
    return {
        "name": best_strategy[0],
        "score": float(best_strategy[1]),
        "expected_balance": strategy_results[best_strategy[0]]["mean_final_balance"],
        "risk_of_ruin": strategy_results[best_strategy[0]]["probability_of_ruin"]
    }


# Backtesting helper functions

def _run_strategy_backtest(
    crash_points: List[float], 
    timestamps: List[datetime], 
    strategy: Dict[str, Any], 
    initial_balance: float
) -> Dict[str, Any]:
    """Run a single strategy backtest."""
    balance = initial_balance
    balance_history = [balance]
    trades = []
    
    if strategy["type"] == "fixed":
        target = strategy["target"]
        bet_fraction = strategy["bet_fraction"]
        
        for i, crash in enumerate(crash_points):
            bet = balance * bet_fraction
            
            if crash >= target:
                profit = bet * (target - 1)
                balance += profit
                result = "win"
            else:
                balance -= bet
                result = "loss"
            
            trades.append({
                "index": i,
                "timestamp": timestamps[i].isoformat() if timestamps[i] else None,
                "crash_point": crash,
                "bet": bet,
                "target": target,
                "result": result,
                "balance": balance
            })
            
            balance_history.append(balance)
            
            if balance < initial_balance * 0.01:  # Stop if balance < 1%
                break
                
    elif strategy["type"] == "kelly":
        kelly_fraction = strategy["kelly_fraction"]
        
        for i, crash in enumerate(crash_points):
            # Dynamic Kelly betting based on recent performance
            if i >= 100:
                recent_crashes = crash_points[i-100:i]
                for target in [2.0, 3.0, 5.0]:
                    prob = sum(1 for c in recent_crashes if c >= target) / len(recent_crashes)
                    edge = (target - 1) * prob - (1 - prob)
                    
                    if edge > 0:
                        optimal_fraction = edge / (target - 1)
                        bet_fraction = min(kelly_fraction, optimal_fraction)
                        bet = balance * bet_fraction
                        
                        if crash >= target:
                            balance += bet * (target - 1)
                            result = "win"
                        else:
                            balance -= bet
                            result = "loss"
                        
                        trades.append({
                            "index": i,
                            "timestamp": timestamps[i].isoformat() if timestamps[i] else None,
                            "crash_point": crash,
                            "bet": bet,
                            "target": target,
                            "result": result,
                            "balance": balance
                        })
                        
                        break
            
            balance_history.append(balance)
    
    elif strategy["type"] == "momentum":
        lookback = strategy["lookback"]
        bet_fraction = strategy["bet_fraction"]
        
        for i, crash in enumerate(crash_points):
            if i >= lookback:
                recent = crash_points[i-lookback:i]
                momentum = np.mean(recent[-10:]) - np.mean(recent)
                
                # Bet more aggressively in positive momentum
                if momentum > 0:
                    target = 3.0
                    adjusted_bet_fraction = bet_fraction * 1.5
                else:
                    target = 1.5
                    adjusted_bet_fraction = bet_fraction * 0.5
                
                bet = balance * adjusted_bet_fraction
                
                if crash >= target:
                    balance += bet * (target - 1)
                    result = "win"
                else:
                    balance -= bet
                    result = "loss"
                
                trades.append({
                    "index": i,
                    "timestamp": timestamps[i].isoformat() if timestamps[i] else None,
                    "crash_point": crash,
                    "bet": bet,
                    "target": target,
                    "result": result,
                    "balance": balance,
                    "momentum": momentum
                })
            
            balance_history.append(balance)
    
    # Calculate performance metrics
    wins = sum(1 for t in trades if t["result"] == "win")
    losses = len(trades) - wins
    
    return {
        "final_balance": balance,
        "total_return": (balance - initial_balance) / initial_balance * 100,
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(trades) * 100 if trades else 0,
        "balance_history": balance_history,
        "max_balance": max(balance_history),
        "min_balance": min(balance_history),
        "trades": trades[-10:]  # Last 10 trades for inspection
    }


def _analyze_backtest_performance(
    performance: Dict[str, Any], 
    crash_points: List[float], 
    initial_balance: float
) -> Dict[str, Any]:
    """Analyze detailed performance metrics for a backtest."""
    balance_history = performance["balance_history"]
    
    # Calculate drawdowns
    peak = balance_history[0]
    max_drawdown = 0
    drawdown_duration = 0
    current_drawdown_duration = 0
    
    for balance in balance_history:
        if balance > peak:
            peak = balance
            current_drawdown_duration = 0
        else:
            drawdown = (peak - balance) / peak
            max_drawdown = max(max_drawdown, drawdown)
            current_drawdown_duration += 1
            drawdown_duration = max(drawdown_duration, current_drawdown_duration)
    
    # Calculate returns distribution
    returns = []
    for i in range(1, len(balance_history)):
        if balance_history[i-1] > 0:
            ret = (balance_history[i] - balance_history[i-1]) / balance_history[i-1]
            returns.append(ret)
    
    if returns:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        sortino_denominator = np.std([r for r in returns if r < 0]) if any(r < 0 for r in returns) else 0
        sortino = np.mean(returns) / sortino_denominator * np.sqrt(252) if sortino_denominator > 0 else 0
    else:
        sharpe = sortino = 0
    
    return {
        "max_drawdown": max_drawdown * 100,
        "max_drawdown_duration": drawdown_duration,
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "volatility": float(np.std(returns) * np.sqrt(252)) if returns else 0,
        "best_trade": max(performance["trades"], key=lambda x: x.get("balance", 0))["balance"] if performance["trades"] else 0,
        "worst_trade": min(performance["trades"], key=lambda x: x.get("balance", float('inf')))["balance"] if performance["trades"] else 0,
        "recovery_factor": performance["total_return"] / max_drawdown if max_drawdown > 0 else float('inf')
    }


def _compare_backtest_strategies(performances: Dict[str, Any], initial_balance: float) -> Dict[str, Any]:
    """Compare multiple strategy performances."""
    comparison = {}
    
    for name, perf in performances.items():
        comparison[name] = {
            "rank_by_return": 0,
            "rank_by_sharpe": 0,
            "rank_by_drawdown": 0,
            "rank_by_consistency": 0
        }
    
    # Rank by different metrics
    sorted_by_return = sorted(performances.items(), key=lambda x: x[1]["total_return"], reverse=True)
    sorted_by_win_rate = sorted(performances.items(), key=lambda x: x[1]["win_rate"], reverse=True)
    
    for i, (name, _) in enumerate(sorted_by_return):
        comparison[name]["rank_by_return"] = i + 1
    
    for i, (name, _) in enumerate(sorted_by_win_rate):
        comparison[name]["rank_by_win_rate"] = i + 1
    
    return comparison


def _find_best_return_strategy(performances: Dict[str, Any]) -> Dict[str, Any]:
    """Find strategy with best returns."""
    best = max(performances.items(), key=lambda x: x[1]["total_return"])
    return {
        "name": best[0],
        "total_return": best[1]["total_return"],
        "final_balance": best[1]["final_balance"]
    }


def _find_lowest_risk_strategy(performances: Dict[str, Any]) -> Dict[str, Any]:
    """Find strategy with lowest risk."""
    # Calculate risk score based on volatility and drawdown
    risk_scores = {}
    
    for name, perf in performances.items():
        balance_history = perf["balance_history"]
        returns = [(balance_history[i] - balance_history[i-1]) / balance_history[i-1] 
                  for i in range(1, len(balance_history)) if balance_history[i-1] > 0]
        
        volatility = np.std(returns) if returns else 0
        min_balance_ratio = perf["min_balance"] / perf["balance_history"][0]
        
        risk_scores[name] = volatility + (1 - min_balance_ratio)
    
    best = min(risk_scores.items(), key=lambda x: x[1])
    
    return {
        "name": best[0],
        "risk_score": best[1],
        "total_return": performances[best[0]]["total_return"]
    }


def _find_best_sharpe_strategy(performances: Dict[str, Any]) -> Dict[str, Any]:
    """Find strategy with best Sharpe ratio."""
    sharpe_ratios = {}
    
    for name, perf in performances.items():
        balance_history = perf["balance_history"]
        returns = [(balance_history[i] - balance_history[i-1]) / balance_history[i-1] 
                  for i in range(1, len(balance_history)) if balance_history[i-1] > 0]
        
        if returns and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
            sharpe_ratios[name] = sharpe
    
    if sharpe_ratios:
        best = max(sharpe_ratios.items(), key=lambda x: x[1])
        return {
            "name": best[0],
            "sharpe_ratio": best[1],
            "total_return": performances[best[0]]["total_return"]
        }
    
    return {"name": "None", "sharpe_ratio": 0, "total_return": 0}


def _find_most_consistent_strategy(performances: Dict[str, Any]) -> Dict[str, Any]:
    """Find most consistent strategy."""
    consistency_scores = {}
    
    for name, perf in performances.items():
        # Consistency based on win rate and low volatility
        balance_history = perf["balance_history"]
        returns = [(balance_history[i] - balance_history[i-1]) / balance_history[i-1] 
                  for i in range(1, len(balance_history)) if balance_history[i-1] > 0]
        
        if returns:
            volatility = np.std(returns)
            consistency = perf["win_rate"] / 100 * (1 / (1 + volatility))
            consistency_scores[name] = consistency
    
    if consistency_scores:
        best = max(consistency_scores.items(), key=lambda x: x[1])
        return {
            "name": best[0],
            "consistency_score": best[1],
            "win_rate": performances[best[0]]["win_rate"]
        }
    
    return {"name": "None", "consistency_score": 0, "win_rate": 0}


# Correlation analysis helper functions

def _interpret_correlation(correlation: float) -> str:
    """Interpret correlation coefficient."""
    abs_corr = abs(correlation)
    
    if abs_corr < 0.1:
        return "No correlation"
    elif abs_corr < 0.3:
        return "Weak correlation"
    elif abs_corr < 0.5:
        return "Moderate correlation"
    elif abs_corr < 0.7:
        return "Strong correlation"
    else:
        return "Very strong correlation"


def _calculate_transition_matrix(crash_points: List[float], ranges: List[Tuple[float, float]]) -> Dict[str, Any]:
    """Calculate transition probabilities between ranges."""
    n_ranges = len(ranges)
    transition_counts = np.zeros((n_ranges, n_ranges))
    
    # Assign each crash point to a range
    range_indices = []
    for cp in crash_points:
        for i, (min_val, max_val) in enumerate(ranges):
            if min_val <= cp < max_val:
                range_indices.append(i)
                break
    
    # Count transitions
    for i in range(len(range_indices) - 1):
        from_range = range_indices[i]
        to_range = range_indices[i + 1]
        transition_counts[from_range, to_range] += 1
    
    # Convert to probabilities
    transition_probs = np.zeros((n_ranges, n_ranges))
    for i in range(n_ranges):
        row_sum = transition_counts[i].sum()
        if row_sum > 0:
            transition_probs[i] = transition_counts[i] / row_sum
    
    # Format for output
    result = {}
    for i, range1 in enumerate(ranges):
        for j, range2 in enumerate(ranges):
            key = f"{range1[0]}-{range1[1]}x_to_{range2[0]}-{range2[1]}x"
            result[key] = {
                "probability": float(transition_probs[i, j] * 100),
                "count": int(transition_counts[i, j])
            }
    
    return result


def _detect_range_trend(range_crashes: List[float], all_crashes: List[float]) -> str:
    """Detect trend within a specific range."""
    if len(range_crashes) < 10:
        return "Insufficient data"
    
    # Find indices of range crashes in all crashes
    indices = []
    range_idx = 0
    for i, cp in enumerate(all_crashes):
        if range_idx < len(range_crashes) and cp == range_crashes[range_idx]:
            indices.append(i)
            range_idx += 1
    
    if len(indices) > 1:
        # Fit linear trend to indices
        trend = np.polyfit(range(len(indices)), indices, 1)[0]
        
        if trend < -0.5:
            return "Becoming more frequent"
        elif trend > 0.5:
            return "Becoming less frequent"
        else:
            return "Stable frequency"
    
    return "No clear trend"


def _generate_correlation_insights(correlation_data: Dict[str, Any]) -> List[str]:
    """Generate insights from correlation analysis."""
    insights = []
    
    # Check for strong correlations
    strong_correlations = []
    for key, value in correlation_data["range_correlations"].items():
        if abs(value["correlation"]) > 0.5:
            strong_correlations.append((key, value["correlation"]))
    
    if strong_correlations:
        insights.append(f"Found {len(strong_correlations)} strong correlations between ranges")
    
    # Check sequential patterns
    sequential_patterns = []
    for lag_key, lag_data in correlation_data["sequential_analysis"].items():
        for range_key, corr in lag_data.items():
            if abs(corr) > 0.1:
                sequential_patterns.append((lag_key, range_key, corr))
    
    if sequential_patterns:
        insights.append(f"Detected {len(sequential_patterns)} sequential dependencies")
    
    # Analyze transition probabilities
    high_prob_transitions = []
    for key, value in correlation_data["transition_probabilities"].items():
        if value["probability"] > 30:
            high_prob_transitions.append((key, value["probability"]))
    
    if high_prob_transitions:
        top_transition = max(high_prob_transitions, key=lambda x: x[1])
        insights.append(f"Highest transition probability: {top_transition[0]} at {top_transition[1]:.1f}%")
    
    if not insights:
        insights.append("No significant correlations or patterns detected")
    
    return insights


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
        
        # Get Bayesian probability updates
        result["bayesian_updates"] = calculate_bayesian_probability_updates(session, limit=limit)
        
        # Get Monte Carlo simulations
        result["monte_carlo_simulations"] = run_monte_carlo_simulations(session, num_simulations=1000)
        
        # Get strategy backtesting
        result["backtesting"] = backtest_strategies(session)
        
        # Get multiplier correlations
        result["correlations"] = calculate_multiplier_correlations(session, limit=limit)
        
        return result
    
    except Exception as e:
        logger.error(f"Error in combined statistical analysis: {str(e)}")
        raise