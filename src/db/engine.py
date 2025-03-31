"""
SQLAlchemy database connection and operations.

This module provides the Database class which handles all SQLAlchemy
operations for crash games in a centralized manner.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from .models import Base, CrashGame
from .. import config

# Configure logging
logger = logging.getLogger(__name__)


class Database:
    """
    Database connection and operations using SQLAlchemy.
    """

    def __init__(self, connection_string=None):
        """
        Initialize the database connection.

        Args:
            connection_string (str, optional): Connection string for the database.
                If not provided, it will be read from the config.
        """
        if connection_string is None:
            # Get database connection string from config
            connection_string = config.DATABASE_URL

        # Create engine and session
        self.engine = create_engine(connection_string)
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

        # Get a masked version of the connection string for logging
        masked_connection = connection_string
        if '@' in connection_string:
            # Remove password from connection string for logging
            parts = connection_string.split('@')
            auth_parts = parts[0].split(':')
            if len(auth_parts) > 2:  # Has password
                masked_connection = f"{auth_parts[0]}:****@{parts[1]}"

        logger.info(f"Connected to database: {masked_connection}")

    def get_session(self):
        """
        Get a database session.

        Returns:
            sqlalchemy.orm.Session: Database session
        """
        return self.Session()

    # Add synchronous context manager support
    def __enter__(self):
        """
        Enter the synchronous context manager.

        Returns:
            sqlalchemy.orm.Session: Database session
        """
        self.session = self.get_session()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the synchronous context manager.
        """
        if self.session:
            if exc_type is not None:
                self.session.rollback()
            self.session.close()

    # Add asynchronous context manager support
    async def __aenter__(self):
        """
        Enter the asynchronous context manager.

        Returns:
            sqlalchemy.orm.Session: Database session
        """
        self.session = self.get_session()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the asynchronous context manager.
        """
        if self.session:
            if exc_type is not None:
                self.session.rollback()
            self.session.close()

    # Add a method to run synchronous functions in async context
    async def run_sync(self, func, *args, **kwargs):
        """
        Run a synchronous function with database session.

        Args:
            func: The function to run
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Any: The result of the function
        """
        return func(self.session, *args, **kwargs)

    def create_tables(self):
        """
        Create database tables if they don't exist.
        """
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")

    def add_crash_game(self, game_data: Dict[str, Any]) -> CrashGame:
        """
        Add a new crash game to the database.

        Args:
            game_data (Dict[str, Any]): Game data

        Returns:
            CrashGame: The created game instance
        """
        session = self.get_session()
        try:
            # Check if a game with this ID already exists
            existing_game = session.query(CrashGame).filter(
                CrashGame.gameId == game_data['gameId']
            ).first()

            if existing_game:
                logger.info(
                    f"Game with ID {game_data['gameId']} already exists, skipping")
                return existing_game

            # Create new game
            game = CrashGame(**game_data)
            session.add(game)
            session.commit()
            logger.info(f"Added new game with ID {game_data['gameId']}")
            return game
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error adding crash game: {str(e)}")
            raise
        finally:
            session.close()

    def update_crash_game(self, game_id: str, game_data: Dict[str, Any]) -> Optional[CrashGame]:
        """
        Update an existing crash game.

        Args:
            game_id (str): The ID of the game to update
            game_data (Dict[str, Any]): New game data

        Returns:
            Optional[CrashGame]: The updated game or None if not found
        """
        session = self.get_session()
        try:
            # Get the existing game
            game = session.query(CrashGame).filter(
                CrashGame.gameId == game_id).first()

            if not game:
                logger.warning(f"Game with ID {game_id} not found for update")
                return None

            # Update game attributes
            for key, value in game_data.items():
                setattr(game, key, value)

            session.commit()
            logger.info(f"Updated game with ID {game_id}")
            return game
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating crash game: {str(e)}")
            raise
        finally:
            session.close()

    def bulk_add_crash_games(self, games_data: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple crash games in a single transaction.

        Args:
            games_data (List[Dict[str, Any]]): List of game data dictionaries

        Returns:
            List[str]: List of added game IDs
        """
        if not games_data:
            return []

        session = self.get_session()
        added_game_ids = []
        failed_game_ids = []

        try:
            for game_data in games_data:
                game_id = game_data.get('gameId')

                # Skip if no game_id
                if not game_id:
                    logger.warning(f"Skipping game with no ID: {game_data}")
                    continue

                try:
                    # Check if game already exists
                    existing_game = session.query(CrashGame).filter(
                        CrashGame.gameId == game_id
                    ).first()

                    if existing_game:
                        logger.debug(
                            f"Game with ID {game_id} already exists, skipping")
                        continue

                    # Create and add game
                    game = CrashGame(**game_data)
                    session.add(game)
                    added_game_ids.append(game_id)
                except Exception as e:
                    # If an individual game fails, log it and continue with others
                    logger.error(f"Error adding game {game_id}: {str(e)}")
                    failed_game_ids.append(game_id)
                    continue

            # Commit all changes at once
            session.commit()

            if failed_game_ids:
                logger.warning(
                    f"Failed to add {len(failed_game_ids)} games: {failed_game_ids[:10]}...")

            logger.info(f"Added {len(added_game_ids)} new games in bulk")
            return added_game_ids
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error in bulk adding crash games: {str(e)}")
            # Return the games that were successfully added up to this point
            logger.info(f"Transaction failed, no games were added")
            return []
        finally:
            session.close()

    def get_crash_games(self, limit: int = 100, offset: int = 0,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[CrashGame]:
        """
        Get crash games with pagination and optional date filtering.

        Args:
            limit (int, optional): Maximum number of games to return. Defaults to 100.
            offset (int, optional): Offset for pagination. Defaults to 0.
            start_date (datetime, optional): Start date for filtering. Defaults to None.
            end_date (datetime, optional): End date for filtering. Defaults to None.

        Returns:
            List[CrashGame]: List of crash games
        """
        session = self.get_session()
        try:
            query = session.query(CrashGame)

            # Apply date filters if provided
            if start_date:
                query = query.filter(CrashGame.beginTime >= start_date)
            if end_date:
                query = query.filter(CrashGame.beginTime <= end_date)

            # Apply limit and offset and get results
            query = query.order_by(CrashGame.beginTime.desc()).limit(
                limit).offset(offset)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting crash games: {str(e)}")
            raise
        finally:
            session.close()

    def get_latest_crash_games(self, limit: int = 10) -> List[CrashGame]:
        """
        Get the most recent crash games.

        Args:
            limit (int, optional): Maximum number of games to return. Defaults to 10.

        Returns:
            List[CrashGame]: List of recent crash games
        """
        return self.get_crash_games(limit=limit)

    def get_crash_game_by_id(self, game_id: str) -> Optional[CrashGame]:
        """
        Get a crash game by its ID.

        Args:
            game_id (str): Game ID

        Returns:
            Optional[CrashGame]: Crash game if found, None otherwise
        """
        session = self.get_session()
        try:
            return session.query(CrashGame).filter(CrashGame.gameId == game_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting crash game by ID: {str(e)}")
            raise
        finally:
            session.close()

    def count_crash_games(self, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> int:
        """
        Count crash games in the database with optional date filtering.

        Args:
            start_date (datetime, optional): Start date for filtering. Defaults to None.
            end_date (datetime, optional): End date for filtering. Defaults to None.

        Returns:
            int: Number of crash games
        """
        session = self.get_session()
        try:
            query = session.query(func.count(CrashGame.gameId))

            # Apply date filters if provided
            if start_date:
                query = query.filter(CrashGame.beginTime >= start_date)
            if end_date:
                query = query.filter(CrashGame.beginTime <= end_date)

            return query.scalar()
        except SQLAlchemyError as e:
            logger.error(f"Error counting crash games: {str(e)}")
            raise
        finally:
            session.close()

    def get_last_crash_game(self) -> Optional[CrashGame]:
        """
        Get the most recently created crash game.

        Returns:
            Optional[CrashGame]: The most recent crash game or None if no games exist
        """
        session = self.get_session()
        try:
            return session.query(CrashGame).order_by(CrashGame.beginTime.desc()).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting last crash game: {str(e)}")
            raise
        finally:
            session.close()

    def close(self):
        """
        Close the database connection.
        """
        self.Session.remove()
        logger.info("Database connection closed")


# Singleton instance
_db_instance = None


def get_database(engine=None) -> Database:
    """Get or create the database instance.

    Args:
        engine: SQLAlchemy engine to use (optional)

    Returns:
        The database instance
    """
    global _db_instance
    if _db_instance is None:
        if engine:
            _db_instance = Database(
                engine.url.render_as_string(hide_password=False))
        else:
            _db_instance = Database()
    return _db_instance
