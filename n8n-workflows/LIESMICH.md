# KI4KI — n8n-Workflows (Aufnahme) · Partner-Import

Diese 3 Workflows sind die **komplette Dokument-Aufnahme**. Fragen beantwortet
der Prüf-Proxy, nicht n8n — dafür ist hier nichts nötig.

## Import
1. In n8n **alle 3 JSON importieren** (Reihenfolge egal — die IDs bleiben erhalten,
   damit die Verknüpfung stimmt).
2. **`KI4KI Masse-Ingest`** ist der Haupt-Workflow; er ruft die beiden anderen als
   Unter-Workflows auf (`Dateien in JSON umwandeln`, `Markdown-Datei erzeugen`).
3. Nur den **Masse-Ingest aktivieren** (Schalter an). Er hat 3 Auslöser:
   Handstart · alle 5 Minuten automatisch · Webhook `ki4ki-aufnahme` (UI-Upload).
   Die beiden Unter-Workflows bleiben **inaktiv** (werden nur aufgerufen).

## Voraussetzungen (Service-Namen im Docker-Netz)
Der Ablauf spricht diese Dienste an — Namen müssen zur Partner-Compose passen:
`pruef-proxy:3001` · `docling:5001` · `anythingllm:3001` · `nothink-proxy:11435`.
Für den UI-Upload: im Proxy `KI4KI_AUFNAHME_HAKEN=http://n8n:5678/webhook/ki4ki-aufnahme` setzen.

## Enthält bewusst NICHT
Keine alten/Test-Workflows, keine Dubletten, **keine `rm -f`-Nodes**. Nur der
aktuelle, laufende Stand.
