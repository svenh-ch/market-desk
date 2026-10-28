from fastapi import APIRouter, Query
from app.services import scoring
from app.services.reference_data import risk_free_rates

router = APIRouter(prefix="/api", tags=["score"])


@router.get("/score/{symbol}")
def score(symbol: str, refresh: bool = Query(default=False)):
    """Eigener Score. Läuft im Hintergrund – Antwort enthält status 'running' oder 'done'."""
    return scoring.get_or_start(symbol, refresh=refresh)


@router.get("/rates")
def rates():
    """Risikofreie Zinsen (FRED für USD, SNB für CHF)."""
    return risk_free_rates()
