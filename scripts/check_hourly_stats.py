#!/usr/bin/env python
"""
Script to check hourly stats in the database and verify they are being saved correctly.
"""

from src.models import CrashStats
from src.sqlalchemy_db import Database
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
import pytz
from sqlalchemy import text, func

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    """Check hourly stats in the database."""
    # Connect to the database
    db = Database()
    logger.info("Connected to database")

    session = db.get_session()

    try:
        # Count hourly stats
        total_records = session.query(CrashStats).filter(
            CrashStats.time_range == 'hourly').count()

        # Get min and max dates
        date_range_result = session.query(
            func.min(CrashStats.date),
            func.max(CrashStats.date)
        ).filter(CrashStats.time_range == 'hourly').first()

        min_date, max_date = date_range_result

        # Get all hourly stats
        hourly_stats = session.query(
            CrashStats.id,
            CrashStats.date,
            CrashStats.gamesCount,
            CrashStats.averageCrash,
            CrashStats.medianCrash,
            CrashStats.minCrash,
            CrashStats.maxCrash,
            CrashStats.standardDeviation
        ).filter(CrashStats.time_range == 'hourly').order_by(CrashStats.date).all()

        # Display the hourly stats
        print("\nHourly Stats:")
        print(f"{'ID':<5} {'Date':<20} {'Games':<8} {'Avg':<8} {'Median':<8} {'Min':<8} {'Max':<8} {'StdDev':<8}")
        print("-" * 75)

        for row in hourly_stats:
            id, date, games, avg, median, min_val, max_val, std_dev = row
            print(f"{id:<5} {date.strftime('%Y-%m-%d %H:%M:%S'):<20} {games:<8} {avg:.2f} {median:.2f} {min_val:.2f} {max_val:.2f} {std_dev:.2f}")

        # Check for missing hours in the expected range
        if min_date and max_date:
            start_date = min_date.replace(minute=0, second=0, microsecond=0)
            end_date = max_date.replace(
                minute=0, second=0, microsecond=0) + timedelta(hours=1)

            expected_hours = []
            current = start_date
            while current < end_date:
                expected_hours.append(current)
                current += timedelta(hours=1)

            existing_timestamps = [row[1].replace(
                minute=0, second=0, microsecond=0) for row in hourly_stats]
            missing_hours = [
                hour for hour in expected_hours if hour not in existing_timestamps]

            # Summary
            print(f"\nTotal hourly stats records: {total_records}")
            print(
                f"Date range covered: {min_date.date()} to {max_date.date()}")
            print(f"Expected hours in range: {len(expected_hours)}")
            print(
                f"Missing hours: {len(missing_hours)} out of {len(expected_hours)}")

            if missing_hours:
                print("\nMissing timestamps:")
                for hour in missing_hours:
                    print(f"  {hour.strftime('%Y-%m-%d %H:%M:%S')}")

    finally:
        # Close the session
        session.close()

    # Close the database connection
    db.close()
    logger.info("Database connection closed")


if __name__ == "__main__":
    main()
