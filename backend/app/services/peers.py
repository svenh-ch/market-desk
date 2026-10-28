"""
Vergleichsgruppen: Firmen derselben Branche, möglichst aus derselben Region.

Quelle: Yahoo-Finance-Screener (Branche + Region + Börsenwert). Er ersetzt die
vom Nutzer genannten Indexlisten (SMI/SPI, STOXX 600, S&P 500), deren
Zusammensetzung nicht frei abrufbar ist; die Untergrenze von 1 Mrd. USD
Börsenwert bildet ungefähr das Universum solcher Indizes nach.

Stufen (die erste mit mind. MIN_PEERS Firmen gewinnt):
  1. Branche · Heimatland
  2. Branche · Europa (bzw. USA)
  3. Branche · Europa + USA
  4. Sektor · Heimatregion
  5. sonst: zu wenige Vergleichsfirmen → Damodaran-Branchenwerte als Rückfallebene
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

import yfinance as yf
from yfinance import EquityQuery as Q
from yfinance.const import EQUITY_SCREENER_EQ_MAP

from app import scoring_config as cfg
from app.services import cache
from app.services.fundamentals import normalize_name
from app.services.market_stats import fx, info, region_of

log = logging.getLogger(__name__)

REGION_LABELS = {"ch": "Schweiz", "us": "USA", "de": "Deutschland", "fr": "Frankreich", "gb": "Grossbritannien",
                 "nl": "Niederlande", "it": "Italien", "es": "Spanien", "se": "Schweden", "dk": "Dänemark"}


def _screener_values(field: str) -> set:
    v = EQUITY_SCREENER_EQ_MAP.get(field, {})
    if isinstance(v, dict):
        return {x for vals in v.values() for x in vals}
    return set(v)


def _screener_industry(industry: Optional[str]) -> Optional[str]:
    """'Banks - Diversified' (Firmenangabe) → 'Banks—Diversified' (Screener-Schreibweise)."""
    if not industry:
        return None
    valid = _screener_values("industry")
    for cand in (industry, industry.replace(" - ", "—"), industry.replace(" - ", " — ")):
        if cand in valid:
            return cand
    return None


def _screen(field: str, value: str, regions: List[str]) -> List[dict]:
    q = Q("and", [Q("eq", [field, value]), Q("is-in", ["region", *regions])])
    res = yf.screen(q, size=250, sortField="intradaymarketcap", sortAsc=False)
    return res.get("quotes", []) if isinstance(res, dict) else []


def _clean(quotes: List[dict], exclude_symbol: str, exclude_name: str, regions: List[str]) -> List[dict]:
    """
    Firma selbst, Zweitlistungen an fremden Börsen, OTC-Kopien und kleine Firmen
    entfernen; danach nur Firmen mit Sitz in einer der Regionen behalten.
    """
    allowed_exchanges = set().union(*(cfg.PRIMARY_EXCHANGES.get(r, set()) for r in regions))
    candidates = []
    for q in quotes:
        sym = q.get("symbol")
        if not sym or sym == exclude_symbol or q.get("exchange") not in allowed_exchanges:
            continue
        if q.get("quoteType") not in (None, "EQUITY"):
            continue
        cur, mc = q.get("currency"), q.get("marketCap")
        if mc is None or not cur:
            continue
        if cur in ("GBp", "GBX"):
            cur, mc = "GBP", mc / 100  # Screener liefert London-Werte in Pence
        rate = fx(cur, "USD")
        if not rate or mc * rate < cfg.MIN_MARKET_CAP_USD:
            continue
        name = q.get("longName") or q.get("shortName") or sym
        candidates.append({"symbol": sym, "name": name, "exchange": q.get("exchange"),
                           "currency": q.get("currency"), "market_cap_usd": mc * rate})
    candidates.sort(key=lambda x: x["market_cap_usd"], reverse=True)

    unique = candidates
    seen = {normalize_name(exclude_name)} if exclude_name else set()

    # Sitzland prüfen (Firmenangaben), parallel und nur so viele wie nötig
    out = []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i in range(0, len(unique), 12):
            batch = unique[i:i + 12]
            for c, inf in zip(batch, pool.map(lambda c: _safe_info(c["symbol"]), batch)):
                home = region_of((inf or {}).get("country"))
                # nur Firmen mit Sitz in der Region UND nur ihre Listung an der Heimatbörse
                if home in regions and c["exchange"] in cfg.PRIMARY_EXCHANGES.get(home, set()):
                    n = normalize_name(c["name"])
                    if n in seen:
                        continue
                    seen.add(n)
                    c["country"] = inf.get("country")
                    out.append(c)
            if len(out) >= cfg.MAX_PEERS:
                break
    return out[:cfg.MAX_PEERS]


def _safe_info(sym: str) -> Optional[dict]:
    try:
        return info(sym)
    except Exception:
        return None


def peer_group(symbol: str) -> dict:
    """Vergleichsgruppe inkl. Beschreibung, welche Stufe verwendet wurde (wöchentlich gespeichert)."""
    def fetch():
        i = info(symbol)
        industry, sector, country = i.get("industry"), i.get("sector"), i.get("country")
        region = region_of(country)
        home = [region] if region != "other" else ["us"]
        wide = cfg.EUROPE_REGIONS if region in cfg.EUROPE_REGIONS else ["us"]
        both = list(dict.fromkeys(wide + ["us"] + cfg.EUROPE_REGIONS))
        home_label = REGION_LABELS.get(home[0], home[0].upper())
        wide_label = "Europa" if wide is cfg.EUROPE_REGIONS else "USA"
        ind = _screener_industry(industry)
        sec_ok = sector in _screener_values("sector")

        levels = []
        if ind:
            if home != wide:
                levels.append(("industry", ind, home, f"Branche „{industry}“ · {home_label}"))
            levels += [("industry", ind, wide, f"Branche „{industry}“ · {wide_label}"),
                       ("industry", ind, both, f"Branche „{industry}“ · Europa + USA")]
        if sec_ok:
            levels.append(("sector", sector, wide, f"Sektor „{sector}“ · {wide_label}"))

        tried = []
        best: List[dict] = []
        for field, value, regions, label in levels:
            try:
                peers = _clean(_screen(field, value, regions), symbol, i.get("name") or "", regions)
            except Exception as e:
                log.warning("Screener %s/%s fehlgeschlagen: %s", value, regions, e)
                peers = []
            tried.append({"level": label, "count": len(peers)})
            if len(peers) > len(best):
                best = peers
            if len(peers) >= cfg.MIN_PEERS:
                return {"symbol": symbol, "level": label, "peers": peers[:cfg.MAX_PEERS], "tried": tried,
                        "enough": True, "industry": industry, "sector": sector, "country": country,
                        "source": "Yahoo-Finance-Screener", "fetched_at": datetime.now(timezone.utc).isoformat()}
        return {"symbol": symbol, "level": tried[-1]["level"] if tried else "keine", "peers": best[:cfg.MAX_PEERS],
                "tried": tried, "enough": False, "industry": industry, "sector": sector, "country": country,
                "source": "Yahoo-Finance-Screener", "fetched_at": datetime.now(timezone.utc).isoformat()}

    value, _, _ = cache.cached(f"peers:{symbol}", cfg.CACHE_PEERS, fetch)
    return value
