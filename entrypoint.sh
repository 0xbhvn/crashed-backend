#!/bin/bash
set -e

echo "========================================"
echo "Starting BC Game Crash Monitor"
echo "========================================"
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Environment variables:"
env | grep -v "PATH\|LS_COLORS\|_" | sort

# Add diagnostic info
echo ""
echo "---------- System Info ----------"
echo "Memory: $(free -h)"
echo "Disk space: $(df -h)"
echo "Number of CPUs: $(nproc)"
echo "Hostname: $(hostname)"
echo "-------------------------------"
echo ""

# Run database migrations
echo "Running database migrations..."
python -m src migrate upgrade --revision head

# Check if migrations completed successfully
if [ $? -ne 0 ]; then
  echo "ERROR: Database migrations failed!"
  # Try to diagnose database issues
  echo "Checking database connection..."
  if [ -n "$DATABASE_URL" ]; then
    echo "DATABASE_URL is set"
  else
    echo "ERROR: DATABASE_URL is not set!"
  fi
  exit 1
fi

echo "Migrations completed successfully"

# Start the application with diagnostics in case of failure
echo "Starting application with observer in headless mode..."
python -m src monitor --skip-catchup --with-observer --headless &
PID=$!

# Wait for 10 seconds to see if the app starts properly
sleep 10

# Check if the process is still running
if ps -p $PID > /dev/null; then
  echo "Application started successfully with PID $PID"
  # Check if health check server is listening
  if netstat -tulpn 2>/dev/null | grep -q ":8080"; then
    echo "Health check server listening on port 8080"
  else
    echo "WARNING: Health check server not detected on port 8080!"
  fi
  
  # Check if API server is listening
  if netstat -tulpn 2>/dev/null | grep -q ":3000"; then
    echo "API server listening on port 3000"
  else
    echo "WARNING: API server not detected on port 3000!"
  fi
else
  echo "ERROR: Application failed to start!"
  echo "Checking for Python error logs:"
  cat /tmp/app_error.log 2>/dev/null || echo "No error log found"
fi

# Wait for the application to finish or be terminated
wait $PID 