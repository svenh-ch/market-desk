from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PositionCreate(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    notes: Optional[str] = None


class Position(BaseModel):
    id: str
    symbol: str
    name: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    pnl: float
    pnl_pct: float
    day_pnl: float
    day_pnl_pct: float
    notes: Optional[str] = None
    opened_at: datetime


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    positions: list[Position]
