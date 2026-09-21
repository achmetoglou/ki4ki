"""Dokumentkennung aus Bereich und Pfad - unabhaengig von der Stufe.

Warum nicht der Dateiname: Bei Kundenakten heissen Dateien reihenweise
gleich - 423 mehrfach vergebene Namen, 1.587 betroffene Dateien, groesste
Gruppe 99 (gemessen 20.09., bau/pfad-messung.py).

Warum die Stufe herausfaellt: Eine Datei wandert input -> parkplatz ->
archiv. Waere die Stufe Teil der Kennung, bekaeme dasselbe Dokument bei
jedem Umzug eine neue - genau der Kettenbruch, der behoben werden soll.

Warum ein Fingerabdruck und nicht der Pfad selbst: Alle acht
Vergleichsfunktionen werfen jedes Zeichen ausser a-z0-9 weg; bei acht
Ordnerebenen fallen dann 785 Pfade zusammen, die sich nur in Trennzeichen
unterscheiden. Und gemessen 21.09.: AnythingLLM macht aus '&' ein 'and',
aus '%' 'percent', aus dem Eurozeichen 'euro'. Solche Ersetzungen
ueberleben die Normalisierung und verschieben den Namen - Ziffern und
Buchstaben nie.
"""
import hashlib

STUFEN = ("input", "parkplatz", "archiv", "aussortiert", "loeschen")
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def kennpfad(bereich, unterpfad):
    """Bereich + Pfad unterhalb der Stufe. Der Stufenordner faellt weg.

    Der Bereich ist ABSICHTLICH ein eigenes Argument. Eine fruehere Fassung
    nahm einen einzelnen Pfad und riet den Bereich als erstes Segment - bei
    einem bereichsrelativen Pfad ("archiv/KundeA/x.pdf") wurde daraus still
    der "Bereich archiv". Im Proxy liegen Pfade an mehreren Stellen genau so
    vor (z.B. pruef_proxy.py:668 baut mit join(wurzel, "archiv", d)). Lieber
    ein Abbruch als ein plausibel aussehendes falsches Ergebnis.
    """
    b = str(bereich).strip().strip("/")
    if not b or "/" in b:
        raise ValueError("kennpfad: Bereich fehlt oder ist kein einzelner Name: %r"
                         % bereich)
    if b in STUFEN:
        # Ein Bereich kann nie so heissen wie ein Stufenordner. Kommt das vor,
        # wurde ein bereichsrelativer Pfad uebergeben - dann ist das erste
        # Segment die Stufe und der Bereich fehlt ganz. Hier abbrechen, sonst
        # entsteht still der "Bereich archiv".
        raise ValueError("kennpfad: %r ist ein Stufenname, kein Bereich - "
                         "vermutlich fehlt der Bereich im Pfad" % b)
    teile = [t for t in str(unterpfad).replace("\\", "/").split("/") if t]
    if teile and teile[0] in STUFEN:
        teile = teile[1:]
    if not teile:
        raise ValueError("kennpfad: Pfad enthaelt keine Datei: %r" % unterpfad)
    return "/".join([b] + teile)


def kennpfad_aus_bestandspfad(relpfad):
    """Fuer Pfade der Form <bereich>/<stufe>/<rest> unterhalb von dokumente/."""
    teile = [t for t in str(relpfad).replace("\\", "/").split("/") if t]
    if len(teile) < 2:
        raise ValueError("kennpfad_aus_bestandspfad: zu kurz: %r" % relpfad)
    return kennpfad(teile[0], "/".join(teile[1:]))


def fingerabdruck(kpfad):
    """Zehn Zeichen aus a-z0-9, die genau diesen Kennpfad bezeichnen."""
    roh = hashlib.sha256(kpfad.encode("utf-8")).digest()
    zahl = int.from_bytes(roh[:8], "big")
    aus = []
    for _ in range(10):
        zahl, rest = divmod(zahl, len(ALPHABET))
        aus.append(ALPHABET[rest])
    return "".join(aus)
