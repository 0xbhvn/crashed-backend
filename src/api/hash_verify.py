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
        # Default salt if not provided
        salt = params.get('salt', 'bc_game_salt')

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

        # Process the hash and calculate crash points
        results = []
        current_hash = game_hash

        # Add 0x prefix if not present
        if not current_hash.startswith("0x"):
            current_hash = "0x" + current_hash

        # Calculate crash points for the specified number of games
        for i in range(count):
            try:
                # Calculate crash point for current hash
                crash_point = calculate_crash_point(current_hash, salt)

                # Add to results
                results.append({
                    'game_number': i + 1,
                    'hash': current_hash,
                    'crash_point': crash_point
                })

                # Calculate hash for previous game
                current_hash = calculate_previous_hash(current_hash)
            except Exception as e:
                logger.error(f"Error processing game {i+1}: {e}")
                # Skip this game and continue with the next
                current_hash = calculate_previous_hash(current_hash)
                continue

        # Return the results
        response_data = {
            'status': 'success',
            'salt': salt,
            'count': len(results),
            'results': results
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
