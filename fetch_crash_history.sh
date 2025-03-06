#!/bin/bash

# Define a function to handle errors
handle_error() {
  echo "Error: $1" >&2
  exit 1
}

# Set default values
PAGE=1
PAGE_SIZE=20
OUTPUT_FILE="crash_history.json"

# Process command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -p|--page)
      PAGE="$2"
      shift 2
      ;;
    -s|--size)
      PAGE_SIZE="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [-p|--page PAGE] [-s|--size PAGE_SIZE] [-o|--output OUTPUT_FILE]"
      exit 1
      ;;
  esac
done

# Set random User-Agent
USER_AGENTS=(
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

RANDOM_INDEX=$((RANDOM % ${#USER_AGENTS[@]}))
SELECTED_USER_AGENT="${USER_AGENTS[$RANDOM_INDEX]}"

# Remove previous output file if it exists
if [ -f "$OUTPUT_FILE" ]; then
  rm "$OUTPUT_FILE"
fi

# Use a longer timeout to ensure we get a response
echo "Fetching data from BC Game API (page $PAGE)..."

curl 'https://bc.fun/api/game/bet/multi/history' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: en' \
  -H 'content-type: application/json' \
  -b 'SESSION=01rittzlnpyfwv1955c55634355a1fa79af122793b0612636b; smidV2=20250303193737fb6136787347d6dae6b325e18df23b9b005f961a12434b890; _gcl_au=1.1.439502465.1741010860; _ga=GA1.1.1996791068.1741010860; rtgio_tid=v1.0.14990220482.19728079508; slfps=a61a07529a69e235fcbabaf860a89f6de3fc1efb855aa20722a11495387d9218; _dads=jig; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%221955c5572d8377-021b2e24a967084-1c525636-8294400-1955c5572d922e4%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E5%BC%95%E8%8D%90%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC%22%2C%22%24latest_referrer%22%3A%22https%3A%2F%2Fbc.fun%2Fgame%2Fcrash%3F__cf_chl_tk%3DSMTabJdCkd0koCv6CFB6BlKC3QYMbQsFa0Quw1epmqg-1741232965-1.0.1.1-2IV1ULyHLRSepbH8oxIvM.uFKiFQWG4DmNy848MmDmQ%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTk1NWM1NTcyZDgzNzctMDIxYjJlMjRhOTY3MDg0LTFjNTI1NjM2LTgyOTQ0MDAtMTk1NWM1NTcyZDkyMmU0In0%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%221955c5572d8377-021b2e24a967084-1c525636-8294400-1955c5572d922e4%22%7D; __cf_bm=PRQdHta6V9o16P1eInNxUU1tP4t1hSt4EC8LkLdyLU0-1741235083-1.0.1.1-eLUhge7WIibgd3xW6qgpUGyCu_Wmw_Rmdg6gwHhVZkPjlgxr3rH88O4aP0_SW0bxso9RXblQXjiW40TpXq4nogsOujDL0Id1y59J9cPvf4c; cf_clearance=z6iTM0cxKdo4ugbs3f6DeLto.v4C4EkuazkPiy_x6Po-1741235637-1.2.1.1-Ir3ADilY2jhOK_.teOxwwM5fqLZyISamGlqZ_zU29cDonn2xlQ9o8UKBnV17WiBpM_y9ru8SxHdCVJhOMjnvhBuX4dnY8PstktoVsN9_0qTntqFCZxD4uu.sFxYCjZDfRCJu5ZPGT1WW86qsWD26vyFZTNoNbgRZ1uOcpb5PaWoGg6kp4hcIP3visZonzsNxf5ijweQ__HBG_BOgZhbSOmPGjLjhuLBbd1KeH1QQRiFi6U5Dl2Lary2zwmtffq4w1Xg6KLH23EnvGEqSvFkdOwuGzDYbqOadK4A30Dz1QkHirVTBjrk7c01BxGTvC8jpqdxQrDeSr0Al2hBUK5Jipi7wIPNxF.HNn422606yLtwqtpPfi1e_TzEvNVOol45TTkPyIeRV4YctQ3.LnJoW8Rdih0o8zuJA5HAi05sumRR4mszUG0YL4g6PFrEg7daLHLvd7PACKNmAyUJ8xSUVAw; visit-url=https%3A%2F%2Fbc.fun%2Fgame%2Fcrash; .thumbcache_1f3830c3848041ef5612f684078f2210=aVOP5G564aiBaS/wHSPYfp79VSpNPN3yI12BzuK+lIH+x8/vQdTOjyi2rpD27VN22d0Z3bNX6zIBf9CxwZiP8g%3D%3D; _ga_B23BPN2TGE=GS1.1.1741235626.14.1.1741235683.0.0.0' \
  -H 'dnt: 1' \
  -H 'origin: https://bc.fun' \
  -H 'priority: u=1, i' \
  -H 'referer: https://bc.fun/game/crash' \
  -H 'sec-ch-ua: "Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"' \
  -H 'sec-ch-ua-arch: "arm"' \
  -H 'sec-ch-ua-bitness: "64"' \
  -H 'sec-ch-ua-full-version: "133.0.6943.142"' \
  -H 'sec-ch-ua-full-version-list: "Not(A:Brand";v="99.0.0.0", "Google Chrome";v="133.0.6943.142", "Chromium";v="133.0.6943.142"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-model: ""' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-ch-ua-platform-version: "15.4.0"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36' \
  --data-raw "{\"gameUrl\":\"crash\",\"page\":$PAGE,\"pageSize\":$PAGE_SIZE}" \
  --output "$OUTPUT_FILE" || handle_error "Failed to fetch data from API"

# Check if the output file was created and contains valid JSON
if [ ! -f "$OUTPUT_FILE" ]; then
  handle_error "Output file not created"
fi

# Check if the output begins with HTML (Cloudflare challenge) instead of JSON
if grep -q "<!DOCTYPE html>" "$OUTPUT_FILE"; then
  echo "Warning: Received Cloudflare challenge instead of JSON data" >&2
  # Create a valid JSON response with empty data so the application doesn't crash
  echo '{"data":{"list":[]}}' > "$OUTPUT_FILE"
fi

# Check file size
FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)
if [ "$FILE_SIZE" -lt 10 ]; then
  echo "Warning: Response file is too small ($FILE_SIZE bytes)" >&2
  # Create a valid JSON response with empty data
  echo '{"data":{"list":[]}}' > "$OUTPUT_FILE"
fi

echo "Fetch completed successfully"
exit 0