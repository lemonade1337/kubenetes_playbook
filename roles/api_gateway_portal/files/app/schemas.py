from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    remaining_tokens: int
    monthly_quota: int
    total_consumed: int
    created_at: datetime

    class Config:
        from_attributes = True

class ApiKeyOut(BaseModel):
    id: int
    name: str
    api_key: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GenerateApiKeyRequest(BaseModel):
    name: str = Field(default="My API Key")

class AddTokensRequest(BaseModel):
    user_id: int
    amount: int = Field(gt=0, description="Amount of tokens to add")

class SetMonthlyQuotaRequest(BaseModel):
    quota: int = Field(gt=0, description="New default monthly token quota")
    apply_to_existing_users: bool = True

class ResetBalancesRequest(BaseModel):
    reset_to_quota: bool = True

class UsageLogOut(BaseModel):
    id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    endpoint: str
    status_code: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "qwen2.5:3b"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
