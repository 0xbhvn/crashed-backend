#!/usr/bin/env python3
"""
Unified entry point for the BC Game Crash Monitor application.

This module serves as the main entry point for the application,
initializing components and running the monitor.
"""

import os
import sys
import asyncio
import argparse
import logging
from typing import Optional, Dict, Any
from aiohttp import web
import gc
import json
import subprocess

# Import from local modules
from . import config
from .history import BCCrashMonitor
from .utils import load_env, configure_logging, fetch_game_history, fetch_games_batch
from .db import get_database, CrashGame, create_migration, upgrade_database, downgrade_database, show_migrations


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="BC Game Crash Monitor - A tool for monitoring BC Game's crash game"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Monitor command
    monitor_parser = subparsers.add_parser(
        "monitor", help="Run the crash monitor")
    monitor_parser.add_argument(
        "--skip-catchup",
        action="store_true",
        help="Skip the catchup process on startup"
    )
    monitor_parser.add_argument(
        "--skip-polling",
        action="store_true",
        help="Skip the polling process and only run the API server"
    )

    # Catchup command
    catchup_parser = subparsers.add_parser(
        "catchup", help="Run only the catchup process")
    catchup_parser.add_argument(
        "--pages",
        type=int,
        default=config.CATCHUP_PAGES,
        help=f"Number of pages to fetch (default: {config.CATCHUP_PAGES})"
    )
    catchup_parser.add_argument(
        "--batch-size",
        type=int,
        default=config.CATCHUP_BATCH_SIZE,
        help=f"Batch size for concurrent requests (default: {config.CATCHUP_BATCH_SIZE})"
    )
    catchup_parser.add_argument(
        "--page-size",
        type=int,
        default=int(os.environ.get('PAGE_SIZE', '20')),
        help=f"Number of items per page (default: 20, max: 100)"
    )

    # Database migration commands
    migrate_parser = subparsers.add_parser(
        "migrate", help="Database migration commands")
    migrate_subparsers = migrate_parser.add_subparsers(
        dest="migrate_command", help="Migration command to run")

    # Create migration command
    create_parser = migrate_subparsers.add_parser(
        "create", help="Create a new migration")
    create_parser.add_argument(
        "message", help="Migration message")

    # Upgrade command
    upgrade_parser = migrate_subparsers.add_parser(
        "upgrade", help="Upgrade to a later version")
    upgrade_parser.add_argument(
        "--revision",
        type=str,
        default="head",
        help="Revision to upgrade to (default: head)"
    )

    # Downgrade command
    downgrade_parser = migrate_subparsers.add_parser(
        "downgrade", help="Revert to a previous version")
    downgrade_parser.add_argument(
        "--revision",
        type=str,
        default="-1",
        help="Revision to downgrade to (default: -1)"
    )

    # History command
    migrate_subparsers.add_parser(
        "history", help="Show migration history")

    return parser.parse_args()


async def run_monitor(skip_catchup: bool = False, skip_polling: bool = False) -> None:
    """
    Run the BC Game Crash Monitor

    Args:
        skip_catchup: Whether to skip the catchup process
        skip_polling: Whether to skip the polling process and only run the API server
    """
    logger = logging.getLogger("app")

    # Initialize the monitor
    db_engine = None
    db = None

    if config.DATABASE_ENABLED:
        try:
            # Initialize database
            from sqlalchemy import create_engine
            db_engine = create_engine(config.DATABASE_URL)
            # Create database instance for API routes
            from .db.engine import Database
            db = Database(connection_string=config.DATABASE_URL)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Continuing without database support")

    # Set up API server
    from .api import setup_api
    api_app = web.Application()

    # Store database in app
    if db:
        api_app['db'] = db

    # Set up API and WebSocket routes
    setup_api(api_app)

    # Get API port from config or environment, fallback to 3000 for container compatibility
    api_port = int(config.get_env_var('API_PORT', '3000'))

    # Create API server
    api_runner = web.AppRunner(api_app)
    await api_runner.setup()
    api_site = web.TCPSite(api_runner, '0.0.0.0', api_port)
    await api_site.start()
    logger.info(f"API server started on port {api_port}")

    # Skip the rest if we're only running the API server
    if skip_polling:
        logger.info("Polling skipped, only running API server")
        # Keep the application running
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
        return

    # Create monitor instance
    monitor = BCCrashMonitor(
        database_enabled=config.DATABASE_ENABLED,
        db_engine=db_engine,
        # Disable verbose logging in the monitor since we'll log in the callback
        verbose_logging=False
    )

    # Store monitor in app for API access
    api_app['monitor'] = monitor

    # Run catchup process if enabled
    if not skip_catchup and config.CATCHUP_ENABLED:
        try:
            logger.info("Running catchup process...")
            await run_catchup(pages=config.CATCHUP_PAGES, batch_size=config.CATCHUP_BATCH_SIZE, page_size=config.CATCHUP_PAGE_SIZE)
            logger.info("Catchup process completed")
        except Exception as e:
            logger.error(f"Error during catchup process: {e}")
            logger.warning("Continuing with monitor despite catchup failure")

    # Register callback for new games
    async def log_game(game_data: Dict[str, Any]) -> None:
        """Log new games and broadcast via WebSocket."""
        # Convert crashPoint to float for logging
        crash_point = float(game_data.get('crashPoint', 0))
        game_id = game_data.get('gameId', 'unknown')

        logger.info(f"New game: {game_id} with crash point: {crash_point}")

        try:
            # Broadcast the new game to WebSocket clients if we have a WebSocket manager
            if 'websocket_manager' in api_app:
                await api_app['websocket_manager'].broadcast_new_game(game_data)
        except Exception as e:
            logger.error(f"Error broadcasting game via WebSocket: {e}")

    # Register the callback with the monitor
    monitor.register_game_callback(log_game)

    # Start the monitor (run forever)
    logger.info("Starting BC Game Crash Monitor")
    await monitor.run()

    # Cleanup on exit
    await api_runner.cleanup()
    logger.info("BC Game Crash Monitor stopped")


async def run_catchup(pages: int = 20, batch_size: int = 20, page_size: int = None) -> None:
    """
    Run the catchup process to fetch historical crash game data.

    Args:
        pages: Number of pages to fetch
        batch_size: Batch size for concurrent requests
        page_size: Number of items per page (default is 20, max is 100)
    """
    logger = logging.getLogger("app.catchup")
    logger.info(
        f"Starting catchup with {pages} pages, batch size {batch_size}, page size {page_size}")

    # Use default page size if not provided
    if page_size is None:
        page_size = int(os.environ.get('PAGE_SIZE', '20'))

    # Import here to avoid circular imports
    from .db.engine import Database

    # Initialize database
    db = None

    if config.DATABASE_ENABLED:
        try:
            db = Database(connection_string=config.DATABASE_URL)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Continuing without database support")

    # Set up batches
    total_fetched = 0
    total_skipped = 0
    total_saved = 0
    total_failed = 0

    # Helper function to use our Selenium-based fetcher
    def fetch_with_selenium_fetcher(page, page_size, output_file="temp_data.json"):
        try:
            # First, try to import the cookie-based fetcher directly
            use_cf_cookies_path = os.path.join(os.path.dirname(
                os.path.dirname(__file__)), "use_cf_cookies.py")

            if os.path.exists(use_cf_cookies_path):
                # Add the project root to sys.path if it's not already there
                project_root = os.path.dirname(os.path.dirname(__file__))
                if project_root not in sys.path:
                    sys.path.append(project_root)

                # Try to import functions directly
                try:
                    # Using importlib to import the module dynamically
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(
                        "use_cf_cookies", use_cf_cookies_path)
                    cf_cookies_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(cf_cookies_module)

                    # Now use the imported function
                    logger.info(
                        f"Using direct import of use_cf_cookies for page {page}, size {page_size}")
                    data = cf_cookies_module.fetch_game_history(
                        page, page_size)

                    # Save the data to the output file
                    with open(output_file, 'w') as f:
                        json.dump(data, f, indent=2)

                    return data

                except Exception as e:
                    logger.warning(
                        f"Error importing use_cf_cookies directly: {e}")
                    # Fall back to subprocess approach

            # Locate our bc_game_fetcher.py in the project root
            script_path = os.path.join(os.path.dirname(
                os.path.dirname(__file__)), "bc_game_fetcher.py")

            if not os.path.exists(script_path):
                logger.error(f"Fetcher script not found at {script_path}")
                return None

            # Execute our BC Game fetcher script
            cmd = [sys.executable, script_path,
                   "--page", str(page),
                   "--size", str(page_size),
                   "--output", output_file]

            logger.info(f"Executing fetcher: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)
            logger.info(f"Fetcher stdout: {result.stdout}")

            if result.stderr:
                logger.warning(f"Fetcher stderr: {result.stderr}")

            if result.returncode != 0:
                logger.error(f"Error running fetcher: {result.stderr}")
                return None

            # Check if output file exists
            if not os.path.exists(output_file):
                logger.error(f"Output file {output_file} not created")
                return None

            # Load the data from the file
            with open(output_file, 'r') as f:
                try:
                    data = json.load(f)
                    logger.info(
                        f"File content keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    if 'data' in data:
                        logger.info(
                            f"Data keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'not a dict'}")
                    return data
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in output file: {e}")
                    return None
        except Exception as e:
            logger.error(f"Error using Selenium fetcher: {e}")
            return None

    # Fetch data in batches
    for page in range(1, pages + 1, batch_size):
        # Calculate end page for this batch
        end_page = min(page + batch_size - 1, pages)
        pages_in_batch = end_page - page + 1

        logger.info(
            f"Fetching batch {(page-1)//batch_size + 1}/{(pages+batch_size-1)//batch_size}: "
            f"pages {page}-{end_page}"
        )

        # Process individual pages
        batch_fetched = 0
        batch_skipped = 0
        batch_saved = 0
        batch_failed = 0

        # First try with the Selenium-based fetcher
        for current_page in range(page, end_page + 1):
            temp_file = f"temp_page_{current_page}.json"
            data = fetch_with_selenium_fetcher(
                current_page, page_size, temp_file)

            # If Selenium fetcher fails, fall back to the original method
            if not data:
                logger.warning(
                    f"Selenium fetcher failed for page {current_page}, falling back to original method")
                try:
                    # Original API fetching method
                    from .utils.api import fetch_game_history
                    data = await fetch_game_history(page=current_page, page_size=page_size)
                except Exception as e:
                    logger.error(f"Error fetching page {current_page}: {e}")
                    batch_failed += 1
                    continue

            # Get game items - handle both formats ('list' and 'items')
            game_items = []
            if 'data' in data:
                if 'items' in data['data']:
                    game_items = data['data']['items']
                elif 'list' in data['data']:
                    game_items = data['data']['list']

            # Skip if no games were found
            if not game_items:
                logger.warning(f"No games found on page {current_page}")
                batch_skipped += 1
                continue

            # Process batch of games instead of one by one
            try:
                if db and config.DATABASE_ENABLED:
                    # Prepare game data for bulk insert
                    prepared_games = []

                    for game in game_items:
                        # Extract game details
                        game_id = str(game.get("gameId", ""))

                        # Extract game details if in JSON string format
                        game_detail = {}
                        if "gameDetail" in game and isinstance(game["gameDetail"], str):
                            try:
                                game_detail = json.loads(game["gameDetail"])
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Failed to parse gameDetail for game {game_id}")
                                continue

                        # Get hash and crash point
                        hash_value = game.get(
                            "hash", "") or game_detail.get("hash", "")

                        # Get crash point (rate)
                        crash_point = 1.0  # Default value
                        if "rate" in game_detail:
                            try:
                                crash_point = float(game_detail["rate"])
                            except (ValueError, TypeError):
                                pass

                        # Calculate expected crash point
                        calculated_point = 0.0
                        if hash_value and config.BC_GAME_SALT:
                            try:
                                from .history import BCCrashMonitor
                                calculated_point = BCCrashMonitor.calculate_crash_point(
                                    hash_value, config.BC_GAME_SALT)
                            except Exception as e:
                                logger.error(
                                    f"Error calculating crash point: {e}")

                        # Add to prepared games list
                        prepared_games.append({
                            'game_id': game_id,
                            'hash': hash_value,
                            'crash_point': crash_point,
                            'calculated_point': calculated_point,
                            'game_detail': game_detail
                        })

                    # Use bulk database operations
                    if prepared_games:
                        from .db.operations import bulk_store_crash_games
                        stored_ids = await bulk_store_crash_games(prepared_games)
                        batch_saved += len(stored_ids)
                        games_processed = len(prepared_games)
                        logger.info(
                            f"Bulk stored {len(stored_ids)} games from page {current_page}")

                # Even if not storing in database, count as processed
                else:
                    games_processed = len(game_items)

            except Exception as e:
                logger.error(
                    f"Error processing games from page {current_page}: {e}")
                batch_failed += 1

            logger.info(
                f"Processed {games_processed} games from page {current_page}")
            batch_fetched += games_processed

            # Clean up temp file
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove temp file {temp_file}: {e}")

        # Update totals
        total_fetched += batch_fetched
        total_skipped += batch_skipped
        total_saved += batch_saved
        total_failed += batch_failed

        logger.info(
            f"Batch complete: fetched {batch_fetched}, skipped {batch_skipped}, "
            f"saved {batch_saved}, failed {batch_failed}"
        )

        # Add a short delay between batches
        await asyncio.sleep(1)

    # Print summary
    logger.info(
        f"Catchup complete: fetched {total_fetched}, skipped {total_skipped}, "
        f"saved {total_saved}, failed {total_failed}"
    )

    # Broadcast games via WebSocket if database is connected
    if config.DATABASE_ENABLED and db is not None:
        try:
            # Get the API app to access the websocket manager
            from aiohttp.web import Application
            from .db.models import CrashGame

            for obj in gc.get_objects():
                if isinstance(obj, Application) and 'websocket_manager' in obj:
                    api_app = obj
                    break
            else:
                logger.warning(
                    "Could not find API app, not broadcasting games via WebSocket")
                return

            # Get the most recent games
            with db.get_session() as session:
                recent_games = session.query(CrashGame).order_by(
                    CrashGame.beginTime.desc()
                ).limit(10).all()

                # Convert to dictionaries
                games_data = []
                for game in recent_games:
                    game_dict = {
                        'gameId': game.gameId,
                        'hashValue': game.hashValue,
                        'crashPoint': float(game.crashPoint),
                        'calculatedPoint': float(game.calculatedPoint),
                        'crashedFloor': int(game.crashedFloor) if game.crashedFloor else None,
                        'endTime': game.endTime.isoformat() if game.endTime else None,
                        'prepareTime': game.prepareTime.isoformat() if game.prepareTime else None,
                        'beginTime': game.beginTime.isoformat() if game.beginTime else None
                    }
                    games_data.append(game_dict)

                # Broadcast the games
                await api_app['websocket_manager'].broadcast_multiple_games(games_data)
                logger.info(
                    f"Broadcasted {len(games_data)} recent games via WebSocket")
        except Exception as e:
            logger.error(f"Error broadcasting games via WebSocket: {e}")

    # Close database connection
    if db:
        db.close()


async def run_migrations(migrate_command, **kwargs):
    """
    Run database migration commands

    Args:
        migrate_command: Migration command to run
        **kwargs: Additional arguments for the migration command
    """
    logger = logging.getLogger("app")
    logger.info(f"Running database migration command: {migrate_command}")

    try:
        if migrate_command == "create":
            create_migration(kwargs.get("message", ""))
        elif migrate_command == "upgrade":
            upgrade_database(kwargs.get("revision", "head"))
        elif migrate_command == "downgrade":
            downgrade_database(kwargs.get("revision", "-1"))
        elif migrate_command == "history":
            show_migrations()
        else:
            logger.error(f"Unknown migration command: {migrate_command}")
            return

        logger.info(
            f"Migration command '{migrate_command}' completed successfully")
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise


async def health_check(request):
    """Simple health check endpoint for Railway deployment."""
    return web.Response(text="OK", status=200)


async def start_health_check_server():
    """Start a simple health check server."""
    logger = logging.getLogger("app")
    app = web.Application()
    app.router.add_get('/', health_check)

    # Get health check port from config or environment, fallback to 8080 for container compatibility
    health_port = int(config.get_env_var('HEALTH_PORT', '8080'))

    # Create health check server
    health_runner = web.AppRunner(app)
    await health_runner.setup()
    health_site = web.TCPSite(health_runner, '0.0.0.0', health_port)
    await health_site.start()
    logger.info(f"Health check server started on port {health_port}")


async def main() -> None:
    """Main entry point for the application"""
    # Start health check server for Railway
    asyncio.create_task(start_health_check_server())

    # Parse command line arguments
    args = parse_arguments()

    # Load environment variables
    load_env()

    # Reload configuration from environment variables
    from src.config import reload_config
    reload_config()

    # Configure logging
    logger = configure_logging("app", config.LOG_LEVEL)

    # Log configuration
    config.log_config()

    # Run the appropriate command
    if args.command == "catchup":
        await run_catchup(pages=args.pages, batch_size=args.batch_size, page_size=args.page_size)
    elif args.command == "migrate":
        if not args.migrate_command:
            logger.error("No migration command specified")
            sys.exit(1)
        await run_migrations(
            args.migrate_command,
            message=getattr(args, "message", None),
            revision=getattr(args, "revision", None)
        )
    else:
        # Default to monitor command
        skip_catchup = getattr(args, "skip_catchup", False)
        skip_polling = getattr(args, "skip_polling", False)
        await run_monitor(skip_catchup=skip_catchup, skip_polling=skip_polling)


def main_cli() -> None:
    """Entry point for console script"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBC Game Crash Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error running BC Game Crash Monitor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBC Game Crash Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error running BC Game Crash Monitor: {e}")
        sys.exit(1)
