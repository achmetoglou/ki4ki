#!/usr/bin/env python3
"""Kleiner Dienst, der die Markdown-Erzeugung anbietet.

Warum es ihn gibt: Der n8n-Ablauf baute die Markdown-Datei mit eigenem
JavaScript nach - sogar in zwei Fassungen im selben Workflow ("Markdown
erzeugen" und "Markdown erzeugen-fix"). Keine davon kannte die
spaeteren Verbesserungen: durchnummerierte Seitenmarken,
Verzeichnisputz, Behandlung einseitiger Dokumente.

Zwei Nachbildungen derselben Sache driften auseinander. In einem frueheren Fall entstanden
schon 325 Zeilen Unterschied und 15 fehlende Funktionen.
Deshalb ruft n8n jetzt dieselbe Fassung auf, die auch die
Skript-Kette benutzt: mk_md.baue_markdown().

Schnittstelle
-------------
POST /markdown
    {"rohtext": "...", "tagging": {...}, "basisname": "BS-00-000"}
    -> {"markdown": "...", "zeichen": 22365, "seiten": 97}

    "tagging" darf fehlen oder leer sein - dann entsteht die Datei ohne
    Schlagwortabschnitte, genau wie bei einer fehlgeschlagenen
    Verschlagwortung in der Skript-Kette.

GET /health
    -> {"status": "ok"}

Bewusst ohne Zugangsschutz: Der Dienst hoert nur im Docker-Netz, gibt
nichts aus dem Bestand heraus und veraendert nichts. Er formt Text um.
"""
import json
import os
import sys
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_md  # noqa: E402
import pdfstelle  # noqa: E402
import seiten_echt  # noqa: E402

PORT = int(os.environ.get("KI4KI_MKMD_PORT") or 5055)
DOCLING = os.environ.get("KI4KI_DOCLING") or "http://docling:5001"
# Mehr als das nimmt kein Dokument ein; schuetzt vor versehentlichen
# Riesen-Anfragen.
HOECHSTENS = 40 * 1024 * 1024


def _leichter_docling(pdf_bytes, dateiname):
    """Leichter Docling-Aufruf nur fuers JSON (OHNE Bildbeschreibung).

    Liefert json_content (dict) mit den echten Seiten je Textblock, oder
    None. Ohne Bildbeschreibung dauert das Sekunden statt Minuten - und die
    SEITENSTRUKTUR ist dieselbe wie beim schweren Lauf (gemessen:
    gleiche [[SEITE]]-Zahl mit und ohne Beschreibung).
    """
    grenze = "----ki4kiSeitenGrenze"

    def feld(name, wert):
        return ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n"
                "%s\r\n" % (grenze, name, wert)).encode()

    teile = [feld(k, v) for k, v in (
        ("to_formats", "json"), ("do_table_structure", "true"),
        ("table_mode", "accurate"), ("md_page_break_placeholder", "[[SEITE]]"),
        ("do_picture_description", "false"),
        ("do_picture_classification", "false"))]
    teile.append(("--%s\r\nContent-Disposition: form-data; name=\"files\"; "
                  "filename=\"%s\"\r\nContent-Type: application/pdf\r\n\r\n"
                  % (grenze, dateiname)).encode())
    teile.append(pdf_bytes)
    teile.append(("\r\n--%s--\r\n" % grenze).encode())
    req = urllib.request.Request(DOCLING + "/v1/convert/file",
                                 data=b"".join(teile), method="POST")
    req.add_header("Content-Type",
                   "multipart/form-data; boundary=%s" % grenze)
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.load(r)
    doc = d.get("document") or d
    inh = doc.get("json_content") or {}
    if isinstance(inh, str):
        inh = json.loads(inh)
    return inh or None


def echte_seiten(rohtext, basisname):
    """bare [[SEITE]] -> [[SEITE:N]] ueber einen leichten Docling-Aufruf.

    Der Batch-Weg schreibt die echten Seiten schon in bildbeschreibung.py;
    der n8n-Weg liefert hier bare [[SEITE]]. Statt die Logik ein zweites
    Mal (in n8n-JavaScript) nachzubauen, holt der Dienst kurz das JSON mit
    den echten Seiten und laesst dieselbe Fassung wie der Batch-Weg laufen
    (seiten_echt.py). Docling setzt zu WENIGE Trenner - das blosse
    Durchzaehlen in mk_md lief darum mit dem Dokument immer weiter daneben.

    ⚠ Bei JEDEM Fehler (kein PDF gefunden, Docling nicht erreichbar, ...)
    bleibt rohtext unveraendert - dann zaehlt mk_md sequenziell wie bisher,
    also KEIN Rueckschritt gegenueber dem Stand vor diesem Fix.
    """
    if "[[SEITE:" in rohtext or "[[SEITE]]" not in rohtext:
        return rohtext
    try:
        pfad = pdfstelle.pdf_pfad(basisname)
        if not pfad:
            print("[mkmd] kein PDF zu %r gefunden - Seiten sequenziell"
                  % basisname, file=sys.stderr, flush=True)
            return rohtext
        with open(pfad, "rb") as f:
            roh = f.read()
        inhalt = _leichter_docling(roh, os.path.basename(pfad))
        if not inhalt:
            return rohtext
        neu, _ = seiten_echt.nummeriere(rohtext, inhalt)
        print("[mkmd] echte Seiten fuer %s eingesetzt (%d Trenner)"
              % (basisname, rohtext.count("[[SEITE]]")),
              file=sys.stderr, flush=True)
        return neu
    except Exception as e:
        print("[mkmd] echte Seiten uebersprungen (%s): %s"
              % (basisname, str(e)[:150]), file=sys.stderr, flush=True)
        return rohtext


class Griff(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _antwort(self, code, daten):
        roh = json.dumps(daten, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", ""):
            self._antwort(200, {"status": "ok"})
            return
        self._antwort(404, {"fehler": "unbekannter Pfad"})

    def do_POST(self):
        if self.path.rstrip("/") != "/markdown":
            self._antwort(404, {"fehler": "unbekannter Pfad"})
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n > HOECHSTENS:
            self._antwort(413, {"fehler": "Anfrage zu gross"})
            return
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._antwort(400, {"fehler": "kein gueltiges JSON: %s" % e})
            return

        rohtext = d.get("rohtext") or ""
        basisname = (d.get("basisname") or "").strip()
        tagging = d.get("tagging")
        if isinstance(tagging, str):
            # n8n schickt verschachteltes JSON gern als Zeichenkette
            try:
                tagging = json.loads(tagging)
            except Exception:
                tagging = {}
        if not rohtext.strip():
            self._antwort(400, {"fehler": "rohtext fehlt oder ist leer"})
            return
        if not basisname:
            self._antwort(400, {"fehler": "basisname fehlt"})
            return

        # n8n-Weg: echte Seiten nachziehen (Batch-Weg hat sie schon).
        rohtext = echte_seiten(rohtext, basisname)
        try:
            text, inhalt, tags = mk_md.baue_markdown(rohtext, tagging,
                                                    basisname)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self._antwort(500, {"fehler": str(e)[:300]})
            return

        def lst(key):
            v = (tags or {}).get(key)
            return [str(i) for i in v] if isinstance(v, list) else []

        print("[mkmd] %s: %d Zeichen, %d Seiten, %d Tags"
              % (basisname, len(inhalt), inhalt.count("[Seite "),
                 len(lst("tags"))), file=sys.stderr, flush=True)
        self._antwort(200, {
            "markdown": text,
            "dateiname": basisname + ".md",
            "zeichen": len(inhalt),
            "seiten": inhalt.count("[Seite "),
            "tags": lst("tags"),
            "keywords": lst("keywords"),
            "methoden": lst("methods"),
        })

    def log_message(self, *a):
        pass


def main():
    print("[mkmd] hoert auf Port %d" % PORT, file=sys.stderr, flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Griff).serve_forever()


if __name__ == "__main__":
    main()
