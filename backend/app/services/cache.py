"""
Dauerhafter Zwischenspeicher (SQLite) für aufbereitete Daten.

Gespeichert wird JSON mit Abrufzeit. So überleben Bilanzdaten, Vergleichsgruppen
usw. einen Neustart der App, und Quellen werden nicht unnötig oft abgefragt.
"""
import json
import threading
import time
from typing import Any, Callable, Optional, Tuple

from sqlalchemy import Column, Float, String, Text

from app.database.connection import Base, SessionLocal, engine

_lock = threading.Lock()


class CacheEntry(Base):
    __tablename__ = "data_cache"
    key = Column(String, primary_key=True)
    fetched_at = Column(Float, nullable=False)
    payload = Column(Text, nullable=False)


Base.metadata.create_all(bind=engine, tables=[CacheEntry.__table__])


def get(key: str) -> Tuple[Optional[Any], float]:
    """(Wert, Alter in Sekunden) – oder (None, inf)."""
    with SessionLocal() as db:
        e = db.get(CacheEntry, key)
        if not e:
            return None, float("inf")
        return json.loads(e.payload), time.time() - e.fetched_at


def put(key: str, value: Any) -> None:
    payload = json.dumps(value, default=str)
    with _lock, SessionLocal() as db:
        e = db.get(CacheEntry, key)
        if e:
            e.payload, e.fetched_at = payload, time.time()
        else:
            db.add(CacheEntry(key=key, payload=payload, fetched_at=time.time()))
        db.commit()


def delete(key: str) -> None:
    with _lock, SessionLocal() as db:
        e = db.get(CacheEntry, key)
        if e:
            db.delete(e)
            db.commit()


def cached(key: str, ttl: float, fetch: Callable[[], Any], keep_on_error: bool = True) -> Tuple[Any, float, bool]:
    """
    Liefert (Wert, Alter, veraltet). Ist der Eintrag jünger als ttl, kommt er aus
    dem Speicher. Sonst wird neu geholt; schlägt das fehl, wird – falls vorhanden –
    der alte Wert mit veraltet=True zurückgegeben (Fehler wird sonst weitergereicht).
    """
    value, age = get(key)
    if value is not None and age < ttl:
        return value, age, False
    try:
        fresh = fetch()
    except Exception:
        if keep_on_error and value is not None:
            return value, age, True
        raise
    if fresh is not None:
        put(key, fresh)
    return fresh, 0.0, False
