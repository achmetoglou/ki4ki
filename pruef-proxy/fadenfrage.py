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
        if stamm in _UNSPEZIFISCH_STAEMME:
            continue
        if stamm not in raus:
            raus.append(stamm)
    return raus[:8]


def _staemme(woerter):
    aus = set()
    for w in woerter:
        f = _falte(w).replace(" ", "")
        if len(f) >= 4:
            aus.add(f[:6] if len(f) >= 8 else f)
    return aus


_UNSPEZIFISCH_STAEMME = _staemme(assistent._UNSPEZIFISCH | set(wortsuche.HAEUFIG)) | {
    "kerner", "kernau", "kernfa", "wichti", "zentra", "haupta", "aussag", "ergebn"}


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


KENNWERT_REGEL = (
    "6. Die Frage zielt auf ZAHLENWERTE. Gib sie als Markdown-Tabelle mit den Spalten "
    "| Größe | Wert | Einheit | Messbedingung | Seite | aus. Steht die Messbedingung "
    "(Temperatur, Rate, Feuchte, Probekörper) nicht auf der Seite, schreibe in die "
    "Spalte genau: fehlt. Übernimm Werte und Einheiten wörtlich, rechne nichts um.\n")


def auftrag(frage, titel, nummern, seiten, je_seite=ZEICHEN_JE_SEITE, modus="frage"):
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
    if modus == "kennwerte":
        regel += KENNWERT_REGEL
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


def vergleichs_auftrag(frage, aspekt, a, b, modus="vergleich", je_seite=3000):
    """a, b = (kennung, titel, nummern, seiten). Tabelle mit Seitenbelegen je
    Zelle; bei modus 'widerspruch' zusaetzlich die Spalte Bewertung."""
    ka, ta, na, sa = a
    kb, tb, nb, sb = b
    regel = (
        "Du vergleichst ZWEI Dokumente AUSSCHLIESSLICH anhand der unten stehenden Seiten.\n"
        "Regeln:\n"
        "1. Nichts erfinden, nichts aus anderem Wissen ergänzen.\n"
        "2. Antworte als Markdown-Tabelle: | Aspekt | %s | %s |%s. In jede Zelle gehört "
        "die Aussage UND die Seitenangabe in der Form (%s, S. 12) bzw. (%s, S. 7).\n"
        "3. Fehlt zu einem Aspekt in einem Dokument etwas, schreibe in die Zelle: nicht auf den geprüften Seiten.\n"
        "4. Nach der Tabelle höchstens drei Sätze Einordnung, jede mit Seitenangabe.\n"
        "5. Deutsch, knapp, keine Einleitung.\n"
        % (ka, kb, " Bewertung (Übereinstimmung / Widerspruch / nicht vergleichbar) |" if modus == "widerspruch" else "", ka, kb))
    if modus == "widerspruch":
        regel += ("6. Ein WIDERSPRUCH liegt nur vor, wenn beide Dokumente zur gleichen Größe unter "
                  "vergleichbaren Bedingungen Gegenteiliges sagen. Zitiere dann beide Stellen wörtlich in „…“.\n")
    teile = [regel, "FRAGE: %s" % frage.strip(), "ASPEKT: %s" % (aspekt or "allgemein: Ziel, Methode, Ergebnis")]
    for k, t, nummern, seiten in ((ka, ta, na, sa), (kb, tb, nb, sb)):
        teile.append("##### DOKUMENT %s — %s" % (k, t))
        for n in nummern:
            if 0 < n <= len(seiten):
                teile.append("=== %s, Seite %d ===\n%s" % (k, n, (seiten[n - 1] or "")[:je_seite]))
    return "\n\n".join(teile)


def verlinken_mehrfach(text, dokumente):
    """(Kennung, S. n) -> Link, fuer mehrere Dokumente. dokumente = {kennung:
    (schluessel, seiten)}. Zitate direkt davor werden geprueft."""
    gesamt_ok, gesamt_nein = 0, 0
    aus = text or ""
    for kennung, (schluessel, seiten) in dokumente.items():
        dq = quote(str(schluessel), safe="")
        k = re.escape(kennung)
        zit = re.compile(r"[„\"“]([^„“\"]{8,400}?)[“\"”]\s*\(\s*%s\s*,\s*S\.?\s*(\d{1,4})\s*\)" % k)

        def _z(m, seiten=seiten, dq=dq):
            nonlocal gesamt_ok, gesamt_nein
            zitat, s = m.group(1).strip(), int(m.group(2))
            if 0 < s <= len(seiten) and _steht_auf(zitat, seiten[s - 1]):
                gesamt_ok += 1
                return "„%s“ [%s, S. %d](/stelle?dok=%s&seite=%d&zitat=%s)" % (
                    zitat, kennung, s, dq, s, quote(zitat[:400], safe=""))
            gesamt_nein += 1
            return "„%s“ (%s, S. %d — nicht wörtlich gefunden)" % (zitat, kennung, s)
        aus = zit.sub(_z, aus)
        aus = re.sub(r"(?<!\[)\(\s*%s\s*,\s*S\.?\s*(\d{1,4})\s*\)" % k,
                     lambda m: "[%s, S. %s](/stelle?dok=%s&seite=%s)" % (kennung, m.group(1), dq, m.group(1)), aus)
    return aus, gesamt_ok, gesamt_nein


def uebersichtsseiten(seiten, hoechstens=4):
    """Seiten mit Zusammenfassung/Einleitung/Fazit - fuer Vergleiche ohne
    konkreten Aspekt."""
    marker = re.compile(r"(?im)^\s*(?:\d+(?:\.\d+)?\s+)?(?:Zusammenfassung|Kurzfassung|Abstract|Einleitung|"
                        r"Fazit|Schlussfolgerung(?:en)?|Ausblick|Summary|Conclusion)\b")
    aus = []
    for i, s in enumerate(seiten or [], 1):
        if len(s or "") >= MINDEST_SEITENLAENGE and marker.search(s or ""):
            aus.append(i)
        if len(aus) >= hoechstens:
            break
    return aus or [n for n in range(1, min(len(seiten or []), 3) + 1)]


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


def nichts_gefunden(titel, terme, frage=""):
    # Dem Menschen die Woerter zeigen, nicht die Wortstaemme ("kerner").
    woerter = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{3,}", frage or "")
               if any((_falte(w).replace(" ", ""))[:6].startswith(t[:5]) for t in (terme or []))]
    such = ", ".join(woerter[:4]) if woerter else (", ".join(terme[:4]) if terme else "die Frage")
    text = ("In **%s** finde ich zu %s keine Seite. Das heißt: Dazu steht in "
            "diesem Dokument nichts — ich weiche nicht auf andere Dokumente "
            "aus. Anders formulieren, ein anderes Dokument nennen (Kennung "
            "oder Verfasser) oder mit „im ganzen Bestand:“ überall suchen."
            % (titel, "„%s“" % such if terme else such))
    k = assistent.kontakt_zeile()
    if k:
        text += " *%s*" % k
    return text


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


# ---- Abbildungen aus Seitentexten --------------------------------------------
_ABB_MUSTER = re.compile(r"(?m)^\s*(?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*(\d{1,2}[.\-]\d{1,3})\b[:\s]*([^\n]{0,160})")
_VERZEICHNIS = re.compile(r"(?i)abbildungsverzeichnis|verzeichnis\s+der\s+abbildungen|list\s+of\s+figures|bildverzeichnis")


def _ist_verzeichnisseite(text, treffer):
    """Abbildungsverzeichnis: Ueberschrift oder viele Eintraege, die mit einer
    Seitenzahl enden ('2.1 Allgemeiner Spannungszustand ... 11')."""
    if _VERZEICHNIS.search(text or ""):
        return True
    if len(treffer) < 4:
        return False
    mit_zahl = sum(1 for m in treffer if re.search(r"(?:\.{2,}|\s)\s*\d{1,3}\s*$", m.group(2).strip()))
    return mit_zahl >= max(3, int(len(treffer) * 0.6))


def abbildungen_aus_seiten(seiten):
    """[(nummer, seite, unterschrift)] - echte Bildunterschriften. Gemessen
    27.08.: '2.1 | S. 11' und '1.1 | S. 12' stammten aus dem Abbildungs-
    VERZEICHNIS vorne im Buch - die Anlage zeigte weisse Seiten. Verzeichnis-
    seiten werden uebersprungen; taucht ein Bild nur dort auf, wird die
    Unterschrift im Text gesucht und die echte Seite genommen."""
    aus, gesehen, nur_verzeichnis = [], {}, []
    for i, s in enumerate(seiten, 1):
        treffer = list(_ABB_MUSTER.finditer(s or ""))
        if not treffer:
            continue
        verzeichnis = _ist_verzeichnisseite(s, treffer)
        for m in treffer:
            n = m.group(1).replace("-", ".")
            u = re.sub(r"\s+", " ", m.group(2)).strip()
            if verzeichnis:
                u = re.sub(r"(?:\s*\.{2,}\s*|\s+)\d{1,3}\s*$", "", u).strip()
                if n not in gesehen:
                    nur_verzeichnis.append((n, i, u[:160]))
                continue
            if n in gesehen:
                continue
            gesehen[n] = len(aus)
            aus.append((n, i, u[:160]))
    # Nur im Verzeichnis gefunden: die Unterschrift im Text suchen
    for n, vz_seite, u in nur_verzeichnis:
        if n in gesehen:
            continue
        kern = _falte(u)[:40]
        seite = 0
        if len(kern) >= 15:
            for j in range(vz_seite, len(seiten)):
                if kern in _falte(seiten[j] or ""):
                    seite = j + 1
                    break
        gesehen[n] = len(aus)
        aus.append((n, seite or vz_seite, u))
    # nach Seite ordnen, damit die Liste dem Buch folgt
    aus.sort(key=lambda t: (t[1], [int(x) for x in re.findall(r"\d+", t[0])]))
    return aus
