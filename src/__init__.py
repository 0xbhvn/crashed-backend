"""
BC Game Crash Monitor Package

This package provides modules for monitoring BC Game's crash game,
calculating crash values, and storing results in a database.

Modules:
    config: Centralizes all configuration values with defaults
    history: Contains the main application logic
"""

# Version information
__version__ = '0.1.0'

# Allow running the package directly with python -m src
if __name__ == '__main__':
    import sys
    from . import history
    import asyncio

    try:
        asyncio.run(history.main())
    except KeyboardInterrupt:
        print("Monitor stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error running monitor: {e}")
        sys.exit(1)
