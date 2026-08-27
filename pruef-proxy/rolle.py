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
    if re.search(r"st(ö|oe)rfall|st(ö|oe)rung|anlage|maschine|instandhalt|wartung|fehler|labor|pr(ü|ue)fstand", alles):
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


def zusammensetzen(kern, rolle):
    """Der Prompt, der in AnythingLLM landet: Kern + Rolle (wenn eingerichtet)."""
    kern = (kern or "").rstrip()
    if not ist_eingerichtet(rolle):
        return kern
    return kern + "\n\n## Rolle dieses Bereichs\n\n" + rolle.strip() + "\n"


def fuer_gespraech(rolle, hoechstens=1500):
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
    "agent": ("Vertreter", "Werkzeugmodus ohne Quellenangaben — für die Wissensdatenbank nicht empfohlen"),
}


def glaett_auftrag(vorlage_text):
    """Der Auftrag an das lokale Modell: die Vorlage als fluessigen
    Rollen-Abschnitt formulieren - ohne neue Fakten."""
    return ("Unten steht die Rolle eines Arbeitsbereichs einer Wissensdatenbank, aus drei Angaben "
            "zusammengesetzt. Formuliere daraus einen klaren Systemprompt-Abschnitt auf Deutsch: "
            "hoechstens 10 Zeilen, Du-Form an das Modell ('Du beantwortest hier ...'), keine "
            "Ueberschriften, keine Aufzaehlungszeichen, keine Anfuehrungszeichen um den Text. "
            "Nimm NUR auf, was in den Angaben steht - keine neuen Fachbegriffe, Normen, Zahlen "
            "oder Beispiele erfinden. Die Regeln unter 'So antwortest du hier' muessen sinngemaess "
            "alle enthalten sein. Antworte NUR mit dem Abschnitt.\n\n" + vorlage_text)


def geglaettet_brauchbar(text, fach, nutzer):
    """Hat das Modell etwas Brauchbares geliefert? Sonst bleibt die Vorlage."""
    t = (text or "").strip()
    if not (120 <= len(t) <= 1600) or t.count("\n") > 14:
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


MARKE_ABSCHNITT = "## Rolle dieses Bereichs"


def aus_prompt(prompt):
    """Den Rollen-Abschnitt aus einem in der Oberflaeche gespeicherten Prompt
    holen - '' wenn keiner drin ist. Die Oberflaeche ist die Wahrheit
    (Emrach 27.08.: 'Bequemlichkeit wird immer ueber die UI kommen')."""
    t = prompt or ""
    i = t.find(MARKE_ABSCHNITT)
    if i < 0:
        return ""
    return t[i + len(MARKE_ABSCHNITT):].strip() + "\n"


def kern_aus_prompt(prompt):
    """Der Teil vor dem Rollen-Abschnitt."""
    t = prompt or ""
    i = t.find(MARKE_ABSCHNITT)
    return (t if i < 0 else t[:i]).rstrip()
