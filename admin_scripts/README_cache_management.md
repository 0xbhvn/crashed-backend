# Redis Cache Management

This document explains how to manage the Redis cache for the crashed-backend application.

## Quick Start

The `clear_redis_cache.py` script provides several commands to manage the Redis cache:

### 1. Clear All Cache (Recommended)

This is the safest way to clear the cache. It updates the cache version, invalidating all existing cached data:

```bash
python admin_scripts/clear_redis_cache.py clear --all
```

### 2. Clear Specific Cache Patterns

To clear only specific types of cached data:

```bash
# Clear all analytics cache
python admin_scripts/clear_redis_cache.py clear --pattern "analytics:*"

# Clear all games list cache
python admin_scripts/clear_redis_cache.py clear --pattern "games:*"

# Clear all individual game detail cache
python admin_scripts/clear_redis_cache.py clear --pattern "game:*"
```

### 3. View Cache Statistics

To see current cache usage and statistics:

```bash
python admin_scripts/clear_redis_cache.py stats
```

### 4. List Cache Keys

To see what's currently cached:

```bash
# List all keys
python admin_scripts/clear_redis_cache.py list

# List specific pattern
python admin_scripts/clear_redis_cache.py list --pattern "analytics:*"
```

### 5. Flush Entire Database (WARNING)

This deletes ALL data in Redis, not just cache. Use with extreme caution:

```bash
python admin_scripts/clear_redis_cache.py flush
```

## Cache Key Patterns

The application uses the following cache key patterns:

- `analytics:*` - Analytics endpoint cache (intervals, occurrences, series, etc.)
- `games:*` - Games list endpoint cache
- `game:*` - Individual game detail cache

All keys include a version suffix (e.g., `:v1`) that changes when cache is invalidated.

## Alternative Method: Using Redis CLI

If you have direct access to Redis CLI:

```bash
# Connect to Redis
redis-cli

# List all keys
KEYS *

# Delete specific pattern
DEL analytics:*

# Flush database (WARNING: deletes everything)
FLUSHDB
```

## When to Clear Cache

You should clear the cache when:

1. You've made code changes that affect the data structure or calculation logic
2. You've manually updated data in the database
3. You're debugging and need to see fresh results
4. The cached data seems stale or incorrect

## Cache TTL (Time-To-Live)

The application automatically expires cache entries based on configured TTL values:

- Short TTL (default 300s / 5 minutes): For frequently changing data
- Long TTL (default 3600s / 1 hour): For stable data

Cache entries will automatically expire after their TTL, so manual clearing is only needed for immediate updates.
