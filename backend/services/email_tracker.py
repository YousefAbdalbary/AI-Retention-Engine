"""
Enterprise AI Retention Engine — Email Status Tracker.

Thread-safe, in-memory tracker that persists to a JSON file so status
survives restarts.  Each record stores:
  - email_id        (UUID)
  - customer_id
  - risk_level      LOW / MEDIUM / HIGH
  - status          QUEUED / SENDING / SENT / FAILED
  - attempts        int
  - created_at      ISO-8601
  - updated_at      ISO-8601
  - error           Optional error message
  - subject         Email subject line
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.db import get_db_connection

logger = logging.getLogger("enterprise-retention-ai.email-tracker")

_STORE_FILE = Path(__file__).resolve().parent.parent / "email_campaign_log.json"
_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmailTracker:
    """Singleton-style email status store with file persistence."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    # ── persistence ────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM emails")
                rows = cursor.fetchall()
                if rows:
                    self._records = {json.loads(r["data"])["email_id"]: json.loads(r["data"]) for r in rows}
                    logger.info("Loaded %d email records from SQLite", len(self._records))
                    return

            if _STORE_FILE.exists():
                logger.info("SQLite email store empty, migrating from JSON...")
                data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._records = {r["email_id"]: r for r in data}
                elif isinstance(data, dict):
                    self._records = data
                
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    for email_id, record in self._records.items():
                        cursor.execute(
                            "INSERT OR REPLACE INTO emails (email_id, data) VALUES (?, ?)",
                            (email_id, json.dumps(record, ensure_ascii=False))
                        )
                    conn.commit()

                backup_path = _STORE_FILE.with_suffix(".json.bak")
                shutil.move(str(_STORE_FILE), str(backup_path))
                logger.info("Email migration complete.")
        except Exception as exc:
            logger.warning("Failed to load email store: %s", exc)

    def _save(self, email_id: str = None) -> None:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                if email_id and email_id in self._records:
                    cursor.execute(
                        "INSERT OR REPLACE INTO emails (email_id, data) VALUES (?, ?)",
                        (email_id, json.dumps(self._records[email_id], ensure_ascii=False))
                    )
                else:
                    for eid, record in self._records.items():
                        cursor.execute(
                            "INSERT OR REPLACE INTO emails (email_id, data) VALUES (?, ?)",
                            (eid, json.dumps(record, ensure_ascii=False))
                        )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to persist email store: %s", exc)

    # ── public API ─────────────────────────────────────────────────────

    def create(
        self,
        customer_id: str,
        risk_level: str,
        subject: str,
    ) -> str:
        """Create a new tracking record and return its ``email_id``."""
        email_id = str(uuid.uuid4())
        record = {
            "email_id": email_id,
            "customer_id": customer_id,
            "risk_level": risk_level,
            "status": "QUEUED",
            "attempts": 0,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "error": None,
            "subject": subject,
        }
        with _lock:
            self._records[email_id] = record
            self._save(email_id)
        logger.info("Email %s created for customer %s", email_id, customer_id)
        return email_id

    def mark_sending(self, email_id: str) -> None:
        with _lock:
            if email_id in self._records:
                rec = self._records[email_id]
                rec["status"] = "SENDING"
                rec["attempts"] += 1
                rec["updated_at"] = _now_iso()
                self._save(email_id)

    def mark_sent(self, email_id: str) -> None:
        with _lock:
            if email_id in self._records:
                rec = self._records[email_id]
                rec["status"] = "SENT"
                rec["updated_at"] = _now_iso()
                rec["error"] = None
                self._save(email_id)
        logger.info("Email %s marked SENT", email_id)

    def mark_failed(self, email_id: str, error: str) -> None:
        with _lock:
            if email_id in self._records:
                rec = self._records[email_id]
                rec["status"] = "FAILED"
                rec["updated_at"] = _now_iso()
                rec["error"] = error
                self._save(email_id)
        logger.warning("Email %s marked FAILED: %s", email_id, error)

    def get(self, email_id: str) -> dict[str, Any] | None:
        with _lock:
            return self._records.get(email_id)

    def get_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        with _lock:
            return [
                r for r in self._records.values()
                if r["customer_id"] == customer_id
            ]

    def get_all(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with _lock:
            records = list(self._records.values())
        if status:
            records = [r for r in records if r["status"] == status]
        records.sort(key=lambda r: r["updated_at"], reverse=True)
        return records[:limit]

    def summary(self) -> dict[str, int]:
        with _lock:
            records = list(self._records.values())
        counts: dict[str, int] = {"QUEUED": 0, "SENDING": 0, "SENT": 0, "FAILED": 0}
        for r in records:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        counts["total"] = len(records)
        return counts


# Module-level singleton
tracker = EmailTracker()
