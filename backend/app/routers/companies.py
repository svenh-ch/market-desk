from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database.connection import get_db
from app.database.models import Company

router = APIRouter(prefix="/api/companies", tags=["companies"])

# Liefert nur die Auswahlliste (Stammdaten). Kurse holt die Oberfläche separat
# über /api/market/quotes, Kennzahlen über /api/assets/{symbol}/info.


def _to_dict(c: Company) -> dict:
    return {"symbol": c.symbol, "name": c.name, "sector": c.sector, "exchange": c.exchange}


@router.get("")
def list_companies(
    sector: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if sector:
        q = q.filter(Company.sector == sector)
    if search:
        q = q.filter(Company.symbol.ilike(f"%{search}%") | Company.name.ilike(f"%{search}%"))
    total = q.count()
    rows = q.order_by(Company.symbol).offset(offset).limit(limit).all()
    return {"total": total, "items": [_to_dict(c) for c in rows]}


@router.get("/sectors")
def list_sectors(db: Session = Depends(get_db)):
    return sorted({r[0] for r in db.query(Company.sector).distinct().all() if r[0]})


@router.get("/{symbol}")
def get_company(symbol: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.symbol == symbol.upper()).first()
    if not c:
        raise HTTPException(404, f"'{symbol}' ist nicht in der Auswahlliste")
    return _to_dict(c)
