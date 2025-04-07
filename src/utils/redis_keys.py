"""
Redis key generation utility module for Crash Monitor.

This module provides standardized functions for generating Redis keys
to ensure consistency across the application.
"""

import logging
import hashlib
import time
from typing import Optional, List, Dict, Any

from .. import config

# Initialize logger
logger = logging.getLogger(__name__)

# Global cache version
_cache_version = "v1"


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
    return f"games:page:{page}:per_page:{per_page}:tz:{timezone}:{get_cache_version()}"


def generate_game_detail_key(game_id: str) -> str:
    """
    Generate a standardized Redis key for game detail endpoints.

    Args:
        game_id: Game ID

    Returns:
        str: Standardized Redis key
    """
    return f"game:{game_id}:{get_cache_version()}"


def generate_analytics_key(key_suffix: str) -> str:
    """
    Generate a standardized Redis key for analytics endpoints.

    Args:
        key_suffix: Suffix to append to the key (should include specific parameters)

    Returns:
        str: Standardized Redis key
    """
    return f"analytics:{key_suffix}:{get_cache_version()}"


def generate_hash_key(param_dict: Dict[str, Any]) -> str:
    """
    Generate a hash key from a dictionary of parameters.
    Useful for complex parameter combinations.

    Args:
        param_dict: Dictionary of parameters to hash

    Returns:
        str: Hash key
    """
    # Convert dict to sorted string representation for consistent hashing
    param_str = str(sorted(param_dict.items()))

    # Create MD5 hash of the parameter string
    return hashlib.md5(param_str.encode()).hexdigest()


def invalidate_analytics_cache_for_new_game() -> None:
    """
    Invalidate Redis cache keys affected by a new game.

    This can be called whenever a new game is processed to ensure
    analytics endpoints return fresh data.

    Options:
    1. Targeted approach - invalidate specific keys that would be affected
    2. Global approach - update the cache version to invalidate all caches

    For simplicity, we use the global approach here.
    """
    # Update the cache version to invalidate all cached analytics
    logger.info("Invalidating analytics cache due to new game")
    set_cache_version()


def invalidate_specific_analytics_cache(cache_pattern: str) -> int:
    """
    Invalidate specific Redis cache keys matching a pattern.

    Args:
        cache_pattern: Pattern to match keys (e.g., "analytics:last_game*")

    Returns:
        int: Number of keys invalidated
    """
    from .redis import get_redis_client, is_redis_available

    if not config.REDIS_ENABLED or not is_redis_available():
        logger.warning(
            "Redis not available, skipping targeted cache invalidation")
        return 0

    try:
        redis = get_redis_client()
        keys = redis.keys(cache_pattern)
        if keys:
            count = redis.delete(*keys)
            logger.info(
                f"Invalidated {count} cache keys matching pattern: {cache_pattern}")
            return count
        return 0
    except Exception as e:
        logger.error(f"Error invalidating cache keys: {str(e)}")
        return 0
