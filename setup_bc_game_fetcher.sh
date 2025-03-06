#!/bin/bash

# BC Game Fetcher Setup Script
# This script installs all necessary dependencies for the BC Game fetcher scripts

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up BC Game Fetcher...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3 first.${NC}"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}pip3 is not installed. Please install pip3 first.${NC}"
    exit 1
fi

# Check if we're in a virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Not in a virtual environment. It's recommended to use a virtual environment.${NC}"
    echo -e "${YELLOW}Would you like to create and activate a virtual environment? (y/n)${NC}"
    read -r create_venv
    
    if [[ "$create_venv" == "y" || "$create_venv" == "Y" ]]; then
        echo -e "${GREEN}Creating virtual environment...${NC}"
        python3 -m venv venv
        
        echo -e "${GREEN}Activating virtual environment...${NC}"
        source ./venv/bin/activate
        
        echo -e "${GREEN}Virtual environment created and activated.${NC}"
    else
        echo -e "${YELLOW}Continuing without virtual environment...${NC}"
    fi
fi

# Install Python dependencies
echo -e "${GREEN}Installing Python dependencies...${NC}"
pip3 install selenium requests

# Make scripts executable
echo -e "${GREEN}Making scripts executable...${NC}"
chmod +x selenium_bc_game.py use_cf_cookies.py bc_game_fetcher.py fetch_crash_history.sh

# Check if Chrome is installed
if ! command -v google-chrome &> /dev/null && ! command -v /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome &> /dev/null; then
    echo -e "${YELLOW}Google Chrome doesn't seem to be installed. Selenium requires Chrome.${NC}"
    echo -e "${YELLOW}Please install Chrome from: https://www.google.com/chrome/${NC}"
fi

# Check if Chrome Driver is installed
if ! command -v chromedriver &> /dev/null; then
    echo -e "${YELLOW}ChromeDriver doesn't seem to be in PATH.${NC}"
    echo -e "${YELLOW}Selenium may attempt to download it automatically, but if you encounter issues,${NC}"
    echo -e "${YELLOW}download the appropriate version from: https://chromedriver.chromium.org/downloads${NC}"
fi

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}You can now run the fetcher using: ./bc_game_fetcher.py${NC}"
echo -e "${GREEN}Or try the Selenium script directly: ./selenium_bc_game.py${NC}"
echo -e "${GREEN}Or use the Cloudflare cookies script: ./use_cf_cookies.py${NC}" 