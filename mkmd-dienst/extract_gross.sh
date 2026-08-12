#!/bin/bash
# PHASE 1 fuer GROSSE Dokumente: Auftrag abgeben, spaeter abholen.
#
# Warum getrennt von extract.sh: Sobald Bildbeschreibung eingeschaltet
# ist, dauert ein Werk mit vielen Abbildungen Stunden - DVS 2213-1 hat
# 475. Der gewoehnliche Weg wartet auf einer offenen Verbindung, und die
# haelt so lange nicht durch: Sie brach schon einmal nach 6 Minuten mit
# "HTTP 100" ab, obwohl die Zeitgrenze auf zwei Stunden stand und
# Docling selbst bis zu einer Stunde synchron wartet.
#
# Hier wird der Auftrag abgegeben, die Kennung gemerkt und der
# Fortschritt in Ruhe abgefragt. Faellt die Verbindung dazwischen aus,
# laeuft der Auftrag weiter.
#
#   ./extract_gross.sh <pdf> <zielordner> [minuten-geduld]
set -u
PDF="$1"; OUT="$2"; GEDULD="${3:-600}"
NAME=$(basename "$PDF"); BASE="${NAME%.pdf}"
HIER="$(cd "$(dirname "$0")" && pwd)"
[ -s "$OUT/$BASE.raw.md" ] && { echo "liegt schon vor"; exit 0; }
mkdir -p "$OUT"
TMP=$(mktemp -d)

# Dem Waechter sagen, dass hier ein langer Lauf arbeitet. Ohne diese
# Marke sieht er stundenlang kein fertiges Dokument, haelt das fuer
# Stillstand und startet Docling neu - nach 57 Minuten genau
# so passiert, der Auftrag war weg.
# Die Marke traegt einen Zeitstempel und verfaellt beim Waechter von
# selbst, falls dieses Skript hart abgebrochen wird.
BILDMARKE="$(dirname "$0")/.bildlauf-aktiv"
date +%s > "$BILDMARKE"
# Auch bei Abbruch wegraeumen - eine liegengebliebene Marke macht den
# Waechter fuer echte Haenger blind.
trap 'rm -rf "$TMP"; rm -f "$BILDMARKE"' EXIT INT TERM

# Die Anfuehrungszeichen um $PDF sind kein Schmuck: curl liest in -F das
# KOMMA als Trennzeichen fuer mehrere Dateien.
ABGABE=$(curl -s -m 300 -X POST \
  http://localhost:5001/v1/convert/file/async \
  -F "files=@\"$PDF\"" -F "to_formats=md" -F "to_formats=json" \
  -F "do_formula_enrichment=true" -F "do_table_structure=true" \
  -F "table_mode=accurate" -F "md_page_break_placeholder=[[SEITE]]" \
  -F "do_picture_description=true" \
  -F "do_picture_classification=true" \
  -F "picture_description_area_threshold=0.03" \
  -F "picture_description_custom_config=$(cat "$HIER/bildmodell.json")")

KENNUNG=$(printf '%s' "$ABGABE" | python3 -c \
  'import json,sys
try: print(json.load(sys.stdin).get("task_id") or "")
except Exception: print("")')

if [ -z "$KENNUNG" ]; then
  echo "Auftrag nicht angenommen: $(printf '%s' "$ABGABE" | head -c 200)"
  exit 1
fi
echo "Auftrag $KENNUNG abgegeben, Geduld ${GEDULD} Minuten"

ENDE=$(( $(date +%s) + GEDULD * 60 ))
STAND=""
while [ "$(date +%s)" -lt "$ENDE" ]; do
  ANTWORT=$(curl -s -m 60 "http://localhost:5001/v1/status/poll/$KENNUNG?wait=30")
  NEU=$(printf '%s' "$ANTWORT" | python3 -c \
    'import json,sys
try: print(json.load(sys.stdin).get("task_status") or "?")
except Exception: print("?")')
  if [ "$NEU" != "$STAND" ]; then
    echo "  [$(date +%H:%M)] $NEU"
    STAND="$NEU"
  fi
  case "$NEU" in
    success) break ;;
    failure|revoked) echo "Auftrag gescheitert: $NEU"; exit 1 ;;
  esac
  sleep 20
done

if [ "$STAND" != "success" ]; then
  echo "Nach ${GEDULD} Minuten noch nicht fertig (Stand: $STAND)."
  echo "Der Auftrag laeuft weiter. Ergebnis spaeter abholen mit:"
  echo "  curl -s http://localhost:5001/v1/result/$KENNUNG -o ergebnis.json"
  exit 2
fi

curl -s -m 300 "http://localhost:5001/v1/result/$KENNUNG" -o "$TMP/d.json"
python3 "$HIER/bildbeschreibung.py" "$TMP/d.json" "$OUT/$BASE.raw.md"
