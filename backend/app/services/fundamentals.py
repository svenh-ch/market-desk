"""
Jahreszahlen (Bilanz, Erfolgsrechnung, Cashflow) in einem einheitlichen Format.

Quellen in dieser Reihenfolge (offizieller Bericht vor yfinance):
  1. SEC EDGAR companyfacts (US-GAAP oder IFRS; 10-K, 20-F, 40-F)
  2. ESEF-Jahresbericht über filings.xbrl.org (EU-Firmen, wo vorhanden)
  3. Yahoo Finance (yfinance) für alle übrigen Firmen

Ergebnis (gekürzt):
  {"symbol", "source", "currency", "fetched_at",
   "years": [{"period_end", "filed", "form", "values": {posten: zahl}}, …]  # neuestes zuerst
  }
"""
import logging
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import yfinance as yf

from app import scoring_config as cfg
from app.services import cache, sec

log = logging.getLogger(__name__)

ITEMS = ["revenue", "cogs", "gross_profit", "net_income", "ebit", "d_and_a", "total_assets",
         "current_assets", "current_liabilities", "total_liabilities", "equity", "retained_earnings",
         "cfo", "capex", "long_term_debt", "short_term_debt", "total_debt", "cash", "shares"]

# Zeitraum-Posten (Erfolgsrechnung/Cashflow) vs. Stichtags-Posten (Bilanz)
FLOW_ITEMS = {"revenue", "cogs", "gross_profit", "net_income", "ebit", "d_and_a", "cfo", "capex", "shares"}

US_GAAP = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
             "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"],
    "gross_profit": ["GrossProfit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "ebit": ["OperatingIncomeLoss"],
    "d_and_a": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "total_liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "short_term_debt": ["ShortTermBorrowings", "CommercialPaper", "DebtCurrent", "LongTermDebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "shares": ["WeightedAverageNumberOfSharesOutstandingBasic"],
}

IFRS = {
    "revenue": ["Revenue", "RevenueFromContractsWithCustomers"],
    "cogs": ["CostOfSales"],
    "gross_profit": ["GrossProfit"],
    "net_income": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "ebit": ["ProfitLossFromOperatingActivities"],
    "d_and_a": ["DepreciationAndAmortisationExpense", "AdjustmentsForDepreciationAndAmortisationExpense",
                "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"],
    "total_assets": ["Assets"],
    "current_assets": ["CurrentAssets"],
    "current_liabilities": ["CurrentLiabilities"],
    "total_liabilities": ["Liabilities"],
    "equity": ["EquityAttributableToOwnersOfParent", "Equity"],
    "retained_earnings": ["RetainedEarnings"],
    "cfo": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipment"],
    "long_term_debt": ["NoncurrentBorrowings", "LongtermBorrowings"],
    "short_term_debt": ["CurrentBorrowings", "ShorttermBorrowings", "CurrentPortionOfLongtermBorrowings"],
    "total_debt": ["Borrowings"],
    "cash": ["CashAndCashEquivalents"],
    "shares": ["WeightedAverageShares"],
}

YF_ROWS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "cogs": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit": ["Gross Profit"],
    "net_income": ["Net Income Common Stockholders", "Net Income"],
    "ebit": ["Operating Income", "EBIT"],
    "d_and_a": ["Reconciled Depreciation", "Depreciation And Amortization"],
    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "equity": ["Stockholders Equity", "Common Stock Equity"],
    "retained_earnings": ["Retained Earnings"],
    "cfo": ["Operating Cash Flow"],
    "capex": ["Capital Expenditure"],
    "long_term_debt": ["Long Term Debt"],
    "short_term_debt": ["Current Debt"],
    "total_debt": ["Total Debt"],
    "cash": ["Cash And Cash Equivalents"],
    "shares": ["Diluted Average Shares", "Basic Average Shares", "Ordinary Shares Number"],
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

_LEGAL = r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|ag|sa|se|nv|n v|s a|spa|s p a|ab|asa|oyj|a s|as|holding|holdings|group|the|de|cl a|class a)\b"


def normalize_name(name: str) -> str:
    """Firmenname vereinfachen, damit 'Nestlé S.A.' und 'NESTLE SA' gleich aussehen."""
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = re.sub(_LEGAL, " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _derive(v: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Fehlende Posten aus vorhandenen ableiten (nur eindeutige Rechnungen). Abgeleitetes steht in v['_derived']."""
    derived = []
    if v.get("gross_profit") is None and v.get("revenue") is not None and v.get("cogs") is not None:
        v["gross_profit"] = v["revenue"] - v["cogs"]
        derived.append("gross_profit")
    if v.get("revenue") is None and v.get("gross_profit") is not None and v.get("cogs") is not None:
        v["revenue"] = v["gross_profit"] + v["cogs"]  # z. B. Novartis: Umsatz nur unter firmeneigenem Tag
        derived.append("revenue")
    if v.get("total_debt") is None and (v.get("long_term_debt") is not None or v.get("short_term_debt") is not None):
        v["total_debt"] = (v.get("long_term_debt") or 0) + (v.get("short_term_debt") or 0)
        derived.append("total_debt")
    if v.get("total_debt") is None and (v.get("long_term_debt") is not None or v.get("short_term_debt") is not None):
        v["total_debt"] = (v.get("long_term_debt") or 0) + (v.get("short_term_debt") or 0)
    if v.get("capex") is not None:
        v["capex"] = abs(v["capex"])  # Investitionen immer als positive Zahl
    v["ebitda"] = v["ebit"] + v["d_and_a"] if v.get("ebit") is not None and v.get("d_and_a") is not None else None
    v["_derived"] = derived
    return v


def _num(x) -> Optional[float]:
    try:
        f = float(x)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


# ── SEC companyfacts ──────────────────────────────────────────────────────────

def _sec_years(facts: dict, point_in_time: bool = False):
    """
    Jahreswerte je Geschäftsjahresende aus den SEC-Fakten.
    Pro Posten gilt die Reihenfolge der Tag-Liste: ein späterer Tag füllt nur Lücken
    (Firmen wechseln ihre Kennzeichnung über die Jahre).
    point_in_time=True nimmt pro Wert die ERSTE Meldung (für Rückblick-Tests),
    sonst die neueste (inkl. Korrekturen).
    """
    taxonomy, mapping = ("us-gaap", US_GAAP) if "us-gaap" in facts["facts"] else ("ifrs-full", IFRS)
    tags = facts["facts"].get(taxonomy, {})

    # Berichtswährung = häufigste Währungseinheit bei den Total Assets
    currency = None
    for name in mapping["total_assets"]:
        units = tags.get(name, {}).get("units", {})
        cur = [u for u in units if re.fullmatch(r"[A-Z]{3}", u)]
        if cur:
            currency = max(cur, key=lambda u: len(units[u]))
            break

    by_end: Dict[str, dict] = {}
    for item, names in mapping.items():
        unit = "shares" if item == "shares" else currency
        for rank, name in enumerate(names):
            for f in tags.get(name, {}).get("units", {}).get(unit, []):
                form = (f.get("form") or "").replace("/A", "")
                if form not in sec.ANNUAL_FORMS:
                    continue
                if item in FLOW_ITEMS:
                    if not f.get("start"):
                        continue
                    days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
                    if not 350 <= days <= 380:
                        continue
                y = by_end.setdefault(f["end"], {"period_end": f["end"], "form": form, "values": {}, "meta": {}})
                m = y["meta"].get(item)
                better_rank = m is None or rank < m["rank"]
                same_rank_newer = m is not None and rank == m["rank"] and (
                    f["filed"] < m["filed"] if point_in_time else f["filed"] > m["filed"])
                if better_rank or same_rank_newer:
                    y["values"][item] = _num(f["val"])
                    y["meta"][item] = {"rank": rank, "filed": f["filed"], "form": form}

    years = []
    for y in by_end.values():
        if y["values"].get("total_assets") is None:
            continue
        # Ein Geschäftsjahr gilt ab der ersten Meldung seiner Kernzahlen als veröffentlicht
        core = [y["meta"][k]["filed"] for k in ("total_assets", "revenue", "net_income") if k in y["meta"]]
        y["filed"] = min(core) if point_in_time else max(core)
        y["form"] = y["meta"]["total_assets"]["form"]
        y.pop("meta")
        y["values"] = _derive({k: y["values"].get(k) for k in ITEMS})
        years.append(y)
    years.sort(key=lambda y: y["period_end"], reverse=True)
    # Nur echte Geschäftsjahresenden (mit Umsatz oder Gewinn), max. 6 Jahre
    years = [y for y in years if y["values"].get("revenue") is not None or y["values"].get("net_income") is not None]
    return (years if point_in_time else years[:6]), currency


def sec_cik_for(symbol: str, company_name: Optional[str]) -> Optional[int]:
    """CIK über den Ticker (US) oder – für ausländische Listings – über den exakten Firmennamen."""
    cik = sec.cik_for(symbol)
    if cik or not company_name:
        return cik
    target = normalize_name(company_name)
    if not target:
        return None
    for v in sec.ticker_map().values():
        if normalize_name(v["title"]) == target:
            return v["cik"]
    return None


def from_sec(cik: int, symbol: str) -> Optional[dict]:
    latest = sec.latest_annual(cik)
    key = f"fund:sec:{cik}"
    value, age = cache.get(key)
    if value is not None and age < cfg.CACHE_FUNDAMENTALS and value.get("latest_accession") == (latest or {}).get("accession"):
        return value
    facts = sec.companyfacts(cik)
    years, currency = _sec_years(facts)
    if not years:
        return None
    result = {
        "symbol": symbol, "cik": cik, "source": f"SEC {years[0]['form']}", "currency": currency,
        "entity": facts.get("entityName"), "latest_accession": (latest or {}).get("accession"),
        "fetched_at": datetime.now(timezone.utc).isoformat(), "years": years,
    }
    cache.put(key, result)
    return result


# ── ESEF (filings.xbrl.org) ───────────────────────────────────────────────────

ESEF_BASE = "https://filings.xbrl.org"


def _esef_entity(company_name: str) -> Optional[dict]:
    """Entität nur bei exakter Namensübereinstimmung (nach Vereinfachung) – keine Fuzzy-Treffer."""
    import json
    import urllib.parse
    import requests
    target = normalize_name(company_name)
    words = target.split()
    if not words:
        return None
    flt = urllib.parse.quote(json.dumps([{"name": "name", "op": "ilike", "val": f"%{words[0]}%"}]))
    data = requests.get(f"{ESEF_BASE}/api/entities?filter={flt}&page%5Bsize%5D=100", timeout=30).json().get("data", [])
    for e in data:
        if normalize_name(e["attributes"]["name"]) == target:
            return e
    return None


def from_esef(company_name: str, symbol: str) -> Optional[dict]:
    import requests
    key = f"fund:esef:{normalize_name(company_name)}"

    def fetch():
        e = _esef_entity(company_name)
        if not e:
            return {"none": True}
        rel = e["relationships"]["filings"]["links"]["related"]
        filings = requests.get(f"{ESEF_BASE}{rel}?sort=-period_end&page%5Bsize%5D=10", timeout=30).json().get("data", [])
        # Nur Jahresberichte (Stichtag Jahresende eines Geschäftsjahres, i.d.R. 12-31 oder Jahresende des Konzerns)
        for f in filings:
            a = f["attributes"]
            j = requests.get(ESEF_BASE + a["json_url"], timeout=120).json()
            years, currency = _esef_years(j["facts"])
            if years:
                return {"symbol": symbol, "source": "ESEF-Jahresbericht", "currency": currency,
                        "entity": e["attributes"]["name"], "lei": e["attributes"]["identifier"],
                        "report_url": ESEF_BASE + a.get("report_url", ""),
                        "fetched_at": datetime.now(timezone.utc).isoformat(), "years": years}
        return {"none": True}

    value, _, _ = cache.cached(key, cfg.CACHE_FUNDAMENTALS, fetch)
    return None if value.get("none") else value


def _esef_years(facts: dict):
    by_end: Dict[str, dict] = {}
    currency = None
    plain = {"concept", "entity", "period", "unit", "language"}
    values: Dict[str, Dict[str, Dict[str, float]]] = {}  # end → concept → value
    for v in facts.values():
        d = v.get("dimensions", {})
        if not set(d) <= plain or not d.get("concept", "").startswith("ifrs-full:"):
            continue
        unit = (d.get("unit") or "").replace("iso4217:", "")
        period = d.get("period", "")
        if "/" in period:
            s, e = period.split("/")
            sd, ed = datetime.fromisoformat(s[:19]), datetime.fromisoformat(e[:19])
            if not 350 <= (ed - sd).days <= 380:
                continue
        else:
            ed = datetime.fromisoformat(period[:19])
        end = (ed - timedelta(days=1)).date().isoformat()  # ESEF: Stichtag = Folgetag 00:00
        values.setdefault(end, {})[d["concept"].split(":")[1] + "|" + unit] = _num(v.get("value"))
        if re.fullmatch(r"[A-Z]{3}", unit):
            currency = currency or unit
    for end, cv in values.items():
        row = {}
        for item, names in IFRS.items():
            for n in names:
                unit = "shares" if item == "shares" else currency
                val = cv.get(f"{n}|{unit}")
                if val is not None:
                    row[item] = val
                    break
        if row.get("total_assets") is not None:
            by_end[end] = {"period_end": end, "filed": None, "form": "ESEF", "values": _derive({k: row.get(k) for k in ITEMS})}
    years = sorted(by_end.values(), key=lambda y: y["period_end"], reverse=True)[:6]
    return years, currency


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def from_yfinance(symbol: str) -> Optional[dict]:
    key = f"fund:yf:{symbol}"

    def fetch():
        t = yf.Ticker(symbol)
        frames = [t.income_stmt, t.balance_sheet, t.cashflow]
        if all(f is None or f.empty for f in frames):
            return {"none": True}
        years: Dict[str, dict] = {}
        for item, rows in YF_ROWS.items():
            for frame in frames:
                if frame is None or frame.empty:
                    continue
                row = next((r for r in rows if r in frame.index), None)
                if row is None:
                    continue
                for col, val in frame.loc[row].items():
                    end = col.date().isoformat()
                    y = years.setdefault(end, {"period_end": end, "filed": None, "form": "Yahoo", "values": {}})
                    if y["values"].get(item) is None:
                        y["values"][item] = _num(val)
                break
        out = []
        for y in sorted(years.values(), key=lambda y: y["period_end"], reverse=True):
            y["values"] = _derive({k: y["values"].get(k) for k in ITEMS})
            if y["values"].get("total_assets") is not None:
                out.append(y)
        info = t.info or {}
        return {"symbol": symbol, "source": "Yahoo Finance", "currency": info.get("financialCurrency"),
                "fetched_at": datetime.now(timezone.utc).isoformat(), "years": out[:6]}

    value, _, _ = cache.cached(key, cfg.CACHE_FUNDAMENTALS, fetch)
    return None if value.get("none") else value


# ── Auswahl & Abgleich ────────────────────────────────────────────────────────

def _fill_gaps_from_yahoo(official: dict, symbol: str) -> dict:
    """
    Offizieller Bericht bleibt Basis; nur FEHLENDE Posten werden aus Yahoo ergänzt
    (gleiches Geschäftsjahr ±10 Tage, gleiche Währung) und in '_from_yahoo' vermerkt.
    Grund: manche Firmen (z. B. Novartis) melden Posten nur mit firmeneigenen Tags.
    """
    try:
        yfd = from_yfinance(symbol)
    except Exception:
        return official
    if not yfd or yfd.get("currency") != official.get("currency"):
        return official
    for y in official["years"]:
        match = next((m for m in yfd["years"] if abs((date.fromisoformat(m["period_end"]) - date.fromisoformat(y["period_end"])).days) <= 10), None)
        if not match:
            continue
        filled = []
        for item in ITEMS:
            if y["values"].get(item) is None and match["values"].get(item) is not None:
                y["values"][item] = match["values"][item]
                filled.append(item)
        if filled:
            derived = y["values"].get("_derived", [])
            y["values"] = _derive({k: y["values"].get(k) for k in ITEMS})
            y["values"]["_derived"] = sorted(set(derived + y["values"]["_derived"]))
            y["values"]["_from_yahoo"] = filled
    return official


def get_fundamentals(symbol: str, company_name: Optional[str], country: Optional[str], use_esef: bool = True) -> Optional[dict]:
    """Beste verfügbare Quelle in der Reihenfolge SEC → ESEF → Yahoo (Lücken aus Yahoo ergänzt)."""
    try:
        cik = sec_cik_for(symbol, company_name)
        if cik:
            f = from_sec(cik, symbol)
            if f:
                return _fill_gaps_from_yahoo(f, symbol)
    except Exception as e:
        log.warning("SEC für %s fehlgeschlagen: %s", symbol, e)
    if use_esef and company_name and cfg.COUNTRY_TO_REGION.get(country or "") in cfg.EUROPE_REGIONS and country != "Switzerland":
        try:
            f = from_esef(company_name, symbol)
            if f:
                return _fill_gaps_from_yahoo(f, symbol)
        except Exception as e:
            log.warning("ESEF für %s fehlgeschlagen: %s", symbol, e)
    try:
        return from_yfinance(symbol)
    except Exception as e:
        log.warning("Yahoo-Bilanz für %s fehlgeschlagen: %s", symbol, e)
        return None


CHECK_ITEMS = {"revenue": "Umsatz", "net_income": "Reingewinn", "total_assets": "Total Assets", "equity": "Eigenkapital"}


def cross_check(official: dict, symbol: str) -> List[dict]:
    """Vergleicht den offiziellen Bericht mit yfinance (gleiches Geschäftsjahr, gleiche Währung)."""
    if not official or official["source"] == "Yahoo Finance":
        return []
    yfd = from_yfinance(symbol)
    if not yfd or not yfd["years"] or yfd.get("currency") != official.get("currency"):
        return []
    off = official["years"][0]
    match = next((y for y in yfd["years"] if abs((date.fromisoformat(y["period_end"]) - date.fromisoformat(off["period_end"])).days) <= 10), None)
    if not match:
        return []
    out = []
    for item, label in CHECK_ITEMS.items():
        a, b = off["values"].get(item), match["values"].get(item)
        if a and b:
            dev = abs(a - b) / max(abs(a), abs(b))
            if dev > cfg.SOURCE_DEVIATION_WARN:
                out.append({"item": label, "official": a, "yahoo": b, "deviation_pct": round(dev * 100, 1)})
    return out
