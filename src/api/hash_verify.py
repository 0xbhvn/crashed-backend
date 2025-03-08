"""
BC Game Hash Verification API

This module provides an API endpoint to verify BC Game crash points
for a given game hash and its previous games.
"""

import hashlib
import hmac
import math
import json
import logging
from typing import List, Dict, Any, Optional

from aiohttp import web

from .. import config
from .utils import json_response, error_response

# Configure logging
logger = logging.getLogger(__name__)

# Define routes
routes = web.RouteTableDef()


def calculate_crash_point(seed: str, salt: str) -> float:
    """
    Calculate crash point using the BC Game algorithm.

    Args:
        seed: The game hash
        salt: The salt value

    Returns:
        float: The calculated crash point
    """
    try:
        # Remove 0x prefix if present
        if seed.startswith("0x"):
            seed = seed[2:]

        # Generate the HMAC-SHA256 hash
        h = hmac.new(salt.encode(), bytes.fromhex(
            seed), hashlib.sha256).hexdigest()

        # Take the first 13 hex characters (52 bits)
        h = h[:13]

        # Convert to a number between 0 and 1
        r = int(h, 16)
        X = r / (2**52)

        # Apply the BC Game crash point formula
        X = 99 / (1 - X)

        # Floor and divide by 100
        result = math.floor(X) / 100

        # Return the result, with a minimum of 1.00
        return max(1.00, result)
    except Exception as e:
        logger.error(f"Error calculating crash point: {e}")
        # Return 1.00 (the minimum crash point) on error
        return 1.00


def calculate_previous_hash(hash_value: str) -> str:
    """
    Calculate the previous game hash based on BC Game's chain algorithm.

    Args:
        hash_value: The current game hash

    Returns:
        str: The calculated previous game hash
    """
    # Remove 0x prefix if present
    if hash_value.startswith("0x"):
        hash_value = hash_value[2:]

    # Calculate SHA256 of the current hash
    prev_hash = hashlib.sha256(bytes.fromhex(hash_value)).hexdigest()

    # Add 0x prefix for consistency
    return "0x" + prev_hash


@routes.get('/api/hash-verify')
async def verify_hash(request: web.Request) -> web.Response:
    """
    Verify a BC Game hash and calculate crash points for the given hash and previous games.

    Query parameters:
        hash: The game hash to verify
        count: Number of games to verify (including the provided hash)
        salt: Salt to use for verification (defaults to app config)
    """
    try:
        # Get query parameters
        hash_value = request.query.get('hash')
        count_str = request.query.get('count', '10')
        salt = request.query.get('salt', config.BC_GAME_SALT)

        # Validate hash parameter
        if not hash_value:
            return error_response("Missing required parameter: hash", 400)

        # Validate count parameter
        try:
            count = int(count_str)
            if count < 1:
                count = 1
            elif count > 100:
                count = 100  # Limit to 100 games maximum
        except ValueError:
            return error_response(f"Invalid count parameter: {count_str}", 400)

        # Prepare results list
        results = []

        # Process the given hash and its previous hashes
        current_hash = hash_value
        for i in range(count):
            # Calculate crash point for current hash
            crash_point = calculate_crash_point(current_hash, salt)

            # Add to results
            results.append({
                'game_number': i,
                'hash': current_hash,
                'crash_point': crash_point
            })

            # Calculate previous hash (for next iteration)
            if i < count - 1:
                current_hash = calculate_previous_hash(current_hash)

        # Prepare response
        response_data = {
            'status': 'success',
            'results': results,
            'salt': salt,
            'count': len(results)
        }

        return json_response(response_data)

    except Exception as e:
        logger.error(f"Error in verify_hash: {e}")
        return error_response(str(e), 500)


def setup_hash_verify_routes(app: web.Application) -> None:
    """
    Set up hash verification routes for the application.

    Args:
        app: The aiohttp application.
    """
    app.add_routes(routes)
    logger.info("Hash verification routes configured")
