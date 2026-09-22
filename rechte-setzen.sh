#!/bin/sh
# Die Rechte auf dokumente/ richtigstellen - EIN Durchgang.
#
# Warum es das gibt: n8n (Kennung 1000) und der Mensch auf dem Server teilen
# sich diesen Baum. Ordner, die ein Mensch per SFTP anlegt, gehoeren ihm und
# haben oft kein Gruppen-Schreibrecht. Die Aufnahme darf die Datei dann zwar
# lesen, aber nicht aus dem Ordner HERAUSBEWEGEN - sie bleibt im Eingang und
# wird bei jedem Minutentakt erneut aufgenommen. Gemessen am 21.09.: Aus
# einer Datei wurden binnen Minuten fuenf Bestandseintraege.
#
# ⛔ NUR anfassen, was wirklich falsch steht. Ein chown oder chmod auf eine
#   schon richtige Datei schreibt trotzdem ihre ctime neu - und an der ctime
#   haengen die Claim-Garantie (3 h) und das Einraeumen (1 h). Ohne die
#   ! -perm / ! -user / ! -group Filter stellte jeder Durchgang beide Uhren
#   fuer alles im Eingang auf null (gemessen 25.08.).
#
#   Genau deshalb darf dieses Skript im Takt laufen: Steht alles richtig,
#   fasst es nichts an und keine Uhr bewegt sich.
#
# Aufruf:  rechte-setzen.sh [zielordner]
# Umgebung: KI4KI_GID (Gruppe des Server-Nutzers), KI4KI_UID_ANLAGE (1000)
set -u

ZIEL="${1:-/files/dokumente}"
U="${KI4KI_UID_ANLAGE:-1000}"
G="${KI4KI_GID:-1000}"

mkdir -p "$ZIEL" || exit 1

find "$ZIEL" ! -user  "$U" -exec chown "$U" {} +
find "$ZIEL" ! -group "$G" -exec chgrp "$G" {} +
find "$ZIEL" -type d ! -perm 2775 -exec chmod 2775 {} +
find "$ZIEL" -type f ! -perm 664  -exec chmod 664  {} +
