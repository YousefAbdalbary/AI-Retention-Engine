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
            100 - (sum(row["risk"] for row in CUSTOMERS) / len(CUSTOMERS)) * 0.42
        )
        avg_churn = round(sum(row["risk"] for row in CUSTOMERS) / len(CUSTOMERS), 2)
    else:
        saved_rate = 100
        avg_churn = 0

    top_alerts = sorted(
        high_risk, key=lambda row: (row["priority_score"], row["revenue"]), reverse=True
    )[:6]
    activity = []
    for index, row in enumerate(top_alerts):
        activity.append(
            {
                "id": f"ACT-{index + 1}",
                "message": f"{row['priority']} intervention queued for {row['customer_id']}",
                "customer_id": row["customer_id"],
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(minutes=index * 9 + 2)
                ).isoformat(),
                "severity": row["priority"],
            }
        )
    return {
        "total_customers": len(CUSTOMERS),
        "low_risk_users": len(low_risk),
        "medium_risk_users": len(medium_risk),
        "high_risk_band_users": len(high_risk_band),
        "critical_risk_users": len(critical_risk),
        "revenue_at_risk": round(
            sum(row["revenue"] * row["risk"] / 100 for row in high_risk), 2
        ),
        "vip_customers": len(vip_customers),
        "average_churn": avg_churn,
        "ai_interventions_triggered": len(interventions),
        "retention_success_rate": round(saved_rate, 2),
        "model_status": "online" if model is not None else "offline",
        "alerts": [
            {
                "customer_id": row["customer_id"],
                "risk": row["risk"],
                "priority": row["priority"],
                "message": row["llm_analysis"]["next_best_action"],
            }
            for row in top_alerts
        ],
        "activity_feed": activity,
        "generated_at": now_iso(),
    }


@router.get("/analytics")
async def analytics():
    risk_bands = {
        "Low": len([row for row in CUSTOMERS if row["risk"] < 40]),
        "Medium": len([row for row in CUSTOMERS if 40 <= row["risk"] < 64]),
        "High": len([row for row in CUSTOMERS if 64 <= row["risk"] < 85]),
        "Critical": len([row for row in CUSTOMERS if row["risk"] >= 85]),
    }
    segments = sorted({row["segment"] for row in CUSTOMERS})
    action_counts: dict[str, int] = {}
    for row in CUSTOMERS:
        action_counts[row["ai_decision"]] = action_counts.get(row["ai_decision"], 0) + 1

    monthly_trends = []
    if CUSTOMERS:
        for month in range(1, 13):
            avg_risk = sum(
                row["monthly_risk"][month - 1]["risk"] for row in CUSTOMERS
            ) / len(CUSTOMERS)
            monthly_trends.append(
                {
                    "month": f"M{month}",
                    "retention": round(100 - avg_risk * 0.38, 2),
                    "risk": round(avg_risk, 2),
                    "interventions": len(
                        [
                            row
                            for row in CUSTOMERS
                            if row["monthly_risk"][month - 1]["risk"] >= 64
                        ]
                    ),
                }
            )

    heatmap = []
    for segment in segments:
        segment_rows = [row for row in CUSTOMERS if row["segment"] == segment]
        heatmap.append(
            {
                "segment": segment,
                "low": len([row for row in segment_rows if row["risk"] < 40]),
                "medium": len([row for row in segment_rows if 40 <= row["risk"] < 64]),
                "high": len([row for row in segment_rows if 64 <= row["risk"] < 85]),
                "critical": len([row for row in segment_rows if row["risk"] >= 85]),
            }
        )

    return {
        "churn_distribution": risk_bands,
        "revenue_impact": {
            "Protected": round(
                sum(row["revenue"] for row in CUSTOMERS if row["risk"] < 40), 2
            ),
            "Watchlist": round(
                sum(row["revenue"] for row in CUSTOMERS if 40 <= row["risk"] < 64), 2
            ),
            "At Risk": round(
                sum(row["revenue"] for row in CUSTOMERS if row["risk"] >= 64), 2
            ),
        },
        "customer_segmentation": [
            {
                "segment": segment,
                "count": len([row for row in CUSTOMERS if row["segment"] == segment]),
                "avg_risk": round(
                    sum(row["risk"] for row in CUSTOMERS if row["segment"] == segment)
                    / max(
                        1, len([row for row in CUSTOMERS if row["segment"] == segment])
                    ),
                    2,
                ),
            }
            for segment in segments
        ],
        "risk_heatmap": heatmap,
        "vip_vs_non_vip": {
            "VIP": len([row for row in CUSTOMERS if row["is_vip"]]),
            "Non-VIP": len([row for row in CUSTOMERS if not row["is_vip"]]),
        },
        "monthly_retention_trends": monthly_trends,
        "ai_action_distribution": action_counts,
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
                "detail": f"{row['customer_id']} requires {row['priority']} action",
            }
            for row in sample[:3]
        ],
        "logs": [
            {
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(seconds=i * 38)
                ).isoformat(),
                "message": f"Retention workflow evaluated for {row['customer_id']}",
            }
            for i, row in enumerate(sample)
        ],
    }
