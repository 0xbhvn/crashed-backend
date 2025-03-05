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
    from .api import setup_api_routes
    api_app = web.Application()

    if db:
        # Set up API routes if database is available
        setup_api_routes(api_app, db)

    # Start API server
    # Default to port 3000 if not specified
    api_port = int(os.environ.get('API_PORT', 3000))
    runner = web.AppRunner(api_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', api_port)
    await site.start()
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

    # Register a callback to print new games
    async def log_game(game_data: Dict[str, Any]) -> None:
        """Log new game data when received from the monitor"""
        logger.info(
            f"New crash game detected: Game #{game_data['gameId']} crashed at {game_data['crashPoint']}x " +
            f"(calculated: {game_data.get('calculatedPoint', 'N/A')}x)"
        )

    monitor.register_game_callback(log_game)

    # Run the monitor
    try:
        logger.info("Starting BC Game Crash Monitor...")
        await monitor.run()
    finally:
        # Close database connection if open
        if db_engine:
            db_engine.dispose()
            logger.info("Database connection closed")


async def run_catchup(pages: int = 20, batch_size: int = 20) -> None:
    """
    Run the catchup process to fetch historical game data

    Args:
        pages: Number of pages to fetch
        batch_size: Batch size for concurrent requests
    """
    logger = logging.getLogger("app")
    logger.info(
        f"Starting catchup process with {pages} pages, batch size {batch_size}...")

    db_engine = None
    db = None

    try:
        if config.DATABASE_ENABLED:
            # Initialize database
            from sqlalchemy import create_engine
            db_engine = create_engine(config.DATABASE_URL)
            db = get_database(db_engine)
            logger.info("Database connection established for catchup")

        # Fetch historical data
        total_games = 0

        for page_num in range(1, pages + 1):
            logger.info(f"Fetching page {page_num} of {pages}...")

            # Fetch a batch of games
            games_batch = await fetch_games_batch(
                base_url=config.API_BASE_URL,
                endpoint=config.API_HISTORY_ENDPOINT,
                game_url=config.GAME_URL,
                start_page=page_num,
                end_page=page_num,
                batch_size=batch_size
            )

            if not games_batch:
                logger.warning(
                    f"No games found on page {page_num}, stopping catchup")
                break

            # Store in database if enabled
            if config.DATABASE_ENABLED and db:
                with db.get_session() as session:
                    for game in games_batch:
                        # Check if game already exists
                        existing_game = session.query(CrashGame).filter(
                            CrashGame.gameId == game['gameId']
                        ).first()

                        if not existing_game:
                            # Calculate crash point
                            hash_value = game.get('hashValue')
                            if hash_value:
                                calculated_point = BCCrashMonitor.calculate_crash_point(
                                    seed=hash_value, salt=config.BC_GAME_SALT
                                )
                                game['calculatedPoint'] = calculated_point

                            # Create new game object
                            new_game = CrashGame(**game)
                            session.add(new_game)

                    # Commit all changes
                    session.commit()

            total_games += len(games_batch)
            logger.info(
                f"Processed {len(games_batch)} games from page {page_num}")

        logger.info(
            f"Catchup completed: processed {total_games} games from {pages} pages")

    except Exception as e:
        logger.error(f"Error during catchup process: {e}")
        raise

    finally:
        # Close database connection if open
        if db_engine:
            db_engine.dispose()
            logger.info("Database connection closed")


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
    """Start a simple HTTP server for health checks."""
    app = web.Application()
    app.router.add_get('/', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    # Railway will route to port 8080 by default
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    logger = logging.getLogger("app")
    logger.info("Health check server started on port 8080")


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
