#!/usr/bin/env python3
"""
BC Game Crash Monitor - Launcher Script

This script loads environment variables from .env file and starts the monitor.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path
import platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('launcher')


def activate_venv():
    """Activate virtual environment if it exists"""
    venv_path = Path('venv')
    if not venv_path.exists():
        logger.warning(
            "Virtual environment 'venv' not found. Using system Python.")
        return False

    logger.info("Activating virtual environment...")

    # Determine appropriate activate script based on platform
    if platform.system() == 'Windows':
        activate_script = venv_path / 'Scripts' / 'activate.bat'
        activate_cmd = f'"{activate_script}"'
    else:
        activate_script = venv_path / 'bin' / 'activate'
        activate_cmd = f'source "{activate_script}"'

    # Set environment variables to indicate venv is activated
    venv_bin = str(
        venv_path / ('Scripts' if platform.system() == 'Windows' else 'bin'))
    os.environ['PATH'] = f"{venv_bin}{os.pathsep}{os.environ['PATH']}"
    os.environ['VIRTUAL_ENV'] = str(venv_path.absolute())

    logger.info(f"Virtual environment activated at {venv_path.absolute()}")
    return True


def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path('.env')
    if not env_path.exists():
        logger.warning(".env file not found, using default settings")
        return

    logger.info(f"Loading environment from {env_path.absolute()}")

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                key, value = line.split('=', 1)
                os.environ[key] = value

        logger.info("Environment variables loaded successfully")
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
        sys.exit(1)


def check_database_tables():
    """Check if the database tables exist and create them if needed."""
    try:
        # Try importing SQLAlchemy models
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from src.models import Base
        from sqlalchemy import create_engine

        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.warning(
                "DATABASE_URL not set, will use default when required")
            return False

        # Create engine and verify tables
        engine = create_engine(database_url)

        # Check if tables exist
        logger.info("Checking database tables...")

        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully")
        return True
    except ImportError:
        logger.warning(
            "SQLAlchemy not installed. Database functionality may be limited.")
        return False
    except Exception as e:
        logger.error(f"Error checking database tables: {e}")
        return False


def run_monitor():
    """Run the BC Game Crash Monitor"""
    try:
        # Enable database by default
        if 'DATABASE_ENABLED' not in os.environ:
            os.environ['DATABASE_ENABLED'] = 'true'
            logger.info("Database enabled by default")

        # Check database tables
        if os.environ.get('DATABASE_ENABLED') == 'true':
            database_ready = check_database_tables()
            if not database_ready:
                logger.warning(
                    "Database tables check failed. Database functionality may be limited.")

        # Print key configuration values
        logger.info(
            f"API Base URL: {os.environ.get('API_BASE_URL', 'https://bc.game')}")
        logger.info(f"Database Enabled: {os.environ.get('DATABASE_ENABLED')}")
        logger.info(
            f"Database URL: {os.environ.get('DATABASE_URL', '[not set]')}")

        # Run the monitor
        logger.info("Starting BC Game Crash Monitor...")

        # Use the Python executable from the current environment
        python_exe = sys.executable

        # Run the main script
        result = subprocess.run(
            [python_exe, "src/main.py"],
            check=True
        )

        return result.returncode

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Monitor exited with error code {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"Error running monitor: {e}")
        return 1


if __name__ == "__main__":
    # Activate virtual environment if available
    activate_venv()

    # Load environment variables
    load_env_file()

    # Run the monitor
    exit_code = run_monitor()

    # Exit with the same code
    sys.exit(exit_code)
