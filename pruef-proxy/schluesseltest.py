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


def test_schluessel():
    print("\nSchluessel")
    S, K, F = schluessel.schluessel, schluessel.kennpfad, schluessel.fingerabdruck
    s = S("kap", "archiv/kunde/angebot/bericht.pdf")
    pruefe(s.count(".pdf") == 1, "Endung steht genau einmal drin: %r" % s)
    pruefe(len(s.encode("utf-8")) <= 200,
           "hoechstens 200 Byte, ist %d" % len(s.encode("utf-8")))
    pruefe(all(ord(c) < 128 for c in s), "reines ASCII")
    pruefe(F(K("kap", "archiv/kunde/angebot/bericht.pdf")) in s, "Abdruck steckt drin")
    # Der Umzug - das Kernstueck des Vertrags
    pruefe(S("kap", "parkplatz/KundeA/A.pdf") == S("kap", "archiv/KundeA/A.pdf"),
           "parkplatz und archiv ergeben EINEN Schluessel")
    pruefe(S("kap", "archiv/KundeA/A.pdf") != S("auw", "archiv/KundeA/A.pdf"),
           "zwei Bereiche ergeben ZWEI Schluessel")
    # Punktnamen, die keine Endung sind (in Kundenordnern die Regel)
    for name, erwartet in (("Angebot Nr. 4711", ""), ("Pruefbericht v1.2 final", ""),
                           ("2024.09.20 Protokoll", ""), ("Bericht.pdf", ".pdf"),
                           ("Tabelle.XLSX", ".xlsx")):
        sn = S("kap", "archiv/" + name)
        endet = sn[sn.rindex("--") + 12:]
        pruefe(endet == erwartet,
               "Endung von %r ist %r (erwartet %r)" % (name, endet, erwartet))
    # Ueberlaenge
    lang = "archiv/" + "/".join("o" * 40 for _ in range(8)) + "/datei.pdf"
    sl = S("kap", lang)
    pruefe(len(sl.encode("utf-8")) <= 200,
           "acht tiefe Ebenen unter 200 Byte, ist %d" % len(sl.encode("utf-8")))
    pruefe(F(K("kap", lang)) in sl, "Abdruck ueberlebt die Kuerzung")
    # Lange Punkt-Kette darf die Zusicherung nicht sprengen.
    # ACHTUNG: Die naechsten zwei Pruefungen allein reichen NICHT. Gegenprobe
    # am 21.09.: Entfernt man das max(0, ...) in schluessel(), bleiben sie
    # gruen - weil die Endungsregel den Fall schon ausschliesst. Rot wird erst
    # die dritte, und sie bewacht genau die Bedingung, von der die anderen
    # beiden still abhaengen.
    kette = "archiv/datei." + "x" * 200
    sx = S("kap", kette)
    pruefe(len(sx.encode("utf-8")) <= 200,
           "lange Punkt-Kette bleibt unter 200, ist %d" % len(sx.encode("utf-8")))
    pruefe(sx.split("--")[0] != "", "lesbarer Teil ist nicht leer")
    pruefe(len(schluessel._endung_von(K("kap", kette)).encode("utf-8")) <= 9,
           "eine 200-Zeichen-Punkt-Kette gilt NICHT als Endung - sonst wird der "
           "Platz fuer den lesbaren Teil negativ und die 200 Byte fallen")
    # Die Wort-Ersetzungen aus der Messung
    for z in ("&", "%", "€", "ü"):
        p = "archiv/Bericht %s Anlage/x.pdf" % z
        sp = S("kap", p)
        pruefe(F(K("kap", p)) in sp, "Abdruck unversehrt bei %r" % z)
        pruefe(all(ord(ch) < 128 for ch in sp), "Ergebnis bleibt ASCII bei %r" % z)
    # Nicht-lateinische Namen: Identitaet heil, aber der lesbare Teil ist weg.
    # NICHT "... or sc.startswith('kap')" schreiben - das ist immer wahr, weil
    # der lesbare Teil stets mit dem Bereichsnamen beginnt. Genau festschreiben,
    # was herauskommt, sonst kann die Pruefung nicht rot werden.
    for name in ("中文文件.pdf", "Документ.pdf", "___.pdf"):
        lesbar = S("kap", "archiv/" + name).split("--")[0]
        pruefe(lesbar == "kap",
               "nicht-lateinisch %r: lesbarer Teil ist GENAU der Bereich, ist %r"
               % (name, lesbar))
    pruefe(S("kap", "archiv/Bericht.pdf").split("--")[0] != "kap",
           "lateinischer Name behaelt dagegen seinen lesbaren Teil")


if __name__ == "__main__":
    test_kennpfad()
    test_fingerabdruck()
    test_schluessel()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
