import json
import shutil
from typing import Any

from core.config import BASE_DIR, logger
from core.db import get_db_connection

STORE_FILE_JSON = BASE_DIR / "retention_customer_store.json"

async def async_load_customers_from_store() -> list[dict[str, Any]]:
    """Load previously analyzed customers from the SQLite store asynchronously."""
    import asyncio
    
    def _load_sync():
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM customers")
                rows = cursor.fetchall()
                
                if rows:
                    data = [json.loads(row["data"]) for row in rows]
                    logger.info("Loaded %d customers from SQLite store", len(data))
                    return data
                
                # Auto-migrate from JSON if SQLite is empty
                if STORE_FILE_JSON.exists():
                    logger.info("SQLite store empty, migrating from JSON...")
                    with open(STORE_FILE_JSON, "r", encoding="utf-8") as f:
                        json_data = json.load(f)
                    
                    # Insert all records into SQLite
                    for cust in json_data:
                        cid = cust["customer_id"]
                        cursor.execute(
                            "INSERT OR REPLACE INTO customers (customer_id, data) VALUES (?, ?)",
                            (cid, json.dumps(cust, ensure_ascii=False))
                        )
                    conn.commit()
                    
                    # Backup old JSON file
                    backup_path = STORE_FILE_JSON.with_suffix(".json.bak")
                    shutil.move(str(STORE_FILE_JSON), str(backup_path))
                    logger.info(f"Migration complete. Migrated {len(json_data)} customers. Backed up to {backup_path.name}")
                    return json_data
                    
        except Exception as exc:
            logger.warning("Failed to load or migrate customer store: %s", exc)
        return []
        
    return await asyncio.to_thread(_load_sync)

def save_customers_to_store():
    """Persist current customers to the SQLite store. Provided for backwards compatibility."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for cust in CUSTOMERS:
                cursor.execute(
                    "INSERT OR REPLACE INTO customers (customer_id, data) VALUES (?, ?)",
                    (cust["customer_id"], json.dumps(cust, ensure_ascii=False))
                )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to sync store: %s", exc)

# Global in-memory state
CUSTOMERS = []
CUSTOMERS_BY_ID = {}
RECENT_ANALYSES: dict[str, dict[str, Any]] = {}

def update_customer_in_store(customer: dict[str, Any]):
    """Helper to add or update a customer in memory and trigger save."""
    cid = customer["customer_id"]
    if cid in CUSTOMERS_BY_ID:
        CUSTOMERS[:] = [c for c in CUSTOMERS if c["customer_id"] != cid]
    CUSTOMERS.insert(0, customer)
    CUSTOMERS_BY_ID[cid] = customer
    RECENT_ANALYSES[cid] = customer
    
    # Save atomically to SQLite
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO customers (customer_id, data) VALUES (?, ?)",
                (cid, json.dumps(customer, ensure_ascii=False))
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to save customer to SQLite store: %s", exc)
