# Redis 7.4 Upgrade Guide

## Overview

This document outlines the steps to upgrade our Redis implementation to version 7.4 and implement its new features to enhance our analytics caching strategy.

## Implementation Priorities Checklist

Based on our application's needs, we should prioritize the Redis 7.4 features as follows:

### Priority 1: Critical Performance Improvements

- [ ] **Environment Upgrade**
  - [ ] Update Redis client library to 5.2.1+ in requirements.txt
  - [ ] Update Docker configuration for Redis 7.4
  - [ ] Test basic compatibility with existing code

- [ ] **Field-Level Expiration for Analytics**
  - [ ] Implement in `src/utils/redis_cache.py`
  - [ ] Apply to analytics endpoints with high-volume batch requests
  - [ ] Update analytics dashboard caching with varied TTLs

### Priority 2: High-Value Optimizations

- [ ] **Batch Endpoint Caching Optimization**
  - [ ] Implement volatility-based TTLs for different result types
  - [ ] Apply to crash-point analytics endpoints
  - [ ] Benchmark performance improvements

- [ ] **Enhanced Stream Processing**
  - [ ] Implement latest entry retrieval for real-time monitoring
  - [ ] Apply to game-event processing

### Priority 3: Future Considerations

- [ ] **Advanced Redis Cloud Features** (if/when migrating to Redis Cloud)
  - [ ] Time Series for crash-point historical trends
  - [ ] Query Engine for complex analytics

## Rationale for Prioritization

1. **Field-Level Expiration** provides immediate value for our analytics caching:
   - Different metrics can have different freshness requirements
   - Improves cache efficiency by keeping stable data longer
   - Reduces database load for our most frequently accessed analytics

2. **Batch Endpoint Optimization** targets our most resource-intensive endpoints:
   - Volatile data (low crash points) gets shorter TTLs
   - Stable historical data gets longer TTLs
   - Will significantly reduce database queries for batch operations

3. **Stream Processing** improvements enhance real-time monitoring capabilities:
   - Provides more efficient access to latest game events
   - Useful for dashboard and alerting features

## 1. Environment Upgrade

### Docker Environment

Update your docker-compose.yml:

```yaml
services:
  redis:
    image: redis:7.4
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
```

### Direct Installation

For non-Docker environments:

```bash
# Ubuntu/Debian
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis-server

# Start Redis and enable on boot
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Requirements Update

Update requirements.txt to ensure latest Redis client support:

```text
redis>=5.0.1  # Required for Redis 7.4 support
```

## 2. Key Feature Implementations

### 2.1 Field-Level Expiration for Analytics

Redis 7.4 introduces `HEXPIRE`, `HEXPIREAT`, and `HPEXPIRE` commands that let specific hash fields expire. This is perfect for our analytics data where different metrics have different freshness requirements.

Implementation in `src/utils/redis_cache.py`:

```python
async def cache_with_field_expiry(redis_conn, key, field, value, ttl_seconds):
    """Cache a specific field with its own expiration time."""
    # Convert value to JSON string if it's not already a string
    if not isinstance(value, str):
        value = json.dumps(value)
    
    # Set the hash field
    await redis_conn.hset(key, field, value)
    
    # Set field-specific expiration
    await redis_conn.execute_command('HEXPIRE', key, field, ttl_seconds)
    
    return True

# Example usage for analytics with different TTLs:
# Short-lived data (30s)
await cache_with_field_expiry(redis, "analytics:dashboard", "recent_games", games_data, 30)
# Longer-lived data (5 minutes)
await cache_with_field_expiry(redis, "analytics:dashboard", "historical_trends", trend_data, 300)
```

### 2.2 Enhanced Stream Processing

Redis 7.4 allows starting stream reading from the last entry with the special ID `$` in `XREAD`. This is particularly useful for our real-time event processing.

Implementation in `src/utils/redis.py`:

```python
async def get_latest_stream_entries(redis_conn, stream_name):
    """Get only the latest entries from a stream."""
    # Get the ID of the last message
    last_id = await redis_conn.execute_command('XREVRANGE', stream_name, '+', '-', 'COUNT', 1)
    
    if not last_id:
        return []
    
    # Use the new Redis 7.4 feature to read from the last ID
    last_id_str = last_id[0][0].decode('utf-8')
    entries = await redis_conn.execute_command('XREAD', 'STREAMS', stream_name, last_id_str)
    
    if not entries:
        return []
    
    # Process and return the latest entries
    return [
        {
            'id': entry[0].decode('utf-8'),
            'data': {k.decode('utf-8'): v.decode('utf-8') for k, v in entry[1]}
        }
        for stream_data in entries
        for entry in stream_data[1]
    ]
```

### 2.3 Optimizing the Caching Strategy with EXPIREMEMBER

Optimizing our batch endpoints caching with the new `EXPIREMEMBER` commands:

```python
async def cache_batch_results(redis_conn, base_key, batch_values, results, default_ttl=120):
    """Cache batch results with individualized TTLs based on data volatility."""
    # Store overall results mapping
    serialized_results = {str(k): json.dumps(v) for k, v in results.items()}
    await redis_conn.hset(base_key, mapping=serialized_results)
    
    # Set different expirations for different values based on volatility
    for value, result in results.items():
        # Analyze result to determine appropriate TTL
        result_ttl = default_ttl
        
        # More volatile data (like crash points <= 1.3) get shorter TTL
        if isinstance(value, (int, float)) and value <= 1.3:
            result_ttl = 60  # 1 minute only
        
        # Set field-specific expiration
        await redis_conn.execute_command('HEXPIRE', base_key, str(value), result_ttl)
    
    # Set overall key TTL (fallback)
    await redis_conn.expire(base_key, default_ttl)
    
    return True
```

## 3. Implementing Advanced Redis Cloud Features (Optional)

If migrating to Redis Cloud, consider these additional implementations:

### 3.1 Time Series for Historical Analytics

```python
async def record_crash_point_timeseries(redis_conn, crash_point, timestamp=None):
    """Record a crash point value in a time series for trend analysis."""
    if timestamp is None:
        timestamp = int(time.time() * 1000)  # Current time in milliseconds
    
    # Create time series if it doesn't exist (with auto retention policies)
    try:
        await redis_conn.execute_command(
            'TS.CREATE', 'ts:crash_points', 
            'RETENTION', 86400000,  # 24 hours in milliseconds
            'DUPLICATE_POLICY', 'LAST',
            'LABELS', 'source', 'game', 'metric', 'crash_point'
        )
    except:
        # Series likely already exists
        pass
    
    # Add value to time series
    await redis_conn.execute_command('TS.ADD', 'ts:crash_points', timestamp, crash_point)
    
    # Also add to downsampled series for longer-term storage
    try:
        # Create downsampled series if needed (1-minute aggregations)
        await redis_conn.execute_command(
            'TS.CREATE', 'ts:crash_points:1min',
            'RETENTION', 2592000000,  # 30 days in milliseconds
            'DUPLICATE_POLICY', 'LAST',
            'LABELS', 'source', 'game', 'metric', 'crash_point', 'resolution', '1min'
        )
    except:
        pass
    
    # Create rule if doesn't exist
    try:
        await redis_conn.execute_command(
            'TS.CREATERULE', 'ts:crash_points', 'ts:crash_points:1min', 'AGGREGATION', 'AVG', 60000  # 1 minute in ms
        )
    except:
        pass
    
    return True

async def get_crash_point_trends(redis_conn, from_time, to_time, bucket_size_ms=3600000):
    """Get crash point trends from time series data with aggregation."""
    # Default to last hour if not specified
    if to_time is None:
        to_time = int(time.time() * 1000)
    if from_time is None:
        from_time = to_time - 3600000  # 1 hour in milliseconds
    
    # Choose appropriate time series based on query range
    range_duration = to_time - from_time
    if range_duration > 86400000:  # > 24 hours
        series_key = 'ts:crash_points:1min'
    else:
        series_key = 'ts:crash_points'
    
    # Get aggregated data
    result = await redis_conn.execute_command(
        'TS.RANGE', series_key, from_time, to_time, 
        'AGGREGATION', 'AVG', bucket_size_ms
    )
    
    # Format result
    return [{'timestamp': entry[0], 'value': entry[1]} for entry in result]
```

### 3.2 Redis Query Engine for Analytics

Redis Cloud's Query Engine enables SQL-like queries on your Redis data:

```python
async def query_analytics_data(redis_conn, min_crash_point=None, max_date=None, limit=100):
    """Use Redis Stack's query engine for advanced analytics queries."""
    # Build query
    query = "SELECT crash_point, game_id, end_time FROM games_index"
    conditions = []
    
    if min_crash_point is not None:
        conditions.append(f"crash_point >= {min_crash_point}")
    
    if max_date is not None:
        conditions.append(f"end_time <= '{max_date}'")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += f" ORDER BY end_time DESC LIMIT {limit}"
    
    # Execute query
    result = await redis_conn.execute_command('FT.SEARCH', 'games_idx', query)
    
    # Process and return results
    return result
```

## 4. Migration and Testing Plan

1. **Development Environment Upgrade**
   - Upgrade Redis in the development environment
   - Update client libraries
   - Test existing functionality to ensure compatibility

2. **Feature Implementation**
   - Implement field-level expiration for analytics data
   - Update stream processing for real-time analytics
   - Enhance batch caching with new Redis 7.4 features

3. **Testing**
   - Create unit tests for new features
   - Verify performance improvements with benchmarks
   - Test failover and high-availability scenarios

4. **Production Deployment**
   - Create backup of existing Redis data
   - Schedule maintenance window for upgrade
   - Deploy new Redis version and updated application code
   - Monitor for any issues after deployment

## 5. Rollback Plan

In case of issues:

1. Restore Redis data from backup
2. Revert to previous Redis version
3. Roll back application code changes
4. Validate system functionality

## Conclusion

Upgrading to Redis 7.4 will enhance our caching strategy with field-level expiration, improved stream handling, and better performance. The changes outlined in this document will allow us to take full advantage of these new features while maintaining backward compatibility with our existing implementation.
