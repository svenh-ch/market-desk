from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DataMeta(BaseModel):
    """Herkunft und Alter eines Datensatzes – wird überall mitgeliefert."""
    source: str = "Yahoo Finance"
    fetched_at: Optional[datetime] = None     # wann wir die Daten geholt haben
    from_cache: bool = False
    cache_age_seconds: int = 0
    stale: bool = False                       # True = Aktualisierung fehlgeschlagen, ältere Daten
    error: Optional[str] = None               # verständliche Fehlermeldung


class Quote(DataMeta):
    symbol: str
    name: str
    available: bool
    price: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    market_time: Optional[datetime] = None    # Zeitpunkt des Kurses laut Börse


class OHLCV(BaseModel):
    time: int  # Unix-Zeit
    open: float
    high: float
    low: float
    close: float
    volume: int


class History(DataMeta):
    symbol: str
    available: bool
    currency: Optional[str] = None
    candles: List[OHLCV] = []


class AssetInfo(DataMeta):
    symbol: str
    available: bool
    name: str
    description: Optional[str] = None
    asset_type: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    financial_currency: Optional[str] = None
    exchange: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    ev_ebitda: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = None   # in Prozent
    revenue: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    avg_volume: Optional[int] = None


class Indicator(BaseModel):
    name: str
    values: List[dict]  # [{time: int, value: float}]


class IndicatorsResponse(DataMeta):
    symbol: str
    available: bool
    indicators: List[Indicator] = []
    signal: Optional[str] = None
    signal_reason: Optional[str] = None


class SearchResult(BaseModel):
    symbol: str
    name: str
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
