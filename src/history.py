"""
BC Game Crash Monitor - History Module

This module contains the main BCCrashMonitor class that handles
fetching and processing crash game data from the BC Game API.
"""

import json
import time
import hmac
import math
import random
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from collections import deque
from typing import List, Dict, Any, Callable, Awaitable, Optional
import pytz
import os
import sys
import requests
import subprocess
import aiohttp

# Import from config
from . import config

# Import from utils
from .utils import configure_logging, fetch_game_history, process_game_data, APIError

# Import from db
from .db import get_database, CrashGame


class BCCrashMonitor:
    def __init__(self, api_base_url=None, api_history_endpoint=None, game_url=None, salt=None,
                 polling_interval=None, database_enabled=None, db_engine=None, verbose_logging=False):
        """
        Initialize the BC Crash Monitor.

        Args:
            api_base_url (str, optional): Base URL for the API. Defaults to config.API_BASE_URL.
            api_history_endpoint (str, optional): Endpoint for game history. Defaults to config.API_HISTORY_ENDPOINT.
            game_url (str, optional): Game URL path. Defaults to config.GAME_URL.
            salt (str, optional): Salt for crash point calculation. Defaults to config.BC_GAME_SALT.
            polling_interval (int, optional): Interval between API polls in seconds. Defaults to config.POLL_INTERVAL.
            database_enabled (bool, optional): Whether to store results in database. Defaults to config.DATABASE_ENABLED.
            db_engine: SQLAlchemy engine instance for database operations.
            verbose_logging (bool, optional): Whether to log detailed game results. Defaults to False.
        """
        # API configuration
        self.api_base_url = api_base_url or config.API_BASE_URL
        self.api_history_endpoint = api_history_endpoint or config.API_HISTORY_ENDPOINT
        self.game_url = game_url or config.GAME_URL
        self.salt = salt or config.BC_GAME_SALT

        # Polling configuration
        self.polling_interval = polling_interval or config.POLL_INTERVAL

        # Store latest hashes to avoid duplicates
        self.latest_hashes = deque(maxlen=config.MAX_HISTORY_SIZE)
        self.last_processed_game_id = None

        # Initialize the history list for the new implementation
        self.history = []
        self.max_history_size = config.MAX_HISTORY_SIZE

        # Game callbacks
        self.game_callbacks: List[Callable[[
            Dict[str, Any]], Awaitable[None]]] = []

        # Database configuration
        self.database_enabled = database_enabled if database_enabled is not None else config.DATABASE_ENABLED
        self.db_engine = db_engine
        if self.database_enabled and db_engine:
            self.logger.info("Database enabled, using provided engine")
        else:
            self.logger.info(
                f"Database storage is {'enabled' if self.database_enabled else 'disabled'}")

        # Logging
        self.logger = logging.getLogger("bc_crash_monitor")
        self.verbose_logging = verbose_logging

    def register_game_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Register a callback for new game events

        Args:
            callback: Async function that will be called with game data
        """
        self.game_callbacks.append(callback)
        self.logger.info(
            f"Registered new game callback, total callbacks: {len(self.game_callbacks)}")

    async def notify_game_callbacks(self, game_data: Dict[str, Any]):
        """
        Notify all registered callbacks about a new game

        Args:
            game_data: Game data dictionary with game details
        """
        for callback in self.game_callbacks:
            try:
                await callback(game_data)
            except Exception as e:
                self.logger.error(f"Error in game callback: {e}")

    @staticmethod
    def calculate_crash_point(seed, salt=None):
        """Calculate crash point using the BC Game algorithm"""
        # Use default salt from config if none is provided
        if salt is None:
            salt = config.BC_GAME_SALT

        # Generate the HMAC-SHA256 hash
        try:
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
            # Return 1.00 (the minimum crash point) on error
            return 1.00

    async def fetch_crash_history(self, page=1, page_size=50, force_refresh=False):
        """Fetch crash history from BC.GAME API or local history file"""
        self.logger.info(
            f"Fetching crash history: page={page}, size={page_size}, force_refresh={force_refresh}")

        if not force_refresh:
            try:
                # First, try to load from history file
                history = self.load_history()
                if history is not None:
                    # If history has enough items for the requested page
                    total_items = len(history)
                    start_idx = (page - 1) * page_size
                    if start_idx < total_items:
                        end_idx = min(start_idx + page_size, total_items)
                        self.logger.info(
                            f"Using cached history (items {start_idx+1}-{end_idx} of {total_items})")
                        return history[start_idx:end_idx]
                    else:
                        self.logger.info(
                            f"Cached history doesn't have page {page} (total items: {total_items})")
            except Exception as e:
                self.logger.error(f"Error loading cached history: {e}")

        # Use direct POST API call to fetch crash history
        try:
            self.logger.info(
                f"Fetching crash history from BC Game API: page={page}, size={page_size}")

            url = "https://bc.game/api/game/bet/multi/history"

            # Prepare JSON payload
            payload = {
                "gameUrl": "crash",
                "page": page,
                "pageSize": page_size
            }

            # Set standard headers (no cookies needed)
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Site": "same-origin",
                "Accept-Language": "en",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Mode": "cors",
                "Origin": "https://bc.game",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
                "Referer": "https://bc.game/game/crash",
                "Sec-Fetch-Dest": "empty"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"API request failed with status code {response.status}")
                        # Fall back to mock data if API request fails
                        return self.get_mock_crash_data(page, page_size)

                    data = await response.json()

                    # Process the response data to extract crash games
                    if 'data' in data and 'list' in data['data']:
                        items = self.extract_crash_games_from_response(
                            data['data']['list'])
                        self.logger.info(
                            f"Successfully retrieved {len(items)} items from BC.GAME API")
                        return items
                    else:
                        self.logger.error(
                            f"Unexpected API response format: {data}")
                        # Fall back to mock data if API response is not as expected
                        return self.get_mock_crash_data(page, page_size)

        except Exception as e:
            self.logger.error(f"Error fetching crash history from API: {e}")
            # Fall back to mock data if any exception occurs during API request
            return self.get_mock_crash_data(page, page_size)

    def extract_crash_games_from_response(self, game_list):
        """
        Extract crash game data from the new API response format.

        The new endpoint returns bet history which needs to be transformed to match
        our expected crash game format.

        Args:
            game_list: List of game objects from the BC Game API response

        Returns:
            List of formatted crash game data
        """
        try:
            games = []

            for game in game_list:
                try:
                    game_id = game.get('gameId', '')
                    # Game details are stored as a JSON string, need to parse it
                    game_detail_str = game.get('gameDetail', '{}')
                    game_detail = json.loads(game_detail_str)

                    # Extract fields from game_detail
                    crash_point = float(game_detail.get('rate', 1.0))
                    hash_value = game_detail.get('hash', '')
                    end_time = game_detail.get('endTime', 0)

                    # Convert timestamp to ISO format
                    if end_time:
                        created_at = datetime.fromtimestamp(
                            end_time / 1000).isoformat()
                    else:
                        created_at = datetime.now().isoformat()

                    game_data = {
                        'id': game_id,
                        'gameId': game_id,
                        'created_at': created_at,
                        'hash': hash_value,
                        'crash_point': crash_point
                    }
                    games.append(game_data)

                except Exception as e:
                    self.logger.error(
                        f"Error processing game {game.get('gameId', 'unknown')}: {e}")
                    continue

            return games
        except Exception as e:
            self.logger.error(
                f"Error extracting crash games from response: {e}")
            return []

    def get_mock_crash_data(self, page=1, page_size=50):
        """Get mock crash data as a fallback."""
        self.logger.info("Using mock crash data as fallback")

        try:
            # Generate some mock data with incrementing IDs
            mock_data = []
            base_time = datetime.now() - timedelta(hours=24)

            for i in range(page_size):
                idx = (page - 1) * page_size + i
                # Generate a deterministic hash based on the index
                hash_seed = f"mock_game_{idx}".encode('utf-8')
                game_hash = hashlib.sha256(hash_seed).hexdigest()

                # Generate a pseudo-random crash point between 1.0 and 10.0
                random.seed(idx)  # Set seed for reproducibility
                crash_point = round(1.0 + random.random() * 9.0, 2)

                # Create the mock game entry
                game_time = (base_time - timedelta(minutes=idx*2)).isoformat()
                game_id = f"{7000000 + idx}"

                mock_data.append({
                    'id': game_id,              # Include id for new code
                    'gameId': game_id,          # Include gameId for backward compatibility
                    'created_at': game_time,
                    'hash': game_hash,
                    'crash_point': crash_point
                })

            return mock_data

        except Exception as e:
            self.logger.error(f"Error generating mock data: {e}")
            return []

    async def poll_and_process(self) -> None:
        """Poll the BC Game API and process the latest crash games."""
        try:
            # Get the latest games from the API
            games = await self.get_latest_games()

            if not games:
                logger.warning("No games returned from API")
                return

            # Process each game
            for game in games:
                # Extract the game ID
                game_id = game.get('gameId') or game.get('id')

                # Skip if we've already processed this game
                if self.last_processed_game_id == game_id:
                    continue

                # Extract the hash value
                hash_value = game.get('hashValue') or game.get('hash')

                # Skip if we've already seen this hash
                if hash_value in self.latest_hashes:
                    continue

                # Add the hash to our deque to avoid duplicates
                self.latest_hashes.append(hash_value)

                # Extract the crash point
                crash_point = float(game.get('crashPoint'))

                # Create a timestamp
                created_at = game.get('createdAt')

                # Add the game to our history list
                game_data = {
                    'gameId': game_id,
                    'hashValue': hash_value,
                    'crashPoint': crash_point,
                    'createdAt': created_at
                }

                # Add to the beginning of the list (most recent first)
                self.history.insert(0, game_data)

                # Trim the history list if it exceeds the maximum size
                if len(self.history) > self.max_history_size:
                    self.history = self.history[:self.max_history_size]

                # Update the last processed game ID
                self.last_processed_game_id = game_id

                # Store in database if enabled
                if self.db_engine:
                    try:
                        # Create a dictionary with the game data
                        db_game = {
                            'gameId': game_id,
                            'hashValue': hash_value,
                            'crashPoint': crash_point,
                            'calculatedPoint': crash_point,  # For now, just use the same value
                            'createdAt': created_at
                        }

                        # Store the game in the database
                        from src.db.operations import store_crash_game
                        await store_crash_game(self.db_engine, db_game)
                    except Exception as e:
                        logger.error(f"Error storing game in database: {e}")

                # Call the game callbacks
                for callback in self.game_callbacks:
                    try:
                        await callback(game_data)
                    except Exception as e:
                        logger.error(f"Error in game callback: {e}")

        except Exception as e:
            logger.error(f"Error polling and processing games: {e}")

    async def run(self):
        """Run the monitor loop"""
        self.logger.info(
            f"Starting BC Game Crash Monitor with polling interval {self.polling_interval}s")

        while True:
            try:
                # Poll and process new games
                await self.poll_and_process()

                # Wait for the next polling interval
                await asyncio.sleep(self.polling_interval)
            except asyncio.CancelledError:
                self.logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                self.logger.info(
                    f"Retrying in {self.retry_interval} seconds...")
                await asyncio.sleep(self.retry_interval)

    def get_latest_results(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the latest crash results

        Args:
            limit: Maximum number of results to return (None for all)

        Returns:
            List of crash result dictionaries
        """
        if limit is None:
            return list(self.latest_hashes)
        else:
            return list(self.latest_hashes)[-limit:]

    def load_history(self):
        """Load crash history from local history file."""
        try:
            history_file = os.path.join(os.path.dirname(
                os.path.dirname(__file__)), "crash_history.json")
            if not os.path.exists(history_file):
                self.logger.warning(f"History file {history_file} not found")
                return None

            # Check if file is too old (> 1 hour)
            file_age = time.time() - os.path.getmtime(history_file)
            if file_age > 3600:  # 1 hour in seconds
                self.logger.warning(
                    f"History file is {file_age/3600:.1f} hours old, may be stale")

            with open(history_file, 'r') as f:
                data = json.load(f)

            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                self.logger.info(
                    f"Loaded {len(items)} items from history file")
                return items
            else:
                self.logger.warning("History file has unexpected format")
                return None
        except Exception as e:
            self.logger.error(f"Error loading history file: {e}")
            return None

    async def get_latest_games(self, max_games=50):
        """
        Get the latest games from BC.GAME API.

        Args:
            max_games: Maximum number of games to retrieve

        Returns:
            List of new game data dictionaries
        """
        try:
            # Fetch crash history from the API
            history_response = await self.fetch_crash_history()

            self.logger.info(
                f"Fetched history response: {type(history_response)}")

            # The fetch_crash_history now returns a list of game dictionaries directly
            if not history_response:
                self.logger.warning("No data received from API")
                return []

            history_data = history_response

            if not history_data:
                self.logger.warning("No games in API response")
                return []

            # Process only the new entries
            new_results = []
            for game_data in history_data:
                try:
                    game_id = game_data.get('id')

                    # Skip games that don't have an ID
                    if not game_id:
                        self.logger.warning(
                            f"Skipping game without ID: {game_data}")
                        continue

                    # Check if we already have this game in our history
                    if not self.is_new_game(game_id):
                        continue

                    # Add to new results
                    new_results.append(game_data)

                    # Stop once we have enough games
                    if len(new_results) >= max_games:
                        break
                except Exception as e:
                    self.logger.error(
                        f"Error processing game {game_data}: {e}")
                    continue

            return new_results
        except Exception as e:
            self.logger.error(f"Error getting latest games: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def is_new_game(self, game_id):
        """
        Check if a game is new (not already in our history).

        Args:
            game_id: The ID of the game to check

        Returns:
            bool: True if the game is new, False otherwise
        """
        # Check in memory cache first
        for game in self.latest_hashes:
            if game.get('id') == game_id:
                return False

        # If we have a DB, check there too
        if self.database_enabled and self.db_engine:
            try:
                from src.db.operations import check_game_exists
                if check_game_exists(self.db_engine, game_id):
                    return False
            except Exception as e:
                self.logger.error(f"Error checking if game exists in DB: {e}")

        return True

    def add_game_to_history(self, game_data):
        """
        Add a game to the in-memory history cache.

        Args:
            game_data: The game data to add
        """
        # Add to the front of the list (most recent first)
        self.latest_hashes.insert(0, game_data)

        # Trim history if it gets too large
        if len(self.latest_hashes) > config.MAX_HISTORY_SIZE:
            self.latest_hashes = self.latest_hashes[:config.MAX_HISTORY_SIZE]

    async def store_game_to_db(self, game_data):
        """
        Store a game in the database.

        Args:
            game_data: The game data to store
        """
        if not self.database_enabled or not self.db_engine:
            return

        try:
            from src.db.operations import store_crash_game

            # Format the game data for storing
            db_game = {
                'gameId': game_data.get('id'),
                'hashValue': game_data.get('hash'),
                'crashPoint': game_data.get('crash_point'),
                'createdAt': game_data.get('created_at')
            }

            # Store in the database
            await store_crash_game(self.db_engine, db_game)
            self.logger.debug(f"Stored game {db_game['gameId']} in database")
        except Exception as e:
            self.logger.error(f"Error storing game in database: {e}")
            raise


async def main():
    """Main entry point when run directly"""
    # Configure logging
    logger = configure_logging('bc_crash_monitor', config.LOG_LEVEL)

    # Create monitor instance
    monitor = BCCrashMonitor()

    # Register a callback to print new games
    async def print_game(game_data):
        print(
            f"New game: {game_data['gameId']} - Crash point: {game_data['crashPoint']}x")

    monitor.register_game_callback(print_game)

    # Run the monitor
    try:
        await monitor.run()
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")


if __name__ == "__main__":
    asyncio.run(main())
