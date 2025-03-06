#!/usr/bin/env python3
"""
Selenium script to navigate to BC Game crash page.
Uses a visible browser (headless=False) to help bypass Cloudflare challenges.
"""

import sys
import os
import time
import logging

# First, let's print environment information to diagnose the issue
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    print("Successfully imported Selenium modules")
except ImportError as e:
    print(f"Error importing Selenium: {e}")
    print("\nTrying to install Selenium within the script...")

    # Try to install Selenium using the current Python interpreter
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pip", "install", "selenium"],
                            capture_output=True, text=True)
    print(result.stdout)

    if result.returncode != 0:
        print(f"Error installing Selenium: {result.stderr}")
        print("\nPlease ensure you're using the correct Python environment.")
        print("Try one of these approaches:")
        print("1. Activate your virtual environment: source venv/bin/activate")
        print("2. Install Selenium globally: python -m pip install selenium")
        print("3. Run the script with the full path to the Python in your venv:")
        print("   /path/to/venv/bin/python selenium_bc_game.py")
        sys.exit(1)

    # Try importing again after installation
    print("Retrying imports...")
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    print("Successfully imported Selenium modules after installation")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_driver():
    """Set up the Chrome WebDriver with appropriate options."""
    chrome_options = Options()
    chrome_options.headless = False  # Set headless to False as requested

    # Add additional options to help bypass detection
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # Set user agent to appear more like a regular browser
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

    # Add experimental options to avoid detection
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        # Create the driver
        driver = webdriver.Chrome(options=chrome_options)

        # Execute CDP commands to prevent detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })

        return driver
    except Exception as e:
        logger.error(f"Error creating Chrome driver: {e}")
        logger.info(
            "Make sure you have Chrome browser installed and ChromeDriver is in PATH")
        logger.info(
            "You may need to download the appropriate ChromeDriver version from: https://chromedriver.chromium.org/downloads")
        raise


def navigate_to_bc_game():
    """Navigate to BC Game crash page and handle any challenges."""
    driver = None
    try:
        logger.info("Setting up Chrome WebDriver...")
        driver = setup_driver()

        # Navigate to the target URL
        target_url = "https://bc.fun/game/crash"
        logger.info(f"Navigating to {target_url}...")
        driver.get(target_url)

        # Wait for page to load
        logger.info("Waiting for page to load...")
        wait = WebDriverWait(driver, 30)

        try:
            # First check if there's a Cloudflare challenge
            if "Checking your browser" in driver.page_source or "Just a moment" in driver.page_source:
                logger.info(
                    "Detected Cloudflare challenge, waiting for it to resolve...")
                # Wait longer for challenge to resolve
                time.sleep(10)

            # Wait for some element that indicates the page has loaded
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Give extra time for the page to fully render
            time.sleep(5)

            # Get cookies after successful navigation
            cookies = driver.get_cookies()
            logger.info(
                f"Successfully loaded page. Got {len(cookies)} cookies.")

            # Optional: Print the most important cookies (especially Cloudflare ones)
            cf_cookies = [
                cookie for cookie in cookies if 'cf_' in cookie['name']]
            if cf_cookies:
                logger.info("Found Cloudflare cookies:")
                for cookie in cf_cookies:
                    logger.info(
                        f"  {cookie['name']}: {cookie['value'][:20]}...")

                # Save cookies to a file for later use
                with open('cf_cookies.txt', 'w') as f:
                    for cookie in cf_cookies:
                        f.write(f"{cookie['name']}={cookie['value']}\n")
                logger.info("Saved Cloudflare cookies to cf_cookies.txt")

            # Take screenshot to verify
            screenshot_path = "bc_game_screenshot.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")

            # Get page source
            page_title = driver.title
            logger.info(f"Page title: {page_title}")

            # Wait for user to manually close browser if needed
            input("Press Enter to close the browser...")

        except TimeoutException:
            logger.error("Timeout waiting for page to load")

    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if driver:
            logger.info("Closing browser...")
            driver.quit()


if __name__ == "__main__":
    navigate_to_bc_game()
