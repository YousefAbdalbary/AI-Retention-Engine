import json
from typing import Any

from core.config import BASE_DIR, logger

STORE_FILE = BASE_DIR / "retention_customer_store.json"

def load_customers_from_store() -> list[dict[str, Any]]:
    """Load previously analyzed customers from the JSON store file."""
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded %d customers from store", len(data))
            return data
        except Exception as exc:
            logger.warning("Failed to load store file: %s", exc)
    return []

def save_customers_to_store():
    """Persist current customers to the JSON store file."""
    try:
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(CUSTOMERS, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to save store file: %s", exc)

# Global in-memory state
CUSTOMERS = load_customers_from_store()
CUSTOMERS_BY_ID = {customer["customer_id"]: customer for customer in CUSTOMERS}
RECENT_ANALYSES: dict[str, dict[str, Any]] = {}

def update_customer_in_store(customer: dict[str, Any]):
    """Helper to add or update a customer in memory and trigger save."""
    cid = customer["customer_id"]
    if cid in CUSTOMERS_BY_ID:
        CUSTOMERS[:] = [c for c in CUSTOMERS if c["customer_id"] != cid]
    CUSTOMERS.insert(0, customer)
    CUSTOMERS_BY_ID[cid] = customer
    RECENT_ANALYSES[cid] = customer
    save_customers_to_store()
