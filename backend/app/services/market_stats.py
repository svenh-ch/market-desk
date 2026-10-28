"""
Marktdaten für den Score: Firmenangaben, Wechselkurse, Momentum, Volatilität, Beta.
Alles aus echten Yahoo-Kursen (dividendenbereinigt), täglich zwischengespeichert.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from app import scoring_config as cfg
from app.services import cache

log = logging.getLogger(__name__)


def _num(x) -> Optional[float]:
    try:
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


# ── Firmenangaben ─────────────────────────────────────────────────────────────

def info(symbol: str) -> dict:
    """Die für Score und Vergleichsgruppe nötigen Felder aus Yahoo (täglich)."""
    def fetch():
        i = yf.Ticker(symbol).info or {}
        cur = i.get("currency")
        return {
            "symbol": symbol,
            "name": i.get("longName") or i.get("shortName"),
            "sector": i.get("sector"), "industry": i.get("industry"), "country": i.get("country"),
            "quote_type": i.get("quoteType"), "exchange": i.get("exchange"),
            "currency": cur,
            # Yahoo gibt bei London-Kursen (GBp) den Börsenwert bereits in GBP an
            "market_cap_currency": "GBP" if cur in ("GBp", "GBX") else (cur.upper() if cur else None),
            "market_cap": _num(i.get("marketCap")),
            "financial_currency": i.get("financialCurrency") or (cur.upper() if cur and cur not in ("GBp", "GBX") else "GBP"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    value, _, _ = cache.cached(f"info:{symbol}", cfg.CACHE_INFO, fetch)
    return value


# ── Wechselkurse ──────────────────────────────────────────────────────────────

def fx(from_ccy: Optional[str], to_ccy: Optional[str]) -> Optional[float]:
    """1 Einheit from_ccy in to_ccy (Yahoo-Devisenkurs, täglich)."""
    if not from_ccy or not to_ccy:
        return None
    if from_ccy.upper() == to_ccy.upper():
        return 1.0

    def fetch():
        h = yf.Ticker(f"{from_ccy.upper()}{to_ccy.upper()}=X").history(period="5d")
        if h.empty:
            return None
        return {"rate": float(h["Close"].dropna().iloc[-1]), "date": h.index[-1].date().isoformat()}

    value, _, _ = cache.cached(f"fx:{from_ccy.upper()}{to_ccy.upper()}", cfg.CACHE_FX, fetch)
    return value["rate"] if value else None


def market_cap_in(symbol_info: dict, currency: Optional[str]) -> Optional[float]:
    mc = symbol_info.get("market_cap")
    if mc is None:
        return None
    rate = fx(symbol_info.get("market_cap_currency"), currency)
    return mc * rate if rate else None


# ── Region und Marktindex ─────────────────────────────────────────────────────

def region_of(country: Optional[str]) -> str:
    return cfg.COUNTRY_TO_REGION.get(country or "", "other")


def market_index_for(country: Optional[str]) -> str:
    r = region_of(country)
    if r == "us":
        return cfg.MARKET_INDEX["us"]
    if r == "ch":
        return cfg.MARKET_INDEX["ch"]
    if r in cfg.EUROPE_REGIONS:
        return cfg.MARKET_INDEX["europe"]
    return cfg.MARKET_INDEX["other"]


# ── Kursstatistiken ───────────────────────────────────────────────────────────

def _download(symbols: List[str]) -> pd.DataFrame:
    """Dividendenbereinigte Schlusskurse, 5 Jahre täglich, eine Spalte pro Ticker."""
    df = yf.download(symbols, period="5y", interval="1d", auto_adjust=True, progress=False, threads=True, group_by="column")
    if df is None or df.empty:
        return pd.DataFrame()
    close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": symbols[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def _stats_from_series(px: pd.Series, mkt: Optional[pd.Series]) -> dict:
    px = px.dropna()
    out = {"mom_12_1": None, "mom_6": None, "volatility": None, "beta": None,
           "last_price_date": px.index[-1].date().isoformat() if len(px) else None, "observations": int(len(px))}
    if len(px) >= 253:
        # [AMP] MOM2–12: Rendite von t−12 Monaten bis t−1 Monat (≈ 21 Handelstage)
        out["mom_12_1"] = float(px.iloc[-22] / px.iloc[-253] - 1)
    if len(px) >= 127:
        out["mom_6"] = float(px.iloc[-1] / px.iloc[-127] - 1)
    logret = np.log(px).diff().dropna()
    if len(logret) >= 120:
        out["volatility"] = float(logret.iloc[-252:].std() * math.sqrt(252))
    if mkt is not None:
        joined = pd.concat([np.log(px), np.log(mkt.dropna())], axis=1, join="inner").dropna()
        joined.columns = ["s", "m"]
        if len(joined) >= 750:  # Frazzini/Pedersen: mind. ~3 Jahre für die Korrelation
            r1 = joined.diff().dropna()
            sd_s, sd_m = r1["s"].iloc[-252:].std(), r1["m"].iloc[-252:].std()
            r3 = (joined - joined.shift(3)).dropna().iloc[-1260:]  # überlappende 3-Tages-Renditen, 5 J.
            rho = r3["s"].corr(r3["m"])
            if sd_m and not math.isnan(rho):
                out["beta"] = float(rho * sd_s / sd_m)
    return out


def price_stats(symbols: List[str], index_symbol: str) -> Dict[str, dict]:
    """Momentum, Volatilität und Beta für mehrere Ticker (ein gemeinsamer Download)."""
    result: Dict[str, dict] = {}
    missing = []
    for s in symbols:
        v, age = cache.get(f"pstats:{s}:{index_symbol}")
        if v is not None and age < cfg.CACHE_MARKET_STATS:
            result[s] = v
        else:
            missing.append(s)
    if missing:
        try:
            close = _download(list(dict.fromkeys(missing + [index_symbol])))
        except Exception as e:
            log.warning("Kursdownload fehlgeschlagen: %s", e)
            close = pd.DataFrame()
        mkt = close[index_symbol] if index_symbol in close else None
        now = datetime.now(timezone.utc).isoformat()
        for s in missing:
            if s in close and close[s].notna().sum() > 0:
                st = _stats_from_series(close[s], mkt)
                st.update({"index": index_symbol, "fetched_at": now})
                cache.put(f"pstats:{s}:{index_symbol}", st)
                result[s] = st
            else:
                result[s] = {"error": "Kein Kursverlauf von Yahoo", "index": index_symbol}
    return result
