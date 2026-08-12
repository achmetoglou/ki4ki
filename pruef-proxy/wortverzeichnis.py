#!/usr/bin/env python3
"""Ein Verzeichnis seltener Woerter - damit die woertliche Suche schnell wird.

⛔ DER ANLASS: Die woertliche Suche findet "Mastizieren"
zuverlaessig in allen vier Arbeiten - aber sie braucht 158 Sekunden, weil
sie alle 1.253 Arbeiten nacheinander laedt. So kann sie nicht in eine Frage
eingehaengt werden.

DIE LOESUNG: Einmal ein Verzeichnis bauen "welches Wort steht in welchen
Arbeiten". Dann muessen fuer eine Frage nur noch die WENIGEN Arbeiten
geladen werden, die das Wort ueberhaupt enthalten - vier statt 1.253.

WAS AUFGENOMMEN WIRD, und warum nur das:

  - Woerter ab 6 Zeichen. Kuerzere sind fast nie Fachbegriffe, und sie
    stehen ueberall - die woertliche Suche liefert dann Rauschen.

  - Nur Woerter, die in HOECHSTENS 80 Arbeiten vorkommen. Ein Wort, das in
    600 Arbeiten steht, unterscheidet nichts; dort ist die
    Aehnlichkeitssuche ohnehin besser. Das Verzeichnis soll genau die
    Luecke schliessen, die sie hat: seltene Fachbegriffe.

  Beides zusammen macht das Verzeichnis klein genug, um es in Sekunden zu
  laden - und schneidet nichts weg, was gebraucht wird.

⚠ DAS VERZEICHNIS VERALTET. Kommt ein Dokument dazu, fehlen seine Woerter.
  Deshalb steht im Kopf, aus wie vielen Arbeiten es gebaut wurde; passt die
  Zahl nicht mehr, wird es neu gebaut. Ein Verzeichnis, das stillschweigend
  veraltet, ist schlimmer als keines - es behauptet, ein Wort komme nicht
  vor.

  python3 wortverzeichnis.py bauen [<bestandsordner>]
  python3 wortverzeichnis.py suche <wort> [<wort> ...]
"""
import json
import os
import re
import sys
import threading
import traceback
import time
import unicodedata

BESTAND = os.environ.get("KI4KI_BESTAND") or "/daten/bestand"
VERZEICHNIS = os.environ.get("KI4KI_WORTVERZEICHNIS") or \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".wortverzeichnis.json")

MINDESTLAENGE = 6
HOECHSTENS_ARBEITEN = 80


def falte(s):
    """Kleinschreibung ohne Umlaute und Zeichensetzung - wie in wortsuche."""
    n = unicodedata.normalize("NFKD", s or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()


def _dateien(ordner):
    raus = []
    for wurzel, _, dateien in os.walk(ordner):
        for f in dateien:
            if f.endswith(".json"):
                raus.append(os.path.join(wurzel, f))
    return sorted(raus)


def bauen(ordner=BESTAND, ziel=VERZEICHNIS, melden=print):
    t0 = time.time()
    dateien = _dateien(ordner)
    melden("   %d Arbeiten werden gelesen" % len(dateien))

    # wort -> Menge von Arbeitsnummern (spart Speicher gegenueber Namen)
    karte = {}
    namen = []
    for i, p in enumerate(dateien):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        namen.append(os.path.basename(p).split(".md-")[0])
        nr = len(namen) - 1
        text = falte(d.get("pageContent") or "")
        gesehen = set()
        for w in text.split():
            if len(w) < MINDESTLAENGE or w in gesehen:
                continue
            gesehen.add(w)
            karte.setdefault(w, []).append(nr)
        if melden and (i + 1) % 200 == 0:
            melden("   %d von %d gelesen, %d verschiedene Woerter"
                   % (i + 1, len(dateien), len(karte)))

    vorher = len(karte)
    # Haeufige Woerter raus - die unterscheiden nichts.
    karte = {w: a for w, a in karte.items() if len(a) <= HOECHSTENS_ARBEITEN}
    melden("   %d Woerter gesamt, davon %d selten genug (<= %d Arbeiten)"
           % (vorher, len(karte), HOECHSTENS_ARBEITEN))

    inhalt = {
        "gebaut": int(time.time()),
        "arbeiten": len(namen),
        "mindestlaenge": MINDESTLAENGE,
        "hoechstens_arbeiten": HOECHSTENS_ARBEITEN,
        "namen": namen,
        "woerter": karte,
    }
    vorlaeufig = ziel + ".neu"
    with open(vorlaeufig, "w", encoding="utf-8") as f:
        json.dump(inhalt, f, ensure_ascii=False)
    os.replace(vorlaeufig, ziel)
    melden("   %s  (%.1f MB, %.0f s)"
           % (ziel, os.path.getsize(ziel) / 1048576.0, time.time() - t0))
    return inhalt


_GELADEN = None
# Laeuft gerade ein Neubau? Ohne diese Sperre startet JEDE Frage waehrend
# des Baus einen weiteren - bei 25 Fragen 25 Durchlaeufe ueber 1.253
# Dateien gleichzeitig.
_BAUT = threading.Lock()


def _neu_bauen_im_hintergrund(pfad, ordner, melden=None):
    """Verzeichnis erneuern, ohne den Frage-Faden aufzuhalten.

    35 Sekunden Wartezeit mitten in einer Frage waeren fuer den Menschen
    ein Haenger ohne Erklaerung. Deshalb im Hintergrund: Diese Frage
    bekommt keine woertliche Suche, die naechste wieder.
    """
    if not _BAUT.acquire(blocking=False):
        return                      # baut schon jemand
    def arbeit():
        global _GELADEN
        try:
            if melden:
                melden("Wortverzeichnis veraltet - wird im Hintergrund neu gebaut")
            bauen(ordner, pfad, melden=lambda m: None)
            _GELADEN = None         # beim naechsten laden() frisch einlesen
            if melden:
                melden("Wortverzeichnis neu gebaut")
        except Exception:
            traceback.print_exc(file=sys.stderr)
        finally:
            _BAUT.release()
    threading.Thread(target=arbeit, daemon=True).start()


def laden(pfad=VERZEICHNIS, ordner=BESTAND, melden=None):
    """Verzeichnis holen - und pruefen, ob es noch passt.

    ⚠ Passt die Zahl der Arbeiten nicht mehr, wird None geliefert. Der
      Aufrufer faellt dann auf die langsame Suche zurueck oder laesst es
      bleiben - aber er bekommt KEINE veraltete Auskunft.
    """
    global _GELADEN
    if _GELADEN is not None:
        return _GELADEN
    if not os.path.exists(pfad):
        return None
    try:
        with open(pfad, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return None
    jetzt = len(_dateien(ordner))
    if d.get("arbeiten") != jetzt:
        if melden:
            melden("Verzeichnis ist von %d Arbeiten, es sind jetzt %d - "
                   "es wird neu gebaut" % (d.get("arbeiten"), jetzt))
        # ⚠ Nicht nur ablehnen, sondern erneuern. Sonst faellt die
        #   woertliche Suche nach dem ersten neuen Dokument LAUTLOS aus.
        _neu_bauen_im_hintergrund(pfad, ordner, melden)
        return None
    _GELADEN = d
    return d


def arbeiten_mit(wort, pfad=VERZEICHNIS, ordner=BESTAND, auch_teilwort=True):
    """In welchen Arbeiten steht das Wort? None = keine Auskunft moeglich.

    ⚠ TEILWORTSUCHE IST IM DEUTSCHEN PFLICHT, nicht Feinschliff.
      Erste Fassung verglich nur ganze Woerter und fand "Mastizieren" in
      DREI Arbeiten. Die Volltextsuche fand VIER - in BS-00-000 steht es
      als Teil eines anderen Wortes (Beugung oder Zusammensetzung).
      Ein Verzeichnis, das "Mastizierens" nicht als "Mastizieren" erkennt,
      verliert in einer Fachsprache mit zusammengesetzten Woertern
      systematisch Treffer. Gefunden durch die Gegenprobe gegen den
      Volltext - nicht durch Nachdenken.

      Der Durchlauf ueber alle Schluessel kostet rund 20 ms bei 371.000
      Woertern. Das ist der Preis, und er ist es wert.
    """
    d = laden(pfad, ordner)
    if d is None:
        return None
    w = falte(wort)
    if not w or len(w) < d.get("mindestlaenge", MINDESTLAENGE):
        return None

    nummern = set(d["woerter"].get(w) or [])
    if auch_teilwort:
        for schluessel, arbeiten in d["woerter"].items():
            if schluessel != w and w in schluessel:
                nummern.update(arbeiten)

    # ⚠ Eine leere Liste heisst "nicht als seltenes Wort bekannt", NICHT
    #   "kommt nicht vor": Woerter aus mehr als HOECHSTENS_ARBEITEN
    #   Arbeiten stehen gar nicht im Verzeichnis.
    return [d["namen"][n] for n in sorted(nummern)]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "bauen":
        bauen(sys.argv[2] if len(sys.argv) > 2 else BESTAND)
    elif len(sys.argv) > 2 and sys.argv[1] == "suche":
        for w in sys.argv[2:]:
            a = arbeiten_mit(w)
            if a is None:
                print("   %-24s keine Auskunft (Verzeichnis fehlt/veraltet)" % w)
            else:
                print("   %-24s %d Arbeiten: %s"
                      % (w, len(a), ", ".join(a[:8]) + (" …" if len(a) > 8 else "")))
    else:
        print(__doc__)
