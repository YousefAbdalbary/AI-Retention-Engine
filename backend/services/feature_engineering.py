from datetime import datetime
from models.schemas import CustomerData

def engineer_features(customer: CustomerData) -> CustomerData:
    """
    Automatically generates missing model features and engineered metrics from raw data.
    """
    
    # 1. Billing Tenure Days
    if customer.billing_tenure_days is None:
        if customer.first_purchase:
            try:
                # Try parsing standard YYYY-MM-DD
                first = datetime.fromisoformat(customer.first_purchase.split("T")[0])
                last = datetime.fromisoformat(customer.last_activity.split("T")[0]) if customer.last_activity else datetime.utcnow()
                customer.billing_tenure_days = max(1, (last - first).days)
            except Exception:
                customer.billing_tenure_days = 365 # Default if unparseable
        else:
            customer.billing_tenure_days = 365 # Default

    # 2. Total Amount Paid
    if customer.total_amount_paid is None:
        # If we have transactions and an avg plan price, we can estimate
        customer.total_amount_paid = float(customer.avg_plan_price * customer.total_transactions)

    # 3. Cancel Rate
    if customer.cancel_rate is None:
        if customer.total_transactions > 0:
            customer.cancel_rate = float(customer.total_cancellations / customer.total_transactions)
        else:
            customer.cancel_rate = 0.0
            
    # 4. Email Open Rate
    if customer.email_open_rate is None:
        if customer.emails_sent > 0:
            customer.email_open_rate = float(customer.emails_opened / customer.emails_sent)
        else:
            customer.email_open_rate = 0.0

    return customer
