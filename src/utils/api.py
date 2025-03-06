"""
API utilities for BC Game Crash Monitor.

This module provides functions for interacting with the BC Game API,
including fetching game history and processing game data.
"""

import logging
import os
import json
import aiohttp
import asyncio
import subprocess
import random
import time
import pytz
from typing import Dict, List, Any, Optional
from datetime import datetime

from .. import config

# Configure logging
logger = logging.getLogger(__name__)

# Track consecutive failures
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 3


class APIError(Exception):
    """Exception raised for API errors."""
    pass


async def fetch_game_history(page: int = 1, page_size: int = None, base_url: str = None, endpoint: str = None) -> Dict[str, Any]:
    """
    Fetch game history from BC Game by executing the shell script.

    Args:
        page: Page number to fetch (used for updating the script data payload)
        page_size: Number of items per page (default is 50, max is 1000)
        base_url: API base URL (not used with shell script approach)
        endpoint: API endpoint (not used with shell script approach)

    Returns:
        Dictionary containing game history data

    Raises:
        APIError: If there was an error fetching the history
    """
    global consecutive_failures

    # Use default page size from config if not specified
    if page_size is None:
        page_size = int(os.environ.get('PAGE_SIZE', '20'))

    logger.info(
        f"Fetching game history from page {page} with size {page_size} using shell script")

    try:
        # Path to the shell script relative to current working directory
        script_path = os.path.join(os.getcwd(), "fetch_crash_history.sh")

        # Ensure the script is executable
        os.chmod(script_path, 0o755)

        # Add a small random delay to avoid rate limiting
        await asyncio.sleep(random.uniform(0.5, 2.0))

        # Prepare output file name for this page to avoid conflicts with concurrent requests
        json_file_path = os.path.join(
            os.getcwd(), f"crash_history_p{page}_s{page_size}.json")

        start_time = time.time()

        # Execute the shell script using subprocess with page parameter
        # This will create the JSON file in the current directory
        process = await asyncio.create_subprocess_exec(
            script_path,
            "--page", str(page),
            "--size", str(page_size),
            "--output", json_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the script to complete
        stdout, stderr = await process.communicate()

        end_time = time.time()
        elapsed = end_time - start_time

        if process.returncode != 0:
            logger.error(f"Shell script execution failed: {stderr.decode()}")
            consecutive_failures += 1
            raise APIError(
                f"Failed to fetch game history: Shell script returned {process.returncode}")

        logger.debug(f"Shell script completed in {elapsed:.2f}s")

        # Read the results from the JSON file
        try:
            with open(json_file_path, 'r') as f:
                file_content = f.read()
                logger.debug(
                    f"Read {len(file_content)} bytes from {json_file_path}")

                # Check if the file contains HTML (Cloudflare challenge) instead of JSON
                if file_content.strip().startswith('<!DOCTYPE html>') or '<html' in file_content[:100]:
                    logger.warning(
                        "Received Cloudflare challenge instead of JSON. API access may be blocked.")
                    consecutive_failures += 1

                    # Return an empty result with expected structure to prevent crashing
                    return {'data': {'items': []}}

                # If the file is empty, return empty result
                if not file_content.strip():
                    logger.warning(f"Empty JSON file: {json_file_path}")
                    consecutive_failures += 1
                    return {'data': {'items': []}}

                # Try to parse the JSON
                json_data = json.loads(file_content)

                # Reset the failure counter on success
                consecutive_failures = 0

                # Clean up the file after reading it
                try:
                    os.remove(json_file_path)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove temporary file {json_file_path}: {e}")

            # Check for the right format in the JSON data
            if 'data' in json_data and 'list' in json_data['data']:
                items_count = len(json_data['data']['list'])
                logger.debug(
                    f"Fetched page {page} with {items_count} games from file")

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
                logger.debug(f"Fetched page {page} with {items_count} games")
                return json_data
            else:
                logger.warning(f"Unexpected response format in JSON file")
                consecutive_failures += 1
                # Return empty result with expected structure
                return {'data': {'items': []}}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON file: {str(e)}")
            consecutive_failures += 1
            raise APIError(f"Failed to parse JSON file: {str(e)}")
        except FileNotFoundError:
            logger.error(f"JSON file not found at {json_file_path}")
            consecutive_failures += 1
            raise APIError(f"JSON file not found at {json_file_path}")

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Error fetching game history: {str(e)}")
        consecutive_failures += 1
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


async def fetch_games_batch(start_page: int = 1, num_pages: int = 1,
                            base_url: str = None, endpoint: str = None,
                            game_url: str = None, end_page: int = None,
                            batch_size: int = None, page_size: int = None) -> List[Dict[str, Any]]:
    """
    Fetch multiple pages of game history concurrently using shell script.

    Args:
        start_page: Starting page number
        num_pages: Number of pages to fetch
        base_url: API base URL (not used with shell script approach)
        endpoint: API endpoint (not used with shell script approach)
        game_url: Game URL (default from config)
        end_page: End page number (overrides num_pages if provided)
        batch_size: Batch size for concurrent requests (default from config)
        page_size: Number of items per page (default is 20, max is 100)

    Returns:
        List of processed game data dictionaries
    """
    # Use default values from config if not provided
    game_url = game_url or config.GAME_URL
    # Default to a smaller batch to be safe
    batch_size = batch_size or min(config.CONCURRENCY_LIMIT, 3)
    # Use default page size if not provided
    page_size = page_size or int(os.environ.get('PAGE_SIZE', '20'))

    # Calculate the number of pages to fetch
    if end_page is not None:
        num_pages = end_page - start_page + 1

    logger.info(
        f"Fetching {num_pages} pages starting from page {start_page} with batch size {batch_size}")

    tasks = []
    all_games = []
    error_count = 0
    max_errors = num_pages // 2  # Allow up to half of requests to fail

    # Create tasks for each page
    for page_offset in range(num_pages):
        page = start_page + page_offset
        tasks.append(fetch_game_history(page, page_size=page_size))

    # Process in batches to avoid too many concurrent processes
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_start = i + start_page
        batch_end = min(i + batch_size + start_page -
                        1, start_page + num_pages - 1)

        logger.info(
            f"Processing batch {i//batch_size + 1}/{(len(tasks)-1)//batch_size + 1}: pages {batch_start}-{batch_end}")

        # Wait for all tasks in this batch to complete
        results = await asyncio.gather(*batch, return_exceptions=True)

        # Process results
        empty_results = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching page: {result}")
                error_count += 1
                continue

            # Extract games from the response
            if 'data' in result and 'items' in result['data']:
                game_items = result['data']['items']

                # Check if we're getting empty results which might indicate API blocking
                if not game_items:
                    empty_results += 1

                # Process each game
                for game in game_items:
                    try:
                        processed_game = process_game_data(game, game_url)
                        all_games.append(processed_game)
                    except Exception as e:
                        logger.error(f"Error processing game data: {str(e)}")

        # If all results in this batch were empty, log a warning
        if empty_results == len(results):
            logger.warning(
                f"Batch {i//batch_size + 1} returned all empty results - API access may be limited")

        # If we have too many errors, abort
        if error_count > max_errors:
            logger.error(
                f"Too many errors ({error_count}/{num_pages}), aborting batch fetch")
            break

        # Add a delay between batches to avoid overwhelming the API
        if i + batch_size < len(tasks):
            delay = random.uniform(1.0, 3.0)
            logger.debug(f"Sleeping for {delay:.2f}s between batches")
            await asyncio.sleep(delay)

    logger.info(f"Fetched {len(all_games)} games from {num_pages} pages")
    return all_games
