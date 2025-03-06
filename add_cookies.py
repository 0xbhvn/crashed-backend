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
from datetime import datetime
import requests
import getpass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_environment_info():
    """Get information about the current environment."""
    info = {}
    try:
        # Get hostname
        try:
            hostname = socket.gethostname()
            info["hostname"] = hostname
        except Exception as e:
            info["hostname"] = f"Error getting hostname: {str(e)}"

        # Try to get IP address (may fail in some environments)
        try:
            ip = socket.gethostbyname(socket.gethostname())
            info["ip"] = ip
        except Exception as e:
            info["ip"] = "Unknown"

        # Other environment info that should be safe
        info.update({
            "platform": platform.platform(),
            "python": platform.python_version(),
            "is_container": os.environ.get('CONTAINER', '') == 'true' or os.environ.get('DOCKER', '') == 'true'
        })
    except Exception as e:
        info = {
            "error": f"Error getting environment info: {str(e)}",
            "platform": platform.platform(),
            "python": platform.python_version(),
        }

    return info


def print_instructions():
    """Print instructions for obtaining Cloudflare cookies."""
    instructions = """
=================================================
    BC GAME CLOUDFLARE COOKIE SETUP UTILITY
=================================================

This utility will help you add Cloudflare cookies needed to access the BC GAME API.

To get these cookies:

1. Open Chrome or Firefox (Chrome preferred)
2. Navigate to https://bc.game
3. Make sure you can access the site (pass any Cloudflare challenges)
4. Open Developer Tools (F12 or Right-click > Inspect)
5. Go to the "Application" tab in Chrome or "Storage" tab in Firefox
6. Under "Cookies", click on "https://bc.game"
7. Look for these cookies:
   - cf_clearance: This is essential
   - __cf_bm: This is also important

For each cookie:
1. Double-click the value to select it all
2. Copy the value (Ctrl+C or Command+C)
3. Paste it when prompted by this script

These cookies are tied to your browser fingerprint and may expire.
If API access stops working, you'll need to run this script again.

=================================================
"""
    print(instructions)


def save_cookies(cookies):
    """Save Cloudflare cookies to a file."""
    try:
        with open('cf_cookies.txt', 'w') as f:
            for name, value in cookies.items():
                f.write(f"{name}={value}\n")
        logger.info(f"Cookies saved successfully to cf_cookies.txt")
        return True
    except Exception as e:
        logger.error(f"Error saving cookies: {e}")
        return False


def test_cookies(cookies):
    """Test if the Cloudflare cookies are working."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://bc.game",
    }

    try:
        logger.info("Testing cookies...")
        url = "https://bc.game/api/game/support/crash/history"

        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            timeout=10
        )

        logger.info(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            try:
                data = response.json()
                if 'data' in data and 'items' in data['data']:
                    games_count = len(data['data']['items'])
                    logger.info(f"Success! Retrieved {games_count} games")

                    # Save a sample of the data for debugging/verification
                    sample_data = {
                        'response_code': response.status_code,
                        'games_count': games_count,
                        'sample': data['data']['items'][:2] if games_count > 0 else [],
                        'timestamp': datetime.now().isoformat(),
                        'environment': get_environment_info()
                    }

                    with open('cookie_test_sample.json', 'w') as f:
                        json.dump(sample_data, f, indent=2)
                    logger.info("Saved sample data to cookie_test_sample.json")

                    return True
                else:
                    logger.error(f"Invalid response format: {data}")
            except json.JSONDecodeError:
                logger.error("Response is not valid JSON")
                if "Cloudflare" in response.text or "challenge" in response.text:
                    logger.error(
                        "Received Cloudflare challenge - cookies are invalid")
                    with open('cloudflare_response.html', 'w') as f:
                        f.write(response.text)
                    logger.info(
                        "Saved Cloudflare response to cloudflare_response.html")
        else:
            logger.error(f"Error response: {response.status_code}")
            if response.status_code == 403:
                logger.error(
                    "Forbidden (403) - Cookies are invalid or expired")

        return False
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return False


def prompt_for_cookie(cookie_name):
    """Prompt the user for a specific cookie value with improved UX."""
    print(f"\nEnter {cookie_name} cookie value:")
    print(f"(This cookie can be found in your browser's developer tools under Application > Cookies > bc.game)")

    # Use getpass to handle long inputs better, though it will hide input
    # This helps with very long cookie values that might span multiple lines
    value = getpass.getpass(
        f"Paste {cookie_name} value (input will be hidden for security): ")

    # Clean up the value (remove extra spaces, quotes, etc.)
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]

    return value


def main():
    """Main function to add cookies."""
    try:
        clear_screen()
        print_instructions()

        # Get environment info for logging
        env_info = get_environment_info()
        logger.info(f"Environment: {json.dumps(env_info, indent=2)}")

        # Get cookies from user
        cookies = {}

        # Get cf_clearance cookie
        cf_clearance = prompt_for_cookie("cf_clearance")
        if cf_clearance:
            cookies["cf_clearance"] = cf_clearance
        else:
            logger.error("cf_clearance cookie is required!")
            return False

        # Get __cf_bm cookie (optional but helpful)
        cf_bm = prompt_for_cookie("__cf_bm")
        if cf_bm:
            cookies["__cf_bm"] = cf_bm
        else:
            logger.warning("__cf_bm cookie not provided (may still work)")

        # Save cookies to file
        if save_cookies(cookies):
            # Test the cookies
            if test_cookies(cookies):
                print("\n✅ Success! Cookies are working and have been saved.")
                print("You should now be able to access the BC Game API.")
                return True
            else:
                print("\n❌ Cookies were saved, but they don't seem to be working.")
                print("Please check that you copied them correctly.")
                return False
        else:
            print("\n❌ Failed to save cookies.")
            return False

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return False
    except Exception as e:
        logger.error(f"Error adding cookies: {e}")
        print(f"\n❌ An error occurred: {e}")
        return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
