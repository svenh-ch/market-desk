import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import PortfolioPosition
from app.models.portfolio import PositionCreate
from app.services.market_data import get_quote, get_quotes

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _enrich(p: PortfolioPosition, q) -> dict:
    """Position mit aktuellem Kurs. Ohne Kurs werden keine Werte erfunden (None)."""
    cost = p.avg_cost * p.quantity
    price = q.price if q.available else None
    value = price * p.quantity if price is not None else None
    pnl = value - cost if value is not None else None
    day_pnl = (price - q.prev_close) * p.quantity if price is not None and q.prev_close else None
    return {
        "id": p.id, "symbol": p.symbol, "name": q.name,
        "quantity": p.quantity, "avg_cost": p.avg_cost,
        "currency": q.currency,
        "current_price": price,
        "market_value": round(value, 2) if value is not None else None,
        "cost_basis": round(cost, 2),
        "pnl": round(pnl, 2) if pnl is not None else None,
        "pnl_pct": round(pnl / cost * 100, 4) if pnl is not None and cost else None,
        "day_pnl": round(day_pnl, 2) if day_pnl is not None else None,
        "day_pnl_pct": q.change_pct if price is not None else None,
        "notes": p.notes,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "quote_time": q.market_time.isoformat() if q.market_time else None,
        "quote_error": q.error,
    }


@router.get("")
def get_portfolio(db: Session = Depends(get_db)):
    rows = db.query(PortfolioPosition).all()
    quotes = {q.symbol: q for q in get_quotes([r.symbol for r in rows])}
    positions = [_enrich(r, quotes[r.symbol]) for r in rows]

    # Summen nur, wenn alle Positionen dieselbe Währung und einen Kurs haben –
    # sonst würden verschiedene Währungen fälschlich addiert.
    currencies = {p["currency"] for p in positions}
    complete = all(p["market_value"] is not None for p in positions)
    summable = len(currencies) == 1 and complete
    total_value = sum(p["market_value"] for p in positions) if summable else None
    total_cost = sum(p["cost_basis"] for p in positions) if summable else None
    total_pnl = total_value - total_cost if summable else None
    return {
        "positions": positions,
        "currency": currencies.pop() if summable and positions else None,
        "total_value": round(total_value, 2) if total_value is not None else None,
        "total_cost": round(total_cost, 2) if total_cost is not None else None,
        "total_pnl": round(total_pnl, 2) if total_pnl is not None else None,
        "total_pnl_pct": round(total_pnl / total_cost * 100, 4) if summable and total_cost else None,
        "day_pnl": round(sum(p["day_pnl"] for p in positions), 2) if summable and all(p["day_pnl"] is not None for p in positions) else None,
        "totals_note": None if summable or not positions else
            "Keine Summe: Positionen in verschiedenen Währungen oder ohne aktuellen Kurs.",
    }


@router.post("/positions", status_code=201)
def add_position(body: PositionCreate, db: Session = Depends(get_db)):
    sym = body.symbol.upper().strip()
    q = get_quote(sym)
    if not q.available:
        raise HTTPException(400, f"Für '{sym}' sind keine Kursdaten verfügbar – Ticker prüfen.")
    p = PortfolioPosition(id=str(uuid.uuid4())[:8], symbol=sym, quantity=body.quantity,
                          avg_cost=body.avg_cost, notes=body.notes)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _enrich(p, q)


@router.delete("/positions/{position_id}", status_code=204)
def remove_position(position_id: str, db: Session = Depends(get_db)):
    p = db.get(PortfolioPosition, position_id)
    if not p:
        raise HTTPException(404, "Position nicht gefunden")
    db.delete(p)
    db.commit()
