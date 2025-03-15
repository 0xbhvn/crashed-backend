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
import pytz

from .. import config

# Configure logging
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Exception raised for API errors."""
    pass


class BCGameAPI:
    """Client for BC Game API operations"""

    def __init__(self, base_url: Optional[str] = None, history_endpoint: Optional[str] = None,
                 game_url: Optional[str] = None):
        """
        Initialize the BC Game API client

        Args:
            base_url: Base URL for the API (default from config)
            history_endpoint: Endpoint for game history (default from config)
            game_url: Game URL path (default from config)
        """
        self.base_url = base_url or config.API_BASE_URL
        self.history_endpoint = history_endpoint or config.API_HISTORY_ENDPOINT
        self.game_url = game_url or config.GAME_URL
        self.logger = logging.getLogger(__name__)

    async def fetch_game_history(self, page: int = 1) -> Dict[str, Any]:
        """
        Fetch game history from the BC Game API.

        Args:
            page: Page number to fetch

        Returns:
            Dictionary containing game history data

        Raises:
            APIError: If there was an error fetching the history
        """
        url = f"{self.base_url}{self.history_endpoint}"

        # Prepare request payload based on the curl command
        payload = {
            "gameUrl": self.game_url,
            "page": page,
            "pageSize": config.PAGE_SIZE
        }

        self.logger.info(f"Fetching game history from page {page}")

        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()

                # Debug: Log full request details
                debug_info = {
                    "url": url,
                    "headers": config.API_HEADERS,
                    "payload": payload
                }
                self.logger.debug(
                    f"API Request details: {json.dumps(debug_info, indent=2)}")

                # Make POST request with proper headers and payload
                async with session.post(
                    url,
                    json=payload,
                    headers=config.API_HEADERS,
                    timeout=30
                ) as response:
                    end_time = time.time()
                    elapsed = end_time - start_time
                    self.logger.debug(
                        f"API request completed in {elapsed:.2f}s (status: {response.status})")

                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(
                            f"API returned error: {response.status} - {error_text}")
                        raise APIError(
                            f"Failed to fetch game history: {response.status} - {error_text}")

                    try:
                        json_data = await response.json()

                        # Check for the new response format (list instead of items)
                        if 'data' in json_data and 'list' in json_data['data']:
                            items_count = len(json_data['data']['list'])
                            self.logger.debug(
                                f"Fetched page {page} with {items_count} games")

                            # Convert to expected format for compatibility
                            converted_data = {
                                'data': {
                                    'items': json_data['data']['list'],
                                    # Preserve pagination metadata
                                    'page': json_data['data'].get('page', page),
                                    'pageSize': json_data['data'].get('pageSize', config.PAGE_SIZE),
                                    'total': json_data['data'].get('total', 0),
                                    'totalPage': json_data['data'].get('totalPage', 0)
                                }
                            }
                            return converted_data
                        elif 'data' in json_data and 'items' in json_data['data']:
                            # Original format
                            items_count = len(json_data['data']['items'])
                            self.logger.debug(
                                f"Fetched page {page} with {items_count} games")
                            return json_data
                        else:
                            self.logger.warning(
                                f"Unexpected response format: {json_data}")
                            # Return empty result with expected structure
                            return {'data': {'items': []}}

                    except json.JSONDecodeError as e:
                        error_text = await response.text()
                        self.logger.error(
                            f"Failed to parse API response: {str(e)} - Response: {error_text[:200]}...")
                        raise APIError(
                            f"Failed to parse API response: {str(e)}")
        except asyncio.TimeoutError:
            self.logger.error(f"API request timed out for page {page}")
            raise APIError(f"API request timed out for page {page}")
        except Exception as e:
            self.logger.error(f"Error fetching game history: {str(e)}")
            raise APIError(f"Failed to fetch game history: {str(e)}")

    async def fetch_games_batch(self, start_page: int = 1, num_pages: int = 1,
                                end_page: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch multiple pages of game history concurrently.

        Args:
            start_page: Starting page number
            num_pages: Number of pages to fetch
            end_page: End page number (overrides num_pages if provided)

        Returns:
            List of processed game data dictionaries
        """
        # Calculate the number of pages to fetch
        if end_page is not None:
            num_pages = end_page - start_page + 1

        tasks = []
        all_games = []

        # Create tasks for each page
        for page_offset in range(num_pages):
            page = start_page + page_offset
            tasks.append(self.fetch_game_history(page))

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error fetching page: {result}")
                continue

            # Extract games from the response
            if 'data' in result and 'items' in result['data']:
                game_items = result['data']['items']

                # Process each game
                for game in game_items:
                    try:
                        processed_game = process_game_data(game, self.game_url)
                        all_games.append(processed_game)
                    except Exception as e:
                        self.logger.error(
                            f"Error processing game data: {str(e)}")

        self.logger.info(
            f"Fetched {len(all_games)} games from {num_pages} pages")
        return all_games

    async def fetch_game_by_id(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific game by its ID from the BC Game API.

        Args:
            game_id: The game ID to fetch

        Returns:
            Processed game data dictionary or None if game not found
        """
        self.logger.info(f"Fetching specific game by ID: {game_id}")

        try:
            # First try to get the game from recent history
            history_response = await self.fetch_game_history(page=1)

            if history_response and 'data' in history_response and 'items' in history_response['data']:
                for game in history_response['data']['items']:
                    if str(game.get('gameId', '')) == str(game_id):
                        self.logger.info(
                            f"Found game {game_id} in recent history")
                        return process_game_data(game, self.game_url)

            # If not found in first page, try a few more pages
            for page in range(2, 5):  # Try pages 2-4
                history_response = await self.fetch_game_history(page=page)

                if history_response and 'data' in history_response and 'items' in history_response['data']:
                    for game in history_response['data']['items']:
                        if str(game.get('gameId', '')) == str(game_id):
                            self.logger.info(
                                f"Found game {game_id} in history page {page}")
                            return process_game_data(game, self.game_url)

            self.logger.warning(
                f"Game {game_id} not found in recent history pages")
            return None

        except APIError as e:
            self.logger.error(f"API error fetching game by ID: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching game by ID: {e}")
            return None


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

        # Get the timezone inside the function to avoid circular imports
        app_timezone = pytz.timezone(config.TIMEZONE)

        # Add timestamps if available
        if "endTime" in game_data:
            processed_data["endTime"] = datetime.fromtimestamp(
                game_data["endTime"] / 1000, tz=app_timezone) if game_data["endTime"] else None
        if "prepareTime" in game_data:
            processed_data["prepareTime"] = datetime.fromtimestamp(
                game_data["prepareTime"] / 1000, tz=app_timezone) if game_data["prepareTime"] else None
        if "beginTime" in game_data:
            processed_data["beginTime"] = datetime.fromtimestamp(
                game_data["beginTime"] / 1000, tz=app_timezone) if game_data["beginTime"] else None

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
                            timestamp_val / 1000, tz=app_timezone) if timestamp_val else None
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Error converting timestamp for {field}: {e}")

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


# Create convenience functions that use the API class for backward compatibility
async def fetch_game_history(page: int = 1, base_url: Optional[str] = None,
                             endpoint: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch game history from the BC Game API (Backward-compatible function).

    Args:
        page: Page number to fetch
        base_url: API base URL (default from config)
        endpoint: API endpoint (default from config)

    Returns:
        Dictionary containing game history data
    """
    api = BCGameAPI(base_url=base_url, history_endpoint=endpoint)
    return await api.fetch_game_history(page)


async def fetch_games_batch(start_page: int = 1, num_pages: int = 1,
                            base_url: Optional[str] = None, endpoint: Optional[str] = None,
                            game_url: Optional[str] = None, end_page: Optional[int] = None,
                            batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch multiple pages of game history concurrently (Backward-compatible function).

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
    api = BCGameAPI(base_url=base_url,
                    history_endpoint=endpoint, game_url=game_url)
    return await api.fetch_games_batch(start_page, num_pages, end_page)


async def fetch_game_by_id(game_id: str, base_url: Optional[str] = None,
                           endpoint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific game by its ID from the BC Game API (Backward-compatible function).

    Args:
        game_id: The game ID to fetch
        base_url: API base URL (default from config)
        endpoint: API endpoint (default from config)

    Returns:
        Processed game data dictionary or None if game not found
    """
    api = BCGameAPI(base_url=base_url, history_endpoint=endpoint)
    return await api.fetch_game_by_id(game_id)
