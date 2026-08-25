"""Fragen INNERHALB eines Gespraechsfadens aus dem Faden-Dokument beantworten.

⛔ DER ANLASS (25.08.): Nach "Fasse die Dissertation von Becker zusammen" ging
   "Was ist das Ziel der Arbeit?" als gewoehnliche Suche ueber den ganzen
   Bestand - die Antwort mischte drei fremde Arbeiten. In der Literatur
   heisst das Quellenvermischung; sie ist einer der Vertrauens-Killer
   (GESPRAECH-ANFORDERUNGEN.md, Abschnitt 3).

Hier: Die Frage wird NUR gegen die Seiten des Faden-Dokuments beantwortet.
  1. Seiten waehlen - woertlich, nach den tragenden Woertern der Frage
     (kein Modell, in Millisekunden).
  2. Das Modell antwortet AUSSCHLIESSLICH aus diesen Seiten, mit Seitenzahl
     und woertlichem Zitat je Aussage.
  3. Jedes Zitat wird gegen die Seite geprueft; nur geprueft wird verlinkt
     (gelb im Original). Ungepruefte Zitate werden als solche markiert.
  4. Trifft keine Seite, sagt die Anlage das - statt in fremde Dokumente
     auszuweichen (MTRAG: "unanswerable" ehrlich benennen).

Alle Funktionen hier sind reine Textfunktionen - ohne Modell, ohne Netz -
damit die Dialog-Testreihe sie deterministisch pruefen kann.
"""
import math
import re
from urllib.parse import quote

import assistent
import wortsuche

HOECHSTENS_SEITEN = 6
ZEICHEN_JE_SEITE = 4000
MINDEST_SEITENLAENGE = 80        # kuerzer = Leerseite/Trenner, nicht werten

NICHTS = "Dazu steht auf den geprüften Seiten nichts."


def _falte(s):
    return wortsuche._falte(s)


def suchwoerter(frage):
    """Die tragenden Woerter der Frage als Wortstaemme (gefaltet).

    Lange Woerter werden auf sechs Zeichen gekuerzt, damit Beugungen
    mitgefunden werden ("Schwindung" / "Schwindungen" -> "schwin").
    """
    raus = []
    for w in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{3,}", frage or ""):
        f = _falte(w).replace(" ", "")
        if len(f) < 4:
            continue
        kl = w.lower()
        if (f in wortsuche.HAEUFIG or kl in wortsuche.HAEUFIG
                or kl in assistent._UNSPEZIFISCH or kl in assistent._FUELLWORT):
            continue
        stamm = f[:6] if len(f) >= 8 else f
        if stamm not in raus:
            raus.append(stamm)
    return raus[:8]


def seiten_waehlen(frage, seiten, hoechstens=HOECHSTENS_SEITEN):
    """(Seitennummern, Suchstaemme) - die Seiten, auf denen die Frage am
    ehesten beantwortet wird. Leer, wenn kein tragendes Wort vorkommt."""
    terme = suchwoerter(frage)
    if not terme or not seiten:
        return [], terme
    gefaltet = [_falte(s) for s in seiten]
    n = len(seiten)
    df = {t: sum(1 for g in gefaltet if t in g) for t in terme}
    idf = {t: math.log((n + 1.0) / (df[t] + 1.0)) + 0.1 for t in terme}
    punkte = []
    for i, g in enumerate(gefaltet):
        if len(g) < MINDEST_SEITENLAENGE:
            continue
        p, getroffen = 0.0, 0
        for t in terme:
            c = g.count(t)
            if c:
                getroffen += 1
                p += idf[t] * (1 + math.log(c))
        if getroffen:
            punkte.append((getroffen, p, i + 1))
    # Erst die Seiten mit den MEISTEN verschiedenen Suchwoertern, dann nach
    # Gewicht - eine Seite, die drei Begriffe der Frage traegt, schlaegt
    # eine, die einen Begriff zwanzigmal nennt.
    punkte.sort(key=lambda x: (-x[0], -x[1]))
    mindest = max(1, (len(terme) + 2) // 3)
    gute = [s for g, p, s in punkte if g >= mindest]
    return gute[:hoechstens], terme


def auftrag(frage, titel, nummern, seiten, je_seite=ZEICHEN_JE_SEITE):
    """Der Auftrag ans Modell - die Seiten stehen woertlich darin."""
    regel = (
        "Du beantwortest eine Frage AUSSCHLIESSLICH aus den unten stehenden "
        "Seiten des Dokuments „%s“.\n"
        "Regeln:\n"
        "1. Nichts erfinden, nichts aus anderem Wissen ergänzen.\n"
        "2. Jede Aussage endet mit der Seitenangabe in Klammern, z. B. (S. 12).\n"
        "3. Belege die wichtigste Aussage je Punkt mit einem WÖRTLICHEN Zitat "
        "von der Seite in „…“ (höchstens 25 Wörter), gefolgt von (S. n).\n"
        "4. Steht die Antwort nicht auf diesen Seiten, schreibe genau: %s\n"
        "5. Antworte auf Deutsch, knapp; Zwischenüberschriften nur bei "
        "mehreren Punkten; keine Einleitung, keine Schlussfloskel.\n"
        % (titel, NICHTS))
    teile = [regel, "FRAGE: %s" % frage.strip()]
    for n in nummern:
        if 0 < n <= len(seiten):
            teile.append("=== Seite %d ===\n%s" % (n, (seiten[n - 1] or "")[:je_seite]))
    return "\n\n".join(teile)


_ZITAT = re.compile(r"[„\"“]([^„“\"]{8,400}?)[“\"”]\s*\(\s*S\.?\s*(\d{1,4})\s*\)")
_SEITE = re.compile(r"\(\s*S\.?\s*(\d{1,4})\s*\)")


def _steht_auf(zitat, seitentext):
    z = _falte(zitat)
    if len(z) < 8:
        return False
    return z[:80] in _falte(seitentext)


def verlinken(text, schluessel, seiten, geprueft=None):
    """Zitate pruefen und verlinken. Rueckgabe (text, anzahl_geprueft,
    anzahl_ungeprueft). `geprueft` = Seitennummern, unter denen bei einem
    falsch genannten Blatt nachgesehen wird."""
    dq = quote(str(schluessel), safe="")
    zaehler = {"ok": 0, "nein": 0}
    kandidaten = list(geprueft or [])

    def _seite_finden(zitat, genannt):
        reihe = [genannt] + [s for s in kandidaten if s != genannt]
        for s in reihe:
            if 0 < s <= len(seiten) and _steht_auf(zitat, seiten[s - 1]):
                return s
        return None

    def _zitat(m):
        zitat, genannt = m.group(1).strip(), int(m.group(2))
        s = _seite_finden(zitat, genannt)
        if s:
            zaehler["ok"] += 1
            return "„%s“ [S. %d](/stelle?dok=%s&seite=%d&zitat=%s)" % (
                zitat, s, dq, s, quote(zitat[:400], safe=""))
        zaehler["nein"] += 1
        return "„%s“ (S. %d — nicht wörtlich gefunden)" % (zitat, genannt)

    text = _ZITAT.sub(_zitat, text or "")

    def _seite(m):
        s = int(m.group(1))
        if 0 < s <= len(seiten):
            return "[S. %d](/stelle?dok=%s&seite=%d)" % (s, dq, s)
        return m.group(0)

    # Nur die noch unverlinkten (S. n) - die verlinkten stehen jetzt in [S. n](...)
    text = re.sub(r"(?<!\[)\(\s*S\.?\s*(\d{1,4})\s*\)", _seite, text)
    return text, zaehler["ok"], zaehler["nein"]


def fuss(titel, nummern, ok, nein, sekunden=None):
    teile = ["*Antwort nur aus **%s** — geprüft auf S. %s."
             % (titel, ", ".join(str(n) for n in nummern))]
    if ok:
        teile.append("%d Zitat%s wörtlich im Original gefunden (Klick = gelb markiert)."
                     % (ok, "" if ok == 1 else "e"))
    if nein:
        teile.append("%d Zitat%s NICHT wörtlich gefunden — bitte prüfen."
                     % (nein, "" if nein == 1 else "e"))
    teile.append("Anderes Dokument gemeint? Kennung oder Verfasser nennen. "
                 "Alle Dokumente durchsuchen: Frage mit „im ganzen Bestand:“ beginnen.*")
    return " ".join(teile)


def nichts_gefunden(titel, terme):
    such = ", ".join(terme[:4]) if terme else "die Frage"
    return ("In **%s** finde ich zu %s keine Seite. Das heißt: Dazu steht in "
            "diesem Dokument nichts — ich weiche nicht auf andere Dokumente "
            "aus. Anders formulieren, ein anderes Dokument nennen (Kennung "
            "oder Verfasser) oder mit „im ganzen Bestand:“ überall suchen."
            % (titel, "„%s“" % such if terme else such))


_GESAMT = re.compile(
    r"^\s*(?:im\s+ganzen\s+bestand|im\s+gesamten\s+bestand|in\s+allen\s+"
    r"(?:dokumenten|arbeiten|dissertationen)|(?:ue|ü)berall|gesamtbestand)\s*[:,\-–]?\s*",
    re.I)
_ANDERE = re.compile(
    r"\b(?:andere[nrs]?|weitere[nrs]?|sonstige[nrs]?|alle[nrs]?)\s+"
    r"(?:arbeit(?:en)?|dokument(?:e|en)?|dissertation(?:en)?|quelle(?:n)?|"
    r"autor(?:en)?|verfasser)\b|\bim\s+bestand\b|\bgibt\s+es\s+(?:noch\s+)?(?:andere|weitere|mehr)\b",
    re.I)


def will_gesamtbestand(frage):
    """Will der Fragende ausdruecklich AUS dem Faden-Dokument heraus?
    Rueckgabe (True/False, bereinigte Frage)."""
    f = frage or ""
    m = _GESAMT.match(f)
    if m:
        return True, f[m.end():].strip() or f
    if _ANDERE.search(f):
        return True, f
    return False, f
