#!/usr/bin/env python3
"""
Test script for the updated BC Game API method.
This script tests the direct API call to BC Game without cookies.
"""

import aiohttp
import asyncio
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_bc_game_api(page=1, page_size=10):
    """Test the BC Game API using the new approach."""
    try:
        logger.info(f"Testing BC Game API: page={page}, page_size={page_size}")

        url = "https://bc.game/api/game/bet/multi/history"

        # Prepare JSON payload
        payload = {
            "gameUrl": "crash",
            "page": page,
            "pageSize": page_size
        }

        # Set standard headers (no cookies needed)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Sec-Fetch-Site": "same-origin",
            "Accept-Language": "en",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Mode": "cors",
            "Origin": "https://bc.game",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
            "Referer": "https://bc.game/game/crash",
            "Sec-Fetch-Dest": "empty"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as response:
                logger.info(f"Response status: {response.status}")

                if response.status != 200:
                    logger.error(
                        f"API request failed with status code {response.status}")
                    return False

                data = await response.json()
                logger.info(
                    f"Response received with format: {list(data.keys())}")

                # Process the response data to extract crash games
                if 'data' in data and 'list' in data['data']:
                    game_list = data['data']['list']
                    logger.info(
                        f"Successfully retrieved {len(game_list)} games from BC.GAME API")

                    # Extract crash games
                    games = []
                    for game in game_list:
                        try:
                            game_id = game.get('gameId', '')
                            # Game details are stored as a JSON string, need to parse it
                            game_detail_str = game.get('gameDetail', '{}')
                            game_detail = json.loads(game_detail_str)

                            # Extract fields from game_detail
                            crash_point = float(game_detail.get('rate', 1.0))
                            hash_value = game_detail.get('hash', '')
                            end_time = game_detail.get('endTime', 0)

                            # Convert timestamp to ISO format
                            if end_time:
                                created_at = datetime.fromtimestamp(
                                    end_time / 1000).isoformat()
                            else:
                                created_at = datetime.now().isoformat()

                            game_data = {
                                'id': game_id,
                                'created_at': created_at,
                                'hash': hash_value,
                                'crash_point': crash_point
                            }
                            games.append(game_data)

                        except Exception as e:
                            logger.error(
                                f"Error processing game {game.get('gameId', 'unknown')}: {e}")

                    logger.info(
                        f"Extracted {len(games)} crash games from response")

                    # Print the first game details
                    if games:
                        logger.info(
                            f"First game details: {json.dumps(games[0], indent=2)}")

                    # Save the games to a file for reference
                    with open('crash_games_test.json', 'w') as f:
                        json.dump(games, f, indent=2)
                    logger.info("Saved games to crash_games_test.json")

                    return True
                else:
                    logger.error(f"Unexpected API response format: {data}")
                    return False

    except Exception as e:
        logger.error(f"Error testing BC Game API: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def main():
    """Main function to run the test."""
    logger.info("Starting BC Game API test")

    # Test with default parameters
    success = await test_bc_game_api()

    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!")

if __name__ == "__main__":
    asyncio.run(main())
