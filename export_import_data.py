#!/usr/bin/env python
"""
Script to export data from local database and import it to production database.

Usage:
1. Export data: python export_import_data.py export
2. Import data: python export_import_data.py import
"""

from src.utils import load_env
from src import config
from src.db.models import CrashGame
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import argparse
import json
import sys
import os
from datetime import datetime
import pytz

# Add parent directory to sys.path
sys.path.insert(0, '.')


# Load environment variables
load_env()

# Remove module level timezone definition
# app_timezone = pytz.timezone(config.TIMEZONE)


def serialize_datetime(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def export_data(output_file='crash_games_export.json'):
    """Export data from local database to JSON file"""
    from src.db.engine import get_database

    print(f"Exporting data from local database ({config.DATABASE_URL})...")

    # Get database and session
    db = get_database()

    # Query all crash games
    session = db.get_session()
    try:
        games = session.query(CrashGame).all()
        print(f"Found {len(games)} games to export")

        # Convert to dictionaries
        games_data = [game.to_dict() for game in games]

        # Save to JSON file
        with open(output_file, 'w') as f:
            json.dump(games_data, f, default=serialize_datetime, indent=2)

        print(f"Data exported to {output_file}")
    finally:
        session.close()


def import_data(input_file='crash_games_export.json', target_db_url=None):
    """Import data from JSON file to target database"""
    target_db_url = target_db_url or config.DATABASE_URL
    print(f"Importing data to target database...")

    # Load data from JSON file
    try:
        with open(input_file, 'r') as f:
            games_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File {input_file} not found. Run export first.")
        sys.exit(1)

    # Connect to target database
    engine = create_engine(target_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if target table exists
        conn = engine.connect()
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'crash_games')"))
        table_exists = result.scalar()
        conn.close()

        if not table_exists:
            print(
                "ERROR: crash_games table doesn't exist in target database. Run migrations first.")
            sys.exit(1)

        # Import data
        print(f"Importing {len(games_data)} games...")

        # Clear existing data if requested
        if input("Do you want to clear existing data in the target database? (y/n): ").lower() == 'y':
            session.execute(text("DELETE FROM crash_games"))
            session.commit()
            print("Existing data cleared.")

        # Insert data
        count = 0
        for game_data in games_data:
            # Get the timezone inside the function to avoid circular imports
            app_timezone = pytz.timezone(config.TIMEZONE)

            # Convert string ISO dates back to datetime objects
            for date_field in ['endTime', 'prepareTime', 'beginTime']:
                if game_data.get(date_field) and isinstance(game_data[date_field], str):
                    # Parse the ISO format string and set the timezone
                    naive_dt = datetime.fromisoformat(game_data[date_field])
                    # If the datetime doesn't have tzinfo, add the configured timezone
                    if naive_dt.tzinfo is None:
                        game_data[date_field] = app_timezone.localize(naive_dt)
                    else:
                        game_data[date_field] = naive_dt

            # Check if game already exists
            existing = session.query(CrashGame).filter(
                CrashGame.gameId == game_data['gameId']).first()

            if existing:
                print(f"Game {game_data['gameId']} already exists, skipping")
                continue

            # Create new game instance
            game = CrashGame(**game_data)
            session.add(game)
            count += 1

            # Commit in batches of 100
            if count % 100 == 0:
                session.commit()
                print(f"Imported {count} games...")

        # Final commit
        session.commit()
        print(f"Successfully imported {count} games to target database")

    except Exception as e:
        session.rollback()
        print(f"ERROR during import: {str(e)}")
        raise
    finally:
        session.close()


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Export/Import BC Game crash data')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Export command
    export_parser = subparsers.add_parser(
        'export', help='Export data from database')
    export_parser.add_argument('--output', help='Output file path',
                               default='crash_games_export.json')

    # Import command
    import_parser = subparsers.add_parser(
        'import', help='Import data to database')
    import_parser.add_argument('--input', help='Input file path',
                               default='crash_games_export.json')
    import_parser.add_argument('--target-db', help='Target database URL',
                               default=os.environ.get('RAILWAY_DATABASE_URL', config.DATABASE_URL))

    args = parser.parse_args()

    if args.command == 'export':
        export_data(args.output)
    elif args.command == 'import':
        import_data(args.input, args.target_db)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
