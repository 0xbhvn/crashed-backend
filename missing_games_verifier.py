#!/usr/bin/env python3
"""
Missing Games Verifier for BC.Game Crash

This script:
1. Identifies ranges of missing game IDs in the database
2. Gets the hash values for games before and after the missing range
3. Uses Playwright to verify the missing games on BC.Game's verification page
4. Maps the verified games to their correct game IDs
5. Optionally stores the results in the database or exports to CSV
"""

from src.history import BCCrashMonitor
from src.db.models import CrashGame
from src.db.engine import Database
import os
import csv
import sys
import argparse
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from playwright.async_api import async_playwright
from tqdm.auto import tqdm
import dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"missing_games_{datetime.now().strftime('%Y%m%d')}.log")
    ]
)
logger = logging.getLogger("missing_games_verifier")

# Import modules from project

# Load environment variables from .env file
dotenv.load_dotenv()

# Get DATABASE_URL from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. Please check your .env file.")


async def find_missing_ranges(db: Database) -> List[Tuple[int, int, int]]:
    """
    Find ranges of missing game IDs in the database.

    Args:
        db: Database connection

    Returns:
        List of tuples (range_start, range_end, total_missing)
    """
    missing_ranges = []

    with db.get_session() as session:
        try:
            query = text("""
            WITH game_ids AS (
              -- 1. Extract distinct game_id values and convert them to integers.
              SELECT DISTINCT CAST(game_id AS INTEGER) AS game_id_int
              FROM crash_games
            ),
            min_max AS (
              -- 2. Find the minimum and maximum game_id values.
              SELECT MIN(game_id_int) AS min_game_id, MAX(game_id_int) AS max_game_id
              FROM game_ids
            ),
            all_game_ids AS (
              -- 3. Generate a series of integers from the minimum to the maximum game_id.
              SELECT generate_series(min_game_id, max_game_id) AS game_id_int
              FROM min_max
            ),
            missing AS (
              -- 4. Identify missing game_ids by left joining the full series with actual game_ids.
              SELECT a.game_id_int AS missing_game_id
              FROM all_game_ids a
              LEFT JOIN game_ids g ON a.game_id_int = g.game_id_int
              WHERE g.game_id_int IS NULL
            ),
            grouped AS (
              -- 5. Group contiguous missing game_ids.
              -- The difference (missing_game_id - row_number) remains constant for contiguous sequences.
              SELECT 
                missing_game_id,
                missing_game_id - ROW_NUMBER() OVER (ORDER BY missing_game_id) AS grp
              FROM missing
            )
            -- 6. For each contiguous group, return the minimum and maximum missing game_id values
            -- along with the total count of missing game_ids in that range.
            SELECT 
              MIN(missing_game_id) AS range_start,
              MAX(missing_game_id) AS range_end,
              COUNT(*) AS total_missing_games
            FROM grouped
            GROUP BY grp
            ORDER BY range_start DESC;
            """)

            result = session.execute(query)
            for row in result:
                missing_ranges.append(
                    (row.range_start, row.range_end, row.total_missing_games))

            logger.info(f"Found {len(missing_ranges)} missing game ranges")
            for i, (start, end, count) in enumerate(missing_ranges):
                logger.info(
                    f"Range {i+1}: Games {start} to {end} ({count} games)")

        except SQLAlchemyError as e:
            logger.error(f"Database error finding missing ranges: {e}")

    return missing_ranges


async def get_adjacent_hashes(db: Database, range_start: int, range_end: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Get hash values for the games immediately before and after the missing range.

    Args:
        db: Database connection
        range_start: Start of the missing range
        range_end: End of the missing range

    Returns:
        Tuple (before_hash, after_hash)
    """
    before_hash = None
    after_hash = None

    with db.get_session() as session:
        # Get the game before the range
        before_game = session.query(CrashGame).filter(
            CrashGame.gameId == str(range_start - 1)
        ).first()

        if before_game:
            before_hash = before_game.hashValue
            logger.info(
                f"Found hash for game before range: Game #{before_game.gameId} with hash {before_hash}")
        else:
            logger.warning(
                f"Could not find game before range (ID: {range_start - 1})")

        # Get the game after the range
        after_game = session.query(CrashGame).filter(
            CrashGame.gameId == str(range_end + 1)
        ).first()

        if after_game:
            after_hash = after_game.hashValue
            logger.info(
                f"Found hash for game after range: Game #{after_game.gameId} with hash {after_hash}")
        else:
            logger.warning(
                f"Could not find game after range (ID: {range_end + 1})")

    return (before_hash, after_hash)


async def verify_games_with_playwright(hash_value: str, num_games: int) -> List[Tuple[str, float]]:
    """
    Use Playwright to verify games on BC.Game verification page.

    Args:
        hash_value: Hash value to start verification from
        num_games: Number of games to verify

    Returns:
        List of tuples (hash, crash_point)
    """
    verified_games = []
    logger.info(f"Verifying {num_games} games using hash {hash_value[:10]}...")

    # Show progress bar
    with tqdm(total=num_games, desc="Verifying games") as pbar:
        try:
            async with async_playwright() as p:
                # Launch browser with viewport size large enough to see the table
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 800})

                # Navigate to verification page
                await page.goto("https://bcgame-project.github.io/verify/crash.html")

                # Increase timeout for page operations
                page.set_default_timeout(600000)  # 10 minutes

                # Fill in the hash value and number of games
                await page.fill('//*[@id="game_hash_input"]', hash_value)
                await page.fill('//*[@id="game_amount_input"]', str(num_games))

                # Click verify button
                await page.click('//*[@id="game_verify_submit"]')

                # Wait for the verification to start
                await page.wait_for_selector('//*[@id="game_verify_table"]/tr')

                # Wait for all games to be verified
                max_attempts = 60
                for attempt in range(max_attempts):
                    await asyncio.sleep(10)  # Check every 10 seconds

                    # Count the number of rows in the table
                    rows = await page.query_selector_all('//*[@id="game_verify_table"]/tr')
                    num_rows = len(rows)

                    # Update progress bar
                    pbar.update(num_rows - pbar.n)

                    logger.info(
                        f"Verification progress: {num_rows}/{num_games} games")

                    # If we have all the rows, break out of the loop
                    if num_rows >= num_games:
                        logger.info(
                            f"All {num_games} games have been verified")
                        break

                    # Show remaining time estimation
                    remaining_attempts = max_attempts - attempt - 1
                    logger.info(
                        f"Waiting for more games... {remaining_attempts * 10} seconds left")

                # Take a screenshot for debugging
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"verification_{timestamp}.png"
                await page.screenshot(path=screenshot_path)
                logger.info(
                    f"Saved verification screenshot to {screenshot_path}")

                # Get all rows from the table
                rows = await page.query_selector_all('//*[@id="game_verify_table"]/tr')
                num_verified = len(rows)

                if num_verified < num_games:
                    logger.warning(
                        f"Could only verify {num_verified} of {num_games} games")

                # Extract data from each row
                for row in rows:
                    hash_cell = await row.query_selector('td:nth-child(1)')
                    bust_cell = await row.query_selector('td:nth-child(2)')

                    if hash_cell and bust_cell:
                        hash_text = await hash_cell.inner_text()
                        bust_text = await bust_cell.inner_text()
                        verified_games.append((hash_text, float(bust_text)))

                await browser.close()

        except Exception as e:
            # Take a screenshot if verification fails
            logger.error(f"Error verifying games: {e}")
            try:
                error_screenshot = f"verification_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=error_screenshot)
                logger.info(f"Saved error screenshot to {error_screenshot}")
            except:
                logger.error("Could not save error screenshot")
            finally:
                try:
                    await browser.close()
                except:
                    pass

    logger.info(f"Successfully verified {len(verified_games)} games")
    return verified_games


def map_verified_games_to_ids(verified_games: List[Tuple[str, float]], range_start: int, range_end: int) -> List[Dict[str, Any]]:
    """
    Map verified games to their correct game IDs.

    Args:
        verified_games: List of verified games as (hash, crash_point) tuples
        range_start: Start of the missing range
        range_end: End of the missing range

    Returns:
        List of game data dictionaries
    """
    if not verified_games:
        logger.warning("No verified games to map to IDs")
        return []

    # Skip the first game, which corresponds to the game after the missing range
    if len(verified_games) <= 1:
        logger.warning("Not enough verified games to map (need at least 2)")
        return []

    # The number of games we expect to map is the number of missing games
    expected_count = range_end - range_start + 1

    # We must skip the first game in the list (the game after the range)
    verified_games = verified_games[1:]  # Skip the first game

    if len(verified_games) < expected_count:
        logger.warning(
            f"Only {len(verified_games)} verified games after removing the first game, expected {expected_count}")
        logger.warning("Not enough verified games to fill the entire range")

    # Show progress with tqdm
    game_data = []
    with tqdm(total=min(len(verified_games), expected_count), desc="Mapping games to IDs") as pbar:
        # Map games to IDs - we map from the end (latest) to start (earliest)
        current_game_id = range_end

        # Map each verified game to its game ID
        for hash_value, crash_point in verified_games:
            if current_game_id < range_start:
                # We've mapped all the missing games
                break

            # Calculate the crash point using our own algorithm to verify
            calculated_point = BCCrashMonitor.calculate_crash_point(
                seed=hash_value)

            # Create game data dictionary
            game = {
                'gameId': str(current_game_id),
                'hashValue': hash_value,
                'crashPoint': crash_point,
                'calculatedPoint': calculated_point,
                'crashedFloor': int(crash_point),
                'endTime': datetime(1970, 1, 1).isoformat(),
                'prepareTime': datetime(1970, 1, 1).isoformat(),
                'beginTime': datetime(1970, 1, 1).isoformat()
            }

            game_data.append(game)
            current_game_id -= 1
            pbar.update(1)

    logger.info(f"Mapped {len(game_data)} games to IDs")
    return game_data


async def save_to_csv(game_data: List[Dict[str, Any]], range_start: int, range_end: int) -> str:
    """
    Save game data to a CSV file.

    Args:
        game_data: List of game data dictionaries
        range_start: Start of the range
        range_end: End of the range

    Returns:
        Path to the saved CSV file
    """
    if not game_data:
        logger.warning("No game data to save to CSV")
        return ""

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"missing_games_{range_start}_{range_end}_{timestamp}.csv"

    fieldnames = game_data[0].keys()

    # Show progress with tqdm
    with tqdm(total=len(game_data), desc="Saving to CSV") as pbar:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for game in game_data:
                writer.writerow(game)
                pbar.update(1)

    logger.info(f"Saved {len(game_data)} games to {filename}")
    return filename


async def store_games_in_db(db: Database, game_data: List[Dict[str, Any]]) -> List[str]:
    """
    Store the verified games in the database.

    Args:
        db: Database connection
        game_data: List of game data dictionaries

    Returns:
        List of stored game IDs
    """
    if not game_data:
        logger.warning("No game data to store in database")
        return []

    logger.info(f"Storing {len(game_data)} games in the database...")

    # Show timer with tqdm
    with tqdm(total=0, desc="Storing in database", bar_format='{desc}: {elapsed}') as pbar:
        # Store games in database
        stored_ids = db.bulk_add_crash_games(game_data)

    if stored_ids:
        logger.info(
            f"Successfully stored {len(stored_ids)} games in the database")
    else:
        logger.warning("Failed to store games in the database")

    return stored_ids


async def process_missing_range(db: Database, range_start: int, range_end: int, missing_count: int,
                                batch_size: int = 100, store: bool = False, csv: bool = False) -> List[Dict[str, Any]]:
    """
    Process a range of missing games by verifying them and preparing data.

    Args:
        db: Database connection
        range_start: Start of the missing range
        range_end: End of the missing range
        missing_count: Number of missing games in the range
        batch_size: Maximum number of games to verify in a single batch
        store: Whether to store the results in the database
        csv: Whether to export the results to CSV

    Returns:
        List of game data dictionaries
    """
    logger.info(
        f"Processing range {range_start} to {range_end} ({missing_count} games)")

    # Get hash values for games adjacent to the missing range
    before_hash, after_hash = await get_adjacent_hashes(db, range_start, range_end)

    # We need the hash of the game after the range
    if not after_hash:
        logger.error(
            f"Could not find hash for game after range ({range_end + 1})")
        logger.error(
            "Cannot proceed without the hash of the game after the range")
        return []

    logger.info(f"Using hash {after_hash[:10]}... to verify games")

    # For hash verification, we need to verify missing_count + 1 games
    # The +1 is for the game after the range, which we use to verify
    num_games = missing_count + 1

    # Verify the games
    verified_games = await verify_games_with_playwright(after_hash, num_games)

    # Check if we got enough games
    if len(verified_games) < num_games:
        logger.warning(
            f"Could only verify {len(verified_games)} of {num_games} games")
        logger.warning(
            "This may result in an incomplete recovery of the missing range")

    # Map verified games to their correct game IDs
    game_data = map_verified_games_to_ids(
        verified_games, range_start, range_end)

    # Check the first game's hash
    if game_data and before_hash:
        # Last in list = first game in range
        first_hash = game_data[-1]['hashValue']
        if first_hash != before_hash:
            logger.warning(f"Hash mismatch for first game in range:")
            logger.warning(f"  Expected: {before_hash}")
            logger.warning(f"  Actual:   {first_hash}")
            logger.warning(
                "This suggests there might be an issue with the verification")

            # Try to find the game with matching hash
            for i, game in enumerate(game_data):
                if game['hashValue'] == before_hash:
                    logger.info(f"Found matching hash at position {i+1}")
                    break

    # Save to CSV if requested
    if csv and game_data:
        await save_to_csv(game_data, range_start, range_end)

    # Store in database if requested
    if store and game_data:
        await store_games_in_db(db, game_data)

    return game_data


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Find and verify missing crash games')
    parser.add_argument('--store', action='store_true',
                        help='Store verified games in the database')
    parser.add_argument('--csv', action='store_true',
                        help='Export verified games to CSV')
    parser.add_argument('--limit', type=int, default=1,
                        help='Maximum number of missing ranges to process')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Maximum number of games to verify in a single batch')

    args = parser.parse_args()

    # Log the start of the script
    logger.info("Starting Missing Games Verifier")
    logger.info(
        f"Options: store={args.store}, csv={args.csv}, limit={args.limit}, batch_size={args.batch_size}")

    # Connect to database
    logger.info(f"Connecting to database: {DATABASE_URL}")
    db = Database(DATABASE_URL)

    # Find missing game ranges
    missing_ranges = await find_missing_ranges(db)

    if not missing_ranges:
        logger.info("No missing game ranges found. Exiting.")
        return

    # Process ranges up to the limit
    all_game_data = []
    num_ranges_to_process = min(args.limit, len(missing_ranges))

    logger.info(
        f"Processing {num_ranges_to_process} of {len(missing_ranges)} missing ranges")

    # Process each range with progress tracking
    with tqdm(total=num_ranges_to_process, desc="Processing ranges") as pbar:
        for i, (start, end, count) in enumerate(missing_ranges[:args.limit]):
            logger.info(
                f"Range {i+1}/{num_ranges_to_process}: Games {start} to {end} ({count} games)")

            game_data = await process_missing_range(
                db, start, end, count,
                batch_size=args.batch_size,
                store=args.store,
                csv=args.csv
            )

            if game_data:
                all_game_data.extend(game_data)
                logger.info(f"Successfully processed range {start} to {end}")
            else:
                logger.warning(f"Failed to process range {start} to {end}")

            pbar.update(1)

    # Log completion
    logger.info(
        f"Processed {len(all_game_data)} missing games from {num_ranges_to_process} ranges")
    logger.info("Missing Games Verifier completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
