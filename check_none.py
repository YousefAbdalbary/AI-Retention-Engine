import sqlite3
import json
conn = sqlite3.connect('backend/retention.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT data FROM customers")
rows = cursor.fetchall()
for r in rows:
    d = json.loads(r['data'])
    rev = d.get('revenue')
    risk = d.get('risk')
    if rev is None or risk is None:
        print(f"Customer {d.get('customer_id')} has rev={rev}, risk={risk}")
