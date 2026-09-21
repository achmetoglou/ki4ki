"""Die Dokumente, an denen Docling scheiterte - kommen sie im Zweitversuch durch?

Der Lauf vom 21.09. meldete 16 von 788 PDF mit
"docling-parse could not load document". Daraus wurde notiert, diese
Dateien haetten im Betrieb weder Text noch Bildbeschreibung.

Das koennte falsch sein. Der Unter-Ablaufplan hat einen zweiten Knoten,
"Docling Zweitversuch (pypdfium2)", der bei einem Fehlschlag mit einem
ANDEREN PDF-Motor nachsetzt - und zusaetzlich mit Texterkennung
(ocr_preset=easyocr). Genau fuer solche Faelle. Die Messung kennt diesen
Zweitversuch nicht und meldet deshalb moeglicherweise Ausfaelle, die im
Betrieb gar keine sind.

Statt den Bestand erneut 50 Minuten lang durchzurechnen, nutzt dieses
Skript die Rohdatei des letzten Laufs: Sie enthaelt eine Zeile je
GELUNGENEM Dokument mit seiner laufenden Nummer. Die fehlenden Nummern
sind genau die Fehlschlaege. Weil die Auswahl mit festem Startwert
gemischt wird, fuehrt dieselbe Nummer wieder zu derselben Datei.

Gibt nur Zahlen und Fehlertexte aus, keine Dateinamen.

Aufruf:
    cd ~/ki4ki
    docker exec -i ki4ki-pruef-proxy python3 - < bau/bildfehler.py
"""
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

WURZEL = os.environ.get("WURZEL", "/daten/pdfs")
ROHDATEN = os.environ.get("ROHDATEN", "/tmp/bildmessung-roh.csv")
DOCLING = os.environ.get("DOCLING", "http://docling:5001/v1/convert/file")
ZEITLIMIT = int(os.environ.get("ZEITLIMIT", "600"))


def _multipart(pfad, felder):
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


def versuch(pfad, felder):
    """(zeichen, abbildungen, sekunden, fehlertext)"""
    koerper, typ = _multipart(pfad, felder)
    anfrage = urllib.request.Request(DOCLING, data=koerper,
                                     headers={"Content-Type": typ})
    start = time.time()
    try:
        with urllib.request.urlopen(anfrage, timeout=ZEITLIMIT) as antwort:
            roh = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as f:
        return None, None, time.time() - start, f.__class__.__name__
    dauer = time.time() - start
    dokument = roh.get("document") or {}
    inhalt = dokument.get("md_content")
    json_teil = dokument.get("json_content")
    if not isinstance(json_teil, dict):
        pannen = roh.get("errors") or []
        text = ""
        if isinstance(pannen, list) and pannen:
            erste = pannen[0]
            text = (erste.get("error_message") or "") if isinstance(erste, dict) \
                else str(erste)
        return None, None, dauer, (text[:90] or str(roh.get("status")))
    return len(inhalt or ""), len(json_teil.get("pictures") or []), dauer, None


# Null Zeichen ist KEIN Erfolg, auch wenn die Umwandlung formal gelingt -
# genau das ist der stille Ausfall aus Punkt 10: HTTP 200 mit leerem Text,
# und die Datei landet trotzdem als aufgenommen im Archiv.
LEER = "  ⛔ ABER LEER"

ERSTVERSUCH = [
    ("to_formats", "json"), ("do_picture_description", "false"),
    ("do_picture_classification", "false"), ("do_formula_enrichment", "false"),
    ("do_table_structure", "false"), ("do_ocr", "false"),
]

# Genau die Einstellungen aus dem Knoten "Docling Zweitversuch (pypdfium2)"
ZWEITVERSUCH = [
    ("to_formats", "json"), ("do_picture_description", "false"),
    ("do_picture_classification", "false"), ("do_formula_enrichment", "false"),
    ("do_table_structure", "true"), ("table_mode", "accurate"),
    ("pdf_backend", "pypdfium2"), ("ocr_preset", "easyocr"),
    ("ocr_lang", "de"), ("ocr_lang", "en"),
]


# Erste Bytes gaengiger Formate. "keine PDF" allein ist keine Diagnose -
# erst der Typ sagt, ob hier Muell, ein falsch benanntes Dokument oder ein
# Nebenprodukt des Kopierens liegt. Jeder Fall braucht eine andere Massnahme.
KENNUNGEN = (
    (b"\x00\x05\x16\x07", "macOS-Metadatei (AppleDouble, kein Dokument)"),
    (b"PK\x03\x04", "ZIP-Format - docx/xlsx/pptx, falsch benannt"),
    (b"\xd0\xcf\x11\xe0", "altes Office-Format - doc/xls/ppt, falsch benannt"),
    (b"\xff\xd8\xff", "JPEG-Bild, falsch benannt"),
    (b"\x89PNG", "PNG-Bild, falsch benannt"),
    (b"II*\x00", "TIFF-Bild, falsch benannt"),
    (b"MM\x00*", "TIFF-Bild, falsch benannt"),
    (b"%!PS", "PostScript, kein PDF"),
    (b"{\\rtf", "RTF-Text, falsch benannt"),
    (b"<?xml", "XML, falsch benannt"),
    (b"\x1f\x8b", "gzip-Archiv"),
)


def _was_denn_dann(kopf):
    """Wenn es keine PDF ist - was ist es dann?"""
    for kennung, name in KENNUNGEN:
        if kopf.startswith(kennung):
            return name
    if not kopf.strip():
        return "nur Nullbytes oder Leerzeichen"
    druckbar = sum(1 for b in kopf if 32 <= b < 127 or b in (9, 10, 13))
    if druckbar > len(kopf) * 0.9:
        return "reiner Text, keine PDF"
    return "unbekanntes Format, PDF-Kennung fehlt"


def _beschaffenheit(pfad):
    """Was ist das fuer eine Datei? Nur Art und Groesse, kein Name, kein Inhalt.

    Anlass: Unter den Fehlermeldungen tauchte zweimal der Hash
    e3b0c44298fc1c149... auf - das ist der SHA-256 der LEEREN Zeichenkette.
    Zwei der Dateien sind also vermutlich 0 Byte gross. Ob die uebrigen
    beschaedigt, verschluesselt oder gar keine PDF sind, entscheidet
    darueber, ob hier die Anlage oder der Bestand das Problem ist.
    """
    try:
        groesse = os.path.getsize(pfad)
    except OSError:
        return "Datei nicht lesbar"
    if groesse == 0:
        return "LEERE Datei (0 Byte)"
    try:
        with open(pfad, "rb") as f:
            kopf = f.read(1024)
    except OSError:
        return "Datei nicht lesbar (%d Byte)" % groesse
    if not kopf.startswith(b"%PDF"):
        return "%s (%d Byte)" % (_was_denn_dann(kopf), groesse)
    try:
        ergebnis = subprocess.run(["pdfinfo", pfad], capture_output=True,
                                  text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "PDF-Kennung da, pdfinfo nicht ausfuehrbar (%d Byte)" % groesse
    if ergebnis.returncode == 0:
        return ("gueltige PDF, die nur Docling nicht laedt (%d Byte)" % groesse)
    meldung = (ergebnis.stderr or "").strip().splitlines()
    grund = meldung[0][:60] if meldung else "ohne Meldung"
    if "Encrypted" in (ergebnis.stdout or ""):
        return "verschluesselte PDF (%d Byte)" % groesse
    return "auch poppler scheitert: %s (%d Byte)" % (grund, groesse)


def main():
    if not os.path.isdir(WURZEL):
        print("Wurzel fehlt - nichts zu tun.")
        return 1
    if not os.path.exists(ROHDATEN):
        print("Rohdatei %s fehlt. Erst bau/bildflaechen_docling.py laufen"
              " lassen - sie entsteht dort." % ROHDATEN)
        return 1

    alle = []
    for ordner, _u, namen in os.walk(WURZEL):
        for n in namen:
            if n.lower().endswith(".pdf"):
                alle.append(os.path.join(ordner, n))
    gemischt = sorted(alle)
    random.seed(20260921)
    random.shuffle(gemischt)

    gelungen = set()
    with open(ROHDATEN) as f:
        for zeile in f:
            teil = zeile.split(";")[0].strip()
            if teil.isdigit():
                gelungen.add(int(teil))
    if not gelungen:
        print("Rohdatei enthaelt keine Nummern.")
        return 1

    hoechste = max(gelungen)
    fehlend = [n for n in range(1, hoechste + 1) if n not in gelungen]
    print("Rohdatei: %d gelungene Dokumente, hoechste Nummer %d"
          % (len(gelungen), hoechste))
    print("Daraus %d Fehlschlaege des Erstversuchs.\n" % len(fehlend))
    if not fehlend:
        print("Keine Fehlschlaege - nichts nachzupruefen.")
        return 0

    geht_doch = unrettbar = leer = 0
    gruende = {}
    for nr in fehlend:
        if nr > len(gemischt):
            continue
        pfad = gemischt[nr - 1]
        z1, _b1, _d1, f1 = versuch(pfad, ERSTVERSUCH)
        z2, b2, d2, f2 = versuch(pfad, ZWEITVERSUCH)
        if z1 is not None:
            # Beim Nachmessen gelungen, obwohl es im Lauf scheiterte:
            # spricht fuer eine Ueberlastung, nicht fuer eine kaputte Datei.
            print("  Nr %3d: Erstversuch geht JETZT (%d Zeichen)%s - im Lauf"
                  " war es also kein Dateifehler"
                  % (nr, z1, LEER if z1 == 0 else ""))
            leer += 1 if z1 == 0 else 0
            geht_doch += 1
            continue
        if z2 is not None:
            print("  Nr %3d: Erstversuch scheitert, Zweitversuch liefert"
                  " %6d Zeichen und %d Abbildungen (%.0f s)%s"
                  % (nr, z2, b2, d2, LEER if z2 == 0 else ""))
            leer += 1 if z2 == 0 else 0
            geht_doch += 1
        else:
            # Nicht bei "geht nicht" stehenbleiben, sondern die Datei selbst
            # befragen: Groesse, Kennung, ob poppler sie oeffnen kann. Das
            # entscheidet, ob die ANLAGE ein Problem hat oder der BESTAND.
            art = _beschaffenheit(pfad)
            gruende[art] = gruende.get(art, 0) + 1
            print("  Nr %3d: beide Versuche scheitern · %s" % (nr, art))
            unrettbar += 1

    print("\n%d von %d kommen ueber den Zweitversuch doch durch." % (geht_doch, len(fehlend)))
    if leer:
        print("⛔ davon %d mit NULL Zeichen - formal gelungen, inhaltlich"
              " leer. Das ist der stille Ausfall aus Punkt 10, nicht ein"
              " geretteter Fall." % leer)
    print("%d bleiben liegen." % unrettbar)
    if gruende:
        print("\nWas fuer Dateien das sind:")
        for text, n in sorted(gruende.items(), key=lambda x: -x[1]):
            print("  %2d x  %s" % (n, text))
        echte = sum(n for text, n in gruende.items()
                    if text.startswith("gueltige PDF"))
        if echte:
            print("\n  ⛔ %d davon sind gueltige PDF, die poppler oeffnen"
                  " kann - dort liegt es an Docling, nicht am Bestand." % echte)
        kaputt = unrettbar - echte
        if kaputt:
            print("  → %d sind leer, beschaedigt oder keine PDF. Da kann die"
                  " Anlage nichts gewinnen - sie muss sie aber AUSSORTIEREN"
                  " statt archivieren (Punkt 10)." % kaputt)
    if geht_doch:
        print("\n⭐ Der Befund 'diese Dateien haetten weder Text noch"
              " Bildbeschreibung' war damit zu pessimistisch: Der"
              " Zweitversuch im Ablaufplan faengt sie ab. Die Messung kennt"
              " ihn nicht, der Betrieb schon.")
    if unrettbar:
        print("\n⛔ Fuer die uebrigen %d gilt der Befund weiter - und nach"
              " Punkt 10 wuerden sie trotzdem als aufgenommen im Archiv"
              " landen." % unrettbar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
