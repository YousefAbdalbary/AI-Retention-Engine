import os
from fastapi import APIRouter
from services.store import CUSTOMERS
from services.ml_engine import model, SHAP_AVAILABLE
from services.email_tracker import tracker as email_tracker
from core.config import LLAMA_API_KEY

router = APIRouter()

@router.get("/health")
async def health():
    sender_configured = bool(os.getenv("SENDER_EMAIL")) and bool(
        os.getenv("SENDER_PASSWORD")
    )
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
