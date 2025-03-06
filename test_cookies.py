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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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


def get_cloudflare_cookies():
    """Get Cloudflare cookies from the saved file."""
    cookie_file = 'cf_cookies.txt'
    cookies = {}

    if not os.path.exists(cookie_file):
        logger.error(f"Cookie file {cookie_file} not found!")
        return cookies

    # Check cookie file age
    cookie_age_seconds = datetime.now().timestamp() - os.path.getmtime(cookie_file)
    cookie_age_hours = cookie_age_seconds / 3600
    logger.info(f"Cookie file age: {cookie_age_hours:.1f} hours old")

    if cookie_age_hours > 24:
        logger.warning(
            f"Cookie file is more than 24 hours old! Cookies have likely expired.")

    # Read cookies
    with open(cookie_file, 'r') as f:
        for line in f:
            # Skip comment lines
            if line.strip().startswith('#'):
                continue

            if '=' in line:
                name, value = line.strip().split('=', 1)
                cookies[name] = value

    logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")

    # Check if we have the key cookies
    if 'cf_clearance' not in cookies:
        logger.warning("Missing critical cookie: cf_clearance")
    if 'cf_bm' not in cookies:
        logger.warning("Missing cookie: cf_bm")

    return cookies


def get_headers():
    """Get headers to use for the request."""
    # Try to load custom headers if they exist
    headers_file = 'cf_headers.json'
    if os.path.exists(headers_file):
        try:
            with open(headers_file, 'r') as f:
                headers = json.load(f)
            logger.info(f"Loaded custom headers from {headers_file}")
            return headers
        except Exception as e:
            logger.warning(f"Error loading headers file: {e}")

    # Default headers
    return {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en',
        'content-type': 'application/json',
        'dnt': '1',
        'origin': 'https://bc.fun',
        'referer': 'https://bc.fun/game/crash',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }


def test_cookies():
    """Test if the Cloudflare cookies are working."""
    try:
        # Get environment info
        env_info = get_environment_info()
        logger.info(f"Environment: {json.dumps(env_info, indent=2)}")

        # Get cookies
        cookies = get_cloudflare_cookies()
        if not cookies:
            logger.error(
                "No cookies found. Run add_cookies.py to add cookies.")
            return False

        # Get headers
        headers = get_headers()

        # API endpoint
        url = 'https://bc.fun/api/game/bet/multi/history'

        # Request payload
        payload = {
            'gameId': 'crashnormal',
            'type': 'casino',
            'timeRange': 0,
            'clientSeed': 'test-cookies-script',
            'page': 1,
            'pageSize': 5  # Just request a few games to test
        }

        logger.info(f"Making test request to {url}")
        logger.info(f"Headers: {json.dumps(headers, indent=2)}")
        logger.info(
            f"Cookies: {json.dumps({k: v[:10] + '...' for k, v in cookies.items()}, indent=2)}")

        # Make the API request
        response = requests.post(url, headers=headers,
                                 cookies=cookies, json=payload)

        # Log basic response info
        logger.info(f"Response status code: {response.status_code}")
        logger.info(
            f"Response headers: {json.dumps(dict(response.headers), indent=2)}")

        # Check if it's a Cloudflare challenge response
        if "Just a moment" in response.text or "Checking if the site connection is secure" in response.text:
            logger.error(
                "FAILED: Received Cloudflare challenge response. Cookies are not working!")
            logger.info("Response content preview:")
            logger.info(response.text[:500] + "...")
            return False

        # Check if successful
        if response.status_code == 200:
            try:
                data = response.json()

                # Check for API errors
                if 'success' in data and not data['success']:
                    logger.error(
                        f"API returned error: {data.get('msg', 'Unknown error')}")
                    return False

                # Check if we got game data
                if 'data' in data:
                    if 'list' in data['data']:
                        games_count = len(data['data']['list'])
                        logger.info(
                            f"SUCCESS: Retrieved {games_count} games in 'list' format")

                        # Show a sample of the data
                        if games_count > 0:
                            logger.info(
                                f"Sample game data: {json.dumps(data['data']['list'][0], indent=2)}")

                        return True
                    elif 'items' in data['data']:
                        games_count = len(data['data']['items'])
                        logger.info(
                            f"SUCCESS: Retrieved {games_count} games in 'items' format")

                        # Show a sample of the data
                        if games_count > 0:
                            logger.info(
                                f"Sample game data: {json.dumps(data['data']['items'][0], indent=2)}")

                        return True
                    else:
                        logger.warning(
                            "Response contains 'data' key but no game list/items")
                        logger.info(
                            f"Response data: {json.dumps(data, indent=2)}")
                        return False
                else:
                    logger.warning("Response does not contain 'data' key")
                    logger.info(f"Response data: {json.dumps(data, indent=2)}")
                    return False
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON response")
                logger.info("Response content preview:")
                logger.info(response.text[:500] + "...")
                return False
        else:
            logger.error(
                f"Request failed with status code {response.status_code}")
            logger.info("Response content preview:")
            logger.info(response.text[:500] + "...")
            return False
    except Exception as e:
        logger.error(f"Error testing cookies: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting cookie test...")
    if test_cookies():
        logger.info(
            "✅ Cookies are working! You should be able to access the BC Game API.")
    else:
        logger.error("❌ Cookies test failed. See errors above for details.")
        logger.error("Try running add_cookies.py to add new cookies.")
        sys.exit(1)
