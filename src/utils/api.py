"""
API utilities for BC Game Crash Monitor.

This module provides functions for interacting with the BC Game API,
including fetching game history and processing game data.
"""

import logging
import aiohttp
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

from .. import config

# Configure logging
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Exception raised for API errors."""
    pass


async def fetch_game_history(page: int = 1, base_url: str = None, endpoint: str = None) -> Dict[str, Any]:
    """
    Fetch game history from the BC Game API.

    Args:
        page: Page number to fetch
        base_url: API base URL (default from config)
        endpoint: API endpoint (default from config)

    Returns:
        Dictionary containing game history data

    Raises:
        APIError: If there was an error fetching the history
    """
    base_url = base_url or config.API_BASE_URL
    endpoint = endpoint or config.API_HISTORY_ENDPOINT

    url = f"{base_url}{endpoint}"

    # Prepare request payload based on the curl command
    payload = {
        "gameUrl": config.GAME_URL,
        "page": page,
        "pageSize": config.PAGE_SIZE
    }

    logger.info(f"Fetching game history from page {page}")

    try:
        async with aiohttp.ClientSession() as session:
            start_time = time.time()

            # Make POST request with proper headers and payload
            async with session.post(
                url,
                json=payload,
                headers=config.API_HEADERS,
                timeout=30
            ) as response:
                end_time = time.time()
                elapsed = end_time - start_time
                logger.debug(
                    f"API request completed in {elapsed:.2f}s (status: {response.status})")

                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f"API returned error: {response.status} - {error_text}")
                    raise APIError(
                        f"Failed to fetch game history: {response.status} - {error_text}")

                try:
                    json_data = await response.json()

                    # Check for the new response format (list instead of items)
                    if 'data' in json_data and 'list' in json_data['data']:
                        items_count = len(json_data['data']['list'])
                        logger.debug(
                            f"Fetched page {page} with {items_count} games")

                        # Convert to expected format for compatibility
                        converted_data = {
                            'data': {
                                'items': json_data['data']['list']
                            }
                        }
                        return converted_data
                    elif 'data' in json_data and 'items' in json_data['data']:
                        # Original format
                        items_count = len(json_data['data']['items'])
                        logger.debug(
                            f"Fetched page {page} with {items_count} games")
                        return json_data
                    else:
                        logger.warning(
                            f"Unexpected response format: {json_data}")
                        # Return empty result with expected structure
                        return {'data': {'items': []}}

                except json.JSONDecodeError as e:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to parse API response: {str(e)} - Response: {error_text[:200]}...")
                    raise APIError(f"Failed to parse API response: {str(e)}")
    except asyncio.TimeoutError:
        logger.error(f"API request timed out for page {page}")
        raise APIError(f"API request timed out for page {page}")
    except Exception as e:
        logger.error(f"Error fetching game history: {str(e)}")
        raise APIError(f"Failed to fetch game history: {str(e)}")


def process_game_data(game_data: Dict[str, Any], game_url: str = None) -> Dict[str, Any]:
    """
    Process game data to a standardized format.

    Args:
        game_data: Raw game data from the API
        game_url: Game URL (default from config)

    Returns:
        Standardized game data dictionary
    """
    game_url = game_url or config.GAME_URL

    # Create a copy to avoid modifying the original
    processed_data = {}

    try:
        # Extract game details if in JSON string format
        game_detail = {}
        if "gameDetail" in game_data and isinstance(game_data["gameDetail"], str):
            try:
                game_detail = json.loads(game_data["gameDetail"])
                logger.debug(f"Parsed game detail JSON: {game_detail.keys()}")
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse gameDetail JSON: {game_data['gameDetail']}")

        # Basic fields every game should have
        processed_data = {
            "gameId": str(game_data.get("gameId", ""))
        }

        # Extract crash point from gameDetail
        if "rate" in game_detail:
            try:
                processed_data["crashPoint"] = float(game_detail["rate"])
            except (ValueError, TypeError):
                processed_data["crashPoint"] = 1.0  # Default value
        else:
            # Fallback to payOut if available
            processed_data["crashPoint"] = float(game_data.get("payOut", 1.0))

        # Add hash value if available
        if "hash" in game_data:
            processed_data["hashValue"] = str(game_data["hash"])
        elif "hash" in game_detail:
            processed_data["hashValue"] = str(game_detail["hash"])

        # Add timestamps if available
        if "endTime" in game_data:
            processed_data["endTime"] = datetime.fromtimestamp(
                game_data["endTime"] / 1000) if game_data["endTime"] else None
        if "prepareTime" in game_data:
            processed_data["prepareTime"] = datetime.fromtimestamp(
                game_data["prepareTime"] / 1000) if game_data["prepareTime"] else None
        if "beginTime" in game_data:
            processed_data["beginTime"] = datetime.fromtimestamp(
                game_data["beginTime"] / 1000) if game_data["beginTime"] else None

        # Add crashed floor value
        if "crashPoint" in processed_data:
            processed_data["crashedFloor"] = int(processed_data["crashPoint"])

        # Add additional fields from gameDetail that match our model
        if game_detail:
            for field in ["prepareTime", "beginTime", "endTime"]:
                if field in game_detail and field not in processed_data:
                    try:
                        # Convert timestamp to datetime
                        timestamp_val = int(game_detail[field])
                        processed_data[field] = datetime.fromtimestamp(
                            timestamp_val / 1000.0)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to convert {field}: {e}")

        # Add additional fields from the original data
        for src_field, dest_field in [
            ("status", "status"),
            ("betAmount", "betAmount"),
            ("profit", "profit"),
            ("currency", "currency")
        ]:
            if src_field in game_data:
                processed_data[dest_field] = game_data[src_field]

        # Debugging
        logger.debug(
            f"Processed game {processed_data['gameId']} with crash point {processed_data.get('crashPoint', 'unknown')}")

    except Exception as e:
        logger.error(f"Error processing game data: {e}")
        # Return a basic structure with error info to avoid breaking the flow
        if not processed_data:
            processed_data = {
                "gameId": str(game_data.get("gameId", "")),
                "error": str(e),
            }

    return processed_data


async def fetch_games_batch(start_page: int = 1, num_pages: int = 1,
                            base_url: str = None, endpoint: str = None,
                            game_url: str = None, end_page: int = None,
                            batch_size: int = None) -> List[Dict[str, Any]]:
    """
    Fetch multiple pages of game history concurrently.

    Args:
        start_page: Starting page number
        num_pages: Number of pages to fetch
        base_url: API base URL (default from config)
        endpoint: API endpoint (default from config)
        game_url: Game URL (default from config)
        end_page: End page number (overrides num_pages if provided)
        batch_size: Batch size for concurrent requests (not used, kept for compatibility)

    Returns:
        List of processed game data dictionaries
    """
    # Use default values from config if not provided
    base_url = base_url or config.API_BASE_URL
    endpoint = endpoint or config.API_HISTORY_ENDPOINT
    game_url = game_url or config.GAME_URL

    # Calculate the number of pages to fetch
    if end_page is not None:
        num_pages = end_page - start_page + 1

    tasks = []
    all_games = []

    # Create tasks for each page
    for page_offset in range(num_pages):
        page = start_page + page_offset
        tasks.append(fetch_game_history(page, base_url, endpoint))

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Error fetching page: {result}")
            continue

        # Extract games from the response
        if 'data' in result and 'items' in result['data']:
            game_items = result['data']['items']

            # Process each game
            for game in game_items:
                try:
                    processed_game = process_game_data(game, game_url)
                    all_games.append(processed_game)
                except Exception as e:
                    logger.error(f"Error processing game data: {str(e)}")

    logger.info(f"Fetched {len(all_games)} games from {num_pages} pages")
    return all_games
