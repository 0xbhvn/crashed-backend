# Crash Monitor

A Python application for monitoring crash game values, calculating crash points, and storing results in a database.

## Features

- Real-time monitoring of crash results
- Historical data catchup functionality
- Crash point calculation and verification
- Database storage of game results
- REST API for accessing crash data
- Configurable logging and monitoring settings
- Command-line interface for different operations

## Project Structure

```text
src/
├── __init__.py        # Package initialization
├── __main__.py        # Entry point when run as a module
├── app.py             # Main application entry point
├── config.py          # Configuration settings
├── history.py         # Crash monitor implementation
├── api/               # API module
│   ├── __init__.py    # API module initialization
│   ├── routes.py      # API route handlers
│   ├── utils.py       # API utility functions
│   └── websocket.py   # WebSocket functionality
├── db/                # Database module
│   ├── __init__.py    # Database module initialization
│   ├── engine.py      # Database engine and connection
│   ├── models.py      # SQLAlchemy models
│   └── operations.py  # Database operations
└── utils/             # Utility modules
    ├── __init__.py    # Utility module initialization
    ├── api.py         # API interaction utilities
    ├── env.py         # Environment variable utilities
    └── logging.py     # Logging utilities
```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/bc-game-crash-monitor.git
   cd bc-game-crash-monitor
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables (see Configuration section)

## Configuration

The application can be configured using environment variables:

### Application Environment
- `ENVIRONMENT`: Set to 'development' or 'production' to determine environment-specific settings (default: empty/production)
  - In development mode, API server runs on port 8000 by default
  - In production mode, API server runs on port 3000 by default

### API Settings
- `API_BASE_URL`: Base URL for the game API (default: '[https://example.com](https://example.com)')
- `API_HISTORY_ENDPOINT`: API endpoint for crash history (default: '/api/crash/games/history')
- `GAME_URL`: Game URL path (default: '/game/crash')
- `PAGE_SIZE`: Number of games per page in API requests (default: 50)
- `API_PORT`: Port for the REST API server (default: 8000 in development, 3000 in production)
- `HEALTH_PORT`: Port for the health check server (default: 8080)

### Authentication & Calculation Settings

- `BC_GAME_SALT`: Salt value for crash calculation (required for accurate calculations)

### Monitoring Settings

- `POLL_INTERVAL`: Interval in seconds between API polls (default: 5)
- `RETRY_INTERVAL`: Retry interval in seconds after errors (default: 10)
- `MAX_HISTORY_SIZE`: Maximum number of games to keep in memory (default: 1000)

### Logging Settings

- `LOG_LEVEL`: Logging level (default: 'INFO')

### Database Settings

- `DATABASE_ENABLED`: Whether to store games in the database (default: true)
- `DATABASE_URL`: Database connection URL (default: 'postgresql://postgres:postgres@localhost:5432/bc_crash_db')

### Catchup Settings

- `CATCHUP_ENABLED`: Whether to run catchup on startup (default: true)
- `CATCHUP_PAGES`: Number of pages to fetch during catchup (default: 20)
- `CATCHUP_BATCH_SIZE`: Batch size for concurrent requests during catchup (default: 20)

### Timezone Settings

- `TIMEZONE`: Timezone for datetime values in API responses (default: 'UTC'). Any valid timezone name from the IANA timezone database can be used (e.g., 'America/New_York', 'Europe/London', 'Asia/Kolkata').

## Usage

### Running the Monitor

```bash
# Run with default settings
python -m src

# Run with specific command
python -m src monitor --skip-catchup

# Run without initial catchup
python -m src monitor --skip-catchup

# Run only the API server (no polling)
python -m src monitor --skip-polling

# Run catchup only
python -m src catchup --pages 50 --batch-size 10
```

### Command-line Arguments

- `monitor`: Run the crash monitor (default command)
  - `--skip-catchup`: Skip the initial catchup process
  - `--skip-polling`: Run only the API server without polling the game service

- `catchup`: Run only the historical data catchup
  - `--pages`: Number of pages to fetch (default: from config)
  - `--batch-size`: Batch size for concurrent requests (default: from config)

### API

The application includes a REST API for accessing crash data.

Basic endpoints:

- `GET /api/games` - Get crash games with pagination
- `GET /api/games/{game_id}` - Get a specific game by ID

For detailed API documentation, see [docs/API.md](docs/API.md).

## Development

### Requirements

- Python 3.8+
- PostgreSQL (if database storage is enabled)

### Setting up a Development Environment

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies:

   ```bash
   pip install -r requirements-dev.txt
   ```

4. Set up pre-commit hooks:

   ```bash
   pre-commit install
   ```
