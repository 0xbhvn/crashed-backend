#!/usr/bin/env python3
import json
import random
import time
import datetime
import os
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_game_id(start_id=7900000, range_size=100000):
    """Generate a random game ID in a realistic range."""
    return random.randint(start_id, start_id + range_size)


def generate_crash_point():
    """Generate a realistic crash point value."""
    # Most crash points are low, with occasional high values
    if random.random() < 0.8:
        # 80% chance for a value between 1.00 and 3.00
        return round(random.uniform(1.00, 3.00), 2)
    elif random.random() < 0.95:
        # 15% chance for a value between 3.00 and 10.00
        return round(random.uniform(3.00, 10.00), 2)
    else:
        # 5% chance for a high value between 10.00 and 100.00
        return round(random.uniform(10.00, 100.00), 2)


def generate_timestamp(start_time=None, end_time=None):
    """Generate a realistic timestamp in milliseconds."""
    if not start_time:
        # Default to 1 week ago
        start_time = datetime.datetime.now() - datetime.timedelta(days=7)
    if not end_time:
        # Default to now
        end_time = datetime.datetime.now()

    # Convert to unix timestamp in milliseconds
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    return random.randint(start_ts, end_ts)


def generate_single_game(index=0, with_timestamp=True):
    """Generate data for a single crash game."""
    timestamp = generate_timestamp() if with_timestamp else None
    game = {
        "gameId": generate_game_id(),
        "crashPoint": generate_crash_point(),
        "hash": "0x" + "".join(random.choice("0123456789abcdef") for _ in range(64))
    }

    # Add timestamp if requested
    if with_timestamp:
        game["timestamp"] = timestamp

    return game


def generate_crash_history(count=50, page=1, page_size=50):
    """Generate mock crash history data."""
    # Create a realistic number of total items across pages
    total_items = count if count > page * page_size else page * \
        page_size + random.randint(0, page_size)

    # Create the page of items requested
    items = []
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total_items)

    for i in range(start_index, end_index):
        items.append(generate_single_game(i))

    # Create the full response structure
    data = {
        "data": {
            "items": items,
            "total": total_items,
            "page": page,
            "pageSize": page_size
        },
        "msg": "",
        "code": 200,
        "success": True,
        "timestamp": int(time.time() * 1000),
        "generated": True  # Flag to indicate this is mock data
    }

    return data


def generate_recent_history(count=50):
    """Generate mock recent crash history data."""
    items = []
    for i in range(count):
        items.append(generate_single_game(i, with_timestamp=False))

    # Create the full response structure
    data = {
        "data": items,
        "msg": "",
        "code": 200,
        "success": True,
        "timestamp": int(time.time() * 1000),
        "generated": True  # Flag to indicate this is mock data
    }

    return data


def save_json(data, output_file, pretty=True):
    """Save data to a JSON file."""
    with open(output_file, 'w') as f:
        if pretty:
            json.dump(data, f, indent=2)
        else:
            json.dump(data, f)
    logger.info(f"Saved mock data to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate mock crash game data")
    parser.add_argument("--history", action="store_true",
                        help="Generate crash history data")
    parser.add_argument("--recent", action="store_true",
                        help="Generate recent crash history data")
    parser.add_argument("--count", type=int, default=50,
                        help="Number of items to generate")
    parser.add_argument("--page", type=int, default=1,
                        help="Page number for history data")
    parser.add_argument("--page-size", type=int, default=50,
                        help="Page size for history data")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--pretty", action="store_true",
                        default=True, help="Pretty-print JSON output")

    args = parser.parse_args()

    # If no specific type is requested, generate both
    generate_both = not (args.history or args.recent)

    if args.history or generate_both:
        history_data = generate_crash_history(
            args.count, args.page, args.page_size)
        history_output = args.output if args.output else "crash_history.json"
        save_json(history_data, history_output, args.pretty)

    if args.recent or generate_both:
        recent_data = generate_recent_history(args.count)
        recent_output = args.output if args.output and not generate_both else "recent_history.json"
        save_json(recent_data, recent_output, args.pretty)

    logger.info("Mock data generation complete")


if __name__ == "__main__":
    main()
