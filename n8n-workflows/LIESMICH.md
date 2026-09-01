# n8n-Ablaufpläne (Aufnahme)

Die drei Dateien hier sind die komplette Dokument-Aufnahme. `start.sh` und
`aktualisiere.sh` spielen sie automatisch ein und aktivieren sie — von Hand ist
normalerweise nichts zu tun.

Falls doch (Meldung „Nicht alle Ablaufpläne aktiviert"): alle drei in n8n
importieren und **alle drei aktivieren**, auch die beiden Unter-Abläufe. Ein
inaktiver Unter-Ablauf wird von n8n nicht ausgeführt — jedes Dokument landet
dann ohne Fehlermeldung mit leerem Text in `aussortiert/`.

- `1_KI4KI-Masse-Ingest.json` — Hauptablauf: sieht **jede Minute** in `dokumente/*/input/` nach, Webhook `ki4ki-aufnahme` für den Upload aus der Oberfläche
- `2_Dateien-in-JSON-umwandeln.json` — Unter-Ablauf: Office → PDF, Docling, Excel/CSV, Tika
- `3_Markdown-Datei-erzeugen.json` — Unter-Ablauf: Textfassung über den mkmd-Dienst

Ablauf, Schalter und Fehlersuche: [`../doku/BETRIEB.md`](../doku/BETRIEB.md), Abschnitte 2.3 und 5.
