# Railway Database Migration Guide

This guide explains how to manually run database migrations on Railway for the BC Game Crash Monitor application.

## Option 1: Using Railway Web Interface

1. Go to your Railway project dashboard
2. Select your application service
3. Click on the "Shell" tab
4. Run the following commands:

```bash
# Run all pending migrations
python -m src migrate upgrade --revision head

# Or to create a new migration
python -m src migrate create --autogenerate --message "Description of changes"
```

## Option 2: Using Railway CLI

1. Install the Railway CLI if you haven't already:

   ```bash
   npm i -g @railway/cli
   ```

2. Link to your project:

   ```bash
   railway link
   ```

3. Run a shell command on your application service:

   ```bash
   railway run python -m src migrate upgrade --revision head
   ```

## Troubleshooting

If migrations fail, you might need to:

1. **View migration logs**: In the Railway dashboard, check the logs from the migration command for specific errors.

2. **Reset the database**: In extreme cases, you might need to reset the database through the Railway dashboard:
   - Go to your PostgreSQL service
   - Click "Settings"
   - Look for a "Reset Database" option (use with caution - this deletes all data!)

3. **Check alembic_version table**: You can run a SQL query to see the current migration version:

   ```sql
   SELECT * FROM alembic_version;
   ```

4. **Manually create initial migration**: If you need to start from scratch:

   ```bash
   railway run python -m src migrate create --autogenerate --message "Initial migration"
   railway run python -m src migrate upgrade --revision head
   ```
