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
# danach - evtl. ueber Tabellenzellen hinweg - eine SEITENZAHL, und dann ist
# die Zeile ZU ENDE.
#
# \u26d4 GEMESSEN 25.09.: Die alte Fassung endete auf "\\d{1,4}\\b" ohne
#   Zeilenende. Damit traf sie JEDE Zeile mit Punktfuehrung und einer Zahl -
#   also auch jede Positionszeile eines Angebots oder einer Rechnung:
#     "Laborleistung gem. Angebot 274821 ....... 1.234,56"
#     "Zwischensumme ............................ 5.890,00"
#     "| Reisekosten | ...... | 412,80 |"
#   Gemessen an fuenf realistischen Belegzeilen: FUENF von fuenf wurden
#   geloescht. Und zwar VOR dem Einbetten - die Position war danach weder
#   auffindbar noch belegbar, und niemand erfuhr davon.
#
# \u2b50 Der Unterschied ist die ZAHL SELBST, nicht ihr Umfeld: Eine
#   Seitenzahl ist eine ganze Zahl und steht am Zeilenende. Ein Betrag hat
#   Nachkommastellen, einen Tausenderpunkt oder eine Waehrung dahinter.
#   Deshalb: Anker auf das Zeilenende, und ein ausdruecklicher Riegel gegen
#   alles, was nach Geld aussieht.
#
# \u26a0 Das "Sicherheitsnetz" darunter (len(ohne) < 200) war keines - fast
#   jede Zeile hat weniger als 200 Zeichen ohne Punkte und Ziffern. Es hat
#   nie etwas gerettet und den Fehler verdeckt, weil es nach Vorsicht aussah.
_NAVI = re.compile(r"\.{4,}\s*\|?\s*\d{1,4}\s*\|?\s*$")
# Sieht die Zahl nach Geld aus, ist es keine Seitenzahl. Nachkommastellen
# (1.234,56 / 1,234.56), ein Waehrungszeichen oder eine Waehrungsabkuerzung.
_GELD = re.compile(r"\d[.,]\d{2}\b|[\u20ac$\u00a3]|\b(?:EUR|USD|CHF|GBP)\b", re.I)
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
    if _GELD.search(zeile):
        return False        # Betrag, keine Seitenzahl - niemals loeschen
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
