#!/usr/bin/env python3
"""
Import CSV File with Missing Games to Database

This script imports CSV files containing verified missing games into the database.

Usage:
    python import_csv_to_db.py <csv_file> [--dry-run]
    
Options:
    --dry-run    Preview the import without storing in the database
"""

import os
import csv
import sys
import argparse
from typing import List, Dict, Any
from tqdm.auto import tqdm
import dotenv

# Import modules from project
from src.db.engine import Database
from src.db.models import CrashGame

# Load environment variables from .env file
dotenv.load_dotenv()

# Get DATABASE_URL from environment variables
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. Please check your .env file.")


def read_csv_file(filename: str) -> List[Dict[str, Any]]:
    """
    Read game data from a CSV file.

    Args:
        filename: Path to CSV file

    Returns:
        List of game data dictionaries
    """
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found")
        return []

    game_data = []

    try:
        print(f"Reading data from {filename}...")
        with open(filename, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)

            # Convert row to dictionary and add to list
            for row in reader:
                # Convert types to match database model
                row_data = {
                    'gameId': row['gameId'],
                    'hashValue': row['hashValue'],
                    'crashPoint': float(row['crashPoint']),
                    'calculatedPoint': float(row['calculatedPoint']),
                    'crashedFloor': int(row['crashedFloor']),
                    'endTime': row['endTime'],
                    'prepareTime': row['prepareTime'],
                    'beginTime': row['beginTime']
                }
                game_data.append(row_data)

        print(f"Successfully read {len(game_data)} games from CSV")
        return game_data

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []


def check_for_existing_games(db: Database, game_data: List[Dict[str, Any]]) -> List[str]:
    """
    Check if any games in the CSV already exist in the database.

    Args:
        db: Database connection
        game_data: List of game data dictionaries

    Returns:
        List of game IDs that already exist in the database
    """
    if not game_data:
        return []

    existing_games = []

    print("Checking for existing games in the database...")

    # Extract all game IDs
    game_ids = [game['gameId'] for game in game_data]

    with db.get_session() as session:
        # Query existing games in chunks to avoid overly large IN clause
        chunk_size = 1000
        for i in range(0, len(game_ids), chunk_size):
            chunk = game_ids[i:i+chunk_size]
            query = session.query(CrashGame.gameId).filter(
                CrashGame.gameId.in_(chunk))
            existing_in_chunk = [game.gameId for game in query.all()]
            existing_games.extend(existing_in_chunk)

    if existing_games:
        print(
            f"Found {len(existing_games)} games that already exist in the database")
    else:
        print("No existing games found in the database")

    return existing_games


def import_to_database(db: Database, game_data: List[Dict[str, Any]], dry_run: bool = False, batch_size: int = 100) -> List[str]:
    """
    Import game data to the database in batches.

    Args:
        db: Database connection
        game_data: List of game data dictionaries
        dry_run: If True, preview the import without storing in the database
        batch_size: Number of games to store in each batch

    Returns:
        List of stored game IDs
    """
    if not game_data:
        print("No game data to import")
        return []

    if dry_run:
        print(
            f"DRY RUN: Would import {len(game_data)} games into the database")
        print("First 5 games that would be imported:")
        for i, game in enumerate(game_data[:5]):
            print(
                f"  {i+1}. Game ID: {game['gameId']}, Crash Point: {game['crashPoint']}")
        return [game['gameId'] for game in game_data]

    print(
        f"Importing {len(game_data)} games into the database in batches of {batch_size}...")

    stored_ids = []
    total_batches = (len(game_data) + batch_size -
                     1) // batch_size  # Ceiling division

    # Process in batches with a progress bar
    with tqdm(total=total_batches, desc="Storing batches", unit="batch") as pbar:
        for i in range(0, len(game_data), batch_size):
            # Get current batch
            batch = game_data[i:i+batch_size]

            # Store batch in database
            batch_ids = db.bulk_add_crash_games(batch)
            stored_ids.extend(batch_ids)

            # Update progress bar
            pbar.update(1)
            pbar.set_postfix({"total_games": len(stored_ids)})

    print(f"Successfully imported {len(stored_ids)} games into the database")
    return stored_ids


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Import CSV file with missing games to database')
    parser.add_argument('csv_file', type=str, help='Path to CSV file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview the import without storing in the database')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of games to store in each batch (default: 100)')
    args = parser.parse_args()

    # Connect to database
    print(f"Connecting to database: {DATABASE_URL}")
    db = Database(DATABASE_URL)

    # Read CSV file
    game_data = read_csv_file(args.csv_file)
    if not game_data:
        print("No data to import. Exiting.")
        sys.exit(1)

    # Check for existing games
    existing_games = check_for_existing_games(db, game_data)

    # Filter out existing games
    if existing_games:
        original_count = len(game_data)
        game_data = [game for game in game_data if game['gameId']
                     not in existing_games]
        print(f"Filtered out {original_count - len(game_data)} existing games")

    # Import to database
    if game_data:
        import_to_database(db, game_data, args.dry_run, args.batch_size)
    else:
        print("No new games to import")


if __name__ == "__main__":
    main()
