#!/usr/bin/env python3
"""Erfundene Probedokumente fuer die Abnahme des Pfad-Schluessels.

Kein echter Bestand, keine Kundendaten - alle Zahlen und Namen sind
ausgedacht. Jedes Dokument prueft GENAU EINE Sache; ohne den Umbau
scheitert jedes an seiner eigenen Stelle:

  KundeAlpha/Prüfbericht.pdf   ⎫ gleicher Dateiname, zwei Kunden.
  KundeBeta/Prüfbericht.pdf    ⎭ Ohne den Umbau ueberlebt nur EINER -
                                  der andere verschwindet still.
  KundeAlpha/Angebot & Kalkulation.pdf
                                  AnythingLLM macht aus '&' ein 'and'.
                                  Die Wortersetzung ueberlebt jede
                                  Normalisierung (BUGS_UND_FIXES.md 11).
  Normen/Kleben/Verfahren.pdf     Drei Ebenen tief. Bis zum Umbau
                                  unbenutzbar (BUGS_UND_FIXES.md 7).

Jedes traegt eine eigene, leicht abfragbare Zahl - daran laesst sich
erkennen, WELCHES Dokument ein Beleg wirklich getroffen hat.

  python3 bau/probedokumente.py <zielordner>
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

SEITEN = {
    os.path.join("KundeAlpha", "Pruefbericht.pdf"): [
        ("Prüfbericht Zugversuch - Kunde Alpha", [
            "Werkstoff: Polyamid 6.6, glasfaserverstärkt (30 Prozent).",
            "Probekörper nach Norm, Prüfgeschwindigkeit 5 mm je Minute.",
            "",
            "Ergebnis: Die Zugfestigkeit beträgt 412 MPa.",
            "Bruchdehnung 3,1 Prozent. Prüfklima 23 Grad, 50 Prozent Feuchte.",
        ]),
        ("Prüfbericht Zugversuch - Kunde Alpha, Seite 2", [
            "Anmerkung zur Streuung: Fünf Proben, Standardabweichung 9 MPa.",
            "Die Kennlinie zeigt kein ausgeprägtes Fließen.",
            "Freigabe durch die Prüfstelle am 14. März.",
        ]),
    ],
    os.path.join("KundeBeta", "Pruefbericht.pdf"): [
        ("Prüfbericht Zugversuch - Kunde Beta", [
            "Werkstoff: Polypropylen, talkumgefuellt (20 Prozent).",
            "Probekörper nach Norm, Prüfgeschwindigkeit 5 mm je Minute.",
            "",
            "Ergebnis: Die Zugfestigkeit beträgt 287 MPa.",
            "Bruchdehnung 5,8 Prozent. Prüfklima 23 Grad, 50 Prozent Feuchte.",
        ]),
        ("Prüfbericht Zugversuch - Kunde Beta, Seite 2", [
            "Anmerkung zur Streuung: Fünf Proben, Standardabweichung 14 MPa.",
            "Die Kennlinie zeigt ein ausgeprägtes Fließen bei 240 MPa.",
            "Freigabe durch die Prüfstelle am 22. März.",
        ]),
    ],
    os.path.join("KundeAlpha", "Angebot & Kalkulation.pdf"): [
        ("Angebot und Kalkulation - Kunde Alpha", [
            "Leistung: Serienpruefung Zugversuch, 120 Probekörper.",
            "",
            "Der angebotene Stückpreis beträgt 47 Euro je Probekörper.",
            "Gesamtsumme 5.640 Euro, Laufzeit acht Wochen.",
        ]),
    ],
    os.path.join("Normen", "Kleben", "Verfahren.pdf"): [
        ("Verfahrensanweisung Kleben", [
            "Geltungsbereich: Klebverbindungen an thermoplastischen Bauteilen.",
            "",
            "Die Aushaertezeit beträgt 36 Stunden bei Raumtemperatur.",
            "Vorbehandlung: Beflammen, danach hoechstens 20 Minuten Wartezeit.",
        ]),
        ("Verfahrensanweisung Kleben, Seite 2", [
            "Pruefung der Verbindung im Zugscherversuch nach 36 Stunden.",
            "Mindestwert der Zugscherfestigkeit: 12 MPa.",
        ]),
    ],
}


def bauen(ziel, name, seiten):
    pfad = os.path.join(ziel, name)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    c = canvas.Canvas(pfad, pagesize=A4)
    for ueberschrift, zeilen in seiten:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(25 * mm, 265 * mm, ueberschrift)
        c.setFont("Helvetica", 11)
        y = 250 * mm
        for z in zeilen:
            c.drawString(25 * mm, y, z)
            y -= 7 * mm
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(25 * mm, 15 * mm,
                     "Erfundenes Probedokument - keine echten Daten.")
        c.showPage()
    c.save()
    return pfad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    ziel = sys.argv[1]
    os.makedirs(ziel, exist_ok=True)
    for name, seiten in SEITEN.items():
        p = bauen(ziel, name, seiten)
        print("  %6d Byte  %s" % (os.path.getsize(p), name))
    print("\n%d Dokumente unter %s" % (len(SEITEN), ziel))
    print("\nWas sie beweisen sollen:")
    print("  - zwei gleichnamige Prüfberichte in zwei Kundenordnern muessen")
    print("    BEIDE im Bestand landen (412 MPa und 287 MPa)")
    print("  - das Angebot mit '&' im Namen muss anklickbar bleiben")
    print("  - die Verfahrensanweisung liegt drei Ebenen tief")
    return 0


if __name__ == "__main__":
    sys.exit(main())
