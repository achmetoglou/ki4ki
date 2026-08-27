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

# ⚠ SELBST-UPDATE: git pull ersetzt auch DIESE Datei - waehrend sie laeuft.
#   Die Shell liest ein Skript stueckweise; nach dem Pull liefe der Rest
#   aus der ALTEN Fassung (oder an der falschen Stelle der neuen). Gemessen:
#   Ein neu hinzugekommener Schritt (Gruppe in die .env) griff erst beim
#   ZWEITEN Lauf. Deshalb: erst holen, dann die frische Fassung neu starten
#   und alles Weitere dort erledigen.
if [ "$1" != "--nach-pull" ]; then
  echo "→ Neueste Fassung holen ..."
  git pull --ff-only
  exec "$0" --nach-pull
fi

echo "→ Belegpruefung und mkmd-Dienst neu bauen (falls Code geaendert) ..."
docker compose build pruef-proxy mkmd-dienst office-dienst

# Gruppe des Server-Nutzers in die .env (falls die Anlage vor diesem Stand
# installiert wurde): rechte-init gibt ./dokumente an 1000:<Gruppe> mit
# setgid, damit Massenlaeufe per SFTP/scp moeglich sind.
touch .env
for kv in "KI4KI_UID=$(id -u)" "KI4KI_GID=$(id -g)"; do
  k="${kv%%=*}"
  if grep -q "^$k=" .env 2>/dev/null; then sed -i "s|^$k=.*|$kv|" .env; else echo "$kv" >> .env; fi
done

echo "→ Aktualisierte Dienste starten ..."
docker compose up -d

# Ablaufplaene (n8n-Workflows) mit einspielen - sie sind Teil des Pakets.
# Ohne diesen Schritt bliebe eine Aenderung an den Workflow-Dateien auf
# bestehenden Anlagen wirkungslos (nur start.sh importierte sie). Import
# behaelt die IDs, danach ALLE DREI aktivieren (inaktive Unterketten
# fuehrt n8n nicht aus) und n8n neu starten, damit es die Fassung laedt.
echo "→ Ablaufplaene einspielen ..."
set +e
docker exec ki4ki-n8n sh -c 'rm -rf /tmp/wf && mkdir -p /tmp/wf' >/dev/null 2>&1
for wf in n8n-workflows/*.json; do docker cp "$wf" ki4ki-n8n:/tmp/wf/ >/dev/null 2>&1; done
if docker exec ki4ki-n8n n8n import:workflow --separate --input=/tmp/wf >/dev/null 2>&1; then
  _ok=1
  for _wid in 1DKWgDbdCiwa25E1 uK5WCYhjVqPawcvP J8pPkKTKmkFTXjGn; do
    docker exec ki4ki-n8n n8n update:workflow --id="$_wid" --active=true >/dev/null 2>&1 || _ok=0
  done
  docker restart ki4ki-n8n >/dev/null 2>&1
  [ "$_ok" = 1 ] && echo "  Ablaufplaene eingespielt und aktiviert (n8n neu gestartet)" \
    || echo "  ⚠ Nicht alle Ablaufplaene aktiviert - bitte in n8n (Port 5678) pruefen"
else
  echo "  ⚠ Ablaufplaene konnten nicht importiert werden - bitte in n8n (Port 5678) von Hand importieren"
fi
set -e

echo "✓ Fertig. Aktueller Stand:"
git log -1 --format='   %h  %s'
