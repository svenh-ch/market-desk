"""
KONFIGURATION DES EIGENEN SCORES – alle Gewichte, Schwellen und Regeln an einem Ort.

Grundsatz: Jeder Wert ist mit Literatur begründet (Quelle im Kommentar).
Nichts hier wurde anhand vergangener Renditen optimiert.
Wo die Literatur keinen Wert vorgibt, steht "KEINE LITERATURVORGABE" und
der gewählte Wert ist als bewusste, einfache Setzung gekennzeichnet.

PDF-Kürzel (Ordner "PDF ORNer arberie"):
  [NM]   Novy-Marx (2010): The Other Side of Value – Gross Profitability Premium (NBER w15940)
  [QMJ]  Asness, Frazzini, Pedersen: Quality Minus Junk (Review of Accounting Studies)
  [AMP]  Asness, Moskowitz, Pedersen (2013): Value and Momentum Everywhere
  [ALT]  Altman (2000): Predicting Financial Distress – Revisiting the Z-Score and ZETA Models
  [DAM]  Damodaran (2006): Valuation Approaches and Metrics – A Survey
  [JKP]  Jensen, Kelly, Pedersen: Is There a Replication Crisis in Finance?
  [PIO]  Piotroski (2000): Value Investing – Historical Financial Statement Information (SP84.pdf)
"""

# ── Säulen und Gewichte ───────────────────────────────────────────────────────
# Gleichgewichtung. KEINE LITERATURVORGABE für eine bessere Gewichtung; [QMJ]
# mittelt seine Teilkomponenten ebenfalls gleichgewichtet (Profitability +
# Growth + Safety), [AMP] kombiniert Value und Momentum 50/50.
PILLAR_WEIGHTS = {
    "quality":   0.25,
    "value":     0.25,
    "momentum":  0.25,
    "safety":    0.25,
}

PILLAR_LABELS = {
    "quality": "Qualität",
    "value": "Bewertung",
    "momentum": "Momentum",
    "safety": "Sicherheit",
}

# ── Kennzahlen ────────────────────────────────────────────────────────────────
# higher_is_better: Richtung für das Perzentil (True = hoher Wert ist gut).
# enabled: False = wird berechnet/angezeigt, fliesst aber nicht in den Score.
METRICS = {
    # Qualität
    "gpoa": {
        "pillar": "quality", "label": "Bruttogewinn / Total Assets", "higher_is_better": True, "enabled": True,
        "source": "[NM] (REVT − COGS)/AT; ebenso Teil von [QMJ] Profitability",
    },
    "roe": {
        "pillar": "quality", "label": "Eigenkapitalrendite (ROE)", "higher_is_better": True, "enabled": True,
        "source": "[QMJ] ROE = Reingewinn / Buchwert Eigenkapital",
    },
    "roa": {
        "pillar": "quality", "label": "Gesamtkapitalrendite (ROA)", "higher_is_better": True, "enabled": True,
        "source": "[QMJ] ROA = Reingewinn / Total Assets",
    },
    "margin_stability": {
        "pillar": "quality", "label": "Schwankung der Bruttomarge (5 J.)", "higher_is_better": False, "enabled": True,
        "source": "[ALT] ZETA-Variable X2 'Stability of earnings'; [QMJ] EVOL (Gewinnschwankung)",
    },
    "piotroski_f": {
        "pillar": "quality", "label": "Piotroski F-Score (0–9)", "higher_is_better": True, "enabled": True,
        "source": "[PIO] Summe von 9 binären Signalen (Profitabilität, Finanzierung, Effizienz)",
    },
    # Bewertung (immer relativ zur Vergleichsgruppe)
    "ebitda_to_ev": {
        "pillar": "value", "label": "EV/EBITDA", "higher_is_better": True, "enabled": True,
        "display_inverse": True,  # angezeigt wird EV/EBITDA, gerechnet mit EBITDA/EV (bei Verlusten sinnvoll)
        "source": "[DAM] EV/EBITDA eines der meistgenutzten Multiples, Vergleich mit Branchenfirmen",
    },
    "book_to_market": {
        "pillar": "value", "label": "Kurs-Buchwert (KBV)", "higher_is_better": True, "enabled": True,
        "display_inverse": True,  # angezeigt wird KBV, gerechnet mit Buchwert/Marktwert wie [AMP]
        "source": "[AMP] Value = Buchwert/Marktwert (BE/ME); [DAM] Kurs/Buchwert",
    },
    "fcf_yield": {
        "pillar": "value", "label": "Free-Cash-Flow-Rendite", "higher_is_better": True, "enabled": True,
        "source": "[DAM] Cashflow-Multiples; Free Cashflow wie in [NM] (CFO − Investitionen)",
    },
    "earnings_yield": {
        "pillar": "value", "label": "Gewinnrendite (E/P)", "higher_is_better": True, "enabled": True,
        "source": "[DAM] Kehrwert des KGV (PE); E/P bleibt bei Verlusten sinnvoll sortierbar",
    },
    # Momentum
    "mom_12_1": {
        "pillar": "momentum", "label": "Rendite 12 Monate ohne letzten Monat (12-1)", "higher_is_better": True, "enabled": True,
        "source": "[AMP] MOM2–12: kumulierte Rendite der letzten 12 Monate ohne den jüngsten Monat",
    },
    # Sicherheit
    "altman_z": {
        "pillar": "safety", "label": "Altman Z-Score", "higher_is_better": True, "enabled": True,
        "source": "[ALT] Z = 1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MVE/TL + 1.0·S/TA; so auch in [QMJ] Safety",
    },
    "leverage": {
        "pillar": "safety", "label": "Verschuldung (Schulden / Total Assets)", "higher_is_better": False, "enabled": True,
        "source": "[QMJ] LEV; Achtung [JKP]: Thema 'low leverage' repliziert NICHT",
    },
    "volatility": {
        "pillar": "safety", "label": "Kursschwankung (1 J., annualisiert)", "higher_is_better": False, "enabled": True,
        "source": "[QMJ] Beta-Schätzung nach Frazzini/Pedersen nutzt 1-J.-Volatilität; [JKP] Thema 'low risk' repliziert",
    },
    "beta": {
        "pillar": "safety", "label": "Beta zum Markt", "higher_is_better": False, "enabled": True,
        "source": "[QMJ] BAB = −Beta; Schätzung: Volatilität 1 J. tägl., Korrelation 5 J. aus 3-Tages-Renditen",
    },
}

# Nur zur Information angezeigt, nicht im Score
INFO_METRICS = {
    "mom_6": "Rendite 6 Monate (nur Information)",
}

# ── Perzentile und Farben ─────────────────────────────────────────────────────
# Drittel (Terzile) wie die Portfolios P1/P2/P3 in [AMP]: oberes Drittel grün,
# mittleres gelb, unteres rot. Gilt für Kennzahlen, Säulen und Gesamtscore.
GREEN_FROM = 66.7
RED_BELOW = 33.3

# Ausreisser kappen (1./99. Perzentil). Hinweis: Für die Rangbildung selbst
# ändert das nichts (Ränge sind robust), es wirkt auf die angezeigten Gruppenwerte.
WINSOR_LOW = 0.01
WINSOR_HIGH = 0.99

# Mindestabdeckung für einen Gesamtscore. KEINE LITERATURVORGABE (Wunsch des Nutzers).
MIN_COVERAGE = 0.60
# Mindestanzahl Vergleichswerte, damit ein Perzentil sinnvoll ist. KEINE LITERATURVORGABE.
MIN_VALUES_FOR_PERCENTILE = 5

# ── Vergleichsgruppen ─────────────────────────────────────────────────────────
MIN_PEERS = 8               # Vorgabe des Nutzers
MAX_PEERS = 20              # begrenzt die Zahl der Abfragen
MIN_MARKET_CAP_USD = 1e9    # grob die Grösse von Index-Mitgliedern (SPI/STOXX 600/S&P 500); KEINE LITERATURVORGABE
OTC_EXCHANGES = {"PNK", "OQX", "OQB", "OEM", "OTC", "OTCM", "OBB"}  # ausserbörsliche Kopien ausschliessen
# Yahoos Screener-"Region" ist der Börsenplatz, nicht der Firmensitz. Deshalb wird
# zusätzlich das Sitzland geprüft und pro Firma die Heimatbörse bevorzugt.
PRIMARY_EXCHANGES = {
    "us": {"NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS"}, "ch": {"EBS"}, "de": {"GER"}, "fr": {"PAR"},
    "gb": {"LSE"}, "nl": {"AMS"}, "it": {"MIL"}, "es": {"MCE"}, "se": {"STO"}, "dk": {"CPH"}, "be": {"BRU"},
    "fi": {"HEL"}, "no": {"OSL"}, "at": {"VIE"}, "ie": {"ISE"}, "pt": {"LIS"}, "pl": {"WSE"},
}

EUROPE_REGIONS = ["ch", "de", "fr", "gb", "nl", "it", "es", "se", "dk", "be", "fi", "no", "at", "ie", "pt", "pl"]
COUNTRY_TO_REGION = {
    "United States": "us", "Switzerland": "ch", "Germany": "de", "France": "fr", "United Kingdom": "gb",
    "Netherlands": "nl", "Italy": "it", "Spain": "es", "Sweden": "se", "Denmark": "dk", "Belgium": "be",
    "Finland": "fi", "Norway": "no", "Austria": "at", "Ireland": "ie", "Portugal": "pt", "Poland": "pl",
    "Canada": "ca", "Japan": "jp", "Australia": "au",
}

# Marktindex für Beta, je nach Region
MARKET_INDEX = {"us": "^GSPC", "ch": "^SSHI", "europe": "^STOXX", "other": "^GSPC"}

# ── Finanzfirmen ──────────────────────────────────────────────────────────────
# Altman-Modelle wurden für Industrie-/Handelsfirmen entwickelt [ALT]; [NM]
# schliesst Finanzfirmen (SIC 6xxx) aus; [DAM]: Investitionen und Working Capital
# sind bei Banken/Versicherern kaum schätzbar, dort dominieren Kurs/Buchwert.
# → Für diese Branchen KEIN Gesamtscore, nur Teilinformationen.
FINANCIAL_INDUSTRY_KEYWORDS = ("Bank", "Insurance", "Capital Markets", "Asset Management",
                               "Financial Conglomerates", "Mortgage Finance", "Shell Companies")
# Für Finanzfirmen trotzdem angezeigte Kennzahlen (als Information)
FINANCIAL_INFO_METRICS = ["book_to_market", "earnings_yield", "mom_12_1", "volatility", "beta"]

# ── Piotroski: absolute Einordnung (zusätzlich zum Perzentil) ─────────────────
# [PIO]: "low F_SCORE" = 0 oder 1, "high F_SCORE" = 8 oder 9.
# (Abweichung vom ursprünglichen Vorschlag 0–2 rot: das Paper gilt.)
PIOTROSKI_LOW_MAX = 1
PIOTROSKI_HIGH_MIN = 8

# ── Altman: absolute Zonen (nur Anzeige, zusätzlich zum Perzentil) ────────────
# Original-Z für Industriefirmen [ALT]: unter 1.81 = Gefahrenzone; 1.81–2.67 =
# Grauzone ("zone of ignorance"); Trennwert 2.675. (Die oft zitierte 2.99 steht
# nicht im PDF.)
Z_DISTRESS_BELOW = 1.81
Z_SAFE_FROM = 2.675
# Z'' für Nicht-Industriefirmen [ALT]: Das PDF nennt keine Grenzwerte, nur die
# Rating-Tabelle für den EM-Score (= Z'' + 3.25). Gewählt (vom Nutzer bestätigt):
# grün ab BBB− (5.65), rot unter B− (3.75).
EM_SCORE_SAFE_FROM = 5.65
EM_SCORE_DISTRESS_BELOW = 3.75
# Branchen, die als "Industrie/Herstellung" gelten (Original-Z), sonst Z''.
MANUFACTURING_SECTORS = {"Industrials", "Basic Materials", "Consumer Cyclical", "Consumer Defensive",
                         "Energy", "Healthcare", "Technology"}
NON_MANUFACTURING_INDUSTRY_KEYWORDS = ("Software", "Internet", "Information Technology Services",
                                       "Retail", "Restaurants", "Services", "Travel", "Lodging",
                                       "Entertainment", "Advertising", "Staffing", "Consulting")

# ── Datenquellen ──────────────────────────────────────────────────────────────
# Die SEC verlangt eine Kontaktadresse im User-Agent. Sie steht privat in backend/.env
# (SEC_CONTACT_EMAIL=...), nicht im Code.
import os
from app import config as _config  # noqa: F401  (lädt die .env-Datei)
SEC_CONTACT_EMAIL = os.getenv("SEC_CONTACT_EMAIL", "")
SEC_USER_AGENT = f"Market Desk (private research tool) {SEC_CONTACT_EMAIL}".strip()
SEC_MAX_REQUESTS_PER_SECOND = 8   # SEC erlaubt max. 10/s – wir bleiben darunter
# Abweichung zwischen offiziellem Bericht und yfinance, ab der gewarnt wird. KEINE LITERATURVORGABE.
SOURCE_DEVIATION_WARN = 0.05

# Cache-Dauer (Sekunden)
CACHE_FUNDAMENTALS = 7 * 86400     # Bilanzdaten wöchentlich (früher, wenn neuer Bericht erscheint)
CACHE_FILINGS_INDEX = 86400        # Liste der SEC-Berichte täglich prüfen
CACHE_PEERS = 7 * 86400            # Vergleichsgruppen wöchentlich
CACHE_MARKET_STATS = 86400         # Momentum/Volatilität/Beta täglich
CACHE_INFO = 86400                 # Börsenwert, Branche
CACHE_FX = 86400
CACHE_RATES = 86400
CACHE_DAMODARAN = 30 * 86400       # erscheint jährlich (Januar)
CACHE_SUPPLY_CHAIN = 30 * 86400    # bzw. sofort neu, wenn ein neuer 10-K/20-F erscheint
