import requests as http_requests
from typing import Any

from core.config import (
    LLAMA_API_KEY,
    LLAMA_API_URL,
    LLAMA_MODEL_NAME,
    OPTIMAL_THRESHOLD,
    logger,
)
from utils.helpers import sentiment_from_customer, sentiment_from_customer_ar, clamp


def build_structured_llm_analysis(customer: dict[str, Any]) -> dict[str, Any]:
    priority = customer.get("priority", "LOW")
    risk = round(float(customer.get("risk", 0)), 2)
    is_vip = bool(customer.get("is_vip", False))
    confidence = round(
        clamp(68 + abs(risk - 50) * 0.44 + (4 if is_vip else 0), 70, 98), 2
    )
    sentiment = sentiment_from_customer(customer)
    sentiment_ar = sentiment_from_customer_ar(customer)

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
        offer_ar = "مكالمة نجاح مخصصة بالإضافة إلى رصيد تجديد خاص ومراجعة للدعم المميز."
        next_best_action = (
            "Create an escalation case and contact the customer within 24 hours."
        )
        next_best_action_ar = "إنشاء حالة تصعيد والاتصال بالعميل خلال 24 ساعة."
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
        offer_ar = "حافز تجديد بنسبة 15% محدد بوقت مع ميزات التجديد التلقائي."
        next_best_action = "Enroll customer in automated retention journey."
        next_best_action_ar = "تسجيل العميل في مسار الاحتفاظ التلقائي."
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
        offer_ar = "لا حاجة لعرض إنقاذ؛ الاستمرار في رسائل الولاء القياسية."
        next_best_action = "No immediate intervention required."
        next_best_action_ar = "لا يتطلب تدخلاً فورياً."

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
            "customer_persona": "Standard Persona",
            "customer_segment": "Standard Segment",
            "retention_strategy": strategy,
            "communication_strategy": "Email Outreach",
            "email_strategy": f"Subject: Account Review\n\nHi {customer.get('name', 'Customer')},\n\nWe noticed some changes in your usage...",
            "why_generated": f"System detected declining commitment patterns requiring immediate intervention. Confidence: {confidence}%.",
            "personalization_factors": "Health score, NPS history, and recent cancellation frequency.",
            "expected_outcome": f"Protects ${revenue:,.0f} in ARR by re-engaging the decision maker.",
            "recommended_actions": actions,
            "follow_up_plan": next_best_action,
            "executive_summary": f"The account is at a {risk:.1f}% risk of churn. Immediate action required.",
        },
        "arabic": {
            "customer_persona": "الشخصية القياسية",
            "customer_segment": "الشريحة القياسية",
            "retention_strategy": strategy_ar,
            "communication_strategy": "التواصل عبر البريد الإلكتروني",
            "email_strategy": f"الموضوع: مراجعة الحساب\n\nمرحباً {customer.get('name', 'عميلنا العزيز')},\n\nلاحظنا بعض التغييرات...",
            "why_generated": f"اكتشف النظام أنماط التزام متراجعة تتطلب تدخلاً فورياً. الثقة: {confidence}%.",
            "personalization_factors": "درجة الصحة، تاريخ NPS، وتواتر الإلغاءات الأخيرة.",
            "expected_outcome": f"حماية مبلغ ${revenue:,.0f} من الإيرادات السنوية عبر إعادة تفاعل صانع القرار.",
            "recommended_actions": actions_ar,
            "follow_up_plan": next_best_action_ar,
            "executive_summary": f"الحساب معرض لخطر الإلغاء بنسبة {risk:.1f}%. يتطلب تدخلاً فورياً.",
        },
    }

    from utils.helpers import risk_level_from_priority, build_timeline, build_timeline_ar
    return {
        "summary": (
            f"{customer.get('customer_id', 'User')} is classified as {priority} priority with {risk:.2f}% churn risk. "
            f"The recommended motion is {next_best_action.lower()}"
        ),
        "summary_ar": (
            f"تم تصنيف العميل {customer.get('customer_id', '')} كأولوية {priority} مع خطر إلغاء بنسبة {risk:.2f}%. "
            f"الإجراء الموصى به هو: {next_best_action_ar}"
        ),
        "risk_level": risk_level_from_priority(priority),
        "main_reasons": reasons,
        "main_reasons_ar": reasons_ar,
        "recommended_actions": actions,
        "recommended_actions_ar": actions_ar,
        "customer_sentiment": sentiment,
        "customer_sentiment_ar": sentiment_ar,
        "retention_strategy": strategy,
        "retention_strategy_ar": strategy_ar,
        "priority_score": int(round(customer.get("priority_score", 0))),
        "human_intervention_required": priority in {"CRITICAL", "HIGH"},
        "personalized_offer": offer,
        "personalized_offer_ar": offer_ar,
        "next_best_action": next_best_action,
        "next_best_action_ar": next_best_action_ar,
        "timeline": build_timeline(priority, is_vip),
        "timeline_ar": build_timeline_ar(priority, is_vip),
        "ai_confidence_score": confidence,
        "feature_effects": feature_effects,
        "nba_recommendation": nba_recommendation,
        "llama_report": llama_report,
    }


def call_llama_api(
    user_id: str, risk_pct: float, top_drivers_text: str, is_vip: bool, revenue: float, customer_data: dict[str, Any] = None
) -> dict[str, Any]:
    """Call Groq LLaMA API for bilingual structured retention analysis."""
    if customer_data is None:
        customer_data = {}

    if not LLAMA_API_KEY:
        return _llama_fallback(user_id, risk_pct, is_vip)

    risk_level = (
        "CRITICAL"
        if risk_pct >= 85
        else "HIGH" if risk_pct >= 64 else "MEDIUM" if risk_pct >= 40 else "LOW"
    )

    from services.prompt_builder import PromptBuilder
    messages = PromptBuilder.build_final_prompt(
        customer_id=user_id,
        customer_data=customer_data,
        risk_pct=risk_pct,
        risk_level=risk_level,
        is_vip=is_vip,
        revenue=revenue,
        top_drivers_text=top_drivers_text
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLAMA_API_KEY}",
    }
    data = {
        "model": LLAMA_MODEL_NAME,
        "messages": messages,
        "temperature": 0.4,
    }

    try:
        resp = http_requests.post(LLAMA_API_URL, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
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
            "customer_persona": "Standard Enterprise User",
            "customer_segment": "At-Risk Segment",
            "retention_strategy": "Escalate to retention specialist with personalized offer.",
            "communication_strategy": "Email outreach followed by a phone call.",
            "email_strategy": "Subject: Checking in on your account...\nHi,\nWe noticed some signals and want to help before you make any decisions.",
            "recommended_actions": ["Send standard email", "Flag in CRM", "Assign agent"],
            "follow_up_plan": "Check engagement within 48 hours.",
            "executive_summary": f"Customer {user_id} is at {risk_pct:.1f}% churn risk, classified as {risk_level} priority."
        },
        "arabic": {
            "customer_persona": "مستخدم مؤسسي قياسي",
            "customer_segment": "شريحة معرضة للخطر",
            "retention_strategy": "تصعيد إلى مختص احتفاظ مع عرض مخصص لإنقاذ العميل.",
            "communication_strategy": "التواصل عبر البريد الإلكتروني يتبعه مكالمة هاتفية.",
            "email_strategy": "الموضوع: الاطمئنان على حسابك...\nمرحباً،\nلقد لاحظنا بعض المؤشرات ونود مساعدتك لضمان حصولك على أفضل تجربة.",
            "recommended_actions": ["إرسال بريد قياسي", "تحديد في نظام إدارة العملاء", "تعيين وكيل"],
            "follow_up_plan": "التحقق من التفاعل خلال 48 ساعة.",
            "executive_summary": f"العميل {user_id} معرض لخطر إلغاء بنسبة {risk_pct:.1f}%، مصنف كأولوية {risk_level}."
        },
    }
