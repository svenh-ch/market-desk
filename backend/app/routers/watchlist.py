from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database.connection import get_db
from app.database.models import WatchlistItem
from app.services.market_data import get_quote

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Die Watchlist speichert nur die Ticker. Kurse holt die Oberfläche
# laufend über /api/market/quotes (mit Zeitstempel und Quelle).


class WatchlistAdd(BaseModel):
    symbol: str
    notes: Optional[str] = None


def _to_dict(i: WatchlistItem) -> dict:
    return {"id": i.id, "symbol": i.symbol, "notes": i.notes,
            "added_at": i.added_at.isoformat() if i.added_at else None}


@router.get("")
def get_watchlist(db: Session = Depends(get_db)):
    return [_to_dict(i) for i in db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()]


@router.post("", status_code=201)
def add_to_watchlist(body: WatchlistAdd, db: Session = Depends(get_db)):
    sym = body.symbol.upper().strip()
    if db.query(WatchlistItem).filter(WatchlistItem.symbol == sym).first():
        raise HTTPException(400, f"'{sym}' ist bereits auf der Watchlist")
    if not get_quote(sym).available:
        raise HTTPException(400, f"Für '{sym}' sind keine Kursdaten verfügbar – Ticker prüfen.")
    item = WatchlistItem(symbol=sym, notes=body.notes)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


@router.delete("/{symbol}", status_code=204)
def remove_from_watchlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.symbol == symbol.upper()).first()
    if not item:
        raise HTTPException(404, f"'{symbol}' ist nicht auf der Watchlist")
    db.delete(item)
    db.commit()
