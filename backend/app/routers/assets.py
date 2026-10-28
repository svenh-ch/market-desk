from fastapi import APIRouter, Query
from app.services.market_data import get_quote, get_history, get_asset_info, get_indicators

router = APIRouter(prefix="/api/assets", tags=["assets"])

# Alle Endpunkte liefern auch bei fehlenden Daten eine Antwort (available=false + error),
# damit die Oberfläche "Daten nicht verfügbar" anzeigen kann statt abzustürzen.


@router.get("/{symbol}/quote")
def asset_quote(symbol: str):
    return get_quote(symbol).model_dump()


@router.get("/{symbol}/info")
def asset_info(symbol: str):
    return get_asset_info(symbol).model_dump()


@router.get("/{symbol}/history")
def asset_history(symbol: str, days: int = Query(default=365, ge=7, le=1825)):
    return get_history(symbol, days).model_dump()


@router.get("/{symbol}/indicators")
def asset_indicators(symbol: str):
    return get_indicators(symbol).model_dump()
