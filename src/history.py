"""
BC Game Crash Monitor - History Module

This module contains the main BCCrashMonitor class that handles
fetching and processing crash game data from the BC Game API.
"""

import json
import asyncio
import hmac
import math
import logging
from datetime import datetime
from collections import deque
import hashlib
from typing import List, Dict, Any, Callable, Awaitable, Optional
import pytz

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
        self.retry_interval = config.RETRY_INTERVAL
        self.event_driven = False  # New flag to indicate if running in event-driven mode

        # Store latest hashes to avoid duplicates
        self.latest_hashes = deque(maxlen=config.MAX_HISTORY_SIZE)
        self.last_processed_game_id = None

        # Game callbacks
        self.game_callbacks: List[Callable[[
            Dict[str, Any]], Awaitable[None]]] = []

        # Database configuration
        self.database_enabled = database_enabled if database_enabled is not None else config.DATABASE_ENABLED
        self.db = None
        if self.database_enabled and db_engine:
            from src.db.engine import get_database
            self.db = get_database(db_engine)

        # Logging
        self.logger = logging.getLogger("bc_crash_monitor")
        self.verbose_logging = verbose_logging

        # Event-related attributes
        self.running = False
        self.event_queue = asyncio.Queue()

        self.logger.info(
            f"Database storage is {'enabled' if self.database_enabled else 'disabled'}")

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
        """Fetch crash game history from the BC Game API using the utility function"""
        self.logger.debug("Fetching crash history from API...")

        try:
            # Use the utility function to fetch game history
            game_list = await fetch_game_history(
                base_url=self.api_base_url,
                endpoint=self.api_history_endpoint,
                page=1
            )

            self.logger.debug(
                f"Successfully fetched {len(game_list)} crash history records")
            return game_list

        except APIError as e:
            self.logger.error(f"API error fetching crash history: {e}")
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
            history_response = await self.fetch_crash_history()

            if not history_response or 'data' not in history_response or 'items' not in history_response['data']:
                self.logger.warning(
                    f"No data received from API or invalid format")
                return []

            history_data = history_response['data']['items']

            if not history_data:
                self.logger.warning(f"No games in API response")
                return []

            # Process only the new entries
            new_results = []
            for game_data in history_data:
                try:
                    game_id = game_data.get('gameId')

                    if not game_id:
                        self.logger.warning(
                            f"Game data missing gameId: {game_data}")
                        continue

                    # Skip if we've already processed this game
                    if game_id == self.last_processed_game_id:
                        self.logger.debug(
                            f"Found last processed game {game_id}, stopping")
                        break

                    # Process the game data using the utility function
                    processed_data = process_game_data(game_data)

                    # Calculate crash point using the hash as the seed
                    hash_value = processed_data.get('hashValue')
                    if hash_value:
                        calculated_crash = self.calculate_crash_point(
                            seed=hash_value, salt=self.salt)
                        processed_data['calculatedPoint'] = calculated_crash

                    # Add to new results
                    new_results.append(processed_data)
                    self.logger.debug(f"Added new game {game_id} to results")
                except Exception as e:
                    self.logger.error(
                        f"Error processing individual game data: {e}")

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
                    if self.database_enabled and self.db:
                        try:
                            # Store game in database using the db module
                            with self.db.get_session() as session:
                                # Check if game already exists
                                existing_game = session.query(CrashGame).filter(
                                    CrashGame.gameId == result['gameId']
                                ).first()

                                if not existing_game:
                                    # Create new game object
                                    new_game = CrashGame(**result)
                                    session.add(new_game)
                                    session.commit()
                        except Exception as e:
                            self.logger.error(
                                f"Error storing game in database: {e}")

                    # Update last processed ID
                    self.last_processed_game_id = result['gameId']

                    # Notify callbacks
                    await self.notify_game_callbacks(result)

                    # Log for single game results only if verbose logging is enabled
                    if self.verbose_logging and len(new_results) == 1:
                        self.logger.info(
                            f"Found 1 new crash result: Game #{result['gameId']} with crash point {result['crashPoint']}x")

                # Log the overview only if verbose logging is enabled
                if self.verbose_logging and len(new_results) > 1:
                    self.logger.info(
                        f"Found {len(new_results)} new crash results")

                return new_results
            else:
                self.logger.debug("No new crash results found")
                return []

        except Exception as e:
            self.logger.error(f"Error in poll_and_process: {e}")
            return []

    async def process_game_event(self, game_data):
        """
        Process a game event received directly from the observer.

        This method allows external observers to directly feed game data
        into the monitor without going through the polling mechanism.

        Args:
            game_data: Dictionary with game information
                Required keys:
                - gameId: ID of the game
                - crashPoint: Crash point value (can be float or string with 'x')
        """
        try:
            # Validate required fields
            if 'gameId' not in game_data or 'crashPoint' not in game_data:
                self.logger.error("Missing required game data fields")
                return False

            # Convert crash_point to proper format if needed
            crash_point = game_data['crashPoint']
            if isinstance(crash_point, str) and crash_point.endswith('x'):
                crash_point = float(crash_point[:-1])

            # Skip if we've already processed this game
            if self.last_processed_game_id == game_data['gameId']:
                self.logger.debug(
                    f"Skipping already processed game {game_data['gameId']}")
                return False

            # Process the game
            self.logger.info(
                f"Processing direct game event: {game_data['gameId']} with crash point {crash_point}x")

            # Update last processed ID
            self.last_processed_game_id = game_data['gameId']

            # First, try to get complete game data from the API
            complete_data = None
            try:
                # Import the fetch_game_by_id function
                from .utils.api import fetch_game_by_id

                # Try to fetch the complete game data by ID
                self.logger.info(
                    f"Attempting to fetch complete data for game {game_data['gameId']}")
                api_game = await fetch_game_by_id(
                    game_id=game_data['gameId'],
                    base_url=self.api_base_url,
                    endpoint=self.api_history_endpoint
                )

                if api_game:
                    self.logger.info(
                        f"Found complete data for game {game_data['gameId']} from API")

                    # Calculate crash point using the hash as the seed if available
                    hash_value = api_game.get('hashValue')
                    if hash_value:
                        calculated_crash = self.calculate_crash_point(
                            seed=hash_value, salt=self.salt)
                        api_game['calculatedPoint'] = calculated_crash

                    complete_data = api_game
                else:
                    self.logger.warning(
                        f"Could not find complete data for game {game_data['gameId']} from API")
            except Exception as api_error:
                self.logger.warning(
                    f"Error fetching complete game data from API: {api_error}")

            # Store in database if enabled
            if self.database_enabled and self.db:
                try:
                    # Store game in database using the db module
                    with self.db.get_session() as session:
                        # Check if game already exists
                        existing_game = session.query(CrashGame).filter(
                            CrashGame.gameId == game_data['gameId']
                        ).first()

                        if not existing_game:
                            if complete_data:
                                # Use complete data from API
                                new_game = CrashGame(**complete_data)
                            else:
                                # Fallback to minimal data from observer
                                new_game = CrashGame(
                                    gameId=game_data['gameId'],
                                    crashPoint=float(crash_point)
                                )
                            session.add(new_game)
                            session.commit()
                            self.logger.debug(
                                f"Stored game {game_data['gameId']} in database")
                except Exception as db_error:
                    self.logger.error(
                        f"Error storing game in database: {db_error}")

            # Prepare data for callbacks
            if complete_data:
                # If we have complete data, use it for callbacks
                callback_data = complete_data
            else:
                # Fallback to minimal data with proper format
                callback_data = {
                    'gameId': game_data['gameId'],
                    'crashPoint': f"{crash_point}x"
                }

            # Notify callbacks
            await self.notify_game_callbacks(callback_data)
            return True

        except Exception as e:
            self.logger.error(f"Error processing game event: {e}")
            return False

    async def add_game_event(self, game_data):
        """
        Add a game event to the queue for processing

        Args:
            game_data: Dictionary with game information
        """
        if self.running and self.event_driven:
            await self.event_queue.put(game_data)
            return True
        else:
            # If not running in event-driven mode, process directly
            return await self.process_game_event(game_data)

    async def run(self, event_driven=False):
        """
        Run the monitor loop

        Args:
            event_driven: If True, will run in event-driven mode instead of polling
        """
        self.running = True
        self.event_driven = event_driven

        if event_driven:
            self.logger.info(
                "Starting BC Game Crash Monitor in event-driven mode")
            # Run event-driven loop
            try:
                while self.running:
                    try:
                        # Wait for game events from the queue
                        game_data = await self.event_queue.get()
                        await self.process_game_event(game_data)
                        self.event_queue.task_done()
                    except asyncio.CancelledError:
                        self.logger.info("Event loop cancelled")
                        break
                    except Exception as e:
                        self.logger.error(f"Error in event loop: {e}")
            finally:
                self.running = False
                self.logger.info("Event-driven monitor stopped")
        else:
            self.logger.info(
                f"Starting BC Game Crash Monitor with polling interval {self.polling_interval}s")
            # Run polling loop
            try:
                while self.running:
                    try:
                        # Poll and process new games
                        await self.poll_and_process()

                        # Wait for the next polling interval
                        await asyncio.sleep(self.polling_interval)
                    except asyncio.CancelledError:
                        self.logger.info("Polling loop cancelled")
                        break
                    except Exception as e:
                        self.logger.error(f"Error in polling loop: {e}")
                        self.logger.info(
                            f"Retrying in {self.retry_interval} seconds...")
                        await asyncio.sleep(self.retry_interval)
            finally:
                self.running = False
                self.logger.info("Polling monitor stopped")

    def stop(self):
        """Stop the monitor"""
        self.running = False

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
