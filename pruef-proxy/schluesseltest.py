"""Pruefungen fuer das Schluesselmodul.

Laeuft ohne Testrahmen: python3 schluesseltest.py
Rueckgabewert 0, wenn alles gruen ist, sonst 1.

Grundsatz dieser Datei: Zu jeder Pruefung gehoert der Nachweis, mit WELCHER
Eingabe sie rot wird. Eine Pruefung, die per Konstruktion immer gruen ist,
beweist nichts - in vier Planfassungen standen vier solche Pruefungen.
"""
import sys

import schluessel

FEHLER = []

# Absichtlich hier NOCHMAL definiert und nicht aus dem Modul geholt: sonst
# pruefte der Test gegen die eigene Konstante und koennte nicht rot werden.
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def test_kennpfad():
    print("Kennpfad - Bereich explizit, die Stufe faellt raus")
    k, kb = schluessel.kennpfad, schluessel.kennpfad_aus_bestandspfad
    pruefe(k("kap", "archiv/KundeA/Angebot.pdf") == "kap/KundeA/Angebot.pdf",
           "archiv faellt raus")
    pruefe(k("kap", "parkplatz/KundeA/A.pdf") == k("kap", "archiv/KundeA/A.pdf"),
           "parkplatz und archiv ergeben denselben Kennpfad")
    pruefe(k("kap", "KundeA/A.pdf") == k("kap", "archiv/KundeA/A.pdf"),
           "mit und ohne Stufe ergeben denselben Kennpfad")
    pruefe(k("kap", "archiv/KundeA/A.pdf") != k("auw", "archiv/KundeA/A.pdf"),
           "zwei Bereiche bleiben getrennt")
    pruefe(k("kap", "archiv/archiv/x.pdf") == "kap/archiv/x.pdf",
           "nur die ERSTE Stufe faellt raus, ein Unterordner 'archiv' bleibt")
    # Der gefaehrlichste Fall: falscher Bezugspunkt. MUSS abbrechen, nicht raten.
    for schlecht in (("", "archiv/x.pdf"), ("kap", ""), ("kap", "archiv/")):
        try:
            k(*schlecht)
            pruefe(False, "haette abbrechen muessen: %r" % (schlecht,))
        except ValueError:
            pruefe(True, "bricht ab statt zu raten: %r" % (schlecht,))
    pruefe(kb("kap/archiv/KundeA/A.pdf") == "kap/KundeA/A.pdf",
           "Bestandspfad-Hilfe zerlegt <bereich>/<stufe>/<rest>")
    # Die Hintertuer: ein bereichsrelativer Pfad darf NICHT durchrutschen.
    # Genau hier wuerde sonst still der "Bereich archiv" entstehen - und diese
    # Funktion ist die, die die Messung am Bestand benutzt.
    for schlecht in ("archiv/KundeA/A.pdf", "parkplatz/x.pdf", "input/KundeA/A.pdf"):
        try:
            erg = kb(schlecht)
            pruefe(False, "haette abbrechen muessen, lieferte %r fuer %r"
                   % (erg, schlecht))
        except ValueError:
            pruefe(True, "Stufenname als Bereich wird abgewiesen: %r" % schlecht)


def test_fingerabdruck():
    print("\nFingerabdruck")
    a = schluessel.fingerabdruck("kap/KundeA/Angebot.pdf")
    pruefe(len(a) == 10, "genau 10 Zeichen, ist %d" % len(a))
    pruefe(all(c in ALPHABET for c in a), "nur a-z0-9: %r" % a)
    pruefe(a == schluessel.fingerabdruck("kap/KundeA/Angebot.pdf"), "stabil")
    pruefe(a != schluessel.fingerabdruck("kap/KundeB/Angebot.pdf"),
           "zwei Kunden, gleicher Dateiname: zwei Abdruecke")
    pruefe(schluessel.fingerabdruck("Kunde/Angebot 2024/x.pdf")
           != schluessel.fingerabdruck("Kunde/Angebot/2024 x.pdf"),
           "Trennzeichen-Falle bleibt unterscheidbar")


if __name__ == "__main__":
    test_kennpfad()
    test_fingerabdruck()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
