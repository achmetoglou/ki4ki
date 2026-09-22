#!/bin/sh
# Prueft rechte-setzen.sh: Es muss das Falsche richten UND das Richtige in
# Ruhe lassen.
#
# Die zweite Haelfte ist die wichtigere. Erst sie erlaubt, das Skript im
# Takt laufen zu lassen: Fasst es eine schon richtige Datei an, schreibt es
# ihre ctime neu - und stellt damit die Claim-Garantie (3 h) und das
# Einraeumen (1 h) fuer alles im Eingang auf null.
#
#   sh bau/rechte-probe.sh
set -u
HIER=$(cd "$(dirname "$0")/.." && pwd)
BAUM=$(mktemp -d)
FEHLER=0

pruefe() {
  if [ "$1" = "ja" ]; then printf '  ok   %s\n' "$2"
  else printf '  FEHL %s\n' "$2"; FEHLER=$((FEHLER + 1)); fi
}

# --- Baum: zwei falsche, zwei richtige ------------------------------------
mkdir -p "$BAUM/bereich/input/Kunde"      # kommt als 0755 vom mktemp-umask
printf 'x' > "$BAUM/bereich/input/Kunde/neu.pdf"
chmod 0755 "$BAUM/bereich/input/Kunde"
chmod 0644 "$BAUM/bereich/input/Kunde/neu.pdf"

mkdir -p "$BAUM/bereich/archiv"
printf 'x' > "$BAUM/bereich/archiv/alt.pdf"
chmod 2775 "$BAUM/bereich/archiv"
chmod 0664 "$BAUM/bereich/archiv/alt.pdf"

vorher_ctime=$(stat -c %Z "$BAUM/bereich/archiv/alt.pdf")
vorher_dir=$(stat -c %Z "$BAUM/bereich/archiv")
sleep 1                      # damit ein Anfassen an der ctime sichtbar waere

KI4KI_GID=$(id -g) KI4KI_UID_ANLAGE=$(id -u) \
  sh "$HIER/rechte-setzen.sh" "$BAUM" || { echo "Skript brach ab"; exit 1; }

# --- 1. Das Falsche ist gerichtet -----------------------------------------
d=$(stat -c %a "$BAUM/bereich/input/Kunde")
f=$(stat -c %a "$BAUM/bereich/input/Kunde/neu.pdf")
pruefe "$([ "$d" = "2775" ] && echo ja || echo nein)" \
       "der fremde Ordner ist jetzt 2775 (ist $d) - die Aufnahme darf herausbewegen"
pruefe "$([ "$f" = "664" ] && echo ja || echo nein)" \
       "die fremde Datei ist jetzt 664 (ist $f)"

# --- 2. Das Richtige ist UNANGETASTET -------------------------------------
# ⛔ Ohne diese zwei Zeilen duerfte das Skript NICHT im Takt laufen.
nachher_ctime=$(stat -c %Z "$BAUM/bereich/archiv/alt.pdf")
nachher_dir=$(stat -c %Z "$BAUM/bereich/archiv")
pruefe "$([ "$vorher_ctime" = "$nachher_ctime" ] && echo ja || echo nein)" \
       "die schon richtige Datei wurde nicht angefasst (ctime $vorher_ctime -> $nachher_ctime)"
pruefe "$([ "$vorher_dir" = "$nachher_dir" ] && echo ja || echo nein)" \
       "der schon richtige Ordner wurde nicht angefasst (ctime $vorher_dir -> $nachher_dir)"

# --- 3. Gegenprobe: ohne die Filter MUSS die ctime wandern ----------------
# Sonst sagt Nummer 2 nichts - sie waere auch gruen, wenn stat hier immer
# dasselbe liefert oder das Skript ueberhaupt nichts tut.
sleep 1
chmod 664 "$BAUM/bereich/archiv/alt.pdf"          # bedingungslos, wie es das
                                                   # Skript OHNE Filter taete
gegen_ctime=$(stat -c %Z "$BAUM/bereich/archiv/alt.pdf")
pruefe "$([ "$vorher_ctime" != "$gegen_ctime" ] && echo ja || echo nein)" \
       "Gegenprobe: ein bedingungsloses chmod wandert die ctime sehr wohl ($vorher_ctime -> $gegen_ctime)"

rm -rf "$BAUM"
printf '\n%d Fehler\n' "$FEHLER"
[ "$FEHLER" -eq 0 ]
