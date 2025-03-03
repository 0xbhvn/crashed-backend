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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_CFG = os.path.join(BASE_DIR, 'alembic.ini')


def load_env(env_file='.env'):
    """Load environment variables from .env file."""
    if not os.path.exists(env_file):
        logger.warning(f"{env_file} not found. Using default values.")
        return

    logger.info(f"Loading environment from {env_file}")

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            key, value = line.split('=', 1)
            os.environ[key] = value


def run_alembic_command(command_fn, *args, **kwargs):
    """Run an Alembic command."""
    alembic_cfg = Config(ALEMBIC_CFG)
    command_fn(alembic_cfg, *args, **kwargs)


def create_migration(message):
    """Create a new migration."""
    logger.info(f"Creating migration: {message}")
    run_alembic_command(command.revision, autogenerate=True, message=message)
    logger.info("Migration created. Check the migrations/versions directory.")


def upgrade_database(revision='head'):
    """Upgrade the database to a specific revision."""
    logger.info(f"Upgrading database to revision: {revision}")
    run_alembic_command(command.upgrade, revision)
    logger.info("Database upgraded successfully.")


def downgrade_database(revision='-1'):
    """Downgrade the database to a specific revision."""
    logger.info(f"Downgrading database to revision: {revision}")
    run_alembic_command(command.downgrade, revision)
    logger.info("Database downgraded successfully.")


def show_migrations():
    """Show migration history."""
    logger.info("Migration history:")
    run_alembic_command(command.history)


def main():
    """Main entry point for the migration utility."""
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
