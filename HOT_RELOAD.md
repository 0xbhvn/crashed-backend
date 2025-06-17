# Hot Reload Development Setup

This backend now supports hot reload for faster development. When you make changes to your Python files, the server will automatically restart.

## Prerequisites

Hot reload is already installed via `aiohttp-devtools`. If you need to reinstall:

```bash
pip install aiohttp-devtools
```

## Running the Development Server with Hot Reload

### Method 1: Using the Shell Script (Recommended)

```bash
# Basic usage (catchup is skipped by default for faster startup)
./run-dev.sh

# Run with initial catchup (if you need fresh data)
./run-dev.sh --run-catchup

# Enable verbose output
./run-dev.sh --verbose

# Use custom port
./run-dev.sh --port 8080

# Combine options
./run-dev.sh --run-catchup --verbose --port 8080
```

### Method 2: Using adev directly

```bash
# Skip catchup (default)
export SKIP_CATCHUP=true
adev runserver --app-factory create_app --port 8000 dev_server.py

# Run with catchup
export SKIP_CATCHUP=false
adev runserver --app-factory create_app --port 8000 dev_server.py
```

### Method 3: Using adev directly (basic API only)

```bash
export ENVIRONMENT=development
adev runserver --app-factory create_app --port 8000 app_factory.py
```

## Features

The development server includes all production features:

- **Automatic Reload**: The server automatically restarts when you modify any Python file
- **Database Connection**: Full database support if configured
- **Redis Caching**: Redis support if enabled
- **Initial Catchup**: Runs catchup on startup when --run-catchup is used (skipped by default for faster startup)
- **WebSocket Support**: Full WebSocket functionality
- **API Routes**: All API endpoints available
- **Development Mode**: Runs on port 8000 by default
- **Error Display**: Shows detailed error messages in the console
- **File Watching**: Monitors all Python files in the project directory

## Configuration

- Default port: 8000 (in development mode)
- Environment variables work as usual (DATABASE_URL, REDIS_URL, etc.)
- To use a different port: `API_PORT=8080 ./run-dev.sh` or `./run-dev.sh --port 8080`

## What's Different from Production?

- **Polling Disabled**: The development server only runs the API, not the monitoring/polling (always skipped)
- **Catchup Skipped by Default**: Initial catchup is skipped for faster startup (use `--run-catchup` to enable)
- **Hot Reload**: Automatic restart on code changes
- **Development Port**: Uses port 8000 by default instead of 3000
- **Verbose Logging**: More detailed output for debugging

## Default Behavior

For faster development startup, the following are **default**:

- ✅ Skip polling (always)
- ✅ Skip catchup (override with `--run-catchup`)
- ✅ Hot reload enabled
- ✅ Port 8000

This means you can just run `./run-dev.sh` and start coding immediately!

## Normal Production Mode

To run without hot reload (production mode):

```bash
python -m src monitor --skip-polling
```

## Troubleshooting

1. If the server doesn't restart on file changes:
   - Make sure you're editing files within the project directory
   - Check that the file has a `.py` extension
   - Try restarting the dev server

2. If you get import errors:
   - Make sure you're running from the project root directory
   - Check that your virtual environment is activated

3. If port 8000 is already in use:
   - Kill the existing process: `lsof -ti:8000 | xargs kill -9`
   - Or use a different port: `API_PORT=8080 ./run-dev.sh`
