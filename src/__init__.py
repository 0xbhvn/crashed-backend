"""
Crash Monitor Package

This package provides modules for monitoring Crash game,
calculating crash values, and storing results in a database.

Modules:
    config: Centralizes all configuration values with defaults
    history: Contains the main monitoring logic
    db: Database models and operations
    utils: Utility functions for environment, logging, and API interaction
    app: Main application entry point with CLI commands
"""

# Version information
__version__ = '0.2.0'

# Import commonly used modules for convenience
from .db import CrashGame, get_database
from .utils import load_env, configure_logging

# Allow running the package directly with python -m src
if __name__ == '__main__':
    import sys
    from .app import main
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Monitor stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error running monitor: {e}")
        sys.exit(1)
