# Crash Monitor API Examples

This document provides examples of using the Crash Monitor API with curl requests.

## Table of Contents

- [Health Check](#health-check)
- [Games](#games)
- [Intervals](#intervals)
- [Last Games](#last-games)
- [Occurrences](#occurrences)
- [Series](#series)

## Health Check

```bash
# Check if the API is running
curl -X GET "http://localhost:3000/" | jq .
```

## Games

```bash
# Get games with pagination (default: page 1, 10 items per page)
curl -X GET "http://localhost:3000/api/games" | jq .

# Get games with pagination (page 2, 20 items per page)
curl -X GET "http://localhost:3000/api/games?page=2&per_page=20" | jq .

# Get games with timezone conversion
curl -X GET "http://localhost:3000/api/games" -H "X-Timezone: America/New_York" | jq .

# Get a specific game by ID
curl -X GET "http://localhost:3000/api/games/7962298" | jq .

# Get a specific game by ID with timezone conversion
curl -X GET "http://localhost:3000/api/games/7962298" -H "X-Timezone: America/New_York" | jq .
```

## Intervals

```bash
# Get occurrences of crash points >= 10 in 10-minute intervals over 24 hours
curl -X GET "http://localhost:3000/api/analytics/intervals/min-crash-point/10" | jq .

# Get occurrences of crash points >= 10 in 15-minute intervals over 48 hours
curl -X GET "http://localhost:3000/api/analytics/intervals/min-crash-point/10?interval_minutes=15&hours=48" | jq .

# Get occurrences of crash points >= 10 in sets of 10 games over last 1000 games
curl -X GET "http://localhost:3000/api/analytics/intervals/min-crash-point/10/game-sets" | jq .

# Get occurrences of crash points >= 10 in sets of 20 games over last 2000 games
curl -X GET "http://localhost:3000/api/analytics/intervals/min-crash-point/10/game-sets?games_per_set=20&total_games=2000" | jq .

# Get occurrences of multiple crash points in time intervals (batch request)
curl -X POST "http://localhost:3000/api/analytics/intervals/min-crash-points" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [2, 5, 10, 20],
    "interval_minutes": 15,
    "hours": 24
  }' | jq .

# Get occurrences of multiple crash points in game sets (batch request)
curl -X POST "http://localhost:3000/api/analytics/intervals/min-crash-points/game-sets" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [2, 5, 10, 20],
    "games_per_set": 20,
    "total_games": 1000
  }' | jq .
```

## Last Games

```bash
# Get the most recent game with a crash point >= 10
curl -X GET "http://localhost:3000/api/analytics/last-game/min-crash-point/10" | jq .

# Get the most recent game with a crash point floor exactly 10
curl -X GET "http://localhost:3000/api/analytics/last-game/exact-floor/10" | jq .

# Get the most recent game with a crash point <= 2
curl -X GET "http://localhost:3000/api/analytics/last-game/max-crash-point/2" | jq .

# Get the most recent games with crash points >= specified values (batch)
curl -X POST "http://localhost:3000/api/analytics/last-games/min-crash-points" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [2, 5, 10, 20]
  }' | jq .

# Get the most recent games with crash point floors exactly matching specified values (batch)
curl -X POST "http://localhost:3000/api/analytics/last-games/exact-floors" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [1, 2, 5, 10]
  }' | jq .

# Get the most recent games with crash points <= specified values (batch)
curl -X POST "http://localhost:3000/api/analytics/last-games/max-crash-points" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [1.5, 2, 5]
  }' | jq .

# Get the 10 most recent games with crash points >= 10
curl -X GET "http://localhost:3000/api/analytics/last-games/min-crash-point/10" | jq .

# Get the 20 most recent games with crash points >= 10
curl -X GET "http://localhost:3000/api/analytics/last-games/min-crash-point/10?limit=20" | jq .

# Get the 10 most recent games with crash points <= 2
curl -X GET "http://localhost:3000/api/analytics/last-games/max-crash-point/2" | jq .

# Get the 10 most recent games with crash point floor exactly 5
curl -X GET "http://localhost:3000/api/analytics/last-games/exact-floor/5" | jq .
```

## Occurrences

```bash
# Get occurrences of crash points >= 10 in the last 100 games
curl -X GET "http://localhost:3000/api/analytics/occurrences/min-crash-point/10" | jq .

# Get occurrences of crash points >= 10 in the last 200 games
curl -X GET "http://localhost:3000/api/analytics/occurrences/min-crash-point/10?games=200" | jq .

# Get occurrences of crash points >= 10 in the last 1 hour
curl -X GET "http://localhost:3000/api/analytics/occurrences/min-crash-point/10?by_time=true" | jq .

# Get occurrences of crash points >= 10 in the last 3 hours
curl -X GET "http://localhost:3000/api/analytics/occurrences/min-crash-point/10?by_time=true&hours=3" | jq .

# Get occurrences of crash points <= 2 in the last 100 games
curl -X GET "http://localhost:3000/api/analytics/occurrences/max-crash-point/2" | jq .

# Get occurrences of crash points <= 2 in the last 1 hour
curl -X GET "http://localhost:3000/api/analytics/occurrences/max-crash-point/2?by_time=true" | jq .

# Get occurrences of floor value exactly 5 in the last 100 games
curl -X GET "http://localhost:3000/api/analytics/occurrences/exact-floor/5" | jq .

# Get occurrences of floor value exactly 5 in the last 2 hours
curl -X GET "http://localhost:3000/api/analytics/occurrences/exact-floor/5?by_time=true&hours=2" | jq .

# Get occurrences of multiple minimum crash points (batch)
curl -X POST "http://localhost:3000/api/analytics/occurrences/min-crash-points/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [2, 5, 10, 20],
    "games": 200,
    "by_time": false,
    "comparison": true
  }' | jq .

# Get occurrences of multiple minimum crash points by time (batch)
curl -X POST "http://localhost:3000/api/analytics/occurrences/min-crash-points/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [2, 5, 10, 20],
    "hours": 3,
    "by_time": true,
    "comparison": true
  }' | jq .

# Get occurrences of multiple floor values (batch)
curl -X POST "http://localhost:3000/api/analytics/occurrences/exact-floors/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [1, 2, 5, 10],
    "games": 200,
    "comparison": true
  }' | jq .

# Get occurrences of multiple maximum crash points (batch)
curl -X POST "http://localhost:3000/api/analytics/occurrences/max-crash-points/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "values": [1.5, 2, 5],
    "games": 200,
    "comparison": true
  }' | jq .
```

## Series

```bash
# Get series of games without crash points >= 10 in the last 1000 games
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10" | jq .

# Get series of games without crash points >= 10 in the last 2000 games, sorted by series length
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10?limit=2000&sort_by=length" | jq .

# Get series of games without crash points >= 10 in the last 24 hours
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10/time" | jq .

# Get series of games without crash points >= 10 in the last 48 hours, sorted by series length
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10/time?hours=48&sort_by=length" | jq .

# Get series with timezone conversion
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10" -H "X-Timezone: America/New_York" | jq .
```

## Using the X-Timezone Header

All endpoints support the `X-Timezone` header for converting datetime values to a specific timezone:

```bash
# Example with timezone
curl -X GET "http://localhost:3000/api/analytics/series/without-min-crash-point/10" \
  -H "X-Timezone: America/New_York" | jq .
```

Common timezone values:

- `UTC`: Coordinated Universal Time
- `America/New_York`: Eastern Time
- `America/Chicago`: Central Time
- `America/Denver`: Mountain Time
- `America/Los_Angeles`: Pacific Time
- `Europe/London`: British Time
- `Europe/Paris`: Central European Time
- `Asia/Tokyo`: Japan Time
- `Asia/Shanghai`: China Time
- `Australia/Sydney`: Australia Eastern Time
