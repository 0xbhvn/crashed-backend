"""
SQLAlchemy database connection and operations.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError

from src.models import Base, CrashGame
from src import config

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
                CrashGame.game_id == game_data['game_id']
            ).first()

            if existing_game:
                logger.info(
                    f"Game with ID {game_data['game_id']} already exists, skipping")
                return existing_game

            # Create new game
            game = CrashGame(**game_data)
            session.add(game)
            session.commit()
            logger.info(f"Added new game with ID {game_data['game_id']}")
            return game
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error adding crash game: {str(e)}")
            raise
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
            return session.query(CrashGame).filter(CrashGame.game_id == game_id).first()
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


def get_database() -> Database:
    """Get or create the database instance.

    Returns:
        The database instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
