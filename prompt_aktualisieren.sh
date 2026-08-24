#!/bin/bash
# ============================================================================
#  Den Systemprompt aus systemprompt.txt auf ALLE Arbeitsbereiche ausrollen.
#
#  Ein Befehl:  ./prompt_aktualisieren.sh
#
#  Wann noetig: Nach einem Update, das systemprompt.txt veraendert hat. Neue
#  Arbeitsbereiche bekommen den Prompt automatisch (Selbstheilung), bestehende
#  behalten ihren - bis dieser Befehl ihn ersetzt.
#  ⚠ Ueberschreibt eigene Anpassungen am Prompt eines Bereichs.
# ============================================================================
set -e
cd "$(dirname "$0")"
KEY=$(grep -oP '^KI4KI_API_KEY=\K.*' .secrets.env 2>/dev/null || true)
[ -z "$KEY" ] && { echo "Kein KI4KI_API_KEY in .secrets.env"; exit 1; }
PROMPT=$(python3 -c 'import json,sys;print(json.dumps(open("systemprompt.txt",encoding="utf-8").read()))')
SLUGS=$(curl -s -H "Authorization: Bearer $KEY" http://localhost:3001/api/v1/workspaces \
  | python3 -c 'import json,sys;print(" ".join(w["slug"] for w in json.load(sys.stdin).get("workspaces",[])))')
[ -z "$SLUGS" ] && { echo "Keine Arbeitsbereiche gefunden (laeuft die Anlage?)"; exit 1; }
for s in $SLUGS; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    "http://localhost:3001/api/v1/workspace/$s/update" -d "{\"openAiPrompt\": $PROMPT}")
  echo "  $s -> HTTP $code"
done
echo "✓ Prompt ausgerollt. Neue Fragen nutzen ihn sofort."
