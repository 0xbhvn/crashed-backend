#!/usr/bin/env python3
"""
Backfill Crash Point Distributions

This script calculates and stores crash point distributions for existing crash stats.
It processes both daily and hourly stats, counting how many games have crash points
at various thresholds (1x, 2x, 3x, etc.) for each time period.
"""

from sqlalchemy import func, desc
from src.models import CrashGame, CrashStats, CrashDistribution
from src.sqlalchemy_db import Database
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any
import statistics
import time

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to the Python path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)


# Define the thresholds to track
THRESHOLDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20,
              30, 40, 50, 75, 100, 150, 200, 250, 500, 750, 1000]


def calculate_distributions_for_stats(db, stats_id, date, time_range):
    """Calculate crash point distributions for a specific stats record."""
    logger.info(
        f"Calculating distributions for stats_id {stats_id} ({date}, {time_range})")

    session = db.get_session()
    distributions = {threshold: 0 for threshold in THRESHOLDS}

    try:
        # Determine the time range filter based on time_range
        if time_range == 'hourly':
            # For hourly stats, filter by the specific hour
            start_time = date
            end_time = date + timedelta(hours=1)
        else:
            # For daily stats, filter by the entire day
            start_time = date.replace(
                hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)

        # Query games in this time period
        games = session.query(CrashGame).filter(
            CrashGame.beginTime >= start_time,
            CrashGame.beginTime < end_time
        ).all()

        if not games:
            logger.warning(f"No games found for period: {date}, {time_range}")
            return distributions

        logger.info(
            f"Processing {len(games)} games for period: {date}, {time_range}")

        # Count games at each threshold
        for game in games:
            crash_point = game.crashPoint

            # Update counts for all thresholds that this game reached or exceeded
            for threshold in THRESHOLDS:
                if crash_point >= threshold:
                    distributions[threshold] += 1

        # Log summary of distributions
        for threshold in THRESHOLDS:
            if distributions[threshold] > 0:
                logger.info(
                    f"  {threshold}x: {distributions[threshold]} games")

        return distributions

    except Exception as e:
        logger.error(f"Error calculating distributions: {str(e)}")
        return distributions
    finally:
        session.close()


def backfill_crash_distributions(db, time_range=None, start_date=None, end_date=None, force=False):
    """Backfill crash point distributions for existing stats."""
    session = db.get_session()

    try:
        # Build query for stats to process
        query = session.query(CrashStats)

        # Filter by time_range if specified
        if time_range:
            query = query.filter(CrashStats.time_range == time_range)

        # Filter by date range if specified
        if start_date:
            query = query.filter(CrashStats.date >= start_date)
        if end_date:
            query = query.filter(CrashStats.date <= end_date)

        # Order by date (oldest first)
        query = query.order_by(CrashStats.date)

        # Get all matching stats
        stats_list = query.all()

        if not stats_list:
            logger.warning("No matching stats records found")
            return 0

        logger.info(f"Found {len(stats_list)} stats records to process")

        # Process each stats record
        processed_count = 0
        for stats in stats_list:
            # Check if distributions already exist for this stats record
            existing_distributions = session.query(CrashDistribution).filter(
                CrashDistribution.stats_id == stats.id
            ).count()

            if existing_distributions > 0 and not force:
                logger.info(
                    f"Skipping stats_id {stats.id} ({stats.date}, {stats.time_range}) - distributions already exist")
                continue

            # Calculate distributions for this stats record
            distributions = calculate_distributions_for_stats(
                db, stats.id, stats.date, stats.time_range)

            # Update distributions in the database
            db.update_crash_distributions(stats.id, distributions)

            processed_count += 1
            logger.info(
                f"Processed {processed_count}/{len(stats_list)} stats records")

        return processed_count

    except Exception as e:
        logger.error(f"Error in backfill process: {str(e)}")
        return 0
    finally:
        session.close()


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description='Backfill crash point distributions for existing stats')
    parser.add_argument('--time-range', choices=['daily', 'hourly'],
                        help='Process only stats with this time range')
    parser.add_argument('--start-date', type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
                        help='Process stats from this date (format: YYYY-MM-DD)')
    parser.add_argument('--end-date', type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
                        help='Process stats until this date (format: YYYY-MM-DD)')
    parser.add_argument('--force', action='store_true',
                        help='Force update even if distributions already exist')
    args = parser.parse_args()

    try:
        # Initialize database
        logger.info("Connecting to database...")
        db = Database()

        # Start timing
        start_time = time.time()

        # Run backfill process
        processed_count = backfill_crash_distributions(
            db,
            time_range=args.time_range,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force
        )

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        logger.info(
            f"Backfill completed. Processed {processed_count} stats records in {elapsed_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Backfill process failed: {str(e)}")
        sys.exit(1)
    finally:
        db.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    main()
