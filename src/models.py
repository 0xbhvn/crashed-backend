"""
SQLAlchemy models for BC Game Crash Monitor.

This module defines the database models used by the application, replacing the Prisma models
with SQLAlchemy equivalents for better Python integration.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, BigInteger, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz

from . import config

# Define timezone from configuration
app_timezone = pytz.timezone(config.TIMEZONE)


def get_current_timezone_time():
    """Return current time in the configured timezone."""
    return datetime.now(app_timezone)


Base = declarative_base()


class CrashGame(Base):
    """Model representing a crash game result."""

    __tablename__ = 'crash_games'

    gameId = Column(String, primary_key=True, name='game_id')
    hashValue = Column(String, name='hash_value')
    crashPoint = Column(Float, name='crash_point')
    calculatedPoint = Column(Float, name='calculated_point')
    crashedFloor = Column(Integer, name='crashed_floor',
                          nullable=True)  # Floored value of crash point

    # Game timing information
    endTime = Column(DateTime, name='end_time', nullable=True)
    prepareTime = Column(DateTime, name='prepare_time', nullable=True)
    beginTime = Column(DateTime, name='begin_time', nullable=True)

    # Add indexes for commonly queried fields
    __table_args__ = (
        Index('ix_crash_games_crash_point', 'crash_point'),
        Index('ix_crash_games_begin_time', 'begin_time'),
        Index('ix_crash_games_end_time', 'end_time'),
    )

    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'gameId': self.gameId,
            'hashValue': self.hashValue,
            'crashPoint': self.crashPoint,
            'calculatedPoint': self.calculatedPoint,
            'crashedFloor': self.crashedFloor,
            'endTime': self.endTime,
            'prepareTime': self.prepareTime,
            'beginTime': self.beginTime
        }
