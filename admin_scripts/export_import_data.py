#!/usr/bin/env python
"""
Script to export data from local database and import it to production database.

Usage:
1. Export data: python export_import_data.py export
2. Import data: python export_import_data.py import
3. Direct transfer from production to local: python export_import_data.py transfer
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
from urllib.parse import urlparse, urlunparse

# Add parent directory to sys.path
sys.path.insert(0, '.')


# Load environment variables
load_env()

# Remove module level timezone definition
# app_timezone = pytz.timezone(config.TIMEZONE)


def transfer_data(source_db_url=None, target_db_url=None, clear_target=False, batch_size=100, limit=None, db_username=None, db_password=None):
    """Transfer data directly from source database to target database"""
    # Default to production to local transfer
    source_db_url = source_db_url or os.environ.get('RAILWAY_DATABASE_URL', '')

    # If target_db_url is the default and username/password are provided, construct the URL with credentials
    if not target_db_url or target_db_url == config.DATABASE_URL:
        if db_username or db_password:
            # Parse the existing DATABASE_URL to modify it
            parsed = urlparse(config.DATABASE_URL)
            userpass = ""
            if db_username:
                userpass = db_username
                if db_password:
                    userpass += f":{db_password}"
                userpass += "@"
            # Reconstruct the URL with the new credentials
            # Remove existing user:pass if any
            netloc = parsed.netloc.split("@")[-1]
            netloc = f"{userpass}{netloc}"
            target_db_url = urlunparse((parsed.scheme, netloc, parsed.path,
                                       parsed.params, parsed.query, parsed.fragment))
        else:
            target_db_url = config.DATABASE_URL

    if not source_db_url:
        print("ERROR: Source database URL not provided and RAILWAY_DATABASE_URL not found in environment.")
        sys.exit(1)

    print(
        f"Transferring data from source database to target database ({target_db_url})...")

    # Connect to source database
    source_engine = create_engine(source_db_url)
    SourceSession = sessionmaker(bind=source_engine)
    source_session = SourceSession()

    # Connect to target database
    target_engine = create_engine(target_db_url)
    TargetSession = sessionmaker(bind=target_engine)
    target_session = TargetSession()

    try:
        # Check if target table exists
        conn = target_engine.connect()
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'crash_games')"))
        table_exists = result.scalar()
        conn.close()

        if not table_exists:
            print(
                "ERROR: crash_games table doesn't exist in target database. Run migrations first.")
            sys.exit(1)

        # Build base query
        source_query = source_session.query(CrashGame)

        # Get total count from source
        if limit:
            # If limit is specified, get only the latest records
            print(
                f"Will transfer only the latest {limit} games from source database")
            total_games = source_session.query(CrashGame).count()
            source_count = min(total_games, limit)
            # We'll apply the limit and ordering in the batch query
        else:
            source_count = source_session.query(CrashGame).count()

        print(f"Found {source_count} games in source database" + (" (total: " +
              str(source_session.query(CrashGame).count()) + ")" if limit else ""))

        # Clear existing data if requested
        if clear_target:
            confirm = input(
                "Are you sure you want to DELETE ALL DATA from your local database? (type 'yes' to confirm): ")
            if confirm.lower() == 'yes':
                target_session.execute(text("DELETE FROM crash_games"))
                target_session.commit()
                print("Target database cleared.")
            else:
                print("Database clear cancelled.")
                sys.exit(1)

        # Get existing game IDs in target to avoid duplicates
        print("Fetching existing game IDs from target database (this may take a moment)...")
        existing_ids = set()
        for game_id, in target_session.query(CrashGame.gameId).all():
            existing_ids.add(game_id)
        print(f"Found {len(existing_ids)} existing games in target database.")

        # Transfer data in batches
        offset = 0
        processed = 0
        added = 0
        skipped = 0

        app_timezone = pytz.timezone(config.TIMEZONE)

        while offset < source_count:
            # Get batch from source - order by gameId descending if limit is specified
            if limit:
                source_games = source_session.query(CrashGame).order_by(CrashGame.gameId.desc(
                )).offset(offset).limit(min(batch_size, limit-processed)).all()
            else:
                source_games = source_session.query(CrashGame).order_by(
                    CrashGame.gameId).offset(offset).limit(batch_size).all()

            if not source_games:
                break

            batch_size_actual = len(source_games)
            batch_added = 0

            # Process each game
            for source_game in source_games:
                processed += 1

                # Skip if already exists
                if source_game.gameId in existing_ids:
                    skipped += 1
                    continue

                # Convert to dict
                game_data = source_game.to_dict()

                # Ensure proper timezone info
                for date_field in ['endTime', 'prepareTime', 'beginTime']:
                    if game_data.get(date_field):
                        if isinstance(game_data[date_field], datetime):
                            # If the datetime doesn't have tzinfo, add the configured timezone
                            if game_data[date_field].tzinfo is None:
                                game_data[date_field] = app_timezone.localize(
                                    game_data[date_field])

                # Create new game in target
                target_game = CrashGame(**game_data)
                target_session.add(target_game)
                added += 1
                batch_added += 1
                # Update local cache to avoid future duplicates
                existing_ids.add(source_game.gameId)

            # Commit batch
            target_session.commit()
            print(
                f"Transferred {batch_added}/{batch_size_actual} games (total: {added}/{processed}, skipped: {skipped})")

            # Update offset
            offset += batch_size

            # Stop if we've processed the limited amount
            if limit and processed >= limit:
                break

        print(f"\nTransfer completed:")
        print(f"  - {processed} games processed from source")
        print(f"  - {added} games added to target")
        print(f"  - {skipped} games skipped (already existed in target)")

    except Exception as e:
        print(f"ERROR during transfer: {str(e)}")
        target_session.rollback()
        raise
    finally:
        source_session.close()
        target_session.close()
        print("Database connections closed.")


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
        description='Export/Import Crash data')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    subparsers.required = True

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

    # Transfer command (new)
    transfer_parser = subparsers.add_parser(
        'transfer', help='Transfer data directly from production to local database')
    transfer_parser.add_argument('--source-db', help='Source database URL',
                                 default=os.environ.get('RAILWAY_DATABASE_URL', ''))
    transfer_parser.add_argument('--target-db', help='Target database URL',
                                 default=config.DATABASE_URL)
    transfer_parser.add_argument('--clear-target', action='store_true',
                                 help='Clear target database before transfer')
    transfer_parser.add_argument('--batch-size', type=int, default=100,
                                 help='Number of records to transfer in each batch')
    transfer_parser.add_argument('--limit', type=int,
                                 help='Limit transfer to the latest N games')
    transfer_parser.add_argument(
        '--db-username', help='Username for target database')
    transfer_parser.add_argument(
        '--db-password', help='Password for target database')

    args = parser.parse_args()

    if args.command == 'export':
        export_data(args.output)
    elif args.command == 'import':
        import_data(args.input, args.target_db)
    elif args.command == 'transfer':
        transfer_data(args.source_db, args.target_db,
                      args.clear_target, args.batch_size, args.limit,
                      args.db_username, args.db_password)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
