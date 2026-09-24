#!/usr/bin/env python3
"""Was der Verzeichnisputz loeschen darf - und was auf keinen Fall.

⛔ GEMESSEN 25.09.: Die Regel loeschte FUENF von FUENF Positionszeilen
   eines Angebots. Sie traf "Punktfuehrung, dann irgendwo eine Zahl" - und
   das ist die Satzform jeder Rechnungsposition. Geloescht wurde VOR dem
   Einbetten: Die Position war danach weder auffindbar noch belegbar, und
   niemand erfuhr davon. Fuer den Hochschulbestand, fuer den die Regel
   gebaut wurde, war sie richtig.

⭐ Diese Datei ist die erste Pruefung des mkmd-Dienstes ueberhaupt. Sie
   prueft BEIDE Welten gegeneinander: Eine Aenderung, die Verzeichnisse
   besser trifft, aber Belegzeilen mitnimmt, wird hier rot - und umgekehrt.

  python3 vorspanntest.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vorspann_finden import navigationszeile, putze   # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


# (Zeile, soll geloescht werden)
FAELLE = [
    # --- Hochschulbestand: muss weiter greifen ---
    ("Inhaltsverzeichnis", True),
    ("Abbildungsverzeichnis", True),
    ("## Tabellenverzeichnis", True),
    ("1 Einleitung .................... 3", True),
    ("Abbildung 2.1: Aufbau des Pruefstands ......... 12", True),
    ("| 2.3 Versuchsaufbau ..... | 41 |", True),
    ("4.1.2 Ergebnisse der Zugpruefung ............ 137", True),
    # --- Geschaeftsunterlagen: darf NIE geloescht werden ---
    ("Laborleistung gem. Angebot 274821 ....... 1.234,56", False),
    ("Pos. 1  Vorarbeit Werkstoffkreislauf .......... 6.000,00", False),
    ("| Reisekosten | ...... | 412,80 |", False),
    ("Zwischensumme ............................ 5.890,00", False),
    ("Nettobetrag .................. 5.890,00 EUR", False),
    ("Gesamtsumme ......... 12 EUR", False),
    ("Anfahrt Autoverwertungshof ....... 89,50 €", False),
    # --- Fliesstext bleibt immer ---
    ("Die Probe wurde bei 23 Grad gelagert.", False),
    ("Siehe dazu Kapitel 3.", False),
]


def zeilen_einzeln():
    print("\n[1] Jede Zeile einzeln")
    for zeile, soll in FAELLE:
        ist = navigationszeile(zeile)
        pruefe(ist == soll, "%-9s %s" % ("loeschen" if soll else "behalten",
                                         zeile[:56]))


def ganzer_text():
    """⛔ Einzelzeilen genuegen nicht: putze() hat ein eigenes Sicherheitsnetz
    und koennte alles durchlassen oder alles verwerfen."""
    print("\n[2] Am ganzen Text, wie im Betrieb")
    text = "\n".join(z for z, _ in FAELLE)
    aus, weg = putze(text)
    behalten = [z for z, soll in FAELLE if not soll]
    fehlend = [z for z in behalten if z not in aus]
    pruefe(not fehlend,
           "keine Belegzeile verloren (%d fehlen)" % len(fehlend))
    geblieben = [z for z, soll in FAELLE if soll and z in aus]
    pruefe(not geblieben,
           "keine Verzeichniszeile uebrig (%d geblieben)" % len(geblieben))
    pruefe(weg > 0, "es wurde ueberhaupt etwas entfernt (%d Zeichen)" % weg)


def gegenprobe():
    """⛔ Ohne sie sagen die Zahlen oben nichts: Eine Pruefung, die nur
    "0 Fehler" meldet, waere auch dann gruen, wenn navigationszeile()
    schlicht immer False liefert."""
    print("\n[3] Gegenprobe - womit wird diese Reihe rot?")
    pruefe(any(navigationszeile(z) for z, soll in FAELLE if soll),
           "die Regel loescht ueberhaupt etwas (sonst waere alles gruen)")
    pruefe(not all(navigationszeile(z) for z, _ in FAELLE),
           "sie loescht nicht alles (sonst waere auch alles gruen)")
    # Die alte, kaputte Fassung MUSS an dieser Reihe scheitern.
    import re
    alt = re.compile(r"\.{4,}\s*\|?\s*\d{1,4}\b")
    getroffen = [z for z, soll in FAELLE if not soll and alt.search(z)]
    pruefe(len(getroffen) >= 4,
           "die ALTE Fassung haette %d Belegzeilen geloescht - die Reihe "
           "haette sie erwischt" % len(getroffen))


if __name__ == "__main__":
    zeilen_einzeln()
    ganzer_text()
    gegenprobe()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
