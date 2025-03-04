#!/usr/bin/env python3
"""
Script to check crash distributions in the database and verify they are being saved correctly.
"""

from src.sqlalchemy_db import Database
from src.models import CrashStats, CrashDistribution
import sys
import os
import logging
from sqlalchemy import desc

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    """Check crash distributions in the database."""
    try:
        # Connect to the database
        db = Database()
        logger.debug("Connected to database")

        session = db.get_session()

        try:
            # Check daily crash distributions
            print("Checking daily crash distributions:")
            daily_distributions = session.query(
                CrashStats.id,
                CrashStats.date,
                CrashStats.time_range,
                CrashDistribution.threshold,
                CrashDistribution.count
            ).join(
                CrashDistribution, CrashStats.id == CrashDistribution.stats_id
            ).filter(
                CrashStats.time_range == 'daily'
            ).order_by(
                desc(CrashStats.date),
                CrashDistribution.threshold
            ).limit(30).all()

            # Display the daily distributions
            if daily_distributions:
                print(
                    f"Found {len(daily_distributions)} daily distribution records")
                for row in daily_distributions:
                    print(row)
            else:
                print("No daily distribution records found")

            # Check hourly crash distributions
            print("\nChecking hourly crash distributions:")
            hourly_distributions = session.query(
                CrashStats.id,
                CrashStats.date,
                CrashStats.time_range,
                CrashDistribution.threshold,
                CrashDistribution.count
            ).join(
                CrashDistribution, CrashStats.id == CrashDistribution.stats_id
            ).filter(
                CrashStats.time_range == 'hourly'
            ).order_by(
                desc(CrashStats.date),
                CrashDistribution.threshold
            ).limit(30).all()

            # Display the hourly distributions
            if hourly_distributions:
                print(
                    f"Found {len(hourly_distributions)} hourly distribution records")
                for row in hourly_distributions:
                    print(row)
            else:
                print("No hourly distribution records found")

        finally:
            # Close the session
            session.close()

        # Close the database connection
        db.close()
        logger.debug("Database connection closed")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
