import random
import json
import time
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger(__name__)


def generate_crash_point():
    """Generate a realistic crash point value"""
    # Generate based on realistic BC Game algorithm
    # Most values between 1.0 and 2.0, with decreasing probability for higher values
    r = random.random()
    if r < 0.7:  # 70% chance for common values
        return round(random.uniform(1.0, 2.0), 2)
    elif r < 0.9:  # 20% chance for medium values
        return round(random.uniform(2.0, 5.0), 2)
    elif r < 0.98:  # 8% chance for high values
        return round(random.uniform(5.0, 20.0), 2)
    else:  # 2% chance for rare high values
        return round(random.uniform(20.0, 100.0), 2)


def generate_game_id():
    """Generate a unique game ID similar to BC Game format"""
    return ''.join(random.choices('0123456789abcdef', k=24))


def generate_timestamp(page: int):
    """Generate a timestamp based on the page (older for higher pages)"""
    # Current time minus offset based on page number
    offset = page * 50 * 3 * 60  # Approx 3 minutes per game
    base_time = datetime.now() - timedelta(seconds=offset)
    return int(base_time.timestamp() * 1000)


def generate_mock_game(page: int, index: int):
    """Generate a single mock game with realistic data"""
    crash_point = generate_crash_point()
    game_id = generate_game_id()
    # Generate timestamp with variation
    timestamp = generate_timestamp(page) - (index * random.randint(150, 250))

    return {
        "id": game_id,
        "gameId": "crash",
        "crashPoint": str(crash_point),
        "createdAt": timestamp,
        "hash": "".join(random.choices('0123456789abcdef', k=64)),
        "seed": "".join(random.choices('0123456789abcdef', k=64)),
        "nonce": random.randint(1000000, 9999999)
    }


def generate_mock_history(page: int = 1, items_count: int = 20) -> Dict[str, Any]:
    """
    Generate mock crash history data for testing purposes.

    Args:
        page: The page number
        items_count: Number of items to generate (default: 20)

    Returns:
        Dictionary containing mock history data
    """
    logger.info(
        f"Generating mock game history for page {page} with {items_count} items")

    games = []
    for i in range(items_count):
        games.append(generate_mock_game(page, i))

    # Return in the format expected by the application
    return {
        "data": {
            "list": games
        }
    }


def save_mock_history(page: int = 1, items_count: int = 20, output_path: str = "crash_history.json"):
    """
    Generate and save mock history data to a file.

    Args:
        page: The page number
        items_count: Number of items to generate (default: 20)
        output_path: Path to save the file
    """
    mock_data = generate_mock_history(page, items_count)

    with open(output_path, 'w') as f:
        json.dump(mock_data, f, indent=2)

    logger.info(
        f"Saved mock history data with {items_count} games to {output_path}")
    return mock_data


if __name__ == "__main__":
    # Get page size from environment variable or use default
    page_size = int(os.environ.get('PAGE_SIZE', '50'))
    output_path = os.environ.get('OUTPUT_PATH', 'crash_history.json')

    # Save mock history with the specified page size
    save_mock_history(1, page_size, output_path)
    print(
        f"Mock data generated and saved to {output_path} with {page_size} games")
