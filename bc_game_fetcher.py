#!/usr/bin/env python3
"""
BC Game Fetcher - Integration script that combines Selenium and shell script approaches
to reliably fetch crash game data from BC Game API.

This script:
1. First tries to use the Selenium approach with Cloudflare cookies
2. Falls back to the shell script if needed
3. Handles errors gracefully
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from typing import Dict, Any, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add direct stdout logging for debugging
print("BC Game Fetcher starting...")

# Path constants
SCRIPT_DIR = Path(__file__).parent.absolute()
SELENIUM_SCRIPT = SCRIPT_DIR / "selenium_bc_game.py"
CF_COOKIES_SCRIPT = SCRIPT_DIR / "use_cf_cookies.py"
SHELL_SCRIPT = SCRIPT_DIR / "fetch_crash_history.sh"

print(f"Script directory: {SCRIPT_DIR}")
print(f"Selenium script: {SELENIUM_SCRIPT}")
print(f"CF cookies script: {CF_COOKIES_SCRIPT}")
print(f"Shell script: {SHELL_SCRIPT}")


def ensure_selenium_installed():
    """Ensure Selenium is installed in the current environment."""
    try:
        import selenium
        logger.info(f"Found Selenium version {selenium.__version__}")
        print(f"Found Selenium version {selenium.__version__}")
    except ImportError:
        logger.warning("Selenium not found. Attempting to install...")
        print("Selenium not found. Attempting to install...")
        subprocess.run([sys.executable, "-m", "pip",
                       "install", "selenium"], check=True)


def ensure_requests_installed():
    """Ensure requests is installed in the current environment."""
    try:
        import requests
        logger.info(f"Found requests version {requests.__version__}")
        print(f"Found requests version {requests.__version__}")
    except ImportError:
        logger.warning("Requests not found. Attempting to install...")
        print("Requests not found. Attempting to install...")
        subprocess.run([sys.executable, "-m", "pip",
                       "install", "requests"], check=True)


def fetch_with_selenium(page: int, page_size: int, output_file: str) -> bool:
    """
    Attempt to fetch data using the Selenium approach.

    Returns:
        bool: True if fetch was successful, False otherwise
    """
    try:
        # Ensure the CF cookies script uses the same Python interpreter
        cmd = [sys.executable, str(CF_COOKIES_SCRIPT),
               "--page", str(page),
               "--size", str(page_size),
               "--output", output_file]

        logger.info(f"Executing: {' '.join(cmd)}")
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        print(f"Command output: {result.stdout}")
        if result.stderr:
            print(f"Command error: {result.stderr}")

        if result.returncode != 0:
            logger.error(f"Error running CF cookies script: {result.stderr}")
            print(f"Error running CF cookies script: {result.stderr}")
            return False

        # Verify the output file exists and contains valid data
        if not os.path.exists(output_file):
            logger.error(f"Output file {output_file} not created")
            print(f"Output file {output_file} not created")
            return False

        with open(output_file, 'r') as f:
            data = json.load(f)
            if 'data' in data and 'list' in data['data']:
                games_count = len(data['data']['list'])
                logger.info(
                    f"Successfully fetched {games_count} games with Selenium approach")
                print(
                    f"Successfully fetched {games_count} games with Selenium approach")
                return games_count > 0
            else:
                logger.warning("No games found in the response")
                print("No games found in the response")
                return False

    except Exception as e:
        logger.error(f"Error using Selenium approach: {e}")
        print(f"Error using Selenium approach: {e}")
        return False


def fetch_with_shell_script(page: int, page_size: int, output_file: str) -> bool:
    """
    Attempt to fetch data using the shell script approach.

    Returns:
        bool: True if fetch was successful, False otherwise
    """
    try:
        cmd = [str(SHELL_SCRIPT),
               "--page", str(page),
               "--size", str(page_size),
               "--output", output_file]

        logger.info(f"Executing: {' '.join(cmd)}")
        print(f"Executing: {' '.join(cmd)}")
        # Make sure the script is executable
        os.chmod(SHELL_SCRIPT, 0o755)

        result = subprocess.run(cmd, capture_output=True, text=True)

        print(f"Shell script output: {result.stdout}")
        if result.stderr:
            print(f"Shell script error: {result.stderr}")

        if result.returncode != 0:
            logger.error(f"Error running shell script: {result.stderr}")
            print(f"Error running shell script: {result.stderr}")
            return False

        # Verify the output file exists and contains valid data
        if not os.path.exists(output_file):
            logger.error(f"Output file {output_file} not created")
            print(f"Output file {output_file} not created")
            return False

        with open(output_file, 'r') as f:
            try:
                data = json.load(f)
                if 'data' in data and 'list' in data['data']:
                    games_count = len(data['data']['list'])
                    logger.info(
                        f"Successfully fetched {games_count} games with shell script approach")
                    print(
                        f"Successfully fetched {games_count} games with shell script approach")
                    return games_count > 0
                else:
                    logger.warning("No games found in the response")
                    print("No games found in the response")
                    return False
            except json.JSONDecodeError:
                logger.error("Invalid JSON in output file")
                print("Invalid JSON in output file")
                return False

    except Exception as e:
        logger.error(f"Error using shell script approach: {e}")
        print(f"Error using shell script approach: {e}")
        return False


def fetch_crash_history(page: int = 1, page_size: int = 20, output_file: str = "crash_history.json") -> Optional[Dict[str, Any]]:
    """
    Fetch crash game history using a combination of approaches.

    Args:
        page: Page number to fetch
        page_size: Number of items per page
        output_file: Path to save the output

    Returns:
        Optional[Dict[str, Any]]: Game history data if successful, None otherwise
    """
    # First try with Selenium approach
    logger.info(
        f"Fetching crash history page {page} with size {page_size} using Selenium approach")
    print(
        f"Fetching crash history page {page} with size {page_size} using Selenium approach")
    if fetch_with_selenium(page, page_size, output_file):
        logger.info("Selenium approach succeeded")
        print("Selenium approach succeeded")
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)

                # Standardize the format to use 'items' key
                if 'data' in data:
                    if 'list' in data['data'] and 'items' not in data['data']:
                        # Convert 'list' to 'items'
                        print(f"Standardizing format: converting 'list' to 'items'")
                        data['data']['items'] = data['data']['list']
                        # Write back to file to ensure consistency
                        with open(output_file, 'w') as out_f:
                            json.dump(data, out_f, indent=2)
                return data
        except Exception as e:
            logger.error(
                f"Error reading output file after Selenium approach: {e}")
            print(f"Error reading output file after Selenium approach: {e}")

    # Fall back to shell script approach
    logger.info(f"Selenium approach failed. Trying shell script approach...")
    print(f"Selenium approach failed. Trying shell script approach...")
    if fetch_with_shell_script(page, page_size, output_file):
        logger.info("Shell script approach succeeded")
        print("Shell script approach succeeded")
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)

                # Standardize the format to use 'items' key
                if 'data' in data:
                    if 'list' in data['data'] and 'items' not in data['data']:
                        # Convert 'list' to 'items'
                        print(f"Standardizing format: converting 'list' to 'items'")
                        data['data']['items'] = data['data']['list']
                        # Write back to file to ensure consistency
                        with open(output_file, 'w') as out_f:
                            json.dump(data, out_f, indent=2)
                return data
        except Exception as e:
            logger.error(
                f"Error reading output file after shell script approach: {e}")
            print(
                f"Error reading output file after shell script approach: {e}")

    logger.error("All approaches failed to fetch data")
    print("All approaches failed to fetch data")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="BC Game Crash Data Fetcher (Hybrid Approach)")
    parser.add_argument("-p", "--page", type=int, default=1,
                        help="Page number to fetch")
    parser.add_argument("-s", "--size", type=int, default=20,
                        help="Number of items per page")
    parser.add_argument("-o", "--output", type=str,
                        default="crash_history.json", help="Output file path")

    args = parser.parse_args()

    print(
        f"Arguments: page={args.page}, size={args.size}, output={args.output}")

    # Ensure required packages are installed
    ensure_selenium_installed()
    ensure_requests_installed()

    # Fetch data
    data = fetch_crash_history(args.page, args.size, args.output)

    if data:
        print(
            f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
        if 'data' in data:
            print(
                f"Data['data'] keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'not a dict'}")
            if 'list' in data['data']:
                games_count = len(data['data']['list'])
                print(f"Games count: {games_count}")
                print(
                    f"First game keys: {list(data['data']['list'][0].keys()) if games_count > 0 else 'no games'}")
            elif 'items' in data['data']:
                games_count = len(data['data']['items'])
                print(f"Games count (items): {games_count}")
                print(
                    f"First game keys: {list(data['data']['items'][0].keys()) if games_count > 0 else 'no games'}")

        games_count = len(data['data']['list']) if 'data' in data and 'list' in data['data'] else (
            len(data['data']['items']
                ) if 'data' in data and 'items' in data['data'] else 0
        )
        logger.info(
            f"Summary: Successfully fetched page {args.page} with {games_count} games")
        print(
            f"Summary: Successfully fetched page {args.page} with {games_count} games")
        return 0
    else:
        logger.error(f"Failed to fetch data for page {args.page}")
        print(f"Failed to fetch data for page {args.page}")
        return 1


if __name__ == "__main__":
    print("Script starting...")
    exit_code = main()
    print(f"Script completed with exit code {exit_code}")
    exit(exit_code)
