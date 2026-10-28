"""
News – echte Schlagzeilen über die Yahoo-Finance-Suche.

(Hinweis: Ticker.news ist in yfinance 1.2.0 defekt, die Suche liefert aber
dieselben Yahoo-News inkl. Original-Link, Quelle und Zeitpunkt.)
Es gibt keine automatische Stimmungsbewertung – nichts wird erfunden.
"""
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import yfinance as yf

from app.config import settings

log = logging.getLogger(__name__)

# Ohne Ticker: allgemeine Marktnachrichten über diese Suchbegriffe
GENERAL_QUERIES = ["stock market", "SMI Swiss market", "DAX Europe stocks"]

_cache: Dict[str, Tuple[float, List[dict]]] = {}
_lock = threading.Lock()


def _search_news(query: str, count: int) -> List[dict]:
    items = []
    for n in yf.Search(query, max_results=1, news_count=count).news:
        link = n.get("link")
        title = n.get("title")
        if not link or not title:
            continue
        ts = n.get("providerPublishTime")
        items.append({
            "id": n.get("uuid") or link,
            "headline": title,
            "source": n.get("publisher") or "unbekannt",
            "url": link,
            "published_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
            "symbols": n.get("relatedTickers") or [],
        })
    return items


def get_news(symbol: Optional[str] = None, limit: int = 20) -> dict:
    key = (symbol or "ALL").upper()
    with _lock:
        cached = _cache.get(key)
    if cached and time.time() - cached[0] < settings.NEWS_CACHE_SECONDS:
        age = int(time.time() - cached[0])
        return _wrap(cached[1][:limit], cached[0], from_cache=True, age=age)

    try:
        queries = [symbol] if symbol else GENERAL_QUERIES
        seen, items = set(), []
        for q in queries:
            for it in _search_news(q, max(limit, 10)):
                if it["id"] not in seen:
                    seen.add(it["id"])
                    items.append(it)
        items.sort(key=lambda x: x["published_at"] or "", reverse=True)
        now = time.time()
        with _lock:
            _cache[key] = (now, items)
        return _wrap(items[:limit], now)
    except Exception as e:
        log.warning("News-Abfrage fehlgeschlagen: %s", e)
        if cached:
            return _wrap(cached[1][:limit], cached[0], from_cache=True, age=int(time.time() - cached[0]),
                         stale=True, error="Aktualisierung fehlgeschlagen – ältere Nachrichten.")
        return _wrap([], time.time(), error="Nachrichten von Yahoo Finance nicht verfügbar.")


def _wrap(items, fetched_ts, from_cache=False, age=0, stale=False, error=None) -> dict:
    return {
        "items": items,
        "source": "Yahoo Finance (Nachrichtensuche)",
        "fetched_at": datetime.fromtimestamp(fetched_ts, tz=timezone.utc).isoformat(),
        "from_cache": from_cache,
        "cache_age_seconds": age,
        "stale": stale,
        "error": error,
    }
