#!/usr/bin/env python3
"""
Script to verify missing crash games using the BC.Game verification page.

This script:
1. Takes a hash value and number of games as input
2. Uses Playwright to access the BC.Game verification page
3. Submits the hash and number of games for verification
4. Extracts the verification results
5. Exports the results to a CSV file
"""

import os
import asyncio
import csv
import argparse
from datetime import datetime
from playwright.async_api import async_playwright
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()


async def verify_games(hash_value, num_games):
    """
    Verify games using the BC.Game verification page.

    Args:
        hash_value (str): The hash value to start verification from
        num_games (int): Number of games to verify

    Returns:
        list: List of dictionaries containing game data
    """
    results = []

    print(f"Verifying {num_games} games with hash {hash_value}")

    async with async_playwright() as p:
        # Set to True for production
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to the verification page
        await page.goto("https://bcgame-project.github.io/verify/crash.html")

        # Fill in the hash value
        await page.fill('//*[@id="game_hash_input"]', hash_value)

        # Fill in the number of games
        await page.fill('//*[@id="game_amount_input"]', str(num_games))

        # Click the verify button
        await page.click('//*[@id="game_verify_submit"]')

        # Wait for the table to be populated
        await page.wait_for_selector('//*[@id="game_verify_table"]/tr')

        # Take a screenshot for debugging
        await page.screenshot(path="verification_result.png")

        # Extract data from the table
        rows = await page.query_selector_all('//*[@id="game_verify_table"]/tr')

        print(f"Found {len(rows)} verified games")

        for i, row in enumerate(rows):
            cells = await row.query_selector_all('td')

            if len(cells) >= 2:
                game_hash = await cells[0].inner_text()
                bust_value = await cells[1].inner_text()

                # Create a game data entry
                game_data = {
                    'game_index': i,
                    'hash_value': game_hash,
                    'bust_value': float(bust_value),
                    'verified_at': datetime.now().isoformat()
                }

                results.append(game_data)

        await browser.close()

    return results


def save_to_csv(results, output_file):
    """
    Save the verification results to a CSV file.

    Args:
        results (list): List of game data dictionaries
        output_file (str): Path to the output CSV file
    """
    if not results:
        print("No results to save")
        return

    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = results[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)

    print(f"Saved {len(results)} verified games to {output_file}")


async def main():
    parser = argparse.ArgumentParser(
        description='Verify crash games using BC.Game verification page')
    parser.add_argument('hash', help='Hash value to start verification from')
    parser.add_argument('num_games', type=int,
                        help='Number of games to verify')
    parser.add_argument('--output', '-o', default=None, help='Output CSV file')

    args = parser.parse_args()

    # Generate default output filename if not provided
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"verified_games_{timestamp}.csv"

    # Verify games
    results = await verify_games(args.hash, args.num_games)

    # Save results to CSV
    save_to_csv(results, args.output)

if __name__ == "__main__":
    asyncio.run(main())
