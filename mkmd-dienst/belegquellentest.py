#!/usr/bin/env python3
"""Prueft die Office-Regel der AUFNAHME an einem echten Dateibaum.

  python3 mkmd-dienst/belegquellentest.py

Kein laufender Dienst noetig - geprueft wird die Rechnung selbst
(belegquelle.original_zu und mkmd_dienst.eintrag_rechnen).

⭐ Womit wird diese Pruefung ROT? Es genuegt, in mkmd_dienst.eintrag_rechnen
  die Zeile `traeger = belegquelle.original_zu(bereich, rest)` durch
  `traeger = None` zu ersetzen - also genau der Stand vor dieser Aenderung.
  Dann fallen die Faelle 5, 6, 7 und 9 um: Die PDF bekaeme wieder einen
  eigenen Abdruck. Die Gegenprobe steht als Fall 10 daneben und bleibt in
  BEIDEN Staenden gruen, damit ein Abschalten der Regel nicht als "alles
  gruen" durchgeht.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import belegquelle   # noqa: E402
import mkmd_dienst   # noqa: E402
import schluessel    # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def lege_an(wurzel, *pfad):
    voll = os.path.join(wurzel, *pfad)
    os.makedirs(os.path.dirname(voll), exist_ok=True)
    with open(voll, "w", encoding="utf-8") as fh:
        fh.write("x")
    return voll


def main():
    baum = tempfile.mkdtemp(prefix="belegquelle-test-")
    alt = belegquelle.DOKUMENTE
    belegquelle.DOKUMENTE = baum
    try:
        # (1) Original und PDF liegen zusammen in input/ - der Normalfall des
        #     Kundenordners: Word-Datei und die daneben exportierte PDF.
        lege_an(baum, "kap", "input", "KundeA", "Angebot.docx")
        lege_an(baum, "kap", "input", "KundeA", "Angebot.pdf")
        # (2) Das Original liegt schon aus einem frueheren Durchgang im
        #     Archiv, die PDF kommt erst jetzt - andere Stufe, dasselbe
        #     Dokument.
        lege_an(baum, "kap", "archiv", "KundeB", "Folien.pptx")
        # (3) Eine PDF ganz ohne Original - ein eigenes Dokument.
        lege_an(baum, "kap", "input", "KundeC", "Zeichnung.pdf")
        # (4) Ein aussortiertes Original zaehlt NICHT.
        lege_an(baum, "kap", "aussortiert", "KundeD", "Notiz.doc")

        pruefe(belegquelle.original_zu("kap", "KundeA/Angebot.pdf")
               == "KundeA/Angebot.docx",
               "1 Original im selben Ordner wird gefunden")
        pruefe(belegquelle.original_zu("kap", "KundeB/Folien.pdf")
               == "KundeB/Folien.pptx",
               "2 Original in einer anderen Stufe wird gefunden")
        pruefe(belegquelle.original_zu("kap", "KundeC/Zeichnung.pdf") is None,
               "3 PDF ohne Original bleibt ihr eigenes Dokument")
        pruefe(belegquelle.original_zu("kap", "KundeD/Notiz.pdf") is None,
               "4 aussortiertes Original zaehlt nicht als Traeger")

        # --- Die Zusicherung, um die es geht -------------------------------
        pdf = mkmd_dienst.eintrag_rechnen("kap", "input/KundeA/Angebot.pdf")
        doc = mkmd_dienst.eintrag_rechnen("kap", "input/KundeA/Angebot.docx")
        pruefe(pdf["abdruck"] == doc["abdruck"],
               "5 Word und seine PDF haben EINEN Abdruck (%s / %s)"
               % (pdf["abdruck"], doc["abdruck"]))
        pruefe(pdf["schluessel"] == doc["schluessel"],
               "6 Word und seine PDF haben EINEN Schluessel")
        pruefe(pdf["nur_beleg"] is True and doc["nur_beleg"] is False,
               "7 nur die PDF ist als Belegquelle gekennzeichnet")
        pruefe(pdf["traeger"] == "KundeA/Angebot.docx",
               "8 der Traeger steht in der Antwort")

        # Und ueber die Stufengrenze hinweg: PDF in input, Original in archiv.
        pdf2 = mkmd_dienst.eintrag_rechnen("kap", "input/KundeB/Folien.pdf")
        doc2 = mkmd_dienst.eintrag_rechnen("kap", "archiv/KundeB/Folien.pptx")
        pruefe(pdf2["abdruck"] == doc2["abdruck"],
               "9 auch ueber die Stufengrenze hinweg EIN Abdruck")

        # ⛔ GEGENPROBE mit umgekehrtem Ergebnis: Ohne Original daneben MUSS
        #   die PDF ihren eigenen Abdruck behalten. Faellt diese Zeile um, ist
        #   die Regel zu gierig und verschmilzt fremde Dokumente.
        frei = mkmd_dienst.eintrag_rechnen("kap", "input/KundeC/Zeichnung.pdf")
        eigen = schluessel.fingerabdruck(
            schluessel.kennpfad("kap", "KundeC/Zeichnung.pdf"))
        pruefe(frei["abdruck"] == eigen and frei["nur_beleg"] is False,
               "10 Gegenprobe: PDF ohne Original behaelt ihren eigenen Abdruck")

        # ⛔ Kein Blick aus dem Bestand heraus.
        lege_an(baum, "draussen.docx")
        pruefe(belegquelle.original_zu("kap", "../../draussen.pdf") is None,
               "11 Gegenprobe: '..' im Pfad fuehrt nicht aus dem Bestand")

        # ⛔ Ein Ordner ist kein Original. Ohne os.path.isfile genuegte ein
        #   Ordner namens "Bericht.docx", um der PDF den Abdruck zu nehmen.
        os.makedirs(os.path.join(baum, "kap", "input", "KundeE",
                                 "Bericht.docx"))
        pruefe(belegquelle.original_zu("kap", "KundeE/Bericht.pdf") is None,
               "12 Gegenprobe: ein ORDNER mit Office-Endung zaehlt nicht")
    finally:
        belegquelle.DOKUMENTE = alt
        shutil.rmtree(baum, ignore_errors=True)

    print("\n%d Fehler" % len(FEHLER))
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
