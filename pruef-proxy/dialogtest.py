#!/usr/bin/env python3
"""Dialog-Testreihe - Schicht 1: deterministisch, ohne Modell, ohne Server.

Prueft die ENTSCHEIDUNGEN des Proxys ueber mehrere Gespraechszuege hinweg:
Einordnung der Frage, gewaehltes Dokument, Faden-Zustand, Beschwerde-
Erkennung, Wortsuche-Kandidaten, Seitenwahl und Zitatpruefung der
Faden-Antwort. Jeder Fall stammt aus einem echten Gespraech oder aus den
Pflichtszenarien in GESPRAECH-ANFORDERUNGEN.md §5.

Aufruf:   python3 dialogtest.py          (Exit 0 = alle gruen)
Vor jedem Push laufen lassen. Neue Fehl-Dialoge als Fall anhaengen.

Was hier NICHT geprueft wird: die Verdrahtung im Proxy-Handler und die
Modellantworten (Schicht 2, referenzbasiert - spaeter).
"""
import json
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
os.environ.setdefault("KI4KI_AUFFANGNETZ", "0")
_tmp = tempfile.mkdtemp(prefix="ki4ki-dialogtest-")
os.environ["KI4KI_FADEN_GEDAECHTNIS"] = os.path.join(_tmp, "faden.json")
os.environ["KI4KI_BESTANDSINDEX"] = os.path.join(_tmp, "katalog.json")

KATALOG = {
    "DS-23-004": {"titel": "Eine simulationsgestützte Methodik zur Dimensionierung von statischen und dynamischen Mischteilen für die Extrusion", "verfasser": "Malte Schön", "jahr": "2023"},
    "DS-23-005": {"titel": "Vorhersage des dehnratenabhängigen Schädigungsverhaltens von endlosfaserverstärkten Kunststoffen", "verfasser": "Jonas Maximilian Müller", "jahr": "2023"},
    "DS-24-005": {"titel": "Untersuchung des Einflusses einer Mitteneinspannung auf das statische und Ermüdungsverhalten von glasfaserverstärkten Kunststoffblattfedern", "verfasser": "Fabian Becker", "jahr": "2024"},
    "DS-24-006": {"titel": "Geometrieabhängige Einspritzprofilierung für das Spritzgießverfahren", "verfasser": "Thilo Köbel", "jahr": "2024"},
    "DS-24-007": {"titel": "Werkstoffgerechte Auslegung von Direktverschraubungen in duroplastischen Formmassen", "verfasser": "Maximilian Kramer", "jahr": "2024"},
}
json.dump(KATALOG, open(os.environ["KI4KI_BESTANDSINDEX"], "w", encoding="utf-8"), ensure_ascii=False)
NAMEN = [k + ".md" for k in KATALOG]

import assistent      # noqa: E402
import fadenfrage     # noqa: E402
import wortsuche      # noqa: E402

FEHLER = []
ZAEHLER = [0]


def pruefe(bedingung, text):
    ZAEHLER[0] += 1
    if not bedingung:
        FEHLER.append(text)
        print("  FEHLER  " + text)
    else:
        print("  ok      " + text)


def faden(name):
    """Ein frischer Gespraechsfaden mit eigenem Gedaechtnis."""
    v = assistent.Verlauf()
    k = "wissensdatenbank|%s" % name
    return v, k


# --------------------------------------------------------------- Szenarien

def szenario_1_verfasser_und_folgefragen():
    print("\n[1] Verfasser nennen -> drei Folgefragen ohne Nennung")
    v, k = faden("t1")
    f1 = "Kannst du mir von der Dissertation von Fabian Becker eine Zusammenfassung machen?"
    pruefe(assistent.einordnen(f1) == "zusammenfassung", "Zug 1 = Zusammenfassung")
    g, _ = assistent.dokument_gemeint(f1, NAMEN)
    pruefe(g == "DS-24-005.md", "Zug 1 findet Becker ueber den Katalog: %r" % g)
    v.merken(k, f1, "zusammenfassung", [{"title": g}]); v.dokument_merken(k, g)
    for f in ("Schreib mir eine gesamte Zusammenfassung",
              "Und die Kernaussagen?",
              "Kannst du mir ein Diagram aus der arbeit zeigen?",
              "was ist das ziel der arbeit?"):
        pruefe(assistent.bezieht_sich_auf_vorheriges(f), "ohne eigenen Gegenstand: %r" % f)
        pruefe(not assistent.ist_beschwerde(f), "keine Beschwerde: %r" % f)
        g2, _ = assistent.dokument_gemeint(f, NAMEN)
        pruefe(g2 is None, "nennt kein anderes Dokument: %r" % f)
    pruefe(v.letztes_dokument(k) == "DS-24-005.md", "Faden-Dokument bleibt Becker")
    pruefe(wortsuche.auffaellige_woerter("Schreib mir eine gesamte Zusammenfassung") == [],
           "Wortsuche haelt 'Schreib' nicht fuer ein Fachwort")


def szenario_2_beschwerde_reparatur():
    print("\n[2] Beschwerde nach falschem Treffer -> Reparatur mit letzter Frage")
    v, k = faden("t2")
    v.merken(k, "Fasse Becker zusammen", "zusammenfassung", []); v.dokument_merken(k, "DS-24-005.md")
    v.merken(k, "Kannst du mir ein Diagram aus der arbeit zeigen?", "bild", [])
    for f in ("Das ist ein Diagram aus einer anderen DissertatioN!!!!!",
              "hä? ich habe nicht nach einem Bestand gefragt!",
              "nein das ist falsch", "das stimmt so nicht", "falsches Dokument"):
        pruefe(assistent.ist_beschwerde(f), "Beschwerde erkannt: %r" % f)
        pruefe(not assistent.ist_bestand_verfeinerung(f), "keine Bestands-Verfeinerung: %r" % f)
    lf = v.letzte_frage(k)
    pruefe(lf == ("Kannst du mir ein Diagram aus der arbeit zeigen?", "bild"),
           "Reparatur nimmt die letzte inhaltliche Frage (Bild): %r" % (lf,))
    v.merken(k, "Das ist falsch!!", "beschwerde", [])
    pruefe(v.letzte_frage(k)[1] == "bild", "Beschwerde selbst ist nie 'letzte Frage'")
    pruefe(v.letzte_art(k) == "beschwerde", "letzte Art = beschwerde")


def szenario_3_themenwechsel():
    print("\n[3] Echter Themenwechsel: neuer Verfasser -> Faden wechselt")
    v, k = faden("t3")
    v.dokument_merken(k, "DS-24-005.md")
    f = "Was sagt Müller zum Schädigungsverhalten?"
    pruefe(not assistent.bezieht_sich_auf_vorheriges(f), "eigener Gegenstand erkannt")
    g, _ = assistent.dokument_gemeint(f, NAMEN)
    pruefe(g == "DS-23-005.md", "Mueller gefunden (Umlaut): %r" % g)
    v.dokument_merken(k, g)
    pruefe(v.letztes_dokument(k) == "DS-23-005.md", "Faden-Dokument gewechselt")
    f2 = "Fasse mir die Dissertation von Meier zusammen"
    g2, kand = assistent.dokument_gemeint(f2, NAMEN)
    pruefe(g2 is None and not kand, "unbekannter Name wird NICHT umgebogen")
    pruefe(not assistent.bezieht_sich_auf_vorheriges(f2), "... und gilt nicht als Bezug aufs Vorige")


def szenario_4_rueckkehr():
    print("\n[4] Rueckkehr zum ersten Thema nach Wechsel")
    v, k = faden("t4")
    v.dokument_merken(k, "DS-24-005.md"); v.dokument_merken(k, "DS-23-005.md")
    f = "und bei Becker?"
    g, _ = assistent.dokument_gemeint(f, NAMEN)
    pruefe(g == "DS-24-005.md", "kurze Rueckkehr-Frage findet Becker: %r" % g)
    pruefe(assistent.einordnen("Und die Kernaussagen?", hat_verlauf=True) in ("folgefrage", "zusammenfassung"),
           "Folgefrage-Einordnung mit Verlauf")


def szenario_5_nicht_im_dokument():
    print("\n[5] Frage ohne Antwort im Faden-Dokument -> ehrlich, kein Ausweichen")
    seiten = ["Deckblatt", "Inhaltsverzeichnis " * 10,
              "Die Mitteneinspannung der Blattfeder wird im skalierten Modell untersucht. " * 6,
              "Das Ermüdungsverhalten glasfaserverstärkter Kunststoffe zeigt eine Abnahme der Steifigkeit. " * 6]
    nummern, terme = fadenfrage.seiten_waehlen("Welche Schmelzviskosität hat PA6 bei 260 Grad?", seiten)
    pruefe(nummern == [], "keine Seite zu fachfremder Frage: %r" % nummern)
    text = fadenfrage.nichts_gefunden("DS-24-005", terme)
    pruefe("nichts" in text and "ganzen Bestand" in text, "ehrliche Leermeldung mit Ausweg")
    nummern, terme = fadenfrage.seiten_waehlen("Was passiert mit der Steifigkeit bei Ermüdung?", seiten)
    pruefe(nummern == [4], "Treffer auf Seite 4: %r (Terme %r)" % (nummern, terme))
    nummern, _ = fadenfrage.seiten_waehlen("Wie wird die Mitteneinspannung im Modell untersucht?", seiten)
    pruefe(nummern[:1] == [3], "Beugung 'Mitteneinspannung' -> Seite 3: %r" % nummern)
    g, f = fadenfrage.will_gesamtbestand("im ganzen Bestand: welche Arbeiten nennen Schwindung?")
    pruefe(g and f.startswith("welche"), "Ausstieg 'im ganzen Bestand:' erkannt, Vorspann abgestreift")
    g, _ = fadenfrage.will_gesamtbestand("Gibt es dazu auch andere Arbeiten?")
    pruefe(g, "'andere Arbeiten' verlaesst das Faden-Dokument")
    g, _ = fadenfrage.will_gesamtbestand("was ist das ziel der arbeit?")
    pruefe(not g, "'der Arbeit' bleibt im Faden")


def szenario_6_zitate_pruefen():
    print("\n[6] Faden-Antwort: Zitate gegen die Seite pruefen und verlinken")
    seiten = ["", "Die Blattfeder wird mittig eingespannt, um das Ermüdungsverhalten zu messen.",
              "Ergebnis: Die Steifigkeit sinkt um 12 % nach 10^6 Zyklen."]
    roh = ('Die Feder wird mittig eingespannt: „Die Blattfeder wird mittig eingespannt“ (S. 2).\n'
           'Die Steifigkeit sinkt um 12 % (S. 3).\n'
           'Angeblich: „Die Feder bricht nach 500 Zyklen“ (S. 3).')
    text, ok, nein = fadenfrage.verlinken(roh, "DS-24-005", seiten, [2, 3])
    pruefe(ok == 1 and nein == 1, "1 Zitat geprueft, 1 nicht: ok=%d nein=%d" % (ok, nein))
    pruefe("/stelle?dok=DS-24-005&seite=2&zitat=" in text, "geprueftes Zitat verlinkt mit gelber Markierung")
    pruefe("nicht wörtlich gefunden" in text, "erfundenes Zitat markiert")
    pruefe("[S. 3](/stelle?dok=DS-24-005&seite=3)" in text, "Seitenangabe ohne Zitat verlinkt")
    text2, ok2, _ = fadenfrage.verlinken('„Steifigkeit sinkt um 12 %“ (S. 2)', "DS-24-005", seiten, [2, 3])
    pruefe(ok2 == 1 and "seite=3" in text2, "falsch genannte Seite wird auf die richtige (3) korrigiert")
    a = fadenfrage.auftrag("Was passiert?", "DS-24-005", [2, 3], seiten)
    pruefe("=== Seite 2 ===" in a and "=== Seite 3 ===" in a and fadenfrage.NICHTS in a, "Auftrag enthaelt Seiten + Leer-Regel")


def szenario_7_fachwort_vs_alltag():
    print("\n[7] Seltenes Fachwort -> Wortsuche; Alltagswort/Satzanfang -> keine")
    pruefe(wortsuche.auffaellige_woerter("Was ist Mastizieren?") == ["Mastizieren"], "Mastizieren")
    pruefe(wortsuche.auffaellige_woerter("Laser-Durchstrahlschweissen erklären") == ["Laser-Durchstrahlschweissen"], "Bindestrichwort am Satzanfang")
    pruefe(wortsuche.auffaellige_woerter("hä? ich habe nicht nach einem Bestand gefragt!") == [], "'Bestand' ist kein Fachwort")
    pruefe(wortsuche.auffaellige_woerter("Zeig mir ein Diagramm") == [], "'Diagramm' ist kein Fachwort")
    pruefe(fadenfrage.suchwoerter("Wie funktioniert die Einspritzprofilierung beim Spritzgießen?") == ["einspri", "spritz"][:2] or
           fadenfrage.suchwoerter("Wie funktioniert die Einspritzprofilierung beim Spritzgießen?")[0].startswith("einspr"),
           "Suchstaemme: %r" % fadenfrage.suchwoerter("Wie funktioniert die Einspritzprofilierung beim Spritzgießen?"))


def szenario_8_bestand_tippfehler():
    print("\n[8] Bestandsfrage mit Tippfehlern")
    for f in ("Welche Dokumente haben wir?", "welche dissertationen gibt es", "Was haben wir alles an Dissertationen?"):
        pruefe(assistent.einordnen(f) == "bestand", "Bestand: %r" % f)
    pruefe(assistent.einordnen("Fasse mir die Dissertation von Malte zusammen") == "zusammenfassung",
           "'Dissertation' in Zusammenfassungs-Auftrag bleibt Zusammenfassung")
    # Verfeinerung nur direkt nach Bestand
    v, k = faden("t8")
    v.merken(k, "Welche Dokumente haben wir?", "bestand", [])
    pruefe(v.letzte_art(k) == "bestand" and assistent.ist_bestand_verfeinerung("nur Dissertationen"),
           "direkt nach Bestand: 'nur Dissertationen' verfeinert")
    v.merken(k, "Fasse Becker zusammen", "zusammenfassung", [])
    pruefe(v.letzte_art(k) != "bestand", "nach Zusammenfassung: keine Verfeinerung mehr moeglich")


def szenario_9_klaerfrage():
    print("\n[9] Leerer Faden + Frage ohne Gegenstand -> Klaerfrage mit Optionen")
    v, k = faden("t9")
    f = "Fasse die Dissertation zusammen"
    g, kand = assistent.dokument_gemeint(f, NAMEN)
    pruefe(g is None and not kand, "bei 5 Dissertationen keine Wahl auf gut Glueck")
    pruefe(assistent.bezieht_sich_auf_vorheriges(f) and v.letztes_dokument(k) is None,
           "kein Gegenstand, kein Faden-Dokument -> Klaerfrage faellig")
    z = assistent.dokument_zeile("DS-24-005.md")
    pruefe(z.startswith("DS-24-005 — Fabian Becker (2024): Untersuchung"), "Option lesbar: %r" % z)
    v.wahl_merken(k, NAMEN[:3])
    g2, _ = assistent.dokument_gemeint("die von Becker", v.offene_wahl(k))
    pruefe(g2 == "DS-24-005.md", "Antwort 'die von Becker' auf die Klaerfrage verstanden")
    g3, _ = assistent.dokument_gemeint("DS-24-005", NAMEN)
    pruefe(g3 == "DS-24-005.md", "Antwort per Kennung verstanden")


def szenario_10_gedaechtnis_dauerhaft():
    print("\n[10] Gedaechtnis ueberlebt Neustart und Sitzungswechsel")
    V = assistent.Verlauf
    k = V.kennung("/api/workspace/wissensdatenbank/thread/abc-123/stream-chat", {"Cookie": "s=1"})
    k2 = V.kennung("/api/workspace/wissensdatenbank/thread/abc-123/stream-chat", {"Authorization": "Bearer neu"})
    pruefe(k == k2 == "wissensdatenbank|abc-123", "Faden-Schluessel ohne Sitzung")
    v = V(); v.merken(k, "Fasse Becker zusammen", "zusammenfassung", []); v.dokument_merken(k, "DS-24-005.md")
    w = V()
    pruefe(w.letztes_dokument(k) == "DS-24-005.md" and w.letzte_frage(k)[0] == "Fasse Becker zusammen",
           "neue Instanz (Neustart) kennt Dokument und letzte Frage")
    import time as _t
    echt = _t.time; _t.time = lambda: echt() + 30 * 86400
    try:
        pruefe(w.letztes_dokument(k) == "DS-24-005.md", "nach 30 Tagen noch da")
    finally:
        _t.time = echt


if __name__ == "__main__":
    for s in (szenario_1_verfasser_und_folgefragen, szenario_2_beschwerde_reparatur,
              szenario_3_themenwechsel, szenario_4_rueckkehr, szenario_5_nicht_im_dokument,
              szenario_6_zitate_pruefen, szenario_7_fachwort_vs_alltag, szenario_8_bestand_tippfehler,
              szenario_9_klaerfrage, szenario_10_gedaechtnis_dauerhaft):
        try:
            s()
        except Exception as e:
            import traceback
            traceback.print_exc()
            FEHLER.append("%s: Ausnahme %s" % (s.__name__, e))
    print("\n%d Pruefungen, %d Fehler" % (ZAEHLER[0], len(FEHLER)))
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1 if FEHLER else 0)
