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
  echo ""
  echo "  NOCH ZU TUN, sonst nimmt die Anlage keine Dokumente auf:"
  echo "  In AnythingLLM unter Einstellungen > API-Schluessel einen Schluessel"
  echo "  anlegen und in .secrets.env bei KI4KI_API_KEY eintragen."
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
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
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

# --- Bauen und starten -----------------------------------------------------
sagen "Belegpruefung bauen"
docker compose $DATEIEN build pruef-proxy

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
  docker exec ki4ki-n8n n8n update:workflow --id=1DKWgDbdCiwa25E1 --active=true >/dev/null 2>&1 \
    && echo "  Masse-Ingest aktiviert"
  docker restart ki4ki-n8n >/dev/null 2>&1   # damit der Zeitplan-Ausloeser registriert
else
  echo "  ⚠ Auto-Import nicht moeglich - Workflows bitte per n8n-Oberflaeche"
  echo "    (Port 5678, Import from File) aus n8n-workflows/ laden."
fi
set -e

# --- Fertig ----------------------------------------------------------------
sagen "Fertig"
docker compose $DATEIEN ps --format "  {{.Name}}  {{.Status}}"

cat <<'ENDE'

  Oberflaeche:  http://<dieser-rechner>:3001
  Ablaufplaene: http://<dieser-rechner>:5678

  Die Ablaufplaene sind schon eingespielt und aktiv. Es bleiben nur noch
  diese Schritte (einmalig, aus Sicherheitsgruenden nicht automatisierbar):

  1. Auf Port 3001 ein Konto anlegen, dann unter
     Einstellungen -> Werkzeuge -> API-Schluessel einen Schluessel erzeugen.

  2. Den Schluessel in .secrets.env bei KI4KI_API_KEY eintragen und einmal
     neu laden:   ./start.sh
     (Ohne den Schluessel nimmt die Aufnahme keine Dokumente an.)

  3. Einen Arbeitsbereich anlegen:   ./arbeitsbereich_anlegen.sh <Schluessel>
     Oder per Oberflaeche - neue Bereiche stellen sich automatisch richtig ein.
     Danach PDFs nach ./dokumente legen; die Aufnahme laeuft von selbst.

ENDE
