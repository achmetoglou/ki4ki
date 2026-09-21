"""Dieselbe Messung wie bildflaechen.py - aber mit Doclings eigenen Augen.

Warum es diese zweite Messung braucht: bildflaechen.py zaehlt ueber
pdfimages nur EINGEBETTETE RASTERBILDER. Eine technische Zeichnung ist im
PDF aber oft eine Ansammlung von Linien und hat gar kein Rasterbild -
pdfimages sieht sie nicht, Docling erkennt sie sehr wohl als Abbildung.
Fuer UC 1 (Stoerfallassistenz) sind Zeichnungen das Wertvollste, also ist
genau diese Luecke die wichtige.

Hier wird deshalb gefragt, was DOCLING sieht - und zwar mit derselben
Rechnung, die Docling intern fuer picture_description_area_threshold
benutzt: Flaeche des Bildrahmens geteilt durch Seitenflaeche.

Bildbeschreibung und Texterkennung sind ABGESCHALTET. Es geht nur um
Erkennen und Vermessen, nicht um Beschreiben - deshalb kein Sprachmodell,
keine GPU-Last durch Beschreibungen und kein langer Lauf.

Dieselbe Stichprobe wie bildflaechen.py (gleicher Startwert), damit sich
die beiden Ergebnisse direkt gegenueberstellen lassen.

Gibt AUSSCHLIESSLICH Zahlen aus - keine Dateinamen, keine Inhalte.

Aufruf:
    cd ~/ki4ki
    docker exec -i ki4ki-pruef-proxy python3 - < bau/bildflaechen_docling.py

Weniger/mehr Dokumente, laengeres Zeitlimit:
    docker exec -e ANZAHL=5 -e ZEITLIMIT=600 -i ki4ki-pruef-proxy \\
        python3 - < bau/bildflaechen_docling.py
"""
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

WURZEL = os.environ.get("WURZEL", "/daten/pdfs")
ANZAHL = int(os.environ.get("ANZAHL", "10"))
SCHWELLE = float(os.environ.get("SCHWELLE", "0.08"))
ZEITLIMIT = int(os.environ.get("ZEITLIMIT", "300"))
DOCLING = os.environ.get("DOCLING", "http://docling:5001/v1/convert/file")
SEKUNDEN_JE_BILD = 3.3

_SEITE = re.compile(r"Page size:\s+([0-9.]+) x ([0-9.]+)")


def raster_bilder(pfad):
    """Wie viele eingebettete Rasterbilder hat die Datei (pdfimages-Sicht)."""
    try:
        aus = subprocess.run(["pdfimages", "-list", pfad], capture_output=True,
                             text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return sum(1 for z in aus.splitlines()[2:]
               if len(z.split()) >= 14 and z.split()[2] in ("image", "smask", "stencil"))


def _multipart(pfad, felder):
    """Sendekoerper fuer multipart/form-data von Hand - keine Fremdpakete."""
    grenze = "----ki4ki" + uuid.uuid4().hex
    teile = []
    for name, wert in felder:
        teile.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (grenze, name, wert)).encode("utf-8"))
    with open(pfad, "rb") as f:
        inhalt = f.read()
    teile.append(("--%s\r\nContent-Disposition: form-data; name=\"files\";"
                  " filename=\"probe.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
                  % grenze).encode("utf-8"))
    teile.append(inhalt)
    teile.append(("\r\n--%s--\r\n" % grenze).encode("utf-8"))
    return b"".join(teile), "multipart/form-data; boundary=%s" % grenze


def docling_bilder(pfad):
    """Flaechenanteile aller von Docling erkannten Abbildungen.

    Rueckgabe: (anteile, sekunden) oder (None, sekunden) bei Fehler.
    """
    felder = [
        ("to_formats", "json"),
        ("do_picture_description", "false"),   # kein Modell, nur erkennen
        ("do_picture_classification", "false"),
        ("do_formula_enrichment", "false"),
        ("do_table_structure", "false"),
        ("do_ocr", "false"),                   # Tempo; aendert das Layout nicht
    ]
    koerper, typ = _multipart(pfad, felder)
    anfrage = urllib.request.Request(DOCLING, data=koerper,
                                     headers={"Content-Type": typ})
    start = time.time()
    try:
        with urllib.request.urlopen(anfrage, timeout=ZEITLIMIT) as antwort:
            roh = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as f:
        return None, time.time() - start, str(f.__class__.__name__)
    dauer = time.time() - start

    dok = (roh.get("document") or {}).get("json_content")
    if not isinstance(dok, dict):
        return None, dauer, "keine JSON-Fassung in der Antwort"

    seiten = {}
    for nr, seite in (dok.get("pages") or {}).items():
        groesse = (seite or {}).get("size") or {}
        try:
            seiten[str(nr)] = float(groesse["width"]) * float(groesse["height"])
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
                breite = abs(float(kasten["r"]) - float(kasten["l"]))
                hoehe = abs(float(kasten["t"]) - float(kasten["b"]))
            except (KeyError, TypeError, ValueError):
                continue
            anteile.append(breite * hoehe / flaeche)
    return anteile, dauer, None


def main():
    if not os.path.isdir(WURZEL):
        print("Wurzel fehlt - nichts gemessen.")
        return 1
    alle = []
    for ordner, _u, namen in os.walk(WURZEL):
        for n in namen:
            if n.lower().endswith(".pdf"):
                alle.append(os.path.join(ordner, n))
    if not alle:
        print("Keine PDF gefunden - nichts gemessen.")
        return 1

    # Praefix-stabil mischen statt sample(): So ist die Auswahl bei ANZAHL=10
    # garantiert der Anfang der Auswahl bei ANZAHL=200, und zwei Laeufe mit
    # verschiedener Groesse bleiben vergleichbar. random.sample(alle, k) gibt
    # diese Zusicherung NICHT - bei anderem k kommt eine andere Menge heraus.
    gemischt = sorted(alle)          # stabile Ausgangsordnung, unabhaengig vom Dateisystem
    random.seed(20260921)
    random.shuffle(gemischt)
    probe = gemischt[:ANZAHL]

    print("Docling-Sicht auf %d Dokumente (von %d PDF im Bestand)"
          % (len(probe), len(alle)))
    print("Bildbeschreibung und Texterkennung sind abgeschaltet -"
          " es geht nur ums Erkennen und Vermessen.\n")

    treppe = [0] * 6
    ueber = unter = 0
    d_gesamt = r_gesamt = 0
    fehler = 0
    zeiten = []
    je_dokument = []

    for i, p in enumerate(probe, 1):
        anteile, dauer, panne = docling_bilder(p)
        zeiten.append(dauer)
        if anteile is None:
            fehler += 1
            print("  %2d/%d  FEHLER nach %.0f s: %s" % (i, len(probe), dauer, panne))
            continue
        raster = raster_bilder(p)
        d_gesamt += len(anteile)
        r_gesamt += raster or 0
        klein = sum(1 for a in anteile if a < SCHWELLE)
        je_dokument.append(klein)
        for a in anteile:
            if a >= SCHWELLE:
                ueber += 1
            else:
                unter += 1
            for k, grenze in enumerate((0.01, 0.02, 0.04, 0.08, 0.16)):
                if a < grenze:
                    treppe[k] += 1
                    break
            else:
                treppe[5] += 1
        print("  %2d/%d  %5.0f s · Docling sieht %4d Abbildungen · pdfimages"
              " %4d Rasterbilder · davon unter der Schwelle %4d"
              % (i, len(probe), dauer, len(anteile),
                 raster if raster is not None else -1, klein))

    gesamt = ueber + unter
    print("\n%d Dokumente gemessen, %d Fehler, im Schnitt %.0f s je Dokument"
          % (len(probe) - fehler, fehler,
             sum(zeiten) / len(zeiten) if zeiten else 0))
    if gesamt == 0:
        print("Docling hat keine Abbildungen gefunden.")
        return 0

    print("\n⭐ Die Frage, um die es geht - sieht Docling mehr als pdfimages?")
    print("  Docling:   %5d Abbildungen" % d_gesamt)
    print("  pdfimages: %5d Rasterbilder" % r_gesamt)
    unterschied = d_gesamt - r_gesamt
    print("  Unterschied: %+d" % unterschied)
    if unterschied > 0:
        print("  -> Docling erkennt MEHR. Die Differenz sind Abbildungen ohne"
              " eingebettetes Rasterbild, also Zeichnungen und Vektorgrafiken."
              " Genau die, die der ersten Messung entgangen sind.")
    elif unterschied < 0:
        print("  -> pdfimages zaehlt mehr. Das spricht fuer zerlegte Bilder:"
              " Docling fasst viele Kacheln zu EINER Abbildung zusammen.")
    else:
        print("  -> gleich viele. Keine Vektorgrafiken in dieser Stichprobe.")

    print("\n%d Abbildungen, Schwelle %.2f" % (gesamt, SCHWELLE))
    print("  wird heute beschrieben:  %5d  (%4.1f %%)"
          % (ueber, 100.0 * ueber / gesamt))
    print("  faellt heute weg:        %5d  (%4.1f %%)"
          % (unter, 100.0 * unter / gesamt))
    print("\nVerteilung nach Doclings eigener Rechnung:")
    for name, n in zip(("unter 1 %", "1 bis 2 %", "2 bis 4 %", "4 bis 8 %",
                        "8 bis 16 %", "16 % und mehr"), treppe):
        print("  %-14s %5d  %s" % (name, n, "#" * int(round(40.0 * n / gesamt))))

    sortiert = sorted(je_dokument)
    if sortiert:
        mitte = sortiert[len(sortiert) // 2]
        print("\nVerteilung auf die Dokumente: Median %d · groesstes %d"
              % (mitte, sortiert[-1]))
        if mitte and sortiert[-1] > 10 * mitte:
            print("  ⛔ Vom Ausreisser getrieben - mit dem Mittelwert"
                  " hochzurechnen waere nicht belastbar.")

    print("\nWas die einzelnen Schwellen braechten:")
    kanten = (0.0, 0.01, 0.02, 0.04)
    namen = ("unter 1 %", "1 bis 2 %", "2 bis 4 %", "4 bis 8 %")
    dazu = 0
    n_dok = max(1, len(probe) - fehler)
    for k in range(3, -1, -1):
        dazu += treppe[k]
        print("  Schwelle %.2f: +%-5d Abbildungen -> +%5.1f Stunden fuer %d PDF"
              "   (Gruppe %s)"
              % (kanten[k], dazu,
                 1.0 * dazu / n_dok * SEKUNDEN_JE_BILD * len(alle) / 3600.0,
                 len(alle), namen[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
