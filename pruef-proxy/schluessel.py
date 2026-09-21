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
import os
import re
import unicodedata

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


ABDRUCK_LAENGE = 10

# Was AnythingLLM anhaengt: '-<uuid>.json' auf den Uploadnamen '<schluessel>.md'.
# Die Bindestriche der Kennung ueberleben die Normalisierung nicht, die 32
# Hexzeichen schon - deshalb sind die Striche hier alle freigestellt.
_UUID = re.compile(
    r"-?[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)


def ohne_uuid(name):
    """Den von AnythingLLM angehaengten Kennungsteil abschneiden.

    Ohne diesen Schritt stuenden am Ende des Namens die Hexzeichen der
    Kennung - und die letzten zehn alphanumerischen Zeichen waeren ihre,
    nicht die des Abdrucks.
    """
    n = str(name or "")
    for endung in (".json", ".md"):
        if n.lower().endswith(endung):
            n = n[:-len(endung)]
    return _UUID.sub("", n)


def abdruck_kandidaten(name):
    """Alle Abdruck-Kandidaten eines geschriebenen Namens, von RECHTS.

    Warum Kandidaten und nicht ein Abdruck: Neun Normalisierungen laufen im
    Haus, und jede behandelt die Endung anders - aus '.pdf' wird '-pdf',
    'pdf' oder gar nichts. Ein einzelnes Herausschneiden muesste alle neun
    nachbauen; das ist das Spiel, das der naechste Dateiname gewinnt.

    Warum von rechts: Der echte Abdruck steht am Ende. Ein zufaellig
    passendes Fenster im lesbaren Teil wird dadurch nie zuerst gefunden.

    ⛔ Ein Rueckgabewert ist KEIN Beweis, dass ein Abdruck vorliegt - jeder
       Name mit zehn alphanumerischen Zeichen liefert Kandidaten. Erst die
       Mitgliedschaft in einem Verzeichnis entscheidet. Deshalb ist
       abdruck_finden() die Funktion, die benutzt wird, und nicht diese.
    """
    nur = re.sub(r"[^A-Za-z0-9]", "", ohne_uuid(name)).lower()
    return tuple(nur[i:i + ABDRUCK_LAENGE]
                 for i in range(len(nur) - ABDRUCK_LAENGE, -1, -1))


def abdruck_finden(name, verzeichnis):
    """Der erste Kandidat, den das Verzeichnis kennt - sonst None.

    `verzeichnis` ist alles, was `in` beantwortet (dict, set, frozenset).
    Das ist die EINZIGE Art, in der im Haus ein Abdruck erkannt wird.
    """
    for a in abdruck_kandidaten(name):
        if a in verzeichnis:
            return a
    return None


LESBAR_BYTE = 120
GRENZE_BYTE = 200   # 255 (ext4) - 3 (".md" beim Upload) - 42 (Aufschlag), abgerundet

_ENDUNG = re.compile(r"^\.[A-Za-z0-9]{1,8}$")
RUECKFALL = "dok"   # wenn vom lesbaren Teil nichts uebrigbleibt


def _bereinigen(text):
    """Auf A-Za-z0-9- bringen.

    Nicht Kosmetik: Solange Sonderzeichen drin sind, ist die Laenge nicht
    berechenbar, weil AnythingLLM sie unterschiedlich lang ersetzt
    ('&' -> 'and' waechst, der Winkel-Pfeil schrumpft von 3 Byte auf 1).
    Gemessen wurden +39, +40, +42 und +14 Byte bei vier Testnamen.
    """
    n = unicodedata.normalize("NFKD", text)
    n = "".join(c for c in n if not unicodedata.combining(c)).replace("ß", "ss")
    return re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-")


def _kuerzen(text, hoechstens):
    roh = text.encode("utf-8")
    return text if len(roh) <= hoechstens else roh[:hoechstens].decode("utf-8", "ignore")


def _endung_von(kpfad):
    """Nur echte Endungen. os.path.splitext allein macht aus
    'Angebot Nr. 4711' die Endung '.4711' und aus '2024.09.20 Protokoll'
    die Endung '.20 Protokoll' - in Kundenordnern keine Ausnahme,
    sondern die Regel."""
    e = os.path.splitext(kpfad)[1]
    return e.lower() if _ENDUNG.match(e) else ""


def schluessel(bereich, unterpfad):
    """Lesbarer Teil + '--' + Fingerabdruck + Endung.

    Verglichen wird ausschliesslich der Fingerabdruck. Der lesbare Teil
    ist fuer Menschen und darf verstuemmelt werden.
    """
    kpfad = kennpfad(bereich, unterpfad)
    endung = _endung_von(kpfad)
    stamm = kpfad[:-len(endung)] if endung else kpfad
    schwanz = "--%s%s" % (fingerabdruck(kpfad), endung)
    # ⛔ Die 200-Byte-Zusicherung haengt AN _ENDUNG, nicht an diesem max(0, ...).
    # Solange eine Endung hoechstens 8 Zeichen hat, ist schwanz hoechstens
    # 21 Byte, platz nie negativ und die Grenze sicher. Weicht jemand _ENDUNG
    # auf, rettet das max(0, ...) die Zusicherung NICHT: platz wird 0, der
    # Rueckfall haengt sich an einen ueberlangen schwanz, und heraus kommen
    # 216 Byte (gemessen 21.09. mit einer 250-Zeichen-Endung).
    # Das max(0, ...) verhindert nur das Schlimmere - _kuerzen wuerde bei
    # negativer Laenge von HINTEN schneiden und den Abdruck zerstoeren.
    # Bewacht wird die eigentliche Bedingung von der Pruefung
    # "eine 200-Zeichen-Punkt-Kette gilt NICHT als Endung" in schluesseltest.py.
    platz = max(0, min(LESBAR_BYTE, GRENZE_BYTE - len(schwanz.encode("utf-8"))))
    lesbar = _kuerzen(_bereinigen(stamm), platz) or RUECKFALL
    return lesbar + schwanz
