"""
Eigener Score auf Basis wissenschaftlicher Literatur – NICHT validiert, keine Anlageempfehlung.

Ablauf für eine Aktie:
  1. Vergleichsgruppe bestimmen (peers.py)
  2. Für Aktie UND Vergleichsfirmen dieselben Kennzahlen berechnen (compute_metrics)
  3. Jede Kennzahl → Perzentil innerhalb der Gruppe (Richtung je Kennzahl)
  4. Säule = Mittel der Perzentile ihrer Kennzahlen; Gesamtscore = gewichtetes Mittel der Säulen
  5. Datenabdeckung < MIN_COVERAGE → kein Gesamtscore

Alle Gewichte/Schwellen: app/scoring_config.py. Erklärung: SCORE_METHODIK.md.
"""
import logging
import math
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from app import scoring_config as cfg
from app.services import cache
from app.services.fundamentals import cross_check, get_fundamentals
from app.services.market_stats import info, market_cap_in, market_index_for, price_stats
from app.services.peers import peer_group
from app.services.reference_data import damodaran_for

log = logging.getLogger(__name__)

DISCLAIMER = "Eigener Score auf Basis wissenschaftlicher Literatur. Nicht validiert, keine Anlageempfehlung."


# ── Hilfen ────────────────────────────────────────────────────────────────────

def _div(a, b) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    r = a / b
    return None if math.isnan(r) or math.isinf(r) else r


def color_for(percentile: Optional[float]) -> str:
    if percentile is None:
        return "grey"
    if percentile >= cfg.GREEN_FROM:
        return "green"
    if percentile < cfg.RED_BELOW:
        return "red"
    return "yellow"


def is_financial(industry: Optional[str]) -> bool:
    return any(k.lower() in (industry or "").lower() for k in cfg.FINANCIAL_INDUSTRY_KEYWORDS)


def is_manufacturing(sector: Optional[str], industry: Optional[str]) -> bool:
    if any(k.lower() in (industry or "").lower() for k in cfg.NON_MANUFACTURING_INDUSTRY_KEYWORDS):
        return False
    return sector in cfg.MANUFACTURING_SECTORS


# ── Kennzahlen einer Firma ────────────────────────────────────────────────────

def piotroski(y0: dict, y1: dict, y2: Optional[dict]) -> Optional[dict]:
    """
    Piotroski F-Score nach [PIO] (Selected Paper 84), 9 binäre Signale:
    ROA, CFO (je / Total Assets am Jahresanfang), ΔROA, ACCRUAL (CFO > ROA),
    ΔLEVER (lfr. Schulden inkl. kurzfristigem Anteil / Ø Total Assets), ΔLIQUID
    (Current Ratio), EQ_OFFER (keine neuen Aktien), ΔMARGIN (Bruttomarge),
    ΔTURN (Umsatz / Total Assets am Jahresanfang). Braucht 3 Geschäftsjahre.
    """
    a, b = y0["values"], y1["values"]
    c = y2["values"] if y2 else {}
    def ok(cond):
        return None if cond is None else bool(cond)
    def avg(x, y):
        return (x + y) / 2 if None not in (x, y) else None
    ltd = lambda v: v.get("long_term_debt") if v.get("long_term_debt") is not None else v.get("total_debt")
    roa0, roa1 = _div(a.get("net_income"), b.get("total_assets")), _div(b.get("net_income"), c.get("total_assets"))
    cfo0 = _div(a.get("cfo"), b.get("total_assets"))
    lev0 = _div(ltd(a), avg(a.get("total_assets"), b.get("total_assets")))
    lev1 = _div(ltd(b), avg(b.get("total_assets"), c.get("total_assets")))
    cr0, cr1 = _div(a.get("current_assets"), a.get("current_liabilities")), _div(b.get("current_assets"), b.get("current_liabilities"))
    gm0, gm1 = _div(a.get("gross_profit"), a.get("revenue")), _div(b.get("gross_profit"), b.get("revenue"))
    at0, at1 = _div(a.get("revenue"), b.get("total_assets")), _div(b.get("revenue"), c.get("total_assets"))
    signals = {
        "ROA positiv": ok(roa0 > 0 if roa0 is not None else None),
        "Operativer Cashflow positiv": ok(cfo0 > 0 if cfo0 is not None else None),
        "ROA gestiegen": ok(roa0 > roa1 if None not in (roa0, roa1) else None),
        "Cashflow > Gewinn (ACCRUAL)": ok(cfo0 > roa0 if None not in (cfo0, roa0) else None),
        "Verschuldung gesunken": ok(lev0 < lev1 if None not in (lev0, lev1) else None),
        "Liquidität gestiegen": ok(cr0 > cr1 if None not in (cr0, cr1) else None),
        "Keine neuen Aktien (Näherung: Aktienzahl)": ok(a.get("shares") <= b.get("shares") if None not in (a.get("shares"), b.get("shares")) else None),
        "Bruttomarge gestiegen": ok(gm0 > gm1 if None not in (gm0, gm1) else None),
        "Kapitalumschlag gestiegen": ok(at0 > at1 if None not in (at0, at1) else None),
    }
    known = [v for v in signals.values() if v is not None]
    if len(known) < 9:
        return {"score": None, "signals": signals, "note": f"Nur {len(known)} von 9 Signalen berechenbar"}
    return {"score": sum(known), "signals": signals}


def compute_metrics(fund: Optional[dict], inf: dict, pstats: dict) -> Dict[str, Optional[float]]:
    """Rohwerte aller Kennzahlen (gleiche Formeln für Aktie und Vergleichsfirmen)."""
    m: Dict[str, Optional[float]] = {k: None for k in cfg.METRICS}
    m.update({"mom_6": None, "_mc_fin": None, "_ev": None, "_z_zone_model": None, "_z_alt": None})
    if fund and fund.get("years"):
        y0 = fund["years"][0]
        v = y0["values"]
        ta, eq, ni = v.get("total_assets"), v.get("equity"), v.get("net_income")
        m["gpoa"] = _div(v.get("gross_profit"), ta)
        m["roe"] = _div(ni, eq) if eq and eq > 0 else None
        m["roa"] = _div(ni, ta)
        margins = [_div(y["values"].get("gross_profit"), y["values"].get("revenue")) for y in fund["years"][:5]]
        margins = [x for x in margins if x is not None]
        m["margin_stability"] = statistics.stdev(margins) if len(margins) >= 3 else None
        if len(fund["years"]) >= 2:
            p = piotroski(y0, fund["years"][1], fund["years"][2] if len(fund["years"]) >= 3 else None)
            m["piotroski_f"] = p["score"] if p else None
            m["_piotroski"] = p
        m["leverage"] = _div(v.get("total_debt"), ta)

        mc = market_cap_in(inf, fund.get("currency"))
        m["_mc_fin"] = mc
        if mc:
            ev = mc + (v.get("total_debt") or 0) - (v.get("cash") or 0) if v.get("total_debt") is not None else None
            m["_ev"] = ev
            m["ebitda_to_ev"] = _div(v.get("ebitda"), ev) if ev and ev > 0 else None
            m["book_to_market"] = _div(eq, mc) if eq and eq > 0 else None
            m["fcf_yield"] = _div((v.get("cfo") - v.get("capex")) if None not in (v.get("cfo"), v.get("capex")) else None, mc)
            m["earnings_yield"] = _div(ni, mc)
            tl = v.get("total_liabilities")
            wc = (v.get("current_assets") - v.get("current_liabilities")) if None not in (v.get("current_assets"), v.get("current_liabilities")) else None
            re_, ebit, sales = v.get("retained_earnings"), v.get("ebit"), v.get("revenue")
            if None not in (wc, re_, ebit, sales, tl, ta) and ta and tl:
                # [ALT] Original-Z (so auch in [QMJ] für alle Firmen) – fürs Perzentil
                m["altman_z"] = 1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta + 0.6 * mc / tl + 1.0 * sales / ta
                # Z'' für Nicht-Industriefirmen (Buchwert statt Marktwert, ohne Umsatz) – nur Anzeige
                if eq is not None:
                    m["_z_alt"] = 6.56 * wc / ta + 3.26 * re_ / ta + 6.72 * ebit / ta + 1.05 * eq / tl
    for k in ("mom_12_1", "mom_6", "volatility", "beta"):
        m[k] = pstats.get(k) if pstats else None
    return m


# ── Perzentile ────────────────────────────────────────────────────────────────

def percentile(value: Optional[float], others: List[float], higher_is_better: bool) -> Optional[float]:
    """Anteil der Vergleichsfirmen, die schlechter sind (Gleichstand zählt halb), 0–100."""
    if value is None or len(others) < cfg.MIN_VALUES_FOR_PERCENTILE:
        return None
    worse = sum(1 for o in others if (o < value if higher_is_better else o > value))
    ties = sum(1 for o in others if o == value)
    return round(100 * (worse + 0.5 * ties) / len(others), 1)


def winsorized_median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    lo = s[int(cfg.WINSOR_LOW * (len(s) - 1))]
    hi = s[int(math.ceil(cfg.WINSOR_HIGH * (len(s) - 1)))]
    return statistics.median([min(max(x, lo), hi) for x in s])


def _display(key: str, raw: Optional[float]) -> Optional[float]:
    """Für die Anzeige: EV/EBITDA und KBV statt der gerechneten Kehrwerte."""
    if raw is None:
        return None
    if cfg.METRICS.get(key, {}).get("display_inverse"):
        return 1 / raw if raw > 0 else None
    return raw


def _piotroski_zone(f) -> Optional[dict]:
    """[PIO]: 0–1 = tief (rot), 8–9 = hoch (grün), dazwischen gelb."""
    if f is None:
        return None
    color = "red" if f <= cfg.PIOTROSKI_LOW_MAX else "green" if f >= cfg.PIOTROSKI_HIGH_MIN else "yellow"
    return {"value": f, "color": color, "rule": f"rot 0–{cfg.PIOTROSKI_LOW_MAX}, grün {cfg.PIOTROSKI_HIGH_MIN}–9 [PIO]"}


# ── Score für eine Aktie ──────────────────────────────────────────────────────

def _company_bundle(symbol: str, index_symbol: str, pstats: dict, use_esef: bool) -> dict:
    inf = info(symbol)
    fund = get_fundamentals(symbol, inf.get("name"), inf.get("country"), use_esef=use_esef)
    return {"symbol": symbol, "info": inf, "fund": fund, "metrics": compute_metrics(fund, inf, pstats.get(symbol, {}))}


def compute_score(symbol: str, progress=lambda msg, pct: None) -> dict:
    sym = symbol.upper()
    progress("Firmenangaben laden …", 5)
    inf = info(sym)
    if not inf.get("name") and not inf.get("industry"):
        return {"symbol": sym, "available": False, "error": "Keine Firmenangaben von Yahoo Finance."}
    if inf.get("quote_type") not in (None, "EQUITY"):
        return {"symbol": sym, "available": False,
                "error": f"Score nur für Aktien verfügbar (dies ist: {inf.get('quote_type')})."}

    progress("Vergleichsgruppe bestimmen …", 10)
    group = peer_group(sym)
    peer_syms = [p["symbol"] for p in group["peers"]]
    index_symbol = market_index_for(inf.get("country"))

    progress("Kursverläufe laden (Momentum, Volatilität, Beta) …", 20)
    pstats = price_stats([sym] + peer_syms, index_symbol)

    progress("Bilanzdaten der Aktie laden …", 30)
    target = _company_bundle(sym, index_symbol, pstats, use_esef=True)

    progress(f"Bilanzdaten von {len(peer_syms)} Vergleichsfirmen laden …", 40)
    peers: List[dict] = []
    done = [0]
    lock = threading.Lock()

    def load(ps):
        try:
            b = _company_bundle(ps, index_symbol, pstats, use_esef=False)
        except Exception as e:
            log.warning("Vergleichsfirma %s fehlgeschlagen: %s", ps, e)
            b = None
        with lock:
            done[0] += 1
            progress(f"Vergleichsfirmen: {done[0]}/{len(peer_syms)}", 40 + int(50 * done[0] / max(1, len(peer_syms))))
        return b

    with ThreadPoolExecutor(max_workers=4) as pool:
        peers = [b for b in pool.map(load, peer_syms) if b]

    progress("Score berechnen …", 95)
    financial = is_financial(inf.get("industry"))
    tm = target["metrics"]
    fund = target["fund"]
    y0 = fund["years"][0] if fund and fund.get("years") else None
    damo = damodaran_for(inf.get("industry"))

    fund_label = None
    if y0:
        fund_label = f"{fund['source']}, Geschäftsjahr bis {y0['period_end']}" + (f", eingereicht {y0['filed']}" if y0.get("filed") else "")
    price_label = f"Yahoo-Kurse bis {pstats.get(sym, {}).get('last_price_date', '–')}, Index {index_symbol}"
    mc_label = f"Börsenwert Yahoo ({inf.get('fetched_at', '')[:10]})"

    metric_rows = {}
    for key, spec in cfg.METRICS.items():
        others = [p["metrics"][key] for p in peers if p["metrics"].get(key) is not None]
        raw = tm.get(key)
        applicable = not (financial and key not in cfg.FINANCIAL_INFO_METRICS)
        pct = percentile(raw, others, spec["higher_is_better"]) if applicable else None
        if spec["pillar"] in ("quality", "safety") and key not in ("volatility", "beta"):
            src = fund_label
        elif spec["pillar"] == "value":
            src = f"{fund_label}; {mc_label}" if fund_label else mc_label
        else:
            src = price_label
        reason = None
        if not applicable:
            reason = "Für Banken/Versicherungen nicht aussagekräftig"
        elif raw is None:
            reason = "Daten fehlen oder Kennzahl nicht sinnvoll (z. B. negatives Eigenkapital/EBITDA)"
        elif pct is None:
            reason = f"Zu wenige Vergleichswerte ({len(others)} < {cfg.MIN_VALUES_FOR_PERCENTILE})"
        metric_rows[key] = {
            "key": key, "label": spec["label"], "pillar": spec["pillar"], "enabled": spec["enabled"],
            "higher_is_better": spec["higher_is_better"] if not spec.get("display_inverse") else False,
            "value": _display(key, raw), "raw": raw,
            "peer_median": _display(key, winsorized_median(others)) if others else None,
            "peer_count": len(others), "percentile": pct,
            "color": color_for(pct) if spec["enabled"] or pct is not None else "grey",
            "literature": spec["source"], "data_source": src, "reason": reason,
        }

    # Branchenwerte (Damodaran) zur Information / Rückfallebene
    if damo:
        dv = damo["values"]
        for key, dkey in (("ebitda_to_ev", "ev_ebitda"), ("book_to_market", "pbv"), ("earnings_yield", "pe")):
            metric_rows[key]["damodaran"] = dv.get(dkey)
        metric_rows["roe"]["damodaran"] = dv.get("roe")

    # Säulen
    pillars = {}
    enabled_keys = [k for k, s in cfg.METRICS.items() if s["enabled"]]
    for p in cfg.PILLAR_WEIGHTS:
        rows = [metric_rows[k] for k in enabled_keys if cfg.METRICS[k]["pillar"] == p]
        vals = [r["percentile"] for r in rows if r["percentile"] is not None]
        score = round(sum(vals) / len(vals), 1) if vals else None
        pillars[p] = {"label": cfg.PILLAR_LABELS[p], "score": score, "color": color_for(score),
                      "weight": cfg.PILLAR_WEIGHTS[p], "metrics_used": len(vals), "metrics_total": len(rows)}

    used = sum(1 for k in enabled_keys if metric_rows[k]["percentile"] is not None)
    coverage = used / len(enabled_keys)
    overall, overall_note = None, None
    if financial:
        overall_note = ("Score für Finanzfirmen nicht verfügbar: Altman- und Profitabilitätskennzahlen sind "
                        "für Banken/Versicherungen nicht aussagekräftig ([ALT], [NM], [DAM]). "
                        "Einzelne Kennzahlen werden zur Information angezeigt.")
    elif coverage < cfg.MIN_COVERAGE:
        overall_note = f"Nicht genug Daten (Abdeckung {coverage:.0%} < {cfg.MIN_COVERAGE:.0%})."
    else:
        ws = [(pillars[p]["score"], w) for p, w in cfg.PILLAR_WEIGHTS.items() if pillars[p]["score"] is not None]
        overall = round(sum(s * w for s, w in ws) / sum(w for _, w in ws), 1)
        missing = [pillars[p]["label"] for p in cfg.PILLAR_WEIGHTS if pillars[p]["score"] is None]
        if missing:
            overall_note = f"Ohne Säule(n) {', '.join(missing)} – Gewichte auf die übrigen verteilt."

    # Altman absolut (Zonen aus dem PDF)
    altman_abs = None
    if not financial and tm.get("altman_z") is not None:
        if is_manufacturing(inf.get("sector"), inf.get("industry")):
            z = tm["altman_z"]
            zone = "red" if z < cfg.Z_DISTRESS_BELOW else "green" if z >= cfg.Z_SAFE_FROM else "yellow"
            altman_abs = {"model": "Z (Original, Industriefirmen)", "value": round(z, 2), "color": zone,
                          "rule": f"rot < {cfg.Z_DISTRESS_BELOW}, gelb bis {cfg.Z_SAFE_FROM}, grün ab {cfg.Z_SAFE_FROM} [ALT]"}
        elif tm.get("_z_alt") is not None:
            em = tm["_z_alt"] + 3.25
            zone = "red" if em < cfg.EM_SCORE_DISTRESS_BELOW else "green" if em >= cfg.EM_SCORE_SAFE_FROM else "yellow"
            altman_abs = {"model": "Z'' (Nicht-Industrie) als EM-Score = Z''+3.25", "value": round(em, 2), "color": zone,
                          "rule": f"rot < {cfg.EM_SCORE_DISTRESS_BELOW} (unter B−), grün ab {cfg.EM_SCORE_SAFE_FROM} (BBB−) – Rating-Tabelle [ALT]"}

    warnings = []
    if y0 and (date.today() - date.fromisoformat(y0["period_end"])).days > 460:
        warnings.append(f"Letzter verfügbarer Jahresabschluss ist älter als 15 Monate ({y0['period_end']}).")
    if not group.get("enough"):
        warnings.append(f"Nur {len(group['peers'])} Vergleichsfirmen gefunden (< {cfg.MIN_PEERS}). "
                        "Perzentile sind entsprechend unsicher; Damodaran-Branchenwerte als Referenz.")
    try:
        deviations = cross_check(fund, sym) if fund else []
    except Exception:
        deviations = []
    if fund and fund["years"] and fund["years"][0]["values"].get("_derived"):
        warnings.append("Abgeleitete Posten (aus anderen Posten berechnet): " + ", ".join(fund["years"][0]["values"]["_derived"]))
    if fund and fund["years"] and fund["years"][0]["values"].get("_from_yahoo"):
        warnings.append(f"Im Bericht ({fund['source']}) fehlende Posten aus Yahoo ergänzt: "
                        + ", ".join(fund["years"][0]["values"]["_from_yahoo"]))

    return {
        "symbol": sym, "available": True, "name": inf.get("name"), "disclaimer": DISCLAIMER,
        "is_financial": financial,
        "overall": overall, "overall_color": color_for(overall), "overall_note": overall_note,
        "coverage": round(coverage * 100), "pillars": pillars, "metrics": metric_rows,
        "info_metrics": {"mom_6": {"label": cfg.INFO_METRICS["mom_6"], "value": tm.get("mom_6")}},
        "piotroski": tm.get("_piotroski"),
        "piotroski_absolute": _piotroski_zone(tm.get("piotroski_f")),
        "altman_absolute": altman_abs,
        "peer_group": {"level": group["level"], "enough": group["enough"], "source": group["source"],
                       "tried": group["tried"], "fetched_at": group["fetched_at"],
                       "members": [{"symbol": p["symbol"], "name": p["name"], "country": p.get("country"),
                                    "market_cap_usd": p["market_cap_usd"]} for p in group["peers"]],
                       "with_data": len(peers)},
        "damodaran": damo,
        "fundamentals": {"source": fund["source"] if fund else None, "currency": fund.get("currency") if fund else None,
                         "period_end": y0["period_end"] if y0 else None, "filed": y0.get("filed") if y0 else None,
                         "entity": fund.get("entity") if fund else None,
                         "standard": ("US-GAAP" if fund and fund["source"].startswith("SEC") and fund.get("currency") == "USD" else None),
                         "deviations_vs_yahoo": deviations},
        "market": {"index": index_symbol, "market_cap_fin_ccy": tm.get("_mc_fin"), "ev": tm.get("_ev"),
                   "price_date": pstats.get(sym, {}).get("last_price_date")},
        "warnings": warnings,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Hintergrund-Berechnung ────────────────────────────────────────────────────

_jobs: Dict[str, dict] = {}
_jobs_lock = threading.Lock()
_runner = ThreadPoolExecutor(max_workers=2, thread_name_prefix="score")


def get_or_start(symbol: str, refresh: bool = False) -> dict:
    """Fertiges Ergebnis (aus Cache, max. 1 Tag) oder Status der laufenden Berechnung."""
    sym = symbol.upper()
    if not refresh:
        value, age = cache.get(f"score:{sym}")
        if value is not None and age < cfg.CACHE_MARKET_STATS:
            return {"status": "done", "result": value, "cache_age_seconds": int(age)}
    with _jobs_lock:
        job = _jobs.get(sym)
        if job and job["status"] == "running":
            return {"status": "running", "message": job["message"], "progress": job["progress"]}
        if job and job["status"] in ("done", "error") and not refresh and time.time() - job["finished"] < 60:
            return {k: v for k, v in job.items() if k != "finished"}
        job = {"status": "running", "message": "Start …", "progress": 0}
        _jobs[sym] = job

    def progress(msg, pct):
        job["message"], job["progress"] = msg, pct

    def run():
        try:
            res = compute_score(sym, progress)
            if res.get("available"):
                cache.put(f"score:{sym}", res)
            job.update({"status": "done", "result": res, "cache_age_seconds": 0})
        except Exception as e:
            log.exception("Score für %s fehlgeschlagen", sym)
            job.update({"status": "error", "error": f"Berechnung fehlgeschlagen ({type(e).__name__}: {e})"})
        job["finished"] = time.time()

    _runner.submit(run)
    return {"status": "running", "message": job["message"], "progress": 0}
