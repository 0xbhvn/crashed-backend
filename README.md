# BC Game Crash Monitor

A Python application for monitoring BC Game's crash game, calculating crash values, and storing results in a database.

## Features

- Real-time monitoring of BC Game crash results
- Historical data catchup functionality
- Crash point calculation and verification
- Database storage of game results
- Configurable logging and monitoring settings
- Command-line interface for different operations

## Project Structure

```
src/
├── __init__.py        # Package initialization
├── __main__.py        # Entry point when run as a module
├── app.py             # Main application entry point
├── config.py          # Configuration settings
├── history.py         # Crash monitor implementation
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
   ```
   git clone https://github.com/yourusername/bc-game-crash-monitor.git
   cd bc-game-crash-monitor
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables (see Configuration section)

## Configuration

The application can be configured using environment variables:

### API Settings
- `API_BASE_URL`: Base URL for the BC Game API (default: 'https://bc.game')
- `API_HISTORY_ENDPOINT`: API endpoint for crash history (default: '/api/crash/games/history')
- `GAME_URL`: Game URL path (default: '/game/crash')
- `PAGE_SIZE`: Number of games per page in API requests (default: 50)

### Calculation Settings
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

## Usage

### Running the Monitor

```
# Run with default settings
python -m src

# Run with specific command
python -m src monitor --skip-catchup

# Run catchup only
python -m src catchup --pages 50 --batch-size 10
```

### Command-line Arguments

- `monitor`: Run the crash monitor (default command)
  - `--skip-catchup`: Skip the initial catchup process

- `catchup`: Run only the historical data catchup
  - `--pages`: Number of pages to fetch (default: from config)
  - `--batch-size`: Batch size for concurrent requests (default: from config)

## Development

### Requirements

- Python 3.8+
- PostgreSQL (if database storage is enabled)

### Setting up a Development Environment

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies:
   ```
   pip install -r requirements-dev.txt
   ```

4. Set up pre-commit hooks:
   ```
   pre-commit install
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This project is not affiliated with BC Game. It is a third-party tool for educational purposes only. Use at your own risk.
