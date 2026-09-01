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

## Offen / vor einer Vermarktung zu klären

- **Erste vollständige Installation von null** auf der Zielumgebung — erst damit
  ist bewiesen, dass ein Partner startklar wird.
- **n8n-Lizenz** (*Sustainable Use License*): interner Betrieb gedeckt; ein
  vermarktetes Produkt mit fest verbautem n8n wäre vorher zu prüfen (siehe
  `LIZENZEN.md`).
