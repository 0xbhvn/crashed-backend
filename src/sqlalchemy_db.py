"""
SQLAlchemy database module for BC Game Crash Monitor.

This module provides database functionality using SQLAlchemy ORM,
replacing the Prisma client with a more Python-native approach.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
import pytz

from src.models import Base, CrashGame, CrashStats
from . import config

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)  # Respect the configured log level

# Define timezone from configuration
app_timezone = pytz.timezone(config.TIMEZONE)


class Database:
    """SQLAlchemy database manager for BC Game Crash Monitor."""

    def __init__(self, database_url: str = None):
        """Initialize the database connection.

        Args:
            database_url: The database connection URL. If None, uses DATABASE_URL from environment.
        """
        if database_url is None:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError(
                    "DATABASE_URL environment variable is not set")

        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine)

        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        logger.info(f"Connected to database: {database_url}")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def create_tables(self):
        """Create all tables defined in the models."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")

    def add_crash_game(self, game_data: Dict[str, Any]) -> CrashGame:
        """Add a new crash game to the database.

        Args:
            game_data: Dictionary containing crash game data.

        Returns:
            The newly created CrashGame instance.

        Raises:
            SQLAlchemyError: If there's an error during database operation.
        """
        try:
            with self.get_session() as session:
                # Create new CrashGame instance
                new_game = CrashGame(**game_data)

                # Add to session and commit
                session.add(new_game)
                session.commit()

                # Refresh to get the assigned ID
                session.refresh(new_game)

                logger.debug(f"Added new crash game with ID {new_game.gameId}")
                return new_game
        except SQLAlchemyError as e:
            logger.error(f"Database error adding crash game: {str(e)}")
            raise

    def bulk_add_crash_games(self, games_data: List[Dict[str, Any]]) -> List[str]:
        """Add multiple crash games to the database in a single transaction.

        Args:
            games_data: List of dictionaries containing crash game data.

        Returns:
            List of game IDs that were successfully added.

        Raises:
            SQLAlchemyError: If there's an error during database operation.
        """
        if not games_data:
            logger.debug("No games to bulk add")
            return []

        added_game_ids = []
        try:
            with self.get_session() as session:
                # Create CrashGame instances for each game data
                new_games = [CrashGame(**game_data)
                             for game_data in games_data]

                # Add all games to session
                session.add_all(new_games)

                # Commit the transaction
                session.commit()

                # Collect the game IDs
                added_game_ids = [game.gameId for game in new_games]

                logger.debug(f"Bulk added {len(added_game_ids)} crash games")
                return added_game_ids

        except SQLAlchemyError as e:
            logger.error(f"Database error bulk adding crash games: {str(e)}")
            raise

        return added_game_ids

    def get_crash_game_by_id(self, game_id: str) -> Optional[CrashGame]:
        """Get a crash game by its game ID.

        Args:
            game_id: The game ID to search for

        Returns:
            CrashGame instance if found, None otherwise
        """
        session = self.get_session()
        try:
            crash_game = session.query(CrashGame).filter(
                CrashGame.gameId == game_id).first()
            return crash_game
        except SQLAlchemyError as e:
            logger.error(f"Error getting crash game by ID: {str(e)}")
            raise
        finally:
            session.close()

    def get_latest_crash_games(self, limit: int = 10) -> List[CrashGame]:
        """Get the latest crash games.

        Args:
            limit: Maximum number of games to return

        Returns:
            List of CrashGame instances
        """
        session = self.get_session()
        try:
            crash_games = session.query(CrashGame).order_by(
                desc(CrashGame.gameId)).limit(limit).all()
            return crash_games
        except SQLAlchemyError as e:
            logger.error(f"Error getting latest crash games: {str(e)}")
            raise
        finally:
            session.close()

    def update_crash_game(self, game_id: str, update_data: Dict[str, Any]) -> Optional[CrashGame]:
        """Update a crash game by its game ID.

        Args:
            game_id: The game ID to update
            update_data: Dictionary containing fields to update

        Returns:
            Updated CrashGame instance if found, None otherwise
        """
        session = self.get_session()
        try:
            crash_game = session.query(CrashGame).filter(
                CrashGame.gameId == game_id).first()
            if not crash_game:
                logger.warning(
                    f"Crash game with ID {game_id} not found for update")
                return None

            # Update fields
            for key, value in update_data.items():
                if hasattr(crash_game, key):
                    setattr(crash_game, key, value)

            session.commit()
            session.refresh(crash_game)
            logger.info(f"Updated crash game with ID: {game_id}")
            return crash_game
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating crash game: {str(e)}")
            raise
        finally:
            session.close()

    def get_crash_stats(self, date: datetime) -> Optional[CrashStats]:
        """Get crash statistics for a specific date.

        Args:
            date: The date to get statistics for

        Returns:
            CrashStats instance if found, None otherwise
        """
        session = self.get_session()
        try:
            stats = session.query(CrashStats).filter(
                func.date(CrashStats.date) == func.date(date)).first()
            return stats
        except SQLAlchemyError as e:
            logger.error(f"Error getting crash stats: {str(e)}")
            raise
        finally:
            session.close()

    def update_or_create_crash_stats(self, date: datetime, stats_data: Dict[str, Any]) -> CrashStats:
        """Update or create crash statistics for a specific date.

        Args:
            date: The date to update or create statistics for
            stats_data: Dictionary containing statistics data

        Returns:
            Updated or created CrashStats instance
        """
        session = self.get_session()
        try:
            stats = session.query(CrashStats).filter(
                func.date(CrashStats.date) == func.date(date)).first()

            if stats:
                # Update existing stats
                for key, value in stats_data.items():
                    if hasattr(stats, key):
                        setattr(stats, key, value)
                logger.debug(f"Updated crash stats for date: {date}")
            else:
                # Create new stats
                stats_data['date'] = date
                stats = CrashStats(**stats_data)
                session.add(stats)
                logger.info(f"Created crash stats for date: {date}")

            session.commit()
            session.refresh(stats)
            return stats
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating or creating crash stats: {str(e)}")
            raise
        finally:
            session.close()

    def close(self):
        """Close the database connection."""
        self.engine.dispose()
        logger.info("Database connection closed")


# Singleton instance
_db_instance = None


def get_database() -> Database:
    """Get or create the database instance.

    Returns:
        The database instance
    """
    global _db_instance
    if _db_instance is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            database_url = "postgresql://postgres:postgres@localhost:5432/bc_crash_db"
            logger.warning(
                f"DATABASE_URL not set, using default: {database_url}")
        _db_instance = Database(database_url)
    return _db_instance
