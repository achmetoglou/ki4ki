# Abgleich T4 (Testserver, Juli–August) ↔ A40-Paket — Stand 26.08.2026

Anlass (Emrach): „Das ist blöd, dass wir alles auf der T4 gemacht haben und auf der A40
plötzlich alles weg ist." Deshalb hier, **nur gelesen** auf der T4 (`~/ki4ki`, Container,
Cron, n8n-Exporte, Workspace-Einstellungen per API) gegen den Stand dieses Repos.

## Ergebnis in einem Satz

Der **Code** ist im Paket vollständig und neuer als auf der T4 (jede Funktion des T4-Proxys und
des T4-Assistenten existiert hier; dazu ~30 Funktionen mehr). **Verloren gegangen sind keine
Programme, sondern vier Dinge daneben:** ein gemessener Einstellwert, eine Datenregel für Excel,
zwei Prüfwerkzeuge — und die Daten/Prompts der T4, die nie ins Paket gehörten.

## Was geprüft wurde

| Ebene | T4 | Paket | Befund |
|---|---|---|---|
| Proxy-Funktionen (`pruef_proxy.py`) | 5 080 Zeilen, 130 Funktionen | 7 900 Zeilen, 173 Funktionen | T4 ⊂ Paket, **nichts fehlt** |
| Assistent (`assistent.py`) | 1 988 Zeilen, 53 Funktionen | 2 866 Zeilen | T4 ⊂ Paket, **nichts fehlt** |
| Aufnahme-Module | mk_md, pdfstelle, seiten_echt, vorspann_finden, bildbeschreibung, namen, abbildung | alle vorhanden | ✅ |
| n8n-Workflows | 8 Exporte (Duplikate/Backups), 3 Namen | dieselben 3, weiterentwickelt | ✅ |
| Container | ollama, nothink, docling, tika, n8n, anythingllm, pruef-proxy, mkmd, **office** | dito, **office seit heute** (`e7d09d2`) | ✅ |
| Routen des Proxys | /stelle /seitenbild /abbildung /pdf /protokoll(+2) /pruef-status /pruef-strom-test | dieselben + **/kpi /rueckmeldungen** | ✅ |
| Wortlisten | `wortlisten.txt` | gleich bis auf Beispielkennungen | ✅ |
| Systemprompt | je Bereich 4 500–6 200 Zeichen (Kern + Rolle), nur in der T4-Datenbank | `systemprompt.txt` (144 Zeilen), für neue Bereiche | ⚠ siehe D2 |
| Neustart/Wächter | `waechter.sh`, `zyklus.sh`, `nach_neustart.sh` (Host-Prozesse, @reboot) | `restart: unless-stopped` + n8n-Takt + Proxy-Wache (Löschen, Einräumen, Bereiche) | ✅ ersetzt, nicht verloren |

## Lücken — nach Gewicht

### L1 · topN 6 statt 25 (gemessener Wert verloren) — **hoch, 5 Minuten**
Auf der T4 wurde am 04.08. gemessen (5 Fragen × 5 Fassungen): **topN 25 gewinnt** gegen 9 und
100 (mehr Inhalt, 100 kostet nur Zeit). Alle produktiven T4-Bereiche stehen auf **25**
(ikv-wissen-konfidenz, auw, kap; heute per API gelesen). Das Paket setzt für **jeden neuen
Bereich topN 6** (`arbeitsbereich_anlegen.sh`, `GEPRUEFT_WERTE` im Proxy, seit Commit
`14b5509` vom 13.08.) — ohne Messung. Temperatur 0,3 statt 0,2 ebenso.
→ **Empfehlung:** 25 / 0,2 übernehmen; bestehende A40-Bereiche einmalig nachziehen (Proxy fasst
bestehende Bereiche absichtlich nie an).

### L2 · Excel: interne Spalten landen im Text — **hoch, 10 Minuten**
T4 `xlsx_fragen.py` ließ Spalten mit „Kommentar / Notiz / Anmerkung / intern" weg (Emrachs
Auftrag Ende Juli: Arbeitsnotizen gehören nicht in eine Antwort an einen Prüfling). Der neue
Knoten „Nicht-PDF vereinheitlichen" übernimmt **alle** Spalten — in der AuW-Excel steht in
Spalte H z. B. „Fragen zur Wärmebehandlung würde ich rauslassen …".
→ **Empfehlung:** dieselbe Ausschlussliste im Knoten (und im Prüfungskatalog-Parser).

### L3 · `wegabgleich.py` fehlt (Rechteprüfung je Ausgabeweg) — **hoch für die Auslieferung**
Bedingung A2 der Auslieferungssperre: Ein Syntaxbaum-Test prüft, dass **jeder** Weg nach draußen
an `bereich_sichtbar / erlaubte_dokumente / dokument_erlaubt / darf_sehen` vorbeiführt — mit
Gegenprobe (Prüfung entfernt → Test rot). Auf der T4 liegt er in `reextract/archiv/pruefwerkzeug/`,
im Paket gibt es ihn nicht. Seit dem 13.08. kamen hier **neue Wege** dazu (`/kpi`,
`/rueckmeldungen`, `/pdf` für Excel, Gesprächswerkzeuge) — genau der Fall, für den der Test gebaut
wurde. Das Rechteloch ist zweimal auf diese Weise entstanden.
→ **Empfehlung:** portieren und in `dialogtest.py` (vor jedem Push) einhängen.

### L4 · Selbstcheck (`selbstcheck.py` + Ampel-Bericht) — **mittel**
Rotierende Fragen aus dem eigenen Bestand + feste Härtefälle, mechanisches Urteil (deckt der
Beleg die Aussage? Bestandsfrage → Liste?), Ampel als HTML/PDF. Für Partner gedacht („arbeitet
die Anlage noch richtig?"). Im Paket: `dialogtest`/`absichttest` (Entwicklertests) und `/kpi`
(Betriebszahlen), aber kein Selbstcheck gegen den **eigenen** Bestand.
→ Portieren, sobald L1–L3 stehen.

### L5 · Grafikkarte-Wächter — **mittel**
T4 `waechter.sh` erkannte `ollama_auf_cpu` (Treiber weg → Ollama rechnet still auf CPU, alles
10× langsamer) und `docling_laeuft`. Das Paket meldet das nirgends.
→ `/pruef-status` um `ollama /api/ps` (VRAM-Anteil je Modell) erweitern; Warnung im Log.

### L6 · Dokument-Version ersetzen — **mittel**
T4 `ersetzen.py`: austragen, löschen, neu hochladen, einbetten — ein Befehl. Paket: zweite Fassung
gleichen Namens wird **aussortiert** mit Hinweis („erst löschen, dann hochladen"), also zwei
Handgriffe (loeschen/ → input/).
→ Option: Ordner `ersetzen/` — legt die neue Fassung hinein, die Wache tauscht.

### L7 · Schriftmüll-Aussortierung — **niedrig**
T4 `aussortieren.py` warf Dokumente mit defekter Schrift (`.notdef`, `g39g76…`) aus dem Bereich.
Paket: `veredeln.py` filtert solche Zitate, die Aufnahme sortiert das Dokument aber nicht aus.

### L8 · Dokumentation nicht im Repo — **niedrig**
Schaubilder (`KI4KI_Ablauf.html`, `KI4KI_Verarbeitung.html`), `KI4KI_Funktionsweise_Wartung.pdf`,
`KI4KI_Bausteine_38_aktive.pdf`, `KI4KI_Selbstcheck.pdf` liegen auf T4/Nextcloud. Inhaltlich
teils überholt (7-Fälle-Router → Stufe 1/2).

## Daten — keine Lücke des Pakets, aber eine Entscheidung

| | T4 | A40 |
|---|---|---|
| Dokumente | **1 263** im Bestand, 1 266 PDFs (ikv-wissen-konfidenz, auw, kap …) | 19 (wissensdatenbank) + 8 (auw) |
| Katalog | `bestandsindex.json`, 1 285 Einträge aus `METADATEN.KORRIGIERT.xlsx` (Titel, Verfasser, Jahr, Schlagworte) | wird je Dokument vom Deckblatt gelesen |
| Prompts | je Bereich gepflegt (Kern + Rolle), nur in der T4-Datenbank | `systemprompt.txt` |

**D1** Der kuratierte Katalog ist wertvoll (Schlagworte, korrigierte Verfasser) und lässt sich
1:1 nach `/daten/pruefung/bestandsindex.json` übernehmen — sobald dieselben Dokumente auf der
A40 liegen. **D2** Die Bereichs-Prompts der T4 (auw 5 857 Z., kap 4 558 Z.) per API exportieren
und auf der A40 mit `prompt_aktualisieren.sh` einspielen. **D3** Massenübernahme der 1 263
Dokumente: als PDFs nach `dokumente/<bereich>/input/` (Aufnahme ~2 min je 100 Seiten mit
GPU-OCR) — oder Volumes kopieren (schneller, aber alte Einbettung).

## Was auf der T4 bleibt und NICHT ins Paket gehört
`schaufenster.py` (Demo-Oberfläche 8099 — die Oberfläche ist heute AnythingLLM selbst),
`frage.py` (Kommandozeile), `breite_messen.py`, `bildtest.*` (Messungen), `gegentest-durchreiche`
(socat für A/B-Tests), `phase1/2/3`, `extract*`, `zyklus*`, `batch.sh`, `one.sh`, `tag.sh`
(Skript-Kette, durch n8n ersetzt), `fix_*` (einmal gelaufen), `bauen.sh` (baute `partner/`, das
heute dieses Repo ist).

## Reihenfolge
1. L1 + L2 (heute, klein) → 2. L3 (vor der nächsten Auslieferung) → 3. L5 → 4. L4 → 5. L6/L7 →
Daten D1–D3 nach Emrachs Entscheidung.
