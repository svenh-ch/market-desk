from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class AlertCreate(BaseModel):
    symbol: str
    condition: Literal["above", "below"]
    threshold: float
    note: Optional[str] = None


class Alert(BaseModel):
    id: str
    symbol: str
    condition: Literal["above", "below"]
    threshold: float
    note: Optional[str] = None
    triggered: bool = False
    created_at: datetime
    triggered_at: Optional[datetime] = None
