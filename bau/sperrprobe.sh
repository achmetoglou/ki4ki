#!/bin/bash
# Trockenprobe fuer die Claim-Garantie: Wohin wandert eine Datei aus einem
# Unterordner? Die alte Fassung legte sie UNTERHALB des Eingangs ab und der
# naechste Durchgang sammelte sie von dort wieder ein - der Riegel gegen
# Endlosschleifen erzeugte eine.
set -e
W="$(dirname "$0")/probe"

aufbauen () {
  rm -rf "$W"
  mkdir -p "$W/kap/in"put/Normen/Kleben
  : > "$W/kap/in"put/Normen/Kleben/x.pdf
  : > "$W/kap/in"put/flach.pdf
}

zeigen () {
  find "$W" -type f | sed "s|$W/||" | sort | sed 's/^/     /'
}

aufbauen
echo "=== ALTE Fassung: dirname(dirname(f)) ==="
find "$W" -type f -exec sh -c '
  for f do
    b=$(dirname "$(dirname "$f")")
    mkdir -p "$b/aussortiert"
    mv "$f" "$b/aussortiert/" 2>/dev/null || true
  done' sh {} +
zeigen

aufbauen
echo
echo "=== NEUE Fassung: Segment vor dem Eingang ==="
find "$W" -type f -exec sh -c '
  for f do
    b=${f%%/in"put"/*}
    r=${f#*/in"put"/}
    mkdir -p "$b/aussortiert/$(dirname "$r")"
    mv "$f" "$b/aussortiert/$r" 2>/dev/null || true
  done' sh {} +
zeigen
rm -rf "$W"
