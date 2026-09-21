# Einstieg in die nächste Sitzung

Stand 20.09.2026. Diese Datei ersetzt das Zusammensuchen am Sitzungsanfang.
Sie sagt, wo die Ziele stehen, was entschieden ist, was offen ist und was als
Beweis zählt. **Erst lesen, dann arbeiten.**

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
| `doku/entwicklung/BUGS_UND_FIXES.md` | Gefundene Fehler mit Ursache. **Punkte 6 und 7 sind offen.** |
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
   ⭐ **Zwei Anforderungen laufen mit**, ohne Zusatzaufwand, und sie machen die
   Beweisführung in Schritt 3 überhaupt erst möglich:
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
3. **KAP vollständig neu einspielen und messen**, dass der Fehlerzähler
   **stillsteht** — nicht nur, dass der Bestand steigt.
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
- ⚠ **Der Server hängt zwei Commits zurück** (nur Markdown, kein Code). Wer dort
  `BUGS_UND_FIXES.md` liest, sieht die Punkte 6 und 7 **nicht**.
  `./aktualisiere.sh` ist seit dem 20.09. nicht gelaufen.

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
  ⛔ **Korrektur 21.09.: „Das funktioniert" war falsch.** Gemessen werden nur
  Abbildungen über **8 % Seitenfläche** beschrieben — bei der Probe **null von
  drei**. Die Schwelle 0,08 unterdrückt die Bildbeschreibung im **ganzen
  Bestand**, ohne Meldung. Siehe `BUGS_UND_FIXES.md` §9a.
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

## 4 · Stand der Anlage

```
Zweig     pfad-identitaet · Rückweg: Tag vor-pfad-identitaet-2026-09-20
          zurück mit: git checkout main && ./aktualisiere.sh
n8n       LÄUFT wieder (seit 21.09.), aber alle Eingänge sind LEER —
          deshalb nimmt die Anlage nichts auf. Bleibt so bis der Umbau steht.
          ⚠ Die Lösch-Wache im Proxy läuft unabhängig davon jede Minute
KAP       Eingang leer · 8 im Archiv · 15 aussortiert · 4.241 geparkt
Bestand   67 Dokumente
Daten     Emrach hat alle Rohdaten lokal — der Serverbestand ist entbehrlich
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
