#!/usr/bin/env python3
"""Pruefreihe fuer den Anhang-Weg (Weg A: Datei an den Chat haengen).

⛔ Meldung vom 17.09.2026, woertlich: "Es wurden 3 Dateien ueber das
  + Zeichen zusaetzlich in diesem Chat bereitgestellt allerdings nur eins
  bei der Anfrage ausgewertet."

Aufruf:   python3 anhangtest.py     (Exit 0 = alle gruen)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anhang          # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


# Die Textgewinnung (Tika) wird hier ersetzt - geprueft wird die
# Zusammenfuehrung, nicht Tika.
def text_aus(inhalt):
    return inhalt.decode("utf-8")


DREI = [("a.pdf", b"Alpha-Inhalt"),
        ("b.docx", b"Beta-Inhalt"),
        ("c.xlsx", b"Gamma-Inhalt")]


def test_drei_dateien_auf_einmal():
    print("\nDrei Dateien in EINEM Hochladen")
    e = anhang.aufnehmen(DREI, text_aus, jetzt=1000.0)
    pruefe(e is not None and len(e.get("dokumente") or []) == 3,
           "alle drei Dateien sind im Eintrag")
    for stueck in ("Alpha-Inhalt", "Beta-Inhalt", "Gamma-Inhalt"):
        pruefe(e is not None and stueck in e["text"],
               "der Text enthaelt %s" % stueck)
    pruefe(e is not None and all(n in e["name"] for n in
                                 ("a.pdf", "b.docx", "c.xlsx")),
           "die Herkunftszeile nennt alle drei Dateinamen")
    pruefe(e is not None and e["roh_len"] == len(e["text"]),
           "roh_len ist die Gesamtlaenge - sonst luegt die Gelesen-Zeile")


def test_nachgereicht():
    print("\nErst eine Datei, dann zwei weitere nachgereicht")
    erst = anhang.aufnehmen(DREI[:1], text_aus, jetzt=1000.0)
    dann = anhang.aufnehmen(DREI[1:], text_aus, vorher=erst, jetzt=1010.0)
    pruefe(dann is not None and len(dann.get("dokumente") or []) == 3,
           "die zuerst hochgeladene Datei geht nicht verloren")
    pruefe(dann is not None and "Alpha-Inhalt" in dann["text"],
           "der Text der ersten Datei ist noch da")


def test_vorgaenger_abgelaufen():
    print("\nEin alter Anhang zaehlt nicht mehr mit")
    alt = anhang.aufnehmen(DREI[:1], text_aus, jetzt=1000.0)
    neu = anhang.aufnehmen(DREI[1:2], text_aus, vorher=alt,
                           jetzt=1000.0 + 5000, haltbar=1200)
    pruefe(neu is not None and len(neu.get("dokumente") or []) == 1,
           "nach Ablauf der Haltbarkeit bleibt nur das Neue")


def test_dieselbe_datei_erneut():
    print("\nDieselbe Datei noch einmal hochgeladen")
    erst = anhang.aufnehmen([("a.pdf", b"alt")], text_aus, jetzt=1000.0)
    neu = anhang.aufnehmen([("a.pdf", b"neu")], text_aus, vorher=erst,
                           jetzt=1010.0)
    pruefe(neu is not None and len(neu.get("dokumente") or []) == 1,
           "sie steht einmal drin, nicht zweimal")
    pruefe(neu is not None and "neu" in neu["text"] and "alt" not in neu["text"],
           "die neue Fassung gewinnt")


def test_unlesbare_datei_reisst_nichts_mit():
    print("\nEine unlesbare Datei darf die anderen nicht mitnehmen")
    e = anhang.aufnehmen([("leer.db", b""), ("b.docx", b"Beta-Inhalt")],
                         text_aus, jetzt=1000.0)
    pruefe(e is not None and len(e.get("dokumente") or []) == 1,
           "die lesbare Datei ist da")
    pruefe(e is not None and "Beta-Inhalt" in e["text"],
           "und ihr Text auch")
    leer = anhang.aufnehmen([("leer.db", b"")], text_aus, jetzt=1000.0)
    pruefe(leer is None,
           "gar nichts Lesbares und kein Vorgaenger -> kein Eintrag")


def test_eine_datei_bleibt_wie_bisher():
    print("\nRueckwaerts vertraeglich: eine einzelne Datei")
    e = anhang.aufnehmen(DREI[:1], text_aus, jetzt=1000.0)
    pruefe(e is not None and e["text"] == "Alpha-Inhalt",
           "der Text ist unveraendert der Dateiinhalt (keine Zwischenzeile)")
    pruefe(e is not None and e["name"] == "a.pdf",
           "die Fusszeile nennt weiterhin nur den Dateinamen")


if __name__ == "__main__":
    test_drei_dateien_auf_einmal()
    test_nachgereicht()
    test_vorgaenger_abgelaufen()
    test_dieselbe_datei_erneut()
    test_unlesbare_datei_reisst_nichts_mit()
    test_eine_datei_bleibt_wie_bisher()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
