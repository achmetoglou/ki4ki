#!/usr/bin/env python3
"""Prueft den /schluessel-Endpunkt gegen einen laufenden mkmd-Dienst.

  KI4KI_MKMD=http://localhost:5055 python3 mkmd-dienst/schluesseldienst_test.py

Auf der Anlage:
  docker exec ki4ki-mkmd python3 /app/schluesseldienst_test.py

Ohne erreichbaren Dienst: Rueckgabe 1 mit klarer Meldung - NICHT gruen.
Ein uebersprungener Lauf sieht beim Ueberfliegen aus wie ein bestandener.
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import schluessel   # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def hole(dateien):
    ziel = (os.environ.get("KI4KI_MKMD") or "http://mkmd-dienst:5055") + "/schluessel"
    roh = json.dumps({"dateien": dateien}).encode()
    req = urllib.request.Request(ziel, data=roh, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    faelle = [{"bereich": "kap", "unterpfad": "input/KundeA/Angebot.pdf"},
              {"bereich": "kap", "unterpfad": "archiv/KundeA/Angebot.pdf"},
              {"bereich": "kap", "unterpfad": "input/KundeB/Angebot.pdf"},
              {"bereich": "auw", "unterpfad": "input/KundeA/Angebot.pdf"}]
    try:
        antwort = hole(faelle)
    except Exception as e:
        print("  FEHL Dienst nicht erreichbar (%s: %s)"
              % (e.__class__.__name__, str(e)[:100]))
        print("\nDER LAUF IST NICHT GUELTIG - es wurde nichts geprueft.")
        return 1

    s = {(e["bereich"], e["unterpfad"]): e for e in antwort.get("schluessel", [])}
    pruefe(len(s) == 4, "vier Antworten, sind %d" % len(s))
    if len(s) != 4:
        print("\nDER LAUF IST NICHT GUELTIG - der Dienst antwortet unvollstaendig.")
        return 1

    a = s[("kap", "input/KundeA/Angebot.pdf")]
    b = s[("kap", "archiv/KundeA/Angebot.pdf")]
    pruefe(a["schluessel"] == b["schluessel"],
           "Umzug input->archiv aendert den Schluessel nicht")
    pruefe(a["abdruck"] != s[("kap", "input/KundeB/Angebot.pdf")]["abdruck"],
           "zwei Kunden, gleicher Dateiname: zwei Abdruecke")
    pruefe(a["abdruck"] != s[("auw", "input/KundeA/Angebot.pdf")]["abdruck"],
           "zwei Bereiche bleiben getrennt")

    # ⭐ Die Zusicherung, die den ganzen Umbau traegt: Der Dienst rechnet
    #   GENAU dasselbe wie das Modul im Proxy. Waeren beide verschieden,
    #   vergaebe die Aufnahme Schluessel, die die Auswertung nicht kennt -
    #   und kein Dokument waere wiederzufinden.
    eigen = schluessel.schluessel("kap", "input/KundeA/Angebot.pdf")
    eigen_a = schluessel.fingerabdruck(
        schluessel.kennpfad("kap", "input/KundeA/Angebot.pdf"))
    pruefe(a["schluessel"] == eigen,
           "Dienst und Modul liefern denselben Schluessel (%r / %r)"
           % (a["schluessel"], eigen))
    pruefe(a["abdruck"] == eigen_a,
           "Dienst und Modul liefern denselben Abdruck (%r / %r)"
           % (a["abdruck"], eigen_a))

    # ⛔ Gegenprobe: Ein Pfad ohne Bereich muss als FEHLER zurueckkommen,
    #   nicht als plausibler Schluessel. Ohne diese Zeile waere alles oben
    #   auch dann gruen, wenn der Dienst den Bereich einfach raet - und ein
    #   bereichsrelativer Pfad wuerde still zum "Bereich archiv".
    kaputt = hole([{"bereich": "", "unterpfad": "archiv/x.pdf"},
                   {"bereich": "archiv", "unterpfad": "KundeA/x.pdf"}])
    pruefe(len(kaputt.get("fehler", [])) == 2 and not kaputt.get("schluessel"),
           "fehlender und geratener Bereich werden abgewiesen, nicht geraten "
           "(Fehler: %d, Schluessel: %d)"
           % (len(kaputt.get("fehler", [])), len(kaputt.get("schluessel", []))))

    # Und die Gegenprobe dazu: Eine leere Liste ist kein Fehler.
    leer = hole([])
    pruefe(leer.get("schluessel") == [] and leer.get("fehler") == [],
           "leerer Auftrag ergibt eine leere Antwort, keinen Fehler")

    print("\n%d Fehler" % len(FEHLER))
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
