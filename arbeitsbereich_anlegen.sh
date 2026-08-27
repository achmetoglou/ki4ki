#!/bin/bash
# ============================================================================
#  Arbeitsbereich anlegen - mit den Einstellungen, auf die alles aufbaut
#
#  Aufruf:  ./arbeitsbereich_anlegen.sh <API-Schluessel>
#
#  Warum das nicht von Hand geht: AnythingLLMs Voreinstellungen bauen die
#  Belegpruefung still ab. Drei Werte entscheiden darueber, und keiner davon
#  faellt beim Klicken auf. Sie stehen unten mit Begruendung.
# ============================================================================
set -e
cd "$(dirname "$0")"

SCHLUESSEL="$1"
[ -n "$SCHLUESSEL" ] || { echo "Aufruf: $0 <API-Schluessel aus der Oberflaeche>"; exit 1; }

API="http://127.0.0.1:3001/api/v1"
NAME="${2:-Wissensdatenbank}"

[ -f systemprompt.txt ] || { echo "systemprompt.txt fehlt"; exit 1; }

python3 - "$SCHLUESSEL" "$API" "$NAME" <<'ENDE'
import json, sys, urllib.request

schluessel, api, name = sys.argv[1], sys.argv[2], sys.argv[3]
kopf = {"Authorization": "Bearer " + schluessel, "Content-Type": "application/json"}
prompt = open("systemprompt.txt", encoding="utf-8").read()


def ruf(pfad, koerper=None):
    daten = json.dumps(koerper).encode() if koerper is not None else None
    req = urllib.request.Request(api + pfad, data=daten, headers=kopf)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# 1. anlegen
neu = ruf("/workspace/new", {"name": name})
w = neu.get("workspace") or {}
slug = w.get("slug")
if not slug:
    print("Anlegen fehlgeschlagen:", neu)
    sys.exit(1)

# 2. die drei entscheidenden Werte setzen
ruf("/workspace/%s/update" % slug, {
    # ohne Zitierpflicht schreibt das Modell keine woertlichen Belege -
    # dann hat die Pruefschicht nichts zu pruefen
    "openAiPrompt": prompt,
    # "query" statt der Voreinstellung "automatic": im automatischen Modus
    # springt der Chat in den Agent-Modus und liefert GAR KEINE Quellen
    "chatMode": "query",
    # wie viele Textstellen die Suche vorlegen darf. GEMESSEN (T4, 04.08.,
    # 5 Fragen x 5 Fassungen): 25 schlaegt 9 und 100 - mehr Inhalt aus mehr
    # Arbeiten; 100 kostet nur 40 s mehr und bringt nichts.
    "topN": 25,
    # Voreinstellung 0,75 laesst kaum etwas durch
    "similarityThreshold": 0.25,
    # wie viele frühere Nachrichten mitgehen. Zu viele, und das Modell sieht
    # seine eigene vorherige Antwort und schreibt etwas anderes - gemessen:
    # 14 % Aehnlichkeit zwischen zwei Antworten auf dieselbe Frage
    "openAiHistory": 6,
    "openAiTemp": 0.2,
})

nach = ruf("/workspace/%s" % slug)
wa = nach.get("workspace")
wa = wa[0] if isinstance(wa, list) else wa
print("  Arbeitsbereich '%s' angelegt (%s)" % (wa.get("name"), slug))
print("  Modus %s · topN %s · Schwelle %s · Verlauf %s · Prompt %d Zeichen"
      % (wa.get("chatMode"), wa.get("topN"), wa.get("similarityThreshold"),
         wa.get("openAiHistory"), len(wa.get("openAiPrompt") or "")))
ENDE

echo
echo "  Jetzt Dokumente nach ./dokumente legen und den Ablaufplan in n8n starten."
