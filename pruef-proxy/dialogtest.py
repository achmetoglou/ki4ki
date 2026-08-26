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


def szenario_11_dieses_dokument_kein_bestand():
    print("\n[11] 'diese Arbeit' bei gesetztem Faden-Dokument ist nie Bestand (26.08.)")
    for f in ("Wieviele Diagramme hat diese Arbeit?", "Wie viele Seiten hat das Dokument?",
              "Wer ist der Verfasser dieser Dissertation?"):
        pruefe(assistent.meint_dieses_dokument(f), "meint dieses Dokument: %r" % f)
        pruefe(not assistent.ist_thema_bezug(f), "kein Themen-Bezug: %r" % f)
    for f in ("Welche Dokumente haben wir?", "Gibt es andere Arbeiten dazu?", "Welche Dissertationen behandeln Kleben?"):
        pruefe(not assistent.meint_dieses_dokument(f), "meint NICHT dieses Dokument: %r" % f)
    pruefe(assistent.dokument_fakten_frage("Wieviele Diagramme hat diese Arbeit?") == "abbildungen", "Fakt: Abbildungen")
    pruefe(assistent.dokument_fakten_frage("Wie viele Seiten hat das Dokument?") == "seiten", "Fakt: Seiten")
    pruefe(assistent.dokument_fakten_frage("Wer ist der Verfasser dieser Dissertation?") == "verfasser", "Fakt: Verfasser")
    pruefe(assistent.dokument_fakten_frage("Aus welchem Jahr ist die Arbeit?") == "jahr", "Fakt: Jahr")
    pruefe(assistent.dokument_fakten_frage("Was ist das Ziel der Arbeit?") is None, "Zielfrage ist kein Fakt")


def szenario_12_zielfrage_und_reparatur():
    print("\n[12] Zielfrage -> gezielt aus dem Dokument; Reparatur nie dieselbe Zusammenfassung")
    for f in ("Was ist das Ziel der Arbeit?", "Welche Methodik wird verwendet?", "Was sind die Ergebnisse?", "Warum wurde die Arbeit geschrieben, was ist die Motivation?"):
        pruefe(assistent.ist_zielfrage(f), "Zielfrage: %r" % f)
        pruefe(assistent.einordnen(f) == "zusammenfassung" or assistent.einordnen(f) == "normal", "Einordnung bleibt (Routing im Proxy)")
    pruefe(not assistent.ist_zielfrage("Fasse die Dissertation zusammen"), "reine Bitte ist keine Zielfrage")
    pruefe(fadenfrage.suchwoerter("Was ist das Ziel der Arbeit?") == [] or True, "Suchwoerter berechnet")
    pruefe(fadenfrage.suchwoerter("Fasse die Dissertation zusammen") == [], "Zusammenfassungs-Bitte hat keine Inhaltswoerter -> Rueckfrage 'welche Aussage'")
    pruefe(fadenfrage.suchwoerter("Was ist das Ziel der Arbeit?") == [], "'Ziel' allein: keine Inhaltswoerter -> Seitenwahl ueber Text")
    t = assistent.rueckfrage_welche_aussage("DS-24-005.md")
    pruefe("Welche Aussage" in t and "DS-24-005" in t, "Rueckfrage nennt das Dokument")


def szenario_13_zweifel_und_anlage():
    print("\n[13] 'Sicher?' ist Zweifel; Fragen an die Anlage beantwortet der Proxy")
    for f in ("Sicher", "sicher?", "Bist du sicher?", "Wirklich?", "Stimmt das?", "Ist das so richtig?"):
        pruefe(assistent.ist_zweifel(f), "Zweifel: %r" % f)
    for f in ("Sicherheitsfaktor der Verschraubung?", "Was ist ein sicherer Betriebspunkt?"):
        pruefe(not assistent.ist_zweifel(f), "kein Zweifel: %r" % f)
    for f in ("Hast du jetzt nur diese eine Dissertation angedockt und kann dich nur damit sachen fragen? Kannst du das ausdocken oder eine andere nehmen?",
              "Welches Dokument nutzt du gerade?", "Kannst du eine andere Dissertation nehmen?"):
        pruefe(assistent.ist_anlagefrage(f), "Anlage-Frage: %r" % f[:50])
    pruefe(not assistent.ist_anlagefrage("Welche Dokumente haben wir?"), "Bestandsfrage ist keine Anlage-Frage")
    t = assistent.anlage_antwort("DS-24-005.md", 11)
    pruefe("DS-24-005" in t and "im ganzen Bestand" in t and "11 im Bereich" in t, "Anlage-Antwort nennt Zustand und Wege")


def szenario_14_selbes_thema():
    print("\n[14] 'zum selben Thema' nimmt das Thema des Faden-Dokuments")
    pruefe(assistent.ist_thema_bezug("Haben wir Dissertationen zum selben thema?"), "Themen-Bezug erkannt")
    pruefe(assistent.ist_thema_bezug("Gibt es ähnliche Arbeiten?"), "'aehnliche Arbeiten'")
    pruefe(not assistent.ist_thema_bezug("Welche Dissertationen haben wir zum Thema Kleben?"), "konkretes Thema ist kein Bezug")
    a = assistent.aehnliche_titel("DS-24-005.md", NAMEN)
    pruefe(any(n == "DS-23-005.md" for n, _ in a), "Becker (glasfaserverstaerkt) findet Mueller (endlosfaserverstaerkt): %r" % [n for n, _ in a])
    pruefe(all(n != "DS-24-005.md" for n, _ in a), "sich selbst nicht")


def szenario_15_vergleich():
    print("\n[15] Vergleich zweier Dokumente als Tabelle mit Seitenbeleg")
    for f in ("Vergleiche die Methodik von Becker und Müller", "Was ist der Unterschied zwischen Becker und Kramer?",
              "Vergleiche Becker mit Köbel"):
        v = assistent.vergleichs_dokumente(f, NAMEN)
        pruefe(v is not None and v[0] == "DS-24-005.md", "beide Dokumente erkannt: %r -> %r" % (f, v and (v[0], v[1], v[2])))
    v = assistent.vergleichs_dokumente("Vergleiche die Methodik von Becker und Müller", NAMEN)
    pruefe(v and "methodik" in v[2].lower(), "Aspekt herausgeloest: %r" % (v and v[2]))
    pruefe(assistent.vergleichs_dokumente("Vergleiche Becker und Meier", NAMEN) is None, "unbekannter Name -> kein Vergleichsweg")
    pruefe(assistent.ist_widerspruchsfrage("Widersprechen sich Becker und Müller beim Ermüdungsverhalten?"), "Widerspruch erkannt")
    seitenA = ["", "Becker: Die Steifigkeit sinkt um 12 %."]; seitenB = ["", "Müller: Die Steifigkeit steigt um 5 %."]
    roh = 'Tabelle | Steifigkeit | „Die Steifigkeit sinkt um 12 %“ (DS-24-005, S. 2) | „Die Steifigkeit steigt um 5 %“ (DS-23-005, S. 2) |\nEinordnung (DS-24-005, S. 2).'
    text, ok, nein = fadenfrage.verlinken_mehrfach(roh, {"DS-24-005": ("DS-24-005", seitenA), "DS-23-005": ("DS-23-005", seitenB)})
    pruefe(ok == 2 and nein == 0 and "dok=DS-23-005&seite=2" in text and "[DS-24-005, S. 2](/stelle?dok=DS-24-005&seite=2)" in text, "beide Dokumente verlinkt, Zitate geprueft (ok=%d)" % ok)
    a = fadenfrage.vergleichs_auftrag("Vergleiche", "Methodik", ("DS-24-005", "Becker", [2], seitenA), ("DS-23-005", "Müller", [2], seitenB), modus="widerspruch")
    pruefe("DOKUMENT DS-24-005" in a and "DOKUMENT DS-23-005" in a and "WIDERSPRUCH" in a, "Widerspruchs-Auftrag enthaelt beide Dokumente")
    pruefe(fadenfrage.uebersichtsseiten(["Deckblatt", "1 Einleitung " * 20, "Text " * 30, "7 Zusammenfassung " * 10]) == [2, 4], "Uebersichtsseiten: Einleitung + Zusammenfassung")


def szenario_16_kennwerte_abkuerzung():
    print("\n[16] Kennwerte als Tabelle; Abkuerzungen aus dem Dokument")
    pruefe(assistent.ist_kennwertfrage("Welche E-Modul-Werte nennt die Arbeit?"), "Kennwertfrage E-Modul")
    pruefe(assistent.ist_kennwertfrage("Wie hoch ist die Schmelzviskosität bei 260 °C?"), "Kennwertfrage Viskositaet")
    pruefe(not assistent.ist_kennwertfrage("Was ist das Ziel der Arbeit?"), "Zielfrage ist keine Kennwertfrage")
    a = fadenfrage.auftrag("Welche Werte?", "X", [1], ["Text"], modus="kennwerte")
    pruefe("Messbedingung" in a and "fehlt" in a, "Kennwert-Regel im Auftrag")
    for f, e in [("Wofür steht GFK?", "GFK"), ("Was heißt FVK?", "FVK"), ("GFK?", "GFK"), ("Was ist Mastizieren?", None), ("Was bedeutet REM", "REM")]:
        r = assistent.abkuerzungs_frage(f); pruefe(r == e, "Abkuerzung %r -> %r" % (f, r))
    seiten = ["", "Für glasfaserverstärkte Kunststoffe (GFK) gilt ...", "REM: Rasterelektronenmikroskop. Später GFK erneut."]
    t = assistent.abkuerzung_aufloesen("GFK", seiten)
    pruefe(t and t[0][0] == 2 and "glasfaserverstärkte Kunststoffe" in t[0][1], "GFK aufgeloest auf S. 2: %r" % (t[:1],))
    t2 = assistent.abkuerzung_aufloesen("REM", seiten)
    pruefe(t2 and t2[0][0] == 3 and t2[0][1].startswith("Rasterelektronenmikroskop"), "REM per Doppelpunkt: %r" % (t2[:1],))
    pruefe(assistent.abkuerzung_aufloesen("XYZ", seiten) == [], "unbekannt -> leer, kein Raten")


def szenario_17_export_kontakt_tippfehler():
    print("\n[17] Export, Ansprechpartner, Tippfehler bei Verfassern")
    pruefe(assistent.export_frage("Exportiere das als CSV") == "csv" and assistent.export_frage("Gib mir den Bestand als BibTeX") == "bibtex", "Export erkannt")
    pruefe(assistent.export_frage("Welche Werte hat die Tabelle?") is None, "keine Export-Frage")
    b = assistent.bibtex_eintraege(["DS-24-005.md"])
    pruefe("@phdthesis{becker2024" in b and "author = {Fabian Becker}" in b, "BibTeX-Eintrag: %s" % b.split("\n")[0])
    csv = assistent.tabelle_zu_csv("Text\n| Kennung | Wert |\n|---|---|\n| [DS-24-005](/pdf/x) | 12; 5 |\n")
    pruefe(csv == 'Kennung;Wert\nDS-24-005;"12; 5"', "Markdown-Tabelle -> CSV: %r" % csv)
    v = assistent.Verlauf(); k = "wissensdatenbank|t17"; v.antwort_merken(k, "| a | b |\n|---|---|\n| 1 | 2 |")
    pruefe(assistent.Verlauf().letzte_antwort(k).startswith("| a |"), "letzte Antwort persistiert")
    os.environ["KI4KI_KONTAKT"] = "Max Mustermann, max@institut.de"
    pruefe("Max Mustermann" in assistent.anlage_antwort("DS-24-005.md", 11) and "Max Mustermann" in fadenfrage.nichts_gefunden("X", ["zeug"]), "Kontakt erscheint")
    os.environ["KI4KI_KONTAKT"] = ""
    g, _ = assistent.dokument_gemeint("Fasse die Arbeit von Beker zusammen", NAMEN)
    pruefe(g == "DS-24-005.md", "Tippfehler 'Beker' -> Becker: %r" % g)
    g, _ = assistent.dokument_gemeint("Was sagt Mueller dazu?", NAMEN)
    pruefe(g == "DS-23-005.md", "'Mueller' (ue) -> Müller: %r" % g)
    pruefe("Weiter:" in assistent.naechste_schritte("faden", "DS-24-005.md"), "naechste Schritte vorhanden")


def szenario_18_absichts_modell():
    print("\n[18] Stufe 1: Absichts-Modell - Auftrag, Parsen, Waechter (Modell simuliert)")
    import absicht
    zeilen = [assistent.dokument_zeile(n) for n in NAMEN]
    p = absicht.anweisung("Und die Kernaussagen?", [("Fasse Becker zusammen", "zusammenfassung", "Die Arbeit ...")],
                          "DS-24-005.md", "zusammenfassung", [], zeilen)
    pruefe("FADEN-DOKUMENT: DS-24-005.md" in p and "DS-24-005 — Fabian Becker" in p and "NEUE EINGABE: Und die Kernaussagen?" in p,
           "Auftrag enthaelt Zustand, Dokumente, Eingabe")
    pruefe(absicht.parsen('{"aktion":"frage_an_dokument","dokument":"DS-24-005","zweites_dokument":null,"aspekt":"Kernaussagen","frage":"Was sind die Kernaussagen?","sicherheit":0.9,"begruendung":"x"}')["aktion"] == "frage_an_dokument", "JSON geparst")
    pruefe(absicht.parsen('Hier: {"aktion":"bild","dokument":"null","zweites_dokument":null,"aspekt":"","frage":"","sicherheit":"0.8","begruendung":""} fertig')["dokument"] is None, "Text drumherum + 'null' toleriert")
    pruefe(absicht.parsen('{"aktion":"unsinn"}') is None and absicht.parsen("kaputt") is None, "Murks -> None")
    a, g = absicht.pruefen({"aktion": "frage_an_dokument", "dokument": "DS-24-005", "zweites_dokument": None, "aspekt": "", "frage": "", "sicherheit": 0.9, "begruendung": ""}, NAMEN)
    pruefe(a["dokument"] == "DS-24-005.md" and g == "ok", "Kennung auf Namen abgebildet: %r" % a["dokument"])
    a, g = absicht.pruefen({"aktion": "frage_an_dokument", "dokument": "DS-99-999", "zweites_dokument": None, "aspekt": "", "frage": "", "sicherheit": 0.9, "begruendung": ""}, NAMEN)
    pruefe(a["aktion"] == "klaerfrage", "unbekanntes Dokument -> Klaerfrage (%s)" % g)
    a, g = absicht.pruefen({"aktion": "frage_an_dokument", "dokument": None, "zweites_dokument": None, "aspekt": "", "frage": "", "sicherheit": 0.9, "begruendung": ""}, NAMEN, faden_dok="DS-24-005.md")
    pruefe(a["dokument"] == "DS-24-005.md" and a["aktion"] == "frage_an_dokument", "ohne Nennung -> Faden-Dokument")
    a, g = absicht.pruefen({"aktion": "zusammenfassung", "dokument": "DS-24-005", "zweites_dokument": None, "aspekt": "", "frage": "", "sicherheit": 0.3, "begruendung": ""}, NAMEN)
    pruefe(a["aktion"] == "klaerfrage", "geringe Sicherheit -> Klaerfrage")
    a, g = absicht.pruefen({"aktion": "vergleich", "dokument": "DS-24-005", "zweites_dokument": None, "aspekt": "", "frage": "", "sicherheit": 0.9, "begruendung": ""}, NAMEN)
    pruefe(a["aktion"] == "klaerfrage", "Vergleich mit einem Dokument -> Klaerfrage")
    a, g, ms = absicht.erkennen("Sicher?", [], "DS-24-005.md", "faden", [], zeilen, NAMEN,
                                rufen=lambda p: '{"aktion":"rueckmeldung","dokument":null,"zweites_dokument":null,"aspekt":"","frage":"Sicher?","sicherheit":0.95,"begruendung":"Zweifel"}')
    pruefe(a and a["aktion"] == "rueckmeldung" and absicht.als_art(a) == "beschwerde", "erkennen() Ende-zu-Ende mit simuliertem Modell")
    a, g, ms = absicht.erkennen("x", [], None, None, [], zeilen, NAMEN, rufen=lambda p: (_ for _ in ()).throw(RuntimeError("weg")))
    pruefe(a is None and g.startswith("Fehler"), "Modell weg -> None, kein Absturz")
    v = assistent.Verlauf(); k = "wissensdatenbank|t18"; v.merken(k, "Fasse Becker zusammen", "zusammenfassung", []); v.antwort_merken(k, "Die Arbeit untersucht ...")
    vk = v.verlauf_kurz(k)
    pruefe(vk == [("Fasse Becker zusammen", "zusammenfassung", "Die Arbeit untersucht ...")], "verlauf_kurz: %r" % vk)


def szenario_19_gespraechsmodus():
    print("\n[19] Stufe 2: Gespraechsmodus - Werkzeugkette, Waechter-Runde, Bereinigung (Modell simuliert)")
    import gespraech
    pruefe(gespraech.bereinigen("thought\n<channel|>[[BILD:DS-24-005:141:6.12]] Text") == "[[BILD:DS-24-005:141:6.12]] Text", "Template-Reste entfernt")
    pruefe(gespraech.bildnennungen("Siehe Abbildung 6.12 und Bild 3-2, [Abbildung 6.12]") == ["6.12", "3.2"], "Bildnennungen erkannt, ohne Doppelte")
    w = gespraech.waechter_bilder("Die Abbildungen sind: Abbildung 3.1 (S. 68)", [], "DS-24-005")
    pruefe(w and w["werkzeug"] == "abbildungen_auflisten" and w["args"]["dokument"] == "DS-24-005", "Waechter: Bilder ohne Werkzeug -> Liste selbst holen")
    pruefe(gespraech.waechter_bilder("Die Abbildungen sind: Abbildung 3.1", [("abbildungen_auflisten", {}, 5)]) is None, "Waechter: mit Werkzeug -> ok")
    pruefe(gespraech.waechter_bilder("Wir reden ueber Grafiken allgemein.", []) is None, "Waechter: ohne Nummern -> ok")
    b = gespraech.waechter_belege("Die Klemmung erhoeht die Lebensdauer (DS-24-005, S. 12).", [("abbildungen_auflisten", {"dokument": "DS-24-005"}, 1)], "DS-24-005", "wie sieht es aus", [], [])
    pruefe(b and b["werkzeug"] == "seiten_lesen" and b["args"]["dokument"] == "DS-24-005", "Waechter: Seitenbeleg ohne Lesen -> Seiten selbst holen")
    pruefe(gespraech.waechter_belege("Es sinkt (DS-24-005, S. 141).", [("seiten_lesen", {"dokument": "DS-24-005"}, 1)], "DS-24-005", "", ["=== DS-24-005, Seite 141 ===\nText"], []) is None, "Beleg aus gelesener Seite -> ok")
    pruefe(gespraech.waechter_belege("Es sinkt (DS-24-005, S. 141).", [], "DS-24-005", "", [], ["... (DS-24-005, S. 141) ..."]) is None, "Beleg aus dem bisherigen Gespraech -> ok")
    pruefe(gespraech.waechter_belege("Es sinkt (DS-24-005, S. 77).", [("zusammenfassen", {"dokument": "DS-24-005"}, 1)], "DS-24-005", "", ["..."], []) is None, "nach Zusammenfassung sind Seiten des Dokuments erlaubt")
    # Simuliertes Modell: Runde 1 ruft zwei Werkzeuge, Runde 2 antwortet
    lauf = {"n": 0}
    def rufen(msgs):
        lauf["n"] += 1
        if lauf["n"] == 1:
            return {"content": "", "tool_calls": [{"function": {"name": "zusammenfassen", "arguments": {"dokument": "DS-24-005"}}},
                                                  {"function": {"name": "abbildung_zeigen", "arguments": {"dokument": "DS-24-005", "nummer": "6.12"}}}]}
        letzte = msgs[-1]["content"]
        pruefe("Zusammenfassung-Text" in "".join(m.get("content", "") for m in msgs if m.get("role") == "tool"), "Werkzeugergebnis kam beim Modell an")
        return {"content": "Kernergebnis: 40 % (DS-24-005, S. 141). [[BILD:DS-24-005:141:6.12]]", "tool_calls": []}
    def werkzeug(name, args):
        return {"zusammenfassen": "Zusammenfassung-Text", "abbildung_zeigen": "[[BILD:DS-24-005:141:6.12]]"}.get(name, "?")
    e = gespraech.fuehren("Fasse zusammen und zeig das wichtigste Bild", [("Hallo", "gespraech", "Hallo!")], "DS-24-005", ["DS-24-005 — Becker"], werkzeug, rufen=rufen)
    pruefe(e["runden"] == 2 and [n for n, _, _ in e["aufrufe"]] == ["zusammenfassen", "abbildung_zeigen"], "zwei Werkzeuge in einer Runde ausgefuehrt: %r" % [n for n, _, _ in e["aufrufe"]])
    pruefe("[[BILD:DS-24-005:141:6.12]]" in e["text"] and e["dokumente"] == ["DS-24-005"], "Antwort mit Platzhalter, Dokument beruehrt")
    # Waechter-Runde: Modell erfindet Bilder ohne Werkzeug, dann nachgebessert
    lauf2 = {"n": 0}
    def rufen2(msgs):
        lauf2["n"] += 1
        if lauf2["n"] == 1:
            return {"content": "Abbildung 3.1 (S. 68), Abbildung 4.1 (S. 92)", "tool_calls": []}
        pruefe(msgs[-2]["role"] == "tool" and "6.12" in msgs[-2]["content"] and "ECHTE Liste" in msgs[-1]["content"], "Waechter hat die Liste selbst geholt und vorgelegt")
        return {"content": "Es gibt Bild 1.1 (S. 12) und 6.12 (S. 141).", "tool_calls": []}
    e2 = gespraech.fuehren("andere Grafiken?", [], "DS-24-005", [], lambda n, a: '[{"nummer":"1.1","seite":12},{"nummer":"6.12","seite":141}]', rufen=rufen2)
    pruefe(e2["text"].startswith("Es gibt Bild 1.1") and any(n == "waechter" for n, _, _ in e2["aufrufe"]) and e2["dokumente"] == ["DS-24-005"], "Waechter-Runde: erfundene Liste verworfen, Dokument beruehrt")
    # Ausfall des Modells -> Fehler, kein Absturz
    e3 = gespraech.fuehren("x", [], None, [], lambda n, a: "", rufen=lambda m: (_ for _ in ()).throw(RuntimeError("weg")))
    pruefe(e3["fehler"] and not e3["text"], "Modell weg -> fehler gesetzt")
    # Verlauf mit Antworten je Schritt
    v = assistent.Verlauf(); k = "wissensdatenbank|t19"
    v.merken(k, "Fasse Becker zusammen", "gespraech", [], antwort="Die Arbeit ..."); v.merken(k, "und Bilder?", "gespraech", [], antwort="Bild 6.12 ...")
    vk = v.verlauf_kurz(k)
    pruefe(vk[0][2] == "Die Arbeit ..." and vk[1][2] == "Bild 6.12 ...", "verlauf_kurz traegt Antworten je Schritt")
    n = gespraech.nachrichten("SYS", vk, "weiter")
    pruefe([m["role"] for m in n] == ["system", "user", "assistant", "user", "assistant", "user"], "Nachrichtenfolge fuer das Modell")
    import mehrstufig
    pruefe(not mehrstufig.brauchbar({"text": "kurz"}) and mehrstufig.brauchbar({"text": "x" * 3000}), "schwache Zusammenfassung wird nicht gespeichert")


if __name__ == "__main__":
    for s in (szenario_1_verfasser_und_folgefragen, szenario_2_beschwerde_reparatur,
              szenario_3_themenwechsel, szenario_4_rueckkehr, szenario_5_nicht_im_dokument,
              szenario_6_zitate_pruefen, szenario_7_fachwort_vs_alltag, szenario_8_bestand_tippfehler,
              szenario_9_klaerfrage, szenario_10_gedaechtnis_dauerhaft,
              szenario_11_dieses_dokument_kein_bestand, szenario_12_zielfrage_und_reparatur,
              szenario_13_zweifel_und_anlage, szenario_14_selbes_thema,
              szenario_15_vergleich, szenario_16_kennwerte_abkuerzung, szenario_17_export_kontakt_tippfehler,
              szenario_18_absichts_modell, szenario_19_gespraechsmodus):
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
