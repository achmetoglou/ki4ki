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
# Gesamtbudget je Zug: sonst sieht der Mensch bei haengendem Modell bis zu
# 6 x 240 s "Denke nach ..." (Fund 01.09.).
BUDGET = float(os.environ.get("KI4KI_GESPRAECH_BUDGET") or "300")
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
        "name": "bestand_durchsuchen",
        "description": "Durchsucht ALLE Dokumente des Bereichs nach Begriffen und liefert die passendsten Seiten mit Text (Kennung, Seite). Fuer Fragen ohne bestimmtes Dokument, Pruefungsfragen, 'welche Norm/Arbeit sagt etwas zu X', Vergleiche ueber viele Dokumente.",
        "parameters": {"type": "object", "properties": {
            "begriffe": {"type": "string", "description": "Fachbegriffe, Fehlercode, Anlagenname - keine Fuellwoerter"}},
            "required": ["begriffe"]}}},
    {"type": "function", "function": {
        "name": "stoerfall_suchen",
        "description": "Stoerfallassistenz: sucht in Fehlerkatalogen, Handbuechern, Pruef- und Fehlerberichten nach Anlage, Fehlercode und Symptom und liefert die passenden Stellen mit Seite und Gueltigkeitsstatus. Danach antwortest du als Tabelle Ursache | Massnahme | Quelle (Kennung, S.) | Gueltigkeit.",
        "parameters": {"type": "object", "properties": {
            "anlage": {"type": "string"}, "fehlercode": {"type": "string"}, "symptom": {"type": "string"}},
            "required": []}}},
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
        "name": "pruefungsfrage",
        "description": "Eine EXAKTE Frage aus einem Pruefungskatalog des Bereichs (Excel/PDF mit Fragen und Optionen): Fragetext und Optionen woertlich, mit Nummer. nummer=0: die naechste noch nicht gestellte. Nur damit Pruefungsfragen stellen - nie selbst welche ausdenken.",
        "parameters": {"type": "object", "properties": {
            "dokument": {"type": "string", "description": "Kennung des Katalogs (leer = der einzige Katalog im Bereich)"},
            "nummer": {"type": "integer", "description": "Fragenummer, 0 = naechste"},
            "thema": {"type": "string", "description": "Themenwunsch, optional"}}}}},
    {"type": "function", "function": {
        "name": "exportieren",
        "description": "Gibt etwas als kopierbaren Text aus: 'bibtex' (Katalog) oder 'csv' (letzte Tabelle im Gespraech).",
        "parameters": {"type": "object", "properties": {
            "format": {"type": "string", "enum": ["bibtex", "csv"]}},
            "required": ["format"]}}},
]

BILD_MARKE = re.compile(r"\[\[BILD:([^:\]]+):(\d{1,4}):([^\]]*)\]\]")
# Gemessen 27.08.: Das 12B schreibt Werkzeugaufrufe gelegentlich als TEXT
# ("[abbildung_zeigen(dokument=“DS-24-005”, nummer=“2.1”)]") statt sie zu
# rufen - das Bild kam nie. Solche Zeilen werden erkannt und ausgefuehrt.
_PSEUDO = re.compile(r"\[?\b(seiten_lesen|abbildungen_auflisten|abbildung_zeigen|seite_zeigen|zusammenfassen|zaehlen|"
                     r"bestand_durchsuchen|stoerfall_suchen|dokument_finden|abkuerzung|pruefungsfrage|exportieren|bestand)"
                     r"\s*\(([^()]*)\)\]?")
_PSEUDO_ARG = re.compile(r"(\w+)\s*[=:]\s*[\"“”„']([^\"“”„']*)[\"“”„']")


def pseudo_aufrufe(text):
    """[(name, args)] aus als Text geschriebenen Aufrufen; '' wenn keine."""
    aus = []
    for m in _PSEUDO.finditer(text or ""):
        args = {k: v for k, v in _PSEUDO_ARG.findall(m.group(2))}
        if m.group(1) in ("seiten_lesen", "abbildungen_auflisten", "abbildung_zeigen", "seite_zeigen", "zusammenfassen",
                          "zaehlen", "abkuerzung") and not args.get("dokument"):
            continue
        aus.append((m.group(1), args))
    return aus


def ohne_pseudo(text):
    t = re.sub(_PSEUDO.pattern, " ", text or "")
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def system_text(faden_dok=None, dokumente=None, kontakt="", rolle="", allgemeinwissen=False):
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
        "12. 'Zeig mir die Seite / eine Seite mit Formeln' -> seite_zeigen mit der Seitenzahl aus seiten_lesen.\n"
        "13. STOERFALL (Anlage, Fehlercode, Symptom, 'was tun bei', 'Ursache', 'Abhilfe'): stoerfall_suchen, dann "
        "Tabelle | Ursache | Massnahme | Quelle (Kennung, S. n) | Gueltigkeit |. Nur Massnahmen, die auf den "
        "Seiten stehen. Findet sich nichts Belegtes: KEINE eigene Vermutung - sag 'nicht im Bestand belegt' und "
        "nenne den Ansprechpartner. Steht bei einer Quelle 'nicht freigegeben' oder 'abgelaufen', sag das dazu.\n"
        "14. PRUEFUNGSFRAGEN (Optionen A-D, 'welche Aussage ist falsch/richtig', 'was ist keine Aufgabe von'): "
        "Je Option: Beleg lesen, dann Option und Beleg WOERTLICH vergleichen. Sagt der Beleg das Gegenteil "
        "(z.B. 'verkuerzt die Lebensdauer' gegen 'erhoeht die Lebensdauer'), ist die Option FALSCH - nie 'richtig' "
        "mit einem widersprechenden Zitat. Ohne Beleg: 'nicht belegbar'. Schluss: ein Satz mit dem Urteil.\n"
        "15. Ohne Faden-Dokument und ohne genanntes Dokument: bestand_durchsuchen statt raten oder nachfragen.\n"
        "17. LINKS: Schreibe (Kennung, S. n) - die Anlage macht daraus einen Link auf die Seite. Ein ganzes Dokument "
        "verlinkst du als [Kennung](/pdf/Kennung). Sag NIE, du koenntest keine Links erzeugen.\n"
        "18. WERKZEUGE rufst du NUR ueber die Funktionsschnittstelle auf - nie als Text wie "
        "'abbildung_zeigen(dokument=...)' in die Antwort schreiben. Ein solcher Text ist kein Aufruf.\n"
        "19. PRUEFUNGSKATALOGE (Dokumente, die als Katalog markiert sind) enthalten Antwortoptionen, keine belegten "
        "Aussagen: zitiere eine Option NIE als Tatsache. Fakten kommen aus Normen, Handbuechern, Arbeiten.\n"
        "16. PRUEFUNGSKATALOG ('stell mir eine Pruefungsfrage', 'frag mich ab', 'Frage 7'): NUR pruefungsfrage nutzen und "
        "dessen Text UNVERAENDERT ausgeben - nie eigene Fragen oder Optionen erfinden. Antwortet der Mensch auf eine "
        "Frage, gilt allein die Loesung aus dem Katalogeintrag (RICHTIG/FALSCH im Werkzeugtext); fehlt sie, sag das.",
        "20. BESTAND: Fragt der Mensch, WELCHE Dokumente/Arbeiten/Unterlagen es gibt - auch knapp ('und im Bereich X', "
        "'als Liste', 'als Katalog', 'als Tabelle') -, rufe bestand(thema=...) auf und gib die gelieferte Tabelle "
        "unveraendert aus. Fasse dann KEINE Inhalte zusammen.",
        "GESPRAECHSZUSTAND:\nFaden-Dokument: %s" % (faden_dok or "keins (frag nach oder nutze dokument_finden/bestand)"),
    ]
    if allgemeinwissen:
        teile.append("ALLGEMEINWISSEN ERLAUBT (dieser Bereich steht auf Modus 'Chat'): Findet sich im Bestand nichts "
                     "oder fragt der Mensch ausdruecklich nach 'ausserhalb der Dokumente', MUSST du aus eigenem Wissen "
                     "antworten (nicht nur 'nicht belegt' sagen) - als EIGENER Absatz, der woertlich mit 'Aus Allgemeinwissen (nicht aus den Dokumenten):' "
                     "beginnt, ohne Belege, ohne erfundene Kennungen. Nie mit Aussagen aus den Dokumenten vermischen.")
    if rolle:
        teile.append("ROLLE DIESES BEREICHS (vom Betreiber festgelegt - gilt zusaetzlich zu den Grundsaetzen):\n" + rolle.strip())
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
    m = dict(antwort.get("message") or {})
    m["_nutzung"] = {"prompt": int(antwort.get("prompt_eval_count") or 0), "antwort": int(antwort.get("eval_count") or 0),
                     "dauer_ms": int((antwort.get("total_duration") or 0) / 1e6)}
    return m


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
# ⭐ Belege fuer JEDE Kennung, nicht nur DS-24-005: "(DVS 2213-1_neu, S. 12)",
#   "(Pruefungsfragen zu DVS 2291, S. 1)". Gemessen 26.08. im Bereich AuW:
#   das Modell erfand Zitate mit solchen Kennungen, und der Waechter sah sie
#   nicht, weil er nur DS-24-xxx kannte.
_BELEG = re.compile(r"\(\s*([A-Za-z0-9ÄÖÜäöüß][^(),\n]{1,90}?)\s*,\s*S\.?\s*(\d{1,4})\s*\)")


def belege(text):
    return _BELEG.findall(text or "")


def _dokument_im_text(text, faden_dok, kennungen=None):
    m = _KENNUNG.search(text or "")
    if m:
        return m.group(1)
    for k in sorted(kennungen or [], key=len, reverse=True):
        if k and k in (text or ""):
            return k
    return faden_dok or None


def waechter_bilder(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None, kennungen=None):
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
    dok = _dokument_im_text(text, faden_dok, kennungen)
    if not dok:
        return None
    return {"werkzeug": "abbildungen_auflisten", "args": {"dokument": dok},
            "hinweis": ("Die eben genannten Abbildungsnummern stammen aus keinem Werkzeug. "
                        "Oben steht die ECHTE Liste. Antworte neu und nenne NUR Nummern "
                        "und Seiten aus dieser Liste; zeige passende Bilder mit abbildung_zeigen.")}


def waechter_belege(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None, kennungen=None):
    """Zitiert das Modell Seiten (Kennung, S. n), die kein Werkzeug geliefert
    hat und die auch nicht aus dem bisherigen Gespraech stammen? Gemessen
    26.08.: 'die Einspannung erhoeht die Lebensdauer (DS-24-005, S. 12)' -
    erfunden, das Gegenteil der Arbeit, ohne eine Seite gelesen zu haben."""
    belege = _BELEG.findall(text or "")
    if not belege:
        return None
    if kennungen:
        # Nur Belege auf Dokumente des Bereichs pruefen - alles andere ist Text in Klammern.
        bekannt = {re.sub(r"\.(?:md|pdf)$", "", k.lower()) for k in kennungen if k}
        belege = [(re.sub(r"\.(?:md|pdf)$", "", k.strip(), flags=re.I), s) for k, s in belege]
        belege = [(k, s) for k, s in belege if k.lower() in bekannt or _KENNUNG.fullmatch(k)]
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


def waechter(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None, kennungen=None):
    for w in (waechter_bilder, waechter_belege):
        a = w(text, aufrufe, faden_dok, frage, tool_texte, verlauf_texte, kennungen)
        if a:
            return a
    return None


def fuehren(frage, verlauf, faden_dok, dokumente, werkzeug, rufen=None, kontakt="",
            melden=None, max_runden=None, pruefer=None, vorwissen=None, denken=None, kennungen=None, rolle="",
            allgemeinwissen=False):
    """Ein Gespraechszug. werkzeug(name, args) -> str. rufen(messages) -> message.
    Rueckgabe dict: text, aufrufe [(name, args, ms)], dokumente (beruehrte
    Kennungen), runden, ms, fehler."""
    begonnen = time.time()
    rufen = rufen or (lambda m: _modell_aufruf(m, denken=denken))
    msgs = nachrichten(system_text(faden_dok, dokumente, kontakt, rolle, allgemeinwissen), verlauf, frage)
    aufrufe, beruehrt, texte = [], [], []
    nutzung = {"prompt": 0, "antwort": 0, "dauer_ms": 0}
    # ⭐ VORWISSEN: Belege, die der Proxy VOR dem Modell deterministisch geholt
    #   hat (Pruefungsfragen je Option, Stoerfall ohne Dokument, Frage ohne
    #   Faden-Dokument). Sie stehen als Werkzeugergebnis im Gespraech - das
    #   Modell muss nicht raten, welches Dokument gemeint ist (gemessen 26.08.:
    #   bei einer Pruefungsfrage riet es ein Dokument und erfand Zitate).
    for name, args, ergebnis in (vorwissen or []):
        msgs.append({"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": name, "arguments": args}}]})
        msgs.append({"role": "tool", "content": str(ergebnis)[:20000]})
        aufrufe.append((name, args, 0))
        d = args.get("dokument") if isinstance(args, dict) else None
        if d and d not in beruehrt:
            beruehrt.append(d)
    fehler = None
    m = {}
    geprueft = False
    _beginn = time.time()
    for runde in range(max_runden or MAX_RUNDEN):
        if time.time() - _beginn > BUDGET:
            fehler = "Zeitbudget von %d s erschoepft" % BUDGET
            break
        try:
            m = rufen(msgs)
        except Exception as e:
            fehler = "Modell: %s" % str(e)[:120]
            break
        inhalt = bereinigen(m.get("content") or "")
        calls = m.get("tool_calls") or []
        for k, v in (m.get("_nutzung") or {}).items():
            nutzung[k] = nutzung.get(k, 0) + int(v or 0)
        if not calls:
            # Als Text hingeschriebene Aufrufe -> echte Aufrufe (einmal je Runde)
            ps = pseudo_aufrufe(inhalt)
            if ps and len(aufrufe) < (max_runden or MAX_RUNDEN) * 3:
                calls = [{"function": {"name": n, "arguments": a}} for n, a in ps]
                inhalt = ohne_pseudo(inhalt)
                m = dict(m); m["content"] = inhalt
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
                    korrektur = (pruefer or waechter)(inhalt, aufrufe, faden_dok, frage, tool_texte, verlauf_texte, kennungen)
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
            "fehler": fehler, "nutzung": nutzung}
