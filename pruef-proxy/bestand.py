"""Was liegt im Regal? Titel, Verfasser, Jahr und Art je Arbeit.

⛔ WOZU: Auf die Frage "Welche Dissertationen haben wir im Bestand? nenne
   mir alle Namen und deren Titel auf" kamen 17 nackte Kennungen -
   von 144 Dissertationen im Bestand, ohne einen einzigen Titel.

   Der Grund ist grundsaetzlich, nicht eine Einstellung: Wer sagt "hol nur
   25 Zettel von 6.494.535 Zetteln", bekommt auch nur 25 durch.

   Die Aehnlichkeitssuche beantwortet INHALTSFRAGEN ("was steht
   ueber X drin?") - dafuer reichen 25 gute Textstellen. Eine BESTANDSFRAGE
   ("was liegt bei uns im Regal?") steht auf keiner einzigen Textstelle;
   sie steht im VERZEICHNIS. Auch mit 1000 Zetteln waere die Antwort
   falsch, nur langsamer.

DIE QUELLE: eine Metadaten-Tabelle (je Dokument Titel, Verfasser, Jahr, Art),
aus der der Katalog `bestandsindex.json` gebaut wird. Deckt idealerweise den
ganzen Bestand ab; fehlt zu einer Arbeit ein Eintrag, erscheint sie ohne Titel.

⚠ PROVISORISCH. Die richtige Pflege kommt aus dem Bibliothekssystem ueber
  SRU/Z39.50/OAI-PMH - OPAC ist nur dessen Suchmaske. Bis dahin ist diese
  Datei die Ersatzquelle.

⚠ VORRANG-REGEL: Der Titel des PDFs (also das Cover, die erste Seite oder
  das Impressum) hat Vorrang. Der Katalog ist die
  ZWEITE Quelle. Solange der Titel aus dem PDF noch nicht gelesen wird,
  ist der Katalog die einzige - das steht in der Auskunft dabei.
"""
import json
import os
import re
import threading

VERZEICHNIS = os.environ.get("KI4KI_BESTANDSINDEX") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "bestandsindex.json")

# Die Buchstaben vor der Nummer sagen, um welche ART Arbeit es sich handelt.
# Belegt aus den BLATTNAMEN der Metadatenliste, nicht geraten.
ARTEN = {
    "DS": ("Dissertation", "Dissertationen"),
    "BS": ("Bachelorarbeit", "Bachelorarbeiten"),
    "M": ("Masterarbeit", "Masterarbeiten"),
    "D": ("Diplomarbeit", "Diplomarbeiten"),
    "S": ("Studienarbeit", "Studienarbeiten"),
    "PA": ("Projektarbeit", "Projektarbeiten"),
}

# Wonach jemand fragen koennte -> Kennung. Nur als FILTER, nie als Ausloeser:
# "Hol mir die Dissertation von Max Mustermann" ist eine Inhaltsfrage.
_WORT_ZU_ART = {}
for k, (einzahl, mehrzahl) in ARTEN.items():
    for w in (einzahl, mehrzahl):
        _WORT_ZU_ART[w.lower()] = k
_WORT_ZU_ART.update({
    "doktorarbeit": "DS", "doktorarbeiten": "DS", "promotion": "DS",
    "promotionen": "DS", "diss": "DS",
    "abschlussarbeit": None, "abschlussarbeiten": None,   # mehrere Arten
})

def _aus_datei():
    """Arten und gleichbedeutende Woerter aus wortlisten.txt holen.

    ⚠ Rueckfall auf die eingebauten Werte, wenn die Datei fehlt. In einer
      anderen Installation stehen dort die eigenen Kennungen -
      DS/BS/M sind die dieses Bestands.
    """
    try:
        import wortlisten
        return wortlisten.arten(), wortlisten.wort_zu_art()
    except Exception:
        return None, None


_datei_arten, _datei_woerter = _aus_datei()
if _datei_arten:
    ARTEN = _datei_arten
if _datei_woerter:
    _WORT_ZU_ART = dict(_datei_woerter)
    _WORT_ZU_ART.setdefault("abschlussarbeit", None)
    _WORT_ZU_ART.setdefault("abschlussarbeiten", None)

_ART_MUSTER = re.compile(
    r"\b(%s)\b" % "|".join(sorted(_WORT_ZU_ART, key=len, reverse=True)), re.I)

_GELADEN = None
_SPERRE = threading.Lock()


def laden(pfad=VERZEICHNIS):
    """Verzeichnis einlesen (einmal, dann gemerkt). None, wenn es fehlt."""
    global _GELADEN
    if _GELADEN is not None:
        return _GELADEN
    with _SPERRE:
        if _GELADEN is not None:
            return _GELADEN
        try:
            with open(pfad, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return None
        # Nachschlagen ueber eine Grundform, damit Schreibvarianten treffen
        _GELADEN = {"roh": d, "nach_grund": {}}
        for name, e in d.items():
            _GELADEN["nach_grund"].setdefault(_grund(name), (name, e))
        return _GELADEN


def _grund(n):
    return re.sub(r"[^a-z0-9]", "", str(n).lower())


def kennung(name):
    """Buchstaben vor der Nummer: 'DS-00-000' -> 'DS'. Sonst None."""
    m = re.match(r"([A-Za-z]{1,3})[-_ ]?\d", str(name).strip())
    return m.group(1).upper() if m else None


def art_von(name):
    """Welche Art Arbeit ist das? 'Dissertation' o. ae., sonst None."""
    k = kennung(name)
    return ARTEN[k][0] if k in ARTEN else None


def angaben(name):
    """Titel, Verfasser, Jahr, Art zu einer Arbeit - oder None."""
    d = laden()
    if not d:
        return None
    stamm = str(name)
    if stamm.lower().endswith((".pdf", ".md")):
        stamm = stamm.rsplit(".", 1)[0]
    treffer = d["nach_grund"].get(_grund(stamm))
    if not treffer:
        return None
    _, e = treffer
    # ⚠ ALLES durchreichen, nicht eine handverlesene Auswahl. Wird der
    #   Index um Schlagworte, Autoren und Betreuer erweitert, muss diese
    #   Stelle mitgezogen werden - sonst bekommt die Stichwortsuche immer
    #   eine leere Liste und findet 0 Treffer ueber Schlagworte, obwohl z.B.
    #   15 Arbeiten "Innenmischer" als Schlagwort tragen.
    angabe = dict(e)
    angabe["titel"] = e.get("titel") or ""
    angabe["verfasser"] = e.get("verfasser") or ""
    angabe["jahr"] = e.get("jahr") or ""
    angabe["art"] = art_von(stamm) or e.get("gruppe") or ""
    angabe.setdefault("schlagworte", [])
    return angabe


def gefragte_art(frage):
    """Welche ART ist gemeint? Gibt (Kennung, Wort) zurueck oder (None, None).

    ⚠ NUR ein Filter. Ob es ueberhaupt eine Bestandsfrage ist, entscheidet
      etwas anderes - sonst wuerde "Hol mir die Dissertation von Max
      Mustermann" eine Bestandsliste ausspucken.
    """
    m = _ART_MUSTER.search(frage or "")
    if not m:
        return None, None
    wort = m.group(1).lower()
    return _WORT_ZU_ART.get(wort), wort


def nach_art(namen, kennzeichen):
    """Aus einer Namensliste die einer Art herausfiltern."""
    return [n for n in namen if kennung(n) == kennzeichen]


# ------------------------------------------ Katalog aus dem Dokument fuellen
#
# REGEL (Entscheidung 11.08.): Katalog vor Modell - das Modell fuellt NUR
# Leerstellen. Auf einer frischen Anlage gibt es keinen Katalog; ohne diesen
# Weg staende in jeder Bestandsliste "kein Katalogeintrag". Das kleine Modell
# liest Titel, Verfasser und Jahr vom Deckblatt (gemessen: bei 839 von 1256
# Arbeiten deckungsgleich mit dem Katalog) und der Eintrag wird dauerhaft
# abgelegt - markiert mit quelle="modell", damit ein spaeterer Katalog ihn
# ueberschreiben darf.

_BESTAND_ORDNER = os.environ.get("KI4KI_BESTAND") or "/daten/bestand/documents"
_NETZ_MODELL = os.environ.get("KI4KI_NETZ_MODELL") or "gemma4:e2b"
_NETZ_URL = os.environ.get("KI4KI_NETZ_URL") or "http://nothink-proxy:11435/api/chat"
_NACHTRAG_SPERRE = threading.Lock()
_NACHTRAG_LAEUFT = set()

_DECKBLATT_ANWEISUNG = (
    "Unten stehen die ersten Seiten eines Dokuments (Deckblatt, Impressum, "
    "Titelseite) - eine wissenschaftliche Arbeit, eine Norm oder Richtlinie, ein "
    "Lehrgang, ein Handbuch, ein Bericht, eine Praesentation oder eine Tabelle. "
    "Der Text kann durch Texterkennung zerhackt sein (Wortreste, einzelne "
    "Buchstaben) - ueberspringe solche Stellen und nimm die naechste lesbare. "
    "Lies daraus den TITEL des Dokuments, wie er auf der Titelseite steht (bei "
    "Lehrgaengen z.B. 'DVS-Lehrgang Fachmann fuer Kunststofflaminierer und "
    "-kleber nach DVS 2213-1'; bei Normen Nummer und Titel), den VERFASSER (bei "
    "'Autoren:'/'Verfasser:' die genannten Personen, sonst die herausgebende "
    "Organisation - nicht Betreuer oder Gutachter) und das JAHR (Auflage, "
    "Copyright oder Abgabe; bei Spannen wie '1980 - 2026' das letzte Jahr). "
    "Der Dateiname ist KEIN Titel. Ist kein Titel lesbar, lass ihn leer. "
    "Antworte NUR mit einer JSON-Zeile der Form "
    '{"titel": "...", "verfasser": "...", "jahr": "..."}. Nichts erfinden.')


def _wurzel_des_dokuments(name):
    """dokumente/<bereich> zu einem Bestandsdokument (ueber den Ablageordner) - oder None."""
    stamm = str(name)
    if stamm.lower().endswith((".pdf", ".md")):
        stamm = stamm.rsplit(".", 1)[0]
    ziel = _grund(stamm)
    eingang = os.environ.get("KI4KI_EINGANG") or "/daten/eingang"
    for wurzel, _, dateien in os.walk(_BESTAND_ORDNER):
        for d in dateien:
            if d.endswith(".json") and _grund(d.split(".md-")[0]) == ziel:
                bereich = os.path.basename(wurzel)
                return os.path.join(eingang, bereich) if bereich and bereich != os.path.basename(_BESTAND_ORDNER) else None
    return None


def _volltext_anfang(name, zeichen=4000, ab_inhalt=False):
    """Der Anfang des aufbereiteten Textes - oder ''. ab_inhalt=True: ohne den
    Kopf der Aufnahme (dessen '# Dateiname' hielt das Modell fuer den Titel,
    gemessen 28.08.: 'DVS 2213-1_neu' statt 'DVS-Lehrgang Fachmann fuer
    Kunststofflaminierer und -kleber')."""
    stamm = str(name)
    if stamm.lower().endswith((".pdf", ".md")):
        stamm = stamm.rsplit(".", 1)[0]
    ziel = _grund(stamm)
    for wurzel, _, dateien in os.walk(_BESTAND_ORDNER):
        for d in dateien:
            if not d.endswith(".json"):
                continue
            if _grund(d.split(".md-")[0]) != ziel:
                continue
            try:
                with open(os.path.join(wurzel, d), encoding="utf-8") as f:
                    t = json.load(f).get("pageContent") or ""
                if ab_inhalt:
                    i = t.find("## Inhalt")
                    if i >= 0:
                        t = t[i + len("## Inhalt"):]
                    t = re.sub(r"<!-- image -->\s*", "", t)
                return t[:zeichen]
            except Exception:
                return ""
    return ""


def _json_aus(inhalt):
    """Titel/Verfasser/Jahr aus der Modellantwort - oder None."""
    m = re.search(r"\{.*?\}", inhalt or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    titel = titel_bereinigen(str(d.get("titel") or ""))
    if len(titel) < 8 or len(titel.split()) < 2:
        return None          # zu kurz/allgemein ("Leitfaden") - dann bleibt der Dateiname
    if re.search(r"\.(?:pdf|md|xlsx|docx)$", titel, re.I) or re.search(r"_\w+_\d", titel):
        return None          # das ist ein Dateiname, kein Titel
    jahre = re.findall(r"(?:19|20)\d{2}", str(d.get("jahr") or ""))
    return {"titel": titel[:300],
            "verfasser": re.sub(r"\s+", " ", str(d.get("verfasser") or "")).replace("nicht angegeben", "").strip()[:120],
            "jahr": jahre[-1] if jahre else ""}          # "1980 - 2026" -> 2026


_ENGLISCHER_ANHANG = re.compile(
    r"^(.{25,}?)\s+(?=(?:Investigation|Analysis|Development|Influence|Prediction|Design|Geometry-dependent|"
    r"Material-Specific|Contactless|Non-contact|Experimental|Numerical|Effect|Characteri[sz]ation|Simulation|Modell?ing|"
    r"A |An |The |Towards|On the|Adjoint)\b)")


def titel_bereinigen(titel):
    """Titel glaetten: Whitespace, Anfuehrungszeichen, und bei zweisprachigen
    Deckblaettern (IKV: deutscher Titel + englische Uebersetzung) nur den
    ersten Teil (gemessen 28.08.: 'Untersuchung ... Modell Investigation of the
    Influence ...' in einer Zelle)."""
    t = re.sub(r"\s+", " ", titel or "").strip().strip("„“\"'")
    m = _ENGLISCHER_ANHANG.match(t)
    if m and re.search(r"\b(?:of|for|on|and|the|in)\b", t[m.end(1):]) and not re.search(r"\b(?:der|die|das|und|von|für|fuer)\b", t[m.end(1):]):
        t = m.group(1).strip()
    return t


_ENGLISCH = re.compile(r"(?i)\b(?:and|of|the|behavio[u]r|processing|fib(?:er|re)|analysis|strength|reinforced|design|"
                       r"optimi[sz]ation|materials?|properties|manufacturing|mou?lding|flow|clamping|springs?|loading|"
                       r"reduction|construction|printing|composites?|thermosets?|elements?|mixing|simulation|damage|"
                       r"technology|channels?|plastics?|polymers?|surface|waviness|rate)\b|ing$|tion$|ity$")


def _englisch(worte):
    treffer = sum(1 for w in worte if _ENGLISCH.search(w or "") and not re.search(r"[äöüßÄÖÜ]", w or ""))
    return treffer >= max(2, len(worte) // 2)


def _themen_uebersetzen(worte):
    """Englische Schlagworte eines deutschen Dokuments eindeutschen (kleines
    Modell, ein Aufruf, ~1 s). Liefert die Liste oder None."""
    try:
        from urllib.request import Request, urlopen
        leib = json.dumps({"model": _NETZ_MODELL, "think": False, "stream": False,
                           "options": {"temperature": 0},
                           "messages": [{"role": "user", "content":
                                         "Uebersetze diese Fachbegriffe ins Deutsche (Kunststofftechnik). Antworte NUR mit einer "
                                         "JSON-Liste von Strings in derselben Reihenfolge, deutsche Begriffe unveraendert lassen:\n"
                                         + json.dumps(worte, ensure_ascii=False)}]}).encode("utf-8")
        a = Request(_NETZ_URL, data=leib, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(a, timeout=60) as r:
            antwort = json.loads(r.read())
        inhalt = ((antwort.get("message") or {}).get("content") or "")
        m = re.search(r"\[.*\]", inhalt, re.S)
        neu = json.loads(m.group(0)) if m else None
        if isinstance(neu, list) and len(neu) == len(worte) and all(isinstance(x, str) and x.strip() for x in neu):
            return [re.sub(r"\s+", " ", x).strip()[:40] for x in neu]
    except Exception:
        pass
    return None


def _deckblatt_lesen(text):
    """Fragt das kleine Modell. Gibt dict oder None - wirft NIE."""
    try:
        from urllib.request import Request, urlopen
        leib = json.dumps({
            "model": _NETZ_MODELL,
            "messages": [{"role": "user",
                          "content": _DECKBLATT_ANWEISUNG + "\n\n" + text}],
            "think": False, "stream": False,
            "options": {"temperature": 0},
        }).encode("utf-8")
        a = Request(_NETZ_URL, data=leib,
                    headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(a, timeout=90) as r:
            antwort = json.loads(r.read())
        return _json_aus(((antwort.get("message") or {}).get("content") or ""))
    except Exception:
        return None


def eintragen(name, angabe, quelle="modell", pfad=VERZEICHNIS):
    """Einen Katalogeintrag dauerhaft ablegen und den Speicher nachziehen."""
    global _GELADEN
    with _SPERRE:
        try:
            with open(pfad, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        eintrag = dict(angabe)
        eintrag["quelle"] = quelle
        d[str(name)] = eintrag
        try:
            os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
            tmp = pfad + ".neu"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.replace(tmp, pfad)
        except Exception:
            pass          # dann gilt der Eintrag nur bis zum Neustart
        _GELADEN = None   # beim naechsten laden() frisch einlesen
    return eintrag


def entfernen(name, pfad=VERZEICHNIS):
    """Katalogeintrag eines geloeschten Dokuments entfernen (alle
    Schreibvarianten des Namens). Liefert die Zahl der entfernten."""
    global _GELADEN
    ziel = _grund(str(name).rsplit(".", 1)[0] if str(name).lower().endswith((".pdf", ".md")) else name)
    with _SPERRE:
        try:
            with open(pfad, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return 0
        weg = [k for k in d if _grund(k) == ziel]
        for k in weg:
            d.pop(k, None)
        if weg:
            try:
                tmp = pfad + ".neu"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=1)
                os.replace(tmp, pfad)
            except Exception:
                pass
            _GELADEN = None
        return len(weg)


def kategorie_bestimmen(name, text, alt=None, ist_katalog=False):
    """Kategorie, Themen, Sprache, Dokumenttyp aus dem Kopf der Aufnahme -
    ohne Modell. Eine von Hand gesetzte Kategorie bleibt."""
    import kategorie as _kat
    kopf = _kat.aus_kopf(text)
    alt = alt or {}
    themen = _kat.themen(kopf)
    sprache = (kopf.get("sprache") or "").lower()
    # Deutsches Dokument, englische Schlagworte (die Verschlagwortung antwortete
    # frueher auf Englisch): eindeutschen - einmal, dann steht es im Katalog.
    if themen and sprache.startswith(("german", "deutsch", "de")) and _englisch(themen) and alt.get("themen_quelle") != "uebersetzt":
        neu = _themen_uebersetzen(themen)
        if neu:
            themen = neu
    aus = {"themen": themen, "sprache": kopf.get("sprache") or "",
           "themen_quelle": "uebersetzt" if (themen and sprache.startswith(("german", "deutsch", "de")) and not _englisch(themen)) else "aufnahme",
           "dokumenttyp": kopf.get("dokumenttyp") or "", "gebiet": kopf.get("domain") or "",
           "teilgebiet": kopf.get("subdomain") or "", "methoden": (kopf.get("methoden") or [])[:8],
           "kurzfassung": kopf.get("kurzfassung") or ""}
    if alt.get("kategorie_quelle") == "mensch" and alt.get("kategorie"):
        aus["kategorie"] = alt["kategorie"]
        aus["kategorie_quelle"] = "mensch"
    else:
        aus["kategorie"] = _kat.zuordnen(kopf, dateiname=str(name), titel=alt.get("titel") or "",
                                         kennung=str(name), ist_katalog=ist_katalog, wurzel=_wurzel_des_dokuments(name))
        aus["kategorie_quelle"] = "aufnahme"
    return aus


def _einen_nachtragen(name):
    with _NACHTRAG_SPERRE:
        if name in _NACHTRAG_LAEUFT:
            return False
        _NACHTRAG_LAEUFT.add(name)
    try:
        text = _volltext_anfang(name, zeichen=6000)
        if not text.strip():
            return False
        alt = angaben(name) or {}
        stamm = str(name)[:-3] if str(name).lower().endswith(".md") else str(name)
        titel_ist_dateiname = _grund(alt.get("titel") or "") == _grund(stamm)
        if alt.get("titel") and not titel_ist_dateiname:
            angabe = {k: alt.get(k) for k in ("titel", "verfasser", "jahr") if alt.get(k)}
            quelle = alt.get("quelle") or "modell"
        else:
            # Deckblatt OHNE den Aufnahme-Kopf lesen; erste Seiten ausfuehrlicher
            angabe = _deckblatt_lesen(_volltext_anfang(name, zeichen=6000, ab_inhalt=True) or text)
            if not angabe:
                if alt.get("titel"):
                    angabe = {k: alt.get(k) for k in ("titel", "verfasser", "jahr") if alt.get(k)}
                else:
                    return False
            quelle = "modell"
        try:
            import pruefungskatalog as _pk
            ist_katalog = _pk.ist_katalog(text if len(text) >= 6000 else _volltext_anfang(name, zeichen=60000))
        except Exception:
            ist_katalog = False
        angabe.update(kategorie_bestimmen(name, text, alt, ist_katalog=ist_katalog))
        eintragen(name, angabe, quelle=quelle)
        return True
    finally:
        with _NACHTRAG_SPERRE:
            _NACHTRAG_LAEUFT.discard(name)


def nach_kategorie(namen, kategorie_name):
    import kategorie as _kat
    return [n for n in namen if _kat.passt((angaben(n) or {}).get("kategorie"), kategorie_name)]


def kategorie_setzen(name, kategorie_name):
    """Von Hand (Chat, Betreiber): bleibt gegen jede Neuberechnung bestehen."""
    alt = angaben(name) or {}
    alt.pop("art", None)
    alt["kategorie"] = kategorie_name
    alt["kategorie_quelle"] = "mensch"
    eintragen(name, alt, quelle=alt.get("quelle") or "modell")
    return alt


def nachtragen(namen, hoechstens=5):
    """Fehlende Katalogeintraege vom Deckblatt lesen lassen.

    Bis `hoechstens` sofort (je ~1-2 s), der Rest im Hintergrund - eine
    Bestandsfrage darf nicht minutenlang haengen, nur weil 500 Arbeiten
    noch keinen Eintrag haben. Beim naechsten Aufruf sind mehr da.
    Liefert die Zahl der sofort nachgetragenen."""
    offen = []
    for n in namen or []:
        a = angaben(n)
        if a and a.get("titel") and a.get("kategorie") and not (
                a.get("themen") and str(a.get("sprache") or "").lower().startswith(("german", "deutsch", "de"))
                and a.get("themen_quelle") != "uebersetzt" and _englisch(a.get("themen") or [])):
            continue
        offen.append(n)          # ohne Titel (Modell) ODER ohne Kategorie ODER englische Themen (nur Kopf lesen)
    if not offen:
        return 0
    sofort, spaeter = offen[:hoechstens], offen[hoechstens:]
    getan = sum(1 for n in sofort if _einen_nachtragen(n))
    if spaeter:
        threading.Thread(target=lambda: [_einen_nachtragen(n) for n in spaeter],
                         daemon=True).start()
    return getan


def wie_viele_im_katalog(kennzeichen):
    """Wie viele Arbeiten dieser Art kennt der Katalog insgesamt?"""
    d = laden()
    if not d:
        return None
    return sum(1 for n in d["roh"] if kennung(n) == kennzeichen)


if __name__ == "__main__":
    print("=== Gegenprobe: Art aus der Kennung")
    faelle = [("DS-00-000", "Dissertation"), ("BS-00-000", "Bachelorarbeit"),
              ("M-00-000", "Masterarbeit"), ("D-00-000", "Diplomarbeit"),
              ("S-23-001", "Studienarbeit"), ("PA-24-002", "Projektarbeit"),
              ("DVS 2213-1", None), ("Reparatur", None), ("0000000", None)]
    schlecht = 0
    for n, soll in faelle:
        ist = art_von(n)
        gut = ist == soll
        schlecht += not gut
        print("   %-5s %-16s -> %s" % ("ok" if gut else "FALSCH", n, ist))

    print()
    print("=== Gegenprobe: welche Art fragt jemand ab?")
    fragen = [
        ("Welche Dissertationen haben wir im Bestand?", "DS"),
        ("Was haben wir alles an Bachelorarbeiten?", "BS"),
        ("Zeig mir die Masterarbeiten", "M"),
        ("Wie viele Doktorarbeiten gibt es?", "DS"),
        ("Hol mir die Dissertation von Max Mustermann", "DS"),
        ("Was steht in der Studienarbeit ueber Kleben?", "S"),
        ("Was ist Mastizieren?", None),
    ]
    for f, soll in fragen:
        ist, _ = gefragte_art(f)
        gut = ist == soll
        schlecht += not gut
        print("   %-5s %-46s -> %s" % ("ok" if gut else "FALSCH", f[:46], ist))
    print()
    print("   ⚠ Die letzten beiden treffen eine Art, sind aber INHALTSFRAGEN.")
    print("     Dass sie trotzdem keine Liste ausspucken, entscheidet der")
    print("     Ausloeser in assistent.py - nicht dieses Modul.")
    raise SystemExit(1 if schlecht else 0)
