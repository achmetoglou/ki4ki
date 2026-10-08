#!/usr/bin/env python3
"""Freistehende Bilddateien beschreiben, damit sie auffindbar werden.

AUSGANGSLAGE, gemessen am 08.10.2026 auf der A40 im Bereich kap:

    3.671 Bilddateien   jpg 2.847 · tif 690 · jpeg 118 · tiff 9 · png 7
    11,3 GB             Mittel 3,15 MB, groesste 372,8 MB
    davon beschrieben   0
    davon aussortiert   257 ("Format nicht vorgesehen")

Sie erreichen Docling nie. Die Positivliste im Ablaufplan
(1_KI4KI-Masse-Ingest.json, Knoten "Nur ein Bereich je Durchgang",
jsCode-Zeile 177) kennt keine Bildendung, und der Protokolltext sagt
warum: "Bilder, Archive, CAD- und Messgeraetedateien liefern keinen
belegbaren Text." Fuer die Stoerfallassistenz sind das ausgerechnet die
Schadensfotos und Zeichnungen.

⭐ EMRACHS ENTSCHEIDUNG, 08.10.2026: Bildbeschreibungen duerfen in den
  Bestand - aber GEKENNZEICHNET. Sie sind vom Modell erzeugt, nicht aus
  einem Dokument belegt. Deshalb traegt jede erzeugte Datei die Marke im
  Text UND einen Eintrag "herkunft": "bildbeschreibung" in der
  metadaten.json des Bereichs. Daraus baut metadaten.warnung() eine
  Fusszeile, die bei JEDER Antwort erscheint, die so ein Dokument nutzt.

⛔ WO DAS LAEUFT: im Container ki4ki-pruef-proxy. Nur der hat alles
  beisammen - Schreibrecht auf /daten/eingang, Pillow im Abbild und
  einen Weg zum Modell. Die Adresse wird NICHT eingetragen, sondern aus
  KI4KI_MODELL gelesen (dort steht http://nothink-proxy:11435/api/chat).
  Container-Adressen wandern; eine eingetragene waere nach dem naechsten
  Neustart falsch.

      docker cp bau/bilder_nachholen.py ki4ki-pruef-proxy:/tmp/
      docker exec ki4ki-pruef-proxy python3 /tmp/bilder_nachholen.py \
              --bereich kap --probe 50          # erst messen
      docker exec ki4ki-pruef-proxy python3 /tmp/bilder_nachholen.py \
              --bereich kap                     # dann alles

⛔ DAS SKRIPT STARTET KEINE AUFNAHME. Es legt die Markdown-Dateien in
  <bereich>/bilder-md/ ab und sagt zum Schluss, mit welchem Befehl man
  sie in den Eingang schiebt. Wer die Aufnahme ausloest, entscheidet ein
  Mensch - 3.671 neue Dokumente sind nichts, was nebenbei anlaufen soll.

⚠ UND ERST DANACH die Bildendungen in die Positivliste nachtragen. Vorher
  waere es schlimmer als jetzt: Das Bild ginge an Docling, kaeme mit 11
  Zeichen zurueck (gemessen, BUGS_UND_FIXES.md §9b), fiele durch die
  Mindestzeichengrenze und landete WIEDER in aussortiert/ - nur nach
  mehr Arbeit.
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.request

BILDENDUNGEN = (".jpg", ".jpeg", ".png", ".tif", ".tiff")
QUELLEN = ("parkplatz", "aussortiert")
ZIELORDNER = "bilder-md"
MARKE = "Maschinell erzeugte Bildbeschreibung"
MODELL = "gemma4:12b"
KANTE = 1280

# ⛔ Kuerzer als das ist keine Beschreibung, sondern ein Achselzucken.
#   Dieselbe Falle wie bei _bild_beschreiben im Proxy: ein Modell, das
#   nichts erkennt, antwortet gern mit einem Wort. Eine .md mit "Ja."
#   waere ein Dokument im Bestand, das nichts aussagt - und in der
#   Volltextsuche trotzdem Treffer erzeugt.
MINDESTZEICHEN = 40

# Der Auftragstext stammt woertlich aus mkmd-dienst/bildmodell.json - der
# ist am Bestand erprobt. Eine zweite Fassung waere eine zweite Wahrheit.
AUFTRAG = (
    "Beschreibe diese Abbildung aus einem technischen Fachtext. Antworte "
    "AUSSCHLIESSLICH auf Deutsch und beginne mit den Worten 'Die Abbildung "
    "zeigt'. Nenne, was dargestellt ist, die Beschriftungen der Achsen mit "
    "ihren Einheiten und die erkennbaren Zahlenwerte. Bei Diagrammen: "
    "beschreibe den Verlauf der Kurven und nenne Anfangs-, End- und "
    "Extremwerte. Bei technischen Zeichnungen: nenne die bezeichneten "
    "Bauteile und die eingetragenen Masse. Bei Fotografien und "
    "Mikroskopaufnahmen: beschreibe das Werkstueck, erkennbare Fehler oder "
    "Strukturen und den Massstab, sofern angegeben. Wenn du etwas nicht "
    "sicher lesen kannst, sage das, statt zu raten.")


def bilder_finden(wurzel, bereich, quellen=QUELLEN):
    """Alle Bilddateien unter <wurzel>/<bereich>/<quelle>/ - rekursiv.

    ⛔ archiv/ ist NICHT dabei: was dort liegt, ist aufgenommen. Und
      Grossschreibung zaehlt nicht - im Bestand liegen .TIF und .tif.
    """
    gefunden = []
    for quelle in quellen:
        start = os.path.join(wurzel, bereich, quelle)
        if not os.path.isdir(start):
            continue
        for ordner, _unter, dateien in os.walk(start):
            for d in dateien:
                if d.lower().endswith(BILDENDUNGEN) and not d.startswith("._"):
                    gefunden.append(os.path.join(ordner, d))
    return sorted(gefunden)


def kennung_fuer(pfad):
    """Der Dateiname ohne Endung - er traegt Kunde und Vorgang bereits."""
    return os.path.splitext(os.path.basename(pfad))[0]


def bild_vorbereiten(pfad, kante=KANTE):
    """Das Bild als JPEG, lange Kante hoechstens <kante>.

    ⛔ NICHT ueberspringen, verkleinern. Die groesste Datei im Bestand hat
      372,8 MB; als Base64 waeren das rund 497 MB Nutzlast. Ueberspringen
      hiesse aber, ausgerechnet das groesste Bild unauffindbar zu lassen.
      Pillow liegt im Abbild (pruef-proxy/Dockerfile).

    ⚠ Kleine Bilder werden NICHT aufgeblasen - das brauchte Rechenzeit und
      brachte kein Pixel mehr Information.
    """
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None     # Scans sprengen sonst die Warnschwelle
    with Image.open(pfad) as bild:
        bild = bild.convert("RGB")
        if max(bild.size) > kante:
            bild.thumbnail((kante, kante), Image.LANCZOS)
        puffer = io.BytesIO()
        bild.save(puffer, format="JPEG", quality=85, optimize=True)
        return puffer.getvalue()


def anfrage_bauen(jpeg, auftrag=AUFTRAG, modell=MODELL):
    """Die Nutzlast fuer /api/chat - mit dem Bild, nicht nur dem Auftrag."""
    return {
        "model": modell,
        "messages": [{"role": "user", "content": auftrag,
                      "images": [base64.b64encode(jpeg).decode("ascii")]}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 600},
        "keep_alive": "24h",
    }


def markdown_bauen(kennung, rel_pfad, beschreibung, modell, datum):
    """Die Markdown-Datei - Kennzeichnung VOR der Beschreibung.

    ⛔ Die Reihenfolge ist nicht Geschmack. Zitiert das Modell spaeter eine
      Stelle aus der Mitte, soll der Warnsatz oberhalb davon stehen und
      nicht darunter.
    """
    return (
        "# Bildbeschreibung: %s\n\n"
        "> ⚠ **%s.** Dieser Text stammt **nicht aus einem Dokument** -\n"
        "> ein Sprachmodell hat ihn aus dem Bild abgeleitet.\n"
        "> Er ist **keine belegte Fundstelle** und kann Fehler enthalten.\n"
        "> Im Zweifel das Bild selbst ansehen.\n\n"
        "**Bilddatei:** `%s`  \n"
        "**Erzeugt:** %s mit `%s`\n\n"
        "---\n\n"
        "%s\n"
        % (kennung, MARKE, rel_pfad, datum, modell, beschreibung.strip()))


def metadaten_ergaenzen(datei, kennung, modell):
    """Den Eintrag in metadaten.json setzen, ohne andere zu verlieren."""
    daten = {}
    if os.path.exists(datei):
        try:
            daten = json.load(open(datei, encoding="utf-8")) or {}
        except Exception:
            # ⛔ Lieber abbrechen als eine kaputte Datei ueberschreiben -
            #   dort stehen Freigaben, die ueber Sichtbarkeit entscheiden.
            raise
    daten[kennung] = {"herkunft": "bildbeschreibung",
                      "art": "Bildbeschreibung",
                      "kategorie": "Bildbeschreibung (maschinell)",
                      "modell": modell}
    vorlaeufig = datei + ".neu"
    with open(vorlaeufig, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(vorlaeufig, datei)


def besitz_angleichen(pfad, vorbild, chown=os.chown):
    """Neue Dateien bekommen Benutzer und Gruppe des Bereichsordners.

    ⛔ 08.10. gemessen: ki4ki-pruef-proxy hat kein `user:` in der Compose,
      laeuft also als root. Der Ordner dokumente/ gehoert auf dem Host
      emanager:emrach (2775). Ohne diese Zeile gehoerten die 3.671 neuen
      Dateien root - und wer sie spaeter verschiebt oder aufraeumt, ist
      nicht root. Das faellt erst mitten im Lauf auf.

    ⚠ Scheitert sie, ist das kein Grund abzubrechen: eine Datei mit dem
      falschen Besitzer ist besser als keine Beschreibung.
    """
    try:
        s = os.stat(vorbild)
    except OSError:
        return False
    try:
        chown(pfad, s.st_uid, s.st_gid)
        return True
    except Exception:
        return False


def probe_waehlen(bilder, wieviele):
    """Eine Auswahl, die die GROESSENSPANNE abdeckt.

    ⛔ Zweck der Probe ist, die echte Sekundenzahl je Bild zu messen. Die
      ersten N alphabetisch waeren womoeglich lauter Miniaturen, und die
      Hochrechnung auf 3.671 waere wertlos. Deshalb nach Groesse sortieren
      und gleichmaessig ueber die ganze Spanne greifen - das kleinste und
      das groesste sind immer dabei.
    """
    if wieviele >= len(bilder):
        return list(bilder)
    if wieviele <= 0:
        return []
    nach_groesse = sorted(bilder, key=lambda p: os.path.getsize(p))
    if wieviele == 1:
        return [nach_groesse[-1]]
    letzter = len(nach_groesse) - 1
    stellen = sorted({round(i * letzter / (wieviele - 1))
                      for i in range(wieviele)})
    return [nach_groesse[i] for i in stellen]


def _ueber_netz(adresse, zeitgrenze=600):
    def senden(anfrage):
        leib = json.dumps(anfrage).encode("utf-8")
        bitte = urllib.request.Request(
            adresse, data=leib, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(bitte, timeout=zeitgrenze) as r:
            antwort = json.loads(r.read().decode("utf-8"))
        return ((antwort.get("message") or {}).get("content") or "").strip()
    return senden


def nachholen(wurzel, bereich, senden, quellen=QUELLEN, ziel=ZIELORDNER,
              modell=MODELL, kante=KANTE, probe=0, trocken=False,
              laut=True, datum=None):
    """Der Lauf. Gibt einen Bericht als dict zurueck."""
    bilder = bilder_finden(wurzel, bereich, quellen)
    bericht = {"gefunden": len(bilder), "uebersprungen": 0, "fertig": 0,
               "fehler": 0, "sekunden": 0.0, "bytes": 0}
    if probe:
        bilder = probe_waehlen(bilder, probe)
        bericht["probe"] = len(bilder)
    if trocken:
        if laut:
            print("Trockenlauf: %d Bilder gefunden, nichts geschrieben."
                  % bericht["gefunden"])
        return bericht

    bereichsordner = os.path.join(wurzel, bereich)
    zielordner = os.path.join(bereichsordner, ziel)
    metadatei = os.path.join(bereichsordner, "metadaten.json")
    datum = datum or time.strftime("%Y-%m-%d")

    for nummer, pfad in enumerate(bilder, 1):
        kennung = kennung_fuer(pfad)
        md = os.path.join(zielordner, kennung + ".md")
        if os.path.exists(md):
            # ⛔ Fortsetzen statt von vorn: Bei 3.671 Bildern und einer
            #   Nacht Laufzeit darf ein Abbruch um 4 Uhr nicht alles
            #   wiederholen.
            bericht["uebersprungen"] += 1
            continue
        begonnen = time.time()
        try:
            jpeg = bild_vorbereiten(pfad, kante)
            beschreibung = (senden(anfrage_bauen(jpeg, AUFTRAG, modell)) or "")
            if len(beschreibung.strip()) < MINDESTZEICHEN:
                raise ValueError("Antwort zu kurz (%d Zeichen): %r"
                                 % (len(beschreibung.strip()),
                                    beschreibung.strip()[:60]))
            rel = os.path.relpath(pfad, bereichsordner)
            text = markdown_bauen(kennung, rel, beschreibung, modell, datum)
            os.makedirs(zielordner, exist_ok=True)
            # Erst vollstaendig schreiben, dann umbenennen: Ein Abbruch
            # mittendrin darf keine halbe Datei hinterlassen, die der
            # naechste Lauf fuer erledigt haelt.
            with open(md + ".neu", "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(md + ".neu", md)
            besitz_angleichen(md, bereichsordner)
            besitz_angleichen(zielordner, bereichsordner)
            metadaten_ergaenzen(metadatei, kennung, modell)
            besitz_angleichen(metadatei, bereichsordner)
            bericht["fertig"] += 1
            bericht["bytes"] += len(jpeg)
        except Exception as e:
            bericht["fehler"] += 1
            if laut:
                print("  FEHLER  Bild %d/%d: %s" % (nummer, len(bilder), e),
                      file=sys.stderr, flush=True)
            continue
        finally:
            bericht["sekunden"] += time.time() - begonnen
        if laut and (nummer % 25 == 0 or nummer == len(bilder)):
            je = bericht["sekunden"] / max(1, bericht["fertig"])
            print("  %d/%d  %.1f s je Bild  Hochrechnung fuer %d: %.1f h"
                  % (nummer, len(bilder), je, bericht["gefunden"],
                     je * bericht["gefunden"] / 3600.0), flush=True)
    return bericht


def haupt(argumente=None):
    p = argparse.ArgumentParser(
        description="Freistehende Bilddateien beschreiben und als Markdown "
                    "ablegen. Startet KEINE Aufnahme.")
    p.add_argument("--bereich", required=True)
    p.add_argument("--wurzel", default=os.environ.get("KI4KI_EINGANG")
                   or "/daten/eingang")
    p.add_argument("--quellen", default=",".join(QUELLEN))
    p.add_argument("--ziel", default=ZIELORDNER)
    p.add_argument("--modell", default=os.environ.get("KI4KI_BILDMODELL")
                   or MODELL)
    p.add_argument("--adresse", default=os.environ.get("KI4KI_MODELL")
                   or "http://nothink-proxy:11435/api/chat")
    p.add_argument("--kante", type=int, default=KANTE)
    p.add_argument("--probe", type=int, default=0,
                   help="nur so viele Bilder, ueber die Groessenspanne verteilt")
    p.add_argument("--trocken", action="store_true")
    a = p.parse_args(argumente)

    quellen = tuple(x.strip() for x in a.quellen.split(",") if x.strip())
    begonnen = time.time()
    bericht = nachholen(a.wurzel, a.bereich, _ueber_netz(a.adresse),
                        quellen=quellen, ziel=a.ziel, modell=a.modell,
                        kante=a.kante, probe=a.probe, trocken=a.trocken)
    dauer = time.time() - begonnen
    print("\n--- Bericht ---")
    print("gefunden        %d" % bericht["gefunden"])
    if bericht.get("probe"):
        print("probe           %d (ueber die Groessenspanne verteilt)"
              % bericht["probe"])
    print("beschrieben     %d" % bericht["fertig"])
    print("uebersprungen   %d (lagen schon vor)" % bericht["uebersprungen"])
    print("Fehler          %d" % bericht["fehler"])
    print("Dauer           %.0f s" % dauer)
    if bericht["fertig"]:
        je = bericht["sekunden"] / bericht["fertig"]
        print("je Bild         %.1f s" % je)
        print("Hochrechnung    %.1f h fuer alle %d"
              % (je * bericht["gefunden"] / 3600.0, bericht["gefunden"]))
    if bericht["fertig"] and not a.trocken:
        ziel = os.path.join(a.wurzel, a.bereich, a.ziel)
        print("\nDie Beschreibungen liegen in %s." % ziel)
        print("Die Aufnahme startet NICHT von selbst. Wenn sie laufen soll:")
        print("    mv %s/*.md %s/"
              % (ziel, os.path.join(a.wurzel, a.bereich, "input")))
    return 1 if bericht["fehler"] and not bericht["fertig"] else 0


if __name__ == "__main__":
    sys.exit(haupt())
