"""Rolle je Bereich - der bereichseigene Teil des Systemprompts.

Kern (systemprompt.txt: Belegpflicht, Zitierform, Verbote) + Rolle
(dokumente/<bereich>/prompt.md: wofuer der Bereich da ist, wer fragt, was
besonders ist). Entsteht im Chat aus drei Fragen ("Rolle einrichten") oder
beim Anlegen per Skript; ein Partner aendert sie mit jedem Editor in der
Datei, der Proxy spielt Aenderungen alle fuenf Minuten ein - in AnythingLLM
UND in den Gespraechsmodus. Auf dem Testserver lagen die Rollen nur in der
Datenbank (4 500-6 200 Zeichen je Bereich, von Hand) - hier sind sie Datei.

Reine Textfunktionen, ohne Modell - pruefbar in dialogtest.py.
"""
import re

DATEI = "prompt.md"
MARKE_ABSCHNITT = "## Rolle dieses Bereichs"
PLATZHALTER_MARKE = "<!-- noch nicht eingerichtet -->"

FRAGEN = [
    ("fach", "**Rolle einrichten (1/3):** Um welches Fachgebiet geht es in diesem Bereich? "
             "(z. B. „Kunststoffschweißen und -kleben nach DVS“, „Spritzgießen“, „Prüflabor Werkstoffe“)"),
    ("nutzer", "**(2/3):** Wer stellt hier Fragen? "
               "(z. B. „Prüflinge und Ausbilder“, „Wissenschaftler“, „Instandhalter an der Anlage“, „Studierende“)"),
    ("besonderes", "**(3/3):** Was ist besonders — worauf soll die Anlage achten? "
                   "(z. B. „Normstellen und Grenzwerte nennen“, „Sicherheitshinweise immer dazu“, "
                   "„Störfälle: Ursache und Maßnahme“, „wissenschaftlich mit Methodik“ — oder „nichts“)"),
]

_WUNSCH = re.compile(r"\brolle\s+(?:einrichten|festlegen|anpassen|ändern|aendern|setzen|neu)|"
                     r"bereich\s+einrichten|(?:system)?prompt\s+(?:einrichten|anpassen|ändern|aendern)|"
                     r"\brolle\s+(?:des|für|fuer)\s+(?:den\s+)?bereich", re.I)
_ABBRUCH = re.compile(r"^\s*(?:abbrechen|abbruch|stop|stopp|lass(?:en)?\s+wir|nein\s+danke|vergiss\s+es)\s*[.!]?\s*$", re.I)


def ist_wunsch(eingabe):
    return bool(_WUNSCH.search(eingabe or ""))


def ist_abbruch(eingabe):
    return bool(_ABBRUCH.match(eingabe or ""))


def platzhalter(slug):
    return ("%s\n# Rolle des Bereichs „%s“\n\n"
            "Noch nicht eingerichtet. Zwei Wege:\n"
            "- im Chat dieses Bereichs (als Admin) „Rolle einrichten“ sagen — drei Fragen, fertig;\n"
            "- oder diese Datei mit einem Editor füllen (Fachgebiet, wer fragt, worauf achten).\n\n"
            "Die Anlage spielt Änderungen an dieser Datei innerhalb von fünf Minuten ein — "
            "in die Oberfläche und in den Gesprächsmodus. Solange sie so aussieht, gilt nur der Kern-Prompt.\n"
            % (PLATZHALTER_MARKE, slug))


def ist_eingerichtet(text):
    t = (text or "").strip()
    return bool(t) and PLATZHALTER_MARKE not in t and len(re.sub(r"^#.*$", "", t, flags=re.M).strip()) >= 20


def _regeln(fach, nutzer, besonderes):
    """Aus den drei Antworten die Antwortregeln ableiten - ohne Modell."""
    alles = " ".join((fach, nutzer, besonderes)).lower()
    r = []
    if re.search(r"pr(ü|ue)f(ling|ung)|ausbild|lehrgang|schul|kurs|azubi|lehrling|studier", alles):
        r.append("Antworte prüfungsnah und verständlich: erst die Kernaussage, dann die Normstelle mit Seite; "
                 "Zahlen immer mit Einheit und Bedingung. Prüfungsfragen stellst du nur aus einem hinterlegten Katalog.")
    if re.search(r"norm|richtlinie|dvs|din|iso|vorschrift|regelwerk", alles):
        r.append("Nenne bei jeder Regel die Normstelle (Dokument, Abschnitt, Seite) und ob sie eine Muss- oder Soll-Vorgabe ist.")
    if re.search(r"sicher|gefahr|schutz|arbeitsschutz|brand|gift|l(ö|oe)semittel", alles):
        r.append("Sicherheits- und Arbeitsschutzhinweise gehören in jede Antwort, in der sie im Dokument stehen — nie weglassen.")
    if re.search(r"st(ö|oe)rfall|st(ö|oe)rung|anlage|maschine|instandhalt|wartung|fehler|labor|pr(ü|ue)fstand|rep[ae]ratur", alles):
        r.append("Bei Störungen und Fehlerbildern: Ursache · Maßnahme · Quelle · Gültigkeit als Tabelle; ohne belegte "
                 "Maßnahme keine Vermutung, sondern Ansprechpartner nennen.")
    if re.search(r"wissenschaft|forsch|disser|methodik|studie|publikation|paper", alles):
        r.append("Antworte wissenschaftlich: Methode, Randbedingungen und Messunsicherheit mitnennen; Ergebnisse "
                 "verschiedener Arbeiten nebeneinanderstellen statt zu vermischen.")
    if re.search(r"englisch|english|international", alles):
        r.append("Antworte in der Sprache der Frage; Fachbegriffe beim ersten Vorkommen zweisprachig.")
    if not r:
        r.append("Antworte knapp und belegt; wo das Dokument schweigt, sag es.")
    return r


def vorlage(fach, nutzer, besonderes, slug=""):
    fach, nutzer, besonderes = (re.sub(r"\s+", " ", (x or "")).strip(" .") for x in (fach, nutzer, besonderes))
    zeilen = ["# Rolle des Bereichs" + (" „%s“" % slug if slug else ""), "",
              "**Fachgebiet:** %s" % (fach or "—"),
              "**Wer fragt hier:** %s" % (nutzer or "—"),
              "**Besonderheiten:** %s" % (besonderes or "—"), "",
              "## So antwortest du hier"]
    for r in _regeln(fach, nutzer, besonderes):
        zeilen.append("- " + r)
    zeilen.append("")
    zeilen.append("*(Diese Datei darf frei bearbeitet werden — Änderungen wirken innerhalb von fünf Minuten.)*")
    return "\n".join(zeilen) + "\n"


def fuer_prompt(rolle):
    """Die Rolle ohne Datei-Kopf und ohne Datei-Hinweis - das liest das Modell."""
    t = re.sub(r"^# Rolle des Bereichs.*$", "", rolle or "", flags=re.M)
    t = re.sub(r"\*\(Diese Datei darf frei bearbeitet werden.*?\)\*", "", t, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def zusammensetzen(kern, rolle):
    """Der Prompt, der in AnythingLLM landet: Kern + Rolle (wenn eingerichtet)."""
    kern = (kern or "").rstrip()
    if not ist_eingerichtet(rolle):
        return kern
    return kern + "\n\n" + MARKE_ABSCHNITT + "\n\n" + fuer_prompt(rolle) + "\n"


def fuer_gespraech(rolle, hoechstens=2400):
    """Kurzfassung fuer den Gespraechsmodus (Stufe 2) - ohne Markdown-Kopf."""
    if not ist_eingerichtet(rolle):
        return ""
    t = re.sub(r"^#.*$", "", rolle, flags=re.M)
    t = re.sub(r"\*\(Diese Datei.*?\)\*", "", t, flags=re.S)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:hoechstens]


def schritt(zustand, eingabe):
    """Der Einrichtungsdialog. zustand = None (Start) oder {'schritt': n, 'antworten': {...}}.
    Rueckgabe (neuer_zustand | None, text, fertig_antworten | None)."""
    if zustand is None:
        return {"schritt": 0, "antworten": {}}, FRAGEN[0][1] + "\n\n*(„abbrechen“ beendet die Einrichtung.)*", None
    if ist_abbruch(eingabe):
        return None, "Einrichtung abgebrochen — es bleibt beim bisherigen Prompt.", None
    n = int(zustand.get("schritt", 0))
    antworten = dict(zustand.get("antworten") or {})
    antwort = re.sub(r"\s+", " ", (eingabe or "")).strip()
    if len(antwort) < 2:
        return zustand, "Bitte eine kurze Antwort — " + FRAGEN[n][1], None
    antworten[FRAGEN[n][0]] = antwort
    if n + 1 < len(FRAGEN):
        return {"schritt": n + 1, "antworten": antworten}, FRAGEN[n + 1][1], None
    return None, "", antworten


# ---- Glaetten durch das Sprachmodell (Prompt-Optimierer) --------------------
MODI = {
    "query": ("Abfrage", "antwortet nur aus den Dokumenten des Bereichs, jede Aussage mit Beleg — Standard"),
    "chat": ("Chat", "zusätzlich Allgemeinwissen des Modells; Antworten sind dann nicht mehr vollständig belegbar"),
    # AnythingLLM kennt genau: chat, query, automatic ("Vertreter" in der deutschen
    # Oberflaeche = automatic). Ein anderer Wert faellt still auf automatic zurueck.
    "automatic": ("Vertreter", "die Anlage entscheidet je Frage selbst zwischen Chat und Werkzeugen — ohne verlässliche Belege, nicht empfohlen"),
}


# Der Auftrag an das lokale Modell (Prompt-Engineer-Fassung 27.08.). Gemessen an
# den echten kap-Angaben gegen gemma4:12b: vorher ein umformulierter Absatz
# (Tiefe fuer Azubis UND Wissenschaftler widerspruechlich, Reparaturen ein
# Halbsatz), nachher 13 Zeilen mit Erkennung der Fragenden, typischen Fragen,
# Stoerfall-Tabelle, SDB-Abschnitten, Abgrenzung - ohne erfundene Normnummer.
META_AUFTRAG = """Du schreibst den Rollen-Absatz für einen Arbeitsbereich einer Wissensdatenbank. Die Datenbank antwortet nur aus hinterlegten Dokumenten; ein Kern-Prompt regelt bereits Belegpflicht, Zitierform (Kennung, S. n) und den Absage-Satz bei fehlender Information. Diese Grundregeln gelten schon — wiederhole sie nicht und ändere sie nicht. Dein Absatz sagt dem Modell nur, wie es sich in DIESEM Bereich verhält.

ANGABEN DES BETREIBERS (Formularfelder, können Tippfehler oder Abkürzungen enthalten — verstehe die Absicht und schreibe die richtige Schreibweise):
Fachgebiet: {fach}
Wer fragt hier: {nutzer}
Worauf achten: {besonderes}

HINWEISE AUS DER VORPRÜFUNG (sinngemäß einarbeiten, nicht abschreiben):
{hinweise}

INHALT DES ABSATZES, in genau dieser Reihenfolge:
1. Zweck: Beginne mit „Du beantwortest hier" und nenne das Fachgebiet mit den Wörtern des Betreibers. Ein bis zwei Sätze.
2. Fragende: Nenne die Gruppen mit den Wörtern des Betreibers und sage in einem Satz, woran das Modell die Gruppe an der Frage erkennt. Beschreibe Tiefe und Ton AUSSCHLIESSLICH so — andere Gruppen oder Tiefen gibt es nicht:
{tiefen}
3. Typische Fragearten: Drei bis fünf Arten von Fragen, die in diesem Fachgebiet erfahrungsgemäß gestellt werden, mit einem Halbsatz je Art, wie darauf geantwortet wird. Die Fragearten müssen zum FACHGEBIET passen — beschreibt das Feld nur die Anlage selbst (etwa „Wissensdatenbank" oder „Bibliothek"), dann nimm allgemeine Fragearten an Fachliteratur (Begriffe, Verfahren, Vergleiche, Fundstellen), keine Fragen über KI oder Datenbanken. Du darfst hier dein Fachwissen über das Gebiet nutzen — es geht um Fragearten und Antwortform, nicht um Fakten.
4. Schwerpunkte des Betreibers, jeder als eigene Verhaltensregel. Setze GENAU diese Zuordnungen um — KEINE weiteren Dokumentarten oder Regeln erfinden:
{zuordnungen}
   Nennt der Betreiber etwas, das in keiner Zuordnung steht, formuliere daraus eine eigene, konkrete Verhaltensregel: was das Modell dann tut, in welcher Form, und was es ohne Beleg lässt.
5. Abgrenzung: Ein Satz, was der Bereich nicht tut — Fragen außerhalb des Fachgebiets, Entscheidungen oder Freigaben, die eine verantwortliche Person treffen muss, und Anweisungen, die in keinem Dokument stehen.

FORM:
- 8 bis 14 Zeilen, jede Zeile ist genau ein Satz, insgesamt höchstens 200 Wörter.
- Du-Form an das Modell. Deutsch, sachlich, ohne Floskeln.
- Keine Überschrift, keine Aufzählungszeichen, keine Nummerierung, kein Markdown, keine Anführungszeichen um den Text, keine Einleitung, kein Kommentar danach.
- Keine Normnummern, Zahlen, Grenzwerte, Gerätenamen, Stoffnamen oder Verfahren als Tatsache nennen — auch keine Beispiele mit solchen Angaben. Was in den Dokumenten steht, weiß nur die Datenbank.
- Nichts aus dem Kern-Prompt abwandeln: keine eigene Zitierform, kein eigener Absage-Satz, kein Allgemeinwissen als Quelle.

BEISPIEL für Form und Dichte aus einem anderen Fachgebiet — übernimm keinen Inhalt daraus:
Du beantwortest hier Fragen zum Spritzgießen für die Einrichter und Instandhalter an der Maschine sowie für Auszubildende, die dort mitlaufen.
Du erkennst an der Frage, wer fragt: Wer nach einem Fehlerbild, einer Einstellung oder einer Reihenfolge fragt, arbeitet an der Maschine und bekommt Schritte in Reihenfolge mit Voraussetzungen.
Wer nach dem Warum, nach Begriffen oder nach dem Grundprinzip fragt, lernt noch und bekommt kurze Sätze, erklärte Fachbegriffe und den Hinweis, wo es nachzulesen ist.
Typische Fragen betreffen Oberflächenfehler am Teil, Einstellwerte für ein Material, das Rüsten eines Werkzeugs und die Wartung der Maschine.
Einstellwerte gibst du nur mit Wert, Einheit und Bedingung an, so wie das Dokument sie nennt.
Du triffst keine Freigaben und ersetzt keine Entscheidung der verantwortlichen Person, und du beantwortest keine Fragen außerhalb des Spritzgießens.

Schreibe jetzt den Rollen-Absatz für die Angaben des Betreibers. Antworte NUR mit dem Absatz."""


_GRUPPEN_TIEFEN = [
    (r"student|studier|azubi|auszubild|lernend|anwender|laie|einsteiger|sch(ü|ue)ler|f(ö|oe)rdermitglied",
     "Lernende und fachfremde Fragende bekommen kurze Sätze, erklärte Fachbegriffe und den Weg zum Nachlesen."),
    (r"wissenschaft|ingenieur|fachperson|fachleute|fachlich|experte|forscher|doktorand",
     "Fachleute und Wissenschaftler bekommen knappe Antworten mit Methode, Randbedingungen und Messunsicherheit."),
    (r"techniker|instandhalt|einrichter|monteur|werker|meister|handwerk",
     "Techniker und Instandhalter bekommen Schritte in Reihenfolge mit Voraussetzungen."),
]


def _tiefen_fuer(nutzer):
    """Nur die Tiefen-Beschreibungen der GENANNTEN Gruppen - sonst schreibt das
    Modell den ganzen Katalog ab ('Techniker und Instandhalter' in der
    Bibliothek, Emrach 02.09.)."""
    n = (nutzer or "").lower()
    treffer = [t for rx, t in _GRUPPEN_TIEFEN if re.search(rx, n)]
    if not treffer:
        return "   - Alle Fragenden bekommen knappe, belegte Antworten in verständlicher Sprache."
    return "\n".join("   - " + t for t in treffer)


ZUORDNUNGEN = [
    (r"norm|richtlinie|dvs|din|iso|vorschrift|regelwerk",
     "Normen, Normstellen, Richtlinien, Regelwerke: bei jeder Regel Dokument, Abschnitt und Seite nennen und sagen, ob sie eine Muss- oder Soll-Vorgabe ist."),
    (r"sicherheitsdatenbl|datenbl(a|ä)tt|chemikal|gefahrstoff",
     "Sicherheitsdatenblätter: die einschlägigen Abschnitte nennen, Gefahrenhinweise und Schutzmaßnahmen immer nennen, wenn sie im Dokument stehen, und bei Unklarheit nach Stoff und Fassung fragen."),
    (r"sicher|gefahr|schutz|arbeitsschutz|brand|gift|l(ö|oe)semittel",
     "Sicherheit, Arbeitsschutz, Gefahr: Sicherheits- und Schutzhinweise gehören in jede Antwort, in der sie im Dokument stehen."),
    (r"st(ö|oe)rfall|st(ö|oe)rung|reparatur|instandhalt|wartung|fehlerbild|anlage|maschine|techniker",
     "Reparaturen, Störungen, Fehlerbilder, Instandhaltung, Wartung: als Tabelle mit den Spalten Ursache, Maßnahme, Quelle und Gültigkeit antworten; ohne belegte Maßnahme keine Vermutung, sondern auf Herstellerunterlage oder zuständige Person verweisen."),
    (r"pr(ü|ue)f(ling|ung)|ausbild|lehrgang|schul|kurs|azubi|lehrling",
     "Prüfung, Ausbildung, Lehrgang: zuerst die Kernaussage, dann der Beleg; Zahlen mit Wert, Einheit und Bedingung; Prüfungsfragen nur aus einem hinterlegten Katalog."),
    (r"wissenschaft|forsch|disser|methodik|studie|publikation|paper|ingenieur",
     "Wissenschaftliche Fragen: Methode, Randbedingungen und Messunsicherheit mitnennen; Ergebnisse verschiedener Arbeiten nebeneinanderstellen, nicht vermischen."),
]


def _zuordnungen_fuer(fach, nutzer, besonderes):
    """Nur die Bausteine, die der Betreiber wirklich anspricht - der Rollen-
    Absatz eines Bibliotheksbereichs bekommt keine Stoerungs-Tabellen und
    Sicherheitsdatenblatt-Regeln (Emrach 02.09.: 'ich dachte modular')."""
    alles = " ".join((fach or "", nutzer or "", besonderes or "")).lower()
    treffer = [t for rx, t in ZUORDNUNGEN if re.search(rx, alles)]
    if not treffer:
        return "   - (keine besonderen Dokumentarten genannt: keine Zusatzregeln, nur knapp und belegt antworten)"
    return "\n".join("   - " + t for t in treffer)


def glaett_auftrag(fach, nutzer="", besonderes=""):
    """Der Auftrag an das lokale Modell: aus den drei Angaben den
    Rollen-Absatz schreiben. Die Vorlagen-Regeln gehen als Hinweise mit."""
    if nutzer == "" and besonderes == "" and "\n" in (fach or ""):
        # alte Aufrufform (fertige Vorlage): Angaben herauslesen
        import re as _re
        t = fach
        fach = (_re.search(r"\*\*Fachgebiet:\*\* (.*)", t) or [None, ""])[1]
        nutzer = (_re.search(r"\*\*Wer fragt hier:\*\* (.*)", t) or [None, ""])[1]
        besonderes = (_re.search(r"\*\*Besonderheiten:\*\* (.*)", t) or [None, ""])[1]
    hinweise = "\n".join("- " + r for r in _regeln(fach or "", nutzer or "", besonderes or ""))
    return META_AUFTRAG.format(fach=fach or "—", nutzer=nutzer or "—", besonderes=besonderes or "—", hinweise=hinweise,
                               zuordnungen=_zuordnungen_fuer(fach, nutzer, besonderes),
                               tiefen=_tiefen_fuer(nutzer))


def geglaettet_brauchbar(text, fach, nutzer, besonderes=""):
    _alles = " ".join((fach or "", nutzer or "", besonderes or "")).lower()
    for _rx, _hinweis in ((r"techniker|instandhalter", r"techniker|instandhalt|einrichter|monteur|werker|meister|handwerk"),
                          (r"auszubildende|azubi", r"azubi|auszubild|lehrling|lernend"),
                          (r"sicherheitsdatenbl", r"sicherheitsdatenbl|datenbl|chemikal|gefahrstoff|sicher|gefahr"),
                          (r"ursache, ?ma(ß|ss)nahme, ?quelle", r"st(ö|oe)r|reparatur|instandhalt|wartung|fehlerbild|anlage|maschine|techniker"),
                          (r"pr(ü|ue)fungsfragen|lehrgang", r"pr(ü|ue)f|ausbild|lehrgang|schul|kurs|azubi|lehrling|katalog")):
        if re.search(_rx, (text or "").lower()) and not re.search(_hinweis, _alles):
            return False        # Baustein im Text, den der Betreiber nie genannt hat -> Vorlage statt Glaettung
    """Hat das Modell etwas Brauchbares geliefert? Sonst bleibt die Vorlage."""
    t = (text or "").strip()
    if not (120 <= len(t) <= 2400) or t.count("\n") > 16:
        return False
    if re.search(r"^\s*(#|\*|-|\d+\.)", t, re.M):
        return False
    unten = t.lower()
    kern = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", (fach or "") + " " + (nutzer or ""))][:6]
    return sum(1 for w in kern if w.lower() in unten) >= max(1, len(kern) // 2)


def vorlage_mit_glaettung(fach, nutzer, besonderes, geglaettet, slug=""):
    """Vorlage, deren Regelteil durch die Modellfassung ersetzt ist."""
    v = vorlage(fach, nutzer, besonderes, slug=slug)
    kopf = v.split("## So antwortest du hier")[0].rstrip()
    return kopf + "\n\n## So antwortest du hier\n\n" + geglaettet.strip() + \
        "\n\n*(Diese Datei darf frei bearbeitet werden — Änderungen wirken innerhalb von fünf Minuten.)*\n"



def aus_prompt(prompt):
    """Den Rollen-Abschnitt aus einem in der Oberflaeche gespeicherten Prompt
    holen - '' wenn keiner drin ist. Die Oberflaeche ist die Wahrheit
    (Emrach 27.08.: 'Bequemlichkeit wird immer ueber die UI kommen')."""
    t = prompt or ""
    i = t.find(MARKE_ABSCHNITT)
    if i < 0:
        return ""
    kern_text = t[i + len(MARKE_ABSCHNITT):].strip()
    if not kern_text:
        return ""
    if not kern_text.startswith("# Rolle des Bereichs"):
        kern_text = "# Rolle des Bereichs\n\n" + kern_text
    return kern_text + "\n\n*(Diese Datei darf frei bearbeitet werden — Änderungen wirken innerhalb von fünf Minuten.)*\n"


def kern_aus_prompt(prompt):
    """Der Teil vor dem Rollen-Abschnitt."""
    t = prompt or ""
    i = t.find(MARKE_ABSCHNITT)
    return (t if i < 0 else t[:i]).rstrip()
