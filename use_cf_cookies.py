#!/usr/bin/env python3
"""
DEPRECATED: This script is no longer used for accessing BC Game API.

The application now uses a direct POST request to the API without requiring cookies or Cloudflare bypass.
See src/history.py for the new implementation.

This file is kept for reference only.
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
from datetime import datetime, timedelta
import random
import platform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
COOKIE_FILE = 'cf_cookies.txt'
MOCK_DATA_FILE = 'crash_history.json'
API_ENDPOINTS = {
    'history': 'https://bc.game/api/game/support/crash/history',
    'recent': 'https://bc.game/api/game/support/crash/recent/history'
}
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
API_TIMEOUT = 10  # seconds


def get_cloudflare_cookies():
    """Get Cloudflare cookies from the saved file."""
    cookies = {}

    if not os.path.exists(COOKIE_FILE):
        logger.error(f"Cookie file {COOKIE_FILE} not found!")
        return cookies

    # Check cookie file age
    try:
        cookie_age_seconds = datetime.now().timestamp() - os.path.getmtime(COOKIE_FILE)
        cookie_age_hours = cookie_age_seconds / 3600
        logger.info(f"Cookie file age: {cookie_age_hours:.1f} hours old")

        if cookie_age_hours > 24:
            logger.warning(
                f"Cookie file is more than 24 hours old! Cookies may have expired.")
    except Exception as e:
        logger.warning(f"Could not check cookie file age: {e}")

    # Read cookies
    try:
        with open(COOKIE_FILE, 'r') as f:
            for line in f:
                # Skip comment lines
                if line.strip().startswith('#') or not line.strip():
                    continue

                if '=' in line:
                    name, value = line.strip().split('=', 1)
                    cookies[name] = value

        logger.info(f"Loaded {len(cookies)} cookies from {COOKIE_FILE}")

        # Check if we have the key cookies
        if 'cf_clearance' not in cookies:
            logger.warning("Missing critical cookie: cf_clearance")
    except Exception as e:
        logger.error(f"Error reading cookie file: {e}")

    return cookies


def get_headers():
    """Get headers to use for the request."""
    # Default headers with a modern browser User-Agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://bc.game/',
        'DNT': '1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }

    # Try to load custom headers if they exist
    headers_file = 'cf_headers.json'
    if os.path.exists(headers_file):
        try:
            with open(headers_file, 'r') as f:
                custom_headers = json.load(f)
            logger.info(f"Loaded custom headers from {headers_file}")
            # Update with custom headers but keep defaults if not specified
            headers.update(custom_headers)
        except Exception as e:
            logger.warning(f"Error loading headers file: {e}")

    return headers


def make_api_request(endpoint, params=None, cookies=None, headers=None):
    """Make an API request with appropriate error handling and retries."""
    if not cookies:
        cookies = get_cloudflare_cookies()

    if not headers:
        headers = get_headers()

    if not params:
        params = {}

    # Add cache-busting query parameter
    params['_'] = int(time.time() * 1000)

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Making API request to {endpoint} (attempt {attempt+1}/{MAX_RETRIES})")

            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=API_TIMEOUT
            )

            # Check if successful
            if response.status_code == 200:
                try:
                    data = response.json()

                    # Check if we actually got game data
                    if 'data' in data:
                        logger.info(f"API request successful")
                        return True, data
                    else:
                        logger.warning(
                            f"API response doesn't contain expected data structure")
                        # Still return as successful but with warning
                        return True, data
                except json.JSONDecodeError:
                    # Check if it's a Cloudflare challenge
                    if "Just a moment" in response.text or "Checking if the site connection is secure" in response.text:
                        logger.error(
                            "Received Cloudflare challenge instead of JSON data")
                        # Save the response for debugging
                        with open('cloudflare_challenge.html', 'w') as f:
                            f.write(response.text)
                        logger.info(
                            "Saved Cloudflare challenge HTML to cloudflare_challenge.html")
                    else:
                        logger.error(
                            f"Response is not valid JSON: {response.text[:100]}...")

            else:
                logger.error(
                    f"API request failed with status code {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response content: {response.text[:200]}...")

            # Wait before retrying, with exponential backoff
            if attempt < MAX_RETRIES - 1:
                retry_delay = RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")

            # Wait before retrying, with exponential backoff
            if attempt < MAX_RETRIES - 1:
                retry_delay = RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

    # All attempts failed
    return False, None


def try_shell_script_fallback(endpoint_key, params=None):
    """Try the shell script as a fallback method."""
    try:
        # Get the appropriate shell script command
        if endpoint_key == 'history':
            page = params.get('page', 1) if params else 1
            page_size = params.get('size', 50) if params else 50
            logger.info(
                f"Trying shell script fallback for history (page={page}, size={page_size})")
            # Use shell script to get the history
            cmd = ['./get_crash_history.sh', str(page), str(page_size)]
        elif endpoint_key == 'recent':
            logger.info("Trying shell script fallback for recent history")
            # Use shell script to get recent history
            cmd = ['./get_recent_history.sh']
        else:
            logger.error(f"Unknown endpoint key: {endpoint_key}")
            return False, None

        # Execute the shell script
        logger.info(f"Executing command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Shell script failed with code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            return False, None

        # Try to parse the output as JSON
        try:
            data = json.loads(result.stdout)
            logger.info(f"Successfully retrieved data using shell script")
            return True, data
        except json.JSONDecodeError:
            logger.error("Shell script output is not valid JSON")
            logger.error(f"Output: {result.stdout[:200]}...")
            return False, None

    except Exception as e:
        logger.error(f"Error running shell script: {e}")
        return False, None


def load_mock_data():
    """Load mock data as a last resort."""
    try:
        if os.path.exists(MOCK_DATA_FILE):
            with open(MOCK_DATA_FILE, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded mock data from {MOCK_DATA_FILE}")
            return True, data
        else:
            logger.error(f"Mock data file {MOCK_DATA_FILE} not found")
            return False, None
    except Exception as e:
        logger.error(f"Error loading mock data: {e}")
        return False, None


def fetch_crash_data(endpoint_key, params=None):
    """
    Fetch crash data using available methods, with fallbacks.

    Args:
        endpoint_key: Key from API_ENDPOINTS ('history' or 'recent')
        params: Dictionary of query parameters

    Returns:
        Tuple of (success, data)
    """
    if endpoint_key not in API_ENDPOINTS:
        logger.error(f"Unknown endpoint key: {endpoint_key}")
        return False, None

    endpoint = API_ENDPOINTS[endpoint_key]

    # Try direct API request first
    logger.info(f"Attempting direct API request to {endpoint_key} endpoint")
    success, data = make_api_request(endpoint, params)

    if success:
        return True, data

    # If API request failed, try shell script fallback
    logger.info(f"Direct API request failed, trying shell script fallback")
    success, data = try_shell_script_fallback(endpoint_key, params)

    if success:
        return True, data

    # If shell script also failed, use mock data as last resort
    logger.warning(
        f"Shell script fallback failed, using mock data as last resort")
    return load_mock_data()


def get_crash_history(page=1, page_size=50):
    """
    DEPRECATED: This function is no longer used.

    The application now uses a direct API call in src/history.py.
    This function is kept for backward compatibility but will just log a warning.
    """
    logger.warning(
        "This method is deprecated. The application now uses a direct API call in src/history.py"
    )
    return []


def get_recent_history():
    """Get recent crash game history using the best available method."""
    success, data = fetch_crash_data('recent')

    if success and data and 'data' in data:
        items = data['data']
        logger.info(
            f"Successfully retrieved {len(items)} recent crash game items")
        return items
    else:
        logger.error("Failed to retrieve recent crash game history")
        return []


def fetch_game_history(page=1, page_size=50, output_file=None):
    """
    Legacy compatibility function for older code.
    Maps to get_crash_history with the correct parameters.
    """
    logger.info(
        f"Legacy fetch_game_history called with page={page}, size={page_size}")

    # Try to get real data first
    items = get_crash_history(page=page, page_size=page_size)

    # If real data retrieval failed, try to load mock data directly
    if not items:
        logger.warning(
            "Failed to get real data, trying to load mock data directly")
        try:
            if os.path.exists(MOCK_DATA_FILE):
                with open(MOCK_DATA_FILE, 'r') as f:
                    mock_data = json.load(f)

                if 'data' in mock_data and 'items' in mock_data['data']:
                    logger.info(
                        f"Successfully loaded {len(mock_data['data']['items'])} items from mock data")

                    # If mock data has proper structure, return it directly
                    if 'page' in mock_data['data'] and 'pageSize' in mock_data['data']:
                        logger.info(
                            "Mock data has proper structure, returning directly")

                        # Save to output file if specified
                        if output_file:
                            try:
                                with open(output_file, 'w') as f:
                                    json.dump(mock_data, f, indent=2)
                                logger.info(
                                    f"Saved mock data to {output_file}")
                            except Exception as e:
                                logger.error(
                                    f"Error saving mock data to {output_file}: {e}")

                        return mock_data

                    # Otherwise extract items and format properly
                    items = mock_data['data']['items']

                    # If page size doesn't match, slice the items accordingly
                    start_idx = (page - 1) * page_size
                    end_idx = min(start_idx + page_size, len(items))

                    if start_idx < len(items):
                        items = items[start_idx:end_idx]
                        logger.info(
                            f"Sliced mock data to {len(items)} items for page {page}")
                    else:
                        logger.warning(
                            f"Page {page} exceeds available mock data, returning empty list")
                        items = []
        except Exception as e:
            logger.error(f"Error loading mock data: {e}")
            items = []

    # Format in the expected structure
    result = {
        'data': {
            'items': items if items else [],
            'page': page,
            'pageSize': page_size,
            'total': len(items) if items else 0
        },
        'success': True,
        'timestamp': int(time.time() * 1000),
        'msg': '',
        'code': 200
    }

    # Save to output file if specified
    if output_file:
        try:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Saved game history to {output_file}")
        except Exception as e:
            logger.error(f"Error saving game history to {output_file}: {e}")

    return result


def main():
    """Test function to verify cookie functionality."""
    logger.info("Testing BC Game API access...")

    # Try to get crash history
    history = get_crash_history(page=1, page_size=10)
    if history:
        logger.info(f"Successfully retrieved {len(history)} history items")
        logger.info(f"First item: {json.dumps(history[0], indent=2)}")
    else:
        logger.error("Failed to retrieve crash history")

    # Try to get recent history
    recent = get_recent_history()
    if recent:
        logger.info(f"Successfully retrieved {len(recent)} recent items")
        logger.info(f"First item: {json.dumps(recent[0], indent=2)}")
    else:
        logger.error("Failed to retrieve recent history")


if __name__ == "__main__":
    print("DEPRECATED: This script is no longer used for accessing BC Game API.")
    print("The application now uses a direct POST request to the API without requiring cookies.")
    print("See src/history.py for the new implementation.")
