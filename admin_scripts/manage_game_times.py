#!/usr/bin/env python3
"""
Script to manage game times for Crash Games.
This script provides functionality to:
1. Update game times (subtract hours/minutes)
2. Revert game times (add hours/minutes)
3. Verify current game times

Usage examples:
  # Update times for a specific game (subtract 5h30m)
  python manage_game_times.py update --game-id 7916261
  
  # Update times for multiple games
  python manage_game_times.py update --game-ids 7916261,7916260,7916259
  
  # Update times for a range of games
  python manage_game_times.py update --min-id 7916250 --max-id 7916261
  
  # Revert times for a specific game (add 5h30m)
  python manage_game_times.py revert --game-id 7912114
  
  # Verify times for specific games
  python manage_game_times.py verify --game-ids 7916261,7916260,7916259
  
  # Customize time adjustment (for update or revert)
  python manage_game_times.py update --game-id 7916261 --hours -2 --minutes -15
  python manage_game_times.py revert --game-id 7916261 --hours 2 --minutes 15
"""

from src.db.models import CrashGame
from src.db.engine import get_database
import asyncio
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default time adjustments
DEFAULT_UPDATE_HOURS = -5
DEFAULT_UPDATE_MINUTES = -30
DEFAULT_REVERT_HOURS = 5
DEFAULT_REVERT_MINUTES = 30

# Default batch size for processing
DEFAULT_BATCH_SIZE = 50


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Manage game times for Crash Games')

    subparsers = parser.add_subparsers(dest='action', help='Action to perform')
    subparsers.required = True

    # Common arguments for game selection
    game_selection_args = argparse.ArgumentParser(add_help=False)
    group = game_selection_args.add_mutually_exclusive_group(required=True)
    group.add_argument('--game-id', type=str,
                       help='Specific game ID to process')
    group.add_argument('--game-ids', type=str,
                       help='Comma-separated list of game IDs')
    group.add_argument('--min-id', type=str,
                       help='Minimum game ID in range (inclusive)')

    # Common arguments for time adjustment
    time_adjustment_args = argparse.ArgumentParser(add_help=False)
    time_adjustment_args.add_argument(
        '--hours', type=int, help='Hours to adjust')
    time_adjustment_args.add_argument(
        '--minutes', type=int, help='Minutes to adjust')
    time_adjustment_args.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                                      help=f'Batch size for processing (default: {DEFAULT_BATCH_SIZE})')

    # Update command
    update_parser = subparsers.add_parser('update', parents=[game_selection_args, time_adjustment_args],
                                          help='Update game times (subtract hours/minutes)')
    update_parser.add_argument(
        '--max-id', type=str, help='Maximum game ID in range (inclusive)')

    # Revert command
    revert_parser = subparsers.add_parser('revert', parents=[game_selection_args, time_adjustment_args],
                                          help='Revert game times (add hours/minutes)')
    revert_parser.add_argument(
        '--max-id', type=str, help='Maximum game ID in range (inclusive)')

    # Verify command
    verify_parser = subparsers.add_parser('verify', parents=[game_selection_args],
                                          help='Verify current game times')

    return parser.parse_args()


def get_game_ids(args) -> List[str]:
    """Get the list of game IDs to process based on command line arguments."""
    db = get_database()
    try:
        if args.game_id:
            return [args.game_id]
        elif args.game_ids:
            return args.game_ids.split(',')
        elif args.min_id:
            session = db.get_session()
            query = session.query(CrashGame.gameId).filter(
                CrashGame.gameId >= args.min_id)

            if hasattr(args, 'max_id') and args.max_id:
                query = query.filter(CrashGame.gameId <= args.max_id)

            game_ids = [game_id[0] for game_id in query.all()]
            session.close()
            return game_ids
        else:
            return []
    finally:
        db.close()


def get_time_adjustment(args, action: str) -> timedelta:
    """Get the time adjustment based on the action and command line arguments."""
    if action == 'update':
        hours = args.hours if args.hours is not None else DEFAULT_UPDATE_HOURS
        minutes = args.minutes if args.minutes is not None else DEFAULT_UPDATE_MINUTES
    else:  # action == 'revert'
        hours = args.hours if args.hours is not None else DEFAULT_REVERT_HOURS
        minutes = args.minutes if args.minutes is not None else DEFAULT_REVERT_MINUTES

    return timedelta(hours=hours, minutes=minutes)


async def update_game_time(game_id: str, time_adjustment: timedelta) -> bool:
    """Update the time for a specific game."""
    db = get_database()

    try:
        # Get the game from the database
        game = db.get_crash_game_by_id(game_id)

        if not game:
            logger.warning(f"Game with ID {game_id} not found")
            return False

        # Store original times for logging
        original_begin = game.beginTime
        original_end = game.endTime
        original_prepare = game.prepareTime

        # Calculate new times
        new_begin_time = game.beginTime + time_adjustment if game.beginTime else None
        new_end_time = game.endTime + time_adjustment if game.endTime else None
        new_prepare_time = game.prepareTime + \
            time_adjustment if game.prepareTime else None

        # Create updated data dictionary
        updated_data = {}

        # Update beginTime if it exists
        if game.beginTime:
            updated_data['beginTime'] = new_begin_time

        # Update endTime if it exists
        if game.endTime:
            updated_data['endTime'] = new_end_time

        # Update prepareTime if it exists
        if game.prepareTime:
            updated_data['prepareTime'] = new_prepare_time

        # Update the game in the database
        updated_game = db.update_crash_game(game_id, updated_data)

        if updated_game:
            logger.info(f"Successfully updated game {game_id}")
            logger.info(f"  Begin Time: {original_begin} -> {new_begin_time}")
            logger.info(f"  End Time: {original_end} -> {new_end_time}")
            logger.info(
                f"  Prepare Time: {original_prepare} -> {new_prepare_time}")
            return True
        else:
            logger.error(f"Failed to update game {game_id}")
            return False

    finally:
        db.close()


async def process_games(game_ids: List[str], time_adjustment: timedelta, batch_size: int) -> Dict[str, int]:
    """Process multiple games with the given time adjustment."""
    total_games = len(game_ids)
    logger.info(f"Found {total_games} games to process")

    # Counter for successful updates
    success_count = 0

    # Process games in batches to avoid memory issues
    for i in range(0, total_games, batch_size):
        batch = game_ids[i:i+batch_size]
        logger.info(
            f"Processing batch {i//batch_size + 1} of {(total_games + batch_size - 1)//batch_size} (games {i+1}-{min(i+batch_size, total_games)})")

        for game_id in batch:
            success = await update_game_time(game_id, time_adjustment)
            if success:
                success_count += 1

        # Log progress after each batch
        logger.info(
            f"Completed {min(i+batch_size, total_games)} of {total_games} games ({success_count} successful updates)")

    return {
        "total": total_games,
        "success": success_count
    }


async def verify_game_times(game_ids: List[str]) -> None:
    """Verify the current times for specified game IDs."""
    db = get_database()

    try:
        for game_id in game_ids:
            logger.info(f"Verifying game ID: {game_id}")

            # Get the game from the database
            game = db.get_crash_game_by_id(game_id)

            if not game:
                logger.warning(f"Game with ID {game_id} not found")
                continue

            # Log the current times
            logger.info(f"  Begin Time: {game.beginTime}")
            logger.info(f"  End Time: {game.endTime}")
            logger.info(f"  Prepare Time: {game.prepareTime}")
    finally:
        # Close the database connection
        db.close()
        logger.info("Database connection closed")


async def main():
    """Main function to run the script based on command line arguments."""
    args = parse_arguments()

    logger.info(f"Starting game time {args.action} script")

    # Get the list of game IDs to process
    game_ids = get_game_ids(args)

    if not game_ids:
        logger.error("No game IDs found to process")
        return

    logger.info(f"Found {len(game_ids)} game(s) to process")

    # Process the games based on the action
    if args.action in ['update', 'revert']:
        time_adjustment = get_time_adjustment(args, args.action)
        batch_size = args.batch_size

        logger.info(f"Time adjustment: {time_adjustment}")
        logger.info(f"Batch size: {batch_size}")

        results = await process_games(game_ids, time_adjustment, batch_size)
        logger.info(
            f"Successfully processed {results['success']} out of {results['total']} games")

    elif args.action == 'verify':
        await verify_game_times(game_ids)

    logger.info(f"Game time {args.action} completed")


if __name__ == "__main__":
    asyncio.run(main())
