from pydantic import BaseModel, Field


class CustomerData(BaseModel):
    user_id: str = Field(..., min_length=2, max_length=80)
    avg_plan_price: float = Field(..., ge=0)
    total_amount_paid: float = Field(..., ge=0)
    total_transactions: int = Field(..., ge=0)
    billing_tenure_days: int = Field(..., ge=0)
    auto_renew_count: int = Field(..., ge=0)
    total_cancellations: int = Field(..., ge=0)
    cancel_rate: float = Field(0.0, ge=0)


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
