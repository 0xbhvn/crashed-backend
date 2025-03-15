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
    - `value` (float): Minimum crash point value
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  - Response:

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
        "games_since": integer  // Number of games played since this matching game
      }
    }
    ```

  - Error Responses:
    - 400: Invalid value parameter
    - 404: No matching games found
    - 500: Internal server error

- **Last game with crash points == X floor value**
  - Endpoint: `/api/analytics/last-game/exact-floor/{value}`
  - Method: GET
  - Parameters:
    - `value` (int): Exact floor value to match
  - Headers:
    - `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')
  - Response:

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
        "games_since": integer  // Number of games played since this matching game
      }
    }
    ```

  - Error Responses:
    - 400: Invalid value parameter (must be integer)
    - 404: No matching games found
    - 500: Internal server error

- **Batch: Last games with crash points >= X values**
  - Endpoint: `/api/analytics/last-games/min-crash-points`
  - Method: POST
  - Request Body:

    ```json
    {
      "values": [float]  // List of minimum crash point values
    }
    ```

  - Response:

    ```json
    {
      "status": "success",
      "data": {
        "2.5": {  // The value being searched for
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
          "games_since": integer  // Number of games played since this matching game
        },
        "3.0": null,  // Example of value with no matching game
        // ... results for other values ...
      }
    }
    ```

- **Batch: Last games with crash points == X floor values**
  - Endpoint: `/api/analytics/last-games/exact-floors`
  - Method: POST
  - Request Body:

    ```json
    {
      "values": [integer]  // List of floor values
    }
    ```

  - Response:

    ```json
    {
      "status": "success",
      "data": {
        "2": {  // The floor value being searched for
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
          "games_since": integer  // Number of games played since this matching game
        },
        "3": null,  // Example of value with no matching game
        // ... results for other values ...
      }
    }
    ```

#### 2. Crash Point Occurrence Analysis [Pending]

These endpoints will analyze how frequently specific crash points occur:

- **Total occurrences of >= X crash point**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/min-crash-point/{value}`
    - Parameters:
      - `value` (float): Minimum crash point to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/min-crash-point/{value}/time`
    - Parameters:
      - `value` (float): Minimum crash point to count
      - `hours` (int, optional): Hours to look back (default: 1)

- **Total occurrences of == X floor crash point**
  - By game count:
    - Endpoint: `/api/analytics/occurrences/exact-floor/{value}`
    - Parameters:
      - `value` (int): Exact floor value to count
      - `limit` (int, optional): Number of games to analyze (default: 100)
  
  - By time duration:
    - Endpoint: `/api/analytics/occurrences/exact-floor/{value}/time`
    - Parameters:
      - `value` (int): Exact floor value to count
      - `hours` (int, optional): Hours to look back (default: 1)

#### 3. Interval Analysis [Pending]

These endpoints will analyze crash points in specific intervals:

- **Occurrences of >= X crash point in time intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-point/{value}`
  - Parameters:
    - `value` (float): Minimum crash point threshold
    - `interval_minutes` (int, optional): Size of each interval in minutes (default: 10)
    - `hours` (int, optional): Total hours to analyze (default: 24)

- **Occurrences of >= X crash point in game set intervals**
  - Endpoint: `/api/analytics/intervals/min-crash-point/{value}/game-sets`
  - Parameters:
    - `value` (float): Minimum crash point threshold
    - `games_per_set` (int, optional): Number of games in each set (default: 10)
    - `total_games` (int, optional): Total games to analyze (default: 1000)

#### 4. Non-occurrence Series Analysis [Pending]

- **Series of games without >= X crash point**
  - By game count:
    - Endpoint: `/api/analytics/series/without-min-crash-point/{value}`
    - Parameters:
      - `value` (float): Minimum crash point threshold
      - `limit` (int, optional): Number of games to analyze (default: 1000)
  
  - By time duration:
    - Endpoint: `/api/analytics/series/without-min-crash-point/{value}/time`
    - Parameters:
      - `value` (float): Minimum crash point threshold
      - `hours` (int, optional): Hours to look back (default: 24)

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

## Analytics API Documentation

### Crash Point Occurrence Analysis

#### Get Occurrences of Crash Points >= Value (By Games)

**HTTP Method**: GET  
**Endpoint**: `/api/analytics/occurrences/min-crash-point/{value}`

Retrieves the total occurrences of crash points greater than or equal to a specified value in the last N games.

**Path Parameters**:

- `value` (float): Minimum crash point value to analyze

**Query Parameters**:

- `limit` (int, optional): Number of games to analyze (default: 100)

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "count": 15,
        "total_games": 100,
        "percentage": 15.0,
        "first_game_time": "2024-03-20T10:00:00+05:30",
        "last_game_time": "2024-03-20T11:00:00+05:30"
    }
}
```

**Error Responses**:

- 400: Invalid parameters
- 500: Internal server error

#### Get Occurrences of Crash Points >= Value (By Time)

**HTTP Method**: GET  
**Endpoint**: `/api/analytics/occurrences/min-crash-point/{value}/time`

Retrieves the total occurrences of crash points greater than or equal to a specified value in the last N hours.

**Path Parameters**:

- `value` (float): Minimum crash point value to analyze

**Query Parameters**:

- `hours` (int, optional): Hours to look back (default: 1)

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "count": 8,
        "total_games": 50,
        "percentage": 16.0,
        "start_time": "2024-03-20T10:00:00+05:30",
        "end_time": "2024-03-20T11:00:00+05:30"
    }
}
```

**Error Responses**:

- 400: Invalid parameters
- 500: Internal server error

#### Get Occurrences of Exact Floor Value (By Time)

**HTTP Method**: GET  
**Endpoint**: `/api/analytics/occurrences/exact-floor/{value}/time`

Retrieves the total occurrences of an exact floor value in the last N hours.

**Path Parameters**:

- `value` (int): Exact floor value to analyze

**Query Parameters**:

- `hours` (int, optional): Hours to look back (default: 1)

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "count": 3,
        "total_games": 50,
        "percentage": 6.0,
        "start_time": "2024-03-20T10:00:00+05:30",
        "end_time": "2024-03-20T11:00:00+05:30"
    }
}
```

**Error Responses**:

- 400: Invalid parameters
- 500: Internal server error

#### Get Occurrences of Multiple Crash Points >= Values (By Games)

**HTTP Method**: POST  
**Endpoint**: `/api/analytics/occurrences/min-crash-points`

Retrieves the total occurrences of crash points greater than or equal to each specified value in the last N games.

**Request Body**:

```json
{
    "values": [2.0, 3.0, 5.0],  // List of minimum crash point values
    "limit": 100  // Optional, number of games to analyze (default: 100)
}
```

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "2.0": {
            "count": 25,
            "total_games": 100,
            "percentage": 25.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        },
        "3.0": {
            "count": 15,
            "total_games": 100,
            "percentage": 15.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        },
        "5.0": {
            "count": 5,
            "total_games": 100,
            "percentage": 5.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        }
    }
}
```

**Error Responses**:

- 400: Invalid request body or parameters
- 500: Internal server error

#### Get Occurrences of Multiple Crash Points >= Values (By Time)

**HTTP Method**: POST  
**Endpoint**: `/api/analytics/occurrences/min-crash-points/time`

Retrieves the total occurrences of crash points greater than or equal to each specified value in the last N hours.

**Request Body**:

```json
{
    "values": [2.0, 3.0, 5.0],  // List of minimum crash point values
    "hours": 1  // Optional, hours to look back (default: 1)
}
```

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "2.0": {
            "count": 12,
            "total_games": 50,
            "percentage": 24.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        },
        "3.0": {
            "count": 8,
            "total_games": 50,
            "percentage": 16.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        },
        "5.0": {
            "count": 3,
            "total_games": 50,
            "percentage": 6.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        }
    }
}
```

**Error Responses**:

- 400: Invalid request body or parameters
- 500: Internal server error

#### Get Occurrences of Multiple Exact Floor Values (By Games)

**HTTP Method**: POST  
**Endpoint**: `/api/analytics/occurrences/exact-floors`

Retrieves the total occurrences of exact floor values in the last N games.

**Request Body**:

```json
{
    "values": [2, 3, 5],  // List of floor values
    "limit": 100  // Optional, number of games to analyze (default: 100)
}
```

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "2": {
            "count": 20,
            "total_games": 100,
            "percentage": 20.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        },
        "3": {
            "count": 10,
            "total_games": 100,
            "percentage": 10.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        },
        "5": {
            "count": 5,
            "total_games": 100,
            "percentage": 5.0,
            "first_game_time": "2024-03-20T10:00:00+05:30",
            "last_game_time": "2024-03-20T11:00:00+05:30"
        }
    }
}
```

**Error Responses**:

- 400: Invalid request body or parameters
- 500: Internal server error

#### Get Occurrences of Multiple Exact Floor Values (By Time)

**HTTP Method**: POST  
**Endpoint**: `/api/analytics/occurrences/exact-floors/time`

Retrieves the total occurrences of exact floor values in the last N hours.

**Request Body**:

```json
{
    "values": [2, 3, 5],  // List of floor values
    "hours": 1  // Optional, hours to look back (default: 1)
}
```

**Headers**:

- `X-Timezone` (optional): Timezone for datetime values (e.g., 'Asia/Kolkata')

**Response Structure**:

```json
{
    "status": "success",
    "data": {
        "2": {
            "count": 10,
            "total_games": 50,
            "percentage": 20.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        },
        "3": {
            "count": 5,
            "total_games": 50,
            "percentage": 10.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        },
        "5": {
            "count": 2,
            "total_games": 50,
            "percentage": 4.0,
            "start_time": "2024-03-20T10:00:00+05:30",
            "end_time": "2024-03-20T11:00:00+05:30"
        }
    }
}
```

**Error Responses**:

- 400: Invalid request body or parameters
- 500: Internal server error
