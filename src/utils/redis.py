"""
Redis utility module for Crash Monitor.

This module provides Redis connection management and utility functions.
It implements connection pooling and handles error cases with proper logging.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse
import time
import asyncio
import hashlib
import os.path

import redis
from redis import Redis
from redis.client import PubSub
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from .. import config

# Initialize logger
logger = logging.getLogger(__name__)

# Redis connection pool - will be initialized in setup_redis
_redis_pool = None
_pubsub_clients: Dict[str, PubSub] = {}

# Global cache version
_cache_version = "v1"


def setup_redis() -> None:
    """
    Set up the Redis connection pool with appropriate memory allocation.

    This function configures the Redis connection pool with:
    - Appropriate connection limits
    - Socket timeout settings
    - Memory optimization settings
    - Persistence configuration (RDB/AOF)

    It should be called once at application startup.
    """
    global _redis_pool

    if not config.REDIS_ENABLED:
        logger.info("Redis is disabled, skipping Redis setup")
        return

    try:
        # Parse Redis URL to extract host information
        url = urlparse(config.REDIS_URL)

        # Create connection pool with memory allocation settings
        _redis_pool = ConnectionPool.from_url(
            config.REDIS_URL,
            max_connections=config.REDIS_MAX_CONNECTIONS,
            socket_timeout=config.REDIS_SOCKET_TIMEOUT,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30
        )

        # Test connection
        with get_redis_client() as client:
            info = client.info("memory")
            total_memory = info.get("total_system_memory_human", "unknown")
            used_memory = info.get("used_memory_human", "unknown")
            peak_memory = info.get("used_memory_peak_human", "unknown")

            logger.info(
                f"Connected to Redis at {url.hostname}:{url.port or 6379}. "
                f"Memory: {used_memory} used, {peak_memory} peak, {total_memory} total system"
            )

            # Set memory management if available
            # Only for Redis >=4.0 instances
            if "maxmemory_policy" in info:
                # Set volatile-lru policy - will evict only keys with TTL when memory is full
                client.config_set("maxmemory-policy", "volatile-lru")
                logger.info("Set Redis maxmemory policy to volatile-lru")

            # Configure persistence settings
            configure_persistence(client)

    except (RedisError, ConnectionError, TimeoutError) as e:
        logger.error(f"Failed to initialize Redis: {str(e)}")
        _redis_pool = None


def configure_persistence(client: Redis) -> None:
    """
    Configure Redis persistence (RDB/AOF) based on data importance.

    Args:
        client: Redis client instance
    """
    try:
        # Get current persistence configuration
        config_get = client.config_get('*')
        logger.debug(f"Current Redis persistence configuration retrieved")

        # Configure RDB (Redis Database) persistence
        # RDB performs point-in-time snapshots of your dataset at specified intervals
        # Format: save <seconds> <changes>
        # These settings will create snapshots:
        # - After 900 sec (15 min) if at least 1 key changed
        # - After 300 sec (5 min) if at least 10 keys changed
        # - After 60 sec if at least 10000 keys changed
        client.config_set('save', '900 1 300 10 60 10000')

        # Configure AOF (Append Only File) persistence
        # AOF logs every write operation received by the server
        # This can be used to reconstruct the original dataset by replaying operations
        # - appendonly: whether AOF is enabled (yes/no)
        # - appendfsync: sync strategy (always/everysec/no)
        #   'always': fsync after every write (most durable, slowest)
        #   'everysec': fsync once per second (good compromise)
        #   'no': let OS decide when to sync (fastest, least durable)

        # For crash data, we'll use AOF with everysec sync strategy
        # This provides good durability without significant performance impact
        client.config_set('appendonly', 'yes')
        client.config_set('appendfsync', 'everysec')

        logger.info(
            "Redis persistence configured: RDB snapshots and AOF enabled")
    except RedisError as e:
        logger.warning(f"Failed to configure Redis persistence: {str(e)}")
        logger.warning("Redis will use default persistence settings")


def get_redis_client() -> Redis:
    """
    Get a Redis client from the connection pool.

    Returns:
        Redis client object

    Raises:
        RuntimeError: If Redis is disabled or not initialized
    """
    if not config.REDIS_ENABLED:
        raise RuntimeError("Redis is disabled")

    if _redis_pool is None:
        raise RuntimeError("Redis connection pool not initialized")

    return Redis(connection_pool=_redis_pool)


def is_redis_available() -> bool:
    """
    Check if Redis is available and working.

    Returns:
        bool: True if Redis is available, False otherwise
    """
    if not config.REDIS_ENABLED or _redis_pool is None:
        return False

    try:
        with get_redis_client() as client:
            return client.ping()
    except RedisError:
        return False


def close_redis_connections() -> None:
    """
    Close all Redis connections and clean up resources.

    This should be called when shutting down the application.
    """
    global _redis_pool, _pubsub_clients

    # Close any active pubsub connections
    for channel, pubsub in _pubsub_clients.items():
        try:
            pubsub.close()
            logger.debug(f"Closed PubSub client for channel: {channel}")
        except Exception as e:
            logger.warning(
                f"Error closing PubSub for channel {channel}: {str(e)}")

    _pubsub_clients = {}

    # Release all connections in the pool
    if _redis_pool is not None:
        try:
            _redis_pool.disconnect()
            logger.info("Closed all Redis connections")
        except Exception as e:
            logger.warning(f"Error disconnecting Redis pool: {str(e)}")

        _redis_pool = None


# Key generation functions for standardized Redis key naming
def get_cache_version() -> str:
    """
    Get the current cache version.

    This version is used in all cache keys to allow for versioning and cache invalidation.

    Returns:
        str: Current cache version
    """
    global _cache_version
    return _cache_version


def set_cache_version(new_version: Optional[str] = None) -> str:
    """
    Set a new cache version to invalidate all existing keys.

    Args:
        new_version: Optional specific version to set. If None, generates a timestamp-based version.

    Returns:
        str: The new cache version
    """
    global _cache_version

    if new_version is None:
        # Generate a timestamp-based version
        _cache_version = f"v{int(time.time())}"
    else:
        _cache_version = new_version

    logger.info(f"Cache version updated to {_cache_version}")
    return _cache_version


def generate_games_key(page: int, per_page: int, timezone: str) -> str:
    """
    Generate a standardized Redis key for games list endpoints.

    Args:
        page: Page number
        per_page: Number of items per page
        timezone: Timezone for game timestamps

    Returns:
        str: Standardized Redis key
    """
    return f"games:list:page:{page}:per_page:{per_page}:tz:{timezone}:{get_cache_version()}"


def generate_game_detail_key(game_id: str) -> str:
    """
    Generate a standardized Redis key for a game detail endpoint.

    Args:
        game_id: Unique identifier for the game

    Returns:
        str: Standardized Redis key
    """
    return f"games:detail:{game_id}:{get_cache_version()}"


def generate_analytics_key(endpoint: str, params: Dict[str, Any]) -> str:
    """
    Generate a standardized Redis key for analytics endpoints.

    Args:
        endpoint: Analytics endpoint name (e.g., 'interval', 'occurrence')
        params: Dictionary of query parameters

    Returns:
        str: Standardized Redis key
    """
    # Sort parameters for consistent key generation
    sorted_params = sorted(params.items())

    # Build parameter part of the key
    param_parts = [f"{k}:{v}" for k, v in sorted_params]
    param_string = ":".join(param_parts)

    return f"analytics:{endpoint}:{param_string}:{get_cache_version()}"


def generate_hash_key(data: Any) -> str:
    """
    Generate a hash key for complex data structures.

    This is useful when the parameter space is too large for string-based keys.

    Args:
        data: Any JSON-serializable data structure

    Returns:
        str: Hashed key
    """
    # Convert data to a stable string representation
    data_str = json.dumps(data, sort_keys=True)

    # Hash the string
    hash_obj = hashlib.md5(data_str.encode())
    return hash_obj.hexdigest()
