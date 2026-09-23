#!/usr/bin/env python3
"""Pruefreihe: Nichtdokumente muessen aus dem Eingang verschwinden.

⛔ Gemessen 23.09. am laufenden System: Eine 'Thumbs.db' im Eingang wird
  bei JEDEM Durchgang erneut als "kein Dokument" uebersprungen - und
  bleibt liegen. Ueber zehn Durchgaenge hinweg: input 1, aussortiert 0.
  Sie blockiert nichts mehr, aber der Eingang wird nie leer. Bei 41 .db
  und 54 Office-Sperrdateien im KAP-Bestand heisst das: "Eingang leer"
  taugt nicht mehr als Zeichen, dass ein Lauf durch ist.

Aufruf:   python3 wegraeumtest.py      (Exit 0 = alle gruen)
"""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nichtdokumente_wegraeumen as w   # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def baum():
    """Ein Eingang wie auf dem Server - echte Dateien, kein Nachbau."""
    d = tempfile.mkdtemp(prefix="ki4ki-wegraeum-")
    for p in ("kap/input/_probe", "kap/input/Kunde/Auftrag", "kap/aussortiert",
              "auw/input"):
        os.makedirs(os.path.join(d, p))
    dateien = [
        "kap/input/_probe/Thumbs.db",            # muss weg
        "kap/input/_probe/probe-stoerrisch.db",  # muss BLEIBEN (kein Muster)
        "kap/input/Kunde/Auftrag/~$Angebot.docx",  # muss weg, tief
        "kap/input/Bericht.pdf",                 # muss bleiben
        "auw/input/._Notiz.pdf",                 # muss weg, anderer Bereich
    ]
    for f in dateien:
        io.open(os.path.join(d, f), "w").write("x")
    return d


def test_zielpfad():
    print("\nDas Ziel spiegelt den Unterordner")
    pruefe(w.ziel_fuer("/files/dokumente/kap/input/_probe/Thumbs.db")
           == "/files/dokumente/kap/aussortiert/_probe/Thumbs.db",
           "Unterordner bleibt erhalten")
    pruefe(w.ziel_fuer("/files/dokumente/kap/input/Thumbs.db")
           == "/files/dokumente/kap/aussortiert/Thumbs.db",
           "flach im Eingang geht auch")
    pruefe(w.ziel_fuer("/files/dokumente/kap/parkplatz/Thumbs.db") is None,
           "ausserhalb von input/ wird NICHTS angefasst - der Parkplatz "
           "ist Kundenbestand")


def test_trockenlauf_bewegt_nichts():
    print("\nDer Trockenlauf zaehlt nur")
    d = baum()
    try:
        e = w.wegraeumen(d, wirklich=False)
        pruefe(e["erkannt"] == 3, "drei Nichtdokumente erkannt (ist: %s)"
               % e["erkannt"])
        pruefe(e["verschoben"] == 0, "aber nichts bewegt")
        pruefe(os.path.exists(os.path.join(d, "kap/input/_probe/Thumbs.db")),
               "die Datei liegt noch da")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_wirklich_raeumt_auf():
    print("\nMit --wirklich wird geraeumt")
    d = baum()
    try:
        e = w.wegraeumen(d, wirklich=True, jetzt="2026-09-23 12:00:00")
        pruefe(e["verschoben"] == 3, "drei verschoben (ist: %s)"
               % e["verschoben"])
        weg = [("kap", "input/_probe/Thumbs.db", "aussortiert/_probe/Thumbs.db"),
               ("kap", "input/Kunde/Auftrag/~$Angebot.docx",
                "aussortiert/Kunde/Auftrag/~$Angebot.docx"),
               ("auw", "input/._Notiz.pdf", "aussortiert/._Notiz.pdf")]
        for bereich, alt, neu in weg:
            pruefe(not os.path.exists(os.path.join(d, bereich, alt)),
                   "weg aus dem Eingang: %s/%s" % (bereich, alt))
            pruefe(os.path.exists(os.path.join(d, bereich, neu)),
                   "angekommen: %s/%s" % (bereich, neu))
        # ⛔ Die Gegenprobe. Ohne sie beweist ein leerer Eingang nichts -
        #   er waere auch dann leer, wenn ALLES verschwaende.
        pruefe(os.path.exists(os.path.join(d, "kap/input/Bericht.pdf")),
               "Gegenprobe: das echte Dokument liegt unangetastet da")
        pruefe(os.path.exists(
            os.path.join(d, "kap/input/_probe/probe-stoerrisch.db")),
               "Gegenprobe: eine .db OHNE Muster bleibt auch liegen")
        log = os.path.join(d, "kap/aussortiert/aussortiert.log")
        pruefe(os.path.exists(log), "das Protokoll wurde geschrieben")
        if os.path.exists(log):
            t = io.open(log, encoding="utf-8").read()
            pruefe("Ordner-Merkdatei" in t,
                   "und nennt den Grund, nicht nur den Namen")
            pruefe("2026-09-23 12:00:00" in t, "mit Zeitstempel")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_zweimal_raeumen_schadet_nicht():
    print("\nZweimal laufen lassen tut nicht weh")
    d = baum()
    try:
        w.wegraeumen(d, wirklich=True)
        e = w.wegraeumen(d, wirklich=True)
        pruefe(e["erkannt"] == 0 and e["verschoben"] == 0,
               "beim zweiten Lauf gibt es nichts mehr zu tun")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_zielpfad()
    test_trockenlauf_bewegt_nichts()
    test_wirklich_raeumt_auf()
    test_zweimal_raeumen_schadet_nicht()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
