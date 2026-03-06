#!/usr/bin/env python
"""
Database migration script for the API application.
This script handles database migrations using Flask-Migrate.

Usage:
    python migrate.py init     - Initialize migration repository
    python migrate.py migrate  - Create a new migration
    python migrate.py upgrade  - Apply migrations to database
    python migrate.py downgrade - Revert last migration
"""

import sys
import os
from flask_migrate import Migrate, init, migrate, upgrade, downgrade
from main import app, db

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