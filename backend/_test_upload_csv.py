import requests
import json

CSV_PAYLOAD = """user_id,avg_plan_price,total_amount_paid,total_transactions,billing_tenure_days,auto_renew_count,total_cancellations,cancel_rate
CUST-ALPHA-HIGH,250,2500,10,45,0,3,0.65
CUST-BETA-MED,100,1200,12,180,1,1,0.25
CUST-GAMMA-LOW,50,600,12,365,5,0,0.00
"""

def run_test():
    url = "http://127.0.0.1:8000/api/v1/customers/upload-csv"
    print(f"🚀 Sending CSV batch upload to {url}...")
    try:
        resp = requests.post(url, json={"csv_text": CSV_PAYLOAD.strip()}, timeout=60)
        print(f"Status Code: {resp.status_code}")
        print("Response JSON:")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"❌ Error calling upload API: {e}")

if __name__ == "__main__":
    run_test()
