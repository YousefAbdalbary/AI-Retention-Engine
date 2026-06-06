import sqlite3
import json
from core.config import BASE_DIR, logger

DB_FILE = BASE_DIR / "retention.sqlite3"

def get_db_connection():
    """Returns a new SQLite connection. The caller is responsible for closing it."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    try:
        with get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS emails (email_id TEXT PRIMARY KEY, data TEXT)")
            conn.commit()
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")

# Initialize db when this module is imported
init_db()
