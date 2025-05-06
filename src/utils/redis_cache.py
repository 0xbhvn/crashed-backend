"""
Redis caching utilities for API endpoints.

This module provides reusable functions for implementing Redis caching
in API endpoint handlers, reducing code duplication.
"""

import json
import logging
import time
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, Tuple

from aiohttp import web
from .redis import get_redis_client, is_redis_available
from .redis_keys import generate_analytics_key
from .. import config

# Initialize logger
logger = logging.getLogger(__name__)


async def get_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Check if a response is cached in Redis and return it if found.

    Args:
        cache_key: Redis key for the cached response

    Returns:
        Cached response data if found, None otherwise
    """
    if not config.REDIS_ENABLED or not is_redis_available():
        return None

    try:
        redis = get_redis_client()
        cached_data = redis.get(cache_key)

        if cached_data:
            response_data = json.loads(cached_data)
            # Add source to indicate it was served from cache
            response_data['source'] = 'redis'
            logger.debug(f"Cache hit for {cache_key}")
            return response_data

        return None
    except Exception as e:
        logger.error(f"Error retrieving cached response: {str(e)}")
        return None


def cache_response(cache_key: str, response_data: Dict[str, Any], ttl: int = None) -> bool:
    """
    Store a response in Redis cache.

    Args:
        cache_key: Redis key for the cached response
        response_data: Response data to cache
        ttl: Time-to-live in seconds (default: config.REDIS_CACHE_TTL_SHORT)

    Returns:
        bool: True if cached successfully, False otherwise
    """
    if not config.REDIS_ENABLED or not is_redis_available():
        return False

    if ttl is None:
        ttl = config.REDIS_CACHE_TTL_SHORT

    try:
        redis = get_redis_client()
        # Add timestamp for when it was cached
        if 'cached_at' not in response_data:
            response_data['cached_at'] = int(time.time())

        redis.setex(
            cache_key,
            ttl,
            json.dumps(response_data)
        )
        logger.debug(f"Cached response at {cache_key} with TTL {ttl}s")
        return True
    except Exception as e:
        logger.error(f"Error caching response: {str(e)}")
        return False


async def cached_endpoint(request: web.Request,
                          key_builder: Callable,
                          data_fetcher: Callable[[web.Request], Awaitable[Tuple[Dict[str, Any], bool]]],
                          ttl: int = None) -> web.Response:
    """
    Handle a request with Redis caching, using a common pattern for analytics endpoints.

    Args:
        request: The aiohttp request object
        key_builder: Function that builds a Redis key from the request (can be async or sync)
        data_fetcher: Async function that generates the response data if not cached
                      Returns tuple of (response_data, success)
        ttl: Optional custom TTL for cache

    Returns:
        web.Response: JSON response with data from cache or freshly generated
    """
    # Generate cache key - support both async and sync key_builder functions
    if asyncio.iscoroutinefunction(key_builder):
        cache_key = await key_builder(request)
    else:
        cache_key = key_builder(request)

    # Check cache first
    cached_data = await get_cached_response(cache_key)
    if cached_data is not None:
        return web.json_response(cached_data)

    # If not in cache, fetch the data
    response_data, success = await data_fetcher(request)

    # If successful, cache the response
    if success:
        cache_response(cache_key, response_data, ttl)

    return web.json_response(response_data)


def build_key_from_match_info(prefix: str, param_name: str) -> Callable[[web.Request], str]:
    """
    Create a key builder function for endpoints with a single path parameter.

    Args:
        prefix: Prefix for the analytics key (e.g., "last_game:min")
        param_name: Name of the path parameter

    Returns:
        Function that builds a Redis key from a request
    """
    def key_builder(request: web.Request) -> str:
        param_value = request.match_info[param_name]
        return generate_analytics_key(f"{prefix}:{param_value}")

    return key_builder


def build_key_with_query_param(prefix: str, path_param: str, query_param: str = 'limit') -> Callable[[web.Request], str]:
    """
    Create a key builder function for endpoints with a path parameter and query parameter.

    Args:
        prefix: Prefix for the analytics key (e.g., "last_games:min")
        path_param: Name of the path parameter
        query_param: Name of the query parameter (default: 'limit')

    Returns:
        Function that builds a Redis key from a request
    """
    def key_builder(request: web.Request) -> str:
        path_value = request.match_info[path_param]
        query_value = request.query.get(
            query_param, '10')  # Default to 10 for limit
        return generate_analytics_key(f"{prefix}:{path_value}:{query_param}:{query_value}")

    return key_builder


def build_key_from_json_body(prefix: str, key_field: str = 'values') -> Callable[[web.Request], str]:
    """
    Create a key builder function for endpoints with a JSON body containing a list.

    Args:
        prefix: Prefix for the analytics key (e.g., "last_games:min:batch")
        key_field: Field in the JSON body that contains the values (default: 'values')

    Returns:
        Function that builds a Redis key from a request and its body
    """
    async def key_builder(request: web.Request) -> str:
        try:
            body = await request.json()
            values = body.get(key_field, [])
            sorted_values = sorted(values)
            values_str = '-'.join([str(v) for v in sorted_values])
            return generate_analytics_key(f"{prefix}:{values_str}")
        except Exception as e:
            logger.error(f"Error building key from JSON body: {str(e)}")
            # Fallback to a timestamp-based key if we can't parse the body
            return generate_analytics_key(f"{prefix}:error:{int(time.time())}")

    return key_builder


def build_hash_based_key(prefix: str) -> Callable[[web.Request], str]:
    """
    Create a non-async key builder function for endpoints that works reliably with aiohttp.

    This implementation creates a deterministic key based on the request method, endpoint path,
    and request details, ensuring consistent caching of identical requests.

    Args:
        prefix: Prefix for the analytics key (e.g., "last_games:min:batch")

    Returns:
        Function that builds a Redis key from a request
    """
    def key_builder(request: web.Request) -> str:
        try:
            # Get basic request information
            method = request.method
            endpoint_path = str(request.url.path)

            # Initialize components that will form our key
            key_components = [method, endpoint_path]

            # Add query string for GET requests
            if method == "GET" and request.query_string:
                key_components.append(request.query_string)

            # For POST requests, use headers to create a fingerprint
            if method == "POST" and request.has_body:
                content_length = request.headers.get('Content-Length', '0')
                content_type = request.headers.get('Content-Type', '')
                key_components.extend([content_length, content_type])

                # If we can see if this is a JSON request with a consistent structure,
                # we can try to incorporate that information
                if 'application/json' in content_type.lower():
                    # We'll add more uniqueness by including hash of the content length
                    # This helps differentiate between different JSON payloads
                    # without needing to actually parse the JSON
                    key_components.append(f"json_len_{content_length}")

            # Create a fingerprint from all components
            from hashlib import md5
            components_str = ":".join(key_components)
            fingerprint = md5(components_str.encode()).hexdigest()[:12]

            # Use a stable, deterministic key format
            return generate_analytics_key(f"{prefix}:{fingerprint}")

        except Exception as e:
            logger.error(f"Error building hash-based key: {str(e)}")
            # Fallback to a timestamp-based key
            return generate_analytics_key(f"{prefix}:error:{int(time.time())}")

    return key_builder


def build_hash_based_key_with_body(prefix: str) -> Callable[[web.Request], str]:
    """
    Create a key builder that incorporates the actual request body content into the key.
    This is especially useful for POST endpoints that accept JSON data with different values
    that should be cached separately.

    Args:
        prefix: Prefix for the analytics key (e.g., "last_games:min:batch")

    Returns:
        Function that builds a Redis key incorporating the request body
    """
    async def key_builder(request: web.Request) -> str:
        try:
            # Basic request information
            method = request.method
            endpoint_path = str(request.url.path)

            # For POST requests with JSON content
            if method == "POST" and 'application/json' in request.headers.get('Content-Type', '').lower():
                try:
                    # Get the actual body content
                    body = await request.json()

                    # If there's a 'values' field, use it to make the key unique
                    if 'values' in body:
                        # Sort values to ensure consistent keys regardless of order
                        values = sorted(str(v) for v in body['values'])
                        values_str = '-'.join(values)

                        # Create a fingerprint incorporating the values
                        from hashlib import md5
                        body_hash = md5(values_str.encode()).hexdigest()[:12]
                        return generate_analytics_key(f"{prefix}:values_{body_hash}")
                except Exception as e:
                    logger.error(
                        f"Error processing request body for cache key: {str(e)}")

            # Fallback to the basic hash method if we can't use the body
            components = [method, endpoint_path]
            if request.query_string:
                components.append(request.query_string)

            # Create a fingerprint
            from hashlib import md5
            components_str = ":".join(components)
            fingerprint = md5(components_str.encode()).hexdigest()[:12]

            return generate_analytics_key(f"{prefix}:{fingerprint}")

        except Exception as e:
            logger.error(f"Error building body-based hash key: {str(e)}")
            # Fallback to a timestamp-based key
            return generate_analytics_key(f"{prefix}:error:{int(time.time())}")

    return key_builder
