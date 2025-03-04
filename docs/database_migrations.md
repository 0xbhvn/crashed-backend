# Database Schema Migration Guide

This guide explains how to manage database schema changes in the BC Game Crash Monitor application.

## Current Database Schema Management

Currently, the application uses SQLAlchemy's `create_all` method to create tables if they don't exist. In `src/sqlalchemy_db.py`, this is implemented as:

```python
def create_tables(self):
    """Create all tables defined in the models."""
    Base.metadata.create_all(self.engine)
    logger.info("Database tables created")
```

This approach has limitations:

- It only creates new tables, it doesn't modify existing tables
- When you change a model, you need to manually update the database schema

## Using Alembic for Schema Migrations

For a more robust solution, we've integrated Alembic, SQLAlchemy's migration tool. Here's how to use it:

### Prerequisites

1. Install Alembic:

   ```bash
   pip install alembic
   ```

2. Initialize Alembic (already done):

   ```bash
   alembic init migrations
   ```

### Workflow for Schema Changes

When you need to modify the database schema (e.g., add a column, change a data type):

1. **Update your SQLAlchemy models in `src/models.py`**
   - Add new columns, modify existing ones, etc.

2. **Create a migration to reflect these changes**:

   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```

   - This creates a new file in `migrations/versions/` with the changes needed

3. **Review the generated migration**:
   - Check the migration file to ensure it correctly captures your changes
   - Make any necessary adjustments

4. **Apply the migration to update the database**:

   ```bash
   alembic upgrade head
   ```

   - This applies all pending migrations to bring the database up to date

5. **If something goes wrong, you can roll back**:

   ```bash
   alembic downgrade -1
   ```

   - This reverts the last migration

### Example: Adding a New Column

Let's say you want to add a `notes` column to the `CrashGame` model:

1. First, update `src/models.py`:

   ```python
   class CrashGame(Base):
       # ... existing columns ...
       notes = Column(String, nullable=True)
   ```

2. Create a migration:

   ```bash
   alembic revision --autogenerate -m "Add notes column to CrashGame"
   ```

3. Apply the migration:

   ```bash
   alembic upgrade head
   ```

### Common Commands

- **Create a migration**: `alembic revision --autogenerate -m "Message"`
- **Apply all migrations**: `alembic upgrade head`
- **Apply specific migrations**: `alembic upgrade +2` (apply next 2 migrations)
- **Revert migrations**: `alembic downgrade -1` (revert last migration)
- **Get current version**: `alembic current`
- **See migration history**: `alembic history`

## Alternative: Manual Schema Updates

If you prefer to manage schema changes manually:

1. Connect to your PostgreSQL database:

   ```bash
   psql postgresql://postgres@localhost:5432/bc_crash_db
   ```

2. Use SQL to modify the tables:

   ```sql
   -- Example: Adding a new column
   ALTER TABLE crash_games ADD COLUMN notes TEXT;
   
   -- Example: Modifying a column type
   ALTER TABLE crash_games ALTER COLUMN crash_point TYPE NUMERIC(10,2);
   
   -- Example: Renaming a column
   ALTER TABLE crash_games RENAME COLUMN old_name TO new_name;
   ```

## Limitations of Current Setup

The current approach has these limitations:

1. **No automated migrations**: When models change, database tables aren't automatically updated
2. **Risk of data loss**: Without proper migrations, there's a risk of data loss during schema changes
3. **No version control for schema**: Without Alembic, there's no easy way to track schema changes

## Recommendations

1. Use Alembic for all schema changes
2. Back up your database before applying migrations
3. Test migrations in a development environment before applying to production
4. Include migration files in your version control system
