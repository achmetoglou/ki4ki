"""Kategorie und Themen je Dokument - aus dem Kopf, den die Aufnahme schreibt.

Die Aufnahme (n8n, Verschlagwortung) setzt jedem Dokument einen Kopf voran:
    Dokumenttyp: Practical Guide / Manual
    Sprache: German · Domain: ... · Subdomain: ...
    ## Tags / ## Keywords / ## Methoden
Bisher las das niemand (Rueckmeldung 27.08.: "wie erkennt das System, was was ist?").
Hier wird daraus eine KATEGORIE aus einer festen, je Bereich pflegbaren Liste
(dokumente/<bereich>/kategorien.txt) und eine Handvoll THEMEN (Keywords).

Rangfolge: Mensch (Kategorie im Chat gesetzt) > Pruefungskatalog (erkannt) >
Kennung (DS-/BS-/M-...) > Dokumenttyp > Titel > Dateiname/Tags >
"Sonstiges". Kein Modellaufruf - alles deterministisch und pruefbar.

⛔ ZWEI EINSCHRAENKUNGEN AN DER KENNUNG (sie stand frueher ganz oben und hat
   blind gewonnen, siehe _KENNUNG_MUSTER und GESCHAEFTLICH):
   1. Sie gilt nur in der Schreibweise des Hochschulbestands (DS-24-005).
      "PA-2026-001-Preisanfrage" ist keine Projektarbeit.
   2. Meldet die Aufnahme ausdruecklich eine Geschaeftsunterlage
      ("Invoice"), schlaegt das die Kennung. Sonst waere "M-24-0042"
      (Mahnung) fuer immer eine Masterarbeit.

⛔ KEINE der Listen hier darf GESCHLOSSEN sein. Der Bestand ist gemischt:
   neben Hochschulschriften liegen die Geschaeftsunterlagen eines
   Auftragslabors. Was hier fehlt, wird nicht "unbekannt", sondern FALSCH
   einsortiert - und das steht danach in der Aufnahme. Die Gegenproben dazu
   stehen in kategorietest.py.
"""
import os
import re

DATEI = "kategorien.txt"

# (Kategorie, Stichwoerter deutsch/englisch - klein, Teilwort genuegt)
STANDARD = [
    # ⚠ "exam catalog" deckt auch "Exam catalogue" ab (Teilwortvergleich) -
    #   und genau DIESEN Wert liefert die Aufnahme. Bisher stand er in keiner
    #   Zeile: ein Pruefungskatalog fiel ueber den Dokumenttyp auf
    #   "Sonstiges", solange ihn nicht der Pruefungskatalog-Erkenner selbst
    #   gefunden hatte (ist_katalog). Gefunden von kategorietest.py.
    ("Prüfungskatalog", ["prüfungsfragen", "pruefungsfragen", "testfragen", "fragenkatalog", "prüfungskatalog", "exam question", "exam catalog", "question catalog", "quiz"]),
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
    # --- Geschaeftsunterlagen -------------------------------------------
    # Diese Liste war fuer HOCHSCHULSCHRIFTEN gebaut. Im Bestand liegen
    # inzwischen die Geschaeftsunterlagen eines Auftragslabors. Ohne diese
    # Zeilen faellt eine Rechnung auf "Sonstiges" - oder schlimmer auf
    # "Datenblatt", weil sie Zahlen und eine Tabelle traegt.
    #
    # ⚠ Der Vergleich unten ist ein TEILWORTvergleich. Ein Stichwort mit
    #   Leerzeichen davor trifft deshalb nur den Wortanfang: " rechnung "
    #   muss so dastehen, sonst wird jede "Berechnung" und jedes
    #   "Rechnungswesen" zur Rechnung. Das Muster darunter ersetzt
    #   - _ . / durch Leerzeichen, "Rechnung_274821.pdf" trifft also.
    ("Rechnung", [" rechnung ", " rechnungen ", " rechnungsnummer", " rechnungsdatum", " schlussrechnung", " teilrechnung", " abschlagsrechnung", "invoice", " gutschrift", "credit note"]),
    ("Mahnung", [" mahnung ", " mahnungen ", " zahlungserinnerung", " dunning", " reminder "]),
    ("Angebot", [" angebot ", " angebote ", " angebotsnummer", "kostenvoranschlag", "quotation", " offer "]),
    ("Preisanfrage", [" preisanfrage", " angebotsanfrage", "request for quotation", " rfq "]),
    ("Bestellung", [" bestellung ", " bestellungen ", " bestellnummer", " bestellschein", "purchase order"]),
    ("Auftragsbestätigung", [" auftragsbestätigung", " auftragsbestaetigung", "order confirmation"]),
    ("Lieferschein", [" lieferschein", "delivery note", " packliste", "packing list"]),
    ("Anschreiben", [" anschreiben ", " begleitschreiben", "cover letter", "geschäftsbrief", "geschaeftsbrief"]),
    ("Reisekostenabrechnung", [" reisekosten", " spesen", " spesenabrechnung", "expense report"]),
    ("Laufzettel", [" laufzettel", "routing slip", " begleitzettel"]),
    ("Vertrag/Vereinbarung", [" vertrag ", " verträge ", " vertraege ", " vertragsnummer", " werkvertrag", " rahmenvertrag", " contract", "agreement", " vereinbarung "]),
    ("Geheimhaltungsvereinbarung", ["geheimhaltungsvereinbarung", "verschwiegenheitserklärung", "verschwiegenheitserklaerung", "non disclosure", "nondisclosure", " nda "]),
    ("Sonstiges", []),
]

# Kategorien OHNE Hochschulbezug. Sagt die Aufnahme ausdruecklich, dass sie
# eine Rechnung vor sich hat, schlaegt das die Kennung aus dem Dateinamen -
# sonst bliebe "M-24-0042" (Mahnung) fuer immer eine Masterarbeit.
# ⚠ Pflegt ein Bereich eine eigene kategorien.txt mit anderen Namen, greift
#   die Sperre dort nicht. Sie kann nur nicht schaden: ohne Treffer bleibt
#   alles so, wie es vorher war.
GESCHAEFTLICH = {"Rechnung", "Mahnung", "Angebot", "Preisanfrage", "Bestellung",
                 "Auftragsbestätigung", "Lieferschein", "Anschreiben",
                 "Reisekostenabrechnung", "Laufzettel", "Vertrag/Vereinbarung",
                 "Geheimhaltungsvereinbarung"}

KENNUNG_ZU_KATEGORIE = {"DS": "Dissertation", "BS": "Bachelorarbeit", "M": "Masterarbeit", "D": "Masterarbeit",
                        "S": "Projektarbeit", "PA": "Projektarbeit"}

# ⛔ Die Kennung galt bisher fuer JEDEN Namen, der mit ein bis drei Buchstaben
# vor einer Ziffer beginnt - und zwar VOR jeder Stichwortpruefung. Damit wurde
# "PA-2026-001-Preisanfrage" zur Projektarbeit, "M-2026-0042" (Mahnung) zur
# Masterarbeit und "D-2026-..." ebenfalls zur Masterarbeit.
#
# Der Hochschulbestand schreibt die Kennung immer gleich: Buchstaben,
# ZWEIstelliges Jahr, laufende Nummer - DS-24-005, S-23-001, PA-24-002
# (belegt in bestand.py:765-767 und doku/entwicklung/BUGS_UND_FIXES.md:541).
# Eine Geschaeftsnummer traegt die Jahreszahl vierstellig und faellt damit
# heraus. Das zweite Trennzeichen ist Pflicht: ohne es wuerde "PA-2026-001"
# wieder als "PA" + "20" gelesen.
#
# ⚠ Eine Kennung OHNE Trennzeichen ("DS24005") gilt damit nicht mehr. Im
#   Bestand kommt diese Schreibweise nicht vor; taucht sie doch auf, gehoert
#   sie hier ergaenzt - und nicht das Muster wieder aufgeweicht.
_KENNUNG_MUSTER = re.compile(r"([A-Za-z]{1,3})[-_ ]?(\d{2})[-_ ]\d")

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
    # ⛔ Ohne diese Zeilen bekommt "Zeig mir alle Angebote" KEINEN
    #   Kategoriefilter: gefragte() gibt (None, None) zurueck, und die
    #   Bestandsauskunft faellt auf die allgemeine Liste ueber ALLES
    #   zurueck. Gefragt ist aber nach einer Art von Unterlage.
    "Rechnung": ["rechnung", "rechnungen", "gutschrift", "gutschriften"],
    "Mahnung": ["mahnung", "mahnungen", "zahlungserinnerung", "zahlungserinnerungen"],
    "Angebot": ["angebot", "angebote", "kostenvoranschlag", "kostenvoranschläge", "kostenvoranschlaege"],
    "Preisanfrage": ["preisanfrage", "preisanfragen", "angebotsanfrage", "angebotsanfragen"],
    "Bestellung": ["bestellung", "bestellungen"],
    "Auftragsbestätigung": ["auftragsbestätigung", "auftragsbestätigungen", "auftragsbestaetigung", "auftragsbestaetigungen"],
    "Lieferschein": ["lieferschein", "lieferscheine"],
    "Anschreiben": ["anschreiben", "begleitschreiben"],
    "Reisekostenabrechnung": ["reisekostenabrechnung", "reisekostenabrechnungen", "reisekosten", "spesenabrechnung", "spesenabrechnungen"],
    "Laufzettel": ["laufzettel"],
    "Vertrag/Vereinbarung": ["vertrag", "verträge", "vertraege", "vereinbarung", "vereinbarungen", "werkvertrag", "werkverträge", "rahmenvertrag", "rahmenverträge"],
    "Geheimhaltungsvereinbarung": ["geheimhaltungsvereinbarung", "geheimhaltungsvereinbarungen", "verschwiegenheitserklärung", "verschwiegenheitserklärungen", "nda"],
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
                    # ⛔ HIER STAND EIN UEBERSCHREIBEN, und es war falsch.
                    #   Es hat die Standardkategorien in eine bereichseigene
                    #   Liste nachgetragen - gut gemeint (sonst bliebe die
                    #   Liste in so einem Bereich geschlossen), aber es nimmt
                    #   dem Betreiber die Entscheidung aus der Hand. Eine
                    #   eigene kategorien.txt ERSETZT den Standard; genau das
                    #   haelt die Pruefung "eigene Liste je Bereich gilt" fest,
                    #   und sie ist deshalb rot geworden (25.09.).
                    #
                    # ⭐ Der richtige Weg ist kein stilles Nachtragen: Wer
                    #   eine eigene Liste fuehrt und Geschaeftsunterlagen
                    #   aufnimmt, traegt die Kategorien dort ein - oder
                    #   loescht die Datei und faellt auf den Standard zurueck.
                    #   Eine Anlage, die die Wahl des Betreibers stillschweigend
                    #   erweitert, ist schlimmer als eine, die zu wenig kennt:
                    #   Die eine faellt auf, die andere nicht.
                    aus = [(n, w) for n, w in aus if n != "Sonstiges"]
                    aus.append(("Sonstiges", []))
                    return aus
        except OSError:
            pass
    return list(STANDARD)


def datei_text():
    """Inhalt fuer eine frische kategorien.txt - der Standard, zum Bearbeiten."""
    zeilen = ["# Kategorien dieses Bereichs - eine je Zeile: Name: Stichwort, Stichwort, ...",
              "# Die Anlage sieht der Reihe nach im Dokumenttyp, im Titel und im Dateinamen",
              "# plus Tags nach. Im selben Stueck Text gewinnt das LAENGSTE passende",
              "# Stichwort - nicht die oberste Zeile ('werkzeugliste' schlaegt 'dvs ').",
              "# Die Reihenfolge hier entscheidet also nichts; genauere Stichwoerter schon.",
              "# Aenderungen wirken beim naechsten Nachtragen (Minuten).",
              "# Was hier fehlt, aber zum Standard der Anlage gehoert, gilt trotzdem: eine",
              "# Liste, die einmal geschrieben wurde, soll nicht neue Dokumentarten aussperren.",
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
    m = re.search(r"(?m)^Kategorie \(Vorgabe\):\s*(.+)$", kopf)
    aus["vorgabe"] = m.group(1).strip() if m else ""
    m = re.search(r"(?m)^Themen \(Vorgabe\):\s*(.+)$", kopf)
    aus["themen_vorgabe"] = [t.strip() for t in m.group(1).split("/") if t.strip()] if m else []
    for feld, schl in (("Dokumenttyp", "dokumenttyp"), ("Sprache", "sprache"), ("Domain", "domain"), ("Subdomain", "subdomain")):
        m = re.search(r"(?m)^%s:\s*(.+)$" % feld, kopf)
        if m:
            aus[schl] = m.group(1).strip()
    for abschnitt, schl in (("Tags", "tags"), ("Keywords", "keywords"), ("Methoden", "methoden")):
        m = re.search(r"(?ms)^## %s\s*\n(.*?)(?=^## |\Z)" % abschnitt, kopf)
        if m:
            aus[schl] = [re.sub(r"^[-*]\s*", "", z).strip() for z in m.group(1).splitlines() if z.strip().startswith(("-", "*"))][:20]
    m = re.search(r"(?ms)^## Kurzfassung \(Aufnahme\)\s*\n(.*?)(?=^## |\Z)", kopf)
    aus["kurzfassung"] = re.sub(r"\s+", " ", m.group(1)).strip()[:1500] if m else ""
    return aus


def zuordnen(kopf, dateiname="", titel="", kennung="", ist_katalog=False, wurzel=None):
    """Die Kategorie eines Dokuments - deterministisch."""
    k0 = kopf or {}
    if k0.get("vorgabe"):
        # Unterordner im Eingang: der Mensch hat es beim Hochladen gesagt
        v = str(k0["vorgabe"]).strip()
        for name in namen(wurzel):
            if name.lower() == v.lower() or name.lower().split("/")[0] == v.lower():
                return name
        g, _w = gefragte(v)            # "Normen" -> Norm/Richtlinie, "Handbücher" -> Handbuch/Anleitung
        if g:
            return g
        # ⛔ HIER STAND "return v[:40]" - der Ordnername WOERTLICH als
        #   Kategorie. Gemessen 25.09. an einem echten Bestand: Die Ordner
        #   heissen dort nach KUNDEN, nicht nach Kategorien. 44 von 56
        #   Dokumenten trugen deshalb die Kategorie
        #   "Lanxess Deutschland GmbH, Chempark Dorma" - der Kundenname,
        #   auf 40 Zeichen abgeschnitten. Die Frage "Welche Rechnungen
        #   haben wir?" fand NICHTS, obwohl die Rechnungen da waren und
        #   die Kategorie "Rechnung" am selben Tag eingefuehrt wurde.
        #
        # \u2b50 Die Absicht war richtig: Ein Ordner "Normen" soll die
        #   Kategorie setzen. Das tut er weiter - ueber namen() und
        #   gefragte(). Nur wird ein Name, den NIEMAND als Kategorie kennt,
        #   nicht mehr zu einer gemacht. Eine erfundene Kategorie sieht aus
        #   wie eine echte und ist deshalb schlimmer als keine.
        #
        # \u26a0 Die Angabe geht nicht verloren: Sie steht als Thema in der
        #   Aufnahme und bleibt durchsuchbar. Verloren geht nur der
        #   faelschliche Anspruch, eine Kategorie zu sein.
    if ist_katalog:
        return "Prüfungskatalog"
    k = kopf or {}
    kats = liste(wurzel)
    # Vorrang: was die Aufnahme als Dokumenttyp erkannt hat ("Practical Guide /
    # Manual") vor Titel vor Dateiname+Tags - sonst macht "DVS" im Dateinamen
    # aus jedem Leitfaden eine Norm.
    typ_kategorie = _stichwort_treffer(str(k.get("dokumenttyp") or ""), kats)
    # Die Kennung darf nicht mehr blind gewinnen: sie gilt nur in der Form des
    # Hochschulbestands (siehe _KENNUNG_MUSTER) und nur, solange die Aufnahme
    # nicht ausdruecklich eine Geschaeftsunterlage gemeldet hat.
    m = _KENNUNG_MUSTER.match(str(kennung or dateiname or "").strip())
    if (m and m.group(1).upper() in KENNUNG_ZU_KATEGORIE
            and typ_kategorie not in GESCHAEFTLICH):
        return KENNUNG_ZU_KATEGORIE[m.group(1).upper()]
    if typ_kategorie:
        return typ_kategorie
    for stoff in (str(titel or ""),
                  str(dateiname or "") + " " + " ".join(k.get("tags") or [])):
        treffer = _stichwort_treffer(stoff, kats)
        if treffer:
            return treffer
    return "Sonstiges"


def _stichwort_treffer(stoff, kats):
    """Welche Kategorie steckt in diesem Stueck Text? Sonst None."""
    stoff = " " + re.sub(r"[_\-./]+", " ", str(stoff or "").lower()) + " "
    if not stoff.strip():
        return None
    # das laengste passende Stichwort gewinnt ("werkzeugliste" vor "dvs ")
    beste = max(((len(w), name) for name, woerter in kats for w in woerter if w and w in stoff), default=None)
    return beste[1] if beste else None


def themen(kopf, hoechstens=6):
    """Themen = die Keywords der Aufnahme (deutsch bevorzugt), sonst Tags."""
    k = kopf or {}
    aus = []
    for w in (k.get("themen_vorgabe") or []) + (k.get("keywords") or []) + (k.get("tags") or []):
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
