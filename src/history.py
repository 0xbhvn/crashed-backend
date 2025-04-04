"""
Crash Monitor - History Module

This module contains the main BCCrashMonitor class that handles
fetching and processing crash game data from the Crash API.
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
from .utils.api import CloudflareBlockError

# Import from db
from .db import get_database, CrashGame

# Define reduced polling interval when blocked
REDUCED_POLLING_INTERVAL = 60  # seconds


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
        self.last_processed_game_id: Optional[str] = None
        self.cloudflare_block_active: bool = False

        # Game callbacks
        self.game_callbacks: List[Callable[[
            Dict[str, Any]], Awaitable[None]]] = []

        # Logging - Move before database config
        self.logger = logging.getLogger("bc_crash_monitor")
        self.verbose_logging = verbose_logging

        # Database configuration
        self.database_enabled = database_enabled if database_enabled is not None else config.DATABASE_ENABLED
        self.db = None
        if self.database_enabled and db_engine:
            from src.db.engine import get_database
            from sqlalchemy import func
            self.db = get_database(db_engine)
            try:
                with self.db.get_session() as session:
                    max_id_result = session.query(
                        func.max(CrashGame.gameId)).scalar()
                    if max_id_result:
                        self.last_processed_game_id = str(max_id_result)
                        self.logger.info(
                            f"Initialized last_processed_game_id from DB: {self.last_processed_game_id}")
                    else:
                        self.logger.info(
                            "Database is empty, last_processed_game_id set to None.")
            except Exception as e:
                self.logger.error(
                    f"Error fetching max gameId from DB: {e}. Initializing last_processed_game_id to None.")
                self.last_processed_game_id = None

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
        """Calculate crash point using the Crash algorithm"""
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

            # Apply the Crash point formula
            X = 99 / (1 - X)

            # Floor and divide by 100
            result = math.floor(X) / 100

            # Return the result, with a minimum of 1.00
            return max(1.00, result)
        except Exception as e:
            # Return 1.00 (the minimum crash point) on error
            return 1.00

    async def fetch_crash_history(self):
        """Fetch crash game history from the Crash API using the utility function"""
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
        except CloudflareBlockError as e:
            self.logger.warning(
                f"Cloudflare block detected during history fetch: {e}")
            self.cloudflare_block_active = True
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

                    # Update last processed ID only after successful processing/saving
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

    async def run(self):
        """Run the monitor loop"""
        self.logger.info(
            f"Starting Crash Monitor with polling interval {self.polling_interval}s")

        while True:
            try:
                # Poll and process new games
                await self.poll_and_process()
            except asyncio.CancelledError:
                self.logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                # Determine sleep interval based on block status
                current_sleep_interval = REDUCED_POLLING_INTERVAL if self.cloudflare_block_active else self.polling_interval
                retry_msg = f"Retrying in {current_sleep_interval} seconds..."
                self.logger.error(f"Error in monitor loop: {e}")
                self.logger.info(retry_msg)
                # Use the determined interval for sleeping after an error
                await asyncio.sleep(current_sleep_interval)
            else:
                # Determine sleep interval for the next poll based on block status
                if self.cloudflare_block_active:
                    sleep_interval = REDUCED_POLLING_INTERVAL
                    self.logger.debug(
                        f"Cloudflare block active. Using reduced polling interval: {sleep_interval}s")
                else:
                    # Check if we just recovered from a block
                    if 'previously_blocked' not in locals() or previously_blocked:
                        if 'previously_blocked' in locals():  # Avoid logging on first run
                            self.logger.info(
                                f"Cloudflare block cleared. Returning to normal polling interval: {self.polling_interval}s")
                    sleep_interval = self.polling_interval

                # Store current block state for the next iteration's check
                previously_blocked = self.cloudflare_block_active

                # Wait for the next polling interval
                await asyncio.sleep(sleep_interval)

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
