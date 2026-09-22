#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Welche Dateiformate liegen im Bestand - und welchen Weg nehmen sie?

⛔ Gibt AUSSCHLIESSLICH Endungen und Anzahlen aus. Keine Datei- und keine
   Ordnernamen. Mit der Datensperre vereinbar.

Warum das vor dem KAP-Lauf zu wissen ist: Die Weichenkette in Ablaufplan 2
endet mit "sonst -> Tika". Alles, was nicht PDF, CSV, HTML, Excel, Text,
Word oder Praesentation ist, geht also an Tika - ungefragt und ohne
Meldung. Fuer .msg ist das richtig und gewollt. Fuer ein ZIP, eine
CAD-Zeichnung oder ein Foto kommt dabei leerer oder unbrauchbarer Text
heraus, und das Dokument landet trotzdem im Bestand.

Diese Messung sagt, WIE VIELE Dateien das betrifft - vorher, nicht nachher.

  python3 bau/formate-zaehlen.py
"""
import os
import sys

# Genau die Zuordnung aus dem Knoten "Dateien klassifizieren".
WEGE = {
    "pdf": "Docling",
    "csv": "Text", "txt": "Text", "html": "Text", "htm": "Text",
    "xlsx": "Excel", "xls": "Excel",
    "doc": "Office->PDF", "docx": "Office->PDF", "odt": "Office->PDF",
    "rtf": "Office->PDF",
    "ppt": "Office->PDF", "pptx": "Office->PDF", "odp": "Office->PDF",
}
# Was Tika zwar annimmt, aber wofuer kein brauchbarer Text herauskommt.
OHNE_TEXT = {"zip", "rar", "7z", "gz", "tar", "exe", "dll", "bin",
             "dwg", "dxf", "stp", "step", "igs", "iges", "stl", "sldprt",
             "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "heic",
             "mp4", "mov", "avi", "wav", "mp3", "db", "lnk", "url"}
STEUER = {"bereich.json", "metadaten.json", "prompt.md", "kategorien.txt",
          "bilder-nachholen.txt", "aussortiert.log", "loeschen.log"}


def main():
    wurzel = os.environ.get("KI4KI_PDFS") or os.path.expanduser("~/ki4ki/dokumente")
    if not os.path.isdir(wurzel):
        print("Bestand fehlt: %s - DIE MESSUNG IST UNGUELTIG" % wurzel)
        return 1

    zaehler = {}
    ohne_endung = 0
    dateien = 0
    for ordner, _u, namen in os.walk(wurzel):
        for n in namen:
            if n in STEUER or n.startswith(".") or n.endswith(".log"):
                continue
            dateien += 1
            stamm, punkt, endung = n.rpartition(".")
            if not punkt:
                ohne_endung += 1
                continue
            zaehler[endung.lower()] = zaehler.get(endung.lower(), 0) + 1

    gruppen = {}
    for endung, anzahl in zaehler.items():
        weg = WEGE.get(endung) or ("Tika (ohne Text)" if endung in OHNE_TEXT
                                   else "Tika (Rueckfall)")
        gruppen.setdefault(weg, []).append((anzahl, endung))

    print("Dateien insgesamt: %d   (ohne Endung: %d)\n" % (dateien, ohne_endung))
    reihenfolge = ["Docling", "Office->PDF", "Excel", "Text",
                   "Tika (Rueckfall)", "Tika (ohne Text)"]
    for weg in reihenfolge:
        eintraege = sorted(gruppen.get(weg, []), reverse=True)
        summe = sum(a for a, _e in eintraege)
        if not eintraege:
            continue
        print("%-18s %6d  %s" % (weg, summe,
                                 ", ".join("%s: %d" % (e, a)
                                           for a, e in eintraege[:12])))

    tika = sum(a for a, _e in gruppen.get("Tika (Rueckfall)", []))
    stumm = sum(a for a, _e in gruppen.get("Tika (ohne Text)", []))
    print()
    # ⛔ Beide Gruppen gehen an Tika, sind aber NICHT dasselbe: Aus der
    #   einen kommt Text (.msg, .eml), aus der anderen nicht (Archive,
    #   CAD, Bilder). Sie zusammenzuzaehlen oder die eine als Teilmenge
    #   der anderen auszuweisen waere eine falsche Zahl - und eine
    #   falsche Zahl ist schlimmer als keine.
    print("An Tika gehen insgesamt: %d Dateien" % (tika + stumm))
    print("  davon mit verwertbarem Text (z.B. .msg, .eml): %d" % tika)
    print("  davon ohne verwertbaren Text (Archive, CAD, Bilder): %d" % stumm)
    if stumm:
        print("⛔ Die %d ohne Text landen trotzdem im Bestand - als "
              "Dokumente ohne Inhalt." % stumm)
    else:
        print("⭐ Keine Datei darunter, aus der kein Text kommen kann.")

    # ⛔ Gegenprobe: Die Messung sagt nur etwas, wenn ueberhaupt etwas
    #   ausserhalb der bekannten Wege liegt. Ist alles bekannt, gibt es
    #   nichts zu entscheiden - und das gehoert dann auch dagestanden,
    #   statt als "alles gut" gelesen zu werden.
    if not tika and not stumm:
        print("\n⚠ Es liegt NICHTS ausserhalb der bekannten Wege. Diese "
              "Messung trifft hier also keine Aussage ueber .msg - dann ist "
              "im gemessenen Ordner keine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
