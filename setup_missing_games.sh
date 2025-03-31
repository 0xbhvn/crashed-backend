#!/bin/bash

# Setup script for Missing Games Verifier

echo "Setting up Missing Games Verifier..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements-missing-games.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install

# Create sample .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating sample .env file..."
    cat > .env << EOL
# Database connection string
# Format: postgresql://username:password@host:port/database
DATABASE_URL=postgresql://postgres:avyZzMkfHbyHaUoonVTxhWnaVJMtoroO@gondola.proxy.rlwy.net:12265/railway

# Uncomment and modify if you need to customize these settings
# BC_GAME_SALT=0000000000000000000301e2801a9a9598bfb114e574a91a887f2132f33047e6
# LOG_LEVEL=INFO
EOL

    echo "Created sample .env file. Please edit it with your database credentials."
else
    echo ".env file already exists, skipping creation."
fi

# Ensure tqdm is installed (even if requirements file doesn't have it)
pip install tqdm

echo "Setup complete! You can now run the script with:"
echo "source venv/bin/activate"
echo "python missing_games_verifier.py [--csv] [--store] [--limit N] [--force]" 