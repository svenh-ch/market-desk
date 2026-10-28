"""
Marktdaten – ausschliesslich echte Daten von Yahoo Finance (über yfinance).

Grundsätze:
  - Keine simulierten, zufälligen oder fest eingetragenen Kurse/Kennzahlen.
  - Jeder Datensatz trägt Quelle, Abrufzeit und Cache-Alter (siehe DataMeta).
  - Schlägt eine Abfrage fehl, wird das klar gemeldet. Ist ein älterer Wert
    im Cache, wird er nur mit stale=True (= "veraltet") zurückgegeben.
  - Abfragen passieren nur, wenn die Oberfläche Daten anfragt; Kurse werden
    höchstens QUOTE_CACHE_SECONDS lang wiederverwendet.
"""
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

import yfinance as yf

from app.config import settings
from app.database.company_data import COMPANY_CATALOG
from app.models.asset import (
    AssetInfo, History, Indicator, IndicatorsResponse, OHLCV, Quote, SearchResult,
)

log = logging.getLogger(__name__)

CATALOG: Dict[str, dict] = {c["symbol"]: c for c in COMPANY_CATALOG}

# Yahoo liefert manche Börsen in Unterwährungen (Pence, Cent, Agorot)
_MINOR_CURRENCIES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}

_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="yahoo")


# ── Kleiner Cache mit Altersangabe ────────────────────────────────────────────

class _Cache:
    def __init__(self):
        self._data: Dict[str, Tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Tuple[Optional[object], float]:
        with self._lock:
            entry = self._data.get(key)
        if not entry:
            return None, math.inf
        return entry[1], time.time() - entry[0]

    def put(self, key: str, value: object) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)


_quotes = _Cache()
_histories = _Cache()
_infos = _Cache()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cached(cache: _Cache, key: str, ttl: int, fetch: Callable[[], object], unavailable: Callable[[str], object]):
    """
    Liefert frische Daten (aus Cache, falls jünger als ttl) mit Herkunftsangaben.
    Bei Fehlern: ältere Daten mit stale=True, sonst ein "nicht verfügbar"-Objekt.
    """
    value, age = cache.get(key)
    if value is not None and age < ttl:
        return value.model_copy(update={"from_cache": True, "cache_age_seconds": int(age)})

    try:
        fresh = fetch()
    except Exception as e:  # Netzwerk, Yahoo-Sperre, unbekannter Ticker …
        log.warning("Abfrage %s fehlgeschlagen: %s", key, e)
        fresh = unavailable(f"Abfrage bei Yahoo Finance fehlgeschlagen ({type(e).__name__}).")

    if getattr(fresh, "available", False):
        cache.put(key, fresh)
        return fresh

    if value is not None:  # Aktualisierung fehlgeschlagen → alte Daten deutlich kennzeichnen
        return value.model_copy(update={
            "from_cache": True, "cache_age_seconds": int(age), "stale": True,
            "error": "Aktualisierung fehlgeschlagen – angezeigt werden ältere Daten.",
        })
    return fresh


def _currency(raw: Optional[str]) -> Tuple[Optional[str], float]:
    """Währung normalisieren. Gibt (Währung, Teiler) zurück, z. B. GBp → (GBP, 100)."""
    if raw in _MINOR_CURRENCIES:
        return _MINOR_CURRENCIES[raw]
    return (raw.upper() if raw else None), 1.0


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _to_datetime(ts) -> Optional[datetime]:
    """Yahoo-Zeitpunkt (Unix-Zahl oder – ab yfinance 1.7 – pandas.Timestamp) → datetime (UTC)."""
    if ts is None:
        return None
    if hasattr(ts, "to_pydatetime"):
        dt = ts.to_pydatetime()
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _catalog_name(sym: str) -> str:
    return CATALOG.get(sym, {}).get("name", sym)


# ── Kurse ─────────────────────────────────────────────────────────────────────

def _fetch_quote(sym: str) -> Quote:
    t = yf.Ticker(sym)
    bars = t.history(period="1d", interval="1m", auto_adjust=False)
    meta = t.history_metadata or {}

    currency, div = _currency(meta.get("currency"))
    price = _num(meta.get("regularMarketPrice"))
    prev = _num(meta.get("previousClose")) or _num(meta.get("chartPreviousClose"))
    if price is None and not bars.empty:
        price = _num(bars["Close"].dropna().iloc[-1]) if not bars["Close"].dropna().empty else None
    if price is None:
        return _quote_unavailable(sym, "Keine Kursdaten von Yahoo Finance erhalten (Ticker unbekannt oder nicht gehandelt).")

    price /= div
    prev = prev / div if prev else None
    high = _num(meta.get("regularMarketDayHigh"))
    low = _num(meta.get("regularMarketDayLow"))
    ts = meta.get("regularMarketTime")

    return Quote(
        symbol=sym,
        name=meta.get("longName") or meta.get("shortName") or _catalog_name(sym),
        available=True,
        price=round(price, 4),
        prev_close=round(prev, 4) if prev else None,
        change=round(price - prev, 4) if prev else None,
        change_pct=round((price - prev) / prev * 100, 4) if prev else None,
        day_high=round(high / div, 4) if high else None,
        day_low=round(low / div, 4) if low else None,
        volume=int(meta["regularMarketVolume"]) if meta.get("regularMarketVolume") else None,
        currency=currency,
        exchange=meta.get("fullExchangeName") or meta.get("exchangeName"),
        market_time=_to_datetime(ts),
        fetched_at=_now(),
    )


def _quote_unavailable(sym: str, error: str) -> Quote:
    return Quote(symbol=sym, name=_catalog_name(sym), available=False, fetched_at=_now(), error=error)


def get_quote(symbol: str) -> Quote:
    sym = symbol.upper().strip()
    return _cached(_quotes, sym, settings.QUOTE_CACHE_SECONDS,
                   lambda: _fetch_quote(sym), lambda err: _quote_unavailable(sym, err))


def get_quotes(symbols: List[str]) -> List[Quote]:
    """Mehrere Kurse parallel (maximal 6 gleichzeitige Anfragen an Yahoo)."""
    syms = list(dict.fromkeys(s.upper().strip() for s in symbols if s.strip()))
    return list(_pool.map(get_quote, syms))


# ── Kursverlauf ───────────────────────────────────────────────────────────────

def _period_for(days: int) -> str:
    for limit, period in ((31, "1mo"), (93, "3mo"), (186, "6mo"), (370, "1y"), (740, "2y")):
        if days <= limit:
            return period
    return "5y"


def _history_unavailable(sym: str, err: str) -> History:
    return History(symbol=sym, available=False, fetched_at=_now(), error=err)


def _fetch_history(sym: str, days: int) -> History:
    t = yf.Ticker(sym)
    df = t.history(period=_period_for(days), interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return _history_unavailable(sym, "Kein Kursverlauf von Yahoo Finance erhalten.")
    currency, div = _currency((t.history_metadata or {}).get("currency"))
    candles: Dict[int, OHLCV] = {}
    for ts, row in df.iterrows():
        o, h, l, c = (_num(row.get(k)) for k in ("Open", "High", "Low", "Close"))
        if None in (o, h, l, c):
            continue
        unix = int(ts.timestamp())
        candles[unix] = OHLCV(time=unix, open=round(o / div, 4), high=round(h / div, 4),
                              low=round(l / div, 4), close=round(c / div, 4),
                              volume=int(_num(row.get("Volume")) or 0))
    if not candles:
        return _history_unavailable(sym, "Kursverlauf enthält keine gültigen Werte.")
    return History(symbol=sym, available=True, currency=currency,
                   candles=[candles[k] for k in sorted(candles)], fetched_at=_now())


def get_history(symbol: str, days: int = 365) -> History:
    sym = symbol.upper().strip()
    return _cached(_histories, f"{sym}:{days}", settings.HISTORY_CACHE_SECONDS,
                   lambda: _fetch_history(sym, days), lambda err: _history_unavailable(sym, err))


# ── Firmenangaben & Kennzahlen ────────────────────────────────────────────────

def _info_unavailable(sym: str, err: str) -> AssetInfo:
    return AssetInfo(symbol=sym, available=False, name=_catalog_name(sym), fetched_at=_now(), error=err)


def _fetch_info(sym: str) -> AssetInfo:
    i = yf.Ticker(sym).info or {}
    if not i or not (i.get("longName") or i.get("shortName") or i.get("quoteType")):
        return _info_unavailable(sym, "Keine Firmenangaben von Yahoo Finance erhalten.")
    currency, div = _currency(i.get("currency"))

    def price_field(key):
        v = _num(i.get(key))
        return round(v / div, 4) if v is not None else None

    return AssetInfo(
        symbol=sym, available=True,
        name=i.get("longName") or i.get("shortName") or _catalog_name(sym),
        description=i.get("longBusinessSummary"),
        asset_type=(i.get("quoteType") or "").lower() or None,
        sector=i.get("sector"), industry=i.get("industry"), country=i.get("country"),
        currency=currency, financial_currency=i.get("financialCurrency"),
        exchange=i.get("fullExchangeName") or i.get("exchange"),
        website=i.get("website"),
        employees=i.get("fullTimeEmployees"),
        market_cap=_num(i.get("marketCap")),
        pe_ratio=_num(i.get("trailingPE")),
        price_to_book=_num(i.get("priceToBook")),
        ev_ebitda=_num(i.get("enterpriseToEbitda")),
        eps=_num(i.get("trailingEps")),
        # Yahoo liefert dividendYield inzwischen bereits in Prozent (z. B. 3.7 = 3,7 %)
        dividend_yield=_num(i.get("dividendYield")),
        revenue=_num(i.get("totalRevenue")),
        week_52_high=price_field("fiftyTwoWeekHigh"),
        week_52_low=price_field("fiftyTwoWeekLow"),
        avg_volume=i.get("averageVolume"),
        fetched_at=_now(),
    )


def get_asset_info(symbol: str) -> AssetInfo:
    sym = symbol.upper().strip()
    return _cached(_infos, sym, settings.INFO_CACHE_SECONDS,
                   lambda: _fetch_info(sym), lambda err: _info_unavailable(sym, err))


# ── Technische Indikatoren (berechnet aus dem echten Kursverlauf) ─────────────

def _sma(prices: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(prices)
    for i in range(window - 1, len(prices)):
        out[i] = sum(prices[i - window + 1: i + 1]) / window
    return out


def _ema(prices: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(prices)
    if not prices:
        return out
    k, ema = 2 / (window + 1), prices[0]
    for i, p in enumerate(prices):
        ema = p * k + ema * (1 - k)
        if i >= window - 1:
            out[i] = ema
    return out


def _rsi(prices: List[float], window: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(prices)
    if len(prices) < window + 1:
        return out
    gains = [max(prices[i] - prices[i - 1], 0) for i in range(1, len(prices))]
    losses = [max(prices[i - 1] - prices[i], 0) for i in range(1, len(prices))]
    avg_g, avg_l = sum(gains[:window]) / window, sum(losses[:window]) / window
    for i in range(window, len(prices)):
        avg_g = (avg_g * (window - 1) + gains[i - 1]) / window
        avg_l = (avg_l * (window - 1) + losses[i - 1]) / window
        rs = avg_g / avg_l if avg_l else 100
        out[i] = round(100 - 100 / (1 + rs), 2)
    return out


def get_indicators(symbol: str) -> IndicatorsResponse:
    hist = get_history(symbol, 400)
    meta = {k: getattr(hist, k) for k in ("source", "fetched_at", "from_cache", "cache_age_seconds", "stale", "error")}
    if not hist.available:
        return IndicatorsResponse(symbol=hist.symbol, available=False, **meta)

    times = [c.time for c in hist.candles]
    closes = [c.close for c in hist.candles]

    def pack(vals):
        return [{"time": t, "value": round(v, 4)} for t, v in zip(times, vals) if v is not None]

    sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
    ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
    macd = [{"time": t, "value": round(a - b, 4)} for t, a, b in zip(times, ema12, ema26) if a is not None and b is not None]

    signal, reason = "NEUTRAL", "Zu wenig Daten für ein Signal (mind. 200 Handelstage nötig)."
    valid = [(a, b) for a, b in zip(sma50, sma200) if a and b]
    if len(valid) >= 2:
        (p50, p200), (c50, c200) = valid[-2], valid[-1]
        if p50 <= p200 and c50 > c200:
            signal, reason = "BUY", "Golden Cross: SMA50 hat SMA200 nach oben gekreuzt"
        elif p50 >= p200 and c50 < c200:
            signal, reason = "SELL", "Death Cross: SMA50 hat SMA200 nach unten gekreuzt"
        elif c50 > c200:
            signal, reason = "BUY", "SMA50 über SMA200 (Aufwärtstrend)"
        else:
            signal, reason = "SELL", "SMA50 unter SMA200 (Abwärtstrend)"

    return IndicatorsResponse(
        symbol=hist.symbol, available=True,
        indicators=[
            Indicator(name="SMA20", values=pack(_sma(closes, 20))),
            Indicator(name="SMA50", values=pack(sma50)),
            Indicator(name="SMA200", values=pack(sma200)),
            Indicator(name="EMA12", values=pack(ema12)),
            Indicator(name="EMA26", values=pack(ema26)),
            Indicator(name="RSI14", values=pack(_rsi(closes))),
            Indicator(name="MACD", values=macd),
        ],
        signal=signal, signal_reason=reason, **meta,
    )


# ── Übersicht & Suche ─────────────────────────────────────────────────────────

# Laufband unten: wichtige Indizes und Kryptowährungen
TICKER_SYMBOLS = ["^GSPC", "^IXIC", "^DJI", "^SSMI", "^GDAXI", "^FTSE", "BTC-USD", "ETH-USD"]


def get_market_overview() -> List[Quote]:
    return get_quotes(TICKER_SYMBOLS)


def search_assets(query: str, limit: int = 12) -> Tuple[List[SearchResult], Optional[str]]:
    """
    Sucht nach Firmenname oder Ticker. Kombiniert die eigene Auswahlliste
    mit der Yahoo-Suche (findet weltweit Wertpapiere, z. B. "Nestle" → NESN.SW).
    Gibt (Treffer, Fehlermeldung oder None) zurück.
    """
    q = query.strip()
    ql = q.lower()
    results: Dict[str, SearchResult] = {}
    for sym, c in CATALOG.items():
        if ql in sym.lower() or ql in c["name"].lower():
            results[sym] = SearchResult(symbol=sym, name=c["name"], exchange=c.get("exchange"), sector=c.get("sector"))

    error = None
    try:
        for r in yf.Search(q, max_results=limit, news_count=0).quotes:
            sym = r.get("symbol")
            if not sym or sym in results:
                continue
            results[sym] = SearchResult(
                symbol=sym,
                name=(r.get("longname") or r.get("shortname") or sym).strip(),
                asset_type=r.get("quoteTypeDisp") or r.get("quoteType"),
                exchange=r.get("exchDisp") or r.get("exchange"),
                sector=r.get("sectorDisp") or r.get("sector"),
            )
    except Exception as e:
        log.warning("Yahoo-Suche fehlgeschlagen: %s", e)
        error = "Yahoo-Suche nicht erreichbar – es werden nur Treffer aus der eigenen Liste angezeigt."
    return list(results.values())[:limit], error
