import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")

# Insert backend dir to path to import services
sys.path.insert(0, str(backend_dir))

from services.connectors import MixpanelConnector

def test_mixpanel():
    print("--- Mixpanel Connector Test ---")
    secret = os.environ.get("MIXPANEL_API_SECRET", "")
    pid = os.environ.get("MIXPANEL_PROJECT_ID", "")
    print(f"API Secret present: {bool(secret)}")
    print(f"Project ID: {pid}")
    
    conn = MixpanelConnector()
    print("Starting sync (limit 3)...")
    res = conn.sync(limit=3)
    
    print(f"Result Mode: {res.mode}")
    print(f"Total Fetched: {res.total}")
    if res.errors:
        print(f"Errors: {res.errors}")
    
    if res.customers:
        print("\nSample Data:")
        for c in res.customers:
            print(f" - {c['user_id']}: Risk Features [Price: {c['avg_plan_price']}, Tx: {c['total_transactions']}]")
    else:
        print("No customers fetched.")

if __name__ == "__main__":
    test_mixpanel()
