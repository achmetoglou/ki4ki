"""Die Wortlisten aus einer Textdatei lesen - ohne Neustart.

⭐ WOZU: Die Ausloeser stehen jetzt in einer Textdatei, nicht mehr im Code.

   Frueher standen sie im Code (assistent.py, bestand.py). Aendern hiess:
   Datei anfassen, Proxy neu starten, zwei Minuten Ausfall. Fuer eine
   Wortliste ist das absurd.

⚠ ES WIRKT SOFORT. Die Datei wird bei jeder Frage angesehen; hat sich ihr
  Zeitstempel geaendert, wird sie neu gelesen. Kein Neustart, kein
  Ausfall. Das ist der eigentliche Gewinn - nicht die Datei selbst.

⚠ FEHLT DIE DATEI ODER IST SIE KAPUTT, gelten die eingebauten Vorgaben.
  Eine Wortliste darf die Anlage nicht lahmlegen: Wer sich beim Bearbeiten
  vertippt, soll eine schlechtere Erkennung bekommen - keinen Ausfall.

⚠ FUER ANDERE INSTALLATIONEN wichtig: Die Kennungen DS/BS/M/... sind die
  dieses Bestands. Ein anderes Haus hat andere. Bisher waren sie fest
  eingebaut; jetzt stehen sie in einer Datei, die zum Paket gehoert.
"""
import os
import re
import threading

DATEI = os.environ.get("KI4KI_WORTLISTEN") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "wortlisten.txt")

# Eingebaute Vorgaben - gelten, wenn die Datei fehlt oder unbrauchbar ist.
VORGABE_AUSLOESER = [
    "Bestand", "Bestandsliste", "Bestandsübersicht", "Bestandsaufnahme",
    "was haben wir alles an", "was haben wir an",
    "was habt ihr alles an", "was habt ihr an",
    "was habt ihr zum Thema", "was haben wir zum Thema",
    "Liste aller", "Liste der", "Übersicht über", "Aufstellung aller",
    "welche gibt es", "wie viele gibt es", "wie viele habt ihr",
    "wie viele haben wir", "welche habt ihr", "welche haben wir",
    "was liegt vor", "was ist vorhanden", "was steht zur Verfügung",
]
VORGABE_ARTEN = {
    "DS": ("Dissertation", "Dissertationen"),
    "BS": ("Bachelorarbeit", "Bachelorarbeiten"),
    "M": ("Masterarbeit", "Masterarbeiten"),
    "D": ("Diplomarbeit", "Diplomarbeiten"),
    "S": ("Studienarbeit", "Studienarbeiten"),
    "PA": ("Projektarbeit", "Projektarbeiten"),
}
VORGABE_GLEICH = {
    "doktorarbeit": "DS", "doktorarbeiten": "DS", "promotion": "DS",
    "promotionen": "DS", "diss": "DS",
}

_SPERRE = threading.Lock()
_STAND = {"zeit": None, "daten": None}


def _lesen(pfad):
    ausloeser, arten, gleich = [], {}, {}
    abschnitt = None
    with open(pfad, encoding="utf-8") as f:
        for roh in f:
            zeile = roh.split("#", 1)[0].strip()
            if not zeile:
                continue
            m = re.match(r"^\[(\w+)\]$", zeile)
            if m:
                abschnitt = m.group(1).lower()
                continue
            if abschnitt == "ausloeser":
                ausloeser.append(zeile)
            elif abschnitt == "arten":
                # KENNUNG = Einzahl | Mehrzahl
                if "=" not in zeile:
                    continue
                k, rest = zeile.split("=", 1)
                teile = [t.strip() for t in rest.split("|")]
                einzahl = teile[0] if teile else ""
                mehrzahl = teile[1] if len(teile) > 1 else einzahl
                if k.strip() and einzahl:
                    arten[k.strip().upper()] = (einzahl, mehrzahl)
            elif abschnitt == "gleichbedeutend":
                if "=" not in zeile:
                    continue
                wort, k = zeile.split("=", 1)
                if wort.strip() and k.strip():
                    gleich[wort.strip().lower()] = k.strip().upper()
    return ausloeser, arten, gleich


def laden(pfad=DATEI):
    """Wortlisten holen. Liest die Datei neu, wenn sie sich geaendert hat."""
    try:
        zeit = os.path.getmtime(pfad)
    except OSError:
        zeit = None
    if _STAND["daten"] is not None and _STAND["zeit"] == zeit:
        return _STAND["daten"]
    with _SPERRE:
        if _STAND["daten"] is not None and _STAND["zeit"] == zeit:
            return _STAND["daten"]
        if zeit is None:
            daten = (list(VORGABE_AUSLOESER), dict(VORGABE_ARTEN),
                     dict(VORGABE_GLEICH))
        else:
            try:
                a, ar, g = _lesen(pfad)
                # ⚠ Eine LEERE Liste waere schlimmer als die Vorgabe: dann
                #   erkennt die Anlage gar keine Bestandsfrage mehr, und
                #   niemand wuesste warum. Leer heisst hier "nicht gepflegt",
                #   nicht "ausgeschaltet".
                daten = (a or list(VORGABE_AUSLOESER),
                         ar or dict(VORGABE_ARTEN),
                         g if g or ar else dict(VORGABE_GLEICH))
            except Exception:
                daten = (list(VORGABE_AUSLOESER), dict(VORGABE_ARTEN),
                         dict(VORGABE_GLEICH))
        _STAND["zeit"] = zeit
        _STAND["daten"] = daten
        return daten


def ausloeser():
    return laden()[0]


def arten():
    return laden()[1]


def gleichbedeutend():
    return laden()[2]


def ausloeser_muster():
    """Ein Suchmuster aus den Wendungen - Reihenfolge und Abstand egal.

    ⚠ Die Wendungen sind KEINE Regeln fuer Fachleute, sondern Sprache. Wer
      "was haben wir alles an" eintraegt, meint auch "was haben wir denn so
      alles an". Deshalb werden Leerzeichen grosszuegig behandelt und
      Fuellwoerter dazwischen erlaubt.
    """
    teile = []
    for w in ausloeser():
        woerter = [re.escape(x) for x in w.split()]
        if not woerter:
            continue
        # ⚠ Zwischen den Woertern MUSS ein Leerzeichen stehen, dazu
        #   duerfen bis zu drei Fuellwoerter kommen. Ohne das \s+ am
        #   Anfang klebte alles zusammen ("washaben") und drei von sechs
        #   Proben fielen durch - der Verbinder frass das Leerzeichen.
        teile.append(r"\s+(?:\w+\s+){0,3}".join(woerter))
    if not teile:
        return None
    return re.compile("|".join(teile), re.I)


def wort_zu_art():
    """Alle Woerter, die eine Art bezeichnen -> Kennung."""
    raus = {}
    for k, (einzahl, mehrzahl) in arten().items():
        for w in (einzahl, mehrzahl):
            if w:
                raus[w.lower()] = k
    raus.update(gleichbedeutend())
    return raus


if __name__ == "__main__":
    import sys
    a, ar, g = laden()
    print("=== Datei: %s" % DATEI)
    print("   %s" % ("gelesen" if os.path.exists(DATEI) else "FEHLT - Vorgaben gelten"))
    print()
    print("=== %d Ausloeser" % len(a))
    for w in a[:6]:
        print("   %s" % w)
    print("   …")
    print()
    print("=== %d Arten" % len(ar))
    for k, (e, m) in sorted(ar.items()):
        print("   %-4s %s | %s" % (k, e, m))
    print()
    print("=== %d gleichbedeutende Woerter" % len(g))
    print("   %s" % ", ".join(sorted(g)))
    print()
    print("=== Probe: was loest aus?")
    muster = ausloeser_muster()
    faelle = [
        ("Welche Dissertationen haben wir im Bestand?", True),
        ("Was haben wir alles an Bachelorarbeiten?", True),
        ("Was haben wir denn so alles an Masterarbeiten?", True),
        ("Wie viele Dissertationen gibt es?", True),
        ("Hol mir die Dissertation von Max Mustermann", False),
        ("Was ist Mastizieren?", False),
    ]
    schlecht = 0
    for f, soll in faelle:
        ist = bool(muster.search(f))
        gut = ist == soll
        schlecht += not gut
        print("   %-5s %-46s %s" % ("ok" if gut else "FALSCH", f[:46],
                                    "loest aus" if ist else "loest nicht aus"))
    sys.exit(1 if schlecht else 0)
