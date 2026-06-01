from fastapi import APIRouter, HTTPException, Query

from services.connectors import registry as connector_registry
from services.ml_engine import _score_and_store_customer
from services.store import CUSTOMERS, CUSTOMERS_BY_ID, save_customers_to_store
from utils.helpers import now_iso
from core.config import logger

router = APIRouter()

@router.get("/status")
async def get_connectors_status():
    return {
        "connectors": connector_registry.status(),
        "checked_at": now_iso(),
    }


@router.get("/lookup/{customer_id}")
async def lookup_connector_customer(customer_id: str):
    res = connector_registry.lookup_customer(customer_id)
    if not res:
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{customer_id}' not found in any active connectors.",
        )
    return res


@router.post("/sync-all")
async def sync_all_connectors(
    limit_per_source: int = Query(25), score: bool = Query(True)
):
    merged = connector_registry.sync_all(limit_per_source=limit_per_source)
    scored_count = 0
    skipped = 0

    results_list = []

    if score:
        for raw_dict in merged["customers"]:
            try:
                cust = _score_and_store_customer(raw_dict)
                results_list.append(cust)
                scored_count += 1
            except Exception as ex:
                logger.warning("Failed to score synced customer: %s", ex)
                skipped += 1
    else:
        for raw_dict in merged["customers"]:
            results_list.append(
                {
                    "customer_id": raw_dict.get("user_id"),
                    "connector_source": raw_dict.get("_connector_source"),
                }
            )

    save_customers_to_store()

    return {
        "total_fetched": merged["total_fetched"],
        "total_synced": merged["total_fetched"],
        "scored_count": scored_count,
        "skipped": skipped,
        "sources_summary": merged["sources_summary"],
        "synced_at": merged["synced_at"],
        "results": results_list,
    }


@router.post("/{source}/sync")
async def sync_one_connector(
    source: str, limit: int = Query(50), score: bool = Query(True)
):
    if source not in connector_registry.connectors:
        raise HTTPException(status_code=400, detail=f"Unknown source '{source}'")

    res = connector_registry.sync_one(source, limit=limit)
    scored_count = 0

    results_list = []

    if score:
        for raw_dict in res.customers:
            try:
                cust = _score_and_store_customer(raw_dict)
                results_list.append(cust)
                scored_count += 1
            except Exception as ex:
                logger.warning("Failed to score synced customer: %s", ex)
    else:
        for raw_dict in res.customers:
            results_list.append(
                {"customer_id": raw_dict.get("user_id"), "connector_source": source}
            )

    save_customers_to_store()

    return {
        "source": source,
        "mode": res.mode,
        "total_fetched": res.total,
        "total_synced": res.total,
        "scored_count": scored_count,
        "errors": res.errors,
        "synced_at": res.synced_at,
        "results": results_list,
    }
