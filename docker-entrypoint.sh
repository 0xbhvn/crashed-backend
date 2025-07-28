#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
python -m src.app migrate upgrade

# Start the application with any passed arguments
echo "Starting the application..."
exec "$@"