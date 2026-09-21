# Einstieg in die nächste Sitzung

**Stand 21.09.2026, abends.** Diese Datei ersetzt das Zusammensuchen am
Sitzungsanfang. Sie sagt, wo die Ziele stehen, was entschieden ist, was offen
ist und was als Beweis zählt. **Erst lesen, dann arbeiten.**

⭐ **Wer nur eines liest: §3d.** Dort steht, was am 21.09. gebaut und
entschieden wurde — und was davon noch aussteht.

---

## 1 · Harte Regeln

- **Nie auf dem Server schreiben.** Alles über das Repo, Emrach macht
  `./aktualisiere.sh`. Lesender Zugang: `ssh -i ~/.ssh/a40_ki4ki emrach@100.84.225.57`
- **Nie Dokumenteninhalte lesen** — in keinem Arbeitsbereich. Ein Hook sperrt es.
  Wird ein Ausschnitt gebraucht: sagen, welcher, und ihn sich geben lassen.
- **Nie Daten automatisch löschen.** ⛔ Nie `docker system prune --volumes`.
- Keine Secrets ausgeben. Commits ohne Co-Authored-By.
- **Skill zuerst**, bei jeder Aufgabe: `sp-brainstorming` → `sp-writing-plans` →
  `sp-test-driven-development` → `sp-verification-before-completion` →
  `/code-review`. Für ungeklärte Fehler `sp-systematic-debugging`.
  Die Liste steht auf `start.eoglou.de`; ein `KATALOG.tsv` gibt es nicht mehr.

## 2 · Wo die Ziele stehen

| Quelle | Was drinsteht |
|---|---|
| `doku/entwicklung/GESPRAECH-ANFORDERUNGEN.md` | **Die Hauptquelle.** Drei Recherchen (Laien-Erwartungen, Wissenschaftler/Ingenieure, Stand der Technik für mehrstufige RAG-Dialoge) mit Quellen. Abgleichstabelle: **31 ✅ · 24 🟡 · 12 ❌** (Stand 25.–27.08.). Abschnitt 7 wertet die **Partner-Unterlagen** aus (Netzwerktreffen 2+3, Implementierungsleitfaden 141 S.), Abschnitt K die Demonstrator-Anforderungen. |
| `doku/entwicklung/ARCHITEKTUR-GESPRAECH.md` | Architekturentscheidungen zum Gesprächsteil |
| `doku/entwicklung/BUGS_UND_FIXES.md` | Gefundene Fehler mit Ursache, **12 Punkte**. Offen: **6** Dokumentkennung · **7** Unterordner · **8** Protokoll zählt Versuche · **9** Bildkette (teils erledigt) · **11** Fundstellen-Sprung. Neu am 21.09.: **9** Bildkette · **10** Formate · **11** `&`/`%`/`€` · **12** die 16 Ausfälle. |
| Gedächtnis `project_ki4ki_index` | Hub über 18 KI4KI-Einträge — bei jeder KI4KI-Frage zuerst öffnen |
| Gedächtnis `project_ki4ki_produktanspruch` | Emrach wörtlich (03.08.): die Anlage muss **beides** können — Schlüsse ziehen und zusammenfassen **und** belegen. Gilt für alle Bereiche, auch Partner. |

⭐ **Der benannte Pilotfall ist UC 1 „KI-gestützte Störfallassistenz"** im Prozess
*Breakdown-to-Recovery* (Leitfaden S. 102) — **nicht** „Fragen an Dissertationen".
Jede Bewertung der Anlage misst sich zuerst daran.

⚠ `~/HANDOFF_KI4KI.md` (07.08.) und `~/MASTERPROMPT_KI4KI.md` (31.07.) liegen im
Home-Verzeichnis und sind sechs Wochen alt — vor Gebrauch gegen den heutigen
Stand prüfen oder archivieren.

## 3 · Was als Nächstes dran ist

**Die Durchsicht ist am 21.09. gelaufen** (67 Zeilen, fünf Opus-Prüfer). Ergebnis:
drei Zeilen echt grün geworden, drei verschlechtert, der Rest gelb oder rot. Zwei
Befunde überlagern alles andere:

- **S1 — der Regel-Router ist im Betrieb toter Code.** `pruef_proxy.py:4891`
  greift bei `KI4KI_GESPRAECH=1` (gemessen: aktiv) fast jede Frage vor dem Router
  ab; `_gespraech_antwort` hat genau ein `return False` (leerer Bereich).
  Mindestens acht ✅ berufen sich auf deterministische Wege **dahinter**.
  ⭐ **Für jedes ✅, das auf einen deterministischen Weg verweist, gilt: liegt er
  vor oder hinter Zeile 4891?**
- **UC 1 wird nicht bedient** — nicht am Code, sondern am Bestand. Gefordert sind
  strukturierte Datensätze mit Feldern; die Aufnahmekette erzeugt ausschließlich
  Fließtext.

### Die Reihenfolge (entschieden von Emrach, 21.09.)

Die Anlage muss **beides** können. Erst die saubere Dokumentaufnahme, dann UC 1 —
nicht aus Ordnungsliebe, sondern weil die Aufnahme heute **still Dokumente
löscht**. Darauf baut man nichts. Und ein Fehlerkatalog für UC 1 liefe in
denselben Namenskonflikt: ein Fehlercode wie `E42` kommt bei jedem Kunden und
jeder Linie vor.

1. ✅ **ERLEDIGT 21.09.** Die zweite Ursache gibt es nicht (siehe §6.2).
   Die Sperre „nicht bauen, bevor das gemessen ist" ist damit **aufgehoben**.
2. **Pfad + Fingerabdruck bauen** (siehe §5), mit Prüfungen, die **Verhalten**
   messen, nicht Zeichenketten im Quelltext (siehe §7).
   ✅ **Teil 1 ist am 21.09. abends gebaut und am Bestand gemessen** —
   `pruef-proxy/schluessel.py`, Einzelheiten in §3d. ⚠ Das Modul wird bisher
   **von niemandem aufgerufen**; die Umstellung der sieben Verzeichnisse ist
   Teil 3 und steht noch aus.
   ⭐ **Zwei Anforderungen laufen mit**, ohne Zusatzaufwand, und sie machen die
   Beweisführung in Schritt 3 überhaupt erst möglich — **beide noch offen**:
   - Die Meldung muss zwischen „nie hochgeladen" und „hochgeladen, aber nicht
     wiedergefunden" **unterscheiden**. Heute prüft der Ablaufplan nur, ob der
     Name in der Antwort des Einbetten-Aufrufs steht — und der baut seine Liste
     aus der **Antwort des Uploads** (`adds: ($json.documents || []).map(d =>
     d.location)`). Scheitert der Upload, ist die Liste leer und das Einbetten
     meldet trotzdem Erfolg. Dazwischen liegen sieben Knoten, **alle auf „bei
     Fehler weitermachen", keiner mit Wiederholung** (gesamter Ablaufplan: 20
     von 30 Knoten so, genau einer wiederholt).
   - Eine gescheiterte Datei darf **einmal** protokolliert werden, nicht bei
     jedem Minutentakt erneut. ⛔ **Solange das nicht gilt, ist die Forderung
     „der Fehlerzähler muss nach dem Fix stillstehen" nicht durchführbar** — er
     kann per Konstruktion nie stillstehen.
   ✅ Eine dritte Anforderung, die hier stand, ist **erledigt**: Ein leeres
   Ergebnis wird nicht mehr archiviert, sondern aussortiert (§3d).
3. **KAP vollständig neu einspielen und messen**, dass der Fehlerzähler
   **stillsteht** — nicht nur, dass der Bestand steigt.
   ⚠ Mit Schwelle 0,01 dauert das **rund 12,7 Stunden** (§3d).
4. **Dann UC 1.** Dafür braucht es zuerst eine Entscheidung über den Bestand:
   Störfalldaten als Datensätze mit Feldern, nicht als Dokumente.

## 3b · Sofort erledigbar (Durchsicht 21.09., am laufenden System gemessen)

- ⛔ **Der Hauptbereich `wissensdatenbank` steht auf Modus `chat`, nicht `query`.**
  `BUGS_UND_FIXES.md` §3 nennt das als eine der drei Einstellungen, an denen die
  Belegprüfung hängt. `auw`, `kap` und der FAQ-Bereich stehen korrekt.
  ⚠ Die Selbstheilung greift nicht: sie berührt nur **neu angelegte** Bereiche.
- ⛔ **`KI4KI_KONTAKT` ist leer.** Der „Weg zum Menschen" und die für UC 1
  geforderte Eskalation laufen ins Nichts — die Anforderung ist im Abgleich als
  ✅ geführt und im Betrieb wirkungslos.
- ~~Der Server hängt zwei Commits zurück~~ — ✅ **erledigt 21.09.**, Repo und
  Server stehen beide auf `28e207c`.

## 3c · Was der KAP-Bestand wirklich enthält (gemessen 21.09.)

4.264 Dateien, Endungen gezählt:

```
jpg 786 · tif 690 · jpeg 118      = 1.594 Bilder            37 %
pdf 612 · doc 559 · docx 320 · pptx 142 · txt 93 · ppt 92
csv 84 · xlsx 78 · xls 54          = 2.034 in der Formatliste 48 %
msg 64 · xlsm 64                   = nicht in der Liste
ds_store 142 · db 87 · 001 72 · inf 32  ≈ 333 Müll
```

⛔ **Rund die Hälfte des Bestands passiert die Eingangstür nicht.** Die
Klassifizierung im Ablaufplan kennt genau: pdf · csv · txt · html/htm · xlsx/xls ·
doc/docx/odt/rtf · ppt/pptx/odp. Alles andere wird `unsupported`
(`let fileType = 'unsupported'` als Vorgabe).

⭐ **Wichtige Unterscheidung bei Bildern — die Fähigkeit ist da, der Weg fehlt:**
- Abbildungen **in** einem Dokument werden beim Aufnehmen an Docling gereicht
  (`do_picture_description`, `do_picture_classification`) und wandern in die
  Textfassung.
  ⛔ **Korrektur 21.09.: „Das funktioniert" war falsch.** Es wurden nur
  Abbildungen über **8 % Seitenfläche** beschrieben — im ganzen Bestand
  56,2 % aller Abbildungen fielen durch, ohne Meldung.
  ✅ **Behoben am selben Abend:** Schwelle steht auf **0,01**, siehe §3d und
  `BUGS_UND_FIXES.md` §9.
- **Freistehende** Bilddateien erreichen Docling nie — sie scheitern schon an der
  Klassifizierung. Für die Störfallassistenz sind das ausgerechnet Schadensfotos
  und Zeichnungen. Und selbst wenn man sie durchreicht, hilft Docling nicht: es
  erkennt in einer `.jpg` **null Bildmarken** (§9b). Der Weg, der nachweislich
  trägt, führt direkt zum Modell — **2,0 s je Bild**, rund 53 Minuten für alle
  1.594.
- `_bild_beschreiben` **zur Antwortzeit** (`pruef_proxy.py:8515`) arbeitet nur aus
  dem Seitentext. Das ist eine dritte, davon unabhängige Funktion — sie erklärt
  eine bereits aufgenommene Abbildung, sie nimmt keine auf.

✅ **Mit Testdateien beantwortet (21.09.), Einzelheiten in `BUGS_UND_FIXES.md` §10:**

```
.msg    HTTP 200   1.244 Zeichen   → kommt über Tika durch
.xlsm   HTTP 200     286 Zeichen   → kommt über Tika durch, aber als FLIESSTEXT
                                     (.xlsx geht über den Tabellenweg)
.jpg    HTTP 200       0 Zeichen   → stiller Erfolg
.tif    HTTP 200       0 Zeichen   → stiller Erfolg
```

⛔ **Der Fund, der schwerer wiegt als die Formatfrage: HTTP 200 mit null Zeichen
gilt als Erfolg.** „Nicht-PDF vereinheitlichen" setzt zwar ein Fehlerfeld, aber
„Ablage entscheiden" nutzt es nur für den Begründungstext — über Archiv oder
Aussortiert entscheidet allein der Namensvergleich. Eine leere Datei landet im
Archiv und gilt als aufgenommen. **Damit wäre Schritt 3 durch leere Dokumente
abnehmbar.** Es braucht eine Verzweigung vor dem Upload.

## 3d · Stand 21.09. abends — was gebaut und entschieden ist

### ✅ Teil 1: das Schlüsselmodul steht

`pruef-proxy/schluessel.py` und `schluesseltest.py`, **71 Prüfungen**, am echten
Bestand gemessen:

⚠ **Die Zahl 48 war falsch** — nachgezählt am 21.09.: Es waren **46** (45 grün
plus die rote Zeile „Prüfbaum fehlt"), mit Prüfbaum 51. Seit dem Abdruck-Leser
aus Teil 3 sind es **71 mit Prüfbaum, 66 ohne**. Gemessen, nicht gerechnet:
`python3 schluesseltest.py | grep -c "^  ok"`.

```
4.484 Dokumente = 4.484 Kennpfade = 4.484 Schlüssel
Doppelablagen (dieselbe Datei in zwei Stufen):            0
Dokumente, deren lesbarer Teil nur der Bereichsname ist:  0
längster Kennpfad 202 Byte -> längster Schlüssel 137 Byte
lesbarer Teil gestutzt: 59 · Fingerabdruck fehlt bei: 0
```

⭐ **0 Doppelablagen** heißt für Teil 3: Beim Umstellen fällt nichts zusammen,
jede Datei bleibt ein eigenes Dokument. Ein Risiko weniger.

⛔ **Die 200-Byte-Zusicherung war strukturell immer grün.** 137 = 120
(`LESBAR_BYTE`) + 2 + 10 + 5 — mehr als 141 Byte kann ein Schlüssel nie werden,
an keinem Bestand. Scharf ist erst der Vergleich mit dieser Obergrenze.
⚠ Und die Grenze hängt an der **Endungsregel** (1–8 Zeichen), *nicht* am
`max(0, …)`: Mit aufgeweichter Regel kommen 216 Byte heraus, obwohl das
`max(0, …)` greift. Wer `_ENDUNG` anfasst, bricht die Grenze.

⚠ **Offen für Teil 3:** Von 200 zulässigen Byte bleiben 63 ungenutzt, weil
`LESBAR_BYTE` härter deckelt als `GRENZE_BYTE`. Deshalb sind 59 lesbare Teile
gestutzt. Eine Anhebung auf 179 ist möglich, **nicht entschieden**.

### ✅ Die Bildfrage ist entschieden: Schwelle 0,08 → 0,01

Am ganzen Bestand gemessen (772 von 788 PDF): **21.713 Abbildungen**, davon
werden heute 9.512 beschrieben und 12.201 übersprungen. Die neue Schwelle holt
**4.353** davon; das Neu-Einlesen dauert damit **12,7 statt 8,7 Stunden**.
Unter 1 % liegen 7.848 Abbildungen — Trennlinien, Logos, Schnipsel; die kosten
7 weitere Stunden und bringen nichts. Einzelheiten in `BUGS_UND_FIXES.md` §9.

⭐ **Wie Docling überhaupt erkennt** (gemessen, §9e): Es arbeitet **visuell auf
der gerenderten Seite**, nicht an den PDF-Bildobjekten.
- Ein **gekacheltes Bild** (36 Kacheln à 1 %) wird als **eine** Abbildung mit
  36 % erkannt und beschrieben — zerlegte Bilder fallen **nicht** durch.
- **Icons in einer Infografik** werden **einzeln** erkannt und fallen durch.
  Das ist der Grund für 0,01 statt 0,02.
- Bei **37 % der Dokumente** sieht Docling Abbildungen, die `pdfimages` nicht
  findet — Zeichnungen ohne eingebettetes Bild, für UC 1 die wichtigsten.

### ✅ Vier Änderungen an der Aufnahmekette (`53edd7c`, im Betrieb bestätigt)

1. Schwelle **0,01**.
2. Der **Massenlauf** kann die Bildbeschreibung nicht mehr abschalten — Schritt 3
   ist selbst ein Massenlauf, ohne das wäre Nr. 1 wirkungslos.
3. **macOS-Metadateien** (`._*`) und Merkdateien werden übersprungen. Neun davon
   steckten im Bestand, je exakt 4.096 Byte, und zählten als Dokumente mit —
   auch in den 4.484 oben.
4. ⭐ **Ein leeres Ergebnis geht nicht mehr ins Archiv.** Bisher entschied allein
   der Namensvergleich; eine Datei ohne gewonnenen Text galt als aufgenommen.
   Damit wäre Schritt 3 durch leere Dokumente abnehmbar gewesen.

`bau/ablauf_pruefen.py` prüft diese Knoten, ohne sie im Betrieb auszuprobieren —
und gleicht ab, was n8n **wirklich geladen** hat. Aufruf auf dem Host:
`cd ~/ki4ki && python3 bau/ablauf_pruefen.py`

### Was daraus offen bleibt

1. **Vier beschädigte PDF** (`BUGS_UND_FIXES.md` §12). Nur dort geht wirklich
   Inhalt verloren — Emrach hat die Rohdaten lokal und kann sie neu bereitstellen.
2. **`LESBAR_BYTE`** (siehe oben), gehört zu Teil 3.
3. **Die Protokoll-Wiederholung** bei jedem Minutentakt (§3, Punkt 2).

## 3e - Teil 3 laeuft: 8 von 14 Aufgaben gebaut (21.09., spaeter Abend)

Plan: `/home/runlvl89/.claude/plans/ki4ki-wissensdatenbank-des-snazzy-willow.md`
(14 Aufgaben, 92 Schritte). Gebaut wird in einem Klon, gepusht auf
`pfad-identitaet`; **Emrach macht `./aktualisiere.sh`**.

### Was steht

| Aufgabe | Commit | Was |
|---|---|---|
| 1 | `336036b` | `abdruck_finden()` im Schluesselmodul - Mitgliedschaft statt Herausschneiden |
| 2 | `f9dda5a` | Pruefbaum enthaelt die Fehlerklasse (sonst beweist er nichts) |
| 3 | `f1e43ec` | `bau/abdruck-messung.py` - sechs Zahlen am echten Bestand |
| 4 | `cde53f4` | `POST /schluessel` am mkmd-Dienst - eine Rechnung, zwei Leser |
| 5 | `5bb4a41` | PDF-Index auf den Schluessel, `_pdf_schluessel` loest ueber den Abdruck auf |
| 6 | `6e2866f` | Zweitindex `pdfstelle.py` (beide Kopien) |
| 6b | `dfc47f2` | Belegvorrat - keine gleichnamige Fassung wird mehr verworfen |
| 6c | `b500ecd` | Anzeigetitel in `kennung()`, `angaben()`, `metadaten._grund()` |

### Die Messung am echten Bestand (21.09., `bau/abdruck-messung.py`)

```
4.321 Dateien = 4.321 Kennpfade, 0 unzerlegbar, 0 Doppelablagen
echte Kollisionen (zwei Kennpfade, ein Abdruck):            0
Fehlzuordnungen ueber Fenster:                    0 von 4.321
PDF mit gleichnamigem Office-Original daneben:     293 von 779
Gegenprobe - heutiger Schluessel kollidiert:     1.593 Dateien
```

⭐ **293 von 779 PDF sind gewandelte Office-Dokumente.** Ohne die Office-Regel
bekaemen 293 Dokumente zwei Abdruecke, und jeder Beleg eines Word-Dokuments
spraenge ins Leere. Die Regel ist damit am Bestand belegt, nicht angenommen.

⚠ Aufruf **ohne** `KI4KI_PDFS`: Der erste Versuch lief mit dem Pfad aus dem
Container, den es auf dem Host nicht gibt. Container-innen ist nicht Host.

### Was noch aussteht

| Aufgabe | Was | Gate |
|---|---|---|
| 7 | Belegvergleich `mit_verweisen` auf den Abdruck | ⛔ danach **Belegmessung am laufenden System**, bevor irgendetwas neu eingelesen wird |
| 8 | Rechtepruefung `dokument_erlaubt`, fail-closed | braucht 6c (das K3-Tor ist die erste Zeile darin) |
| 9 | Loeschweg - dreifach nachgesehen | |
| 10 | Aufnahmekette in n8n + die zwei Unterordner-Fehler | |
| 11 | `bau/ablauf_pruefen.py` erweitern | |
| 12 | Ausrollen, neu einlesen, Uebergangsstuetze entfernen | |

### Die Uebergangsstuetze und wann sie weg darf

Der nackte Dateiname loest weiter auf, damit die Dokumente aus der Zeit vor dem
Umbau waehrend des Neu-Einlesens nicht unauffindbar werden. Sie ist an ihre
Begruendung **gekoppelt**: `curl localhost:3001/pruef-status` zeigt
`nur_altweg` und `altweg_aktiv`. Sinkt `nur_altweg` auf 0 und steht
`altweg_aktiv` weiter auf `true`, wird die Pruefung in
`schluesselwege_test.py` **von selbst rot** - das ist das Startsignal fuer den
Rueckbau (Aufgabe 12). `-1` heisst "Bestand nicht lesbar", nicht "darf weg".

### Pruefreihen (alle ohne Server lauffaehig)

```
cd pruef-proxy
KI4KI_PRUEFBAUM=<baum> python3 schluesseltest.py    71 Pruefungen
python3 schluesselwege_test.py                      33 Pruefungen
python3 dialogtest.py                              519 Pruefungen
python3 wegabgleich.py                               0 Loecher
python3 ../bau/abdruck-messung.py                  sechs Zahlen
```
`<baum>` legt `python3 bau/kunstbaum.py <baum>` an.
⚠ `absichttest.py` braucht Ollama und laeuft nur auf der A40.

### Vier Fallen, die beim Bauen aufgefallen sind - nicht beim Lesen

1. **Der Abdruck steht NICHT am Ende des Schluessels** - dahinter kommt noch
   die Endung. Wer das Abdruckverzeichnis mit "die letzten zehn Zeichen"
   fuellt, legt jeden Eintrag falsch an. Beim Suchen faellt das nicht auf
   (das Fensterverfahren findet ihn trotzdem), beim Loeschen und bei den
   Rechten schon.
2. **`eintragen()` schrieb an `angaben()` vorbei** - Katalog unter dem rohen
   Schluessel abgelegt, gesucht ueber den Anzeigetitel. Der Katalog haette
   sich gefuellt und die Bibliothek waere ohne Angaben geblieben.
3. **`nur_ueber_altweg()` zaehlte jede `.json`** im Bestandsordner. Eine
   einzige fremde Datei haette die Uebergangsstuetze fuer immer am Leben
   gehalten - das Versagen, das die Kopplung verhindern soll.
4. **Eine Pruefung war aus dem falschen Grund gruen**: Sie verglich zwei
   Aufrufe, die beide `None` lieferten - gruen also gerade dann, wenn gar
   nichts mehr gefunden wird.

⭐ Und die Mutationsprobe hat eine fuenfte gefunden: `ohne_uuid()` liess sich
entfernen, ohne dass eine Pruefung ausschlug. Wozu es da ist, zeigt jetzt ein
gebauter Fall - ein Abdruck INNERHALB der AnythingLLM-Kennung, der den echten
sonst ueberholt.

## 4 · Stand der Anlage

```
Stand     Repo UND Server auf 28e207c (21.09. abends), 30 Commits vor main
Zweig     pfad-identitaet · Rückweg: Tag vor-pfad-identitaet-2026-09-20
          zurück mit: git checkout main && ./aktualisiere.sh
n8n       LÄUFT wieder (seit 21.09.), aber alle Eingänge sind LEER —
          deshalb nimmt die Anlage nichts auf. Bleibt so bis der Umbau steht.
          ⚠ Die Lösch-Wache im Proxy läuft unabhängig davon jede Minute
KAP       Eingang leer · 8 im Archiv · 15 aussortiert · 4.241 geparkt
Bestand   67 Dokumente
Daten     Emrach hat alle Rohdaten lokal — der Serverbestand ist entbehrlich

Bildbeschreibung   Schwelle 0,01 (war 0,08), Massenlauf kann sie NICHT
                   mehr abschalten. Eingespielt und im Betrieb bestätigt.
Aufnahmefilter     ._* und Merkdateien werden übersprungen
Leerer Text        wird aussortiert, NICHT mehr archiviert (Mindestmass
                   20 Zeichen)
Schlüsselmodul     gebaut und gemessen, aber noch von NIEMANDEM aufgerufen
```

## 5 · Der Umbau: was entschieden ist

Ein Dokument wird über seinen **relativen Pfad** identifiziert; Archiv und
Aussortier-Ordner spiegeln die Unterordner des Eingangs. Der Pfad allein reicht
**nicht** — gemessen mit `bau/pfad-messung.py` am echten Bestand:

```
heutiger Schlüssel (nackter Name)   423 Gruppen · 1.587 Dateien · größte 99
mit relativem Pfad                  386 Gruppen ·   785 Dateien · größte  4
mit Pfad + Fingerabdruck              0       ·       0        ·       0
```

Deshalb: **lesbarer Name auf 120 Byte gekürzt + zehnstelliger Fingerabdruck.**
Der Fingerabdruck ist alphanumerisch und überlebt alle acht
Normalisierungsfunktionen; Trennzeichen tun das nie, und Wortersetzungen wie
`&`→`and` ebenfalls nicht (`BUGS_UND_FIXES.md` §11).
**Dateien auf der Platte werden nicht umbenannt.** Dieselbe Datei bei zwei
Kunden wird zweimal aufgenommen. Die bestehenden 66 Dokumente werden nicht neu
aufgebaut.

⭐ **Entschieden am 21.09. — der Bezugspunkt, der seit dem 20.09. offen war:**
Der Abdruck geht **nicht** über den vollen Pfad, sondern über
**Bereichsname + Pfad unterhalb der Stufe**. Die fünf Stufenordner der Kette
(Eingang, Parkplatz, Archiv, Aussortiert, Löschen) fallen heraus.

Grund: Eine Datei wandert Eingang → Parkplatz → Archiv. Wäre die Stufe Teil der
Kennung, bekäme **dasselbe Dokument bei jedem Umzug eine neue** — genau der
Kettenbruch, der behoben werden soll. Erwünschte Nebenwirkung: dieselbe Datei in
Parkplatz und Archiv ist **ein** Dokument, nicht zwei. Zwei Bereiche mit
gleichem Unterpfad bleiben dagegen **getrennt**.

**Zweite Festlegung, verbindlich:** Verglichen wird **ausschließlich der
Fingerabdruck**. Der lesbare Teil ist Bequemlichkeit für Menschen und darf
verstümmelt werden. Keine Codestelle darf den ganzen Schlüssel vergleichen.

**Grenze 200 Byte:** 255 (ext4) − 3 (`.md` beim Upload) − 42 (Aufschlag
`-<uuid>.json`), abgerundet.

## 6 · Offen, vor dem Bauen zu klären

1. ~~Wie AnythingLLM Uploadnamen wirklich umschreibt~~ — **ERLEDIGT 21.09.,
   gemessen** (Einzelheiten `BUGS_UND_FIXES.md` §11):
   - Es ersetzt Zeichen durch **Wörter**: `&` → `and`, `%` → `percent`,
     `€` → `euro`. ⛔ Solche Ersetzungen **überleben** die Normalisierung und
     brechen den Fundstellen-Sprung bei jedem Dokument mit diesen Zeichen.
     `pdfstelle.py:72-94` baut die Umformung nicht nach.
   - Es **kürzt nicht**. Aufschlag **42 Byte** auf den umgeschriebenen Namen,
     bei 255 Byte **HTTP 500**, nutzbare Grenze **200 Byte**.
   - Gleicher Name zweimal → **zwei** Einträge, keine Ablösung.
   - Der Aufschlag ist **nicht konstant** (+39/+40/+42/+14 bei vier Testnamen),
     weil die Umschreibung selbst die Länge ändert. Daraus folgt: Der lesbare
     Teil des Schlüssels muss **vor** der Längenrechnung bereinigt werden,
     sonst ist sie nicht exakt.
2. ~~Die zweite Ursache hinter „Aufnahme unvollständig"~~ — **ERLEDIGT 21.09.:
   es gibt keine zweite Ursache.** Die Zahlen 107 und 147 zählen
   **Protokollzeilen, nicht Dokumente**. Betroffen waren **17 Dateien**,
   dieselben 17 vor wie nach dem Fix, null neue. Der Ablage-Fix `5650806` hat
   gewirkt. Gegenprobe gegen eine blockierte Warteschlange: 7 der 8
   Archivdateien wurden am 18.09. **im Fehlerfenster** abgelegt — neue Dateien
   liefen also durch. Damit ist „null neue" aussagekräftig.
   ⚠ **Die Fehlsuche entstand aus einer Messung am falschen Artefakt:** eine
   Protokolldatei, die je *Versuch* eine Zeile anhängt, wurde als *Dokument*-
   zähler gelesen. Dritter Fall dieser Fehlerklasse in diesem Projekt.

3. **Löschweg, Rechteprüfung, Belegprüfung und `pdfstelle.py` gehören in den
   Umfang.** „Nicht anfassen" war eine Fehlannahme — alle vier hängen am
   Dateinamen.

## 7 · Was als Beweis NICHT zählt

- `dialogtest.py` grün — aber **anders, als eine frühere Fassung dieser Datei
  behauptete.** Ausgezählt am 21.09. über alle 415 Prüfstellen: **79 % prüfen
  echtes Verhalten**, nur 15 % vergleichen Zeichenketten im eigenen Quelltext.
  Die Testreihe ist besser als ihr alter Ruf hier.
  ⛔ **Die Zeichenketten-Prüfungen ballen sich aber genau dort, wo es zählt:**
  Szenario 43 (Hochladen nur mit Rolle) **10 von 10 = 100 %**, Szenario 44
  (Ablage wird angelegt) **8 von 8 = 100 %**. Zu diesen beiden Themen beweist
  ein grüner Lauf ausschließlich, dass bestimmte Zeilen in einer bestimmten
  Reihenfolge im File stehen. Szenario 44 ist ausgerechnet das, was nach dem
  teuersten stillen Fehler des Projekts gebaut wurde.
  ⚠ Und **kein einziges Szenario führt einen Zug durch `_chat`** — die Testreihe
  kann strukturell nicht bemerken, wenn ein deterministischer Weg unerreichbar
  geworden ist.
- `pdfs:` in `/pruef-status` — zählt Schlüssel, nicht Dokumente. Bei Kollision
  steigt die Zahl, obwohl Dokumente fehlen.
- Ein leeres Aussortier-Protokoll — die Übersicht liest nicht rekursiv und sieht
  Dateien in Unterordnern gar nicht.
- n8n „succeeded" — rund 20 Knoten stehen auf „bei Fehler weitermachen".
- Stichproben über den Gesamtbestand — zu 98 % blind. Beweiskraft hat nur die
  Gruppe der 1.587 gleichnamigen Dateien.

- ⛔ **Eine Prüfung, die nicht rot werden kann.** Neu am 21.09., und teuer
  gelernt: In vier aufeinanderfolgenden Planfassungen standen vier Prüfungen,
  die per Konstruktion **immer grün** waren — jede entstand beim Beheben der
  vorigen, keine fiel beim Lesen auf, alle vier sofort beim Ausführen. Beispiele:
  `dateien == schluessel`, wenn beide aus derselben Quelle stammen;
  `pruefe(True, …)` in **beiden** Zweigen eines try/except; `… or
  s.startswith(bereich)`, wenn der lesbare Teil stets mit dem Bereich beginnt.
  ⭐ **Regel: Zu jeder Prüfung gehört der Nachweis, mit welcher Eingabe sie
  fehlschlägt. Steht der nicht dabei, ist die Prüfung nicht fertig.**
- ⛔ **Ein Versuch ohne Gegenprobe, deren erwartetes Ergebnis das umgekehrte
  ist.** Am 21.09. sollte geklärt werden, ob Docling ein gekacheltes Bild als
  eine große Abbildung erkennt. Es tat es — aber die Gegenprobe (fünf getrennte
  Icons, wo Trennen richtig gewesen wäre) lieferte ebenfalls *eine* Abbildung.
  Der Versuch hätte also **jede** Antwort bestätigt, die man von ihm hören
  wollte; die Vorlagen waren zu unrealistisch. Mit besseren Vorlagen trennte die
  Gegenprobe korrekt, und erst dann war das Ergebnis etwas wert
  (`BUGS_UND_FIXES.md` §9e).

**Was zählt:** Prüfsummenvergleich statt Namensvergleich, gezielte Proben in der
Kollisionsgruppe, eine Löschprobe, bei der die **anderen** nachgezählt werden —
und ein Fehlerzähler, der nach dem Fix **stillsteht**.
