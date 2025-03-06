#!/usr/bin/env python3
"""
Test script to verify if the Cloudflare cookies are working in the current environment.
This is especially useful in production to diagnose API access issues.
"""

import os
import sys
import json
import logging
import requests
import socket
import platform
from datetime import datetime
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cookie_test')

# Constants
BASE_URL = "https://bc.game"
HISTORY_URL = urljoin(BASE_URL, "/api/game/support/crash/history")
RETRY_COUNT = 3
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(CURRENT_DIR, "cf_cookies.txt")


def get_environment_info():
    """Get information about the current environment."""
    try:
        # Get hostname
        hostname = socket.gethostname()

        # Try to get IP address (may fail in some environments)
        try:
            ip = socket.gethostbyname(hostname)
        except:
            ip = "Unknown"

        info = {
            "hostname": hostname,
            "ip": ip,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "is_container": os.environ.get('CONTAINER', '') == 'true' or os.environ.get('DOCKER', '') == 'true',
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return info
    except Exception as e:
        logger.error(f"Error getting environment info: {e}")
        return {"error": str(e)}


def load_cookies():
    """Load cookies from file."""
    try:
        if not os.path.exists(COOKIE_FILE):
            logger.error(f"Cookie file not found: {COOKIE_FILE}")
            return {}

        with open(COOKIE_FILE, "r") as f:
            cookie_data = f.read().strip().split('\n')

        cookies = {}
        for line in cookie_data:
            if not line or line.startswith('#'):
                continue

            parts = line.split('=', 1)
            if len(parts) != 2:
                logger.warning(f"Invalid cookie format: {line}")
                continue

            name, value = parts
            cookies[name.strip()] = value.strip()

        if not cookies:
            logger.error("No valid cookies found in file")
        else:
            logger.info(f"Loaded {len(cookies)} cookies")

        return cookies

    except Exception as e:
        logger.error(f"Error loading cookies: {e}")
        return {}


def check_cookies(cookies):
    """Test if the cookies work by making an API request."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE_URL,
    }

    if "cf_clearance" not in cookies:
        logger.error("Missing cf_clearance cookie")
    if "__cf_bm" not in cookies:
        logger.warning("Missing __cf_bm cookie (may still work)")

    success = False

    for attempt in range(RETRY_COUNT):
        try:
            logger.info(
                f"Testing cookies (attempt {attempt+1}/{RETRY_COUNT})...")

            response = requests.get(
                HISTORY_URL,
                headers=headers,
                cookies=cookies,
                timeout=10
            )

            logger.info(f"Response status code: {response.status_code}")

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    if 'data' in json_data and 'items' in json_data['data']:
                        game_count = len(json_data['data']['items'])
                        logger.info(f"Success! Retrieved {game_count} games")
                        success = True
                        break
                    else:
                        logger.error(f"Invalid response format: {json_data}")
                except json.JSONDecodeError:
                    logger.error("Response is not valid JSON")
                    if "Cloudflare" in response.text or "challenge" in response.text:
                        logger.error(
                            "Received Cloudflare challenge - cookies are invalid or expired")
            else:
                logger.error(f"Error response: {response.status_code}")
                if response.status_code == 403:
                    logger.error(
                        "Forbidden (403) - Cookies are invalid or expired")
                    # Print the first 200 characters of the response for debugging
                    logger.debug(f"Response preview: {response.text[:200]}...")

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")

        if not success and attempt < RETRY_COUNT - 1:
            logger.info(f"Retrying in 2 seconds...")
            import time
            time.sleep(2)

    return success


def check_cookie_expiry(cookies):
    """Estimate cookie expiry based on known patterns."""
    if 'cf_clearance' in cookies:
        # Try to extract timestamp from cf_clearance
        try:
            parts = cookies['cf_clearance'].split('-')
            for part in parts:
                # Look for 10-digit unix timestamp
                if part.isdigit() and len(part) == 10:
                    timestamp = int(part)
                    expiry_time = datetime.datetime.fromtimestamp(timestamp)
                    now = datetime.datetime.now()

                    # Typical Cloudflare cookies last 30 days
                    if expiry_time > now:
                        days_remaining = (expiry_time - now).days
                        logger.info(
                            f"Cookie appears to expire on {expiry_time} (in ~{days_remaining} days)")
                    else:
                        logger.warning(
                            f"Cookie appears to have expired on {expiry_time}")

                    return
        except Exception as e:
            logger.debug(f"Could not determine expiry: {e}")

    logger.info("Could not determine cookie expiry time")


def main():
    """Main function to test cookies."""
    logger.info("=== BC Game Cookie Tester ===")

    # Load cookies
    cookies = load_cookies()
    if not cookies:
        logger.error("No cookies loaded. Please add cookies to cf_cookies.txt")
        return False

    # Check expiry (best effort)
    check_cookie_expiry(cookies)

    # Test the cookies
    success = check_cookies(cookies)

    if success:
        logger.info("✅ Cookies are working correctly!")
        return True
    else:
        logger.error(
            "❌ Cookies are NOT working. They may have expired or are invalid.")
        logger.info("Please run add_cookies.py to update them.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
