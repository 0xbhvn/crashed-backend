# BC Game Crash Monitor

A Python application that monitors BC Game's crash game and calculates crash values in real-time.

## Features

- Real-time monitoring of BC Game crash games
- Verification of crash points using HMAC-SHA256 algorithm
- Logging of game results to console and file
- Database integration for storing game results and statistics
- Resilient design with automatic reconnection and error handling

## Requirements

- Python 3.11 or higher
- PostgreSQL database
- Internet connection to access BC Game API

### Dependencies

The application uses the following key dependencies:

- aiohttp 3.11.13 - For asynchronous HTTP requests
- SQLAlchemy 2.0.28 - ORM for database operations
- psycopg2-binary 2.9.10 - PostgreSQL adapter
- python-dotenv 1.0.1 - Environment variable management
- alembic 1.14.1 - Database migration tool

For a complete list, see `requirements.txt`.

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/bc-crash-monitor.git
   cd bc-crash-monitor
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:

   ```bash
   pip install -e .
   ```

5. Create a `.env` file based on `.env.example`:

   ```bash
   cp .env.example .env
   ```

6. Edit the `.env` file with your configuration settings.

7. Run the application:

   ```bash
   python main.py
   ```

   The database tables will be created automatically on first run.

## Architecture

The application consists of several main components:

1. **BC Crash Monitor** (`src/history.py`): Core component that polls the BC Game API for crash results and processes them in real-time.

2. **Database Module** (`src/sqlalchemy_db.py`): Handles database operations using SQLAlchemy, including storing crash games and calculating statistics.

3. **Models** (`src/models.py`): Defines SQLAlchemy models for the database schema.

4. **Main Application** (`main.py`): Entry point that sets up the environment and runs the monitor.

5. **Setup Script** (`run.py`): Helper script for first-time setup and development environment configuration.

## Project Structure

```text
bc-game-crash-monitor/
├── .env                      # Environment variables (not in repository)
├── .env.example              # Example environment configuration
├── README.md                 # Project documentation
├── requirements.txt          # Core production dependencies
├── dev-requirements.txt      # Development dependencies
├── setup.py                  # Package installation configuration
├── alembic.ini               # Alembic migration configuration
├── main.py                   # Application entry point
├── run.py                    # Development environment setup script
├── docs/                     # Documentation
│   └── database_migrations.md # Guide for database schema migrations
├── logs/                     # Log files (generated at runtime)
├── migrations/               # Database migration files
│   ├── env.py                # Alembic environment configuration
│   └── versions/             # Migration version scripts
│       └── fec343f2d3f9_init.py # Initial migration
├── prisma/                   # Prisma schema (legacy, SQLAlchemy is now used)
│   └── schema.prisma         # Prisma database schema
└── src/                      # Source code
    ├── __init__.py           # Package initialization
    ├── __main__.py           # Package entry point
    ├── config.py             # Configuration management
    ├── database.py           # Database interface
    ├── history.py            # BC Game crash monitor implementation
    ├── main.py               # Module entry point
    ├── migrate.py            # Database migration utility
    ├── models.py             # SQLAlchemy data models
    └── sqlalchemy_db.py      # SQLAlchemy database implementation
```

## Database Integration

The application uses SQLAlchemy ORM for database operations, providing:

- Type-safe database access
- Automatic schema migration
- Efficient database queries
- Object-oriented data access

The database schema includes:

- **crash_games**: Stores individual game results
  - game_id: Unique identifier for the game
  - hash_value: The hash value from the game
  - crash_point: The actual crash point from BC Game
  - calculated_point: Our calculated crash point for verification
  - verified: Whether our calculation matches the actual result
  - deviation: The difference between actual and calculated points
  - end_time_unix: Unix timestamp when the game ended (in milliseconds)
  - end_time: End time converted to datetime (in IST timezone UTC+5:30)
  - prepare_time_unix: Unix timestamp when the game started preparing (in milliseconds)
  - prepare_time: Prepare time converted to datetime (in IST timezone UTC+5:30)
  - begin_time_unix: Unix timestamp when the game began (in milliseconds)
  - begin_time: Begin time converted to datetime (in IST timezone UTC+5:30)
  - created_at: Timestamp when the record was created (in IST timezone UTC+5:30)
  - updated_at: Timestamp when the record was last updated (in IST timezone UTC+5:30)

- **crash_stats**: Stores daily statistical aggregates
  - date: The date of the statistics
  - games_count: Number of games that day
  - average_crash: Average crash point
  - median_crash: Median crash point
  - max_crash: Maximum crash point
  - min_crash: Minimum crash point
  - standard_deviation: Standard deviation of crash points
  - created_at: Timestamp when the record was created (in IST timezone UTC+5:30)
  - updated_at: Timestamp when the record was last updated (in IST timezone UTC+5:30)

### Timezone Handling

All timestamp fields in the database (end_time, prepare_time, begin_time, created_at, updated_at) are stored in the configured timezone, which defaults to IST (UTC+5:30, Asia/Kolkata) but can be changed via the `TIMEZONE` environment variable. This helps with:

- Easier analysis of crash data according to your local business hours
- Simplified reporting and monitoring for users in the configured timezone
- Consistent timestamp format throughout the application

The timezone can be configured in the `.env` file using the standard IANA timezone database name format:

```bash
# Examples
TIMEZONE=Asia/Kolkata  # Indian Standard Time (UTC+5:30)
TIMEZONE=America/New_York  # Eastern Time
TIMEZONE=Europe/London  # Greenwich Mean Time/British Summer Time
TIMEZONE=Asia/Tokyo  # Japan Standard Time
```

The conversion from Unix timestamps to timezone-aware datetime objects is handled automatically by the application using the `pytz` library.

### Database Schema Migrations

When you need to change the database schema (add columns, change data types, etc.):

1. Update the SQLAlchemy models in `src/models.py`
2. Use one of these methods to update the database:

   a. **Using Alembic (recommended)**:

      ```bash
      # Create a migration
      alembic revision --autogenerate -m "Description of changes"
      
      # Apply the migration
      alembic upgrade head
      ```

   b. **Manual SQL** (for simple changes):

      ```bash
      # Connect to the database
      psql your_connection_string
      
      # Make changes with SQL
      ALTER TABLE crash_games ADD COLUMN new_column TEXT;
      ```

For more details, see [Database Migration Guide](docs/database_migrations.md).

## Configuration

The application is configured through environment variables, which can be set in the `.env` file:

```bash
# API Settings
API_BASE_URL=https://bc.game
API_HISTORY_ENDPOINT=/api/game/bet/multi/history
GAME_URL=crash
PAGE_SIZE=50

# Calculation Settings
BC_GAME_SALT=0000000000000000000301e2801a9a9598bfb114e574a91a887f2132f33047e6

# Monitoring Settings
POLL_INTERVAL=5
RETRY_INTERVAL=10
MAX_HISTORY_SIZE=10

# Logging Settings
LOG_FILE_PATH=logs/bc_crash_monitor.log
LOG_LEVEL=INFO

# Database Settings
DATABASE_ENABLED=true
DATABASE_URL=postgresql://username:password@localhost:5432/bc_crash_db

# Timezone Settings
TIMEZONE=Asia/Kolkata
```

## Usage

Run the application with:

```bash
python main.py
```

The application will:

1. Connect to the BC Game API
2. Initialize the database connection (if enabled)
3. Start monitoring crash games
4. Calculate and verify crash points
5. Store results in the database (if enabled)
6. Log results to console and file

## Output Format

The application logs each crash game with the following information:

```bash
New crash result: Game ID 7911249, Crash Point 1.9x, Hash 4c5cb893...
```

## How Crash Point Calculation Works

BC Game uses a provably fair algorithm based on HMAC-SHA256 to determine crash points:

1. Each game has a unique hash value
2. The hash is combined with a salt value using HMAC-SHA256
3. The first 13 characters of the resulting hash are converted to a number between 0 and 1
4. The crash point is calculated using the formula: `99 / (1 - X)`
5. The result is floored and divided by 100, with a minimum of 1.00

This application implements this algorithm to verify that the crash points reported by BC Game are accurate.

## Database Management

The application uses SQLAlchemy to manage the database schema and operations. The tables are created automatically when the application is run for the first time.

If you need to work with the database directly:

```python
from src.sqlalchemy_db import get_database
from src.models import CrashGame, CrashStats

# Get database instance
db = get_database()

# Query data using a session
with db.get_session() as session:
    recent_games = session.query(CrashGame).order_by(CrashGame.id.desc()).limit(10).all()
    for game in recent_games:
        print(f"Game ID: {game.gameId}, Crash Point: {game.crashPoint}x")

# Or use the convenience methods
recent_games = db.get_latest_crash_games(limit=10)
for game in recent_games:
    print(f"Game ID: {game.gameId}, Crash Point: {game.crashPoint}x")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
