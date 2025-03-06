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
import json
import socket
import platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_environment_info():
    """Get information about the current environment."""
    info = {
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "is_container": os.environ.get('CONTAINER', '') == 'true' or os.environ.get('DOCKER', '') == 'true'
    }
    return info


def add_cookies():
    """Add Cloudflare cookies manually."""
    try:
        cookie_file = 'cf_cookies.txt'

        # Get environment info
        env_info = get_environment_info()
        is_production = env_info['is_container']

        logger.info("=== BC Game Cloudflare Cookie Helper ===")
        logger.info(
            f"Environment: {'Production/Container' if is_production else 'Development'}")
        logger.info(f"Hostname: {env_info['hostname']}")
        logger.info(f"IP: {env_info['ip']}")
        logger.info(f"Platform: {env_info['platform']}")
        logger.info("")
        logger.info(
            "This tool helps you manually add Cloudflare cookies for API access")
        logger.info("")

        if is_production:
            logger.info("PRODUCTION ENVIRONMENT DETECTED!")
            logger.info(
                "You must get cookies that will work from this server's IP address.")
            logger.info("Options:")
            logger.info(
                "1. Use a browser with a proxy that routes through this server")
            logger.info(
                "2. Use cookies from a browser on this server (if GUI available)")
            logger.info(
                "3. Try using cookies from your local machine (may not work)")
            logger.info("")

        logger.info("How to get cookies from your browser:")
        logger.info(
            "1. Open Chrome/Firefox and visit https://bc.fun/game/crash")
        logger.info("2. Complete any Cloudflare challenges")
        logger.info("3. Open Developer Tools (F12) > Application tab > Cookies")
        logger.info("4. Find cookies named 'cf_clearance' and 'cf_bm'")
        logger.info("")
        logger.info(
            "You should also use the same User-Agent header as your browser:")
        logger.info(
            "Chrome: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        logger.info(
            "Firefox: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0")
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

        # Ask for user agent
        logger.info("")
        logger.info("User-Agent is critical for Cloudflare cookies to work.")
        user_agent = input(
            "Enter the User-Agent string from your browser (optional): ").strip()

        # Write cookies to file
        with open(cookie_file, 'w') as f:
            f.write("# Cloudflare cookies for BC Game\n")
            for name, value in cookies.items():
                f.write(f"{name}={value}\n")

            # Save user agent if provided
            if user_agent:
                f.write(f"# User-Agent: {user_agent}\n")

        # Update the headers file if user agent was provided
        if user_agent:
            try:
                headers_file = 'cf_headers.json'
                headers = {
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en',
                    'content-type': 'application/json',
                    'dnt': '1',
                    'origin': 'https://bc.fun',
                    'referer': 'https://bc.fun/game/crash',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': user_agent,
                }

                # Extract sec-ch-ua values if possible
                if "Chrome" in user_agent:
                    chrome_version = user_agent.split(
                        "Chrome/")[1].split(" ")[0]
                    headers['sec-ch-ua'] = f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"'
                    headers['sec-ch-ua-mobile'] = '?0'
                    headers['sec-ch-ua-platform'] = '"macOS"' if "Mac" in user_agent else '"Windows"' if "Windows" in user_agent else '"Linux"'

                with open(headers_file, 'w') as f:
                    json.dump(headers, f, indent=2)
                logger.info(
                    f"Updated headers file with User-Agent: {headers_file}")
            except Exception as e:
                logger.warning(f"Failed to save headers file: {e}")

        logger.info(
            f"Successfully saved {len(cookies)} cookies to {cookie_file}")

        if is_production:
            logger.info("")
            logger.info("PRODUCTION ENVIRONMENT NOTES:")
            logger.info("1. Test the cookies with a manual API request")
            logger.info(
                "2. If the API access still fails, try getting cookies from a browser on this server")
            logger.info(
                "3. Remember that cookies typically expire in 24 hours")
            logger.info(
                "4. Consider setting up an automated cookie refresher if possible")

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
