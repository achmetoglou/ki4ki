#!/usr/bin/env python3
"""Office nach PDF - als Dienst fuer die n8n-Aufnahme.

POST /pdf   Rohdaten der Datei im Koerper
            X-Dateiname: folien.pptx        (Pflicht - bestimmt den Umwandler)
            X-Ziel: /files/dokumente/<bereich>/archiv/folien.pdf   (optional)
            -> application/pdf (die gewandelte Datei)
            Mit X-Ziel wird die PDF zusaetzlich dorthin geschrieben - neben
            das Original im Archiv, damit Fundstellen-Links, Seitenbilder
            und die gelbe Markierung im Original funktionieren.
GET  /health -> {"status": "ok"}

Nur Text- und Foliendokumente (doc, docx, odt, rtf, ppt, pptx, odp).
Tabellen bleiben Tabellen - siehe Dockerfile.
"""
import json
from urllib.parse import unquote
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("KI4KI_OFFICE_PORT") or 5060)
WURZEL = os.environ.get("KI4KI_OFFICE_WURZEL") or "/files/dokumente"
GID = int(os.environ.get("KI4KI_GID") or 1000)
WANDELBAR = (".doc", ".docx", ".odt", ".rtf", ".ppt", ".pptx", ".odp")
HOECHSTENS = 200 * 1024 * 1024
ZEITLIMIT = int(os.environ.get("KI4KI_OFFICE_ZEITLIMIT") or 900)


def wandeln(daten, dateiname):
    """(pdf_bytes, fehler). soffice arbeitet in einem eigenen Ordner mit
    eigenem Profil, damit zwei gleichzeitige Aufrufe sich nicht stoeren."""
    name = os.path.basename(dateiname or "").strip() or "dokument"
    stamm, endung = os.path.splitext(name)
    if endung.lower() not in WANDELBAR:
        return None, "Dateiart %s wird nicht gewandelt" % (endung or "?")
    arbeit = tempfile.mkdtemp(prefix="office-")
    try:
        quelle = os.path.join(arbeit, "quelle" + endung.lower())
        with open(quelle, "wb") as fh:
            fh.write(daten)
        profil = os.path.join(arbeit, "profil")
        r = subprocess.run(
            ["soffice", "--headless", "--norestore", "--nologo",
             "-env:UserInstallation=file://" + profil,
             "--convert-to", "pdf", "--outdir", arbeit, quelle],
            capture_output=True, text=True, timeout=ZEITLIMIT)
        ziel = os.path.join(arbeit, "quelle.pdf")
        if os.path.exists(ziel) and os.path.getsize(ziel) > 500:
            with open(ziel, "rb") as fh:
                return fh.read(), None
        return None, ((r.stderr or r.stdout or "keine Ausgabe").strip())[:300]
    except subprocess.TimeoutExpired:
        return None, "Zeitlimit (%d s) ueberschritten" % ZEITLIMIT
    except Exception as e:
        return None, str(e)[:300]
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)


def ablegen(pdf, ziel):
    """Die PDF ins Archiv schreiben - nur unter der Wurzel, nur .pdf, nie
    ueber einen Pfad-Trick hinaus. Rechte wie die anderen Dateien (664,
    1000:GID), damit Aufnahme und Loesch-Wache sie behandeln koennen."""
    if not ziel:
        return ""
    voll = os.path.realpath(ziel)
    if not voll.startswith(os.path.realpath(WURZEL) + os.sep) or not voll.lower().endswith(".pdf"):
        return "Ziel ausserhalb von %s oder keine .pdf" % WURZEL
    try:
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        tmp = voll + ".teil"
        with open(tmp, "wb") as fh:
            fh.write(pdf)
        os.replace(tmp, voll)
        try:
            os.chown(voll, 1000, GID)
            os.chmod(voll, 0o664)
        except Exception:
            pass
        return ""
    except Exception as e:
        return "Ablage fehlgeschlagen: %s" % str(e)[:200]


class Griff(BaseHTTPRequestHandler):
    def _json(self, code, daten):
        roh = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"status": "ok"})
        self._json(404, {"error": "unbekannt"})

    def do_POST(self):
        if not self.path.startswith("/pdf"):
            return self._json(404, {"error": "unbekannt"})
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            laenge = 0
        if laenge <= 0 or laenge > HOECHSTENS:
            return self._json(400, {"error": "Koerper fehlt oder ist groesser als %d MB" % (HOECHSTENS // 1048576)})
        daten = self.rfile.read(laenge)
        dateiname = unquote(self.headers.get("X-Dateiname") or "")   # n8n schickt URL-kodiert (Gedankenstrich, Euro ...)
        try:
            dateiname = bytes(dateiname, "latin-1").decode("utf-8")
        except Exception:
            pass
        ziel = unquote(self.headers.get("X-Ziel") or "")
        try:
            ziel = bytes(ziel, "latin-1").decode("utf-8")
        except Exception:
            pass
        pdf, fehler = wandeln(daten, dateiname)
        if not pdf:
            print("[Office] %s: FEHLER %s" % (dateiname, fehler), file=sys.stderr, flush=True)
            return self._json(422, {"error": fehler, "dateiname": dateiname})
        ablage = ablegen(pdf, ziel)
        print("[Office] %s -> PDF (%d KB)%s" % (dateiname, len(pdf) // 1024,
              (" | Ablage: " + ablage) if ablage else (" | abgelegt: " + ziel if ziel else "")),
              file=sys.stderr, flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("X-Ablage", ablage or "ok")
        self.end_headers()
        self.wfile.write(pdf)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("Office-Dienst auf :%d (Wurzel %s)" % (PORT, WURZEL), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Griff).serve_forever()
