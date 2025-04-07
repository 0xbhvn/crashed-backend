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


def setup_redis() -> None:
    """
    Set up the Redis connection pool with appropriate memory allocation.

    This function configures the Redis connection pool with:
    - Appropriate connection limits
    - Socket timeout settings
    - Memory optimization settings

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

    except (RedisError, ConnectionError, TimeoutError) as e:
        logger.error(f"Failed to initialize Redis: {str(e)}")
        _redis_pool = None


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
