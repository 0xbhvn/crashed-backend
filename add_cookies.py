#!/usr/bin/env python3
"""
Helper script to manually add Cloudflare cookies in production environments.
This script is especially useful in container environments where Selenium cannot run.

Usage:
1. Obtain Cloudflare cookies (cf_clearance and cf_bm) from your browser after visiting BC Game
2. Run this script and input the cookie values when prompted
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def add_cookies():
    """Add Cloudflare cookies manually."""
    try:
        cookie_file = 'cf_cookies.txt'

        logger.info("=== BC Game Cloudflare Cookie Helper ===")
        logger.info(
            "This tool helps you manually add Cloudflare cookies for API access")
        logger.info("")
        logger.info("How to get cookies from your browser:")
        logger.info(
            "1. Open Chrome/Firefox and visit https://bc.fun/game/crash")
        logger.info("2. Complete any Cloudflare challenges")
        logger.info("3. Open Developer Tools (F12) > Application tab > Cookies")
        logger.info("4. Find cookies named 'cf_clearance' and 'cf_bm'")
        logger.info("")

        cookies = {}

        # Get cookies from user input
        cf_clearance = input("Enter cf_clearance cookie value: ").strip()
        cf_bm = input("Enter cf_bm cookie value: ").strip()

        if not cf_clearance and not cf_bm:
            logger.warning("No cookie values provided. Exiting.")
            return False

        if cf_clearance:
            cookies['cf_clearance'] = cf_clearance
        if cf_bm:
            cookies['cf_bm'] = cf_bm

        # Write cookies to file
        with open(cookie_file, 'w') as f:
            f.write("# Cloudflare cookies for BC Game\n")
            for name, value in cookies.items():
                f.write(f"{name}={value}\n")

        logger.info(
            f"Successfully saved {len(cookies)} cookies to {cookie_file}")
        logger.info(
            "The BCCrashMonitor should now be able to access the BC Game API.")

        return True

    except Exception as e:
        logger.error(f"Error adding cookies: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting manual cookie entry process...")
    if add_cookies():
        logger.info("Cookies successfully added.")
    else:
        logger.error("Failed to add cookies. See errors above for details.")
        sys.exit(1)
