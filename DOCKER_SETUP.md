# Docker Setup Guide

This guide explains how to run the Crash Monitor application using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10 or higher
- Docker Compose v2.0 or higher

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/crashed-backend.git
   cd crashed-backend
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and update the `BC_GAME_SALT` value with your actual salt.

3. **Start all services**

   ```bash
   docker compose up -d
   ```

   This will:
   - Build the application image
   - Start PostgreSQL database
   - Start Redis cache
   - Automatically run database migrations on startup
   - Start the Crash Monitor application

4. **Check service status**

   ```bash
   docker compose ps
   ```

## Service URLs

- **API**: <http://localhost:3000>
- **Health Check**: <http://localhost:8080>
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## Common Commands

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f crashed-backend
```

### Run database migrations manually

Migrations run automatically on container startup, but if needed:

```bash
docker compose exec crashed-backend python -m src.app migrate upgrade
```

### Stop all services

```bash
docker compose down
```

### Stop and remove all data

```bash
docker compose down -v
```

### Rebuild application image

```bash
docker compose build crashed-backend
```

### Access application shell

```bash
docker compose exec crashed-backend /bin/bash
```

### Run specific commands

```bash
# Catchup historical data
docker compose run --rm crashed-backend python -m src.app catchup --pages 50

# Show database migrations
docker compose run --rm crashed-backend python -m src.app db show
```

## Environment Variables

The Docker Compose setup uses environment variables defined in `.env`. Key variables:

- `BC_GAME_SALT`: Required for crash calculation
- `DATABASE_URL`: Pre-configured for Docker (uses service name)
- `REDIS_URL`: Pre-configured for Docker (uses service name)
- `LOG_LEVEL`: Set to DEBUG for more verbose logging
- `POLL_INTERVAL`: Adjust polling frequency (default: 5 seconds)

## Troubleshooting

### Services won't start

1. Check if ports are already in use:

   ```bash
   lsof -i :3000 -i :5432 -i :6379 -i :8080
   ```

2. View detailed logs:

   ```bash
   docker compose logs crashed-backend
   ```

### Database connection issues

The application waits for PostgreSQL and Redis to be healthy before starting. If you see connection errors:

1. Check database logs:

   ```bash
   docker compose logs postgres
   ```

2. Manually test connection:

   ```bash
   docker compose exec postgres psql -U postgres -d bc_crash_db
   ```

### Redis connection issues

1. Check Redis logs:

   ```bash
   docker compose logs redis
   ```

2. Test Redis connection:

   ```bash
   docker compose exec redis redis-cli ping
   ```

## Production Deployment

For production deployment:

1. Update `.env` with production values
2. Use specific image tags instead of building locally
3. Consider using Docker Swarm or Kubernetes for orchestration
4. Set up proper logging and monitoring
5. Use external volumes for data persistence

## Development Workflow

1. Make code changes
2. Rebuild the image:

   ```bash
   docker compose build crashed-backend
   ```

3. Restart the service:

   ```bash
   docker compose restart crashed-backend
   ```

Or use hot reload by mounting source code:

```bash
docker compose run --rm -v $(pwd)/src:/app/src crashed-backend python -m src.app monitor
```
