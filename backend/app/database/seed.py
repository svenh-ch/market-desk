"""
Datenbank vorbereiten: Tabellen anlegen, Auswahlliste einspielen,
alte Daten (früheres Terminal) einmalig übernehmen.
"""
import logging
import sqlite3

from sqlalchemy import inspect, text

from app.config import BACKEND_DIR
from app.database.connection import engine, SessionLocal, Base
from app.database.models import Company, WatchlistItem
from app.database.company_data import COMPANY_CATALOG

log = logging.getLogger(__name__)

OLD_DB = BACKEND_DIR / "terminal.db"


def _drop_outdated_tables():
    """Alte Tabellen mit von Hand eingetragenen Kennzahlen bzw. Lieferketten ohne Quelle entfernen."""
    insp = inspect(engine)
    with engine.begin() as conn:
        if "companies" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("companies")}
            if "base_price" in cols or "pe_ratio" in cols:
                conn.execute(text("DROP TABLE companies"))
        if "company_relationships" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("company_relationships")}
            if "origin" not in cols:
                conn.execute(text("DROP TABLE company_relationships"))


def _import_old_watchlist(db):
    """Watchlist aus der alten terminal.db übernehmen (nur einmal, solange die neue leer ist)."""
    if not OLD_DB.exists() or db.query(WatchlistItem).count() > 0:
        return
    try:
        con = sqlite3.connect(str(OLD_DB))
        rows = con.execute("SELECT symbol, notes FROM watchlist").fetchall()
        con.close()
    except Exception as e:  # alte DB unlesbar: einfach überspringen
        log.warning("Alte Watchlist nicht lesbar: %s", e)
        return
    for symbol, notes in rows:
        db.add(WatchlistItem(symbol=symbol, notes=notes))
    db.commit()
    log.info("Watchlist übernommen: %d Einträge", len(rows))


def seed():
    _drop_outdated_tables()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = {r[0] for r in db.query(Company.symbol).all()}
        for row in COMPANY_CATALOG:
            if row["symbol"] not in existing:
                db.add(Company(**row))
        db.commit()
        _import_old_watchlist(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
