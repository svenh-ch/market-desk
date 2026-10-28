"""
SEC EDGAR – offizielle US-Berichte (gratis, ohne Key).

- company_tickers.json: Ticker → CIK (Firmennummer)
- data.sec.gov/submissions: Liste der eingereichten Berichte (10-K, 20-F …)
- data.sec.gov/api/xbrl/companyfacts: alle gemeldeten Bilanz-/GuV-Zahlen
- efts.sec.gov: Volltextsuche in Berichten

Die SEC verlangt einen User-Agent mit Kontaktadresse und höchstens 10 Anfragen
pro Sekunde. Wir bleiben bei SEC_MAX_REQUESTS_PER_SECOND.
"""
import logging
import re
import threading
import time
from typing import Dict, List, Optional

import requests

from app import scoring_config as cfg
from app.services import cache

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers.update({"User-Agent": cfg.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"})
_rate_lock = threading.Lock()
_last_request = [0.0]


def _get(url: str, **kw) -> requests.Response:
    """GET mit Ratenbegrenzung und einem Wiederholversuch bei 429/5xx."""
    for attempt in range(3):
        with _rate_lock:
            wait = 1.0 / cfg.SEC_MAX_REQUESTS_PER_SECOND - (time.time() - _last_request[0])
            if wait > 0:
                time.sleep(wait)
            _last_request[0] = time.time()
        r = _session.get(url, timeout=30, **kw)
        if r.status_code in (429, 500, 502, 503) and attempt < 2:
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError("SEC nicht erreichbar")


# ── Ticker → CIK ──────────────────────────────────────────────────────────────

def ticker_map() -> Dict[str, dict]:
    """{TICKER: {cik, title}} – wöchentlich aktualisiert."""
    def fetch():
        data = _get("https://www.sec.gov/files/company_tickers.json").json()
        return {v["ticker"].upper(): {"cik": int(v["cik_str"]), "title": v["title"]} for v in data.values()}
    value, _, _ = cache.cached("sec:tickers", 7 * 86400, fetch)
    return value


def cik_for(symbol: str) -> Optional[int]:
    """Nur für US-Ticker ohne Börsenzusatz (AAPL, BRK-B → BRK-B)."""
    sym = symbol.upper()
    if "." in sym or sym.startswith("^") or "=" in sym:
        # Ausländische Listings (NOVN.SW) haben keine SEC-Berichte unter diesem Ticker
        return None
    m = ticker_map()
    hit = m.get(sym) or m.get(sym.replace("-", "."))
    return hit["cik"] if hit else None


# ── Berichte ──────────────────────────────────────────────────────────────────

def submissions(cik: int) -> dict:
    def fetch():
        d = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
        r = d["filings"]["recent"]
        filings = [
            {"form": r["form"][i], "filed": r["filingDate"][i], "accession": r["accessionNumber"][i],
             "primary": r["primaryDocument"][i], "report_date": r["reportDate"][i]}
            for i in range(len(r["form"]))
        ]
        return {"name": d.get("name"), "sic": d.get("sic"), "sic_description": d.get("sicDescription"),
                "filings": filings}
    value, _, _ = cache.cached(f"sec:subm:{cik}", cfg.CACHE_FILINGS_INDEX, fetch)
    return value


ANNUAL_FORMS = ("10-K", "20-F", "40-F")


def latest_annual(cik: int) -> Optional[dict]:
    for f in submissions(cik)["filings"]:
        if f["form"] in ANNUAL_FORMS:
            return f
    return None


def document_url(cik: int, filing: dict) -> str:
    acc = filing["accession"].replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{filing['primary']}"


def fetch_document_text(cik: int, filing: dict) -> str:
    """Hauptdokument eines Berichts als reiner Text (HTML wird entfernt)."""
    from bs4 import BeautifulSoup
    html = _get(document_url(cik, filing)).text
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    # XBRL-Kopfbereich (ix:header) enthält keine Fliesstexte
    for t in soup.find_all(re.compile(r"^ix:header$")):
        t.decompose()
    text = soup.get_text(" ")
    return re.sub(r"\s+", " ", text)


def companyfacts(cik: int) -> dict:
    """
    Rohdaten der XBRL-Fakten (mehrere MB). Werden bewusst NICHT roh gespeichert –
    fundamentals.py speichert nur die aufbereiteten Jahreswerte und lädt neu,
    sobald latest_annual() einen neuen Bericht meldet.
    """
    return _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json").json()


# ── Volltextsuche ─────────────────────────────────────────────────────────────

def full_text_search(query: str, forms: str = "10-K,20-F", start: str = "2024-01-01", end: Optional[str] = None) -> List[dict]:
    """Treffer der EDGAR-Volltextsuche: [{cik, name, form, filed, accession, file}]"""
    from datetime import date
    end = end or date.today().isoformat()
    r = _get("https://efts.sec.gov/LATEST/search-index",
             params={"q": query, "forms": forms, "dateRange": "custom", "startdt": start, "enddt": end})
    out = []
    for h in r.json().get("hits", {}).get("hits", []):
        s = h.get("_source", {})
        acc, _, file = h.get("_id", "").partition(":")
        ciks = s.get("ciks") or []
        out.append({
            "cik": int(ciks[0]) if ciks else None,
            "name": (s.get("display_names") or [""])[0],
            "form": s.get("form") or s.get("root_form"),
            "filed": s.get("file_date"),
            "accession": acc, "file": file,
        })
    return out
