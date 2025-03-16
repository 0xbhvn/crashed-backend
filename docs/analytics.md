# BC Crash Game Analytics

## Overview

This document outlines the analytics features for the BC Crash Game monitoring system. These analytics will help users identify patterns, track performance, and make data-driven decisions based on game outcomes.

## Design Philosophy

Based on the existing codebase architecture and the specific requirements, we'll implement analytics as API endpoints that compute results on-demand rather than creating separate database models for each analytic. This approach has several advantages:

1. **Simplicity**: Avoids creating and maintaining numerous database models
2. **Flexibility**: Makes it easier to modify analytics or add new ones
3. **Performance**: For time-sensitive analytics, querying the existing data may be more efficient than maintaining additional tables
4. **Maintainability**: Reduces database migration complexity

## Analytics Features

### Core Analytics

#### 1. Last Game With Crash Points [Done]

These endpoints will find the most recent game that meets specific crash point criteria:

- **Last game with crash points >= X value**
  - Endpoint: `/api/analytics/last-game/min-crash-point/{value}`
  - Method: GET
  - Parameters:
    - `value` (float): Minimum crash point to count
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Last game with crash points == X floor value**
  - Endpoint: `/api/analytics/last-game/exact-floor/{value}`
  - Method: GET
  - Parameters:
    - `value` (int): Exact floor value to match
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Last games with crash points >= X values**
  - Endpoint: `/api/analytics/last-games/min-crash-points`
  - Method: POST
  - Request Body:
    - `values` (List[float]): List of minimum crash point values
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Last games with crash points == X floor values**
  - Endpoint: `/api/analytics/last-games/exact-floors`
  - Method: POST
  - Request Body:
    - `values` (List[int]): List of floor values
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

Single value endpoints return:

```json
{
    "status": "success",
    "data": {
        "game": {
            "gameId": "string",
            "hashValue": "string",
            "crashPoint": float,
            "calculatedPoint": float,
            "crashedFloor": integer,
            "endTime": "datetime",
            "prepareTime": "datetime",
            "beginTime": "datetime"
        },
        "games_since": integer
    }
}
```

Batch endpoints return:

```json
{
    "status": "success",
    "data": {
        "2.5": {
            "game": {
                "gameId": "string",
                "hashValue": "string",
                "crashPoint": float,
                "calculatedPoint": float,
                "crashedFloor": integer,
                "endTime": "datetime",
                "prepareTime": "datetime",
                "beginTime": "datetime"
            },
            "games_since": integer
        },
        "3.0": null
    }
}
```

Error Responses:

- 400: Invalid parameters or request body
- 404: No matching games found
- 500: Internal server error

#### 2. Crash Point Occurrence Analysis [Done]

These endpoints will analyze how frequently specific crash points occur:

- **Total occurrences of >= X crash point**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/min-crash-point/{value}`
    - Parameters:
      - `value` (float): Minimum crash point to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/min-crash-point/{value}/time`
    - Parameters:
      - `value` (float): Minimum crash point to count
      - `hours` (int, optional): Hours to look back (default: 1)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Total occurrences of exact floor value**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/exact-floor/{value}`
    - Parameters:
      - `value` (int): Exact floor value to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/exact-floor/{value}/time`
    - Parameters:
      - `value` (int): Exact floor value to count
      - `hours` (int, optional): Hours to look back (default: 1)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Total occurrences of >= X crash points**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/min-crash-points`
    - Request Body:
      - `values` (List[float]): List of minimum crash points to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/min-crash-points/time`
    - Request Body:
      - `values` (List[float]): List of minimum crash points to count
      - `hours` (int, optional): Hours to look back (default: 1)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Total occurrences of exact floor values**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/exact-floors`
    - Request Body:
      - `values` (List[int]): List of floor values to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/exact-floors/time`
    - Request Body:
      - `values` (List[int]): List of floor values to count
      - `hours` (int, optional): Hours to look back (default: 1)
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

Each endpoint returns:

```json
{
    "status": "success",
    "data": {
        "count": 15,
        "total_games": 100,
        "percentage": 15.0,
        "first_game_time/start_time": "2024-03-20T10:00:00+05:30",
        "last_game_time/end_time": "2024-03-20T11:00:00+05:30"
    }
}
```

For batch endpoints, the response data will be a map of values to their respective statistics:

```json
{
    "status": "success",
    "data": {
        "2.0": {
            "count": 25,
            "total_games": 100,
            "percentage": 25.0,
            "first_game_time/start_time": "2024-03-20T10:00:00+05:30",
            "last_game_time/end_time": "2024-03-20T11:00:00+05:30"
        },
        "3.0": {
            "count": 15,
            "total_games": 100,
            "percentage": 15.0,
            "first_game_time/start_time": "2024-03-20T10:00:00+05:30",
            "last_game_time/end_time": "2024-03-20T11:00:00+05:30"
        }
    }
}
```

Error Responses:

- 400: Invalid parameters or request body
- 500: Internal server error

#### 3. Non-occurrence Series Analysis [Done]

- **Series of games without >= X crash point**
  - By game count:
    - Endpoint: `/api/analytics/series/without-min-crash-point/{value}`
    - Method: GET
    - Parameters:
      - `value` (float): Minimum crash point threshold
      - `limit` (int, optional): Number of games to analyze (default: 1000)
      - `sort_by` (string, optional): How to sort results - 'time' (default) or 'length'
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  
  - By time duration:
    - Endpoint: `/api/analytics/series/without-min-crash-point/{value}/time`
    - Method: GET
    - Parameters:
      - `value` (float): Minimum crash point threshold
      - `hours` (int, optional): Hours to look back (default: 24)
      - `sort_by` (string, optional): How to sort results - 'time' (default) or 'length'
    - Headers:
      - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

Both endpoints return:

```json
{
    "status": "success",
    "data": [
        {
            "start_game_id": "string",
            "start_time": "datetime",
            "end_game_id": "string",
            "end_time": "datetime",
            "length": integer
        },
        // More series (if any)...
    ]
}
```

By default, the results are sorted by time (most recent first). If `sort_by=length` is specified, the results will be sorted by series length (longest first). Each series represents a consecutive set of games where the crash point was below the specified threshold value.

Error Responses:

- 400: Invalid parameters
- 500: Internal server error

#### 4. Interval Analysis [Pending]

These endpoints will analyze crash points in specific intervals:

- **Occurrences of >= X crash point in time intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-point/{value}`
  - Method: GET
  - Parameters:
    - `value` (float): Minimum crash point threshold
    - `interval_minutes` (int, optional): Size of each interval in minutes (default: 10)
    - `hours` (int, optional): Total hours to analyze (default: 24)
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Occurrences of >= X crash point in game set intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-point/{value}/game-sets`
  - Method: GET
  - Parameters:
    - `value` (float): Minimum crash point threshold
    - `games_per_set` (int, optional): Number of games in each set (default: 10)
    - `total_games` (int, optional): Total games to analyze (default: 1000)
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Occurrences of >= X crash points in time intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-points`
  - Method: POST
  - Request Body:
    - `values` (List[float]): List of minimum crash point thresholds
    - `interval_minutes` (int, optional): Size of each interval in minutes (default: 10)
    - `hours` (int, optional): Total hours to analyze (default: 24)
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

- **Batch: Occurrences of >= X crash points in game set intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-points/game-sets`
  - Method: POST
  - Request Body:
    - `values` (List[float]): List of minimum crash point thresholds
    - `games_per_set` (int, optional): Number of games in each set (default: 10)
    - `total_games` (int, optional): Total games to analyze (default: 1000)
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

Time-based interval endpoints return:

```json
{
    "status": "success",
    "data": [
        {
            "interval_start": "datetime",
            "interval_end": "datetime",
            "count": integer,
            "total_games": integer,
            "percentage": float
        },
        // More intervals...
    ]
}
```

Game-set interval endpoints return:

```json
{
    "status": "success",
    "data": [
        {
            "set_number": integer,
            "start_game": "string",
            "end_game": "string",
            "count": integer,
            "total_games": integer,
            "percentage": float,
            "start_time": "datetime",
            "end_time": "datetime"
        },
        // More sets...
    ]
}
```

Batch time-based interval endpoints return:

```json
{
    "status": "success",
    "data": {
        "2.0": [
            {
                "interval_start": "datetime",
                "interval_end": "datetime",
                "count": integer,
                "total_games": integer,
                "percentage": float
            },
            // More intervals...
        ],
        "3.0": [
            // Intervals for 3.0...
        ]
    }
}
```

Batch game-set interval endpoints return:

```json
{
    "status": "success",
    "data": {
        "2.0": [
            {
                "set_number": integer,
                "start_game": "string",
                "end_game": "string",
                "count": integer,
                "total_games": integer, 
                "percentage": float,
                "start_time": "datetime",
                "end_time": "datetime"
            },
            // More sets...
        ],
        "3.0": [
            // Sets for 3.0...
        ]
    }
}
```

Error Responses:

- 400: Invalid parameters or request body
- 500: Internal server error

### Additional Analytics

#### 5. Distribution Analysis [Pending]

- **Crash Point Distribution**
  - Endpoint: `/api/analytics/distribution`
  - Parameters:
    - `bucket_size` (float, optional): Size of distribution buckets (default: 0.5)
    - `limit` (int, optional): Number of games to analyze (default: 1000)
  
- **Floor Value Distribution**
  - Endpoint: `/api/analytics/floor-distribution`
  - Parameters:
    - `limit` (int, optional): Number of games to analyze (default: 1000)

#### 6. Streak Analysis [Pending]

- **Current Streak of Low/High Crash Points**
  - Endpoint: `/api/analytics/streak/current`
  - Parameters:
    - `threshold` (float, optional): Threshold defining low/high (default: 2.0)

- **Longest Streaks**
  - Endpoint: `/api/analytics/streak/longest`
  - Parameters:
    - `threshold` (float, optional): Threshold defining low/high (default: 2.0)
    - `limit` (int, optional): Number of games to analyze (default: 1000)

#### 7. Time-Based Patterns [Pending]

- **Hourly/Daily Averages**
  - Endpoint: `/api/analytics/time-pattern/average`
  - Parameters:
    - `grouping` (string, optional): Group by "hour" or "day" (default: "hour")
    - `days` (int, optional): Days to look back (default: 7)

#### 8. Volatility Metrics [Pending]

- **Crash Point Volatility**
  - Endpoint: `/api/analytics/volatility`
  - Parameters:
    - `window_size` (int, optional): Size of moving window (default: 100)
    - `limit` (int, optional): Number of games to analyze (default: 1000)

## Implementation Plan

### 1. Create Analytics Module

Create a new module at `src/api/analytics.py` to contain all analytics logic. This module will implement functions for each analytic that can be called from API route handlers.

### 2. Define API Routes

Add new routes to `src/api/routes.py` that map to the analytics functions. These routes will follow the pattern described above.

### 3. Implement Core Database Queries

Implement efficient database queries that can be reused across different analytics functions. These should leverage the existing SQLAlchemy models and include appropriate indexing strategies.

### 4. Add Caching (Optional)

Implement a simple caching mechanism for expensive queries, with configurable time-to-live (TTL) values based on the nature of each analytic.

### 5. Add Documentation

Update the API documentation to include all new analytics endpoints, their parameters, and example responses.

## Database Considerations

Rather than creating new database models for each analytic, we will:

1. Ensure the `CrashGame` model has appropriate indexes for efficient querying (we already have indexes on `crash_point`, `begin_time`, and `end_time`)
2. Use SQLAlchemy's query capabilities to efficiently compute analytics on-demand
3. Consider adding a simple query cache for frequently requested analytics with short TTLs

This approach balances simplicity, performance, and flexibility while avoiding the overhead of additional database models and migrations.

## Next Steps

1. Implement the analytics module with the core functions
2. Add API routes for each analytic
3. Add tests to ensure accuracy of calculations
4. Add documentation for each endpoint
5. Monitor performance and optimize as needed
