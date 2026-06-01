import csv
import io
import math
from typing import Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd

from models.schemas import CSVUploadPayload, CustomerData
from services.ml_engine import (
    model,
    build_feature_frame,
    customer_from_prediction,
    _score_and_store_customer,
)
from services.store import (
    CUSTOMERS,
    CUSTOMERS_BY_ID,
    RECENT_ANALYSES,
    save_customers_to_store,
)
from services.email_service import send_retention_email
from utils.helpers import sigmoid
import random
from core.config import logger

router = APIRouter()

@router.post("/customers/upload-csv")
async def upload_csv_customers(
    payload: CSVUploadPayload, background_tasks: BackgroundTasks
):
    if payload.mode == "raw":
        raw_rows = []
        skipped_rows = 0
        reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))

        fieldnames = [str(f).lower().strip() for f in reader.fieldnames or []]
        raw_req = ["customer_id", "transaction_date", "amount", "plan_name"]
        missing_raw = [req for req in raw_req if req not in fieldnames]
        if missing_raw:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_columns",
                    "missing": missing_raw,
                    "required": raw_req,
                    "hint": "Raw transaction mode requires customer_id, transaction_date, amount, plan_name.",
                },
            )

        for row_idx, row in enumerate(reader):
            clean_row = {str(k).lower().strip(): v for k, v in row.items()}
            cid = clean_row.get("customer_id", "").strip()
            tdate = clean_row.get("transaction_date", "").strip()
            amt_str = clean_row.get("amount", "").strip()

            if not cid or not tdate or not amt_str:
                logger.warning(
                    "Skipping raw row %d: missing required field", row_idx + 1
                )
                skipped_rows += 1
                continue

            try:
                amt = float(amt_str)
                if amt < 0:
                    logger.warning("Skipping raw row %d: negative amount", row_idx + 1)
                    skipped_rows += 1
                    continue
            except ValueError:
                logger.warning("Skipping raw row %d: non-numeric amount", row_idx + 1)
                skipped_rows += 1
                continue

            canc_val = (
                1 if str(clean_row.get("is_cancellation", "")).strip() == "1" else 0
            )
            renew_val = (
                1 if str(clean_row.get("is_auto_renew", "")).strip() == "1" else 0
            )

            raw_rows.append(
                {
                    "customer_id": cid,
                    "transaction_date": tdate,
                    "amount": amt,
                    "plan_name": clean_row.get("plan_name", "").strip(),
                    "is_cancellation": canc_val,
                    "is_auto_renew": renew_val,
                }
            )

        if not raw_rows:
            return {
                "mode": "raw",
                "rows_received": skipped_rows,
                "customers_engineered": 0,
                "customers_scored": 0,
                "skipped_rows": skipped_rows,
                "feature_engineering_summary": {
                    "avg_transactions_per_customer": 0,
                    "avg_tenure_days": 0,
                    "avg_cancel_rate": 0,
                },
                "results": [],
            }

        df = pd.DataFrame(raw_rows)
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        bad_dates = df["transaction_date"].isna().sum()
        if bad_dates > 0:
            skipped_rows += int(bad_dates)
            df = df.dropna(subset=["transaction_date"])

        results = []
        tot_tx = []
        tot_tenure = []
        tot_canc_rate = []

        for cid, group in df.groupby("customer_id"):
            if len(group) == 0:
                continue
            group = group.sort_values("transaction_date")
            first_date = group["transaction_date"].iloc[0]
            last_date = group["transaction_date"].iloc[-1]

            tx_count = len(group)
            canc_count = int(group["is_cancellation"].sum())
            renew_count = int(group["is_auto_renew"].sum())
            amt_sum = float(group["amount"].sum())
            amt_mean = float(group["amount"].mean())
            tenure_days = max(1, (last_date - first_date).days)
            if tx_count == 1:
                tenure_days = 1

            c_rate = round(canc_count / max(1, tx_count), 4)

            eng_features = {
                "user_id": str(cid),
                "avg_plan_price": round(amt_mean, 2),
                "total_amount_paid": round(amt_sum, 2),
                "total_transactions": tx_count,
                "billing_tenure_days": tenure_days,
                "auto_renew_count": renew_count,
                "total_cancellations": canc_count,
                "cancel_rate": c_rate,
            }

            tot_tx.append(tx_count)
            tot_tenure.append(tenure_days)
            tot_canc_rate.append(c_rate)

            try:
                cust_dict = _score_and_store_customer(eng_features)
                results.append(cust_dict)
            except Exception as ex:
                logger.warning(
                    "Failed to score raw engineered customer %s: %s", cid, ex
                )

        save_customers_to_store()

        summary_stats = {
            "avg_transactions_per_customer": (
                round(sum(tot_tx) / len(tot_tx), 1) if tot_tx else 0
            ),
            "avg_tenure_days": (
                int(sum(tot_tenure) / len(tot_tenure)) if tot_tenure else 0
            ),
            "avg_cancel_rate": (
                round(sum(tot_canc_rate) / len(tot_canc_rate), 2)
                if tot_canc_rate
                else 0
            ),
        }

        return {
            "mode": "raw",
            "rows_received": len(raw_rows) + skipped_rows,
            "customers_engineered": len(results),
            "customers_scored": len(results),
            "skipped_rows": skipped_rows,
            "feature_engineering_summary": summary_stats,
            "results": results,
        }

    # Default Mode: "ready"
    reader = csv.DictReader(io.StringIO(payload.csv_text.strip()))
    fieldnames = [str(f).lower().strip() for f in reader.fieldnames or []]

    mapped_fields = set()
    for f in fieldnames:
        if f in ("user_id", "user id"):
            mapped_fields.add("user_id")
        elif f in ("avg_plan_price", "avg plan price"):
            mapped_fields.add("avg_plan_price")
        elif f in ("total_amount_paid", "total amount paid"):
            mapped_fields.add("total_amount_paid")
        elif f in ("total_transactions", "total transactions"):
            mapped_fields.add("total_transactions")
        elif f in ("billing_tenure_days", "billing tenure days"):
            mapped_fields.add("billing_tenure_days")
        elif f in ("auto_renew_count", "auto renew count"):
            mapped_fields.add("auto_renew_count")
        elif f in ("total_cancellations", "total cancellations"):
            mapped_fields.add("total_cancellations")

    required = [
        "user_id",
        "avg_plan_price",
        "total_amount_paid",
        "total_transactions",
        "billing_tenure_days",
        "auto_renew_count",
        "total_cancellations",
    ]
    missing = [req for req in required if req not in mapped_fields]
    if missing:
        return JSONResponse(
            status_code=400,
            content={
                "error": "missing_columns",
                "missing": missing,
                "required": required,
                "hint": "Use mode='raw' if you have raw transaction data.",
            },
        )

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
        normalized_row = {str(k).lower().strip(): v for k, v in row.items()}
        try:
            user_id = str(
                normalized_row.get("user_id")
                or normalized_row.get("user id")
                or f"CSV-{imported+1}"
            ).strip()
            tx = safe_int(
                normalized_row.get("total_transactions")
                or normalized_row.get("total transactions")
            )
            canc = safe_int(
                normalized_row.get("total_cancellations")
                or normalized_row.get("total cancellations")
            )
            calc_cancel_rate = canc / tx if tx > 0 else 0.0

            cust_data = CustomerData(
                user_id=user_id,
                avg_plan_price=safe_float(
                    normalized_row.get("avg_plan_price")
                    or normalized_row.get("avg plan price")
                ),
                total_amount_paid=safe_float(
                    normalized_row.get("total_amount_paid")
                    or normalized_row.get("total amount paid")
                ),
                total_transactions=tx,
                billing_tenure_days=safe_int(
                    normalized_row.get("billing_tenure_days")
                    or normalized_row.get("billing tenure days")
                ),
                auto_renew_count=safe_int(
                    normalized_row.get("auto_renew_count")
                    or normalized_row.get("auto renew count")
                ),
                total_cancellations=canc,
                cancel_rate=calc_cancel_rate,
            )

            if model is not None:
                try:
                    risk_prob = float(
                        model.predict_proba(build_feature_frame(cust_data))[:, 1][0]
                    )
                except Exception as model_exc:
                    logger.warning(
                        "Model prediction failed for %s, using fallback: %s",
                        user_id,
                        model_exc,
                    )
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

            CUSTOMERS.insert(0, result)
            CUSTOMERS_BY_ID[result["customer_id"]] = result
            batch_customers_for_email.append(result)
            imported += 1
        except Exception as e:
            errors.append(f"Row {imported + 1} error: {e}")

    save_customers_to_store()

    if batch_customers_for_email:

        def _coordinated_bulk_delivery(targets=batch_customers_for_email):
            import time

            for idx, item in enumerate(targets):
                if idx > 0:
                    time.sleep(2.5)
                try:
                    send_retention_email(
                        customer_id=item["customer_id"],
                        risk_pct=item["risk_percentage"],
                    )
                except Exception as ex:
                    logger.warning(
                        "Batch email failed for %s: %s", item["customer_id"], ex
                    )

        background_tasks.add_task(_coordinated_bulk_delivery)

    return {
        "imported": imported,
        "errors": errors,
        "customers_scored": imported,
        "results": batch_customers_for_email,
    }


@router.delete("/customer/{customer_id}")
async def delete_customer(customer_id: str):
    from services.store import CUSTOMERS, CUSTOMERS_BY_ID, RECENT_ANALYSES, save_customers_to_store
    found = False

    if customer_id in CUSTOMERS_BY_ID:
        del CUSTOMERS_BY_ID[customer_id]
        # Remove from CUSTOMERS in place to modify the global list
        CUSTOMERS[:] = [c for c in CUSTOMERS if c["customer_id"] != customer_id]
        found = True

    if customer_id in RECENT_ANALYSES:
        del RECENT_ANALYSES[customer_id]
        found = True

    if not found:
        raise HTTPException(status_code=404, detail="Customer not found")

    save_customers_to_store()
    return {"status": "deleted"}


@router.get("/customers")
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


@router.get("/customer/{customer_id}")
async def get_customer(customer_id: str):
    customer = CUSTOMERS_BY_ID.get(customer_id) or RECENT_ANALYSES.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/llm-analysis/{customer_id}")
async def get_llm_analysis(customer_id: str):
    customer = CUSTOMERS_BY_ID.get(customer_id) or RECENT_ANALYSES.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer analysis not found")
    return customer["llm_analysis"]
