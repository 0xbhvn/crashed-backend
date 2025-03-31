#!/usr/bin/env python
"""
Update calculated points for all games in the database.
"""

import logging
from tqdm import tqdm
from src.db.engine import Database
from src.db.models import CrashGame
from src.history import BCCrashMonitor

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def update_calculated_points():
    """Update calculated points for all games that don't have them."""
    # Initialize database
    db = Database()

    with db.get_session() as session:
        # Count games without calculated points
        count_missing = session.query(CrashGame).filter(
            (CrashGame.calculatedPoint.is_(None)) &
            (CrashGame.hashValue.isnot(None))
        ).count()

        logger.info(
            f"Found {count_missing} games that need their calculated points updated")

        if count_missing == 0:
            logger.info("No games need updating, exiting")
            return

        # Get all games without calculated points but with hash values
        games_to_update = session.query(CrashGame).filter(
            (CrashGame.calculatedPoint.is_(None)) &
            (CrashGame.hashValue.isnot(None))
        ).all()

        # Update each game
        updated_count = 0
        failed_count = 0

        for game in tqdm(games_to_update, desc="Updating games"):
            try:
                if game.hashValue:
                    calculated_point = BCCrashMonitor.calculate_crash_point(
                        seed=game.hashValue)
                    game.calculatedPoint = calculated_point
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error updating game {game.gameId}: {e}")
                failed_count += 1

        # Commit all changes
        session.commit()

        logger.info(f"Updated {updated_count} games with calculated points")
        if failed_count > 0:
            logger.warning(f"Failed to update {failed_count} games")

    # Verify the updates
    with db.get_session() as session:
        count_still_missing = session.query(CrashGame).filter(
            (CrashGame.calculatedPoint.is_(None)) &
            (CrashGame.hashValue.isnot(None))
        ).count()

        logger.info(
            f"Games still missing calculated points: {count_still_missing}")

        # Sample a few games to verify
        sample_games = session.query(CrashGame).filter(
            CrashGame.calculatedPoint.isnot(None)
        ).limit(5).all()

        logger.info("Sample of updated games:")
        for game in sample_games:
            logger.info(
                f"Game {game.gameId}: Crash Point={game.crashPoint}, Calculated Point={game.calculatedPoint}")


if __name__ == "__main__":
    update_calculated_points()
