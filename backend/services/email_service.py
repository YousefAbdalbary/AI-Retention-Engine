"""
Enterprise AI Retention Engine — Email Delivery Service.

Handles:
  • Gmail SMTP_SSL delivery via smtp.gmail.com:465
  • Risk-based email routing (LOW / MEDIUM / HIGH)
  • Automatic retry with exponential back-off
  • Optional PDF attachment
  • Status tracking via EmailTracker
  • Dynamic subject lines
  • Personalized messaging placeholder for AI-generated copy

Environment variables required:
  SENDER_EMAIL      — Gmail sender address
  SENDER_PASSWORD   — Google App Password (NOT your Gmail password)
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
import traceback
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from services.email_templates import generate_email_template
from services.email_tracker import tracker

logger = logging.getLogger("enterprise-retention-ai.email-service")

# ── SMTP configuration ────────────────────────────────────────────────────
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds; doubles each attempt



# Email type display names for terminal output
_EMAIL_TYPE_NAMES = {
    "LOW": "Appreciation & Loyalty Email",
    "MEDIUM": "Re-engagement & Incentive Email",
    "HIGH": "Urgent VIP Recovery Email",
}


def _get_credentials() -> tuple[str, str]:
    """Read sender credentials from environment variables."""
    sender = os.getenv("SENDER_EMAIL", "")
    password = os.getenv("SENDER_PASSWORD", "")
    if not sender or not password:
        raise EnvironmentError(
            "SENDER_EMAIL and SENDER_PASSWORD environment variables must be set. "
            "Use a Google App Password — never your regular Gmail password."
        )
    return sender, password


def _classify_risk(risk_pct: float) -> str:
    """Return risk tier label."""
    if risk_pct < 40:
        return "LOW"
    if risk_pct < 70:
        return "MEDIUM"
    return "HIGH"


def send_retention_email(
    customer_id: str,
    risk_pct: float,
    *,
    receiver_email: str | None = None,
    personalized_message: str = "",
    attachment_path: str | None = None,
) -> dict[str, Any]:
    """
    Build and send a risk-appropriate retention email.

    Parameters
    ----------
    customer_id : str
        Customer identifier shown in the email body.
    risk_pct : float
        Churn risk percentage (0–100).
    receiver_email : str, optional
        Override the default test receiver.
    personalized_message : str, optional
        AI-generated or custom copy injected into the template.
    attachment_path : str, optional
        Absolute path to a PDF file to attach.

    Returns
    -------
    dict
        ``{"email_id": ..., "status": "SENT" | "FAILED", "attempts": int, ...}``
    """

    risk_level = _classify_risk(risk_pct)
    # Dynamically read from env at runtime to ensure dotenv loaded variables are captured
    receiver = receiver_email or os.getenv("RECEIVER_EMAIL", "").strip()
    if not receiver:
        raise ValueError(
            "Receiver email address is empty. Please set RECEIVER_EMAIL in your .env file "
            "or pass receiver_email explicitly."
        )
    email_type_name = _EMAIL_TYPE_NAMES.get(risk_level, "Retention Email")

    print(f"\n{'='*60}")
    print(f"  EMAIL CAMPAIGN — {email_type_name}")
    print(f"  Customer : {customer_id}")
    print(f"  Risk Tier: {risk_level} ({risk_pct:.1f}%)")
    print(f"  Receiver : {receiver}")
    print(f"{'='*60}")

    # 1. Generate the template
    subject, html_body = generate_email_template(
        customer_id,
        risk_pct,
        personalized_message=personalized_message,
    )

    # 2. Register in tracker
    email_id = tracker.create(customer_id, risk_level, subject)

    # 3. Attempt delivery with retries
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tracker.mark_sending(email_id)
            _send_smtp(
                receiver=receiver,
                subject=subject,
                html_body=html_body,
                attachment_path=attachment_path,
            )
            tracker.mark_sent(email_id)
            logger.info(
                "Email SENT to %s for customer %s (attempt %d)",
                receiver, customer_id, attempt,
            )
            print(f"  >> SENT [{email_type_name}] to {receiver}")
            print(f"     Subject: {subject}")
            print(f"{'='*60}\n")
            return {
                "email_id": email_id,
                "customer_id": customer_id,
                "receiver": receiver,
                "risk_level": risk_level,
                "risk_pct": risk_pct,
                "subject": subject,
                "html_body": html_body,
                "status": "SENT",
                "attempts": attempt,
            }
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "⚠️  Attempt %d/%d failed for %s: %s",
                attempt, MAX_RETRIES, customer_id, last_error,
            )
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("   Retrying in %ds…", wait)
                time.sleep(wait)

    # All attempts exhausted
    tracker.mark_failed(email_id, last_error)
    logger.error(
        "Email FAILED for customer %s after %d attempts: %s",
        customer_id, MAX_RETRIES, last_error,
    )
    print(f"  >> FAILED [{email_type_name}] for {customer_id}: {last_error}")
    print(f"{'='*60}\n")
    return {
        "email_id": email_id,
        "customer_id": customer_id,
        "receiver": receiver,
        "risk_level": risk_level,
        "risk_pct": risk_pct,
        "subject": subject,
        "status": "FAILED",
        "attempts": MAX_RETRIES,
        "error": last_error,
    }


def _send_smtp(
    *,
    receiver: str,
    subject: str,
    html_body: str,
    attachment_path: str | None = None,
) -> None:
    """Low-level SMTP_SSL send via Gmail."""
    sender, password = _get_credentials()

    # Create proper MIME hierarchy to ensure reliable rendering across all mail clients
    if attachment_path:
        root_msg = MIMEMultipart("mixed")
        body_container = MIMEMultipart("alternative")
        root_msg.attach(body_container)
    else:
        root_msg = MIMEMultipart("alternative")
        body_container = root_msg

    root_msg["From"] = f"AI Retention Engine <{sender}>"
    root_msg["To"] = receiver
    root_msg["Subject"] = subject
    root_msg["X-Priority"] = "1"
    root_msg["X-Mailer"] = "Enterprise-AI-Retention-Engine/4.0"

    # Plaintext fallback ensures email gateways don't treat standalone HTML as an empty message
    plain_text = (
        f"Customer Retention Notice\n\n"
        f"Subject: {subject}\n\n"
        f"Please view this message in an HTML-compatible email client to access your premium membership details, rewards, and exclusive retention discounts."
    )
    body_container.attach(MIMEText(plain_text, "plain", "utf-8"))
    body_container.attach(MIMEText(html_body, "html", "utf-8"))

    # Optional PDF attachment
    if attachment_path:
        pdf_path = Path(attachment_path)
        if pdf_path.exists() and pdf_path.suffix.lower() == ".pdf":
            with open(pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=pdf_path.name,
                )
                root_msg.attach(part)
            logger.info("📎 Attached PDF: %s", pdf_path.name)
        else:
            logger.warning("Attachment path invalid or not a PDF: %s", attachment_path)

    # Send via SSL
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, receiver, root_msg.as_string())


def send_bulk_retention_emails(
    customers: list[dict[str, Any]],
    *,
    receiver_email: str | None = None,
) -> list[dict[str, Any]]:
    """
    Send retention emails to multiple customers (sequential).

    Parameters
    ----------
    customers : list[dict]
        Each dict must contain ``customer_id`` and ``risk`` (or ``risk_percentage``).
    receiver_email : str, optional
        Override receiver for all emails (useful for testing).

    Returns
    -------
    list[dict]
        Per-customer send results.
    """
    results = []
    for cust in customers:
        cid = cust.get("customer_id", "UNKNOWN")
        risk = float(cust.get("risk", cust.get("risk_percentage", 50)))
        result = send_retention_email(
            customer_id=cid,
            risk_pct=risk,
            receiver_email=receiver_email,
        )
        results.append(result)
    return results
