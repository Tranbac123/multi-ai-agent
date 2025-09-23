from pydantic import BaseModel

class AgentRunCompleted(BaseModel):
    tenant_id: str
    run_id: str
    result: str

class BillingEvent(BaseModel):
    tenant_id: str
    request_id: str
    cost_usd: float

