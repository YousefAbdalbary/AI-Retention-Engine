import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse

from models.schemas import EmailSendRequest, BulkEmailRequest, CampaignTriggerRequest
from services.email_service import send_retention_email, send_bulk_retention_emails
from services.email_tracker import tracker as email_tracker
from services.email_templates import generate_email_template
from services.store import CUSTOMERS, CUSTOMERS_BY_ID
from utils.helpers import now_iso
from core.config import logger

router = APIRouter()

@router.post("/send")
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
    risk_level = (
        "LOW"
        if payload.risk_pct < 40
        else "MEDIUM" if payload.risk_pct < 70 else "HIGH"
    )
    return {
        "message": "Email queued for delivery",
        "customer_id": payload.customer_id,
        "risk_level": risk_level,
        "risk_pct": payload.risk_pct,
        "receiver": payload.receiver_email or os.getenv("RECEIVER_EMAIL", ""),
        "queued_at": now_iso(),
    }


@router.post("/send-sync")
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


@router.post("/send-bulk")
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


@router.post("/campaign")
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


@router.get("/status/{email_id}")
async def get_email_status(email_id: str):
    """Get the delivery status of a specific email by its tracking ID."""
    record = email_tracker.get(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email ID not found")
    return record


@router.get("/history/{customer_id}")
async def get_customer_email_history(customer_id: str):
    """Get all emails sent to a specific customer."""
    records = email_tracker.get_by_customer(customer_id)
    return {"customer_id": customer_id, "emails": records, "total": len(records)}


@router.get("/campaign-dashboard")
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


@router.get("/preview/{risk_level}")
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
        customer_id,
        risk_pct,
        personalized_message="This is a preview of the AI-generated personalized message.",
    )
    return HTMLResponse(content=html)
