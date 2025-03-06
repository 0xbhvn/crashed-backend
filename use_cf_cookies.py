#!/usr/bin/env python3
"""
Helper script to use Cloudflare cookies with BC Game API requests.
This demonstrates how to use the cookies captured by Selenium to make API requests.
"""

import os
import json
import logging
import argparse
import subprocess
import requests
import time
import sys
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cloudflare_cookies() -> Dict[str, str]:
    """Get Cloudflare cookies from the saved file."""
    cookie_file = 'cf_cookies.txt'
    cookies = {}

    if not os.path.exists(cookie_file):
        logger.warning(
            f"Cookie file {cookie_file} not found.")

        # Check if we're in a production container environment
        in_container = os.environ.get(
            'CONTAINER', '') == 'true' or os.environ.get('DOCKER', '') == 'true'

        if in_container:
            logger.warning(
                "Running in container environment - cannot use Selenium browser.")
            logger.warning(
                "You need to manually add Cloudflare cookies to cf_cookies.txt")
            logger.warning("Format: cf_clearance=value\\ncf_bm=value")

            # Try to create an empty cookie file so we don't keep trying
            try:
                with open(cookie_file, 'w') as f:
                    f.write("# Add Cloudflare cookies here\n")
                    f.write("# Format: cf_clearance=value\n")
                    f.write("# cf_bm=value\n")
            except Exception as e:
                logger.error(f"Error creating empty cookie file: {e}")
        else:
            # Determine the Python executable path
            if os.path.exists('./venv/bin/python'):
                python_path = './venv/bin/python'
            elif os.path.exists('/opt/venv/bin/python'):
                python_path = '/opt/venv/bin/python'
            else:
                python_path = sys.executable  # Use current Python interpreter

            logger.info(f"Running Selenium script with Python: {python_path}")

            try:
                # Run the Selenium script to get cookies
                subprocess.run(
                    [python_path, 'selenium_bc_game.py'], check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to run Selenium script: {e}")
            except FileNotFoundError as e:
                logger.error(f"Selenium script not found: {e}")
    else:
        # Check cookie file age - warn if older than 1 hour
        cookie_age = time.time() - os.path.getmtime(cookie_file)
        if cookie_age > 3600:  # older than 1 hour (3600 seconds)
            hours_old = cookie_age / 3600
            logger.warning(
                f"Cookie file is {hours_old:.1f} hours old and may be expired.")
            logger.warning(
                "If API calls fail, run ./refresh_cookies.py to refresh cookies.")

    # Now the cookie file should exist
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            for line in f:
                # Skip comment lines
                if line.strip().startswith('#'):
                    continue

                if '=' in line:
                    name, value = line.strip().split('=', 1)
                    cookies[name] = value
        logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")
    else:
        logger.error(
            f"Cookie file {cookie_file} still not found after attempting to create it")

    return cookies


def fetch_game_history(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """Fetch game history using Cloudflare cookies."""
    cookies = get_cloudflare_cookies()

    url = 'https://bc.fun/api/game/bet/multi/history'

    headers = {
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

    # Set a deterministic clientSeed for consistency (doesn't affect results)
    client_seed = f"python-client-{page}-{page_size}"

    payload = {
        'gameId': 'crashnormal',
        'type': 'casino',
        'timeRange': 0,
        'clientSeed': client_seed,
        'page': page,
        'pageSize': page_size
    }

    # Log diagnostic information in production
    is_production = os.environ.get(
        'CONTAINER', '') == 'true' or os.environ.get('DOCKER', '') == 'true'

    try:
        logger.info(
            f"Making API request to {url} with page={page}, size={page_size}")

        # Print verbose debugging in production
        if is_production:
            logger.info(f"Request headers: {headers}")
            logger.info(f"Request cookies: {cookies}")
            logger.info(f"Request payload: {payload}")

            # Test if cookies are properly formatted
            logger.info(f"Cookie count: {len(cookies)}")
            for name, value in cookies.items():
                # Only show first 10 chars of value for security
                logger.info(f"Cookie {name}: {value[:10]}...")

        # Make the API request
        response = requests.post(url, headers=headers,
                                 cookies=cookies, json=payload)

        # Log the response details
        if is_production:
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")

            # Print a small part of the response for debugging
            if response.status_code != 200:
                logger.info(
                    f"Response content (first 500 chars): {response.text[:500]}")

                # If Cloudflare challenge detected in response text
                if "Just a moment" in response.text or "challenge" in response.text.lower():
                    logger.error(
                        "Cloudflare challenge detected in response - cookies rejected")

                # Try analyzing what might be wrong
                if response.status_code == 403:
                    logger.error("403 Forbidden - Possible reasons:")
                    logger.error("1. Cookies are expired")
                    logger.error("2. Cookies are from a different IP address")
                    logger.error("3. Request is missing required headers")
                    logger.error("4. Rate limiting is active")

        # Check if the request was successful
        response.raise_for_status()

        # Parse the response as JSON
        data = response.json()

        # Check for error message in response
        if 'msg' in data and data.get('success') is False:
            logger.warning(f"API returned error: {data['msg']}")
            return {'data': {'items': []}}

        # Return the response data
        return data
    except requests.exceptions.HTTPError as e:
        logger.error(f"Error fetching game history: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise


def save_game_history(data: Dict[str, Any], output_file: str = "api_game_history.json"):
    """Save game history data to a file."""
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved game history to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch BC Game crash game history using Cloudflare cookies")
    parser.add_argument("-p", "--page", type=int, default=1,
                        help="Page number to fetch")
    parser.add_argument("-s", "--size", type=int, default=20,
                        help="Number of items per page")
    parser.add_argument("-o", "--output", type=str,
                        default="api_game_history.json", help="Output file path")

    args = parser.parse_args()

    try:
        # Fetch and save game history
        data = fetch_game_history(args.page, args.size)
        save_game_history(data, args.output)

        # Print summary
        games_count = len(
            data['data']['items']) if 'data' in data and 'items' in data['data'] else 0
        logger.info(
            f"Summary: Fetched page {args.page} with {games_count} games")

    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
