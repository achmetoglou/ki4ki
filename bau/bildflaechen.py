"""Wie gross sind die Abbildungen im Bestand wirklich?

Hintergrund: Docling beschreibt eine Abbildung nur, wenn sie groesser als
picture_area_threshold (heute 0,08 = 8 Prozent der Seitenflaeche) ist. Bei
der Probe am 21.09. waren das null von drei Abbildungen - die Schwelle
unterdrueckt Bildbeschreibungen also moeglicherweise im ganzen Bestand.

Bevor eine Schwelle gesenkt wird, die einmal gegen eine Endlosschleife
eingefuehrt wurde (BUGS_UND_FIXES.md Punkt 1), gehoert gezaehlt, wie viel
sie tatsaechlich wegwirft und was das Senken an Laufzeit kostet.

Gibt AUSSCHLIESSLICH Zahlen aus - keine Dateinamen, keine Ordnernamen,
keine Inhalte. Mit der Datensperre vereinbar.

⚠ Was diese Messung NICHT sieht: Vektorgrafiken. Eine CAD-Zeichnung ohne
eingebettetes Rasterbild taucht bei pdfimages nicht auf, wird von Docling
aber als Abbildung erkannt. Die Zahlen hier sind deshalb eine UNTERE
Schranke. Fuer technische Zeichnungen - also genau den UC-1-Fall - kann
die echte Zahl hoeher liegen. Der Gegencheck mit Docling steht aus.

Aufruf: Das Skript liegt NICHT im Container-Image (dorthin kommen nur die
Dateien aus pruef-proxy/), poppler-utils dagegen schon. Deshalb wird es
ueber die Standardeingabe hineingereicht - kein Neubau noetig:

    cd ~/ki4ki
    docker exec -i ki4ki-pruef-proxy python3 - < bau/bildflaechen.py

Mehr Dokumente, andere Schwelle, anderer Baum:

    docker exec -e ANZAHL=50 -e SCHWELLE=0.04 -i ki4ki-pruef-proxy \\
        python3 - < bau/bildflaechen.py
"""
import os
import random
import re
import subprocess
import sys

WURZEL = os.environ.get("WURZEL", "/daten/pdfs")
ANZAHL = int(os.environ.get("ANZAHL", "20"))
SCHWELLE = float(os.environ.get("SCHWELLE", "0.08"))
SEKUNDEN_JE_BILD = 3.3   # gemessen 21.09.

_SEITE = re.compile(r"Page size:\s+([0-9.]+) x ([0-9.]+)")


def seitenflaeche(pfad):
    """Flaeche der ersten Seite in Quadratpunkten, 0 wenn unlesbar."""
    try:
        aus = subprocess.run(["pdfinfo", pfad], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return 0.0
    t = _SEITE.search(aus)
    return float(t.group(1)) * float(t.group(2)) if t else 0.0


def bildanteile(pfad, flaeche):
    """Flaechenanteil jedes eingebetteten Bildes an der Seite."""
    try:
        aus = subprocess.run(["pdfimages", "-list", pfad], capture_output=True,
                             text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    anteile = []
    for zeile in aus.splitlines()[2:]:
        s = zeile.split()
        if len(s) < 14 or s[2] not in ("image", "smask", "stencil"):
            continue
        try:
            breite, hoehe = float(s[3]), float(s[4])
            xppi, yppi = float(s[12]), float(s[13])
        except ValueError:
            continue
        if xppi <= 0 or yppi <= 0:
            continue
        # Pixel / (Pixel je Zoll) * 72 Punkte je Zoll = Punkte auf der Seite
        gross = (breite / xppi * 72.0) * (hoehe / yppi * 72.0)
        anteile.append(gross / flaeche)
    return anteile


def main():
    if not os.path.isdir(WURZEL):
        print("Wurzel %s fehlt - nichts gemessen." % WURZEL)
        return 1
    alle = []
    for ordner, _u, namen in os.walk(WURZEL):
        for n in namen:
            if n.lower().endswith(".pdf"):
                alle.append(os.path.join(ordner, n))
    if not alle:
        print("Keine PDF gefunden - nichts gemessen.")
        return 1

    random.seed(20260921)   # feste Auswahl, damit die Messung wiederholbar ist
    probe = random.sample(alle, min(ANZAHL, len(alle)))

    mit_bild = ohne_bild = unlesbar = 0
    ueber = unter = 0
    groesstes_unter = 0.0
    treppe = [0] * 6   # <1%, 1-2%, 2-4%, 4-8%, 8-16%, >=16%

    for p in probe:
        flaeche = seitenflaeche(p)
        if flaeche <= 0:
            unlesbar += 1
            continue
        anteile = bildanteile(p, flaeche)
        if anteile is None:
            unlesbar += 1
            continue
        if not anteile:
            ohne_bild += 1
            continue
        mit_bild += 1
        for a in anteile:
            if a >= SCHWELLE:
                ueber += 1
            else:
                unter += 1
                groesstes_unter = max(groesstes_unter, a)
            for i, grenze in enumerate((0.01, 0.02, 0.04, 0.08, 0.16)):
                if a < grenze:
                    treppe[i] += 1
                    break
            else:
                treppe[5] += 1

    gesamt = ueber + unter
    print("Stichprobe: %d von %d PDF im Bestand" % (len(probe), len(alle)))
    print("  %d mit eingebetteten Bildern · %d ohne · %d unlesbar"
          % (mit_bild, ohne_bild, unlesbar))
    if gesamt == 0:
        print("  Keine Bilder gefunden - die Schwelle ist hier ohne Wirkung.")
        return 0
    print("\n%d Bilder insgesamt, Schwelle %.2f" % (gesamt, SCHWELLE))
    print("  wird heute beschrieben:  %5d  (%4.1f %%)"
          % (ueber, 100.0 * ueber / gesamt))
    print("  faellt heute weg:        %5d  (%4.1f %%)"
          % (unter, 100.0 * unter / gesamt))
    print("  groesstes weggefallenes Bild: %.1f %% der Seite"
          % (100.0 * groesstes_unter))
    print("\nVerteilung der Bildgroessen (Anteil an der Seitenflaeche):")
    for name, n in zip(("unter 1 %", "1 bis 2 %", "2 bis 4 %", "4 bis 8 %",
                        "8 bis 16 %", "16 % und mehr"), treppe):
        strich = "#" * int(round(40.0 * n / gesamt)) if gesamt else ""
        print("  %-14s %5d  %s" % (name, n, strich))
    print("\nWas das Senken der Schwelle kosten wuerde, hochgerechnet:")
    je_dok = 1.0 * unter / len(probe)
    print("  %.1f zusaetzliche Bilder je Dokument -> %.1f s je Dokument"
          % (je_dok, je_dok * SEKUNDEN_JE_BILD))
    stunden = je_dok * SEKUNDEN_JE_BILD * len(alle) / 3600.0
    print("  bei %d PDF im Bestand: rund %.1f Stunden zusaetzlich"
          % (len(alle), stunden))
    schon = 1.0 * ueber / len(probe) * SEKUNDEN_JE_BILD * len(alle) / 3600.0
    print("  (heute gehen dafuer schon %.1f Stunden drauf - das ist der"
          " Vergleichswert, nicht null)" % schon)
    print("\n⚠ Untere Schranke: Vektorgrafiken sind hier NICHT mitgezaehlt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
