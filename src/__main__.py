"""
Main entry point for the package when run as a module.

This file simply imports and runs the main function from the app module.
"""

import sys
import asyncio
from .app import main

if __name__ == "__main__":
    try:
        # Run the Crash Monitor
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCrash Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error running Crash Monitor: {e}")
        sys.exit(1)
