# Database Migrations with Alembic

This project uses Alembic for database schema management. Migrations are automatically run on application startup to ensure the database schema is always up to date.

## Overview

- **Baseline Migration**: `0001_baseline.py` - Creates the initial database schema
- **Auto-migration**: Migrations run automatically when the app starts
- **Fallback**: Local development can use `DEV_CREATE_TABLES=true` for direct table creation

## Creating a New Migration

### 1. Generate Migration File

```bash
# Create a new migration with auto-detection of schema changes
alembic revision --autogenerate -m "description of changes"

# Create an empty migration file
alembic revision -m "description of changes"
```

### 2. Review and Edit Migration

The generated migration file will be in `alembic/versions/`. Review the generated SQL and modify if needed:

```python
def upgrade() -> None:
    # Add your schema changes here
    op.add_column('table_name', sa.Column('new_column', sa.String()))

def downgrade() -> None:
    # Add rollback logic here
    op.drop_column('table_name', 'new_column')
```

### 3. Test Migration

```bash
# Test upgrade
alembic upgrade head

# Test downgrade (if needed)
alembic downgrade -1
```

## Running Migrations

### Automatic (Production)

Migrations run automatically when the application starts. If migrations fail, the application will exit with an error.

### Manual

```bash
# Check current status
alembic current

# Check migration history
alembic history

# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade 0002

# Downgrade
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade 0001
```

### Using Migration Utility

```bash
# Run migrations programmatically
python utils/migrate.py

# Check migration status
python utils/migrate.py status
```

## Development vs Production

### Development

Set `DEV_CREATE_TABLES=true` in your `.env` file to enable fallback table creation:

```bash
DEV_CREATE_TABLES=true
```

This allows the app to start even if migrations fail, useful for local development.

### Production

In production (Railway), migrations run automatically on startup. The fallback table creation is disabled to ensure schema consistency.

## Migration Files

- **`alembic.ini`**: Alembic configuration
- **`migrations/env.py`**: Migration environment setup
- **`migrations/script.py.mako`**: Migration file template
- **`migrations/versions/`**: Migration history files

## Best Practices

1. **Always test migrations** on a copy of production data
2. **Keep migrations small** and focused on single changes
3. **Test both upgrade and downgrade** paths
4. **Use descriptive names** for migration files
5. **Review auto-generated migrations** before applying

## Troubleshooting

### Migration Fails on Startup

1. Check database connection
2. Verify migration files are correct
3. Check for conflicting schema changes
4. Review application logs for specific errors

### Schema Drift

If the database schema doesn't match your models:

1. Create a new baseline migration
2. Or manually sync the schema and create a migration

### Common Issues

- **Enum type conflicts**: Ensure enum values match between migrations and models
- **Index conflicts**: Check for duplicate index names
- **Constraint violations**: Verify foreign key relationships

## Adding New Models

When adding new models to `models.py`:

1. Create a migration: `alembic revision --autogenerate -m "add new model"`
2. Review the generated migration
3. Test the migration locally
4. Commit the migration file

## Rollback Strategy

Always test downgrade operations:

```bash
# Test downgrade to previous version
alembic downgrade -1

# Verify schema is correct
alembic current
```

## Environment Variables

- `DATABASE_URL`: Primary database connection string
- `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`: Individual database components
- `DEV_CREATE_TABLES`: Enable fallback table creation (development only)
