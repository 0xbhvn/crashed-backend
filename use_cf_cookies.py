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
            f"Cookie file {cookie_file} not found. Running Selenium script to get cookies...")
        # Run the Selenium script to get cookies
        subprocess.run(
            ['./venv/bin/python', 'selenium_bc_game.py'], check=True)

    # Now the cookie file should exist
    if os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            for line in f:
                if '=' in line:
                    name, value = line.strip().split('=', 1)
                    cookies[name] = value
        logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")
    else:
        logger.error(
            f"Cookie file {cookie_file} still not found after running Selenium")

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
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    }

    data = {
        "gameUrl": "crash",
        "page": page,
        "pageSize": page_size
    }

    logger.info(
        f"Fetching game history for page {page} with size {page_size}...")

    try:
        response = requests.post(url, headers=headers,
                                 cookies=cookies, json=data)
        response.raise_for_status()

        # Check if we got actual JSON data
        if response.headers.get('content-type', '').startswith('application/json'):
            result = response.json()

            # Check if we got game data and standardize the format
            if 'data' in result:
                if 'list' in result['data']:
                    games_count = len(result['data']['list'])
                    logger.info(
                        f"Successfully fetched {games_count} games (list format)")

                    # Create a standard format with 'items' key
                    standardized_result = {
                        'data': {
                            'items': result['data']['list'],
                            'page': result['data'].get('page', page),
                            'pageSize': result['data'].get('pageSize', page_size),
                            'total': result['data'].get('total', games_count),
                            'totalPage': result['data'].get('totalPage', 1)
                        }
                    }
                    return standardized_result

                elif 'items' in result['data']:
                    games_count = len(result['data']['items'])
                    logger.info(
                        f"Successfully fetched {games_count} games (items format)")
                    return result
                else:
                    logger.warning(
                        "Response does not contain expected game data structure")
                    # Create an empty standardized result
                    return {'data': {'items': []}}
            else:
                logger.warning("Response does not contain 'data' key")
                return {'data': {'items': []}}
        else:
            # This might be a Cloudflare challenge
            logger.warning(
                "Response is not JSON, possibly a Cloudflare challenge")
            logger.info("Refreshing cookies with Selenium...")

            # Remove the old cookie file
            if os.path.exists('cf_cookies.txt'):
                os.remove('cf_cookies.txt')

            # Run Selenium again to refresh cookies
            subprocess.run(
                ['./venv/bin/python', 'selenium_bc_game.py'], check=True)

            # Try once more with the new cookies
            cookies = get_cloudflare_cookies()
            response = requests.post(
                url, headers=headers, cookies=cookies, json=data)
            response.raise_for_status()

            result = response.json()
            if 'data' in result and 'list' in result['data']:
                games_count = len(result['data']['list'])
                logger.info(
                    f"Successfully fetched {games_count} games on second attempt (list format)")
                return {'data': {'items': result['data']['list']}}
            elif 'data' in result and 'items' in result['data']:
                games_count = len(result['data']['items'])
                logger.info(
                    f"Successfully fetched {games_count} games on second attempt (items format)")
                return result
            else:
                logger.warning(
                    "Response still does not contain expected game data structure")
                return {'data': {'items': []}}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching game history: {e}")
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
