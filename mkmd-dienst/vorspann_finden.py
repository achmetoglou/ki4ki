#!/usr/bin/env python3
"""
Findet Verzeichniszeilen (Inhalt, Abbildungen, Tabellen) in den Arbeiten.

Verzeichnisse enthalten keine Aussage, aber sehr viele Fachbegriffe auf engem
Raum. Beim Suchen gewinnen sie deshalb gegen echten Fliesstext - es kam
auf eine Fachfrage aus der einschlaegigsten Arbeit ausgerechnet das
Inhaltsverzeichnis zurueck.

Bewusst NICHT geschnitten wird "alles vor Abschnitt 1": davor stehen auch
Kurzfassung und Abstract, und die sind inhaltlich wertvoll. Entfernt werden
nur Navigationszeilen - erkennbar an der Punktfuehrung mit Seitenzahl am Ende.

Das Skript SCHNEIDET NICHTS. Es misst nur.

  ./vorspann_finden.py            Uebersicht
  ./vorspann_finden.py --proben   zusaetzlich Textproben
"""
import glob
import os
import re
import sys

QUELLE = os.path.expanduser("~/ki4ki/reextract/md_fertig")

# Eine Verzeichniszeile: irgendwo eine Punktfuehrung (vier Punkte oder mehr),
# danach - evtl. ueber Tabellenzellen hinweg - eine Seitenzahl.
_NAVI = re.compile(r"\.{4,}\s*\|?\s*\d{1,4}\b")
# Ueberschriften der Verzeichnisse selbst
_UEBERSCHRIFT = re.compile(
    r"^#{0,4}\s*(?:[IVX0-9]+\.?\s*)?(Inhaltsverzeichnis|Abbildungsverzeichnis"
    r"|Tabellenverzeichnis|Abk[üu]rzungsverzeichnis|Formelverzeichnis"
    r"|Symbolverzeichnis|Table of contents|List of figures|List of tables)"
    r"\s*$", re.I)


def navigationszeile(zeile):
    """Ist das eine reine Verzeichniszeile?"""
    if _UEBERSCHRIFT.match(zeile.strip()):
        return True
    if not _NAVI.search(zeile):
        return False
    # Sicherheitsnetz: eine echte Textzeile bleibt auch ohne die Punkte lesbar.
    # Eine Verzeichniszeile besteht fast nur aus Punkten, Ziffern und Titeln.
    ohne = re.sub(r"[.\s|\d]", "", zeile)
    return len(ohne) < 200


def putze(text):
    behalten, weg = [], 0
    for zeile in text.split("\n"):
        if navigationszeile(zeile):
            weg += len(zeile) + 1
            continue
        behalten.append(zeile)
    return "\n".join(behalten), weg


def main():
    proben = "--proben" in sys.argv
    dateien = sorted(glob.glob(os.path.join(QUELLE, "*.md")))
    betroffen, gesamt_weg, gesamt_gross, beispiele = 0, 0, 0, []
    schlimmste = []
    for pfad in dateien:
        text = open(pfad, encoding="utf-8").read()
        neu, weg = putze(text)
        gesamt_gross += len(text)
        if not weg:
            continue
        betroffen += 1
        gesamt_weg += weg
        schlimmste.append((100.0 * weg / len(text), os.path.basename(pfad),
                           weg, len(text)))
        if len(beispiele) < 5:
            entfernt = [z for z in text.split("\n") if navigationszeile(z)]
            beispiele.append((os.path.basename(pfad), entfernt[:2],
                              [z for z in text.split("\n")
                               if z.strip() and not navigationszeile(z)][:1]))

    print("Dateien gesamt:        %d" % len(dateien))
    print("mit Verzeichniszeilen: %d (%.0f %%)"
          % (betroffen, 100.0 * betroffen / max(1, len(dateien))))
    print("entfernte Zeichen:     %d von %d (%.1f %% des Bestands)"
          % (gesamt_weg, gesamt_gross, 100.0 * gesamt_weg / max(1, gesamt_gross)))
    print()
    schlimmste.sort(reverse=True)
    print("Groesster Anteil je Arbeit:")
    for a, n, w, g in schlimmste[:8]:
        print("  %5.1f %%  %-22s %7d von %7d Zeichen" % (a, n, w, g))

    if proben:
        print()
        print("=" * 70)
        for name, entfernt, bleibt in beispiele:
            print("\n--- %s" % name)
            for z in entfernt:
                print("  WEG    : " + " ".join(z.split())[:130])
            for z in bleibt:
                print("  BLEIBT : " + " ".join(z.split())[:130])


if __name__ == "__main__":
    main()
