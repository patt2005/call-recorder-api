# Database Migration Guide

This project uses Flask-Migrate (based on Alembic) for database migrations.

## Configuration

The database connection string is configured in `main.py`:
```
postgresql://postgres:IHaqrKkfZMUkHIfsgotyNPJorsJzgMKP@shortline.proxy.rlwy.net:39111/railway
```

## Current Database Schema

### Tables:
1. **call_users** - Stores user information
   - id (UUID, primary key)
   - phone_number (String, unique)
   - country_code (String, nullable)
   - fcm_token (String)
   - push_notifications_enabled (Boolean)
   - created_at (DateTime)
   - updated_at (DateTime)

2. **calls** - Stores call recordings and transcriptions
   - id (String, primary key)
   - from_phone (String)
   - call_date (DateTime)
   - title (String)
   - summary (Text)
   - recording_url (String)
   - recording_duration (Integer)
   - recording_status (String)
   - transcription_text (Text)
   - transcription_status (String)

## Migration Commands

### Using Flask-Migrate CLI:
```bash
# Initialize migrations (already done)
FLASK_APP=main.py flask db init

# Create a new migration
FLASK_APP=main.py flask db migrate -m "Description of changes"

# Apply migrations to database
FLASK_APP=main.py flask db upgrade

# Revert to previous migration
FLASK_APP=main.py flask db downgrade
```

### Using the migration script:
```bash
# Apply migrations to database
python migrate.py upgrade

# Create a new migration
python migrate.py migrate

# Revert last migration
python migrate.py downgrade
```

## Making Database Changes

1. Modify the model files in `models/` directory
2. Create a migration: `FLASK_APP=main.py flask db migrate -m "Description"`
3. Review the generated migration in `migrations/versions/`
4. Apply the migration: `FLASK_APP=main.py flask db upgrade`

## Production Deployment

When deploying to production:
1. Ensure all model changes are committed
2. Run `FLASK_APP=main.py flask db upgrade` to apply migrations
3. The migration history is tracked in the `alembic_version` table

## Troubleshooting

- If tables already exist, you may need to stamp the database:
  ```bash
  FLASK_APP=main.py flask db stamp head
  ```

- To check current migration version:
  ```bash
  FLASK_APP=main.py flask db current
  ```

- To see migration history:
  ```bash
  FLASK_APP=main.py flask db history
  ```