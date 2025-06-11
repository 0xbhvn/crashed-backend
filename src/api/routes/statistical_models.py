"""
Statistical models API routes.

This module provides REST API endpoints for advanced statistical analysis
including moving averages, volatility indicators, probability distributions,
and streak analysis.
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


@routes.get('/api/analytics/statistical-models/moving-averages')
async def get_moving_averages(request: web.Request) -> web.Response:
    """
    Get moving averages for crash points.
    
    Query Parameters:
    - windows: Comma-separated list of window sizes (default: 5,10,20)
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with moving averages data
    """
    try:
        # Parse query parameters
        windows_param = request.query.get('windows', '5,10,20')
        limit = int(request.query.get('limit', 1000))
        
        # Parse window sizes
        try:
            window_sizes = [int(w.strip()) for w in windows_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid window sizes format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if any(w <= 0 or w > 1000 for w in window_sizes):
            return web.json_response({"error": "Window sizes must be between 1 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate moving averages
            result = analytics.calculate_moving_averages(session, window_sizes, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in moving averages endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/volatility')
async def get_volatility_indicators(request: web.Request) -> web.Response:
    """
    Get volatility indicators including standard deviation and variance.
    
    Query Parameters:
    - windows: Comma-separated list of window sizes (default: 10,20,50)
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with volatility indicators data
    """
    try:
        # Parse query parameters
        windows_param = request.query.get('windows', '10,20,50')
        limit = int(request.query.get('limit', 1000))
        
        # Parse window sizes
        try:
            window_sizes = [int(w.strip()) for w in windows_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid window sizes format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if any(w <= 0 or w > 1000 for w in window_sizes):
            return web.json_response({"error": "Window sizes must be between 1 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Calculate volatility indicators
            result = analytics.calculate_volatility_indicators(session, window_sizes, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in volatility indicators endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/probability-distribution')
async def get_probability_distribution(request: web.Request) -> web.Response:
    """
    Get probability distribution analysis for crash point ranges.
    
    Query Parameters:
    - limit: Number of games to analyze (default: 10000)
    - ranges: Custom ranges in format "min1-max1,min2-max2" (optional)
    
    Returns:
    - JSON response with probability distribution data
    """
    try:
        # Parse query parameters
        limit = int(request.query.get('limit', 10000))
        ranges_param = request.query.get('ranges')
        
        # Validate limit
        if limit <= 0 or limit > 50000:
            return web.json_response({"error": "Limit must be between 1 and 50000"}, status=400)
        
        # Parse custom ranges if provided
        crash_point_ranges = None
        if ranges_param:
            try:
                ranges_list = []
                for range_str in ranges_param.split(','):
                    min_val, max_val = range_str.split('-')
                    min_val = float(min_val.strip())
                    max_val = float(max_val.strip()) if max_val.strip() != 'inf' else float('inf')
                    ranges_list.append((min_val, max_val))
                crash_point_ranges = ranges_list
            except ValueError:
                return web.json_response({"error": "Invalid ranges format. Use 'min1-max1,min2-max2'"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Analyze probability distribution
            result = analytics.analyze_probability_distribution(session, crash_point_ranges, limit)
            
            return web.json_response({
                "success": True,
                "data": result
            })
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error in probability distribution endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/streaks')
async def get_streak_analysis(request: web.Request) -> web.Response:
    """
    Get streak analysis for hot and cold streaks.
    
    Query Parameters:
    - threshold_high: Threshold for hot streaks (default: 5.0)
    - threshold_low: Threshold for cold streaks (default: 2.0)
    - min_length: Minimum streak length (default: 3)
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with streak analysis data
    """
    try:
        # Parse query parameters
        threshold_high = float(request.query.get('threshold_high', 5.0))
        threshold_low = float(request.query.get('threshold_low', 2.0))
        min_streak_length = int(request.query.get('min_length', 3))
        limit = int(request.query.get('limit', 1000))
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if threshold_high <= threshold_low:
            return web.json_response({"error": "High threshold must be greater than low threshold"}, status=400)
        
        if min_streak_length <= 0 or min_streak_length > 100:
            return web.json_response({"error": "Minimum streak length must be between 1 and 100"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Detect streaks
            result = analytics.detect_streaks(
                session, 
                threshold_high, 
                threshold_low, 
                min_streak_length, 
                limit
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
        logger.error(f"Error in streak analysis endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/combined')
async def get_combined_analysis(request: web.Request) -> web.Response:
    """
    Get combined statistical analysis including all statistical models.
    
    Query Parameters:
    - ma_windows: Moving average windows (default: 5,10,20)
    - vol_windows: Volatility windows (default: 10,20,50)
    - threshold_high: Hot streak threshold (default: 5.0)
    - threshold_low: Cold streak threshold (default: 2.0)
    - limit: Number of games to analyze (default: 1000)
    
    Returns:
    - JSON response with combined statistical analysis
    """
    try:
        # Parse query parameters
        ma_windows_param = request.query.get('ma_windows', '5,10,20')
        vol_windows_param = request.query.get('vol_windows', '10,20,50')
        threshold_high = float(request.query.get('threshold_high', 5.0))
        threshold_low = float(request.query.get('threshold_low', 2.0))
        limit = int(request.query.get('limit', 1000))
        
        # Parse window sizes
        try:
            ma_windows = [int(w.strip()) for w in ma_windows_param.split(',')]
            vol_windows = [int(w.strip()) for w in vol_windows_param.split(',')]
        except ValueError:
            return web.json_response({"error": "Invalid window sizes format"}, status=400)
        
        # Validate parameters
        if limit <= 0 or limit > 10000:
            return web.json_response({"error": "Limit must be between 1 and 10000"}, status=400)
        
        if threshold_high <= threshold_low:
            return web.json_response({"error": "High threshold must be greater than low threshold"}, status=400)
        
        if any(w <= 0 or w > 1000 for w in ma_windows + vol_windows):
            return web.json_response({"error": "Window sizes must be between 1 and 1000"}, status=400)
        
        # Get database session
        db = get_database()
        Session = sessionmaker(bind=db.engine)
        session = Session()
        
        try:
            # Get combined analysis
            result = analytics.get_combined_statistical_analysis(
                session,
                ma_windows=ma_windows,
                volatility_windows=vol_windows,
                streak_thresholds=(threshold_high, threshold_low),
                limit=limit
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
        logger.error(f"Error in combined analysis endpoint: {str(e)}")
        return web.json_response({"error": "Internal server error"}, status=500)


@routes.get('/api/analytics/statistical-models/health')
async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint for statistical models API."""
    return web.json_response({
        "success": True,
        "service": "statistical_models",
        "status": "healthy"
    })