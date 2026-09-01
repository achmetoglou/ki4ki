#!/bin/bash
# ============================================================================
#  Arbeitsbereich anlegen - mit den Einstellungen, auf die alles aufbaut
#
#  Aufruf:  ./arbeitsbereich_anlegen.sh <API-Schluessel> [Name] [Fachgebiet] [Wer fragt] [Besonderheiten]
#           Die drei letzten Angaben ergeben die ROLLE des Bereichs
#           (dokumente/<bereich>/prompt.md) - sonst spaeter im Chat
#           "Rolle einrichten" sagen oder die Datei bearbeiten.
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

FACH="${3:-}"; NUTZER="${4:-}"; BESONDERES="${5:-}"
python3 - "$SCHLUESSEL" "$API" "$NAME" "$FACH" "$NUTZER" "$BESONDERES" <<'ENDE'
import json, os, re, sys, urllib.request
sys.path.insert(0, "pruef-proxy")
import rolle

schluessel, api, name = sys.argv[1], sys.argv[2], sys.argv[3]
fach, nutzer, besonderes = sys.argv[4], sys.argv[5], sys.argv[6]
kopf = {"Authorization": "Bearer " + schluessel, "Content-Type": "application/json"}
kern = open("systemprompt.txt", encoding="utf-8").read()
prompt = kern


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

# 1b. Rolle des Bereichs (Datei) - wenn die drei Angaben mitkommen
ordner = os.path.join("dokumente", re.sub(r"[^A-Za-z0-9_-]+", "-", slug).strip("-"))
if fach or nutzer or besonderes:
    os.makedirs(ordner, exist_ok=True)
    text = rolle.vorlage(fach, nutzer, besonderes, slug=os.path.basename(ordner))
    with open(os.path.join(ordner, rolle.DATEI), "w", encoding="utf-8") as fh:
        fh.write(text)
    prompt = rolle.zusammensetzen(kern, text)
    print("  Rolle geschrieben: %s" % os.path.join(ordner, rolle.DATEI))

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
    # 27.08.: 20 statt 6 - mit 6 vergass der Bereich das Gespraech nach drei Fragen;
    # den Faden haelt ohnehin der Proxy, AnythingLLM bekommt dieselbe Tiefe
    "openAiHistory": 20,
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
echo "  Jetzt Dokumente nach ./dokumente/<bereich>/input/ legen - die Aufnahme startet von selbst."
