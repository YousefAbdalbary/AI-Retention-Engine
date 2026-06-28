from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse
import pandas as pd
import csv
import io
import math
from typing import Any
import random
import hashlib
import datetime

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
from core.config import logger

router = APIRouter()

@router.post("/customers/upload-file")
async def upload_file_customers(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("ready")
):
    try:
        content = await file.read()
        filename = file.filename.lower()
        
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            # openpyxl requires a file-like object for reading bytes
            df = pd.read_excel(io.BytesIO(content), header=[0, 1] if "sample_100_clients" in filename else 0)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[1] if "Unnamed" in col[0] else col[0] + " - " + col[1] for col in df.columns]
        else:
            # Assume CSV
            df = pd.read_csv(io.StringIO(content.decode("utf-8")))
            
        # Normalize columns
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        raw_rows = df.to_dict(orient="records")
        imported = 0
        errors = []
        batch_customers_for_email = []
        
        for idx, row in enumerate(raw_rows):
            clean_row = {k: v for k, v in row.items() if pd.notna(v)}
            
            # Extract basic ID mapping
            user_id = str(
                clean_row.get("user_id") or clean_row.get("identity - user id") or clean_row.get("profile - user id") or clean_row.get("user id") or clean_row.get("customer_id") or clean_row.get("identity") or f"UPLOAD-{imported+1}"
            ).strip()

            # Aggressively search for a "name" column, prioritizing exact match or suffix match
            found_name = clean_row.get("name")
            if not found_name:
                for key in clean_row.keys():
                    if key.endswith("- name") or " name" in key or key.startswith("name"):
                        found_name = clean_row[key]
                        break
            if not found_name:
                found_name = user_id

            # Aggressively search for email
            found_email = clean_row.get("email") or clean_row.get("identity - email") or clean_row.get("profile - email")
            if not found_email:
                for key in clean_row.keys():
                    if key.endswith("- email") or " email" in key or key.startswith("email"):
                        found_email = clean_row[key]
                        break

            # Map remaining fields roughly matching our dataset analysis
            mapped = {
                "user_id": user_id,
                "name": found_name,
                "email": found_email,
                "industry": clean_row.get("industry") or clean_row.get("identity - industry") or clean_row.get("profile - industry"),
                "contract": clean_row.get("contract") or clean_row.get("identity - contract") or clean_row.get("profile - contract"),
                "segment": clean_row.get("segment") or clean_row.get("identity - segment") or clean_row.get("profile - segment"),
                "avg_plan_price": clean_row.get("avg_plan_price") or clean_row.get("billing & transactions - avg plan price") or clean_row.get("billing & usage - avg plan price") or clean_row.get("avg plan price"),
                "total_amount_paid": clean_row.get("total_paid") or clean_row.get("total_amount_paid") or clean_row.get("billing & transactions - total paid"),
                "total_transactions": clean_row.get("transactions") or clean_row.get("total_transactions") or clean_row.get("billing & transactions - transactions") or clean_row.get("billing & usage - transactions"),
                "billing_tenure_days": clean_row.get("tenure (days)") or clean_row.get("billing_tenure_days") or clean_row.get("billing & transactions - tenure (days)"),
                "auto_renew_count": clean_row.get("auto_renewals") or clean_row.get("auto_renew_count") or clean_row.get("engagement metrics - auto renewals"),
                "total_cancellations": clean_row.get("cancellations") or clean_row.get("total_cancellations") or clean_row.get("engagement metrics - cancellations"),
                "payment_failures": clean_row.get("payment_failures") or clean_row.get("engagement metrics - payment failures"),
                "support_tickets": clean_row.get("support_tickets") or clean_row.get("health indicators - support tickets"),
                "nps_score": clean_row.get("nps_score") or clean_row.get("health indicators - nps score"),
                "feature_usage_pct": clean_row.get("feature_usage_pct") or clean_row.get("health indicators - feature usage %"),
                "emails_sent": clean_row.get("emails_sent") or clean_row.get("health indicators - emails sent"),
                "emails_opened": clean_row.get("emails_opened") or clean_row.get("health indicators - emails opened"),
                "first_purchase": clean_row.get("first_purchase") or clean_row.get("billing & usage - first purchase"),
                "last_activity": clean_row.get("last_activity") or clean_row.get("billing & usage - last activity")
            }
            
            # Remove Nones so Pydantic defaults or feature engineering kicks in
            mapped = {k: v for k, v in mapped.items() if v is not None}
            
            try:
                result = _score_and_store_customer(mapped)
                batch_customers_for_email.append(result)
                imported += 1
            except Exception as e:
                errors.append(f"Row {idx + 1} error: {e}")
                
        if batch_customers_for_email:
            async def _coordinated_bulk_delivery(targets=batch_customers_for_email):
                import asyncio
                from services.store import update_customer_in_store
                for idx, item in enumerate(targets):
                    if idx > 0:
                        await asyncio.sleep(2.5)
                    try:
                        pers_msg = item.get("llm_analysis", {}).get("english", {}).get("email_strategy", "")
                        email_res = send_retention_email(
                            customer_id=item["customer_id"],
                            customer_name=item.get("name", item["customer_id"]),
                            receiver_email=item.get("email"),
                            risk_pct=item["risk_percentage"],
                            personalized_message=pers_msg
                        )
                        if email_res["status"] == "SENT":
                            item["sent_email"] = {
                                "subject": email_res.get("subject", ""),
                                "html_body": email_res.get("html_body", ""),
                                "timestamp": email_res.get("updated_at", "")
                            }
                            update_customer_in_store(item)
                    except Exception as ex:
                        logger.warning("Batch email failed for %s: %s", item["customer_id"], ex)
            background_tasks.add_task(_coordinated_bulk_delivery)

        return {
            "imported": imported,
            "errors": errors,
            "customers_scored": imported,
            "results": batch_customers_for_email,
        }
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        return JSONResponse(status_code=400, content={"error": str(e)})

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

        async def _coordinated_bulk_delivery(targets=batch_customers_for_email):
            import asyncio
            from services.store import update_customer_in_store

            for idx, item in enumerate(targets):
                if idx > 0:
                    await asyncio.sleep(2.5)
                try:
                    pers_msg = item.get("llm_analysis", {}).get("english", {}).get("email_strategy", "")
                    email_res = send_retention_email(
                        customer_id=item["customer_id"],
                        customer_name=item.get("name", item["customer_id"]),
                        receiver_email=item.get("email"),
                        risk_pct=item["risk_percentage"],
                        personalized_message=pers_msg
                    )
                    if email_res["status"] == "SENT":
                        item["sent_email"] = {
                            "subject": email_res.get("subject", ""),
                            "html_body": email_res.get("html_body", ""),
                            "timestamp": email_res.get("updated_at", "")
                        }
                        update_customer_in_store(item)
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


import hashlib
import datetime
import random

def _get_or_create_comm_plan(customer_id: str) -> dict:
    seed = int(hashlib.md5(customer_id.encode()).hexdigest(), 16)
    r = random.Random(seed)
    
    types = ["Call", "WhatsApp", "Email", "Meeting"]
    priorities = ["High", "Medium", "Low"]
    statuses = ["Pending", "Completed", "Overdue"]
    team_members = ["Sarah M.", "Ahmed K.", "Nour E.", "Laila T."]
    
    offset = r.randint(-5, 14)
    followup_date = (datetime.date.today() + datetime.timedelta(days=offset)).isoformat()
    
    status = r.choice(statuses)
    if offset < 0 and status == "Pending":
        status = "Overdue"
    elif offset >= 0 and status == "Overdue":
        status = "Pending"
        
    return {
        "followup_date": followup_date,
        "followup_type": r.choice(types),
        "priority": r.choice(priorities),
        "status": status,
        "assigned_to": r.choice(team_members),
        "notes": "Discuss renewal offer and check account health." if r.random() > 0.5 else "Send pricing updates and follow up on latest ticket."
    }

@router.get("/customers")
async def get_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=100),
    search: str = "",
    risk: str = "all",
    vip: str = "all",
    sort_by: str = "risk",
    sort_dir: str = "desc",
    date_from: str = "",
    date_to: str = "",
    comm_priority: str = "all",
    comm_status: str = "all",
    assigned_to: str = "all",
):
    rows = CUSTOMERS
    
    for row in rows:
        if "communication_plan" not in row:
            row["communication_plan"] = _get_or_create_comm_plan(row["customer_id"])

    if search:
        needle = search.lower()
        rows = [
            row
            for row in rows
            if needle in row["customer_id"].lower() or needle in row.get("name", "").lower() or needle in row["segment"].lower()
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
        
    if date_from:
        rows = [row for row in rows if row["communication_plan"]["followup_date"] >= date_from]
    if date_to:
        rows = [row for row in rows if row["communication_plan"]["followup_date"] <= date_to]
    if comm_priority != "all":
        rows = [row for row in rows if row["communication_plan"]["priority"].lower() == comm_priority.lower()]
    if comm_status != "all":
        rows = [row for row in rows if row["communication_plan"]["status"].lower() == comm_status.lower()]
    if assigned_to != "all":
        rows = [row for row in rows if row["communication_plan"]["assigned_to"].lower() == assigned_to.lower()]

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
            "name": row.get("name", row["customer_id"]),
            "risk": row["risk"],
            "vip_status": row["vip_status"],
            "revenue": row["revenue"],
            "priority": row["priority"],
            "priority_score": row["priority_score"],
            "last_activity": row["last_activity"],
            "communication_plan": row["communication_plan"],
            "timeline": row.get("llm_analysis", {}).get("timeline_ar", []),
            "recommended_actions": row.get("llm_analysis", {}).get("recommended_actions_ar", [])
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


@router.post("/customers/{customer_id}/draft-email")
async def draft_customer_email(customer_id: str):
    customer = CUSTOMERS_BY_ID.get(customer_id) or RECENT_ANALYSES.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Extract the email strategy from the LLM analysis
    llm = customer.get("llm_analysis", {})
    english_email = llm.get("english", {}).get("email_strategy", "Draft not available.")
    arabic_email = llm.get("arabic", {}).get("email_strategy", "المسودة غير متوفرة.")
    
    why_generated = llm.get("english", {}).get("why_generated", "Routine check-in")
    factors = llm.get("english", {}).get("personalization_factors", "Usage metrics")
    outcome = llm.get("english", {}).get("expected_outcome", "Improved engagement")
    
    # Simulate logging the event to the timeline
    if "timeline" not in customer:
        customer["timeline"] = []
        
    from datetime import datetime, timezone
    customer["timeline"].append({
        "type": "email_drafted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detail": "AI drafted personalized communication strategy."
    })
    
    return {
        "email_english": english_email,
        "email_arabic": arabic_email,
        "why_generated": why_generated,
        "personalization_factors": factors,
        "expected_outcome": outcome
    }

from fastapi.responses import FileResponse
import os

@router.get("/customers/template")
async def download_template():
    template_path = "backend/assets/template.xlsx"
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template not found")
    return FileResponse(template_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="AI_Retention_Engine_Template.xlsx")

@router.get("/customers/export")
async def export_customers():
    # Convert CUSTOMERS dict list to DataFrame
    if not CUSTOMERS:
        raise HTTPException(status_code=400, detail="No customers to export")
    
    df = pd.DataFrame(CUSTOMERS)
    
    # We create a simple DataFrame mapping original keys to something presentable.
    export_df = pd.DataFrame()
    export_df["User ID"] = df.get("customer_id", df.get("user_id", ""))
    export_df["Name"] = df.get("name", "")
    export_df["Email"] = df.get("email", "")
    export_df["Industry"] = df.get("industry", "")
    export_df["Contract"] = df.get("contract", "")
    export_df["Segment"] = df.get("segment", "")
    export_df["Avg Plan Price"] = df.get("avg_plan_price", 0)
    export_df["Total Paid"] = df.get("total_amount_paid", 0)
    export_df["Transactions"] = df.get("total_transactions", 0)
    export_df["Tenure (Days)"] = df.get("billing_tenure_days", 0)
    export_df["First Purchase"] = df.get("first_purchase", "")
    export_df["Last Activity"] = df.get("last_activity", "")
    export_df["Auto Renewals"] = df.get("auto_renew_count", 0)
    export_df["Cancellations"] = df.get("total_cancellations", 0)
    export_df["Payment Failures"] = df.get("payment_failures", 0)
    export_df["Support Tickets"] = df.get("support_tickets", 0)
    export_df["NPS Score"] = df.get("nps_score", 0)
    export_df["Feature Usage %"] = df.get("feature_usage_pct", 0)
    export_df["Emails Sent"] = df.get("emails_sent", 0)
    export_df["Emails Opened"] = df.get("emails_opened", 0)
    export_df["Risk Score"] = df.get("risk", 0)
    export_df["Health Score"] = df.get("health_score", 0)
    
    export_path = "backend/assets/export.xlsx"
    os.makedirs("backend/assets", exist_ok=True)
    export_df.to_excel(export_path, index=False)
    
    return FileResponse(export_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Customer_Export.xlsx")
