"""Stufe 2 der Gespraechsfuehrung: Das MODELL fuehrt das Gespraech.

Befund 26.08. (ARCHITEKTUR-GESPRAECH.md): Selbst mit richtiger Absichts-
erkennung blieb es ein Automat - je Zug EIN starres Werkzeug, Rueckmeldungen
wurden zur Wiederholung, zwei Aufgaben in einem Satz verloren eine, und auf
"Warum stand da unlesbar?" oder "Kann ich mit dir diskutieren?" gab es
keinen Weg, auf dem das Modell einfach antwortet.

Hier sieht das Modell den ganzen Faden (Fragen UND bisherige Antworten),
den Zustand (Faden-Dokument, Dokumentliste) und hat Werkzeuge: Seiten
lesen, Abbildungen auflisten und zeigen, zusammenfassen, zaehlen, Bestand,
Dokument finden, Abkuerzung, Export. Es ruft sie selbst auf - auch mehrere
hintereinander - und schreibt die Antwort selbst. Der Proxy bleibt Pruefer:
Zitate werden gegen das Original geprueft, Bilder eingebettet, Seiten
verlinkt; ausserhalb der Werkzeuge gibt es keine Quelle.

Gemessen 26.08. (gemma4:12b ueber Ollama): "fasse zusammen und zeig die
wichtigste Grafik" -> zusammenfassen -> abbildungen_auflisten ->
abbildung_zeigen(6.12) in 7,8 s, ohne Anleitung zur Reihenfolge.

Alles hier ist ohne Netz testbar: `fuehren()` bekommt `rufen` (Modell) und
`werkzeug` (Ausfuehrung) als Funktionen.
"""
import json
import os
import re
import time
import urllib.request

AN = (os.environ.get("KI4KI_GESPRAECH") or "0") == "1"
MODELL = os.environ.get("KI4KI_GESPRAECH_MODELL") or "gemma4:12b"
URL = (os.environ.get("KI4KI_GESPRAECH_URL") or os.environ.get("KI4KI_NETZ_URL")
       or "http://nothink-proxy:11435/api/chat")
TIMEOUT = float(os.environ.get("KI4KI_GESPRAECH_TIMEOUT") or "240")
MAX_RUNDEN = int(os.environ.get("KI4KI_GESPRAECH_RUNDEN") or "5")
DENKEN = (os.environ.get("KI4KI_GESPRAECH_DENKEN") or "0") == "1"

WERKZEUGE = [
    {"type": "function", "function": {
        "name": "seiten_lesen",
        "description": "Liest die zur Frage passenden Seiten EINES Dokuments (woertliche Suche nach den Begriffen der Frage) und gibt ihren Text mit Seitenzahlen zurueck. Fuer konkrete inhaltliche Fragen. Fuer 'worum geht es', 'Ueberblick', 'Ergebnisse insgesamt' nutze stattdessen zusammenfassen.",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string", "description": "Kennung aus der Dokumentliste, z.B. DS-24-005"},
            "frage": {"type": "string", "description": "Wonach gesucht wird - Fachbegriffe, nicht Fuellwoerter"}},
            "required": ["dokument", "frage"]}}},
    {"type": "function", "function": {
        "name": "abbildungen_auflisten",
        "description": "Alle Abbildungen eines Dokuments mit Nummer, Seite und Bildunterschrift. Nutze das, um die passende Abbildung auszuwaehlen (z.B. 'die wichtigste', 'die zum Ergebnis').",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"},
            "ab": {"type": "integer", "description": "Ab welcher Position (0 = Anfang) - fuer 'weitere Abbildungen'"}},
            "required": ["dokument"]}}},
    {"type": "function", "function": {
        "name": "abbildung_zeigen",
        "description": "Zeigt eine Abbildung im Chat. Gibt einen Platzhalter zurueck, den du an der passenden Stelle in deine Antwort setzt.",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"},
            "nummer": {"type": "string", "description": "Bildnummer aus der Unterschrift, z.B. 6.12"}},
            "required": ["dokument", "nummer"]}}},
    {"type": "function", "function": {
        "name": "seite_zeigen",
        "description": "Zeigt eine ganze Seite eines Dokuments als Bild im Chat (z.B. eine Seite mit Formeln, einer Tabelle oder Herleitung). Gibt einen Platzhalter zurueck, den du in die Antwort setzt.",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"}, "seite": {"type": "integer"}},
            "required": ["dokument", "seite"]}}},
    {"type": "function", "function": {
        "name": "zusammenfassen",
        "description": "Zusammenfassung des GANZEN Dokuments (dauert bei langen Arbeiten ein bis zwei Minuten). Optional mit Auftrag (z.B. 'als Stichpunkte fuer einen Vortrag').",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"},
            "auftrag": {"type": "string"}},
            "required": ["dokument"]}}},
    {"type": "function", "function": {
        "name": "zaehlen",
        "description": "Zaehlbares eines Dokuments: seiten, abbildungen, tabellen, verfasser, jahr, titel.",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"},
            "was": {"type": "string", "enum": ["seiten", "abbildungen", "tabellen", "verfasser", "jahr", "titel"]}},
            "required": ["dokument", "was"]}}},
    {"type": "function", "function": {
        "name": "bestand",
        "description": "Liste der Dokumente im Bereich, optional zu einem Thema oder einer Art. Fuer 'was habt ihr', 'gibt es andere Arbeiten zu X'.",
        "parameters": {"type": "object", "properties": {
            "thema": {"type": "string"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "dokument_finden",
        "description": "Findet die Kennung zu einem Verfasser, Titelwort oder Tippfehler ('beker', 'Sasse', 'die mit den Blattfedern').",
        "parameters": {"type": "object", "properties": {
            "suche": {"type": "string"}},
            "required": ["suche"]}}},
    {"type": "function", "function": {
        "name": "abkuerzung",
        "description": "Wofuer eine Abkuerzung in einem Dokument steht (aus dem Dokument selbst).",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string"}, "kurz": {"type": "string"}},
            "required": ["dokument", "kurz"]}}},
    {"type": "function", "function": {
        "name": "exportieren",
        "description": "Gibt etwas als kopierbaren Text aus: 'bibtex' (Katalog) oder 'csv' (letzte Tabelle im Gespraech).",
        "parameters": {"type": "object", "properties": {
            "format": {"type": "string", "enum": ["bibtex", "csv"]}},
            "required": ["format"]}}},
]

BILD_MARKE = re.compile(r"\[\[BILD:([^:\]]+):(\d{1,4}):([^\]]*)\]\]")


def system_text(faden_dok=None, dokumente=None, kontakt=""):
    teile = [
        "Du bist die Wissensdatenbank dieses Bereichs und fuehrst ein Gespraech ueber die "
        "hinterlegten Dokumente - was immer dort liegt: Berichte, Normen, Arbeitsanweisungen, "
        "Dissertationen, Protokolle. Du redest wie ein kundiger Kollege: direkt, knapp, auf "
        "Deutsch, ohne Floskeln.",
        "GRUNDSAETZE:\n"
        "1. Inhalte kommen NUR aus den Werkzeugen. Nichts aus eigenem Wissen behaupten, nichts erfinden. "
        "Steht etwas nicht in den gelesenen Seiten, sag das.\n"
        "2. Jede Aussage aus einem Dokument endet mit (Kennung, S. n), z.B. (DS-24-005, S. 141). "
        "Die wichtigste Aussage je Punkt belegst du mit einem WOERTLICHEN Zitat von der Seite in „…“, danach (Kennung, S. n).\n"
        "3. Will der Mensch mehrere Dinge in einem Satz, erledige ALLE (z.B. zusammenfassen UND Bild zeigen).\n"
        "4. Eine Rueckmeldung ('das ist falsch', 'nein, Grafiken zeigen', 'sicher?', 'warum stand da X?') "
        "ist keine neue Suche: Lies, was du zuletzt geantwortet hast, und reagiere darauf - korrigiere, "
        "erklaere oder tu das Verlangte. Wiederhole nie einfach die letzte Antwort.\n"
        "5. 'die Arbeit', 'das Dokument', 'daraus', 'andere Grafiken' beziehen sich auf das Faden-Dokument. "
        "Ein neuer Verfasser oder eine Kennung wechselt das Dokument (dokument_finden, wenn unklar).\n"
        "6. Bilder: erst abbildungen_auflisten, dann die passende Nummer mit abbildung_zeigen holen und den "
        "Platzhalter in die Antwort setzen; sag in einem Satz, warum diese. 'Weitere' = abbildungen_auflisten mit 'ab'.\n"
        "7. Ist die Eingabe wirklich unklar, stell EINE kurze Rueckfrage mit 2-3 Optionen - statt zu raten.\n"
        "8. Fragen zu dir selbst (was du kannst, welches Dokument du nutzt, warum eine Antwort so aussah) "
        "beantwortest du direkt aus dem Gespraechszustand - ohne Werkzeuge. 'Unlesbare Stellen' heisst: "
        "Formeln oder Tabellen im PDF-Text sind zerlegt - der Rest des Dokuments ist lesbar.\n"
        "8b. Meinungs- und Diskussionsfragen ('ist 0,6 nicht sehr konservativ?') beantwortest du "
        "sachlich aus dem, was die Dokumente hergeben, und sagst offen, wo die Einschaetzung endet.\n"
        "9. Zahlen: Wert, Einheit, Messbedingung, Seite - fehlt die Bedingung, schreib 'Bedingung fehlt'.\n"
        "10. Keine Meta-Saetze wie 'Basierend auf den Werkzeugen'. Schreibe NIE Zeilen wie 'Gespraech mit "
        "Werkzeugen: ...' - das fuegt die Anlage selbst an.\n"
        "11. Liefert ein Werkzeug eine Markdown-Tabelle oder eine Liste (Bestand, Abbildungen), uebernimm "
        "sie UNVERAENDERT und vollstaendig - keine Kuerzung, keine Umformung in Fliesstext, keine "
        "eigenen Seitenzahlen. Fehlt dir eine Seitenzahl, lass sie weg.\n"
        "12. 'Zeig mir die Seite / eine Seite mit Formeln' -> seite_zeigen mit der Seitenzahl aus seiten_lesen.",
        "GESPRAECHSZUSTAND:\nFaden-Dokument: %s" % (faden_dok or "keins (frag nach oder nutze dokument_finden/bestand)"),
    ]
    if dokumente:
        teile.append("DOKUMENTE IM BEREICH (%d):\n%s" % (len(dokumente), "\n".join("- " + d for d in dokumente[:40])))
    if kontakt:
        teile.append("Ansprechpartner fuer alles, was du nicht kannst: %s" % kontakt)
    return "\n\n".join(teile)


def nachrichten(system, verlauf, frage):
    """verlauf = [(frage, art, antwort)] aelteste zuerst."""
    msgs = [{"role": "system", "content": system}]
    for f, art, ant in (verlauf or [])[-6:]:
        if f:
            msgs.append({"role": "user", "content": str(f)[:600]})
        if ant:
            msgs.append({"role": "assistant", "content": str(ant)[:1800]})
    msgs.append({"role": "user", "content": (frage or "").strip()})
    return msgs


_MUELL = re.compile(r"<\|?channel\|?>|<\|[a-z_]+\|>|^\s*thought\s*$|<start_of_turn>|<end_of_turn>", re.M)


def bereinigen(text):
    """Template-Reste des Modells entfernen (gemessen: 'thought', '<channel|>')."""
    t = _MUELL.sub("", text or "")
    t = re.sub(r"^(?:thought|analysis)\s*\n", "", t.strip(), flags=re.I)
    return t.strip()


def _modell_aufruf(messages, tools=True, denken=None):
    leib = json.dumps({
        "model": MODELL,
        "messages": messages,
        "tools": WERKZEUGE if tools else [],
        "stream": False,
        "think": bool(DENKEN if denken is None else denken),
        "options": {"temperature": 0, "num_ctx": 65536, "num_predict": 1800},
        "keep_alive": "24h",
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=leib, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        antwort = json.load(r)
    return antwort.get("message") or {}


_BILDNENNUNG = re.compile(r"\[?\b(?:Abbildung|Abb\.?|Bild|Figure|Fig\.?)\s*(\d{1,2}[.\-]\d{1,3})\b\]?", re.I)


def bildnennungen(text):
    """Alle Abbildungsnummern, die im Text vorkommen (in Reihenfolge, ohne Doppelte)."""
    aus = []
    for m in _BILDNENNUNG.finditer(text or ""):
        n = m.group(1).replace("-", ".")
        if n not in aus:
            aus.append(n)
    return aus


_KENNUNG = re.compile(r"\b([A-Z]{1,4}-\d{2}-\d{3})\b")
_BELEG = re.compile(r"\(\s*([A-Z]{1,4}-\d{2}-\d{3})\s*,\s*S\.?\s*(\d{1,4})\s*\)")


def _dokument_im_text(text, faden_dok):
    m = _KENNUNG.search(text or "")
    return m.group(1) if m else (faden_dok or None)


def waechter_bilder(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None):
    """Nennt das Modell Abbildungsnummern, ohne die Liste geholt zu haben?
    Gemessen 26.08.: bei 'andere Grafiken' erfand es zehn Nummern samt
    Seiten - und wiederholte sie nach einer blossen Aufforderung. Deshalb
    liefert der Waechter einen WERKZEUGAUFTRAG, den fuehren() selbst
    ausfuehrt: {"werkzeug", "args", "hinweis"} - oder None."""
    if not bildnennungen(text):
        return None
    namen = {n for n, _, _ in (aufrufe or [])}
    if namen & {"abbildungen_auflisten", "abbildung_zeigen"}:
        return None
    dok = _dokument_im_text(text, faden_dok)
    if not dok:
        return None
    return {"werkzeug": "abbildungen_auflisten", "args": {"dokument": dok},
            "hinweis": ("Die eben genannten Abbildungsnummern stammen aus keinem Werkzeug. "
                        "Oben steht die ECHTE Liste. Antworte neu und nenne NUR Nummern "
                        "und Seiten aus dieser Liste; zeige passende Bilder mit abbildung_zeigen.")}


def waechter_belege(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None):
    """Zitiert das Modell Seiten (Kennung, S. n), die kein Werkzeug geliefert
    hat und die auch nicht aus dem bisherigen Gespraech stammen? Gemessen
    26.08.: 'die Einspannung erhoeht die Lebensdauer (DS-24-005, S. 12)' -
    erfunden, das Gegenteil der Arbeit, ohne eine Seite gelesen zu haben."""
    belege = _BELEG.findall(text or "")
    if not belege:
        return None
    gelesen = set(n for n, _, _ in (aufrufe or []))
    quelle = "\n".join(tool_texte or []) + "\n" + "\n".join(verlauf_texte or [])
    zusammengefasst = {str(a.get("dokument") or "") for n, a, _ in (aufrufe or []) if n == "zusammenfassen"}
    for kennung, seite in belege:
        if any(kennung in z or z in kennung for z in zusammengefasst if z):
            continue
        if re.search(r"%s,\s*Seite\s+%s\b" % (re.escape(kennung), seite), quelle) or \
                re.search(r"\(\s*%s\s*,\s*S\.?\s*%s\s*\)" % (re.escape(kennung), seite), quelle) or \
                re.search(r"===\s*Seite\s+%s\s*===" % seite, quelle):
            continue
        return {"werkzeug": "seiten_lesen", "args": {"dokument": kennung, "frage": frage},
                "hinweis": ("Deine Antwort nennt (%s, S. %s), aber diese Seite hat kein Werkzeug "
                            "geliefert. Oben stehen jetzt die passenden Seiten. Antworte neu und "
                            "stuetze dich NUR auf gelesene Seiten; was dort nicht steht, sagst du."
                            % (kennung, seite))}
    return None


def waechter(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None):
    for w in (waechter_bilder, waechter_belege):
        a = w(text, aufrufe, faden_dok, frage, tool_texte, verlauf_texte)
        if a:
            return a
    return None


def fuehren(frage, verlauf, faden_dok, dokumente, werkzeug, rufen=None, kontakt="",
            melden=None, max_runden=None, pruefer=None):
    """Ein Gespraechszug. werkzeug(name, args) -> str. rufen(messages) -> message.
    Rueckgabe dict: text, aufrufe [(name, args, ms)], dokumente (beruehrte
    Kennungen), runden, ms, fehler."""
    begonnen = time.time()
    rufen = rufen or _modell_aufruf
    msgs = nachrichten(system_text(faden_dok, dokumente, kontakt), verlauf, frage)
    aufrufe, beruehrt, texte = [], [], []
    fehler = None
    m = {}
    geprueft = False
    for runde in range(max_runden or MAX_RUNDEN):
        try:
            m = rufen(msgs)
        except Exception as e:
            fehler = "Modell: %s" % str(e)[:120]
            break
        inhalt = bereinigen(m.get("content") or "")
        calls = m.get("tool_calls") or []
        if inhalt and calls:
            texte.append(inhalt)     # Text VOR den Aufrufen (Teilantwort) behalten
        if not calls:
            # ⭐ WAECHTER-RUNDE: Behauptet das Modell etwas, was kein Werkzeug
            #   geliefert hat (Abbildungslisten), muss es nacharbeiten - einmal.
            korrektur = None
            if not geprueft:
                try:
                    tool_texte = [x.get("content", "") for x in msgs if x.get("role") == "tool"]
                    verlauf_texte = [x.get("content", "") for x in msgs[:-1] if x.get("role") == "assistant"]
                    korrektur = (pruefer or waechter)(inhalt, aufrufe, faden_dok, frage, tool_texte, verlauf_texte)
                except Exception:
                    korrektur = None
            if korrektur:
                # Nicht bitten, sondern nachschlagen: das Werkzeug selbst ausfuehren
                # und das Ergebnis als einzige Quelle vorlegen.
                geprueft = True
                wname, wargs = korrektur["werkzeug"], korrektur["args"]
                if melden:
                    try:
                        melden(wname, wargs)
                    except Exception:
                        pass
                try:
                    ergebnis = werkzeug(wname, wargs)
                except Exception as e:
                    ergebnis = "Fehler im Werkzeug %s: %s" % (wname, str(e)[:120])
                aufrufe.append((wname, wargs, 0))
                aufrufe.append(("waechter", {"grund": korrektur["hinweis"][:60]}, 0))
                d = wargs.get("dokument")
                if d and d not in beruehrt:
                    beruehrt.append(d)
                msgs.append({"role": "assistant", "content": m.get("content") or ""})
                msgs.append({"role": "tool", "content": str(ergebnis)[:20000]})
                msgs.append({"role": "user", "content": korrektur["hinweis"]})
                continue
            if inhalt:
                texte.append(inhalt)
            break
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": calls})
        for c in calls:
            fn = c.get("function") or {}
            name = fn.get("name") or ""
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if melden:
                try:
                    melden(name, args)
                except Exception:
                    pass
            t0 = time.time()
            try:
                ergebnis = werkzeug(name, args)
            except Exception as e:
                ergebnis = "Fehler im Werkzeug %s: %s" % (name, str(e)[:120])
            aufrufe.append((name, args, int((time.time() - t0) * 1000)))
            d = args.get("dokument") if isinstance(args, dict) else None
            if d and d not in beruehrt:
                beruehrt.append(d)
            msgs.append({"role": "tool", "content": str(ergebnis)[:20000]})
    else:
        # Rundenlimit erreicht - letzte Antwort ohne Werkzeuge erzwingen
        try:
            msgs.append({"role": "user", "content": "Schreibe jetzt die Antwort mit dem, was du hast."})
            m = rufen(msgs)
            inhalt = bereinigen(m.get("content") or "")
            if inhalt:
                texte.append(inhalt)
        except Exception as e:
            fehler = "Modell: %s" % str(e)[:120]
    # Nach einer Waechter-Runde zaehlt nur die neue Antwort.
    if geprueft and texte:
        texte = texte[-1:]
    # Doppelte Teilantworten (Modell wiederholt sich nach Werkzeugen) zusammenfuehren
    text = ""
    for t in texte:
        if t and t not in text:
            text = (text + "\n\n" + t).strip() if text else t
    return {"text": text, "aufrufe": aufrufe, "dokumente": beruehrt,
            "runden": len(aufrufe), "ms": int((time.time() - begonnen) * 1000),
            "fehler": fehler}
