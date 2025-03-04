#!/usr/bin/env python
"""
Fill Hourly Stats Script.

This script backfills hourly statistics for a specified date range.
It ensures that hourly stats are created for all hours in the range,
even for hours that might not have any games.
"""

from src.sqlalchemy_db import Database
from src.models import CrashGame, CrashStats
import os
import sys
import logging
import argparse
import asyncio
from datetime import datetime, timedelta
import statistics
from sqlalchemy import func, and_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)


async def fill_hourly_stats_for_date_range(start_date, end_date, db, force=False):
    """
    Fill hourly stats for all dates in the given range.

    Args:
        start_date: The start date (inclusive)
        end_date: The end date (inclusive)
        db: Database instance
        force: Whether to force update existing stats
    """
    current_date = start_date
    total_updates = 0
    total_hours_processed = 0
    total_hours_with_data = 0

    while current_date <= end_date:
        logger.info(f"Processing date: {current_date.strftime('%Y-%m-%d')}")
        updates = await fill_hourly_stats_for_date(current_date, db, force)
        total_updates += updates['hours_with_data']
        total_hours_processed += 24
        total_hours_with_data += updates['hours_with_data']
        current_date += timedelta(days=1)

    logger.info(f"Completed backfill of hourly stats:")
    logger.info(
        f"- Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"- Total hours processed: {total_hours_processed}")
    logger.info(f"- Hours with data: {total_hours_with_data}")
    logger.info(
        f"- Empty hours: {total_hours_processed - total_hours_with_data}")


async def fill_hourly_stats_for_date(date, db, force=False):
    """
    Fill hourly stats for a specific date.

    Args:
        date: The date to process
        db: Database instance
        force: Whether to force update existing stats

    Returns:
        Dict with stats about the update operation
    """
    logger.info(f"Filling hourly stats for date: {date.strftime('%Y-%m-%d')}")

    # Create properly formatted datetime objects for the day
    if isinstance(date, datetime):
        date_obj = date
    else:
        date_obj = datetime(date.year, date.month, date.day, 0, 0, 0)

    start_of_day = datetime(
        date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
    end_of_day = start_of_day + timedelta(days=1)

    hours_with_data = 0

    # Get session from the database
    session = db.get_session()
    try:
        # Process each hour of the day
        for hour in range(24):
            hour_start = start_of_day + timedelta(hours=hour)
            hour_end = hour_start + timedelta(hours=1)

            # Fetch games for this hour with specific query
            try:
                games = session.query(CrashGame).filter(
                    CrashGame.beginTime.isnot(None),
                    CrashGame.beginTime >= hour_start,
                    CrashGame.beginTime < hour_end
                ).all()

                logger.debug(
                    f"Found {len(games)} games for hour starting at {hour_start.strftime('%Y-%m-%d %H:00')}")

                if games:
                    # Calculate stats
                    crash_points = [game.crashPoint for game in games]
                    games_count = len(crash_points)
                    average_crash = sum(crash_points) / games_count
                    median_crash = statistics.median(crash_points)
                    max_crash = max(crash_points)
                    min_crash = min(crash_points)
                    std_dev = statistics.stdev(
                        crash_points) if games_count > 1 else 0

                    # Check if hourly stats already exist for this exact hour
                    existing_stats = session.query(CrashStats).filter(
                        and_(
                            func.date_trunc('hour', CrashStats.date) == func.date_trunc(
                                'hour', hour_start),
                            CrashStats.time_range == 'hourly'
                        )
                    ).first()

                    if existing_stats and not force:
                        logger.debug(
                            f"  Hourly stats already exist for {hour_start.strftime('%Y-%m-%d %H:00')}")
                    else:
                        if existing_stats:
                            # Update existing stats
                            existing_stats.gamesCount = games_count
                            existing_stats.averageCrash = average_crash
                            existing_stats.medianCrash = median_crash
                            existing_stats.maxCrash = max_crash
                            existing_stats.minCrash = min_crash
                            existing_stats.standardDeviation = std_dev
                            existing_stats.updatedAt = datetime.now()
                            logger.info(
                                f"  Updated hourly stats for {hour_start.strftime('%Y-%m-%d %H:00')}: {games_count} games, avg={average_crash:.2f}x")
                        else:
                            # Create new stats
                            new_stats = CrashStats(
                                date=hour_start,
                                time_range='hourly',
                                gamesCount=games_count,
                                averageCrash=average_crash,
                                medianCrash=median_crash,
                                maxCrash=max_crash,
                                minCrash=min_crash,
                                standardDeviation=std_dev
                            )
                            session.add(new_stats)
                            logger.info(
                                f"  Created hourly stats for {hour_start.strftime('%Y-%m-%d %H:00')}: {games_count} games, avg={average_crash:.2f}x")

                        # Commit the changes
                        session.commit()

                        # Verify the stats were saved
                        saved_stats = session.query(CrashStats).filter(
                            and_(
                                func.date_trunc('hour', CrashStats.date) == func.date_trunc(
                                    'hour', hour_start),
                                CrashStats.time_range == 'hourly'
                            )
                        ).first()

                        if saved_stats:
                            logger.debug(
                                f"  Verified stats saved: {saved_stats.gamesCount} games")
                        else:
                            logger.warning(
                                f"  Failed to save stats for {hour_start.strftime('%Y-%m-%d %H:00')}")

                    hours_with_data += 1
                else:
                    logger.debug(
                        f"  No games found for hour starting at {hour_start.strftime('%Y-%m-%d %H:00')}")
            except Exception as e:
                logger.error(
                    f"Error processing hour {hour_start.strftime('%Y-%m-%d %H:00')}: {str(e)}")
                session.rollback()
    finally:
        session.close()

    return {
        "date": date_obj.strftime('%Y-%m-%d'),
        "hours_with_data": hours_with_data
    }


async def main():
    """Command-line entry point for filling hourly stats."""
    parser = argparse.ArgumentParser(
        description='BC Game Hourly Stats Backfill Utility')
    parser.add_argument('--start-date', type=str, required=True,
                        help='Start date (inclusive) in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str,
                        help='End date (inclusive) in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--database-url', type=str,
                        help='Database connection URL (defaults to DATABASE_URL env var)')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose (debug) logging')
    parser.add_argument('--force', action='store_true',
                        help='Force update of stats even if they already exist')

    args = parser.parse_args()

    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')

        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        else:
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        sys.exit(1)

    # Validate dates
    if start_date > end_date:
        logger.error(
            f"Start date ({args.start_date}) must be before or equal to end date ({args.end_date})")
        sys.exit(1)

    # Get database URL
    database_url = args.database_url or os.environ.get('DATABASE_URL')
    if not database_url:
        logger.warning(
            "DATABASE_URL not set. Using default connection string.")
        database_url = "postgresql://postgres:postgres@localhost:5432/bc_crash_db"

    # Create database instance
    db = Database(database_url)

    try:
        logger.info(
            f"Starting hourly stats backfill from {args.start_date} to {args.end_date or 'today'}")
        await fill_hourly_stats_for_date_range(start_date, end_date, db, args.force)
        logger.info("Hourly stats backfill completed successfully")
    except Exception as e:
        logger.error(f"Error during hourly stats backfill: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
