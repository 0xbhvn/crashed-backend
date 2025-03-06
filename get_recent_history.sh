#!/bin/bash

# Script to get recent crash history from BC.GAME API with better error handling
# Usage: ./get_recent_history.sh

# Default arguments
OUTPUT_FILE="recent_history.json"
ERROR_FILE="recent_api_error.html"
TEMP_DIR="temp"
COOKIES_FILE="cf_cookies.txt"
USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Create temp directory if it doesn't exist
mkdir -p "$TEMP_DIR"

# Set URLs
API_URL="https://bc.game/api/game/support/crash/recent/history?_=$(date +%s%3N)"

echo "Fetching recent crash history..."

# Check if cookie file exists and get cf_clearance value
COOKIE=""
if [ -f "$COOKIES_FILE" ]; then
  echo "Using cookies from $COOKIES_FILE"
  CF_CLEARANCE=$(grep -m 1 "cf_clearance" "$COOKIES_FILE" | cut -d '=' -f2)
  CF_BM=$(grep -m 1 "__cf_bm" "$COOKIES_FILE" | cut -d '=' -f2)
  
  if [ -n "$CF_CLEARANCE" ]; then
    COOKIE="cf_clearance=$CF_CLEARANCE"
    echo "Found cf_clearance cookie"
  fi
  
  if [ -n "$CF_BM" ]; then
    if [ -n "$COOKIE" ]; then
      COOKIE="$COOKIE; __cf_bm=$CF_BM"
    else
      COOKIE="__cf_bm=$CF_BM"
    fi
    echo "Found __cf_bm cookie"
  fi
else
  echo "Warning: Cookie file $COOKIES_FILE not found"
fi

# Use curl to fetch data
echo "Making API request to $API_URL"
HTTP_CODE=$(curl -s -o "$TEMP_DIR/recent_response.txt" -w "%{http_code}" \
  -H "User-Agent: $USER_AGENT" \
  -H "Accept: application/json, text/plain, */*" \
  -H "Accept-Language: en-US,en;q=0.9" \
  -H "Referer: https://bc.game/" \
  -H "Origin: https://bc.game" \
  -H "Cookie: $COOKIE" \
  "$API_URL")

echo "HTTP response code: $HTTP_CODE"

# Check for success or handle errors
if [ "$HTTP_CODE" -eq 200 ]; then
  # Check if the response is valid JSON
  if grep -q "^\s*{" "$TEMP_DIR/recent_response.txt"; then
    # Check if the response contains Cloudflare challenge text
    if grep -q "Just a moment" "$TEMP_DIR/recent_response.txt" || grep -q "challenge" "$TEMP_DIR/recent_response.txt"; then
      echo "Error: Received Cloudflare challenge instead of JSON data"
      cp "$TEMP_DIR/recent_response.txt" "$ERROR_FILE"
      echo "Saved Cloudflare challenge response to $ERROR_FILE"
      
      # Return a valid JSON error response
      echo "{\"error\":\"cloudflare_challenge\",\"message\":\"Cloudflare is blocking access. Try refreshing cookies.\"}" | tee "$OUTPUT_FILE"
      exit 1
    else
      # Success! Move the response to the output file
      cp "$TEMP_DIR/recent_response.txt" "$OUTPUT_FILE"
      echo "Successfully retrieved recent crash history"
      
      # Count items in the response
      ITEMS_COUNT=$(grep -o '"crashPoint"' "$OUTPUT_FILE" | wc -l)
      echo "Found $ITEMS_COUNT items in the response"
      
      # Output the response
      cat "$OUTPUT_FILE"
      exit 0
    fi
  else
    echo "Error: Response is not valid JSON"
    cp "$TEMP_DIR/recent_response.txt" "$ERROR_FILE"
    echo "Saved error response to $ERROR_FILE"
    
    # Return a valid JSON error response
    echo "{\"error\":\"invalid_json\",\"message\":\"Response is not valid JSON\"}" | tee "$OUTPUT_FILE"
    exit 1
  fi
else
  echo "Error: HTTP code $HTTP_CODE"
  cp "$TEMP_DIR/recent_response.txt" "$ERROR_FILE"
  echo "Saved error response to $ERROR_FILE"
  
  # Try to determine the type of error
  ERROR_TYPE="unknown"
  if [ "$HTTP_CODE" -eq 403 ]; then
    ERROR_TYPE="forbidden"
    # Check if it's a Cloudflare challenge
    if grep -q "Just a moment" "$TEMP_DIR/recent_response.txt" || grep -q "challenge" "$TEMP_DIR/recent_response.txt"; then
      ERROR_TYPE="cloudflare_challenge"
    fi
  elif [ "$HTTP_CODE" -eq 429 ]; then
    ERROR_TYPE="rate_limited"
  elif [ "$HTTP_CODE" -eq 500 ]; then
    ERROR_TYPE="server_error"
  elif [ "$HTTP_CODE" -eq 0 ]; then
    ERROR_TYPE="connection_error"
  fi
  
  # Return a valid JSON error response
  echo "{\"error\":\"${ERROR_TYPE}\",\"http_code\":${HTTP_CODE},\"message\":\"HTTP error ${HTTP_CODE}\"}" | tee "$OUTPUT_FILE"
  exit 1
fi 