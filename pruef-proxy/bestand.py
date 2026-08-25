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
    "Unten steht der Anfang eines wissenschaftlichen Dokuments (Deckblatt, "
    "Impressum). Lies daraus den TITEL der Arbeit, den VERFASSER (die Person, "
    "die die Arbeit geschrieben hat - nicht Betreuer, Gutachter oder Institut) "
    "und das JAHR. Antworte NUR mit einer JSON-Zeile der Form "
    '{"titel": "...", "verfasser": "...", "jahr": "..."}. Was nicht dasteht, '
    "bleibt leer. Nichts erfinden.")


def _volltext_anfang(name, zeichen=4000):
    """Der Anfang des aufbereiteten Textes (Deckblatt, Impressum) - oder ''."""
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
                    return (json.load(f).get("pageContent") or "")[:zeichen]
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
    titel = re.sub(r"\s+", " ", str(d.get("titel") or "")).strip()
    if len(titel) < 8:
        return None
    jahr = re.search(r"(?:19|20)\d{2}", str(d.get("jahr") or ""))
    return {"titel": titel[:300],
            "verfasser": re.sub(r"\s+", " ", str(d.get("verfasser") or "")).strip()[:120],
            "jahr": jahr.group(0) if jahr else ""}


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


def _einen_nachtragen(name):
    with _NACHTRAG_SPERRE:
        if name in _NACHTRAG_LAEUFT:
            return False
        _NACHTRAG_LAEUFT.add(name)
    try:
        text = _volltext_anfang(name)
        if not text.strip():
            return False
        angabe = _deckblatt_lesen(text)
        if not angabe:
            return False
        eintragen(name, angabe, quelle="modell")
        return True
    finally:
        with _NACHTRAG_SPERRE:
            _NACHTRAG_LAEUFT.discard(name)


def nachtragen(namen, hoechstens=5):
    """Fehlende Katalogeintraege vom Deckblatt lesen lassen.

    Bis `hoechstens` sofort (je ~1-2 s), der Rest im Hintergrund - eine
    Bestandsfrage darf nicht minutenlang haengen, nur weil 500 Arbeiten
    noch keinen Eintrag haben. Beim naechsten Aufruf sind mehr da.
    Liefert die Zahl der sofort nachgetragenen."""
    offen = []
    for n in namen or []:
        a = angaben(n)
        if a and a.get("titel"):
            continue
        offen.append(n)
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
