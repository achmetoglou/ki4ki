# KI4KI — Innenansicht für Entwickler

Wie die Anlage arbeitet, wo was steht und wie man prüft, dass sie noch richtig
arbeitet. Bedienung: [`README.md`](../README.md) · Betrieb: [`BETRIEB.md`](BETRIEB.md).

## 1 · Aufbau

```
Frage ──► Prüf-Proxy (3001) ──► AnythingLLM (Suche, Oberfläche) ──► Ollama/Gemma (über nothink-proxy)
              │                                                              │
              └──── Wächter, Werkzeuge, Belegprüfung gegen das Original ◄────┘
                                        │
                                   Antwort mit Beleg, Link, gelber Markierung
```

AnythingLLM bleibt unverändert und hat keine eigene offene Tür. Der Prüf-Proxy
(`pruef-proxy/pruef_proxy.py`) sitzt davor, reicht die Oberfläche durch, hängt
eigene Skripte ein (Formularfelder, Daumen runter, Quellen unter der Antwort) und
beantwortet einen Teil der Anfragen selbst.

**Das Gespräch** läuft in zwei Stufen (`KI4KI_ABSICHT_MODELL`, `KI4KI_GESPRAECH`):

1. **Absicht** (`absicht.py`): Das Modell bekommt die letzten Züge, den Faden-Zustand
   (aktuelles Dokument) und die Dokumentliste des Bereichs und antwortet mit
   erzwungenem JSON — Aktion, Dokument, umformulierte Frage, Sicherheit. Unter 0,6
   Sicherheit folgt eine Klärfrage mit Optionen. Regel-Wächter bleiben davor hart:
   Beschwerde, Export, Fragen an die Anlage selbst, genanntes Dokument muss im
   Katalog existieren.
2. **Gespräch mit Werkzeugen** (`gespraech.py`): Das Modell ruft Proxy-Funktionen auf
   (Seiten lesen, Abbildungen auflisten und zeigen, zusammenfassen, zählen, Bestand,
   Dokument finden, Abkürzung, exportieren, Prüfungsfrage), höchstens 24 Schritte, nur
   lesend. Wächter holen Belege vorab selbst; jede Aussage mit `(Kennung, S. n)` wird
   per Wortdeckung gegen die Seite geprüft, wörtliche Zitate werden geprüft und
   verlinkt, erfundene Bildnummern gestrichen. Textlich geschriebene Werkzeugaufrufe
   werden erkannt und ausgeführt.

**Deterministische Wege vor dem Modell** (im Proxy, ohne Modell): Bestandsliste,
Kategorien-Abfragen, Prüfungskatalog, Dokument-Fakten (Seiten, Abbildungen,
Verfasser, Jahr), Vergleich-Vorbereitung, Bild-Weg, Rollen-Einrichtung, Feedback —
und der **leere Bereich** (`_leerer_bereich`): ohne Dokumente kein Stufe-1/2-Durchlauf,
im Chat-Modus eine direkte Modellantwort mit einer Kennzeichnung, im Abfrage-Modus der
Hinweis, wie der Bereich gefüllt wird.
Fällt das Modell aus, greift der alte Regel-Router (`assistent.py`).

## 2 · Was die Aufnahme je Dokument ablegt

Die Textfassung (Markdown, `mkmd-dienst/mk_md.py`) beginnt mit einem Kopf:
Quelle, Dokumenttyp, Sprache, Domain/Subdomain, `Kategorie (Vorgabe)` und
`Themen (Vorgabe)` aus dem Ordnerpfad, Abschnitte Tags/Keywords/Methoden und eine
Kurzfassung (2–3 Sätze). Docling-Bildklassen (Logo, Diagramm, Zeichnung, Foto)
stehen an jeder Abbildungsstelle.

**Kategorie** (`kategorie.py`): 16 Standardkategorien mit deutschen und englischen
Stichwörtern, je Bereich überschreibbar in `kategorien.txt`. Vorrang: von Hand
gesetzt > Ordner-Vorgabe > Kennung (DS-/BS-/M-) > Prüfungskatalog erkannt >
Dokumenttyp der Aufnahme > Titel > Dateiname/Tags; bei mehreren Treffern gewinnt das
längste Stichwort. Kein Modellaufruf.

**Katalog** (`bestand.py`, `bestandsindex.json` im Volume `pruefdaten`): Kategorie,
Themen, Sprache, Gebiet, Methoden und Kurzfassung liest der Proxy ohne Modell aus dem
Kopf; Titel, Verfasser und Jahr liest das kleine Modell aus dem Inhalt (nicht aus dem
Kopf — sonst wird der Dateiname zum Titel). Englische Themen älterer Einträge
werden beim Nachtragen eingedeutscht. Von Hand: „Kategorie von X ist Y" im Chat.

**Prüfungskatalog** (`pruefungskatalog.py`): erkennt Excel-Tabellen mit
`Frage | Antwort richtig | Antwort falsch …` und gescannte Kataloge mit a)/b)/c);
stellt Fragen wörtlich, mischt die Optionen, prüft die Antwort gegen den Katalog,
merkt sich je Faden, was schon gestellt wurde. Ohne Lösungsspalte kein Urteil.

**Seiten** (`_seitentexte_pdf`): Textebene per `pdftotext`; nur Scans (unter 60
Zeichen je Seite) werden über die OCR-Fassung gelesen — nie gemischt, sonst landen
OCR-Seitennummern auf falschen physischen Seiten.

**Namensvergleich** (`_loesch_grund`): rechnet wie AnythingLLM und der
Dubletten-Filter in n8n — NFKD, Umlaute zu Grundbuchstaben, ß → ss, dann nur
`a-z0-9`. Jede andere Rechnung lässt Dateien mit Umlauten im Eingang liegen.

## 3 · Rolle und Einstellwerte je Bereich

Der Prompt eines Bereichs = **Kern** (`systemprompt.txt`, für alle gleich:
Belegpflicht, Zitierform, Verbote) + **Rolle** (`dokumente/<bereich>/prompt.md`).
`rolle.py` baut die Rolle aus drei Feldern (Fachgebiet, wer fragt, Besonderes);
das Modell glättet den Absatz ohne neue Fakten (`KI4KI_ROLLE_GLAETTEN`). Quellen der
Rolle: Formular „Neuer Arbeitsbereich", Chat-Einstellungen des Bereichs (die
Oberfläche ist die Wahrheit), Chat „Rolle einrichten", `arbeitsbereich_anlegen.sh`,
oder die Datei selbst. Der Proxy spielt Änderungen alle 5 Minuten in AnythingLLM ein.

Geprüfte Werte für neue Bereiche (`GEPRUEFT_WERTE`): topN 25, Schwelle 0,25,
Temperatur 0,2, Verlauf 20, Modus `query`. Gemessen: 25 Textstellen liefern mehr
Inhalt als 9, 100 bringen nur Wartezeit. Bestehende Bereiche fasst die Anlage nie
an — `bereiche_nachziehen.sh` holt sie einmalig nach. Modi: Abfrage = `query`,
Chat = `chat` (Allgemeinwissen sichtbar getrennt), Vertreter = `automatic` (ohne
Quellen, nicht empfohlen).

Drei Einstellungen, an denen die Belegprüfung hängt und die im Betrieb nicht
auffallen: Kontextfenster `OLLAMA_MODEL_TOKEN_LIMIT` 65536 (sonst werden
Fundstellen still abgeschnitten), Modus `query` (in `automatic` antwortet AnythingLLM
ohne Quellen; zusätzlich `PROVIDER_DISABLE_NATIVE_TOOL_CALLING=ollama`), und der
Kern-Prompt (die Zitierform entsteht nur dort). Neue Bereiche bekommen alle drei
automatisch (`KI4KI_BEREICH_HEILEN`).

## 4 · Rechte

Vier Prüfungen: `bereich_sichtbar` (liefert AnythingLLM diesen Bereich für diese
Anmeldung?), `erlaubte_dokumente`, `dokument_erlaubt`, `darf_sehen`. Die Dokumentmenge
einer Chat-Anfrage liefert `namen_der_anfrage`: die Dokumente des Bereichs der Anfrage
(`titel_im_bereich`, `[]` = bekannt und leer); nur bei unbekanntem Bereich (`None`) die
kontoweite Menge. Zwei Mengen, zwei Zwecke: `erlaubte_dokumente` ist ein Recht (darf
diesen Beleg-Link öffnen), `namen_der_anfrage` ist der Gegenstand (woraus antwortet
dieser Bereich).

Jeder Weg, der Daten ausgibt, muss an einer der vier Prüfungen vorbei. `wegabgleich.py` prüft das im
Syntaxbaum, mit Gegenprobe (eine Prüfung entfernt → rot); Verteiler zählen nie als
Prüfung. Das Konto einer Anfrage kommt aus der Anmeldungs-Kopfzeile oder — im
Browser-Tab ohne Kopfzeile — über die Marke im Cookie (`konto_aus_anfrage`); eine
mitgeschickte, aber unbestätigte Kopfzeile wird abgewiesen.

## 5 · Prüfen, dass es noch stimmt

| Werkzeug | Was es prüft | Wann |
|---|---|---|
| `python3 pruef-proxy/dialogtest.py` | 33 Szenarien, 352 Prüfungen ohne Modell: Router, Faden, Prüfungskatalog, Rolle, Kategorien, Rechte je Ausgabeweg, Aufnahme-Übersicht | vor jedem Push |
| `python3 pruef-proxy/wegabgleich.py` | Rechteprüfung an jedem Ausgabeweg (Teil von dialogtest) | vor jedem Push |
| `docker exec ki4ki-pruef-proxy python3 /app/absichttest.py` | 32 echte Dialogzüge gegen das Absichts-Modell, Bedingung ≥ 90 % | nach Modell-/Prompt-Änderung |
| `docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py [bereich] [n]` | Zufallsfragen aus dem eigenen Bestand, mechanisches Urteil, Ampel unter `/selbstcheck` | im Betrieb |
| n8n-Ablaufpläne | `1_KI4KI-Masse-Ingest.json`, `2_Dateien-in-JSON-umwandeln.json`, `3_Markdown-Datei-erzeugen.json` — nach Änderung Verbindungen und Erreichbarkeit prüfen | bei Änderung |

Fehlerpfade in den Ablaufplänen stehen bewusst auf „bei Fehler weitermachen", damit
ein kaputtes Dokument nicht den Durchgang mit 25 Dateien abbricht — deshalb zeigt
n8n grün, und die Wahrheit steht in `aussortiert.log` und auf `/kpi`.

## 6 · Module

| Datei | Aufgabe |
|---|---|
| `pruef-proxy/pruef_proxy.py` | Der Kern: einzige Tür, Wege, Belegprüfung, Rechte, Wachen (Löschen, Einräumen, Bereiche, Rolle, GPU) |
| `assistent.py` | Regel-Router, Faden-Gedächtnis, Bestandsliste, Index-Tabelle |
| `absicht.py` / `gespraech.py` | Stufe 1 (Absicht) / Stufe 2 (Werkzeuge, Wächter, Belege) |
| `mehrstufig.py` | Zusammenfassung in mehreren Durchgängen — das ganze Dokument wird gelesen, nicht ein Ausschnitt |
| `namen.py` | Dokumentnamen säubern, bevor sie in die Anlage kommen (Sonderzeichen, Umbenennungen durch die Oberfläche) |
| `bestand.py` / `kategorie.py` | Katalog nachtragen / Kategorien und Themen |
| `pruefungskatalog.py` | Prüfungsfragen aus Katalogen |
| `fadenfrage.py` | Seitenwahl im Faden-Dokument, Abbildungen und Bildarten |
| `rolle.py` | Rolle je Bereich, Modi, Formularfelder |
| `stoerfall.py` / `metadaten.py` | Störfall-Weg / Metadaten und Freigabestatus |
| `pruefprotokoll.py` | Hash-Kette, Kennzahlen, Einsichtsrecht |
| `veredeln.py` / `pdfstelle.py` / `abbildung.py` | Zitate prüfen / Stelle im PDF finden / Abbildung ausschneiden |
| `wortsuche.py` / `wortverzeichnis.py` / `wortlisten.py` | wörtliche Suche seltener Fachbegriffe / Auslöser-Wörter |
| `selbstcheck.py` / `wegabgleich.py` / `dialogtest.py` / `absichttest.py` | Prüfwerkzeuge |
| `mkmd-dienst/` | Textfassung mit Kopfdaten (`mk_md.py`), echte Seitenzahlen aus dem PDF (`seiten_echt.py`), Bildbeschreibungen (`bildbeschreibung.py`), Deckblatt-Erkennung (`vorspann_finden.py`) |
| `office-dienst/office_dienst.py` | LibreOffice → PDF (`POST /pdf`, Ziel neben dem Original) |
| `nothink-proxy/` | schaltet das laute Denken des Modells ab |

## 7 · Arbeitsdokumente und Historie

Die Entstehung ist in den Arbeitsdokumenten unter [`entwicklung/`](entwicklung/)
festgehalten — mit Datum, Befund und Entscheidung. Quelltext-Kommentare verweisen
auf sie mit dem Dateinamen.

- [`entwicklung/ARCHITEKTUR-GESPRAECH.md`](entwicklung/ARCHITEKTUR-GESPRAECH.md) — vom Regel-Router zum Modell mit Werkzeugen (Stufe 1/2, Messungen, Grenzen des 12B-Modells)
- [`entwicklung/GESPRAECH-ANFORDERUNGEN.md`](entwicklung/GESPRAECH-ANFORDERUNGEN.md) — Anforderungen aus Recherche und Partner-Unterlagen (Leitfaden K1–K5), Stand je Punkt
- [`entwicklung/T4-ABGLEICH.md`](entwicklung/T4-ABGLEICH.md) — Abgleich Testserver ↔ Paket, Lücken L1–L8 und ihr Stand
- [`entwicklung/BUGS_UND_FIXES.md`](entwicklung/BUGS_UND_FIXES.md) — Fehler mit Ursache und Behebung

Frühere Fassungen der Anleitung liegen unter [`archiv/`](archiv/). Der laufende
Änderungsstand steht in der Git-Historie (`git log --oneline`).
