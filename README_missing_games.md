# Missing Games Verifier for BC.Game Crash

This tool identifies missing game IDs in the BC.Game Crash database and verifies them using the BC.Game verification page.

## Overview

The script performs the following operations:

1. Connects to the database and identifies ranges of missing game IDs
2. Gets the hash values for games before and after each missing range
3. Uses Playwright to verify the missing games on BC.Game's verification page
4. Maps the verified games to their correct game IDs
5. Optionally stores the results in the database or exports to CSV

## Prerequisites

- Python 3.8+
- PostgreSQL database with crash_games table
- The following Python packages:
  - sqlalchemy
  - playwright
  - psycopg2-binary (for PostgreSQL)
  - python-dotenv
  - tqdm (for progress bars)

## Installation

1. Make sure you have Python 3.8+ installed
1. Install required packages:

```bash
pip install sqlalchemy playwright psycopg2-binary python-dotenv tqdm
```

1. Install Playwright browsers:

```bash
playwright install
```

1. Create a `.env` file in the project root directory with your database connection string:

```text
DATABASE_URL=postgresql://username:password@host:port/database
```

## Usage

### Basic Usage

```bash
python missing_games_verifier.py
```

By default, this will process the first missing range of games found and output the results to the console.

### Command Line Options

- `--csv`: Export verified games to CSV files
- `--store`: Store verified games in the database
- `--limit N`: Process up to N ranges of missing games (default: 1)
- `--batch-size B`: Maximum number of games to verify in a single batch (default: 100)

### Examples

Process all missing game ranges and store them in the database:

```bash
python missing_games_verifier.py --store --limit 9999
```

Process up to 5 missing game ranges and export to CSV:

```bash
python missing_games_verifier.py --csv --limit 5
```

Process a large range of missing games with a smaller batch size (useful if the verification page is limiting results):

```bash
python missing_games_verifier.py --batch-size 50 --csv --store
```

## Batch Processing

The verification page may have limitations on how many games it can process at once. This tool handles this by:

1. Breaking down large ranges into smaller batches (controlled by `--batch-size`)
2. Processing each batch individually, starting with the hash of the game after the missing range
3. For subsequent batches, using the hash of the last verified game from the previous batch
4. Combining all verified games and mapping them to the correct game IDs

This approach allows the tool to handle ranges of any size, working around the limitations of the verification page.

## Progress Tracking

The script includes progress bars for all time-consuming operations:

- Verifying games: Shows progress as each batch is processed
- Mapping games to IDs: Shows progress as games are mapped
- Storing in database: Shows elapsed time during database operations
- Saving to CSV: Shows progress as games are written to the file
- Overall range processing: Tracks progress across multiple ranges

These progress bars provide real-time feedback on the script's operations, making it easy to track progress and estimate completion times.

## Output

- For each range of missing games, the script will generate screenshots of the verification page
- If `--csv` is specified, CSV files will be created with names like `missing_games_START_END_TIMESTAMP.csv`
- If `--store` is specified, verified games will be added to the database

## Database Configuration

The script reads the database connection string from the `.env` file in the project root directory. The format of the connection string is:

```text
DATABASE_URL=postgresql://username:password@host:port/database
```

For example:

```text
DATABASE_URL=postgresql://postgres:password@localhost:5432/bc_crash_db
```

## Troubleshooting

- If you encounter issues with the database connection, check that your PostgreSQL server is running and accessible
- If Playwright fails to access the verification page, check your internet connection and ensure the page URL is still valid
- Screenshots of the verification process are saved for debugging purposes
- If you're processing a large range and only getting a few games, try reducing the batch size with `--batch-size`

## License

This tool is provided under the same license as the BC.Game Crash Monitor project.
