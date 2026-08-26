"""Pruefungskatalog - exakte Fragen aus einer Datei stellen und Antworten
gegen den Katalog pruefen. Ohne Modell: Fragetext und Optionen kommen
WOERTLICH aus dem Bestandstext, die Loesung steht im Katalog oder gar nicht.

Gemessen 26.08. (Bereich AuW): "Stell mir eine Pruefungsfrage" - das Modell
erfand Fragen, Optionen und Zitate, weil die Excel keine PDF-Seiten hat und
kein Werkzeug den Katalog lesen konnte. Emrach: "er sollte doch exakte
Fragen aus der Datei mir nennen ... wenn ich eine Antwort gebe, pruefst du
anhand des Katalogs, ob das richtig ist."

Erkannte Formen:
  A) Tabelle mit Kopfzeile (Excel/CSV ueber die Aufnahme):
       | Frage | Antwort richtig | Antwort falsch | Antwort falsch | Bereich | LE |
     -> Loesung bekannt (Spalte 'richtig'), Thema aus 'Bereich'/'Thema'.
  B) Fragen mit Optionen a) b) c) d) in Zeilen oder Tabellenzellen (gescannte
     Kataloge, Docling-Tabellen) -> Loesung unbekannt, wird gesagt.
"""
import random
import re

_KOPF_FRAGE = re.compile(r"frage|question", re.I)
_KOPF_RICHTIG = re.compile(r"richtig|korrekt|l(ö|oe)sung|correct", re.I)
_KOPF_FALSCH = re.compile(r"falsch|distraktor|wrong", re.I)
_KOPF_THEMA = re.compile(r"bereich|thema|kategorie|kapitel|topic", re.I)
_KOPF_STELLE = re.compile(r"^\s*(?:le|lehreinheit|seite|s\.|folie|quelle)\s*$", re.I)
_OPTION = re.compile(r"^\s*(?:[^\sA-Za-z0-9(]{0,3}[a-z]{2,8}\s+)?\(?([a-hA-H])\s*[)\].:]\s*(.*)$")
_NUMMER = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(?:\1\s*[.)]\s*)?(.*)$")
_WUNSCH = re.compile(
    r"(?:pr(?:ü|ue)fungs|test|(?:ü|ue)bungs|quiz|katalog)-?frage|frag\s+mich\s+ab|abfragen|pr(?:ü|ue)f\s+mich|"
    r"stell(?:e|st)?\s+mir\s+(?:bitte\s+)?(?:eine|noch\s+eine|die\s+n(?:ä|ae)chste|weitere|ne)\s+(?:exakte\s+)?frage|"
    r"n(?:ä|ae)chste\s+frage|noch\s+(?:eine|ne)\s+frage|weitere\s+frage|frage\s+(?:nr\.?\s*)?\d+\s+(?:aus|vom|von|des)\s|"
    r"\bquiz\b", re.I)
_WEITER = re.compile(r"^\s*(?:ja|weiter|n(?:ä|ae)chste|noch\s+eine|die\s+n(?:ä|ae)chste|bitte|ok(?:ay)?|gerne|los)\s*[.!]?\s*$", re.I)
_ANTWORT = re.compile(r"^\s*(?:antwort\s*[:=]?\s*)?(?:die\s+|option\s+|buchstabe\s+)?\(?([a-hA-H])\s*[)\].:]?\s*$", re.I)
_NUMMER_WUNSCH = re.compile(r"\bfrage\s+(?:nr\.?\s*|nummer\s+)?(\d{1,3})\b", re.I)
_THEMA_WUNSCH = re.compile(r"\b(?:zum\s+thema|(?:ü|ue)ber|aus\s+dem\s+bereich|zu)\s+([A-Za-zÄÖÜäöüß][\w\- ]{2,40}?)(?:\s*[?.!]|$)", re.I)


_SEITENMARKE = re.compile(r"^\s*\[Seite (\d+)\]\s*$", re.M)


def seiten_aus_text(text):
    """Bestandstext -> Seitentexte ueber die [Seite n]-Marken der Aufnahme;
    ohne Marken ist der ganze Text eine Seite. Fuer Dokumente ohne PDF."""
    t = text or ""
    if not t.strip():
        return []
    teile = _SEITENMARKE.split(t)
    if len(teile) < 3:
        return [t]
    seiten = {}
    for i in range(1, len(teile) - 1, 2):
        n = int(teile[i])
        seiten[n] = seiten.get(n, "") + teile[i + 1]
    return [seiten.get(n, "") for n in range(1, max(seiten) + 1)]


def _zellen(zeile):
    return [z.strip() for z in zeile.strip().strip("|").split("|")]


def _sauber(t):
    return re.sub(r"\s+", " ", (t or "").replace("…", "...")).strip()


def _ist_muell(t):
    """OCR-Reste wie 'uh z eh rr' oder 'poale' - kein Optionstext."""
    t = _sauber(t)
    if len(t) < 3:
        return True
    woerter = t.split()
    return len(woerter) >= 3 and sum(1 for w in woerter if len(w) <= 2) >= len(woerter) * 0.6


def _tabelle_mit_kopf(zeilen):
    """Form A: Tabelle, deren Kopfzeile eine Frage-Spalte nennt."""
    fragen = []
    i = 0
    while i < len(zeilen):
        z = zeilen[i]
        if not z.lstrip().startswith("|"):
            i += 1
            continue
        kopf = _zellen(z)
        if not any(_KOPF_FRAGE.search(k) for k in kopf) or len(kopf) < 2:
            i += 1
            continue
        sp_frage = next(j for j, k in enumerate(kopf) if _KOPF_FRAGE.search(k))
        sp_richtig = [j for j, k in enumerate(kopf) if _KOPF_RICHTIG.search(k)]
        sp_falsch = [j for j, k in enumerate(kopf) if _KOPF_FALSCH.search(k)]
        sp_thema = [j for j, k in enumerate(kopf) if _KOPF_THEMA.search(k)]
        sp_stelle = [j for j, k in enumerate(kopf) if _KOPF_STELLE.search(k)]
        sp_option = sp_richtig + sp_falsch
        if not sp_option:
            sp_option = [j for j, k in enumerate(kopf) if j != sp_frage and j not in sp_thema and j not in sp_stelle
                         and re.search(r"antwort|option|auswahl|[a-d]\)", k, re.I)]
        i += 1
        while i < len(zeilen) and zeilen[i].lstrip().startswith("|"):
            zellen = _zellen(zeilen[i])
            i += 1
            if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in zellen):
                continue
            if len(zellen) <= sp_frage or not _sauber(zellen[sp_frage]):
                continue
            def _z(j):
                return _sauber(zellen[j]) if j < len(zellen) else ""
            richtig = [_z(j) for j in sp_richtig if _z(j)]
            falsch = [_z(j) for j in sp_falsch if _z(j)]
            optionen = richtig + falsch if (sp_richtig or sp_falsch) else [_z(j) for j in sp_option if _z(j)]
            if len(optionen) < 2:
                continue
            fragen.append({
                "frage": _sauber(zellen[sp_frage]), "optionen": optionen,
                "richtig": richtig[0] if richtig else None,
                "thema": _z(sp_thema[0]) if sp_thema else "",
                "stelle": _z(sp_stelle[0]) if sp_stelle else "",
            })
    return fragen


def _optionen_zeilen(zeilen):
    """Form B: Fragen mit a) b) c) - in Zeilen oder Tabellenzellen."""
    fragen = []
    aktuell = None

    def _abschliessen():
        if aktuell and len(aktuell["optionen"]) >= 2 and aktuell["frage"]:
            aktuell.pop("_marken", None)
            fragen.append(aktuell)

    for roh in zeilen:
        z = roh.strip()
        if not z or re.fullmatch(r"\|?[\s|:\-]+\|?", z):
            continue
        teile = [t for t in (_zellen(z) if z.startswith("|") else [z]) if t]
        if not teile:
            continue
        # Option: Marke in der ersten Zelle oder am Zeilenanfang
        m = _OPTION.match(teile[0])
        if m and (m.group(2).strip() or len(teile) > 1):
            text = m.group(2).strip() or " ".join(teile[1:])
            buchstabe = m.group(1).lower()
            if aktuell is not None and buchstabe in aktuell["_marken"]:
                # a) nach d): eine neue Frage, deren Text verloren ging (Scan)
                _abschliessen()
                aktuell = None
            if aktuell is not None and not _ist_muell(text):
                aktuell["optionen"].append(_sauber(text))
                aktuell["_marken"].add(buchstabe)
            continue
        if len(teile) > 1 and _OPTION.match(teile[-1] if False else teile[0]) is None:
            m2 = _OPTION.match(teile[0]) if len(teile[0]) <= 3 else None
            if m2:
                continue
        # Frage: Nummer + Text, oder Zelle mit Fragezeichen
        text = " ".join(t for t in teile if not re.fullmatch(r"\d{1,3}\s*[.)](?:\s*\d{1,3}\s*[.)])?", t))
        mn = _NUMMER.match(teile[0])
        if mn or "?" in text:
            _abschliessen()
            aktuell = {"frage": _sauber(mn.group(2) if mn and mn.group(2) else text), "optionen": [],
                       "richtig": None, "thema": "", "stelle": "", "_marken": set()}
            if mn and mn.group(2) == "" and len(teile) > 1:
                aktuell["frage"] = _sauber(" ".join(teile[1:]))
            continue
        # Fortsetzung des Fragetexts (vor der ersten Option)
        if aktuell is not None and not aktuell["optionen"] and not _ist_muell(text) and len(text) > 8:
            aktuell["frage"] = _sauber(aktuell["frage"] + " " + text) if aktuell["frage"] else _sauber(text)
    _abschliessen()
    return fragen


def fragen_aus_text(text):
    """[{'nr','frage','optionen','richtig','thema','stelle','seite'}] - in
    Katalogreihenfolge. Leer, wenn der Text kein Katalog ist."""
    if not text:
        return []
    zeilen = text.splitlines()
    fragen = _tabelle_mit_kopf(zeilen)
    if len(fragen) < 2:
        fragen = _optionen_zeilen(zeilen)
    # Seitenmarken [Seite n] zuordnen
    seite_je_zeile, seite = [], 0
    for z in zeilen:
        m = re.match(r"\s*\[Seite (\d+)\]", z)
        if m:
            seite = int(m.group(1))
        seite_je_zeile.append(seite)
    for n, f in enumerate(fragen, 1):
        f["nr"] = n
        f["seite"] = 0
        kurz = f["frage"][:40]
        for i, z in enumerate(zeilen):
            if kurz and kurz in z:
                f["seite"] = seite_je_zeile[i]
                break
    return fragen


def ist_katalog(text, mindestens=3):
    return len(fragen_aus_text(text)) >= mindestens


def ist_wunsch(eingabe):
    return bool(_WUNSCH.search(eingabe or ""))


def ist_weiter(eingabe):
    return bool(_WEITER.match(eingabe or ""))


def gewuenschte_nummer(eingabe):
    m = _NUMMER_WUNSCH.search(eingabe or "")
    return int(m.group(1)) if m else None


def gewuenschtes_thema(eingabe):
    m = _THEMA_WUNSCH.search(eingabe or "")
    if not m:
        return ""
    t = re.sub(r"\s+(?:bitte|mal|doch|noch|jetzt)$", "", m.group(1).strip(), flags=re.I)
    return "" if re.fullmatch(r"(?:dem|der|den|das|die|katalog|datei|excel|bestand)\b.*", t, re.I) else t


def _reihenfolge(frage):
    """Deterministische Mischung der Optionen je Frage - die richtige
    Antwort steht sonst immer an erster Stelle (Form A)."""
    idx = list(range(len(frage["optionen"])))
    random.Random(len(frage["frage"]) * 7919 + frage.get("nr", 0) * 31).shuffle(idx)
    return idx


def stellen(frage, gesamt=None, kennung=""):
    """(Text fuer den Chat, Zustand zum Merken)."""
    reihe = _reihenfolge(frage)
    buchstaben = "abcdefgh"
    kopf = "**Frage %d%s**" % (frage.get("nr", 0), (" von %d" % gesamt) if gesamt else "")
    meta = [x for x in (("Thema: " + frage["thema"]) if frage.get("thema") else "",
                        ("LE " + frage["stelle"]) if frage.get("stelle") and frage["stelle"].strip("! ").isdigit() else
                        (frage["stelle"] if frage.get("stelle") else ""),
                        kennung) if x]
    if meta:
        kopf += " *(%s)*" % " · ".join(meta)
    zeilen = [kopf, "", frage["frage"], ""]
    for pos, i in enumerate(reihe):
        zeilen.append("%s) %s" % (buchstaben[pos], frage["optionen"][i]))
    zeilen.append("")
    zeilen.append("*Antworte mit %s.*" % " / ".join(buchstaben[:len(reihe)]))
    if frage.get("richtig") is None:
        zeilen.append("*Hinweis: Dieser Katalog enthält keine Lösungen — ich kann deine Antwort dann nur gegen die Norm-Dokumente prüfen.*")
    zustand = {"nr": frage.get("nr", 0), "reihe": reihe, "kennung": kennung}
    return "\n".join(zeilen), zustand


def gewaehlt(eingabe, frage, zustand):
    """Welche Option der Mensch meint: (Buchstabe, Originalindex) oder None."""
    if not eingabe:
        return None
    reihe = zustand.get("reihe") or list(range(len(frage["optionen"])))
    buchstaben = "abcdefgh"
    m = _ANTWORT.match(eingabe)
    if m:
        pos = buchstaben.find(m.group(1).lower())
        if 0 <= pos < len(reihe):
            return buchstaben[pos], reihe[pos]
        return None
    # Optionstext (ganz oder in Teilen): Woerter UND Zahlen zaehlen - "90 mm"
    # gegen "250 mm" unterscheidet sich nur in der Zahl.
    _tok = lambda t: set(re.findall(r"[a-zäöüß]{3,}|\d+(?:[.,]\d+)?", t.lower()))
    e = _tok(eingabe)
    if len(e) < 2:
        return None
    werte = []
    for pos, i in enumerate(reihe):
        o = _tok(frage["optionen"][i])
        if o:
            werte.append((len(e & o) / float(len(e | o)), pos, i))
    werte.sort(reverse=True)
    if not werte or werte[0][0] < 0.5 or (len(werte) > 1 and werte[0][0] - werte[1][0] < 0.1):
        return None
    return buchstaben[werte[0][1]], werte[0][2]


def ist_antwort(eingabe, frage, zustand):
    return gewaehlt(eingabe, frage, zustand) is not None


def pruefen(eingabe, frage, zustand, kennung=""):
    """Urteil als Chat-Text - oder None, wenn die Eingabe keine Antwort ist."""
    w = gewaehlt(eingabe, frage, zustand)
    if not w:
        return None
    buchstabe, i = w
    reihe = zustand.get("reihe") or list(range(len(frage["optionen"])))
    buchstaben = "abcdefgh"
    quelle = ", ".join(x for x in (kennung or zustand.get("kennung") or "", "Frage %d" % frage.get("nr", 0),
                                   ("Thema " + frage["thema"]) if frage.get("thema") else "",
                                   ("LE " + frage["stelle"]) if frage.get("stelle") else "") if x)
    if frage.get("richtig") is None:
        return ("Du hast **%s)** gewählt: „%s“.\n\nDer Katalog enthält zu dieser Frage keine Lösung — ich kann sie nicht "
                "gegen den Katalog prüfen. Sag „prüfe das gegen die Norm“, dann suche ich die Stelle in den Dokumenten.\n\n"
                "*(%s)* — Nächste Frage: „weiter“." % (buchstabe, frage["optionen"][i], quelle))
    richtig_i = frage["optionen"].index(frage["richtig"]) if frage["richtig"] in frage["optionen"] else 0
    richtig_b = buchstaben[reihe.index(richtig_i)] if richtig_i in reihe else "?"
    if i == richtig_i:
        return "✅ **Richtig.** %s) „%s“\n\n*(%s)* — Nächste Frage: „weiter“." % (buchstabe, frage["optionen"][i], quelle)
    return ("❌ **Nicht richtig.** Du hast %s) „%s“ gewählt.\n\nLaut Katalog ist **%s)** richtig: „%s“\n\n"
            "*(%s)* — Nächste Frage: „weiter“, Begründung: „warum?“" % (buchstabe, frage["optionen"][i], richtig_b, frage["richtig"], quelle))


def waehlen(fragen, gestellt=None, nummer=None, thema=""):
    """Die naechste Frage: gewuenschte Nummer, sonst die erste noch nicht
    gestellte (bei Thema: nur passende); alle durch -> von vorn."""
    if not fragen:
        return None
    if nummer:
        for f in fragen:
            if f["nr"] == nummer:
                return f
        return None
    gestellt = set(gestellt or [])
    kandidaten = fragen
    if thema:
        t = thema.lower()
        kandidaten = [f for f in fragen if t in (f.get("thema") or "").lower() or t in f["frage"].lower()] or fragen
    offen = [f for f in kandidaten if f["nr"] not in gestellt]
    return (offen or kandidaten)[0]


def zeile_fuer_modell(frage, kennung=""):
    """Der Katalogeintrag als Werkzeugtext - fuer 'warum?' im Gespraechsmodus."""
    aus = ["Pruefungskatalog %s, Frage %d%s:" % (kennung, frage.get("nr", 0), (" (Thema %s)" % frage["thema"]) if frage.get("thema") else ""),
           "FRAGE: " + frage["frage"]]
    for o in frage["optionen"]:
        aus.append(("RICHTIG: " if o == frage.get("richtig") else "FALSCH: " if frage.get("richtig") else "OPTION: ") + o)
    if frage.get("richtig") is None:
        aus.append("(Der Katalog nennt keine Loesung.)")
    return "\n".join(aus)
