import asyncio
import os
import json
import random
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
import aiohttp
import argparse

# Add the current directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger("observer")
logger.setLevel(logging.INFO)

# Add console handler if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# XPath expressions for key elements
HISTORY_TABLE_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[3]/div/div[2]/div/div[1]/table/tbody"
HISTORY_BUTTON_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[2]/button[2]"
HISTORY_FIRST_ROW_XPATH = "/html/body/div[1]/div[1]/div/div[2]/div[2]/div[3]/div/div[2]/div/div[1]/table/tbody/tr[1]"

# Global variable to store the last game ID we've seen
last_processed_game_id = None

# Global variable to store the monitor reference
crash_monitor = None

# Message queue to store failed transmissions for retry
message_queue = asyncio.Queue()

# Default retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 5  # seconds

# Flag to track if retry task is running
retry_task_running = False

# Status tracking
observer_running = False
monitor_connection_status = "disconnected"
API_ENDPOINT = "http://localhost:3000"  # Default API endpoint


async def ping_status_to_api():
    """Send status update to the API"""
    global last_processed_game_id, observer_running, monitor_connection_status

    try:
        status_data = {
            "is_running": observer_running,
            "last_game_id": last_processed_game_id,
            "connection_status": monitor_connection_status
        }

        logger.debug(f"Sending status update to API: {status_data}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_ENDPOINT}/api/observer/ping",
                json=status_data,
                timeout=5
            ) as response:
                if response.status == 200:
                    logger.debug("Successfully updated observer status")
                    return True
                else:
                    logger.warning(
                        f"Failed to update observer status: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error sending status update: {e}")
        return False


async def status_update_loop():
    """Background task to periodically send status updates to the API"""
    global observer_running

    try:
        while observer_running:
            await ping_status_to_api()
            await asyncio.sleep(30)  # Update every 30 seconds
    except asyncio.CancelledError:
        logger.info("Status update loop cancelled")
    except Exception as e:
        logger.error(f"Error in status update loop: {e}")


async def connect_to_monitor():
    """Try to connect to an existing monitor instance running on the local API server"""
    global crash_monitor, monitor_connection_status

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
            monitor_connection_status = "connected"
            await ping_status_to_api()  # Send immediate status update
            return True
        else:
            logger.warning("No running BC Crash Monitor instance found")
            monitor_connection_status = "disconnected"
            await ping_status_to_api()  # Send immediate status update
            return False
    except ImportError:
        logger.error("Could not import BC Crash Monitor modules")
        monitor_connection_status = "error"
        await ping_status_to_api()  # Send immediate status update
        return False
    except Exception as e:
        logger.error(f"Error connecting to monitor: {str(e)}")
        monitor_connection_status = "error"
        await ping_status_to_api()  # Send immediate status update
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
                logger.info(f"Found overlay close button: {selector}")
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
        logger.error(f"Error clearing overlays: {str(e)}")


async def open_history_tab(page):
    """Open the history tab if it's not already open"""
    try:
        # Check if history is already open by looking for table
        history_table = page.locator('xpath=' + HISTORY_TABLE_XPATH)

        if not await history_table.is_visible(timeout=1000):
            logger.info("History tab is not open. Attempting to open it...")

            # For the button, also use locator with xpath
            history_button = page.locator('xpath=' + HISTORY_BUTTON_XPATH)

            # Wait for the button to be visible
            await history_button.wait_for(state="visible", timeout=10000)

            # Human-like delay before clicking
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Increase the click timeout for better reliability
            await history_button.click(timeout=10000)
            logger.info("Clicked history button")

            # Wait for history data to load
            await asyncio.sleep(2)

            # Verify that the history table is now visible
            if await history_table.is_visible(timeout=5000):
                logger.info("History tab opened successfully")
            else:
                logger.warning(
                    "Warning: History tab may not have opened correctly")
        else:
            logger.info("History tab is already open")

        return True
    except Exception as e:
        logger.error(f"Error opening history tab: {str(e)}")
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

        # Send status update with new game ID
        asyncio.create_task(ping_status_to_api())

        # Convert result to float (removing 'x' if present)
        crash_value = float(crash_data["result"].replace('x', ''))

        logger.info(
            f"New crash detected - Game ID: {crash_data['gameId']}, Value: {crash_value}x")

        # Log every crash point
        timestamp = datetime.now().isoformat()
        logger.info(
            f"[{timestamp}] Crash logged - Game ID: {crash_data['gameId']}, Value: {crash_value}x")

        # Prepare the minimal payload - the monitor will enhance with API data if possible
        game_data = {
            "gameId": crash_data["gameId"],
            "crashPoint": crash_value
        }

        # Simplified communication with monitor
        await send_to_monitor(game_data)

    except Exception as e:
        logger.error(f"Error handling crash notification: {str(e)}")


async def send_to_monitor(game_data, max_retries=DEFAULT_MAX_RETRIES, retry_delay=DEFAULT_RETRY_DELAY):
    """
    Send game data to the monitor with improved error handling and retry logic.

    Args:
        game_data: Dictionary with game information
        max_retries: Maximum number of immediate retries
        retry_delay: Delay between retries (seconds)

    Returns:
        bool: True if successfully sent, False otherwise
    """
    global crash_monitor, message_queue, retry_task_running, monitor_connection_status

    # Validate required fields before sending
    if not game_data.get("gameId") or "crashPoint" not in game_data:
        logger.error(
            f"Invalid game data - missing required fields: {game_data}")
        return False

    # First attempt - try with existing connection
    if crash_monitor:
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Sending game data to monitor: {game_data['gameId']} (attempt {attempt+1}/{max_retries})")
                success = await crash_monitor.add_game_event(game_data)
                if success:
                    logger.info(
                        f"Successfully sent crash data to monitor: {game_data['gameId']}")
                    # Update connection status if it was previously disconnected
                    if monitor_connection_status != "connected":
                        monitor_connection_status = "connected"
                        asyncio.create_task(ping_status_to_api())

                    # Check message queue and start processing if needed
                    if not message_queue.empty() and not retry_task_running:
                        asyncio.create_task(process_message_queue())
                    return True
                else:
                    logger.warning(
                        f"Monitor rejected game data: {game_data['gameId']}")
                    if attempt < max_retries - 1:  # Not the last attempt
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error sending data to monitor: {str(e)}")
                if attempt < max_retries - 1:  # Not the last attempt
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)

    # Connection appears to be broken
    if monitor_connection_status == "connected":
        monitor_connection_status = "disconnected"
        asyncio.create_task(ping_status_to_api())

    # Reconnection attempt with fresh connection
    try:
        logger.info("Attempting to connect to monitor...")
        if await connect_to_monitor():
            if crash_monitor:
                try:
                    success = await crash_monitor.add_game_event(game_data)
                    if success:
                        logger.info(
                            f"Successfully sent crash data after reconnection: {game_data['gameId']}")
                        # Update connection status
                        monitor_connection_status = "connected"
                        asyncio.create_task(ping_status_to_api())

                        # Also check message queue
                        if not message_queue.empty() and not retry_task_running:
                            asyncio.create_task(process_message_queue())
                        return True
                    else:
                        logger.warning(
                            f"Monitor rejected game data after reconnection: {game_data['gameId']}")
                except Exception as e:
                    logger.error(
                        f"Error sending data after reconnection: {str(e)}")
            else:
                logger.warning(
                    "No monitor connection available after reconnect attempt")
        else:
            logger.warning("Failed to connect to monitor")
    except Exception as e:
        logger.error(f"Error in reconnection attempt: {str(e)}")

    # Ensure connection status is updated
    if monitor_connection_status != "error":
        monitor_connection_status = "error"
        asyncio.create_task(ping_status_to_api())

    # If we've reached here, all attempts have failed
    # Add to retry queue for future processing
    logger.info(
        f"Adding game {game_data['gameId']} to retry queue for later processing")
    await message_queue.put({
        "data": game_data,
        "timestamp": datetime.now().isoformat(),
        "attempts": max_retries
    })

    # Start the queue processor if it's not already running
    if not retry_task_running:
        asyncio.create_task(process_message_queue())

    return False


async def process_message_queue():
    """
    Background task to process messages in the retry queue with exponential backoff.
    """
    global retry_task_running, message_queue

    # Set flag to prevent multiple queue processors
    retry_task_running = True

    try:
        backoff = 10  # Start with 10 seconds
        max_backoff = 300  # Cap at 5 minutes

        while not message_queue.empty():
            # Get the next message
            message = await message_queue.get()
            game_data = message["data"]
            attempts = message.get("attempts", 0)

            # Try to send it
            logger.info(
                f"Retrying queued game {game_data['gameId']} (previous attempts: {attempts})")

            if crash_monitor:
                try:
                    success = await crash_monitor.add_game_event(game_data)
                    if success:
                        logger.info(
                            f"Successfully sent previously queued game: {game_data['gameId']}")
                        message_queue.task_done()
                        # Reset backoff on success
                        backoff = 10
                        continue
                except Exception as e:
                    logger.error(f"Error sending queued game: {str(e)}")

            # If failed, either requeue with incremented attempts or discard if too old
            timestamp = datetime.fromisoformat(message["timestamp"])
            age_seconds = (datetime.now() - timestamp).total_seconds()

            # Discard if older than 30 minutes
            if age_seconds > 1800:
                logger.info(
                    f"Discarding old game data: {game_data['gameId']} (age: {age_seconds:.0f}s)")
                message_queue.task_done()
            else:
                # Requeue with incremented attempts
                message["attempts"] = attempts + 1
                await message_queue.put(message)
                message_queue.task_done()

                # Apply exponential backoff
                logger.info(
                    f"Waiting {backoff} seconds before next retry (queue size: {message_queue.qsize()})")
                await asyncio.sleep(backoff)
                # Double the backoff time, capped at max
                backoff = min(backoff * 2, max_backoff)

    finally:
        # Clear flag when done
        retry_task_running = False
        if not message_queue.empty():
            # If there are still items, restart the task after a delay
            logger.info(
                f"Queue still has {message_queue.qsize()} items, restarting processor in 30s")
            await asyncio.sleep(30)
            asyncio.create_task(process_message_queue())


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

    logger.info("Added anti-bot detection measures")


async def monitor_crash_game(headless=False):
    """Main function to monitor the crash game using real-time detection with async Playwright

    Args:
        headless: Whether to run in headless mode (no visible browser window)
    """
    global observer_running

    logger.info("Starting crash monitoring...")
    observer_running = True

    # Start status update loop
    status_task = asyncio.create_task(status_update_loop())

    try:
        async with async_playwright() as p:
            # Launch browser locally
            browser = None

            try:
                # Set up a more realistic browser configuration
                logger.info(
                    "Starting local browser session with anti-detection measures...")

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
                logger.info("Warming up browser...")
                await page.goto("https://www.google.com", wait_until="domcontentloaded")
                await asyncio.sleep(1)

                # Navigate to the crash game page with adjusted timeouts
                logger.info("Navigating to BC.game crash page...")

                # Set a longer timeout but wait only for DOM content
                await page.goto(
                    "https://bc.game/game/crash",
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                logger.info(f"Page loaded: {await page.title()}")

                # Wait for the page to become interactive
                logger.info("Waiting for page to stabilize...")
                try:
                    # Wait for main content to appear
                    await page.wait_for_selector("div.game-crash", timeout=30000)
                except:
                    logger.warning(
                        "Timeout waiting for crash game interface, but continuing anyway...")

                # Add random delay to appear more human-like
                await asyncio.sleep(random.uniform(2, 4))

                # Clear any overlays once at startup
                logger.info("Clearing any overlays...")
                await clear_overlays(page)

                # Open the history tab
                logger.info("Opening history tab...")
                if not await open_history_tab(page):
                    raise Exception("Could not open history tab")

                # Take a screenshot to help debug
                screenshot_path = "history_tab_opened.png"
                await page.screenshot(path=screenshot_path)
                logger.info(f"Saved screenshot as {screenshot_path}")

                # Expose the callback to the page context
                logger.info("Setting up real-time crash monitoring...")
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

                logger.info(
                    "Real-time crash monitoring has been set up with zero-lag detection")
                logger.info("Monitoring for all crash points...")
                logger.info("Press Ctrl+C to stop monitoring")

                # Keep the browser open until manually stopped
                try:
                    # Keep the script running with a completely event-driven approach
                    while observer_running:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Monitoring stopped by user")
                except asyncio.CancelledError:
                    logger.info("Observer task cancelled")
                    raise

            except Exception as e:
                logger.error(f"An error occurred: {str(e)}")
                if page:
                    await page.screenshot(path="error_screenshot.png")
                    logger.info(
                        "Saved error screenshot as error_screenshot.png")
                raise  # Re-raise to inform the caller

            finally:
                if browser:
                    await browser.close()
                    logger.info("Browser session closed")
    finally:
        # Make sure we clean up properly
        observer_running = False

        # Cancel status update task
        if status_task and not status_task.done():
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass


async def main():
    logger.info("Starting BC Game Crash Observer")
    logger.info("Observing crash games in real-time")

    global API_ENDPOINT

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="BC Game Crash Observer")
    parser.add_argument("--headless", action="store_true",
                        help="Run in headless mode")
    parser.add_argument("--api-endpoint", default=API_ENDPOINT,
                        help=f"API endpoint URL (default: {API_ENDPOINT})")

    # Parse only known args to allow for other arguments
    args, _ = parser.parse_known_args()

    # Update API endpoint from command line
    API_ENDPOINT = args.api_endpoint
    logger.info(f"Using API endpoint: {API_ENDPOINT}")

    # Check if headless mode is specified
    headless_mode = args.headless
    if headless_mode:
        logger.info("Running in headless mode")
    else:
        logger.info("Running in visible browser mode")

    # First, try to connect to the monitor
    if await connect_to_monitor():
        logger.info("Connected to BC Game Crash Monitor")
    else:
        logger.warning("Warning: Could not connect to BC Game Crash Monitor")
        logger.warning(
            "Make sure to run 'python -m src monitor --skip-catchup --event-driven' first")
        logger.warning(
            "Continuing anyway but crash events may not be processed correctly")

    # Main monitoring with automatic recovery
    while True:
        try:
            await monitor_crash_game(headless=headless_mode)
        except Exception as e:
            logger.error(f"Critical error: {str(e)}")
            logger.error("Restarting monitor in 30 seconds...")
            await asyncio.sleep(30)


if __name__ == "__main__":
    # If the script is being run directly, use the main function
    asyncio.run(main())
else:
    # If the script is being imported, expose the main function
    # This allows the monitor to import and run this script directly
    __all__ = ['monitor_crash_game', 'handle_new_crash']
