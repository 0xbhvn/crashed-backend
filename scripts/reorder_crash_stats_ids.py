#!/usr/bin/env python3

"""
One-time script to reorder the IDs in crash_stats table based on chronological order.
The oldest record will have ID 1 and incrementing from there.
"""

import os
import sys
import logging
import argparse
from sqlalchemy import text
from src.sqlalchemy_db import Database

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def reorder_crash_stats_ids(dry_run=False):
    """
    Reorder the IDs in crash_stats table based on date column.
    Oldest record will have ID 1, incrementing from there.

    Args:
        dry_run (bool): If True, show what would be done without making changes
    """
    db = Database()
    session = db.get_session()

    try:
        logger.info("Getting current record count...")
        count_result = session.execute(
            text("SELECT COUNT(*) FROM crash_stats"))
        total_records = count_result.scalar()
        logger.info(f"Found {total_records} records in crash_stats table")

        if dry_run:
            logger.info(
                "DRY RUN: Showing what would be updated without making changes")

            # Get records ordered by date
            results = session.execute(
                text(
                    "SELECT id, date, time_range FROM crash_stats ORDER BY date ASC LIMIT 10")
            )
            sample = results.fetchall()

            logger.info(
                "Sample of the first 10 records that would be reordered:")
            logger.info("Current ID | New ID | Date | Time Range")
            logger.info("-" * 60)

            for i, row in enumerate(sample):
                logger.info(f"{row[0]:10} | {i+1:6} | {row[1]} | {row[2]}")

            logger.info(
                "\nTo execute the actual update, run without --dry-run flag")
            return

        # Create a temporary table with the same structure
        logger.info("Creating temporary table...")
        session.execute(text("""
            CREATE TABLE crash_stats_reordered (
                id SERIAL PRIMARY KEY,
                date TIMESTAMP WITH TIME ZONE NOT NULL,
                games_count INTEGER NOT NULL,
                average_crash FLOAT NOT NULL,
                median_crash FLOAT NOT NULL,
                min_crash FLOAT NOT NULL,
                max_crash FLOAT NOT NULL,
                standard_deviation FLOAT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                time_range VARCHAR(10) DEFAULT 'daily' NOT NULL
            )
        """))

        # Insert records in order by date
        logger.info("Copying data to temporary table with new IDs...")
        result = session.execute(text("""
            INSERT INTO crash_stats_reordered 
            (date, games_count, average_crash, median_crash, min_crash, max_crash, standard_deviation, created_at, updated_at, time_range)
            SELECT date, games_count, average_crash, median_crash, min_crash, max_crash, standard_deviation, created_at, updated_at, time_range
            FROM crash_stats
            ORDER BY date ASC
        """))

        session.commit()
        logger.info(f"Copied {result.rowcount} records with reordered IDs")

        # Verify row count matches before swapping tables
        verify_count = session.execute(
            text("SELECT COUNT(*) FROM crash_stats_reordered")).scalar()
        if verify_count != total_records:
            raise ValueError(
                f"Record count mismatch: original={total_records}, reordered={verify_count}")

        # Swap tables
        logger.info("Swapping tables...")
        session.execute(text("DROP TABLE crash_stats"))
        session.execute(
            text("ALTER TABLE crash_stats_reordered RENAME TO crash_stats"))
        session.commit()

        logger.info("Success! crash_stats table has been reordered by date.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error reordering crash_stats IDs: {str(e)}")
        if not dry_run:
            logger.error(
                "The database may be in an inconsistent state. Please check and restore if needed.")
        raise
    finally:
        session.close()
        db.close()
        logger.info("Database connection closed")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description='Reorder crash_stats table IDs by date (oldest = ID 1)'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be updated without making changes')

    args = parser.parse_args()

    try:
        reorder_crash_stats_ids(dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
