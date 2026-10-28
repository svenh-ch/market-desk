"""
Lieferketten aus offiziellen Berichten – nur belegte Verbindungen.

Quellen:
  a) Eigener neuester Jahresbericht bei der SEC (10-K / 20-F)
  b) Gegenrichtung: Berichte ANDERER Firmen, die diese Firma als Kunde/Lieferant
     nennen (SEC-Volltextsuche). So bekommen auch Firmen ohne SEC-Berichte
     (z. B. Nestlé) Verbindungen.
  c) Europäische Jahresberichte (ESEF über filings.xbrl.org), wo verfügbar
  d) Optional: Claude API zur Extraktion, wenn ANTHROPIC_API_KEY gesetzt ist –
     jedes Ergebnis wird gegen den Originalsatz geprüft.

Regeln: jede Verbindung mit Quelle (Dokument, Jahr, Abschnitt, Originalsatz),
Art (Kunde/Lieferant), Umsatzanteil falls genannt, Sicherheitsstufe
("bestätigt" = namentlich und eindeutig, "wahrscheinlich" = abgeleitet).
Anonyme Grosskunden ("Customer A", "one direct customer") werden als anonyme
Verbindung mit Umsatzanteil gespeichert – es wird NICHT geraten, wer gemeint ist.
Es wird NIE etwas aus allgemeinem Wissen ergänzt.
"""
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import yfinance as yf

from app import scoring_config as cfg
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import CompanyRelationship
from app.services import cache, sec
from app.services.fundamentals import normalize_name
from app.services.market_stats import info

log = logging.getLogger(__name__)

# ── Text in Sätze zerlegen (Abkürzungen schützen) ─────────────────────────────

_ABBR = ["Co.", "Inc.", "Ltd.", "Corp.", "No.", "U.S.", "U.K.", "S.A.", "N.V.", "Mr.", "Ms.", "Dr.", "St.",
         "e.g.", "i.e.", "approx.", "vs.", "Jan.", "Feb.", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.", "L.P.", "LLC.", "plc."]


def split_sentences(text: str) -> List[Tuple[int, str]]:
    """[(Position im Text, Satz)] – Abkürzungen wie 'Co.' beenden keinen Satz."""
    protected = text
    for a in _ABBR:
        protected = protected.replace(a, a.replace(".", "§"))
    out, pos = [], 0
    for m in re.finditer(r"(?<=[.;!?])\s+(?=[A-Z(“\"])", protected):
        out.append((pos, protected[pos:m.start()].replace("§", ".").strip()))
        pos = m.end()
    out.append((pos, protected[pos:].replace("§", ".").strip()))
    return [(p, s) for p, s in out if 20 < len(s) < 1200]


# ── Abschnitte eines 10-K erkennen ────────────────────────────────────────────

_ITEMS = {"1": "Item 1 – Geschäftstätigkeit", "1A": "Item 1A – Risikofaktoren", "7": "Item 7 – Lagebericht (MD&A)",
          "8": "Item 8 – Jahresrechnung/Anhang", "3": "Item 3 – Rechtsstreitigkeiten", "5": "Item 5 – Markt"}


def section_lookup(text: str):
    marks = [(m.start(), m.group(1).upper()) for m in re.finditer(r"\bItem\s+(1A|1B|1C|1|2|3|4|5|6|7A|7|8|9A|9B|9|10|11|12|13|14|15)\b\.?", text)]

    def find(pos: int) -> str:
        last = None
        for p, item in marks:
            if p > pos:
                break
            last = item
        return _ITEMS.get(last, f"Item {last}") if last else "unbekannter Abschnitt"
    return find


# ── Muster ────────────────────────────────────────────────────────────────────

SHARE = r"(?:approximately |about |roughly )?(\d{1,2}(?:\.\d+)?)\s?(?:%|percent)"
REVENUE_WORDS = r"(?:total |net |consolidated )?(?:revenues?|net sales|sales|turnover)"

ANON_PATTERNS = [
    # "Customer A accounted for 12% of revenue"
    re.compile(rf"\b(Customer [A-Z])\b[^.;]{{0,80}}?(?:accounted for|represented|comprised)\s+{SHARE}[^.;]{{0,30}}{REVENUE_WORDS}", re.I),
    # "sales to one direct customer represented 22% of total revenue"
    re.compile(rf"\b((?:one|another|a single|our largest|our second largest|a third|a)\s+(?:direct |indirect |major |significant )?customer)\b[^.;]{{0,60}}?(?:accounted for|represented|comprised)\s+{SHARE}[^.;]{{0,30}}{REVENUE_WORDS}", re.I),
]

SUPPLIER_CUES = re.compile(r"(sole[- ]source|single[- ]source|sole supplier|single supplier|suppliers? such as|"
                           r"foundr(?:y|ies)[^.;]{0,20}such as|contract manufacturers? such as|subcontractors?[^.;]{0,40}such as|"
                           r"rely on [^.;]{0,30}suppliers?|purchase[sd]? [^.;]{0,60} from|supplied by|manufactured by|"
                           r"depend(?:s|ent)? on [^.;]{0,30}(?:supplier|manufacturer|foundr))", re.I)
CUSTOMER_CUES = re.compile(r"(customer|accounted for|represented|of (?:our )?(?:total |net )?(?:revenue|sales))", re.I)
NEGATIVE_CUES = re.compile(r"(compet|rival|acqui(?:re|sition)|lawsuit|litigation|merger)", re.I)

# Organisationsnamen-Kandidaten: Folge grossgeschriebener Wörter, optional mit Rechtsform
ORG = re.compile(r"\b([A-Z][A-Za-z0-9&'\-]+(?:\s+(?:[A-Z][A-Za-z0-9&'\-]+|of|&|de|du))*"
                 r"(?:,?\s+(?:Inc\.|Inc|Co\.,? Ltd\.|Co\., Ltd|Co\.|Ltd\.|Limited|Corporation|Corp\.|AG|SE|S\.A\.|N\.V\.|plc|LLC|GmbH))?)")
STOP = {"We", "Our", "The", "Company", "Table", "Contents", "Customer", "Customers", "Supplier", "Suppliers", "In", "For",
        "Asia", "Europe", "United States", "U.S", "China", "Taiwan", "Korea", "Japan", "Mexico", "India", "Item", "Note",
        "During", "As", "If", "These", "This", "Currently", "Certain", "Some", "Many", "Other", "Such", "AI", "OEM", "OEMs",
        "ODM", "ODMs", "CSP", "CSPs", "Compute", "Networking", "Graphics", "Gigafactory", "Form", "Annual Report",
        "All", "Any", "Each", "Both", "Most", "Revenue", "Revenues", "Sales", "Total", "Fiscal", "Year", "Products",
        "Services", "However", "Although", "While", "Because", "Accordingly", "Further", "Additionally", "See",
        "Part", "Risk", "Factors", "Supply", "Inventory", "Cash", "Net", "Our Supply", "Concentration",
        "Direct", "Indirect", "Direct Customers", "Indirect Customers", "Limited", "Currently"}


LEAD_STOP = {"We", "Our", "The", "In", "For", "As", "If", "These", "This", "During", "Currently", "Certain", "Some",
             "Many", "Other", "Such", "Each", "All", "Any", "See", "However", "Item", "Note", "Table", "Part"}


def _org_candidates(sentence: str, own_name: str) -> List[str]:
    own = normalize_name(own_name)
    aliases = set(re.findall(r"\(([A-Z][A-Za-z]{1,6})\)", sentence)) | set(re.findall(r", or ([A-Z][A-Za-z]{1,6})\b", sentence))
    out = []
    for m in ORG.finditer(sentence):
        cand = m.group(1).strip(" ,")
        words = cand.split()
        if cand in STOP or (len(words) == 1 and words[0] in STOP) or words[0] in LEAD_STOP or len(cand) < 3 or cand in aliases:
            continue
        n = normalize_name(cand)
        if not n or n == own or own.startswith(n) or len(n) < 3:
            continue
        out.append(cand)
    return list(dict.fromkeys(out))


# ── Namen → Ticker ────────────────────────────────────────────────────────────

def resolve_name(name: str) -> dict:
    """
    Firmenname aus dem Bericht → Ticker.
      sicher:   exakter (vereinfachter) Namensabgleich mit der SEC-Liste oder Yahoo
      unsicher: Yahoo-Treffer, dessen Name den Berichtsnamen nur enthält
      None:     keine Zuordnung (Name wird trotzdem angezeigt)
    """
    key = f"resolve:{normalize_name(name)}"

    def fetch():
        n = normalize_name(name)
        for t, v in sec.ticker_map().items():
            if normalize_name(v["title"]) == n:
                return {"ticker": t, "certain": True, "matched": v["title"], "via": "SEC-Firmenliste"}
        words = name.replace(",", "").split()
        best = None
        for k in sorted({len(words), min(len(words), 3), min(len(words), 2)}, reverse=True):
            try:
                quotes = yf.Search(" ".join(words[:k]), max_results=8, news_count=0).quotes
            except Exception:
                quotes = []
            for q in quotes:
                if q.get("quoteType") != "EQUITY" or q.get("exchange") in cfg.OTC_EXCHANGES:
                    continue
                qn = normalize_name(q.get("longname") or q.get("shortname") or "")
                if qn == n:
                    return {"ticker": q["symbol"], "certain": True, "matched": q.get("longname"), "via": "Yahoo-Suche"}
                if best is None and qn and (qn.startswith(n) or n.startswith(qn)) and len(n) >= 4:
                    best = {"ticker": q["symbol"], "certain": False, "matched": q.get("longname") or q.get("shortname"), "via": "Yahoo-Suche"}
        return best or {"ticker": None, "certain": False, "matched": None, "via": None}

    value, _, _ = cache.cached(key, 30 * 86400, fetch)
    return value


# ── Extraktion aus einem Text ─────────────────────────────────────────────────

_SUBJ = r"\b(?:we|the company|the registrant)\b"


def accent_regex(name: str) -> str:
    """'Nestle' passt auch auf 'Nestlé' (Akzente in Berichten)."""
    v = {"a": "[aàáâä]", "e": "[eèéêë]", "i": "[iìíîï]", "o": "[oòóôö]", "u": "[uùúûü]", "c": "[cç]", "n": "[nñ]"}
    out = []
    for ch in name:
        cls = v.get(ch.lower())
        if cls:  # Gross-/Kleinschreibung des Originals beibehalten: 'N' → [NÑ], 'e' → [eèéêë]
            out.append(cls.upper() if ch.isupper() else cls)
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _explicit_relation(sentence: str, name: str, name_re: Optional[str] = None) -> Tuple[Optional[str], Optional[float]]:
    """
    Eindeutige Satzmuster direkt am Namen → ("customer"|"customer_channel"|"supplier", Anteil) oder (None, None).
    Sicht des BERICHTENDEN Unternehmens: "customer" = name ist Kunde, "supplier" = name ist Lieferant.
    """
    # Punkte in Abkürzungen ("Inc.", "Co.") würden [^.;] in den Mustern stoppen → schützen
    for a in _ABBR:
        sentence = sentence.replace(a, a.replace(".", "§"))
        name = name.replace(a, a.replace(".", "§"))
    N = name_re or re.escape(name)
    customer = [
        rf"{N}[^.;]{{0,60}}?(?:accounted for|represented|comprised)\s+{SHARE}[^.;]{{0,40}}{REVENUE_WORDS}",
        rf"(?:sales|revenues?) (?:to|from) {N}[^.;]{{0,40}}?(?:accounted for|represented|comprised|were|was)\s+{SHARE}",
        rf"{N},? (?:is|was|are|were|became|remains?) (?:our|one of our) (?:largest |biggest |most significant |significant |major |key |principal |primary )?customers?\b",
        rf"\bour (?:largest|biggest|significant|major|key|principal) customers?,? (?:include|including|such as|were|are|is|was)\s+[^.;]{{0,80}}?{N}",
    ]
    supplier = [
        rf"\b(?:our|we use|we utilize|we engage(?: with)?|we rely on)\b[^.;]{{0,40}}?(?:suppliers?|vendors?|foundr(?:y|ies)|contract manufacturers?|subcontractors?)[^.;]{{0,40}}?(?:such as|including)\s+[^.;]{{0,160}}?{N}",
        rf"{_SUBJ}(?:\s+\w+){{0,2}}\s+(?:purchase[sd]?|buy|bought|procure[sd]?|source[sd]?|obtain(?:ed|s)?)\s+[^.;]{{0,80}}?\bfrom\s+[^.;]{{0,120}}?{N}",
        rf"{_SUBJ}(?:\s+\w+){{0,2}}\s+(?:purchase[sd]?|buy|bought|use[sd]?)\b[^.;]{{0,80}}?(?:manufactured|made|produced|supplied) by\s+[^.;]{{0,40}}?{N}",
        rf"\b(?:our|its)\b[^.;]{{0,60}}\b(?:supplied|manufactured|produced|fabricated) (?:exclusively |solely |primarily )?by\s+{N}",
        rf"{N},? (?:is|was|are|remains?) (?:our|the) (?:sole |single |primary |principal |main |major |key |largest )?(?:supplier|source|vendor|manufacturer|foundry)",
        rf"{_SUBJ}(?:\s+\w+){{0,2}}\s+(?:rely|relies|depend|depends) (?:on|upon)\s+(?:suppliers such as\s+)?{N}",
    ]
    for pat in customer:
        m = re.search(pat, sentence, re.I)
        if m:
            share = next((float(g) for g in m.groups() if g and re.fullmatch(r"\d{1,2}(?:\.\d+)?", g)), None)
            # Anteil für mehrere Kunden zusammen ("top three … accounted for 45%") → kein Einzelanteil
            if re.search(r"\b(combined|together|collectively|in (?:the )?aggregate|top (?:two|three|four|five|\d+))\b", sentence, re.I):
                return "customer_group", None
            if re.search(r"\b(through|via|platform|store|channel)\b", sentence, re.I):
                return "customer_channel", share  # Umsatz über Plattform = eher Vertriebskanal
            return "customer", share
    for pat in supplier:
        if re.search(pat, sentence, re.I):
            return "supplier", None
    return None, None


def extract_from_text(text: str, own_name: str, doc: dict, focus_name: Optional[str] = None) -> List[dict]:
    """
    Findet Kunden-/Lieferantenangaben. doc = {label, year, url, accession}.
    focus_name gesetzt (Gegenrichtung) → nur Sätze, die diese Firma nennen,
    und nur eindeutige Muster. Ohne focus_name (eigener Bericht) zusätzlich
    "wahrscheinlich"-Treffer bei Kunden-/Lieferanten-Stichworten.
    """
    find_section = section_lookup(text)
    found: List[dict] = []
    focus_re = None
    if focus_name:
        focus_re = re.compile(rf"\b{accent_regex(focus_name)}\b(?-i:(?!\s+[A-Z][a-z]))")

    for pos, s in split_sentences(text):
        if NEGATIVE_CUES.search(s) or _is_prior_year(s, doc["year"]):
            continue
        section = find_section(pos)
        quote = s[:600]

        if focus_re is None:
            for pat in ANON_PATTERNS:
                for m in pat.finditer(s):
                    found.append({"other": None, "anon_label": m.group(1).strip(), "type": "customer",
                                  "share": float(m.group(2)), "confidence": "bestätigt",
                                  "section": section, "quote": quote, **doc})

        if focus_re is not None:
            names = [focus_name] if focus_re.search(s) else []
        elif SUPPLIER_CUES.search(s) or CUSTOMER_CUES.search(s):
            names = _org_candidates(s, own_name)
        else:
            names = []

        for nm in names:
            rel, share = _explicit_relation(s, nm, focus_re.pattern if focus_re is not None else None)
            if not rel:
                continue  # ohne eindeutiges Satzmuster keine Verbindung (keine Vermutungen)
            found.append({"other": nm, "anon_label": None, "type": "customer" if rel.startswith("customer") else "supplier",
                          "share": share, "confidence": "wahrscheinlich" if rel in ("customer_channel", "customer_group") else "bestätigt",
                          "section": section, "quote": _quote_around(s, nm), **doc})
    return found


def _quote_around(sentence: str, name: str, width: int = 260) -> str:
    """Ausschnitt des Originalsatzes rund um den Namen (für die Quellenanzeige)."""
    m = re.search(re.escape(name), sentence)
    if not m or len(sentence) <= 2 * width:
        return sentence[:600]
    a, b = max(0, m.start() - width), min(len(sentence), m.end() + width)
    return ("… " if a else "") + sentence[a:b] + (" …" if b < len(sentence) else "")


def _is_prior_year(sentence: str, doc_year: int) -> bool:
    """Satz bezieht sich nur auf frühere Geschäftsjahre (z. B. 'For fiscal year 2024 …')."""
    years = [int(y) for y in re.findall(r"\b(?:fiscal(?: year)?|FY|in|during)\s+(20\d\d)\b", sentence, re.I)]
    return bool(years) and max(years) < doc_year


# ── Optional: Claude API ──────────────────────────────────────────────────────

def claude_available() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def extract_with_claude(sentences: List[str], own_name: str, doc: dict) -> List[dict]:
    """
    Nur wenn ein API-Key vorhanden ist. Claude bekommt ausschliesslich die
    vorgefilterten Originalsätze; jedes Ergebnis wird danach geprüft:
    der genannte Name UND das Zitat müssen wörtlich im Originalsatz stehen.
    """
    from app.services.claude_extract import extract_relations
    out = []
    for item in extract_relations(sentences, own_name):
        src = next((s for s in sentences if item["quote"] and item["quote"] in s), None)
        if not src or (item.get("name") and item["name"] not in src):
            continue  # nicht belegbar → verworfen
        out.append({"other": item.get("name"), "anon_label": item.get("anonymous_label"), "type": item["type"],
                    "share": item.get("revenue_share_pct"), "confidence": item.get("confidence", "wahrscheinlich"),
                    "section": doc.get("section_hint", "Jahresbericht"), "quote": src[:600], **doc, "method": "Claude API"})
    return out


# ── Speichern ─────────────────────────────────────────────────────────────────

_RANK = {"bestätigt": 2, "wahrscheinlich": 1}


def _store(edges: List[dict], origin: str, filer_symbol: str, reset: bool) -> int:
    """Kanten speichern; pro (Firma, Gegenpartei, Art) die stärkste Angabe behalten."""
    resolved = {}
    for e in edges:  # erst alle Namen auflösen (eigene DB-Zugriffe), dann schreiben
        if e["other"] and e["other"] not in resolved:
            resolved[e["other"]] = resolve_name(e["other"])
    best: Dict[tuple, dict] = {}
    for e in edges:
        if e["other"]:
            r = resolved[e["other"]]
            if e.get("_needs_mapping") and not r["ticker"]:
                continue  # schwacher Treffer ohne erkennbare Firma → verwerfen (wohl kein Firmenname)
            b_key = r["ticker"] or f"NAME:{e['other']}"
            e.update({"mapped": r["ticker"], "mapping_certain": r["certain"], "mapped_name": r["matched"]})
        else:
            b_key = f"ANON:{e['anon_label']}|{e['share']}"
            e.update({"mapped": None, "mapping_certain": None, "mapped_name": None})
        if b_key == filer_symbol:
            continue
        k = (filer_symbol, b_key, e["type"])
        prev = best.get(k)
        if prev is None or (_RANK[e["confidence"]], e["share"] or 0) > (_RANK[prev["confidence"]], prev["share"] or 0):
            best[k] = e
    with SessionLocal() as db:
        if reset:
            db.query(CompanyRelationship).filter(CompanyRelationship.company_a == filer_symbol,
                                                 CompanyRelationship.origin == origin).delete()
        for (a, b, typ), e in best.items():
            existing = db.query(CompanyRelationship).filter_by(company_a=a, company_b=b, relationship_type=typ).first()
            if existing:
                if _RANK[e["confidence"]] <= _RANK.get(existing.confidence, 0):
                    continue
                db.delete(existing)
                db.flush()
            db.add(CompanyRelationship(
                company_a=a, company_b=b, relationship_type=typ, revenue_share=e["share"],
                confidence=e["confidence"], source_doc=e["label"], source_year=e["year"], source_url=e["url"],
                section=e["section"], description=e["quote"], name_in_report=e["other"] or e["anon_label"],
                mapping_certain=e["mapping_certain"], origin=origin, method=e.get("method", "Regeln (Textmuster)"),
            ))
        db.commit()
        return len(best)


# ── Ablauf für eine Firma ─────────────────────────────────────────────────────

def _symbol_for_cik(cik: int) -> Optional[str]:
    for t, v in sec.ticker_map().items():
        if v["cik"] == cik:
            return t
    return None


def process_own_filing(symbol: str, cik: int, own_name: str) -> dict:
    filing = sec.latest_annual(cik)
    if not filing:
        return {"own": "kein 10-K/20-F gefunden"}
    key = f"supply:own:{symbol}:{filing['accession']}"
    done, _ = cache.get(key)
    if done is not None:
        return done  # dieser Bericht wurde schon ausgewertet; neuer Bericht → neuer Schlüssel
    text = sec.fetch_document_text(cik, filing)
    doc = {"label": f"SEC {filing['form']} ({filing['report_date'] or filing['filed']})",
           "year": int((filing["report_date"] or filing["filed"])[:4]), "url": sec.document_url(cik, filing),
           "accession": filing["accession"]}
    edges = extract_from_text(text, own_name, doc)
    if claude_available():
        try:
            sents = [s for _, s in split_sentences(text) if SUPPLIER_CUES.search(s) or re.search(r"customer", s, re.I)]
            edges += extract_with_claude(sents[:150], own_name, doc)
        except Exception as e:
            log.warning("Claude-Extraktion fehlgeschlagen: %s", e)
    n = _store(edges, "own_filing", symbol, reset=True)
    result = {"own": f"{filing['form']} vom {filing['filed']} ausgewertet: {n} Verbindungen", "accession": filing["accession"]}
    cache.put(key, result)
    return result


def search_name_for(company_name: str) -> str:
    """Kurzname für die Volltextsuche, z. B. 'Nestlé S.A.' → 'Nestle', 'Apple Inc.' → 'Apple'."""
    n = normalize_name(company_name)
    return " ".join(w.capitalize() if len(w) > 3 else w.upper() for w in n.split()[:2]) if n else company_name


def process_mentions(symbol: str, company_name: str, own_cik: Optional[int]) -> dict:
    """Gegenrichtung: Wer nennt diese Firma in seinem 10-K/20-F als Kunde oder Lieferant?"""
    key = f"supply:mentions:{symbol}"
    done, age = cache.get(key)
    if done is not None and age < cfg.CACHE_SUPPLY_CHAIN:
        return done
    name = search_name_for(company_name)
    start = (date.today() - timedelta(days=550)).isoformat()
    hits = []
    phrases = []
    for n in dict.fromkeys([name, company_name.split(",")[0].split(" S.A")[0].split(" AG")[0].strip()]):
        phrases += [f'"{n} accounted for"', f'"sales to {n}"', f'"revenue from {n}"', f'"purchased from {n}"',
                    f'{n} "accounted for"', f'{n} "largest customer"', f'{n} "supplier"']
    for q in phrases:  # Reihenfolge = Priorität (exakte Phrasen zuerst)
        try:
            hits += sec.full_text_search(q, start=start)
        except Exception as e:
            log.warning("Volltextsuche fehlgeschlagen: %s", e)
    seen, checked, edges = set(), 0, 0
    for h in hits:
        if not h["cik"] or h["cik"] == own_cik or h["cik"] in seen or not h["file"]:
            continue
        if normalize_name(name) in normalize_name(h["name"]):
            continue  # Selbstnennung (z. B. 'Apple iSports Group')
        seen.add(h["cik"])
        if checked >= 25:
            break
        checked += 1
        filer = _symbol_for_cik(h["cik"])
        if not filer:
            continue
        acc = h["accession"].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{h['cik']}/{acc}/{h['file']}"
        try:
            text = sec.fetch_document_text(h["cik"], {"accession": h["accession"], "primary": h["file"]})
        except Exception:
            continue
        filed = date.fromisoformat(h["filed"])
        fiscal_year = filed.year - 1 if filed.month <= 6 else filed.year  # Jahresberichte erscheinen nach Jahresende
        doc = {"label": f"SEC {h['form']} von {filer} ({h['filed']})", "year": fiscal_year, "url": url,
               "accession": h["accession"]}
        found = extract_from_text(text, h["name"], doc, focus_name=name)
        for e in found:
            e["other"] = symbol  # Gegenpartei ist die gesuchte Firma selbst
        if found:
            # Zuordnung ist hier sicher (wir haben gezielt nach dieser Firma gesucht)
            for e in found:
                e["_force_mapping"] = True
            edges += _store_mentions(found, filer, symbol)
    result = {"mentions": f"{checked} fremde Berichte geprüft, {edges} Nennungen gefunden", "search_name": name}
    cache.put(key, result)
    return result


def _store_mentions(found: List[dict], filer: str, target: str) -> int:
    with SessionLocal() as db:
        best: Dict[str, dict] = {}
        for e in found:
            k = e["type"]
            prev = best.get(k)
            if prev is None or (_RANK[e["confidence"]], e["share"] or 0) > (_RANK[prev["confidence"]], prev["share"] or 0):
                best[k] = e
        for typ, e in best.items():
            existing = db.query(CompanyRelationship).filter_by(company_a=filer, company_b=target, relationship_type=typ).first()
            if existing and _RANK[e["confidence"]] <= _RANK.get(existing.confidence, 0):
                continue
            if existing:
                db.delete(existing)
                db.flush()
            db.add(CompanyRelationship(
                company_a=filer, company_b=target, relationship_type=typ, revenue_share=e["share"],
                confidence=e["confidence"], source_doc=e["label"], source_year=e["year"], source_url=e["url"],
                section=e["section"], description=e["quote"], name_in_report=search_name_for(target),
                mapping_certain=True, origin="mention", method="Regeln (Textmuster)",
            ))
        db.commit()
        return len(best)


def process_esef(symbol: str, company_name: str) -> dict:
    """Europäische Firmen: Jahresbericht (ESEF) als Text auswerten, falls verfügbar."""
    from app.services.fundamentals import ESEF_BASE, _esef_entity
    import requests
    from bs4 import BeautifulSoup
    key = f"supply:esef:{symbol}"
    done, age = cache.get(key)
    if done is not None and age < cfg.CACHE_SUPPLY_CHAIN:
        return done
    e = _esef_entity(company_name)
    if not e:
        result = {"esef": "kein ESEF-Bericht gefunden"}
        cache.put(key, result)
        return result
    rel = e["relationships"]["filings"]["links"]["related"]
    f = requests.get(f"{ESEF_BASE}{rel}?sort=-period_end&page%5Bsize%5D=1", timeout=30).json()["data"][0]["attributes"]
    url = ESEF_BASE + f["report_url"]
    html = requests.get(url, timeout=180).text
    text = re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" "))
    doc = {"label": f"ESEF-Jahresbericht {f['period_end'][:4]}", "year": int(f["period_end"][:4]), "url": url,
           "accession": f.get("fxo_id")}
    edges = extract_from_text(text, company_name, doc)
    for x in edges:
        x["section"] = "Jahresbericht (ESEF)"
    n = _store(edges, "esef", symbol, reset=True)
    result = {"esef": f"ESEF-Bericht {f['period_end']} ausgewertet: {n} Verbindungen"}
    cache.put(key, result)
    return result


def build(symbol: str, progress=lambda m, p: None) -> dict:
    sym = symbol.upper()
    inf = info(sym)
    name = inf.get("name") or sym
    from app.services.fundamentals import sec_cik_for
    cik = sec_cik_for(sym, name)
    status = {}
    if cik:
        progress("Eigenen Jahresbericht (SEC) auswerten …", 20)
        try:
            status.update(process_own_filing(sym, cik, name))
        except Exception as e:
            status["own"] = f"Fehler: {type(e).__name__}"
    elif cfg.COUNTRY_TO_REGION.get(inf.get("country") or "") in cfg.EUROPE_REGIONS and inf.get("country") != "Switzerland":
        progress("Europäischen Jahresbericht (ESEF) auswerten …", 20)
        try:
            status.update(process_esef(sym, name))
        except Exception as e:
            status["esef"] = f"Fehler: {type(e).__name__}"
    progress("Nennungen in Berichten anderer Firmen suchen …", 50)
    try:
        status.update(process_mentions(sym, name, cik))
    except Exception as e:
        status["mentions"] = f"Fehler: {type(e).__name__}"
    return status


# ── Abfrage für die Grafik ────────────────────────────────────────────────────

def graph(symbol: str) -> dict:
    sym = symbol.upper()
    with SessionLocal() as db:
        rows = db.query(CompanyRelationship).filter(
            (CompanyRelationship.company_a == sym) | (CompanyRelationship.company_b == sym)).all()
    links = []
    for r in rows:
        if r.company_a == sym:
            other, typ, direction = r.company_b, r.relationship_type, "eigener Bericht"
        else:
            # Gegenrichtung: A nennt sym als Kunde → für sym ist A Lieferant (und umgekehrt)
            other = r.company_a
            typ = {"customer": "supplier", "supplier": "customer"}[r.relationship_type]
            direction = "Bericht der Gegenpartei"
        anon = other.startswith("ANON:")
        label = (r.name_in_report if anon or other.startswith("NAME:") else other)
        links.append({
            "other": None if anon or other.startswith("NAME:") else other,
            "label": label, "anonymous": anon, "type": typ,
            "revenue_share": r.revenue_share,
            # Ein Anteil bezieht sich immer auf den Umsatz des BERICHTENDEN Unternehmens (company_a)
            "share_basis": ("eigener Umsatz" if r.company_a == sym else f"Umsatz von {r.company_a}") if r.revenue_share else None,
            "confidence": r.confidence,
            "mapping_certain": r.mapping_certain, "name_in_report": r.name_in_report,
            "source_doc": r.source_doc, "source_year": r.source_year, "source_url": r.source_url,
            "section": r.section, "quote": r.description, "via": direction, "method": r.method,
        })
    links.sort(key=lambda l: (l["type"], -(l["revenue_share"] or 0), l["confidence"] != "bestätigt"))
    return {"center": sym, "links": links,
            "message": None if links else "Keine öffentlichen Lieferkettendaten gefunden."}


# ── Hintergrund ───────────────────────────────────────────────────────────────

_jobs: Dict[str, dict] = {}
_lock = threading.Lock()


def get_or_start(symbol: str) -> dict:
    sym = symbol.upper()
    fresh, age = cache.get(f"supply:done:{sym}")
    if fresh is not None and age < cfg.CACHE_FILINGS_INDEX:
        return {"status": "done", "graph": graph(sym), "build": fresh}
    with _lock:
        job = _jobs.get(sym)
        if job and job["status"] == "running":
            return {"status": "running", "message": job["message"], "progress": job["progress"], "graph": graph(sym)}
        job = {"status": "running", "message": "Start …", "progress": 0}
        _jobs[sym] = job

    def progress(m, p):
        job["message"], job["progress"] = m, p

    def run():
        try:
            status = build(sym, progress)
            status["built_at"] = datetime.now(timezone.utc).isoformat()
            cache.put(f"supply:done:{sym}", status)
            job.update({"status": "done"})
        except Exception as e:
            log.exception("Lieferkette %s fehlgeschlagen", sym)
            job.update({"status": "error", "error": str(e)})

    threading.Thread(target=run, daemon=True, name=f"supply-{sym}").start()
    return {"status": "running", "message": job["message"], "progress": 0, "graph": graph(sym)}
