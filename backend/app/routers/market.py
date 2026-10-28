from fastapi import APIRouter, Query
from app.services.market_data import get_market_overview, get_quotes, search_assets

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview")
def market_overview():
    """Laufband: wichtige Indizes und Kryptowährungen."""
    return [q.model_dump() for q in get_market_overview()]


@router.get("/quotes")
def quotes(symbols: str = Query(..., description="Kommagetrennt, z. B. AAPL,NESN.SW")):
    """Mehrere Kurse auf einmal (die Oberfläche fragt so alle sichtbaren Kurse ab)."""
    syms = [s for s in symbols.split(",") if s.strip()][:60]
    return [q.model_dump() for q in get_quotes(syms)]


@router.get("/search")
def search(q: str = Query(..., min_length=1)):
    results, error = search_assets(q)
    return {"results": [r.model_dump() for r in results], "error": error}
