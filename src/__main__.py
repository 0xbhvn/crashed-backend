"""
Main entry point for the package when run as a module.
"""
import sys
import asyncio
from . import history

try:
    print("Starting BC Game Crash Monitor (run as module)...")
    asyncio.run(history.main())
except KeyboardInterrupt:
    print("Monitor stopped by user.")
    sys.exit(0)
except Exception as e:
    print(f"Error running monitor: {e}")
    sys.exit(1) 