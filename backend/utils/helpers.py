import math
from datetime import datetime, timezone
from typing import Any

from core.config import OPTIMAL_THRESHOLD, VIP_PLAN_PRICE


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def sentiment_from_customer_ar(customer: dict[str, Any]) -> str:
    risk = customer.get("risk", 50)
    cancel_rate = customer.get("cancel_rate", 0)
    if risk >= 78 or cancel_rate >= 0.36:
        return "سلبي"
    if risk >= 48 or cancel_rate >= 0.18:
        return "مختلط"
    return "إيجابي"


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
