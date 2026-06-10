from models.schemas import CustomerData

def segment_customer(customer: CustomerData, risk_pct: float) -> str:
    """
    Rules-based classification running before the LLM.
    Segments: Critical VIP, At-Risk Loyal Customer, Dissatisfied Customer, 
    Low Adoption Customer, Power User, Upsell Opportunity, Standard.
    """
    is_vip = customer.total_amount_paid and customer.total_amount_paid > 5000  # arbitrary threshold for VIP if not directly marked

    if risk_pct > 70 and is_vip:
        return "Critical VIP"
    if risk_pct > 60 and customer.billing_tenure_days and customer.billing_tenure_days > 365:
        return "At-Risk Loyal Customer"
    if customer.nps_score <= 6 or customer.support_tickets > 5:
        return "Dissatisfied Customer"
    if customer.feature_usage_pct < 30:
        return "Low Adoption Customer"
    if customer.feature_usage_pct > 80 and customer.nps_score >= 9:
        return "Power User"
    if risk_pct < 30 and customer.feature_usage_pct > 75:
        return "Upsell Opportunity"
    
    return "Standard Customer"
