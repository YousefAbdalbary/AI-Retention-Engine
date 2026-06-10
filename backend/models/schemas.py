from typing import Optional
from pydantic import BaseModel, Field

class CustomerProfile(BaseModel):
    user_id: str = Field(..., min_length=2, max_length=80)
    name: str = "Unknown"
    email: str = "Unknown"
    industry: str = "Unknown Industry"
    contract: str = "Standard Plan"
    segment: str = "Unassigned"

class BillingRaw(BaseModel):
    first_purchase: Optional[str] = None
    last_activity: Optional[str] = None
    avg_plan_price: float = Field(0.0, ge=0)
    total_transactions: int = Field(1, ge=0)
    auto_renew_count: int = Field(0, ge=0)
    cancellations: int = Field(0, ge=0)
    payment_failures: int = Field(0, ge=0)
    # the ones below can be raw or computed
    total_amount_paid: Optional[float] = None
    billing_tenure_days: Optional[int] = None
    cancel_rate: Optional[float] = None

class HealthRaw(BaseModel):
    support_tickets: int = Field(0, ge=0)
    nps_score: float = Field(5.0, ge=0, le=10)
    feature_usage_pct: float = Field(0.0, ge=0, le=100)
    emails_sent: int = Field(0, ge=0)
    emails_opened: int = Field(0, ge=0)
    email_open_rate: Optional[float] = None

class CustomerData(BaseModel):
    """The unified customer payload."""
    user_id: str = Field(..., min_length=2, max_length=80)
    
    # Raw Inputs (mapped from CSV/CRM)
    name: str = "Unknown"
    email: str = "Unknown"
    industry: str = "Unknown Industry"
    contract: str = "Standard Plan"
    segment: str = "Unassigned"
    
    avg_plan_price: float = Field(0.0, ge=0)
    total_transactions: int = Field(1, ge=0)
    auto_renew_count: int = Field(0, ge=0)
    total_cancellations: int = Field(0, ge=0)
    payment_failures: int = Field(0, ge=0)
    
    support_tickets: int = Field(0, ge=0)
    nps_score: float = Field(5.0, ge=0, le=10)
    feature_usage_pct: float = Field(0.0, ge=0, le=100)
    emails_sent: int = Field(0, ge=0)
    emails_opened: int = Field(0, ge=0)
    
    last_activity: Optional[str] = None
    first_purchase: Optional[str] = None

    # Engineered Features (if passed directly, else will be computed)
    total_amount_paid: Optional[float] = None
    billing_tenure_days: Optional[int] = None
    cancel_rate: Optional[float] = None
    email_open_rate: Optional[float] = None


class CSVUploadPayload(BaseModel):
    csv_text: str
    mode: str = Field("ready", pattern="^(ready|raw)$")


class EmailSendRequest(BaseModel):
    customer_id: str = Field(..., min_length=2, max_length=80)
    risk_pct: float = Field(..., ge=0, le=100)
    receiver_email: str | None = None
    personalized_message: str = ""
    attachment_path: str | None = None


class BulkEmailRequest(BaseModel):
    customer_ids: list[str] = Field(..., min_length=1)
    receiver_email: str | None = None


class CampaignTriggerRequest(BaseModel):
    risk_filter: str = Field("all", pattern="^(all|low|medium|high)$")
    receiver_email: str | None = None
    limit: int = Field(50, ge=1, le=500)
