from models.schemas import CustomerData
from typing import Dict, Any

def compute_revenue_intelligence(customer: CustomerData, risk_pct: float, health_score: int) -> Dict[str, Any]:
    """
    Computes executive-friendly revenue metrics.
    """
    current_value = customer.total_amount_paid or 0.0
    # Annualize plan price for at-risk calculation
    annual_contract_value = customer.avg_plan_price * 12
    estimated_revenue_at_risk = annual_contract_value * (risk_pct / 100.0)
    
    if risk_pct > 70 and estimated_revenue_at_risk > 10000:
        retention_priority = "CRITICAL"
        revenue_priority = "TIER 1 - IMMEDIATE SAVE"
    elif risk_pct > 50 and estimated_revenue_at_risk > 5000:
        retention_priority = "HIGH"
        revenue_priority = "TIER 2 - HIGH VALUE AT RISK"
    elif health_score > 80 and estimated_revenue_at_risk < 1000:
        retention_priority = "LOW"
        revenue_priority = "TIER 4 - STABLE"
    else:
        retention_priority = "MEDIUM"
        revenue_priority = "TIER 3 - STANDARD MONITORING"

    # Opportunity Score Calculation (0-100)
    # Weights: Health (30%), Usage (30%), NPS (20%), Revenue Tier (10%), VIP (10%)
    usage = getattr(customer, 'feature_usage_pct', 0) or 0
    nps = getattr(customer, 'nps_score', 5) or 5
    nps_norm = (nps / 10.0) * 100
    
    rev_tier = min(100, (current_value / 10000) * 100) if current_value else 50
    is_vip = getattr(customer, 'is_vip', customer.contract == "Enterprise")
    vip_bonus = 100 if is_vip else 0
    
    opportunity_score = (
        (health_score * 0.3) +
        (usage * 0.3) +
        (nps_norm * 0.2) +
        (rev_tier * 0.1) +
        (vip_bonus * 0.1)
    )
    opportunity_score = round(min(100, max(0, opportunity_score)), 1)

    return {
        "current_customer_value": round(current_value, 2),
        "estimated_revenue_at_risk": round(estimated_revenue_at_risk, 2),
        "retention_priority": retention_priority,
        "revenue_priority": revenue_priority,
        "opportunity_score": opportunity_score
    }
