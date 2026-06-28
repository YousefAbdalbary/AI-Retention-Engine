import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import FRONTEND_DIR, logger
from api.routers import (
    risk,
    customers,
    dashboard,
    emails,
    connectors_api,
    health,
)

app = FastAPI(
    title="Customer Retention AI",
    description="Enterprise customer retention, churn analytics, and structured LLM insights API",
    version="4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(risk.router, prefix="/api/v1", tags=["Risk Analysis"])
app.include_router(customers.router, prefix="/api/v1", tags=["Customers"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(emails.router, prefix="/api/v1/email", tags=["Emails"])
app.include_router(
    connectors_api.router, prefix="/api/v1/connectors", tags=["Connectors"]
)
app.include_router(health.router, prefix="/api/v1", tags=["System Health"])

import asyncio


async def background_init():
    logger.info("Starting background initialization...")
    from services.store import (
        async_load_customers_from_store,
        CUSTOMERS,
        CUSTOMERS_BY_ID,
    )

    loaded_data = await async_load_customers_from_store()

    # Populate the global store
    CUSTOMERS.extend(loaded_data)
    for c in CUSTOMERS:
        CUSTOMERS_BY_ID[c["customer_id"]] = c

    logger.info("Background initialization complete. Store is ready.")


# Startup Event
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_init())


# Static Mount
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found: %s", FRONTEND_DIR)

# Trigger reload
