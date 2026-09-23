# Einstieg in die nächste Sitzung

**Stand 23.09.2026, nachmittags.** Diese Datei ersetzt das Zusammensuchen am
Sitzungsanfang. Sie sagt, wo die Ziele stehen, was entschieden ist, was offen
ist und was als Beweis zählt. **Erst lesen, dann arbeiten.**

⭐ **Wer nur eines liest: §3v** - Stand der Abnahmen und was offen ist.
Die drei Nutzermeldungen stehen in §3l; die vom 17.09. ist erledigt.

⭐ Frueherer Zeiger: §3l — drei offene Nutzermeldungen. Die vom
17.09. ist in §3n repariert. ⛔ **Drei Reparaturen warten auf Abnahme am
laufenden System** (§3m Return-Knoten, §3n Chat-Anhang, §3o Leerlauf-
Meldung). Erst abnehmen, dann weiterbauen — Stapeln hat am 22.09. den
Schaden angerichtet.

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

## 4k - GEBAUT 23.09. spaet: das Kontextfenster passt sich der Frage an

Gemessen, nachdem qwen3.8 zu 100 % auf der Karte lief:

```
1m 2s (15.50 tok/s)
```

Immer noch langsam - aber aus einem neuen Grund: `num_ctx` stand fest auf
**65.536**. Der Zwischenspeicher fuer die Aufmerksamkeit waechst mit dem
EINGESTELLTEN Fenster, nicht mit dem, was wirklich drinsteht. Jedes Token
kostet damit Rechenzeit fuer Platz, der leer bleibt.

`gespraech.kontextfenster()` waehlt jetzt die kleinste passende Stufe:

```
 8.192  kurzer Chat-Zug
16.384  mittlere Frage mit Fundstellen
32.768
65.536  Zusammenfassung eines grossen Dokuments
```

### ⛔ Die Falle, die dabei zu vermeiden war

Ein zu kleines Fenster ist **schlimmer** als ein zu grosses: Ollama wirft
den Anfang des Prompts weg - **still, ohne Meldung**. Die Antwort stuetzte
sich dann auf Dokumente, die gar nicht mehr dastehen, und niemand merkt
es. Genau die Sorte stiller Fehler, die dieses Projekt sonst jagt.

⭐ Deshalb gibt `kontextfenster()` auch zurueck, **ob** es passt, und der
Aufrufer meldet es:

```
[Kontext] 214000 Zeichen passen nicht in 65536 Token - der Anfang geht verloren
```

### Womit die Pruefung rot wird

`test_kontextfenster_passt_sich_an` und
`test_das_fenster_ist_nie_zu_klein`. Gegen den Stub (immer 65536):
**3 Fehler**. Mutationsprobe (wieder fest 65536): **2 Fehler**. Danach 0.

⭐ Die zweite Pruefung ist die wichtigere: Sie rechnet fuer fuenf
Groessen nach, dass das gewaehlte Fenster **nie kleiner** ist als das,
was der Prompt braucht. Eine Tempo-Optimierung, die Belege verschluckt,
waere schlimmer als der langsame Zustand.

### ⚠ Abnahme

Dieselbe fachliche Frage in AuW stellen und die Token-Rate vergleichen.
Vorher **15,50 tok/s**. Bleibt sie gleich, ist das Fenster nicht der
Hebel - dann steht der naechste Verdacht an (Modellgroesse: qwen3.8 ist
mit 17 GB deutlich groesser als gemma4:12b mit 8,9 GB).

## 4j - GEBAUT 23.09. spaet: aufgegebene Anfragen werden bei Ollama abgesagt

Die Reparatur zum Befund aus §4i.

`pruef-proxy/ollamaruf.py` fuehrt die Verbindung zu Ollama selbst und
schliesst sie in einem `finally` - in JEDEM Fall, auch bei
Zeitueberschreitung. Nur daran merkt Ollama, dass niemand mehr zuhoert,
und bricht die Erzeugung ab.

⛔ Vorher: `urllib.request.urlopen(req, timeout=...)`. Laeuft die
Zeitgrenze ab, wirft das eine Ausnahme und ueberlaesst die Verbindung dem
Aufraeumer. Ollama merkt davon nichts.

### Alle vier Aufrufstellen umgestellt

| Datei | wofuer |
|---|---|
| `gespraech.py` | der Gespraechsmodus - die langen Antworten, hier entstanden die Zombies |
| `pruef_proxy.py` | Zusammenfassungen (Zeitgrenze 900 s) |
| `absicht.py` | Absichtserkennung |
| `assistent.py` | Auffangnetz, zwei Stellen |

⭐ Gegenprobe: `grep "with urlopen"` findet in diesen Dateien **keine**
Stelle mehr, die Ollama ohne Absage ruft. Genau die Sorte Durchgang, die
am 04.08. gefehlt hat ("13 Stellen, 3 gefunden").

### Womit die Pruefung rot wird

`ollamaruftest.py`, 4 Faelle mit einem vorgetaeuschten Draht, der
mitschreibt, ob er geschlossen wurde:

```
Stub (heutiges urlopen-Verhalten)        Fehler (geht ins echte Netz)
close() aus dem finally entfernt         3 Fehler
nach der Reparatur                       0 Fehler
```

⭐ Der entscheidende Fall heisst
`test_zeitgrenze_sagt_ollama_ab`: Die Zeitueberschreitung muss beim
Aufrufer ankommen UND die Leitung muss zu sein. Beides zusammen, sonst
ist es keine Absage.

⚠ Was die Pruefung NICHT zeigt: ob Ollama daraufhin wirklich abbricht.
Das ist eine Eigenschaft von Ollama, nicht von uns. **Abnahme:** Eine
Anfrage in die Zeitgrenze laufen lassen und danach im Protokoll
nachsehen, ob noch ein Auftrag rechnet:

```bash
docker logs --since 2m ki4ki-ollama 2>&1 | grep "print_timing" | tail -3
```

Kommt dort nach dem Abbruch nichts mehr, ist der Zombie weg.

## 4i - ⭐⭐⭐ DIE TODESSPIRALE: abgebrochene Anfragen rechnen weiter

Im Ollama-Protokoll gefunden, waehrend `ollama stop` haengen blieb:

```
slot id 0 | task 764  | n_gen = 1131 | tg = 0.41 t/s
slot id 1 | task 434  | n_gen = 1459 | tg = 0.41 t/s
```

⛔ **0,41 Token pro Sekunde.** Nicht 53,9 - null Komma vier. Und zwei
Auftraege liefen **immer noch**, obwohl die Anfragen laengst abgebrochen
waren.

### Die Kette

1. Eine Anfrage laeuft in die Zeitgrenze, der Browser gibt auf.
2. **Ollama rechnet trotzdem weiter** - niemand sagt ihm, dass keiner
   mehr zuhoert.
3. Der Auftrag belegt weiter einen Rechenplatz und das halb auf der CPU
   liegende Modell.
4. Die naechste Frage teilt sich die lahme Haelfte mit dem Zombie.
5. Beide werden langsamer → mehr Abbrueche → mehr Zombies.

⭐ **Deshalb wurde es im Lauf des Abends immer schlimmer statt besser.**
Bei 0,41 t/s braucht eine Antwort von 2.000 Token 81 Minuten. Kein
Token-Deckel der Welt haette das gerettet - und ich habe vier Stunden an
Token-Deckeln gedreht.

⚠ `ollama stop` blieb auf `Stopping...` stehen: Solange gerechnet wird,
laesst sich das Modell nicht entladen. Auch das war ein Symptom, kein
eigenes Problem.

### Der Weg zurueck (23.09., gemessen)

```
Ausgangslage        927 MiB frei   (Docling 5 Worker + 3 Modelle + 2 Zombies)
nach Docling=1   12.313 MiB frei   (-11,4 GB durch die Worker)
nach ollama-Neustart
                 44.629 MiB frei   (Zombies weg, alle Modelle entladen)
```

⭐ Von **927 MiB auf 44.629 MiB**. Die Modelle laden bei der naechsten
Frage von selbst nach - in einen fast leeren Speicher, also vollstaendig
auf die Karte.

### ⛔ Der Fehler, der daraus zu beheben ist

**Wenn der Proxy aufgibt, muss er Ollama absagen.** Heute laesst
`urlopen` die Verbindung nach `TIMEOUT` einfach fallen; Ollama merkt
davon nichts und rechnet ins Leere. Jede gescheiterte Anfrage
hinterlaesst einen Zombie, der die naechste verlangsamt.

Zu bauen (mit Pruefung, nicht heute Nacht):

| | |
|---|---|
| Abbruch weiterreichen | Die Verbindung sauber schliessen, damit Ollama die Erzeugung abbricht - Ollama beendet einen Lauf, wenn der Client geht, aber nur bei einem ECHTEN Verbindungsabbruch |
| Zombies sichtbar machen | Beim Start und periodisch `ollama ps` auswerten: laeuft etwas, das niemand angefordert hat? Ins Sichtfenster `ki4ki-ueberblick.sh system` |
| Nicht mehrere gleichzeitig | Pro Gespraech laeuft schon nur eine Frage (WARTE_TEXT). Ueber Gespraeche hinweg nicht - zwei Nutzer, zwei Slots, halbe Geschwindigkeit |

### ⚠ Was dieser Tag ueber Messen lehrt

Ich habe nacheinander vermutet und gedreht: Token-Deckel, Zeitgrenze,
Lebenszeichen, Rundenzahl. Jede Aenderung war fuer sich richtig. **Keine
war die Ursache.**

Die Ursache bestand aus drei Dingen, die sich gegenseitig verstaerkten
und alle drei in zwanzig Sekunden messbar waren:

```
nvidia-smi                     -> 927 MiB frei von 46 GB
docker exec ... ollama ps      -> gemma4:12b 49%/51% CPU/GPU
docker logs ki4ki-ollama       -> 0.41 t/s, zwei Zombie-Auftraege
```

⭐ **Regel, teuer gelernt:** Wenn etwas langsam ist, misst man ZUERST
die Maschine - Speicher, Auslastung, was laeuft ueberhaupt. Erst danach
die Einstellungen. "Langsam" ist eine Aussage ueber den Zustand der
Anlage, nicht ueber den Parameter, den man gerade in der Hand haelt.

## 4h - ⭐⭐⭐ BEWIESEN UND BEHOBEN: das Chat-Modell rechnete zur Haelfte auf der CPU

```
NAME              SIZE      PROCESSOR          UNTIL
gemma4:e2b        2.0 GB    100% GPU           Forever
gemma4:12b        8.9 GB    49%/51% CPU/GPU    23 hours   ⛔
qwen3.8:latest    17  GB    100% GPU           22 hours

ki4ki-docling            12.222 MiB  (DOCLING_SERVE_ENG_LOC_NUM_WORKERS=5)
frei                        927 MiB von 46.068
```

⛔ **`gemma4:12b` ist das Modell des Gespraechsmodus** - also genau das,
das die Chats beantwortet. Es lief zu **51 % auf der CPU**. Das erklaert
alles von heute Abend: 53,9 Token/s, 140 s, 160 s, Abbrueche bei 240 s.

### Warum Ollama es nicht selbst geloest hat

⭐ Die Erklaerung liegt im Zusammenspiel, nicht in einer einzelnen
Einstellung:

1. Docling haelt mit **fuenf Workern** 12,2 GB - jeder Worker haelt seine
   eigenen Modelle.
2. qwen3.8 (17 GB) ist mit `keep_alive: 24h` **festgenagelt**.
3. Als gemma4:12b geladen werden sollte, war kein Platz mehr - und Ollama
   **durfte** qwen nicht verdraengen.
4. Also schob es gemma zur Haelfte auf die CPU. Kein Fehler, keine
   Meldung: es rechnet eben langsamer.

⚠ `keep_alive: 24h` ist fuer sich genommen richtig (Emrach: *"doch, soll
er - ausser man wechselt im chat, dann soll das erst laden"*). Falsch ist
die **Kombination** aus drei festgenagelten Modellen und einem
Docling, das die Haelfte des Speichers besetzt haelt, ohne zu arbeiten.

### Behoben (sofort, weil es jede Partner-Anlage betrifft)

```yaml
- DOCLING_SERVE_ENG_LOC_NUM_WORKERS=${KI4KI_DOCLING_WORKERS:-1}
```

Rechnung: Docling faellt von 12,2 GB auf rund 2,4 GB. Dann stehen

```
qwen3.8 17,0 + gemma4:12b 8,9 + gemma4:e2b 2,0 + docling 2,4 = 30,3 GB
frei: rund 15,7 GB  ->  gemma4:12b passt GANZ auf die Grafikkarte
```

⚠ Ein Tausch: Ein Worker wandelt Dokumente langsamer. Fuer einen grossen
Aufnahmelauf `KI4KI_DOCLING_WORKERS` hochsetzen, danach zurueck - der Chat
laeuft jeden Tag, die Aufnahme nicht.

⛔ **Fuer Partner besonders wichtig:** Wer eine kleinere Karte hat als
die A40 (46 GB), trifft das frueher und haerter. Emrach: *"das wird den
partnern jetzt schon aergern dass das so laeuft."*

### ⭐ Das eigentliche Ziel: Speicher nach Bedarf, nicht auf Vorrat

Emrach, woertlich: *"wir brauchen ein intelligentes system... wenn
dokumente verarbeitet werden soll docling kommen... wenn nicht, dann raus
damit... auch beim modellwechsel in den threads... rein raus rein raus."*

Richtig, und es ist machbar - die Bausteine gibt es schon:

| Wann | Was | Wie |
|---|---|---|
| Aufnahme startet | Docling hoch | n8n hat schon einen Baustein "Grafikkarte freigeben"; dieselbe Stelle kann den Container starten |
| Aufnahme fertig | Docling runter | Container stoppen gibt den Speicher **sicher** frei - `/v1/clear/converters` tat es nachweislich NICHT (12,2 GB standen trotz Aufruf) |
| Modellwechsel im Thread | altes Modell entladen | Ollama nimmt `keep_alive: 0` je Anfrage - ein Aufruf auf das alte Modell gibt es frei, bevor das neue laedt |

⚠ Der Preis ist jeweils die **Ladezeit beim Wiederkommen**: Docling
braucht beim Start seine Modelle, ein Sprachmodell zehn bis dreissig
Sekunden. Genau deshalb darf nur das raus, was gerade NICHT gebraucht
wird - und das aktive Modell bleibt festgenagelt.

⛔ Das ist ein eigenes Stueck Arbeit mit eigener Abnahme, nicht ein
Handgriff heute Abend. Aber es ist der richtige Entwurf, und die
Reparatur oben macht ihn nicht ueberfluessig, sondern kauft Zeit dafuer.

### ⚠ Was ich daraus lerne

Ich habe sechs Stunden an Token-Deckeln, Zeitgrenzen und Lebenszeichen
gearbeitet. Alles davon war notwendig - aber **nichts davon war die
Ursache**. Ein `nvidia-smi` und ein `ollama ps` haetten in zwanzig
Sekunden gezeigt, dass die Maschine zur Haelfte auf der CPU rechnet.

⭐ **Regel:** Bevor man an Stellschrauben dreht, misst man, ob die
Maschine ueberhaupt laeuft, wie sie soll. "Es ist langsam" ist eine
Aussage ueber die MASCHINE, nicht ueber die Einstellung, die man gerade
in der Hand haelt.

## 4g - ⭐⭐⭐ DIE EIGENTLICHE URSACHE: die Grafikkarte ist voll

Emrach, woertlich: *"die antworten muessen wie aus der pistole geschossen
kommen.. bei jeder frage... wie bei chatgpt oder claude"*.

Gemessen am 23.09. abends, nachdem ich stundenlang am Token-Deckel
gedreht hatte:

```
Grafikspeicher  46.068 MiB gesamt | 44.564 belegt | 927 MiB frei

ki4ki-ollama    22.238 + 4.032 + 6.030 = 32.300 MiB  (drei Modelle)
ki4ki-docling                            12.222 MiB
```

⛔ **927 MiB frei von 46 GB.** Das ist derselbe Zustand, der am
04.08. schon einmal dokumentiert wurde - dort stand woertlich:
*"Docling gibt Grafikspeicher NIE frei. Ollama bekam 931 MiB und
rechnete auf der CPU (4,4 statt ~40 t/s)."* Damals 931 MiB, heute 927.

⭐ **Ollama haelt drei Modelle gleichzeitig.** Unser eigener Code setzt
`keep_alive: "24h"` an vier Stellen (`absicht.py`, `gespraech.py`,
`assistent.py`, `pruef_proxy.py`).

⛔ **Das ist RICHTIG so, und mein erster Schluss daraus war falsch.**
Emrach, woertlich: *"doch, soll er - ausser man wechselt im chat, dann
soll das erst laden."* Genau. Ein entladenes Modell muss beim naechsten
Mal von der Platte gelesen werden; das sind zehn bis dreissig Sekunden
VOR der ersten Antwort. Wer `keep_alive` kuerzt, macht die erste Frage
nach jeder Pause langsam - also genau das Gegenteil des Ziels.

⭐ **Das Problem ist nicht, WIE LANGE die Modelle bleiben, sondern DASS
ES DREI SIND.** Die Frage lautet nicht "schneller entladen?", sondern
"warum sind drei gleichzeitig noetig?".

### ⛔ Was ich falsch gemacht habe

Ich habe den ganzen Abend am **Token-Deckel** gedreht: 1800 → 8192 → 4096
→ 2048. Jedes Mal wurde die Antwort nur **kuerzer**, nie schneller. Der
Deckel begrenzt, WIE VIEL geschrieben wird - nicht, wie schnell.

⭐ **Fuenfte Spielart derselben Regel aus §7:** Ich habe die Stellschraube
gemessen, die ich in der Hand hatte, statt die Maschine, die die Arbeit
macht. Ein `nvidia-smi` haette das in zehn Sekunden gezeigt - und es
stand als Fundstelle seit dem 04.08. in unserer eigenen Doku.

### ⭐ Und der zweite, unabhaengige Grund: wir streamen nicht

ChatGPT und Claude fuehlen sich nicht deshalb schnell an, weil sie
schneller rechnen - sondern weil das **erste Wort nach einer Sekunde**
dasteht. Unser Proxy ruft das Modell mit `"stream": False` und zeigt
**gar nichts**, bis alles fertig UND geprueft ist.

⛔ Das ist bewusst so gebaut: Die Antwort wird gegen die Dokumente
geprueft, bevor sie erscheint. Nichts Ungeprueftes geht raus - das ist
der Produktanspruch.

⚠ **Aber der Preis ist genau das Gefuehl, ueber das sich Emrach
beschwert.** Diese Abwaegung gehoert entschieden, nicht stillschweigend
beibehalten:

| Weg | Gefuehl | Beleg |
|---|---|---|
| heute: erst pruefen, dann zeigen | stumme Wartezeit | nichts Ungeprueftes sichtbar |
| streamen, Fusszeile danach | erstes Wort sofort | der Text ist kurz sichtbar, bevor die Pruefung laeuft |

⭐ Der Mittelweg, der beides haelt: **streamen, und die Pruefung haengt
hinten an** - Fusszeile, gepruefte Zitate, Warnungen. Wo die Pruefung
heute still etwas streicht (erfundene Abbildungsnummern), wuerde sie es
dann **benennen** statt es unsichtbar zu entfernen. Das waere sogar
ehrlicher als heute.

### Naechste Schritte, in dieser Reihenfolge

1. **Grafikspeicher freiraeumen** - das ist die Ursache, nicht das Gefuehl.
   ⛔ `keep_alive` NICHT anfassen (siehe oben). Zwei echte Hebel:

   **a) Docling gibt 12.222 MiB nicht her, obwohl es nichts tut.**
   Der beste Hebel: 12 GB, ohne dass sich an der Antwortqualitaet
   irgendetwas aendert. Der Ablaufplan ruft zwar
   `/v1/clear/converters` ("Grafikkarte freigeben"), der Speicher
   steht trotzdem. Schon am 04.08. als "Docling gibt Grafikspeicher
   NIE frei" dokumentiert; damals half
   `DOCLING_SERVE_ENG_LOC_NUM_WORKERS=1`. Pruefen, ob das noch gilt.

   **b) Zwei Chat-Modelle laufen parallel.**
   ```
   KI4KI_MODELL_NAME=gemma4:12b        <- der Proxy
   KI4KI_GESPRAECH_MODELL=gemma4:12b   <- der Gespraechsmodus
   chatModel: "qwen3.8:latest"         <- die Arbeitsbereiche
   ```
   Bis zu 22 GB haengen an einem davon. Auf EIN Modell zu gehen
   raeumt am meisten frei.
   ⚠ Das ist aber eine **Qualitaetsentscheidung**, keine reine
   Speicherfrage: gemma4 ist fuer den Gespraechsmodus mit Werkzeugen
   gesetzt worden. Erst messen, ob qwen dieselben Werkzeugaufrufe
   sauber beherrscht - sonst tauscht man Tempo gegen Verlaesslichkeit.

   ⭐ Erst a), dann messen. Vielleicht erledigt sich b) danach.
2. **Danach neu messen** - erst dann weiss man, was der Deckel wirklich
   kostet. Alle Zahlen von heute (53,9 Token/s) stammen von einer vollen
   Grafikkarte.
3. **Dann entscheiden**, ob gestreamt wird.
4. Das **Budget ueber den ganzen Zug** bleibt richtig, ist aber nach 1.
   vielleicht gar nicht mehr dringend.

⚠ **Fuer Partner wichtig:** Wer eine kleinere Karte hat als die A40
(46 GB), trifft das frueher und haerter. Das gehoert in die
Installationsunterlage, sobald die Zahlen nach dem Aufraeumen stehen.

## 4f - ENTSCHIEDEN 23.09. abends: 2048 Token, und die Zeitgrenze kam nie an

Emrach, woertlich: *"keiner wartet so lange auf eine antwort sind jetzt
bei 140 s"* - dann 160 s, dann:

```
Formuliere die Antwort ... (240 s)
Die Antwort ist nicht zustande gekommen (Modell: timed out).
```

### ⛔ Befund: KI4KI_GESPRAECH_TIMEOUT=600 ist nicht angekommen

Der Abbruch kam bei **exakt 240 s** - der Vorgabe im Code. Die Compose
setzt 600. Der Wert erreicht den laufenden Proxy also nicht.
**Ungeklaert.** Zu pruefen, indem man sich im Proxy-Container per
`printenv` die beiden Werte KI4KI_GESPRAECH_TIMEOUT und
KI4KI_ANTWORT_TOKEN ausgeben laesst.

⭐ Die Entscheidung haengt aber nicht daran: **2048 x 5 Runden = 190 s**
passt auch unter die alten 240 s. Der Wert ist sicher, egal welche
Zeitgrenze wirklich gilt - das ist mehr wert als ein hoeherer Wert, der
von einer ungeklaerten Einstellung abhaengt.

### Die Zahlen, bei 53,9 Token/s gemessen

| Vorgabe | je Aufruf | 5 Runden | |
|---|---|---|---|
| 8192 | 152 s | 760 s | ⛔ ueber jeder Zeitgrenze |
| 4096 | 76 s | 380 s | ⛔ ueber 240 s |
| **2048** | **38 s** | **190 s** | ✅ unter beiden |

2048 Token sind rund 4.300 Zeichen - anderthalb Seiten. Fuer eine
Chat-Antwort reichlich.

### ⚠ Die Einordnung, die ich schuldig bin

Der Prompt, der 160 s brauchte, verlangt elf Fragen mal mindestens acht
Saetze - rund **sechs Seiten**. Den habe **ich** als Belastungstest
gebaut, um den Deckel sichtbar zu machen. Als Messung war er richtig, als
Alltagsbeispiel irrefuehrend: Am selben Tag kamen normale Antworten in
**1,9 s** und **10,4 s**.

⛔ Das entschuldigt nichts. Eine Obergrenze, die man nicht
ueberschreiten kann, muss es geben. Heute gibt es sie nicht, weil der
Deckel JE AUFRUF gilt und ein Zug bis zu fuenf Aufrufe hat.

### ⭐ Erster Punkt fuer morgen

Ein **Budget ueber den ganzen Zug**: Der Zug bekommt insgesamt z. B. 3000
Token, jede Runde nimmt sich, was uebrig ist. Dann ist die Wartezeit nach
oben begrenzt - unabhaengig von der Rundenzahl und unabhaengig davon, ob
eine Umgebungsvariable ankommt.

## 4e - ABGENOMMEN 23.09. 14:49: der Threadwechsel, belegt auf der Leitung

```
GET /api/workspace/auw/thread/<id>/chats      16 ms      (vorher 2.248 ms)

hinein:  ki4ki_zugang=1790210951.48763b77d2bbd955.d29b…
heraus:  ki4ki_zugang=1790210954.48763b77d2bbd955.1636…
                       └ Uhrzeit wandert   └ Kennung IDENTISCH
```

⭐ **Der beste Beweis des Tages**, weil er nicht aus einer Pruefreihe
stammt, sondern aus den Kopfzeilen der echten Anfrage: Ablaufzeit und
Unterschrift wandern weiter (so soll es sein), die Kennung in der Mitte
ist ein fester Punkt. Genau die Eigenschaft, die
`test_die_kennung_wandert_nicht` als Kette prueft - hier am laufenden
System bestaetigt.

⚠ `[Dokzugang] 51 Zugaenge aus Platte geladen` sind **Altlasten** aus der
kaputten Phase (1 → 36 → 51). Die Zahl wird beim Start gelesen; sie darf
ab jetzt **nicht weiter wachsen**. Das ist die eigentliche Gegenprobe fuer
morgen - eine einzelne Zahl sagt noch nichts, ihre Entwicklung schon.

### Offen

- **Eine NORMALE Frage mit 2048** - nicht mein Belastungstest
- ⛔ Warum KI4KI_GESPRAECH_TIMEOUT=600 den Proxy nicht erreicht (§4f)
- Das **Token-Budget ueber den ganzen Zug** statt je Aufruf (§4d)
- Die Umleitung nummerierter Fragen in den Pruefungskatalog (§3x)
- **BUGS 28**: aussortierte Dokumente bleiben im Arbeitsbereich (§3s)
- Ein **Stand-Stempel fuer den Proxy** - bei n8n gibt es ihn (§3r), beim
  Proxy half heute nur der Zufall, dass ich eine Protokollzeile
  mitgeaendert hatte

## 4d - ZWEI NACHTRAEGE 23.09. abends: halbe Reparatur, und eine Rechnung zu wenig

### ⛔ 1. Die Kennung wanderte - der Zwischenspeicher blieb kalt

Nach §4a war der Threadwechsel kurz schnell und dann **wieder langsam**
(1.848 ms). Im Protokoll: `[Dokzugang] 36 Zugaenge aus Platte geladen` -
vorher stand dort 1.

```
kennung_neu = sha256(Authorization + "|" + Cookie_alt)
Cookie_alt  = <ablauf>.<kennung_alt>.<unterschrift>
                └─ eine Uhrzeit, die der Proxy bei jeder Antwort neu setzt
```

⭐ Ich hatte den **Leser** stabil gemacht (`zugangs_schluessel`) und den
**Schreiber** vergessen. Die Kennung, die in die neue Marke geht, entstand
weiter aus dem alten Cookie - und wanderte damit bei jeder Antwort.
**Halb repariert ist hier nicht besser als gar nicht**: Der Schluessel war
stabil und bekam trotzdem jedes Mal einen neuen Wert.

`rolle.marken_kennung()` sieht die Marke jetzt gar nicht an. Damit ist die
Kennung ab dem ersten Aufruf ein fester Punkt - in der Pruefung als Kette
belegt: dreimal hintereinander derselbe Wert.

### ⛔ 2. `num_predict` gilt JE AUFRUF - ein Zug hat bis zu fuenf

Gemessen: ein Zug lief **440 s** und endete mit `Modell: timed out`.

```
        je Aufruf   x5 Runden      Dauer bei 53,9 Token/s
 1800      1800        9.000              167 s
 4096      4096       20.480              380 s
 8192      8192       40.960              760 s   ⛔ > Zeitgrenze 600 s
```

⛔ **Das hatte ich beim Rechnen uebersehen.** `KI4KI_GESPRAECH_RUNDEN=5`
steht seit Langem in `gespraech.py`; ich habe nur den einzelnen Aufruf
gerechnet und daraus 8192 empfohlen. Im schlimmsten Fall reisst das die
Zeitgrenze - und dann kommt statt einer gekuerzten Antwort **gar keine**.

Vorgabe jetzt **4096**: hoechstens 380 s, im ueblichen Fall (ein bis zwei
Runden) 76-152 s.

⭐ **Die saubere Loesung steht noch aus:** ein Budget ueber den GANZEN Zug
statt je Aufruf. Dann duerfte die letzte Runde viel schreiben, wenn die
Werkzeugrunden davor wenig gebraucht haben. Heute waere das die vierte
Aenderung an derselben Stelle an einem Tag - das ist genau das Stapeln,
vor dem 3k warnt.

### ⚠ Was daran auffaellt

Drei Reparaturen an einem Nachmittag, und jede hat die naechste
Beobachtung erst sichtbar gemacht: erst der stille Durchgang, dann die
tote Leitung, dann die leeren Nachrichten, dann die wandernde Kennung.
Keine davon war falsch - aber jede war **zu frueh fertig gemeldet**.
⭐ Merke fuer morgen: Nach einer Reparatur an einem stark verketteten Weg
gehoert die Abnahme VOR die naechste Reparatur, auch wenn die naechste
klein aussieht.

## 4c - MEIN FEHLER: 8192 Token ohne Lebenszeichen killten die Verbindung

```
POST stream-chat   NS_ERROR_NET_PARTIAL_TRANSFER   92.432 ms
Proxy-Protokoll:   BrokenPipeError: [Errno 32] Broken pipe
```

Keine Antwort, kein Hinweis. **Direkte Folge der Erhoehung auf 8192.**

### Die Ursache

Der Modellaufruf laeuft mit `"stream": False` - der Proxy wartet die
KOMPLETTE Antwort ab und schickt in dieser Zeit **nichts** an den
Browser. Bei 1800 Token waren das rund 33 s und blieben unter der
Zeitgrenze der Gegenstelle. Bei 8192 sind es ueber zwei Minuten: Die
Gegenstelle kappte die stille Leitung, und als der Proxy schreiben
wollte, war sie weg. Der BrokenPipeError ist die **Folge**, nicht die
Ursache.

⭐ **Warum nicht einfach streamen:** Die Antwort wird NACH dem Erzeugen
gegen die Dokumente geprueft - Zitate, unbelegte Aussagen, erfundene
Bildnummern. Wer den Rohtext durchreicht, sendet Ungeprueftes. Genau das
tut diese Anlage nicht. Also ein **leeres Stueck** als Lebenszeichen,
alle 20 s (`KI4KI_LEBENSZEICHEN`).

⭐ **Vom aufrufenden Faden, nicht aus dem Arbeitsfaden.** Zwei Faeden auf
derselben Leitung koennten sich mitten in einem Stueck ins Wort fallen -
dieselbe Fehlerklasse wie das Wettrennen beim Chat-Anhang von heute
Mittag. Hier arbeitet der zweite Faden, und der erste schickt.

### ⛔ Nachtrag am selben Tag: die erste Fassung muellte den Chat zu

Das Lebenszeichen ging als leeres `textResponseChunk` mit **neuer**
Kennung raus. AnythingLLM macht daraus jedes Mal eine eigene, leere
Nachricht - der Chat war voller riesiger Leerflaechen, und die Antwort
kam trotzdem nicht.

⭐ Richtig ist `statusResponse` mit **gleicher** Kennung: Sie ersetzt die
vorige Meldung, erzeugt keinen neuen Block und wird am Ende mit
`removeStatusResponse` weggeraeumt. Genau dafuer gibt es sie - und sie
wurde im selben Griff schon fuer "Denke nach …" benutzt. Ich habe einen
neuen Weg gebaut, wo der richtige danebenlag.

⭐ Nebeneffekt, und ein guter: Der Mensch sieht jetzt
*"Formuliere die Antwort … (42 s)"* statt einer stummen Seite. Bei
Antworten, die zwei Minuten brauchen, ist das kein Beiwerk.

### Womit die Pruefung rot wird

`test_lange_antwort_haelt_die_leitung_wach`: Gegen den Stub **1 Fehler**
("waehrend des Wartens kamen Lebenszeichen: 0"). Mutationsprobe
(Lebenszeichen weglassen): 1 Fehler. Danach 0.
Gegenproben: Eine schnelle Antwort bekommt **kein** Lebenszeichen, und
ein Fehler im Arbeitsfaden kommt unveraendert beim Aufrufer an.

`test_das_lebenszeichen_macht_keine_leeren_nachrichten` faengt den
Rueckfall: Mutationsprobe (wieder neue Kennung) → rot.
⚠ Diese eine Pruefung liest den Quelltext, weil die Stelle in einem
HTTP-Griff steckt, der ohne Server nicht aufrufbar ist. Sie ist damit
schwaecher als eine Verhaltenspruefung - sie faengt genau den Fehler, der
heute passiert ist, und nicht mehr.

### ⭐ Was am selben Lauf ABGENOMMEN ist

```
erster  Threadwechsel:  chats  2268 ms   (Zwischenspeicher leer)
weitere Threadwechsel:  chats  ohne messbaren Balken
```

§4a ist damit abgenommen. Emrach: *"Der Threadwechsel geht jetzt
deutlich schneller."*

### ⚠ Sicherheit: der Admin-Schluessel steht in jeder HAR-Datei

Beim Messen fiel auf, dass eine HAR-Aufzeichnung den
`Authorization: Bearer <JWT>` des Admin-Kontos im Klartext enthaelt
(Laufzeit rund 30 Tage) sowie das Sitzungs-Cookie.

⛔ **Das ist KEINE Luecke der Anlage** - so meldet sich jede
Einseiten-Anwendung an, der Schluessel liegt ohnehin im Browser. Ein
Risiko wird es erst, wenn jemand eine HAR-Datei weitergibt.
⭐ Regel fuer Partner und uns: HAR-Dateien nie vollstaendig weitergeben.
Wer nur Zeiten braucht, zieht sie heraus - URL und Millisekunden
genuegen, Kopfzeilen nie.

## 4b - FUER PARTNER-ANLAGEN: was der 23.09. bringt, und was dafuer zu tun ist

⭐ **Zu tun ist genau eins:** `cd ~/ki4ki && ./aktualisiere.sh`.
Alle Werte stehen in `docker-compose.yml` und kommen damit automatisch
mit - kein Eingriff an der Anlage, nichts von Hand zu setzen. Wer einen
Wert anders will, setzt ihn in der `.env`; die Compose nutzt ueberall
`${VAR:-Vorgabe}`.

| Symptom beim Partner | Ursache | ab jetzt |
|---|---|---|
| Aufnahme laeuft, aber nichts kommt im Bestand an - Durchgang meldet trotzdem Erfolg | eine stoerrische Datei gab kein Element zurueck und riss den ganzen Block mit | Ablaufplan 2 sichert eine Rueckgabe zu (§3m); ein Leerlauf meldet sich jetzt laut (§3o) |
| Mehrere Dateien an den Chat gehaengt, nur eine wird ausgewertet | der Merkspeicher hielt nur eine, und gleichzeitige Uploads ueberholten sich | alle Dateien werden zusammengefuehrt, wettrennsicher (§3n, §3u) |
| Lange Antwort bricht mitten im Wort ab | fest verdrahtete Grenze von 1800 Token | 8192, und ein Abschnitt wird benannt statt verschwiegen (§3y) |
| Derselbe Dokumenttitel steht zweimal unter der Antwort | "durchsucht" und "vollstaendig gelesen" nannten ihn beide | nur noch einmal (§3z) |
| Threadwechsel dauert Sekunden | ein Zwischenspeicher, dessen Schluessel sich bei jeder Antwort selbst aenderte | Schluessel stabil (§4a) |
| Eingang wird nie leer | Thumbs.db, ._* und Office-Sperrdateien werden uebersprungen, aber nie geraeumt | `bau/nichtdokumente_wegraeumen.py` (§3q) |

⚠ **Ein Wert lohnt einen Blick je Anlage:** `KI4KI_ANTWORT_TOKEN=8192`
passt zu rund 54 Token/s. Ist die Grafikkarte langsamer, dauert eine volle
Antwort laenger als die Zeitgrenze von 600 s - dann entweder die Grenze
hoch oder die Tokenzahl runter. Die Token-Rate steht bei jeder Antwort in
der Oberflaeche (`outputTps`).

⭐ **Welche Fassung laeuft?** Seit §3r schreibt jeder Durchgang den Commit
ins Protokoll: `docker logs ki4ki-n8n | grep Stand`. Damit ist ohne
Ratespiel zu klaeren, ob eine Partner-Anlage den Stand wirklich hat.

## 4a - GEFUNDEN 23.09.: der Threadwechsel dauerte 2,2 s, weil ein Zwischenspeicher nie traf

Rueckmeldung: *"das umschalten der threads braucht voll lange aufeinmal"*.
An einer Netzwerk-Aufzeichnung (Firefox HAR) gemessen:

```
/api/workspace/auw/threads                      19 ms
/api/workspace/auw/parsed-files                 20 ms
/api/workspace/auw/thread/<id>/chats          2248 ms   <- 14 Byte Antwort
```

⭐ **2,2 Sekunden fuer `{"history":[]}`.** Und die Antwort trug
`set-cookie: ki4ki_zugang` und `cache-control: no-store` - unsere
Kopfzeilen, nicht die von AnythingLLM. Der Pfad lief also durch den Proxy.

### Die Ursache

Beim Laden eines Verlaufs ruft der Proxy `erlaubte_dokumente()`. Das fragt
**jeden Arbeitsbereich einzeln** bei AnythingLLM ab - eine dieser Antworten
ist allein **42 KB** (`/api/workspace/auw`, in derselben Aufzeichnung).

Dafuer gibt es `_DOKZUGANG` mit 300 Sekunden Haltbarkeit. Der Speicher traf
**nie**:

```python
ausweis = Authorization + "|" + Cookie        # der Schluessel
```

Der Cookie ist `ki4ki_zugang=<ablauf>.<kennung>.<unterschrift>`, und
`<ablauf>` setzt der Proxy bei **jeder Antwort** neu. In der Aufzeichnung
sichtbar: `1790206354...` hinein, `1790206687...` heraus.

⛔ **Der Proxy machte seinen eigenen Zwischenspeicher bei jeder Antwort
kaputt.** Neuer Cookie → neuer Schluessel → alles nochmal.

⭐ Das erklaert auch das "auf einmal": Mit jedem Dokument in AuW wurde die
Abfrage teurer. Der Zwischenspeicher haette das abgefangen - er kam nie
zum Zug.

### Gebaut

`rolle.zugangs_schluessel()` baut den Schluessel aus dem **stabilen** Teil:
der Kennung in der Mitte der Marke. Ablaufzeit und Unterschrift fliegen
raus, alles andere am Cookie bleibt - eine andere AnythingLLM-Sitzung ist
weiterhin ein anderer Zugang.

### Womit die Pruefung rot wird

`rollentest.py`, 4 Faelle. Gegen den Stub mit dem heutigen Verhalten:
**1 Fehler** ("die wechselnde Ablaufzeit darf den Schluessel NICHT
aendern"). Mutationsprobe (wieder den ganzen Cookie): 1 Fehler. Danach 0.

⛔ **Zwei Gegenproben schuetzen die Sicherheit**, nicht die Schnelligkeit:
eine andere Kennung MUSS einen anderen Schluessel ergeben, und eine andere
Anmeldung ebenso. Sonst saehe ein Konto die Dokumente eines anderen - ein
zu grosszuegiger Schluessel waere schlimmer als der langsame Weg.

### ⛔ Abnahme

Dieselbe Netzwerk-Aufzeichnung nach dem Einspielen. Erwartet: der erste
Threadwechsel kostet weiterhin ~2 s (der Speicher ist leer), **jeder
weitere innerhalb von 300 Sekunden deutlich weniger**.

## 3z - GEBAUT 23.09.: die Fusszeile nennt kein Dokument mehr doppelt

Meldung vom 15.09. aus 3l: *"steht fast bei jedem Output zwei mal die
Modellangabe und die Dokumente die gesucht wurden"*. Die Modellzeile fiel
am 22.09.; die doppelte Dokumentnennung blieb. Am 23.09. an einer echten
Antwort gesehen:

```
durchsucht: Pruefungsfragen zu DVS 2291 ... · zusammengefasst ·
vollstaendig gelesen: Pruefungsfragen zu DVS 2291 ... (ganzer Text)
            └── derselbe Titel, zweimal in derselben Zeile ──┘
```

`fusszeile.dokumente_fuer_zeile()` laesst die Titel weg, die weiter hinten
ohnehin als "vollstaendig gelesen" stehen. Bleibt nichts uebrig, entfaellt
die Suchzeile ganz. "Vollstaendig gelesen" sagt ohnehin mehr: Wer den
ganzen Text gelesen hat, hat ihn erst recht durchsucht.

### ⛔ Warum die Fusszeile NICHT ganz verschwindet

Gefragt wurde, ob man sie nicht streichen kann - die Denkphase und der
Quellen-Knopf von AnythingLLM zeigen doch schon, was gesucht wurde.
Zeigen sie nicht. Die Fusszeile traegt drei Dinge, die es sonst nirgends
gibt:

| | |
|---|---|
| `Quelle:` gegen `durchsucht:` | belegt gegen nur gesucht - genau dieser Unterschied hat am 22.09. einen fehlenden Beleg gemeldet |
| `N Zitate geprueft, M nicht gefunden` | das Ergebnis der Zitatpruefung |
| `⚠ erfundene Bildnummern gestrichen` · `⚠ N Aussage(n) nicht belegt` | Warnungen, die die Anlage gegen sich selbst ausspricht |

⭐ Die Quellenliste von AnythingLLM zeigt **gefundene Textstellen**. Sie
kann nicht sagen, dass eine Aussage **unbelegt** geblieben ist. Genau das
ist der Produktanspruch (03.08., woertlich): Schluesse ziehen **und**
belegen. Wer die Zeile streicht, streicht den Beleg-Teil.

### Womit die Pruefung rot wird

`fusszeilentest.py`, 3 Faelle. Gegen den Stub mit dem heutigen Verhalten:
**2 Fehler**. Mutationsprobe (Filter entfernt): 2 Fehler. Danach 0.
Gegenprobe: Ohne gelesene Dokumente bleibt die Zeile unveraendert.

Damit ist die **dritte** der drei Nutzermeldungen aus 3l bearbeitet.

## 3y - URSACHE GEFUNDEN 23.09.: die Meldung vom 18.09. ist ein Laengendeckel

### Der Versuch, in einem FRISCHEN Faden

```
kurze Antworten verlangt  -> alle 11 beantwortet (4 6 8 ... 24)
lange Antworten verlangt  -> Abbruch MITTEN IM WORT:
        "... Alltagsbeispiel: Du hast 12 Stifte und bekommst"
```

⭐ **Der Beweis steht nicht in der Anzahl, sondern im Schnitt.** Ein
Modell, das selbst aufhoert, endet sauber. Ein Schnitt mitten im Wort ist
die Unterschrift einer Token-Grenze.

`gespraech.py` rief das Modell mit `num_predict: 1800` - fest verdrahtet,
waehrend das Kontextfenster 65.536 fasst. Bei Fachtext (2,1 Zeichen je
Token, gemessen in `mehrstufig.py`) sind 1800 Token rund 3.800 Zeichen -
**etwa vier ausfuehrliche Antworten**. Genau das meldete der Nutzer am
18.09.: *"bricht aber in der 4ten Frage ab"*.

⚠ Meine Vorhersage war "Abbruch bei 5 bis 9", tatsaechlich kam er bei 11.
Der Grund: Die Rechenaufgaben-Antworten sind hochgradig wiederholend und
zahlenreich, die brauchen weniger als 2,1 Zeichen je Token. Die
Groessenordnung stimmte, die Zahl nicht - und die Richtung des Befunds
haengt nicht daran.

### Gebaut

| | |
|---|---|
| `ANTWORT_TOKEN` (`KI4KI_ANTWORT_TOKEN`) | Vorgabe **4096** statt fest 1800, ohne Neubau aenderbar |
| `abgeschnitten()` | liest Ollamas `done_reason`; faellt auf die Token-Zahl zurueck, wenn die Fassung es nicht meldet |
| `abschnitt_vermerken()` | haengt einen sichtbaren Hinweis an, statt stumm mitten im Wort zu enden |
| `nutzung["abgeschnitten"]` | im Protokoll auswertbar: wie oft trifft es uns wirklich? |

⭐ **Das Schlimmste war nicht der Deckel, sondern die Stille.** Die
Antwort endete mitten im Wort, und nichts sagte, dass etwas fehlt. Wer es
nicht bemerkt, haelt Unvollstaendiges fuer vollstaendig - bei einer
Wissensdatenbank der teuerste Fehler. Dieselbe Krankheit wie der gruene
leere Durchgang aus 3o.

### ⛔ Zum VIERTEN Mal an einem Tag: die Pruefung sass auf der falschen Ebene

Die erste Fassung der Pruefreihe testete `abgeschnitten()` und
`abschnitt_vermerken()` **einzeln**. Als ich die eine Zeile entfernte, die
beide im Gespraechszug verbindet, blieb sie **gruen**.

⭐ Jetzt faehrt `test_der_hinweis_kommt_wirklich_im_gespraechszug_an`
einen echten Zug durch `fuehren()` mit einem vorgetaeuschten Modell.
Mutationsproben: Verdrahtung entfernt → rot; Grenze zurueck auf 1800 →
rot.

⚠ **Und ein Eigentor:** Ich habe die Mutation mit
`git checkout -- gespraech.py` zurueckgenommen - das hat die ganze,
noch nicht committete Reparatur geloescht. Wiederherstellbar nur, weil das
Einbau-Skript noch im Arbeitsordner lag. **Eine Mutationsprobe wird mit
einer Kopie zurueckgedreht, nie mit `git checkout`.**

### ⛔ Abnahme steht aus

Nach `aktualisiere.sh` denselben Lauf B wiederholen, in einem frischen
Faden. Erwartet: Die elfte Antwort ist vollstaendig - und wenn doch
abgeschnitten wird, steht es jetzt dabei.

## 3x - BEOBACHTET 23.09.: mehrere Fragen werden in den Pruefungskatalog umgeleitet

Beim Versuch zur Meldung vom 18.09. (elf Fragen, vier beantwortet) trat
etwas anderes auf - reproduzierbar, zweimal hintereinander, im Bereich `auw`:

```
Frage:  "Beantworte jede Frage mit genau einer Zahl ... 1. 2+2? 2. 3+3? ..."
Anlage: Denke nach ... Hole die Frage aus dem Katalog ...
        "Frage 1 von 29 (Thema: Waermebehandlung ...)"
naechste Nachricht -> "Frage 2 von 29"
```

Die gestellten Fragen wurden **nicht beantwortet**. Stattdessen stellte die
Anlage Pruefungsfragen aus einem Katalog des Bereichs.

### Was der Quelltext dazu sagt

⛔ Der **deterministische** Weg erklaert es NICHT:
`pruefungskatalog.ist_wunsch()` verlangt Woerter wie "Pruefungsfrage",
"frag mich ab", "quiz", "naechste Frage" - keines davon stand in der Frage.
Und liegt eine Frage offen, faellt eine fachfremde Eingabe ausdruecklich
durch (`return False  # "warum?", andere Frage -> Gespraech mit Vorwissen`).

⭐ **Uebrig bleibt der Weg ueber das Modell.** Der Gespraechsmodus bietet
ein Werkzeug *"Eine EXAKTE Frage aus einem Pruefungskatalog des Bereichs"*
(`gespraech.py`, WERKZEUGE). Die Statuszeile "Hole die Frage aus dem
Katalog ..." ist genau dieses Werkzeug. In einem Bereich voller
Pruefungskataloge waehlt das Modell es offenbar, sobald eine Eingabe nach
nummerierten Fragen aussieht.

⚠ **Beobachtung, kein Befund.** Belegt ist, WAS passiert; der Weg dorthin
ist aus dem Quelltext erschlossen, nicht gemessen.

### ⛔ Zwei Fehler in meinem Versuchsaufbau

1. **Alles im selben Faden.** Nach der ersten Antwort trug der Faden eine
   offene Pruefungsfrage; jede weitere Nachricht lief in denselben Zweig.
   Ein Versuch ueber mehrere Zuege braucht **je Lauf einen frischen Faden**.
2. **Rechenaufgaben in einem Bereich voller Pruefungskataloge.** Denkbar
   ungeeignet: Genau dort hat das Modell ein Werkzeug, das nach
   "nummerierte Fragen" aussieht. Der Versuch zur Antwortlaenge gehoert in
   einen Bereich OHNE Kataloge.

⭐ Beides ist dieselbe Familie wie die Regel in §7: Ich habe die richtige
Sache gemessen, aber in einer Umgebung, die die Messung selbst veraendert.

### Offen

- Der Deckel `num_predict: 1800` in `gespraech.py` ist weiterhin der
  Hauptverdacht fuer die Meldung vom 18.09. - **ungeprueft**.
- Die Umleitung in den Katalog ist ein **eigener** Punkt. Sie kann
  Nutzerfragen unbeantwortet lassen, ohne dass jemand es merkt.

## 3w - GEMESSEN 23.09.: 410 Nichtdokumente, nicht 95

```
Dateien ueberall          : 6889
davon keine Dokumente     :  410     = 6 % des Bestands
    Ordner-Merkdatei       263       Thumbs.db / .DS_Store
    macOS-Metadatei         92       ._*
    Office-Sperrdatei       54
    versteckte Datei         1
```

⚠ **Die 410 sind noch nicht die Zahl, die zaehlt.** `--alles` laeuft auch
durch `archiv/` und `aussortiert/`; dort stoeren Nichtdokumente niemanden.
Entscheidend ist allein der **Parkplatz** - die wandern in den Eingang und
bleiben dort liegen, jeden Durchgang neu.

⭐ Deshalb zaehlt das Werkzeug jetzt **je Ablagestufe**.

⛔ **Beim ersten Anlauf blieb die Aufschluesselung unsichtbar.** Sie stand
nur bei MEHR ALS EINER Stufe da - lagen alle Treffer im Parkplatz, fehlte
sie genau dann, wenn die Frage eine eindeutige Antwort gehabt haette. Eine
Ausgabe, die sich bei Eindeutigkeit versteckt, ist schlechter als gar
keine: Man haelt die Zahl fuer unaufgeschluesselt und raet weiter.
Die Ausgabe liegt jetzt in `bericht()` und ist damit pruefbar. Die Gesamtzahl
allein haette zu einer Planung auf falscher Grundlage gefuehrt - dieselbe
Sorte Fehler wie "41 .db" (aus 813 Dateien) gegen "263 Ordner-Merkdateien"
(aus 6.889): zwei Zahlen, zwei Nenner, ein Missverstaendnis.

⛔ **Was 410 im Eingang bedeuten wuerden:** Sie blockieren nichts (das ist
seit 3m/3p geklaert), aber sie gehen nie weg. Bei Bloecken von 25 waere in
jedem Durchgang ein Teil davon dabei, der Eingang wuerde nie leer, und
"Eingang leer" bliebe als Fertig-Zeichen unbrauchbar. Vor dem KAP-Lauf
einmal `--wirklich` laufen lassen - danach ist der Eingang ehrlich.

## 3v - ABGENOMMEN 23.09.: der Chat-Anhang liest alle drei

```
(Gelesen: das komplette Dokument (174 Zeichen).)
probe-a.txt  ALPHA-7431 | probe-c.txt  GAMMA-2618 | probe-b.txt  BETA-9052
📎 3 Dokumente: probe-a.txt, probe-c.txt, probe-b.txt

[Anhang] 1 Datei(en) angenommen fuer auw - jetzt 1 Dokument(e),  19 Zeichen
[Anhang] 1 Datei(en) angenommen fuer auw - jetzt 2 Dokument(e), 116 Zeichen
[Anhang] 1 Datei(en) angenommen fuer auw - jetzt 3 Dokument(e), 174 Zeichen
```

⭐ **Die 174 sind nachgerechnet, nicht geglaubt:**

```
Block je Datei = Trennzeile(37) + Umbruch(1) + Text     57 + 57 + 56 = 170
zwei Trenner "\n\n" dazwischen                                       +   4
                                                                      = 174
```

Damit ist die Meldung vom 17.09. aus `/rueckmeldungen` erledigt - die
erste der drei offenen Nutzermeldungen.

⭐ Die aufsteigende Folge 1 → 2 → 3 im Protokoll ist der eigentliche
Beweis: Vorher stand dort dreimal "jetzt 1". Eine Zahl, die mitzaehlt,
haette das Wettrennen schon am 23.09. mittags sichtbar gemacht.

### Stand der Abnahmen

| | |
|---|---|
| §3n/3u Chat-Anhang | ✅ abgenommen |
| §3o Leerlauf-Meldung + Lautsprecher | ✅ abgenommen (Protokollzeilen sichtbar) |
| §3r Stand-Stempel | ✅ abgenommen (`[Stand a6086e7]`) |
| §3q Aufraeum-Werkzeug | ✅ 1 Datei verschoben |
| §3m Return-Knoten | ⚠ durch die Wegpruefung belegt, im Lauf nie gefeuert |
| §3t `--alles` | ⚠ Reparatur gepusht, auf dem Server noch nicht wiederholt |

### Offen

- **18.09.** elf Fragen, vier beantwortet (naechstes Stueck)
- **15.09.** doppelte Dokumentnennung
- **BUGS 28** aussortierte Dokumente bleiben im Arbeitsbereich - am
  23.09. mit Zahlen belegt (Bestand 83, `linkprobe` VERSCHOLLEN 1)
- ⚠ Der Proxy hat **keinen Stand-Stempel**. Dass wir den alten vom neuen
  Code unterscheiden konnten, lag nur daran, dass ich die Protokollzeile
  mitgeaendert hatte - Glueck, kein Entwurf.

## 3u - MEIN FEHLER: der Chat-Anhang hatte ein Wettrennen (23.09., behoben)

Die Abnahme von 3n ist durchgefallen - und die Ursache war meine eigene
Reparatur.

```
Gelesen: das komplette Dokument (19 Zeichen)     <- eine Datei, nicht drei
📎 Antwort aus dem angehaengten Dokument probe-a.txt
```

Das Protokoll des Proxys sagte, was los war:

```
[Anhang] 1 Datei(en) angenommen fuer kap - jetzt 1 Dokument(e), 19 Zeichen
[Anhang] 1 Datei(en) angenommen fuer kap - jetzt 1 Dokument(e), 18 Zeichen
[Anhang] 1 Datei(en) angenommen fuer kap - jetzt 1 Dokument(e), 19 Zeichen
```

Dreimal "jetzt 1". Nacheinander muesste der dritte "jetzt 3" melden.

### Die Ursache

Der Browser laedt die Anhaenge **gleichzeitig** hoch, und der Proxy fuehrt
je Anfrage einen eigenen Faden (`ThreadingHTTPServer`). Mein Code las den
Speicher, fuehrte zusammen und schrieb zurueck - **ohne Sperre**. Alle drei
lasen, bevor einer schrieb; der letzte gewann.

⚠ Fuenf andere Stellen im Proxy benutzen laengst `threading.Lock`. Meine
neue nicht.

### ⛔ Warum `anhangtest.py` das nicht gefunden hat

Er rief `aufnehmen` **nacheinander** auf. Die Funktion war und ist
richtig - falsch war das Lesen-Aendern-Schreiben **drumherum**.

⭐ **Dritte Spielart derselben Regel** (§7, "Teile statt Weg"): Nach der
falschen Flughoehe und der falschen Umgebung jetzt die falsche
**Gleichzeitigkeit**. Eine Pruefung, die nur einen Faden kennt, kann ein
Wettrennen nicht sehen - egal wie gruen sie ist.

### Gebaut

`anhang.merken()` kapselt lesen-zusammenfuehren-schreiben unter einer
Sperre; der Handler ruft nur noch das. Im Proxy gibt es keine Stelle mehr,
die `_ANHANG` von Hand beschreibt.

⭐ Die Textgewinnung (Tika, Sekunden) laeuft **ausserhalb** der Sperre.
Unteilbar ist nur das Kurze, worauf es ankommt.

### Womit die Pruefung rot wird

`test_drei_gleichzeitige_uploads`: drei Faeden, absichtlich verlangsamte
Textgewinnung, damit das Fenster sicher aufgeht. Gegen den Stand von eben:
**3 Fehler**, und zwar mit demselben Muster wie die Anlage - genau ein
Dokument ueberlebt, der letzte. Nach der Sperre: 0.
Gegenprobe `test_merken_haengt_an_den_vorgaenger_an`: nacheinander sind es
weiterhin drei.

## 3t - FEHLER VON MIR, behoben: `--alles` sprengte die Befehlszeile

```
OSError: [Errno 7] Argument list too long: 'docker'
```

Alle Namen gingen in EINEN node-Aufruf. Gemessen: 6.435 Namen sind als
JSON **135.135 Zeichen** - ARG_MAX liegt typisch bei **131.072**.
Jetzt in Haeppchen von hoechstens 60.000 Zeichen.

### ⛔ Der lehrreiche Teil: mein erster Test war gruen

Der naheliegende Test - 6.000 Namen durch `_gruende` schicken - ist auf
meiner Maschine **gruen**, weil `node` dort direkt vorliegt. Auf dem
Server laeuft er ueber `docker exec`, und erst dort reisst die Grenze.

⭐ **Ein Test, der nur auf einer von zwei Maschinen rot wird, prueft die
Maschine, nicht den Code.** Deshalb prueft er jetzt die EIGENSCHAFT:
kein Paket ueber 60.000 Zeichen, und zusammengesetzt wieder dieselben
Namen in derselben Reihenfolge. Das ist ueberall reproduzierbar.
Gehoert zur Regel in §7 (Teile statt Weg) als zweite Spielart:
**die falsche UMGEBUNG messen.**

⚠ Und die Rechnung war beim ersten Anlauf auch noch falsch: `json.dumps`
trennt mit Komma UND Leerzeichen, also 2 Zeichen je Name statt 1. Bei
3.000 Namen sind das genau 3.000 Zeichen Unterschied - die Pruefung wurde
rot (62.979 statt <= 60.000) und hat es gefangen.

## 3s - ABGENOMMEN 23.09. mittags: was laeuft, laeuft richtig

### ✅ Es laeuft, was wir gepusht haben

```
Kontrolle a6086e7 : 1      (Ablaufplan 1 - im Protokoll nachgewiesen)
Plan 2  _waehlen  : 1      (Ablaufplan 2 - eindeutiger Marker)
```

⭐ Der Export zeigt die LAUFENDE Fassung - das war seit 3j offen und ist
jetzt beantwortet: Die Kontrollzahl stammt aus dem Plan, von dem das
Protokoll selbst sagt, dass er laeuft. Stimmt sie, taugt der Export auch
fuer Plan 2.
⚠ Erster Anlauf mit dem Marker "Rueckfall" ergab **2** - das Wort steht
auch in den Kommentaren von Ablaufplan 1. Ein Marker muss eindeutig sein,
sonst misst man Kommentare.

⛔ **Publish bleibt ungedrueckt.** Der Knopf wuerde den Entwurf
`d0810e64` ueber die laufende, aktuelle Fassung legen.

### ✅ Die Kette traegt, am echten Lauf belegt

```
archiv/_probe      1     die .pdf, vollstaendig durch
aussortiert/_probe 1     die .db, mit Begruendung:
    "Format nicht vorgesehen (.db) - nur pdf, doc, docx, ... werden aufgenommen.
     Bleibt hier liegen; soll das Format dazu, wird es in VORGESEHEN eingetragen"
```

⚠ **Das war NICHT der Return-Knoten**, sondern die Positivliste in
"Ablage entscheiden". Der Rueckfall-Zweig ist weiterhin nie gefeuert; er
bleibt durch die Wegpruefung belegt, nicht durch einen Lauf.

### ⛔ BUGS 28 zum ersten Mal live und mit Zahlen

```
Bestand 81 -> 82 (.pdf) -> 83 (???)
linkprobe: VERSCHOLLEN 1    "1 nicht im Index"
```

Die aussortierte `.db` liegt **auch im Arbeitsbereich**. Grund steht in der
Reihenfolge der Bausteine:

```
Markdown speichern -> Upload -> Einbetten -> Ablage entscheiden -> Ablegen
                      \___ hochgeladen ___/   \__ erst HIER aussortiert __/
```

⭐ Jede aussortierte Datei hinterlaesst eine Karteileiche in der Suche.
Bei 4.300 Dateien ist das kein Schoenheitsfehler mehr. `linkprobe.py`
zaehlt sie als VERSCHOLLEN - das Werkzeug dafuer gibt es also schon.

### ⚠ Korrektur: die Nichtdokumente liegen im PARKPLATZ, nicht im Eingang

Der Trockenlauf des Aufraeum-Werkzeugs fand **1** Datei, nicht die ~95, die
ich erwartet hatte. Ich hatte Parkplatz und Eingang verwechselt. Die 41
`.db` und 54 Sperrdateien liegen im Parkplatz und stoeren dort niemanden -
sie werden erst zum Problem, wenn der Parkplatz in den Eingang wandert.

⭐ Deshalb neu: `--alles` zaehlt ueberall (Vorschau, wie viel sich stauen
wird), verschiebt aber weiterhin NUR aus `input/`. Der Parkplatz ist
Kundenbestand.

```
python3 bau/nichtdokumente_wegraeumen.py dokumente --alles
```

## 3r - GEBAUT 23.09. abends: der Ablaufplan nennt seinen Stand

Emrachs Frage: *"wann soll ich oben das orange Publish machen? vllt liegt
es daran?"* Berechtigt - und bis jetzt **nicht beantwortbar**. Nichts im
Betrieb sagte, aus welchem Commit der laufende Ablaufplan stammt.

Ab sofort schreibt der Baustein, der ohnehin jede Minute eine Zeile
schreibt, den Commit voran:

```
[Stand f48e900] Bereich kap: 1 zu verarbeiten, 0 schon im Bestand, ...
```

`aktualisiere.sh` setzt `__STAND__` aus `git rev-parse --short HEAD` ein -
auf einer **Kopie**, die Repo-Datei bleibt unveraendert.

⭐ Damit ist die offene Frage aus 3j ("was exportiert `export:workflow`
in n8n 2.x - Entwurf oder veroeffentlichte Fassung?") **umgangen statt
beantwortet**: Es ist egal, welche Fassung der Export zeigt, wenn der
LAUFENDE Ablaufplan selbst sagt, woher er kommt.

### ⛔ Zum Publish-Knopf: weiterhin NICHT druecken

Der Knopf veroeffentlicht den **Entwurf**, und was in `d0810e64` steckt,
weiss niemand. Er kann aelter sein als alles, was seit dem 21.09. gebaut
wurde. Der Stempel klaert die Frage ohne Risiko:

| im Protokoll steht | Bedeutung |
|---|---|
| der Commit, den `aktualisiere.sh` gemeldet hat | ✅ es laeuft, was wir gepusht haben - Publish waere ein Rueckschritt |
| ein **aelterer** Commit | ⛔ der Import erreicht die laufende Fassung nicht - DANN ist Publish (oder der Direktweg aus dem Gedaechtnis) noetig |
| `[Stand __STAND__]` woertlich | der Plan wurde an `aktualisiere.sh` vorbei eingespielt |

### Womit die Pruefung rot wird

`test_stand_steht_im_protokoll`, 6 Stellen. Vor dem Bau: **5 Fehler**.
Danach 0. Die Gegenprobe fuehrt den Ersetzungsbefehl wirklich aus.

⚠ **Eine Pruefung davon war zuerst falsch gebaut.** Sie verlangte, dass
`docker cp "$wf"` verschwindet - die Zeile bleibt aber zu Recht stehen,
nur die Schleife darueber aendert sich. Eine Pruefung, die korrekter Code
nicht erfuellen kann, ist genauso wertlos wie eine, die nie rot wird.
Korrigiert auf: die Schleife darf nicht mehr ueber `n8n-workflows/*.json`
laufen, sondern ueber die gestempelten Kopien.

## 3q - GEBAUT 23.09. abends: Nichtdokumente raeumen sich weg

`bau/nichtdokumente_wegraeumen.py` holt die uebersprungenen Dateien aus den
Eingaengen und legt sie nach `aussortiert/` - mit Grund und Zeitstempel,
Unterordner gespiegelt.

```
python3 bau/nichtdokumente_wegraeumen.py dokumente             # nur zaehlen
python3 bau/nichtdokumente_wegraeumen.py dokumente --wirklich  # raeumen
```

⭐ **EINE Regel, zwei Leser.** Die Entscheidung "ist das ein Dokument?"
wird nicht nachgebaut, sondern aus dem Ablaufplan geholt und mit `node`
ausgefuehrt - derselbe Code, den n8n im Betrieb nutzt. Eine zweite Fassung
in Python waere genau der Fehler, den der mkmd-Dienst vermeidet.

⭐ **Warum ausserhalb des Ablaufplans** (meine erste Einschaetzung
"billig im Ablaufplan" war falsch): Der Weg nach `aussortiert/` braucht
`aussortiert_path`, `bereich` und `source_path` - Felder, die erst NACH der
Unterkette entstehen. Ein uebersprungenes Nichtdokument kommt da nie hin.
Und ein `executeCommand` mitten im Datenstrom verschluckt die Binaerdaten
(gemessen 04.08.). Das Werkzeug fasst den laufenden Betrieb nicht an -
Null Risiko fuer die offenen Abnahmen.

### Womit die Pruefung rot wird

`bau/wegraeumtest.py`, 4 Faelle auf einem echten Dateibaum (kein Nachbau).
Gegen den Stub mit dem heutigen Verhalten: **11 Fehler**. Danach 0.
Mutationsprobe: Ziel auf `input` statt `aussortiert` gedreht → **11 Fehler**.

⭐ Zwei Gegenproben stecken drin: ein echtes Dokument und eine `.db`
**ohne** Muster muessen liegen bleiben. Ohne sie waere ein leerer Eingang
auch dann gruen, wenn das Werkzeug ALLES wegraeumt.

⚠ Der Trockenlauf ist die Vorgabe; `--wirklich` muss man tippen. Namen
zeigt es nur mit `--namen`.

## 3p - KORREKTUR 23.09. abends: die `.db` war NICHT der Stoerenfried

Bei der Abnahme am laufenden System gemessen, mit Zeitstempeln:

```
09:32:24  'Bereich kap: 1 zu verarbeiten, ..., 1 keine Dokumente (uebersprungen).'
                         └ die .pdf              └ die .db
Bestand 81 -> 82   archiv/_probe 1   input/_probe 1   aussortiert/_probe 0
```

Die `.pdf` lief vollstaendig durch. Die `.db` wurde **ganz vorne** als
"kein Dokument" uebersprungen und hat die Unterkette **nie erreicht**.

### ⛔ Was daraus folgt: 3k beschreibt zwei Dinge als eines

| | belegt |
|---|---|
| Alle `.db` im KAP-Parkplatz sind `Thumbs.db` | gemessen: `find ... ! -iname "Thumbs.db"` findet **keine** |
| `Thumbs.db` steht seit **21.09.** auf der Nichtdokument-Liste (`53edd7c`, im Betrieb bestaetigt) | git |
| Der `~$`-Filter fuer Office-Sperrdateien kam erst am **23.09.** (`6385bec`) | git |

⭐ **Also kann die `.db` am 23.09. nicht ausgeloest haben, was 3k ihr
zuschreibt.** Sie wurde schon damals uebersprungen. Beobachtet wurde
"liegt im Eingang, wird weder verarbeitet noch aussortiert" - das stimmt,
aber es ist das Verhalten eines uebersprungenen Nichtdokuments, nicht das
eines Block-Killers. Der Zusatz "und legt dabei jeden Durchgang still"
war eine **Ableitung aus der Nachbarschaft**, keine Messung.

⚠ **Wer der Stoerenfried am 22.09. war, ist damit wieder offen.**
Naheliegend sind die **54 Office-Sperrdateien** - am 22.09. noch
ungefiltert, mit der Endung des Originals, also mitten im Office-Zweig.
Das ist ein begruendeter Verdacht, **kein Befund**.

### ⛔ Neuer, gemessener Befund: Nichtdokumente bleiben EWIG im Eingang

Ein uebersprungenes Nichtdokument wird nie nach `aussortiert` geraeumt.
Gemessen ueber drei Durchgaenge: `input/_probe 1`, `aussortiert/_probe 0`,
jeder Durchgang meldet erneut "1 keine Dokumente (uebersprungen)".

Es **blockiert nichts** (das war der alte Fehler, der ist weg), aber:
bei 41 `.db` + 54 Sperrdateien im KAP-Bestand wird der Eingang **nie
leer** - und "Eingang leer" taugt damit nicht mehr als Fertig-Zeichen.
⭐ Sie gehoeren nach `aussortiert` mit Grund. Naechstes Stueck Arbeit.

### ⚠ Was das fuer die Abnahme von 3m bedeutet

**Der Return-Knoten ist nicht scharf geschaltet worden.** Beide bekannten
Stoerenfriede werden heute VOR der Unterkette abgefangen. Es gibt im
Bestand derzeit keine Datei, von der belegt waere, dass sie die Unterkette
leer zurueckkommen laesst.

⛔ Ehrlich: Die Zusicherung ist durch die Wegpruefung belegt
(`test_rueckgabe_garantiert`, 14 Fehler vorher / 0 nachher), **nicht**
durch einen Lauf. Ein Lauf kann derzeit nur zeigen, dass kein Dokument
mehr den Block mitreisst - nicht, dass der Rueckfall feuert.

## 3o - GEBAUT 23.09. spaet: der stille Durchgang meldet sich

Aus der Rueckmeldung: *"Das Problem am `return []` ist nicht der fehlende Wurf -
es ist die Stille."* Stimmt. Gebaut, ohne zu werfen.

```
[LEERLAUF] Unterkette lieferte 0 Ergebnis(se) fuer 25 Datei(en) - dieser
Durchgang legt nichts ab, der Eingang bleibt voll, und er meldet trotzdem
Erfolg. Siehe BUGS_UND_FIXES 29.
```

⭐ **Kein Wurf, wie vorgeschlagen.** Ein Wurf beendete den Durchgang vor
`Sperre freigeben`; die Laufsperre bliebe liegen und blockierte alles bis zum
120-Minuten-Notnagel (am 04.08. schon passiert). Die Zeile geht raus, danach
laeuft alles wie bisher weiter.

### ⛔ Der Haken, der die Zeile fast taub gemacht haette

`console.log` aus einem n8n-Code-Baustein geht laut n8n-Doku **in die
Browser-Konsole**, nicht ins Container-Protokoll. `CODE_ENABLE_STDOUT` steht per
Vorgabe auf `false`:

> *"Set to `true` to send Code node logs from `console.log` or `print` to the
> process's stdout, only for production executions."*

⭐ **Daraus folgt ein zweiter Befund:** Die **beiden Meldungen, die
Ablaufplan 1 schon immer schrieb** (`[Sperre] ...` und `... zu verarbeiten`),
waren im Betrieb **nie** zu sehen. Am laufenden System nachgezaehlt: 2.519
Zeilen im n8n-Protokoll, **0 Treffer** fuer beide Marker.
⚠ Diese Null allein beweist nichts — bei leerem Eingang laufen die Bausteine
gar nicht. Belastbar ist die Doku-Vorgabe, und `docker exec` auf die
KI4KI-Container ist hier gesperrt, also blieb der Schalter am laufenden System
ungeprueft. **Die Gegenprobe macht die Abnahme** (siehe unten).

Deshalb zusaetzlich `CODE_ENABLE_STDOUT=true` in `docker-compose.yml`.
⚠ Damit koennen kuenftige `console.log` auch Dokumentinhalte ins Protokoll
schreiben. Die drei vorhandenen tun es nicht.

### Pruefung

`test_stiller_durchgang_meldet_sich` in `bau/ablauf_pruefen.py` - 7 Stellen.
Rot vor dem Bau: **2 Fehler** (Marker fehlt, Schalter fehlt). Danach 0.
Geprueft wird die Meldung ausgefuehrt (nicht gelesen): meldet bei 0 von 3,
schweigt bei 3 von 3, nennt beide Zahlen, und meldet **nicht** bei null
Dateien.

### ⭐ Gegenprobe fuer den Schalter, kostenlos

Nach `aktualisiere.sh` muessen im n8n-Protokoll die **alten** Zeilen
auftauchen, sobald ein Durchgang mit Dateien laeuft:

```bash
docker logs ki4ki-n8n 2>&1 | grep -E "zu verarbeiten|\[Sperre\]" | tail -5
```

Kommt da nichts, hat der Schalter nicht gewirkt — und die Leerlauf-Meldung
waere ebenfalls taub. **Das ist die eigentliche Abnahme dieses Punktes**, nicht
die gruene Pruefreihe.

## 3n - GEBAUT 23.09. spaet: der Anhang-Weg liest jetzt ALLE Dateien

Meldung vom 17.09. aus 3l, woertlich: *"Es wurden 3 Dateien ueber das
+ Zeichen zusaetzlich in diesem Chat bereitgestellt allerdings nur eins
bei der Anfrage ausgewertet."*

### Die Ursache steht im Quelltext, sie musste nicht erraten werden

Der Anhang-Weg konnte **nie** mehr als eine Datei halten, und zwar
doppelt:

| Stelle | Was sie tat |
|---|---|
| `_parse_mitschnitt` | nahm aus der Formularsendung nur `dateien[0]` |
| `_ANHANG[(bereich, konto)]` | war EIN Eintrag - eine zweite Sendung ueberschrieb die erste |

Beide Wege enden gleich: genau ein Dokument erreicht die Antwort. Welchen
der beiden die Oberflaeche geht (drei Dateien in einer Sendung oder drei
Sendungen), spielt fuer den Befund keine Rolle - beide waren kaputt.

⭐ **Die Formularzerlegung war immer richtig.** `_dateien_aus_formular`
liefert alle Dateien; der Hochladen-Knopf nebenan laeuft mit
`for name, inhalt in dateien:` korrekt ueber alle. Verloren gingen sie
erst im Chat-Anhang. Deshalb fiel es beim Hochladen nie auf.

### Gebaut

`pruef-proxy/anhang.py` fuehrt alle Dateien zu EINEM Eintrag zusammen und
haengt sie an einen noch frischen Vorgaenger an. Der zusammengefuehrte
Text geht denselben Weg wie ein grosses Einzeldokument: `mehrstufig.stuecke()`
zerlegt ihn, jedes Stueck wird gelesen. Die Maschinerie dafuer gibt es seit
dem 28.08. - sie musste nur etwas zu lesen bekommen.

⭐ Die Zusammenfuehrung liegt in einem eigenen Modul, nicht im Handler:
so ist sie ohne Server pruefbar, und im Handler gibt es keine Stelle mehr,
an der jemand versehentlich wieder nur die erste Datei nimmt.

⚠ Bei **einer** Datei bleibt alles woertlich wie bisher (kein Vorspann,
Fusszeile nennt den Dateinamen). Sonst haette sich der haeufigste Fall
mitgeaendert, ohne dass daran etwas falsch war.

### Womit die Pruefung rot wird

`pruef-proxy/anhangtest.py`, 6 Faelle. Gegen den Stand von heute frueh
(nur `dateien[0]`, kein Anhaengen) gemessen: **8 Fehler**, darunter
woertlich "alle drei Dateien sind im Eintrag" und "die zuerst
hochgeladene Datei geht nicht verloren". Nach dem Umbau: 0.
`dialogtest.py` bleibt bei 520 Pruefungen / 0 Fehlern.

### ⛔ Abnahme steht aus

Drei Dateien anhaengen und etwas fragen, das alle drei braucht. Erwartet:
die Zeile *"Gelesen: das komplette Dokument (N Zeichen)"* nennt die Summe,
und die Fusszeile nennt **alle drei Dateinamen**.
⚠ Die Fusszeile lautet dann "Antwort aus dem angehaengten Dokument
**3 Dokumente: a.pdf, b.docx, c.xlsx**" - sprachlich schief, inhaltlich
richtig. Wenn es stoert: eine Zeile in `_anhang_antwort`.

### Noch offen aus 3l

- **18.09.** elf Fragen, vier beantwortet - noch nicht angefasst
- **15.09.** doppelte Dokumentnennung - noch nicht angefasst

⛔ Die Vermutung aus 3l ("bearbeitet den ersten von mehreren") ist durch
diesen Fund **nicht** bestaetigt. Der Anhang-Weg hatte eine eigene,
oertliche Ursache - er las nicht "nur den ersten von mehreren", er konnte
gar nicht mehr als einen speichern. Fuer die anderen beiden Meldungen
sagt das nichts. Getrennt nachstellen, wie in 3l vorgesehen.

## 3m - GEBAUT 23.09. nachmittags: Return-Knoten, Abnahme offen

### Was gebaut ist

Der Return-Knoten aus 3k steht. Ablaufplan 2 ist jetzt eine Funktion mit
zugesicherter Rueckgabe: **ein Element hinein, genau ein Element hinaus.**

| | |
|---|---|
| `Rueckfall` (Set) | haengt direkt am Ausloeser, liefert IMMER ein Element an den Merge (3. Eingang) |
| `Return` (Code) | waehlt aus: echtes Ergebnis gewinnt, sonst `{ok:false, grund}` mit leerem Text + Dateiname |
| 11 Bausteine | Fehlerabfang ergaenzt - Weichen, Merge, Code-Bausteine |
| `bau/ablauf_pruefen.py` | neue Pruefung `test_rueckgabe_garantiert` |

⭐ **Warum der Rueckfall-Zweig und nicht nur `alwaysOutputData` am Return:**
Ob n8n einen Baustein mit **leerem** Eingang ueberhaupt ausfuehrt, ist nicht
sicher - und `alwaysOutputData` greift laut Doku, wenn ein Baustein *nichts
zurueckgibt*, nicht wenn er *gar nicht laeuft*. Der Rueckfall-Zweig haengt am
Ausloeser, der immer genau ein Element hat. Damit steht die Zusicherung
unabhaengig von dieser offenen Frage.

⭐ **Der Dateiname muss im Fehlerfall mit.** Der Elternteil paart ueber
`docling_filename` (Reparatur vom 26.08.). Ohne Namen verschiebt sich die
Zuordnung, und ein Dokument bekaeme den Text eines anderen.

### Die Pruefung prueft den WEG, nicht die Bausteine

`test_unterkette_reisst_nicht_mit` war am 23.09. **gruen, waehrend der Fehler
lief** - sie sieht Bausteine einzeln an und zaehlte nur HTTP und Extract.
Die neue Pruefung fragt stattdessen: *Gibt es einen Weg vom Ausloeser zum
Ausgang, auf dem kein Baustein das Element verlieren kann?*

⭐ **Womit sie rot wird** - am Plan von `c2c4a21` gemessen, nicht behauptet:

```
Plan vor dem Umbau                  14 Fehler
Rueckfall-Zweig entfernt            rot (Gegenprobe steckt im Test selbst)
return [echt[0]] -> return liste    rot ("genau 1 Element")
Plan nach dem Umbau                  0 Fehler
```

### ⛔ Die Abnahme steht noch aus - erst danach gilt das als behoben

Kein Beweis ohne Lauf. Die Pruefung sagt, der Plan ist richtig verdrahtet;
sie sagt **nicht**, dass n8n sich so verhaelt.

1. `git pull && ./aktualisiere.sh`
   ⚠ **`aktualisiere.sh` loest die Laufsperre selbst** (Zeile 63). Der
   Eingang ist mit 0 leer, also passiert erst etwas, wenn eine Datei
   hineinkommt - aber man sollte es wissen.
2. **Dieselbe `.db`** nach `kap/input/_probe` legen - die Datei, die es
   ausgeloest hat.
3. Einen Durchgang abwarten, dann messen:
   `docker exec ki4ki-pruef-proxy python3 /app/laufstand.py` und `linkprobe.py`

| | |
|---|---|
| **Traegt es** | `.db` liegt in `aussortiert`, Eingang leer, Durchgang gruen |
| **Traegt es nicht** | `.db` bleibt liegen - dann ist die Unterausfuehrung als GANZES gescheitert, nicht nur ein Zweig |

4. Danach eine Handvoll gemischter Dateien MIT der `.db` zusammen. Erwartet:
   die anderen laufen durch, die `.db` wird aussortiert, **der Block ueberlebt**.

### ⛔ Was NICHT behoben ist: der Verstaerker im Elternteil

`Code` in Ablaufplan 1 liefert weiterhin still `return []`, wenn die
Unterausfuehrung als Ganzes scheitert (Zeitgrenze, Speicher, Unterablauf nicht
aktiv). Der Return-Knoten hilft dagegen nicht - er laeuft dann gar nicht.

⛔ **Der naheliegende Riegel waere falsch.** "Dann eben werfen" beendet den
Durchgang vor `Sperre freigeben` - die Laufsperre bleibt liegen und blockiert
alles bis zum 120-Minuten-Notnagel. Genau das ist am 04.08. schon einmal
passiert. Richtig waere ein Fehlerzweig, der die Sperre in JEDEM Fall
freigibt. Eigenes Stueck Arbeit.

⚠ Zweiter offener Punkt, unveraendert aus 3j: **was `export:workflow` in
n8n 2.x exportiert** (Entwurf oder veroeffentlichte Fassung). Solange das
offen ist, ist `test_was_n8n_wirklich_geladen_hat` schwaecher als sein Name.

## 3l - OFFENE MELDUNGEN aus /rueckmeldungen (Stand 23.09.)

⭐ **Zuerst der gute Teil: K2 funktioniert.** Am 22.09. stand hier noch
"Code vorhanden, aber nie gegen die Gate-Bedingung gemessen". Die Liste
liefert echte Befunde aus echter Nutzung - mit Frage, Antwortauszug,
Fundstellen und Faden-Link. Genau das verlangt der Leitfaden (S. 123, 128).
Was fehlt, ist nicht der Kanal, sondern dass jemand die Liste abarbeitet.

### Zwei neue Meldungen, beide unbearbeitet

| Datum | Bereich · Weg | Befund (Wortlaut der meldenden Person) |
|---|---|---|
| **18.09.** | auw · gespraech | *"In der Anweisung sind 11 Fragen gestellt und laut erster Antwortzeile auch erkannt, die bearbeitung bricht aber in der 4ten Frage ab. => Unvollstaendig"* |
| **17.09.** | auw · anhang | *"Es wurden 3 Dateien ueber das + Zeichen zusaetzlich in diesem Chat bereitgestellt allerdings nur eins bei der Anfrage ausgewertet."* |

### Aeltere, noch offene Meldungen

| Datum | Befund |
|---|---|
| 15.09. | *"steht fast bei jedem Output zwei mal die Modellangabe und die Dokumente die gesucht wurden"* - die Modellzeile ist am 22.09. entfernt worden, die doppelte Dokumentnennung nicht geprueft |
| 27.08. | *"mehrere Befehle in einer Anfrage kann er wohl nicht verarbeiten"* |
| 27.08. | *"mehrere Teile melden wohl unlesbare Stellen. Liegt das beim vektorisieren?"* |

### ⚠ Eine Vermutung - ausdruecklich NICHT gemessen

Die Meldungen vom 18.09., 17.09. und 27.08. sehen nach derselben Familie aus:
**Die Anlage bearbeitet den ersten von mehreren und hoert dann auf.** Elf
Fragen → vier beantwortet. Drei Anhaenge → einer gelesen. Mehrere Befehle →
einer ausgefuehrt.

⛔ Das ist eine Aehnlichkeit, kein Befund. Am 22./23.09. haben drei
Schluesse aus genau solchen Aehnlichkeiten in die Irre gefuehrt. Es koennen
drei verschiedene Ursachen sein - ein Abbruch bei der Antwortlaenge, ein
Anhang-Weg der nur das erste Element liest, ein Router der nur die erste
Absicht erkennt. **Erst je einen Versuch bauen, dann zusammenfassen.**

### Vorschlag fuer die Reihenfolge

1. **Anhang-Weg** (17.09.) - der engste Fall, am billigsten nachzustellen:
   drei Dateien anhaengen, zaehlen wie viele gelesen werden.
2. **Mehrere Fragen** (18.09.) - eine Anweisung mit elf durchnummerierten
   Fragen, zaehlen wie viele beantwortet werden. Dann pruefen, ob es an der
   Antwortlaenge liegt (Zeichenzahl der Antwort gegen die Grenze) oder an
   der Zerlegung.
3. **Doppelte Dokumentnennung** (15.09.) - Anzeige, kein Verhalten; billig.

⭐ Diese drei treffen den Nutzer direkt und liegen seit Wochen. Der
KAP-Lauf tut das nicht.

## 3k - GEMESSEN 23.09. mittags: die Kette traegt, EINE Datei legt sie still (Reparatur in 3m)

### Der Versuch

Drei Dateien nach `kap/input/_probe` kopiert - eine `.pdf`, eine `.doc`,
eine `.db`. Dann gemessen:

```
nach 400 s     input 1 von 3 uebrig
               archiv 0 -> 4   (Original + gewandelte PDF + Steuerdatei)
               Bestand kap 1 -> 3
nach 23 min    input 1 (.db), unveraendert - ueber 20 Durchgaenge hinweg
               weder verarbeitet noch aussortiert
```

**Ergebnis: `.pdf` und `.doc` laufen vollstaendig durch.** Gewandelt,
hochgeladen, abgelegt. Die Kette ist nicht kaputt.

### ⛔ Die `.db` ist der Stoerenfried - und sie blockiert DAUERHAFT

Jede Minute laeuft ein Durchgang, nimmt die `.db` auf, die Unterausfuehrung
gibt **kein Element** zurueck, `assignPairedItems` bricht. Der Baustein
`Code` liest `$('Dateien in JSON umwandeln').all()` - leer - und liefert
`return []`. Der Durchgang endet **gruen**. Die Datei bleibt liegen. Naechste
Minute von vorn.

⛔ **Solange sie im Eingang liegt, ist JEDER Durchgang vergiftet.** Neue
Dateien landen im selben Block und werden mit stillgelegt - nicht kaputt,
nur nie verarbeitet.

Notbremse: Die Claim-Garantie schiebt nach **180 Minuten** aus dem Eingang.
Drei Stunden je Stoerenfried, in denen nichts durchkommt.

⭐ **Damit ist der 22.09. restlos erklaert.** In den 813 Dateien lagen 41
`.db` und 54 Office-Sperrdateien. Bei Bloecken von 25 war praktisch jeder
Block vergiftet, und zwar dauerhaft - die Stoerenfriede blieben liegen und
waren beim naechsten Durchgang wieder dabei. Daher: 91 Wandlungen (die
passieren vorher, in der Unterausfuehrung), null Uploads, ein Eingang, der
sich nicht leerte.

⚠ **Korrektur meines Befunds vom 22.09. abends.** Dort stand "die Kette
verliert ihre Elemente" und daraus abgeleitet "die Kette ist kaputt". Falsch:
Sie traegt. Ich hatte einen laufenden Durchgang mit `docker stop` abgewuergt
(der "Error in 13ms" um 16:22 ist genau der) und seinen Stillstand als Defekt
gelesen.

### Gebaut: Office-Sperrdateien fliegen raus (`6385bec`)

Im KAP-Bestand gemessen: **54 Office-Sperrdateien** (`.doc` 26, `.pptx` 14,
`.docx` 10, `.xlsx` 3, `.xlsm` 1). Sie entstehen beim Oeffnen eines Dokuments
und bleiben nach einem Absturz liegen - ein paar hundert Byte, aber mit der
Endung des Originals. Also laufen sie in den Office-Zweig und legen den Block
still wie die `.db`.

```js
if (b.startsWith('~$')) return 'Office-Sperrdatei';
```

Mit Gegenprobe: `Angebot ~$ Nachtrag.docx` bleibt drin - nur der Dateianfang
zaehlt.

⚠ **Das ist Linderung, keine Heilung.** Heute sind es Sperrdateien und
`.db`, morgen ein Format, an das niemand gedacht hat.

### ⭐ Die Reparatur, jetzt begruendet statt geraten

Ein **Return-Knoten am Ende von Ablaufplan 2**, der IMMER genau ein Element
liefert - im Fehlerfall `{ok: false, grund: "..."}`. Dann:

- ueberlebt der Block, auch wenn eine Datei scheitert,
- wandert die `.db` ehrlich nach `aussortiert` statt drei Stunden alles
  aufzuhalten,
- und der `Code`-Verstaerker bekommt wieder etwas zu lesen.

Der Skill `n8n-subworkflows` nennt genau das als Vertragsfehler: *"Shape the
output with a final Set node, named Return"* und *"Return errors, don't
always throw"*. Er widerspricht zugleich dem naheliegenden Umbau: `mode: each`
ist **richtig** gewaehlt; ein `Loop Over Items` im Unterablauf waere ein
Anti-Muster.

### Stand des Bereichs kap nach dem Aufraeumen

```
input         0
parkplatz  6600    (15 oberste Ordner - zwei Kundenordner)
archiv        1    nur die Steuerdatei bilder-nachholen.txt
aussortiert   1    nur das Protokoll
Bestand kap   1    von Hand hochgeladene Geheimhaltung, NICHT aus dem Lauf
```

### ⛔ Zwei Sitzungen an einer Maschine

Am 23.09. haben zwei Sitzungen parallel Befehle gegeben - eine setzte die
Laufsperre, die andere liess sie loesen. Die Lagebeschreibungen liefen
sofort auseinander. **Eine Sitzung faehrt, die andere schweigt.**

## 3j - Stand 23.09. vormittags (durch 3k ueberholt)

### Lage

⛔ **n8n ist gestoppt bzw. mit gesetzter Laufsperre.** Die Aufnahmekette
wandelt Office-Dateien nach PDF und **verliert danach ihre Elemente**: kein
Markdown, kein Upload, keine Ablage - und der Durchgang meldet "Succeeded".

Der Bereich `kap` ist aufgeraeumt (23.09. vormittags):

```
input        0     (813 geloescht - lagen lokal vor)
archiv       0     (144 verwaiste Wandlungen geloescht)
parkplatz 3450+    zwei Kundenordner neu hochgeladen
documents/kap 1    von Hand hochgeladene Geheimhaltung, NICHT aus dem Lauf
mdablage     14    alle aus zz-schluesselprobe, nichts von kap
```

### ⛔ Die Publish-Frage: NICHT veroeffentlichen

In n8n steht der Publish-Knopf orange, angeboten wird Version `d0810e64`.
**Nicht klicken.** Begruendung, gemessen statt vermutet: Der Office-Fix vom
22.09. nachmittags hat nachweislich gelaufen (die gewandelte Word-PDF landete
um 16:0x im gespiegelten Unterordner statt flach - das kann nur die neue
Fassung). Die aktive Fassung ist also aktuell. Was in dem Entwurf steckt,
weiss niemand.

⚠ Offen bleibt, WAS `export:workflow` in n8n 2.x exportiert - Entwurf oder
veroeffentlichte Fassung. Solange das unklar ist, ist
`test_was_n8n_wirklich_geladen_hat` schwaecher, als sein Name verspricht.
Das gehoert geklaert, bevor man sich wieder darauf verlaesst.

### Was schon ausgeschlossen ist (23.09., am Ablaufplan geprueft)

| Verdacht | Ergebnis |
|---|---|
| Eine Dateiendung laeuft ins Nichts | ✅ nein - die Weichen haengen als Kette, alles Unbekannte faellt auf Tika zurueck |
| Der Merge am Ende wartet auf beide Zweige | ✅ nein - zwei Eingaenge, Betriebsart "anhaengen" |
| n8n laeuft mit einer alten Fassung | ✅ unwahrscheinlich, siehe Publish-Frage |
| Positivliste, Bildabweisung, Office-Ziel, Fehlerabfang | ✅ `ablauf_pruefen.py` 0 Fehler |

### ⭐ Der naechste Schritt: nachstellen statt nachsehen

Die n8n-Oberflaeche brauchen wir nicht. Ein kleiner, kontrollierter Durchgang
sagt dasselbe und ist messbar:

1. **Drei Dateien** verschiedener Art (eine `.pdf`, eine `.doc`, eine `.db`)
   aus `kap/parkplatz` nach `kap/input` legen.
2. Laufsperre loesen: `docker exec ki4ki-n8n rmdir /files/json/.lauf.sperre`
3. Einen Durchgang abwarten, dann messen:
   `docker exec ki4ki-pruef-proxy python3 /app/laufstand.py`
   und `.../linkprobe.py`
4. **Erwartet, wenn es traegt:** input 0, archiv 3 (bzw. 2 + 1 aussortiert),
   Bestand waechst.
   **Erwartet, wenn es bricht:** archiv bekommt nur die gewandelten PDF,
   input bleibt voll, Bestand unveraendert.
5. Dann die Menge erhoehen (25) und dieselbe Messung. Traegt es bei 3 und
   bricht bei 25, liegt es an der Menge; bricht es schon bei 3, an einem
   Dateityp - dann einzeln bisektieren.

⚠ `KI4KI_MENGE_JE_LAUF` steuert die Menge je Durchgang (Standard 25).

### Der fachliche Verdacht (noch NICHT bestaetigt)

`assignPairedItems` bricht, wenn eine Unter-Ausfuehrung kein Element
zurueckgibt. Der Unterablauf endet auf einem **Merge** - der gibt zurueck,
was ankommt, und sagt **nicht** zu, dass ueberhaupt etwas ankommt.

⭐ Der Skill `n8n-subworkflows` nennt genau das als Vertragsfehler:
*"Shape the output with a final Set node, named Return"* und *"Return
errors, don't always throw"*. Er widerspricht zugleich dem naheliegenden
Umbau: `mode: each` ist **richtig** gewaehlt (n8n markiert es nur als
veraltet); ein `Loop Over Items` im Unterablauf waere laut Skill ein
Anti-Muster.

→ Wahrscheinliche Reparatur: ein **Return-Knoten** am Ende von Ablaufplan 2,
der IMMER genau ein Element liefert - im Fehlerfall `{ok: false, grund: ...}`.
Erst messen, dann bauen.

### Danach: der Zielkatalog (23.09. ausgezaehlt)

| Ebene | Stand |
|---|---|
| **Leitfaden K1-K5** (Gate-Bedingungen) | Code fuer alle fuenf vorhanden - **aber nie gegen die Gate-Bedingungen gemessen**. Das Anforderungsdokument sagt zu K2-K5 noch "existiert nicht" (Stand 26.08.), das ist ueberholt. |
| **Gespraechsqualitaet** (§1-§6) | 28 Anforderungen: 3 ✅ / 19 🟡 / 6 ❌ |
| **Ganz offen** | Recap des Standes · Weg zum Menschen · Kennwerte mit Messbedingung · Widersprueche nebeneinander · Abkuerzungen · Export |

⚠ **Die Zitate aus dem Implementierungsleitfaden in §7 sind aus zweiter
Hand.** Sie stehen in unserem eigenen Dokument, zugeschrieben mit
Seitenangaben (S. 7, 14, 82), ausgewertet am 31.07. in einer frueheren
Sitzung. Die PDF selbst wurde hier nie gelesen. Belastbar ist die
Seitenangabe, nicht das Zitat.

⭐ **Die strategische Frage, die Emrach entschieden hat:** Erst die Kette
reparieren, dann die Gate-Pakete ehrlich durchmessen, dann der
**Stoerfall-Bestand** (UC 1 des Leitfadens) - KAP laeuft als Nebenbahn mit,
ist aber nicht der Pilotfall.

## 3i - Stand 22.09., spaetabends

⛔ **Der KAP-Lauf ist angehalten. n8n ist gestoppt.** Der Chat und die
Suche laufen weiter - nur die Aufnahme ruht.

### Der Befund in drei Zeilen

Ueber 7 Minuten gemessen, bei laufender Aufnahme:

```
kap/archiv:   44 -> 135   (+91 gewandelte PDFs)
kap/input:   811 -> 811   (unveraendert)
Bestand:      81 -> 81    (nichts hochgeladen)
```

Die Kette **wandelt** Office-Dateien nach PDF und legt sie richtig ab
(Reparatur 27 greift). Danach passiert **nichts**: kein Markdown, kein
Upload, keine Ablageentscheidung - und das Original bleibt im Eingang.
Der Durchgang meldet trotzdem "Succeeded".

### Was schon ausgeschlossen ist

| Verdacht | Ergebnis |
|---|---|
| n8n laeuft mit einer alten Fassung | ✅ widerlegt: `ablauf_pruefen.py` inkl. "Was n8n WIRKLICH geladen hat" ist **0 Fehler** |
| Positivliste, Bildabweisung, Office-Ziel | ✅ alle gruen geprueft |
| Fehlerabfang an den 8 riskanten Bausteinen | ✅ gruen |

### ⛔ Der verbleibende Verdacht - noch NICHT bestaetigt

```
Cannot read properties of undefined (reading 'entries')
   at WorkflowExecute.assignPairedItems
```

Der Knoten **"Dateien in JSON umwandeln"** laeuft im Modus
`Run once for each item` - von n8n 2.31.4 selbst als veraltet markiert, mit
dem Hinweis: *"add a Loop Over Items node before this node and use Run once
with all items"*.

⚠ Mein Fix vom Vormittag (`onError: continueRegularOutput`) hat diesen
Fehler **nur stummgeschaltet, nicht behoben**. Der Durchgang laeuft weiter -
mit leeren Haenden. Genau die Sorte Gruen, vor der dieses Projekt sich
sonst schuetzt, diesmal von mir selbst eingebaut.

### Der naechste Schritt, in dieser Reihenfolge

1. **Bestaetigen, nicht annehmen.** n8n starten, SOFORT die Laufsperre
   setzen, dann in der Executions-Liste einen Durchgang mit Laufzeit in
   MINUTEN oeffnen (die 7-Sekunden-Laeufe sind nur Sperr-Abbrueche):

   ```bash
   docker start ki4ki-n8n && sleep 25 && \
   docker exec ki4ki-n8n mkdir -p /files/json/.lauf.sperre
   ```

   Gesucht: rotes Kreuz an "Dateien in JSON umwandeln", die Meldung, und ob
   die Knoten dahinter Haekchen haben.
   Sperre loesen: `docker exec ki4ki-n8n rmdir /files/json/.lauf.sperre`
   (sie raeumt sich ohnehin nach 120 Minuten selbst weg).

2. **Erst dann umbauen:** `Run once for each item` raus, `Loop Over Items`
   davor. Das ist ein echter Umbau am Ablaufplan - mit einer Pruefung in
   `bau/ablauf_pruefen.py`, die ihn rot machen kann, bevor er auf 4.300
   Dateien losgelassen wird.

3. **Aufraeumen:** In `kap/archiv` liegen ~135 gewandelte PDFs ohne
   zugehoeriges Dokument. Sie gehoeren weg, bevor der echte Lauf startet -
   sonst zaehlen sie als Dokumente mit eigenem Schluessel mit.

### ⚠ Drei Fehlgriffe von mir an diesem Nachmittag, alle derselben Art

- Aus drei `.msg` im Arbeitsbereich auf **2.000 Bilder** geschlossen.
- Aus **einem Byte** Groessenunterschied auf eine beschaedigte Datei.
- Aus "im Eingang bewegt sich nichts" auf einen **Abbruch** - waehrend ein
  Durchgang noch lief. Danach in die Gegenrichtung ueberkorrigiert
  ("die Kette ist doch in Ordnung"), was die Messung dann widerlegte.

⭐ Jedes Mal half dieselbe Frage: **Was habe ich gemessen, und was habe
ich daraus nur abgeleitet?** Und jedes Mal kostete die Messung weniger Zeit
als die Vermutung.

## 3h - Stand 22.09., abends: alle Links tragen, KAP kann laufen

**Einstieg fuer die naechste Sitzung.** Zweig `pfad-identitaet`.

### Was am Nachmittag dazukam

| | |
|---|---|
| **25** | Derselbe Ordner ist ZWEIMAL eingehaengt (lesend und schreibend). `_schluessel_der_datei` rechnete immer gegen die Lese-Wurzel - fuenf von sechs Aufrufstellen waren dadurch **wirkungslos**. Behoben. **Punkt 24 war derselbe Fehler.** |
| **26** | "Seiten" heisst nicht "Seitenbild". Erst entstand kein Link mehr, dann gar keiner - jetzt: Sprung wo es eine Seite gibt, sonst Link auf das Dokument. |
| **27** | Gewandelte Word-PDF lag flach im Archiv statt neben dem Original. Behoben, beide Haelften am System bestaetigt. |
| **28** | ⛔ OFFEN: Aussortierte Dokumente bleiben im Arbeitsbereich (Upload vor Positivliste). |

### Zahlen, gemessen statt geschaetzt

```
linkprobe.py, Bereich zz-schluesselprobe:
  vorher   TOTE LINKS 3   (.docx .txt .xlsx)
  danach   TOTE LINKS 0   Seitenansicht 9, nur Datei 2
  Bild in den Eingang gelegt: Bestand 81 vorher, 81 nachher
```

### Zwei Fehlgriffe von mir, beide derselben Art

- Aus drei `.msg` im Arbeitsbereich auf **2.000 Bilder** geschlossen. Falsch:
  ohne Text entsteht keine Markdown-Fassung, also kein Upload.
- Aus einem Byte Groessenunterschied auf eine beschaedigte Datei geschlossen.
  Falsch: Der Erzeuger arbeitet nicht reproduzierbar (8810/8810/8813).

⭐ Beide Male half dieselbe Frage: **Was genau habe ich gemessen, und was
habe ich daraus nur abgeleitet?**

### ⛔ Die kaputten Probedateien waren MEIN Fehler

Word und Excel im Pruefbereich haben je einen Teil mit falscher Pruefsumme -
schon auf der Nextcloud, vor jeder Beruehrung durch die Anlage. Ich habe sie
hochgeladen und nie nachgemessen, ob ankommt, was ich abgeschickt habe.

⭐ Zwei Folgerungen: Die Anlage ist unschuldig (echte Office-Dateien aus
Word sind nicht betroffen, der KAP-Lauf ist nicht gefaehrdet). Und: Die
Aufnahme hat die Beschaedigung **nicht gemeldet** - sie prueft keine
Dateiintegritaet. Bei einer halb lesbaren Datei gaebe es eine halbe Antwort
ohne Hinweis. Kleine Luecke, notiert.

### Offen, nach dem KAP-Lauf

1. **Punkt 28** - Positivliste vor den Upload.
2. **Quellenleiste rechts** zeigt die `.md` statt der Originale; die Eintraege
   sind nicht anklickbar. Gehoert zu derselben Familie wie die toten Links.
3. **"nicht belegt" bei Tabellen** - die Zahl steht in einer Zelle, das Modell
   formuliert einen Satz daraus, die woertliche Pruefung findet ihn nicht.
4. **Auftrag 3f** - Mails aufnehmen, Herkunft benennen.
5. **Repo-Trennung** - oeffentlicher Baukasten gegen internes Repo, plus
   Freigabe-Waechter fuer `KAP`, Servernamen und Hausadressen.

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

- **Die Art eines Dokuments** (Auftrag 3f). Entschieden 22.09. abends:
  Mails werden AUFGENOMMEN, aber die Antwort nennt die Herkunft
  („aus der E-Mail vom …“). Bis das gebaut ist, bleiben sie draussen -
  verlustfrei, weil der Schluessel auf jeder Stufe derselbe ist.
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
- ⛔ **Eine Prüfung, die die TEILE misst statt den WEG.** Neu am 23.09.,
  zweiter Fall in zwei Tagen. Eine Prüfung kann rot werden *können* und
  trotzdem nie rot werden, wenn sie auf der falschen Flughöhe schaut:

  | Datum | Prüfung | Maß die Teile | Hätte messen müssen |
  |---|---|---|---|
  | 23.09. | `test_unterkette_reisst_nicht_mit` | Fehlerabfang je Baustein (nur HTTP + Extract) | gibt es einen **Weg**, auf dem nichts verlorengeht? |
  | 22.09. | `linkprobe.py` | Links einzeln | tote Links wurden als „Altbestand“ verbucht statt gemeldet |

  Die erste war **grün, während der Fehler lief** — elf weitere Bausteine
  konnten den Ablauf abbrechen, die sie gar nicht ansah.
  ⭐ **Regel: Lautet die Anforderung „X kommt IMMER heraus“, muss die
  Prüfung einen Pfad prüfen, keine Liste von Bausteinen.** Eine Zusicherung
  ist eine Eigenschaft des ganzen Weges. War eine Prüfung grün, während ein
  Fehler lief: nicht nachbessern — fragen, auf welcher Flughöhe sie hätte
  schauen müssen.

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
