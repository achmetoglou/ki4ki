#!/usr/bin/env python3
"""
Die Fundstelle im ORIGINAL-PDF - Seite und Markierung.

Warum das noetig ist: Doclings Seitenmarken [Seite N] sind eine gute
Schaetzung, aber keine Wahrheit. Gemessen an 12 Arbeiten stimmten 7, zwei
lagen eine Seite daneben, drei zwei Seiten. Ursache duerften Seiten sein,
die beim Einlesen keine Marke erzeugen.

Eine falsche Seitenangabe ist schlimmer als keine. Also wird das Zitat im
PDF selbst gesucht - das PDF ist die Instanz, nicht unsere Marke. Dieselbe
Suche liefert nebenbei die Koordinaten fuer die gelbe Markierung.

Gebraucht werden nur poppler (pdftotext, pdftoppm) und PIL, beides ist da.
Keine zusaetzlichen Pakete.
"""
import html
import os
import re
import subprocess
import unicodedata
import threading

EINGANG = (os.environ.get("KI4KI_PDFS")
           or os.path.expanduser("~/ki4ki/dokumente"))

# Seitentexte je PDF, damit nicht bei jeder Frage neu ausgelesen wird
_SEITEN = {}
_SPERRE = threading.Lock()

# Stamm -> voller Pfad. Wird beim ersten Zugriff aufgebaut.
_PFADE = {}
# Derselbe Bestand, aber unter dem Namen, den AnythingLLM vergibt.
_UMGEFORMT = {}
_PFADSPERRE = threading.Lock()


def _index_bauen():
    """Alle PDFs unter EINGANG erfassen - auch in Unterordnern.

    Die Abteilungen liegen als eigene Ordner im Eingang (inbox/auw/ ...).
    Wer nur die oberste Ebene durchsucht, findet ihre Dokumente nie - und
    der Beleg-Klick bleibt fuer eine ganze Abteilung stumm, ohne dass
    irgendwo ein Fehler steht.

    os.walk statt glob auch deshalb, weil glob eckige Klammern im
    Dateinamen als Zeichenklasse liest - Namen wie "[Ehr06] ..." kommen
    in Fachliteratur staendig vor.
    """
    neu, umgeformt, mehrdeutig = {}, {}, set()
    for wurzel, _, dateien in os.walk(EINGANG):
        for d in dateien:
            if d.lower().endswith(".pdf"):
                stamm = d[:-4]
                voll = os.path.join(wurzel, d)
                # Bei gleichem Namen in mehreren Ordnern gewinnt der erste
                # Fund; die oberste Ebene wird zuerst durchlaufen.
                neu.setdefault(stamm, voll)
                # Zweiter Schluessel, so geschrieben wie AnythingLLM ihn
                # ablegt. Siehe _wie_anythingllm().
                k = _wie_anythingllm(stamm)
                if k in umgeformt and umgeformt[k] != voll:
                    mehrdeutig.add(k)
                umgeformt.setdefault(k, voll)
    # Was nicht eindeutig ist, fliegt raus: lieber kein Sprung als ein
    # Sprung in das falsche Dokument.
    for k in mehrdeutig:
        umgeformt.pop(k, None)
    return neu, umgeformt


def _wie_anythingllm(stamm):
    """Einen Namen auf die Grundform bringen, die beide Seiten teilen.

    AnythingLLM schreibt Dateinamen um, bevor es sie ablegt - und zwar
    mehrfach: Leerzeichen und Kommas werden zu Bindestrichen, Klammern
    fallen weg, Umlaute verlieren die Punkte, Doppel-Bindestriche werden
    zusammengezogen.

        [Ehr06] Faserverbund...   ->  Ehr06-Faserverbund...
        LE Ultraschallprüfung     ->  LE-Ultraschallprufung
        S-00000 .pdf              ->  S-00000-

    Der Beleg in einer Antwort traegt deshalb den umgeformten Namen, der
    Dateiindex aber den echten. Diese Funktion baut die Umformung NICHT
    nach - das waere ein Spiel, das der naechste Dateiname gewinnt -,
    sondern bringt beide Seiten auf dieselbe Grundform. Was danach gleich
    ist, ist dasselbe Dokument.
    """
    n = unicodedata.normalize("NFKD", stamm)
    n = "".join(c for c in n if not unicodedata.combining(c))   # ü -> u
    n = n.replace("ß", "ss")
    n = re.sub(r"[^A-Za-z0-9]+", "-", n)
    return n.strip("-").lower()


def pdf_pfad(stamm):
    """Vollen Pfad zu einem Dokument finden, egal in welchem Ordner.

    Zwei Wege, in dieser Reihenfolge:
      1. Der genaue Dateiname. So heisst es, wenn nichts umgeformt wurde.
      2. Der Name in AnythingLLM-Schreibweise. Das trifft alles mit
         Leerzeichen - gemessen 19 von 1198 Dokumenten der
         Bibliothek und 42 von 52 der Aus- und Weiterbildung.

    Fehlt der Stamm in beiden, wird einmal neu gesucht: So sind frisch
    hochgeladene Dokumente sofort anklickbar, ohne Neustart.
    """
    global _PFADE, _UMGEFORMT

    def nachsehen():
        p = _PFADE.get(stamm)
        if p and os.path.exists(p):
            return p
        p = _UMGEFORMT.get(_wie_anythingllm(stamm))
        return p if p and os.path.exists(p) else None

    with _PFADSPERRE:
        if not _PFADE:
            _PFADE, _UMGEFORMT = _index_bauen()
        pfad = nachsehen()
        if pfad:
            return pfad
        _PFADE, _UMGEFORMT = _index_bauen()
        return nachsehen()


def _glatt(s):
    return re.sub(r"\s+", " ", s).strip().lower()


# Marken, die die Belegpruefung SELBST in das Zitat schreibt. Sie stehen in
# keinem PDF - werden sie mitgesucht, findet die Suche nichts.
_MARKEN = re.compile(r"\[nicht wiedergefunden:[^\]]*\]|\[\s*(?:…|\.\.\.)\s*\]")


def ohne_pruefmarken(zitat):
    """Das Zitat ohne die Marken der eigenen Belegpruefung.

    An vier Faellen gemessen: Ein Zitat, das mit
    "[nicht wiedergefunden: ...]" beginnt, liess kaesten() nach genau
    diesen Woertern suchen - sie stehen naturgemaess in keinem Dokument,
    also gab es keinen Startpunkt und keine Markierung. Der Nutzer sah
    eine Seite ohne gelbe Stelle und hielt den Beleg fuer erfunden.
    Betroffen war jedes Zitat aus mehreren Bruchstuecken.
    """
    return re.sub(r"\s+", " ", _MARKEN.sub(" ", zitat or "")).strip()


def seitentexte(stamm):
    """Alle Seiten eines PDFs als Liste. Ein einziger Aufruf je Dokument.

    pdftotext trennt Seiten mit dem Seitenvorschub \\f - damit laesst sich
    die Seitenzahl abzaehlen, ohne je Seite einen eigenen Aufruf zu starten.
    """
    with _SPERRE:
        if stamm in _SEITEN:
            return _SEITEN[stamm]
    pfad = pdf_pfad(stamm) or os.path.join(EINGANG, stamm + ".pdf")
    seiten = []
    if os.path.exists(pfad):
        try:
            aus = subprocess.run(["pdftotext", "-layout", pfad, "-"],
                                 capture_output=True, text=True,
                                 timeout=300).stdout
            seiten = aus.split("\f")
            # Der letzte Seitenvorschub erzeugt einen leeren Rest - der ist
            # keine Seite, sonst zaehlt das Dokument eine zu viel.
            if seiten and not seiten[-1].strip():
                seiten.pop()
        except Exception:
            seiten = []
    with _SPERRE:
        _SEITEN[stamm] = seiten
    return seiten


def hat_textlayer(stamm):
    """Laesst sich in diesem PDF ueberhaupt nach Text suchen?

    Manche Dokumente im Bestand sind gescannt oder als Bild abgelegt. Ihr
    Inhalt steht dann nur im Markdown, das Docling erzeugt hat - im PDF
    selbst gibt es keinen Text, in dem sich eine Belegstelle finden liesse.
    Gemessen: "Testfragen DVS 2290" traegt auf allen sieben
    Seiten nur die Fusszeile "Seite N von 7", und
    "DVS_2213-1_Teil 1_10_2025-WZ" auf 192 Seiten im Schnitt 27 Zeichen.

    Ohne diese Unterscheidung meldet die Fundstellen-Ansicht "Auf dieser
    Seite steht die belegte Stelle nicht" - und das ist dort schlicht
    falsch. Sie steht da, nur nicht maschinenlesbar. Der Leser haelt den
    Beleg fuer erfunden, obwohl er stimmt.

    Schwelle 20 Zeichen je Seite im Schnitt: Eine Seite, die nur eine
    Fusszeile traegt, liegt darunter; jede Seite mit einem einzigen
    Absatz liegt deutlich darueber.
    """
    seiten = [s for s in seitentexte(stamm) if s.strip()]
    if not seiten:
        return False
    return sum(len(s.strip()) for s in seiten) / len(seiten) >= 20


def finde_seite(stamm, zitat, vermutung=None):
    """Auf welcher PDF-Seite steht das Zitat wirklich?

    Gesucht wird mit einem markanten Ausschnitt. Liegt eine Vermutung aus
    der Seitenmarke vor, wird zuerst in ihrer Naehe gesehen - das trifft
    fast immer und spart die Suche ueber das ganze Dokument.

    Liefert (Seitenzahl, gefundener_Ausschnitt) oder (None, None).
    """
    seiten = seitentexte(stamm)
    if not seiten:
        return None, None

    nadel = _glatt(ohne_pruefmarken(zitat))
    if len(nadel) < 20:
        return None, None
    # ein Stueck aus der Mitte ist robuster als der Anfang: Zitatanfaenge
    # werden vom Modell gern veraendert
    kern = nadel[:90] if len(nadel) < 160 else nadel[20:130]

    reihe = range(len(seiten))
    if vermutung:
        nah = [i for i in range(max(0, vermutung - 4), min(len(seiten), vermutung + 4))]
        reihe = nah + [i for i in range(len(seiten)) if i not in set(nah)]

    for i in reihe:
        if kern in _glatt(seiten[i]):
            return i + 1, kern
    # zweiter Anlauf mit einem kuerzeren Stueck
    kurz = kern[:45]
    if len(kurz) >= 20:
        for i in reihe:
            if kurz in _glatt(seiten[i]):
                return i + 1, kurz
    return None, None


def _woerter(pfad, seite):
    """Wortkoordinaten einer Seite (in Punkt), plus Seitengroesse."""
    try:
        xml = subprocess.run(
            ["pdftotext", "-bbox-layout", "-f", str(seite), "-l", str(seite),
             pfad, "-"], capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return [], (612.0, 792.0)
    m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', xml)
    groesse = (float(m.group(1)), float(m.group(2))) if m else (612.0, 792.0)
    woerter = []
    for w in re.finditer(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
            r'yMax="([\d.]+)">(.*?)</word>', xml, re.S):
        woerter.append((float(w.group(1)), float(w.group(2)),
                        float(w.group(3)), float(w.group(4)),
                        html.unescape(w.group(5))))
    return woerter, groesse


def kaesten(stamm, seite, zitat):
    """Rechtecke, die das Zitat auf der Seite umschliessen (in Punkt).

    Gesucht wird die laengste Folge von Woertern der Seite, die zum Zitat
    passt. Je Textzeile ein Rechteck - so folgt die Markierung dem Umbruch
    statt einen Block ueber den halben Absatz zu ziehen.
    """
    pfad = pdf_pfad(stamm) or os.path.join(EINGANG, stamm + ".pdf")
    if not os.path.exists(pfad):
        return [], (612.0, 792.0)
    woerter, groesse = _woerter(pfad, seite)
    if not woerter:
        return [], groesse

    ziel = _glatt(ohne_pruefmarken(zitat)).split()
    if not ziel:
        return [], groesse
    seitenwoerter = [_glatt(w[4]) for w in woerter]

    # Startpunkt: wo die ersten drei Zitatwoerter stehen
    start = None
    for i in range(len(seitenwoerter)):
        if seitenwoerter[i:i + 3] == ziel[:3]:
            start = i
            break
    if start is None:
        for i in range(len(seitenwoerter)):
            if seitenwoerter[i:i + 2] == ziel[:2]:
                start = i
                break
    if start is None:
        # ⭐ STICHWORT-RUECKFALL: Keine Wortfolge gefunden - die
        #   Aussage ist paraphrasiert (das Modell zitiert nicht woertlich).
        #   Dann die markanten Fachbegriffe (ab 6 Zeichen) EINZELN markieren,
        #   wo sie auf der Seite stehen - je Wort eine Box, nicht zeilenweise
        #   (sonst wuerde die halbe Zeile gelb). So leuchtet die relevante
        #   Stelle auf, auch ohne woertliches Zitat. Zitiert das Modell nicht
        #   woertlich, entstehen sonst gar keine gelben Stellen.
        marken = {w for w in ziel if len(w) >= 6}
        boxen = [list(woerter[i][:4]) for i, sw in enumerate(seitenwoerter)
                 if sw in marken][:30]
        if not boxen:
            return [], groesse
        return sorted(boxen, key=lambda r: r[1]), groesse

    # von dort mitlaufen, kleine Abweichungen ueberspringen
    treffer, j, fehl = [], 0, 0
    for i in range(start, len(seitenwoerter)):
        if j >= len(ziel):
            break
        if seitenwoerter[i] == ziel[j]:
            treffer.append(woerter[i]); j += 1; fehl = 0
        elif j + 1 < len(ziel) and seitenwoerter[i] == ziel[j + 1]:
            treffer.append(woerter[i]); j += 2; fehl = 0
        else:
            treffer.append(woerter[i]); fehl += 1
            if fehl > 4:
                treffer = treffer[:-5]
                break
    if not treffer:
        return [], groesse

    # je Zeile ein Rechteck (gleiche Hoehe = gleiche Zeile)
    zeilen = {}
    for x0, y0, x1, y1, _ in treffer:
        schluessel = round(y0, 1)
        naechste = min(zeilen, key=lambda k: abs(k - schluessel), default=None)
        if naechste is not None and abs(naechste - schluessel) < 4:
            schluessel = naechste
        a = zeilen.setdefault(schluessel, [x0, y0, x1, y1])
        a[0] = min(a[0], x0); a[1] = min(a[1], y0)
        a[2] = max(a[2], x1); a[3] = max(a[3], y1)
    return sorted(zeilen.values(), key=lambda r: r[1]), groesse


def seitenbild(stamm, seite, zitat=None, dpi=150):
    """Die Seite als PNG, das Zitat gelb hinterlegt. Liefert Bytes."""
    from PIL import Image, ImageDraw
    import io
    pfad = pdf_pfad(stamm) or os.path.join(EINGANG, stamm + ".pdf")
    if not os.path.exists(pfad):
        return None
    # pdftoppm schreibt mit -singlefile NICHT auf die Standardausgabe,
    # sondern nur in eine Datei. Also ueber eine Zwischendatei.
    import tempfile
    with tempfile.TemporaryDirectory() as ordner:
        ziel = os.path.join(ordner, "seite")
        try:
            subprocess.run(
                ["pdftoppm", "-f", str(seite), "-l", str(seite), "-r", str(dpi),
                 "-png", "-singlefile", pfad, ziel],
                capture_output=True, timeout=300)
        except Exception:
            return None
        if not os.path.exists(ziel + ".png"):
            return None
        bild = Image.open(ziel + ".png").convert("RGB")
        bild.load()

    if zitat:
        rechtecke, (bw, bh) = kaesten(stamm, seite, zitat)
        if rechtecke:
            # Punkt -> Bildpunkt. pdftoppm rendert die Seite auf dpi/72.
            sx = bild.width / bw if bw else dpi / 72.0
            sy = bild.height / bh if bh else dpi / 72.0
            schicht = Image.new("RGBA", bild.size, (0, 0, 0, 0))
            stift = ImageDraw.Draw(schicht)
            for x0, y0, x1, y1 in rechtecke:
                stift.rectangle([x0 * sx - 2, y0 * sy - 2, x1 * sx + 2, y1 * sy + 2],
                                fill=(255, 235, 59, 110),
                                outline=(240, 180, 0, 220), width=2)
            bild = Image.alpha_composite(bild.convert("RGBA"), schicht).convert("RGB")

    aus = io.BytesIO()
    bild.save(aus, format="PNG", optimize=True)
    return aus.getvalue()


def seitenzahl(stamm):
    seiten = seitentexte(stamm)
    return len(seiten) if seiten else 0
