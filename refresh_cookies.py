#!/usr/bin/env python3
"""
Helper script to refresh Cloudflare cookies for BC Game API access.
This simply launches the Selenium browser to solve Cloudflare challenges and save cookies.
"""

import os
import sys
import logging
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def refresh_cookies():
    """Refresh Cloudflare cookies by running the Selenium script."""
    try:
        # Get the path to the selenium script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        selenium_script_path = os.path.join(script_dir, "selenium_bc_game.py")

        if not os.path.exists(selenium_script_path):
            logger.error(
                f"Selenium script not found at {selenium_script_path}")
            return False

        logger.info("Launching Selenium browser to refresh cookies...")
        logger.info(
            "Please wait for the browser to navigate to BC Game and solve any Cloudflare challenges.")
        logger.info(
            "The script will automatically press Enter to close the browser when ready.")

        # Run the script and check the result
        process = subprocess.run(
            [sys.executable, selenium_script_path],
            capture_output=True,
            text=True
        )

        if process.returncode == 0:
            logger.info("Cookie refresh successful!")

            # Check if the cookie file exists and has content
            cookie_file_path = os.path.join(script_dir, "cf_cookies.txt")
            if os.path.exists(cookie_file_path):
                with open(cookie_file_path, 'r') as f:
                    cookies = f.read().strip().split('\n')
                    if cookies:
                        logger.info(
                            f"Found {len(cookies)} Cloudflare cookies.")
                        for cookie in cookies:
                            name, value = cookie.split('=', 1)
                            logger.info(f"  - {name}: {value[:10]}...")
                        return True
                    else:
                        logger.warning("Cookie file exists but is empty!")
            else:
                logger.warning(f"Cookie file not found at {cookie_file_path}")
        else:
            logger.error(
                f"Error running Selenium script: {process.returncode}")
            logger.error(f"Stderr: {process.stderr}")

        return False
    except Exception as e:
        logger.error(f"Error refreshing cookies: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting cookie refresh process...")
    if refresh_cookies():
        logger.info(
            "Cookies successfully refreshed. You can now run the monitor.")
    else:
        logger.error(
            "Failed to refresh cookies. See errors above for details.")
        sys.exit(1)
