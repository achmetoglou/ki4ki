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

## 3g - Stand 22.09., Mittag: Teil 3 abgenommen, Formatprobe laeuft

**Einstieg fuer die naechste Sitzung.** Zweig `pfad-identitaet`.

### Was heute erreicht wurde

✅ **Teil 3 ist abgenommen** (vormittags): Zwei gleichnamige Pruefberichte
in zwei Kundenordnern, beide auffindbar, beide mit eigenem blauem Beleg auf
die richtige Seite mit gelber Markierung.

✅ **Die Formatprobe traegt**: 14 Dokumente im Bereich `zz-schluesselprobe`,
darunter Word, Excel, Text und Outlook-Post. Umlaute und `&` im
Ordnernamen, drei Ebenen tief - die Schluessel stimmen alle.
Die Fachfragen werden richtig beantwortet: **263 °C** (Excel),
**14 Tage** (Text), **371 MPa** (Word), **318/344 MPa** (PDF).

### Die Kette der Fehler, die das gekostet hat

Elf Anlaeufe, elf Fehler - jeder erst sichtbar, nachdem der vorige weg war.
`BUGS_UND_FIXES.md` **16-24**. Die drei wichtigsten:

| | |
|---|---|
| **23** | Eine stoerrige Datei riss den **ganzen Stapel** mit. In der Unterkette war nur der PDF-Weg abgesichert; Tika, Office-Dienst und die vier Extract-Bausteine hatten keine Fehlerbehandlung. Zehn Dateien, ein Ergebnis, alle mit null Zeichen - und "Succeeded" gemeldet. Bei 4.300 Dateien haette das den Nachtlauf gekostet. |
| **(ohne Nummer)** | `pdfs_einlesen()` lief nur ueber `.pdf`. Ein Excel-, Text- oder Word-Dokument stand in keinem Abdruckverzeichnis - dreifach beschaedigt: `nur_altweg` zaehlte falsch, der Name liess sich nicht kuerzen, der Beleg fand es nicht. |
| **24** | ⛔ **OFFEN**: Der Loeschklick raeumt zwei von drei Ablageorten. Das Original in der Ablagestufe bleibt liegen. |

⭐ **Die Lehre des Tages, zweimal gelernt:** Eine Probe aus vier
gleichartigen Dateien beweist nichts. Der Morgenlauf mit vier PDF war gruen
**aus dem falschen Grund** - er hat den einzigen abgesicherten Weg geprueft
und die Bruechigkeit der uebrigen fuenf vollstaendig verdeckt.

### ⛔ Offen, in dieser Reihenfolge

1. **Die drei letzten Fixes am laufenden System pruefen** (`a9759f8`):
   kein "nicht belegt" mehr bei der Excel-Tabelle, kein toter Link mehr
   beim Textdokument, gelbe Markierung bei den PDF-Sprungzielen.
2. ⛔ **Die Positivliste sitzt HINTER dem Upload.** Eine `.msg` wird
   hochgeladen, eingebettet - und erst danach aussortiert. Drei
   Outlook-Nachrichten liegen deshalb im Arbeitsbereich
   `zz-schluesselprobe` und muessen dort geloescht werden. Der Filter
   gehoert VOR "Dateien in JSON umwandeln".
3. **`nur_altweg` nachmessen.** Es stand bei 73 statt 67, weil der Index
   nur PDF kannte. Nach dem Index-Fix sollte es auf 67 zurueckfallen.
   Faellt es nicht, ist etwas anderes offen - und dann taugt der Zaehler
   weiterhin nicht als Abschaltsignal fuer die Uebergangsstuetze.
4. Dann erst **KAP** (~12,7 h, ueber Nacht).

### Zahlen am echten KAP-Bestand (`bau/formate-zaehlen.py`, 22.09.)

```
Dateien insgesamt: 4325
  Docling (pdf)        783
  Office->PDF         1137   doc 559, docx 345, pptx 140, ppt 92
  Excel                134
  Text/CSV             175
  Tika-Rueckfall       386   001: 72, xlsm: 65, msg: 65, tra: 34, ...
  ohne Text           1707   jpg 787, tif 691, db 87
```

⭐ **Von 4.300 Dateien haben nur rund 2.300 ueberhaupt Text.** Die 1.707
Bilddateien landen in der Aussortierstufe mit Begruendung - ihre Zuordnung
zu Kunde und Auftrag bleibt erhalten (gemessen: derselbe Schluessel auf
jeder Stufe), sie sind also spaeter nachholbar, **ohne** den Lauf zu
wiederholen.

⚠ Emrach hat sie durchgesehen: Mikroskopaufnahmen mit Massstab, Fotos von
Pruefstaenden und Bauteilen, Diagramme, handschriftliche Skizzen **und
eingescannte Vertraege**. Also drei verschiedene Beduerfnisse
(Bildbeschreibung, Texterkennung, beides) - ein eigener Bauabschnitt nach
KAP.

### Was heute bewusst NICHT gebaut wurde

- **Die Art eines Dokuments** (Auftrag 3f). Mails bleiben bis dahin
  draussen.
- **Bildbeschreibung fuer Einzeldateien.** Erst KAP, dann die Bilder.
- **Belegsprung fuer Text und Tabellen.** Sie haben keine Seiten; ein
  Sprung braeuchte eine Wandlung nach PDF wie bei Word.

## 3f - AUFTRAG: Die Art eines Dokuments (offen, nach dem KAP-Lauf)

⭐ **Nachgeschaerft am 22.09., abends.** Die Entscheidung ist gefallen und
sie lautet **nicht** "Mails aussortieren", sondern:

> **Die Mails werden aufgenommen. In der Antwort steht, WOHER die Auskunft
> kommt** - "aus diesem Dokument", "aus der E-Mail vom ...".

Das ist die bessere Loesung, weil der Wert der Mails gerade in dem liegt,
was nur dort steht: Absprachen, Rueckfragen, Zusagen. Wer sie aussortiert,
verliert den Zusammenhang eines Auftrags. Wer sie ohne Kennzeichnung
aufnimmt, bekommt eine Absprache als Spezifikation serviert.

Der Unterschied liegt also nicht im Bestand, sondern im **Beleg**:

```
❌ "Die Prozesstemperatur betraegt 240 °C (Dokument, S. 1)."
✅ "Laut E-Mail vom 14.03. an Herrn X wurden 240 °C abgesprochen -
     eine Absprache, keine Spezifikation."
```

### Warum das kein Modellproblem ist

Das Modell sieht nie den Bestand, sondern acht Textstuecke. In einem steht
*"die Prozessimulation haben wir mit 240 Grad gerechnet, passt so"*. Dass
das eine interne Mail von Dienstag ist, steht nicht dabei. Kein Modell kann
unterscheiden, was ihm niemand mitteilt - eine Frage der Information, nicht
der Klugheit.

### Vier Teile, in dieser Reihenfolge

1. **Art bestimmen.** Aus dem Pfad, den der Schluessel seit Teil 3 traegt
   (`.../Angebote/...` → Angebot, `.../Pruefberichte/...` → Pruefbericht)
   und aus der Endung (`.msg`, `.eml` → Korrespondenz).
   ⚠ `bestand.art_von()` gibt es schon, leitet die Art aber aus einer
   KENNUNG ab (`DS-24-005`) - fuer Pfadbestaende fehlt der Weg.

2. **Absender und Datum aus der Mail holen.** Ohne beides ist "aus der
   E-Mail vom ..." nicht schreibbar. Tika liefert die Kopfzeilen mit; sie
   muessen als Metadaten am Dokument haengen, nicht nur im Fliesstext
   stehen.

3. **Den Beleg die Art nennen lassen.** Nicht "(Dokument, S. 1)", sondern
   "(E-Mail vom 14.03.)". Die Belegklammer kennt den Anzeigetitel seit dem
   22.09. - hier kommt die Art daneben.

4. **Die Rangfolge im Prompt.** Widersprechen sich Korrespondenz und
   Fachunterlage, gewinnt die Fachunterlage - und die Antwort sagt, dass es
   einen Widerspruch gibt. Eine Mail darf eine Spezifikation ERGAENZEN,
   nie ERSETZEN.

### ⛔ Was bis dahin gilt

Die Positivliste laesst `.msg`/`.eml` weiterhin in die Aussortierstufe
laufen - **mit Begruendung und ohne Verlust**. Gemessen am 21.09.: Der
Schluessel ist auf jeder Stufe derselbe, die Zuordnung zu Kunde und Auftrag
bleibt erhalten. Die Mails sind also **spaeter nachholbar, ohne den
12,7-Stunden-Lauf zu wiederholen**.

⭐ Deshalb die Empfehlung fuer den KAP-Lauf: **erst ohne Mails laufen
lassen.** Kaemen die 65 `.msg` ohne die Herkunftsangabe mit hinein,
entstuende genau der Fehler, gegen den dieser Auftrag gebaut wird - und der
waere dann im Bestand, nicht nur in der Antwort.

### Weiter gedacht: Postfaecher ausscheidender Mitarbeiter

Laengerfristig sollen ganze Postfaecher eingespeist werden koennen, damit
ein Nachfolger Kontext und Absprachen kennt, wenn die Uebergabe knapp war.
Dann wird aus der Herkunftsangabe eine Pflicht: Bei tausenden Mails ist
"woher kommt das" die einzige Bremse gegen falsche Sicherheit.

⛔ **Vorher zu klaeren, nicht nebenbei:** Ein Postfach enthaelt
Privates, Personalangelegenheiten und Mails Dritter. Das ist eine Frage
fuer Datenschutz und Betriebsrat, keine technische.

## 3e - Teil 3: GEBAUT und am laufenden System belegt (Stand 22.09.)

### ⭐ Was die Abnahme vom 22.09. gezeigt hat

Vier erfundene Dokumente in den Arbeitsbereich `zz-schluesselprobe`, mit
Unterordnern. Gemessen an `/pruef-status`:

| | vorher | nachher | Lesart |
|---|---|---|---|
| `bestand` | 67 | **71** | vier neue Eintraege, **vier verschiedene** |
| `nur_altweg` | 67 | **67** | ⭐ jedes der vier traegt einen Abdruck |
| `altweg_belege` | 0 | **0** | der alte Weg wurde nicht gebraucht |

⭐ Die **71** ist die aussagekraeftige Zahl, nicht die 67: Die zwei
Pruefberichte heissen auf der Platte gleich und liegen nur in verschiedenen
Kundenordnern. Unter dem alten Schluessel waere einer als Dublette verworfen
worden und der Zaehler bei 70 stehengeblieben.

In der Oberflaeche standen die Pfad-Schluessel mit Unterordner
(`...-KundeAlpha-Pruefbericht--<abdruck>.md`), die Frage nach der
Zugfestigkeit brachte **beide** Zahlen aus **zwei** getrennten Quellen.

⛔ **Was dabei NICHT ging - und warum es nicht am Umbau lag:** Es entstand
kein blauer Beleg. Ursache war der Zitatwaechter, der `ue` nicht wie `ü`
liest; meine Probedokumente standen in Behelfsschreibung. Siehe
`BUGS_UND_FIXES.md` **16**. Behoben, und die Probedokumente tragen jetzt
echte Umlaute - damit prueft die Wiederholung den Umbau und nicht den Fix.

### ⛔ Zweiter Anlauf (22.09., Mittag): der Beleg fehlte immer noch

Der Umlaut-Fix aus BUGS 16 lief nachweislich im Container - und es entstand
trotzdem kein Beleg. **Bei Gemma UND Qwen gleich**, also nicht das Modell.

Der wahre Grund stand eine Ebene tiefer: Die Klammerpruefung `_beleg()`
kannte nur volle Titel, das Modell schreibt aber nur den Abdruck. Sie stieg
aus, bevor irgendeine Seitenpruefung lief. **BUGS 18.**

⛔ **Das ist eine zwoelfte Vergleichsstelle**, die der Plan zu Teil 3 nicht
aufgefuehrt hat. Die elf bekannten sind umgestellt; diese hier war ein
eigener Vergleich derselben Klasse wie `dokument_erlaubt` und der
Loeschweg. Wer nach weiteren sucht: Es sind die Stellen, die einen
GESCHRIEBENEN Namen gegen die Identitaet eines Dokuments halten - nicht die
32 Aufrufer von `_pdf_schluessel`.

⭐ **Und ein Fund, der ohne diesen Umweg nicht aufgefallen waere:** Das
doppelte Trennzeichen des Schluessels ueberlebt AnythingLLM nicht. Die
Dateiliste zeigt `--`, die Fundstelle liefert `-`. `anzeigetitel()` schnitt
am `--` ab - nach dem Neueinlesen waere damit der ganze Schaden aus **13**
zurueckgekommen: kein Katalogeintrag, keine Kennung, kein K3-Tor. **BUGS 19**,
behoben; abgeschnitten wird jetzt am Abdruck, nicht am Trennzeichen.

### ✅ ABNAHME BESTANDEN (22.09., nachmittags)

Vier Probedokumente, zwei gleichnamige Pruefberichte in zwei Kundenordnern.
Die Frage nach der Zugfestigkeit bringt **beide** Zahlen, jede mit einem
**blauen Beleg**, der auf das **richtige** Dokument und die richtige Seite
springt; die Stelle ist dort gelb markiert. `bestand` 67 -> 71,
`nur_altweg` unveraendert 67, `altweg_belege` 0.

Bis dahin brauchte es vier Anlaeufe, und jeder hat den naechsten Fehler
freigelegt, weil der vorige ihn verdeckte: BUGS **16** (Umlaut im
Zitatwaechter), **18** (Klammer kannte nur volle Titel), **19** (doppeltes
Trennzeichen ueberlebt AnythingLLM nicht), **20** (Klammer und Sprung
benutzten zwei Namen), **21** (zwei Umlaut-Regeln im Zitatvergleich).

⭐ **Die Lehre, die ueber Teil 3 hinausgeht:** An jeder Modulgrenze sitzt
eine eigene Normalisierung, und sie sind sich nicht einig. Gezaehlt sind
inzwischen **vier** Stellen, die Umlaute behandeln - mit **drei**
verschiedenen Regeln. Zwei davon sind vereinheitlicht (`pruef_proxy`,
`fadenfrage`), zwei behalten bewusst ihre eigene (`veredeln`,
`pdfstelle._glatt`), weil sie IM Seitentext suchen.

### ⚠ Bekannte Restschwaeche (kein Hindernis fuer KAP)

`pdfstelle._glatt()` macht nur klein; "beträgt" und "betraegt" sind dort
verschiedene Woerter. Trifft ein Zitat mit Umlaut auf ein Dokument in
Behelfsschreibung, findet der Dreiwort-Einstieg nichts; es greift der
Zweiwort-Einstieg oder der Stichwort-Rueckfall. Die Markierung wird dann
ungenauer, der **Link bleibt richtig**.

⭐ **Warum das KAP nicht aufhaelt:** Es betrifft nur die Darstellung, nicht
die Aufnahme. Der Fix ist jederzeit nachtraeglich moeglich, **ohne neu
einzulesen**. Echte Dokumente tragen ausserdem echte Umlaute - der
gemischte Fall entstand nur, weil die Probedokumente in Behelfsschreibung
gesetzt waren (inzwischen berichtigt).

### ⛔ Offen: die Belegmessung (Aufgabe 7, Schritt 5)

Nach dem naechsten `./aktualisiere.sh` dieselbe Frage im selben Bereich
stellen. **Erwartet: zwei blaue Belege**, die auf zwei verschiedene
Dokumente springen. Erst das ist der Beweis, dass der Belegweg ueber den
Abdruck traegt - vorher wird **nicht** neu eingelesen.

⚠ Eine Gegenprobe an echten Bestandsdokumenten gibt es nicht: Die 67 alten
tragen keinen Abdruck und laufen ueber die Uebergangsstuetze. Die vier
Probedokumente sind zurzeit die einzigen mit Abdruck.

## 3e-alt - Stand vom 21.09. (spaeter Abend)

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
| 7 | `bb3817d` | Belegvergleich am Abdruck - vier realistische Modell-Abweichungen geprueft |
| 8 | `af7d146` | Rechtepruefung am Abdruck, fail-closed |
| 9 | `3d1611b` | Loeschweg - ein Klick loescht ein Dokument, nicht 99 |
| 10+11 | `3883505` | Aufnahmekette in n8n, beide Unterordner-Fehler, Ablaufpruefung |
| Probe | `ebc78e2` | zwei Fehler am laufenden System gefunden (siehe unten) |
| Loeschen | `964c59c` | der dritte Ablageort wird mitgeraeumt (BUGS 14) |

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
| 12 | Ausrollen, neu einlesen, Uebergangsstuetze entfernen | ⛔ **der einzige noch offene Schritt - er gehoert Emrach** |

### ⛔ Was die erste Probe am laufenden System aufgedeckt hat (21.09.)

Vier erfundene Dokumente (`bau/probedokumente.py`) in einen Testbereich - und
**drei Fehler, bevor KAP durchlief.** Genau dafuer war die kleine Probe da.

1. **Der Uploadname kam nie vom Schluessel.** Er entsteht in Ablaufplan 3
   (`basisname`), nicht im Knoten "JSON-Datei fuer Dokumente vorbereiten".
   Die Aenderung dort war wirkungslos; in AnythingLLM standen weiter die
   alten Dateinamen. Behoben in `ebc78e2`.
2. **`$json` in einer `.map()`-Schleife ist immer das ERSTE Element.** Der
   Waechter haette allen Dateien eines Durchgangs den Schluessel der ersten
   gegeben - genau die Dublettenfalle, die der Umbau beseitigt. Jetzt
   `doc.schluessel` je Element.
3. ⛔ **`mv: Permission denied`.** Ordner, die ein Mensch per SFTP anlegt,
   gehoeren ihm und haben oft kein Gruppen-Schreibrecht. Die Aufnahme darf
   die Datei dann nicht herausbewegen; sie bleibt im Eingang und wird bei
   JEDEM Minutentakt erneut aufgenommen. Aus einer Datei wurden fuenf
   Eintraege. ⭐ **Regel, die damit dazukommt: nach jedem Einspielen per
   SFTP `docker compose up -d rechte-init`.** Steht in `doku/BETRIEB.md` 5.

⭐ **Und ein vierter beim Aufraeumen:** Ein Dokument hat DREI Ablageorte -
Original, Textfassung in AnythingLLM und die erzeugte Markdown-Fassung im
Volume `austausch-md`. Den dritten raeumte niemand; dort lagen Volltexte
zurueck bis August, darunter dem Namen nach vertrauliche Unterlagen.
`BUGS_UND_FIXES.md` 14, behoben in `964c59c`. Die Altlast ist am 21.09. von
Hand geraeumt worden (74 Dateien, `bestand` blieb dabei bei 67 - Beweis, dass
nichts daran hing).

### ⛔ Aufgabe 12: die Reihenfolge, in der eingelesen wird

**Nicht mit KAP anfangen.** Ein Neu-Einlesen von KAP dauert 12,7 Stunden; geht
dabei etwas schief, ist die Zeit weg. Deshalb in dieser Reihenfolge:

1. `./aktualisiere.sh` - baut Proxy und mkmd-Dienst neu und spielt die
   Ablaufplaene ein.
2. **Ein kleiner Bereich zuerst**: Arbeitsbereich in der Oberflaeche anlegen,
   die vier Dokumente aus `bau/probedokumente.py` MIT ihren Unterordnern nach
   `input/`, **dann `docker compose up -d rechte-init`**, einen Durchgang
   abwarten, dann nachsehen:
   - ⭐ **`nur_altweg` muss BLEIBEN, wo es war** (67). Steigt es mit, trägt
     das neue Dokument keinen Abdruck - dann ist der Schluessel wieder nicht
     angekommen, und nichts wird neu eingelesen, bevor das geklaert ist.
   - In der Oberflaeche muessen Namen wie
     `<bereich>-KundeAlpha-Pruefbericht--a1b2c3d4e5.md` stehen, und **zwei**
     Pruefberichte statt einem.
   - Die Frage "Welche Zugfestigkeit steht in den Pruefberichten?" muss
     **beide** Zahlen bringen (412 und 287), mit zwei verschiedenen blauen
     Belegen. Das ist der eigentliche Beweis des ganzen Umbaus.
   - `curl localhost:3001/pruef-status` - `bestand` steigt, `nur_altweg`
     sinkt
   - eine Fachfrage an diesen Bereich: kommt ein **blauer** Beleg? Springt
     der Klick auf die richtige Seite?
3. **Erst dann die Belegmessung**, die vorher gar nichts sagen konnte: Ohne
   ein Dokument MIT Schluessel kann das Modell keinen Abdruck mitschreiben.
   Aus `/kpi` den Anteil quellenbasierter Antworten vorher und nachher
   vergleichen, dazu `altweg_belege` aus `/pruef-status`.

| Ergebnis | Folge |
|---|---|
| Belegquote nachher etwa wie vorher | traegt, weiter im Plan |
| Belegquote bricht ein | ⛔ **anhalten** - das Modell schreibt den Abdruck nicht mit. Dann wird der Anzeigename-Weg gebaut, BEVOR irgendetwas neu eingelesen wird |

⭐ Gegenprobe, ohne die die Zahl nichts sagt: Mindestens eine der drei
Antworten muss ueberhaupt eine Fundstelle gehabt haben. Kommt die Suche in
allen dreien leer zurueck, ist die Belegquote aus einem anderen Grund 0 und
die Messung ungueltig.

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
python3 schluesselwege_test.py                      52 Pruefungen
python3 dialogtest.py                              519 Pruefungen
python3 wegabgleich.py                               0 Loecher
python3 ../bau/abdruck-messung.py                  sechs Zahlen
cd .. && python3 bau/ablauf_pruefen.py              26 Pruefungen
bash bau/sperrprobe.sh            zeigt den Unterordner-Fehler im Vergleich
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
