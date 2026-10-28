"""
Referenzdaten:
  - Damodaran-Branchenwerte (global): Rückfallebene, wenn eine Vergleichsgruppe
    zu klein ist, und Anzeige "Branchenwert" neben dem Firmenwert.
  - Risikofreie Zinsen: FRED (3-Monats-T-Bill, USD) und SNB (SARON, CHF).
"""
import csv
import difflib
import io
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from app import scoring_config as cfg
from app.services import cache

log = logging.getLogger(__name__)

DAMODARAN_BASE = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/"
# Datei → (Spalte im Kopf, Schlüssel bei uns). Jeweils die erste passende Spalte.
DAMODARAN_FILES = {
    "peGlobal.xls": [("Current PE", "pe")],
    "pbvGlobal.xls": [("PBV", "pbv"), ("ROE", "roe")],
    "vebitdaGlobal.xls": [("EV/EBITDA", "ev_ebitda")],
    "marginGlobal.xls": [("Gross Margin", "gross_margin"), ("Net Margin", "net_margin")],
}


def _parse_xls(content: bytes) -> dict:
    import xlrd
    book = xlrd.open_workbook(file_contents=content)
    sh = book.sheet_by_name("Industry Averages")
    raw = sh.cell_value(0, 1) if sh.ncols > 1 else None
    try:
        updated = xlrd.xldate.xldate_as_datetime(raw, book.datemode).date().isoformat() if isinstance(raw, float) else str(raw)
    except Exception:
        updated = str(raw)
    header_row = next(r for r in range(sh.nrows) if str(sh.cell_value(r, 0)).startswith("Industry"))
    header = [str(c.value).strip() for c in sh.row(header_row)]
    rows = {}
    for r in range(header_row + 1, sh.nrows):
        name = str(sh.cell_value(r, 0)).strip()
        if not name or name.lower().startswith("total"):
            continue
        rows[name] = {header[c]: sh.cell_value(r, c) for c in range(1, len(header)) if header[c]}
        rows[name]["_n"] = sh.cell_value(r, 1)
    return {"updated": updated, "header": header, "rows": rows}


def damodaran_tables() -> dict:
    def fetch():
        out = {"fetched_at": datetime.now(timezone.utc).isoformat(), "industries": {}, "updated": None}
        for fname, cols in DAMODARAN_FILES.items():
            r = requests.get(DAMODARAN_BASE + fname, timeout=60)
            r.raise_for_status()
            t = _parse_xls(r.content)
            out["updated"] = out["updated"] or t["updated"]
            for ind, vals in t["rows"].items():
                d = out["industries"].setdefault(ind, {"firms": vals.get("_n")})
                for col, key in cols:
                    v = vals.get(col)
                    if isinstance(v, (int, float)) and key not in d:
                        d[key] = float(v)
        return out
    value, _, _ = cache.cached("damodaran:global", cfg.CACHE_DAMODARAN, fetch)
    return value


def damodaran_for(industry: Optional[str]) -> Optional[dict]:
    """Branchenwerte über die feste Zuordnungstabelle (damodaran_mapping.py) – keine Schätzung."""
    from app.damodaran_mapping import YAHOO_TO_DAMODARAN
    target = YAHOO_TO_DAMODARAN.get((industry or "").replace("—", " - "))
    if not target:
        return None
    try:
        t = damodaran_tables()
    except Exception as e:
        log.warning("Damodaran nicht verfügbar: %s", e)
        return None
    vals = t["industries"].get(target)
    if not vals:
        return None
    return {"industry": target, "matched_from": industry, "values": vals, "updated": t.get("updated"),
            "source": "Damodaran Online, globale Branchen-Durchschnitte",
            "note": "Zuordnung der Branche über feste Tabelle (damodaran_mapping.py)."}


# ── Risikofreie Zinsen ────────────────────────────────────────────────────────

def risk_free_rates() -> dict:
    def fetch():
        out = {"fetched_at": datetime.now(timezone.utc).isoformat()}
        try:
            text = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO", timeout=30).text
            rows = [r for r in csv.reader(io.StringIO(text)) if len(r) == 2 and r[1] not in ("", ".")][1:]
            d, v = rows[-1]
            out["usd"] = {"rate": float(v), "date": d, "series": "3-Monats-T-Bill (DGS3MO)", "source": "FRED, Federal Reserve Bank of St. Louis"}
        except Exception as e:
            out["usd"] = {"error": f"FRED nicht erreichbar ({type(e).__name__})"}
        try:
            text = requests.get("https://data.snb.ch/api/cube/zimoma/data/csv/en", timeout=30).text
            rows = [r for r in csv.reader(io.StringIO(text), delimiter=";") if len(r) == 3 and r[1] == "SARON" and r[2]]
            d, _, v = rows[-1]
            out["chf"] = {"rate": float(v), "date": d, "series": "SARON (Monatsmittel)", "source": "SNB-Datenportal"}
        except Exception as e:
            out["chf"] = {"error": f"SNB nicht erreichbar ({type(e).__name__})"}
        return out
    value, age, stale = cache.cached("rates:riskfree", cfg.CACHE_RATES, fetch)
    return {**value, "cache_age_seconds": int(age), "stale": stale}
