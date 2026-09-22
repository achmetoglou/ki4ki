#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zweite Probe: echte Umlaute, überall wo sie wehtun können.

Die erste Probe (probedokumente.py) hat den Pfad-Schlüssel belegt, war aber
in Behelfsschreibung gesetzt (ue statt ü). Dadurch blieb offen, ob die Kette
mit echten Umlauten trägt — und genau die haben die KAP-Unterlagen.

Diese Probe setzt Umlaute dorthin, wo sie an vier verschiedenen Stellen
etwas kaputtmachen können:

  Ordnername       Müller & Söhne/        -> Umlaut UND '&' gehen in den
                                             Schlüssel ein (BUGS 11)
  Dateiname        Zugversuch Charge 7    -> Leerzeichen im Namen
  Tiefe            Qualität/Wareneingang/ -> drei Ebenen unter input/
  Satzanfang       "Prüfklima während …"  -> die ERSTEN zwei Wörter tragen
                                             Umlaute; daran scheitert der
                                             Dreiwort- UND der Zweiwort-
                                             Einstieg der gelben Markierung
  Sonderzeichen    €, °C, %               -> überleben sie Docling und die
                                             Zeichensatz-Umwandlung?

⭐ Jede Zahl kommt genau EINMAL vor. Antwortet die Anlage mit der Zahl des
   falschen Dokuments, fällt das auf — ohne eindeutige Zahlen wäre jede
   Antwort "irgendwie richtig" und die Probe wertlos.

  python3 bau/probedokumente-umlaute.py <zielordner>
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

SEITEN = {
    os.path.join("Müller & Söhne", "Prüfberichte",
                 "Zugversuch Charge 7.pdf"): [
        ("Prüfbericht Zugversuch – Charge 7", [
            "Werkstoff: Polyamid 6.6, glasfaserverstärkt (35 Prozent).",
            "Prüfklima während der Messung: 23 °C bei 50 % Feuchte.",
            "",
            "Die Zugfestigkeit beträgt 318 MPa.",
            "Glasübergangstemperatur: 148 °C.",
            "Bruchdehnung 2,7 Prozent bei fünf geprüften Körpern.",
        ]),
        ("Prüfbericht Zugversuch – Charge 7, Blatt 2", [
            "Übersicht der Streuung: Standardabweichung 11 MPa.",
            "Für die Freigabe war die Prüfstelle Süd zuständig.",
        ]),
    ],
    os.path.join("Müller & Söhne", "Prüfberichte",
                 "Zugversuch Charge 9.pdf"): [
        ("Prüfbericht Zugversuch – Charge 9", [
            "Werkstoff: Polyamid 6.6, glasfaserverstärkt (35 Prozent).",
            "Prüfklima während der Messung: 23 °C bei 50 % Feuchte.",
            "",
            "Die Zugfestigkeit beträgt 344 MPa.",
            "Glasübergangstemperatur: 151 °C.",
            "Bruchdehnung 2,4 Prozent bei fünf geprüften Körpern.",
        ]),
    ],
    os.path.join("Müller & Söhne", "Angebote",
                 "Angebot & Nachtrag.pdf"): [
        ("Angebot & Nachtrag – Spritzgussteile", [
            "Über die Laufzeit von zwölf Monaten gilt ein fester Preis.",
            "",
            "Der Stückpreis beträgt 12,40 € bei Abnahme von 5.000 Stück.",
            "Werkzeugkosten einmalig 8.900 €, zahlbar bei Auftragserteilung.",
            "Änderungen am Werkzeug werden nach Aufwand berechnet.",
        ]),
    ],
    os.path.join("Schäfer Kunststofftechnik", "Qualität", "Wareneingang",
                 "Prüfanweisung.pdf"): [
        ("Prüfanweisung Wareneingang", [
            "Für jede Lieferung wird ein Rückstellmuster gezogen.",
            "",
            "Rückstellmuster sind 24 Monate aufzubewahren.",
            "Die Größe der Stichprobe richtet sich nach der Losgröße.",
            "Bei Überschreitung der Toleranz wird die Charge gesperrt.",
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
                     "Erfundenes Probedokument – keine echten Daten.")
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
    print("""
Was diese Probe beantworten soll:
  1. Trägt der Schlüssel, wenn Umlaute und '&' IM PFAD stehen?
  2. Bleibt der Beleg blau, wenn das Zitat mit einem Umlautwort beginnt?
  3. Überleben €, °C und % den Weg durch Docling bis in die Antwort?
  4. Werden zwei Chargen im SELBEN Unterordner auseinandergehalten?

Fragen, die zu stellen sind (die Zahlen kommen je genau einmal vor):
  - "Welche Zugfestigkeit haben Charge 7 und Charge 9?"   -> 318 und 344 MPa
  - "Wie hoch ist der Stückpreis?"                        -> 12,40 €
  - "Wie lange sind Rückstellmuster aufzubewahren?"        -> 24 Monate
  - "Bei welchem Prüfklima wurde gemessen?"                -> 23 °C, 50 %

⛔ Antwortet die Anlage auf die erste Frage mit nur EINER Zahl, sind die
   beiden Chargen wieder zusammengefallen - dann ist der Schlüssel nicht
   angekommen.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
