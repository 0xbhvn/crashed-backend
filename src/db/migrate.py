"""
Database migration utility for BC Game Crash Monitor.

This module provides functions to run database migrations using Alembic.
It can be used to update the database schema when the models change.
"""

import os
import sys
import logging
import argparse
from alembic.config import Config
from alembic import command

from ..utils import load_env, configure_logging

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
ALEMBIC_CFG = os.path.join(BASE_DIR, 'alembic.ini')


def run_alembic_command(command_fn, *args, **kwargs):
    """Run an Alembic command."""
    alembic_cfg = Config(ALEMBIC_CFG)

    # Update sqlalchemy.url in the config if DATABASE_URL is set
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        alembic_cfg.set_main_option('sqlalchemy.url', database_url)

    command_fn(alembic_cfg, *args, **kwargs)


def create_migration(message):
    """Create a new migration."""
    logger = logging.getLogger('db.migrate')
    logger.info(f"Creating migration: {message}")
    run_alembic_command(command.revision, autogenerate=True, message=message)
    logger.info("Migration created. Check the migrations/versions directory.")


def upgrade_database(revision='head'):
    """Upgrade the database to a specific revision."""
    logger = logging.getLogger('db.migrate')
    logger.info(f"Upgrading database to revision: {revision}")
    run_alembic_command(command.upgrade, revision)
    logger.info("Database upgraded successfully.")


def downgrade_database(revision='-1'):
    """Downgrade the database to a specific revision."""
    logger = logging.getLogger('db.migrate')
    logger.info(f"Downgrading database to revision: {revision}")
    run_alembic_command(command.downgrade, revision)
    logger.info("Database downgraded successfully.")


def show_migrations():
    """Show migration history."""
    logger = logging.getLogger('db.migrate')
    logger.info("Migration history:")
    run_alembic_command(command.history)


def main():
    """Main entry point for the migration utility."""
    # Configure logging
    configure_logging()
    logger = logging.getLogger('db.migrate')

    parser = argparse.ArgumentParser(description='Database migration utility')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Create migration command
    create_parser = subparsers.add_parser(
        'create', help='Create a new migration')
    create_parser.add_argument('message', help='Migration message')

    # Upgrade command
    upgrade_parser = subparsers.add_parser(
        'upgrade', help='Upgrade the database')
    upgrade_parser.add_argument(
        '--revision', default='head', help='Revision to upgrade to (default: head)')

    # Downgrade command
    downgrade_parser = subparsers.add_parser(
        'downgrade', help='Downgrade the database')
    downgrade_parser.add_argument(
        '--revision', default='-1', help='Revision to downgrade to (default: -1)')

    # History command
    subparsers.add_parser('history', help='Show migration history')

    args = parser.parse_args()

    # Load environment variables
    load_env()

    if args.command == 'create':
        create_migration(args.message)
    elif args.command == 'upgrade':
        upgrade_database(args.revision)
    elif args.command == 'downgrade':
        downgrade_database(args.revision)
    elif args.command == 'history':
        show_migrations()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
