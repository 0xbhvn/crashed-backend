# Redis Caching Strategy for Analytics Endpoints

## 1. Simplified Approach: On-Demand Response Caching

Rather than precomputing all possible analytics aggregates, we've implemented a simpler and more direct approach:

1. **Compute-On-Demand**: When an API endpoint is called, compute the response as normal
2. **Cache the Response**: Store the complete response in Redis with an appropriate TTL
3. **Serve from Cache**: Subsequent identical requests will be served directly from Redis
4. **Invalidate on New Games**: When new games are processed, invalidate affected cached responses
5. **Auto-Expiration**: If no requests are made for a particular response before its TTL expires, it simply vanishes from Redis

This strategy serves our primary goal: if multiple clients request the same data simultaneously, we compute it only once and serve the cached result to all other requests.

## 2. Implementation Overview

### 2.1. Cache Key Generation

We've implemented a structured approach to cache key generation that ensures consistent and readable keys:

#### Single-Value GET Endpoints

```text
analytics:{endpoint_type}:{parameter_name}:{parameter_value}:{version}
```

Examples:

- `analytics:last_game:min:2.0:v1744056452` (Last game with crash point >= 2.0)
- `analytics:last_game:floor:5:v1744056452` (Last game with exact floor value 5)
- `analytics:last_game:max:1.5:v1744056452` (Last game with crash point <= 1.5)
- `analytics:occurrences:min:2.0:by_time:false:games:100:v1744056452` (Occurrences of crash points >= 2.0 in last 100 games)
- `analytics:occurrences:max:1.5:by_time:true:hours:2:v1744056452` (Occurrences of crash points <= 1.5 in last 2 hours)
- `analytics:occurrences:floor:5:by_time:false:games:500:v1744056452` (Occurrences of floor value 5 in last 500 games)

#### Multiple-Games GET Endpoints with Query Parameters

```text
analytics:{endpoint_type}:{parameter_name}:{parameter_value}:{query_param}:{query_value}:{version}
```

Examples:

- `analytics:last_games:min:2.0:limit:10:v1744056473` (Last 10 games with crash point >= 2.0)
- `analytics:last_games:min:2.0:limit:15:v1744056473` (Last 15 games with crash point >= 2.0)
- `analytics:last_games:floor:5:limit:10:v1744056473` (Last 10 games with floor value 5)

#### Batch POST Endpoints

```text
analytics:{endpoint_type}:batch:{fingerprint}:{version}
```

Examples:

- `analytics:last_games:min:batch:f04cce3cd72e:v1744056452` (Batch minimum crash points)
- `analytics:last_games:floor:batch:e6db41ac41d4:v1744056473` (Batch floor values)
- `analytics:last_games:max:batch:46e2ed90d0ad:v1744056473` (Batch maximum crash points)
- `analytics:occurrences:min:batch:a7c43e1b2f9d:v1744056452` (Batch occurrences of minimum crash points)
- `analytics:occurrences:floor:batch:b8d52f3c1e0a:v1744056473` (Batch occurrences of floor values)
- `analytics:occurrences:max:batch:c9e61f4d0g1b:v1744056473` (Batch occurrences of maximum crash points)

The fingerprint is generated from request properties including method, path, content length, and content type, ensuring different requests get different keys while identical requests share the same key.

### 2.2. Cache Storage Format

We store the complete API response as a JSON string with added cache metadata:

```json
{
  "status": "success",
  "data": {
    // Full response data goes here
  },
  "cached_at": 1744056381  // Unix timestamp when the response was cached
}
```

### 2.3. TTL Strategy

Our Redis caching implementation uses a tiered TTL (Time-To-Live) strategy:

- **Short-lived analytics (REDIS_CACHE_TTL_SHORT = 30s)**: For simple, frequently accessed endpoints that return recent data
  - Single-value GET endpoints with small datasets (e.g., `/api/analytics/last-game/min-crash-point/{value}`)
  - Endpoints where data freshness is more important than computational savings

- **Longer-lived analytics (REDIS_CACHE_TTL_LONG = 120s)**: For computationally expensive operations
  - Batch POST requests that process multiple values
  - Endpoints that analyze large datasets (e.g., series analysis)
  - Date range queries and historical analysis
  - Game-sets analysis that requires grouping large numbers of games

This tiered approach balances the need for data freshness with computational efficiency. The TTL values can be adjusted in the configuration based on application needs, traffic patterns, and server load.

### 2.4. Cache Invalidation

When a new game is processed:

1. **Version-Based Invalidation**: We increment the cache version, effectively invalidating all analytics caches
2. **Cache Reset Function**: The `invalidate_analytics_cache_for_new_game()` function is called in the game processing callback

## 3. Implementation Details

### 3.1. Utility Functions

We've created several utility functions to support Redis caching:

- **`cached_endpoint`**: Middleware that wraps API endpoint handlers to provide caching
- **`get_cached_response`**: Check if a response is cached in Redis and return it if found
- **`cache_response`**: Store a response in Redis with an appropriate TTL
- **`build_key_from_match_info`**: Generate keys for endpoints with path parameters
- **`build_key_with_query_param`**: Generate keys for endpoints with path and query parameters
- **`build_hash_based_key`**: Generate keys for POST endpoints with JSON bodies

### 3.2. Currently Cached Endpoints

We've implemented Redis caching for the following endpoint groups:

#### Last Games Endpoints

- `/api/analytics/last-game/min-crash-point/{value}`
- `/api/analytics/last-game/max-crash-point/{value}`
- `/api/analytics/last-game/exact-floor/{value}`
- `/api/analytics/last-games/min-crash-point/{value}`
- `/api/analytics/last-games/max-crash-point/{value}`
- `/api/analytics/last-games/exact-floor/{value}`
- `/api/analytics/last-games/min-crash-points/batch` (POST)
- `/api/analytics/last-games/max-crash-points/batch` (POST)
- `/api/analytics/last-games/exact-floors/batch` (POST)

#### Occurrences Endpoints

- `/api/analytics/occurrences/min-crash-point/{value}`
- `/api/analytics/occurrences/max-crash-point/{value}`
- `/api/analytics/occurrences/exact-floor/{value}`
- `/api/analytics/occurrences/min-crash-points/batch` (POST)
- `/api/analytics/occurrences/exact-floors/batch` (POST)
- `/api/analytics/occurrences/max-crash-points/batch` (POST)

#### Series Endpoints

- `/api/analytics/series/without-min-crash-point/{value}`
- `/api/analytics/series/without-min-crash-point/{value}/time`

#### Intervals Endpoints

- `/api/analytics/intervals/min-crash-point/{value}`
- `/api/analytics/intervals/min-crash-point/{value}/date-range`
- `/api/analytics/intervals/min-crash-point/{value}/game-sets`
- `/api/analytics/intervals/min-crash-points` (POST)
- `/api/analytics/intervals/min-crash-points/date-range` (POST)
- `/api/analytics/intervals/min-crash-points/game-sets` (POST)

### 3.3. Handling POST Requests

For POST endpoints (particularly batch requests), we use a specialized approach:

1. Generate a unique fingerprint based on request properties (method, path, content)
2. Ensure deterministic key generation for identical requests
3. Handle the inability to directly access request body content in non-async functions

### 3.4. Error Handling

Our implementation includes robust error handling:

- Fallback to database if Redis is unavailable
- Graceful handling of JSON parsing errors
- Logging of all cache-related operations
- Protection against missing or invalid cache keys

## 4. Benefits of Our Implementation

1. **Simplicity**: Straightforward implementation focusing on the most valuable caching paths
2. **Storage Efficiency**: Only frequently requested data is cached
3. **Consistent Results**: All clients get the same result for the same query within the TTL period
4. **Reduced Database Load**: Significantly reduces database queries for popular endpoints
5. **Developer-Friendly**: Clear key naming conventions make debugging easier

## 5. Troubleshooting Common Issues

### 5.1. Cache Key Conflicts

If different requests are generating the same cache key, check:

- The key builder function implementation
- Request parameter handling
- Hash generation for batch endpoints

### 5.2. Cache Not Being Used

If responses aren't being cached or retrieved:

- Verify Redis is running and accessible
- Check REDIS_ENABLED configuration
- Examine TTL settings
- Look for Redis connection errors in logs

### 5.3. Stale Data

If clients are receiving outdated data:

- Review cache invalidation logic
- Check if the version increment is working correctly
- Consider reducing TTL for time-sensitive endpoints

## 6. Future Improvements

1. **Selective Precomputation**: Identify the most frequently accessed analytics and precompute only those
2. **Smarter Invalidation**: Develop more targeted cache invalidation that only removes affected data
3. **Tiered Caching**: Implement different TTLs for different types of data (already partially implemented with REDIS_CACHE_TTL_LONG for series)
4. **Compression**: For large responses, implement compression to reduce Redis memory usage
5. **Cache Statistics**: Add monitoring to track hit/miss rates and optimize accordingly

## 7. Implementation Status

As part of the feat/redis-caching branch, we have successfully implemented Redis caching for:

- ✅ Last Games endpoints (min/max crash points, exact floors)
- ✅ Occurrences endpoints (min/max crash points, exact floors)
- ✅ Series endpoints (without-min-crash-point)
- ✅ Intervals endpoints (min-crash-point)

Testing has confirmed significant performance improvements for all implemented endpoints, especially for computationally expensive queries.

## Note on Analytics Aggregates

We've successfully implemented caching for all analytics endpoints, providing immediate performance benefits, particularly for computationally expensive operations like intervals and series analysis.
