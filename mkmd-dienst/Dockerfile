# ============================================================================
#  Markdown-Erzeugung als Dienst
#
#  Damit die Logik nur EINMAL existiert: Die Skript-Kette ruft
#  mk_md.baue_markdown() direkt auf, n8n ruft diesen Dienst. Vorher lag im
#  n8n-Ablauf eine eigene Nachbildung in JavaScript - sogar in zwei
#  Fassungen -, und keine kannte die Seitennummerierung oder den
#  Verzeichnisputz.
#
#  Braucht nichts ausser der Standardbibliothek. Kein veroeffentlichter
#  Anschluss: Der Dienst hoert nur im internen Netz.
# ============================================================================
FROM python:3.12-slim

WORKDIR /app
COPY *.py /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 5055
CMD ["python3", "mkmd_dienst.py"]
