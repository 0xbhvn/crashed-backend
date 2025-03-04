#!/usr/bin/env python3
"""
Script to update crashed_floor values for existing records.
This sets the floor value of each crash point for all existing records.
"""

from src.sqlalchemy_db import get_database
from src.models import CrashGame
import os
import sys
import logging
from sqlalchemy import update
from sqlalchemy.sql import func
import asyncio

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('update_crashed_floor')

# Import our modules


async def update_crashed_floor():
    """Update crashed_floor for all existing records."""
    logger.info("Starting update of crashed_floor values for existing records")

    # Get database instance
    db = get_database()

    try:
        # Get session
        session = db.get_session()

        # Count records before update
        total_records = session.query(CrashGame).count()
        logger.info(f"Total records to update: {total_records}")

        if total_records == 0:
            logger.info("No records found to update.")
            return

        # Update records in chunks to avoid memory issues
        chunk_size = 1000
        updated_count = 0

        # First get all IDs
        all_game_ids = [game_id for (
            game_id,) in session.query(CrashGame.gameId).all()]

        # Process in chunks
        for i in range(0, len(all_game_ids), chunk_size):
            chunk_ids = all_game_ids[i:i+chunk_size]

            # Get games in this chunk
            games = session.query(CrashGame).filter(
                CrashGame.gameId.in_(chunk_ids)).all()

            # Update crashed_floor for each game
            for game in games:
                if game.crashPoint is not None:
                    game.crashedFloor = int(game.crashPoint)

            # Commit the changes
            session.commit()

            # Update count
            updated_count += len(games)
            logger.info(f"Updated {updated_count}/{total_records} records")

        logger.info(
            f"Successfully updated crashed_floor for {updated_count} records")
    except Exception as e:
        logger.error(f"Error updating crashed_floor values: {e}")
        if session:
            session.rollback()
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    # Run the async function
    asyncio.run(update_crashed_floor())
