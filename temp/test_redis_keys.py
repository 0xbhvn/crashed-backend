#!/usr/bin/env python
"""
Test script for Redis key generation functions.
"""

from src.utils.redis import (
    generate_games_key,
    generate_game_detail_key,
    generate_analytics_key,
    generate_hash_key,
    get_cache_version,
    set_cache_version
)
import sys
import os
import json

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.abspath("."))

# Import Redis utilities


def main():
    """Test Redis key generation functions."""
    # Print current cache version
    print(f"Current cache version: {get_cache_version()}")

    # Test games list key generation
    games_key = generate_games_key(
        page=1, per_page=10, timezone="America/New_York")
    print(f"\nGames list key: {games_key}")

    # Test game detail key generation
    game_detail_key = generate_game_detail_key(game_id="12345")
    print(f"Game detail key: {game_detail_key}")

    # Test analytics key generation
    analytics_params = {
        "min": 2.0,
        "interval": 10,
        "hours": 24
    }
    analytics_key = generate_analytics_key(
        endpoint="interval", params=analytics_params)
    print(f"\nAnalytics key: {analytics_key}")

    # Test hash key generation for complex data
    complex_data = {
        "filters": {
            "min_crash_point": 2.0,
            "max_crash_point": 10.0,
            "game_ids": [12345, 67890, 54321]
        },
        "sort": {
            "field": "crash_point",
            "direction": "desc"
        },
        "pagination": {
            "page": 1,
            "per_page": 10
        }
    }
    hash_key = generate_hash_key(complex_data)
    print(f"\nHash key for complex data: {hash_key}")

    # Test cache version updating
    new_version = set_cache_version()
    print(f"\nNew cache version: {new_version}")

    # Show how keys change with new version
    new_games_key = generate_games_key(
        page=1, per_page=10, timezone="America/New_York")
    print(f"Games list key (new version): {new_games_key}")


if __name__ == "__main__":
    main()
