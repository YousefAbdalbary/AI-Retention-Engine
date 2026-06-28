import sqlite3
import json

conn = sqlite3.connect('backend/retention.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT data FROM customers")
rows = cursor.fetchall()
missing_risk = 0
for r in rows:
    data = json.loads(r['data'])
    if 'risk' not in data and 'risk_percentage' not in data:
        missing_risk += 1

print(f"Total rows: {len(rows)}")
print(f"Rows missing risk: {missing_risk}")
