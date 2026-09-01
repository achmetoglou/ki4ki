# ============================================================================
#  Belegpruefung vor AnythingLLM
#
#  Jede Antwort wird gegen die Originalarbeiten geprueft, bevor sie im Chat
#  erscheint. Gebraucht werden nur zwei Dinge, die im schlanken Python-Abbild
#  fehlen:
#    poppler-utils  - um im Original-PDF nachzuschlagen
#    pillow         - um die belegte Stelle auf der Seite gelb zu hinterlegen
#
#  Im Partner-Paket liegt der Programmcode IM Abbild (anders als auf dem
#  Testserver, wo er eingehaengt wird): der Partner soll nichts nachziehen
#  muessen, was er nicht angefasst hat.
# ============================================================================
FROM python:3.12-slim@sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc

RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils tzdata \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pillow==11.*

WORKDIR /app
COPY *.py /app/
# Die Wortlisten MIT ins Abbild: Ohne diese Zeile fehlte die Datei im
# Container, und es galten stillschweigend die eingebauten Vorgaben -
# die "ohne Neustart pflegbar"-Schiene war damit tot. Das Compose haengt
# zusaetzlich die Host-Datei darueber (live aenderbar); diese Kopie ist
# der Rueckfall, falls der Mount fehlt.
COPY wortlisten.txt /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 3001
CMD ["python3", "pruef_proxy.py", "--port", "3001"]
