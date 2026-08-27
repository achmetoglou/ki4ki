#!/bin/bash
# ============================================================================
#  Bestehende Arbeitsbereiche auf die gemessenen Werte bringen
#
#  Der Proxy setzt die geprueften Werte (topN 25, Schwelle 0,25, Modus
#  "query", Verlauf 6, Temperatur 0,2) NUR beim Anlegen eines Bereichs -
#  bestehende Bereiche fasst er absichtlich nie an. Aendern sich die Werte
#  (26.08.: topN 6 -> 25, weil auf dem Testserver gemessen), holt dieses
#  Skript alle Bereiche einmal nach. Der Systemprompt bleibt unangetastet.
#
#  Aufruf:  ./bereiche_nachziehen.sh            (Schluessel aus .secrets.env)
#           ./bereiche_nachziehen.sh <API-Schluessel>
# ============================================================================
set -e
cd "$(dirname "$0")"
SCHLUESSEL="${1:-}"
if [ -z "$SCHLUESSEL" ] && [ -f .secrets.env ]; then
  SCHLUESSEL="$(grep -E '^KI4KI_API_KEY=' .secrets.env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi
[ -n "$SCHLUESSEL" ] || { echo "Kein API-Schluessel (Argument oder KI4KI_API_KEY in .secrets.env)"; exit 1; }

python3 - "$SCHLUESSEL" <<'ENDE'
import json, sys, urllib.request
schluessel = sys.argv[1]
api = "http://127.0.0.1:3001/api/v1"
kopf = {"Authorization": "Bearer " + schluessel, "Content-Type": "application/json"}
WERTE = {"chatMode": "query", "topN": 25, "similarityThreshold": 0.25, "openAiHistory": 20, "openAiTemp": 0.2}

def ruf(pfad, koerper=None):
    daten = json.dumps(koerper).encode() if koerper is not None else None
    req = urllib.request.Request(api + pfad, data=daten, headers=kopf)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

ws = (ruf("/workspaces") or {}).get("workspaces") or []
for w in ws:
    slug = w.get("slug")
    alt = {k: w.get(k) for k in WERTE}
    if all(str(alt.get(k)) == str(v) for k, v in WERTE.items()):
        print("  %-30s unveraendert (topN %s, Temp %s)" % (slug, alt["topN"], alt["openAiTemp"]))
        continue
    ruf("/workspace/%s/update" % slug, WERTE)
    print("  %-30s topN %s -> %s, Temp %s -> %s, Modus %s -> %s" % (
        slug, alt["topN"], WERTE["topN"], alt["openAiTemp"], WERTE["openAiTemp"], alt["chatMode"], WERTE["chatMode"]))
print("%d Bereiche geprueft." % len(ws))
ENDE
