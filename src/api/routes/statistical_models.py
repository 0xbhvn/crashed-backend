"""
Enhanced statistical models API routes.

This module provides REST API endpoints for advanced statistical analysis
specifically designed for BC.game crash mechanics:
- Risk-adjusted performance metrics (Sharpe ratio, drawdown analysis, VaR)
- Pattern recognition and anomaly detection
- Expected value calculations for different strategies
- Market psychology indicators
"""

import logging
from aiohttp import web
from sqlalchemy.orm import sessionmaker
from typing import List, Tuple

from ...db.engine import get_database
from .. import analytics

# Configure logging
logger = logging.getLogger(__name__)

# Create route table
routes = web.RouteTableDef()


@routes.get('/api/analytics/statistical-models/risk-adjusted-metrics')
async def get_risk_adjusted_metrics(request: web.Request) -> web.Response:
    """
    Get risk-adjusted performance metrics for different betting strategies.
    
    Query Parameters:
    - targets: Comma-separated target multipliers (default: "2,3,5,10")
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with risk-adjusted metrics
    """
    try:
        # Parse query parameters
        targets_param = request.query.get('targets', '2,3,5,10')
        limit = int(request.query.get('limit', 1000))
        
        # Parse target multipliers
        try:
            target_multipliers = [float(t.strip()) for t in targets_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid target multipliers format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if any(t <= 0 or t > 1000 for t in target_multipliers):
            return web.json_response({"error": "Target multipliers must be between 1 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate risk-adjusted metrics
            result = analytics.calculate_risk_adjusted_metrics(session, target_multipliers, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in risk-adjusted metrics endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/pattern-analysis')
async def get_pattern_analysis(request: web.Request) -> web.Response:
    """
    Get pattern recognition and anomaly detection analysis.
    
    Query Parameters:
    - limit: Number of games to analyze (default: 1000)
    - anomaly_threshold: Z-score threshold for anomaly detection (default: 3.0)
    
    Returns:
    - JSON response with pattern and anomaly analysis
    """
    try:
        # Parse query parameters
        limit = int(request.query.get('limit', 1000))
        anomaly_threshold = float(request.query.get('anomaly_threshold', 3.0))
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if anomaly_threshold <= 0 or anomaly_threshold > 10:
            return web.json_response({"error": "Anomaly threshold must be between 0 and 10"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Detect patterns and anomalies
            result = analytics.detect_patterns_and_anomalies(session, limit, anomaly_threshold)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in pattern analysis endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/expected-values')
async def get_expected_values(request: web.Request) -> web.Response:
    """
    Get expected value analysis for different target multipliers.
    
    Query Parameters:
    - targets: Comma-separated target multipliers (default: "1.5,2,3,5,10,20,50,100")
    - limit: Number of games to analyze (default: 10000)
    
    Returns:
    - JSON response with expected value analysis
    """
    try:
        # Parse query parameters
        targets_param = request.query.get('targets', '1.5,2,3,5,10,20,50,100')
        limit = int(request.query.get('limit', 10000))
        
        # Parse target multipliers
        try:
            target_multipliers = [float(t.strip()) for t in targets_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid target multipliers format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 50000:
            return web.json_response({"error": "Limit must be between 1 and 50000"}, status=400)
        
        if any(t <= 0 or t > 10000 for t in target_multipliers):
            return web.json_response({"error": "Target multipliers must be between 1 and 10000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate expected values
            result = analytics.calculate_expected_values(session, target_multipliers, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in expected values endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/market-psychology')
async def get_market_psychology(request: web.Request) -> web.Response:
    """
    Get market psychology indicators adapted for crash games.
    
    Query Parameters:
    - limit: Number of games to analyze (default: 1000)
    - short_window: Short-term window for indicators (default: 50)
    - long_window: Long-term window for indicators (default: 200)
    
    Returns:
    - JSON response with market psychology indicators
    """
    try:
        # Parse query parameters
        limit = int(request.query.get('limit', 1000))
        short_window = int(request.query.get('short_window', 50))
        long_window = int(request.query.get('long_window', 200))
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if short_window <= 0 or long_window <= 0:
            return web.json_response({"error": "Window sizes must be positive"}, status=400)
        
        if short_window >= long_window:
            return web.json_response({"error": "Short window must be less than long window"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate market psychology indicators
            result = analytics.calculate_market_psychology_indicators(
                session, 
                limit,
                short_window,
                long_window
            )
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except ValueError as e:
        return web.json_response({"error": f"Invalid parameter value: {str(e)}"}, status=400)
    except Exception as e:
        logger.error(f"Error in market psychology endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/combined')
async def get_combined_analysis(request: web.Request) -> web.Response:
    """
    Get comprehensive statistical analysis including all enhanced models.
    
    Query Parameters:
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with all statistical analyses
    """
    try:
        # Parse query parameters
        limit = int(request.query.get('limit', 1000))
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Get combined analysis
            result = analytics.get_combined_statistical_analysis(session, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in combined analysis endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/bayesian-updates')
async def get_bayesian_updates(request: web.Request) -> web.Response:
    """
    Get Bayesian probability updates for crash game outcomes.
    
    Query Parameters:
    - targets: Comma-separated target multipliers (default: "2,3,5,10")
    - window_size: Size of rolling window for updates (default: 100)
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with Bayesian probability estimates
    """
    try:
        # Parse query parameters
        targets_param = request.query.get('targets', '2,3,5,10')
        window_size = int(request.query.get('window_size', 100))
        limit = int(request.query.get('limit', 1000))
        
        # Parse target multipliers
        try:
            target_multipliers = [float(t.strip()) for t in targets_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid target multipliers format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if window_size <= 10 or window_size > 1000:
            return web.json_response({"error": "Window size must be between 10 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate Bayesian updates
            result = analytics.calculate_bayesian_probability_updates(
                session, target_multipliers, window_size, limit
            )
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in Bayesian updates endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/monte-carlo')
async def get_monte_carlo_simulations(request: web.Request) -> web.Response:
    """
    Run Monte Carlo simulations for strategy evaluation.
    
    Query Parameters:
    - num_simulations: Number of simulation runs (default: 1000, max: 10000)
    - games_per_simulation: Games per simulation (default: 100)
    
    Returns:
    - JSON response with simulation results
    """
    try:
        # Parse query parameters
        num_simulations = int(request.query.get('num_simulations', 1000))
        games_per_simulation = int(request.query.get('games_per_simulation', 100))
        
        # Validate parameters
        if num_simulations <= 0 or num_simulations > 10000:
            return web.json_response({"error": "Number of simulations must be between 1 and 10000"}, status=400)
        
        if games_per_simulation <= 0 or games_per_simulation > 1000:
            return web.json_response({"error": "Games per simulation must be between 1 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Run Monte Carlo simulations
            result = analytics.run_monte_carlo_simulations(
                session, num_simulations, games_per_simulation
            )
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in Monte Carlo simulations endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/backtesting')
async def get_backtesting_results(request: web.Request) -> web.Response:
    """
    Backtest different betting strategies on historical data.
    
    Query Parameters:
    - start_date: Start date for backtesting (ISO format)
    - end_date: End date for backtesting (ISO format)
    - initial_balance: Starting balance (default: 1000)
    
    Returns:
    - JSON response with backtest results
    """
    try:
        # Parse query parameters
        from datetime import datetime
        
        start_date_str = request.query.get('start_date')
        end_date_str = request.query.get('end_date')
        initial_balance = float(request.query.get('initial_balance', 1000))
        
        # Parse dates if provided
        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None
        
        # Validate parameters
        if initial_balance <= 0 or initial_balance > 1000000:
            return web.json_response({"error": "Initial balance must be between 1 and 1000000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Run backtesting
            result = analytics.backtest_strategies(
                session, None, start_date, end_date, initial_balance
            )
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except ValueError as e:
        return web.json_response({"error": f"Invalid date format: {str(e)}"}, status=400)
    except Exception as e:
        logger.error(f"Error in backtesting endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/correlations')
async def get_multiplier_correlations(request: web.Request) -> web.Response:
    """
    Analyze correlations between different multiplier ranges.
    
    Query Parameters:
    - limit: Number of games to analyze (default: 5000)
    
    Returns:
    - JSON response with correlation analysis
    """
    try:
        # Parse query parameters
        limit = int(request.query.get('limit', 5000))
        
        # Validate parameters
        if limit <= 0 or limit > 50000:
            return web.json_response({"error": "Limit must be between 1 and 50000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate correlations
            result = analytics.calculate_multiplier_correlations(session, None, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in correlations endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/health')
async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint for statistical models API."""
    return web.json_response({
        "success": True,
        "service": "statistical_models",
        "status": "healthy"
    })


# Legacy endpoints for backward compatibility

@routes.get('/api/analytics/statistical-models/moving-averages')
async def get_moving_averages_legacy(request: web.Request) -> web.Response:
    """Legacy endpoint - redirects to risk-adjusted metrics."""
    return await get_risk_adjusted_metrics(request)


@routes.get('/api/analytics/statistical-models/volatility')
async def get_volatility_legacy(request: web.Request) -> web.Response:
    """Legacy endpoint - redirects to pattern analysis."""
    return await get_pattern_analysis(request)


@routes.get('/api/analytics/statistical-models/probability-distribution')
async def get_probability_distribution_legacy(request: web.Request) -> web.Response:
    """Legacy endpoint - redirects to expected values."""
    return await get_expected_values(request)


@routes.get('/api/analytics/statistical-models/streaks')
async def get_streaks_legacy(request: web.Request) -> web.Response:
    """Legacy endpoint - returns deprecation notice."""
    return web.json_response({
        "error": "This endpoint has been deprecated. Please use /api/analytics/series endpoints for streak analysis.",
        "redirect_to": "/api/analytics/series/without-min-crash-point",
        "success": False
    }, status=301)