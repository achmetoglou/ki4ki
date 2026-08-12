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
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pillow==11.*

WORKDIR /app
COPY *.py /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 3001
CMD ["python3", "pruef_proxy.py", "--port", "3001"]
