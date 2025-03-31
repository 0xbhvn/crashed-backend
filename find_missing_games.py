"""
Script to identify missing game IDs in the crash_games database and verify them 
using the bcgame verification page.

This script:
1. Connects to the database and identifies ranges of missing game IDs
2. Gets the hash values for games before and after the missing range
3. Uses Playwright to verify the missing games on bcgame's verification page
4. Creates a CSV file with the missing game data
"""

import os
import csv
import argparse
import asyncio
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from playwright.async_api import async_playwright
import dotenv
from src.db.engine import Database
from src.db.models import CrashGame

# Load environment variables from .env file
dotenv.load_dotenv()

# Get DATABASE_URL from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. Please check your .env file.")


async def find_missing_games(db: Database):
    """
    Find ranges of missing game IDs in the database.

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
              FROM public.crash_games
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

        except SQLAlchemyError as e:
            print(f"Database error: {e}")

    return missing_ranges


async def get_adjacent_hashes(db: Database, range_start: int, range_end: int):
    """
    Get hash values for the games immediately before and after the missing range.

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

        # Get the game after the range
        after_game = session.query(CrashGame).filter(
            CrashGame.gameId == str(range_end + 1)
        ).first()

        if after_game:
            after_hash = after_game.hashValue

    return (before_hash, after_hash)


async def verify_games(hash_value, num_games):
    """
    Use Playwright to verify games on bcgame verification page.

    Returns:
        List of tuples (hash, bust_value)
    """
    verified_games = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Navigate to verification page
        await page.goto("https://bcgame-project.github.io/verify/crash.html")

        # Fill in the hash value and number of games
        await page.fill('//*[@id="game_hash_input"]', hash_value)
        await page.fill('//*[@id="game_amount_input"]', str(num_games))

        # Click verify button
        await page.click('//*[@id="game_verify_submit"]')

        # Wait for the table to be populated
        await page.wait_for_selector('//*[@id="game_verify_table"]/tr')

        # Get all rows from the table
        rows = await page.query_selector_all('//*[@id="game_verify_table"]/tr')

        for row in rows:
            hash_cell = await row.query_selector('td:nth-child(1)')
            bust_cell = await row.query_selector('td:nth-child(2)')

            if hash_cell and bust_cell:
                hash_text = await hash_cell.inner_text()
                bust_text = await bust_cell.inner_text()
                verified_games.append((hash_text, float(bust_text)))

        await browser.close()

    return verified_games


async def process_missing_range(db: Database, range_start: int, range_end: int, missing_count: int):
    """
    Process a range of missing games by verifying them and preparing data.

    Returns:
        List of dictionaries with game data
    """
    # Get hash values for games adjacent to the missing range
    before_hash, after_hash = await get_adjacent_hashes(db, range_start, range_end)

    if not after_hash:
        print(
            f"Could not find hash value for game after range ({range_end + 1})")
        return []

    # Number of games to verify (missing games + 2 for verification)
    num_games = missing_count + 2

    # Verify games using the hash of the game after the range
    verified_games = await verify_games(after_hash, num_games)

    if len(verified_games) < num_games:
        print(
            f"Could not verify all games. Only got {len(verified_games)} of {num_games}")
        return []

    # Set earliest valid timestamp (January 1, 1970) for time fields
    earliest_timestamp = datetime(1970, 1, 1).isoformat()

    # Prepare game data (skipping the last game which should match game_id = range_end + 1)
    game_data = []

    # Start with the last hash in the verified list and go backwards
    current_game_id = range_end

    # Skip the last game (which is the one we already have)
    for i in range(1, len(verified_games)):
        hash_value, bust_value = verified_games[-(i+1)]

        # Create game data dictionary
        game = {
            'gameId': str(current_game_id),
            'hashValue': hash_value,
            'crashPoint': bust_value,
            'calculatedPoint': bust_value,
            'crashedFloor': int(bust_value),
            'endTime': earliest_timestamp,
            'prepareTime': earliest_timestamp,
            'beginTime': earliest_timestamp
        }

        game_data.append(game)
        current_game_id -= 1

    return game_data


async def save_to_csv(game_data, filename):
    """Save game data to a CSV file."""
    if not game_data:
        print("No game data to save.")
        return

    fieldnames = game_data[0].keys()

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(game_data)

    print(f"Saved {len(game_data)} games to {filename}")


async def store_games_in_db(db: Database, game_data):
    """Store the verified games in the database."""
    stored_ids = db.bulk_add_crash_games(game_data)
    print(f"Stored {len(stored_ids)} games in the database")
    return stored_ids


async def main():
    parser = argparse.ArgumentParser(
        description='Find and verify missing crash games')
    parser.add_argument('--store', action='store_true',
                        help='Store verified games in the database')
    parser.add_argument('--csv', action='store_true',
                        help='Export verified games to CSV')
    parser.add_argument('--limit', type=int, default=1,
                        help='Maximum number of missing ranges to process')
    args = parser.parse_args()

    # Connect to database
    db = Database(DATABASE_URL)

    # Find missing game ranges
    missing_ranges = await find_missing_games(db)

    if not missing_ranges:
        print("No missing game ranges found.")
        return

    print(f"Found {len(missing_ranges)} missing game ranges:")
    for start, end, count in missing_ranges:
        print(f"  Games {start} to {end} ({count} games)")

    # Process ranges up to the limit
    all_game_data = []
    for i, (start, end, count) in enumerate(missing_ranges[:args.limit]):
        print(
            f"\nProcessing range {i+1}/{min(args.limit, len(missing_ranges))}: Games {start} to {end} ({count} games)")

        game_data = await process_missing_range(db, start, end, count)
        if game_data:
            all_game_data.extend(game_data)

            if args.store:
                await store_games_in_db(db, game_data)

            # Save to CSV if requested or if not storing in database
            if args.csv or not args.store:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"missing_games_{start}_{end}_{timestamp}.csv"
                await save_to_csv(game_data, filename)

    print(f"\nProcessed {len(all_game_data)} missing games.")

if __name__ == "__main__":
    asyncio.run(main())
