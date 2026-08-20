#!/bin/bash
# ============================================================================
#  KI4KI Wissensdatenbank - Start
#
#  Einmal ausfuehren:  ./start.sh
#  Danach oeffnen:     http://<dieser-rechner>:3001
#
#  Das Skript legt Zugangsschluessel an, erkennt eine Grafikkarte, baut die
#  Belegpruefung und holt die Modelle. Nichts davon spricht nach draussen -
#  ausser den Abbildern und Modellen beim ersten Mal.
# ============================================================================
set -e
cd "$(dirname "$0")"

sagen() { echo -e "\n\033[1m$*\033[0m"; }

# --- Voraussetzungen -------------------------------------------------------
sagen "Voraussetzungen pruefen"
if ! command -v docker >/dev/null 2>&1; then
  echo "  Docker fehlt - installiere es (offizielles Skript get.docker.com) ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    echo ""
    echo "  ✓ Docker installiert. Jetzt EINMAL abmelden und neu anmelden"
    echo "    (damit dieser Benutzer Docker bedienen darf), dann ./start.sh nochmal."
    exit 0
  else
    echo "  Docker fehlt und kein 'curl' vorhanden - bitte Docker von Hand"
    echo "  installieren (https://get.docker.com), dann ./start.sh erneut."
    exit 1
  fi
fi
docker compose version >/dev/null 2>&1 || { echo "Docker Compose (v2) fehlt."; exit 1; }
echo "  Docker $(docker --version | cut -d' ' -f3 | tr -d ,) · Compose $(docker compose version --short)"
# Docker da, aber Benutzer nicht in der docker-Gruppe? Dann sagt es das klar,
# statt spaeter mit "permission denied ... docker.sock" abzubrechen.
if ! docker ps >/dev/null 2>&1; then
  echo "  ⚠ Docker laeuft, aber dieser Benutzer darf es nicht bedienen."
  echo "    Einmalig:  sudo usermod -aG docker $USER"
  echo "    Danach ABMELDEN und neu anmelden, dann ./start.sh nochmal."
  exit 1
fi

# --- Zugangsschluessel -----------------------------------------------------
# Diese drei Werte unterschreiben die Anmeldung. Gehen sie verloren, sind alle
# Benutzer ausgesperrt - deshalb werden sie EINMAL erzeugt und nie ersetzt.
if [ ! -f .secrets.env ]; then
  sagen "Zugangsschluessel erzeugen (einmalig)"
  {
    echo "JWT_SECRET=$(openssl rand -hex 32)"
    echo "SIG_KEY=$(openssl rand -hex 32)"
    echo "SIG_SALT=$(openssl rand -hex 32)"
    echo ""
    echo "# Der Zugang, mit dem die Aufnahme Dokumente in AnythingLLM legt."
    echo "# Er laesst sich hier NICHT erzeugen - er wird in AnythingLLM"
    echo "# angelegt und hier eingetragen. Bleibt er leer, meldet die"
    echo "# Aufnahme beim ersten Versuch einen Zugangsfehler."
    echo "KI4KI_API_KEY="
  } > .secrets.env
  chmod 600 .secrets.env
  echo "  .secrets.env angelegt - BITTE SICHERN, ohne sie kommt niemand mehr rein"
  echo "  (Den Zugangsschluessel legt der Setup-Helfer gleich automatisch an -"
  echo "   nichts von Hand noetig.)"
else
  echo "  .secrets.env vorhanden - bleibt unangetastet"
  # Wer von einer aelteren Fassung kommt, hat den Eintrag noch nicht.
  if ! grep -q "^KI4KI_API_KEY=" .secrets.env 2>/dev/null; then
    echo "KI4KI_API_KEY=" >> .secrets.env
    echo "  KI4KI_API_KEY ergaenzt - bitte in AnythingLLM einen Schluessel"
    echo "  anlegen und dort eintragen, sonst nimmt die Anlage nichts auf."
  fi
fi

# --- Ablageordner ----------------------------------------------------------
mkdir -p dokumente
# In diesen Ordner legen die Mitarbeitenden ihre PDFs, gelesen wird er vom
# Container. Damit beides geht, ohne nach Benutzernummern zu fragen:
chmod 0777 dokumente

# --- Grafikkarte -----------------------------------------------------------
sagen "Grafikkarte pruefen"
DATEIEN="-f docker-compose.yml"
if docker run --rm --gpus all ubuntu:24.04 nvidia-smi >/dev/null 2>&1; then
  DATEIEN="$DATEIEN -f docker-compose.gpu.yml"
  echo "  NVIDIA-Karte gefunden - wird genutzt"
elif command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  # Karte + Treiber sind da, aber Docker kann sie nicht nutzen: die GPU-Bruecke
  # (NVIDIA Container Toolkit) fehlt. Wird automatisch eingerichtet (braucht
  # einmal das sudo-Passwort). Schlaegt das fehl, laeuft die Anlage auf CPU
  # weiter - der Fehler bricht die Installation NICHT ab.
  echo "  NVIDIA-Karte da, aber die Docker-GPU-Bruecke fehlt - richte sie ein ..."
  if command -v apt-get >/dev/null 2>&1; then
    set +e
    # --batch --yes: Liegt der Schluessel von einer frueheren Installation
    # schon da, fragt gpg sonst interaktiv "Ueberschreiben (j/N)?" - und die
    # Installation haengt mitten im Lauf an einer Rueckfrage, die niemand
    # erwartet. Es ist derselbe oeffentliche NVIDIA-Schluessel, frisch
    # geladen; Ueberschreiben ist immer richtig.
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | sudo gpg --dearmor --batch --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
    sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    set -e
    if docker run --rm --gpus all ubuntu:24.04 nvidia-smi >/dev/null 2>&1; then
      DATEIEN="$DATEIEN -f docker-compose.gpu.yml"
      echo "  ✓ GPU-Bruecke eingerichtet - Karte wird jetzt genutzt"
    else
      echo "  ⚠ Bruecke eingerichtet, GPU aber weiter nicht nutzbar - laeuft auf CPU."
    fi
  else
    echo "  ⚠ Kein apt-get - NVIDIA Container Toolkit bitte von Hand installieren,"
    echo "    dann ./start.sh erneut. Bis dahin laeuft alles auf CPU."
  fi
elif [ -e /dev/kfd ] && [ -d /dev/dri ]; then
  # AMD-GPU mit ROCm (die Kernel-Schnittstelle /dev/kfd ist da).
  DATEIEN="$DATEIEN -f docker-compose.amd.yml"
  echo "  AMD-Karte (ROCm) erkannt - wird genutzt."
  echo "  (Auf AMD-Hardware noch ungetestet - bitte einmal pruefen:"
  echo "   docker exec ki4ki-ollama ollama ps  -> sollte '100% GPU' zeigen)"
else
  echo "  Keine nutzbare Karte gefunden - alles laeuft auf dem Prozessor."
  echo "  (Funktioniert, ist aber deutlich langsamer als mit NVIDIA-GPU.)"
fi

# Die erkannte Datei-Auswahl DAUERHAFT festhalten. Sonst zieht ein spaeteres
# blankes `docker compose up`/`restart` NUR die Basis-Datei - ohne die
# GPU-Bruecke. Ergebnis: ollama verliert die Karte und stuerzt ab
# (llama-server segfault), docling faellt auf CPU. Genau das darf keinem
# Partner passieren, der mal neu startet. docker compose liest COMPOSE_FILE
# aus .env automatisch bei JEDEM Aufruf -> die GPU-Datei ist ab jetzt immer
# dabei, ohne dass jemand `-f ...` tippen muss.
COMPOSE_WERT=$(printf '%s' "$DATEIEN" | sed 's/-f //g' | xargs | tr ' ' ':')
touch .env
if grep -q '^COMPOSE_FILE=' .env 2>/dev/null; then
  sed -i "s|^COMPOSE_FILE=.*|COMPOSE_FILE=$COMPOSE_WERT|" .env
else
  printf 'COMPOSE_FILE=%s\n' "$COMPOSE_WERT" >> .env
fi
echo "  Compose-Auswahl in .env gemerkt: $COMPOSE_WERT"

# --- Bauen und starten -----------------------------------------------------
sagen "Belegpruefung und Markdown-Dienst bauen"
# BEIDE selbstgebauten Images, nicht nur der Proxy. Fehlt ki4ki-mkmd:1
# lokal (echte Null-Installation), versucht 'compose up' es aus einer
# Registry zu ziehen und zeigt ein beunruhigendes "pull access denied" -
# das Image gibt es nirgends zu ziehen, es entsteht nur hier.
docker compose $DATEIEN build pruef-proxy mkmd-dienst

sagen "Anlage starten"
docker compose $DATEIEN up -d

# --- Modelle holen ---------------------------------------------------------
sagen "Modelle holen (beim ersten Mal einige Minuten)"
for i in $(seq 1 30); do
  docker exec ki4ki-ollama ollama list >/dev/null 2>&1 && break
  sleep 5
done
docker exec ki4ki-ollama ollama pull gemma4:12b
docker exec ki4ki-ollama ollama pull bge-m3

# Docling-Formelmodell: Das Docling-Image bringt Layout/OCR/Tabellen/
# Bild-Klassifikation mit, aber NICHT CodeFormulaV2 - der Aufnahme-Workflow
# nutzt aber Formelerkennung. Fehlt das Modell, bricht Docling den GANZEN
# Convert ab ("Model not found in artifacts_path") und jedes Dokument landet
# mit leerem Text in aussortiert (ohne sichtbaren Fehler). Einmalig laden;
# bleibt im Volume. Ausfallsicher: schlaegt es fehl, laeuft die Installation
# weiter (Formelerkennung dann eingeschraenkt).
set +e
for i in $(seq 1 40); do
  docker exec ki4ki-docling sh -c 'ls /opt/app-root/src/.cache/docling/models >/dev/null 2>&1' && break
  sleep 3
done
if docker exec ki4ki-docling sh -c 'ls /opt/app-root/src/.cache/docling/models/ 2>/dev/null | grep -qi codeformula'; then
  echo "  Docling-Formelmodell schon vorhanden"
else
  echo "  Docling-Formelmodell (CodeFormulaV2) laden - einmalig, ein paar Minuten ..."
  if docker exec ki4ki-docling docling-tools models download-hf-repo docling-project/CodeFormulaV2 >/dev/null 2>&1; then
    echo "  ✓ CodeFormulaV2 geladen"
  else
    echo "  ⚠ CodeFormulaV2-Download fehlgeschlagen (Internet?) - Formelerkennung eingeschraenkt."
  fi
fi
set -e

# --- Ablaufplaene automatisch einspielen -----------------------------------
# Die 3 n8n-Workflows werden per CLI importiert - die IDs bleiben erhalten,
# damit die Unter-Workflow-Verknuepfungen halten - und der Masse-Ingest wird
# aktiviert. Schlaegt etwas fehl, laeuft die Installation weiter; die Workflows
# lassen sich dann per n8n-Oberflaeche ("Import from File") nachziehen.
sagen "Ablaufplaene einspielen"
set +e
for i in $(seq 1 40); do
  docker exec ki4ki-n8n n8n --version >/dev/null 2>&1 && break
  sleep 3
done
docker exec ki4ki-n8n sh -c 'rm -rf /tmp/wf && mkdir -p /tmp/wf'
for wf in n8n-workflows/*.json; do docker cp "$wf" ki4ki-n8n:/tmp/wf/ >/dev/null 2>&1; done
if docker exec ki4ki-n8n n8n import:workflow --separate --input=/tmp/wf >/dev/null 2>&1; then
  echo "  Workflows importiert (Verknuepfungen bleiben erhalten)"
  # ⭐ ALLE DREI aktivieren, nicht nur den Haupt-Workflow. n8n weigert sich,
  #   eine INAKTIVE Unterkette auszufuehren ("Workflow is not active and
  #   cannot be executed"). Dann ruft der Masse-Ingest die Docling- und die
  #   Markdown-Unterkette NIE auf - jedes Dokument landet mit leerem Text in
  #   aussortiert, ganz ohne Fehlermeldung (der Aufruf-Node schluckt sie per
  #   onError=continueRegularOutput). Die executeWorkflow-Verknuepfungen
  #   brauchen die Unterketten AKTIV.
  _wf_ok=1
  for _wid in 1DKWgDbdCiwa25E1 uK5WCYhjVqPawcvP J8pPkKTKmkFTXjGn; do
    docker exec ki4ki-n8n n8n update:workflow --id="$_wid" --active=true >/dev/null 2>&1 || _wf_ok=0
  done
  [ "$_wf_ok" = 1 ] && echo "  Masse-Ingest + Unterketten aktiviert" \
    || echo "  ⚠ Nicht alle Workflows aktiviert - bitte in n8n pruefen"
  docker restart ki4ki-n8n >/dev/null 2>&1   # damit Zeitplan + aktive Unterketten registrieren
else
  echo "  ⚠ Auto-Import nicht moeglich - Workflows bitte per n8n-Oberflaeche"
  echo "    (Port 5678, Import from File) aus n8n-workflows/ laden."
fi
set -e

# --- Konto + Schluessel automatisch anlegen (Setup-Helfer) -----------------
# Nimmt den letzten manuellen Rest ab: Admin-Konto, API-Schluessel und ersten
# Arbeitsbereich. Laeuft NUR, solange in .secrets.env noch kein Schluessel
# steht. Ausfallsicher (set +e): klappt etwas nicht, bleibt der manuelle Weg.
KONTO_FERTIG=""; ADMIN_USER="admin"; ADMIN_PW=""; PW_ERZEUGT=""
if grep -q '^KI4KI_API_KEY=.' .secrets.env 2>/dev/null; then
  KONTO_FERTIG=1                       # schon eingerichtet (erneuter Lauf)
else
  sagen "Konto und Zugangsschluessel einrichten"
  set +e
  TOR="http://127.0.0.1:3001"
  for i in $(seq 1 40); do             # auf die Oberflaeche warten
    [ "$(curl -s -m3 -o /dev/null -w '%{http_code}' "$TOR/" 2>/dev/null)" = "200" ] && break
    sleep 3
  done
  echo ""
  echo "  Es wird EIN Admin-Konto angelegt (Benutzer: admin). Ohne Passwort"
  echo "  kommt niemand in die Oberflaeche - der einzige Schritt fuer einen Menschen."
  # Passwort-Regel wie n8n sie verlangt (min. 8 Zeichen, 1 Zahl, 1 Grossbuch-
  # stabe), damit DASSELBE Passwort fuer Oberflaeche UND n8n funktioniert.
  if [ -t 0 ]; then
    while :; do
      printf "  Passwort festlegen (min. 8 Zeichen, 1 Zahl, 1 Grossbuchstabe; Enter = automatisch): "
      read -rs ADMIN_PW; echo ""
      [ -z "$ADMIN_PW" ] && break        # leer = automatisch erzeugen
      if printf '%s' "$ADMIN_PW" | grep -q '.\{8\}' \
         && printf '%s' "$ADMIN_PW" | grep -q '[0-9]' \
         && printf '%s' "$ADMIN_PW" | grep -q '[A-Z]'; then break; fi
      echo "  Zu schwach - min. 8 Zeichen, 1 Zahl und 1 Grossbuchstabe (fuer n8n noetig)."
    done
  fi
  if [ -z "$ADMIN_PW" ]; then
    # erzeugt, garantiert regelkonform (Grossbuchstabe + Zahl fest, Rest Zufall)
    ADMIN_PW="Ki4ki$(openssl rand -hex 8)"
    PW_ERZEUGT=1
  fi
  _koerper="{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PW\"}"
  curl -s -m20 -X POST "$TOR/api/system/enable-multi-user" \
       -H "Content-Type: application/json" -d "$_koerper" >/dev/null 2>&1
  _token=$(curl -s -m20 -X POST "$TOR/api/request-token" \
       -H "Content-Type: application/json" -d "$_koerper" \
       | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
  KI4KI_KEY=""
  if [ -n "$_token" ]; then
    KI4KI_KEY=$(curl -s -m20 -X POST "$TOR/api/admin/generate-api-key" \
       -H "Authorization: Bearer $_token" -H "Content-Type: application/json" \
       -d '{"name":"ki4ki-aufnahme"}' \
       | python3 -c "import sys,json;print((json.load(sys.stdin).get('apiKey') or {}).get('secret',''))" 2>/dev/null)
  fi
  if [ -n "$KI4KI_KEY" ]; then
    sed -i "s|^KI4KI_API_KEY=.*|KI4KI_API_KEY=$KI4KI_KEY|" .secrets.env
    docker compose $DATEIEN up -d n8n pruef-proxy >/dev/null 2>&1
    for i in $(seq 1 20); do           # auf den Proxy warten, dann Bereich anlegen
      [ "$(curl -s -m3 -o /dev/null -w '%{http_code}' "$TOR/" 2>/dev/null)" = "200" ] && break
      sleep 3
    done
    ./arbeitsbereich_anlegen.sh "$KI4KI_KEY" >/dev/null 2>&1 && echo "  Arbeitsbereich angelegt"
    # n8n-Owner mit DEMSELBEN Admin-Passwort anlegen -> keine "Set up owner"-
    # Wand mehr auf :5678. n8n 2.31 nimmt den Deaktivier-Schalter nicht mehr an,
    # also richten wir das Konto direkt ein. E-Mail ist bei n8n Pflicht
    # (admin@ki4ki.local, Partner brauchen n8n eh nie); Passwort ist identisch.
    _n8n_body=$(ADMIN_PW="$ADMIN_PW" python3 -c "import json,os;print(json.dumps({'email':'admin@ki4ki.local','firstName':'KI4KI','lastName':'Admin','password':os.environ['ADMIN_PW']}))" 2>/dev/null)
    # ⚠ n8n wurde beim Einrichten neu gestartet und braucht einen Moment, bis
    #   der Owner-Endpunkt bereit ist. Ein EINMALIGER Aufruf kam zu frueh und
    #   die "Set up owner"-Wand blieb stehen. Darum WIEDERHOLT versuchen, bis
    #   es klappt (oder das Konto schon steht).
    _n8n_ok=""
    for i in $(seq 1 40); do
      _resp=$(curl -s -m10 -X POST http://127.0.0.1:5678/rest/owner/setup \
                   -H "Content-Type: application/json" -d "$_n8n_body" 2>/dev/null)
      case "$_resp" in
        *'"isOwner":true'*) _n8n_ok=1; break ;;   # frisch angelegt
        *already*)          _n8n_ok=1; break ;;   # schon vorhanden (erneuter Lauf)
      esac
      sleep 3
    done
    [ -n "$_n8n_ok" ] \
      && echo "  n8n-Konto eingerichtet (kein Setup-Bildschirm)" \
      || echo "  ⚠ n8n-Konto nicht automatisch angelegt - :5678 einmal von Hand einrichten"
    echo "  Konto und Zugangsschluessel eingerichtet"
    KONTO_FERTIG=1
    if [ -n "$PW_ERZEUGT" ]; then       # erzeugtes Passwort sichern - sonst weg
      { echo "Oberflaeche: http://<dieser-rechner>:3001"
        echo "Benutzer:    $ADMIN_USER"
        echo "Passwort:    $ADMIN_PW"
        echo ""
        echo "n8n (nur intern, meist nicht noetig): http://<dieser-rechner>:5678"
        echo "Benutzer:    admin@ki4ki.local"
        echo "Passwort:    (dasselbe wie oben)"; } > zugangsdaten.txt
      chmod 600 zugangsdaten.txt
    fi
  else
    echo "  ⚠ Automatische Einrichtung nicht moeglich - siehe manuellen Weg unten."
  fi
  set -e
fi

# --- Fertig ----------------------------------------------------------------
sagen "Fertig"
docker compose $DATEIEN ps --format "  {{.Name}}  {{.Status}}"

echo ""
echo "  Oberflaeche:  http://<dieser-rechner>:3001"
echo "  Ablaufplaene: http://<dieser-rechner>:5678"
echo ""
if [ -n "$KONTO_FERTIG" ]; then
  echo "  Die Anlage ist eingerichtet - die Ablaufplaene laufen."
  if [ -n "$ADMIN_PW" ]; then
    echo ""
    echo "  Anmeldung an der Oberflaeche (Port 3001):"
    echo "     Benutzer:  $ADMIN_USER"
    if [ -n "$PW_ERZEUGT" ]; then
      echo "     Passwort:  $ADMIN_PW"
      echo "     ^-- automatisch erzeugt. Auch gespeichert in ./zugangsdaten.txt (nur du lesbar)."
    else
      echo "     Passwort:  (das von dir gewaehlte)"
    fi
    # Auch die n8n-Anmeldung nennen - sonst steht sie nirgends, wenn der
    # Mensch sein Passwort selbst gewaehlt hat (zugangsdaten.txt entsteht
    # nur beim automatisch erzeugten Passwort).
    echo ""
    echo "  Anmeldung an den Ablaufplaenen (Port 5678, meist nicht noetig):"
    echo "     Benutzer:  admin@ki4ki.local"
    echo "     Passwort:  (dasselbe wie oben)"
  fi
  echo ""
  echo "  Jetzt nur noch PDFs nach ./dokumente legen - die Aufnahme laeuft von selbst."
  echo ""
else
  cat <<'ENDE'
  Die Ablaufplaene sind schon eingespielt und aktiv. Es bleiben nur noch
  diese Schritte (einmalig):

  1. Auf Port 3001 ein Konto anlegen, dann unter
     Einstellungen -> Werkzeuge -> API-Schluessel einen Schluessel erzeugen.

  2. Den Schluessel in .secrets.env bei KI4KI_API_KEY eintragen und einmal
     neu laden:   ./start.sh

  3. Einen Arbeitsbereich anlegen:   ./arbeitsbereich_anlegen.sh <Schluessel>
     Danach PDFs nach ./dokumente legen; die Aufnahme laeuft von selbst.

ENDE
fi
