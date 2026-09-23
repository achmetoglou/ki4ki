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
import ollamaruf
import threading
import time
import urllib.request

AN = (os.environ.get("KI4KI_GESPRAECH") or "0") == "1"
MODELL = os.environ.get("KI4KI_GESPRAECH_MODELL") or "gemma4:12b"
URL = (os.environ.get("KI4KI_GESPRAECH_URL") or os.environ.get("KI4KI_NETZ_URL")
       or "http://nothink-proxy:11435/api/chat")
TIMEOUT = float(os.environ.get("KI4KI_GESPRAECH_TIMEOUT") or "240")
MAX_RUNDEN = int(os.environ.get("KI4KI_GESPRAECH_RUNDEN") or "5")
# ⛔ Bis zum 23.09. stand hier fest 1800. Gemessen an einer Anweisung mit
#   elf Fragen: kurze Antworten kamen alle durch, ausfuehrliche brachen
#   MITTEN IM WORT ab ("... Du hast 12 Stifte und bekommst"). Genau das
#   meldete ein Nutzer am 18.09.: "bricht in der 4ten Frage ab" - bei
#   Fachtext (2,1 Zeichen je Token) reichen 1800 Token fuer rund vier
#   ausfuehrliche Antworten. Das Kontextfenster fasst 65.536; der Deckel
#   war die Engstelle, nicht das Modell.
ANTWORT_TOKEN = int(os.environ.get("KI4KI_ANTWORT_TOKEN") or "4096")
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


def system_text(faden_dok=None, dokumente=None, kontakt="", rolle="", allgemeinwissen=False, modell=None):
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
        "Platzhalter in die Antwort setzen; sag in einem Satz, warum diese. 'Weitere' = abbildungen_auflisten mit 'ab'.\n"        "6b. Ein Werkzeug, das nichts findet, ist KEIN Thema fuer die Antwort. Beantworte dann die "
        "gestellte Frage aus dem Text. Erwaehne fehlende Abbildungen oder Seiten nur, wenn "
        "ausdruecklich danach gefragt wurde - sonst kein Wort darueber.\n"
        "7. Ist die Eingabe wirklich unklar, stell EINE kurze Rueckfrage mit 2-3 Optionen - statt zu raten.\n"
        "8. Fragen zum GESPRAECH selbst (welches Dokument du gerade nutzt, warum eine Antwort so "
        "aussah, was du zuletzt gesagt hast) beantwortest du direkt aus dem Gespraechszustand - "
        "ohne Werkzeuge. NICHT hierher gehoeren Fragen zur BEDIENUNG, Installation oder zum "
        "Betrieb der Anlage ('wie lade ich Dokumente hoch?', 'wie loesche ich etwas?', 'welcher "
        "Schalter...?'): das steht in den Dokumenten, dort wird IMMER erst gesucht. Behaupte nie "
        "aus eigenem Wissen, was die Anlage kann oder nicht kann. 'Unlesbare Stellen' heisst: "
        "Formeln oder Tabellen im PDF-Text sind zerlegt - der Rest des Dokuments ist lesbar.\n"
        "8b. Meinungs- und Diskussionsfragen ('ist 0,6 nicht sehr konservativ?') beantwortest du "
        "sachlich aus dem, was die Dokumente hergeben, und sagst offen, wo die Einschaetzung endet.\n"
        "9. Zahlen: Wert, Einheit, Messbedingung, Seite - fehlt die Bedingung, schreib 'Bedingung fehlt'.\n"
        "10. Keine Meta-Saetze wie 'Basierend auf den Werkzeugen'. Schreibe NIE Zeilen wie 'Gespraech mit "
        "Werkzeugen: ...' - das fuegt die Anlage selbst an. Sprich auch NIE ueber deine eigenen "
        "Zwischenschritte, ueber Hinweise der Anlage an dich oder darueber, dass du dich korrigierst "
        "('Danke, ich habe die Fundstellen gelesen', 'meine vorherige Antwort war falsch', 'ich habe "
        "keine Abbildungsnummern genannt'). Der Leser sieht nur DIESE eine Antwort und kennt nichts "
        "davon - schreib sie so, als waere es deine erste.\n"
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
        "21. HALBSAETZE ('genauer bitte', 'mehr dazu', 'und weiter'): beziehen sich auf das Faden-Dokument und die "
        "letzte Antwort - dort weiterlesen (seiten_lesen), keine Bestandssuche. ZAHLEN wie Seitenzahl, Anzahl "
        "Abbildungen/Tabellen kommen aus dem Werkzeug zaehlen, nie aus dem Text abgelesen.",
        # Fremdmodelle (Modell je Bereich) kennen unsere Zitierform nicht aus
        # dem Alltag - ohne diese Erinnerung schrieben sie Fettdruck statt
        # (Kennung, S. n), und die Belegpruefung lief ins Leere (gemessen 02.09.).
        ("22. ZITIERFORM - WICHTIGSTE REGEL FUER DICH: JEDE inhaltliche Aussage endet mit ihrem Beleg in GENAU dieser "
         "Form: (Kennung, S. n) - die Kennung exakt wie in DOKUMENTE IM BEREICH, die Seite aus dem gelesenen Text. "
         "Beispiel: 'Die Routine berechnet das Profil (DS-24-006, S. 125).' Fettgedruckte Namen, Fussnoten oder "
         "Aussagen ohne Seitenangabe gelten als UNBELEGT und werden gestrichen. Erst lesen (seiten_lesen), dann "
         "mit Seite belegen." if modell else None),
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
    return "\n\n".join(t for t in teile if t)


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


def _modell_aufruf(messages, tools=True, denken=None, modell=None):
    leib = json.dumps({
        "model": modell or MODELL,
        "messages": messages,
        "tools": WERKZEUGE if tools else [],
        "stream": False,
        "think": bool(DENKEN if denken is None else denken),
        "options": {"temperature": 0, "num_ctx": 65536,
                    "num_predict": ANTWORT_TOKEN},
        "keep_alive": "24h",
    }).encode("utf-8")
    # ⛔ ollamaruf, nicht urlopen: Bei einer Zeitueberschreitung
    #   muss die Verbindung WIRKLICH zugehen, sonst rechnet Ollama
    #   weiter ins Leere (gemessen 23.09.: zwei Zombie-Auftraege
    #   bei 0,41 t/s, die jede naechste Frage mitbremsten).
    antwort = ollamaruf.fragen(URL, leib, TIMEOUT)
    m = dict(antwort.get("message") or {})
    m["_nutzung"] = {"prompt": int(antwort.get("prompt_eval_count") or 0), "antwort": int(antwort.get("eval_count") or 0),
                     "dauer_ms": int((antwort.get("total_duration") or 0) / 1e6)}
    # ⭐ Ollama sagt selbst, WARUM es aufgehoert hat. Bis zum 23.09. hat das
    #   niemand gelesen - eine abgeschnittene Antwort sah aus wie eine fertige.
    m["_abgeschnitten"] = abgeschnitten(antwort)
    return m


def abgeschnitten(antwort):
    """Hat das Modell an der Token-Grenze aufgehoert statt von selbst?

    Erste Wahl ist `done_reason` ("length" gegen "stop"). Aeltere
    Ollama-Fassungen melden das nicht; dann bleibt die Zahl: Wer die
    Grenze auf das Token genau ausreizt, wurde fast sicher geschnitten.
    """
    if (antwort or {}).get("done_reason") == "length":
        return True
    if (antwort or {}).get("done_reason"):
        return False
    return int((antwort or {}).get("eval_count") or 0) >= ANTWORT_TOKEN


_ABSCHNITT_HINWEIS = (
    "\n\n---\n*⚠ Diese Antwort wurde an der Laengengrenze **abgeschnitten** "
    "(%d Token). Frag nach dem fehlenden Teil - zum Beispiel \u201eschreib ab "
    "Punkt X weiter\u201c - oder stell weniger Fragen auf einmal.*")


def abschnitt_vermerken(text, wurde_abgeschnitten):
    """Einen Abschnitt benennen, statt ihn zu verschweigen.

    ⛔ Das Schlimmste am Deckel war nicht der Deckel, sondern die Stille:
      Die Antwort endete mitten im Wort, und nichts sagte, dass da noch
      etwas fehlt. Wer es nicht bemerkt, haelt Unvollstaendiges fuer
      vollstaendig - bei einer Wissensdatenbank der teuerste Fehler.
    """
    if not wurde_abgeschnitten or not text:
        return text
    return text + (_ABSCHNITT_HINWEIS % ANTWORT_TOKEN)


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


# ⭐ Jede Waechter-Rueckmeldung endet damit. Gemessen 15.09. mit Qwen: das
#   Modell antwortete der Rueckmeldung statt dem Nutzer ("Danke - ich habe die
#   Fundstellen gelesen", "meine vorherige Antwort war falsch"). Der Leser
#   sieht nur EINE Antwort und kennt die Zwischenschritte nicht.
REGIE = ("Schreibe die VOLLSTAENDIGE Antwort auf die urspruengliche Frage neu, als "
         "waere es deine erste - und erwaehne diese Rueckmeldung mit keinem Wort.")


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
                        "Oben steht die ECHTE Liste. Nenne NUR Nummern "
                        "und Seiten aus dieser Liste; zeige passende Bilder mit abbildung_zeigen. "
                        + REGIE)}


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
                            "geliefert. Oben stehen jetzt die passenden Seiten. Stuetze dich NUR "
                            "auf gelesene Seiten; was dort nicht steht, sagst du. %s"
                            % (kennung, seite, REGIE))}
    return None


# Fragen, die wirklich nur den Gespraechsverlauf betreffen - dort ist eine
# Antwort ohne Werkzeug richtig. Alles andere wird nachgeschlagen.
_VERLAUFSFRAGE = re.compile(
    r"^\s*(wie\s+meinst\s+du|was\s+meinst\s+du\s+damit|welches\s+dokument\s+"
    r"(nutzt|benutzt|hast)\s+du|woher\s+(hast|weisst)\s+du|warum\s+(sagst|"
    r"antwortest|schreibst)\s+du|was\s+hast\s+du\s+(gerade|zuletzt)\s+gesagt|"
    r"wiederhol|nochmal\s+bitte|erklaer\s+das\s+nochmal)", re.I)


def waechter_ohne_suche(text, aufrufe, faden_dok=None, frage="", tool_texte=None,
                        verlauf_texte=None, kennungen=None):
    """Hat das Modell geantwortet, OHNE ein einziges Werkzeug zu rufen?

    Gemessen 15.09. (Faden b3c1a804): "wie lade ich dokumente hoch?" ->
    "Das Hochladen von Dokumenten ist nicht Teil der Funktionen dieser
    Schnittstelle", in 2,9 s, ohne Werkzeug, ohne Beleg - frei erfunden. Die
    Antwort steht woertlich in KI4KI-Haeufige-Fragen. Das Modell hielt die
    Frage fuer eine Frage ueber SICH (Regel 8) und beschrieb seine
    Chat-Schnittstelle statt der Anlage.

    Ueber 328 Stufe-2-Antworten: 96 ohne Beleg, davon 27 unter 6 s ohne jede
    Fundstelle. Eine Wissensdatenbank mit Belegpflicht darf nicht behaupten,
    ohne nachgesehen zu haben - also wird einmal gesucht und neu geantwortet.
    """
    if aufrufe:                       # Vorwissen zaehlt mit: dann lag Material vor
        return None
    if not (text or "").strip():
        return None
    if _VERLAUFSFRAGE.match(frage or ""):
        return None
    begriffe = _suchbegriffe(frage)
    if not begriffe:
        return None
    return {"werkzeug": "bestand_durchsuchen", "args": {"begriffe": begriffe},
            "hinweis": ("Oben stehen die Fundstellen aus dem Bestand. Stuetze dich NUR "
                        "darauf. Steht die Antwort wirklich nicht darin, sag genau das - "
                        "erfinde nichts ueber die Anlage. " + REGIE)}


# Fuellwoerter raus: die Suche will Begriffe, keine Satzteile.
_FUELL = frozenset((
    "wie", "was", "wo", "wer", "wann", "warum", "wieso", "welche", "welcher",
    "welches", "ich", "du", "mir", "mich", "dir", "man", "hier", "das", "der",
    "die", "den", "dem", "ein", "eine", "einen", "einem", "einer", "und",
    "oder", "aber", "denn", "ist", "sind", "war", "kann", "kannst", "koennen",
    "muss", "soll", "will", "wird", "werden", "hat", "habe", "haben", "es",
    "in", "im", "an", "am", "auf", "aus", "bei", "mit", "von", "vom", "zu",
    "zum", "zur", "fuer", "ueber", "nach", "vor", "denn", "nicht", "kein",
    "keine", "auch", "noch", "schon", "mal", "bitte", "eigentlich", "denn"))


def _suchbegriffe(frage):
    woerter = re.findall(r"[\wäöüÄÖÜß-]{3,}", frage or "")
    behalten = [w for w in woerter if w.lower() not in _FUELL]
    return " ".join(behalten[:8]) or " ".join(woerter[:8])


def waechter(text, aufrufe, faden_dok=None, frage="", tool_texte=None, verlauf_texte=None, kennungen=None):
    for w in (waechter_bilder, waechter_belege, waechter_ohne_suche):
        a = w(text, aufrufe, faden_dok, frage, tool_texte, verlauf_texte, kennungen)
        if a:
            return a
    return None


def fuehren(frage, verlauf, faden_dok, dokumente, werkzeug, rufen=None, kontakt="",
            melden=None, max_runden=None, pruefer=None, vorwissen=None, denken=None, kennungen=None, rolle="",
            allgemeinwissen=False, modell=None):
    """Ein Gespraechszug. werkzeug(name, args) -> str. rufen(messages) -> message.
    Rueckgabe dict: text, aufrufe [(name, args, ms)], dokumente (beruehrte
    Kennungen), runden, ms, fehler."""
    begonnen = time.time()
    rufen = rufen or (lambda m: _modell_aufruf(m, denken=denken, modell=modell))
    msgs = nachrichten(system_text(faden_dok, dokumente, kontakt, rolle, allgemeinwissen, modell=modell), verlauf, frage)
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
            # Mit dem Gelesenen antworten statt mit leeren Haenden (Fund 02.09.:
            # 5 Volltext-Teile gelesen, dann Fehlermeldung statt Antwort, waehrend
            # das nackte System in 8 s antwortete). Ein letzter Zug ohne Werkzeuge.
            if any(x.get("role") == "tool" for x in msgs):
                try:
                    msgs.append({"role": "user", "content": "Das Zeitbudget ist erschoepft. Schreibe JETZT die Antwort aus dem bereits gelesenen Material, ohne weitere Werkzeuge."})
                    m = rufen(msgs)
                    inhalt = bereinigen(m.get("content") or "")
                    if inhalt:
                        texte.append(inhalt)
                except Exception:
                    pass
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
        if m.get("_abgeschnitten"):
            nutzung["abgeschnitten"] = 1
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
    if not text and not fehler:
        # Sporadisch leere Modellantwort (Gemma, 2x am 02.09.): EIN Zweitversuch,
        # bevor die ehrliche Fehlermeldung an den Menschen geht.
        try:
            msgs.append({"role": "user", "content": "Deine Antwort war leer. Schreibe die Antwort jetzt."})
            m = rufen(msgs)
            text = bereinigen(m.get("content") or "").strip()
        except Exception as e2:
            fehler = "Modell: %s" % str(e2)[:120]
    text = abschnitt_vermerken(text, bool(nutzung.get("abgeschnitten")))
    return {"text": text, "aufrufe": aufrufe, "dokumente": beruehrt,
            "runden": len(aufrufe), "ms": int((time.time() - begonnen) * 1000),
            "fehler": fehler, "nutzung": nutzung}


def mit_lebenszeichen(lauf, lebenszeichen, abstand=20.0):
    """`lauf()` ausfuehren und die Leitung dabei wachhalten.

    ⛔ Gemessen 23.09.: Nach dem Hochsetzen der Antwortlaenge auf 8192
      Token starb die Chat-Verbindung nach 92 Sekunden
      (NS_ERROR_NET_PARTIAL_TRANSFER im Browser, BrokenPipeError im
      Proxy). Ursache: `"stream": False` - der Proxy wartet die KOMPLETTE
      Antwort ab und schickt waehrenddessen nichts. Bei 1800 Token waren
      das 33 s, bei 8192 ueber zwei Minuten. Die Gegenstelle kappte die
      stille Leitung.

    ⭐ Warum kein echtes Streamen: Die Antwort wird NACH dem Erzeugen
      gegen die Dokumente geprueft. Wer den Rohtext durchreicht, sendet
      Ungeprueftes - genau das, was diese Anlage nicht tut.

    ⭐ Das Lebenszeichen geht vom AUFRUFENDEN Faden raus, nicht aus dem
      Arbeitsfaden: Zwei Faeden auf derselben Leitung koennten sich
      mitten in einem Stueck ins Wort fallen. Hier arbeitet der zweite
      Faden, und der erste schickt - die Reihenfolge bleibt heil.
    """
    ergebnis = {}

    def arbeiten():
        try:
            ergebnis["wert"] = lauf()
        except BaseException as e:      # noqa: BLE001 - kommt unten wieder hoch
            ergebnis["fehler"] = e

    faden = threading.Thread(target=arbeiten, daemon=True)
    faden.start()
    while True:
        faden.join(abstand)
        if not faden.is_alive():
            break
        try:
            lebenszeichen()
        except Exception:
            # Ist die Leitung schon zu, hilft Weitersenden nicht - die
            # Antwort selbst soll trotzdem fertig werden (sie landet im
            # Protokoll und im Gedaechtnis).
            pass
    if "fehler" in ergebnis:
        raise ergebnis["fehler"]
    return ergebnis.get("wert")
