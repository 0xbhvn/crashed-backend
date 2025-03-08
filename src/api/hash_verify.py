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
    Calculate the crash point for a game hash using BC Game's algorithm.

    Args:
        seed: The game hash
        salt: The salt used for HMAC

    Returns:
        float: The calculated crash point value
    """
    try:
        # Remove 0x prefix if present
        if seed.startswith("0x"):
            seed = seed[2:]

        # Create HMAC using the seed and salt
        h = hmac.new(bytes.fromhex(salt), bytes.fromhex(seed), hashlib.sha256)
        hash_hex = h.hexdigest()

        # Get first 8 characters (4 bytes) of the hex
        hash_bytes = hash_hex[:8]

        # Convert to integer (unsigned)
        e = int(hash_bytes, 16)

        # Apply BC Game's crash point formula:
        # Uses modulo 1,000,000 to get value between 0-999,999
        # and divide by 10,000 to get value between 0-99.9999
        X = (e % 1000000) / 10000

        # BC Game formula: (100 - house edge) / (1 - X/100)
        # House edge is 1%, so 99 / (1 - X/100)
        # Result is divided by 100 and floored
        crash_value = math.floor(99 / (1 - X/100)) / 100

        # Return the result, with a minimum of 1.00
        return max(1.00, crash_value)
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
    # BC Game uses a different chaining mechanism from what we implemented
    # Instead of calculating SHA256 of the current hash, they have a separate stored value
    # Since we don't have access to their internal data, we'll use their actual API data
    # for demo purposes and only calculate the crash points accurately

    # This implementation cannot generate the correct chain without BC Game's internal data
    logger.warning(
        "Cannot generate correct hash chain without BC Game's internal sequence")

    # Return the input hash for now, with a warning that this doesn't match BC Game's chain
    # In production, you would need to obtain the actual hash chain from BC Game
    return hash_value


@routes.get('/api/hash-verify')
async def verify_hash(request: web.Request) -> web.Response:
    """
    Verify a BC Game hash and calculate crash points for the given hash and previous games.

    Query parameters:
        hash: The BC Game hash to verify
        count: Number of games to verify (default: 10)
        salt: Custom salt to use for verification (optional)

    Returns:
        JSON response with verification results
    """
    try:
        # Get parameters from request
        params = request.query
        game_hash = params.get('hash')
        count = params.get('count', '10')
        # Default salt for BC Game
        salt = params.get(
            'salt', '0000000000000000000301e2801a9a9598bfb114e574a91a887f2132f33047e6')

        # Validate hash parameter
        if not game_hash:
            logger.warning("Missing hash parameter in request")
            return web.json_response({
                'status': 'error',
                'error': 'Missing hash parameter'
            }, status=400, headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            })

        # Validate count parameter
        try:
            count = int(count)
            if count < 1 or count > 100:
                count = 10  # Default to 10 if out of range
                logger.warning(
                    f"Count parameter out of range, using default: {count}")
        except ValueError:
            count = 10  # Default to 10 if not a valid integer
            logger.warning(f"Invalid count parameter, using default: {count}")

        logger.info(
            f"Processing hash verification request: hash={game_hash}, count={count}, salt={salt}")

        # Calculate crash point for the specified hash
        if not game_hash.startswith("0x"):
            game_hash = "0x" + game_hash

        crash_point = calculate_crash_point(game_hash, salt)

        # Return only the crash point for the given hash
        # Note: We can't accurately generate the hash chain without BC Game's internal data
        response_data = {
            'status': 'success',
            'salt': salt,
            'hash': game_hash,
            'crash_point': crash_point,
            'note': 'BC Game uses a proprietary hash chain that cannot be reproduced without their internal data. Only the crash point calculation is accurate.'
        }

        return web.json_response(response_data, headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })

    except Exception as e:
        logger.error(f"Error in hash verification: {e}")
        return web.json_response({
            'status': 'error',
            'error': str(e)
        }, status=500, headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        })

# Add OPTIONS method handler for CORS preflight requests


@routes.options('/api/hash-verify')
async def options_hash_verify(request: web.Request) -> web.Response:
    """Handle OPTIONS requests for the hash-verify endpoint to support CORS"""
    return web.Response(headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    })


def setup_hash_verify_routes(app: web.Application) -> None:
    """
    Set up hash verification routes for the application.

    Args:
        app: The aiohttp application.
    """
    app.add_routes(routes)
    logger.info("Hash verification routes configured")
