# Market Desk

Persönliches Finanz-Terminal als Mac-App – nur für diesen Mac, nichts wird veröffentlicht.

> **Keine Anlageberatung.** Alle Daten stammen von Yahoo Finance und können verzögert oder fehlerhaft sein.

---

## App starten

- **Programme-Ordner → „Market Desk“** doppelklicken, fertig.
- **Ins Dock legen:** App einmal starten, dann mit der rechten Maustaste (oder Ctrl-Klick) auf das Icon im Dock → **Optionen → Im Dock behalten**.
  Alternativ das Icon aus dem Programme-Ordner ins Dock ziehen.
- **Beenden:** Fenster schliessen oder ⌘Q. Dabei wird alles beendet, es läuft nichts im Hintergrund weiter.

Bedienung:
- `F1`–`F5` wechseln zwischen Startseite, News, Portfolio, Watchlist und Explorer.
- Irgendwo lostippen öffnet die Befehlszeile. Ticker **oder** Firmenname eingeben (z. B. „Nestle“) und Enter drücken.
- Auf der Startseite lassen sich Wertpapiere per Suche hinzufügen und mit ✕ entfernen.

---

## Nach einer Code-Änderung neu bauen

Im Finder den Ordner `market-desk` öffnen und **„App neu bauen.command“** doppelklicken.
Das Skript baut die Oberfläche, packt alles zusammen und ersetzt die App im Programme-Ordner (1–2 Minuten).

Beim allerersten Mal fragt macOS eventuell, ob die Datei geöffnet werden darf: Rechtsklick → **Öffnen**.

---

## Woher kommen die Daten?

| Was | Quelle | Aktualisierung / Cache |
|---|---|---|
| Kurse | Yahoo Finance (über die Python-Bibliothek `yfinance`) | automatisch alle 60 s, höchstens 60 s aus dem Zwischenspeicher |
| Kursverlauf (Chart) | Yahoo Finance, Tageskurse | bis 15 Min. Zwischenspeicher |
| Kennzahlen & Firmenprofil | Yahoo Finance | bis 24 Std. Zwischenspeicher |
| Nachrichten | Yahoo-Finance-Suche (Original-Links) | bis 10 Min. Zwischenspeicher |
| Suche | Yahoo-Finance-Suche + eigene Auswahlliste | bei jeder Eingabe |
| Bilanzzahlen für den Score | SEC EDGAR (10-K/20-F) → ESEF (filings.xbrl.org) → Yahoo | wöchentlich bzw. sobald ein neuer Bericht erscheint |
| Vergleichsgruppen | Yahoo-Screener (Branche + Region, ≥ 1 Mrd. USD) | wöchentlich |
| Branchenwerte | Damodaran Online (global) | monatlich geprüft, erscheint jährlich |
| Risikofreie Zinsen | FRED (USD, 3-Monats-T-Bill), SNB (SARON) | täglich |
| Lieferketten | SEC-Jahresberichte (eigener Bericht + Nennungen in fremden Berichten), ESEF | täglich geprüft, neu bei neuem Bericht |

So zeigt die App die Herkunft an:
- Bei jedem Kurs steht **Zeitpunkt laut Börse**, **Quelle** und gegebenenfalls **„aus Cache (Alter)“**.
- Schlägt eine Aktualisierung fehl, werden ältere Werte nur noch mit **„VERALTET“** angezeigt.
- Fehlen Daten ganz, steht **„Daten nicht verfügbar“**. Es werden nie Ersatzwerte erfunden.

**Grenzen der Daten:**
- Yahoo-Kurse sind je nach Börse **bis ca. 15 Minuten verzögert**, Kryptowährungen meist nahezu in Echtzeit.
- Yahoo Finance ist ein inoffizieller, kostenloser Dienst. Bei vielen Abfragen kann Yahoo vorübergehend sperren, oder Yahoo ändert seine Schnittstelle, sodass eine neuere `yfinance`-Version nötig wird.
- Kennzahlen (KGV, EV/EBITDA usw.) übernimmt die App so, wie Yahoo sie liefert. Einzelne Werte können fehlen oder abweichend berechnet sein.
- London-Kurse liefert Yahoo in Pence. Die App rechnet sie in Pfund (GBP) um.

---

## Eigener Score und Lieferketten

- Reiter **SCORE** auf jeder Aktienseite: Gesamtscore 0–100 aus vier Säulen (Qualität, Bewertung, Momentum, Sicherheit), jede Kennzahl mit Farbe, Tooltip (Begründung + Datenquelle) und Vergleichsgruppe.
  **Eigener Score auf Basis wissenschaftlicher Literatur – nicht validiert, keine Anlageempfehlung.**
- Erklärung jeder Kennzahl: **[SCORE_METHODIK.md](SCORE_METHODIK.md)**
- **Grenzwerte und Gewichte ändern:** `backend/app/scoring_config.py` (jede Zeile mit Kommentar und Quelle), danach „App neu bauen.command“.
- Reiter **LIEFERKETTE**: Netzwerk-Grafik nur mit belegten Verbindungen; Klick auf eine Linie zeigt Bericht, Abschnitt und Originalsatz.
- Die erste Berechnung einer Aktie dauert 5–40 Sekunden (Berichte der Vergleichsfirmen werden geladen), danach kommt sie aus dem Zwischenspeicher.

## Privatsphäre & Sicherheit

- Der eingebaute Server lauscht **nur auf 127.0.0.1**, ist also nur von diesem Mac aus erreichbar, nicht im WLAN.
  Der Port wird bei jedem Start automatisch frei gewählt.
- API-Keys gehören in `backend/.env` (Vorlage: `backend/.env.example`). Diese Datei steht in `.gitignore` und wird nie in Git gespeichert.
  Nach einer Änderung „App neu bauen.command“ ausführen, damit die App die Keys bekommt.
- Deine Daten (Watchlist, Portfolio, Alarme) liegen in `~/Library/Application Support/Market Desk/market_desk.db`.
- Das Protokoll (bei Problemen) liegt in `~/Library/Logs/Market Desk/market-desk.log`.

---

## Aufbau (für Entwickler)

```
market-desk/
├── App neu bauen.command   Doppelklick: App bauen und installieren
├── backend/                Python (FastAPI): Datenabfrage, Datenbank
│   └── app/
│       ├── services/market_data.py   Kurse, Verlauf, Kennzahlen (yfinance) + Cache
│       ├── services/news_service.py  Nachrichten
│       └── routers/                  Schnittstellen für die Oberfläche
├── frontend/               Oberfläche (React + TypeScript)
└── desktop/
    ├── market_desk.py      Startpunkt der App (Server + Fenster)
    ├── market_desk.spec    Bauplan für PyInstaller
    └── make_icon.py        zeichnet das App-Icon
```

Entwicklungsmodus ohne App-Bau (zwei Terminal-Fenster):

```bash
cd backend && .venv/bin/python run.py
```

```bash
cd frontend && npm run dev
```

Danach http://localhost:5173 öffnen.
