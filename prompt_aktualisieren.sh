#!/bin/bash
# ============================================================================
#  Den Systemprompt auf ALLE Arbeitsbereiche ausrollen - je Bereich als
#  Kern (systemprompt.txt) + Rolle (dokumente/<bereich>/prompt.md).
#
#  Ein Befehl:  ./prompt_aktualisieren.sh
#
#  Wann noetig: Nach einem Update, das systemprompt.txt veraendert hat.
#  Aenderungen an einer prompt.md spielt der Proxy von selbst binnen fuenf
#  Minuten ein - dieses Skript braucht es dafuer nicht.
#  ⚠ Ueberschreibt Aenderungen, die jemand direkt in der Oberflaeche am
#    Prompt gemacht hat - die Wahrheit sind die beiden Dateien.
# ============================================================================
set -e
cd "$(dirname "$0")"
KEY=$(grep -oP '^KI4KI_API_KEY=\K.*' .secrets.env 2>/dev/null | tr -d '"' | tr -d "'" || true)
[ -z "$KEY" ] && { echo "Kein KI4KI_API_KEY in .secrets.env"; exit 1; }
python3 - "$KEY" <<'ENDE'
import json, os, re, sys, urllib.request
sys.path.insert(0, "pruef-proxy")
import rolle
key = sys.argv[1]
api = "http://127.0.0.1:3001/api/v1"
kopf = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
kern = open("systemprompt.txt", encoding="utf-8").read()

def ruf(pfad, koerper=None):
    daten = json.dumps(koerper).encode() if koerper is not None else None
    req = urllib.request.Request(api + pfad, data=daten, headers=kopf)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def ordnername(slug):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", slug or "").strip("-")

ws = (ruf("/workspaces") or {}).get("workspaces") or []
if not ws:
    print("Keine Arbeitsbereiche gefunden (laeuft die Anlage?)"); sys.exit(1)
for w in ws:
    slug = w["slug"]
    pfad = os.path.join("dokumente", ordnername(slug), rolle.DATEI)
    text = open(pfad, encoding="utf-8").read() if os.path.exists(pfad) else ""
    prompt = rolle.zusammensetzen(kern, text)
    ruf("/workspace/%s/update" % slug, {"openAiPrompt": prompt})
    print("  %-28s %s (%d Zeichen)" % (slug, "Kern + Rolle" if rolle.ist_eingerichtet(text) else "nur Kern", len(prompt)))
print("✓ Prompt ausgerollt. Neue Fragen nutzen ihn sofort.")
ENDE
