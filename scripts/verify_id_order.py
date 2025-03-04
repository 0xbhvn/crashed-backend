#!/usr/bin/env python3

"""
Simple script to verify the ordering of IDs in the crash_stats table.
"""

import logging
from sqlalchemy import text
from src.sqlalchemy_db import Database

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Check the ordering of IDs in the crash_stats table."""
    db = Database()
    session = db.get_session()

    try:
        # Query the first 10 records to see their IDs
        logger.info("First 10 records ordered by ID:")
        logger.info("ID | Date | Time Range")
        logger.info("-" * 50)

        result = session.execute(
            text("SELECT id, date, time_range FROM crash_stats ORDER BY id ASC LIMIT 10")
        )

        for row in result:
            logger.info(f"{row[0]:2} | {row[1]} | {row[2]}")

        # Verify that IDs match chronological order
        logger.info("\nChecking if IDs match chronological order:")
        result = session.execute(
            text("""
                WITH ordered_dates AS (
                    SELECT id, date, time_range, 
                           ROW_NUMBER() OVER (ORDER BY date ASC) as expected_id
                    FROM crash_stats
                )
                SELECT COUNT(*) FROM ordered_dates WHERE id != expected_id
            """)
        )

        mismatch_count = result.scalar()
        if mismatch_count == 0:
            logger.info("✅ SUCCESS: All IDs match chronological order!")
        else:
            logger.warning(
                f"❌ FAILURE: Found {mismatch_count} IDs that don't match chronological order")

            # Show the mismatched records
            logger.info("\nMismatched records (current ID != expected ID):")
            logger.info("Current ID | Expected ID | Date | Time Range")
            logger.info("-" * 65)

            result = session.execute(
                text("""
                    WITH ordered_dates AS (
                        SELECT id, date, time_range, 
                               ROW_NUMBER() OVER (ORDER BY date ASC) as expected_id
                        FROM crash_stats
                    )
                    SELECT id, expected_id, date, time_range 
                    FROM ordered_dates 
                    WHERE id != expected_id
                    ORDER BY date ASC
                """)
            )

            for row in result:
                logger.info(f"{row[0]:10} | {row[1]:11} | {row[2]} | {row[3]}")

    finally:
        session.close()
        db.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    main()
