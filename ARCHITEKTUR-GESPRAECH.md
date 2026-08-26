# Gesprächsführung: vom Regel-Router zum Modell mit Werkzeugen

Stand 26.08.2026. Entscheidung: Stufe 1 und 2 werden gebaut (Freigabe Emrach, 26.08.).
Grundlage: `GESPRAECH-ANFORDERUNGEN.md` (Recherche) und die Live-Dialoge vom 25./26.08.

## 1 · Befund

Das Sprachmodell (gemma4:12b) kann Gespräche führen — es bekommt das Gespräch nur
nicht zu sehen. Heute entscheidet der Prüf-Proxy **vor** dem Modell mit Wortlisten und
Mustern, was eine Eingabe ist (Bestand, Zusammenfassung, Bild, Beschwerde, Faden-Frage …).
Erst wenn keine Regel greift, sieht das Modell die Frage — plus sechs Textstellen aus
der Ähnlichkeitssuche und einige alte Nachrichten. Es weiß nicht, welches Dokument
gerade Thema ist, was die letzte Antwort war oder dass „sicher?" sich darauf bezieht.

Folge: Jede neue Formulierung braucht eine neue Regel. Gemessen 25./26.08.: „Wieviele
Diagramme hat diese Arbeit?" → Bestandstabelle · „Sicher" → Wortsuche · „Hast du nur
diese Dissertation angedockt?" → erfundene Modellantwort · „das ist falsch" → dieselbe
Antwort noch einmal. Alles einzeln gefixt — und die nächste Formulierung bricht wieder.

Warum es so gebaut wurde: Die Belegprüfung braucht Struktur (Dokument, Seite, Zitat),
AnythingLLM gibt dem Modell keine Werkzeuge, Regeln laufen in Millisekunden. Die Regeln
sind nicht falsch — sie sind die falsche **erste** Instanz.

Voraussetzung geprüft (26.08., `ollama show gemma4:12b`): Fähigkeiten `tools`,
`thinking`, `vision`; Kontext 262 144. Das kleine Modell (gemma4:e2b) ebenso.

## 2 · Zielbild

```
Eingabe ──► Wächter (Regeln, ms) ──► Absichts-Modell (Gespräch + Zustand) ──► Aktion
              │  Beschwerde/Export/          │  Aktion · Dokument · Aspekt ·      │
              │  Anlage-Frage: sicher         │  umformulierte Frage · Sicherheit  │
              ▼                               ▼                                    ▼
          direkte Antwort            unsicher → Klärfrage mit Optionen      Werkzeuge des Proxys
                                                                             (suchen, lesen, zählen,
                                                                              vergleichen, exportieren)
                                                                                       │
                                                                             Belegprüfung (Zitate
                                                                             gegen Original) ──► Antwort
```

Das Modell wird Gesprächsführer, der Proxy bleibt Wächter und Prüfer. Nichts, was heute
gebaut ist, fällt weg: Faden-Gedächtnis, Faden-Antwort, Fakten, Vergleich, Export,
Abkürzungen, Bild-Weg sind die **Werkzeuge**, die das Modell bekommt.

## 3 · Stufe 1 — das Modell erkennt die Absicht

**Eingabe an das Modell** (jede Frage, bevor der Proxy routet):
- die letzten 6 Züge des Fadens (Frage + Antwortanfang, gekürzt),
- der Faden-Zustand: aktuelles Dokument, Art der letzten Antwort, offene Rückfrage,
- die Dokumentliste des Bereichs (Kennung — Verfasser (Jahr): Titel, bis 40),
- die erlaubten Aktionen mit je einem Satz Erklärung.

**Ausgabe** (erzwungenes JSON, Ollama `format`):
```json
{"aktion": "frage_an_dokument | zusammenfassung | bild | fakten | vergleich |
            bestand | export | abkuerzung | rueckmeldung | anlage | klaerfrage | gesamtbestand",
 "dokument": "DS-24-005 | null", "zweites_dokument": "DS-23-005 | null",
 "aspekt": "Methodik", "frage": "eigenständig umformulierte Frage",
 "sicherheit": 0.0–1.0, "begruendung": "ein Satz"}
```

**Wächter (Regeln, bleiben hart):**
1. Beschwerde/Zweifel, Export, Anlage-Frage werden weiterhin per Regel erkannt — das
   Modell darf sie nicht übersehen.
2. Genanntes Dokument muss im Katalog existieren; sonst Klärfrage mit Optionen.
3. `sicherheit < 0,6` → Klärfrage („Meinst du A oder B?"), nie raten.
4. Fällt das Modell aus (Zeit, kaputtes JSON) → heutiger Regel-Router (unverändert).
5. Ergebnis wird protokolliert (`regel`, `absicht`, `sicherheit`) — messbar, vergleichbar.

**Schalter:** `KI4KI_ABSICHT_MODELL=1` (compose, Standard **an** nach Abnahme; vorher
`0` = alter Router). Modell: `KI4KI_ABSICHT_MODELL_NAME` (Standard gemma4:12b, Denken
aus; e2b als schnelle Alternative, ~1 s).

**Kosten:** +1–3 s je Frage (JSON-Ausgabe ~150 Token, Eingabe ~2 000 Token). Läuft
parallel zur Wortsuche.

**Abnahme:** `dialogtest.py` bleibt grün (Regeln unverändert) + neue Schicht-2-Prüfung:
30 echte Dialoge (aus dem Protokoll) mit erwarteter Absicht → Trefferquote ≥ 90 %,
sonst kein Standard „an".

## 4 · Stufe 2 — Werkzeuge

Das Modell ruft die Proxy-Funktionen selbst auf (Ollama-Tool-Calling), kann sie
verketten („Vergleiche Becker und Müller und exportiere das als CSV") und nachfragen.

| Werkzeug | Vorhandene Funktion |
|---|---|
| `in_dokument_suchen(dokument, frage)` | `_faden_antwort` / `fadenfrage.seiten_waehlen` |
| `dokument_zusammenfassen(dokument, auftrag)` | `_zusammenfassung_ganz` |
| `abbildung_zeigen(dokument, nummer)` | `_bild_antwort` |
| `zaehlen(dokument, was)` | `_fakten_zaehlen` |
| `vergleichen(dok_a, dok_b, aspekt, modus)` | `_vergleich_antwort` |
| `bestand(thema, art)` | `assistent.bestandsauskunft` |
| `abkuerzung(dokument, kurz)` | `assistent.abkuerzung_aufloesen` |
| `exportieren(format)` | `_export_antwort` |
| `im_ganzen_bestand_suchen(frage)` | AnythingLLM-Weg mit Belegprüfung |

Regeln für Stufe 2: höchstens 4 Werkzeugaufrufe je Frage; jedes Zitat wird weiter vom
Proxy gegen das Original geprüft; ein Werkzeug schreibt nie, nur liest; Zwischenstände
werden als Statusmeldung gezeigt („lese S. 12, 14 … vergleiche … exportiere").

## 5 · Stufe 3 — größeres Modell (optional, messen)

Auf der A40 (46 GB, ~25 belegt) passt gemma4:27b (≈17 GB Q4). Erwartung: besseres
Sprachgefühl, halbe Geschwindigkeit. Erst nach Stufe 1/2 messen — an denselben 30
Dialogen.

## 6 · Reihenfolge

1. Stufe 1 bauen, Schalter aus; Protokoll vergleicht Regel-Router vs. Absichts-Modell.
2. 30 Dialoge als Prüfreihe; Trefferquote messen; Schalter an.
3. Stufe 2: Werkzeuge, zuerst read-only Ketten (suchen → zeigen), dann Vergleich/Export.
4. Stufe 3 messen.

Changelog: siehe Git-Historie (`git log --oneline`), Prüfreihen unter `pruef-proxy/dialogtest.py`.

## Stand 26.08.2026 — Stufe 1 gebaut, Schalter aus

- Code: `pruef-proxy/absicht.py` (Auftrag, Modellaufruf mit erzwungenem JSON, Parsen, Wächter), Hook im Proxy (`_absicht_ausfuehren`), Protokollfeld `absicht` je Frage.
- Schalter: `KI4KI_ABSICHT_MODELL=1` in der `.env` (Standard 0). Modell: `KI4KI_ABSICHT_MODELL_NAME` (Standard gemma4:12b).
- Prüfreihe Schicht 1 (ohne Modell): `python3 pruef-proxy/dialogtest.py` — 18 Szenarien, 155 Prüfungen.
- Prüfreihe Schicht 2 (mit Modell, auf der Anlage): `docker exec ki4ki-pruef-proxy python3 /app/absichttest.py` — 32 echte Dialogzüge, Bedingung ≥ 90 % für Standard „an".
- Abnahme-Weg: 1) aktualisieren, 2) absichttest laufen lassen, 3) bei ≥ 90 % `KI4KI_ABSICHT_MODELL=1` in die `.env`, `./aktualisiere.sh`, 4) Live-Dialoge vergleichen (Proxy-Log `[Absicht]`-Zeilen).

## Abnahme 26.08.2026 — Stufe 1 an

- Prüfreihe `absichttest.py` auf der A40: **gemma4:12b 31/32 = 97 %**, Ø 3,0 s je Zug (max 3,7 s). Einziger Fehlschlag „Gib mir den Bestand als BibTeX" → bestand — unschädlich, Export fängt der Regel-Wächter vor dem Modell.
- gemma4:e2b: 27/32 = 84 %, Ø 1,9 s — verfehlt Fakten/Ziel/Anlage-Fragen → nicht als Absichts-Modell geeignet.
- Erste Fassung (vor Nachschärfung) lag bei 81 %; Ursachen: Bestand/Gesamtbestand-Abgrenzung, Verfassername statt Kennung beim Vergleich. Behoben durch Auftragstext + Wächter (Namen über Katalog auflösen; Gesamtbestand nur mit ausdrücklichem Marker).
- Schalter jetzt Standard **an** (`KI4KI_ABSICHT_MODELL=1`); Rückfall auf den Regel-Router per `.env`.
- Kosten: +3 s je Frage. Nächster Schritt: Stufe 2 (Werkzeugketten), danach Prompt kürzen (Dokumentliste nur bei Bedarf) für Tempo.

## Stand 26.08.2026 (nachmittags) — Stufe 2 gebaut, Schalter aus, Grenzen gemessen

**Gebaut:** `pruef-proxy/gespraech.py` (Werkzeugschema, Gesprächsschleife bis 5 Runden, Wächter) + `_gespraech_antwort`/`_werkzeug` im Proxy. Werkzeuge: seiten_lesen, abbildungen_auflisten, abbildung_zeigen, zusammenfassen, zaehlen, bestand, dokument_finden, abkuerzung, exportieren. Schalter `KI4KI_GESPRAECH=1` (Standard 0; Stufe 1 bleibt Rückfall). Nichts davon ist an eine bestimmte Bibliothek gebunden — Kennungen aus Dateinamen, Katalog vom Deckblatt, Abbildungen aus Unterschriften; gilt für jeden Bereich (AuW, KAP, Partner).

**Gemessen am Replay des Fadens vom 26.08. (gemma4:12b, simulierte Werkzeuge):**
- ✅ Zwei Aufgaben in einem Zug („Zusammenfassung mit stärkstem Bild") → 3–4 Werkzeuge verkettet, 8–10 s. ✅ „Warum unlesbar?" wird erklärt. ✅ Meinungsfragen sachlich. ✅ Dokumentwechsel per Name.
- ❌ **Das 12B erfindet trotz Werkzeugergebnis**: Abbildungslisten mit Nummern, Seiten und Unterschriften, die es nicht gibt — auch nachdem der Wächter die echte Liste vorgelegt hat; Inhalte samt „Zitat" ohne gelesene Seite (Zug 2: das Gegenteil der Arbeit, mit Seitenangabe).

**Konsequenz — Verteidigung unabhängig vom Modell (eingebaut):**
1. Wächter *holen* Belege selbst (echte Abbildungsliste, passende Seiten) statt zu bitten.
2. Jede Aussage mit (Kennung, S. n) wird per Wortdeckung gegen die Seite geprüft; ohne Deckung → „nicht belegt".
3. Wörtliche Zitate werden geprüft und verlinkt (gelb), erfundene markiert.
4. Erfundene Bildnummern werden gestrichen; die echte Liste wird angehängt; existierende werden eingebettet.
5. Temperatur 0; Ausfall → alter Weg.

**Offen / Entscheidung:** Die Erfindungsneigung ist eine Modellgrenze. Stufe 3 (gemma4:27b, ~17 GB, passt auf die A40) ist jetzt der naheliegende Test — dieselbe Replay-Reihe mit beiden Modellen. Bis dahin: Stufe 2 nur im Testbetrieb (`KI4KI_GESPRAECH=1` in der `.env`), Stufe 1 bleibt Standard.
