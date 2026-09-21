"""Vier kontrollierte Faelle: Was sieht Docling als EINE Abbildung?

Anlass ist eine Frage von Emrach (21.09.), die eine stillschweigende
Annahme der Bildmessung trifft:

  "Bei manchen PDF besteht ein Bild aus mehreren kleinen Boxen. Wenn die
   Schwelle dort ueberspringt, haben wir das Bild nicht. Und eine
   Infografik kann kleine Bilder wie Icons enthalten - wird das auch
   uebersprungen?"

Die Schwelle picture_description_area_threshold arbeitet mit der Flaeche
einer erkannten Abbildung. Ob ein zerlegtes Bild EINE grosse oder viele
kleine Abbildungen ergibt, entscheidet also darueber, ob es beschrieben
wird oder stillschweigend durchfaellt.

Die Messdaten vom 21.09. legen nahe, dass Docling visuell arbeitet und
zusammenfasst: ein Dokument mit 5.110 eingebetteten Bildobjekten ergab
89 Abbildungen, davon 85 UEBER der Schwelle. Das ist ein Indiz, kein
Beweis - der Fall war nicht gebaut, sondern gefunden. Diese Datei baut
ihn nach, mit exakt bekannten Groessen.

Die vier Faelle und was sie unterscheiden sollen:

  1 kachelbild    Ein grosses Bild (36 Prozent der Seite), zerlegt in
                  6 x 6 = 36 Kacheln zu je 1 Prozent.
                  Erkennt Docling 1 Abbildung (36 Prozent) oder 36 (je 1)?
                  Bei 36 einzelnen faellt das ganze Bild unter die Schwelle.

  2 infografik    Ein zusammenhaengender Block mit Ueberschrift, drei
                  kleinen Icons zu je 1 Prozent und Text - wie eine
                  Infografik. Eine Abbildung oder drei?

  3 verstreut     Fuenf einzelne Icons zu je 1 Prozent, ueber die Seite
                  zwischen Textabsaetzen verteilt. Hier ist EINZELN die
                  richtige Antwort - dieser Fall ist die Gegenprobe zu
                  Fall 2, damit "Docling fasst immer zusammen" nicht
                  unwiderlegbar ist.

  4 einzelgross   Ein einzelnes Bild zu 30 Prozent. Kontrolle: Wenn hier
                  nicht genau 1 Abbildung ueber der Schwelle herauskommt,
                  stimmt an der Messung etwas nicht.

Aufruf: erzeugt die PDF, misst sie und gibt aus, was gefunden wurde.

    cd ~/ki4ki
    docker exec -i ki4ki-pruef-proxy python3 - < bau/bildfaelle.py

Braucht KEINE Bibliothek ausser der Standardbibliothek - die PDF werden
von Hand geschrieben, damit das Skript ueberall laeuft.
"""
import json
import os
import sys
import urllib.request
import uuid
import zlib

DOCLING = os.environ.get("DOCLING", "http://docling:5001/v1/convert/file")
ZEITLIMIT = int(os.environ.get("ZEITLIMIT", "300"))
SCHWELLE = float(os.environ.get("SCHWELLE", "0.08"))
ZIEL = os.environ.get("ZIEL", "/tmp/bildfaelle")

BREITE, HOEHE = 595.0, 842.0        # A4 in Punkten
SEITE = BREITE * HOEHE


# --------------------------------------------------------------------------
# PDF von Hand bauen. Kein reportlab, damit es im Container ohne
# Zusatzpaket laeuft.
# --------------------------------------------------------------------------

def _graustufenbild(breite_px, hoehe_px, hell):
    """Ein einfarbiges Graustufenbild als PDF-Objekt-Inhalt."""
    roh = bytes([hell]) * (breite_px * hoehe_px)
    return zlib.compress(roh)


def baue_pdf(pfad, bilder, texte):
    """bilder: Liste (x, y, breite, hoehe, helligkeit) in Punkten.
    texte:  Liste (x, y, zeichenkette)."""
    objekte = []          # jeweils fertige Bytes ohne "N 0 obj"/"endobj"
    bildnamen = []

    for nr, (_x, _y, _b, _h, hell) in enumerate(bilder):
        daten = _graustufenbild(24, 24, hell)
        objekte.append(
            b"<< /Type /XObject /Subtype /Image /Width 24 /Height 24"
            b" /ColorSpace /DeviceGray /BitsPerComponent 8"
            b" /Filter /FlateDecode /Length " + str(len(daten)).encode() +
            b" >>\nstream\n" + daten + b"\nendstream")
        bildnamen.append("Bi%d" % nr)

    strom = []
    for (x, y, b, h, _hell), name in zip(bilder, bildnamen):
        strom.append("q %.2f 0 0 %.2f %.2f %.2f cm /%s Do Q"
                     % (b, h, x, y, name))
    for x, y, s in texte:
        sicher = s.replace("\\", "").replace("(", "").replace(")", "")
        strom.append("BT /F1 11 Tf %.2f %.2f Td (%s) Tj ET" % (x, y, sicher))
    inhalt = "\n".join(strom).encode("latin-1", "replace")
    objekte.append(b"<< /Length " + str(len(inhalt)).encode() + b" >>\nstream\n"
                   + inhalt + b"\nendstream")
    inhalt_nr = len(objekte)

    xobj = " ".join("/%s %d 0 R" % (n, i + 1) for i, n in enumerate(bildnamen))
    objekte.append(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.0f %.0f]"
                    " /Resources << /XObject << %s >> /Font << /F1 %d 0 R >> >>"
                    " /Contents %d 0 R >>"
                    % (inhalt_nr + 2, BREITE, HOEHE, xobj, inhalt_nr + 4,
                       inhalt_nr)).encode())
    seite_nr = len(objekte)
    objekte.append(("<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % seite_nr).encode())
    seiten_nr = len(objekte)
    objekte.append(("<< /Type /Catalog /Pages %d 0 R >>" % seiten_nr).encode())
    katalog_nr = len(objekte)
    objekte.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    aus = [b"%PDF-1.4\n"]
    stellen = []
    stand = len(aus[0])
    for i, koerper in enumerate(objekte, 1):
        stueck = ("%d 0 obj\n" % i).encode() + koerper + b"\nendobj\n"
        stellen.append(stand)
        aus.append(stueck)
        stand += len(stueck)
    xref = stand
    tabelle = [b"xref\n", ("0 %d\n" % (len(objekte) + 1)).encode(),
               b"0000000000 65535 f \n"]
    for s in stellen:
        tabelle.append(("%010d 00000 n \n" % s).encode())
    tabelle.append(("trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                    % (len(objekte) + 1, katalog_nr, xref)).encode())
    with open(pfad, "wb") as f:
        f.write(b"".join(aus + tabelle))


def kante(anteil):
    """Kantenlaenge eines Quadrats mit diesem Flaechenanteil."""
    return (anteil * SEITE) ** 0.5


def faelle():
    """(name, bilder, texte, erwartung) fuer die vier Faelle."""
    ergebnis = []

    # 1 - ein grosses Bild, in 36 Kacheln zerlegt
    k = kante(0.36) / 6.0
    bilder = []
    for zeile in range(6):
        for spalte in range(6):
            bilder.append((100 + spalte * k, 300 + zeile * k, k, k,
                           60 + (zeile * 6 + spalte) * 3))
    ergebnis.append(("1-kachelbild", bilder,
                     [(100, 260, "Abbildung 1: Messaufbau, aus Kacheln zusammengesetzt")],
                     "1 Abbildung mit rund 36 %, NICHT 36 Abbildungen mit je 1 %"))

    # 2 - Infografik: Block aus Ueberschrift, drei Icons, Text
    k2 = kante(0.01)
    bilder = [(120 + i * (k2 + 40), 520, k2, k2, 80 + i * 40) for i in range(3)]
    texte = [(120, 620, "Ablauf der Stoerungsbehebung"),
             (120, 500, "Schritt 1                Schritt 2                Schritt 3"),
             (120, 480, "Anlage pruefen     Fehler eingrenzen     Teil tauschen")]
    ergebnis.append(("2-infografik", bilder, texte,
                     "1 Abbildung (der ganze Block) oder 3 kleine? Das ist die Frage"))

    # 3 - fuenf verstreute Icons zwischen Text (Gegenprobe)
    k3 = kante(0.01)
    bilder = [(90, 700 - i * 130, k3, k3, 70 + i * 30) for i in range(5)]
    texte = [(160, 700 - i * 130 + k3 / 2,
              "Absatz %d - Hinweiszeichen am Rand, gehoert nicht zusammen" % (i + 1))
             for i in range(5)]
    ergebnis.append(("3-verstreut", bilder, texte,
                     "5 einzelne Abbildungen - hier waere Zusammenfassen FALSCH"))

    # 4 - Kontrolle
    k4 = kante(0.30)
    ergebnis.append(("4-einzelgross", [(120, 300, k4, k4, 110)],
                     [(120, 260, "Abbildung 4: Uebersichtsaufnahme")],
                     "genau 1 Abbildung mit rund 30 %"))
    return ergebnis


def _multipart(pfad, felder):
    grenze = "----ki4ki" + uuid.uuid4().hex
    teile = []
    for name, wert in felder:
        teile.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (grenze, name, wert)).encode("utf-8"))
    with open(pfad, "rb") as f:
        inhalt = f.read()
    teile.append(("--%s\r\nContent-Disposition: form-data; name=\"files\";"
                  " filename=\"fall.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
                  % grenze).encode("utf-8"))
    teile.append(inhalt)
    teile.append(("\r\n--%s--\r\n" % grenze).encode("utf-8"))
    return b"".join(teile), "multipart/form-data; boundary=%s" % grenze


def messe(pfad):
    felder = [("to_formats", "json"), ("do_picture_description", "false"),
              ("do_picture_classification", "false"),
              ("do_formula_enrichment", "false"), ("do_table_structure", "false"),
              ("do_ocr", "false")]
    koerper, typ = _multipart(pfad, felder)
    anfrage = urllib.request.Request(DOCLING, data=koerper,
                                     headers={"Content-Type": typ})
    with urllib.request.urlopen(anfrage, timeout=ZEITLIMIT) as antwort:
        roh = json.loads(antwort.read().decode("utf-8"))
    dok = (roh.get("document") or {}).get("json_content")
    if not isinstance(dok, dict):
        return None
    seiten = {}
    for nr, seite in (dok.get("pages") or {}).items():
        g = (seite or {}).get("size") or {}
        try:
            seiten[str(nr)] = float(g["width"]) * float(g["height"])
        except (KeyError, TypeError, ValueError):
            continue
    anteile = []
    for bild in (dok.get("pictures") or []):
        for prov in (bild.get("prov") or [])[:1]:
            kasten = prov.get("bbox") or {}
            flaeche = seiten.get(str(prov.get("page_no")))
            if not flaeche:
                continue
            try:
                b = abs(float(kasten["r"]) - float(kasten["l"]))
                h = abs(float(kasten["t"]) - float(kasten["b"]))
            except (KeyError, TypeError, ValueError):
                continue
            anteile.append(b * h / flaeche)
    return anteile


def main():
    os.makedirs(ZIEL, exist_ok=True)
    print("Vier kontrollierte Faelle, Schwelle %.2f\n" % SCHWELLE)
    for name, bilder, texte, erwartung in faelle():
        pfad = os.path.join(ZIEL, name + ".pdf")
        baue_pdf(pfad, bilder, texte)
        print("%s" % name)
        print("  eingebaut:  %d Bildobjekte" % len(bilder))
        print("  erwartet:   %s" % erwartung)
        try:
            anteile = messe(pfad)
        except Exception as f:
            print("  FEHLER: %s\n" % f)
            continue
        if anteile is None:
            print("  FEHLER: Docling lieferte keine JSON-Fassung\n")
            continue
        ueber = sum(1 for a in anteile if a >= SCHWELLE)
        print("  Docling sieht: %d Abbildungen%s"
              % (len(anteile),
                 (" mit " + ", ".join("%.1f %%" % (a * 100) for a in sorted(anteile, reverse=True)[:8]))
                 if anteile else ""))
        print("  davon beschrieben: %d von %d%s\n"
              % (ueber, len(anteile),
                 "   ⛔ NICHTS wird beschrieben" if anteile and ueber == 0 else ""))
    print("Lesehilfe:")
    print("  Fall 1 muss 1 grosse Abbildung ergeben. Ergibt er 36 kleine,"
          " faellt jedes zerlegte Bild im Bestand durch die Schwelle.")
    print("  Fall 2 sagt, ob Icons in einer Infografik mit dem Block"
          " zusammen erkannt werden oder einzeln durchfallen.")
    print("  Fall 3 muss 5 einzelne ergeben - sonst fasst Docling immer"
          " zusammen und Fall 1 und 2 haetten nichts bewiesen.")
    print("  Fall 4 muss genau 1 ergeben. Tut er das nicht, stimmt die"
          " Messung nicht und die anderen drei sind wertlos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
