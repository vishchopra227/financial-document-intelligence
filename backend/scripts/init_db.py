"""Standalone script to initialize the FinSight Intelligence database schema.
Run this script to initialize MySQL or local SQLite tables.
"""

import sys
from pathlib import Path

# Add backend parent to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.config import settings
from backend.app.db.session import init_db, get_db_status

if __name__ == "__main__":
    print(f"Initializing FinSight Intelligence database schema...")
    status = get_db_status()
    print(f"Current DB status: {status}")
    init_db()
    print("Database schema successfully created!")
