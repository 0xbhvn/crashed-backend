#!/usr/bin/env python3
"""
Redis Cache Management Tool for Crash Monitor.

This script provides utilities to manage the Redis cache for the crashed-backend application.
"""

import argparse
import sys
import os
import time
from urllib.parse import urlparse

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import config
from src.utils.redis import get_redis_client, is_redis_available, setup_redis
from src.utils.redis_keys import set_cache_version, invalidate_specific_analytics_cache


def clear_all_cache():
    """Clear all cache entries by updating the cache version."""
    print("Clearing all cache by updating cache version...")
    old_version = set_cache_version()
    print(f"Cache version updated. All cached data with version {old_version} is now invalid.")
    print("New cache entries will be created as requests come in.")


def clear_specific_pattern(pattern):
    """Clear cache entries matching a specific pattern."""
    print(f"Clearing cache entries matching pattern: {pattern}")
    count = invalidate_specific_analytics_cache(pattern)
    print(f"Deleted {count} cache entries.")


def flush_all_redis():
    """Flush the entire Redis database (WARNING: This deletes ALL data)."""
    print("WARNING: This will delete ALL data in Redis, not just cache!")
    confirm = input("Are you sure you want to flush the entire Redis database? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    try:
        redis = get_redis_client()
        redis.flushdb()
        print("Redis database flushed successfully.")
    except Exception as e:
        print(f"Error flushing Redis: {str(e)}")


def list_cache_keys(pattern="*"):
    """List all cache keys matching a pattern."""
    try:
        redis = get_redis_client()
        keys = redis.keys(pattern)
        
        if not keys:
            print(f"No keys found matching pattern: {pattern}")
            return
        
        print(f"Found {len(keys)} keys matching pattern: {pattern}")
        print("-" * 60)
        
        for key in sorted(keys):
            # Decode key if it's bytes
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            
            # Get TTL
            ttl = redis.ttl(key)
            ttl_str = f"{ttl}s" if ttl > 0 else "no expiry" if ttl == -1 else "expired"
            
            print(f"{key:<50} TTL: {ttl_str}")
            
    except Exception as e:
        print(f"Error listing keys: {str(e)}")


def show_cache_stats():
    """Show Redis cache statistics."""
    try:
        redis = get_redis_client()
        info = redis.info()
        
        print("Redis Cache Statistics")
        print("=" * 60)
        
        # Memory stats
        print(f"Used Memory: {info.get('used_memory_human', 'N/A')}")
        print(f"Peak Memory: {info.get('used_memory_peak_human', 'N/A')}")
        print(f"Memory Fragmentation Ratio: {info.get('mem_fragmentation_ratio', 'N/A')}")
        
        # Key stats
        all_keys = redis.keys("*")
        analytics_keys = redis.keys("analytics:*")
        games_keys = redis.keys("games:*")
        game_keys = redis.keys("game:*")
        
        print(f"\nTotal Keys: {len(all_keys)}")
        print(f"Analytics Keys: {len(analytics_keys)}")
        print(f"Games List Keys: {len(games_keys)}")
        print(f"Game Detail Keys: {len(game_keys)}")
        
        # Connection stats
        print(f"\nConnected Clients: {info.get('connected_clients', 'N/A')}")
        print(f"Total Commands Processed: {info.get('total_commands_processed', 'N/A')}")
        
        # Persistence stats
        print(f"\nLast Save Time: {time.ctime(info.get('rdb_last_save_time', 0))}")
        print(f"AOF Enabled: {'yes' if info.get('aof_enabled', 0) == 1 else 'no'}")
        
    except Exception as e:
        print(f"Error getting cache stats: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Redis Cache Management Tool")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Clear all cache
    clear_parser = subparsers.add_parser("clear", help="Clear cache entries")
    clear_parser.add_argument(
        "--pattern",
        help="Clear only keys matching this pattern (e.g., 'analytics:*')"
    )
    clear_parser.add_argument(
        "--all",
        action="store_true",
        help="Clear all cache by updating cache version"
    )
    
    # Flush database
    flush_parser = subparsers.add_parser(
        "flush",
        help="Flush entire Redis database (WARNING: deletes ALL data)"
    )
    
    # List keys
    list_parser = subparsers.add_parser("list", help="List cache keys")
    list_parser.add_argument(
        "--pattern",
        default="*",
        help="Pattern to match keys (default: '*')"
    )
    
    # Show stats
    stats_parser = subparsers.add_parser("stats", help="Show cache statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup Redis connection
    try:
        setup_redis()
        
        if not is_redis_available():
            print("Error: Redis is not available. Please check your Redis connection.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error connecting to Redis: {str(e)}")
        sys.exit(1)
    
    # Execute command
    if args.command == "clear":
        if args.all:
            clear_all_cache()
        elif args.pattern:
            clear_specific_pattern(args.pattern)
        else:
            print("Please specify --all or --pattern")
            
    elif args.command == "flush":
        flush_all_redis()
        
    elif args.command == "list":
        list_cache_keys(args.pattern)
        
    elif args.command == "stats":
        show_cache_stats()


if __name__ == "__main__":
    main()