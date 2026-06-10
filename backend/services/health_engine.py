from models.schemas import CustomerData

def calculate_health_score(customer: CustomerData, risk_pct: float) -> tuple[int, str]:
    """
    Computes a normalized 0-100 Account Health Score and a Trend.
    account_health_score = ( (100-Risk)*0.4 ) + ( FeatureUsage*0.25 ) + ( (NPS*10)*0.2 ) + ( EmailRate*100*0.1 ) - (Tickets*2)
    """
    inverse_risk = (100 - risk_pct) * 0.40
    feature_usage = customer.feature_usage_pct * 0.25
    nps_val = (customer.nps_score * 10) * 0.20
    email_rate = ((customer.email_open_rate or 0.0) * 100) * 0.10
    ticket_penalty = customer.support_tickets * 2
    
    raw_score = inverse_risk + feature_usage + nps_val + email_rate - ticket_penalty
    score = max(0, min(100, int(round(raw_score))))
    
    # Determine Health Trend
    # Demo heuristic: If usage is high and tickets are low, trend is improving.
    if customer.feature_usage_pct > 80 and customer.support_tickets < 2:
        trend = "improving"
    elif risk_pct > 50 or customer.support_tickets > 5:
        trend = "declining"
    else:
        trend = "stable"
        
    return score, trend
