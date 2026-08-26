"""Stufe 1 der Gespraechsfuehrung: Das MODELL erkennt die Absicht.

Befund (ARCHITEKTUR-GESPRAECH.md): Bisher entschieden Wortlisten VOR dem
Modell, was eine Eingabe ist. Jede neue Formulierung brauchte eine neue Regel.
Hier sieht das Modell das Gespraech (letzte Zuege, Faden-Dokument, letzte
Antwortart, offene Rueckfrage) und die Dokumentliste - und sagt in einem
festen Format, was zu tun ist. Der Proxy bleibt Waechter: Beschwerde, Export
und Anlage-Fragen erkennt er weiter selbst; ein genanntes Dokument muss
existieren; bei geringer Sicherheit wird nachgefragt; faellt das Modell aus,
laeuft der bisherige Regel-Router.

Schalter: KI4KI_ABSICHT_MODELL=1. Modell: KI4KI_ABSICHT_MODELL_NAME.
Alle Funktionen ausser _modell_aufruf sind ohne Netz testbar (dialogtest.py).
"""
import json
import os
import re
import time
import urllib.request

AN = (os.environ.get("KI4KI_ABSICHT_MODELL") or "0") == "1"
MODELL = os.environ.get("KI4KI_ABSICHT_MODELL_NAME") or "gemma4:12b"
URL = (os.environ.get("KI4KI_ABSICHT_URL") or os.environ.get("KI4KI_NETZ_URL")
       or "http://nothink-proxy:11435/api/chat")
TIMEOUT = float(os.environ.get("KI4KI_ABSICHT_TIMEOUT") or "25")
MINDEST_SICHERHEIT = float(os.environ.get("KI4KI_ABSICHT_MINDEST") or "0.6")

# Was die Anlage kann - in der Sprache, in der das Modell es verstehen soll.
AKTIONEN = (
    ("frage_an_dokument", "Eine inhaltliche Frage zu EINEM bestimmten Dokument (dem Faden-Dokument oder einem genannten) - auch Folgefragen wie 'und die Kernaussagen?', 'was ist das Ziel?', 'wie hoch ist der Wert?'."),
    ("zusammenfassung", "Ein ganzes Dokument zusammenfassen oder daraus etwas aufbereiten (Praesentation, Stichpunkte, Handout)."),
    ("bild", "Eine Abbildung, ein Diagramm, eine Grafik ZEIGEN (z.B. 'zeig mir Bild 2.1', 'ein Diagramm aus der Arbeit')."),
    ("fakten", "Zaehlbares zu einem Dokument: wie viele Seiten/Abbildungen/Tabellen, wer ist der Verfasser, welches Jahr, wie lautet der Titel."),
    ("vergleich", "ZWEI Dokumente vergleichen oder auf Widersprueche pruefen."),
    ("bestand", "Welche Dokumente es gibt (Liste, Anzahl, Thema, Art) - Fragen nach dem Bestand, nicht nach Inhalten."),
    ("export", "Etwas als CSV, BibTeX oder Tabelle zum Kopieren ausgeben."),
    ("abkuerzung", "Wofuer eine Abkuerzung steht (GFK, FVK, REM ...)."),
    ("rueckmeldung", "Eine Rueckmeldung zur letzten Antwort, keine neue Frage: 'das ist falsch', 'sicher?', 'nicht danach gefragt', 'nochmal genauer'."),
    ("anlage", "Eine Frage an die Anlage selbst: was sie kann, welches Dokument sie gerade nutzt, wie man wechselt, 'angedockt?'."),
    ("gesamtbestand", "Ausdruecklich ueber ALLE Dokumente suchen ('im ganzen Bestand', 'in allen Arbeiten', 'gibt es andere Arbeiten, die ...')."),
    ("klaerfrage", "Die Eingabe ist nicht eindeutig zu einem Dokument zuzuordnen und es ist keins im Faden - nachfragen, welches gemeint ist."),
    ("smalltalk", "Begruessung, Dank, Smalltalk ohne Aufgabe."),
)
AKTIONS_NAMEN = [a for a, _ in AKTIONEN]

SCHEMA = {
    "type": "object",
    "properties": {
        "aktion": {"type": "string", "enum": AKTIONS_NAMEN},
        "dokument": {"type": ["string", "null"]},
        "zweites_dokument": {"type": ["string", "null"]},
        "aspekt": {"type": "string"},
        "frage": {"type": "string"},
        "sicherheit": {"type": "number"},
        "begruendung": {"type": "string"},
    },
    "required": ["aktion", "dokument", "zweites_dokument", "aspekt", "frage",
                 "sicherheit", "begruendung"],
}


def anweisung(frage, schritte, faden_dok, letzte_art, offene_wahl, dokumente):
    """Der Auftrag ans Modell. schritte = [(frage, art, antwortanfang)],
    dokumente = ['DS-24-005 — Fabian Becker (2024): Titel', ...]."""
    teile = [
        "Du bist der Gespraechsfuehrer einer Wissensdatenbank fuer Fachdokumente "
        "(Dissertationen eines Instituts). Deine Aufgabe: Verstehe, was der Mensch "
        "mit seiner NEUEN EINGABE will - im Zusammenhang des Gespraechs - und gib "
        "es als JSON aus. Du antwortest NICHT inhaltlich, du ordnest nur ein.",
        "MOEGLICHE AKTIONEN:\n" + "\n".join("- %s: %s" % (a, e) for a, e in AKTIONEN),
        "REGELN:\n"
        "- 'dokument' ist die KENNUNG aus der Dokumentliste (z.B. DS-24-005) oder null. "
        "Nennt der Mensch einen Verfasser oder Titelworte, waehle die passende Kennung. "
        "Sagt er 'die Arbeit', 'das Dokument', 'daraus', 'diese' - meint er das FADEN-DOKUMENT.\n"
        "- Ohne Nennung und ohne Faden-Dokument: bei frage_an_dokument/zusammenfassung/bild/fakten "
        "-> aktion 'klaerfrage'.\n"
        "- 'frage': die Eingabe als eigenstaendige, vollstaendige Frage (Pronomen aufloesen, "
        "das Dokument nicht einsetzen). Bei rueckmeldung/anlage/smalltalk: die Eingabe unveraendert.\n"
        "- 'aspekt': das Thema in 1-4 Woertern (z.B. 'Methodik', 'E-Modul', 'Ziel'), sonst ''.\n"
        "- 'sicherheit': 0 bis 1, wie sicher du bei Aktion UND Dokument bist. Unter 0,6 wird nachgefragt.\n"
        "- Tippfehler und Umgangssprache sind normal - nicht daran scheitern.",
    ]
    zustand = ["FADEN-DOKUMENT: %s" % (faden_dok or "keins"),
               "LETZTE ANTWORTART: %s" % (letzte_art or "keine")]
    if offene_wahl:
        zustand.append("OFFENE RUECKFRAGE - zur Wahl standen: " + ", ".join(offene_wahl[:10]))
    teile.append("GESPRAECHSZUSTAND:\n" + "\n".join(zustand))
    if dokumente:
        teile.append("DOKUMENTE IM BEREICH (%d):\n" % len(dokumente)
                     + "\n".join("- " + d for d in dokumente[:40]))
    if schritte:
        zeilen = []
        for f, a, ant in schritte[-6:]:
            zeilen.append("Mensch: %s\nAnlage (%s): %s" % (
                (f or "")[:200], a or "-", (ant or "")[:160].replace("\n", " ")))
        teile.append("BISHERIGES GESPRAECH (aelteste zuerst):\n" + "\n".join(zeilen))
    teile.append("NEUE EINGABE: %s" % (frage or "").strip())
    teile.append("Antworte NUR mit dem JSON.")
    return "\n\n".join(teile)


def _modell_aufruf(prompt, modell=None, timeout=None):
    leib = json.dumps({
        "model": modell or MODELL,
        "messages": [{"role": "user", "content": prompt}],
        "think": False,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0, "num_predict": 400},
        "keep_alive": "24h",
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=leib, headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
        antwort = json.load(r)
    return ((antwort.get("message") or {}).get("content") or "").strip()


def parsen(text):
    """JSON aus der Modellantwort - tolerant gegen Text drumherum. None bei Murks."""
    if not text:
        return None
    try:
        d = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            d = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(d, dict) or d.get("aktion") not in AKTIONS_NAMEN:
        return None
    try:
        d["sicherheit"] = max(0.0, min(1.0, float(d.get("sicherheit") or 0)))
    except Exception:
        d["sicherheit"] = 0.0
    for k in ("dokument", "zweites_dokument"):
        v = d.get(k)
        d[k] = str(v).strip() if v and str(v).strip().lower() not in ("null", "none", "-", "") else None
    d["aspekt"] = str(d.get("aspekt") or "").strip()[:80]
    d["frage"] = str(d.get("frage") or "").strip()[:500]
    d["begruendung"] = str(d.get("begruendung") or "").strip()[:200]
    return d


def _kennung_finden(genannt, namen):
    """'DS-24-005' / 'ds-24-005.md' / 'DS 24 005' -> der Name aus `namen`."""
    if not genannt:
        return None
    g = re.sub(r"[^a-z0-9]", "", str(genannt).lower().replace(".md", "").replace(".pdf", ""))
    if not g:
        return None
    for n in namen:
        k = re.sub(r"[^a-z0-9]", "", str(n).lower().replace(".md", "").replace(".pdf", ""))
        if k == g:
            return n
    # Kennung als Anfang ("DS-24-005" in "DS-24-005 - Titel")
    for n in namen:
        k = re.sub(r"[^a-z0-9]", "", str(n).lower().replace(".md", ""))
        if k.startswith(g) and len(g) >= 6:
            return n
    return None


def pruefen(absicht, namen, faden_dok=None):
    """Waechter: Dokumente muessen existieren, Sicherheit muss reichen.
    Rueckgabe (absicht, grund). Aendert die Aktion auf 'klaerfrage', wenn
    ein Dokument noetig, aber nicht auffindbar ist."""
    if not absicht:
        return None, "keine Absicht"
    a = dict(absicht)
    grund = "ok"
    for k in ("dokument", "zweites_dokument"):
        if a.get(k):
            gefunden = _kennung_finden(a[k], namen)
            if not gefunden:
                grund = "%s '%s' nicht im Bereich" % (k, a[k])
                a[k] = None
            else:
                a[k] = gefunden
    braucht_dok = a["aktion"] in ("frage_an_dokument", "zusammenfassung", "bild", "abkuerzung")
    if braucht_dok and not a.get("dokument"):
        if faden_dok and faden_dok in namen:
            a["dokument"] = faden_dok
        else:
            a["aktion"] = "klaerfrage"
            grund = grund if grund != "ok" else "kein Dokument bestimmbar"
    if a["aktion"] == "vergleich" and not (a.get("dokument") and a.get("zweites_dokument")):
        a["aktion"] = "klaerfrage"
        grund = "Vergleich braucht zwei Dokumente"
    if a["sicherheit"] < MINDEST_SICHERHEIT and a["aktion"] not in ("smalltalk", "anlage", "rueckmeldung", "bestand"):
        a["aktion"] = "klaerfrage"
        grund = "Sicherheit %.2f" % a["sicherheit"]
    return a, grund


def erkennen(frage, schritte, faden_dok, letzte_art, offene_wahl, dokumente, namen,
             rufen=None):
    """Alles in einem: Auftrag bauen, Modell fragen, parsen, pruefen.
    Rueckgabe (absicht|None, grund, millisekunden). Wirft nie."""
    begonnen = time.time()
    try:
        prompt = anweisung(frage, schritte, faden_dok, letzte_art, offene_wahl, dokumente)
        roh = (rufen or _modell_aufruf)(prompt)
        a = parsen(roh)
        if not a:
            return None, "unlesbar", int((time.time() - begonnen) * 1000)
        a, grund = pruefen(a, namen, faden_dok)
        return a, grund, int((time.time() - begonnen) * 1000)
    except Exception as e:
        return None, "Fehler: %s" % str(e)[:80], int((time.time() - begonnen) * 1000)


def als_art(absicht):
    """Die Aktion als Router-Art des Proxys (fuer die Wege, die es schon gibt)."""
    if not absicht:
        return None
    return {
        "frage_an_dokument": "normal", "zusammenfassung": "zusammenfassung",
        "bild": "normal", "fakten": "normal", "vergleich": "vergleich",
        "bestand": "bestand", "export": "normal", "abkuerzung": "normal",
        "rueckmeldung": "beschwerde", "anlage": "anlage", "gesamtbestand": "normal",
        "klaerfrage": "klaerfrage", "smalltalk": "smalltalk",
    }.get(absicht["aktion"])
