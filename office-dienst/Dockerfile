# ============================================================================
#  Office-Dateien nach PDF (Phase 0 der Aufnahme)
#
#  Warum: Aus einer .pptx oder .docx holt Tika zwar den Text, aber es gibt
#  keine Seite zum Nachschlagen - keine Foliennummer, kein Klick ins
#  Original, keine gelbe Markierung. Wandelt man vorher nach PDF, laeuft die
#  normale Kette: Docling, Seitenmarken, Fundstelle. Eine Folie wird eine
#  Seite. So lief es schon auf dem Testserver (T4, Juli 2026).
#
#  Tabellen (Excel/CSV) NICHT: eine nach PDF gedruckte Tabelle verliert,
#  welche Spalte was bedeutet - die bleiben Tabellen (Pruefungskataloge!).
#
#  Bewusst schlank: Writer + Impress, keine Oberflaeche, keine Grafikkarte.
#  Kein veroeffentlichter Anschluss: Der Dienst hoert nur im Docker-Netz.
# ============================================================================
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-impress \
      fonts-dejavu fonts-liberation python3 \
 && rm -rf /var/lib/apt/lists/*

# Ohne eigenes Zuhause legt LibreOffice sein Profil irgendwo an und scheitert
ENV HOME=/tmp PYTHONUNBUFFERED=1
WORKDIR /app
COPY office_dienst.py /app/
EXPOSE 5060
CMD ["python3", "office_dienst.py"]
