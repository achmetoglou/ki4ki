#!/usr/bin/env python3
"""Pruefreihe fuer die Fusszeile unter einer Antwort.

⛔ Meldung vom 15.09.2026, woertlich: "steht fast bei jedem Output zwei
  mal die Modellangabe und die Dokumente die gesucht wurden". Die
  Modellzeile ist am 22.09. entfernt worden, die doppelte Dokumentnennung
  blieb. Gemessen 23.09.:

    durchsucht: Pruefungsfragen zu DVS 2291 ... · zusammengefasst ·
    vollstaendig gelesen: Pruefungsfragen zu DVS 2291 ... (ganzer Text)

  Derselbe Titel zweimal in einer Zeile.

⭐ Was NICHT verschwinden darf: der Unterschied zwischen "Quelle:"
  (wirklich belegt) und "durchsucht:" (gesucht, nichts belegt), die
  geprueften Zitate und die Warnungen. Die stehen nirgendwo sonst - die
  Quellenliste von AnythingLLM kennt kein "2 Aussagen nicht belegt".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fusszeile      # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def titel(d):
    return {"k1": "Pruefungsfragen zu DVS 2291", "k2": "DVS 2213 Lehrgangshandbuch",
            "k3": "LE Kontrolle der Laminierplaene"}.get(d, d)


def test_gelesenes_wird_nicht_nochmal_genannt():
    print("\nEin vollstaendig gelesenes Dokument steht nur einmal da")
    raus = fusszeile.dokumente_fuer_zeile(
        ["k1"], {"Pruefungsfragen zu DVS 2291"}, titel)
    pruefe(raus == [],
           "das einzige Dokument wurde gelesen -> die Suchzeile entfaellt "
           "(ist: %r)" % raus)


def test_nur_das_doppelte_faellt_weg():
    print("\nDie anderen bleiben stehen")
    raus = fusszeile.dokumente_fuer_zeile(
        ["k1", "k2", "k3"], {"Pruefungsfragen zu DVS 2291"}, titel)
    pruefe(raus == ["DVS 2213 Lehrgangshandbuch",
                    "LE Kontrolle der Laminierplaene"],
           "nur der gelesene faellt weg, die gesuchten bleiben (ist: %r)"
           % raus)


def test_ohne_gelesenes_aendert_sich_nichts():
    print("\nGegenprobe: ohne gelesene Dokumente bleibt alles")
    raus = fusszeile.dokumente_fuer_zeile(["k1", "k2"], set(), titel)
    pruefe(raus == ["Pruefungsfragen zu DVS 2291", "DVS 2213 Lehrgangshandbuch"],
           "beide bleiben stehen (ist: %r)" % raus)
    pruefe(fusszeile.dokumente_fuer_zeile([], {"x"}, titel) == [],
           "leere Liste macht keinen Aerger")


if __name__ == "__main__":
    test_gelesenes_wird_nicht_nochmal_genannt()
    test_nur_das_doppelte_faellt_weg()
    test_ohne_gelesenes_aendert_sich_nichts()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
