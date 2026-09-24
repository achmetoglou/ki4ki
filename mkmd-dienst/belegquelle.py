#!/usr/bin/env python3
"""Die Office-Regel fuer die AUFNAHME: Welche PDF ist gar kein Dokument?

Word und PowerPoint werden vor Docling nach PDF gewandelt, und die PDF liegt
neben dem Original im Archiv. Das Dokument ist das ORIGINAL; die PDF ist nur
die Quelle fuer den Belegsprung. Bekaeme sie einen eigenen Abdruck, zeigte
jeder Beleg des Office-Dokuments ins Leere - ohne Meldung.

⛔ Die Auswertung kennt diese Regel laengst (pruef_proxy._schluessel_der_datei
  und pdfstelle._index_bauen rechnen den Abdruck einer PDF aus dem Pfad des
  gleichnamigen Originals). Die AUFNAHME kannte sie nicht: der Dienst
  /schluessel rechnete allein aus Bereich und Pfad. Beide Dateien bekamen
  darum einen eigenen Abdruck - denselben lesbaren Teil, zwei verschiedene
  Abdruecke, zwei Eintraege im Katalog. Den mit dem PDF-Abdruck findet die
  Auswertung NIE wieder; er steht als "Dateiart: Text" da und jeder Klick
  darauf endet mit "Dieses Dokument liegt nicht vor".

⚠ Unterschied zur Auswertung: Dort liegen Original und PDF im selben Ordner,
  weil beide schon abgelegt sind - ein Blick in DIESEN Ordner genuegt. Bei der
  Aufnahme ist das nicht so: Die PDF liegt noch in input/, das Original kann
  aus einem frueheren Durchgang schon in archiv/ liegen. Deshalb wird die
  Stufe hier durchprobiert statt vorausgesetzt.

⛔ aussortiert/ und loeschen/ zaehlen NICHT als Fundort. Ein Original, das
  aussortiert wurde, ist kein Dokument - die PDF daneben ist dann wieder
  selbst eines und braucht ihren eigenen Abdruck. Wer die beiden Stufen
  mitzaehlte, haengte den Abdruck an eine Datei, die keiner mehr aufnimmt.
"""
import os

# Derselbe Baum wie in pdfstelle.py - im Container nur lesbar eingehaengt.
DOKUMENTE = (os.environ.get("KI4KI_PDFS")
             or os.path.expanduser("~/ki4ki/dokumente"))

# Wortgleich mit pruef_proxy._OFFICE_ORIGINAL und pdfstelle._OFFICE_ORIGINAL.
# ⚠ Wer hier eine Endung ergaenzt, ergaenzt sie dort MIT - sonst vergibt die
#   Aufnahme einen Abdruck, den die Auswertung anders rechnet.
OFFICE_ORIGINAL = (".docx", ".doc", ".odt", ".rtf", ".pptx", ".ppt", ".odp")

# Stufen, in denen ein Dokument LEBT (schluessel.STUFEN ohne aussortiert und
# loeschen).
LEBENDE_STUFEN = ("input", "parkplatz", "archiv")


def _unter(basis, *teile):
    """Der Pfad unter basis - oder None, sobald er darunter herausfuehrt.

    ⛔ Der Pfad kommt von aussen (n8n reicht durch, was im Eingang liegt).
      Ohne diese Wache genuegte ein Unterpfad mit '..', um den Dienst nach
      Dateien ausserhalb des Bestands sehen zu lassen.
    """
    wurzel = os.path.realpath(str(basis or ""))
    voll = os.path.realpath(os.path.join(wurzel, *[str(t) for t in teile]))
    if voll == wurzel or voll.startswith(wurzel + os.sep):
        return voll
    return None


def original_zu(bereich, rest, wurzel=None):
    """Der Pfad des Office-Originals zu dieser PDF - oder None.

    `rest` ist der Pfad UNTERHALB der Stufe, also genau der Teil, den
    schluessel.kennpfad() hinter dem Bereich stehen laesst
    ("KundeA/Angebot.pdf", nicht "input/KundeA/Angebot.pdf"). Der Rueckgabewert
    hat dieselbe Form und laesst sich unveraendert an schluessel.kennpfad()
    und schluessel.schluessel() weiterreichen.

    ⛔ Gibt NIE einen geratenen Wert zurueck: Ohne Datei auf der Platte ist
      die Antwort None, und die PDF bleibt ihr eigenes Dokument. Ein geratenes
      Original haengte den Abdruck an etwas, das es nicht gibt.
    """
    r = str(rest or "")
    if not r.lower().endswith(".pdf"):
        return None
    basis = DOKUMENTE if wurzel is None else wurzel
    stamm = r[:-4]
    for stufe in LEBENDE_STUFEN:
        # ⛔ ZWEI Schranken, nicht eine. Eine einzige Pruefung gegen den
        #   Bestandsordner ist zu weit: "../../x.pdf" landet dann zwar
        #   ausserhalb des Bereichs, aber immer noch INNERHALB des Bestands -
        #   und eine Datei aus einem fremden Bereich zoege den Abdruck an sich
        #   (gemessen an Fall 11 in belegquellentest.py). Der Fund muss
        #   unterhalb von <bestand>/<bereich>/<stufe>/ liegen.
        ordner = _unter(basis, bereich, stufe)
        if not ordner:
            continue
        for endung in OFFICE_ORIGINAL:
            p = _unter(ordner, stamm + endung)
            # os.path.isfile, NICHT os.path.exists: Ein ORDNER namens
            # "Bericht.docx" ist kein Original - er naehme der PDF sonst den
            # Abdruck und haengte ihn an etwas, das nie aufgenommen wird.
            if p and os.path.isfile(p):
                return stamm + endung
    return None
