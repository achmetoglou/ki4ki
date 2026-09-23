#!/usr/bin/env python3
"""Pruefreihe: der Schluessel fuer den Dokumentzugang-Zwischenspeicher.

⛔ Gemessen 23.09. an einer Netzwerk-Aufzeichnung: Das Laden eines
  Gespraechsverlaufs dauerte **2.248 ms** und lieferte 14 Byte
  (`{"history":[]}`). Die Zeit ging fuer `erlaubte_dokumente()` drauf -
  das fragt JEDEN Arbeitsbereich einzeln bei AnythingLLM ab (eine
  Antwort allein 42 KB).

⛔ Der Zwischenspeicher dafuer (300 s) griff NIE: Sein Schluessel enthielt
  den ganzen `ki4ki_zugang`-Cookie - und dessen erstes Feld ist eine
  Ablaufzeit, die der Proxy bei JEDER Antwort neu setzt. Neuer Cookie,
  neuer Schluessel, alles nochmal. Der Proxy machte seinen eigenen
  Zwischenspeicher kaputt.

⭐ Der Schluessel muss also aus dem STABILEN Teil gebaut werden: der
  Kennung in der Mitte der Marke, nicht aus Ablaufzeit und Unterschrift.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rolle      # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


AUSWEIS = "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def"
# Dieselbe Sitzung, zwei Sekunden spaeter - Ablauf und Unterschrift anders,
# die Kennung in der Mitte gleich.
COOKIE_A = "ki4ki_zugang=1790206354.4734643704933d18.d44be1546a5121ee5d954"
COOKIE_B = "ki4ki_zugang=1790206687.4734643704933d18.3a3add0771cbb3b4b72a"
# Anderes Konto: andere Kennung.
COOKIE_FREMD = "ki4ki_zugang=1790206687.9999999999999999.3a3add0771cbb3b4b7"


def test_derselbe_zugang_ergibt_denselben_schluessel():
    print("\nDieselbe Sitzung, neuer Cookie -> selber Schluessel")
    a = rolle.zugangs_schluessel(AUSWEIS, COOKIE_A)
    b = rolle.zugangs_schluessel(AUSWEIS, COOKIE_B)
    pruefe(a == b,
           "die wechselnde Ablaufzeit darf den Schluessel NICHT aendern")


def test_fremder_zugang_ergibt_anderen_schluessel():
    print("\nGegenprobe: anderes Konto, anderer Schluessel")
    a = rolle.zugangs_schluessel(AUSWEIS, COOKIE_A)
    f = rolle.zugangs_schluessel(AUSWEIS, COOKIE_FREMD)
    pruefe(a != f,
           "⛔ eine andere Kennung MUSS einen anderen Schluessel geben - "
           "sonst saehe ein Konto die Dokumente eines anderen")
    g = rolle.zugangs_schluessel("Bearer anderer.jwt.hier", COOKIE_A)
    pruefe(a != g, "und eine andere Anmeldung ebenso")


def test_andere_cookies_bleiben_erhalten():
    print("\nAndere Cookies zaehlen weiterhin mit")
    a = rolle.zugangs_schluessel(AUSWEIS, COOKIE_A + "; sitzung=abc")
    b = rolle.zugangs_schluessel(AUSWEIS, COOKIE_A + "; sitzung=xyz")
    pruefe(a != b,
           "eine andere AnythingLLM-Sitzung ist ein anderer Zugang")


def test_ohne_marke_unveraendert():
    print("\nGegenprobe: ohne ki4ki_zugang bleibt alles wie bisher")
    a = rolle.zugangs_schluessel(AUSWEIS, "sitzung=abc")
    b = rolle.zugangs_schluessel(AUSWEIS, "sitzung=abc")
    pruefe(a == b, "gleich bleibt gleich")
    pruefe(rolle.zugangs_schluessel("", "") == "|" or
           rolle.zugangs_schluessel("", "").strip("|") == "",
           "leer bleibt leer - der Aufrufer erkennt das weiterhin")


def test_die_kennung_wandert_nicht():
    """Die Kennung IN der Marke muss ueber die Sitzung gleich bleiben.

    ⛔ Gemessen 23.09., nachdem der Zwischenspeicher-Schluessel stabil
      war: Der Threadwechsel wurde wieder langsam, und im Protokoll stand
      "36 Zugaenge aus Platte geladen" (vorher 1). Ursache: Die Kennung,
      die der Proxy in die NEUE Marke schreibt, entsteht aus dem ALTEN
      Cookie - und das enthaelt vorne eine Ablaufzeit:

          kennung_neu = sha256(Authorization + "|" + Cookie_alt)
          Cookie_alt  = <ablauf>.<kennung_alt>.<unterschrift>

      Damit wandert die Kennung bei jeder Antwort weiter. Ich hatte den
      LESER stabil gemacht, aber nicht den SCHREIBER - halb repariert ist
      hier nicht besser als gar nicht.

    ⭐ Die Kennung darf die Marke daher gar nicht ansehen: Sie entsteht
      aus der Anmeldung und den uebrigen Cookies. Dann ist sie ab dem
      ersten Aufruf ein fester Punkt.
    """
    print("\nDie Kennung in der Marke wandert nicht")
    ohne = rolle.marken_kennung(AUSWEIS, "")
    mit_a = rolle.marken_kennung(AUSWEIS, "ki4ki_zugang=1790206354.%s.sig" % ohne)
    mit_b = rolle.marken_kennung(AUSWEIS, "ki4ki_zugang=1790206687.%s.and" % mit_a)
    pruefe(ohne == mit_a == mit_b,
           "dieselbe Anmeldung ergibt IMMER dieselbe Kennung - egal, was "
           "in der Marke steht (ist: %s / %s / %s)" % (ohne, mit_a, mit_b))
    pruefe(rolle.marken_kennung("Bearer anderer.jwt", "") != ohne,
           "⛔ Gegenprobe: eine andere Anmeldung ergibt eine andere "
           "Kennung - sonst teilten sich zwei Konten die Dokumentrechte")
    pruefe(rolle.marken_kennung(AUSWEIS, "sitzung=abc") != ohne,
           "ein anderes Sitzungs-Cookie zaehlt weiterhin mit")
    pruefe(rolle.marken_kennung("", "") == "",
           "ohne alles gibt es keine Kennung")


if __name__ == "__main__":
    test_derselbe_zugang_ergibt_denselben_schluessel()
    test_fremder_zugang_ergibt_anderen_schluessel()
    test_andere_cookies_bleiben_erhalten()
    test_ohne_marke_unveraendert()
    test_die_kennung_wandert_nicht()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
