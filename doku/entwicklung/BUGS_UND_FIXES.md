# Bugs & Fixes

Protokoll der Fehler, die während der Entwicklung gefunden und behoben wurden —
mit Ursache und Lösung. Für Wartung und Weiterentwicklung. (Diese Dinge stehen
bewusst **hier** und nicht als Erzählung im Quelltext.)

---

## 1 · Aufnahme: Endlosschleife bei bildreichen PDFs

**Symptom.** Bei Dokumenten mit sehr vielen Abbildungen lief die Grafikkarte
dauerhaft voll; dasselbe Dokument wurde immer wieder neu verarbeitet.

**Ursache.** Der Aufnahme-Ablaufplan ließ **jedes** Bild vom Sprachmodell
beschreiben (Schwelle 0,03 ≈ fast jedes Fragment). Bei hunderten Bildern lief die
Beschreibung in den Zeitablauf (Timeout). Weil die meisten Schritte auf
„bei Fehler weitermachen" standen, wurde der Fehler **verdeckt**: Die Datei
erreichte den Verschiebe-Schritt nie, blieb im Eingang liegen — und der
5-Minuten-Takt nahm sie erneut. Endlosschleife.

**Fix 1 — Bildbeschreibung bändigen.** Schwelle auf 0,08 angehoben (nur
substanzielle Abbildungen/Diagramme/Tabellen, keine Mini-Fragmente) und der
Docling-Zeitablauf auf 60 Minuten begrenzt. Bewiesen: ein Dokument mit 285
Bildern lief sauber durch (108 beschrieben, keine Schleife).

**Fix 2 — Claim-Garantie.** Zu Beginn jedes Laufs wird jede Datei, die länger als
180 Minuten im Eingang liegt (= sie schleift), automatisch aussortiert und
protokolliert. Damit kann **kein** fehlgeschlagener Lauf mehr zur Endlosschleife
werden, egal aus welchem Grund.

⛔ **Nachtrag 21.09.: Fix 1 hat eine Nebenwirkung, die damals nicht gemessen
wurde.** Die Schwelle 0,08 unterdrückt Bildbeschreibungen nicht nur bei
bildreichen Ausreißern, sondern **im gesamten Bestand**. Siehe Punkt 9.

---

## 2 · Neue Arbeitsbereiche waren „blank"

**Symptom.** Ein per Klick in der Oberfläche angelegter Arbeitsbereich lieferte
keine Belege — ohne dass ein Fehler erschien.

**Ursache.** AnythingLLM legt neue Bereiche mit seinen Voreinstellungen an: Modus
`chat`/`automatic` statt `query`, ein generischer Standard-Prompt statt des
geprüften Systemprompts. Ohne diese beiden bricht die Belegprüfung still ab.

**Fix — Selbstheilung beim Anlegen.** Der Prüf-Proxy fängt das Anlegen eines
Bereichs ab und setzt direkt danach die geprüften Werte (Systemprompt, Modus
`query`, Trefferzahl, Schwelle, Verlauf, Temperatur). Jeder **neu** angelegte
Bereich ist damit von Geburt an beleg-fähig; **bestehende** Bereiche werden nie
verändert. Schalter: `KI4KI_BEREICH_HEILEN` (Standard an), braucht den
`KI4KI_API_KEY`.

---

## 3 · Drei Einstellungen, an denen die Belegprüfung hängt

Alle drei fallen im Betrieb **nicht** auf — die Anlage antwortet plausibel, nur
eben ohne das, was sie auszeichnet.

- **Kontextfenster (`OLLAMA_MODEL_TOKEN_LIMIT`).** AnythingLLM teilt das Fenster
  fest auf (15 % Systemteil, 70 % Frage, 15 % Verlauf). Die Fundstellen landen im
  Systemteil. Bei der Voreinstellung blieb dafür so wenig Platz, dass **ab der
  zweiten Fundstelle alles stillschweigend abgeschnitten** wurde (gemessen: 1
  statt 3 zitierte Arbeiten). Wert: 65536. Obergrenze setzt die Grafikkarte.
- **Chat-Modus muss `query` sein.** Im Modus `automatic` springt der Chat bei
  lokalen Modellen in den Agent-Modus — **ganz ohne Quellenangaben**. Zusätzlich
  abgesichert über `PROVIDER_DISABLE_NATIVE_TOOL_CALLING=ollama` (der Wert ist
  eine Liste von Anbieter-Kürzeln, kein Schalter — `all` wäre wirkungslos).
- **Der Systemprompt ist das Werkstück.** Die Belegprüfung sucht wörtliche Zitate
  in einer bestimmten Form. Diese Form entsteht **ausschließlich** durch
  `systemprompt.txt`. Ohne ihn: keine Zitate → nichts zu prüfen → keine Belege.

→ Alle drei werden bei neuen Bereichen automatisch gesetzt (siehe §2).

---

## 4 · Rechtemodell — maschinell abgesichert

Die Rechteprüfung (`bereich_sichtbar`, `erlaubte_dokumente`, `dokument_erlaubt`)
sitzt an **jedem** Ausgabeweg. `wegabgleich.py` prüft das maschinell: Vor jedem
Ausgabeweg muss eine der drei Prüfungen liegen. **Gegenprobe:** Wird auf einer
Kopie eine Prüfung unschädlich gemacht, wird der Test rot — ein Test, der immer
grün ist, wäre schlimmer als keiner. Der Blick auf den Code allein genügt hier
nicht, deshalb die maschinelle Prüfung.

---

## 5 · Weitere Funde

- **Seitenzahlen aus dem PDF, nicht aus der Textextraktion.** Die Seitenmarken der
  Extraktion stimmten in einer Stichprobe nur in 7 von 12 Fällen — deshalb wird
  die Seite **im PDF selbst** geprüft.
- **Docling-Zeitablauf.** Die Voreinstellung von 120 s brach große PDFs still mit
  HTTP 504 ab; angehoben, damit große Arbeiten durchlaufen.
- **„Think"-Feld auf dem OpenAI-Weg wirkungslos.** Ollama wertet `"think": false`
  auf diesem Weg nicht aus; deshalb sitzt der nothink-Proxy dazwischen.
- **Kopier-Knopf kam nicht im Browser an.** Ein durchgereichter `ETag` der
  Originalseite führte zu „304 nicht geändert" — der Browser behielt seine alte
  Fassung samt altem Skript. Fix: `ETag`/`Last-Modified` für die veränderte
  Oberfläche nicht mehr durchreichen.

---

## 6 · Ein Dokument wird nur ueber seinen Dateinamen erkannt (20.09.2026, OFFEN)

**Symptom.** Ein Bestand aus Kundenakten (15 Kundenordner, Unterordner wie
Angebot, Pruefbericht, Rechnung) wurde aufgenommen. Dabei: Dokumente
verschwanden aus dem Bestand, andere landeten im Archiv, ohne je eingebettet
worden zu sein, und die Zuordnung zum Kunden ging verloren — im Archiv lagen
lose Dateien, die niemand mehr einem Kunden zuordnen konnte.

**Ursache.** Die Anlage identifiziert ein Dokument **allein ueber seinen
Dateinamen**. Bei Forschungsbestaenden mit eindeutigen Titeln traegt das. Bei
Kundenakten heissen Dateien reihenweise gleich. Gemessen am echten Bestand
(`bau/pfad-messung.py`, 4.315 Dateien in vier Bereichen):

```
423 Schluessel sind mehrfach vergeben · 1.587 Dateien betroffen
groesste Gruppe: 99 gleichnamige Dateien
=> 1.164 Dokumente wuerden sich bei der Aufnahme still gegenseitig ersetzen
```

Betroffen sind **sieben unabhaengige Verzeichnisse** und **acht**
Normalisierungsfunktionen, die alle jedes Zeichen ausser `a-z0-9` wegwerfen:

| Stelle | Folge bei gleichem Namen |
|---|---|
| Archiv (`archiv/<name>`, flach) | zwei Dateien passen nicht nebeneinander — Kundenzuordnung geht verloren |
| „Neue Fassung" (`pruef_proxy.py:668`) | gleicher Name + anderer Inhalt → alte Fassung wird samt Vektoren geloescht |
| Loeschweg (`pruef_proxy.py:557`) | ein Loeschvorgang erfasst **alle** Namensvettern in **allen** Bereichen |
| Ankunftspruefung (n8n, „Ablage entscheiden") | trifft ein fremdes Dokument → nie eingebettete Datei wandert ins Archiv |
| Belegvorrat (`veredeln.py:319`) | jede zweite gleichnamige Textfassung wird verworfen → Dokument ist durchsuchbar, aber **nicht belegbar** |
| PDF-Index (`pruef_proxy.py:2429`) | „erster Fund gewinnt", ohne feste Reihenfolge — derselbe Beleglink kann nach einem Neustart ein anderes Dokument oeffnen |
| Rechtepruefung (`pruef_proxy.py:1967`) | Zugang zu **einem** „Angebot" erlaubt den Zugriff auf **alle** gleichnamigen |

**Loesung (entschieden, noch nicht gebaut).** Die Kennung eines Dokuments wird
sein **relativer Pfad** — Archiv und Aussortier-Ordner spiegeln die Unterordner
des Eingangs. Der Pfad allein reicht aber **nicht**: Weil die Normalisierung
alle Trennzeichen wegwirft, fallen bei bis zu acht Ordnerebenen immer noch
785 Dateien zusammen (`Kunde/Angebot 2024/x` = `Kunde/Angebot/2024 x`), und
zwei Schluessel reissen die 255-Byte-Grenze von ext4.

Deshalb: **lesbarer, auf 120 Byte gekuerzter Name + zehnstelliger
Fingerabdruck des vollen Pfades.** Der Fingerabdruck ist alphanumerisch und
ueberlebt jede der acht Normalisierungen. Am echten Bestand gemessen:
**0 Kollisionen in allen drei Normalformen, laengster Schluessel 176 Byte.**

⚠ **Dateien auf der Platte werden dabei nicht umbenannt.** Der Pfadname
betrifft nur die Kennung und die an AnythingLLM uebergebene Kopie.

## 7 · Unterordner brechen die Aufnahmekette (20.09.2026, OFFEN)

Zwei Fehler, die unabhaengig von Punkt 6 **heute schon** wirken, sobald
Dokumente in Unterordnern des Eingangs liegen:

- **Die 180-Minuten-Sicherung erzeugt eine Endlosschleife.** Sie bestimmt den
  Bereich ueber `dirname(dirname(datei))`. Bei einer Datei in einem Unterordner
  ergibt das den Eingang selbst — die aussortierte Datei landet in einem
  Aussortier-Ordner *unterhalb des Eingangs* und wird beim naechsten Durchgang
  von dort wieder eingesammelt. Der Riegel gegen Endlosschleifen erzeugt eine.
- **Die Bereichserkennung liefert `"input"` statt des Bereichsnamens.** Der
  Knoten „Nur ein Bereich je Durchgang" nimmt das vorletzte Pfadsegment. Folge:
  Dateien verschiedener Bereiche gelten als ein Bereich und werden mit **einem**
  Ablageordner hochgeladen — dem der ersten Datei. Dokumente koennen so im
  falschen Arbeitsbereich landen.

---

## 8 · Das Aufnahmeprotokoll zählt Versuche, nicht Dokumente (21.09.2026, OFFEN)

**Symptom.** Nach einem Fix stieg der Fehlerzähler im Aussortier-Protokoll
weiter — 107 Zeilen davor, 147 danach. Daraus wurde geschlossen, der Fix habe
nicht gewirkt, und das gesamte Projekt darauf gesperrt.

**Ursache.** Die 147 Zeilen verteilen sich auf **17 Dateien** (4×5, 3×9, 10×10).
Keine Datei kommt nur einmal vor. Eine gescheiterte Datei bleibt im Eingang
liegen und wird bei **jedem Minutentakt** erneut aufgegriffen und erneut
protokolliert. Das Protokoll zählt **Versuche**, nicht Dokumente. Der Fix hatte
gewirkt: dieselben 17 vor wie nach ihm, null neue — belegt durch eine Gegenprobe,
die zeigt, dass die Warteschlange nicht blockiert war (7 von 8 Archivdateien
wurden im Fehlerfenster abgelegt, neue Dateien liefen also durch).

**Zwei Mängel, die daraus folgen:**

1. **Die Meldung ist irreführend.** „Im Arbeitsbereich nicht wiedergefunden"
   klingt nach „hochgeladen, aber nicht angekommen". Geprüft wird aber nur, ob
   der Name in der Antwort des Einbetten-Aufrufs steht — und dieser Aufruf baut
   seine Liste aus der **Antwort des Uploads**
   (`adds: ($json.documents || []).map(d => d.location)`). Scheitert der Upload,
   ist die Liste leer und das Einbetten meldet trotzdem Erfolg. Die Meldung
   trifft also auch zu, wenn die Datei **nie hochgeladen wurde**. Dazwischen
   liegen sieben Knoten, alle auf „bei Fehler weitermachen", keiner mit
   Wiederholung. Im gesamten Ablaufplan: **20 von 30 Knoten** laufen bei Fehler
   weiter, **genau einer** wiederholt.
2. **Es gibt keine Kennzeichnung „schon versucht".** Damit ist jede Zählung, die
   auf dem Protokoll beruht, verfälscht — und die Forderung „der Fehlerzähler
   muss nach einem Fix stillstehen" ist **nicht durchführbar**.

**Lösung (noch nicht gebaut).** Beides gehört in den Umfang des Pfad-Umbaus:
die Meldung muss zwischen „nie hochgeladen" und „hochgeladen, nicht
wiedergefunden" unterscheiden, und eine gescheiterte Datei wird einmal
protokolliert, nicht bei jedem Takt erneut.

⚠ **Lehre.** Eine Protokolldatei, die je Versuch anhängt, ist kein Dokument-
zähler. Bevor eine Zahl aus einem Protokoll als Mengenangabe gilt: **eindeutige
Namen zählen, nicht Zeilen.**

---

## 9 · Die Bildkette liefert im ganzen Bestand nichts (21.09.2026, OFFEN)

**Symptom.** Für die Störfallassistenz sind Schadensfotos und Zeichnungen
fachlich das Wertvollste. Im Bestand liegen **1.594 Bilddateien (37 %)**. Aus
keiner davon entsteht durchsuchbarer Text — und auch aus Abbildungen **in**
Dokumenten entsteht praktisch keiner.

Die Kette wurde am 21.09. Glied für Glied durchgemessen. Das Können ist da, es
fehlt an vier Stellen die Konfiguration:

| Glied | Zustand |
|---|---|
| `gemma4:12b` in Ollama | ✓ vorhanden |
| `nothink-proxy:11435` antwortet | ✓ (12,4 s beim ersten Aufruf, Modell wird geladen) |
| Modell versteht **Bilder** | ✓ **160 Zeichen in 2,0 s** |
| Docling reicht Abbildungen weiter | ✗ — siehe 9a und 9b |

### 9a · Die Schwelle 0,08 unterdrückt Bildbeschreibungen im ganzen Bestand

Kontrollierter Versuch mit dem echten Motor-Block aus dem Unter-Ablaufplan,
**nur die Schwelle variiert**, alles andere gleich:

```
Schwelle 0.08   .pdf   HTTP 200    4,1 s   md 11.329   Bildmarken 3 | beschrieben 0
Schwelle 0.0    .pdf   HTTP 200   14,1 s   md 12.507   Bildmarken 3 | beschrieben 3
```

Docling **erkennt** die Abbildungen zuverlässig. Bei 8 % Schwelle **überspringt**
es alle, weil sie kleiner als 8 % der Seitenfläche sind. Das ist kein Fehler im
Bildweg, sondern ein Bestandsproblem: Jedes heute aufgenommene Dokument bekommt
Beschreibungen nur für Abbildungen über 8 % Seitenfläche. Detailzeichnungen,
kleinere Messkurven, Schadensfotos im Fließtext — alle stillschweigend
übersprungen, ohne Meldung, ohne Protokolleintrag.

⚠ Die Schwelle war eine **bewusste** Entscheidung gegen die Endlosschleife
(Punkt 1, Fix 1). Ein Absenken ist deshalb keine reine Verbesserung — es braucht
die Abwägung gegen die Laufzeit und die Rückfallsicherung aus Fix 2.
**Gemessene Kosten: rund 3,3 s je Abbildung.**

⛔ **Der Befund ist am Mechanismus bewiesen, nicht am Bestand.** Eine PDF mit drei
Abbildungen ist keine Stichprobe. Bevor die Schwelle gesenkt wird, gehört
gezählt: **an rund 20 Dokumenten, wie viele Abbildungen unter 8 % Seitenfläche
liegen.** Ohne diese Zahl ist die Laufzeit des Neu-Einlesens nicht abschätzbar —
ein Dokument mit 285 Bildern (Punkt 1) wären allein 15 Minuten.

### 9a-2 · Die Zahlen dazu, gemessen am ganzen Bestand (21.09.)

Der erste Befund stammte aus **einer** PDF mit drei Abbildungen. Inzwischen
sind **772 von 788 PDF** durchgemessen (`bau/bildflaechen_docling.py`, Docling
selbst befragt, Bildbeschreibung und Texterkennung abgeschaltet, 4 s je
Dokument):

```
21.708 Abbildungen insgesamt
  wird heute beschrieben    9.507   43,8 %
  faellt heute weg         12.201   56,2 %

Verteilung nach Doclings eigener Rechnung:
  unter 1 %      7.848   ##############
  1 bis 2 %      1.668   ###
  2 bis 4 %      1.070   ##
  4 bis 8 %      1.615   ###
  8 bis 16 %     2.355   ####
  16 % und mehr  7.152   #############

Verteilung auf die Dokumente: Median 3, groesstes Dokument 588
```

**Was ein Absenken der Schwelle kostet** (Gesamtlaufzeit eines Neu-Einlesens
mit Bildbeschreibung, 3,3 s je Abbildung):

| Schwelle | zusaetzlich beschrieben | Gesamtlaufzeit |
|---|---|---|
| heute 0,08 | — | 8,7 h |
| 0,04 | +1.615 | 10,2 h |
| 0,02 | +2.685 | 11,2 h |
| **0,01** | **+4.353** | **12,7 h** |
| 0,00 | +12.201 | 19,9 h |

⭐ **Empfohlen: 0,01.** Die Gruppe unter 1 % (7.848 Abbildungen) besteht
ueberwiegend aus Trennlinien, Logos und Bildschnipseln — sie kostet 7 Stunden
und bringt nichts. Die Gruppe 1–2 % dagegen enthaelt die kleinen Bildelemente
aus 9e, und die sind inhaltlich relevant.

⚠ **Zum Endlosschleifen-Risiko aus Punkt 1:** Das schlimmste Dokument hat 588
Abbildungen unter der Schwelle. Selbst bei Schwelle 0 waeren das 32 Minuten
fuer dieses eine Dokument — die 180-Minuten-Sicherung aus Fix 2 greift nicht.
Die Gefahr von damals ist abgedeckt.

⭐ **Und die Frage, warum diese Messung ueberhaupt ueber Docling laeuft und
nicht ueber `pdfimages`** — je Dokument gezaehlt:

| | Dokumente | |
|---|---|---|
| Docling sieht **mehr** → Zeichnungen ohne eingebettetes Bild | 284 | **36,8 %** |
| `pdfimages` sieht mehr → zerlegte Bilder | 242 | 31,3 % |
| gleich viele | 246 | 31,9 % |

Bei **gut einem Drittel** der Dokumente stecken Abbildungen drin, die im PDF
gar keine Bilddaten sind — technische Zeichnungen. Eine Messung ueber
`pdfimages` allein haette sie nicht gesehen. Fuer UC 1 sind das die
wichtigsten Abbildungen ueberhaupt.

⚠ Die **Summe** beantwortet diese Frage nicht (21.713 Abbildungen gegenueber
82.700 Rasterbildern): Dort ueberlagern sich zwei gegenlaeufige Effekte —
Docling fasst Kacheln zusammen und erkennt zugleich Vektorzeichnungen.
Nur die Zaehlung je Dokument trennt beides.

⛔ **Die Arbeit konzentriert sich extrem:** 17 Dokumente (2,2 %) stellen
4.606 der 12.201 uebersprungenen Abbildungen — **38 % der Arbeit in 2,2 % der
Dokumente**, die groessten mit 588, 530 und 432. Genau dafuer wurde die
Schwelle eingefuehrt. (In dieser Liste stehen `419, 419` und `308, 308`
nebeneinander: dieselben Dokumente doppelt im Bestand.)

---

### 9b · Freistehende Bilddateien erkennt Docling gar nicht als Abbildung

```
Schwelle 0.08   .jpg   HTTP 200   6,0 s   md 11 Zeichen   Bildmarken 0 | beschrieben 0
Schwelle 0.0    .jpg   HTTP 200   6,0 s   md 11 Zeichen   Bildmarken 0 | beschrieben 0
```

Null Bildmarken bei **beiden** Schwellen. Docling behandelt eine `.jpg` als Seite
mit Text und liefert 11 Zeichen OCR — es gibt keine Abbildung, die es beschreiben
könnte. Die Schwelle ist hier ohne Wirkung.

→ Für die 1.594 freistehenden Bilder führt **kein** Weg über Docling. Es führt
aber ein direkter Weg zum Modell: gemessen **2,0 s je Bild**, rund **53 Minuten**
für den ganzen Bestand.

⚠ Frühere Fassung dieser Doku und von `NAECHSTE-SITZUNG.md` §3c behaupteten, die
Beschreibung von Abbildungen **in** Dokumenten „funktioniert". Gemessen trifft
das nur oberhalb 8 % Seitenfläche zu — im Bestand praktisch nie.

### 9c · Der Massenlauf-Schalter schaltet die Beschreibung zusätzlich ab

Im Knoten „Docling PDF-Extraktion" steht:

```
do_picture_description = massenlauf ? 'false' : 'true'
do_formula_enrichment  = massenlauf ? 'false' : 'true'
```

Der erste Ablaufplan reicht `massenlauf` durch. **Wer den KAP-Bestand am Stück
neu einliest, schaltet damit die Bildbeschreibung ab** — und die Formelerkennung
gleich mit. Genau das ist für Schritt 3 des Umbaus geplant.

**Entschieden von Emrach am 21.09.: Die Bildbeschreibung bleibt beim Einlesen AN.**
Grundlage ist die Messung — der Zeitgewinn durch Abschalten ist gering, der
Verlust wäre vollständig und dauerhaft (siehe 9d).

⛔ **Einschalten allein genügt nicht.** Mit Beschreibung „an" **und** Schwelle
0,08 werden weiterhin nur Abbildungen über 8 % beschrieben — bei der Probe null
von drei. Der Bestand liefe durch, der Schalter stünde auf „an", und die
Detailzeichnungen fehlten trotzdem, ohne Meldung. Schwelle und Schalter sind
**gemeinsam** zu entscheiden.

### 9d · Die Vormerkliste `bilder-nachholen.txt` hat keinen Leser

Dateien, deren Bildbeschreibung übersprungen wurde, werden dort vermerkt. Es gibt
**keinen Cron und keinen vierten Ablaufplan**, der die Liste abarbeitet; die
einzige zweite Fundstelle im Code überspringt sie beim Auflisten. Der Eintrag ist
folgenlos. Damit ist „später nachholen" keine Rückfallebene, sondern ein
stiller Verlust.

---

### 9e · Was Docling als EINE Abbildung sieht (Versuch, 21.09.)

Die Schwelle rechnet mit der Flaeche einer **erkannten** Abbildung. Emrach hat
darauf hingewiesen, dass daran zwei Annahmen haengen, die nie geprueft wurden:
Ein Bild kann im PDF aus vielen kleinen Kacheln bestehen — faellt es dann
komplett durch? Und eine Infografik kann kleine Icons enthalten — fallen die
einzeln durch?

Vier PDF mit exakt bekannten Groessen (`bau/bildfaelle.py`):

| Fall | eingebaut | Docling sieht | beschrieben |
|---|---|---|---|
| Kachelbild | ein 36-%-Bild in 36 Kacheln zu je 1 % | **1** Abbildung, 36,3 % | ja |
| Infografik | Block mit 3 Icons zu je 1 % | **3** Abbildungen, je 1,0 % | **nein** |
| Verstreut *(Gegenprobe)* | 5 Icons zu je 1 % zwischen Absaetzen | 5 Abbildungen | nein |
| Einzelgross *(Kontrolle)* | ein Bild zu 30 % | 1 Abbildung, 30,1 % | ja |

**Ergebnis 1 — Entwarnung:** Ein gekacheltes Bild faellt **nicht** durch.
Docling arbeitet auf der gerenderten Seite, nicht an den PDF-Objekten, und
sieht das Bild so, wie ein Mensch es sieht. Bestaetigt am Bestand: ein Dokument
mit 5.110 eingebetteten Bildobjekten ergab 89 Abbildungen, davon 85 ueber der
Schwelle.

**Ergebnis 2 — bestaetigt:** Icons in einer Infografik werden **einzeln**
erkannt und fallen durch. Docling fasst sie nicht mit dem Block zusammen.
Entscheidend ist der visuelle Abstand, nicht die inhaltliche Zusammengehoerigkeit.
Das ist der Grund fuer die Empfehlung 0,01 statt 0,02 in 9a-2.

⚠ **Die erste Fassung dieses Versuchs war ungueltig, und nur die Gegenprobe hat
es aufgedeckt.** Dort bestanden die Bilder aus einfarbigem Grau und die Seite
aus drei Zeilen Text; Docling machte daraus jedes Mal *eine* Abbildung — auch
im Fall mit den fuenf verstreuten Icons, wo Trennen offensichtlich richtig war.
Das Ergebnis "1 Abbildung mit 36,3 %" beim Kachelbild sah wie ein Befund aus,
war aber dasselbe Artefakt. Erst mit strukturierten Bildern und 400 Woertern
Fliesstext je Seite trennte die Gegenprobe korrekt.

⭐ **Daraus die Regel, die in `NAECHSTE-SITZUNG.md` §7 gehoert:** Ein Versuch
braucht eine Gegenprobe, bei der das erwartete Ergebnis das **umgekehrte** ist.
Ohne den Fall "hier waere Zusammenfassen falsch" haette der Versuch jede
Antwort bestaetigt, die man von ihm hoeren wollte. Das Skript prueft Kontrolle
und Gegenprobe jetzt selbst und schreibt "DER VERSUCH IST UNGUELTIG", bevor es
irgendetwas deutet.

---

## 10 · Formate: was wirklich durchkommt (21.09.2026, gemessen)

`NAECHSTE-SITZUNG.md` §3c ließ zwei Fragen offen, weil sie am Code nicht zu
entscheiden waren. Sie sind jetzt mit Testdateien beantwortet:

```
.msg    HTTP 200   1.244 Zeichen   → kommt über Tika durch
.xlsm   HTTP 200     286 Zeichen   → kommt über Tika durch
.jpg    HTTP 200       0 Zeichen   → stiller Erfolg
.tif    HTTP 200       0 Zeichen   → stiller Erfolg
```

**`.msg` und `.xlsm` sind nicht ausgeschlossen** — beide laufen. Aber `.xlsm`
läuft über Tika als **Fließtext**, während `.xlsx` über den **Tabellenweg**
geht: gleiches Format, zwei Wege, Ursache ist eine Zeile in der Zuordnung.

⛔ **Der eigentliche Fehler: HTTP 200 mit null Zeichen gilt als Erfolg.** Der
Knoten „Nicht-PDF vereinheitlichen" setzt zwar
`fehler: 'Aus der Datei liess sich kein Text gewinnen'`, aber „Ablage
entscheiden" nutzt dieses Feld **nur zur Wahl des Begründungstextes** — über
Archiv oder Aussortiert entscheidet allein der Namensvergleich. Eine leere Datei
wandert also ins Archiv und gilt als aufgenommen.

Das betrifft unmittelbar die Abnahme von Schritt 3: **ein Neu-Einlesen wäre durch
leere Dokumente abnehmbar.** Es braucht eine **Verzweigung vor dem Upload**,
sonst bleibt das Feld folgenlos.

---

## 11 · Der Fundstellen-Sprung scheitert an `&`, `%` und `€` (21.09.2026, OFFEN)

**Symptom.** Belege springen bei manchen Dokumenten nicht an die richtige Stelle.

**Ursache.** AnythingLLM schreibt Uploadnamen um und ersetzt dabei Zeichen durch
**Wörter**: `&` → `and`, `%` → `percent`, `€` → `euro` (gemessen 21.09.).
Die acht Normalisierungsfunktionen werfen alles außer `A-Za-z0-9` weg — eine
**Wortersetzung überlebt das** und verschiebt den Namen dauerhaft. `pdfstelle.py`
baut die Umformung in `_wie_anythingllm` (Zeilen 72–94) **nicht** nach.

**Folge.** Bei jedem Dokument mit diesen Zeichen im Namen läuft der Sprung zur
Fundstelle ins Leere. Ziffern und Buchstaben sind nie betroffen — deshalb ist ein
**alphanumerischer** Fingerabdruck die Lösung (Punkt 6).

**Nebenbefund, Grundlage des Umbaus — Namensgrenzen von AnythingLLM, gemessen:**

- Es **kürzt nicht**; zu lange Namen führen zu HTTP 500.
- Aufschlag **42 Byte** auf den bereits umgeschriebenen Namen (`-<uuid>.json`).
- Bei 255 Byte: **HTTP 500**. Nutzbare Grenze: **200 Byte**.
- Derselbe Name zweimal hochgeladen ergibt **zwei** Einträge, keine Ablösung.

⚠ Solange der lesbare Teil eines Schlüssels Sonderzeichen enthalten darf, ist die
Längenrechnung **grundsätzlich nicht exakt** — die Umschreibung ändert die Länge
je nach Zeichen (Umlaute schrumpfen, `&`→`and` wächst, `›` fällt von 3 Byte auf
1). Gemessen wurden +39, +40, +42 und +14 Byte bei vier Testnamen. Deshalb wird
der lesbare Teil vor der Längenrechnung auf `A-Za-z0-9-` bereinigt.

---

## 12 · 16 PDF scheitern an beiden Motoren - und keine davon ist ein Dokument (21.09.2026)

**Symptom.** Beim Durchmessen des Bestands meldete Docling bei 16 von 788 PDF
`docling-parse could not load document`.

**Erster Schluss war zu voreilig.** Notiert wurde: „Diese Dateien haetten im
Betrieb weder Text noch Bildbeschreibung." Das uebersieht den Knoten
*Docling Zweitversuch (pypdfium2)*, der mit anderem PDF-Motor und mit
Texterkennung nachsetzt — die Messung kennt ihn nicht, der Betrieb schon.
Nachgeprueft mit genau dessen Einstellungen (`bau/bildfehler.py`):
**0 von 16 kommen durch.** Der Befund haelt, aber jetzt belegt.

**Was diese Dateien wirklich sind** — an den ersten Bytes bestimmt, ohne
Namen und ohne Inhalt:

| Art | Anzahl | Groesse |
|---|---|---|
| **macOS-Metadatei (AppleDouble)** | **9** | je exakt 4.096 Byte |
| Beschaedigte PDF (`Couldn't find trailer dictionary`) | 4 | 64 KB bis 904 KB |
| Leere Datei | 2 | 0 Byte |
| Unbekanntes Format ohne PDF-Kennung | 1 | 115 KB |
| **Gueltige PDF, die nur Docling nicht laedt** | **0** | — |

⭐ **Die letzte Zeile ist die wichtigste: Es gibt keine.** Die Anlage
scheitert an keinem einzigen lesbaren Dokument. Ein dritter Extraktionsweg
wird also **nicht** gebraucht — das war die naheliegende und falsche Folgerung.

**Was stattdessen zu tun ist:**

1. **Die 9 macOS-Metadateien beim Einlesen ueberspringen**, wie `.DS_Store`.
   Sie heissen `._<name>.pdf`, entstehen beim Kopieren von einem Mac auf ein
   fremdes Dateisystem und sind keine Dokumente. Der Bestand ist dadurch nicht
   um 9 Dokumente aermer, er war nie um 9 reicher. ⚠ Sie zaehlen heute in
   jeder Bestandszahl mit — auch in den 4.484 aus dem Schluesselmodul.
2. **Die uebrigen 7 aussortieren statt archivieren.** Heute gelten sie als
   erfolgreich aufgenommen, obwohl nichts aus ihnen herauskam — derselbe
   stille Ausfall wie in Punkt 10.
3. **Die 4 beschaedigten PDF Emrach melden.** Das sind echte Dokumente mit
   kaputter Struktur; die Rohdaten liegen lokal und koennten neu bereitgestellt
   werden. Nur hier geht tatsaechlich Inhalt verloren.

⚠ **Lehre.** „Docling kann sie nicht laden" ist keine Fehlerklasse, aus der
eine Massnahme folgt. Erst die Frage *was ist das ueberhaupt fuer eine Datei*
trennt drei voellig verschiedene Faelle: Nichtdokumente zum Ueberspringen,
Muell zum Aussortieren und echte Dokumente zum Neubeschaffen. Aufgefallen ist
das an einer Zahl: **neun Dateien mit exakt derselben Groesse** sind kein
Zufall, und der doppelt auftretende Hash `e3b0c442...` ist der SHA-256 der
leeren Zeichenkette.

---

## 13 · Der Pfad-Schlüssel nimmt der Bibliothek ihre Metadaten (21.09.2026, VOR Teil 3 zu lösen)

**Gefunden beim Gegenlesen des Teil-3-Plans, nicht beim Bauen.** Eine Folge der
Entscheidung „alles neu einlesen", die vorher niemand sehen konnte.

**Symptom.** Nach der Umstellung heisst ein Dokument nicht mehr `DS-24-005.pdf`,
sondern `wissensdatenbank-DS-24-005--dqda3iuv74.pdf`. Am Modul nachgemessen:

```
kennung("DS-24-005.pdf")                       -> "DS"
kennung("wissensdatenbank-DS-24-005--dq…pdf")  -> None
art_von(…)                                      -> None   (statt "Dissertation")
_flach(…).startswith("ds24")                    -> False  (statt True)
```

⛔ **Und eine Ebene tiefer: `bestand.angaben()` bricht ebenfalls.** Es schlägt
in `nach_grund` nach, einem Index, der aus den **alten** Namen gebaut wird
(`bestand.py:119`):

```
im Index steht :  'ds24005'
gesucht wird   :  'wissensdatenbankds24005dqda3iuv74'
Treffer        :  False
```

**Folge.** `angaben()` liefert für **jedes** Dokument `None`. Damit fehlen
**Titel, Verfasser, Jahr, Band, Art, Kategorie und Schlagworte** in der ganzen
Bibliothek. Betroffen sind **14 Aufrufstellen**: 11 in `assistent.py`, **3** im
Proxy (`:8296`, `:8329`, `:8388`), dazu 8 intern in `bestand.py`. Zwei
Nachschlagestellen: `bestand.py:153` und `:618`.

⚠ *Berichtigt am 21.09. beim Nachzählen:* Es sind **3** Proxy-Stellen, nicht 4 —
`pruef_proxy.py:7403` ruft `art_von()`, nicht `angaben()`. Und `metadaten.py`
hat ein **eigenes** `angaben(kennung, wurzel)` mit anderer Signatur und eigenem
Verzeichnis; seine drei Aufrufe gehören **nicht** dazu.

### ⛔ Der dritte Nachschlagepunkt — und der gefährlichste

`metadaten._grund()` (`metadaten.py:38`) normalisiert genauso, und die Schlüssel
in `metadaten.json` sind **von Menschen geschriebene Dokumentnamen**. Mit
Pfad-Schlüssel trifft der Nachschlag nichts, `m` bleibt `{}` — und `fuer_ki()`
entscheidet dann **je nach Bereichseinstellung in zwei entgegengesetzte
Richtungen falsch**:

| Bereich | Zeile | Ergebnis | Schaden |
|---|---|---|---|
| `nur_freigegebene: true` | `:114` | `freigabe` ≠ `freigegeben` → **False** | erste Zeile in `dokument_erlaubt` (`:1938`) → **kein Dokument mehr zugänglich** |
| ohne die Einstellung | `:110` | `ki` fällt auf `"ja"` zurück → **True** | ausdrücklich „für KI ausgeschlossene" Dokumente werden **wieder sichtbar** |

⚠ **Heute ist das latent:** Die Durchsicht zählte 11 Bereiche, **0× mit
`metadaten.json`**. Scharf wird es beim ersten Partner, der die Metadatenebene
benutzt — dann aber sofort und in einer der beiden Richtungen unbemerkt.

**Reparatur:** dieselbe Handschrift wie oben — **eine Zeile in `_grund()`**.
Davon erben `fuer_ki()`, `grund_ausschluss()`, `status_zeile()`, `warnung()`
und `angaben()`.

⭐ **Drei Prüfungen, die in BEIDE Richtungen greifen müssen:** „ausgeschlossen
sperrt" · „freigegeben bleibt zugänglich" · „unbekannt bleibt bei
Freigabepflicht gesperrt". Fehlt eine, prüft keine etwas: Eine Rechteprüfung,
die alles sperrt, besteht die erste; eine, die alles durchlässt, die zweite.

**Lösung (Teil 3, Aufgabe 6c).** Ein `anzeigetitel()` bildet aus dem Schlüssel
wieder `DS-24-005` — Bereichsvorspann und Abdruck fallen weg.
⭐ **Entscheidend ist, wo er eingesetzt wird:** *in* `angaben()` und `kennung()`,
bevor die Grundform gebildet wird — nicht daneben. Dann bleiben alle
15+ Aufrufstellen unangetastet. Zwei Funktionen statt fünfzehn.

⚠ Die Prüfung dazu beginnt mit der Gegenprobe, dass es **ohne** Anzeigetitel
wirklich bricht (`angaben(<schluessel>)` muss `None` liefern) — sonst repariert
man etwas Heiles und merkt es nie.

---

## 14 · Loeschen liess eine Volltext-Kopie zurueck (21.09.2026, BEHOBEN)

**Gefunden beim Aufraeumen nach der Schluesselprobe, nicht beim Suchen.**
Emrach: *"wenn ich mds in der ui loesche, sollten die unbedingt auch auf dem
server ueberall weg sein."*

**Symptom.** Ein Dokument hat **drei** Ablageorte, nicht zwei:

| Ort | Was | Wer raeumt es |
|---|---|---|
| `dokumente/<bereich>/archiv/` | das Original | Loeschweg |
| AnythingLLM-Bestand | Textfassung + Vektoren | Loeschweg / Oberflaeche |
| **Volume `austausch-md`** (`/files/anythingllm`) | **die erzeugte Markdown-Fassung, Volltext** | **niemand** |

Gemessen am laufenden System: Dort lagen Dateien zurueck bis **August** - jedes
jemals aufgenommene Dokument, darunter Unterlagen, die dem Namen nach
vertraulich sind. Ein Loeschklick in der Oberflaeche beruehrte sie nicht.

⛔ **Warum das vor dem KAP-Lauf zaehlt:** Danach laegen dort 4.300
Kundendokumente im Klartext - dauerhaft, unbemerkt, und ein Loeschauftrag
haette sie nicht erreicht. Bei Kundenakten ist das ein Datenschutzschaden,
kein Aufraeumdetail.

**Loesung.** Das Volume ist jetzt **schreibbar** im Pruef-Proxy eingehaengt
(`/daten/mdablage`), und `_eigene_spuren_tilgen()` entfernt die zugehoerige
Markdown-Fassung ueber denselben Abdruck-Vergleich wie alles andere. Damit
raeumen beide Ausloeser - die Wache ueber `loeschen/` und der Papierkorb der
Oberflaeche - alle drei Orte.

⭐ **Die Pruefung greift in beide Richtungen** und ist durch Mutation belegt:
Die Fassung des geloeschten Dokuments muss weg sein, die eines anderen
**unangetastet** bleiben. Ohne die zweite Zeile waere die erste auch dann
gruen, wenn der Loeschweg einfach den ganzen Ordner leerraeumt.

⚠ **Was das NICHT aufraeumt:** die Altlast aus den Monaten davor. Sie muss
einmal von Hand weg - ab jetzt entsteht keine neue.

---

## 15 · Eine Datei namens "undefined" (21.09.2026, OFFEN)

Im Volume `austausch-json` liegt eine Datei mit dem Namen `undefined`.
Sie entstand im misslungenen Probelauf. Der Zweig, der sie schreibt
(*Convert to File* -> *Read/Write Files from Disk1*), ist eine **Sackgasse**:
Er hat keinen Ausgang, sein Ergebnis wird nirgends gelesen.

Zu klaeren: ob der Zweig ueberhaupt noch gebraucht wird. Wenn nicht, faellt
mit ihm ein Volume weg, das sonst bei jedem Durchgang weiterwaechst.

---

## 16 · Der Zitatwächter las ue nicht wie ü (22.09.2026, BEHOBEN)

**Gefunden an der Abnahme, nicht beim Lesen.** Die vier Probedokumente waren
angekommen, beide Prüfberichte getrennt auffindbar, beide Zahlen in der
Antwort — aber **kein blauer Beleg**. Die Fußzeile meldete `durchsucht:`
statt `Quelle:`; das war der einzige Hinweis, und er war korrekt.

**Ursache.** `_dok_hat_aussage()` verlangt mindestens drei gemeinsame
Fachwörter (über sechs Zeichen) zwischen Aussage und Seitentext. Verglichen
wurde **Umlaut gegen Umlaut**:

```
Antwort (Modell):  Prüfbericht · beträgt · Zugfestigkeit
Seite (Dokument):  Pruefbericht · betraegt · Zugfestigkeit
gemeinsam: 1  →  Beleg gesperrt      (nötig: 3)
```

Gegenprobe mit demselben Text in echten Umlauten: gemeinsam 3, Beleg
entsteht. **Die Schreibweise allein kippt das Ergebnis.**

⚠ **Das trifft nicht nur Probedokumente.** Ältere Ausfertigungen, Ausfuhren
aus fremden Anlagen und schwache Texterkennung schreiben regelmäßig `ue`
statt `ü`. Dass die Füllwortliste selbst **beide** Schreibweisen führt
(`gegenueber` **und** `gegenüber`), zeigt: Die Doppelform war bekannt — der
Vergleich hat sie nie gelernt.

⭐ **Ein zweiter Fehler derselben Familie, im selben Atemzug gefunden:** Die
Zerlegung stand an einer Stelle als `[^0-9a-zA-Z…]`, an der anderen als
`[^0-9a-zA-z…]`. Das kleine `z` lässt Unterstrich und eckige Klammern als
Wortzeichen durch — Aussage und Seitentext wurden also **verschieden**
zerlegt, und ein Wort mit Unterstrich deckte nie.

**Lösung.** Eine gemeinsame Funktion `_fachwoerter()` für **alle sechs**
Vergleichsstellen: eine Zerlegung, eine Schreibweise. `ue`/`ae`/`oe`/`ss`
und die echten Umlaute sind dort dasselbe Wort.

⚠ **Nicht angefasst:** die Fachwortliste für die gelbe Markierung
(`/stelle?zitat=…`). Sie sucht Wörter **im** Seitentext — dort muss die
Schreibweise des Dokuments stehen bleiben, sonst markiert sie nichts.

⭐ **Die Prüfung ist beim ersten Anlauf zweimal durchgefallen**, und beides
steht als Kommentar im Test:
1. Sie benutzte einen Phantasienamen. `_dok_hat_aussage` steigt bei einem
   unbekannten Dokument sofort mit `True` aus („unprüfbar → nicht sperren") —
   drei Zeilen waren grün, ohne etwas zu prüfen.
2. Der erste Wortlaut ließ nach dem Wegfall der Umlaute **unter** drei
   Fachwörter übrig, also griff wieder dieselbe Ausstiegsklausel. Die Zeile
   blieb bei der Mutationsprobe grün. Der Wortlaut ist deshalb **gebaut**:
   drei lange Wörter überleben das Zerfallen, damit der Wächter bis zum
   Vergleich läuft.

---

## 17 · Leere Unterordner blieben im Eingang stehen (22.09.2026, BEHOBEN)

Seit Teil 3 spiegeln `archiv/` und `aussortiert/` die Unterordner des
Eingangs. Nach einem Durchgang liegt der Inhalt im Archiv — im Eingang bleibt
die leere Hülle stehen. Emrach: *„die leeren ordner stehen nur noch lose da."*

**Lösung.** `_leere_eingangsordner_raeumen()` läuft mit der Minutenwache und
entfernt leere Unterordner **unterhalb** von `input/`.

⛔ **Mit Karenz (15 Minuten).** Ohne sie räumt die Wache einem Menschen den
Ordner weg, während er per SFTP noch Dateien hineinlädt — der Upload liefe
ins Leere. Der Eingang selbst bleibt immer stehen, auch leer.

⚠ **Eine Falle, die erst die Prüfung zeigte:** Entfernt man `Normen/Kleben`,
bekommt `Normen` dadurch einen frischen Zeitstempel und sieht aus wie eben
angefasst — die Karenz sperrte sich selbst aus, verschachtelte Hüllen
hätten je Ebene einen weiteren Durchgang gebraucht. Ordner, die derselbe
Durchgang selbst geleert hat, sind davon ausgenommen: Bei ihnen ist der
Grund der Änderung bekannt.

---

## Offen / vor einer Vermarktung zu klären

- **Erste vollständige Installation von null** auf der Zielumgebung — erst damit
  ist bewiesen, dass ein Partner startklar wird.
- **n8n-Lizenz** (*Sustainable Use License*): interner Betrieb gedeckt; ein
  vermarktetes Produkt mit fest verbautem n8n wäre vorher zu prüfen (siehe
  `LIZENZEN.md`).
- **Dokumentkennung** (Punkt 6) und **Unterordner in der Aufnahmekette**
  (Punkt 7). Solange beides offen ist, ist die Anlage fuer Bestaende mit
  gleichnamigen Dateien — Kundenakten, Projektablagen, Angebotsarchive —
  **nicht geeignet**. Fuer Forschungsbestaende mit eindeutigen Titeln ist sie es.
- **Der Testlauf `dialogtest.py` deckt diese Fehlerklasse nicht ab.** Von 44
  Szenarien behandelt keines Pfade, Namen, Archiv oder Dubletten; ein grosser
  Teil der Pruefungen sind Zeichenketten-Vergleiche im eigenen Quelltext. Vor
  dem Umbau gehoeren Szenarien dazu, die das **Verhalten** messen.
