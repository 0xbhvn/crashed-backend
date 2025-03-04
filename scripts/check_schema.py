#!/usr/bin/env python
"""
Check the database schema for the crash_stats table.
"""

from sqlalchemy import text
from src.sqlalchemy_db import Database
import os
import sys
import logging

# Add the project root directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)


def main():
    """Check database schema for the crash_stats table."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    db = Database()

    try:
        with db.get_session() as session:
            # Query table columns
            result = session.execute(
                text(
                    'SELECT column_name FROM information_schema.columns WHERE table_name = :table_name'),
                {'table_name': 'crash_stats'}
            )

            columns = [row[0] for row in result]

            print("Columns in the crash_stats table:")
            print("-" * 30)
            for col in columns:
                print(f"- {col}")

            # Check for hourly records
            print("\nChecking for hourly records:")
            print("-" * 30)
            result = session.execute(
                text('SELECT COUNT(*) FROM crash_stats WHERE time_range = :time_range'),
                {'time_range': 'hourly'}
            )
            count = result.scalar()
            print(f"Number of hourly records: {count}")

            # Show sample hourly records if they exist
            if count > 0:
                print("\nSample hourly records:")
                print("-" * 30)
                result = session.execute(
                    text(
                        'SELECT * FROM crash_stats WHERE time_range = :time_range ORDER BY date DESC LIMIT 5'),
                    {'time_range': 'hourly'}
                )

                rows = result.fetchall()
                for row in rows:
                    print(row)

    finally:
        # Close the database connection
        db.close()
        logging.info("Database connection closed")


if __name__ == "__main__":
    main()
