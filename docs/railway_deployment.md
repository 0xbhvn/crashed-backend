# Railway Deployment Guide

This guide explains how to deploy the Crash Monitor application to Railway with a PostgreSQL database.

## Prerequisites

- A [Railway](https://railway.app/) account
- Your project code pushed to a GitHub repository

## Deployment Steps

### 1. Create a New Project in Railway

1. Log in to [Railway](https://railway.app/)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account if not already connected
5. Select the repository

### 2. Add a PostgreSQL Database

1. In your Railway project, click "New" and select "Database" → "PostgreSQL"
2. Wait for the database to be provisioned

### 3. Connect Your Application to the Database

Railway automatically creates environment variables for your PostgreSQL database:

- `DATABASE_URL`: The full connection string to your database

No code changes are needed because the application already reads the `DATABASE_URL` environment variable.

### 4. Configure Environment Variables

Set additional environment variables in the Railway dashboard:

1. Go to your Railway project dashboard
2. Click on your application (not the database)
3. Navigate to the "Variables" tab
4. Add the following environment variables:
   - `DATABASE_ENABLED=true`
   - `BC_GAME_SALT` (if needed)
   - Any other environment variables from your local `.env` file

### 5. Application Configuration

The application is configured with a Procfile that runs database migrations and starts the monitor with the `--skip-catchup` flag:

```bash
web: sh -c 'python -m src migrate upgrade --revision head && python -m src monitor --skip-catchup'
```

This prevents the catchup process from running during initialization, which helps avoid unnecessary API calls and database operations on startup.

### 6. Run Database Migrations

After deployment, you'll need to run database migrations. You can do this using the Railway CLI or by connecting to the application's shell in the Railway dashboard:

```bash
python -m src migrate revision --autogenerate -m "Initial migration"
python -m src migrate upgrade head
```

### Troubleshooting

- **Database Connection Issues**: Check if the `DATABASE_URL` environment variable is correctly set by Railway. You can view this in the Variables tab.
- **Migration Errors**: If migrations fail, you may need to manually connect to the database and drop all tables before re-running migrations.
- **Application Crashes**: Check the logs in the Railway dashboard for error messages.

## Monitoring and Maintenance

- You can view application logs in the Railway dashboard
- To update your application, simply push changes to your GitHub repository
- To backup your database, use the Railway CLI or dashboard
