#!/bin/bash
# ============================================================================
#  KI4KI aktualisieren - holt die neueste Fassung und startet sie neu.
#
#  Ein Befehl:  ./aktualisiere.sh
#
#  Holt die neueste Paketfassung von GitHub, baut die selbstgebauten Dienste
#  (Belegpruefung, mkmd) neu und startet alles aktualisiert. Daten, Modelle
#  und .secrets.env bleiben unangetastet.
# ============================================================================
set -e
cd "$(dirname "$0")"

echo "→ Neueste Fassung holen ..."
git pull --ff-only

echo "→ Belegpruefung und mkmd-Dienst neu bauen (falls Code geaendert) ..."
docker compose build pruef-proxy mkmd-dienst

echo "→ Aktualisierte Dienste starten ..."
docker compose up -d

echo "✓ Fertig. Aktueller Stand:"
git log -1 --format='   %h  %s'
