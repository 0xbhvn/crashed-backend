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

    # Run catchup process if enabled
    if not skip_catchup and config.CATCHUP_ENABLED:
        try:
            logger.info("Running catchup process...")
            await run_catchup(pages=config.CATCHUP_PAGES, batch_size=config.CATCHUP_BATCH_SIZE)
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


async def run_catchup(pages: int = 20, batch_size: int = 20) -> None:
    """
    Run the catchup process to fetch historical game data.

    Args:
        pages: Number of pages to fetch
        batch_size: Batch size for concurrent requests
    """
    logger = logging.getLogger("app.catchup")
    logger.info(
        f"Starting catchup with {pages} pages, batch size {batch_size}")

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

    # Fetch data in batches
    for page in range(1, pages + 1, batch_size):
        # Calculate end page for this batch
        end_page = min(page + batch_size - 1, pages)
        pages_in_batch = end_page - page + 1

        logger.info(
            f"Fetching batch {(page-1)//batch_size + 1}/{(pages+batch_size-1)//batch_size}: "
            f"pages {page}-{end_page}"
        )

        # Fetch pages in parallel
        games = await fetch_games_batch(start_page=page, end_page=end_page)

        if not games:
            logger.warning(
                f"No games found in batch (pages {page}-{end_page})")
            continue

        logger.info(f"Fetched {len(games)} games from pages {page}-{end_page}")
        total_fetched += len(games)

        # Skip saving if database is not enabled
        if not config.DATABASE_ENABLED or db is None:
            logger.info(
                f"Database disabled, not saving games (skipped {len(games)} games)")
            total_skipped += len(games)
            continue

        # Save games to database
        saved_count = 0
        failed_count = 0

        for game in games:
            try:
                db.add_crash_game(game)
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save game {game.get('gameId')}: {e}")
                failed_count += 1

        logger.info(
            f"Saved {saved_count}/{len(games)} games from pages {page}-{end_page}")

        if failed_count > 0:
            logger.warning(
                f"Failed to save {failed_count}/{len(games)} games from pages {page}-{end_page}")

        total_saved += saved_count
        total_failed += failed_count

    logger.info(
        f"Catchup completed: Fetched {total_fetched}, "
        f"Saved {total_saved}, Skipped {total_skipped}, Failed {total_failed}"
    )

    # Broadcast games via WebSocket if database is connected
    if config.DATABASE_ENABLED and db is not None:
        try:
            # Get the API app to access the websocket manager
            from aiohttp.web import Application
            import gc
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
        await run_catchup(pages=args.pages, batch_size=args.batch_size)
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
