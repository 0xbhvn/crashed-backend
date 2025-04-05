"""
Unified entry point for the Crash Monitor application.

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
import math

# Import from local modules
from . import config
from .history import BCCrashMonitor
from .utils import load_env, configure_logging, fetch_game_history, fetch_games_batch
from .db import get_database, CrashGame, create_migration, upgrade_database, downgrade_database, show_migrations
from .utils.env import get_env_var


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Crash Monitor - A tool for monitoring Crash game"
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
    # Add game ID filtering options
    catchup_parser.add_argument(
        "--game-id",
        type=str,
        help="Fetch a specific game ID"
    )
    catchup_parser.add_argument(
        "--start-game-id",
        type=str,
        help="Starting game ID for range (inclusive)"
    )
    catchup_parser.add_argument(
        "--end-game-id",
        type=str,
        help="Ending game ID for range (inclusive)"
    )
    catchup_parser.add_argument(
        "--game-ids",
        type=str,
        help="Comma-separated list of specific game IDs to fetch"
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
    Run the Crash Monitor

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
    dev_mode = get_env_var('ENVIRONMENT', '').lower() == 'development'
    # Use port 8000 for development, 3000 for production
    default_port = '8000' if dev_mode else '3000'
    api_port = int(config.get_env_var('API_PORT', default_port))

    # Create API server
    api_runner = web.AppRunner(api_app)
    await api_runner.setup()
    api_site = web.TCPSite(api_runner, '0.0.0.0', api_port)
    await api_site.start()
    logger.info(
        f"API server started on port {api_port}" + (" (development mode)" if dev_mode else ""))

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

    # Run catchup process if enabled AND not skipping
    if not skip_catchup and config.CATCHUP_ENABLED:
        try:
            logger.info("Running initial catchup process...")
            await run_catchup(
                pages=config.CATCHUP_PAGES,
                batch_size=config.CATCHUP_BATCH_SIZE
            )
            logger.info("Initial catchup process completed")
        except Exception as e:
            logger.error(f"Error during initial catchup process: {e}")
            logger.warning("Continuing with monitor despite catchup failure")

    # Register callback for new games
    async def log_game(game_data: Dict[str, Any]) -> None:
        """Log new games and broadcast via WebSocket."""
        # Add diagnostic logging for Cloudflare block state
        logger.info(
            f"Processing game {game_data.get('gameId')}, cloudflare_block_active: {monitor.cloudflare_block_active}")

        # Convert crashPoint to float for logging
        crash_point = float(game_data.get('crashPoint', 0))
        game_id = game_data.get('gameId', None)

        if not game_id:
            logger.error(
                "Received game data without a gameId, cannot process or update state.")
            return  # Cannot proceed without a game ID

        logger.info(f"New game: {game_id} with crash point: {crash_point}")

        # --- Reactive Catchup Logic ---
        if monitor.cloudflare_block_active:
            try:
                logger.info(
                    f"Detected recovery from Cloudflare block with game {game_id}.")
                monitor.cloudflare_block_active = False  # Reset the flag

                if monitor.last_processed_game_id:
                    try:
                        start_id = int(monitor.last_processed_game_id) + 1
                        end_id = int(game_id) - 1

                        logger.info(
                            f"Calculated catchup range: {start_id} to {end_id}")

                        if start_id <= end_id:
                            num_missing = end_id - start_id + 1
                            # Calculate pages needed: ceiling of num_missing/10, add 1 buffer, cap at 200
                            pages_needed = min(
                                200, max(1, math.ceil(num_missing / 10) + 1))
                            batch_size_catchup = 100  # As requested

                            logger.info(
                                f"Launching targeted catchup for missing games: {start_id} to {end_id} ({num_missing} games). Will fetch {pages_needed} pages with batch size {batch_size_catchup}.")

                            # Launch catchup in the background
                            catchup_task = asyncio.create_task(run_catchup(
                                pages=pages_needed,
                                batch_size=batch_size_catchup,  # Use specific batch size for catchup
                                start_game_id=str(start_id),
                                end_game_id=str(end_id)
                            ))

                            # Add a callback to log when the catchup completes
                            def catchup_done(task):
                                try:
                                    task.result()  # Get the result or exception
                                    logger.info(
                                        f"Catchup for games {start_id}-{end_id} completed successfully")
                                except Exception as e:
                                    logger.error(
                                        f"Catchup for games {start_id}-{end_id} failed: {e}")

                            catchup_task.add_done_callback(catchup_done)
                        else:
                            logger.info(
                                f"No missing games detected between {monitor.last_processed_game_id} and {game_id}.")

                    except ValueError:
                        logger.error(
                            f"Could not convert game IDs ({monitor.last_processed_game_id}, {game_id}) to integers for catchup calculation.")
                    except Exception as e:
                        logger.error(
                            f"Error calculating or launching targeted catchup: {e}")
                else:
                    logger.warning(
                        "Cloudflare block was active, but last_processed_game_id is not set. Skipping targeted catchup.")
            except Exception as e:
                logger.error(f"ERROR in reactive catchup logic: {e}")
                # Still reset the flag even if there's an error
                monitor.cloudflare_block_active = False
        # --- End Reactive Catchup Logic ---

        # Always update the last processed ID after processing a successful game
        monitor.last_processed_game_id = game_id

        try:
            # Broadcast the new game to WebSocket clients if we have a WebSocket manager
            if 'websocket_manager' in api_app:
                await api_app['websocket_manager'].broadcast_new_game(game_data)
        except Exception as e:
            logger.error(f"Error broadcasting game via WebSocket: {e}")

    # Register the callback with the monitor
    monitor.register_game_callback(log_game)

    # Start the monitor (run forever)
    logger.info("Starting Crash Monitor")
    await monitor.run()

    # Cleanup on exit
    await api_runner.cleanup()
    logger.info("Crash Monitor stopped")


async def run_catchup(pages: int = 20, batch_size: int = 20,
                      game_id: str = None, start_game_id: str = None,
                      end_game_id: str = None, game_ids: str = None) -> None:
    """
    Run the catchup process to fetch historical game data.

    Args:
        pages: Number of pages to fetch
        batch_size: Batch size for concurrent requests
        game_id: A specific game ID to fetch
        start_game_id: Starting game ID for range (inclusive)
        end_game_id: Ending game ID for range (inclusive)
        game_ids: Comma-separated list of specific game IDs to fetch
    """
    logger = logging.getLogger("app.catchup")
    logger.info(
        f"Starting catchup with {pages} pages, batch size {batch_size}")

    # Log filtering options if provided
    if game_id:
        logger.info(f"Will only process specific game ID: {game_id}")
    if start_game_id:
        logger.info(f"Will only process games with ID >= {start_game_id}")
    if end_game_id:
        logger.info(f"Will only process games with ID <= {end_game_id}")
    if game_ids:
        game_id_list = [gid.strip() for gid in game_ids.split(',')]
        logger.info(f"Will only process specific game IDs: {game_id_list}")

    # Prepare game IDs list for filtering
    target_game_ids = None
    if game_ids:
        target_game_ids = [gid.strip() for gid in game_ids.split(',')]
    elif game_id:
        target_game_ids = [game_id]

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

    # Set up counters
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

        # Filter games based on criteria
        filtered_games = []
        for game in games:
            game_id_val = str(game.get('gameId', ''))

            # Skip if not in specific IDs list
            if target_game_ids and game_id_val not in target_game_ids:
                continue

            # Skip if game ID is less than start_game_id
            if start_game_id and game_id_val < start_game_id:
                continue

            # Skip if game ID is greater than end_game_id
            if end_game_id and game_id_val > end_game_id:
                continue

            filtered_games.append(game)

        skipped_count = len(games) - len(filtered_games)
        if skipped_count > 0:
            logger.info(
                f"Skipped {skipped_count} games that didn't match the filtering criteria")

        games = filtered_games
        if not games:
            logger.warning(
                f"No games matching criteria found in batch (pages {page}-{end_page})")
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
                # Calculate crash point if hash value is available and calculated point is not set
                if 'hashValue' in game and ('calculatedPoint' not in game or game['calculatedPoint'] is None):
                    hash_value = game['hashValue']
                    calculated_crash = BCCrashMonitor.calculate_crash_point(
                        seed=hash_value)
                    game['calculatedPoint'] = calculated_crash
                    logger.debug(
                        f"Calculated crash point for game {game.get('gameId')}: {calculated_crash}")

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

        # Early exit if we found all specific game IDs
        if target_game_ids and len(target_game_ids) == saved_count:
            logger.info(f"Found all specified game IDs, stopping catchup")
            break

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
                        'crashPoint': float(game.crashPoint) if game.crashPoint is not None else None,
                        'calculatedPoint': float(game.calculatedPoint) if game.calculatedPoint is not None else None,
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
        await run_catchup(
            pages=args.pages,
            batch_size=args.batch_size,
            game_id=args.game_id if hasattr(args, 'game_id') else None,
            start_game_id=args.start_game_id if hasattr(
                args, 'start_game_id') else None,
            end_game_id=args.end_game_id if hasattr(
                args, 'end_game_id') else None,
            game_ids=args.game_ids if hasattr(args, 'game_ids') else None
        )
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
        print("\nCrash Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error running Crash Monitor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCrash Monitor stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error running Crash Monitor: {e}")
        sys.exit(1)
