# Score-Methodik von Market Desk

> **Eigener Score auf Basis wissenschaftlicher Literatur. Nicht validiert, keine Anlageempfehlung.**
> Alle Gewichte und Grenzwerte stehen in `backend/app/scoring_config.py`.

## Die Idee in drei Sätzen

Eine Aktie wird nicht mit festen Grenzwerten beurteilt, sondern **mit ähnlichen Firmen verglichen** (gleiche Branche, möglichst gleiche Region).
Für jede Kennzahl wird bestimmt, wie viel Prozent der Vergleichsfirmen schlechter sind (**Perzentil**, 0–100).
Diese Perzentile werden zu vier **Säulen** gemittelt: Qualität, Bewertung, Momentum, Sicherheit. Die vier Säulen ergeben gleich gewichtet den **Gesamtscore**.

Warum gerade diese vier? Die Literatur zeigt, dass profitable und solide Firmen (*Qualität*, [NM], [QMJ]), günstig bewertete Firmen (*Value*, [AMP]) und Aktien mit guter Kursentwicklung im letzten Jahr (*Momentum*, [AMP]) im Durchschnitt höhere Renditen hatten. Die Replikationsstudie [JKP] bestätigt die meisten dieser Faktor-Themen, nämlich 11 von 13 Themen mit über 50 % Replikationsrate.

## Quellen (PDF-Ordner)

| Kürzel | Paper |
|---|---|
| [NM] | Novy-Marx (2010): *The Other Side of Value – The Gross Profitability Premium* |
| [QMJ] | Asness, Frazzini, Pedersen: *Quality Minus Junk* |
| [AMP] | Asness, Moskowitz, Pedersen (2013): *Value and Momentum Everywhere* |
| [ALT] | Altman (2000): *Predicting Financial Distress – Revisiting the Z-Score and ZETA Models* |
| [PIO] | Piotroski (2000): *Value Investing – The Use of Historical Financial Statement Information* |
| [DAM] | Damodaran (2006): *Valuation Approaches and Metrics – A Survey* |
| [JKP] | Jensen, Kelly, Pedersen: *Is There a Replication Crisis in Finance?* |

## Ablauf der Berechnung

1. **Vergleichsgruppe bilden:** Firmen mit gleicher Yahoo-Branche, Börsenwert ≥ 1 Mrd. USD, Firmensitz in der Region und nur mit der Listung an der Heimatbörse. Mit Stufen:
   - Branche im Land
   - Branche in Europa bzw. den USA
   - Branche in Europa + USA
   - breiterer Sektor

   Die erste Stufe mit mindestens 8 Firmen gewinnt (maximal 20). Gibt es weniger, wird das angezeigt, und Damodarans Branchenwerte dienen als Referenz.
2. **Kennzahlen berechnen:** Für die Aktie **und** jede Vergleichsfirma gelten dieselben Formeln, auf Basis des letzten Geschäftsjahres.
3. **Perzentil:** Anteil der Vergleichsfirmen, die schlechter abschneiden. Ein Gleichstand zählt halb. Bei Kennzahlen, bei denen „tief = gut“ gilt, wird umgedreht. Es braucht mindestens 5 Vergleichswerte.
4. **Farben:** grün = oberes Drittel (≥ 66,7), gelb = mittleres Drittel, rot = unteres Drittel (< 33,3), grau = keine Daten oder nicht anwendbar. Die Drittel entsprechen den Portfolios P1/P2/P3 in [AMP].
5. **Säule:** Durchschnitt der verfügbaren Perzentile ihrer Kennzahlen.
6. **Gesamtscore:** gleich gewichteter Durchschnitt der Säulen (je 25 %). Fehlt eine Säule, werden die Gewichte auf die übrigen verteilt.
7. **Datenabdeckung:** Anteil der Kennzahlen mit Wert. **Unter 60 % gibt es keinen Gesamtscore** („Nicht genug Daten“).

**Ausreisser:** Kappung am 1. und 99. Perzentil. Für die Rangbildung selbst ändert das nichts, weil Ränge robust sind. Es wirkt auf die angezeigten Gruppenmediane.

**Kein Overfitting:** Weder Gewichte noch Grenzen wurden anhand vergangener Renditen gewählt.

## Die Kennzahlen

### Säule 1 – Qualität

| Kennzahl | Formel | Richtung | Begründung | Bekannte Schwächen |
|---|---|---|---|---|
| Bruttogewinn / Total Assets | (Umsatz − Herstellkosten) / Total Assets | hoch = gut | [NM]: hat etwa dieselbe Prognosekraft wie Buchwert/Marktwert; Teil von [QMJ] | Firmen ohne „Herstellkosten“ (Banken, Teile von Software) sind schlecht vergleichbar |
| Eigenkapitalrendite (ROE) | Reingewinn / Eigenkapital | hoch = gut | [QMJ] Profitability | Bei sehr kleinem Eigenkapital (z. B. durch Aktienrückkäufe) extrem hoch, etwa Apple über 150 %; negatives Eigenkapital → nicht berechnet |
| Gesamtkapitalrendite (ROA) | Reingewinn / Total Assets | hoch = gut | [QMJ] Profitability | Einmaleffekte im Reingewinn verzerren |
| Schwankung der Bruttomarge | Standardabweichung der Bruttomarge, letzte 3–5 Jahre | tief = gut | [ALT] ZETA-Variable „Stability of earnings“; [QMJ] EVOL | Nur 3–5 Datenpunkte, Yahoo liefert oft nur 4 Jahre |
| Piotroski F-Score | Summe von 9 Ja/Nein-Signalen (siehe unten) | hoch = gut | [PIO] | Entwickelt für **günstig bewertete** Firmen (hohes B/M); Signal „keine neuen Aktien“ nur über die Aktienzahl angenähert |

**Die 9 Piotroski-Signale** [PIO], je 1 Punkt:
1. ROA > 0
2. Operativer Cashflow > 0 (beides bezogen auf das Gesamtvermögen am Jahresanfang)
3. ROA gestiegen
4. Cashflow > Gewinn (Accruals)
5. Verschuldung gesunken (langfristige Schulden / Ø Gesamtvermögen)
6. Liquidität (Current Ratio) gestiegen
7. Keine neuen Aktien ausgegeben
8. Bruttomarge gestiegen
9. Kapitalumschlag gestiegen

Dafür braucht es drei Geschäftsjahre. Zusätzlich gibt es eine **absolute Einordnung** nach dem Paper: 0–1 = tief (rot), 8–9 = hoch (grün). Dein ursprünglicher Vorschlag war 0–2 rot. Hier gilt das Paper.

### Säule 2 – Bewertung (immer relativ zur Vergleichsgruppe)

| Kennzahl | Formel (angezeigt / gerechnet) | Richtung | Begründung | Bekannte Schwächen |
|---|---|---|---|---|
| EV/EBITDA | angezeigt EV/EBITDA, gerechnet EBITDA/EV; EV = Börsenwert + Finanzschulden − flüssige Mittel | günstig = gut | [DAM]: eines der meistgenutzten Multiples, Vergleich mit Branchenfirmen | Leasingverbindlichkeiten nicht enthalten; für Banken sinnlos |
| Kurs-Buchwert (KBV) | angezeigt KBV, gerechnet Buchwert/Marktwert | günstig = gut | [AMP]: Value = BE/ME | Viele immaterielle Werte (Marken, Software) stehen nicht in der Bilanz |
| Free-Cash-Flow-Rendite | (operativer Cashflow − Investitionen) / Börsenwert | hoch = gut | [DAM] Cashflow-Multiples; Free Cashflow wie [NM] | Investitionen schwanken stark von Jahr zu Jahr |
| Gewinnrendite (E/P) | Reingewinn / Börsenwert | hoch = gut | [DAM]: Kehrwert des KGV, bleibt bei Verlusten sortierbar | Einmaleffekte |

*Warum Kehrwerte?* Bei Verlusten wird ein KGV negativ und lässt sich nicht mehr sinnvoll sortieren. Der Kehrwert E/P bleibt eine durchgehende Skala.
*Warum gilt „günstig = gut“?* [AMP] findet für günstige Aktien höhere Durchschnittsrenditen. [QMJ] warnt aber: Günstig ist oft „Junk“. Deshalb gibt es die Qualitätssäule daneben.

### Säule 3 – Momentum

| Kennzahl | Formel | Richtung | Begründung | Bekannte Schwächen |
|---|---|---|---|---|
| 12-1-Momentum | Kursrendite (inkl. Dividenden) von vor 12 Monaten bis vor 1 Monat | hoch = gut | [AMP] MOM2–12: Der letzte Monat wird ausgelassen, weil sich kurzfristige Bewegungen oft umkehren | Momentum kann abrupt drehen (Crashes); nur eine Kennzahl in der Säule |

Die 6-Monats-Rendite wird nur zur Information angezeigt.

### Säule 4 – Sicherheit („Safety“ nach [QMJ])

| Kennzahl | Formel | Richtung | Begründung | Bekannte Schwächen |
|---|---|---|---|---|
| Altman Z-Score | 1,2·WC/TA + 1,4·RE/TA + 3,3·EBIT/TA + 0,6·Börsenwert/Verbindlichkeiten + 1,0·Umsatz/TA | hoch = gut | [ALT]; so auch in [QMJ] Safety | Für Industriefirmen der 1960er-Jahre entwickelt; Gewinnreserven (RE) fehlen bei manchen Berichten |
| Verschuldung | Finanzschulden / Total Assets | tief = gut | [QMJ] LEV | **[JKP]: Das Thema „low leverage“ repliziert nicht** – schwächster Baustein |
| Kursschwankung | Standardabweichung der Tagesrenditen, 1 Jahr, annualisiert | tief = gut | Volatilitätsteil der Beta-Schätzung in [QMJ]; [JKP]: Thema „low risk“ repliziert | Ein einziges unruhiges Jahr prägt den Wert |
| Beta | Korrelation (überlappende 3-Tages-Renditen, 5 Jahre) × Volatilität Aktie / Volatilität Index (je 1 Jahr) | tief = gut | [QMJ] BAB nach Frazzini/Pedersen | Ohne Schrumpfung Richtung 1; Index je Region: S&P 500, SPI, STOXX 600. Beispiel: Nestlé hat Beta ≈ 1,1, weil die Aktie zuletzt fast doppelt so stark schwankte wie der SPI |

**Absolute Altman-Zonen** (Zusatzanzeige):
- **Industriefirmen**, Original-Z: unter 1,81 rot, 1,81–2,675 gelb, ab 2,675 grün [ALT]. Die oft zitierte Grenze 2,99 steht nicht im PDF.
- **Nicht-Industriefirmen**, Z'' als EM-Score (= Z'' + 3,25): grün ab 5,65 (entspricht Rating BBB−), rot unter 3,75 (schlechter als B−) – Rating-Tabelle in [ALT].

## Banken und Versicherungen

Für Banken und Versicherungen gibt es **keinen Gesamtscore**. Die Begründung:
- Die Altman-Modelle wurden für Industrie- und Handelsfirmen gebaut [ALT].
- [NM] schliesst Finanzfirmen aus.
- [DAM]: Investitionen und Working Capital sind bei Banken kaum schätzbar, dort dominiert Kurs/Buchwert.

Angezeigt werden nur KBV, E/P, Momentum, Volatilität und Beta, jeweils im Vergleich zu anderen Banken.

## Datenquellen und Reihenfolge

1. **SEC EDGAR** (offizielle 10-K/20-F-Zahlen, inkl. Einreichungsdatum)
2. **ESEF-Jahresbericht** (filings.xbrl.org; NL, FR, DK, FI u. a., keine deutschen Firmen)
3. **Yahoo Finance** für alle übrigen Firmen, z. B. Nestlé

Fehlt im offiziellen Bericht ein Posten (z. B. bei Novartis die Abschreibungen), wird er aus Yahoo ergänzt und **gekennzeichnet**. Weichen Bericht und Yahoo um mehr als 5 % ab, erscheint ein Hinweis.

Weitere Quellen:
- **Kurse:** Yahoo Finance.
- **Branchenwerte:** Damodaran (global, feste Zuordnungstabelle).
- **Risikofreie Zinsen:** FRED (USD) und SNB (SARON).

**Wichtig beim Vergleich:** Vergleichsfirmen kommen teils aus der SEC, teils von Yahoo. Firmen mit 20-F-Bericht melden teils nach **US-GAAP**, teils nach **IFRS**. Beispiel ASML: Die SEC-Zahlen (US-GAAP) weichen vom europäischen Bericht (IFRS) ab.

## Was der Score nicht ist

- **Nicht validiert:** Es gab keinen Rückblick-Test mit diesem genauen Score.
- **Nicht vergleichbar mit den Papers:** Die Papers sortieren Tausende Firmen und messen Portfoliorenditen. Hier wird *eine* Firma mit 8–20 anderen verglichen.
- **Kleine Gruppen:** Mit 8–20 Vergleichsfirmen sind Perzentile grob. Ein einziger Rang bewegt den Wert um 5–12 Punkte.
- **Faktorprämien sind kleiner geworden:** Nach Veröffentlichung sind sie deutlich gesunken. [JKP] zitiert „58 % lower post-publication“.

## In 30 Sekunden erklärt (für das Gespräch)

> „Ich vergleiche eine Aktie mit 8 bis 20 ähnlichen Firmen aus derselben Branche und Region. Für zwölf bis dreizehn Kennzahlen aus vier Bereichen, die in der Forschung belegt sind – Qualität nach Novy-Marx und Asness, Bewertung, Momentum nach Asness/Moskowitz/Pedersen und Sicherheit inklusive Altman-Z – rechne ich aus, wie viel Prozent der Vergleichsfirmen schlechter sind. Die vier Bereiche gewichte ich gleich, ohne Optimierung auf vergangene Renditen. Wo Daten fehlen, sinkt die ausgewiesene Datenabdeckung; unter 60 % gibt es keinen Score. Banken bekommen bewusst keinen Gesamtscore, weil die Modelle für sie nicht gemacht sind.“
