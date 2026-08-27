#!/usr/bin/env python3
"""Macht aus der Suchmaschine einen Assistenten.

Ausgangslage: AnythingLLM sucht im Modus "query" mit dem ROHEN Fragetext
(nur die Slash-Befehl-Auswertung, keine Umschreibung des Verlaufs).
Der Gespraechsverlauf geht zwar ans Modell, aber erst NACHDEM gesucht
wurde. Jede Frage, die ihren Gegenstand nicht selbst benennt, findet
deshalb nichts.

Beispiel: "Kannst du mir eine Zusammenfassung machen?" fand nichts, weil
das Wort "Zusammenfassung" in keinem Dokument steht - die Suche fand nichts
Passendes und das Modell lehnte korrekt ab. Kein Fehler, sondern eine Grenze
des Modus. Genau solche Faelle reichert dieses Modul an.

Dieses Modul sitzt VOR der Weiterleitung an AnythingLLM und ordnet jede
Frage ein. Fuenf Faelle:

  bestand        "Welche Dokumente habt ihr?"    -> selbst beantworten
  folgefrage     "Fasse das zusammen"            -> Gegenstand ergaenzen
  zusammenfassung "Worum geht es in DVS 2213-1?" -> Volltext heranziehen
  vergleich      "Unterschied zwischen A und B?" -> beide Seiten suchen
  normal         alles andere                     -> unveraendert weiter

GRUNDREGEL: Im Zweifel nichts tun. Eine falsch angereicherte Frage sucht
am Thema vorbei und ist schlimmer als eine gar nicht angereicherte. Jede
Erkennung hier ist deshalb absichtlich streng - lieber ein Fall zu wenig
als einer zu viel.

Das Modul ist bewusst ohne Abhaengigkeit zum Proxy geschrieben, damit es
sich einzeln pruefen laesst, ohne den laufenden Dienst anzufassen:

    python3 assistent_test.py
"""
import json
import os
import re
import threading
import time

# Wie viele Gespraechsschritte je Unterhaltung behalten werden. Mehr
# braucht es nicht: Anreichern stuetzt sich auf die letzte inhaltliche
# Frage, nicht auf den ganzen Verlauf.
SCHRITTE = 8

# Nach dieser Zeit ohne Frage gilt eine Unterhaltung als beendet. Wer nach
# einer Stunde "und dazu?" schreibt, meint fast nie das Thema von vorhin.
VERGESSEN = 3600

# Laenger als das ist keine Folgefrage mehr, sondern eine eigene Frage.
KURZ = 90


# ---------------------------------------------------------------- Verlauf

# Wo das Faden-Gedaechtnis liegt. Im Container per Umgebungsvariable ins
# Daten-Volume - sonst ist es beim naechsten Neubau weg.
GEDAECHTNIS_DATEI = (os.environ.get("KI4KI_FADEN_GEDAECHTNIS")
                     or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     ".faden-gedaechtnis.json"))
# Mehr Faeden als das werden nicht aufgehoben - die aeltesten fallen weg.
HOECHSTENS_FAEDEN = 5000


class Verlauf:
    """Merkt sich je Unterhaltung, worum es gerade geht.

    Warum selbst merken und nicht AnythingLLM fragen: Der Proxy sieht
    ohnehin jede Frage und jede Antwort, und eine Abfrage an AnythingLLM
    waere ein zusaetzlicher Umweg mitten in der Antwortzeit. Ausserdem
    braucht es hier nur einen Bruchteil dessen, was dort gespeichert ist.

    ⭐ DAUERHAFT JE GESPRAECHSFADEN (25.08.): Ein Faden, der naechste Woche
      wieder geoeffnet wird, muss noch wissen, um welches Dokument es ging.
      Deshalb liegt das Gedaechtnis auf der Platte (Daten-Volume), ohne
      Verfallsdatum, und der Schluessel ist der Faden selbst - nicht die
      Sitzung, die sich bei jeder Anmeldung aendert. Nur Gespraeche OHNE
      Faden (Standard-Chat eines Bereichs, ueber die Sitzung erkannt)
      verfallen wie bisher nach einer Stunde.
    """

    def __init__(self, datei=None):
        self._gespraeche = {}
        self._sperre = threading.Lock()
        self._datei = GEDAECHTNIS_DATEI if datei is None else datei
        self._gemeckert = False
        self._laden()

    @staticmethod
    def kennung(pfad, kopfzeilen=None):
        """Was eine Unterhaltung von einer anderen unterscheidet.

        Mit Faden: "bereich|faden" - der Faden ist weltweit eindeutig und
        bleibt es ueber Anmeldungen hinweg. Ohne Faden: "bereich|-|sitzung",
        damit sich zwei Leute im selben Bereich nicht denselben Verlauf
        teilen - sonst bekaeme ein Nutzer den Gegenstand aus der letzten
        Frage eines anderen untergeschoben.
        """
        m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)(?:/thread/([^/]+))?",
                     pfad or "")
        bereich = m.group(1) if m else "?"
        faden = (m.group(2) if m else None) or ""
        if not faden and kopfzeilen:
            try:
                faden = (kopfzeilen.get("X-KI4KI-Faden") or "").strip()   # JSON-Weg: sessionId
            except Exception:
                faden = ""
        if faden:
            return "%s|%s" % (bereich, faden)
        sitzung = ""
        if kopfzeilen:
            roh = (kopfzeilen.get("Authorization")
                   or kopfzeilen.get("Cookie") or "")
            if roh:
                import hashlib
                sitzung = hashlib.sha1(roh.encode()).hexdigest()[:12]
        return "%s|-|%s" % (bereich, sitzung)

    @staticmethod
    def _dauerhaft(kennung):
        return len((kennung or "").split("|")) == 2

    def _hol(self, kennung):
        """Der Eintrag - oder None, wenn es ihn nicht gibt oder er (ohne
        Faden) verfallen ist."""
        eintrag = self._gespraeche.get(kennung)
        if not eintrag:
            return None
        if not self._dauerhaft(kennung) and \
                time.time() - eintrag.get("zuletzt", 0) > VERGESSEN:
            return None
        return eintrag

    def _neu(self, kennung):
        return self._gespraeche.setdefault(
            kennung, {"schritte": [], "zuletzt": 0})

    # ---- Platte ---------------------------------------------------------

    def _laden(self):
        try:
            with open(self._datei, encoding="utf-8") as fh:
                roh = json.load(fh) or {}
        except Exception:
            return
        if isinstance(roh, dict):
            for k, v in roh.items():
                if self._dauerhaft(k) and isinstance(v, dict) and \
                        isinstance(v.get("schritte"), list):
                    v.setdefault("zuletzt", 0)
                    self._gespraeche[k] = v

    def _sichern(self):
        """Nur die dauerhaften (Faden-)Eintraege - atomar. Mit gehaltener
        Sperre aufrufen."""
        if not self._datei:
            return
        try:
            dauer = {k: v for k, v in self._gespraeche.items()
                     if self._dauerhaft(k)}
            ordner = os.path.dirname(self._datei)
            if ordner:
                os.makedirs(ordner, exist_ok=True)
            tmp = self._datei + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dauer, fh, ensure_ascii=False)
            os.replace(tmp, self._datei)
        except Exception as e:
            if not self._gemeckert:
                self._gemeckert = True
                import sys
                print("[Gedaechtnis] nicht speicherbar (%s): %s"
                      % (self._datei, str(e)[:120]), file=sys.stderr,
                      flush=True)

    # ---- Schreiben ------------------------------------------------------

    def merken(self, kennung, frage, art, quellen=None, antwort=None):
        with self._sperre:
            eintrag = self._neu(kennung)
            eintrag["schritte"].append({
                "frage": frage,
                "art": art,
                "quellen": [q.get("title") or "" for q in (quellen or [])][:9],
                "antwort": (str(antwort)[:1800] if antwort else ""),
                "wann": time.time(),
            })
            eintrag["schritte"] = eintrag["schritte"][-SCHRITTE:]
            eintrag["zuletzt"] = time.time()
            self._aufraeumen()
            self._sichern()

    def wahl_merken(self, kennung, kandidaten):
        """Festhalten, welche Dokumente wir gerade zur Wahl gestellt haben.

        Ohne das ist die Rueckfrage eine Sackgasse: Fragt die Anlage
        "Dazu passen mehrere Dokumente. Welches meinst du?" und zaehlt
        fuenf auf, muss sie die Antwort ("DVS 2213-1_neu") auch verstehen -
        sonst laeuft die naechste Frage als gewoehnliche Suche ins Leere.
        """
        with self._sperre:
            eintrag = self._neu(kennung)
            eintrag["wahl"] = list(kandidaten or [])
            eintrag["zuletzt"] = time.time()
            self._aufraeumen()
            self._sichern()

    def wahl_vergessen(self, kennung):
        """Die Wahl ist getroffen - sie darf die naechste Frage nicht mehr
        an sich ziehen."""
        with self._sperre:
            eintrag = self._gespraeche.get(kennung)
            if eintrag and eintrag.pop("wahl", None) is not None:
                self._sichern()

    def antwort_merken(self, kennung, text):
        """Die letzte Antwort (gekuerzt) - fuer "exportiere das als CSV"."""
        if not text:
            return
        with self._sperre:
            eintrag = self._neu(kennung)
            eintrag["antwort"] = str(text)[-8000:]
            eintrag["zuletzt"] = time.time()
            self._sichern()

    def letzte_antwort(self, kennung):
        eintrag = self._hol(kennung)
        return (eintrag.get("antwort") or "") if eintrag else ""

    def notiz_setzen(self, kennung, name, wert):
        """Ein benannter Zustand je Faden (z.B. die offene Pruefungsfrage).
        wert=None loescht die Notiz."""
        with self._sperre:
            eintrag = self._neu(kennung)
            notizen = eintrag.setdefault("notizen", {})
            if wert is None:
                notizen.pop(name, None)
            else:
                notizen[name] = wert
            eintrag["zuletzt"] = time.time()
            self._sichern()

    def notiz(self, kennung, name):
        eintrag = self._hol(kennung)
        return (eintrag.get("notizen") or {}).get(name) if eintrag else None

    def dokument_merken(self, kennung, name):
        """Welches Dokument in diesem Faden gerade Thema ist.

        Gemessen 25.08.: "Dissertation von Fabian Becker zusammenfassen" ->
        "Schreib mir eine gesamte Zusammenfassung" -> "ein Diagramm aus der
        Arbeit": Die zweite und dritte Frage nennen das Dokument nicht mehr,
        meinen aber offensichtlich dasselbe. Ohne dieses Gedaechtnis fiel
        die Anlage auf Schnipsel aus dem ganzen Bestand zurueck und zeigte
        Diagramme aus einer fremden Arbeit.
        """
        if not name:
            return
        with self._sperre:
            eintrag = self._neu(kennung)
            eintrag["dokument"] = name
            eintrag["zuletzt"] = time.time()
            self._sichern()

    def _aufraeumen(self):
        """Verfallene Sitzungs-Gespraeche wegwerfen; von den dauerhaften
        Faeden hoechstens HOECHSTENS_FAEDEN behalten (die aeltesten gehen)."""
        grenze = time.time() - VERGESSEN
        for k in [k for k, v in self._gespraeche.items()
                  if not self._dauerhaft(k) and v.get("zuletzt", 0) < grenze]:
            self._gespraeche.pop(k, None)
        dauer = [k for k in self._gespraeche if self._dauerhaft(k)]
        if len(dauer) > HOECHSTENS_FAEDEN:
            dauer.sort(key=lambda k: self._gespraeche[k].get("zuletzt", 0))
            for k in dauer[:len(dauer) - HOECHSTENS_FAEDEN]:
                self._gespraeche.pop(k, None)

    # ---- Lesen ----------------------------------------------------------

    def offene_wahl(self, kennung):
        """Die Dokumente aus der letzten Rueckfrage - oder []."""
        eintrag = self._hol(kennung)
        return list(eintrag.get("wahl") or []) if eintrag else []

    def letzter_gegenstand(self, kennung):
        """Die letzte Frage, die einen eigenen Gegenstand hatte.

        Wichtig ist das "eigene": Bei drei Folgefragen hintereinander
        ("fasse zusammen" -> "kuerzer" -> "und die Quelle?") muss die
        Ergaenzung immer auf die letzte INHALTLICHE Frage zurueckgreifen,
        nicht auf die vorige Folgefrage. Sonst verduennt sich der
        Gegenstand mit jedem Schritt, bis nichts mehr da ist.
        """
        eintrag = self._hol(kennung)
        if not eintrag:
            return None
        for schritt in reversed(eintrag["schritte"]):
            if schritt["art"] in ("normal", "zusammenfassung", "vergleich"):
                return schritt["frage"]
        return None

    def letzte_bestand(self, kennung):
        """Die letzten Bestandsfragen in diesem Faden (neueste zuerst) -
        fuer Folgefrage-Verfeinerungen (Thema von vorher erben)."""
        eintrag = self._hol(kennung)
        if not eintrag:
            return []
        return [s["frage"] for s in reversed(eintrag["schritte"])
                if s["art"] == "bestand"][:4]

    def letztes_dokument(self, kennung):
        eintrag = self._hol(kennung)
        return eintrag.get("dokument") if eintrag else None

    def letzte_art(self, kennung):
        """Die Art des UNMITTELBAR vorigen Schritts - oder None."""
        eintrag = self._hol(kennung)
        if not eintrag or not eintrag["schritte"]:
            return None
        return eintrag["schritte"][-1]["art"]

    def verlauf_kurz(self, kennung, hoechstens=6):
        """[(frage, art, antwortanfang)] der letzten Schritte - fuer das
        Absichts-Modell. Die Antworten selbst sind nur als letzte gemerkt;
        aeltere Schritte tragen nur Frage und Art."""
        eintrag = self._hol(kennung)
        if not eintrag:
            return []
        schritte = eintrag["schritte"][-hoechstens:]
        aus = []
        for i, s in enumerate(schritte):
            ant = s.get("antwort") or (eintrag.get("antwort", "") if i == len(schritte) - 1 else "")
            aus.append((s.get("frage", ""), s.get("art", ""), (ant or "")[:1800]))
        return aus

    def letzte_frage(self, kennung):
        """(Frage, Art) des letzten inhaltlichen Schritts - fuer die
        Reparatur nach einer Beschwerde. None, wenn es keinen gibt."""
        eintrag = self._hol(kennung)
        if not eintrag:
            return None
        for s in reversed(eintrag["schritte"]):
            if s["art"] not in ("beschwerde", "bestand"):
                return (s["frage"], s["art"])
        return None

    def letzte_quellen(self, kennung):
        eintrag = self._hol(kennung)
        if not eintrag:
            return []
        for schritt in reversed(eintrag["schritte"]):
            if schritt["quellen"]:
                return schritt["quellen"]
        return []


# ------------------------------------------------------- Fragen einordnen

# Woerter, die auf etwas Vorheriges zeigen, ohne es zu benennen.
_RUECKVERWEIS = re.compile(
    r"\b(das|dazu|davon|dessen|deren|dabei|dafuer|dafür|darueber|darüber|"
    r"daraus|hierzu|dies(?:e|es|em|en)?|es|sie|ihn|ihm|jene[nrs]?)\b",
    re.I)

# Formulierungen, die fast immer eine Folgefrage einleiten.
_FOLGE_START = re.compile(
    r"^\s*(und|aber|okay|ok|ja|nein|gut|ach|also|nochmal|noch\s+mal)\b", re.I)

# Wuensche, die sich auf die vorige Antwort beziehen, ohne Gegenstand.
_BEZUG_AUF_ANTWORT = re.compile(
    r"\b(fass(?:e|t)?\s+(?:mir\s+)?(?:das|es|die[sn]e?s?)?\s*zusammen|"
    r"zusammenfassung|kuerzer|kürzer|ausfuehrlicher|ausführlicher|"
    r"genauer|einfacher|erklaer|erklär|nochmal|anders\s+formuliert|"
    r"in\s+stichpunkten|als\s+liste|uebersetze|übersetze)\b", re.I)

# Fragen nach dem Bestand selbst - nicht nach seinem Inhalt.
# Die Unterscheidung ist heikel: "Welche Dokumente nennen Pruefverfahren?"
# ist eine INHALTS-Frage, keine Bestandsfrage. Deshalb muss ein Wort aus
# _BESITZ dabeistehen ("habt ihr", "gibt es", "liegen vor") und die Frage
# darf keinen weiteren Fachgegenstand tragen.
_BESTAND_OBJEKT = re.compile(
    r"\b(dokument(?:e|en)?|unterlagen|dateien|quellen|literatur|"
    r"arbeiten|normen|richtlinien|lerneinheiten|bestand|best(?:ä|ae)nde|bestandsliste)\b", re.I)
# "Inhalte" gehoert BEWUSST nicht hierher: Wer nach dem INHALT fragt
# ("Stichwortliste der wesentlichen Inhalte"), stellt keine Bestandsfrage.
_BESITZ = re.compile(
    r"\b(habt\s+ihr|hast\s+du|haben\s+wir|gibt\s+es|liegen\s+vor|"
    r"sind\s+(?:denn\s+)?(?:alles\s+)?(?:hier|drin|vorhanden|hinterlegt)|"
    r"verfuegbar|verfügbar|vorhanden|kennst\s+du|kennt\s+ihr|"
    r"enthaelt|enthält|umfasst|steht\s+(?:hier|dir)\s+zur\s+verfuegung)\b",
    re.I)
_BESTAND_DIREKT = re.compile(
    r"^\s*(was|welche|wie\s+viele?|wieviel)\b.{0,80}?\b("
    r"dokument(?:e|en)?|unterlagen|dateien|quellen|literatur|bestand)\b", re.I)

# Bestandsfragen, die gar kein Objektwort nennen: "Was steht dir alles zur
# Verfuegung?", "Was hast du denn so?", "Was ist hier alles drin?". Ohne
# diese Zeile fallen sie durch, weil _BESTAND_OBJEKT nichts findet - und
# genau so fragen Leute, die die Anlage zum ersten Mal sehen.
# ⭐ Ausloeser-Woerter, die eine Frage zur BESTANDSFRAGE machen -
#   unabhaengig davon, WORUEBER gefragt wird. Die Art ("Dissertationen")
#   ist nur der Filter, nie der Ausloeser: "Hol mir die Dissertation von
#   Max Mustermann" ist eine Inhaltsfrage, keine Bestandsliste.
_BESTAND_SIGNAL = re.compile(
    r"\bbestand(?:s(?:liste|uebersicht|übersicht|aufnahme))?\b|"
    r"was\s+haben\s+wir\s+(?:alles\s+|so\s+)?(?:an|f[üu]r|im|in)\b|"
    r"was\s+habt\s+ihr\s+(?:alles\s+|so\s+)?(?:an|f[üu]r|im|in)?\b|"
    r"(?:eine\s+)?(?:liste|uebersicht|übersicht|aufstellung)\s+"
    r"(?:aller|alle|der|des|von|zu|ueber|über)\b|"
    r"wie\s+viele?\b.{0,50}?\b(?:gibt\s+es|habt\s+ihr|haben\s+wir|"
    r"liegen\s+(?:vor|hier)|sind\s+(?:es|vorhanden|hinterlegt))|"
    r"welche\b.{0,50}?\b(?:habt\s+ihr|haben\s+wir|gibt\s+es|"
    r"liegen\s+(?:vor|hier)|sind\s+(?:vorhanden|hinterlegt|da))",
    re.I)

_BESTAND_THEMA = re.compile(
    r"^\s*(?:was|welche)\s+(?:habt\s+ihr|gibt\s*'?s|gibt\s+es|"
    r"haben\s+wir|liegt\s+(?:vor|hier)|ist\s+(?:vorhanden|da|hinterlegt))\b",
    re.I)

_BESTAND_OHNE_OBJEKT = re.compile(
    r"^\s*(was|worueber|worüber)\b.{0,60}?\b("
    r"zur\s+verfuegung|zur\s+verfügung|"
    r"(?:hast|kennst)\s+du\s+(?:denn\s+)?(?:so\s+|alles\s+)|"
    r"(?:ist|steht)\s+(?:denn\s+)?(?:hier|da|drin)\s+alles|"
    r"alles\s+(?:drin|da|vorhanden|hinterlegt|gespeichert)|"
    r"weisst\s+du|weißt\s+du)", re.I)

# "Worum geht es in X" / "Fasse X zusammen" - MIT genanntem Gegenstand.
#
# Grosszuegig, und das ist Absicht: Der Volltext-Weg wird ohnehin nur
# genommen, wenn sich ein Dokument zuordnen laesst (_zusammenfassung() im
# Proxy prueft das). Wer "Was ist das Fazit?" ohne Gegenstand fragt,
# landet weiterhin auf dem normalen Weg. Die Zuordnung haelt dagegen -
# die Erkennung darf deshalb weit sein.
#
# Gemessen: Von 15 alltaeglichen Fragen trafen nur 5 diesen Weg.
# Fazit, Ergebnis, Erkenntnisse, Schluesse, "erklaer mir" fehlten alle -
# also ausgerechnet die Formulierungen, mit denen man nach dem Kern einer
# Arbeit fragt. Daher der Eindruck duenner Antworten: Sie kamen aus neun
# Schnipseln, wo der Volltext gebraucht wurde.
_ZUSAMMENFASSUNG = re.compile(
    r"(worum\s+geht\s+(?:es|s)\s+(?:in|bei)|"
    r"was\s+steht\s+in|inhalt\s+von|"
    r"fass(?:e|t)?\s+(?:mir\s+)?(?!.*\b(?:das|es|dies)\b\s*zusammen)|"
    r"zusammenfassung\s+(?:von|zu|des|der)|"
    r"ueberblick\s+ueber|überblick\s+über|"
    r"kurzfassung\s+(?:von|zu)|"
    # Nach dem Kern einer Arbeit gefragt - dasselbe Beduerfnis, andere Worte:
    r"\bfazit\b|"
    r"\bergebnis(?:se)?\s+(?:von|der|des|aus)|"
    r"\b(?:wichtigste[nrs]?\s+)?erkenntnis(?:se)?\b|"
    r"\bschluss?folgerung(?:en)?\b|"
    r"welche\s+schl(?:ue|ü)sse\s+(?:zieht|werden)|"
    r"\bkernaussage(?:n)?\b|"
    r"\bhauptaussage(?:n)?\b|"
    # Bis zu zwei Fuellwoerter ueberspringen, bevor auf warum/wieso/weshalb
    # geprueft wird - "erklaer mir BITTE warum" ist dasselbe wie "erklaer
    # mir warum": eine Fachfrage, keine Zusammenfassung.
    r"erkl(?:ae|ä)r(?:e|st)?\s+(?:du\s+)?(?:mir\s+)?"
    r"(?!(?:\w+\s+){0,2}(?:warum|wieso|weshalb|wodurch|weswegen)\b)|"
    r"worum\s+handelt\s+es\s+sich|"
    r"was\s+ist\s+das\s+(?:thema|anliegen|ziel)\s+(?:von|der|des))", re.I)

# ⭐ DOKUMENT-AUFTRAG: Aus einem GANZEN Dokument etwas Neues bauen -
#   Praesentation, Gliederung, Handout, Stichpunkte, Vortrag, Lernkarten.
#   Dasselbe Beduerfnis wie die Zusammenfassung (das ganze Dokument lesen,
#   nicht neun Schnipsel), nur mit anderem Ziel. Laeuft ueber denselben
#   Volltext-Weg; die Frage selbst wird zur Aufgabe fuers Modell.
_DOK_AUFTRAG = re.compile(
    r"\b(?:pr(?:ae|ä)sentation\w*|powerpoint|ppt|pptx|folien(?:satz)?|"
    r"vortrag\w*|gliederung|handout|stichpunkt\w*|stichworte|"
    r"lernkarte\w*|karteikarte\w*|skript|expos(?:e|é)|abstract|"
    r"kurzfassung|management\s*summary|zusammenfassung|"
    r"aufbereit\w*|bereite\w*\s+(?:\w+\s+){0,4}?(?:vor|auf))\b", re.I)


def ist_dokument_auftrag(frage):
    """Will jemand aus einem Dokument etwas ERARBEITET haben (Praesentation,
    Gliederung, Handout ...)? Dann gilt der Volltext-Weg mit der Frage als
    Aufgabe. Eine Sachfrage, in der 'Vortrag' nur als Thema vorkommt
    ("Was sagt der Vortrag zu X?"), zaehlt nicht - es braucht ein
    Erstell-Verb oder eine Form-Angabe."""
    f = frage or ""
    if not _DOK_AUFTRAG.search(f):
        return False
    return bool(re.search(
        r"\b(?:erstell\w*|mach\w*|bau\w*|bereite\w*|schreib\w*|entwirf\w*|"
        r"entwerf\w*|formulier\w*|generier\w*|leite\w*\s+ab|fass\w*|"
        r"zusammenfass\w*|aufbereit\w*|gib\s+mir|brauche|will|m(?:oe|ö)chte|"
        r"kannst\s+du|k(?:oe|ö)nntest\s+du|f(?:ue|ü)r\s+(?:eine|einen|ein|meine|"
        r"meinen|mein)\s+(?:pr(?:ae|ä)sentation|vortrag|powerpoint|handout|"
        r"folien))\b", f, re.I))


# Vergleichsfragen. Das Trennwort wird gleich mitgenommen, damit sich die
# beiden Seiten hinterher zerlegen lassen.
_VERGLEICH = re.compile(
    r"(unterschied(?:e)?\s+zwischen|"
    r"vergleich(?:e|en)?\s+(?:von|zwischen)?|"
    r"\bunterscheide[nt]?\s+sich|"
    r"was\s+ist\s+besser|welche[rs]?\s+(?:ist|sind)\s+(?:besser|geeigneter)|"
    r"\bgegenueber\b|\bgegenüber\b|\bversus\b|\bvs\.?\b)", re.I)


# --- Auffangnetz: kleines Modell fuer die Fall-Einordnung -------------------
# Schalter. Standardmaessig AUS: ohne KI4KI_AUFFANGNETZ=1 verhaelt sich
# einordnen() exakt wie vorher - kein Modellaufruf, kein Risiko. Der Wert
# wird beim Start gelesen; Umstellen braucht einen Proxy-Neustart.
NETZ_AN = os.environ.get("KI4KI_AUFFANGNETZ", "") == "1"
NETZ_MODELL = os.environ.get("KI4KI_NETZ_MODELL") or "gemma4:e2b"
NETZ_URL = os.environ.get("KI4KI_NETZ_URL") or "http://nothink-proxy:11435/api/chat"
NETZ_TIMEOUT = float(os.environ.get("KI4KI_NETZ_TIMEOUT") or "8")

# In dieser Reihenfolge geprueft; nur diese Faelle darf das Netz vergeben.
# "folgefrage" braucht den Gespraechsverlauf und bleibt bei den Regeln.
_NETZ_ORDNUNG = ["bestand", "negativfrage", "vergleich", "zusammenfassung", "verfahren"]

# Merkt sich je Anfrage-Thread, ob die LETZTE Einordnung ueber das kleine
# Modell lief (Fall, Modell, Sekunden) - fuer den sichtbaren Hinweis.
_NETZ_INFO = threading.local()


def netz_info():
    return getattr(_NETZ_INFO, "wert", None)

_NETZ_ANWEISUNG = """Ordne die folgende Nutzerfrage an eine Wissensdatenbank in GENAU EINE Kategorie ein. Antworte NUR mit dem Kategorie-Wort, sonst nichts.
- bestand: fragt, WELCHE oder WIE VIELE Dokumente/Arbeiten VORHANDEN sind - auch umschrieben: was habt ihr, was liegt vor, gib einen Ueberblick was ihr zum Thema habt, nenne alles zu, Liste, Bestand.
- negativfrage: fragt nach dem, was NICHT zutrifft (keine, nicht, ausser).
- vergleich: vergleicht zwei genannte Dinge.
- zusammenfassung: will den INHALT eines bestimmten Dokuments oder Themas zusammengefasst bekommen (fasse X zusammen, worum geht es in Y, gib den Inhalt wieder).
- verfahren: fragt, WIE etwas gemacht oder eingestellt wird.
- normal: eine gewoehnliche inhaltliche Sachfrage."""


def _netz_frageart(frage):
    """Fragt das kleine Modell nach der Kategorie. Gibt einen Fall aus
    _NETZ_ORDNUNG zurueck oder None. Wirft NIE - jeder Fehler (Modell weg,
    Zeitgrenze, unbekannte Antwort) fuehrt zu None, dann bleibt es normal."""
    try:
        from urllib.request import Request, urlopen
        leib = json.dumps({
            "model": NETZ_MODELL,
            "messages": [{"role": "user",
                          "content": _NETZ_ANWEISUNG + chr(10) + "Frage: " + frage + chr(10) + "Kategorie:"}],
            "think": False,
            "stream": False,
            "options": {"temperature": 0},
            "keep_alive": "24h",
        }).encode("utf-8")
        a = Request(NETZ_URL, data=leib,
                    headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(a, timeout=NETZ_TIMEOUT) as r:
            antwort = json.loads(r.read())
        inhalt = ((antwort.get("message") or {}).get("content") or "").lower()
        for f in _NETZ_ORDNUNG:
            if f in inhalt:
                return f
        return None
    except Exception:
        return None


_NETZ_BILD_ANWEISUNG = (
    "Will der Nutzer mit der folgenden Eingabe ein BILD, DIAGRAMM, eine "
    "GRAFIK oder ABBILDUNG angezeigt bekommen (auch bei Tippfehlern oder "
    "schlechtem Deutsch)? Antworte NUR mit JA oder NEIN. NEIN bei Sachfragen, "
    "in denen ein Diagramm nur als Thema vorkommt (z.B. 'Welche Typen zeigt "
    "das Diagramm?').")


def netz_bildwunsch(frage):
    """Kleines Modell als Ja/Nein-Instanz fuer Bildwuensche mit Tippfehlern
    oder fremder Wortwahl. None = kein Netz / kein Ergebnis. Wirft nie."""
    if not NETZ_AN or not (frage or "").strip():
        return None
    try:
        from urllib.request import Request, urlopen
        leib = json.dumps({
            "model": NETZ_MODELL,
            "messages": [{"role": "user",
                          "content": _NETZ_BILD_ANWEISUNG + chr(10) + "Eingabe: "
                                     + frage + chr(10) + "Antwort:"}],
            "think": False, "stream": False, "options": {"temperature": 0},
        }).encode("utf-8")
        a = Request(NETZ_URL, data=leib,
                    headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(a, timeout=NETZ_TIMEOUT) as r:
            inhalt = (((json.loads(r.read()).get("message") or {})
                       .get("content") or "")).strip().upper()
        if inhalt.startswith("JA"):
            return True
        if inhalt.startswith("NEIN"):
            return False
        return None
    except Exception:
        return None


def _netz_protokoll(frage, fall):
    """Haelt fest, dass das Netz gegriffen hat - fuer Nachvollziehbarkeit
    (auf welchem Weg entstand die Antwort) und fuer die Auswertung im Test."""
    try:
        print("AUFFANGNETZ: " + (frage or "")[:80] + " -> " + fall, flush=True)
    except Exception:
        pass


def einordnen(frage, hat_verlauf=False):
    """Welcher der sieben Faelle liegt vor?

    Die Reihenfolge ist Absicht: Bestandsfragen zuerst, weil sie sich
    eindeutig erkennen lassen; Folgefragen zuletzt, weil ihre Erkennung
    die unschaerfste ist und nur greifen soll, wenn nichts Besseres passt.
    """
    text = (frage or "").strip()
    try:
        _NETZ_INFO.wert = None
    except Exception:
        pass
    if not text:
        return "normal"

    if _ist_bestandsfrage(text):
        return "bestand"

    # Negativfragen aus dem Pruefungskatalog. Sie muessen VOR allem
    # anderen greifen, weil ihre Suche umgedreht werden muss: Gesucht wird
    # nach dem, was zutrifft, geantwortet wird auf das, was nicht
    # zutrifft. Gescheitert war "Was ist keine Aufgabe des
    # Extruders?" vollstaendig - die Anlage suchte nach dem Fragetext und
    # fand nichts, weil "keine Aufgabe" in keinem Dokument steht.
    if ist_negativfrage(text):
        return "negativfrage"

    if _VERGLEICH.search(text):
        if vergleichsteile(text):
            return "vergleich"
        # Vergleichsform ohne genannte Seiten - "Was ist besser?" meint
        # etwas aus dem Gespraech davor. Ohne Verlauf bleibt es eine
        # gewoehnliche Frage, dann lehnt die Anlage ehrlich ab.
        if hat_verlauf:
            return "folgefrage"

    if _ZUSAMMENFASSUNG.search(text) or ist_dokument_auftrag(text):
        return "zusammenfassung"

    if hat_verlauf and _ist_folgefrage(text):
        return "folgefrage"

    # Verfahrensfragen zuletzt: Sie gehen den gewoehnlichen Weg, nur mit
    # verdichteter Suchanfrage. An einer Verfahrensfrage nach der
    # Anspringtemperatur belegt - dieselbe Information, einmal gefunden und
    # einmal nicht, nur wegen der Formulierung.
    if ist_verfahrensfrage(text) and such_verdichten(text):
        return "verfahren"

    # AUFFANGNETZ (KI4KI_AUFFANGNETZ=1): Die Regeln haben nichts erkannt.
    # Bevor die Frage als "normal" durchgeht, fragt ein kleines Modell nach
    # der Bedeutung - faengt umformulierte Faelle ab, die die Wortliste
    # verpasst. Faellt es aus oder ist unsicher, bleibt es "normal".
    if NETZ_AN:
        import time as _t
        _start = _t.time()
        fall = _netz_frageart(text)
        _dt = round(_t.time() - _start, 1)
        if fall:
            _netz_protokoll(text, fall)
            try:
                _NETZ_INFO.wert = {"fall": fall,
                                   "modell": NETZ_MODELL,
                                   "sekunden": _dt}
            except Exception:
                pass
            return fall
    return "normal"



def _bestand_signal():
    """Das Ausloeser-Muster - aus wortlisten.txt, mit Rueckfall.

    ⚠ Wird bei JEDER Frage geholt. wortlisten.laden() sieht dabei nur auf
      den Zeitstempel der Datei; hat sie sich nicht geaendert, kostet es
      nichts. Dafuer wirkt eine Aenderung SOFORT - ohne Neustart, ohne
      zwei Minuten Ausfall. Das war der ganze Punkt der Uebung.
    """
    try:
        import wortlisten
        m = wortlisten.ausloeser_muster()
        if m:
            return m
    except Exception:
        pass
    return _BESTAND_SIGNAL


def _ist_bestandsfrage(text):
    # ⭐⭐ Ein ZUSAMMENFASSUNGS-Auftrag ist NIE eine Bestandsfrage - auch nicht
    #   mit genannter Art. Gemessen: "Fasse mir die Dissertation von Malte
    #   zusammen" lieferte eine Bestandstabelle statt der Zusammenfassung,
    #   weil "Dissertation" (Art) die Fasse-Ausnahme unten aushebelte. Wer
    #   "fasse ... zusammen" oder "worum geht es" sagt, will Inhalt.
    if re.search(r"\bfass(?:e|t)?\b.*\bzusammen\b|\bzusammenfass\w*|"
                 r"\bzusammenfassung\b|\bworum\s+geht", text or "", re.I):
        return False
    if ist_dokument_auftrag(text):
        return False
    # ⭐ Ein klarer ERZEUGE/EXTRAHIERE/FASSE-Auftrag OHNE genannte Dokument-Art
    #   ist eine Inhalts-Aufgabe (mach etwas MIT Inhalt), keine Bestandsfrage.
    #   Mit Art ("erstelle eine Liste aller Dissertationen") bleibt es Bestand -
    #   das faengt die Art-Pruefung weiter unten ab.
    try:
        import bestand as _b
        _hat_art = bool(_b.gefragte_art(text)[1])
    except Exception:
        _hat_art = False
    if not _hat_art and re.search(
            r"\b(erzeug\w*|erstell\w*|schreib\w*|formulier\w*|extrahier\w*|"
            r"generier\w*|zusammenfass\w*|fass(?:e|t)?)\b", text, re.I):
        return False
    # ⭐ Ausloeser + Art: "Welche Dissertationen haben wir im Bestand?"
    #   Ohne Ausloeser bleibt es eine Inhaltsfrage, auch wenn eine Art
    #   vorkommt - genau das ist die Bedingung.
    if _bestand_signal().search(text):
        try:
            import bestand
            if bestand.gefragte_art(text)[1]:
                return True
        except Exception:
            pass
        if _BESTAND_OBJEKT.search(text):
            return True
        # ⭐ "Was habt ihr zum Thema X?" - Ausloeser + Thema, aber
        #   KEIN inhaltszielendes Verb -> Bestandsliste zu X (so wird es erwartet).
        if _stichwort_aus(text) and not re.search(
                r"\b(nennen|nennt|beschreiben|beschreibt|erwaehnen|erwähnen|"
                r"behandeln|behandelt|sagen|sagt|empfehlen|empfiehlt|fordern|"
                r"fordert|gefunden|steht|erklaeren|erklären|funktioniert|"
                r"bedeutet)\b", text, re.I):
            return True

    # ⭐ "Was habt ihr / was gibt es zu(m Thema) X?" - klare Frage
    #   danach, was zu einem Thema VORLIEGT (Bestandsliste, nicht Inhalt);
    #   ohne inhaltszielendes Verb.
    if _BESTAND_THEMA.search(text) and _stichwort_aus(text) and not re.search(
            r"\b(nennen|nennt|beschreiben|beschreibt|erwaehnen|erwähnen|"
            r"behandeln|behandelt|sagen|sagt|empfehlen|empfiehlt|fordern|"
            r"fordert|gefunden|erklaeren|erklären|funktioniert|bedeutet)\b",
            text, re.I):
        return True
    if _BESTAND_OHNE_OBJEKT.search(text):
        return True
    if not _BESTAND_OBJEKT.search(text):
        return False
    # "Welche Dokumente nennen Pruefverfahren?" darf NICHT hier landen -
    # das ist eine Inhaltsfrage. Verraeterisch ist ein Verb, das auf den
    # Inhalt zielt.
    if re.search(r"\b(nennen|nennt|beschreiben|beschreibt|erwaehnen|"
                 r"erwähnen|behandeln|behandelt|sagen|sagt|empfehlen|"
                 r"empfiehlt|fordern|fordert)\b", text, re.I):
        return False
    return bool(_BESITZ.search(text) or _BESTAND_DIREKT.search(text))


def _ist_folgefrage(text):
    """Streng: kurz UND ohne eigenen Gegenstand.

    Die Laengengrenze allein reicht nicht - "Was ist Pultrusion?" ist kurz
    und trotzdem vollstaendig. Umgekehrt reicht ein Rueckverweis allein
    auch nicht: "Welche Normen gelten dafuer bei Klebeverbindungen?" traegt
    seinen Gegenstand mit. Deshalb beides zusammen.
    """
    if len(text) > KURZ:
        return False
    if _BEZUG_AUF_ANTWORT.search(text):
        return True
    if not (_RUECKVERWEIS.search(text) or _FOLGE_START.match(text)):
        return False
    # Traegt die Frage einen eigenen Gegenstand? Ein grosser Anteil
    # Grosschreibung deutet auf Fachbegriffe (Deutsch schreibt Substantive
    # gross). Bei zwei oder mehr eigenstaendigen Substantiven gehen wir von
    # einer vollstaendigen Frage aus.
    woerter = re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{3,}", text)
    unspezifisch = {"Dokument", "Dokumente", "Unterlagen", "Quelle",
                    "Quellen", "Antwort", "Frage", "Thema", "Beispiel",
                    "Stelle", "Seite", "Zusammenfassung", "Kannst", "Kann",
                    "Was", "Wie", "Welche", "Warum", "Woher", "Gibt"}
    eigene = [w for w in woerter if w not in unspezifisch]
    return len(eigene) < 2


def vergleichsteile(text):
    """Die beiden Seiten eines Vergleichs herausloesen.

    Nur wenn sich sauber zwei Seiten ergeben, wird der Fall als Vergleich
    behandelt. "Was ist besser?" ohne genannte Seiten ist keiner.
    """
    m = re.search(
        r"(?:unterschied(?:e)?\s+zwischen|vergleich(?:e|en)?\s+(?:von|zwischen))"
        r"\s+(.{2,70}?)\s+(?:und|oder|gegenueber|gegenüber|vs\.?|versus)\s+(.{2,70}?)"
        r"\s*[\?\.,;]?\s*$", text, re.I)
    if m:
        return _saubern(m.group(1)), _saubern(m.group(2))
    m = re.search(r"^(.{2,70}?)\s+(?:gegenueber|gegenüber|versus|vs\.?)\s+(.{2,70}?)"
                  r"\s*[\?\.,;]?\s*$", text, re.I)
    if m:
        return _saubern(m.group(1)), _saubern(m.group(2))
    m = re.search(r"vergleich(?:e|en|t)?\s+(?:mir\s+)?(?:bitte\s+)?(?:die\s+|den\s+|das\s+)?"
                  r"(.{2,70}?)\s+(?:und|mit)\s+(.{2,70}?)\s*[\?\.,;]?\s*$", text, re.I)
    if m:
        return _saubern(m.group(1)), _saubern(m.group(2))
    return None


def _saubern(teil):
    teil = re.sub(r"^\s*(dem|der|des|den|das|die|einem|einer|eines|von)\s+",
                  "", teil.strip(), flags=re.I)
    return teil.strip(" ?.,;:")


# ----------------------------------------------------------- Anreicherung

# Wortgeruest, das bei der Suche nur stoert. Es traegt keine Fachbedeutung,
# zieht die Suche aber in Richtung Methodik-Fliesstext.
_GERUEST = re.compile(
    r"\b(wie|was|welche[rsnm]?|warum|wieso|weshalb|wann|wo|wer|womit|wodurch|"
    r"vergleicht?|vergleiche[nt]?|verhaelt|verhält|unterscheide[nt]?|"
    r"unterschied(?:e)?|kannst|kann|koennen|können|du|mir|man|sich|ist|sind|"
    r"wird|werden|hat|haben|denn|eigentlich|bitte|mal|zwischen|"
    r"erklaer(?:e|st)?|erklär(?:e|st)?|nenne?|sage?|zeige?|gib|"
    r"der|die|das|dem|den|des|ein|eine|einer|einem|eines|"
    r"und|oder|mit|von|vom|zum|zur|bei|fuer|für|auf|in|im|an|als|"
    r"bezug|hinsicht|hinsichtlich|bezueglich|bezüglich)\b", re.I)


def such_verdichten(frage):
    """Das Fragegeruest abwerfen und die Fachbegriffe uebriglassen.

    Aus "wie vergleicht man die Haertungstemperatur bei der Warmhaertung
    mit der Anspringtemperatur?" wird "Haertungstemperatur Warmhaertung
    Anspringtemperatur".

    Rueckgabe: der verdichtete Text - oder None, wenn zu wenig uebrig
    bleibt. Lieber die Originalfrage als eine Suche nach zwei Wortresten.
    """
    if not frage:
        return None
    ohne = _GERUEST.sub(" ", frage)
    ohne = re.sub(r"[?!.,;:()\[\]\"'„“]", " ", ohne)
    woerter = [w for w in ohne.split() if len(w) >= 4]
    # Reihenfolge erhalten, Doppelte entfernen
    gesehen, kern = set(), []
    for w in woerter:
        if w.lower() not in gesehen:
            gesehen.add(w.lower())
            kern.append(w)
    if len(kern) < 2:
        return None
    verdichtet = " ".join(kern)
    # Wenn kaum etwas wegfaellt, bringt das Verdichten nichts.
    if len(verdichtet) > 0.8 * len(frage):
        return None
    return verdichtet


def ist_verfahrensfrage(frage):
    """Fragt sie nach einem Verhaeltnis statt nach einem Fakt?

    Diese Formulierungen zielen auf Methodik ("wie vergleicht man",
    "wie verhaelt sich X zu Y") und finden dadurch Fliesstext statt der
    Tabelle, in der die Antwort steht.
    """
    t = (frage or "").lower()
    return bool(re.search(
        r"(wie\s+(?:vergleicht|verhaelt|verhält|unterscheide[nt]|"
        r"berechnet|ermittelt|bestimmt|misst|prueft|prüft)\s+man|"
        r"wie\s+(?:verhaelt|verhält)\s+sich|"
        r"in\s+welchem\s+verhaeltnis|in\s+welchem\s+verhältnis|"
        r"wie\s+haengt|wie\s+hängt|"
        r"welchen\s+(?:einfluss|zusammenhang)|"
        r"wie\s+wirkt\s+sich)", t))


def anreichern(frage, gegenstand):
    """Aus "Fasse das zusammen" wird eine Frage, die etwas findet.

    Angezeigt bekommt der Nutzer weiterhin seine eigene Frage - nur die
    SUCHE bekommt den ergaenzten Text. Deshalb darf hier ruhig etwas
    stehen, das sich sperrig liest.
    """
    if not gegenstand:
        return frage
    gegenstand = gegenstand.strip().rstrip("?.! ")
    # Fragewoerter aus dem Gegenstand entfernen - gesucht wird nach dem
    # Thema, nicht nach der Frageform.
    kern = re.sub(r"^\s*(was|wie|welche[rsnm]?|warum|wieso|weshalb|wann|wo|"
                  r"wer|womit|wodurch|kannst\s+du|kannst\s+du\s+mir|"
                  r"koennen\s+sie|können\s+sie|gib\s+mir|nenne?\s+mir|"
                  r"erklaer(?:e|st)?\s+mir|erklär(?:e|st)?\s+mir)\b\s*",
                  "", gegenstand, flags=re.I).strip()
    kern = re.sub(r"^\s*(ist|sind|gibt\s+es|bedeutet|heisst|heißt)\b\s*",
                  "", kern, flags=re.I).strip()
    if not kern:
        kern = gegenstand
    return "%s (Zusammenhang: %s)" % (frage.strip(), kern)


# ------------------------------------------------------ Bestandsauskunft

def bestandsauskunft(frage, titel, bereich=None, vorher=None, zusatz=None):
    """Auskunft ueber den eigenen Bestand - ohne Umweg ueber das Modell.

    Das ist keine KI-Aufgabe, sondern eine Abfrage. Fuer jeden neuen
    Nutzer ist es aber die allererste Frage, und heute kann die Anlage sie
    nicht beantworten: Sie kennt nur den Inhalt einzelner Textstellen,
    nicht ihren eigenen Bestand.

    Rueckgabe: fertiger Antworttext (Markdown) oder None, wenn sich nichts
    Sinnvolles sagen laesst.
    """
    if not titel:
        return None
    sauber = sorted({_titel_saubern(t) for t in titel if t})
    if not sauber:
        return None

    # ⭐ Folgefrage-Verfeinerung + Art/Thema kombinieren:
    #   "Nur Dissertationen" nach "... ueber Spritzgiessen" meint
    #   Dissertationen ZUM Thema Spritzgiessen. Fehlende Art/Thema aus der
    #   vorigen Bestandsfrage uebernehmen und BEIDES kombinieren, statt dass
    #   die Art allein die ganze Liste zurueckgibt.
    try:
        import bestand as _b
        _art = _b.gefragte_art(frage)[0]
        _stich = _stichwort_aus(frage)
        if vorher:
            for _vf in ([vorher] if isinstance(vorher, str) else vorher):
                if not _art:
                    _art = _b.gefragte_art(_vf)[0]
                if not _stich:
                    _stich = _stichwort_aus(_vf)
                if _art and _stich:
                    break
        if _art and _stich:
            _kombi = _treffer_im_katalog(_stich, _b.nach_art(sauber, _art),
                                         bereich, gattung=_b.ARTEN[_art][1])
            if _kombi:
                return _kombi
            return ("Ich finde %s keine **%s** zum Thema **%s**."
                    % ("in diesem Arbeitsbereich" if bereich else "im Bestand",
                       _b.ARTEN[_art][1], _stich))
    except Exception:
        pass

    # ⭐ Fragt jemand nach einer ART? Dann die Liste danach filtern und mit
    #   Titeln beantworten - aus dem Verzeichnis, nicht aus Textstellen.
    #   z.B. auf die Bitte "nenne mir alle Namen und deren Titel auf".
    antwort = _liste_nach_art(frage, sauber, bereich)
    if antwort:
        return antwort

    # Sucht die Frage nach einem Stichwort? Dann nur passende Titel zeigen.
    stichwort = _stichwort_aus(frage)
    if stichwort:
        # ⭐ Erst im Katalog suchen - Titel UND Schlagworte, deutsch wie
        #   englisch. Vorher wurden nur die DATEINAMEN durchsucht, und bei
        #   Namen wie "DS-00-000" oder "0000000" findet das nie etwas.
        aus_katalog = _treffer_im_katalog(stichwort, sauber, bereich)
        if aus_katalog:
            return aus_katalog
        passend = [t for t in sauber if stichwort.lower() in t.lower()]
        if passend:
            kopf = ("Zu **%s** liegen %d Dokumente vor:"
                    % (stichwort, len(passend)))
            return kopf + "\n\n" + _liste(passend, zusatz) + _fussnote(len(sauber))
        return ("Zu **%s** finde ich im Bestand%s keinen Dokumenttitel. "
                "Das heisst nicht, dass es inhaltlich nichts dazu gibt - "
                "frag ruhig direkt nach der Sache."
                % (stichwort, " dieses Arbeitsbereichs" if bereich else ""))

    kopf = ("Der Arbeitsbereich enthält **%d Dokumente**." % len(sauber)
            if bereich else "Der Bestand umfasst **%d Dokumente**." % len(sauber))
    # Gruppen erst zeigen, wenn die blosse Liste unuebersichtlich wird -
    # bei neun Dokumenten steht die Aufteilung sonst direkt ueber einer
    # Liste, die sie ohnehin zeigt.
    gruppen = _gruppieren(sauber) if len(sauber) >= 15 else []
    if gruppen:
        zeilen = ["- **%s** — %d" % (name, n) for name, n in gruppen]
        kopf += "\n\n" + "\n".join(zeilen)
    if len(sauber) <= 60:
        try:
            import bestand as _bst
            _bst.nachtragen(sauber)
        except Exception:
            pass
        return kopf + "\n\n" + _liste(sauber, zusatz)
    # Bei grossen Bestaenden hilft eine angeschnittene Liste niemandem: Die
    # ersten vierzig Titel der Fremdliteratur heissen "0000000" und sagen
    # gar nichts. Dann lieber nur die Aufteilung zeigen und nach einem
    # Stichwort fragen.
    return (kopf + "\n\nEine vollständige Liste wäre hier wenig hilfreich. "
            "Frag nach einem Stichwort — etwa *„Welche Unterlagen habt ihr "
            "zum Thema Kleben?“* —, dann nenne ich die passenden Titel.")



def _liste_nach_art(frage, namen, bereich=None):
    """Bestandsliste einer Art - mit Titel, Verfasser und Jahr.

    Gibt None zurueck, wenn keine Art gefragt ist; dann greift die
    allgemeine Auskunft weiter unten.

    ⚠ Drei Zahlen gehoeren in die Antwort: was HIER liegt, was der Katalog
      insgesamt kennt und was FEHLT. Ohne die dritte haelt jemand die
      Liste fuer den ganzen Bestand.
    """
    try:
        import bestand
    except Exception:
        return None
    kennzeichen, wort = bestand.gefragte_art(frage or "")
    if not kennzeichen:
        return None

    passend = sorted(bestand.nach_art(namen, kennzeichen))
    einzahl, mehrzahl = bestand.ARTEN[kennzeichen]
    wo = "in diesem Arbeitsbereich" if bereich else "im Bestand"

    if not passend:
        return ("Ich finde %s keine **%s**. Im Katalog stehen "
                "%s davon — sie sind hier aber nicht hinterlegt."
                % (wo, mehrzahl, bestand.wie_viele_im_katalog(kennzeichen) or "welche"))

    im_katalog = bestand.wie_viele_im_katalog(kennzeichen)
    kopf = "**Bestand an %s — %d %s**" % (mehrzahl, len(passend), wo)
    if im_katalog and im_katalog > len(passend):
        kopf += ("\n\nDer Katalog kennt **%d** %s; hier liegen "
                 "**%d**. Es fehlen also %d."
                 % (im_katalog, mehrzahl, len(passend), im_katalog - len(passend)))

    # ⚠ Die Bestandsauskunft geht NIE durch das Modell - sie kommt direkt
    #   vom Proxy. Also greift auch die Nachbearbeitung nicht, die sonst
    #   Verweise in Modellantworten anklickbar macht. Was hier nicht als
    #   Verweis dasteht, wird auch keiner (sonst: Auskunft ohne Links).
    from urllib.parse import quote

    def _zelle(t):
        """Senkrechte Striche zerreissen eine Tabelle - also schuetzen.
        Zeilenumbrueche in Titeln ebenso."""
        return (t or "").replace("|", "\\|").replace("\n", " ").strip()

    # ⭐ Katalog vor Modell - aber Leerstellen fuellt das Modell: Fehlt der
    #   Eintrag (frische Anlage ohne Katalog, Fremddokument), liest das
    #   kleine Modell Titel/Verfasser/Jahr vom Deckblatt und traegt sie ein.
    #   Vorher stand in jeder Zeile "kein Katalogeintrag" - eine
    #   Bestandsliste ohne Titel ist wertlos.
    try:
        bestand.nachtragen(passend)
    except Exception:
        pass
    zeilen = ["| Kennung | Titel | Verfasser | Jahr |",
              "|---|---|---|---|"]
    ohne_titel = 0
    for n in passend:
        a = bestand.angaben(n)
        # Auf den GESCHRIEBENEN Namen verweisen - _pdf_schluessel() im
        # Proxy findet die Datei auch, wenn sie ein Leerzeichen
        # im Namen traegt.
        verweis = "[%s](/pdf/%s)" % (_zelle(n), quote(n, safe=""))
        if a and a["titel"]:
            marke = "°" if a.get("quelle") == "modell" else ""
            zeilen.append("| %s | %s%s | %s | %s |"
                          % (verweis, _zelle(a["titel"]), marke,
                             _zelle(a["verfasser"]), _zelle(a["jahr"])))
        else:
            ohne_titel += 1
            zeilen.append("| %s | *kein Katalogeintrag* |  |  |" % verweis)

    fuss = ("\n\n*Titel aus dem hinterlegten Katalog; mit ° markierte hat das "
            "kleine Modell aus dem Deckblatt gelesen.*")
    if ohne_titel:
        fuss += ("\n\n*Zu %d Arbeit(en) liegt kein Katalogeintrag vor.*"
                 % ohne_titel)
    return kopf + "\n\n" + "\n".join(zeilen) + fuss


def _treffer_im_katalog(stichwort, namen, bereich=None, gattung=None):
    """Arbeiten zu einem Stichwort - ueber Titel und Schlagworte.

    Gibt None zurueck, wenn der Katalog fehlt oder nichts trifft; dann
    greift die alte Namenssuche weiter.

    ⚠ Es wird gesagt, WARUM eine Arbeit getroffen wurde. Ein Treffer,
      dessen Grund man nicht sieht, laesst sich nicht beurteilen.
    """
    try:
        import bestand
    except Exception:
        return None
    w = (stichwort or "").strip().lower()
    if len(w) < 3:
        return None
    # ⭐ "X oder Y" -> Vereinigung: nach JEDEM Teilbegriff suchen.
    teile = [t.strip() for t in re.split(r"\s+oder\s+|\s+und\s+|\s*[,/]\s*", w)
             if len(t.strip()) >= 3] or [w]

    from urllib.parse import quote
    treffer = []
    for n in namen:
        a = bestand.angaben(n) or {}
        if not a.get("titel"):
            continue
        grund = None
        if any(_t in a["titel"].lower() for _t in teile):
            grund = "Titel"
        else:
            passende = [s for s in (a.get("schlagworte") or [])
                        if any(_t in s.lower() for _t in teile)]
            if passende:
                grund = "Schlagwort: " + ", ".join(passende[:3])
        if grund:
            treffer.append((n, a, grund))
    if not treffer:
        return None

    def _zelle(t):
        return (t or "").replace("|", "\\|").replace("\n", " ").strip()

    wo = "in diesem Arbeitsbereich" if bereich else "im Bestand"
    zeilen = ["| Kennung | Titel | Verfasser | Jahr | gefunden über |",
              "|---|---|---|---|---|"]
    for n, a, grund in sorted(treffer):
        zeilen.append("| [%s](/pdf/%s) | %s | %s | %s | %s |"
                      % (_zelle(n), quote(n, safe=""), _zelle(a["titel"]),
                         _zelle(a.get("verfasser")), _zelle(a.get("jahr")),
                         _zelle(grund)))
    kopf = ("**%d %s zu „%s“ %s**"
            % (len(treffer), gattung or "Arbeiten", stichwort, wo))
    fuss = ("\n\n*Gesucht wurde in Titeln und Schlagworten des "
            "hinterlegten Katalogs — nicht im Volltext. "
            "Für Fachbegriffe im Text frag ruhig direkt nach der Sache.*")
    return kopf + "\n\n" + "\n".join(zeilen) + fuss

def _titel_saubern(t):
    t = re.sub(r"\.(md|pdf|docx?|xlsx?|pptx?)$", "", t.strip(), flags=re.I)
    return re.sub(r"\s+", " ", t)


def _liste(titel, zusatz=None):
    """Der INDEX eines Bereichs: IMMER eine Tabelle (Kennung · Titel ·
    Verfasser · Jahr · Art), egal was hochgeladen wurde (Emrach 26.08.:
    "diese Spaltenansicht soll er immer machen, in jedem Workspace, quasi
    ein Index, egal was man hochlaedt"). Vorher gab es die Tabelle nur,
    wenn wenigstens ein Katalogeintrag existierte - sonst nackte Namen.

    zusatz = {kennung: "Dissertation · PDF · 131 S."} vom Proxy (Art,
    Dateiart, Seiten, Pruefungskatalog) - hier nicht ermittelbar."""
    try:
        import bestand
    except Exception:
        bestand = None
    from urllib.parse import quote
    angaben = [(t, bestand.angaben(t) if bestand else None) for t in titel]
    zusatz = zusatz or {}

    def _zelle(x):
        return (x or "").replace("|", "\\|").replace("\n", " ").strip()

    zeilen = ["| Kennung | Titel | Verfasser | Jahr | Art |", "|---|---|---|---|---|"]
    for t, a in angaben:
        verweis = "[%s](/pdf/%s)" % (_zelle(t), quote(t, safe=""))
        art = zusatz.get(t) or (a.get("art") if a else "") or ""
        if a and a.get("titel"):
            marke = "°" if a.get("quelle") == "modell" else ""
            zeilen.append("| %s | %s%s | %s | %s | %s |" % (
                verweis, _zelle(a["titel"]), marke,
                _zelle(a.get("verfasser")), _zelle(str(a.get("jahr") or "")), _zelle(art)))
        else:
            zeilen.append("| %s | — | — | — | %s |" % (verweis, _zelle(art)))
    if any(a and a.get("quelle") == "modell" for _, a in angaben):
        zeilen.append("")
        zeilen.append("*° = aus dem Deckblatt gelesen · — = noch kein Deckblatt-Eintrag (wird nachgetragen).*")
    return "\n".join(zeilen)


def _fussnote(gesamt):
    return "\n\n*(von insgesamt %d Dokumenten)*" % gesamt


def _gruppieren(titel):
    """Nach dem Kuerzel am Anfang gruppieren (BS-, DS-, DVS, LE ...).

    Die Bestaende tragen sprechende Kuerzel; wer den Bestand
    ueberblicken will, kommt damit schneller weiter als mit einer
    alphabetischen Liste.
    """
    zaehler = {}
    for t in titel:
        m = re.match(r"^([A-Za-zÄÖÜ]{1,4})[\s\-_]", t)
        if m:
            zaehler[m.group(1).upper()] = zaehler.get(m.group(1).upper(), 0) + 1
    gross = [(k, v) for k, v in zaehler.items() if v >= 3]
    return sorted(gross, key=lambda x: -x[1])[:8] if len(gross) >= 2 else []


def _stichwort_aus(frage):
    """Das Thema aus einer Bestandsfrage ziehen ("... zum Thema Kleben")."""
    frage = re.sub(r"[#\s]+$", "", frage or "")   # Tipp-Reste wie "#" am Ende dulden
    m = re.search(r"\b(?:zu(?:m|r)?|ueber|über|betreffend|bezueglich|"
                  r"bezüglich|thema|hinsichtlich|in\s+bezug\s+auf)\s+(?:das\s+|die\s+|der\s+|"
                  r"dem\s+|den\s+|thema\s+)?([A-Za-zÄÖÜäöüß0-9\-\s]{3,40}?)"
                  r"\s*[\?\.,;]?\s*$", frage, re.I)
    if not m:
        return None
    wort = m.group(1).strip()
    if re.fullmatch(r"(verfuegung|verfügung|thema|themen)", wort, re.I):
        return None
    return wort if len(wort) >= 3 else None


def ist_bestand_verfeinerung(frage):
    """Anschluss-Verfeinerung einer vorigen Bestandsfrage? ("Nur
    Dissertationen", "und ueber Kleben"). Nennt eine Art ODER ein Thema -
    nur dann darf die vorige Bestandsfrage den Kontext liefern, sonst wuerde
    jede kurze Frage in den Katalog-Weg gezogen."""
    try:
        import bestand as _b
    except Exception:
        return False
    f = (frage or "").strip()
    if not f or len(f) > 80:
        return False
    # Eine Rueckmeldung oder Feststellung ("Das ist ein Diagramm aus einer
    # anderen Dissertation!!!!!") ist keine Verfeinerung - gemessen 25.08.:
    # sie wurde zur Bestandsliste "Dissertationen".
    if ist_beschwerde(f) or "!!" in f or \
            re.match(r"^\s*(?:das|dies|es)\s+(?:ist|war)\b", f, re.I):
        return False
    if _b.gefragte_art(f)[0]:
        return True
    if _stichwort_aus(f):
        return True
    return False


# ------------------------------------------------- Rueckfrage bei Zweifel

def mehrdeutig(quellen, schwelle=0.55):
    """Streuen die Fundstellen ueber sehr verschiedene Werke?

    Wenn neun Fundstellen aus neun verschiedenen Arbeiten stammen und
    keine deutlich besser passt als die anderen, hat die Suche das Thema
    nicht getroffen - sie hat gestreut. Dann ist eine Rueckfrage ehrlicher
    als eine Antwort, die so tut, als sei die Sache klar.

    Rueckgabe: Hinweistext oder None.
    """
    if not quellen or len(quellen) < 4:
        return None
    werke = {}
    for q in quellen:
        name = _titel_saubern(q.get("title") or "")
        wert = q.get("score")
        if not name or wert is None:
            continue
        werke[name] = max(werke.get(name, 0), float(wert))
    if len(werke) < 4:
        return None
    beste = sorted(werke.values(), reverse=True)
    # Liegt der beste Treffer kaum ueber dem viertbesten, ist nichts
    # herausgestochen.
    if beste[0] - beste[3] > 0.06:
        return None
    if beste[0] > schwelle + 0.12:
        return None
    namen = sorted(werke, key=lambda k: -werke[k])[:4]
    return ("*Mehrere Arbeiten passen ähnlich gut: %s. "
            "Nenne eine davon, dann wird die Antwort genauer.*"
            % ", ".join(namen))


# --------------------------------------------------------- Zusammenfassung

# Diese Woerter sagen nichts darueber, WELCHES Dokument gemeint ist.
# "Lerneinheit" steht in keinem Dateinamen - die heissen "LE ...".
_FUELLWORT = {
    "der", "die", "das", "dem", "den", "des", "ein", "eine", "einer",
    "und", "oder", "von", "vom", "zum", "zur", "fuer", "mit", "auf",
    "teil", "dokument", "dokumente", "datei", "unterlage", "unterlagen",
    "lerneinheit", "lerneinheiten", "norm", "richtlinie", "kapitel",
    "abschnitt", "papier", "arbeit", "text",
}


def _flach(text):
    """Auf Vergleichbares reduzieren.

    Der Bestand traegt Dateinamen ohne Umlaute ("LE Klangpruefung"), Leute
    schreiben aber mit ("Klangpruefung" vs. "Klangprüfung"). Ohne diese
    Angleichung findet die Zuordnung genau die Dokumente nicht, nach denen
    am ehesten gefragt wird.
    """
    t = (text or "").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    return re.sub(r"[^a-z0-9]", "", t)


# Wonach jemand fragt, ohne einen Namen zu nennen. Die Kennungs-Praefixe
# entsprechen den Arten aus dem Katalog (DS=Dissertation usw.); None heisst
# "irgendein Dokument".
_ART_WORTE = {
    "dissertation": "DS", "doktorarbeit": "DS", "promotion": "DS",
    "masterarbeit": "M", "bachelorarbeit": "BS", "studienarbeit": "S",
    "diplomarbeit": "D", "projektarbeit": "PA",
    "dokument": None, "arbeit": None, "werk": None, "datei": None,
    "unterlage": None, "pdf": None, "buch": None,
}


def _generisch_gemeint(frage, titel):
    """'Fasse die Dissertation zusammen' - ohne Namen, aber eindeutig?

    Auf einer kleinen Anlage (ein Partner faengt mit EINEM Dokument an)
    ist "das Dokument" oder "die Dissertation" voellig klar - die
    Titelwort-Suche findet aber nichts, weil kein Titelwort in der Frage
    steht, und die Zusammenfassung fiel still auf Schnipsel zurueck.

    Gewaehlt wird NUR bei Eindeutigkeit: genau ein Dokument insgesamt,
    oder genau eines der genannten Art (Kennungs-Praefix wie DS-...).
    Bei mehreren bleibt es bei None - raten waere schlimmer.
    """
    f = (frage or "").lower()
    getroffen = [(w, art) for w, art in _ART_WORTE.items() if w in f]
    if not getroffen:
        return None
    if len(titel) == 1:
        return titel[0]
    arten = {art for _, art in getroffen if art}
    if len(arten) == 1:
        art = arten.pop()
        passend = [t for t in titel
                   if re.match(r"%s-?\d" % art, (t or "").strip(), re.I)]
        if len(passend) == 1:
            return passend[0]
    return None


# Woerter, die kein Dokument benennen - Fragewoerter, Auftraege, Gattungen,
# Bausteine eines Dokuments. Alles andere Grossgeschriebene gilt als
# eigener Gegenstand (Name, Fachbegriff, Titelwort).
_UNSPEZIFISCH = set("""
kannst koenntest könntest kann koennen können bitte danke mach mache machen
erstelle erstell erstellen gib gibt zeig zeige zeigen schreib schreibe
schreiben fasse fass fasst fassen erklaer erklär erklaere erkläre nenne nenn
was wie welche welcher welches welchen warum wieso weshalb wo wann wer und
aber okay ok ja nein nochmal noch dann jetzt hier auch nur sehr mehr alle
alles ich du mir mich dir ihr sie wir uns der die das ein eine einen einem
einer dieser diese dieses diesem gesamt gesamte gesamten komplett komplette
ganz ganze ganzen kurz kurze kurzen lang lange langen ausfuehrlich
ausführlich ausfuehrliche ausführliche deutsch englisch
dokument dokumente arbeit arbeiten dissertation dissertationen doktorarbeit
masterarbeit bachelorarbeit studie paper text werk quelle quellen pdf datei
dateien unterlagen datenbank bestand thema themen
zusammenfassung zusammenfassungen kernaussage kernaussagen kernfakten
ergebnis ergebnisse fazit methodik methode ziel ziele aufbau gliederung
praesentation präsentation handout stichpunkte stichworte vortrag folien
ueberblick überblick inhalt inhalte einleitung schluss abstract kurzfassung
kapitel abschnitt seite seiten tabelle tabellen bild bilder abbildung
abbildungen grafik grafiken diagramm diagramme diagram figur figure
saetze sätze satz woerter wörter wort punkte punkt antwort frage
""".split())


def bezieht_sich_auf_vorheriges(frage):
    """Nennt die Frage KEIN eigenes Dokument (keinen Namen, kein Titelwort)?

    "Schreib mir eine gesamte Zusammenfassung", "ein Diagramm aus der
    Arbeit", "und die Kernaussagen?" - alles ohne Gegenstand; gemeint ist,
    worueber gerade gesprochen wird. "Fasse die Dissertation von Mueller
    zusammen" dagegen traegt einen Namen und darf NICHT auf das vorige
    Dokument umgebogen werden - lieber ehrlich nachfragen.
    """
    f = (frage or "").strip()
    if not f:
        return False
    woerter = re.findall(r"\b[A-ZÄÖÜ][A-Za-zäöüßÄÖÜ]{2,}", f)
    eigene = [w for w in woerter
              if w.lower() not in _UNSPEZIFISCH
              and w.lower() not in _ART_WORTE
              and w.lower() not in _FUELLWORT]
    return not eigene


_BESCHWERDE = re.compile(
    r"^\s*(?:h[äa]+h?\b|was\s+soll\s+das|nein\b|falsch\b|quatsch\b|"
    r"unsinn\b|bl[oö]dsinn\b)|"
    r"\b(?:das|dies|es)\s+(?:ist|war)\s+(?:nicht|kein|keine|falsch|"
    r"ein(?:e|em|en)?\s+ander)|"
    r"\bich\s+hab(?:e|te)?\s+(?:doch\s+)?nicht\s+(?:nach|danach|das|so|"
    r"gefragt|gemeint|gewollt|verlangt)|"
    r"\bnicht\s+(?:danach\s+)?gefragt\b|"
    r"\baus\s+einer\s+anderen\b|"
    r"\bfalsche[nsmr]?\s+(?:dokument|arbeit|dissertation|datei|quelle|"
    r"antwort|bild|diagramm|tabelle)|"
    r"\b(?:nicht|kein)\s+(?:das|die|der)\s+(?:richtige|gesuchte|gemeinte)|"
    r"\bstimmt\s+(?:so\s+)?nicht\b|"
    r"\b(?:schei(?:ss|ß)e?|mist|kacke)\b", re.I)


def ist_beschwerde(frage):
    """Eine Rueckmeldung, keine Frage: "Das ist ein Diagramm aus einer
    anderen Dissertation!!!!!", "hä? ich habe nicht nach einem Bestand
    gefragt!". Gemessen 25.08.: Beide gingen als Frage durch - die erste
    wurde zur Bestandsliste, die zweite zur Wortsuche nach "Bestand"."""
    f = (frage or "").strip()
    if not f or len(f) > 160:
        return False
    return bool(_BESCHWERDE.search(f))


def beschwerde_antwort(letztes_dokument=None):
    teile = ["Entschuldige — das war daneben."]
    if letztes_dokument:
        teile.append("In diesem Gespräch ging es zuletzt um **%s**; die "
                     "nächste Frage beziehe ich darauf."
                     % _titel_saubern(letztes_dokument))
    teile.append("Wenn du ein bestimmtes Dokument meinst, nenn mir die "
                 "Kennung (z. B. DS-24-005) oder den Verfasser — dann hole "
                 "ich es genau daraus.")
    return " ".join(teile)


def dokument_zeile(name):
    """Eine Zeile fuer Listen und Rueckfragen: Kennung — Verfasser (Jahr): Titel."""
    kurz = _titel_saubern(name)
    try:
        import bestand as _b
        ang = _b.angaben(name) or {}
    except Exception:
        ang = {}
    zeile = kurz
    wer = (ang.get("verfasser") or "").strip()
    jahr = (ang.get("jahr") or "").strip()
    if wer:
        zeile += " — %s%s" % (wer, " (%s)" % jahr if jahr else "")
    t = (ang.get("titel") or "").strip()
    if t:
        zeile += ": %s" % (t[:90] + ("…" if len(t) > 90 else ""))
    return zeile


# --------------------------------------------- Rueckmeldungen und Anlage-Fragen

_ZWEIFEL = re.compile(
    r"^\s*(?:(?:bist\s+du\s+(?:dir\s+)?(?:da\s+)?)?(?:ganz\s+)?sicher|wirklich|echt|"
    r"stimmt\s+das|ist\s+das\s+(?:so\s+)?(?:richtig|korrekt|sicher)|"
    r"sicher,?\s+dass\s+(?:das|es)\s+(?:so\s+)?(?:ist|stimmt)|"
    r"kann\s+das\s+(?:so\s+)?(?:sein|stimmen)|bist\s+du\s+dir\s+da\s+sicher)"
    r"[\s?!.]*$", re.I)


def ist_zweifel(frage):
    """"Sicher?", "Wirklich?", "Stimmt das?" - eine Rueckmeldung, keine
    Frage nach dem Wort "sicher". Gemessen 26.08.: "Sicher" wurde zur
    Wortsuche und lieferte "keine Informationen zum Begriff Sicher"."""
    f = (frage or "").strip()
    return bool(f) and len(f) <= 60 and bool(_ZWEIFEL.match(f))


_DIESES_DOKUMENT = re.compile(
    r"\b(?:diese[rsm]?|dieses|das|der|die|jene[rsm]?)\s+"
    r"(?:arbeit|dissertation|doktorarbeit|dokument|studie|paper|werk|datei|pdf|quelle)\b(?!en)",
    re.I)
_MEHRERE = re.compile(
    r"\b(?:andere[nrs]?|weitere[nrs]?|alle[nrs]?|sonstige[nrs]?|mehrere|"
    r"arbeiten|dissertationen|dokumente|studien|quellen|werke)\b", re.I)


def meint_dieses_dokument(frage):
    """"... hat diese Arbeit?", "in dem Dokument" - Einzahl mit Zeiger. Bei
    gesetztem Faden-Dokument darf das NIE zur Bestandsfrage werden (gemessen
    26.08.: "Wieviele Diagramme hat diese Arbeit?" -> Bestandstabelle)."""
    f = frage or ""
    return bool(_DIESES_DOKUMENT.search(f)) and not _MEHRERE.search(f)


_THEMA_BEZUG = re.compile(
    r"\b(?:zum\s+|zu\s+dem\s+|über\s+das\s+|ueber\s+das\s+)?(?:selben|gleichen|"
    r"(?:ae|ä)hnlichen?|diesem|dem\s+gleichen)\s+(?:thema|gebiet|bereich|feld)\b|"
    r"\b(?:ae|ä)hnliche[rsn]?\s+(?:arbeiten|dissertationen|dokumente|themen)\b|"
    r"\bdazu\s+(?:noch\s+|auch\s+)?(?:andere|weitere|mehr)\b|\bvergleichbare[rsn]?\b", re.I)


def ist_thema_bezug(frage):
    """"Haben wir Dissertationen zum selben Thema?" - das Thema ist das des
    Faden-Dokuments, nicht das Wort "selben Thema" (gemessen 26.08.)."""
    return bool(_THEMA_BEZUG.search(frage or ""))


_STAMM_STOPP = set("""untersuchung untersuchungen analyse analysen entwicklung
einfluss einflusses methode methoden methodik verfahren beitrag bewertung
verhalten eigenschaften herstellung anwendung einsatz auslegung
kunststoff kunststoffe kunststoffen polymer polymere polymeren werkstoff
werkstoffe bauteil bauteile bauteilen prozess prozesse mittels unter beim
einer eines eine einem einen durch fuer für ueber über zwischen anhand
geometrie modell modelle""".split())


def _titelgramme(text):
    """Wortstuecke (8 Zeichen) je Titelwort - damit Komposita zueinander
    finden: "glasfaserverstaerkten" und "endlosfaserverstaerkten" teilen
    "faserver", "erverst" ... Rueckgabe {gramm: wort}."""
    gramme = {}
    for w in re.findall(r"[A-Za-zÄÖÜäöüß\-]{6,}", text or ""):
        f = _flach(w)
        if len(f) < 8 or f in _STAMM_STOPP:
            continue
        for i in range(0, len(f) - 7):
            gramme.setdefault(f[i:i + 8], f)
    return gramme


def aehnliche_titel(name, namen, hoechstens=6):
    """Dokumente, deren Katalog-Titel Wortbestandteile mit dem Titel von
    `name` teilen - [(name, [gemeinsame Woerter])], bester zuerst."""
    try:
        import bestand as _b
        eig = _b.angaben(name) or {}
    except Exception:
        return []
    basis = _titelgramme(eig.get("titel") or "")
    if not basis:
        return []
    treffer = []
    for n in namen:
        if n == name:
            continue
        try:
            ang = _b.angaben(n) or {}
        except Exception:
            continue
        andere = _titelgramme(ang.get("titel") or "")
        gemeinsam = sorted({basis[g] for g in basis if g in andere})
        if gemeinsam:
            treffer.append((n, gemeinsam))
    treffer.sort(key=lambda x: -len(x[1]))
    return treffer[:hoechstens]


_ZIELFRAGE = re.compile(
    r"^\s*(?:was|wie|welche[rsn]?|worin|wof(?:ue|ü)r|wozu|warum|wieso|weshalb)\b"
    r".{0,60}?\b(?:ziel|ziele|zielsetzung|thema|anliegen|fragestellung|"
    r"forschungsfrage|hypothese|motivation|methodik|vorgehen|aufbau|"
    r"ergebnis|ergebnisse|fazit|kernaussage|kernaussagen|erkenntnis|"
    r"erkenntnisse|schlussfolgerung|schlussfolgerungen|neuheit|beitrag)\b", re.I)


def ist_zielfrage(frage):
    """"Was ist das Ziel der Arbeit?" ist eine FRAGE an ein Dokument, keine
    Bitte um eine Zusammenfassung. Gemessen 26.08.: zwei Minuten Volltext-
    Lauf mit allgemeiner Zusammenfassung statt einer gezielten Antwort."""
    return bool(_ZIELFRAGE.match((frage or "").strip()))


_FAKTEN = (
    ("seiten", re.compile(r"\bwie\s*viele?\s+seiten\b|\bseitenzahl\b|\bwie\s+lang\s+ist\b", re.I)),
    ("abbildungen", re.compile(r"\bwie\s*viele?\s+(?:abbildungen|bilder|diagramme|grafiken|figuren|abb)\b", re.I)),
    ("tabellen", re.compile(r"\bwie\s*viele?\s+tabellen\b", re.I)),
    ("verfasser", re.compile(r"\b(?:wer\s+(?:ist|war)\s+der\s+(?:verfasser|autor)|von\s+wem\s+(?:ist|stammt)|wer\s+hat\s+(?:die|das|diese|dieses)\s+\w+\s+(?:geschrieben|verfasst))\b", re.I)),
    ("jahr", re.compile(r"\b(?:aus\s+welchem\s+jahr|wann\s+(?:ist|wurde)\s+.{0,30}(?:erschienen|veröffentlicht|veroeffentlicht|geschrieben|eingereicht)|welches\s+jahr)\b", re.I)),
    ("titel", re.compile(r"\bwie\s+(?:heisst|heißt|lautet)\s+(?:der\s+titel|die\s+arbeit|das\s+dokument|die\s+dissertation)\b", re.I)),
)


def dokument_fakten_frage(frage):
    """Welche ZAEHLBARE Eigenschaft eines Dokuments ist gefragt - oder None.
    Seiten, Abbildungen, Tabellen, Verfasser, Jahr, Titel braucht kein
    Sprachmodell; das steht im PDF und im Katalog."""
    for art, muster in _FAKTEN:
        if muster.search(frage or ""):
            return art
    return None


_ANLAGE_FRAGE = re.compile(
    r"\b(?:angedockt|ausdocken|andocken|eingestellt\s+auf|festgelegt\s+auf|"
    r"nur\s+(?:noch\s+)?(?:diese[sr]?|dieses|die\s+eine|auf\s+diese)\s+(?:eine\s+)?"
    r"(?:dissertation|arbeit|dokument|datei)|"
    r"(?:welche[sr]?|welches)\s+(?:dokument|arbeit|dissertation)\s+(?:nutzt|benutzt|verwendest|hast)\s+du|"
    r"worauf\s+(?:bist|beziehst)\s+du|"
    r"(?:kannst|k(?:oe|ö)nntest)\s+du\s+(?:das\s+)?(?:wechseln|umschalten|ausdocken|eine\s+andere\s+nehmen)|"
    r"(?:andere|anderes)\s+(?:dissertation|dokument|arbeit)\s+(?:nehmen|laden|w(?:ae|ä)hlen)|"
    r"wie\s+wechsle\s+ich|wie\s+komme\s+ich\s+(?:zu|an)\s+(?:andere|alle))\b", re.I)


def ist_anlagefrage(frage):
    """Fragen an die ANLAGE selbst ("Hast du nur diese Dissertation
    angedockt? Kannst du eine andere nehmen?"). Die beantwortet der Proxy -
    das Sprachmodell weiss nichts ueber Faeden und erfindet sonst etwas
    (gemessen 26.08.: "kein Zugriff auf externe Datenbank")."""
    f = (frage or "").strip()
    return bool(f) and len(f) <= 220 and bool(_ANLAGE_FRAGE.search(f))


def anlage_antwort(dokument=None, anzahl=None):
    teile = []
    if dokument:
        teile.append("Ja — dieses Gespräch ist gerade auf **%s** eingestellt: "
                     "Folgefragen, Zusammenfassungen und Bilder beziehen sich "
                     "darauf, Antworten kommen nur aus diesem Dokument."
                     % dokument_zeile(dokument))
    else:
        teile.append("Dieses Gespräch ist auf **kein** bestimmtes Dokument "
                     "eingestellt — ich suche über alle Dokumente des Bereichs.")
    teile.append("So steuerst du das:\n"
                 "- **Wechseln:** ein anderes Dokument nennen — Kennung (z. B. DS-24-006) "
                 "oder Verfasser („die Arbeit von Köbel“).\n"
                 "- **Alle durchsuchen:** die Frage mit „im ganzen Bestand:“ beginnen.\n"
                 "- **Übersicht:** „Welche Dokumente haben wir?“%s\n"
                 "- **Neu anfangen:** neuen Gesprächsfaden öffnen."
                 % (" (%d im Bereich)" % anzahl if anzahl else ""))
    k = kontakt_zeile()
    if k:
        teile.append("*%s*" % k)
    return "\n\n".join(teile)


def zweifel_antwort_ohne():
    return ("Verstanden, du zweifelst. Sag mir bitte, **welche Aussage** — "
            "dann prüfe ich genau diese Stelle am Original.")


def rueckfrage_welche_aussage(dokument):
    return ("Entschuldige. Die Zusammenfassung stammt aus dem ganzen Dokument "
            "**%s**. **Welche Aussage ist falsch?** Zitiere sie oder nenne das "
            "Stichwort — dann prüfe ich genau diese Stelle Satz für Satz an den "
            "Seiten, mit wörtlichen Belegen." % _titel_saubern(dokument))


# ------------------------------------------ Vergleich, Kennwerte, Abkuerzungen

_WIDERSPRUCH = re.compile(
    r"widerspr(?:e|i|u|ü)ch|widersprechen|(?:stimmen|passen)\s+.{0,20}(?:überein|ueberein|zusammen)|"
    r"\beinig\b|\buneinig\b|\bgegens(?:ae|ä)tz", re.I)


def ist_widerspruchsfrage(frage):
    return bool(_WIDERSPRUCH.search(frage or ""))


def vergleichs_dokumente(frage, namen):
    """Zwei Dokumente aus einer Vergleichsfrage - (dokA, dokB, aspekt) oder
    None. "Vergleiche die Methodik von Becker und Mueller" -> Becker, Mueller,
    "Methodik". Nur wenn BEIDE Seiten ein Dokument sind."""
    teile = vergleichsteile(frage)
    if not teile:
        return None
    a, b = teile
    da, _ = dokument_gemeint(a, namen)
    db, _ = dokument_gemeint(b, namen)
    if not da or not db or da == db:
        return None
    # Aspekt = die Inhaltswoerter der Frage ohne die Namen der Dokumente
    # und ohne Fuellwoerter ("Methodik" aus "Vergleiche die Methodik von
    # Becker und Mueller").
    namen_flach = set()
    try:
        import bestand as _b
        for d in (da, db):
            ang = _b.angaben(d) or {}
            namen_flach |= {_flach(x) for x in re.findall(r"[A-Za-zÄÖÜäöüß\-]{2,}", ang.get("verfasser") or "")}
            namen_flach.add(_flach(_titel_saubern(d)))
    except Exception:
        pass
    fueller = {"vergleiche", "vergleich", "vergleichen", "vergleicht", "unterschied", "unterschiede",
               "zwischen", "von", "und", "mit", "mir", "bitte", "die", "der", "das", "den", "dem",
               "des", "was", "ist", "sind", "wie", "sich", "unterscheiden", "unterscheidet",
               "arbeit", "arbeiten", "dissertation", "dissertationen", "dokument", "dokumente",
               "bei", "beim", "in", "im", "zu", "zur", "zum", "widersprechen", "widerspricht",
               "gegenüber", "gegenueber", "versus", "vs", "einig", "uneinig", "beide", "beiden"}
    woerter = []
    for w in re.findall(r"[A-Za-zÄÖÜäöüß0-9\-]{2,}", frage):
        f = _flach(w)
        if w.lower() in fueller or f in namen_flach or f in _FUELLWORT:
            continue
        if any(f in n or n in f for n in namen_flach if len(n) >= 4):
            continue
        woerter.append(w)
    aspekt = " ".join(woerter).strip()
    return da, db, aspekt


_KENNWERT = re.compile(
    r"\b(?:kennwert\w*|messwert\w*|zahlenwert\w*|werte?\b|wie\s+(?:hoch|gro(?:ss|ß)|viel|schnell|schwer|dick|lang)\b|"
    r"modul\b|e-modul|festigkeit\w*|viskosit(?:ae|ä)t\w*|temperatur\w*|dichte|"
    r"dehnung\w*|spannung\w*|druck\b|kraft\b|zyklen|lebensdauer|"
    r"\d+\s*(?:mpa|gpa|°c|k\b|mm|µm|%|pa·s|n\b|kn))", re.I)


def ist_kennwertfrage(frage):
    """Fragen nach Zahlen: Antwort als Tabelle Wert | Einheit | Bedingung |
    Seite - und "Bedingung fehlt" statt stillschweigend (GESPRAECH-
    ANFORDERUNGEN §2.18: nur 9 % der Tabellen nennen Messbedingungen)."""
    return bool(_KENNWERT.search(frage or ""))


_ABKUERZUNG = re.compile(
    r"(?:\b(?:was\s+(?:heisst|heißt|bedeutet|ist)|wof(?:ue|ü)r\s+steht|"
    r"was\s+ist\s+(?:die\s+)?abk(?:ue|ü)rzung)\s+(?:die\s+abk(?:ue|ü)rzung\s+)?"
    r"([A-ZÄÖÜ][A-Za-z0-9ÄÖÜäöü\-]{1,9})\b|^\s*([A-ZÄÖÜ]{2,8})\s*\??\s*$)", re.I)


def abkuerzungs_frage(frage):
    """"Wofuer steht GFK?" / "Was heisst FVK?" / "GFK?" -> "GFK", sonst None.
    Aufgeloest wird aus DIESEM Dokument (SciAD: 732 mehrdeutige Akronyme)."""
    m = _ABKUERZUNG.search((frage or "").strip())
    if not m:
        return None
    k = m.group(1) or m.group(2)
    if not k or k.lower() in _UNSPEZIFISCH or k.lower() in _FUELLWORT:
        return None
    # Eine Abkuerzung hat mindestens zwei Grossbuchstaben ("GFK", "E-Modul"
    # nicht) - "Was ist Mastizieren" oder "kleben?" sind keine.
    if sum(1 for c in k if c.isupper()) < 2:
        return None
    return k


def abkuerzung_aufloesen(kurz, seiten):
    """[(seite, ausgeschrieben, zeile)] - Stellen, an denen die Abkuerzung
    eingefuehrt wird: "glasfaserverstaerkter Kunststoff (GFK)" oder
    "GFK (glasfaserverstaerkter Kunststoff)"."""
    k = re.escape(kurz)
    m1 = re.compile(r"((?:[A-Za-zÄÖÜäöüß\-]+\s+){1,6}[A-Za-zÄÖÜäöüß\-]+)\s*\(\s*%s\s*\)" % k)
    m2 = re.compile(r"\b%s\s*[\(:=–\-]\s*([A-Za-zÄÖÜäöüß][^)\n]{4,90})" % k)
    treffer = []
    for i, s in enumerate(seiten or [], 1):
        for m in m1.finditer(s or ""):
            lang = re.sub(r"\s+", " ", m.group(1)).strip()
            # Nur die Woerter, deren Anfangsbuchstaben zur Abkuerzung passen
            woerter = lang.split(" ")
            if len(woerter) > len(kurz) + 2:
                woerter = woerter[-(len(kurz) + 2):]
            treffer.append((i, " ".join(woerter), m.group(0)))
        for m in m2.finditer(s or ""):
            treffer.append((i, re.sub(r"\s+", " ", m.group(1)).strip(" )"), m.group(0)))
        if len(treffer) >= 3:
            break
    return treffer


# ------------------------------------------------------------- Export

_EXPORT = re.compile(r"\b(?:export\w*|als\s+(?:csv|bibtex|ris|excel|tabelle\s+zum\s+download)|"
                     r"(?:csv|bibtex|ris)[\s\-]?(?:datei|format|export)?)\b", re.I)


def export_frage(frage):
    """'bibtex' | 'csv' | None."""
    f = (frage or "")
    if not _EXPORT.search(f):
        return None
    if re.search(r"bibtex|ris\b|literatur|zitier|zotero|citavi", f, re.I):
        return "bibtex"
    return "csv"


def bibtex_eintraege(namen):
    try:
        import bestand as _b
    except Exception:
        return ""
    aus = []
    for n in namen:
        ang = _b.angaben(n) or {}
        kurz = _titel_saubern(n)
        wer = (ang.get("verfasser") or "").strip()
        nach = wer.split()[-1] if wer else kurz
        schl = re.sub(r"[^A-Za-z0-9]", "", _flach(nach)) + str(ang.get("jahr") or "")
        art = (ang.get("art") or "").lower()
        typ = "phdthesis" if "dissertation" in art else "mastersthesis" if "arbeit" in art else "misc"
        felder = ["  title = {%s}" % (ang.get("titel") or kurz)]
        if wer:
            felder.append("  author = {%s}" % wer)
        if ang.get("jahr"):
            felder.append("  year = {%s}" % ang["jahr"])
        felder.append("  note = {%s}" % kurz)
        aus.append("@%s{%s,\n%s\n}" % (typ, schl or kurz, ",\n".join(felder)))
    return "\n\n".join(aus)


def tabelle_zu_csv(markdown):
    """Die erste Markdown-Tabelle im Text als CSV (Semikolon) - oder ""."""
    zeilen = [z for z in (markdown or "").split("\n") if z.strip().startswith("|")]
    if len(zeilen) < 2:
        return ""
    aus = []
    for z in zeilen:
        if re.match(r"^\s*\|?\s*:?-{2,}", z):
            continue
        zellen = [re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", c).replace("**", "").strip()
                  for c in z.strip().strip("|").split("|")]
        aus.append(";".join('"%s"' % c.replace('"', '""') if (";" in c or '"' in c) else c
                            for c in zellen))
    return "\n".join(aus)


def kontakt_zeile():
    k = (os.environ.get("KI4KI_KONTAKT") or "").strip()
    return ("Ansprechpartner: %s" % k) if k else ""


def naechste_schritte(art, dokument=None):
    """Zwei, drei konkrete Anschlussfragen - Laien wissen sonst nicht, was
    die Anlage noch kann (NN/g G4)."""
    if dokument:
        d = _titel_saubern(dokument)
        if art == "zusammenfassung":
            v = ["„Was ist das Ziel der Arbeit?“", "„Zeig mir ein Diagramm“", "„Welche Kennwerte werden genannt?“"]
        elif art == "bild":
            v = ["„Zeig mir Bild 2.1“", "„Wie viele Abbildungen hat die Arbeit?“", "„Was zeigt das Diagramm?“"]
        elif art == "fakten":
            v = ["„Fasse die Arbeit zusammen“", "„Zeig mir ein Diagramm“"]
        else:
            v = ["„Fasse %s zusammen“" % d, "„Zeig mir ein Diagramm“", "„Vergleiche %s mit …“" % d]
        return "*Weiter: %s · Anderes Dokument: Kennung oder Verfasser nennen.*" % " · ".join(v)
    return "*Weiter: „Welche Dokumente haben wir?“ · „Fasse <Kennung> zusammen“*"


def _aus_katalog(frage, titel):
    """Dokument ueber den Katalog finden: Verfasser oder Titelwoerter.

    Gemessen 25.08.: "Dissertation von Fabian Becker" fand nichts - der
    Abgleich kannte nur Dateinamen (DS-24-005), den Verfasser kennt
    allein der Katalog. Rueckgabe (gewaehlt, kandidaten) wie
    dokument_gemeint. Nur ein Verfasser-Treffer oder zwei gehaltvolle
    Titelwoerter zaehlen; ein einzelnes Titelwort waehlt nichts.
    """
    try:
        import bestand as _b
    except Exception:
        return None, []
    f = frage or ""
    namen = [w for w in re.findall(r"\b[A-ZÄÖÜ][A-Za-zäöüßÄÖÜ\-]{2,}", f)
             if w.lower() not in _UNSPEZIFISCH
             and w.lower() not in _ART_WORTE
             and w.lower() not in _FUELLWORT]
    titelwoerter = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß0-9\-]{5,}", f)
                    if w.lower() not in _UNSPEZIFISCH
                    and w.lower() not in _FUELLWORT
                    and w.lower() not in _ART_WORTE]
    if not namen and not titelwoerter:
        return None, []
    punkte = {}
    for t in titel:
        try:
            ang = _b.angaben(t)
        except Exception:
            ang = None
        if not ang:
            continue
        p = 0
        verfasser = {_flach(x) for x in
                     re.findall(r"[A-Za-zÄÖÜäöüß\-]{2,}", ang.get("verfasser") or "")}
        for n in namen:
            fn = _flach(n)
            if fn in verfasser:
                p += 10
            elif len(fn) >= 5:
                # Tippfehler dulden: "Beker", "Mueler" - Aehnlichkeit >= 0,85
                import difflib
                if any(difflib.SequenceMatcher(None, fn, v).ratio() >= 0.85
                       for v in verfasser if len(v) >= 5):
                    p += 8
        ft = _flach(ang.get("titel") or "")
        if ft:
            getroffen = [w for w in titelwoerter if _flach(w) in ft]
            if len(getroffen) >= 2:
                p += sum(len(_flach(w)) for w in getroffen)
        if p:
            punkte[t] = p
    if not punkte:
        return None, []
    sortiert = sorted(punkte.items(), key=lambda x: -x[1])
    beste = [t for t, p in sortiert if p == sortiert[0][1]]
    if sortiert[0][1] < 8:
        return None, []
    if len(beste) == 1:
        return beste[0], beste
    return None, beste


def dokument_gemeint(frage, titel):
    """Welches Dokument meint "Worum geht es in DVS 2213-1"?

    Nur bei einem eindeutigen Treffer wird zusammengefasst. Bei mehreren
    gleich guten Titeln ist eine Rueckfrage besser als eine Wahl auf gut
    Glueck - eine Zusammenfassung des falschen Dokuments faellt niemandem
    auf, weil sie ja plausibel klingt.
    """
    if not titel:
        return None, []
    # Erst der Katalog (Verfasser, Titel) - der weiss mehr als Dateinamen.
    try:
        k_hit, k_kand = _aus_katalog(frage, titel)
    except Exception:
        k_hit, k_kand = None, []
    if k_hit:
        return k_hit, [k_hit]
    if len(k_kand) > 1:
        return None, k_kand
    kern = re.sub(r"^.*?(?:in|von|zu|ueber|über|des|der)\s+", "",
                  frage.strip(), flags=re.I)
    kern = kern.strip(" ?.,;:\"'„“")
    if len(kern) < 3:
        return None, []

    flach_kern = _flach(kern)
    treffer = [t for t in titel
               if flach_kern and (flach_kern in _flach(t)
                                  or _flach(t) in flach_kern)]
    if len(treffer) == 1:
        return treffer[0], treffer
    if treffer:
        return None, treffer

    # Zweiter Versuch mit Punkten statt alles-oder-nichts: Wie viele der
    # aussagekraeftigen Woerter stecken im Titel? Der beste Titel gewinnt,
    # aber nur wenn er allein vorn liegt.
    woerter = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß0-9]{2,}", kern)
               if w.lower() not in _FUELLWORT]
    if not woerter:
        g = _generisch_gemeint(frage, titel)
        return (g, [g]) if g else (None, [])
    punkte = {}
    for t in titel:
        flach_titel = _flach(t)
        getroffen = [w for w in woerter if _flach(w) in flach_titel]
        if not getroffen:
            continue
        # Lange Woerter wiegen schwerer: "Klangpruefung" sagt mehr als "1".
        punkte[t] = sum(len(_flach(w)) for w in getroffen)
    if not punkte:
        # Kein Titelwort in der Frage - der haeufigste Fall auf einer
        # kleinen Anlage: "Fasse mir die Dissertation zusammen" nennt
        # keinen Namen, meint aber offensichtlich das einzige Dokument.
        g = _generisch_gemeint(frage, titel)
        return (g, [g]) if g else (None, [])
    sortiert = sorted(punkte.items(), key=lambda x: -x[1])
    beste = [t for t, p in sortiert if p == sortiert[0][1]]
    # Mindestens ein Wort mit Substanz muss getroffen sein - sonst reicht
    # schon ein gemeinsames "2213", um das falsche Dokument zu waehlen.
    if sortiert[0][1] < 5:
        return None, list(punkte)
    if len(beste) == 1:
        return beste[0], beste
    return None, beste


def vergleich_gedeckt(seiten, quellen, _antwort=""):
    """Steckt bei einem Vergleich wirklich BEIDES in den Fundstellen?

    Das ist die gefaehrlichste Luecke der jetzigen Anlage: Bei "Unterschied
    zwischen A und B" findet die Suche haeufig nur A - und die Antwort
    liest sich trotzdem wie ein vollstaendiger Vergleich. Niemand merkt,
    dass die halbe Grundlage fehlt.

    Zwei getrennte Suchlaeufe waeren sauberer, verdoppeln aber die
    Antwortzeit. Deshalb hier der ehrliche Mittelweg: nachsehen, ob beide
    Seiten vorkommen, und sonst dazusagen, dass die Antwort einseitig ist.

    Rueckgabe: Hinweistext oder None.
    """
    if not seiten or len(seiten) != 2:
        return None
    # Nur die QUELLEN zaehlen, nicht die Antwort. Ob das Modell "DVS 2291"
    # erwaehnt, sagt nichts darueber, ob es dafuer eine Fundstelle gab -
    # im Gegenteil, genau das waere der Fall, den wir fangen wollen.
    heu = _flach(" ".join([(q.get("text") or "") + " " + (q.get("title") or "")
                           for q in (quellen or [])]))
    if not heu:
        return None
    fehlt = [s for s in seiten if not _kommt_vor(s, heu)]
    if not fehlt:
        return None
    if len(fehlt) == 2:
        return ("⚠ Zu **keiner** der beiden Seiten (*%s*, *%s*) habe ich "
                "belastbare Fundstellen. Die Antwort oben stützt sich nicht "
                "auf den Bestand — bitte einzeln nachfragen."
                % (seiten[0], seiten[1]))
    return ("⚠ Zu **%s** habe ich Fundstellen, zu **%s** nicht. Die Antwort "
            "vergleicht also nur einseitig. Frag am besten getrennt nach "
            "*%s*, dann steht die zweite Hälfte auf eigenen Belegen."
            % (seiten[0] if fehlt[0] == seiten[1] else seiten[1],
               fehlt[0], fehlt[0]))


def _kommt_vor(begriff, heuhaufen_flach):
    """Kommt der Begriff vor - auch wenn er anders geschrieben ist?

    Schreibweisen sollen egal sein ("DVS 2290" = "DVS-2290" = "DVS2290"),
    die Sache selbst aber nicht.

    ⚠ Hier steckte ein Fehler, der die ganze Pruefung wertlos machte: Erst
    galt die Mehrheit der Wortteile als Beleg. Bei "DVS 2291" sind das
    "DVS" und "2291" - und "DVS" allein reichte, weil es in jedem zweiten
    Titel steht. Damit galt "DVS 2291" schon dann als gedeckt, wenn nur
    Unterlagen zu DVS 2290 gefunden waren. Genau der Fall, den die
    Pruefung fangen soll, rutschte durch.

    Deshalb jetzt: Nummern sind PFLICHT. Bei technischen Bezeichnungen
    traegt die Nummer die Unterscheidung, nicht das Kuerzel davor.
    """
    teile = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß0-9]{2,}", begriff)
             if w.lower() not in _FUELLWORT]
    if not teile:
        return True
    zahlen = [w for w in teile if any(z.isdigit() for z in w)]
    if zahlen:
        # Jede Nummer muss vorkommen - eine fehlende macht aus 2290 die
        # 2291, und das ist ein anderes Regelwerk.
        return all(_flach(w) in heuhaufen_flach for w in zahlen)
    woerter = [w for w in teile if w not in zahlen]
    treffer = sum(1 for w in woerter if _flach(w) in heuhaufen_flach)
    # Ohne Nummer entscheidet die Mehrheit der Woerter - "praktischer
    # Leitfaden" muss nicht wortwoertlich dastehen.
    return treffer >= max(1, (len(woerter) + 1) // 2)


def zusammenfassungs_auftrag(volltext, titel, hoechstens=48000):
    """Den Auftrag bauen, mit dem das Modell ein Dokument zusammenfasst.

    Warum nicht einfach die Suche nutzen: Eine Zusammenfassung braucht das
    GANZE Dokument, die Suche liefert neun Ausschnitte. Fuer sehr lange
    Arbeiten wird gekuerzt - Anfang und Schluss tragen bei
    wissenschaftlichen Texten am meisten (Einleitung, Zusammenfassung).
    """
    text = volltext or ""
    gekuerzt = False
    if len(text) > hoechstens:
        kopf = int(hoechstens * 0.6)
        fuss = hoechstens - kopf
        text = (text[:kopf] + "\n\n[... Mittelteil ausgelassen ...]\n\n"
                + text[-fuss:])
        gekuerzt = True
    auftrag = (
        "Fasse das folgende Dokument auf Deutsch zusammen.\n\n"
        "Halte dich an diese Vorgaben:\n"
        "1. Beginne mit einem Satz, worum es insgesamt geht.\n"
        "2. Danach die wichtigsten Punkte als Aufzaehlung.\n"
        "3. Nenne nur, was im Text steht. Erfinde nichts und ergaenze "
        "kein Allgemeinwissen.\n"
        "4. Wenn dir der Text unvollstaendig vorkommt, sage das am Ende.\n\n"
        "Dokument: %s\n\n%s" % (_titel_saubern(titel), text))
    return auftrag, gekuerzt


# ============================================================================
#  Auswahlfragen und Negativfragen
#
#  Ein Anwendungsfall ist ein Fragenkatalog aus der Weiterbildung, der aus
#  Auswahlfragen besteht. Vier davon liegen unten als Pruefstueck vor, mit
#  ihren Tippfehlern ("Gram", "Schaniere", "C:" ohne Leerzeichen). Wer die
#  Erkennung an geglaetteten Beispielen baut, baut fuer ein Format, das
#  niemand eintippt.
#
#  Zwei Formate kommen vor:
#      A: Text, B: Text, C: Text        (eine Zeile, kommagetrennt)
#      A: Satz \n B: Satz \n C: Satz    (eigene Zeilen, bis D)
#
#  Bisher antwortete die Anlage bei "tex" inhaltlich richtig ("g/km"),
#  benannte aber den Buchstaben nicht - der Nutzer musste selbst erkennen,
#  dass das B ist. Bei einem Katalog mit hundert Fragen ist das die halbe
#  Arbeit.
# ============================================================================

# Optionen als eigene Zeile. Bis D, weil eine der Pruefstueck-Fragen vier hat.
_OPTION_ZEILE = re.compile(r"^\s*([A-Da-d])\s*[:)]\s*(.+?)\s*$", re.M)

# Optionen in einer Zeile, durch Komma getrennt. Der Vorgriff sorgt dafuer,
# dass ein Komma INNERHALB einer Option (".. Garn, das .." ) nicht trennt -
# getrennt wird nur, wo der naechste Buchstabe folgt.
# Inline auch mit Punkt/Semikolon vor dem naechsten Buchstaben und mit
# Kleinbuchstaben: "A) ... . B) ... . C) ..." (Pruefungskatalog, 26.08.).
_OPTION_REIHE = re.compile(
    r"\b([A-Da-d])\s*[:)]\s*(.+?)(?=\s*[,;.]?\s*\b[A-Da-d]\s*[:)]\s*\S|\s*$)")


def optionen_finden(frage):
    """Zieht die Auswahlmoeglichkeiten aus der Frage.

    Rueckgabe [(Buchstabe, Text), ...] oder [] wenn es keine Auswahlfrage
    ist. Verlangt mindestens zwei Optionen - ein einzelnes "A:" ist eher
    eine Aufzaehlung als eine Auswahl.
    """
    text = (frage or "")
    zeilen = _OPTION_ZEILE.findall(text)
    if len(zeilen) >= 2:
        raus = [(b.upper(), t.strip().rstrip(",;.")) for b, t in zeilen]
    else:
        # Nur die Zeilen absuchen, die ueberhaupt ein "A:" tragen - sonst
        # zerlegt der Ausdruck auch den Fragesatz.
        raus = []
        for zeile in text.splitlines():
            if not re.search(r"\b[A-Da-d]\s*[:)]\s*\S", zeile):
                continue
            for b, t in _OPTION_REIHE.findall(zeile):
                raus.append((b.upper(), t.strip().rstrip(",;.")))
        if len(raus) < 2:
            return []
    # Buchstaben muessen aufsteigend und ohne Wiederholung kommen. Sonst
    # ist es kein Katalog, sondern Zufall - etwa eine Formel "A: B" im Text.
    buchstaben = [b for b, _ in raus]
    if buchstaben != sorted(set(buchstaben)):
        return []
    if not all(t for _, t in raus):
        return []
    return raus


def frageteil(frage):
    """Der Fragesatz ohne die Optionen.

    Fuer die Suche ist "Was ist keine Aufgabe des Extruders" brauchbar,
    "A: Material aufschmelzen, B: ..." verwaessert sie nur.
    """
    text = (frage or "")
    ohne = _OPTION_ZEILE.sub("", text)
    zeilen = []
    for zeile in ohne.splitlines():
        if re.match(r"^\s*[A-D]\s*[:)]\s*\S", zeile):
            continue
        zeilen.append(zeile)
    return " ".join(" ".join(zeilen).split()).strip()


# Negation, die den Fragesatz selbst umdreht: Fragewort, Kopula, Negation.
#
# ⚠ Die Falle steckt in einem echten Bestandsbeispiel: "Wie weist man NICHT
# SICHTBARE Fehlstellen in Bauteilen nach?" ist KEINE Negativfrage - dort
# beschreibt "nicht" ein Attribut des Gesuchten. Wer nur auf "nicht" prueft,
# dreht diese Frage um und sucht das Falsche. Deshalb muss die Negation
# direkt hinter dem Kopulaverb des Fragesatzes stehen.
_NEGATIV = re.compile(
    r"\b(?:was|welche[rsn]?|welches)\b\s+"
    r"(?:\w+\s+){0,2}?"
    r"\b(?:ist|sind|war|waren|gehoert|gehört|gehoeren|gehören|zaehlt|zählt|"
    r"zaehlen|zählen|trifft|treffen|gilt|gelten|stellt|darf|duerfen|dürfen|"
    r"kann|koennen|können|wird|werden)\b\s+"
    r"(?:\w+\s+){0,1}?"
    r"\b(?:nicht|kein|keine|keinen|keiner|keines|keinem|niemals|nie)\b",
    re.I)


def ist_negativfrage(frage):
    """Verlangt die Frage das, was NICHT zutrifft?

    Geprueft an vier echten Katalogfragen: nur "Was ist keine Aufgabe des
    Extruders?" schlaegt an, die drei anderen nicht - und die
    Fehlstellen-Frage mit ihrem attributiven "nicht sichtbare" ebenfalls
    nicht.
    """
    return bool(_NEGATIV.search(frageteil(frage) or ""))


def negativ_umdrehen(frage):
    """Aus der Negativfrage die positive Suchform machen.

    "Was ist keine Aufgabe des Extruders?" -> "Aufgabe des Extruders".
    Die Anlage kann nachschlagen, nicht schlussfolgern. Also schlaegt sie
    nach, was die Aufgaben SIND, und der Abgleich mit den Optionen
    erledigt den Rest.
    """
    text = frageteil(frage)
    ohne = _NEGATIV.sub(" ", text)
    ohne = re.sub(r"^\s*(?:was|welche[rsn]?|welches)\b", " ", ohne, flags=re.I)
    ohne = re.sub(r"\b(?:ist|sind|gehoert|gehört|zaehlt|zählt|trifft|gilt)\b",
                  " ", ohne, flags=re.I)
    ohne = ohne.replace("?", " ")
    woerter = [w for w in ohne.split() if _flach(w) not in _FUELLWORT]
    return " ".join(woerter).strip()


def optionen_belegt(optionen, quellen, mindestens=2):
    """Welche Optionen kommen in den Fundstellen vor, welche nicht?

    Rueckgabe (belegt, offen) - je Liste die Buchstaben.

    Gezaehlt werden die INHALTSWOERTER einer Option. "Material trocknen"
    gilt als belegt, wenn beide Woerter im Fundstellentext auftauchen; bei
    laengeren Optionen genuegt die Mehrheit, sonst scheitert jeder ganze
    Satz an einem einzigen Wort.
    """
    # Auch hier _wortflach: sonst gilt "Gram" als belegt, weil irgendwo
    # "Gramm" steht - und bei einer Negativfrage entscheidet genau das
    # ueber die Antwort.
    heu = _wortflach(" ".join(
        (q.get("text") or "") + " " + (q.get("title") or "")
        for q in (quellen or [])))
    if not heu.strip():
        return [], [b for b, _ in optionen]
    belegt, offen = [], []
    for b, t in optionen:
        woerter = [w for w in re.findall(r"\w{4,}", t)
                   if _flach(w) not in _FUELLWORT]
        if len(woerter) < 1:
            offen.append(b)
            continue
        treffer = sum(1 for w in woerter if _wort_drin(w, heu))
        # Kurze Optionen muessen ganz belegt sein, lange zur Haelfte.
        noetig = len(woerter) if len(woerter) <= mindestens \
            else max(mindestens, (len(woerter) + 1) // 2)
        (belegt if treffer >= noetig else offen).append(b)
    return belegt, offen


def negativ_schluss(optionen, quellen):
    """Der ehrliche Schluss bei einer Negativfrage.

    Wenn genau eine Option unbelegt bleibt, ist sie die gesuchte. Das ist
    ein Schluss aus dem Nichtfinden - und der wird ausdruecklich als
    solcher benannt. Nicht gefunden ist kein Beweis fuer nicht vorhanden,
    und die Anlage darf das nicht verwischen.
    """
    if not optionen:
        return ""
    belegt, offen = optionen_belegt(optionen, quellen)
    text = dict(optionen)

    if len(offen) == 1 and belegt:
        b = offen[0]
        return ("**Hinweis zur Auswahl.** Die Frage verlangt das, was *nicht* "
                "zutrifft — die Anlage kann nachschlagen, nicht schließen. "
                "Deshalb der Abgleich mit den Fundstellen:\n\n"
                + "\n".join("- **%s** (%s) — in den Fundstellen belegt"
                            % (x, text.get(x, "")) for x in belegt)
                + "\n- **%s** (%s) — in den Fundstellen **nicht** belegt"
                  % (b, text.get(b, ""))
                + "\n\nDemnach ist **%s** die gesuchte Antwort. "
                  "⚠ Das ist ein Schluss daraus, dass sich nichts finden "
                  "ließ — kein Nachweis, dass es die Aussage nicht gibt. "
                  "Bitte kurz gegenprüfen." % b)

    # Kein eindeutiges Bild: SCHWEIGEN. Ein "nicht eindeutig" unter einer
    # sauberen, belegten Antwort ist kein Hinweis, sondern ein Widerspruch
    # - genau das passierte bei der Extruder-Frage. Die Antwort
    # darueber war richtig und vierfach belegt; der Nachtrag stellte sie in
    # Frage, weil im Beleg "Einbringen" statt "Einarbeiten" stand.
    return ""


_ALLE = re.compile(r"^\W*(alle[sn]?|beide|jedes|samtliche|sämtliche|"
                   r"alle\s+(davon|zusammen)|alle\s+dokumente)\W*$", re.I)


def ist_alle_wahl(frage):
    """Antwortet jemand auf die Rueckfrage mit "alle" statt einem Titel?

    Beobachtet: Auf "Dazu passen mehrere Dokumente. Welches
    meinst du?" kam "alle" - und lief als gewoehnliche Suche, worauf das
    Modell zu Recht ratlos antwortete ("es wurde lediglich der Befehl
    'alle' uebermittelt").

    Bewusst NICHT geloest, indem alle Treffer zusammengefasst werden: Das
    waeren im gemessenen Fall fuenf Dokumente mit zusammen ueber 600
    Seiten in einem Durchgang. Was dabei herauskaeme, waere kuerzer als
    jede Einzelfassung und ungenauer als alle zusammen.
    """
    return bool(_ALLE.match((frage or "").strip()))


def alle_nicht_moeglich(kandidaten):
    """Die Antwort auf "alle" - mit den Titeln, damit der naechste Schritt
    ohne Zurueckblaettern moeglich ist."""
    liste = "\n".join("- %s" % _titel_saubern(k) for k in (kandidaten or [])[:10])
    return ("Zusammengefasst wird ein Dokument nach dem anderen — jede "
            "Zusammenfassung liest das vollständige Werk, und fünf davon "
            "in einem Zug ergäben nur einen groben Überblick über alles "
            "und nichts.\n\nNenne bitte eines davon:\n\n%s\n\n"
            "Wenn du stattdessen einen bestimmten Punkt über alle hinweg "
            "suchst, frag danach — dann wird in allen gesucht und jede "
            "Fundstelle belegt." % liste)


def negativ_ohne_optionen(frage, abgelehnt=False):
    """Der Hinweis fuer eine Verneinung OHNE vorgegebene Antwortmoeglichkeiten.

    "Was ist keine Aufgabe des Extruders?" wurde als
    Negativfrage erkannt und die Suche richtig umgedreht - aber der ganze
    Nachtrags-Zweig hing an `optionen`, und die gibt es hier nicht.

    An drei Laeufen gemessen: Das Modell lehnt solche Fragen
    fast immer ab ("keine belastbare Information", unter Berufung auf
    Regel 2 des Systemprompts). Die eine positive Antwort, die beobachtet
    wurde, war der Ausreisser - und die irrefuehrendere Variante, weil sie
    aufzaehlt, was der Extruder TUT.

    Deshalb erscheint der Hinweis in BEIDEN Faellen. Bei der Ablehnung ist
    er sogar der wichtigere: "Keine belastbare Information" ist dort
    sachlich richtig, aber ohne Begruendung sieht es nach einer Wissens-
    luecke aus - dabei liegt es an der Form der Frage.

    Was hier ausdruecklich NICHT passiert: das Modell aufzufordern,
    Gegenbeispiele zu formulieren. Es gibt unendlich viele Dinge, die
    keine Aufgabe des Extruders sind; jede solche Aufzaehlung waere
    unbelegt und stuende gegen die Grundregel der ganzen Anlage.
    """
    if abgelehnt:
        return ("**Hinweis zur Verneinung.** Die Frage zielt darauf, was "
                "*nicht* zutrifft — und das lässt sich aus Fundstellen "
                "nicht belegen: Die Unterlagen beschreiben, was ist, nicht "
                "was nicht ist. Dass hier keine Antwort zustande kommt, "
                "liegt an der Form der Frage und nicht zwangsläufig an "
                "einer Lücke im Bestand. Zwei Wege weiter: nach dem fragen, "
                "was zutrifft — oder, wenn die Frage aus einem Katalog "
                "stammt, die Antwortmöglichkeiten mit angeben. Dann wird "
                "jede einzeln geprüft.")
    return ("**Hinweis zur Verneinung.** Die Frage zielt darauf, was "
            "*nicht* zutrifft. Belegt ist oben, was zutrifft — was dort "
            "fehlt, ist damit nicht als zutreffend belegt. Das ist ein "
            "Schluss aus dem Nichtfinden, kein Beleg: Ohne vorgegebene "
            "Antwortmöglichkeiten lässt sich eine Verneinung nicht "
            "abschließend belegen. Stehen im Fragenkatalog Möglichkeiten "
            "zur Wahl, bitte mit angeben — dann wird jede einzeln geprüft.")


def auswahl_nachtrag(optionen, buchstaben, begruendung=""):
    """Die Zeile, die die zutreffenden Buchstaben benennt.

    Nimmt einen Buchstaben oder eine Liste. Getrennt vom Rest, damit im
    Fragenkatalog auf einen Blick steht, was anzukreuzen ist.

    Mehrfachauswahl ist der Regelfall, nicht die Ausnahme: Bei einer Frage
    aus dem Katalog trafen B und C zu, genannt wurde nur B.
    """
    if isinstance(buchstaben, str):
        buchstaben = [buchstaben] if buchstaben else []
    buchstaben = [b.upper() for b in buchstaben if b]
    if not buchstaben:
        return ("**Zur Auswahl.** Keine der genannten Möglichkeiten deckt "
                "sich mit dem, was sich belegen ließ. Bitte prüfen, ob die "
                "richtige Antwort im Fragenkatalog fehlt.")
    text = dict(optionen)
    if len(buchstaben) == 1:
        b = buchstaben[0]
        zeile = "**Antwort: %s**" % b
        if text.get(b):
            zeile += " — %s" % text[b]
    else:
        zeile = "**Antwort: %s**" % " und ".join(buchstaben)
        teile = ["**%s** %s" % (b, text.get(b, "")) for b in buchstaben
                 if text.get(b)]
        if teile:
            zeile += "\n\n" + "\n".join("- " + t for t in teile)
    if begruendung:
        zeile += "\n\n%s" % begruendung
    return zeile


# ============================================================================
#  Ablehnung mit offenen Karten
#
#  Bisher endete eine erfolglose Suche bei "Dazu finde ich keine belastbare
#  Information." Das ist ehrlich, aber eine Sackgasse: Der Nutzer erfaehrt
#  nicht, ob die Anlage am Thema vorbeigesucht hat oder ob im Bestand
#  wirklich nichts steht. Beides sieht gleich aus, verlangt aber
#  Verschiedenes - anders formulieren oder aufhoeren.
# ============================================================================

_ABLEHNUNG = re.compile(
    r"(keine\s+belastbare\s+information|"
    r"finde\s+ich\s+(?:dazu\s+)?(?:leider\s+)?nichts|"
    r"liegen\s+(?:mir\s+)?keine\s+(?:informationen|angaben|unterlagen)|"
    r"lie(?:ss|ß)\s+sich\s+nichts\s+finden|"
    r"in\s+den\s+(?:vorliegenden\s+)?unterlagen\s+nicht)", re.I)


def ist_ablehnung(antwort):
    """Hat die Anlage abgelehnt? Nur der Anfang zaehlt.

    Eine ausfuehrliche Antwort, die am Ende eine Einzelheit offenlaesst
    ("zur Nachbehandlung liegen keine Angaben vor"), ist keine Ablehnung.
    Deshalb wird nur der erste Abschnitt geprueft.
    """
    text = (antwort or "").strip()
    if not text:
        return False
    # Nur der ERSTE Satz. Ein Vorbehalt am Ende einer richtigen Antwort
    # ("zur Nachbehandlung liegen keine Angaben vor") ist kein Fehlschlag,
    # sondern gehoert zur Ehrlichkeit der Anlage - er darf nicht dazu
    # fuehren, dass unter eine belegte Antwort "hier stand sie nicht"
    # geschrieben wird.
    ende = len(text)
    for zeichen in (". ", ".\n", "!\n", "?\n", "\n\n"):
        stelle = text.find(zeichen)
        if 0 < stelle < ende:
            ende = stelle + 1
    erster = text[:ende]
    if not _ABLEHNUNG.search(erster):
        return False
    # Steht nach der Ablehnung noch viel Text, hat die Anlage doch etwas
    # geliefert - etwa eine Rueckfrage mit Vorschlaegen. Dann ist der
    # Hinweis auf die Fundstellen ueberfluessig.
    return len(text) - len(erster) < 600


def trotzdem_gefunden(antwort, quellen, hoechstens=5):
    """Zeigt bei einer Ablehnung, wo die Anlage nachgesehen hat.

    Damit wird aus der Sackgasse ein naechster Schritt: Der Nutzer sieht,
    ob die Suche im richtigen Umfeld war, und kann mit einem Fachbegriff
    aus den gefundenen Titeln nachfassen.
    """
    if not ist_ablehnung(antwort):
        return ""
    titel = []
    for q in (quellen or []):
        t = _titel_saubern(q.get("title") or q.get("docSource") or "")
        if t and t not in titel:
            titel.append(t)
    if not titel:
        return ("**Nachgesehen wurde nichts.** Die Suche hat keine einzige "
                "Fundstelle geliefert — das deutet darauf hin, dass der "
                "Begriff im Bestand gar nicht vorkommt, nicht nur die "
                "Antwort.")
    rest = len(titel) - hoechstens
    liste = "\n".join("- %s" % t for t in titel[:hoechstens])
    if rest > 0:
        liste += "\n- … und %d weitere" % rest
    # ⚠ Gekuerzt: Die Belehrung, wie man eine Frage besser stellt,
    #   ist weg - der Hinweis, WO gesucht wurde, bleibt. Der ist die
    #   eigentliche Auskunft.
    return ("**Durchsucht wurden unter anderem:**\n\n%s\n\n"
            "*Ein Fachbegriff aus diesen Titeln führt meist weiter.*"
            % liste)


def negativ_suchtext(frage):
    """Womit bei einer Negativfrage gesucht wird.

    Die positive Fragefform allein reicht nicht. "Aufgabe Extruders"
    findet die Aufgaben im Allgemeinen, aber der Abgleich braucht
    Fundstellen zu JEDER einzelnen Option - sonst gilt eine Option als
    unbelegt, nur weil die Suche sie nie angesehen hat. Genau dieser
    Fehler wuerde die falsche Antwort erzeugen und dabei ueberzeugt
    aussehen.

    Deshalb wandern die Optionstexte in die Suchanfrage.
    """
    teile = []
    kern = negativ_umdrehen(frage)
    if kern:
        teile.append(kern)
    for _, t in optionen_finden(frage):
        teile.append(t)
    return " ".join(" ".join(teile).split())[:400]


def option_zur_antwort(optionen, antwort):
    """Welche Option deckt sich mit der belegten Antwort?

    Rueckgabe (Buchstabe, sicher). "sicher" ist False, wenn zwei Optionen
    gleich gut passen oder keine ueberzeugt - dann lohnt die Rueckfrage
    beim Sprachmodell.

    Der Abgleich zaehlt Inhaltswoerter. Bei "tex" antwortet die Anlage
    "Gramm pro Kilometer Garn" und Option B lautet genauso - das findet
    die Regel. Steht in der Antwort dagegen nur "g/km", findet sie nichts,
    und das Modell wird gefragt. Einheiten in Kurzform sind der Grund,
    warum es den zweiten Weg ueberhaupt gibt.
    """
    # _wortflach, nicht _flach: fuer Wortvergleiche braucht es Grenzen.
    heu = _wortflach(antwort or "")
    if not heu.strip() or not optionen:
        return "", False
    punkte = []
    for b, t in optionen:
        woerter = [w for w in re.findall(r"\w{4,}", t)
                   if _flach(w) not in _FUELLWORT]
        if not woerter:
            punkte.append((0.0, b))
            continue
        # An Wortgrenzen, nicht als Teilstring. Sonst zaehlt "Gram"
        # (Tippfehler in Option A) als Treffer in "Gramm" aus Option B,
        # beide Optionen kommen sich nahe und die Zuordnung scheitert an
        # einem fremden Schreibfehler.
        treffer = sum(1 for w in woerter if _wort_drin(w, heu))
        punkte.append((treffer / float(len(woerter)), b))
    punkte.sort(reverse=True)
    beste, zweite = punkte[0], (punkte[1] if len(punkte) > 1 else (0.0, ""))
    # Mindestens zwei Drittel der Woerter muessen vorkommen, und die
    # zweitbeste Option muss deutlich zurueckliegen. Ein knappes Rennen
    # zwischen zwei Optionen ist kein Ergebnis, sondern ein Zufall.
    if beste[0] >= 0.66 and beste[0] - zweite[0] >= 0.34:
        return beste[1], True
    return "", False


def auswahl_auftrag(frage, antwort, optionen):
    """Der Auftrag ans Sprachmodell, wenn die Regel nicht ausreicht.

    Bewusst eng gefuehrt: Das Modell soll NICHT die Frage beantworten -
    das ist schon geschehen, mit Belegen. Es soll nur zuordnen, welche der
    vorgegebenen Moeglichkeiten der belegten Antwort entspricht. Damit
    kann es auch nichts hinzuerfinden.
    """
    liste = "\n".join("%s: %s" % (b, t) for b, t in optionen)
    return ("Unten steht eine belegte Fachantwort und darunter mehrere "
            "vorgegebene Moeglichkeiten.\n\n"
            "Deine einzige Aufgabe: Sage, welche Moeglichkeiten der "
            "Antwort entsprechen.\n\n"
            "Es koennen mehrere zutreffen. Antworte NUR mit den "
            "Buchstaben, durch Komma getrennt (Beispiel: B, C). Passt "
            "keine, antworte KEINE. Schreibe nichts weiter - keine "
            "Begruendung, keinen Satz.\n\n"
            "FRAGE:\n%s\n\nBELEGTE ANTWORT:\n%s\n\n"
            "MOEGLICHKEITEN:\n%s\n\nBuchstabe:"
            % (frageteil(frage)[:300], (antwort or "")[:2500], liste))


def buchstaben_lesen(modellantwort, optionen):
    """Zieht ALLE genannten Buchstaben aus der Modellantwort.

    Rueckgabe eine Liste in der Reihenfolge der Optionen, oder [].

    Mehrfachauswahl kommt im Pruefungskatalog regelmaessig vor: Bei
    "Welche sind kunststoffspezifische Features?" trafen B und C zu,
    genannt wurde nur B - weil die Auswertung nur einen
    Buchstaben kannte.

    Gelesen wird nur der Anfang der Modellantwort, und nur Buchstaben, die
    es in dieser Frage wirklich gibt.
    """
    erlaubt = [b for b, _ in optionen]
    kopf = (modellantwort or "").strip()[:120].upper()
    if re.match(r"^(KEINE|NONE|KEIN)\b", kopf):
        return []
    gefunden = {m.group(1) for m in re.finditer(r"\b([A-D])\b", kopf)}
    # Reihenfolge der Frage beibehalten, nicht die der Nennung
    return [b for b in erlaubt if b in gefunden]


def buchstabe_lesen(modellantwort, optionen):
    """Nur der erste Buchstabe - fuer Aufrufer, die einen einzelnen wollen."""
    raus = buchstaben_lesen(modellantwort, optionen)
    return raus[0] if raus else ""


def _wortflach(text):
    """Wie _flach, aber Wortgrenzen bleiben erhalten.

    _flach loescht jedes Trennzeichen und macht aus "Gramm pro Kilometer"
    ein "grammprokilometer". Das ist fuer Titelvergleiche gewollt, macht
    aber jeden Wortvergleich unmoeglich: "Gram" steckt dann in "Gramm",
    "Garn" in "Garnitur".

    Hier werden Trennzeichen zu Leerzeichen. Vorn und hinten steht je
    eines, damit sich ein Wort mit " wort " suchen laesst - das ist eine
    Wortgrenzenpruefung, die keinen regulaeren Ausdruck braucht.
    """
    t = (text or "").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " " + " ".join(t.split()) + " "


def _wort_drin(wort, heuhaufen_wortflach):
    """Kommt das Wort als eigenes Wort vor?"""
    w = _wortflach(wort).strip()
    return bool(w) and (" %s " % w) in heuhaufen_wortflach


def negativ_auftrag(frage, antwort, optionen):
    """Der Auftrag ans Modell bei einer Negativfrage.

    Die Frage ist zu diesem Zeitpunkt schon beantwortet, mit Fundstellen
    und Belegen. Das Modell soll nur noch sagen, welche Moeglichkeit die
    Antwort als NICHT zutreffend ausweist.

    Warum nicht selbst rechnen: Bei der Extruder-Frage stand im Beleg "das
    Einbringen von Additiven", in der Option aber "Einarbeiten von
    Additiven". Eine Wortzaehlung haelt das fuer unbelegt, ein Leser nicht.
    """
    liste = "\n".join("%s: %s" % (b, t) for b, t in optionen)
    return ("Unten steht eine belegte Fachantwort auf eine Frage, die nach "
            "dem Nichtzutreffenden verlangt.\n\n"
            "Deine einzige Aufgabe: Sage, welche der Moeglichkeiten die "
            "Antwort als NICHT zutreffend ausweist.\n\n"
            "Antworte mit GENAU EINEM Buchstaben. Geht das aus der Antwort "
            "nicht hervor, antworte KEINE. Schreibe nichts weiter.\n\n"
            "FRAGE:\n%s\n\nBELEGTE ANTWORT:\n%s\n\n"
            "MOEGLICHKEITEN:\n%s\n\nBuchstabe:"
            % (frageteil(frage)[:300], (antwort or "")[:3000], liste))


# ============================================================================
#  Widerspruchspruefung: sagt der Fliesstext das Gegenteil seines Belegs?
#
#  Gemeldet wurde eine Antwort, die im Fliesstext
#  behauptete:
#
#      "... dass bei diesen Werkstoffen die ERHOEHUNG der Materialkosten
#       der Matrixwerkstoffe nur bedingt zur Senkung der Gesamtkosten
#       beitraegt"
#
#  Im Beleg darunter stand, woertlich und korrekt geprueft:
#
#      "Eine VERRINGERUNG der Materialkosten der Matrixwerkstoffe traegt
#       daher nur bedingt zur Senkung der Gesamtkosten bei."
#
#  Am Original nachgelesen: Der Beleg hat recht, der Fliesstext hatte die
#  Aussage umgedreht.
#
#  DIE LUECKE IST SYSTEMATISCH: Die Belegpruefung schlaegt ZITATE im
#  Quelldokument nach. Was der Fliesstext um die Zitate herum behauptet,
#  wurde nie gegen sie gehalten. Die Anlage versprach damit mehr, als sie
#  prueft - und der Fehler sieht besonders vertrauenswuerdig aus, weil
#  direkt darunter "woertlich im Original gefunden" steht.
#
#  ⚠ Diese Pruefung KORRIGIERT NICHT. Sie warnt und stellt beide Saetze
#  nebeneinander. Ein Automat, der Fachaussagen umschreibt, waere
#  gefaehrlicher als der Fehler, den er behebt.
#
#  ⚠ Und sie muss LEISE sein, wenn sie unsicher ist. Eine Warnung unter
#  einer richtigen Antwort ist schaedlicher als keine - das war schon
#  einmal der Fall, als eine Wortzaehlung eine vierfach belegte
#  Antwort in Zweifel zog.
# ============================================================================

# Gegensatzpaare, wie sie in Verarbeitungstexten vorkommen. Links die
# Richtung "mehr", rechts "weniger" - die Zuordnung ist gleichgueltig,
# geprueft wird nur, ob beide Seiten aufeinandertreffen.
_GEGENSAETZE = [
    ({"erhoehung", "erhoehen", "erhoeht", "steigerung", "steigern",
      "steigert", "zunahme", "zunehmend", "zunimmt", "anstieg", "steigt",
      "steigen", "hoeher", "groesser", "mehr", "verlaengerung",
      "verlaengert"},
     {"verringerung", "verringern", "verringert", "senkung", "senken",
      "senkt", "reduzierung", "reduzieren", "reduziert", "minderung",
      "absenkung", "abnahme", "abnehmend", "abnimmt", "sinkt", "sinken",
      "niedriger", "geringer", "kleiner", "weniger", "verkuerzung",
      "verkuerzt"}),
    ({"vorteil", "vorteile", "vorteilhaft", "guenstig", "geeignet",
      "zulaessig", "erlaubt", "moeglich"},
     {"nachteil", "nachteile", "nachteilig", "unguenstig", "ungeeignet",
      "unzulaessig", "verboten", "untersagt", "unmoeglich"}),
    ({"verbessert", "verbesserung", "verbessern"},
     {"verschlechtert", "verschlechterung", "verschlechtern"}),
    ({"schneller", "beschleunigt", "beschleunigung"},
     {"langsamer", "verzoegert", "verzoegerung"}),
    ({"weich", "weicher", "elastisch", "duktil"},
     {"hart", "harter", "sproede", "steif"}),
]


def _worte(text):
    """Inhaltswoerter in Vergleichsform, Reihenfolge erhalten."""
    flach = _wortflach(text)
    return [w for w in flach.split() if w]


# Woerter, die zwischen dem Richtungswort und seinem Bezug stehen duerfen.
_BINDEWORT = {"der", "die", "das", "des", "dem", "den", "von", "vom",
              "eines", "einer", "zur", "zum", "bei", "in", "im", "an",
              "auf", "aus"}


def _bezugswoerter(worte, stelle, weite=3):
    """Worauf bezieht sich das Wort an dieser Stelle?

    ⚠ Ein breites Umfeld taugt dafuer nicht. Der erste Entwurf nahm alle
    laengeren Woerter im Umkreis von sieben - damit teilten "Erhoehung der
    Materialkosten" und "zur Senkung der Gesamtkosten" die Woerter
    "bedingt" und "senkung", und die Pruefung entwarnte sich selbst.
    Umgekehrt fanden zwei voellig verschiedene Saetze zufaellig ein
    gemeinsames Wort und loesten Fehlalarm aus.

    Deutsche Fachsprache stellt diese Woerter fast immer in eine
    Nominalgruppe: ERHOEHUNG der MATERIALKOSTEN, SENKUNG der GESAMTKOSTEN.
    Bezug ist deshalb das naechste laengere Wort dahinter, ueber
    Bindewoerter hinweg. Bei Verben zaehlt auch das Wort davor - "die
    Temperatur steigt".
    """
    raus = set()
    # Nach vorn bis zu ZWEI Inhaltswoerter. Eines genuegt nicht: In
    # "Vorteil der hohen Festigkeit" ist das erste ein Adjektiv, und
    # "hohen" gegen "geringen" hat nichts gemeinsam - gemeint ist beide
    # Mal die Festigkeit.
    genommen = 0
    i = stelle + 1
    schritte = 0
    while i < len(worte) and schritte < weite + 2 and genommen < 2:
        w = worte[i]
        i += 1
        schritte += 1
        if w in _BINDEWORT or len(w) < 5 or w in _FUELLWORT:
            continue
        raus.add(w)
        genommen += 1
    # Nach hinten eines - das Subjekt eines Verbs ("die Temperatur steigt")
    j = stelle - 1
    schritte = 0
    while j >= 0 and schritte < weite:
        w = worte[j]
        j -= 1
        schritte += 1
        if w in _BINDEWORT or len(w) < 5 or w in _FUELLWORT:
            continue
        raus.add(w)
        break
    return raus


def _satz_um(text, wort):
    """Der Satz, in dem ein Wort steht - fuer die Anzeige."""
    flach = _wortflach(text)
    stelle = flach.find(" %s " % wort)
    if stelle < 0:
        return ""
    # Im Originaltext die entsprechende Stelle grob wiederfinden
    anteil = stelle / max(1, len(flach))
    mitte = int(anteil * len(text))
    anfang = max(0, text.rfind(".", 0, mitte) + 1)
    ende = text.find(".", mitte)
    if ende < 0:
        ende = min(len(text), mitte + 220)
    return " ".join(text[anfang:ende + 1].split())[:260]


def widersprueche(fliesstext, pruefungen):
    """Wo widerspricht der Fliesstext einem geprueften Beleg?

    Rueckgabe Liste von (wort_im_text, wort_im_beleg, satz_text,
    satz_beleg). Leer, wenn nichts Eindeutiges gefunden wird.

    Bedingungen, alle drei muessen zutreffen - sonst wird geschwiegen:
      1. Ein Gegensatzpaar trifft aufeinander: eine Seite im Fliesstext,
         die andere im Beleg.
      2. Beide Stellen teilen mindestens ein laengeres Inhaltswort im
         Umfeld. Ohne diesen Bezug waeren "die Temperatur steigt" und "die
         Kosten sinken" ein Widerspruch, obwohl sie von Verschiedenem
         reden.
      3. Das Gegenwort steht NICHT ebenfalls im Fliesstext. Nennt der Text
         beide Richtungen, referiert er den Beleg vollstaendig.
    """
    if not fliesstext or not pruefungen:
        return []
    t_worte = _worte(fliesstext)
    raus, gesehen = [], set()

    def vorkommen(worte, menge):
        """Jedes Vorkommen eines Wortes aus der Menge, mit seinem Umfeld."""
        return [(w, _bezugswoerter(worte, i))
                for i, w in enumerate(worte) if w in menge]

    for p in pruefungen:
        if p.get("urteil") not in ("woertlich", "geglaettet", "teilweise"):
            continue
        beleg = p.get("original") or ""
        if not beleg:
            continue
        b_worte = _worte(beleg)

        for links, rechts in _GEGENSAETZE:
            for seite_t, seite_b in ((links, rechts), (rechts, links)):
                # ⚠ Der BEZUG entscheidet, nicht das blosse Vorkommen. Im
                # echten Fall stand "Erhoehung der Materialkosten" im Text
                # und "zur Senkung der Gesamtkosten" ebenfalls - eine
                # Pruefung auf "steht das Gegenwort irgendwo im Text"
                # schwieg deshalb und liess den Widerspruch durch.
                for wt, bezug_t in vorkommen(t_worte, seite_t):
                    if not bezug_t:
                        continue
                    for wb, bezug_b in vorkommen(b_worte, seite_b):
                        gemeinsam = bezug_t & bezug_b
                        if not gemeinsam:
                            continue
                        # Entwarnung nur bei GLEICHEM Bezug: Nennt der Text
                        # die andere Richtung fuer dieselbe Sache, gibt er
                        # den Beleg vollstaendig wieder.
                        entwarnt = False
                        for _, bezug_gegen in vorkommen(t_worte, seite_b):
                            if bezug_gegen & gemeinsam:
                                entwarnt = True
                                break
                        if entwarnt:
                            continue
                        marke = (wt, wb, tuple(sorted(gemeinsam))[:2])
                        if marke in gesehen:
                            continue
                        gesehen.add(marke)
                        raus.append((wt, wb,
                                     _satz_um(fliesstext, wt),
                                     " ".join(beleg.split())[:260]))
    return raus


def widerspruchshinweis(fliesstext, pruefungen):
    """Der Hinweis, der unter die Antwort gehoert. Leer, wenn alles passt."""
    gefunden = widersprueche(fliesstext, pruefungen)
    if not gefunden:
        return ""
    # Vorsichtig formuliert, mit Absicht: Die Pruefung erkennt
    # gegenlaeufige Richtungen bei gleichem Gegenstand. Meistens ist das ein
    # echter Fehler ("Erhoehung" statt "Verringerung"), es
    # koennen aber zwei verschiedene Vorgaenge gemeint sein. Ein Hinweis,
    # der um einen Blick bittet, ist in beiden Faellen richtig - eine
    # Fehlerbehauptung waere es nur im ersten.
    teile = ["**⚠ Text und Beleg gehen auseinander — bitte nachsehen.**",
             "",
             "Die Belegprüfung schlägt Zitate im Original nach, prüft aber "
             "nicht, was der Text *um* die Zitate herum behauptet. Hier "
             "weisen beide in verschiedene Richtungen:"]
    for wt, wb, satz_t, satz_b in gefunden[:3]:
        teile.append("")
        teile.append("- Im Text steht **%s**, im Beleg **%s**." % (wt, wb))
        if satz_t:
            teile.append("  - Text: „%s“" % satz_t)
        if satz_b:
            teile.append("  - Beleg: „%s“" % satz_b)
    teile.append("")
    teile.append("**Im Zweifel gilt der Beleg** — er ist im Original "
                 "nachgeschlagen. Bitte die verlinkte Stelle heranziehen.")
    return "\n".join(teile)


# Eine Quellenangabe des Modells, z. B. "(Quelle: Abschnitt 5.4)".
_QUELLENANGABE = re.compile(r"\(Quelle:[^)]{0,120}\)")
# Die Fussnotenmarke, die eine GEPRUEFTE Fundstelle anzeigt.
_MARKE_NACH = re.compile(r"^[ \t]*(?:⚠️|⚠)?[ \t]*\[\d{1,2}\]")
# Irgendwo in der Zeile - siehe unbelegte_aussagen().
_IRGENDEINE_MARKE = re.compile(r"\[\d{1,2}\]")


def unbelegte_aussagen(fliesstext):
    """Aussagen, die eine Quelle nennen, aber kein Zitat mitbringen.

    Erkennbar daran, dass hinter der Quellenangabe KEINE Fussnotenmarke
    steht: Die Marke setzt die Belegpruefung nur dort, wo sie ein Zitat
    im Original nachgeschlagen hat.

    Zurueck kommt der Satz, in dem die Angabe steht - gekuerzt, damit der
    Hinweis lesbar bleibt.
    """
    raus, gesehen = [], set()
    for m in _QUELLENANGABE.finditer(fliesstext or ""):
        anfang = fliesstext.rfind("\n", 0, m.start()) + 1
        ende = fliesstext.find("\n", m.end())
        zeile = fliesstext[anfang:ende if ende > 0 else len(fliesstext)]

        # Traegt die Zeile IRGENDWO eine Fussnotenmarke, ist die Aussage
        # belegt - auch wenn hinter DIESER Klammer keine steht. Eine
        # Aufzaehlung wie "(Quelle: A) [3] (Quelle: B) [4] (Quelle: C)"
        # gehoert zu einer einzigen, zweifach belegten Aussage.
        if _IRGENDEINE_MARKE.search(zeile):
            continue

        satz = fliesstext[anfang:m.start()]
        # Auszeichnung und Aufzaehlungszeichen weg - gelesen wird der Satz,
        # nicht das Markdown.
        satz = satz.replace("**", "").replace("*", "")
        satz = re.sub(r"^\s*(?:\d{1,2}[.)]|[-•])\s*", "", satz)
        satz = " ".join(satz.split()).strip(" :–-")
        if len(satz) < 12 or satz in gesehen:
            continue
        gesehen.add(satz)
        raus.append(satz[:150])
    return raus


def unbelegt_hinweis(fliesstext):
    """Der Hinweis, der unter die Antwort gehoert. Leer, wenn alles belegt."""
    offen = unbelegte_aussagen(fliesstext)
    if not offen:
        return ""
    # Bewusst zurueckhaltend formuliert: Die Aussage kann richtig sein. Was
    # fehlt, ist der Nachweis - und genau das steht hier, nicht mehr.
    # ⚠ Gekuerzt: Die Aufzaehlung der Aussagen im Wortlaut ist weg.
    #   Sie stehen bereits oben in der Antwort - sie ein zweites Mal zu
    #   zitieren verdoppelte den Text und erklaerte nichts. Die ZAHL bleibt,
    #   denn sie ist die Warnung.
    # ⚠ GANZ ENTFERNT. Die blosse Zahl ("Welche 5 Aussagen denn?") ist nicht
    #   handhabbar; MIT den Aussagen im Wortlaut war es zu lang. Beides
    #   falsch, also keins von beidem: "Antworten koennen Fehler enthalten"
    #   deckt es ab, und jede Aussage ohne Zitat traegt ohnehin keine
    #   Fundstelle.
    #   Die Funktion bleibt - unbelegte_aussagen() wird im Protokoll noch
    #   gebraucht.
    return ""
