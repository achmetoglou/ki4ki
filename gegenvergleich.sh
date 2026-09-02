#!/bin/bash
# ============================================================================
#  Gegenvergleich fuer Vorfuehrungen: dasselbe AnythingLLM zusaetzlich nackt
#  auf Tor 3000 - ohne Belegpruefung, ohne Wege, ohne Wachen. Der Unterschied
#  zur Anlage auf Tor 3001 ist das eigentliche Vorfuehrstueck.
#
#  Aufruf:  ./gegenvergleich.sh an     Tor 3000 oeffnen
#           ./gegenvergleich.sh aus    Tor 3000 schliessen (Normalzustand)
#
#  Hinweise: Das Umschalten erzeugt den AnythingLLM-Behaelter neu - die
#  Oberflaeche ist dabei einige Sekunden weg, Daten und Anmeldungen bleiben
#  (Schluessel kommen aus .secrets.env, die Daten liegen im Volume).
#  Nicht umschalten, waehrend jemand mit der Anlage arbeitet.
# ============================================================================
set -e
cd "$(dirname "$0")"

BASIS=$(grep '^COMPOSE_FILE=' .env 2>/dev/null | cut -d= -f2)
BASIS=${BASIS:-docker-compose.yml}

case "$1" in
  an)
    COMPOSE_FILE="$BASIS:docker-compose.gegenvergleich.yml" docker compose up -d anythingllm
    echo "Gegenvergleich AN:"
    echo "  ohne Belegpruefung:  http://<server-ip>:3000  (nacktes AnythingLLM)"
    echo "  die Anlage:          http://<server-ip>:3001  (mit Belegpruefung)"
    echo "  Anmeldung ist auf beiden dieselbe. Nach der Vorfuehrung: ./gegenvergleich.sh aus"
    ;;
  aus)
    COMPOSE_FILE="$BASIS" docker compose up -d anythingllm
    echo "Gegenvergleich AUS - Tor 3000 ist geschlossen, alles laeuft wieder nur ueber die Anlage."
    ;;
  *)
    echo "Aufruf: ./gegenvergleich.sh an|aus"
    exit 1
    ;;
esac
