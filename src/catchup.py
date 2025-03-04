"""
BC Game Catchup Script.

This module provides functionality to catch up on missing games by:
1. Finding the latest game ID from the API
2. Determining how many games we're missing (out of 2000 total)
3. Retrieving missing games in batches (100 per page)
4. Processing and storing these games in the database

This will run when the application starts or can be executed manually.
"""

from .sqlalchemy_db import Database
from .models import CrashGame
from . import config
from . import database
import logging
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import sys
import argparse
import os
from datetime import datetime, timezone
import pytz
import statistics
from sqlalchemy import func

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)  # Respect the configured log level

# Import relative modules


async def get_latest_game_id() -> Optional[int]:
    """
    Get the latest game ID from the API.

    Returns:
        int: The latest game ID or None if the request fails
    """
    url = f"{config.API_BASE_URL}/api/game/bet/multi/history"
    try:
        logger.debug(f"Fetching latest game ID from {url}")

        # Request data with pageSize=20 (minimum required by API)
        data = {
            "gameUrl": "crash",
            "page": 1,
            "pageSize": 20
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=config.DEFAULT_HEADERS) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to get latest game ID: HTTP {response.status}")
                    logger.debug(f"Response: {await response.text()}")
                    return None

                result = await response.json()

                # Check for 'list' field in the response (new API format)
                if result.get('data', {}).get('list'):
                    games = result['data']['list']
                    if games:
                        latest_game = games[0]
                        latest_id = int(latest_game['gameId'])
                        logger.debug(f"Latest game ID: {latest_id}")
                        return latest_id

                # Check for 'data' field in the response (old API format)
                elif result.get('data', {}).get('data'):
                    games = result['data']['data']
                    if games:
                        latest_game = games[0]
                        latest_id = int(latest_game['gameId'])
                        logger.debug(f"Latest game ID: {latest_id}")
                        return latest_id

                logger.error(
                    f"Failed to get latest game ID: No data in response: {result}")
                return None
    except Exception as e:
        logger.error(f"Error getting latest game ID: {e}")
        return None


async def fetch_game_batch(page: int, page_size: int = 20) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch a batch of games from the API.

    Args:
        page: Page number to fetch (1-indexed)
        page_size: Number of games per page (minimum 20, maximum 100)

    Returns:
        List of game data or None if the request fails
    """
    url = f"{config.API_BASE_URL}/api/game/bet/multi/history"

    # Ensure page_size is within valid range (minimum 20, maximum 100)
    page_size = max(20, min(page_size, 100))

    try:
        logger.debug(f"Fetching game batch - page {page}, size {page_size}")

        data = {
            "gameUrl": "crash",
            "page": page,
            "pageSize": page_size
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=config.DEFAULT_HEADERS) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to fetch game batch: HTTP {response.status}")
                    logger.debug(f"Response: {await response.text()}")
                    return None

                result = await response.json()

                # Check for 'list' field in the response (new API format)
                if result.get('data', {}).get('list'):
                    games = result['data']['list']
                    if not games:
                        logger.warning(f"No games found on page {page}")
                        return []

                    logger.debug(
                        f"Fetched {len(games)} games from page {page}")
                    return games

                # Check for 'data' field in the response (old API format)
                elif result.get('data', {}).get('data'):
                    games = result['data']['data']
                    if not games:
                        logger.warning(f"No games found on page {page}")
                        return []

                    logger.debug(
                        f"Fetched {len(games)} games from page {page}")
                    return games

                logger.warning(f"No games found in response: {result}")
                return []
    except Exception as e:
        logger.error(f"Error fetching game batch: {e}")
        return None


def process_game_data(game: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process raw game data into a format ready for database storage.

    Args:
        game: Raw game data from API

    Returns:
        Processed game data
    """
    # Extract game details from the game_detail JSON string
    game_detail = {}
    try:
        if isinstance(game.get('gameDetail'), str):
            game_detail = json.loads(game['gameDetail'])
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse game detail: {e}")

    # Convert timestamps to datetime objects
    end_time = datetime.fromtimestamp(
        int(game_detail.get('endTime', 0)) / 1000,
        tz=timezone.utc
    ) if game_detail.get('endTime') else None

    begin_time = datetime.fromtimestamp(
        int(game_detail.get('beginTime', 0)) / 1000,
        tz=timezone.utc
    ) if game_detail.get('beginTime') else None

    # Calculate crash point (convert to float)
    try:
        crash_point = float(game_detail.get('rate', 0))
    except (ValueError, TypeError):
        crash_point = 0.0

    # Get timing Unix timestamps
    end_time_unix = game_detail.get('endTime', 0)
    begin_time_unix = game_detail.get('beginTime', 0)
    prepare_time_unix = game_detail.get('prepareTime', 0)

    # Prepare time as datetime
    prepare_time = datetime.fromtimestamp(
        int(prepare_time_unix) / 1000,
        tz=timezone.utc
    ) if prepare_time_unix else None

    # Get timezone from config
    app_timezone = pytz.timezone(config.TIMEZONE)

    def convert_timestamp(ts):
        """Convert timestamp in milliseconds to datetime with timezone."""
        if not ts:
            return None
        return datetime.fromtimestamp(ts / 1000, tz=app_timezone)

    # Process the raw game data
    result = {
        'gameId': str(game.get('gameId', 0)),
        'hashValue': game_detail.get('hash', ''),
        'crashPoint': crash_point,
        'calculatedPoint': crash_point,
        'crashedFloor': int(crash_point),  # Floor value of crash point
        # Convert Unix timestamps to datetime objects with timezone
        'endTime': convert_timestamp(end_time_unix),
        'prepareTime': convert_timestamp(prepare_time_unix),
        'beginTime': convert_timestamp(begin_time_unix),
        'createdAt': datetime.now(timezone.utc)
    }

    return result


async def run_catchup(database_enabled: bool = True, session_factory=None,
                      max_pages: int = 20, batch_size: int = 20) -> int:
    """
    Run the catchup process to retrieve historical games.

    Args:
        database_enabled: Whether to store games in the database
        session_factory: Database session factory (required if database_enabled is True)
        max_pages: Maximum number of pages to process (default: 20)
        batch_size: Number of games per page (default: 20, min: 20, max: 100)

    Returns:
        Number of games processed
    """
    logger.info(
        f"Starting catchup process - database storage {'enabled' if database_enabled else 'disabled'}")

    if database_enabled and not session_factory:
        logger.error(
            "Database session factory is required when database is enabled")
        return 0

    # Get latest game ID
    latest_id = await get_latest_game_id()
    if not latest_id:
        logger.error("Failed to get latest game ID, aborting catchup")
        return 0

    logger.info(f"Latest game ID from API: {latest_id}")
    logger.debug(
        f"Will process up to {max_pages} pages of history, {batch_size} games per page")

    # Track processed games
    games_processed = 0

    # Process pages
    for page in range(1, max_pages + 1):
        # Fetch a batch of games
        games = await fetch_game_batch(page, batch_size)
        if not games:
            logger.warning(
                f"No games found on page {page} or error occurred, stopping catchup")
            break

        logger.debug(f"Fetched {len(games)} games from page {page}")

        if database_enabled:
            # Process and store games
            processed_games = []
            game_ids = set()  # Track game IDs for duplicate detection
            dates = set()  # Track dates for stats updates

            for game in games:
                # Process the game data
                processed_game = process_game_data(game)
                game_id = processed_game['gameId']

                # Skip if we've already seen this game ID in this batch
                if game_id in game_ids:
                    logger.debug(f"Skipping duplicate game ID: {game_id}")
                    continue

                game_ids.add(game_id)
                processed_games.append(processed_game)

                # Track date for stats updates
                if processed_game['beginTime']:
                    dates.add(processed_game['beginTime'].date())

            if processed_games:
                # Store games in database
                with session_factory() as session:
                    # Get existing game IDs to avoid duplicates
                    existing_game_ids = set()
                    for game_id, in session.query(CrashGame.gameId).filter(
                        CrashGame.gameId.in_([g['gameId']
                                             for g in processed_games])
                    ).all():
                        existing_game_ids.add(game_id)

                    # Filter out games that already exist
                    new_games = [
                        g for g in processed_games if g['gameId'] not in existing_game_ids]

                    if new_games:
                        logger.debug(
                            f"Storing {len(new_games)} new crash games in database")
                        # Create CrashGame instances for each game data
                        new_game_objects = [
                            CrashGame(**game_data) for game_data in new_games]

                        # Add all games to session
                        session.add_all(new_game_objects)

                        # Commit the transaction
                        session.commit()

                        games_processed += len(new_games)
                    else:
                        logger.debug(
                            "No new games to store (all already exist in database)")

                # Update crash stats for each date
                if dates:
                    for date in dates:
                        logger.debug(f"Updating crash stats for date: {date}")
                        # Call the update_daily_stats function for the specific date
                        try:
                            # Create a datetime object with the date components
                            date_obj = datetime(
                                date.year, date.month, date.day)
                            # Fetch games for this date
                            session = session_factory()
                            games = session.query(CrashGame).filter(
                                CrashGame.beginTime.isnot(None),
                                func.date(CrashGame.beginTime) == date
                            ).all()

                            if not games:
                                logger.debug(
                                    f"No games found for date {date}, skipping stats update")
                                continue

                            # Calculate stats
                            crash_points = [game.crashPoint for game in games]
                            games_count = len(crash_points)
                            average_crash = sum(crash_points) / games_count
                            median_crash = statistics.median(crash_points)
                            max_crash = max(crash_points)
                            min_crash = min(crash_points)
                            std_dev = statistics.stdev(
                                crash_points) if games_count > 1 else 0

                            # Create stats data dictionary
                            stats_data = {
                                "gamesCount": games_count,
                                "averageCrash": average_crash,
                                "medianCrash": median_crash,
                                "maxCrash": max_crash,
                                "minCrash": min_crash,
                                "standardDeviation": std_dev
                            }

                            # Update or create stats
                            db = database.get_database()
                            db.update_or_create_crash_stats(
                                date_obj, stats_data)

                            logger.debug(
                                f"Updated stats for {date}: {games_count} games, avg={average_crash:.2f}x")
                        except Exception as e:
                            logger.error(
                                f"Error updating stats for date {date}: {str(e)}")
                        finally:
                            session.close()
        else:
            # If database is disabled, just count the games
            games_processed += len(games)

    logger.info(
        f"Catchup process complete - processed {games_processed} games")
    return games_processed


async def main():
    """Command-line entry point for manual catchup."""
    # Configure logging based on LOG_LEVEL environment variable
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='BC Game Catchup Utility')
    parser.add_argument('--pages', type=int, default=20,
                        help='Maximum number of pages to process (default: 20)')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='Number of games per page (min: 20, max: 100, default: 20)')
    parser.add_argument('--no-database', action='store_true',
                        help='Disable database storage')
    args = parser.parse_args()

    # Run catchup process
    database_enabled = not args.no_database

    if database_enabled:
        # Connect to database
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.warning(
                "DATABASE_URL not set. Using default connection string.")
            database_url = "postgresql://postgres:postgres@localhost:5432/bc_crash_db"

        # Create database instance
        db = Database(database_url)

        try:
            # Initialize database if needed
            db.create_tables()

            # Run catchup
            await run_catchup(
                database_enabled=True,
                session_factory=db.get_session,
                max_pages=args.pages,
                batch_size=args.batch_size
            )
        finally:
            # No need to explicitly close with SQLAlchemy - engine disposal happens automatically
            pass
    else:
        logger.info("Running catchup without database storage")
        await run_catchup(
            database_enabled=False,
            max_pages=args.pages,
            batch_size=args.batch_size
        )


if __name__ == "__main__":
    asyncio.run(main())
