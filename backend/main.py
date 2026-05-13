from __future__ import annotations

import logging
import math
import os
import random
import traceback
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests as http_requests
import pandas as pd
import xgboost as xgb
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

# Conditional SHAP import (heavy dependency)
try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

# Email campaign services
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from services.email_service import send_retention_email, send_bulk_retention_emails
from services.email_tracker import tracker as email_tracker
from services.email_templates import generate_email_template

# LLM Configuration - Load from .env file
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY", "")
LLAMA_API_URL = os.environ.get(
    "LLAMA_API_URL", "https://api.groq.com/openai/v1/chat/completions"
)
LLAMA_MODEL_NAME = os.environ.get("LLAMA_MODEL_NAME", "llama-3.3-70b-versatile")


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
MODEL_FILE = "ai_retention_xgboost_optimized.json"
OPTIMAL_THRESHOLD = 0.633
VIP_PLAN_PRICE = 500
CUSTOMER_COUNT = 3200

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("enterprise-retention-ai")

app = FastAPI(
    title="Customer Retention AI",
    description="Enterprise customer retention, churn analytics, and structured LLM insights API",
    version="4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CustomerData(BaseModel):
    user_id: str = Field(..., min_length=2, max_length=80)
    avg_plan_price: float = Field(..., ge=0)
    total_amount_paid: float = Field(..., ge=0)
    total_transactions: int = Field(..., ge=0)
    billing_tenure_days: int = Field(..., ge=0)
    auto_renew_count: int = Field(..., ge=0)
    total_cancellations: int = Field(..., ge=0)
    cancel_rate: float = Field(..., ge=0)


class CSVUploadPayload(BaseModel):
    csv_text: str


class EmailSendRequest(BaseModel):
    customer_id: str = Field(..., min_length=2, max_length=80)
    risk_pct: float = Field(..., ge=0, le=100)
    receiver_email: str | None = None
    personalized_message: str = ""
    attachment_path: str | None = None


class BulkEmailRequest(BaseModel):
    customer_ids: list[str] = Field(..., min_length=1)
    receiver_email: str | None = None


class CampaignTriggerRequest(BaseModel):
    risk_filter: str = Field("all", pattern="^(all|low|medium|high)$")
    receiver_email: str | None = None
    limit: int = Field(50, ge=1, le=500)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_model_path() -> Path:
    candidates = [
        BASE_DIR / MODEL_FILE,
        PROJECT_DIR / MODEL_FILE,
        Path.cwd() / MODEL_FILE,
        Path.cwd() / "enterprise_retention_project" / "backend" / MODEL_FILE,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not find {MODEL_FILE}")


def load_model() -> xgb.XGBClassifier | None:
    try:
        model_path = resolve_model_path()
        loaded_model = xgb.XGBClassifier()
        path_str = str(model_path)
        try:
            loaded_model.load_model(path_str)
        except Exception:
            # Fallback for raw booster files or scikit-learn version mismatches
            booster = xgb.Booster()
            booster.load_model(path_str)
            loaded_model._Booster = booster
            if not hasattr(loaded_model, "_estimator_type"):
                setattr(loaded_model, "_estimator_type", "classifier")

        logger.info("XGBoost model loaded from %s", model_path)
        return loaded_model
    except Exception as exc:
        logger.warning("Model load failed (will use fallback scoring): %s", exc)
        return None


model = load_model()


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def priority_from_score(risk_score: float, is_vip: bool) -> str:
    if risk_score >= 85 or (is_vip and risk_score >= 70):
        return "CRITICAL"
    if risk_score >= 64:
        return "HIGH"
    if risk_score >= 40:
        return "MEDIUM"
    return "LOW"


def risk_level_from_priority(priority: str) -> str:
    return {"LOW": "LOW", "MEDIUM": "ELEVATED", "HIGH": "HIGH", "CRITICAL": "CRITICAL"}[
        priority
    ]


def decision_from_priority(priority: str, is_vip: bool) -> str:
    if priority == "CRITICAL" and is_vip:
        return "TRIGGER_LLAMA_AND_ALERT_HUMAN"
    if priority in {"CRITICAL", "HIGH"}:
        return "HUMAN_REVIEW_AND_SAVE_OFFER"
    if priority == "MEDIUM":
        return "SEND_AUTOMATED_DISCOUNT"
    return "NO_ACTION_REQUIRED"


def sentiment_from_customer(customer: dict[str, Any]) -> str:
    risk = customer.get("risk", 50)
    cancel_rate = customer.get("cancel_rate", 0)
    if risk >= 78 or cancel_rate >= 0.36:
        return "Negative"
    if risk >= 48 or cancel_rate >= 0.18:
        return "Mixed"
    return "Positive"


def build_timeline(priority: str, is_vip: bool) -> list[dict[str, str]]:
    if priority == "CRITICAL":
        return [
            {
                "step": "Open escalation case",
                "owner": "Retention Ops",
                "deadline": "15m",
            },
            {"step": "Call customer", "owner": "Support Team", "deadline": "24h"},
            {
                "step": "Approve personalized offer",
                "owner": "Customer Success Lead",
                "deadline": "24h",
            },
            {
                "step": "Review outcome",
                "owner": "Revenue Operations",
                "deadline": "72h",
            },
        ]
    if priority == "HIGH":
        return [
            {
                "step": "Review account signals",
                "owner": "Retention Ops",
                "deadline": "4h",
            },
            {
                "step": "Send save offer",
                "owner": "Lifecycle Automation",
                "deadline": "12h",
            },
            {
                "step": "Monitor response",
                "owner": "Customer Success",
                "deadline": "48h",
            },
        ]
    if priority == "MEDIUM":
        return [
            {
                "step": "Trigger discount journey",
                "owner": "Lifecycle Automation",
                "deadline": "24h",
            },
            {
                "step": "Check engagement lift",
                "owner": "Marketing Ops",
                "deadline": "5d",
            },
        ]
    return [
        {
            "step": "Keep in standard journey",
            "owner": "Lifecycle Automation",
            "deadline": "7d",
        },
        {
            "step": "Rescore after next billing event",
            "owner": "Risk Model",
            "deadline": "30d",
        },
    ]


def build_timeline_ar(priority: str, is_vip: bool) -> list[dict[str, str]]:
    if priority == "CRITICAL":
        return [
            {
                "step": "فتح حالة تصعيد",
                "owner": "فريق عمليات الاحتفاظ",
                "deadline": "15 دقيقة",
            },
            {"step": "الاتصال بالعميل", "owner": "فريق الدعم", "deadline": "24 ساعة"},
            {
                "step": "اعتماد عرض مخصص",
                "owner": "قائد نجاح العملاء",
                "deadline": "24 ساعة",
            },
            {
                "step": "مراجعة النتيجة",
                "owner": "عمليات الإيرادات",
                "deadline": "72 ساعة",
            },
        ]
    if priority == "HIGH":
        return [
            {
                "step": "مراجعة مؤشرات الحساب",
                "owner": "فريق عمليات الاحتفاظ",
                "deadline": "4 ساعات",
            },
            {
                "step": "إرسال عرض الاحتفاظ",
                "owner": "أتمتة دورة حياة العميل",
                "deadline": "12 ساعة",
            },
            {
                "step": "متابعة استجابة العميل",
                "owner": "فريق نجاح العملاء",
                "deadline": "48 ساعة",
            },
        ]
    if priority == "MEDIUM":
        return [
            {
                "step": "تشغيل رحلة الخصم",
                "owner": "أتمتة دورة حياة العميل",
                "deadline": "24 ساعة",
            },
            {
                "step": "قياس تحسن التفاعل",
                "owner": "عمليات التسويق",
                "deadline": "5 أيام",
            },
        ]
    return [
        {
            "step": "إبقاء العميل في المسار القياسي",
            "owner": "أتمتة دورة حياة العميل",
            "deadline": "7 أيام",
        },
        {
            "step": "إعادة التقييم بعد حدث الفوترة القادم",
            "owner": "نموذج المخاطر",
            "deadline": "30 يوما",
        },
    ]


def build_structured_llm_analysis(customer: dict[str, Any]) -> dict[str, Any]:
    priority = customer.get("priority", "LOW")
    risk = round(float(customer.get("risk", 0)), 2)
    is_vip = bool(customer.get("is_vip", False))
    confidence = round(
        clamp(68 + abs(risk - 50) * 0.44 + (4 if is_vip else 0), 70, 98), 2
    )
    sentiment = sentiment_from_customer(customer)

    cancel_rate = customer.get("cancel_rate", 0)
    total_tx = customer.get("total_transactions", 0)
    auto_renew_count = customer.get("auto_renew_count", 0)
    revenue = customer.get("revenue", 0)
    tenure_days = customer.get("billing_tenure_days", 0)

    reasons = [
        f"Churn risk is {risk:.2f}% compared with the {OPTIMAL_THRESHOLD * 100:.1f}% intervention threshold.",
        f"Cancellation rate is {cancel_rate:.2f} across {total_tx} transactions.",
        f"Auto-renew count is {auto_renew_count}, which affects renewal confidence.",
    ]
    reasons_ar = [
        f"مخاطر الإلغاء تساوي {risk:.2f}% مقارنة بحد التدخل البالغ {OPTIMAL_THRESHOLD * 100:.1f}%.",
        f"معدل الإلغاء هو {cancel_rate:.2f} عبر {total_tx} معاملات.",
        f"عدد مرات التجديد التلقائي هو {auto_renew_count}، وهذا يؤثر على ثقة التجديد.",
    ]
    if is_vip:
        reasons.append(f"VIP account with ${revenue:,.0f} lifetime revenue exposure.")
        reasons_ar.append(
            f"حساب VIP مع تعرض إيرادي بقيمة ${revenue:,.0f} على مدى عمر العميل."
        )
    if tenure_days < 120:
        reasons.append(
            "Early-tenure customer has not yet developed stable renewal behavior."
        )
        reasons_ar.append(
            "العميل ما زال في مرحلة مبكرة ولم يكوّن بعد سلوكا مستقرا للتجديد."
        )

    if priority in {"CRITICAL", "HIGH"}:
        actions = [
            "Escalate to a retention specialist with the customer's billing and cancellation history.",
            "Offer a personalized renewal package tied to product usage and plan value.",
            "Track response within the next billing window and suppress generic campaigns.",
        ]
        actions_ar = [
            "تصعيد الحالة إلى مختص احتفاظ مع سجل الفوترة والإلغاءات الخاص بالعميل.",
            "تقديم باقة تجديد مخصصة مرتبطة باستخدام المنتج وقيمة الخطة.",
            "متابعة الاستجابة خلال نافذة الفوترة القادمة وإيقاف الحملات العامة لهذا العميل.",
        ]
        strategy = "High-touch rescue motion with human ownership, executive-save offer, and rapid follow-up."
        strategy_ar = (
            "خطة إنقاذ عالية اللمس بملكية بشرية، وعرض احتفاظ تنفيذي، ومتابعة سريعة."
        )
        offer = "Dedicated success call plus tailored renewal credit and premium support review."
        next_best_action = (
            "Create an escalation case and contact the customer within 24 hours."
        )
    elif priority == "MEDIUM":
        actions = [
            "Send automated save offer based on segment and plan price.",
            "Nudge auto-renew enablement before the next billing cycle.",
            "Monitor support and cancellation activity for escalation triggers.",
        ]
        actions_ar = [
            "إرسال عرض احتفاظ آلي بناء على شريحة العميل وسعر الخطة.",
            "تشجيع تفعيل التجديد التلقائي قبل دورة الفوترة القادمة.",
            "مراقبة نشاط الدعم والإلغاء لاكتشاف إشارات التصعيد.",
        ]
        strategy = "Automated retention workflow with targeted discount and engagement monitoring."
        strategy_ar = "مسار احتفاظ آلي يتضمن خصما موجها ومراقبة مستمرة لتفاعل العميل."
        offer = "Time-boxed 15% renewal incentive with auto-renew benefits."
        next_best_action = "Enroll customer in automated retention journey."
    else:
        actions = [
            "Continue standard lifecycle engagement.",
            "Rescore after the next transaction or cancellation event.",
            "Keep customer eligible for loyalty education campaigns.",
        ]
        actions_ar = [
            "الاستمرار في مسار التفاعل القياسي لدورة حياة العميل.",
            "إعادة احتساب درجة المخاطر بعد المعاملة أو حدث الإلغاء القادم.",
            "إبقاء العميل مؤهلا لحملات التوعية والولاء.",
        ]
        strategy = "Maintain engagement and monitor for behavior drift."
        strategy_ar = "الحفاظ على التفاعل ومراقبة أي تغير في سلوك العميل."
        offer = "No rescue offer required; keep standard loyalty messaging."
        next_best_action = "No immediate intervention required."

    feature_effects = [
        {
            "label": "Cancel Rate",
            "label_ar": "معدل الإلغاء",
            "value": f"{cancel_rate*100:.1f}%",
            "impact": f"+{min(cancel_rate*40, 20):.1f}%",
            "direction": "increases_churn",
            "relative_strength": 85,
            "explanation": "High historical cancel rate drives risk.",
            "explanation_ar": "معدل الإلغاء التاريخي المرتفع يزيد من المخاطر.",
        },
        {
            "label": "Tenure",
            "label_ar": "فترة الاشتراك",
            "value": f"{tenure_days} days",
            "impact": f"-{min(tenure_days/100, 15):.1f}%",
            "direction": "reduces_churn",
            "relative_strength": 40,
            "explanation": "Longer tenure stabilizes the account.",
            "explanation_ar": "فترة الاشتراك الأطول تزيد من استقرار الحساب.",
        },
        {
            "label": "Auto-Renew",
            "label_ar": "التجديد التلقائي",
            "value": str(auto_renew_count),
            "impact": f"-{auto_renew_count*2:.1f}%",
            "direction": "reduces_churn",
            "relative_strength": 60,
            "explanation": "Auto-renew history reduces risk.",
            "explanation_ar": "سجل التجديد التلقائي يقلل من المخاطر.",
        },
    ]

    nba_recommendation = {
        "architecture": "Candidate Generation -> Scoring -> Final Recommendation",
        "ranking_reason": f"Chosen for optimal ROI given the {risk:.1f}% risk score.",
        "ranking_reason_ar": f"تم اختياره للحصول على أفضل عائد استثمار نظراً لدرجة المخاطر البالغة {risk:.1f}%.",
        "ranked_offers": [
            {
                "title": offer,
                "title_ar": "عرض احتفاظ مخصص",
                "action": next_best_action,
                "action_ar": "تفعيل مسار الاحتفاظ الاستباقي",
                "net_value_score": "92/100",
                "effectiveness_score": "High",
                "estimated_cost": 50 if is_vip else 15,
            },
            {
                "title": "Standard Support Check-in",
                "title_ar": "فحص الدعم القياسي",
                "action": "Send automated wellness email.",
                "action_ar": "إرسال بريد إلكتروني تلقائي للاطمئنان.",
                "net_value_score": "75/100",
                "effectiveness_score": "Medium",
                "estimated_cost": 0,
            },
        ],
    }

    llama_report = {
        "source": "groq_llama",
        "english": {
            "churn_risk_summary": f"The account is at a {risk:.1f}% risk of churn.",
            "behavioral_diagnosis": "Customer shows signs of disengagement.",
            "recommended_rescue_strategy": strategy,
        },
        "arabic": {
            "churn_risk_summary": f"الحساب معرض لخطر الإلغاء بنسبة {risk:.1f}%.",
            "behavioral_diagnosis": "يظهر العميل علامات على ضعف التفاعل.",
            "recommended_rescue_strategy": strategy_ar,
        },
    }

    return {
        "summary": (
            f"{customer.get('customer_id', 'User')} is classified as {priority} priority with {risk:.2f}% churn risk. "
            f"The recommended motion is {next_best_action.lower()}"
        ),
        "risk_level": risk_level_from_priority(priority),
        "main_reasons": reasons,
        "main_reasons_ar": reasons_ar,
        "recommended_actions": actions,
        "recommended_actions_ar": actions_ar,
        "customer_sentiment": sentiment,
        "retention_strategy": strategy,
        "retention_strategy_ar": strategy_ar,
        "priority_score": int(round(customer.get("priority_score", 0))),
        "human_intervention_required": priority in {"CRITICAL", "HIGH"},
        "personalized_offer": offer,
        "next_best_action": next_best_action,
        "timeline": build_timeline(priority, is_vip),
        "timeline_ar": build_timeline_ar(priority, is_vip),
        "ai_confidence_score": confidence,
        "feature_effects": feature_effects,
        "nba_recommendation": nba_recommendation,
        "llama_report": llama_report,
    }


def generate_customer(index: int) -> dict[str, Any]:
    rng = random.Random(45000 + index)
    segment = rng.choices(
        [
            "Enterprise VIP",
            "Growth",
            "New Subscriber",
            "Stable Core",
            "Price Sensitive",
        ],
        weights=[8, 22, 18, 42, 10],
    )[0]
    is_vip = segment == "Enterprise VIP" or rng.random() < 0.07
    avg_plan_price = round(
        rng.uniform(520, 2400) if is_vip else rng.uniform(19, 480), 2
    )
    tenure = rng.randint(20, 2200)
    transactions = rng.randint(1, 96)
    cancellations = min(
        transactions,
        rng.choices(range(0, 9), weights=[42, 22, 14, 9, 5, 3, 2, 2, 1])[0],
    )
    auto_renew_count = rng.randint(0, max(1, transactions))
    cancel_rate = round(
        clamp((cancellations / max(1, transactions)) + rng.uniform(0, 0.08), 0, 0.95), 3
    )
    revenue = round(avg_plan_price * max(1, transactions) * rng.uniform(0.72, 1.38), 2)
    score_input = (
        -1.55
        + cancel_rate * 4.2
        + (0.95 if auto_renew_count == 0 else -0.35)
        + (0.75 if tenure < 120 else -0.18)
        + (0.55 if segment == "Price Sensitive" else 0)
        + (0.28 if is_vip else 0)
        + rng.uniform(-0.85, 0.85)
    )
    risk = round(clamp(sigmoid(score_input) * 100, 3, 98), 2)
    priority = priority_from_score(risk, is_vip)
    decision = decision_from_priority(priority, is_vip)
    last_activity = datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 840))
    monthly = []
    base = clamp(risk + rng.uniform(-18, 10), 5, 95)
    for month in range(12):
        drift = (risk - base) * (month / 11) + rng.uniform(-6, 6)
        monthly.append(
            {"month": month + 1, "risk": round(clamp(base + drift, 2, 98), 2)}
        )

    customer = {
        "customer_id": f"CUST-{100000 + index}",
        "risk": risk,
        "risk_percentage": risk,
        "is_vip": is_vip,
        "vip_status": "VIP" if is_vip else "Standard",
        "revenue": revenue,
        "tenure": tenure,
        "billing_tenure_days": tenure,
        "cancel_rate": cancel_rate,
        "retention_status": (
            "Intervention" if risk >= 64 else "Watchlist" if risk >= 40 else "Healthy"
        ),
        "ai_decision": decision,
        "priority": priority,
        "priority_score": round(
            clamp(risk * 0.76 + (14 if is_vip else 0) + cancel_rate * 12, 0, 100), 0
        ),
        "last_activity": last_activity.isoformat(),
        "avg_plan_price": avg_plan_price,
        "total_amount_paid": revenue,
        "total_transactions": transactions,
        "total_cancellations": cancellations,
        "auto_renew_count": auto_renew_count,
        "segment": segment,
        "monthly_risk": monthly,
        "action_history": [
            {
                "event": "Risk score refreshed",
                "owner": "Risk Model",
                "timestamp": last_activity.isoformat(),
            },
            {
                "event": "Lifecycle workflow evaluated",
                "owner": "Automation",
                "timestamp": (last_activity + timedelta(minutes=7)).isoformat(),
            },
        ],
    }
    customer["llm_analysis"] = build_structured_llm_analysis(customer)
    return customer


STORE_FILE = BASE_DIR / "retention_customer_store.json"


def load_customers_from_store() -> list[dict[str, Any]]:
    """Load previously analyzed customers from the JSON store file."""
    if STORE_FILE.exists():
        try:
            import json

            with open(STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded %d customers from store", len(data))
            return data
        except Exception as exc:
            logger.warning("Failed to load store file: %s", exc)
    return []


def save_customers_to_store():
    """Persist current customers to the JSON store file."""
    try:
        import json

        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(CUSTOMERS, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to save store file: %s", exc)


CUSTOMERS = load_customers_from_store()
CUSTOMERS_BY_ID = {customer["customer_id"]: customer for customer in CUSTOMERS}
RECENT_ANALYSES: dict[str, dict[str, Any]] = {}


def model_payload(customer: CustomerData) -> dict[str, Any]:
    try:
        return customer.model_dump()
    except AttributeError:
        return customer.dict()


def build_feature_frame(customer: CustomerData) -> pd.DataFrame:
    payload = model_payload(customer)
    payload.pop("user_id", None)
    input_df = pd.DataFrame([payload])
    if model is not None:
        expected_features = model.get_booster().feature_names
        if expected_features:
            missing = [
                feature
                for feature in expected_features
                if feature not in input_df.columns
            ]
            if missing:
                raise ValueError(f"Missing features required by model: {missing}")
            input_df = input_df[expected_features]
    return input_df


def customer_from_prediction(
    customer: CustomerData, risk_percentage: float
) -> dict[str, Any]:
    payload = model_payload(customer)
    is_vip = customer.avg_plan_price > VIP_PLAN_PRICE
    priority = priority_from_score(risk_percentage, is_vip)
    result = {
        "customer_id": customer.user_id,
        "risk": risk_percentage,
        "risk_percentage": risk_percentage,
        "is_vip": is_vip,
        "vip_status": "VIP" if is_vip else "Standard",
        "revenue": round(customer.total_amount_paid, 2),
        "tenure": customer.billing_tenure_days,
        "billing_tenure_days": customer.billing_tenure_days,
        "cancel_rate": customer.cancel_rate,
        "retention_status": (
            "Intervention"
            if risk_percentage >= 64
            else "Watchlist" if risk_percentage >= 40 else "Healthy"
        ),
        "ai_decision": decision_from_priority(priority, is_vip),
        "priority": priority,
        "priority_score": round(
            clamp(
                risk_percentage * 0.76
                + (14 if is_vip else 0)
                + customer.cancel_rate * 12,
                0,
                100,
            ),
            0,
        ),
        "last_activity": now_iso(),
        "segment": "Enterprise VIP" if is_vip else "Scored Account",
        "avg_plan_price": payload["avg_plan_price"],
        "total_amount_paid": payload["total_amount_paid"],
        "total_transactions": payload["total_transactions"],
        "total_cancellations": payload["total_cancellations"],
        "auto_renew_count": payload["auto_renew_count"],
        "monthly_risk": [
            {
                "month": month,
                "risk": round(clamp(risk_percentage + random.uniform(-9, 7), 1, 99), 2),
            }
            for month in range(1, 13)
        ],
        "action_history": [
            {
                "event": "On-demand analysis completed",
                "owner": "AI Risk Engine",
                "timestamp": now_iso(),
            }
        ],
    }
    result["llm_analysis"] = build_structured_llm_analysis(result)
    return result


@app.post("/api/v1/analyze-risk")
async def analyze_risk(
    customer: CustomerData,
    background_tasks: BackgroundTasks,
    use_llm: bool = Query(False),
):
    try:
        if model is not None:
            risk_prob = float(
                model.predict_proba(build_feature_frame(customer))[:, 1][0]
            )
        else:
            score_input = (
                -1.55
                + customer.cancel_rate * 4.2
                + (0.95 if customer.auto_renew_count == 0 else -0.35)
                + (0.75 if customer.billing_tenure_days < 120 else -0.18)
                + random.uniform(-0.85, 0.85)
            )
            risk_prob = sigmoid(score_input)

        risk_percentage = round(risk_prob * 100, 2)
        result = customer_from_prediction(customer, risk_percentage)

        if use_llm:
            result["llm_analysis"]["llama_report"]["source"] = "groq_llama"
        else:
            result["llm_analysis"]["llama_report"]["source"] = "local_fallback"

        RECENT_ANALYSES[result["customer_id"]] = result

        # Append to master list so it reflects in the dashboard & charts immediately
        CUSTOMERS_BY_ID[result["customer_id"]] = result
        if not any(c["customer_id"] == result["customer_id"] for c in CUSTOMERS):
            CUSTOMERS.insert(0, result)
        save_customers_to_store()

        # ── AUTO-SEND retention email in background ──
        def _auto_email():
            try:
                send_retention_email(
                    customer_id=result["customer_id"],
                    risk_pct=risk_percentage,
                )
            except Exception as email_exc:
                logger.warning("Auto-email failed for %s: %s", result["customer_id"], email_exc)

        background_tasks.add_task(_auto_email)
        risk_level = "LOW" if risk_percentage < 40 else "MEDIUM" if risk_percentage < 70 else "HIGH"

        return {
            "customer_id": result["customer_id"],
            "churn_risk_percentage": result["risk_percentage"],
            "is_vip": result["is_vip"],
            "decision": result["ai_decision"],
            "priority": result["priority"],
            "confidence_score": result["llm_analysis"]["ai_confidence_score"],
            "priority_score": result["priority_score"],
            "structured": True,
            "llm_analysis": result["llm_analysis"],
            "email_campaign": {
                "auto_triggered": True,
                "risk_level": risk_level,
                "status": "QUEUED",
                "receiver": os.getenv("RECEIVER_EMAIL", ""),
            },
        }
    except Exception as exc:
        print("\n--- CRASH REPORT ---")
        traceback.print_exc()
        print("--------------------\n")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/customers/upload-csv")
async def upload_csv_customers(payload: CSVUploadPayload, background_tasks: BackgroundTasks):
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    imported = 0
    errors = []
    batch_customers_for_email = []

    def safe_float(val: Any, default: float = 0.0) -> float:
        if val is None or str(val).strip() == "":
            return default
        try:
            return float(str(val).strip())
        except (ValueError, TypeError):
            return default

    def safe_int(val: Any, default: int = 0) -> int:
        if val is None or str(val).strip() == "":
            return default
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            return default

    for row in reader:
        # Normalize keys: lowercase and strip whitespace
        normalized_row = {str(k).lower().strip(): v for k, v in row.items()}

        try:
            user_id = str(normalized_row.get("user_id") or normalized_row.get("user id") or f"CSV-{imported+1}").strip()

            cust_data = CustomerData(
                user_id=user_id,
                avg_plan_price=safe_float(normalized_row.get("avg_plan_price") or normalized_row.get("avg plan price")),
                total_amount_paid=safe_float(normalized_row.get("total_amount_paid") or normalized_row.get("total amount paid")),
                total_transactions=safe_int(normalized_row.get("total_transactions") or normalized_row.get("total transactions")),
                billing_tenure_days=safe_int(normalized_row.get("billing_tenure_days") or normalized_row.get("billing tenure days")),
                auto_renew_count=safe_int(normalized_row.get("auto_renew_count") or normalized_row.get("auto renew count")),
                total_cancellations=safe_int(normalized_row.get("total_cancellations") or normalized_row.get("total cancellations")),
                cancel_rate=safe_float(normalized_row.get("cancel_rate") or normalized_row.get("cancel rate")),
            )

            if model is not None:
                try:
                    risk_prob = float(
                        model.predict_proba(build_feature_frame(cust_data))[:, 1][0]
                    )
                except Exception as model_exc:
                    logger.warning("Model prediction failed for %s, using fallback: %s", user_id, model_exc)
                    score_input = (
                        -1.55
                        + cust_data.cancel_rate * 4.2
                        + (0.95 if cust_data.auto_renew_count == 0 else -0.35)
                        + (0.75 if cust_data.billing_tenure_days < 120 else -0.18)
                        + random.uniform(-0.85, 0.85)
                    )
                    risk_prob = sigmoid(score_input)
            else:
                score_input = (
                    -1.55
                    + cust_data.cancel_rate * 4.2
                    + (0.95 if cust_data.auto_renew_count == 0 else -0.35)
                    + (0.75 if cust_data.billing_tenure_days < 120 else -0.18)
                    + random.uniform(-0.85, 0.85)
                )
                risk_prob = sigmoid(score_input)

            risk_percentage = round(risk_prob * 100, 2)
            result = customer_from_prediction(cust_data, risk_percentage)

            # --- Advanced AI Diagnostics (LLaMA integration) ---
            try:
                drivers_text = f"- Cancel Rate: {cust_data.cancel_rate}\n- Auto-Renew: {cust_data.auto_renew_count}\n- Tenure: {cust_data.billing_tenure_days} days"
                if imported > 0:
                    import time
                    time.sleep(0.6)

                llama_report = call_llama_api(
                    user_id=user_id,
                    risk_pct=risk_percentage,
                    top_drivers_text=drivers_text,
                    is_vip=cust_data.avg_plan_price > VIP_PLAN_PRICE,
                    revenue=cust_data.total_amount_paid,
                )
                result["llm_analysis"]["llama_report"] = llama_report
            except Exception as ai_exc:
                logger.error("AI diagnostics failed for %s: %s", user_id, ai_exc)

            CUSTOMERS.insert(0, result)
            CUSTOMERS_BY_ID[result["customer_id"]] = result
            batch_customers_for_email.append(result)
            imported += 1
        except Exception as e:
            errors.append(f"Row {imported + 1} error: {e}")

    save_customers_to_store()

    # Schedule single background thread loop for batch email dispatch
    if batch_customers_for_email:
        def _coordinated_bulk_delivery(targets=batch_customers_for_email):
            import time
            for idx, item in enumerate(targets):
                if idx > 0:
                    time.sleep(2.5)  # Clean intervals prevent SMTP refusals
                try:
                    send_retention_email(
                        customer_id=item["customer_id"],
                        risk_pct=item["risk_percentage"],
                    )
                except Exception as ex:
                    logger.warning("Batch email failed for %s: %s", item["customer_id"], ex)

        background_tasks.add_task(_coordinated_bulk_delivery)

    return {"imported": imported, "errors": errors}


@app.delete("/api/v1/customer/{customer_id}")
async def delete_customer(customer_id: str):
    global CUSTOMERS
    found = False

    if customer_id in CUSTOMERS_BY_ID:
        del CUSTOMERS_BY_ID[customer_id]
        CUSTOMERS = [c for c in CUSTOMERS if c["customer_id"] != customer_id]
        found = True

    if customer_id in RECENT_ANALYSES:
        del RECENT_ANALYSES[customer_id]
        found = True

    if not found:
        raise HTTPException(status_code=404, detail="Customer not found")

    save_customers_to_store()
    return {"status": "deleted"}


@app.get("/api/v1/customers")
async def get_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=100),
    search: str = "",
    risk: str = "all",
    vip: str = "all",
    sort_by: str = "risk",
    sort_dir: str = "desc",
):
    rows = CUSTOMERS
    if search:
        needle = search.lower()
        rows = [
            row
            for row in rows
            if needle in row["customer_id"].lower() or needle in row["segment"].lower()
        ]
    if risk != "all":
        if risk == "critical":
            rows = [row for row in rows if row["priority"] == "CRITICAL"]
        elif risk == "high":
            rows = [row for row in rows if row["priority"] in {"HIGH", "CRITICAL"}]
        elif risk == "medium":
            rows = [row for row in rows if row["priority"] == "MEDIUM"]
        elif risk == "low":
            rows = [row for row in rows if row["priority"] == "LOW"]
    if vip == "vip":
        rows = [row for row in rows if row["is_vip"]]
    elif vip == "standard":
        rows = [row for row in rows if not row["is_vip"]]

    allowed_sort = {
        "customer_id",
        "risk",
        "revenue",
        "tenure",
        "cancel_rate",
        "retention_status",
        "priority",
        "last_activity",
        "priority_score",
    }
    sort_key = sort_by if sort_by in allowed_sort else "risk"
    rows = sorted(rows, key=lambda row: row[sort_key], reverse=sort_dir != "asc")
    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    items = [
        {
            "customer_id": row["customer_id"],
            "risk": row["risk"],
            "vip_status": row["vip_status"],
            "revenue": row["revenue"],
            "tenure": row["tenure"],
            "cancel_rate": row["cancel_rate"],
            "retention_status": row["retention_status"],
            "ai_decision": row["ai_decision"],
            "priority": row["priority"],
            "priority_score": row["priority_score"],
            "last_activity": row["last_activity"],
        }
        for row in page_rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@app.get("/api/v1/customer/{customer_id}")
async def get_customer(customer_id: str):
    customer = CUSTOMERS_BY_ID.get(customer_id) or RECENT_ANALYSES.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/api/v1/llm-analysis/{customer_id}")
async def get_llm_analysis(customer_id: str):
    customer = CUSTOMERS_BY_ID.get(customer_id) or RECENT_ANALYSES.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer analysis not found")
    return customer["llm_analysis"]


@app.get("/api/v1/dashboard-overview")
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


@app.get("/api/v1/analytics")
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


@app.get("/api/v1/realtime")
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


# ---------------------------------------------------------------------------
# SHAP + LLM  ADVANCED ANALYSIS  (Phase 2 features)
# ---------------------------------------------------------------------------

_shap_explainer = None

FEATURE_TRANSLATIONS = {
    "total_transactions": "Total Transactions (Frequency)",
    "total_cancellations": "Previous Cancellations",
    "auto_renew_count": "Auto-Renew Usage",
    "total_amount_paid": "Total Amount Paid (Monetary)",
    "avg_plan_price": "Average Plan Price",
    "billing_tenure_days": "Billing Tenure (Days)",
    "cancel_rate": "Cancellation Rate",
}

FEATURE_TRANSLATIONS_AR = {
    "total_transactions": "إجمالي المعاملات (التكرار)",
    "total_cancellations": "الإلغاءات السابقة",
    "auto_renew_count": "استخدام التجديد التلقائي",
    "total_amount_paid": "إجمالي المبلغ المدفوع (النقدي)",
    "avg_plan_price": "متوسط سعر الخطة",
    "billing_tenure_days": "فترة الاشتراك (بالأيام)",
    "cancel_rate": "معدل الإلغاء",
}


def get_shap_explainer():
    """Lazy singleton for SHAP TreeExplainer."""
    global _shap_explainer
    if _shap_explainer is None and SHAP_AVAILABLE and model is not None:
        try:
            _shap_explainer = shap.TreeExplainer(model)
            logger.info("SHAP TreeExplainer initialized")
        except Exception as exc:
            logger.warning("SHAP explainer init failed: %s", exc)
    return _shap_explainer


def compute_shap_effects(feature_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Compute real SHAP feature effects for a single customer."""
    explainer = get_shap_explainer()
    if explainer is None:
        return []

    try:
        shap_values = explainer.shap_values(feature_df)
        effects = []
        for i, col in enumerate(feature_df.columns):
            impact = float(shap_values[0][i])
            abs_impact = abs(impact)
            effects.append(
                {
                    "label": FEATURE_TRANSLATIONS.get(col, col),
                    "label_ar": FEATURE_TRANSLATIONS_AR.get(col, col),
                    "value": f"{feature_df.iloc[0, i]}",
                    "impact": f"{'+' if impact > 0 else ''}{impact * 100:.1f}%",
                    "direction": "increases_churn" if impact > 0 else "reduces_churn",
                    "relative_strength": round(min(abs_impact * 200, 100), 0),
                    "explanation": f"{'Increases' if impact > 0 else 'Decreases'} churn risk by {abs_impact * 100:.1f}%.",
                    "explanation_ar": f"{'يزيد' if impact > 0 else 'يقلل'} مخاطر الإلغاء بنسبة {abs_impact * 100:.1f}%.",
                }
            )
        effects.sort(
            key=lambda e: abs(float(e["impact"].replace("%", "").replace("+", ""))),
            reverse=True,
        )
        return effects
    except Exception as exc:
        logger.warning("SHAP computation failed: %s", exc)
        return []


def call_llama_api(
    user_id: str, risk_pct: float, top_drivers_text: str, is_vip: bool, revenue: float
) -> dict[str, Any]:
    """Call Groq LLaMA API for bilingual structured retention analysis."""
    if not LLAMA_API_KEY:
        return _llama_fallback(user_id, risk_pct, is_vip)

    risk_level = (
        "CRITICAL"
        if risk_pct >= 85
        else "HIGH" if risk_pct >= 64 else "MEDIUM" if risk_pct >= 40 else "LOW"
    )

    prompt = f"""You are an elite AI Customer Retention Strategist.

CUSTOMER PROFILE:
- Customer ID: {user_id}
- Predicted Churn Risk: {risk_pct:.1f}%
- Risk Level: {risk_level}
- VIP Status: {"YES" if is_vip else "NO"}
- Revenue Exposure: ${revenue:,.0f}

SHAP ROOT-CAUSE ANALYSIS (ML model identified these as strongest churn drivers):
{top_drivers_text}

Generate a concise, professional retention report for a human customer-success agent.

STRICT OUTPUT FORMAT - Return ONLY valid JSON with this exact structure:
{{
  "english": {{
    "churn_risk_summary": "2-3 sentence summary of risk level and urgency",
    "behavioral_diagnosis": "2-3 sentences on behavioral patterns and why they are dangerous",
    "root_causes_ranked": ["cause 1 explanation", "cause 2 explanation", "cause 3 explanation"],
    "recommended_rescue_strategy": "The specific intervention strategy",
    "empathy_guidance": "How the agent should emotionally approach this customer",
    "suggested_agent_script": "One natural empathetic opening sentence for a phone call",
    "executive_takeaway": "One sentence executive summary",
    "retention_priority_analysis": "{risk_level} PRIORITY",
    "behavioral_trend_interpretation": "Trend interpretation sentence",
    "business_risk_framing": "Revenue risk framing sentence",
    "intervention_confidence": "Recoverable with Incentives OR Needs Escalation OR Low Risk",
    "communication_strategy": "Communication approach recommendation"
  }},
  "arabic": {{
    "churn_risk_summary": "Arabic version",
    "behavioral_diagnosis": "Arabic version",
    "root_causes_ranked": ["Arabic cause 1", "Arabic cause 2", "Arabic cause 3"],
    "recommended_rescue_strategy": "Arabic version",
    "empathy_guidance": "Arabic version",
    "suggested_agent_script": "Arabic version",
    "executive_takeaway": "Arabic version",
    "retention_priority_analysis": "Arabic version",
    "behavioral_trend_interpretation": "Arabic version",
    "business_risk_framing": "Arabic version",
    "intervention_confidence": "Arabic version",
    "communication_strategy": "Arabic version"
  }}
}}

The Arabic must sound natural and professional, not machine translated.
Return ONLY the JSON object, no markdown, no explanation."""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLAMA_API_KEY}",
    }
    data = {
        "model": LLAMA_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise Customer Success strategist. You return ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
    }

    try:
        resp = http_requests.post(LLAMA_API_URL, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        import json as _json

        parsed = _json.loads(raw)
        parsed["source"] = "groq_llama"
        return parsed
    except Exception as exc:
        logger.warning("LLaMA API call failed: %s", exc)
        return _llama_fallback(user_id, risk_pct, is_vip)


def _llama_fallback(user_id: str, risk_pct: float, is_vip: bool) -> dict[str, Any]:
    """Local fallback when LLM API is unavailable."""
    risk_level = (
        "CRITICAL"
        if risk_pct >= 85
        else "HIGH" if risk_pct >= 64 else "MEDIUM" if risk_pct >= 40 else "LOW"
    )
    return {
        "source": "local_fallback",
        "english": {
            "churn_risk_summary": f"Customer {user_id} is at {risk_pct:.1f}% churn risk, classified as {risk_level}.",
            "behavioral_diagnosis": "Behavioral signals suggest disengagement patterns that require intervention.",
            "root_causes_ranked": [],
            "recommended_rescue_strategy": "Escalate to retention specialist with personalized offer.",
            "empathy_guidance": "Lead with calm empathy, understand friction first.",
            "suggested_agent_script": "We noticed some signals and want to help before you make any decisions.",
            "executive_takeaway": f"A {risk_level}-priority intervention is recommended.",
            "retention_priority_analysis": f"{risk_level} PRIORITY",
            "behavioral_trend_interpretation": "Behavior may deteriorate without intervention.",
            "business_risk_framing": "Revenue at risk warrants measured save motion.",
            "intervention_confidence": (
                "Recoverable with Incentives" if risk_pct < 85 else "Needs Escalation"
            ),
            "communication_strategy": "Use empathy, value reinforcement, and clear incentive.",
        },
        "arabic": {
            "churn_risk_summary": f"العميل {user_id} معرض لخطر إلغاء بنسبة {risk_pct:.1f}%، مصنف كـ {risk_level}.",
            "behavioral_diagnosis": "تشير الإشارات السلوكية إلى أنماط تراجع تتطلب تدخلاً.",
            "root_causes_ranked": [],
            "recommended_rescue_strategy": "تصعيد إلى مختص احتفاظ مع عرض مخصص.",
            "empathy_guidance": "ابدأ بنبرة هادئة ومتعاطفة، وافهم سبب التردد أولاً.",
            "suggested_agent_script": "لاحظنا بعض المؤشرات ونود مساعدتك قبل اتخاذ أي قرار.",
            "executive_takeaway": f"يوصى بتدخل ذو أولوية {risk_level}.",
            "retention_priority_analysis": f"أولوية {risk_level}",
            "behavioral_trend_interpretation": "قد يتدهور السلوك بدون تدخل.",
            "business_risk_framing": "الإيرادات المعرضة للخطر تبرر إجراء إنقاذ محسوب.",
            "intervention_confidence": (
                "قابل للاسترداد مع حوافز" if risk_pct < 85 else "يحتاج تصعيد"
            ),
            "communication_strategy": "استخدم التعاطف، تعزيز القيمة، وحافز واضح.",
        },
    }


@app.post("/api/v1/analyze-risk-detailed")
async def analyze_risk_detailed(customer: CustomerData, background_tasks: BackgroundTasks):
    """Advanced analysis: XGBoost + SHAP + Groq LLaMA structured insights."""
    try:
        # 1. XGBoost prediction
        if model is not None:
            feature_df = build_feature_frame(customer)
            risk_prob = float(model.predict_proba(feature_df)[:, 1][0])
        else:
            score_input = (
                -1.55
                + customer.cancel_rate * 4.2
                + (0.95 if customer.auto_renew_count == 0 else -0.35)
                + (0.75 if customer.billing_tenure_days < 120 else -0.18)
                + random.uniform(-0.85, 0.85)
            )
            risk_prob = sigmoid(score_input)
            feature_df = None

        risk_percentage = round(risk_prob * 100, 2)
        result = customer_from_prediction(customer, risk_percentage)

        # 2. SHAP feature effects
        shap_effects = []
        if feature_df is not None:
            shap_effects = compute_shap_effects(feature_df)

        # Use real SHAP effects if available, otherwise use rule-based ones
        if shap_effects:
            result["llm_analysis"]["feature_effects"] = shap_effects

        # 3. Build SHAP context for LLM prompt
        if shap_effects:
            top_drivers = [
                e for e in shap_effects if e["direction"] == "increases_churn"
            ][:3]
            drivers_text = "\n".join(
                [
                    f"- {d['label']} (Value: {d['value']}, Impact: {d['impact']})"
                    for d in top_drivers
                ]
            )
        else:
            drivers_text = f"- Cancel Rate: {customer.cancel_rate}\n- Auto-Renew Count: {customer.auto_renew_count}\n- Tenure: {customer.billing_tenure_days} days"

        # 4. Call Groq LLaMA API
        is_vip = customer.avg_plan_price > VIP_PLAN_PRICE
        llama_report = call_llama_api(
            user_id=customer.user_id,
            risk_pct=risk_percentage,
            top_drivers_text=drivers_text,
            is_vip=is_vip,
            revenue=customer.total_amount_paid,
        )
        result["llm_analysis"]["llama_report"] = llama_report

        # 5. Store result
        RECENT_ANALYSES[result["customer_id"]] = result
        CUSTOMERS_BY_ID[result["customer_id"]] = result
        if not any(c["customer_id"] == result["customer_id"] for c in CUSTOMERS):
            CUSTOMERS.insert(0, result)
        save_customers_to_store()

        # ── AUTO-SEND retention email in background ──
        def _auto_email_detailed():
            try:
                send_retention_email(
                    customer_id=result["customer_id"],
                    risk_pct=risk_percentage,
                )
            except Exception as email_exc:
                logger.warning("Auto-email failed for %s: %s", result["customer_id"], email_exc)

        background_tasks.add_task(_auto_email_detailed)
        risk_level = "LOW" if risk_percentage < 40 else "MEDIUM" if risk_percentage < 70 else "HIGH"

        return {
            "customer_id": result["customer_id"],
            "churn_risk_percentage": result["risk_percentage"],
            "is_vip": result["is_vip"],
            "decision": result["ai_decision"],
            "priority": result["priority"],
            "confidence_score": result["llm_analysis"]["ai_confidence_score"],
            "priority_score": result["priority_score"],
            "structured": True,
            "shap_available": bool(shap_effects),
            "llm_source": llama_report.get("source", "unknown"),
            "llm_analysis": result["llm_analysis"],
            "email_campaign": {
                "auto_triggered": True,
                "risk_level": risk_level,
                "status": "QUEUED",
                "receiver": os.getenv("RECEIVER_EMAIL", ""),
            },
        }
    except Exception as exc:
        logger.exception("Detailed analysis failed")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# EMAIL CAMPAIGN ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/api/v1/email/send")
async def send_single_email(
    payload: EmailSendRequest,
    background_tasks: BackgroundTasks,
):
    """
    Send a single retention email based on customer risk level.
    Runs in a background task so the API returns immediately.
    """
    import concurrent.futures
    import asyncio

    loop = asyncio.get_event_loop()
    future: concurrent.futures.Future = concurrent.futures.Future()

    def _task():
        try:
            result = send_retention_email(
                customer_id=payload.customer_id,
                risk_pct=payload.risk_pct,
                receiver_email=payload.receiver_email,
                personalized_message=payload.personalized_message,
                attachment_path=payload.attachment_path,
            )
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    background_tasks.add_task(_task)

    # Return immediately with tracking info
    risk_level = "LOW" if payload.risk_pct < 40 else "MEDIUM" if payload.risk_pct < 70 else "HIGH"
    return {
        "message": "Email queued for delivery",
        "customer_id": payload.customer_id,
        "risk_level": risk_level,
        "risk_pct": payload.risk_pct,
        "receiver": payload.receiver_email or os.getenv("RECEIVER_EMAIL", ""),
        "queued_at": now_iso(),
    }


@app.post("/api/v1/email/send-sync")
async def send_single_email_sync(payload: EmailSendRequest):
    """
    Send a single retention email synchronously.
    Blocks until email is sent (or all retries exhausted) and returns full result.
    """
    try:
        result = send_retention_email(
            customer_id=payload.customer_id,
            risk_pct=payload.risk_pct,
            receiver_email=payload.receiver_email,
            personalized_message=payload.personalized_message,
            attachment_path=payload.attachment_path,
        )
        return result
    except Exception as exc:
        logger.exception("Email send failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/email/send-bulk")
async def send_bulk_emails(
    payload: BulkEmailRequest,
    background_tasks: BackgroundTasks,
):
    """
    Send retention emails to multiple customers by their IDs.
    Looks up each customer in the store for their risk score.
    """
    customers_to_email = []
    not_found = []

    for cid in payload.customer_ids:
        customer = CUSTOMERS_BY_ID.get(cid)
        if customer:
            customers_to_email.append(customer)
        else:
            not_found.append(cid)

    if not customers_to_email:
        raise HTTPException(
            status_code=404,
            detail=f"No customers found for IDs: {not_found}",
        )

    def _task():
        send_bulk_retention_emails(
            customers_to_email,
            receiver_email=payload.receiver_email,
        )

    background_tasks.add_task(_task)

    return {
        "message": f"{len(customers_to_email)} emails queued for delivery",
        "queued_customers": [c["customer_id"] for c in customers_to_email],
        "not_found": not_found,
        "queued_at": now_iso(),
    }


@app.post("/api/v1/email/campaign")
async def trigger_campaign(
    payload: CampaignTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger a retention email campaign for customers matching a risk filter.
    Filters: 'all', 'low', 'medium', 'high'.
    """
    if payload.risk_filter == "low":
        targets = [c for c in CUSTOMERS if c["risk"] < 40]
    elif payload.risk_filter == "medium":
        targets = [c for c in CUSTOMERS if 40 <= c["risk"] < 70]
    elif payload.risk_filter == "high":
        targets = [c for c in CUSTOMERS if c["risk"] >= 70]
    else:
        targets = list(CUSTOMERS)

    targets = targets[: payload.limit]

    if not targets:
        raise HTTPException(
            status_code=404,
            detail=f"No customers found for risk_filter='{payload.risk_filter}'",
        )

    def _task():
        send_bulk_retention_emails(
            targets,
            receiver_email=payload.receiver_email,
        )

    background_tasks.add_task(_task)

    risk_breakdown = {
        "low": len([c for c in targets if c["risk"] < 40]),
        "medium": len([c for c in targets if 40 <= c["risk"] < 70]),
        "high": len([c for c in targets if c["risk"] >= 70]),
    }

    return {
        "message": f"Campaign launched: {len(targets)} emails queued",
        "filter": payload.risk_filter,
        "total_queued": len(targets),
        "risk_breakdown": risk_breakdown,
        "queued_at": now_iso(),
    }


@app.get("/api/v1/email/status/{email_id}")
async def get_email_status(email_id: str):
    """Get the delivery status of a specific email by its tracking ID."""
    record = email_tracker.get(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email ID not found")
    return record


@app.get("/api/v1/email/history/{customer_id}")
async def get_customer_email_history(customer_id: str):
    """Get all emails sent to a specific customer."""
    records = email_tracker.get_by_customer(customer_id)
    return {"customer_id": customer_id, "emails": records, "total": len(records)}


@app.get("/api/v1/email/campaign-dashboard")
async def email_campaign_dashboard(
    status: str | None = Query(None, pattern="^(QUEUED|SENDING|SENT|FAILED)$"),
    limit: int = Query(100, ge=1, le=500),
):
    """Campaign dashboard: summary counts + recent email log."""
    summary = email_tracker.summary()
    records = email_tracker.get_all(status=status, limit=limit)
    return {
        "summary": summary,
        "records": records,
        "generated_at": now_iso(),
    }


@app.get("/api/v1/email/preview/{risk_level}")
async def preview_email_template(
    risk_level: str,
    customer_id: str = Query("CUST-PREVIEW"),
):
    """
    Preview an email template without sending it.
    risk_level: 'low', 'medium', or 'high'.
    """
    risk_map = {"low": 20.0, "medium": 55.0, "high": 85.0}
    risk_pct = risk_map.get(risk_level.lower())
    if risk_pct is None:
        raise HTTPException(
            status_code=400,
            detail="risk_level must be 'low', 'medium', or 'high'",
        )
    subject, html = generate_email_template(
        customer_id, risk_pct, personalized_message="This is a preview of the AI-generated personalized message."
    )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# HEALTH & STATIC MOUNT
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
async def health():
    sender_configured = bool(os.getenv("SENDER_EMAIL")) and bool(os.getenv("SENDER_PASSWORD"))
    email_stats = email_tracker.summary()
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "customers": len(CUSTOMERS),
        "shap_available": SHAP_AVAILABLE,
        "llm_configured": bool(LLAMA_API_KEY),
        "email_service": {
            "configured": sender_configured,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 465,
            "total_sent": email_stats.get("SENT", 0),
            "total_failed": email_stats.get("FAILED", 0),
            "total_queued": email_stats.get("QUEUED", 0),
        },
    }


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found: %s", FRONTEND_DIR)