import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter

from services.store import CUSTOMERS
from services.ml_engine import model
from utils.helpers import now_iso

router = APIRouter()

@router.get("/dashboard-overview")
async def dashboard_overview():
    low_risk = [row for row in CUSTOMERS if row["risk"] < 40]
    medium_risk = [row for row in CUSTOMERS if 40 <= row["risk"] < 64]
    high_risk_band = [row for row in CUSTOMERS if 64 <= row["risk"] < 85]
    critical_risk = [row for row in CUSTOMERS if row["risk"] >= 85]

    high_risk = high_risk_band + critical_risk
    vip_customers = [row for row in CUSTOMERS if row["is_vip"]]
    interventions = [
        row for row in CUSTOMERS if row["ai_decision"] != "NO_ACTION_REQUIRED"
    ]

    if CUSTOMERS:
        saved_rate = (
            100 - (sum(row.get("risk", 0) for row in CUSTOMERS) / len(CUSTOMERS)) * 0.42
        )
        avg_churn = round(sum(row.get("risk", 0) for row in CUSTOMERS) / len(CUSTOMERS), 2)
        avg_health = round(sum(row.get("health_score", 50) for row in CUSTOMERS) / len(CUSTOMERS), 1)
    else:
        saved_rate = 100
        avg_churn = 0
        avg_health = 0

    top_alerts = sorted(
        high_risk, key=lambda row: (row.get("priority_score", 0), row.get("revenue", 0)), reverse=True
    )[:6]
    
    active_vips_at_risk = len([row for row in vip_customers if row.get("risk", 0) >= 64])
    
    revenue_at_risk = sum(
        row.get("revenue_intel", {}).get("estimated_revenue_at_risk", row.get("revenue", 0) * row.get("risk", 0) / 100) 
        for row in CUSTOMERS
    )

    activity = []
    for index, row in enumerate(top_alerts):
        activity.append(
            {
                "id": f"ACT-{index + 1}",
                "message": f"{row.get('priority', 'HIGH')} intervention queued for {row['customer_id']}",
                "customer_id": row["customer_id"],
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(minutes=index * 9 + 2)
                ).isoformat(),
                "severity": row.get("priority", "HIGH"),
            }
        )
        
    top_opportunities = sorted(
        CUSTOMERS, key=lambda row: row.get("revenue_intel", {}).get("opportunity_score", 0), reverse=True
    )[:5]
    
    opportunities = [
        {
            "customer_id": row["customer_id"],
            "opportunity_score": row.get("revenue_intel", {}).get("opportunity_score", 0),
            "health_score": row.get("health_score", 50),
            "revenue": row.get("revenue", 0)
        }
        for row in top_opportunities if row.get("revenue_intel", {}).get("opportunity_score", 0) > 50
    ]

    return {
        "total_customers": len(CUSTOMERS),
        "opportunities": opportunities,
        "low_risk_users": len(low_risk),
        "medium_risk_users": len(medium_risk),
        "high_risk_band_users": len(high_risk_band),
        "critical_risk_users": len(critical_risk),
        "revenue_at_risk": round(revenue_at_risk, 2),
        "vip_customers": len(vip_customers),
        "active_vips_at_risk": active_vips_at_risk,
        "average_churn": avg_churn,
        "average_health": avg_health,
        "ai_interventions_triggered": len(interventions),
        "retention_success_rate": round(saved_rate, 2),
        "model_status": "online" if model is not None else "offline",
        "alerts": [
            {
                "customer_id": row["customer_id"],
                "name": row.get("name", row["customer_id"]),
                "risk": row["risk"],
                "priority": row["priority"],
                "message": row.get("llm_analysis", {}).get("recommended_actions_ar", [""])[0] if row.get("llm_analysis") else "تحليل العميل مطلوب",
            }
            for row in top_alerts
        ],
        "activity_feed": activity,
        "generated_at": now_iso(),
    }


@router.get("/analytics")
async def analytics():
    risk_bands = {
        "Low": len([row for row in CUSTOMERS if row.get("risk", 0) < 40]),
        "Medium": len([row for row in CUSTOMERS if 40 <= row.get("risk", 0) < 64]),
        "High": len([row for row in CUSTOMERS if 64 <= row.get("risk", 0) < 85]),
        "Critical": len([row for row in CUSTOMERS if row.get("risk", 0) >= 85]),
    }
    
    health_distribution = {
        "Poor (0-39)": len([row for row in CUSTOMERS if row.get("health_score", 50) < 40]),
        "Fair (40-69)": len([row for row in CUSTOMERS if 40 <= row.get("health_score", 50) < 70]),
        "Good (70-89)": len([row for row in CUSTOMERS if 70 <= row.get("health_score", 50) < 90]),
        "Excellent (90-100)": len([row for row in CUSTOMERS if row.get("health_score", 50) >= 90]),
    }

    segments = sorted(list({row.get("segment", "Standard") for row in CUSTOMERS}))
    
    # NPS vs Feature Adoption Scatter Data
    scatter_data = [
        {
            "id": row.get("customer_id", ""),
            "nps": row.get("nps_score", 5),
            "adoption": row.get("feature_usage_pct", 0),
            "revenue": row.get("revenue", 0)
        }
        for row in CUSTOMERS
    ]

    action_counts: dict[str, int] = {}
    for row in CUSTOMERS:
        ai_decision = row.get("ai_decision", "NO_ACTION")
        action_counts[ai_decision] = action_counts.get(ai_decision, 0) + 1

    heatmap = []
    for segment in segments:
        segment_rows = [row for row in CUSTOMERS if row.get("segment", "Standard") == segment]
        heatmap.append(
            {
                "segment": segment,
                "low": len([row for row in segment_rows if row.get("risk", 0) < 40]),
                "medium": len([row for row in segment_rows if 40 <= row.get("risk", 0) < 64]),
                "high": len([row for row in segment_rows if 64 <= row.get("risk", 0) < 85]),
                "critical": len([row for row in segment_rows if row.get("risk", 0) >= 85]),
            }
        )

    return {
        "churn_distribution": risk_bands,
        "health_distribution": health_distribution,
        "revenue_impact": {
            "Protected": round(sum(row.get("revenue", 0) for row in CUSTOMERS if row.get("risk", 0) < 40), 2),
            "Watchlist": round(sum(row.get("revenue", 0) for row in CUSTOMERS if 40 <= row.get("risk", 0) < 64), 2),
            "At Risk": round(sum(row.get("revenue", 0) for row in CUSTOMERS if row.get("risk", 0) >= 64), 2),
        },
        "customer_segmentation": [
            {
                "segment": segment,
                "count": len([row for row in CUSTOMERS if row.get("segment", "Standard") == segment]),
                "avg_health": round(
                    sum(row.get("health_score", 50) for row in CUSTOMERS if row.get("segment", "Standard") == segment)
                    / max(1, len([row for row in CUSTOMERS if row.get("segment", "Standard") == segment])),
                    1,
                ),
            }
            for segment in segments
        ],
        "risk_heatmap": heatmap,
        "scatter_data": scatter_data,
        "vip_vs_non_vip": {
            "VIP": len([row for row in CUSTOMERS if row.get("is_vip")]),
            "Non-VIP": len([row for row in CUSTOMERS if not row.get("is_vip")]),
        },
        "ai_action_distribution": action_counts,
        "monthly_retention_trends": [
            {"month": "Jan", "retention": 92, "risk": 8},
            {"month": "Feb", "retention": 91, "risk": 9},
            {"month": "Mar", "retention": 93, "risk": 7},
            {"month": "Apr", "retention": 94, "risk": 6},
            {"month": "May", "retention": 95, "risk": 5},
            {"month": "Jun", "retention": 96, "risk": 4},
        ],
    }


@router.get("/realtime")
async def realtime_updates():
    high_risk_rows = [row for row in CUSTOMERS if row["risk"] >= 64]
    sample = random.sample(high_risk_rows, min(5, len(high_risk_rows)))
    return {
        "new_high_risk_customers": [
            {
                "customer_id": row["customer_id"],
                "risk": row["risk"],
                "priority": row["priority"],
            }
            for row in sample
        ],
        "alerts": [
            {
                "title": "AI intervention triggered",
                "detail": f"{row.get('name', row['customer_id'])} requires {row['priority']} action",
            }
            for row in sample[:3]
        ],
        "logs": [
            {
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(seconds=i * 38)
                ).isoformat(),
                "message": f"Retention workflow evaluated for {row.get('name', row['customer_id'])}",
            }
            for i, row in enumerate(sample)
        ],
    }
