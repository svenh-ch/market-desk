import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PriceAlert
from app.models.alert import AlertCreate
from app.services.market_data import get_quote, get_quotes

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _to_dict(a: PriceAlert, price=None) -> dict:
    return {
        "id": a.id, "symbol": a.symbol, "condition": a.condition, "threshold": a.threshold,
        "note": a.note, "triggered": a.triggered_at is not None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        "current_price": price,
    }


@router.get("")
def list_alerts(db: Session = Depends(get_db)):
    alerts = db.query(PriceAlert).all()
    quotes = {q.symbol: q for q in get_quotes([a.symbol for a in alerts])}
    out = []
    for a in alerts:
        q = quotes.get(a.symbol)
        price = q.price if q and q.available and not q.stale else None
        if price is not None and a.triggered_at is None:
            hit = price > a.threshold if a.condition == "above" else price < a.threshold
            if hit:
                a.triggered_at = datetime.now(timezone.utc)
        out.append(_to_dict(a, price))
    db.commit()
    return out


@router.post("", status_code=201)
def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    sym = body.symbol.upper().strip()
    if not get_quote(sym).available:
        raise HTTPException(400, f"Für '{sym}' sind keine Kursdaten verfügbar – Ticker prüfen.")
    a = PriceAlert(id=str(uuid.uuid4())[:8], symbol=sym, condition=body.condition,
                   threshold=body.threshold, note=body.note)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_dict(a)


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: str, db: Session = Depends(get_db)):
    a = db.get(PriceAlert, alert_id)
    if not a:
        raise HTTPException(404, "Alarm nicht gefunden")
    db.delete(a)
    db.commit()
