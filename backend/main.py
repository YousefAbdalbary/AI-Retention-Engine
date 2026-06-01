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


# Static Mount
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    logger.warning("Frontend directory not found: %s", FRONTEND_DIR)

# Trigger reload
