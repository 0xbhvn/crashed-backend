"""
Database module for BC Game Crash Monitor.

This module provides database functionality for storing and retrieving crash games.
It also includes migration utilities for managing database schema changes.
"""

# Import core database components
from .models import Base, CrashGame
from .engine import Database, get_database

# Import migration utilities
from .migrate import (
    create_migration,
    upgrade_database,
    downgrade_database,
    show_migrations
)

# Re-export key functions for backward compatibility
from .engine import get_database

__all__ = [
    # Core database models and engine
    'Base',
    'CrashGame',
    'Database',
    'get_database',

    # Migration utilities
    'create_migration',
    'upgrade_database',
    'downgrade_database',
    'show_migrations',
]
