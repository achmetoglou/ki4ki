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

**Zuerst die vollständige Durchsicht, dann der Umbau.** Rückgrat ist die
Abgleichstabelle: 67 Zeilen gegen den heutigen Code nachprüfen, die 24 gelben und
12 roten zuerst, und die Frage beantworten, ob die Anlage UC 1 bedient.
Mit mehreren Opus-Prüfern parallel, jeder mit einer eigenen Frage und den
Regeln aus Abschnitt 1 im Auftrag. Ergebnis: Mängelliste mit Belegstellen.

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

Deshalb: **lesbarer Name auf 120 Byte gekürzt + zehnstelliger Fingerabdruck des
vollen Pfades.** Der Fingerabdruck ist alphanumerisch und überlebt alle acht
Normalisierungsfunktionen; Trennzeichen tun das nie. Längster Schlüssel 176 von
255 Byte. **Dateien auf der Platte werden nicht umbenannt.** Dieselbe Datei bei
zwei Kunden wird zweimal aufgenommen. Die bestehenden 66 Dokumente werden nicht
neu aufgebaut.

## 6 · Offen, vor dem Bauen zu klären

1. **Wie AnythingLLM Uploadnamen wirklich umschreibt** (Sonderzeichen, Umlaute,
   über 200 Byte). Nirgends gemessen, trägt aber den ganzen Entwurf. Test mit
   fünf Dateien in einem Wegwerf-Bereich.
2. **Die zweite Ursache hinter „Aufnahme unvollständig" 107 → 147** ist weiter
   unbekannt. Vier belegte Kandidaten in `BUGS_UND_FIXES.md` Punkt 7. Nicht
   bauen, bevor das gemessen ist.
3. **Löschweg, Rechteprüfung, Belegprüfung und `pdfstelle.py` gehören in den
   Umfang.** „Nicht anfassen" war eine Fehlannahme — alle vier hängen am
   Dateinamen.

## 7 · Was als Beweis NICHT zählt

- `dialogtest.py` grün — von 44 Szenarien behandelt keines Pfade, Namen, Archiv
  oder Dubletten; viele Prüfungen vergleichen Zeichenketten im eigenen Quelltext.
- `pdfs:` in `/pruef-status` — zählt Schlüssel, nicht Dokumente. Bei Kollision
  steigt die Zahl, obwohl Dokumente fehlen.
- Ein leeres Aussortier-Protokoll — die Übersicht liest nicht rekursiv und sieht
  Dateien in Unterordnern gar nicht.
- n8n „succeeded" — rund 20 Knoten stehen auf „bei Fehler weitermachen".
- Stichproben über den Gesamtbestand — zu 98 % blind. Beweiskraft hat nur die
  Gruppe der 1.587 gleichnamigen Dateien.

**Was zählt:** Prüfsummenvergleich statt Namensvergleich, gezielte Proben in der
Kollisionsgruppe, eine Löschprobe, bei der die **anderen** nachgezählt werden —
und ein Fehlerzähler, der nach dem Fix **stillsteht**.
