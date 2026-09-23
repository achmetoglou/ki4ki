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

## 18 · Die Belegklammer kannte nur volle Titel (22.09.2026, BEHOBEN)

⛔ **Das war der eigentliche Grund, warum kein Beleg entstand** — nicht der
Umlaut-Fehler aus §16, der davor gefunden und behoben wurde.

**Symptom.** Die Antwort nannte beide Zahlen richtig und schrieb den Abdruck
in die Klammer: `(ww2imi8pf9, S. 1)`. Es entstand trotzdem nie ein Beleg.
**Bei zwei verschiedenen Modellen (Gemma und Qwen) identisch** — das schloss
das Modell als Ursache aus.

**Ursache.** `_beleg()` schlug den Klammertext in einem Verzeichnis nach, das
nach **vollem Titel** geschlüsselt war:

```python
if k.lower() not in _bekannt and not re.fullmatch(r"[A-Z]{1,4}-\d{2}-\d{3}", k):
    return m.group(0)          # Klammertext, kein Dokument des Bereichs
```

`ww2imi8pf9` ist kein voller Titel und keine Kennung → Ausstieg, **bevor**
irgendeine Seitenprüfung lief. Der Wächter war also nicht zu streng, er hat
das Dokument nie erkannt.

⛔ **Warum das in Teil 3 durchgerutscht ist:** Der Plan hat `mit_verweisen`
auf den Abdruck umgestellt (Aufgabe 7) und dabei 32 Aufrufstellen von
`_pdf_schluessel` mitgenommen. Diese Klammerprüfung ist ein **eigener**
Vergleich — dieselbe Klasse wie `dokument_erlaubt` und der Löschweg, die im
Plan einzeln aufgeführt sind. Sie stand nicht in der Liste der elf Stellen.
**Elf waren es also nicht, zwölf.**

**Lösung.** Die Entscheidung ist aus der Verschachtelung heraus in
`_beleg_dokument()` gewandert — dadurch überhaupt erst prüfbar. Erkannt wird
der Abdruck, und zwar über die Mitgliedschaft im Verzeichnis **dieses**
Arbeitsbereichs.

⭐ **Fail-closed und belegt:** Ein Abdruck, den es zwar gibt, dessen Dokument
aber nicht in diesem Arbeitsbereich liegt, erzeugt **keinen** Beleg — sonst
belegte die Anlage eine Aussage mit der Akte eines fremden Kunden. Die
Mutationsprobe macht genau zwei Zeilen rot und lässt die vier Gegenproben
grün.

⭐ Nebenbei behoben: In der Klammer steht jetzt der **lesbare** Titel
(`KundeBeta-Pruefbericht`) statt des ganzen Schlüssels.

---

## 19 · Das doppelte Trennzeichen überlebt AnythingLLM nicht (22.09.2026, BEHOBEN)

**Gemessen, nicht vermutet.** Die Dateiliste in der Oberfläche zeigt
`…-Pruefbericht--ww2imi8pf9.md` mit **zwei** Trennzeichen, der Name in der
Fundstelle kommt mit **einem** zurück.

`anzeigetitel()` schnitt am `--` ab. Bei einem Trennzeichen kürzte es
**gar nicht** — und damit wäre nach dem Neueinlesen der ganze Schaden aus
**§13** zurück: `angaben()` findet keinen Katalogeintrag, `kennung()`
liefert `None`, `art_von()` weiß nicht mehr, dass `DS-24-005` eine
Dissertation ist, und `metadaten._grund()` — die **erste Zeile** der
Rechteprüfung — trifft nie.

⭐ **Die Mutationsprobe zeigt genau das:** Baut man das Abschneiden am
Abdruck aus, liefert `angaben()` `None`. Der Schaden ist also nicht
hergeleitet, sondern vorgeführt.

**Lösung.** Abgeschnitten wird am **Abdruck**, nicht am Trennzeichen:
rückwärts zehn alphanumerische Zeichen zählen und gegen das Verzeichnis
prüfen. Ob dazwischen `--`, `-` oder ein Gedankenstrich steht, ist damit
gleichgültig — der Abdruck enthält keines dieser Zeichen.

⛔ **Der Abdruck wird übergeben, nicht geraten.** Ohne Verzeichnis fällt die
Funktion auf das `--` zurück und kürzt bei einem einzelnen Trennzeichen
**nichts** — sonst verlöre jeder Name, der zufällig auf zehn Zeichen endet,
sein Ende. Beide Fälle stehen als Gegenprobe im Test.

---

## 20 · Klammer und Sprung benutzten zwei verschiedene Namen (22.09.2026, BEHOBEN)

**Der dritte Anlauf am selben Tag** — und der Fehler war diesmal von mir
selbst eingebaut, in §18.

**Symptom.** Die Klammer stand richtig da: `(KundeAlpha-Pruefbericht, S. 1)`.
Die Fußzeile meldete **`Quelle:`** statt `durchsucht:`, die Seitenprüfung war
also durchgelaufen. Trotzdem kein anklickbarer Sprung.

**Ursache.** Zwei Stellen, zwei Namen:

| Stelle | Name |
|---|---|
| `_beleg()` schreibt in den Text | **lesbarer Titel** (seit §18) |
| `fadenfrage.verlinken_mehrfach()` sucht im Text | **voller Name** |

Beide für sich richtig — nur nicht miteinander. Der Sprung fiel lautlos
heraus. ⭐ Genau die Fehlerklasse, die dieses Projekt kennt: Nicht eine
Funktion ist falsch, sondern zwei Funktionen sind sich uneinig.

**Lösung.** `_anzeigename()` ist jetzt die **eine** Quelle für beide Stellen.
`_belegverzeichnis()` bildet die Karte einmal, die Klammer schreibt daraus,
und `beruehrt` wird damit geschlüsselt.

⛔ **Und die Falle in dieser Lösung, die der Plan schon kannte:** Zwei
verschiedene Pfade können denselben lesbaren Titel ergeben —
`Angebot 2024/Blatt.pdf` und `Angebot/2024 Blatt.pdf` werden beide zu
`Angebot-2024-Blatt`. Dann zeigte ein Sprung auf das falsche Dokument, und
das ist **genau die Kollisionsklasse, die dieser Umbau beseitigt**. Bei
Mehrdeutigkeit bleibt deshalb der volle Name stehen: länger, aber eindeutig.
Der Fall steht als Prüfung im Test, mit beiden Dateien wirklich angelegt.

⚠ **Was diese Prüfung NICHT abdeckt:** die Verdrahtung im Aufrufer selbst —
er sitzt tief in einem HTTP-Griff und ist ohne Server nicht aufrufbar.
Abgesichert ist stattdessen der Vertrag: Es gibt **eine** Funktion, die den
Anzeigenamen bildet, und die Prüfung hält fest, dass Klammer und Sprung von
derselben Karte ausgehen.

---

## 21 · Zwei Umlaut-Regeln, und das Zitat traf keine (22.09.2026, BEHOBEN)

**Symptom.** `„Die Zugfestigkeit beträgt 412 MPa." (KundeAlpha-Pruefbericht,
S. 1 — nicht wörtlich gefunden)`. Der Dokumentname wurde erkannt, die
Klammer stand richtig da — und der Sprung fiel trotzdem weg. Die Fußzeile
meldete „2 Zitate geprüft, 2 nicht gefunden" und behauptete damit ein
Zitatproblem, **das es nicht gab**: Das Modell hatte wörtlich richtig
zitiert.

**Ursache, gemessen:**

```
Zitat des Modells  ->  'die zugfestigkeit betragt 412 mpa'
Seite im Dokument  ->  'die zugfestigkeit betraegt 412 mpa'
```

`wortsuche._falte()` schleift den Umlaut auf den **Grundbuchstaben** ab
(`ä` → `a`), das Dokument stand in **Behelfsschreibung** (`ae`). Beide Regeln
sind für sich richtig und treffen sich nie.

⚠ **Nicht dasselbe wie §16.** Dort verglich `pruef_proxy` Umlaut gegen
Umlaut; hier faltet `fadenfrage` auf den Grundbuchstaben. Verschiedene
Module, verschiedene Konventionen, gleiche Wirkung — und beide fallen erst
auf, wenn ein Dokument die andere Schreibweise benutzt.

**Lösung.** `wortsuche._falte_ae()` dehnt den Umlaut aus **und** faltet dann;
`_steht_auf()` probiert beide Regeln, jede auf beide Seiten gleich
angewandt. Damit landen `beträgt` und `betraegt` auf derselben Form.

⭐ **Die drei Gegenproben tragen die Prüfung:** Ein Zitat, das nicht auf der
Seite steht, ein erfundenes und ein zu kurzes Bruchstück bleiben
unbestätigt. Ohne sie wären die vier grünen Zeilen auch dann grün, wenn
`_steht_auf` einfach immer `True` lieferte — und dann bekäme **jedes**
erfundene Zitat einen blauen Beleg.

---

## 22 · Die Modellangabe in der Fußzeile war konstant und falsch (22.09.2026, BEHOBEN)

Die Fußzeile nannte das Modell. Ein Arbeitsbereich fragt aber immer dasselbe
Modell — die Zeile sagte also nie etwas Neues. Dazu stand sie **falsch** da:
Emrach am 22.09. beim Gemma-Lauf: *„ja beim gemma lauf, sagt er trotzdem
qwen"*. Entfernt.

---

## 23 · Eine stoerrische Datei riss den ganzen Stapel mit (22.09.2026, NUR HALB BEHOBEN → siehe 29)

⛔ **Der gefährlichste Fund des Tages** — und er wäre im Nachtlauf über
4.300 Dateien mit Sicherheit eingetreten.

**Symptom.** Zehn Dateien im Eingang, alle landen in `aussortiert/` mit
*„kein Text gewonnen (0 Zeichen)"* — auch die PDF, die zwei Stunden vorher
sauber durchliefen. Der Durchgang meldet **„Succeeded"**. Kein roter
Baustein, keine Fehlermeldung im Protokoll außer zwei nackten `TypeError`.

**Was die Oberfläche zeigte:**

```
Dateien in JSON umwandeln
  1 item, 10 sub-executions
  Cannot read properties of undefined (reading 'entries')
  → WorkflowExecute.assignPairedItems   (n8n 2.31.4)
```

Zehn Unterausführungen, **ein** Ergebnis. Eine davon gab nichts zurück, der
Elternbaustein stürzte beim Einsammeln ab, und damit war der Text **aller**
zehn Dateien weg.

**Ursache.** In der Unterkette war **nur der PDF-Weg abgesichert**:

| Weg | `onError` vorher |
|---|---|
| Docling PDF-Extraktion, Zweitversuch | ✅ `continueRegularOutput` |
| Tika (Word, PowerPoint, sonstige) | ⛔ keiner |
| Office nach PDF | ⛔ keiner |
| Extract from File 1–4 (Excel, CSV, HTML, Text) | ⛔ keiner |

⭐ **Deshalb fiel es nie auf:** Solange ausschließlich PDF im Eingang lagen,
konnte nichts passieren. Beim ersten Word-, Excel- oder Outlook-Dokument
schon. Der Testlauf am Morgen (vier PDF) war grün **aus dem falschen
Grund** — er hat den einzigen geschützten Weg geprüft.

**Lösung.** Alle sechs Bausteine bekommen `onError: continueRegularOutput`
**und** `alwaysOutputData: true`. Beides ist nötig: Ein Baustein, der im
Fehlerfall gar kein Element weitergibt, lässt den Elternbaustein genauso
abstürzen wie einer, der abbricht. Eine gescheiterte Datei kommt jetzt ohne
Text weiter, bekommt ihre eigene Begründung und lässt die anderen in Ruhe.

⭐ `bau/ablauf_pruefen.py` hält beides fest; die Mutationsprobe (Tika wieder
ungeschützt) färbt genau zwei Zeilen rot.

⚠ **Was das über unsere Proben sagt:** Vier gleichartige Dateien sind keine
Probe. Der Morgenlauf hat den Umbau bestätigt und die Brüchigkeit der
übrigen fünf Wege dabei vollständig verdeckt. Eine Probe muss die
**Vielfalt** des echten Bestands enthalten, nicht nur seine Fehlerklasse.

---

## 24 · Löschen in der Oberfläche räumt das Original nicht mit (22.09.2026, OFFEN)

**Gemessen am 22.09.** Vier Dokumente in der Oberfläche gelöscht. Das
Protokoll des Proxys zeigt vier Treffer:

```
[Loeschen] Markdown-Fassung entfernt (aus der Oberflaeche geloescht)   ×4
```

Die Markdown-Fassungen im Volume `austausch-md` sind weg (§14 greift), der
Bestandszähler fällt richtig von 75 auf 71 — **die Originale in der
Ablagestufe unterhalb des Bereichs bleiben liegen.** Zu ihnen gibt es keine
einzige Meldung, der Zweig hat also gar nicht zugeschlagen. Emrach musste
fünf Dateien von Hand wegräumen.

⛔ **Warum das zählt:** §14 hat als Anspruch festgehalten, dass ein
Löschklick **alle drei** Ablageorte räumt. Zwei von drei ist keine
Löschung — bei Kundenakten ist das genau der Fall, in dem jemand glaubt,
eine Unterlage sei fort, und sie liegt weiter auf der Platte.

✅ **Am 22.09. nachmittags geklaert und behoben — siehe Punkt 25.**
Die Ursache war keine der beiden Vermutungen unten, sondern die zweite
Einhängung desselben Ordners: `_eigene_spuren_tilgen()` durchläuft den
Eingangsbaum und rechnete den Schlüssel gegen den Lesebaum — es konnte
**nie** ein Treffer entstehen. Derselbe Fehler ließ jeden Link auf ein
Nicht-PDF ins Leere laufen.

Die beiden damaligen Vermutungen, zum Nachlesen:

1. `_eigene_spuren_tilgen()` findet den Abdruck nicht, weil das
   Abdruckverzeichnis zum Zeitpunkt des Löschens noch den Stand vor dem
   Einräumen hat.
2. Die Office-Regel in `_schluessel_der_datei()` ordnet die Datei einem
   anderen Schlüssel zu, wenn ein gleichnamiges Original danebenliegt.

⭐ **Und ein Befund über die Prüfung selbst:** `schluesselwege_test.py`
(`test_loeschweg`) ist an dieser Stelle **grün**. Sie legt die Datei aber
selbst an ihren Platz; das echte System schiebt sie erst durch den Eingang
dorthin. Die Prüfung deckt den Fehler deshalb nicht ab — dieselbe
Fehlerklasse wie beim Morgenlauf mit vier PDF: grün aus dem falschen
Grund.

---

## 25 — Derselbe Ordner, zwei Einhängungen: fünf von sechs Wegen wirkungslos

**Gemessen 22.09. am laufenden System.** Behoben.

Im Arbeitsbereich `zz-schluesselprobe` endete **jeder** Link auf ein
Nicht-PDF auf „Dieses Dokument liegt nicht vor." Die Anlage beantwortet
einen unbekannten Namen und ein gesperrtes Dokument absichtlich
**wortgleich**, damit niemand über die Fehlermeldung Namen erraten kann —
von außen waren die beiden Fälle deshalb nicht zu trennen.

`pruef-proxy/linkprobe.py` hat es von innen gemessen (nur Zahlen und
Endungen, keine Namen):

```
Dokumente im Bestand: 81
  Seitenansicht moeglich (PDF da) :    8
  nur Originaldatei (kein Sprung) :    0
  TOTER LINK (nichts auszuliefern):    3    .docx 1, .txt 1, .xlsx 1
  ohne Abdruck (Altbestand)       :   70
```

Genau die drei Nicht-PDF. Das Rechte-Tor war unschuldig.

### Die Ursache

`./dokumente` ist im Compose **zweimal eingehängt**: einmal nur lesbar
(`KI4KI_PDFS`), einmal schreibbar (`KI4KI_EINGANG`). `_schluessel_der_datei()`
rechnete den Pfad aber immer gegen `KI4KI_PDFS`. Wer eine Datei aus dem
Eingangsbaum hereingab, bekam `../<zweiter Name>/<bereich>/…` — der Bereich
hieß `..`, der Schlüssel war Unsinn und traf nie.

| Aufrufstelle | durchläuft | Zustand |
|---|---|---|
| `pdfs_einlesen` | `KI4KI_PDFS` | ✅ heil — darum gingen die 8 PDF |
| `_archivdatei` | Eingangsbaum | ❌ fand **nie** etwas |
| `_eigene_spuren_tilgen` | Eingangsbaum | ❌ → **das war Punkt 24** |
| `_liegengebliebene_einraeumen` | Eingangsbaum | ❌ |

⭐ **Punkt 24 und die toten Links sind derselbe Fehler.** Sie sahen so
verschieden aus, dass sie zwei Tage lang getrennt gejagt wurden.

**Behoben** durch `_basis_von(pfad)`: Die Wurzel wird aus dem Pfad bestimmt,
nicht angenommen. Eine Funktion statt fünf Aufrufstellen.

### ⛔ Warum die Prüfreihe das nicht sehen konnte

`schluesselwege_test.py` setzte `KI4KI_PDFS` und `KI4KI_EINGANG` seit jeher
auf **denselben** Pfad. Eine Umgebung, die gutmütiger ist als die echte
Anlage, kann diese Fehlerklasse nicht enthalten — dieselbe Klasse wie
„WAL-Reste" am 12.09. `test_zwei_einhaengungen` baut die zweite Einhängung
jetzt eigens nach und war vor der Reparatur rot, mit dem Messwert daneben:
derselbe Bericht, zwei Schlüssel (`…--7sfhn943l6` gegen `…--585ksgdwxq`).

---

## 26 — „Seiten" heißt nicht „Seitenbild"

**Gemessen 22.09.** Behoben. **Mein zweiter Anlauf am selben Tag.**

Der Belegsprung auf eine Excel-Tabelle öffnete eine Ansicht ohne Bild
(„Dieses PDF enthält keinen durchsuchbaren Text").

Mein Fix vom Vormittag fragte „gibt es Seiten?" — und war wirkungslos,
**weil es Seiten gab**: `_seitentexte_pdf()` fällt bei fehlender PDF auf den
Bestandstext zurück. Das ist für Scans so gebaut, damit OCR-Seiten eine
dünne Textebene ersetzen. Eine Tabelle bekam dadurch „Seiten".

⭐ **Die Lehre:** Ich habe die Frage gestellt, die nahelag, statt der, auf die
es ankam. Text hat fast jedes Dokument — ein **Seitenbild** nur eine PDF.

**Behoben** durch `_sprungquelle(name)`: liefert nur dann Schlüssel und
Seiten, wenn eine Datei da ist, die sich aufschlagen lässt.

⛔ **Und dann war es zu viel des Guten.** Mit dem Riegel allein stand in
der Antwort **gar kein Link** mehr — auch nicht auf den Dokumentnamen.
Emrach hat das sofort gesehen: „mh... schau mal keine links“. Ich hatte
vom einen Extrem ins andere repariert.

`_belegquelle(name)` unterscheidet jetzt drei Fälle:

| Lage | Ergebnis |
|---|---|
| PDF liegt vor | Sprung auf die Seite, Stelle gelb markiert |
| nur das Original | Link auf das **Dokument**, kein Sprung, **ohne Seitenzahl** |
| nichts auffindbar | kein Link |

⭐ Die Regel dahinter: **nur versprechen, was die Anlage halten kann.**
Die Seitenzahl fällt weg, weil sie sich nicht aufschlagen lässt.

---

## 27 — Die gewandelte Word-PDF lag im falschen Ordner

**Gemessen 22.09.** Behoben. **Von mir verursacht.**

| | Wohin |
|---|---|
| Word-Original (Ablaufplan 1) | `archiv/<Kunde>/<Auftrag>/Bericht.docx` |
| gewandelte PDF (Ablaufplan 2) | `archiv/Bericht.pdf` ← **flach** |

Ich habe in Ablaufplan 1 die Archivstruktur auf Unterordner umgestellt und
Ablaufplan 2 nicht mitgezogen. Die Office-Regel im Proxy sucht die PDF aber
**im selben Ordner** wie das Original.

**Zwei Folgen:** Word-Dokumente hatten keine Seitenansicht, und jede
gewandelte PDF bekam einen **eigenen Schlüssel** — ein Dokument, das niemand
kennt. Bei **1.137 Office-Dateien** im KAP-Bestand wären das 1.137 solche
Geisterdokumente gewesen.

**Behoben:** `X-Ziel` rechnet jetzt **dieselbe** Formel wie Ablaufplan 1
(`/files/dokumente/<bereich>/archiv/<unter>`, Bereich = Segment vor dem
letzten `input`). Ohne `input` im Pfad wird **kein** Ziel genannt — ein
geratenes Ziel legte die PDF sonst unter den Eingang, und der nächste
Durchgang sammelte sie wieder ein: Der Riegel gegen Endlosschleifen hätte
eine erzeugt.

⚠ **Wirkt nur für neu aufgenommene Dokumente.** Was vorher gewandelt wurde,
liegt weiter flach im Archiv.

✅ **Am 22.09. abends am laufenden System bestätigt — beide Hälften.**

| Nachweis | Ergebnis |
|---|---|
| Ablage | `archiv/Müller & Söhne/Prüfberichte/` enthält jetzt `.docx` **und** `.pdf` — gesehen |
| Index | `linkprobe.py`: `.docx` wandert von `nur_datei` nach `seitenansicht` (8→9 mit Seite, 3→2 ohne) |
| Sprung | `/stelle?dok=…docx&seite=1&zitat=…` öffnet die Seite, belegte Stelle **gelb hinterlegt** |

Ein Word-Dokument mit Umlauten und `&` im Pfad, drei Ebenen tief.

⭐ **Die Lehre:** Zwei Ablaufpläne, die getrennt laufen und eine gemeinsame
Annahme haben — und kein Werkzeug hat sie verglichen.
`test_office_pdf_liegt_neben_dem_original` tut das jetzt; mit der alten
Zeile wird sie rot.

---

## 28 — Aussortierte Dokumente bleiben im Arbeitsbereich

**Gemessen 22.09.** OFFEN.

Die Aufnahmekette lädt **zuerst hoch und sortiert danach**:

```
Markdown speichern → Upload → In Workspace einbetten → Ablage entscheiden
                                                          ↑ hier erst die Positivliste
```

Folge: Ein Dokument, das die Positivliste ablehnt, liegt trotzdem im
Arbeitsbereich — die Datei wandert nach `aussortiert/`, die hochgeladene
Textfassung bleibt. Gemessen: drei von drei `.msg` im Prüfbereich.

### ⚠ Eine Schätzung, die sich als falsch erwies

Ich hatte daraus „rund 2.000 Geisterdokumente im KAP-Arbeitsbereich"
gerechnet — 1.707 Bilder plus 386 Rückfall-Formate. **Die Messung sagt
etwas anderes:** Eine Bilddatei in den Eingang gelegt, Bestand vorher 81,
nachher 81. Das Bild landet **nicht** im Arbeitsbereich.

Der Grund: Ohne Text entsteht keine Markdown-Fassung, also gibt es nichts
hochzuladen. Betroffen sind nur Dateien, die **Text haben und trotzdem
abgelehnt werden** — `.msg`, `.eml` und ein Teil der 386 Rückfall-Formate.

⭐ Von den `.msg` auf die Bilder zu schließen war derselbe Fehlgriff wie
am Morgen: eine Fehlerklasse aus einer verwandten, aber anders gebauten
abgeleitet. Die Messung kostete zwei Minuten, die Schätzung hätte einen
unnötigen Umbau vor dem Nachtlauf ausgelöst.

### ⛔ Zwei Folgefehler, am selben Abend gefunden

In der Bestandsliste standen die beiden Outlook-Nachrichten — und ein
Klick darauf endete auf „Dieses Dokument liegt nicht vor“. Zwei Ursachen
griffen ineinander:

1. `.msg` stand **nicht in `DOKUMENTENDUNGEN`** — kein Abdruck, nicht
   auffindbar. Die Liste war an `VORGESEHEN` ausgerichtet; richtig ist
   aber: Der Index muss jedes Dokument kennen, das im Arbeitsbereich
   **stehen kann**, nicht nur die, welche die Aufnahme behalten wollte.
2. `_archivdatei()` durchsuchte **nur `archiv/`**. Die Datei lag in
   `aussortiert/`. Jetzt: `archiv`, `aussortiert`, `parkplatz` —
   `loeschen` bleibt ausgenommen, was dort liegt ist zum Entfernen
   vorgemerkt.

⭐ **Und ein Befund über die Messung selbst.** `linkprobe.py` meldete
dabei „0 tote Links“. Beide Einträge hatten keinen Abdruck im Index und
fielen deshalb in den Topf „Altbestand“ — wo sie niemand suchte. Eine
Messung, die einen Fehler als Normalzustand verbucht, ist schlimmer als
keine. Die Probe unterscheidet jetzt **VERSCHOLLEN** (trägt einen
Pfad-Schlüssel, ist aber nicht im Index) von **Altbestand** (Name aus
der Zeit vor dem Umbau).

### Was zu tun ist

Die Positivliste gehört **vor** den Upload. Bis dahin: abgelehnte Formate
gar nicht erst in den Eingang legen, oder die Reste danach löschen. Kein
Datenverlust in beiden Fällen — der Schlüssel ist auf jeder Stufe derselbe.

---

## 29 — Die Unterkette sagte nie zu, dass sie etwas zurückgibt (23.09.2026, GEBAUT)

**Symptom.** Eine einzige `.db` im Eingang legte jeden Durchgang still — kein
Markdown, kein Upload, keine Ablage, und der Durchgang meldete **Erfolg**. Die
Datei blieb liegen und vergiftete die nächste Minute erneut, 180 Minuten lang,
bis die Claim-Garantie sie aus dem Eingang schob.

**Ursache, in einer Zeile:** Ablaufplan 2 endete auf einem `Merge`. Ein Merge gibt
zurück, was ankommt — und sagt **nicht** zu, dass überhaupt etwas ankommt. Kam
nichts, brach im Elternteil `assignPairedItems`, der Baustein `Code` las
`$('Dateien in JSON umwandeln').all()` als leere Liste und lieferte `return []`.
Ab da war der Durchgang leer, aber grün.

**⛔ Warum Punkt 23 den Fehler nicht gefangen hat.** Die dort gebaute Prüfung
`test_unterkette_reisst_nicht_mit` sieht Bausteine **einzeln** an (Fehlerabfang je
Baustein) und war am 23.09. grün, während der Fehler lief. Gezählt hat sie
außerdem nur HTTP- und Extract-Bausteine — **elf weitere** Bausteine des Plans
konnten die Unterausführung abbrechen, darunter alle fünf Weichen, der Merge
selbst und drei Code-Bausteine.

**Gebaut.**

1. Ein Zweig `Rueckfall` hängt direkt am Auslöser und liefert **immer** ein
   Element an den Merge (dritter Eingang). Damit hängt die Zusicherung nicht
   daran, ob n8n einen Baustein mit leerem Eingang überhaupt ausführt.
2. Ein Baustein `Return` am Ende wählt aus: gibt es ein echtes Ergebnis, gewinnt
   das; sonst `{ok: false, grund: …}` mit **leerem Text und Dateinamen**. Der
   Elternteil behandelt das wie jede gescheiterte Extraktion — die Störenfriede
   wandern ehrlich nach `aussortiert`, statt liegen zu bleiben.
3. Alle elf abbruchfähigen Bausteine haben einen Fehlerabfang bekommen.

**Die Prüfung** `test_rueckgabe_garantiert` in `bau/ablauf_pruefen.py` prüft
nicht Bausteine, sondern den **Weg**: Gibt es einen Pfad vom Auslöser zum
Ausgang, auf dem kein Baustein das Element verlieren kann?

⭐ **Womit sie rot wird** (das gehört zu jeder Prüfung dazu):
| Eingabe | Ergebnis |
|---|---|
| der Plan von `c2c4a21` (vor dem Umbau) | **14 Fehler** — kein `Return`, kein zugesicherter Weg, 11 Bausteine ohne Abfang |
| Rueckfall-Zweig entfernt | rot (als eingebaute Gegenprobe im Test selbst) |
| `return [echt[0]]` → `return liste` | rot: „echtes Ergebnis + Rueckfall → genau 1 Element“ |
| der heutige Plan | 0 Fehler |

**⛔ Was damit NICHT behoben ist — der Verstärker im Elternteil.** `Code` in
Ablaufplan 1 liefert weiterhin still `return []`, wenn die Unterausführung als
Ganzes scheitert (Zeitgrenze, Speicher, Unterablauf nicht aktiv). Der
naheliegende Riegel — stattdessen werfen — wäre **falsch**: Der Durchgang endet
dann vor `Sperre freigeben`, die Laufsperre bleibt liegen und blockiert alles bis
zum 120-Minuten-Notnagel. Genau dieser Fehler ist am 04.08. schon einmal
passiert. Richtig wäre ein Fehlerzweig, der die Sperre in jedem Fall freigibt —
eigenes Stück Arbeit, noch nicht gebaut.

## 30 — Der Chat-Anhang konnte nur EINE Datei halten (17.09.2026, BEHOBEN + ABGENOMMEN 23.09.)

**Meldung, woertlich:** *"Es wurden 3 Dateien ueber das + Zeichen zusaetzlich in
diesem Chat bereitgestellt allerdings nur eins bei der Anfrage ausgewertet."*

**Ursache, doppelt:** `_parse_mitschnitt` nahm `dateien[0]`; der Merkspeicher
`_ANHANG[(bereich, konto)]` hielt genau einen Eintrag, den die naechste Sendung
ueberschrieb. Beide Wege enden bei einem Dokument.

**⭐ Warum es beim Hochladen nie auffiel:** `_dateien_aus_formular` liefert
immer ALLE Dateien, und der Hochladen-Knopf laeuft korrekt ueber alle. Nur der
Chat-Anhang warf sie weg.

**Gebaut:** `pruef-proxy/anhang.py` (Zusammenfuehrung, ohne Server pruefbar) +
`anhangtest.py`. Rot gegen den Stand von heute frueh: **8 Fehler**. Danach 0,
`dialogtest.py` unveraendert 520/0.

**✅ Abnahme 23.09.:** Drei Dateien angehaengt, alle drei Kennwoerter genannt,
Fusszeile "3 Dokumente: ...", 174 Zeichen - nachgerechnet exakt die Summe.

**⛔ Zweiter Anlauf noetig:** Die erste Abnahme fiel durch. Meine Reparatur las
den Speicher, fuehrte zusammen und schrieb zurueck - ohne Sperre, obwohl der
Proxy je Anfrage einen eigenen Faden fuehrt und der Browser gleichzeitig
hochlaedt. Dreimal "jetzt 1 Dokument(e)" im Protokoll. Behoben mit
`anhang.merken()` unter `threading.Lock`; die Textgewinnung bleibt ausserhalb.

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
