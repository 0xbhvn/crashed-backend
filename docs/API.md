# BC Game Crash Monitor API

This document describes the API endpoints provided by the BC Game Crash Monitor.

## Getting Started

To start the application with only the API server (no polling), run:

```bash
python -m src.app monitor --skip-polling
```

This will start the API server without activating the polling mechanism that fetches data from BC Game. This is useful for local development and testing when you don't want to duplicate polling from your production instance.

## API Endpoints

### Get Games (with Pagination)

```bash
GET /api/games
```

Returns crash games from the database with pagination support.

### **Query Parameters**

- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 10, max: 100)

### **Headers**

- `X-Timezone` (optional): Timezone to use for datetime values in the response (e.g., 'America/New_York', 'Europe/London')

### **Example Response** with pagination

```json
{
  "status": "success",
  "count": 10,
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total_items": 250,
    "total_pages": 25,
    "has_next": true,
    "has_prev": false
  },
  "data": [
    {
      "gameId": "12345678",
      "hashValue": "abcdef123456789",
      "crashPoint": 2.5,
      "calculatedPoint": 2.5,
      "crashedFloor": 2,
      "endTime": "2023-01-01T17:30:00+05:30",
      "prepareTime": "2023-01-01T17:29:30+05:30",
      "beginTime": "2023-01-01T17:29:45+05:30"
    },
    // ... more games
  ]
}
```

### **Example Request with Pagination and Timezone**

```bash
curl -H "X-Timezone: America/New_York" "http://localhost:3000/api/games?page=2&per_page=20"
```

### Get Game by ID

```bash
GET /api/games/{game_id}
```

Returns a specific crash game by ID.

### **Path Parameters**

- `game_id`: The ID of the game to retrieve

### **Headers** (optional)

- `X-Timezone` (optional): Timezone to use for datetime values in the response (e.g., 'America/New_York', 'Europe/London')

### **Example Response** for a single game

```json
{
  "status": "success",
  "data": {
    "gameId": "12345678",
    "hashValue": "abcdef123456789",
    "crashPoint": 2.5,
    "calculatedPoint": 2.5,
    "crashedFloor": 2,
    "endTime": "2023-01-01T17:30:00+05:30",
    "prepareTime": "2023-01-01T17:29:30+05:30",
    "beginTime": "2023-01-01T17:29:45+05:30"
  }
}
```

### **Example Request with Timezone Header**

```bash
curl -H "X-Timezone: Europe/London" http://localhost:3000/api/games/12345678
```

> **Note:** All datetime values are returned in the timezone specified by:
>
> 1. The `X-Timezone` header (if provided in the request)
> 2. Indian Standard Time (Asia/Kolkata) if the environment variable `TIMEZONE` is set to 'UTC' or not specified
> 3. The timezone specified by the `TIMEZONE` environment variable
>
> You can use any valid timezone name from the IANA timezone database, such as 'UTC', 'America/New_York', 'Europe/London', 'Asia/Kolkata', etc.

## Pagination

The `/api/games` endpoint supports pagination with the following parameters:

- `page`: The page number to retrieve (starts at 1)
- `per_page`: Number of items per page (default: 10, max: 100)

The response includes pagination metadata:

```json
"pagination": {
  "page": 1,            // Current page
  "per_page": 10,       // Items per page
  "total_items": 250,   // Total number of items
  "total_pages": 25,    // Total number of pages
  "has_next": true,     // Whether there is a next page
  "has_prev": false     // Whether there is a previous page
}
```

## Error Responses

All API endpoints return a JSON response with a `status` field indicating whether the request was successful or not. If an error occurs, the response will include a `message` field with more details.

Example error response:

```json
{
  "status": "error",
  "message": "Game with ID 12345678 not found"
}
```

## Configuration

The API server runs on port 3000 by default. You can change this by setting the `API_PORT` environment variable.

```bash
export API_PORT=8000
python -m src.app monitor --skip-polling
```

### Timezone Configuration

You can configure the default timezone for datetime values in API responses using:

1. **Request Header (preferred)**: Set the `X-Timezone` header in your API request for per-request timezone configuration.

   ```bash
   curl -H "X-Timezone: America/New_York" http://localhost:3000/api/games
   ```

2. **Environment Variable**: Set the `TIMEZONE` environment variable for server-wide configuration.

   ```bash
   export TIMEZONE=America/New_York
   python -m src.app monitor --skip-polling
   ```

Common timezone values:

- `UTC` (will use 'Asia/Kolkata' for API responses unless overridden by header)
- `America/New_York`
- `Europe/London`
- `Asia/Kolkata` (Indian Standard Time)
- `Asia/Tokyo`
- `Australia/Sydney`

If an invalid timezone is specified in the header, the API will fall back to the default timezone (Asia/Kolkata).
