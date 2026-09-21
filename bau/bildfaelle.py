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

def _graustufenbild(breite_px, hoehe_px, hell, streu=0):
    """Graustufenbild als PDF-Objektinhalt.

    Mit streu > 0 bekommt das Bild Struktur statt einer einfarbigen
    Flaeche. Das ist nicht Kosmetik: In der ersten Fassung waren alle
    Bilder einfarbig grau, und das Layout-Modell hat die ganze Seite als
    EINE Bildregion gelesen - auch im Fall, wo fuenf getrennte Icons
    erwartet waren. Ein Versuch mit unrealistischen Vorlagen misst das
    Modell nicht, sondern die Vorlage.
    """
    if not streu:
        roh = bytes([hell]) * (breite_px * hoehe_px)
    else:
        werte = bytearray()
        zahl = 12345
        for y in range(hoehe_px):
            for x in range(breite_px):
                zahl = (1103515245 * zahl + 12345) % 2147483648
                rand = (zahl >> 16) % (2 * streu + 1) - streu
                # zusaetzlich ein Muster, damit Kanten und Linien entstehen
                muster = 40 if (x // 3 + y // 3) % 2 else 0
                werte.append(max(0, min(255, hell + rand + muster)))
        roh = bytes(werte)
    return zlib.compress(roh)


def baue_pdf(pfad, bilder, texte):
    """bilder: Liste (x, y, breite, hoehe, helligkeit) in Punkten.
    texte:  Liste (x, y, zeichenkette)."""
    objekte = []          # jeweils fertige Bytes ohne "N 0 obj"/"endobj"
    bildnamen = []

    for nr, (_x, _y, _b, _h, hell) in enumerate(bilder):
        daten = _graustufenbild(48, 48, hell, streu=30)
        objekte.append(
            b"<< /Type /XObject /Subtype /Image /Width 48 /Height 48"
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


ZEILE = ("Die Instandhaltung der Anlage folgt einem festen Ablauf. Nach dem "
         "Erkennen der Stoerung wird die Ursache eingegrenzt und das "
         "betroffene Bauteil geprueft. Die Messwerte sind zu dokumentieren.")


def fliesstext(von_y, bis_y, x=90, schritt=15, aussparen=()):
    """Zeilen Fliesstext, damit die Seite wie ein echtes Dokument aussieht.

    Ohne das bestand die erste Fassung aus grauen Quadraten und drei
    Zeilen - das Layout-Modell las darin EINE grosse Bildregion, auch wo
    fuenf getrennte Icons standen. Der Versuch mass damit die Vorlage,
    nicht das Modell.

    aussparen: Liste (y_unten, y_oben), in denen keine Zeile gesetzt wird.
    """
    zeilen = []
    y = von_y
    n = 0
    while y > bis_y:
        if not any(u - 6 <= y <= o + 6 for u, o in aussparen):
            teil = ZEILE[(n * 37) % 90:][:78]
            zeilen.append((x, y, teil or ZEILE[:78]))
        y -= schritt
        n += 1
    return zeilen


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
    unten, oben = 300, 300 + 6 * k
    texte = ([(100, 260, "Abbildung 1: Messaufbau, aus Kacheln zusammengesetzt")]
             + fliesstext(790, 270, aussparen=((unten - 10, oben + 10),)))
    ergebnis.append(("1-kachelbild", bilder, texte,
                     "1 Abbildung mit rund 36 %, NICHT 36 Abbildungen mit je 1 %"))

    # 2 - Infografik: Block aus Ueberschrift, drei Icons, Text
    k2 = kante(0.01)
    bilder = [(120 + i * (k2 + 40), 520, k2, k2, 80 + i * 40) for i in range(3)]
    texte = ([(120, 620, "Ablauf der Stoerungsbehebung"),
              (120, 500, "Schritt 1                Schritt 2                Schritt 3"),
              (120, 480, "Anlage pruefen     Fehler eingrenzen     Teil tauschen")]
             + fliesstext(790, 650) + fliesstext(450, 80))
    ergebnis.append(("2-infografik", bilder, texte,
                     "1 Abbildung (der ganze Block) oder 3 kleine? Das ist die Frage"))

    # 3 - fuenf verstreute Icons zwischen Text (Gegenprobe)
    k3 = kante(0.01)
    bilder = [(90, 700 - i * 130, k3, k3, 70 + i * 30) for i in range(5)]
    texte = []
    for i in range(5):
        kopf_y = 700 - i * 130 + k3
        texte.append((90, kopf_y + 22, "%d. Abschnitt der Pruefanweisung" % (i + 1)))
        # Fliesstext RECHTS vom Icon und darunter - so sieht ein Absatz mit
        # Randzeichen aus, und die Icons sind durch Text getrennt.
        texte += fliesstext(kopf_y, kopf_y - 95, x=160, schritt=16)
    ergebnis.append(("3-verstreut", bilder, texte,
                     "5 einzelne Abbildungen - hier waere Zusammenfassen FALSCH"))

    # 4 - Kontrolle
    k4 = kante(0.30)
    texte4 = ([(120, 260, "Abbildung 4: Uebersichtsaufnahme")]
              + fliesstext(790, 270, aussparen=((290, 300 + k4 + 10),)))
    ergebnis.append(("4-einzelgross", [(120, 300, k4, k4, 110)], texte4,
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
    gefunden = {}
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
        gefunden[name] = anteile
        ueber = sum(1 for a in anteile if a >= SCHWELLE)
        print("  Docling sieht: %d Abbildungen%s"
              % (len(anteile),
                 (" mit " + ", ".join("%.1f %%" % (a * 100) for a in sorted(anteile, reverse=True)[:8]))
                 if anteile else ""))
        print("  davon beschrieben: %d von %d%s\n"
              % (ueber, len(anteile),
                 "   ⛔ NICHTS wird beschrieben" if anteile and ueber == 0 else ""))
    # ---- Gueltigkeit des Versuchs, bevor irgendetwas gedeutet wird ----
    # Die erste Fassung lieferte bei Fall 3 eine Abbildung statt fuenf. Das
    # stand nur in der Lesehilfe und haette beim Ueberfliegen wie ein
    # Ergebnis ausgesehen. Der Versuch beurteilt sich jetzt selbst.
    print("=" * 66)
    verstreut = gefunden.get("3-verstreut") or []
    kontrolle = gefunden.get("4-einzelgross") or []
    maengel = []
    if len(kontrolle) != 1:
        maengel.append("Fall 4 (Kontrolle) ergab %d Abbildungen statt genau 1"
                       % len(kontrolle))
    elif not (0.24 <= kontrolle[0] <= 0.36):
        maengel.append("Fall 4 ergab %.1f %% statt rund 30 %%"
                       % (100 * kontrolle[0]))
    if len(verstreut) < 4:
        maengel.append("Fall 3 (Gegenprobe) ergab %d Abbildungen statt 5 -"
                       " Docling fasst hier zusammen, wo Trennen richtig waere"
                       % len(verstreut))

    if maengel:
        print("⛔ DER VERSUCH IST UNGUELTIG. Nichts davon deuten.")
        for m in maengel:
            print("   - %s" % m)
        print("\n   Warum das zaehlt: Wenn die Gegenprobe zusammenfasst, wo"
              " Trennen richtig waere,\n   dann ist auch das Ergebnis von Fall 1"
              " (\"1 grosse Abbildung\") kein Befund\n   ueber Kacheln, sondern"
              " dasselbe Verhalten. Die Frage bleibt offen.")
        return 1

    print("✓ Der Versuch ist gueltig: Kontrolle stimmt, und die Gegenprobe"
          " trennt,\n  wo Trennen richtig ist. Erst damit sagen Fall 1 und 2"
          " etwas aus.\n")
    kachel = gefunden.get("1-kachelbild") or []
    if len(kachel) == 1 and kachel[0] >= SCHWELLE:
        print("Fall 1: Ein zerlegtes Bild wird als EINE grosse Abbildung"
              " erkannt und beschrieben.\n        Zerlegte Bilder fallen also"
              " NICHT durch die Schwelle.")
    else:
        print("⛔ Fall 1: Ein zerlegtes Bild zerfaellt in %d Abbildungen."
              " Jedes gekachelte Bild\n   im Bestand faellt damit durch die"
              " Schwelle - unabhaengig von seiner wahren Groesse." % len(kachel))

    grafik = gefunden.get("2-infografik") or []
    beschrieben = sum(1 for a in grafik if a >= SCHWELLE)
    if beschrieben:
        print("Fall 2: Die Icons werden mit dem Block zusammen erkannt und"
              " beschrieben.")
    else:
        print("⛔ Fall 2: Der Infografik-Block ergibt %d Abbildung(en) mit"
              " %s - nichts davon\n   wird beschrieben. Icons in Infografiken"
              " fallen durch die Schwelle."
              % (len(grafik),
                 ", ".join("%.1f %%" % (100 * a) for a in grafik) or "keiner"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
