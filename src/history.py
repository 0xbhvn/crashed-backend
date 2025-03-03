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

# Import configuration from config.py
try:
    # When imported as part of the src package
    from src import config
    from src import database
except ImportError:
    # When run directly from the src directory
    import config
    import database


class BCCrashMonitor:
    def __init__(self, api_base_url=None, api_history_endpoint=None, game_url=None, salt=None, polling_interval=None):
        """
        Initialize the BC Game Crash Monitor

        Args:
            api_base_url: Base URL for the BC Game API (default from config)
            api_history_endpoint: API endpoint for crash history (default from config)
            game_url: Game URL path (default from config)
            salt: Salt value for crash calculation (default from config)
            polling_interval: Interval in seconds between API polls (default from config)
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

        # Database enabled flag
        self.database_enabled = os.getenv(
            'DATABASE_ENABLED', 'false').lower() == 'true'
        if self.database_enabled:
            self.logger.info("Database storage is enabled")
        else:
            self.logger.info("Database storage is disabled")

    def setup_logging(self):
        """Setup logging to both console and file"""
        # Get log settings from config
        log_file_path = config.LOG_FILE_PATH
        log_level = config.LOG_LEVEL

        # Create logger
        self.logger = logging.getLogger('bc_crash_monitor')
        self.logger.setLevel(log_level)

        # Check if handlers already exist
        if not self.logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)

            # Create file handler
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(log_level)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)

            # Add handlers to logger
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

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
        self.logger.info("Fetching crash history from API...")

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

                        # Extract the game history list
                        if response_data and response_data.get('data') and response_data['data'].get('list'):
                            game_list = response_data['data']['list']
                            self.logger.info(
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

                        # Create game data dictionary
                        result = {
                            'game_id': game_id,
                            'hash': hash_value,
                            'crash_point': crash_point,
                            'calculated_point': calculated_crash,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            # Add the original game detail
                            'game_detail': game_detail_str,
                            # Extract timing information
                            'endTime': game_detail.get('endTime'),
                            'prepareTime': game_detail.get('prepareTime'),
                            'beginTime': game_detail.get('beginTime')
                        }

                        # Add to new results
                        new_results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing game data: {e}")

            # Process results in reverse order (oldest to newest)
            if new_results:
                self.logger.info(f"Found {len(new_results)} new crash results")

                # First run, just record the latest game ID
                if not self.last_processed_game_id:
                    self.last_processed_game_id = new_results[0]['game_id']
                    self.logger.info(
                        f"Initialized with game ID {self.last_processed_game_id}")
                    return []

                # Process newest results first (they come in newest first)
                for result in reversed(new_results):
                    game_id = result['game_id']
                    hash_value = result['hash']
                    crash_point = result['crash_point']
                    calculated_crash = result['calculated_point']

                    # Log the result
                    self.logger.info(
                        f"New crash result: Game ID {game_id}, Crash Point {crash_point}x, Hash {hash_value[:8]}...")

                    # Store in memory
                    self.latest_hashes.appendleft(result)

                    # Store in database if enabled
                    if self.database_enabled:
                        try:
                            # Store in database
                            await database.store_crash_game(
                                game_id=game_id,
                                hash_value=hash_value,
                                crash_point=crash_point,
                                calculated_point=calculated_crash,
                                game_detail={
                                    'endTime': result.get('endTime'),
                                    'prepareTime': result.get('prepareTime'),
                                    'beginTime': result.get('beginTime')
                                }
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Error storing in database: {str(e)}")

                    # Notify callbacks
                    await self.notify_game_callbacks(result)

                # Update the last processed game ID
                self.last_processed_game_id = new_results[0]['game_id']

                # Update daily stats if database is enabled
                if self.database_enabled:
                    try:
                        await database.update_daily_stats()
                    except Exception as e:
                        self.logger.error(f"Error updating daily stats: {e}")

                return new_results
            else:
                return []
        except Exception as e:
            self.logger.error(f"Error in poll_and_process: {e}")
            return []

    def get_latest_results(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get the latest crash results from memory

        Args:
            limit: Maximum number of results to return

        Returns:
            List of game data dictionaries
        """
        if limit is None:
            return list(self.latest_hashes)
        else:
            return list(self.latest_hashes)[:limit]


async def main():
    """Main function for standalone operation"""
    # Initialize database if enabled
    if os.getenv('DATABASE_ENABLED', 'false').lower() == 'true':
        try:
            await database.init_database()
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            logging.warning("Continuing without database support")
            os.environ['DATABASE_ENABLED'] = 'false'

    # Create and run the monitor
    monitor = BCCrashMonitor()
    try:
        # Process continuously
        while True:
            await monitor.poll_and_process()
            await asyncio.sleep(monitor.polling_interval)
    except KeyboardInterrupt:
        monitor.logger.info("Interrupted by user, shutting down...")
        # Close database connection if enabled
        if os.getenv('DATABASE_ENABLED', 'false').lower() == 'true':
            await database.close_database()
    except Exception as e:
        monitor.logger.error(f"Error during execution: {e}")

if __name__ == "__main__":
    print("Starting BC Game Crash Monitor...")
    asyncio.run(main())
