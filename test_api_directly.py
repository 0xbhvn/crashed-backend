#!/usr/bin/env python3
import os
import json
import requests
import logging
import sys
import argparse
from datetime import datetime
import time
import traceback
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_cookies():
    """Get Cloudflare cookies from the saved file."""
    cookie_file = 'cf_cookies.txt'
    cookies = {}

    if not os.path.exists(cookie_file):
        logger.error(f"Cookie file {cookie_file} not found!")
        return cookies

    # Check cookie file age
    try:
        cookie_age_seconds = datetime.now().timestamp() - os.path.getmtime(cookie_file)
        cookie_age_hours = cookie_age_seconds / 3600
        logger.info(f"Cookie file age: {cookie_age_hours:.1f} hours old")

        if cookie_age_hours > 24:
            logger.warning(
                f"Cookie file is more than 24 hours old! Cookies may have expired.")
    except Exception as e:
        logger.warning(f"Could not check cookie file age: {e}")

    # Read cookies
    try:
        with open(cookie_file, 'r') as f:
            for line in f:
                # Skip comment lines
                if line.strip().startswith('#') or not line.strip():
                    continue

                if '=' in line:
                    name, value = line.strip().split('=', 1)
                    cookies[name] = value

        logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")

        # Check if we have the key cookies
        if 'cf_clearance' not in cookies:
            logger.warning("Missing critical cookie: cf_clearance")
    except Exception as e:
        logger.error(f"Error reading cookie file: {e}")

    return cookies


def get_headers(verbose=False):
    """Get headers to use for the request."""
    # Default headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://bc.game/',
        'DNT': '1',
        'Origin': 'https://bc.game',
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
            headers.update(custom_headers)
        except Exception as e:
            logger.warning(f"Error loading headers file: {e}")

    if verbose:
        logger.info(f"Using headers: {json.dumps(headers, indent=2)}")

    return headers


def get_network_info():
    """Get network information for debugging."""
    info = {}

    try:
        # Get hostname
        info['hostname'] = socket.gethostname()

        # Try to get IP address
        try:
            info['ip'] = socket.gethostbyname(socket.gethostname())
        except Exception as e:
            info['ip'] = f"Error: {e}"

        # Check DNS resolution for BC Game domains
        domains = ['bc.game', 'www.bc.game']
        dns_results = {}

        for domain in domains:
            try:
                ip = socket.gethostbyname(domain)
                dns_results[domain] = ip
            except Exception as e:
                dns_results[domain] = f"Error: {e}"

        info['dns_resolution'] = dns_results

        # Check connectivity
        connections = {}
        for domain in domains:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((domain, 443))
                connections[domain] = "Success" if result == 0 else f"Failed (code: {result})"
                sock.close()
            except Exception as e:
                connections[domain] = f"Error: {e}"

        info['connections'] = connections

    except Exception as e:
        info['error'] = str(e)

    return info


def make_api_request(url, cookies, headers, params=None, verbose=False, output_dir=None):
    """Make an API request with detailed logging."""
    if params is None:
        params = {}

    # Add cache busting parameter
    params['_'] = int(time.time() * 1000)

    # Create output directory if needed
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get network info
    if verbose:
        network_info = get_network_info()
        logger.info(
            f"Network information: {json.dumps(network_info, indent=2)}")

    # Log verbose request info
    if verbose:
        logger.info(f"Making request to: {url}")
        logger.info(f"With params: {params}")
        logger.info(f"Using {len(cookies)} cookies")
        if cookies:
            # Only show first few chars of cookie values for security
            safe_cookies = {k: f"{v[:10]}..." for k, v in cookies.items()}
            logger.info(f"Cookies: {safe_cookies}")

    try:
        # Make the request
        start_time = time.time()
        response = requests.get(
            url,
            params=params,
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        elapsed_time = time.time() - start_time

        # Log response details
        logger.info(
            f"Response status code: {response.status_code} (in {elapsed_time:.2f}s)")

        if verbose:
            logger.info(f"Response headers: {dict(response.headers)}")

        # Save the response if output_dir was provided
        if output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save response details
            response_info = {
                'url': url,
                'method': 'GET',
                'params': params,
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'elapsed_seconds': elapsed_time,
                'timestamp': datetime.now().isoformat(),
            }

            with open(f"{output_dir}/response_info_{timestamp}.json", 'w') as f:
                json.dump(response_info, f, indent=2)

            # Save response content
            if response.status_code == 200:
                try:
                    # If it's JSON, save as JSON
                    json_data = response.json()
                    with open(f"{output_dir}/response_data_{timestamp}.json", 'w') as f:
                        json.dump(json_data, f, indent=2)

                    # Return the response data
                    return True, json_data
                except json.JSONDecodeError:
                    # If not JSON, save as text
                    with open(f"{output_dir}/response_text_{timestamp}.txt", 'w') as f:
                        f.write(response.text)

                    # Check if it's a Cloudflare challenge
                    if "Just a moment" in response.text or "challenge" in response.text:
                        logger.error(
                            "Received Cloudflare challenge instead of JSON")
                        return False, {"error": "Cloudflare challenge"}

                    return False, {"error": "Response is not valid JSON"}
            else:
                # For non-200 responses, save the response text
                with open(f"{output_dir}/response_error_{timestamp}.txt", 'w') as f:
                    f.write(response.text)

                return False, {"error": f"HTTP {response.status_code}"}

        # If no output_dir, process the response in memory
        if response.status_code == 200:
            try:
                json_data = response.json()
                if verbose:
                    logger.info(
                        f"Response data (sample): {json.dumps(json_data)[:200]}...")
                return True, json_data
            except json.JSONDecodeError:
                logger.error("Response is not valid JSON")

                # Check if it's a Cloudflare challenge
                if "Just a moment" in response.text or "challenge" in response.text:
                    logger.error(
                        "Received Cloudflare challenge instead of JSON")
                    if verbose:
                        logger.info(
                            f"Response preview: {response.text[:500]}...")
                    return False, {"error": "Cloudflare challenge"}

                if verbose:
                    logger.info(f"Response preview: {response.text[:500]}...")

                return False, {"error": "Response is not valid JSON"}
        else:
            logger.error(
                f"Request failed with status code {response.status_code}")
            if verbose:
                logger.info(f"Response preview: {response.text[:500]}...")

            return False, {"error": f"HTTP {response.status_code}"}

    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        if verbose:
            logger.error(traceback.format_exc())

        return False, {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Test BC Game API directly with detailed diagnostics")
    parser.add_argument("--url", default="https://bc.game/api/game/support/crash/history",
                        help="API URL to test (default: crash history)")
    parser.add_argument("--page", type=int, default=1,
                        help="Page number for paginated APIs")
    parser.add_argument("--size", type=int, default=10,
                        help="Page size for paginated APIs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    parser.add_argument(
        "--output", "-o", help="Directory to save response files")
    parser.add_argument("--repeat", "-r", type=int, default=1,
                        help="Number of times to repeat the request (with delay)")
    parser.add_argument("--delay", "-d", type=float, default=2.0,
                        help="Delay between repeated requests in seconds")

    args = parser.parse_args()

    cookies = get_cookies()
    headers = get_headers(verbose=args.verbose)

    params = {
        "page": args.page,
        "size": args.size
    }

    logger.info(f"Starting API test with {args.repeat} request(s)...")

    success_count = 0

    for i in range(args.repeat):
        if i > 0:
            logger.info(f"Waiting {args.delay} seconds before next request...")
            time.sleep(args.delay)

        logger.info(f"Making request {i+1}/{args.repeat}...")
        success, data = make_api_request(
            args.url,
            cookies,
            headers,
            params=params,
            verbose=args.verbose,
            output_dir=args.output
        )

        if success:
            success_count += 1

            # If it's crash history, count items
            if 'data' in data and 'items' in data['data']:
                items_count = len(data['data']['items'])
                logger.info(f"Successfully retrieved {items_count} items")

                # Print first item as sample
                if items_count > 0 and args.verbose:
                    logger.info(
                        f"First item: {json.dumps(data['data']['items'][0], indent=2)}")
            else:
                logger.info(
                    "Request successful but response format not recognized")

    # Summary
    if args.repeat > 1:
        logger.info(
            f"Summary: {success_count}/{args.repeat} requests successful ({success_count/args.repeat*100:.1f}%)")

    if success_count > 0:
        return 0
    else:
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
