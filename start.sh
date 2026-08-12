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
command -v docker >/dev/null || { echo "Docker fehlt. Bitte zuerst Docker installieren."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose (v2) fehlt."; exit 1; }
echo "  Docker $(docker --version | cut -d' ' -f3 | tr -d ,) · Compose $(docker compose version --short)"

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
else
  echo "  Keine nutzbare Karte gefunden - alles laeuft auf dem Prozessor."
  echo "  Das funktioniert, ist aber deutlich langsamer. Wer eine NVIDIA-Karte"
  echo "  hat, installiert das NVIDIA Container Toolkit und startet neu."
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

# --- Fertig ----------------------------------------------------------------
sagen "Fertig"
docker compose $DATEIEN ps --format "  {{.Name}}  {{.Status}}"

cat <<'ENDE'

  Oberflaeche:  http://<dieser-rechner>:3001
  Ablaufplaene: http://<dieser-rechner>:5678

  NOCH ZWEI SCHRITTE VON HAND (siehe LIESMICH.md, Abschnitt "Erster Start"):

  1. Auf Port 3001 ein Konto anlegen und unter
     Einstellungen -> Werkzeuge -> API-Schluessel einen Schluessel erzeugen.

  2. Dann hier:   ./arbeitsbereich_anlegen.sh <Schluessel>

     Das legt den Arbeitsbereich mit der richtigen Einstellung an.
     ⚠ Wer den Arbeitsbereich stattdessen von Hand anlegt, bekommt
     AnythingLLMs Voreinstellungen - und damit KEINE geprueften Quellen.
     Warum, steht in der LIESMICH.

ENDE
