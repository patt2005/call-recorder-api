#!/usr/bin/env python
"""
Database migration script for the API application.
This script handles database migrations using Flask-Migrate.

Usage:
    python database/migrate.py init     - Initialize migration repository
    python database/migrate.py migrate  - Create a new migration
    python database/migrate.py upgrade  - Apply migrations to database
    python database/migrate.py downgrade - Revert last migration
"""

import sys
from pathlib import Path

# Add project root to path so "main" can be imported when run as python database/migrate.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask_migrate import init, migrate, upgrade, downgrade
from main import app

def run_migration(command):
    """Execute migration command"""
    with app.app_context():
        if command == 'init':
            print("Initializing migration repository...")
            init()
            print("Migration repository initialized successfully!")
            
        elif command == 'migrate':
            message = input("Enter migration message: ")
            print(f"Creating migration: {message}")
            migrate(message=message)
            print("Migration created successfully!")
            
        elif command == 'upgrade':
            print("Applying migrations to database...")
            upgrade()
            print("Database upgraded successfully!")
            
        elif command == 'downgrade':
            print("Reverting last migration...")
            downgrade()
            print("Database downgraded successfully!")
            
        else:
            print(f"Unknown command: {command}")
            print("Available commands: init, migrate, upgrade, downgrade")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate.py [init|migrate|upgrade|downgrade]")
        sys.exit(1)
    
    command = sys.argv[1]
    run_migration(command)