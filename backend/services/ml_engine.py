import random
import traceback
from typing import Any
from pathlib import Path

import pandas as pd
import xgboost as xgb

from core.config import BASE_DIR, PROJECT_DIR, MODEL_FILE, VIP_PLAN_PRICE, logger
from models.schemas import CustomerData
from utils.helpers import (
    now_iso,
    clamp,
    sigmoid,
    priority_from_score,
    decision_from_priority,
)
from services.llm_engine import build_structured_llm_analysis
from services.store import update_customer_in_store

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


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

        import numpy as np
        if not hasattr(loaded_model, "n_classes_"):
            setattr(loaded_model, "n_classes_", 2)
        if not hasattr(loaded_model, "classes_"):
            setattr(loaded_model, "classes_", np.array([0, 1]))

        logger.info("XGBoost model loaded from %s", model_path)
        return loaded_model
    except Exception as exc:
        logger.warning("Model load failed (will use fallback scoring): %s", exc)
        return None

# Global model instance
model = load_model()


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


def run_prediction(
    features: pd.DataFrame, data: CustomerData
) -> tuple[float, str, str, bool]:
    if model is not None:
        try:
            risk_prob = float(model.predict_proba(features)[:, 1][0])
        except Exception as exc:
            logger.warning("Model prediction failed in sync: %s", exc)
            score_input = (
                -1.55
                + data.cancel_rate * 4.2
                + (0.95 if data.auto_renew_count == 0 else -0.35)
                + (0.75 if data.billing_tenure_days < 120 else -0.18)
                + random.uniform(-0.85, 0.85)
            )
            risk_prob = sigmoid(score_input)
    else:
        score_input = (
            -1.55
            + data.cancel_rate * 4.2
            + (0.95 if data.auto_renew_count == 0 else -0.35)
            + (0.75 if data.billing_tenure_days < 120 else -0.18)
            + random.uniform(-0.85, 0.85)
        )
        risk_prob = sigmoid(score_input)

    risk_pct = round(risk_prob * 100, 2)
    is_vip = data.avg_plan_price > VIP_PLAN_PRICE
    priority = priority_from_score(risk_pct, is_vip)
    decision = decision_from_priority(priority, is_vip)
    return risk_pct, priority, decision, is_vip


def build_customer_record(
    data: CustomerData, risk_pct: float, priority: str, decision: str, is_vip: bool
) -> dict[str, Any]:
    return customer_from_prediction(data, risk_pct)


def _score_and_store_customer(raw: dict) -> dict:
    METADATA_KEYS = {
        "_connector_source",
        "_synced_at",
        "email",
        "company",
        "lifecycle_stage",
        "account_name",
        "mixpanel_id",
        "country",
        "total_sessions",
        "stripe_customer_id",
        "stripe_sub_id",
        "status",
        "currency",
        "_mock_note",
    }
    clean = {k: v for k, v in raw.items() if k not in METADATA_KEYS}

    tc = int(clean.get("total_cancellations", 0))
    tt = max(1, int(clean.get("total_transactions", 1)))
    clean["cancel_rate"] = round(tc / tt, 4)

    data = CustomerData(**clean)
    features = build_feature_frame(data)
    risk_pct, priority, decision, is_vip = run_prediction(features, data)
    customer = build_customer_record(data, risk_pct, priority, decision, is_vip)
    customer["_connector_source"] = raw.get("_connector_source", "unknown")
    customer["_synced_at"] = raw.get("_synced_at", now_iso())

    update_customer_in_store(customer)
    return customer


# SHAP Logic
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
