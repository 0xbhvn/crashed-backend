import asyncio
import os
import json
import random
import sys
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Add the current directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv()

# XPath expressions for key elements
HISTORY_TABLE_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[3]/div/div[2]/div/div[1]/table/tbody"
HISTORY_BUTTON_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[2]/button[2]"
HISTORY_FIRST_ROW_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[3]/div/div[2]/div/div[1]/table/tbody/tr[1]"

# Global variable to store the last game ID we've seen
last_processed_game_id = None

# Global variable to store the monitor reference
crash_monitor = None


async def connect_to_monitor():
    """Try to connect to an existing monitor instance running on the local API server"""
    global crash_monitor

    try:
        # Import the monitor module
        from src.app import get_running_monitor
        import logging

        # Configure logging
        logger = logging.getLogger("observer")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Get the monitor instance
        crash_monitor = get_running_monitor()

        if crash_monitor:
            logger.info("Successfully connected to BC Crash Monitor instance")
            return True
        else:
            logger.warning("No running BC Crash Monitor instance found")
            return False
    except ImportError:
        print("Could not import BC Crash Monitor modules")
        return False
    except Exception as e:
        print(f"Error connecting to monitor: {str(e)}")
        return False


async def clear_overlays(page):
    """Attempt to clear any overlays or popups once at startup"""
    try:
        # Common selectors for close buttons on overlays/popups
        close_button_selectors = [
            "button.close-btn",
            ".modal-close",
            ".dialog-close",
            ".close-icon",
            "button.close",
            ".overlayer .close",
            "[aria-label='Close']",
            ".modal .close-button",
            ".root-layer .close-button"
        ]

        for selector in close_button_selectors:
            if await page.is_visible(selector, timeout=1000):
                print(f"Found overlay close button: {selector}")
                await page.click(selector)
                await asyncio.sleep(1)

        # Try to remove the overlay using JavaScript if it exists
        await page.evaluate("""() => {
            // Try to remove any overlays by class name
            const overlayers = document.querySelectorAll('.overlayer, .modal, .popup, .dialog, .root-layer');
            overlayers.forEach(el => {
                if (el) el.remove();
            });
            
            // Remove any elements that might be intercepting clicks
            const elementsWithHighZIndex = Array.from(document.querySelectorAll('*')).filter(el => {
                const style = window.getComputedStyle(el);
                return style.position === 'fixed' && 
                       (style.zIndex !== 'auto' && parseInt(style.zIndex) > 100) && 
                       (el.offsetWidth > 100 || el.offsetHeight > 100);
            });
            elementsWithHighZIndex.forEach(el => el.remove());
        }""")

    except Exception as e:
        print(f"Error clearing overlays: {str(e)}")


async def open_history_tab(page):
    """Open the history tab if it's not already open"""
    try:
        # Check if history is already open by looking for table
        history_table = page.locator('xpath=' + HISTORY_TABLE_XPATH)

        if not await history_table.is_visible(timeout=1000):
            print("History tab is not open. Attempting to open it...")

            # For the button, also use locator with xpath
            history_button = page.locator('xpath=' + HISTORY_BUTTON_XPATH)

            # Wait for the button to be visible
            await history_button.wait_for(state="visible", timeout=10000)

            # Human-like delay before clicking
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Increase the click timeout for better reliability
            await history_button.click(timeout=10000)
            print("Clicked history button")

            # Wait for history data to load
            await asyncio.sleep(2)

            # Verify that the history table is now visible
            if await history_table.is_visible(timeout=5000):
                print("History tab opened successfully")
            else:
                print("Warning: History tab may not have opened correctly")
        else:
            print("History tab is already open")

        return True
    except Exception as e:
        print(f"Error opening history tab: {str(e)}")
        return False


async def handle_new_crash(source, data_json):
    """Process a new crash that was detected by the MutationObserver"""
    global last_processed_game_id, crash_monitor

    try:
        # Parse the JSON data
        crash_data = json.loads(data_json)

        # Skip if we've already processed this game ID
        if crash_data["gameId"] == last_processed_game_id:
            return

        # Update our last processed game ID
        last_processed_game_id = crash_data["gameId"]

        # Convert result to float (removing 'x' if present)
        crash_value = float(crash_data["result"].replace('x', ''))

        print(
            f"New crash detected - Game ID: {crash_data['gameId']}, Value: {crash_value}x")

        # Log every crash point
        timestamp = datetime.now().isoformat()
        print(
            f"[{timestamp}] Crash logged - Game ID: {crash_data['gameId']}, Value: {crash_value}x")

        # Prepare the minimal payload - the monitor will enhance with API data if possible
        game_data = {
            "gameId": crash_data["gameId"],
            "crashPoint": crash_value
        }

        # Simplified communication with monitor
        await send_to_monitor(game_data)

    except Exception as e:
        print(f"Error handling crash notification: {str(e)}")


async def send_to_monitor(game_data):
    """Send game data to the monitor with auto-reconnection if needed"""
    global crash_monitor

    # First attempt - try with existing connection
    if crash_monitor:
        try:
            print(f"Sending game data to monitor: {game_data['gameId']}")
            success = await crash_monitor.add_game_event(game_data)
            if success:
                print(
                    f"Successfully sent crash data to monitor: {game_data['gameId']}")
                return True
            else:
                print(
                    f"Failed to send crash data to monitor: {game_data['gameId']}")
        except Exception as e:
            print(f"Error sending data to monitor: {str(e)}")
            # Fall through to reconnection attempt

    # Reconnection attempt
    try:
        print("Attempting to connect to monitor...")
        if await connect_to_monitor():
            if crash_monitor:
                try:
                    success = await crash_monitor.add_game_event(game_data)
                    if success:
                        print(
                            f"Successfully sent crash data after reconnection: {game_data['gameId']}")
                        return True
                    else:
                        print(
                            f"Failed to send crash data after reconnection: {game_data['gameId']}")
                except Exception as e:
                    print(f"Error sending data after reconnection: {str(e)}")
        else:
            print("No monitor connection available, crash data not processed")
    except Exception as e:
        print(f"Error in reconnection attempt: {str(e)}")

    return False


async def add_anti_bot_evasion(page):
    """Add various tricks to evade bot detection"""

    # Override the navigator properties to mask automation
    await page.evaluate("""() => {
        // Overwrite the navigator properties that might reveal automation
        const newProto = navigator.__proto__;
        delete newProto.webdriver;
        
        // Add human-like navigator properties
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
            configurable: true
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'PDF Viewer' },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: 'Native Client' }
            ],
            configurable: true
        });
        
        // Modify user-agent behavior
        Object.defineProperty(navigator, 'userAgent', {
            get: () => navigator.userAgent.replace('Headless', ''),
            configurable: true
        });
        
        // Add fake mouse movements periodically
        const randomMouseMove = () => {
            const event = new MouseEvent('mousemove', {
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': Math.floor(Math.random() * window.innerWidth),
                'clientY': Math.floor(Math.random() * window.innerHeight)
            });
            document.dispatchEvent(event);
            
            // Schedule next random move
            setTimeout(randomMouseMove, Math.random() * 3000 + 1000);
        };
        
        // Start random mouse movements
        randomMouseMove();
    }""")

    print("Added anti-bot detection measures")


async def monitor_crash_game(headless=False):
    """Main function to monitor the crash game using real-time detection with async Playwright

    Args:
        headless: Whether to run in headless mode (no visible browser window)
    """

    print("Starting crash monitoring...")

    async with async_playwright() as p:
        # Launch browser locally
        browser = None

        try:
            # Set up a more realistic browser configuration
            print("Starting local browser session with anti-detection measures...")

            # Use a popular user agent
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

            # Configure browser with anti-detection settings
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--window-size=1920,1080',
                    '--user-agent=' + user_agent
                ]
            )

            # Create a context with specific viewport and anti-fingerprinting measures
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                is_mobile=False,
                has_touch=False,
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation']
            )

            # Enable JavaScript and cookies
            page = await context.new_page()

            # Apply anti-bot detection measures
            await add_anti_bot_evasion(page)

            # Speed up by first visiting a faster site
            print("Warming up browser...")
            await page.goto("https://www.google.com", wait_until="domcontentloaded")
            await asyncio.sleep(1)

            # Navigate to the crash game page with adjusted timeouts
            print("Navigating to BC.game crash page...")

            # Set a longer timeout but wait only for DOM content
            await page.goto(
                "https://bc.game/game/crash",
                wait_until="domcontentloaded",
                timeout=60000
            )

            print(f"Page loaded: {await page.title()}")

            # Wait for the page to become interactive
            print("Waiting for page to stabilize...")
            try:
                # Wait for main content to appear
                await page.wait_for_selector("div.game-crash", timeout=30000)
            except:
                print(
                    "Timeout waiting for crash game interface, but continuing anyway...")

            # Add random delay to appear more human-like
            await asyncio.sleep(random.uniform(2, 4))

            # Clear any overlays once at startup
            print("Clearing any overlays...")
            await clear_overlays(page)

            # Open the history tab
            print("Opening history tab...")
            if not await open_history_tab(page):
                raise Exception("Could not open history tab")

            # Take a screenshot to help debug
            screenshot_path = "history_tab_opened.png"
            await page.screenshot(path=screenshot_path)
            print(f"Saved screenshot as {screenshot_path}")

            # Expose the callback to the page context
            print("Setting up real-time crash monitoring...")
            await page.expose_binding("onNewCrash", handle_new_crash)

            # Inject a MutationObserver into the page to watch for changes in the first row
            await page.evaluate(f"""() => {{
                // Function to extract crash data from a table row
                function extractCrashDataFromRow(rowElement) {{
                    try {{
                        // Find game ID cell (first column, span inside span)
                        const gameIdElement = rowElement.querySelector('td:first-child span span:last-child');
                        
                        // Find result cell (second column)
                        const resultElement = rowElement.querySelector('td:nth-child(2)');
                        
                        if (!gameIdElement || !resultElement) {{
                            console.log('Could not find game ID or result elements in row');
                            return null;
                        }}
                        
                        const gameId = gameIdElement.textContent?.trim() || 'Unknown ID';
                        const result = resultElement.textContent?.trim() || 'Unknown Result';
                        
                        console.log('Extracted crash data:', {{ gameId, result }});
                        return {{ gameId, result }};
                    }} catch (e) {{
                        console.error('Error extracting crash data from row:', e);
                        return null;
                    }}
                }}
                
                // Function to find the history table using XPath
                function findElement(xpath) {{
                    return document.evaluate(
                        xpath,
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;
                }}
                
                // Find the table and the first row
                const historyTable = findElement("{HISTORY_TABLE_XPATH}");
                const firstRow = findElement("{HISTORY_FIRST_ROW_XPATH}");
                
                if (!historyTable) {{
                    console.error('History table not found');
                    return;
                }}
                
                if (firstRow) {{
                    // Process initial row to get the starting game ID
                    const initialData = extractCrashDataFromRow(firstRow);
                    if (initialData) {{
                        window.lastProcessedGameId = initialData.gameId;
                        console.log('Initialized with game ID:', initialData.gameId);
                    }}
                    
                    // Set up MutationObserver for the first row (to detect data changes)
                    const rowObserver = new MutationObserver((mutations) => {{
                        for (const mutation of mutations) {{
                            if (mutation.type === 'childList' || mutation.type === 'characterData') {{
                                const crashData = extractCrashDataFromRow(firstRow);
                                if (crashData && crashData.gameId !== window.lastProcessedGameId) {{
                                    window.onNewCrash(JSON.stringify(crashData));
                                }}
                                break;
                            }}
                        }}
                    }});
                    
                    // Watch for changes in the row content
                    rowObserver.observe(firstRow, {{ 
                        childList: true, 
                        subtree: true, 
                        characterData: true 
                    }});
                }}
                
                // Set up MutationObserver for the table body (to detect new rows)
                const tableObserver = new MutationObserver((mutations) => {{
                    for (const mutation of mutations) {{
                        if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {{
                            // We have new rows - check the newest one (first in the table)
                            const newRows = Array.from(mutation.addedNodes)
                                .filter(node => node.nodeName === 'TR');
                            
                            if (newRows.length > 0) {{
                                console.log(`${{newRows.length}} new crash result(s) detected!`);
                                
                                // Process the newest row (should be the first one)
                                const newestRow = newRows[0];
                                const crashData = extractCrashDataFromRow(newestRow);
                                
                                if (crashData) {{
                                    window.onNewCrash(JSON.stringify(crashData));
                                }}
                            }}
                        }}
                    }}
                }});
                
                // Start observing the table for new rows
                tableObserver.observe(historyTable, {{
                    childList: true,
                    subtree: false
                }});
                
                console.log('Real-time crash monitoring active! Watching for new crashes...');
            }}""")

            print("Real-time crash monitoring has been set up with zero-lag detection")
            print("Monitoring for all crash points...")
            print("Press Ctrl+C to stop monitoring")

            # Keep the browser open until manually stopped
            try:
                # Keep the script running with a completely event-driven approach
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("Monitoring stopped by user")
            except asyncio.CancelledError:
                print("Observer task cancelled")
                raise

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            if page:
                await page.screenshot(path="error_screenshot.png")
                print("Saved error screenshot as error_screenshot.png")
            raise  # Re-raise to inform the caller

        finally:
            if browser:
                await browser.close()
                print("Browser session closed")


async def main():
    print("Starting BC Game Crash Observer")
    print("Observing crash games in real-time")

    # First, try to connect to the monitor
    if await connect_to_monitor():
        print("Connected to BC Game Crash Monitor")
    else:
        print("Warning: Could not connect to BC Game Crash Monitor")
        print(
            "Make sure to run 'python -m src monitor --skip-catchup --event-driven' first")
        print("Continuing anyway but crash events may not be processed correctly")

    # Main monitoring with automatic recovery
    while True:
        try:
            await monitor_crash_game()
        except Exception as e:
            print(f"Critical error: {str(e)}")
            print("Restarting monitor in 30 seconds...")
            await asyncio.sleep(30)


if __name__ == "__main__":
    # If the script is being run directly, use the main function
    asyncio.run(main())
else:
    # If the script is being imported, expose the main function
    # This allows the monitor to import and run this script directly
    __all__ = ['monitor_crash_game', 'handle_new_crash']
