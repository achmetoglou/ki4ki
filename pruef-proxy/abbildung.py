"""Eine Abbildung freistellen - die Grafik, nicht die ganze Seite.

Zweck: eine einzelne Abbildung (Zeichnung/Diagramm) aus einer PDF-Seite
ausschneiden, damit sie direkt im Chat erscheinen kann - nicht die ganze
Seite. Eine Grafik im Antwortkontext ist verstaendlicher als ein blosser
Seitenverweis.

⛔ DER ERSTE GEDANKE WAR FALSCH: die eingebetteten Bilder mit pdfimages
   herausholen. Auf Seite 52 von DS-00-000 kommen dabei NEUN Teile heraus:

       929x656  <- die Zeichnung
       390x64   <- ein Beschriftungsstreifen
       773x28   <- noch einer
       289x79   <- ein Fragment
       … fuenf weitere

   Ein PDF setzt eine Abbildung aus mehreren Teilen zusammen. Blind das
   groesste zu nehmen geht meistens gut und manchmal schief - dann steht
   ein Legendenbalken im Chat, wo eine Zeichnung stehen sollte.

⭐ DER RICHTIGE WEG: pdftohtml -xml nennt zu jedem Teil seine POSITION.
   Teile, die sich beruehren, gehoeren zusammen. Aus der gerenderten Seite
   wird dann EIN zusammenhaengendes Stueck ausgeschnitten - Zeichnung
   samt Beschriftung, so wie es im Original aussieht.

       <image top="413" left="206" width="365" height="258" .../>
       <image top="440" left="177" width="114" height="31"  .../>
       …  ->  ein Kasten um alles herum

⚠ Gerechnet wird in den Koordinaten von pdftohtml und erst am Schluss in
  Bildpunkte umgerechnet. Die Seitengroesse steht im selben XML - sie
  einfach anzunehmen waere der naechste Rechenfehler.
"""
import os
import re
import subprocess
import tempfile

RAND = 8          # Punkte Luft um die Abbildung
NAH = 24          # Teile mit weniger Abstand gehoeren zusammen
MINDESTFLAECHE = 0.04   # kleiner als 4 % der Seite: kein eigenes Bild wert


def _kaesten(pdf, seite):
    """(Kaesten, Seitenbreite, Seitenhoehe) aus pdftohtml -xml."""
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run(
            ["pdftohtml", "-xml", "-f", str(seite), "-l", str(seite),
             pdf, os.path.join(tmp, "s")],
            capture_output=True, timeout=120)
        weg = os.path.join(tmp, "s.xml")
        if p.returncode != 0 or not os.path.exists(weg):
            return [], 0, 0
        xml = open(weg, encoding="utf-8", errors="replace").read()
    m = re.search(r'<page number="\d+"[^>]*height="(\d+)"\s+width="(\d+)"', xml)
    if not m:
        return [], 0, 0
    hoehe, breite = int(m.group(1)), int(m.group(2))
    kaesten = []
    for t in re.finditer(
            r'<image top="(-?\d+)" left="(-?\d+)" width="(\d+)" height="(\d+)"',
            xml):
        o, l, b, h = (int(x) for x in t.groups())
        if b < 8 or h < 8:
            continue
        kaesten.append((l, o, l + b, o + h))
    return kaesten, breite, hoehe


def _zusammenfassen(kaesten):
    """Teile, die sich beruehren oder nahe beieinanderliegen, buendeln."""
    haufen = []
    for k in kaesten:
        passend = []
        for h in haufen:
            if (k[0] < h[2] + NAH and k[2] > h[0] - NAH
                    and k[1] < h[3] + NAH and k[3] > h[1] - NAH):
                passend.append(h)
        neu = k
        for h in passend:
            haufen.remove(h)
            neu = (min(neu[0], h[0]), min(neu[1], h[1]),
                   max(neu[2], h[2]), max(neu[3], h[3]))
        haufen.append(neu)
    return haufen


def freistellen(pdf, seite, dpi=150):
    """Die groesste Abbildung der Seite als PNG - oder None.

    Rueckgabe: (bytes, (links, oben, rechts, unten)) oder (None, Grund)
    """
    kaesten, breite, hoehe = _kaesten(pdf, seite)
    if not kaesten:
        return None, "keine Abbildung auf dieser Seite"
    haufen = _zusammenfassen(kaesten)
    seitenflaeche = max(1, breite * hoehe)
    haufen.sort(key=lambda k: (k[2] - k[0]) * (k[3] - k[1]), reverse=True)
    l, o, r, u = haufen[0]
    if (r - l) * (u - o) < seitenflaeche * MINDESTFLAECHE:
        return None, "die groesste Abbildung ist zu klein (unter 4 % der Seite)"

    with tempfile.TemporaryDirectory() as tmp:
        stamm = os.path.join(tmp, "s")
        p = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-f", str(seite),
             "-l", str(seite), "-singlefile", pdf, stamm],
            capture_output=True, timeout=180)
        bild = stamm + ".png"
        if p.returncode != 0 or not os.path.exists(bild):
            return None, "Seite liess sich nicht rendern"
        from PIL import Image
        im = Image.open(bild)
        # ⚠ Umrechnen ERST hier, und mit der Seitengroesse aus DEMSELBEN
        #   XML. Die Seitengroesse anzunehmen waere der naechste Rechenfehler.
        sx = im.width / float(breite)
        sy = im.height / float(hoehe)
        # ⚠ WAAGERECHT die ganze Seitenbreite nehmen, nicht nur den
        #   Bildkasten. Die Beschriftungen einer technischen Zeichnung
        #   ("Aussenzylinder", "Verdraengerkoerper") sind TEXT, kein Bild -
        #   sie stehen also nicht in den Bildkaesten. Beim ersten Versuch
        #   war die Zeichnung da, aber links stand nur noch "…nder".
        #   Senkrecht wird geschnitten, waagerecht nicht.
        kasten = (0,
                  max(0, int((o - RAND) * sy)),
                  im.width,
                  min(im.height, int((u + RAND) * sy)))
        aus = im.crop(kasten)
        # Den weissen Rand wegnehmen, der dadurch entsteht - so sitzt die
        # Abbildung wieder eng im Bild, ohne dass etwas fehlt.
        try:
            from PIL import ImageChops, Image as _I
            grau = aus.convert("L")
            weiss = _I.new("L", grau.size, 255)
            rand = ImageChops.difference(grau, weiss).getbbox()
            if rand:
                aus = aus.crop((max(0, rand[0] - 6), max(0, rand[1] - 6),
                                min(aus.width, rand[2] + 6),
                                min(aus.height, rand[3] + 6)))
        except Exception:
            pass
        import io
        speicher = io.BytesIO()
        aus.save(speicher, "PNG", optimize=True)
        return speicher.getvalue(), kasten


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else \
        "/daten/pdfs/ikv-wissen-konfidenz/archiv/DS-00-000.pdf"
    seiten = [int(x) for x in sys.argv[2:]] or [52, 58, 51, 99, 1]
    print("=== %s" % pdf)
    for s in seiten:
        daten, was = freistellen(pdf, s)
        if daten:
            l, o, r, u = was
            print("   Seite %-4d %7.1f KB   Ausschnitt %dx%d Punkte"
                  % (s, len(daten) / 1024.0, r - l, u - o))
            with open("/tmp/abb-%d.png" % s, "wb") as f:
                f.write(daten)
        else:
            print("   Seite %-4d -" % s, was)


def hat_abbildung(pdf, seite):
    """Gibt es auf dieser Seite ueberhaupt eine Abbildung?

    ⚠ Billig: Die Seite wird NICHT gerendert, es reicht die Liste der
      Bildkaesten (0,04 bis 0,6 s gemessen). Deshalb laesst sich das beim
      Antworten pruefen - und im Chat steht nie ein kaputtes Bildsymbol.
    """
    try:
        kaesten, breite, hoehe = _kaesten(pdf, seite)
        if not kaesten:
            return False
        flaeche = max(1, breite * hoehe)
        for k in _zusammenfassen(kaesten):
            if (k[2] - k[0]) * (k[3] - k[1]) >= flaeche * MINDESTFLAECHE:
                return True
    except Exception:
        pass
    return False
