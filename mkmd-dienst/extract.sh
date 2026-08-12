#!/bin/bash
# PHASE 1: nur Docling-Extraktion -> Roh-Markdown
PDF="$1"; OUT="$2"
NAME=$(basename "$PDF"); BASE="${NAME%.pdf}"
[ -s "$OUT/$BASE.raw.md" ] && exit 0
TMP=$(mktemp -d); trap "rm -rf $TMP" EXIT
# Die Anfuehrungszeichen um $PDF sind kein Schmuck: curl liest in -F das
# KOMMA als Trennzeichen fuer mehrere Dateien. "LE Anforderung an
# Maschinen, Gerate und Einrichtungen.pdf" wurde dadurch zu zwei erfundenen
# Namen, von denen keiner existiert - curl brach ab, bevor eine Verbindung
# stand (Fehler 26, %{time_total} 0.000000s). Mit den Anfuehrungszeichen
# kommt dieselbe Datei in sechs Sekunden durch.
# Bildbeschreibung: Frueher schickte diese Kette WEDER
# do_picture_description NOCH do_picture_classification - die
# Produktivkette hatte Bildbeschreibung also nie eingeschaltet, egal was
# in den Testwerkzeugen stand.
#
# ⚠ Beide Schalter zusammen, nie einzeln: classification_allow im
# Beschreibungs-Abschnitt ist eine POSITIVLISTE. Ohne eingeschaltete
# Klassifikation traegt kein Bild eine Klasse, und die Liste filtert
# ALLES weg. Gemessen (02_126.pdf, S. 10-12):
#   ohne Klassifikation  ->  2 s, 0 von 1 beschrieben
#   mit  Klassifikation  -> 73 s, 1 von 1 beschrieben
#
# to_formats=json wird zusaetzlich gebraucht: Bildunterschrift und Art
# der Abbildung stehen NICHT im Markdown, sondern nur im JSON. Genau die
# Bildunterschrift ist aber der Begriff, den ein Fachnutzer eingibt.
HTTP=$(curl -s -o "$TMP/d.json" -w "%{http_code}" -m 7200 \
  -X POST http://localhost:5001/v1/convert/file \
  -F "files=@\"$PDF\"" -F "to_formats=md" -F "to_formats=json" \
  -F "do_formula_enrichment=true" -F "do_table_structure=true" \
  -F "table_mode=accurate" -F "md_page_break_placeholder=[[SEITE]]" \
  -F "do_picture_description=true" \
  -F "do_picture_classification=true" \
  -F "picture_description_area_threshold=0.03" \
  -F "picture_description_custom_config=$(cat "$(dirname "$0")/bildmodell.json")")
if [ "$HTTP" != "200" ]; then
  # Ohne diese Unterscheidung stand im Protokoll die Meldung von head
  # ("cannot open ...") statt der Ursache - und die Suche danach kostete
  # einen halben Tag.
  if [ -s "$TMP/d.json" ]; then
    echo "HTTP $HTTP: $(head -c 150 "$TMP/d.json")"
  else
    echo "HTTP $HTTP: curl hat nichts geliefert (Datei nicht lesbar? Sonderzeichen im Namen?)"
  fi
  exit 1
fi
# Das Markdown wird nicht mehr hier zusammengesetzt, sondern von
# bildbeschreibung.py: Es ergaenzt je Abbildung die Bildunterschrift und
# die Art der Abbildung, die beide nur im JSON stehen. Der eigentliche
# Beschreibungstext steht bereits im Markdown, direkt hinter der Marke
# "<!-- image -->" - er wird NICHT wiederholt.
#
# Ausgelagert, weil ein Heredoc die Anfuehrungszeichen im JSON zerreisst.
python3 "$(dirname "$0")/bildbeschreibung.py" "$TMP/d.json" "$OUT/$BASE.raw.md"
