import logging
import json
import asyncio
import aiohttp
import os
import sys
from datetime import datetime
from collections import deque
import hashlib
import hmac
import math
from typing import List, Dict, Any, Callable, Awaitable, Optional
import pytz

# Import configuration from config.py
from . import config


class BCCrashMonitor:
    def __init__(self, api_base_url=None, api_history_endpoint=None, game_url=None, salt=None,
                 polling_interval=None, database_enabled=None, session_factory=None):
        """
        Initialize the BC Game Crash Monitor

        Args:
            api_base_url: Base URL for the BC Game API (default from config)
            api_history_endpoint: API endpoint for crash history (default from config)
            game_url: Game URL path (default from config)
            salt: Salt value for crash calculation (default from config)
            polling_interval: Interval in seconds between API polls (default from config)
            database_enabled: Whether to store games in the database
            session_factory: Database session factory (required if database_enabled is True)
        """
        # Use provided values or defaults from config
        self.api_base_url = api_base_url or config.API_BASE_URL
        self.api_history_endpoint = api_history_endpoint or config.API_HISTORY_ENDPOINT
        self.game_url = game_url or config.GAME_URL
        self.salt = salt or config.BC_GAME_SALT
        self.polling_interval = polling_interval or config.POLL_INTERVAL
        self.retry_interval = config.RETRY_INTERVAL

        # Get max history size from config
        self.latest_hashes = deque(maxlen=config.MAX_HISTORY_SIZE)
        self.last_processed_game_id = None

        # Set up callbacks for game events
        self.game_callbacks: List[Callable[[
            Dict[str, Any]], Awaitable[None]]] = []

        # Set up logging
        self.setup_logging()

        # Database settings
        self.database_enabled = database_enabled if database_enabled is not None else \
            os.getenv('DATABASE_ENABLED', 'false').lower() == 'true'
        self.session_factory = session_factory

        if self.database_enabled:
            if not self.session_factory:
                self.logger.warning(
                    "Database is enabled but no session factory provided. Database operations will be skipped.")
                self.database_enabled = False
            else:
                self.logger.info("Database storage is enabled")
        else:
            self.logger.info("Database storage is disabled")

    def setup_logging(self):
        """Setup logging to both console and file"""
        # Get log settings from config
        log_level = config.LOG_LEVEL

        # Create logger
        self.logger = logging.getLogger('bc_crash_monitor')
        self.logger.setLevel(log_level)

        # Prevent propagation to root logger to avoid duplicate logs
        self.logger.propagate = False

        # Check if handlers already exist
        if not self.logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)

            # Add handler to logger
            self.logger.addHandler(console_handler)

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

    async def fetch_crash_history(self):
        """Fetch crash game history directly from the BC Game API using the exact curl parameters"""
        self.logger.debug("Fetching crash history from API...")

        # Get API settings from config
        url = f"{self.api_base_url}{self.api_history_endpoint}"

        # Headers from config
        headers = config.DEFAULT_HEADERS

        # Data based on the curl command
        data = {
            "gameUrl": self.game_url,
            "page": 1,
            "pageSize": config.PAGE_SIZE
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        response_text = await response.text()
                        response_data = json.loads(response_text)

                        # Check for 'list' field in the response (new API format)
                        if response_data and response_data.get('data') and response_data['data'].get('list'):
                            game_list = response_data['data']['list']
                            self.logger.debyg(
                                f"Successfully fetched {len(game_list)} crash history records")
                            return game_list

                        # Check for 'data' field in the response (old API format)
                        elif response_data and response_data.get('data') and response_data['data'].get('data'):
                            game_list = response_data['data']['data']
                            self.logger.debug(
                                f"Successfully fetched {len(game_list)} crash history records")
                            return game_list
                        else:
                            self.logger.error(
                                f"API response missing expected data: {response_text[:200]}...")
                            return []
                    else:
                        self.logger.error(f"API request failed with status {response.status}: {await response.text()}")
                        return []
        except Exception as e:
            self.logger.error(f"Error fetching crash history: {e}")
            return []

    async def poll_and_process(self) -> List[Dict[str, Any]]:
        """
        Poll the API and process new crash games

        Returns:
            List of new game data dictionaries
        """
        try:
            # Fetch crash history from the API
            history_data = await self.fetch_crash_history()

            if not history_data:
                self.logger.warning(f"No data received from API")
                return []

            # Process only the new entries
            new_results = []
            for game_data in history_data:
                game_id = game_data.get('gameId')

                # Skip if we've already processed this game
                if game_id == self.last_processed_game_id:
                    break

                # Extract data from gameDetail JSON string
                try:
                    game_detail_str = game_data.get('gameDetail', '{}')
                    game_detail = json.loads(game_detail_str)
                    hash_value = game_detail.get('hash')
                    crash_point = float(game_detail.get('rate', 0))

                    if hash_value:
                        # Calculate crash point using the hash as the seed
                        calculated_crash = self.calculate_crash_point(
                            seed=hash_value, salt=self.salt)

                        # Get timezone from config
                        app_timezone = pytz.timezone(config.TIMEZONE)

                        # Convert Unix timestamps to datetime with proper timezone
                        def convert_timestamp(ts):
                            if not ts:
                                return None
                            # Convert milliseconds to seconds
                            return datetime.fromtimestamp(ts / 1000, tz=app_timezone)

                        # Create game data dictionary
                        result = {
                            'gameId': game_id,
                            'hashValue': hash_value,
                            'crashPoint': crash_point,
                            'calculatedPoint': calculated_crash,
                            # Convert Unix timestamps to datetime objects with timezone
                            'endTime': convert_timestamp(game_detail.get('endTime')),
                            'prepareTime': convert_timestamp(game_detail.get('prepareTime')),
                            'beginTime': convert_timestamp(game_detail.get('beginTime'))
                        }

                        # Add to new results
                        new_results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing game data: {e}")

            # Process results in reverse order (oldest to newest)
            if new_results:
                if len(new_results) == 1:
                    # For a single result, include game_id and crash point
                    game = new_results[0]
                    self.logger.info(
                        f"Found 1 new crash result: Game #{game['gameId']} with crash point {game['crashPoint']}x")
                else:
                    # For multiple results, just show the count
                    self.logger.info(
                        f"Found {len(new_results)} new crash results")

                # First run, just record the latest game ID
                if self.last_processed_game_id is None and new_results:
                    self.last_processed_game_id = new_results[0]['gameId']
                    self.logger.info(
                        f"First run, setting last processed game ID to {self.last_processed_game_id}")
                    return []

                # Process in reverse order (oldest to newest)
                for result in reversed(new_results):
                    # Store in database if enabled
                    if self.database_enabled and self.session_factory:
                        try:
                            # Store game in database
                            from .models import CrashGame

                            with self.session_factory() as session:
                                # Check if game already exists
                                existing_game = session.query(CrashGame).filter(
                                    CrashGame.gameId == result['gameId']).first()

                                if not existing_game:
                                    # Create new game object
                                    new_game = CrashGame(**result)
                                    session.add(new_game)
                                    session.commit()
                                    self.logger.debug(
                                        f"Stored game #{result['gameId']} with crash point {result['crashPoint']}x in database")
                        except Exception as e:
                            self.logger.error(
                                f"Error storing game in database: {e}")

                    # Notify callbacks
                    await self.notify_game_callbacks(result)

                    # Add to latest hashes
                    self.latest_hashes.append(result)

                # Update last processed game ID
                if new_results:
                    self.last_processed_game_id = new_results[0]['gameId']
                    self.logger.debug(
                        f"Updated last processed game ID to {self.last_processed_game_id}")

                return new_results
            else:
                self.logger.debug("No new crash results found")
                return []

        except Exception as e:
            self.logger.error(f"Error in poll_and_process: {e}")
            return []

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


async def main():
    """Main entry point when run directly"""
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
        print("Monitor stopped by user")


if __name__ == "__main__":
    asyncio.run(main())
