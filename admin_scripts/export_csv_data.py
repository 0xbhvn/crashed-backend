#!/usr/bin/env python
"""
Script to export data from the database into two CSV files:
1. Timestamps (gameId, endTime, prepareTime, beginTime) in ISO format.
2. Other data fields (gameId, and all other non-timestamp fields).

Usage:
python export_csv_data.py
"""

import csv
import sys
import os
import argparse
from datetime import datetime
import pytz  # Import pytz if needed for timezone handling, though isoformat() might suffice

# Add parent directory to sys.path to allow importing from src
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '.')))

try:
    from src.utils import load_env
    from src import config
    from src.db.models import CrashGame
    from src.db.engine import get_database
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    from src.config import reload_config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure you are running this script from the project root directory")
    print("or that the necessary modules are installed and accessible.")
    sys.exit(1)

# Load environment variables
load_env()
reload_config()

# Define the epoch timestamp string
EPOCH_TIMESTAMP_STR = '1970-01-01T00:00:00+00:00'


def export_data_to_csv(times_output_file='crash_games_times_export.csv',
                       epoch_times_output_file='crash_games_epoch_times_export.csv'):
    """Export data from database to two CSV files (main times and epoch times)"""
    print(f"Exporting data from database ({config.DATABASE_URL})...")

    db = get_database()
    session = db.get_session()

    time_keys = ['endTime', 'prepareTime', 'beginTime']
    # Add crashPoint and hashValue to the keys we want in the CSVs
    include_keys = ['crashPoint', 'hashValue']

    times_data = []
    epoch_times_data = []  # List for games with epoch timestamps

    try:
        games = session.query(CrashGame).all()
        print(f"Found {len(games)} games to export")

        if not games:
            print("No games found in the database.")
            return

        # Prepare data for CSVs
        for game in games:
            game_dict = game.to_dict()  # Assuming this method exists and returns a dict
            game_id = game_dict.get('gameId')  # Ensure gameId is present

            time_row = {'gameId': game_id}

            for key, value in game_dict.items():
                # Handle timestamp keys
                if key in time_keys:
                    # Convert datetime to ISO format string if it's a datetime object
                    if isinstance(value, datetime):
                        time_row[key] = value.isoformat()
                    else:
                        time_row[key] = value
                # Handle other included keys (crashPoint, hashValue)
                elif key in include_keys:
                    time_row[key] = value

            # Check if any timestamp is the epoch default BEFORE appending to main times_data
            has_epoch_time = False
            for key in time_keys:
                if time_row.get(key) == EPOCH_TIMESTAMP_STR:
                    has_epoch_time = True
                    break

            # Append to respective lists
            if has_epoch_time:
                # Add the full time_row to epoch list
                epoch_times_data.append(time_row)
            else:
                # Only add to main times list if NO epoch time
                times_data.append(time_row)

        # Sort the data lists by gameId (as integer) before writing
        print("Sorting data by gameId...")
        times_data.sort(key=lambda x: int(x.get('gameId', 0)))
        epoch_times_data.sort(key=lambda x: int(x.get('gameId', 0)))

        # Define headers
        # Ensure 'gameId' is first column for times, followed by timestamps, then other included keys
        # Determine the actual existing time keys from the data to handle missing ones
        actual_time_keys = [k for k in time_keys if any(
            k in row for row in times_data + epoch_times_data)]
        # Determine the actual included keys from the data
        actual_include_keys = [k for k in include_keys if any(
            k in row for row in times_data + epoch_times_data)]

        # Combine fieldnames: gameId, timestamps, crashPoint, hashValue
        fieldnames = ['gameId'] + actual_time_keys + actual_include_keys

        # Write times CSV (excluding epoch games)
        print(
            f"Writing non-epoch timestamp data (including crashPoint, hashValue) to {times_output_file}...")
        with open(times_output_file, 'w', newline='', encoding='utf-8') as csvfile:
            # Use combined fieldnames
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(times_data)
        print(
            f"Non-epoch timestamp data successfully written to {times_output_file}")

        # Write epoch times CSV if any were found
        if epoch_times_data:
            print(
                f"Writing epoch timestamp data (including crashPoint, hashValue) to {epoch_times_output_file}...")
            with open(epoch_times_output_file, 'w', newline='', encoding='utf-8') as csvfile:
                # Use the same fieldnames as the main times CSV
                # Use combined fieldnames
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(epoch_times_data)
            print(
                f"Epoch timestamp data successfully written to {epoch_times_output_file}")
        else:
            print(
                f"No games found with epoch timestamps ('{EPOCH_TIMESTAMP_STR}'). Skipping epoch times file.")

    except Exception as e:
        print(f"An error occurred during export: {e}")
        # Potentially add rollback here if any DB operations were write-based (unlikely for export)
        raise  # Re-raise the exception for debugging
    finally:
        session.close()
        print("Database session closed.")


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Export CrashGame data to CSV files.')
    parser.add_argument('--times-output', help='Output file path for timestamp data',
                        default='crash_games_times_export.csv')
    # Add other arguments if needed, e.g., filtering options
    parser.add_argument('--epoch-times-output', help='Output file path for games with epoch timestamps',
                        default='crash_games_epoch_times_export.csv')

    args = parser.parse_args()

    export_data_to_csv(args.times_output, args.epoch_times_output)


if __name__ == '__main__':
    main()
