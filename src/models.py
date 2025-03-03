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

    id = Column(Integer, primary_key=True, autoincrement=True)
    gameId = Column(String, unique=True, name='game_id')
    hashValue = Column(String, name='hash_value')
    crashPoint = Column(Float, name='crash_point')
    calculatedPoint = Column(Float, name='calculated_point')

    # Game timing information
    endTimeUnix = Column(BigInteger, name='end_time_unix', nullable=True)
    endTime = Column(DateTime, name='end_time', nullable=True)
    prepareTimeUnix = Column(
        BigInteger, name='prepare_time_unix', nullable=True)
    prepareTime = Column(DateTime, name='prepare_time', nullable=True)
    beginTimeUnix = Column(BigInteger, name='begin_time_unix', nullable=True)
    beginTime = Column(DateTime, name='begin_time', nullable=True)

    # Additional fields
    verified = Column(Boolean, default=False)

    # Statistics
    deviation = Column(Float, nullable=True)

    # Metadata - Using timezone from configuration
    createdAt = Column(
        DateTime, default=get_current_timezone_time, name='created_at')
    updatedAt = Column(DateTime, default=get_current_timezone_time,
                       onupdate=get_current_timezone_time, name='updated_at')

    # Add indexes for commonly queried fields
    __table_args__ = (
        Index('ix_crash_games_created_at', 'created_at'),
        Index('ix_crash_games_crash_point', 'crash_point'),
        Index('ix_crash_games_begin_time', 'begin_time'),
        Index('ix_crash_games_end_time', 'end_time'),
        Index('ix_crash_games_verified', 'verified'),
    )

    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'gameId': self.gameId,
            'hashValue': self.hashValue,
            'crashPoint': self.crashPoint,
            'calculatedPoint': self.calculatedPoint,
            'endTimeUnix': self.endTimeUnix,
            'endTime': self.endTime,
            'prepareTimeUnix': self.prepareTimeUnix,
            'prepareTime': self.prepareTime,
            'beginTimeUnix': self.beginTimeUnix,
            'beginTime': self.beginTime,
            'verified': self.verified,
            'deviation': self.deviation,
            'createdAt': self.createdAt,
            'updatedAt': self.updatedAt
        }


class CrashStats(Base):
    """Model representing aggregated statistics for crash games."""

    __tablename__ = 'crash_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, unique=True)
    gamesCount = Column(Integer, name='games_count')
    averageCrash = Column(Float, name='average_crash')
    medianCrash = Column(Float, name='median_crash')
    maxCrash = Column(Float, name='max_crash')
    minCrash = Column(Float, name='min_crash')
    standardDeviation = Column(Float, name='standard_deviation')

    # Metadata - Using timezone from configuration
    createdAt = Column(
        DateTime, default=get_current_timezone_time, name='created_at')
    updatedAt = Column(DateTime, default=get_current_timezone_time,
                       onupdate=get_current_timezone_time, name='updated_at')

    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'date': self.date,
            'gamesCount': self.gamesCount,
            'averageCrash': self.averageCrash,
            'medianCrash': self.medianCrash,
            'maxCrash': self.maxCrash,
            'minCrash': self.minCrash,
            'standardDeviation': self.standardDeviation,
            'createdAt': self.createdAt,
            'updatedAt': self.updatedAt
        }
