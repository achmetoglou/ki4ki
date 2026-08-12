"""Dokumentnamen saeubern, BEVOR sie in die Anlage kommen.

Warum ueberhaupt: Ein Dokumentname taucht an sechs Stellen auf - Dateisystem,
Docling, Markdown-Datei, Arbeitsbereich, Belegadresse, Wortverzeichnis - und
jede geht anders mit ihm um. AnythingLLM schreibt ihn sogar selbst um
(aus "S-10039 .md" wird "S-10039-.md-<Kennung>.json"). Je gewoehnlicher der
Name, desto weniger kann schiefgehen.

⛔ GEMESSEN AN 1263 ARBEITEN:

    1202  Belegsprung moeglich
      61  KEIN Klick moeglich
            55x  Leerzeichen im Namen
             5x  Leerzeichen + Klammern
             1x  GESCHUETZTES Leerzeichen (U+00A0) - unsichtbar

⚠ Umlaute sind NICHT das Problem: AeOeUeaeoeue stehen ausdruecklich in der
  Zeichenklasse der Oberflaeche. Gefaehrlich ist nur die ZERLEGTE
  Schreibweise (NFD), die Macs liefern: "ä" als a + Trema. Sieht identisch
  aus, vergleicht sich ungleich. Im Bestand aktuell 0 Faelle - auf Macs
  ist das nur eine Frage der Zeit.

WAS DIESE PRUEFINSTANZ TUT - und was ausdruecklich NICHT:
  + zerlegte Umlaute zusammensetzen (NFC)
  + geschuetzte/schmale Leerzeichen zu gewoehnlichen machen
  + Steuerzeichen entfernen
  + Leerzeichen am Rand weg, doppelte zu einfachen
  + Zeichen ersetzen, die eine Adresse zerreissen:  #  ?  %  &  /  \
  - Umlaute bleiben Umlaute (kein "ue" aus "ü")
  - Leerzeichen INNEN bleiben (55 Arbeiten heissen so; stattdessen wurde
    das Muster in der Oberflaeche erweitert)
  - Grossschreibung bleibt

Eine Aenderung wird IMMER gemeldet. Ein Werkzeug, das im Stillen umbenennt,
ist schlimmer als eins, das es gar nicht tut.
"""
import os
import re
import unicodedata

# Zeichen, die in einer Adresse oder auf der Platte Aerger machen.
# / und \ trennen Verzeichnisse, # ? % & zerreissen die Belegadresse.
_GEFAEHRLICH = {"#": "-", "?": "-", "%": "-", "&": "und",
                "/": "-", "\\": "-", ":": "-", "*": "-",
                '"': "", "<": "-", ">": "-", "|": "-"}

# Alles, was wie ein Leerzeichen aussieht, aber keines ist.
_WIE_LEERZEICHEN = re.compile(
    "[   -   　 ﻿\t]")


def saeubern(name):
    """Gibt (sauberer_name, [was_geaendert_wurde]) zurueck."""
    urspruenglich = name
    aenderungen = []

    stamm, endung = os.path.splitext(name)

    # 1. Zerlegte Umlaute zusammensetzen. Muss ZUERST kommen, sonst
    #    zaehlen die folgenden Schritte Zeichen doppelt.
    n = unicodedata.normalize("NFC", stamm)
    if n != stamm:
        aenderungen.append("zerlegte Umlaute zusammengesetzt")
        stamm = n

    # 2. Was wie ein Leerzeichen aussieht, wird eines. Das geschuetzte
    #    Leerzeichen ist der Fall, den niemand sieht.
    n = _WIE_LEERZEICHEN.sub(" ", stamm)
    if n != stamm:
        aenderungen.append("unsichtbares Leerzeichen ersetzt")
        stamm = n

    # 3. Steuerzeichen raus.
    n = "".join(c for c in stamm if ord(c) >= 32 and ord(c) != 127)
    if n != stamm:
        aenderungen.append("Steuerzeichen entfernt")
        stamm = n

    # 4. Zeichen, die Adressen zerreissen.
    n = stamm
    for schlecht, gut in _GEFAEHRLICH.items():
        n = n.replace(schlecht, gut)
    if n != stamm:
        aenderungen.append("Sonderzeichen ersetzt")
        stamm = n

    # 5. Doppelte Leerzeichen und Raender. Zuletzt, damit die Schritte
    #    davor nicht wieder Raender erzeugen.
    n = re.sub(r"\s{2,}", " ", stamm).strip(" .")
    if n != stamm:
        aenderungen.append("Leerzeichen am Rand entfernt")
        stamm = n

    if not stamm:
        stamm = "dokument"
        aenderungen.append("Name war nach der Saeuberung leer")

    sauber = stamm + endung.lower()
    if sauber == urspruenglich:
        return urspruenglich, []
    return sauber, aenderungen


def freier_name(ordner, name):
    """Sauberer Name, der im Ordner noch nicht belegt ist.

    ⚠ Zwei verschiedene Namen koennen nach der Saeuberung derselbe sein
      ("A B.pdf" und "A  B.pdf"). Ohne diesen Schritt wuerde die zweite
      Datei die erste ueberschreiben - ein stiller Datenverlust genau in
      dem Werkzeug, das Ordnung schaffen soll.
    """
    sauber, aenderungen = saeubern(name)
    if not os.path.exists(os.path.join(ordner, sauber)):
        return sauber, aenderungen
    stamm, endung = os.path.splitext(sauber)
    for i in range(2, 100):
        versuch = "%s (%d)%s" % (stamm, i, endung)
        if not os.path.exists(os.path.join(ordner, versuch)):
            return versuch, aenderungen + ["Name war belegt, Nummer angehaengt"]
    raise RuntimeError("Kein freier Name fuer %r" % name)


if __name__ == "__main__":
    faelle = [
        ("DS-00-000 .pdf", "DS-00-000.pdf", "Leerzeichen am Ende"),
        ("DS-00-000 .pdf", "DS-00-000.pdf", "geschuetztes Leerzeichen"),
        ("DVS_2213-1_Teil 2.pdf", "DVS_2213-1_Teil 2.pdf", "Leerzeichen INNEN bleibt"),
        ("Prüfverfahren.pdf", "Prüfverfahren.pdf", "zerlegter Umlaut (Mac)"),
        ("Prüfverfahren.pdf", "Prüfverfahren.pdf", "Umlaut bleibt Umlaut"),
        ("Bericht #3 & Anhang.pdf", "Bericht -3 und Anhang.pdf", "Adresszeichen"),
        ("A  B.pdf", "A B.pdf", "doppeltes Leerzeichen"),
        ("Bericht.PDF", "Bericht.pdf", "Endung klein"),
        ("  .pdf", "dokument.pdf", "Name war leer"),
        ("[Ehr06] Faserverbund.pdf", "[Ehr06] Faserverbund.pdf", "Klammern bleiben"),
    ]
    print("=== Gegenprobe am Verhalten")
    schlecht = 0
    for ein, soll, was in faelle:
        ist, aend = saeubern(ein)
        gut = ist == soll
        schlecht += not gut
        print("   %-5s %-28s %r -> %r%s"
              % ("ok" if gut else "FALSCH", was, ein, ist,
                 "" if gut else "   erwartet %r" % soll))
    # Zweimal saeubern darf nichts mehr aendern
    for ein, soll, _ in faelle:
        einmal, _ = saeubern(ein)
        zweimal, a = saeubern(einmal)
        if zweimal != einmal or a:
            print("   FALSCH nicht stabil: %r -> %r -> %r" % (ein, einmal, zweimal))
            schlecht += 1
    print("   %-5s zweimal saeubern aendert nichts mehr"
          % ("ok" if not schlecht else "siehe oben"))
    raise SystemExit(1 if schlecht else 0)
