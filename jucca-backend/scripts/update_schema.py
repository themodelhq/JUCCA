#!/usr/bin/env python3
"""Update database schema for new SystemLog table."""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import text
from app.core.database import engine, SessionLocal

def update_schema():
    """Create SystemLog table if it doesn't exist."""
    db = SessionLocal()
    
    try:
        # Check if SystemLog table exists
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs'"))
        table_exists = result.fetchone()
        
        if table_exists:
            print("SystemLog table already exists. Skipping...")
        else:
            # Create SystemLog table
            create_sql = """
            CREATE TABLE system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level VARCHAR DEFAULT 'info',
                category VARCHAR NOT NULL,
                message TEXT,
                user_id INTEGER,
                ip_address VARCHAR,
                extra_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
            db.execute(text(create_sql))
            db.commit()
            print("SystemLog table created successfully!")
            
    except Exception as e:
        print(f"Error updating schema: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_schema()
