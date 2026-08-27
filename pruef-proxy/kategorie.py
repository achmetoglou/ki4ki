"""Kategorie und Themen je Dokument - aus dem Kopf, den die Aufnahme schreibt.

Die Aufnahme (n8n, Verschlagwortung) setzt jedem Dokument einen Kopf voran:
    Dokumenttyp: Practical Guide / Manual
    Sprache: German · Domain: ... · Subdomain: ...
    ## Tags / ## Keywords / ## Methoden
Bisher las das niemand (Emrach 27.08.: "wie erkennt das System, was was ist?").
Hier wird daraus eine KATEGORIE aus einer festen, je Bereich pflegbaren Liste
(dokumente/<bereich>/kategorien.txt) und eine Handvoll THEMEN (Keywords).

Rangfolge: Mensch (Kategorie im Chat gesetzt) > Kennung (DS-/BS-/M-...) >
Pruefungskatalog (erkannt) > Stichwoerter aus Dokumenttyp, Titel, Dateiname,
Tags > "Sonstiges". Kein Modellaufruf - alles deterministisch und pruefbar.
"""
import os
import re

DATEI = "kategorien.txt"

# (Kategorie, Stichwoerter deutsch/englisch - klein, Teilwort genuegt)
STANDARD = [
    ("Prüfungskatalog", ["prüfungsfragen", "pruefungsfragen", "testfragen", "fragenkatalog", "prüfungskatalog", "exam question", "question catalog", "quiz"]),
    ("Dissertation", ["dissertation", "doktorarbeit", "phd thesis", "doctoral"]),
    ("Masterarbeit", ["masterarbeit", "master thesis", "master's thesis"]),
    ("Bachelorarbeit", ["bachelorarbeit", "bachelor thesis", "bachelor's thesis"]),
    ("Projektarbeit", ["projektarbeit", "studienarbeit", "seminararbeit", "project work", "student research"]),
    ("Norm/Richtlinie", ["norm", "richtlinie", "standard", "guideline", "merkblatt", "technical rule", "dvs ", "din ", "iso ", "vdi ", "en ", "dvs-", "din-", "iso-"]),
    ("Verordnung/Gesetz", ["verordnung", "gesetz", "regulation", "ordinance", "directive", "vorschrift", "unfallverhütung", "betriebsanweisung"]),
    ("Datenblatt", ["datenblatt", "sicherheitsdatenblatt", "data sheet", "datasheet", "safety data", "sds"]),
    ("Handbuch/Anleitung", ["handbuch", "anleitung", "leitfaden", "manual", "guide", "instruction", "bedienung", "wartung", "werkzeugliste", "checkliste", "how-to"]),
    ("Protokoll/Bericht", ["prüfbericht", "pruefbericht", "protokoll", "test report", "messbericht", "gutachten", "report"]),
    ("Forschungsbericht", ["forschungsbericht", "abschlussbericht", "research report", "final report", "igf", "aif", "sachbericht"]),
    ("Fachartikel", ["fachartikel", "paper", "journal", "article", "conference", "tagungsband", "proceedings", "publikation"]),
    ("Präsentation", ["präsentation", "praesentation", "presentation", "folien", "slides", "vortrag", "textbildpr", "schulungsunterlage"]),
    ("Lehrunterlage", ["lehrunterlage", "lerneinheit", "skript", "lecture", "training", "kursunterlage", "lehrgang", "unterrichts", "tutorial", "learning unit"]),
    ("Fachbuch", ["fachbuch", "lehrbuch", "textbook", "handbook", "book", "buch", "sachbuch", "monograph"]),
    ("Sonstiges", []),
]
KENNUNG_ZU_KATEGORIE = {"DS": "Dissertation", "BS": "Bachelorarbeit", "M": "Masterarbeit", "D": "Masterarbeit",
                        "S": "Projektarbeit", "PA": "Projektarbeit"}

# Wonach jemand fragt -> Kategorie
_FRAGEWORTE = {
    "Norm/Richtlinie": ["norm", "normen", "richtlinie", "richtlinien", "dvs-richtlinien", "merkblatt", "merkblätter", "regelwerk", "regelwerke", "standards"],
    "Prüfungskatalog": ["prüfungskatalog", "prüfungskataloge", "pruefungskatalog", "fragenkatalog", "fragenkataloge", "testfragen", "prüfungsfragen", "pruefungsfragen"],
    "Verordnung/Gesetz": ["verordnung", "verordnungen", "gesetz", "gesetze", "vorschrift", "vorschriften"],
    "Datenblatt": ["datenblatt", "datenblätter", "sicherheitsdatenblatt", "sicherheitsdatenblätter"],
    "Handbuch/Anleitung": ["handbuch", "handbücher", "anleitung", "anleitungen", "leitfaden", "leitfäden", "checkliste", "checklisten"],
    "Protokoll/Bericht": ["protokoll", "protokolle", "prüfbericht", "prüfberichte", "pruefbericht", "gutachten"],
    "Forschungsbericht": ["forschungsbericht", "forschungsberichte", "abschlussbericht", "abschlussberichte"],
    "Fachartikel": ["fachartikel", "paper", "papers", "artikel", "publikation", "publikationen", "veröffentlichungen"],
    "Präsentation": ["präsentation", "präsentationen", "praesentation", "folien", "vortrag", "vorträge", "vortraege"],
    "Lehrunterlage": ["lehrunterlage", "lehrunterlagen", "lerneinheit", "lerneinheiten", "skript", "skripte", "schulungsunterlagen", "kursunterlagen"],
    "Fachbuch": ["fachbuch", "fachbücher", "fachbuecher", "lehrbuch", "lehrbücher", "bücher", "buecher", "sachbuch", "sachbücher"],
    "Dissertation": ["dissertation", "dissertationen", "doktorarbeit", "doktorarbeiten", "promotion"],
    "Masterarbeit": ["masterarbeit", "masterarbeiten"],
    "Bachelorarbeit": ["bachelorarbeit", "bachelorarbeiten"],
    "Projektarbeit": ["projektarbeit", "projektarbeiten", "studienarbeit", "studienarbeiten"],
}
_FRAGE_MUSTER = re.compile(r"\b(%s)\b" % "|".join(sorted({w for ws in _FRAGEWORTE.values() for w in ws}, key=len, reverse=True)), re.I)


def liste(wurzel=None):
    """[(Kategorie, [stichwoerter])] - aus kategorien.txt des Bereichs, sonst Standard."""
    if wurzel:
        pfad = os.path.join(wurzel, DATEI)
        try:
            with open(pfad, encoding="utf-8") as fh:
                aus = []
                for zeile in fh:
                    zeile = zeile.strip()
                    if not zeile or zeile.startswith("#"):
                        continue
                    name, _, rest = zeile.partition(":")
                    woerter = [w.strip().lower() for w in rest.split(",") if w.strip()]
                    aus.append((name.strip(), woerter))
                if aus:
                    if not any(n == "Sonstiges" for n, _ in aus):
                        aus.append(("Sonstiges", []))
                    return aus
        except OSError:
            pass
    return list(STANDARD)


def datei_text():
    """Inhalt fuer eine frische kategorien.txt - der Standard, zum Bearbeiten."""
    zeilen = ["# Kategorien dieses Bereichs - eine je Zeile: Name: Stichwort, Stichwort, ...",
              "# Die Anlage ordnet jedes Dokument der ERSTEN Kategorie zu, deren Stichwort im",
              "# Dokumenttyp, Titel, Dateinamen oder in den Tags der Aufnahme vorkommt.",
              "# Reihenfolge = Vorrang. Aenderungen wirken beim naechsten Nachtragen (Minuten).",
              "# Von Hand gesetzte Kategorien (im Chat: 'Kategorie von X ist Y') bleiben bestehen.", ""]
    for name, woerter in STANDARD:
        zeilen.append("%s: %s" % (name, ", ".join(woerter)))
    return "\n".join(zeilen) + "\n"


def namen(wurzel=None):
    return [n for n, _ in liste(wurzel)]


def aus_kopf(text):
    """Die Kopfzeilen der Aufnahme lesen (vor '## Inhalt')."""
    kopf = (text or "")
    i = kopf.find("## Inhalt")
    if i > 0:
        kopf = kopf[:i]
    kopf = kopf[:6000]
    aus = {"dokumenttyp": "", "sprache": "", "domain": "", "subdomain": "", "tags": [], "keywords": [], "methoden": []}
    for feld, schl in (("Dokumenttyp", "dokumenttyp"), ("Sprache", "sprache"), ("Domain", "domain"), ("Subdomain", "subdomain")):
        m = re.search(r"(?m)^%s:\s*(.+)$" % feld, kopf)
        if m:
            aus[schl] = m.group(1).strip()
    for abschnitt, schl in (("Tags", "tags"), ("Keywords", "keywords"), ("Methoden", "methoden")):
        m = re.search(r"(?ms)^## %s\s*\n(.*?)(?=^## |\Z)" % abschnitt, kopf)
        if m:
            aus[schl] = [re.sub(r"^[-*]\s*", "", z).strip() for z in m.group(1).splitlines() if z.strip().startswith(("-", "*"))][:20]
    return aus


def zuordnen(kopf, dateiname="", titel="", kennung="", ist_katalog=False, wurzel=None):
    """Die Kategorie eines Dokuments - deterministisch."""
    if ist_katalog:
        return "Prüfungskatalog"
    m = re.match(r"([A-Za-z]{1,3})[-_ ]?\d", str(kennung or dateiname or "").strip())
    if m and m.group(1).upper() in KENNUNG_ZU_KATEGORIE:
        return KENNUNG_ZU_KATEGORIE[m.group(1).upper()]
    k = kopf or {}
    kats = liste(wurzel)
    # Vorrang: was die Aufnahme als Dokumenttyp erkannt hat ("Practical Guide /
    # Manual") vor Titel vor Dateiname+Tags - sonst macht "DVS" im Dateinamen
    # aus jedem Leitfaden eine Norm.
    for stoff in (str(k.get("dokumenttyp") or ""), str(titel or ""),
                  str(dateiname or "") + " " + " ".join(k.get("tags") or [])):
        stoff = " " + re.sub(r"[_\-./]+", " ", stoff.lower()) + " "
        if not stoff.strip():
            continue
        # das laengste passende Stichwort gewinnt ("werkzeugliste" vor "dvs ")
        beste = max(((len(w), name) for name, woerter in kats for w in woerter if w and w in stoff), default=None)
        if beste:
            return beste[1]
    return "Sonstiges"


def themen(kopf, hoechstens=6):
    """Themen = die Keywords der Aufnahme (deutsch bevorzugt), sonst Tags."""
    k = kopf or {}
    aus = []
    for w in (k.get("keywords") or []) + (k.get("tags") or []):
        w = w.strip().strip(".")
        if 2 < len(w) <= 40 and w.lower() not in {x.lower() for x in aus}:
            aus.append(w)
        if len(aus) >= hoechstens:
            break
    return aus


def gefragte(frage):
    """Nach welcher Kategorie fragt jemand? -> (Kategorie, Wort) oder (None, None)."""
    m = _FRAGE_MUSTER.search(frage or "")
    if not m:
        return None, None
    wort = m.group(1).lower()
    for name, woerter in _FRAGEWORTE.items():
        if wort in woerter:
            return name, wort
    return None, None


def passt(kategorie_dokument, gefragt):
    return (kategorie_dokument or "").strip().lower() == (gefragt or "").strip().lower()
