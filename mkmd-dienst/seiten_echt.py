#!/usr/bin/env python3
"""Gibt Doclings Seitentrennern ihre ECHTE Seitenzahl - inhaltsbasiert.

Docling schreibt nur einen Trenner ohne Nummer ([[SEITE]]) und setzt dabei
ZU WENIGE (gemessen 41 statt 44 bei S-00-000). mk_md zaehlt sie bloss durch
- weil welche fehlen, wandert die Zahl mit dem Dokument nach unten
(+1, +2, +3 ...).

Die Wahrheit steht im JSON: jeder Textblock traegt in prov[].page_no seine
echte Seite. Wir gruppieren den JSON-Text nach Seite und ordnen JEDEM
Markdown-Abschnitt (Text zwischen zwei Trennern) die Seite zu, deren Text
sich am staerksten mit dem Abschnittsanfang deckt - genau der Abgleich, der
in der Versatz-Messung verlaesslich war (saubere Dokumente
Versatz 0, driftende korrekt erkannt). Kein Ausrichten ueber Positionen
(zu fragil), sondern ueber INHALT.

Aus [[SEITE]] wird [[SEITE:37]]. mk_md.seiten_nummerieren nimmt N direkt;
ohne Nummer bleibt es beim alten Durchzaehlen (aeltere raw.md).
"""
import re


def _norm(s):
    return re.sub(r"[^a-zäöüß0-9]+", " ", (s or "").lower()).strip()


def _analyse(inhalt):
    """(seiten_text, echte_uebergaenge). seiten_text: page_no -> Wortmenge.
    echte_uebergaenge: Zahl der Seitenwechsel im Dokumentbaum (Lesereihen-
    folge) - die VERIFIZIERTE Wahrheit, gegen die wir Doclings Trenner
    halten. Sind es gleich viele, hat das Dokument keinen Drift."""
    def hol(ref):
        m = re.match(r"#/(\w+)/(\d+)$", (ref or ""))
        if not m:
            return None
        arr = inhalt.get(m.group(1)) or []
        i = int(m.group(2))
        return arr[i] if 0 <= i < len(arr) else None

    seiten = {}
    folge = []

    def lauf(children):
        for c in (children or []):
            it = hol((c or {}).get("$ref"))
            if not it:
                continue
            pv = it.get("prov") or []
            pn = pv[0].get("page_no") if pv else None
            txt = it.get("text")
            if pn:
                folge.append(pn)
                if txt:
                    seiten.setdefault(pn, set()).update(
                        w for w in _norm(txt).split() if len(w) > 3)
            if it.get("children"):
                lauf(it["children"])

    lauf((inhalt.get("body") or {}).get("children"))
    uebergaenge = 0
    for a, b in zip(folge, folge[1:]):
        if b != a:
            uebergaenge += 1
    return seiten, uebergaenge


def _anfangswoerter(segment, hoechstens=12):
    """Markante Woerter vom ANFANG eines Abschnitts (= Beginn der Seite)."""
    woerter = []
    for z in segment.splitlines():
        zn = re.sub(r"[#*|>_`]+", " ", z)
        for w in _norm(zn).split():
            if len(w) > 3:
                woerter.append(w)
        if len(woerter) >= hoechstens:
            break
    return woerter[:hoechstens]


def _beste_seite(woerter, seiten_text, alle_seiten):
    """Die EINDEUTIG beste Seite - oder None, wenn kein klarer Sieger.

    ⚠ KEINE Verriegelung: ueber ALLE Seiten suchen, nicht nur vorwaerts.
       Ein einziger falscher Vorwaerts-Sprung riss sonst den ganzen Rest
       mit (DS-00-000: Versatz -133). Ein Treffer zaehlt nur, wenn er klar
       ueber dem zweitbesten liegt - sonst lieber keine Aussage.
    """
    if len(woerter) < 4:
        return None
    ziel = set(woerter)
    werte = []
    for p in alle_seiten:
        wm = seiten_text.get(p)
        if wm:
            werte.append((len(ziel & wm) / float(len(ziel)), p))
    if not werte:
        return None
    werte.sort(reverse=True)
    beste_deckung, beste = werte[0]
    zweite = werte[1][0] if len(werte) > 1 else 0.0
    if beste_deckung >= 0.55 and beste_deckung >= zweite + 0.15:
        return beste
    return None


def nummeriere(md, inhalt):
    """md mit [[SEITE]] -> md mit [[SEITE:N]]. Liefert (md, erste_seite).

    ⭐ SICHER FUER SAUBERE DOKUMENTE: Grundlage bleibt die sequenzielle
    Zaehlung (heute bei 82% der Dokumente RICHTIG). Darauf legen wir nur
    einen VERSATZ, der bei 0 beginnt und - wie der echte Drift - monoton
    waechst. Er steigt ausschliesslich, wenn ein inhaltlich EINDEUTIGER
    Seitentreffer das kleinschrittig belegt. So bleibt ein sauberes
    Dokument unveraendert (Versatz 0), waehrend ein driftendes Stueck fuer
    Stueck geradegezogen wird. Ausreisser (ein Fehltreffer auf Seite 170)
    passen nicht in die kleine Stufe und werden verworfen.
    """
    seiten_text, echte_uebergaenge = _analyse(inhalt)
    if not seiten_text or "[[SEITE]]" not in md:
        return md, (min(seiten_text) if seiten_text else 1)

    alle_seiten = sorted(seiten_text)
    erste = alle_seiten[0]
    teile = md.split("[[SEITE]]")

    # ⭐ DRIFT-WAECHTER: Setzt Docling so viele Trenner, wie es echte
    #   Seitenwechsel gibt, ist NICHTS zu korrigieren - sequenziell stimmt
    #   (82% der Dokumente). Dann die Marken bewusst NICHT anfassen, damit
    #   ein sauberes Dokument garantiert unveraendert bleibt. Nur wenn
    #   Trenner FEHLEN (echte_uebergaenge > Trenner), greift die Korrektur.
    if echte_uebergaenge <= (len(teile) - 1):
        return md, erste

    versatz = 0
    seg_seiten = []
    for i, seg in enumerate(teile):
        seq = erste + i                      # sequenzielle Seite dieses Abschnitts
        treffer = _beste_seite(_anfangswoerter(seg), seiten_text, alle_seiten)
        if treffer is not None:
            beobachtet = treffer - seq
            # nur kleine, VORWAERTS gerichtete Anpassung annehmen - der
            # echte Drift waechst langsam; ein grosser Sprung ist ein
            # Fehltreffer.
            if versatz <= beobachtet <= versatz + 3:
                versatz = beobachtet
        seg_seiten.append(seq + versatz)

    # Fuehrende Marke fuer die ERSTE Seite mitgeben, damit mk_md alle
    # Seiten einheitlich aus [[SEITE:N]] liest (auch die erste, falls das
    # Dokument nicht auf Seite 1 beginnt).
    out = ["[[SEITE:%d]]" % seg_seiten[0], teile[0]]
    for i in range(1, len(teile)):
        out.append("[[SEITE:%d]]" % seg_seiten[i])
        out.append(teile[i])
    return "".join(out), seg_seiten[0]
