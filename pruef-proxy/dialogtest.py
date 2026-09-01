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


def szenario_20_proxy_statisch():
    print("\n[20] Proxy statisch: kein Modulname wird von einer lokalen Variable verdeckt (Absturz 26.08.)")
    import ast
    tree = ast.parse(open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read())
    module_names = set()
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                module_names.add((a.asname or a.name).split(".")[0])
    treffer = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        lokal = set()
        for x in ast.walk(fn):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                lokal.add(x.id)
            elif isinstance(x, ast.arg):
                lokal.add(x.arg)
        for x in ast.walk(fn):
            if isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name) \
                    and x.value.id in module_names and x.value.id in lokal:
                treffer.append("%s:%d %s" % (fn.name, x.lineno, x.value.id))
    pruefe(not treffer, "Modul-Schatten: %s" % (treffer[:3] or "keine"))
    import py_compile
    for f in ("pruef_proxy.py", "assistent.py", "fadenfrage.py", "gespraech.py", "absicht.py", "mehrstufig.py", "wortsuche.py", "bestand.py", "pruefungskatalog.py", "metadaten.py", "stoerfall.py", "selbstcheck.py", "rolle.py", "kategorie.py", "wegabgleich.py"):
        try:
            py_compile.compile(os.path.join(HIER, f), doraise=True)
            pruefe(True, "kompiliert: %s" % f)
        except Exception as e:
            pruefe(False, "kompiliert NICHT: %s (%s)" % (f, e))


def szenario_21_metadaten():
    print("\n[21] K3 Metadaten: Freigabe, Gueltigkeit, 'fuer KI ausschliessen'")
    import metadaten, datetime
    w = os.path.join(_tmp, "bereichX"); os.makedirs(w, exist_ok=True)
    json.dump({"HW14-Handbuch": {"freigabe": "freigegeben", "version": "3", "gueltig_bis": "2027-06-30", "owner": "MS", "anlage": "SGM-3", "fehlercodes": "E42, E43"},
               "Bericht-117": {"freigabe": "entwurf", "ki": "nein"},
               "Alt-2019": {"freigabe": "freigegeben", "gueltig_bis": "2020-01-01"}},
              open(os.path.join(w, "metadaten.json"), "w", encoding="utf-8"))
    pruefe(metadaten.fuer_ki("HW14-Handbuch.pdf", w), "freigegeben -> fuer KI")
    pruefe(not metadaten.fuer_ki("bericht 117", w) and metadaten.grund_ausschluss("Bericht-117", w) == "für KI ausgeschlossen", "ki=nein -> ausgeschlossen (Schreibweise egal)")
    pruefe(metadaten.fuer_ki("Unbekannt", w), "ohne Eintrag -> erlaubt")
    pruefe("freigegeben" in metadaten.status_zeile("HW14-Handbuch", w) and "v3" in metadaten.status_zeile("HW14-Handbuch", w), "Statuszeile: %s" % metadaten.status_zeile("HW14-Handbuch", w))
    pruefe("abgelaufen" in metadaten.warnung("Alt-2019", w), "abgelaufene Gueltigkeit gewarnt")
    json.dump({"nur_freigegebene": True}, open(os.path.join(w, "bereich.json"), "w"))
    pruefe(not metadaten.fuer_ki("Neu-ohne-Eintrag", w) and metadaten.fuer_ki("HW14-Handbuch", w), "Bereich verlangt Freigabe -> nur freigegebene")
    json.dump({"nur_freigegebene": True, "abgelaufene_ausschliessen": True}, open(os.path.join(w, "bereich.json"), "w"))
    pruefe(not metadaten.fuer_ki("Alt-2019", w), "abgelaufen ausgeschlossen, wenn der Bereich es verlangt")
    pruefe(metadaten.stoerfall_felder("HW14-Handbuch", w)["fehlercodes"] == ["E42", "E43"], "Fehlercodes als Liste")
    pruefe(metadaten.bereich_von_pfad("/daten/pdfs/kap/archiv/X.pdf", "/daten/pdfs") == "kap", "Bereich aus Pfad")


def szenario_22_stoerfall():
    print("\n[22] K4 Stoerfall-Kontext aus Feldern und aus dem Satz")
    import stoerfall
    k = stoerfall.erkennen("Anlage: SGM-3 · Fehlercode: E42 · Symptom: Düse tropft")
    pruefe(k["anlage"] == "SGM-3" and k["fehlercode"] == "E42" and k["symptom"].startswith("Düse tropft"), "Felder erkannt: %r" % k)
    k2 = stoerfall.erkennen("an der SGM-3 kommt Fehler E42 und die Düse tropft, was tun?")
    pruefe(k2["fehlercode"] == "E42" and "SGM-3" in k2["anlage"], "aus dem Satz: %r" % k2)
    pruefe(stoerfall.ist_stoerfall("Störung an der Extruderlinie 2: Schmelzedruck schwankt") and not stoerfall.ist_stoerfall("Was ist das Ziel der Arbeit?"), "Stoerfall vs. Fachfrage")
    pruefe(stoerfall.suchbegriffe(k) == ["E42", "SGM-3", "Düse tropft"], "Suchbegriffe: %r" % stoerfall.suchbegriffe(k))
    pruefe("Fehlercode: E42" in stoerfall.kontext_zeile(k), "Kontextzeile")


def szenario_23_kennzahlen():
    print("\n[23] K5 Kennzahlen aus dem Protokoll (Eskalation, erste Quelle, Rueckmeldungen)")
    import pruefprotokoll
    eintr = [
        {"art": "frage", "ts": "2026-08-26T10:00:00Z", "konto": "a", "faden": "f1", "verdikt": "woertlich", "dauer_ms": 9000, "regel": "gespraech", "antwort": "Die Lebensdauer sinkt (DS-24-005, S. 141)."},
        {"art": "frage", "ts": "2026-08-26T10:01:00Z", "konto": "a", "faden": "f1", "verdikt": "eigen", "dauer_ms": 4000, "regel": "faden", "antwort": "In DS-24-005 finde ich dazu keine Seite. Dazu steht in diesem Dokument nichts."},
        {"art": "frage", "ts": "2026-08-27T10:00:00Z", "konto": "b", "faden": "f2", "verdikt": "ungedeckt", "dauer_ms": 12000, "regel": "normal", "antwort": "...", "kontext": {"fehlercode": "E42"}},
        {"art": "rueckmeldung", "ts": "2026-08-27T10:02:00Z", "konto": "b", "bewertung": "nicht hilfreich"},
        {"art": "rueckmeldung", "ts": "2026-08-27T10:03:00Z", "konto": "a", "bewertung": "hilfreich"},
    ]
    alt = pruefprotokoll.alle_eintraege
    pruefprotokoll.alle_eintraege = lambda seit=None, bis=None: eintr
    try:
        z = pruefprotokoll.kennzahlen()
    finally:
        pruefprotokoll.alle_eintraege = alt
    pruefe(z["vorgaenge"] == 3 and z["eskaliert"] == 1 and z["stoerfaelle"] == 1, "gezaehlt: %s" % {k: z[k] for k in ("vorgaenge", "eskaliert", "stoerfaelle")})
    pruefe(z["zeit_bis_erste_quelle_median_ms"] == 9000 and z["faeden"] == 2, "erste Quelle je Faden: %s ms, %d Faeden" % (z["zeit_bis_erste_quelle_median_ms"], z["faeden"]))
    pruefe(z["rueckmeldungen"] == {"hilfreich": 1, "nicht_hilfreich": 1, "gesamt": 2}, "Rueckmeldungen: %s" % z["rueckmeldungen"])
    pruefe(z["nutzung_je_tag"] == {"2026-08-26": 1, "2026-08-27": 1} and z["belegt_anteil"] == round(100.0 / 3, 1), "Nutzung je Tag + belegt-Anteil")


def szenario_24_pruefungskatalog():
    print("\n[24] Pruefungskatalog: exakte Fragen aus Excel/Scan, Antwort gegen den Katalog, Belege fuer alle Kennungen (AuW 26.08.)")
    import pruefungskatalog as pk
    import gespraech
    excel = ("## Inhalt\n\n[Seite 1]\n"
             "| Frage | Antwort richtig | Antwort falsch | Antwort falsch | Antwort falsch | Bereich | LE |\n"
             "| --- | --- | --- | --- | --- | --- | --- |\n"
             "| Womit dürfen PVC-U Rohre wärmebehandlelt werden? | Nur ausschließlich mit Heißluft bzw. mit einem Heißluftgerät. | Mit Gas und einer kleinen Flamme. | Wegen der thermoplastischen Struktur nicht möglich | Nur bei einer Aussentemperatur von + 5 °C | Wärmebehandlung | 31 |\n"
             "| Adhäsion ist | .... ist die Bezeichnung der Bindungskräfte zwischen Klebstoff und Fügeteil. | .... ist die Bezeichnung der Kräfte, die den Klebstoff zusammenhalten. | .... ist die Bezeichnung des Abbindevorgangs. | ..... ist die Bezeichnung der Oberflächenspannung. | Grundlagen Kleben | 41 |\n"
             "| Ab welcher Dimension sind Klebarbeiten mit zwei Personen auszuführen? | Ab einer Dimension von ≥ d 90 mm. | Ab einer Dimension von ≥ d 60 mm. | Ab einer Dimension von ≥ d 160 mm. | Ab einer Dimension von ≥ d 250 mm. | Kleben | 67 |\n"
             "\nZeile 1: Frage: Womit dürfen ...\n")
    f = pk.fragen_aus_text(excel)
    pruefe(len(f) == 3 and f[2]["richtig"] == "Ab einer Dimension von ≥ d 90 mm." and f[2]["thema"] == "Kleben" and f[2]["stelle"] == "67",
           "Excel-Katalog: %d Fragen, Loesung und Thema erkannt" % len(f))
    pruefe(pk.ist_katalog(excel) and not pk.ist_katalog("Ein Bericht ueber Rohre. Seite 1. Ergebnisse: 3 mm."), "ist_katalog trennt Katalog von Bericht")
    text, z = pk.stellen(f[2], gesamt=3, kennung="Pruefungsfragen zu DVS 2291")
    pruefe(text.startswith("**Frage 3 von 3**") and "Ab welcher Dimension sind Klebarbeiten mit zwei Personen auszuführen?" in text
           and text.count("\n- **a)** ") == 1 and text.count("\n- **d)** ") == 1, "Frage woertlich mit Optionen a-d als Listenzeilen")
    t_q, _ = pk.stellen(f[2], gesamt=3, kennung="K", quelle="[K, S. 1](/stelle?dok=K&seite=1)")
    pruefe(t_q.rstrip().endswith("*Quelle: [K, S. 1](/stelle?dok=K&seite=1)*"), "Quelle mit Link unter der Frage")
    pruefe(pk.genanntes_dokument("Stell mir ine Frage aus den Prüfungsfragen zu DVS 2291") == "Prüfungsfragen zu DVS 2291"
           and pk.genanntes_dokument("Nein dsv2291_uberarbeitet von leo") == "dsv2291_uberarbeitet von leo"
           and pk.genanntes_dokument("Frage aus den Testfragen bitte") == ""   # Einzelwort: loest der Proxy ueber dokument_gemeint
           and pk.genanntes_dokument("Stell mir eine Prüfungsfrage") == "" and pk.genanntes_dokument("eine Frage aus dem Katalog") == ""
           and pk.genanntes_dokument("eine Prüfungsfrage zum Thema Kleben") == "", "genanntes Dokument aus dem Wunsch, Fuellwoerter nicht")
    pruefe(pk.ist_beschwerde("Es gibt diese Frage gar nicht…") and pk.ist_beschwerde("hä?") and not pk.ist_beschwerde("b"), "Beschwerde bei offener Frage erkannt")
    pruefe(pk.will_link("Mach mal ein Link zu der Quelle damit ich das dokument hier öffnen kann") and not pk.will_link("weiter"), "Link-Wunsch erkannt")
    pruefe(pk._sauber("(e Milieuharze verdunsten") == "Milieuharze verdunsten", "OCR-Rest am Anfang entfernt")
    dop = pk.fragen_aus_text("| 3. | Wodurch unterscheidet sich X von der |\n| Bei den EP-Harzen... | Bei den EP-Harzen... |\n| a) | eins |\n| b) | zwei |\n")
    pruefe(dop and dop[0]["frage"].count("Bei den EP-Harzen") == 1, "doppelte Tabellenzellen nur einmal im Fragetext")
    tab = assistent._liste(["DVS 2213-1_neu", "Katalog X"], {"Katalog X": "Excel · Prüfungskatalog (29 Fragen)"})
    pruefe(tab.startswith("| Kennung | Titel | Verfasser | Jahr | Kategorie | Themen | Datei |") and "| [Katalog X](/pdf/Katalog%20X) | — | — | — | — |  | Excel · Prüfungskatalog (29 Fragen) |" in tab
           and "[DVS 2213-1_neu](/pdf/" in tab, "Index-Tabelle auch ohne Katalogeintrag, mit Kategorie/Themen/Datei")
    pruefe(assistent._ist_bestandsfrage("Was haben wir alles im bestand") and not assistent._ist_bestandsfrage("Stell mir eine Frage aus dem Katalog"),
           "'Was haben wir alles im Bestand' ist eine Bestandsfrage, der Katalogwunsch nicht")
    pruefe(sorted(z["reihe"]) == [0, 1, 2, 3] and z["reihe"] != [0, 1, 2, 3], "Optionen deterministisch gemischt (richtige nicht immer a)")
    richtig_b = "abcd"[z["reihe"].index(0)]
    u = pk.pruefen(richtig_b, f[2], z, kennung="K")
    pruefe(u and u.startswith("✅") and "Frage 3" in u and "Thema Kleben" in u, "richtige Antwort erkannt: %s" % richtig_b)
    falsch_b = "abcd"[z["reihe"].index(3)]
    u2 = pk.pruefen("Antwort: %s" % falsch_b.upper(), f[2], z)
    pruefe(u2 and u2.startswith("❌") and ("**%s)** richtig" % richtig_b) in u2 and "90 mm" in u2, "falsche Antwort: Katalog-Loesung genannt")
    u3 = pk.pruefen("Ab einer Dimension von 160 mm", f[2], z)
    pruefe(u3 and u3.startswith("❌") and "160 mm" in u3.split("Laut Katalog")[0], "Antwort als Text: Zahl entscheidet")
    pruefe(pk.pruefen("warum?", f[2], z) is None and pk.pruefen("Was ist Adhäsion?", f[2], z) is None, "Rueckfragen sind keine Antworten")
    scan = ("[Seite 1]\n| 3. 3. | Wodurch unterscheidet sich die Kalthärtung der EP-Harze von der |\n"
            "| Bei den EP-Harzen... | Bei den EP-Harzen... |\n| a) | benötigt man keinen Beschleuniger. |\n| b) | benötigt man einen speziellen Beschleuniger. |\n"
            "| c) | muss die Mischung erwärmt werden. |\n| poale d) | besteht kein Unterschied zu UP-Harzen. |\n"
            "[Seite 2]\n7. Welche Aussage ist richtig?\na) eins zwei\nb) drei vier\nc) fuenf sechs\n")
    g = pk.fragen_aus_text(scan)
    pruefe(len(g) == 2 and len(g[0]["optionen"]) == 4 and g[0]["richtig"] is None and g[1]["seite"] == 2, "Scan-Katalog (a/b/c ohne Loesung): %d Fragen, Seite erkannt" % len(g))
    t2, z2 = pk.stellen(g[0], kennung="Testfragen DVS 2290")
    pruefe("keine Lösungen" in t2, "ohne Loesung: Hinweis statt Behauptung")
    u4 = pk.pruefen("b", g[0], z2)
    pruefe(u4 and "keine Lösung" in u4 and not u4.startswith("✅") and not u4.startswith("❌"), "ohne Loesung wird kein Urteil erfunden")
    pruefe(all(pk.ist_wunsch(x) for x in ("Kannst du mir Prüfungsfragen stellen?", "stell mir bitte eine exakte Frage aus dem Katalog", "nächste Frage", "frag mich ab", "Frage 7 aus dem Katalog"))
           and not any(pk.ist_wunsch(x) for x in ("Was ist Adhäsion?", "Welche Aussage ist richtig? a) x b) y")), "Wunsch erkannt, Sachfragen nicht")
    pruefe(pk.gewuenschte_nummer("Frage 7 aus dem Katalog") == 7 and pk.gewuenschtes_thema("eine Prüfungsfrage zum Thema Kleben bitte") == "Kleben"
           and pk.gewuenschtes_thema("stell mir eine Frage aus dem Katalog") == "", "Nummer und Thema aus dem Wunsch")
    w = pk.waehlen(f, gestellt=[1, 2], thema="")
    pruefe(w["nr"] == 3 and pk.waehlen(f, gestellt=[1, 2, 3])["nr"] == 1 and pk.waehlen(f, thema="Kleben")["nr"] == 2 and pk.waehlen(f, nummer=9) is None,
           "Auswahl: naechste offene, von vorn, Thema, unbekannte Nummer")
    pruefe(all(pk.ist_weiter(x) for x in ("weiter", "ja", "Nächste")) and not pk.ist_weiter("warum?"), "weiter/ja/naechste")
    m = pk.zeile_fuer_modell(f[2], "K")
    pruefe("RICHTIG: Ab einer Dimension von ≥ d 90 mm." in m and m.count("FALSCH:") == 3, "Katalogeintrag fuer das Modell mit Loesung")
    s_ = pk.seiten_aus_text("kopf\n[Seite 1]\nA\n[Seite 2]\nB\nC\n")
    pruefe(s_ == ["\nA\n", "\nB\nC\n"] and pk.seiten_aus_text("nur Text") == ["nur Text"] and pk.seiten_aus_text("  ") == [], "Seiten aus [Seite n]-Marken")
    v = assistent.Verlauf(); k = "auw|faden24"
    v.notiz_setzen(k, "pruefung", {"dok": "X", "nr": 3}); v2 = assistent.Verlauf()
    pruefe(v2.notiz(k, "pruefung") == {"dok": "X", "nr": 3}, "Notiz je Faden dauerhaft")
    v2.notiz_setzen(k, "pruefung", None)
    pruefe(assistent.Verlauf().notiz(k, "pruefung") is None, "Notiz geloescht")
    b = gespraech.waechter_belege("Laut Norm gilt 5 °C (DVS 2213-1_neu, S. 12).", [], None, "", [], [], kennungen=["DVS 2213-1_neu", "Testfragen DVS 2290"])
    pruefe(b and b["args"]["dokument"] == "DVS 2213-1_neu", "Waechter sieht Belege mit Nicht-DS-Kennung")
    pruefe(gespraech.waechter_belege("Es gilt (siehe oben, S. 12).", [], None, "", [], [], kennungen=["DVS 2213-1_neu"]) is None, "Klammertext ohne Dokument -> kein Alarm")
    pruefe(gespraech.waechter_belege("Es gilt (DVS 2213-1_neu, S. 12).", [("seiten_lesen", {"dokument": "DVS 2213-1_neu"}, 1)], None, "", ["=== DVS 2213-1_neu, Seite 12 ===\nText"], [], kennungen=["DVS 2213-1_neu"]) is None, "gelesene Seite -> ok")
    pruefe(any(w["function"]["name"] == "pruefungsfrage" for w in gespraech.WERKZEUGE) and "16. PRUEFUNGSKATALOG" in gespraech.system_text(), "Werkzeug und Regel 16 vorhanden")
    pruefe(gespraech.pseudo_aufrufe("Text\n\n[abbildung_zeigen(dokument=“DS-24-005”, nummer=“2.1”)]") == [("abbildung_zeigen", {"dokument": "DS-24-005", "nummer": "2.1"})]
           and gespraech.ohne_pseudo("A abbildungen_auflisten(dokument=“X”) B") == "A B", "als Text geschriebene Werkzeugaufrufe werden erkannt und entfernt")
    lauf3 = {"n": 0}
    def rufen3(msgs):
        lauf3["n"] += 1
        if lauf3["n"] == 1:
            return {"content": "Hier: [abbildung_zeigen(dokument=“DS-24-005”, nummer=“6.12”)]", "tool_calls": []}
        return {"content": "Bild 6.12 zeigt es. [[BILD:DS-24-005:141:6.12]]", "tool_calls": []}
    e4 = gespraech.fuehren("zeig 6.12", [], "DS-24-005", [], lambda n, a: "[[BILD:DS-24-005:141:6.12]]", rufen=rufen3)
    pruefe([n for n, _, _ in e4["aufrufe"]] == ["abbildung_zeigen"] and "[[BILD:" in e4["text"], "Pseudo-Aufruf wird ausgefuehrt und das Bild kommt")
    pruefe("ALLGEMEINWISSEN ERLAUBT" in gespraech.system_text(allgemeinwissen=True) and "ALLGEMEINWISSEN" not in gespraech.system_text(), "Allgemeinwissen nur im Chat-Modus")
    pruefe(assistent.ist_bestandsfrage_unscharf("Was haben wi rim Besdant?") and not assistent.ist_bestandsfrage_unscharf("Was ist Laminieren?"), "Bestandsfrage trotz Tippfehler")
    pruefe(assistent.ist_faden_raus("Tue das mal raus und vergleiche") and assistent.ist_faden_raus("Vergiss das Dokument") and not assistent.ist_faden_raus("Was ist Kleben?"), "'Dokument raus' erkannt")
    seiten = ["Titel", "Abbildungsverzeichnis\nAbbildung 1.1 Ausführungen von GFK Blattfedern ... 15\nAbbildung 2.1 Allgemeiner Spannungszustand ..... 21\nAbbildung 2.2 Transformation der Spannungen 23\nAbbildung 4.4 Modellierung der Probekörperbiegung 42",
              "", "Text", "Kapitel 1\nAbbildung 1.1: Ausführungen von GFK Blattfedern und deren Einbaulage", "", "Abbildung 2.1: Allgemeiner Spannungszustand in der homogenisierten UD-Einheitszelle",
              "Bild 2.1 zeigt den Zustand. Abbildung 2.2: Transformation der Spannungen in eine Wirkebene", "Abbildung 4.4: Modellierung der Probekörperbiegung als Balken"]
    ab = fadenfrage.abbildungen_aus_seiten(seiten)
    pruefe([(n, s_) for n, s_, _ in ab] == [("1.1", 5), ("2.1", 7), ("2.2", 8), ("4.4", 9)], "Abbildungsverzeichnis uebersprungen, echte Seiten: %s" % [(n, s_) for n, s_, _ in ab])
    ab2 = fadenfrage.abbildungen_aus_seiten(["Abbildungsverzeichnis\nAbbildung 3.1 Verbindungspunkte zum Chassis und Mittenklemmung 29\nAbbildung 3.2 Uebertragung der Mittenklemmung 30\nAbbildung 3.3 Dritte 31\nAbbildung 3.4 Vierte 32", "", "Hier: Verbindungspunkte zum Chassis und Mittenklemmung der Feder"])
    pruefe(("3.1", 3) in [(n, s_) for n, s_, _ in ab2] and all(s_ >= 1 for _, s_, _ in ab2), "nur im Verzeichnis: Unterschrift im Text gesucht -> Seite 3; Rest behaelt Verzeichnisseite")
    v3 = assistent.Verlauf(); k3 = "wissensdatenbank|f24"; v3.dokument_merken(k3, "DS-24-002.md")
    pruefe(v3.dokument_vergessen(k3) and v3.letztes_dokument(k3) is None, "Faden-Dokument vergessen")


def szenario_25_rolle():
    print("\n[25] Rolle je Bereich: Dialog aus drei Fragen, Vorlage, Kern+Rolle, Gespraechsmodus")
    import rolle
    import gespraech
    z, t, f = rolle.schritt(None, "")
    pruefe(z == {"schritt": 0, "antworten": {}} and "1/3" in t and f is None, "Start: erste Frage")
    z, t, f = rolle.schritt(z, "x")
    pruefe(z["schritt"] == 0 and "kurze Antwort" in t, "zu kurze Antwort -> Frage wiederholt")
    z, t, f = rolle.schritt(z, "Kunststoffschweißen nach DVS")
    z, t, f = rolle.schritt(z, "Prüflinge und Ausbilder")
    pruefe(z["schritt"] == 2 and "3/3" in t and f is None, "zweite und dritte Frage")
    z, t, f = rolle.schritt(z, "Normstellen nennen, Sicherheit immer dazu")
    pruefe(z is None and f == {"fach": "Kunststoffschweißen nach DVS", "nutzer": "Prüflinge und Ausbilder", "besonderes": "Normstellen nennen, Sicherheit immer dazu"}, "fertig: drei Antworten")
    pruefe(rolle.schritt({"schritt": 1, "antworten": {"fach": "x"}}, "abbrechen")[0] is None, "abbrechen beendet")
    v = rolle.vorlage(f["fach"], f["nutzer"], f["besonderes"], slug="auw")
    pruefe(v.startswith("# Rolle des Bereichs „auw“") and "prüfungsnah" in v and "Normstelle" in v and "Sicherheits-" in v and "Störung" not in v,
           "Vorlage: Regeln aus den Antworten abgeleitet (Pruefung, Norm, Sicherheit; kein Stoerfall)")
    pruefe(rolle.ist_eingerichtet(v) and not rolle.ist_eingerichtet(rolle.platzhalter("auw")) and not rolle.ist_eingerichtet(""), "eingerichtet vs Platzhalter")
    k = "KERN: Belege Pflicht."
    zk = rolle.zusammensetzen(k, v)
    pruefe(rolle.zusammensetzen(k, rolle.platzhalter("auw")) == k and zk.startswith(k + "\n\n## Rolle dieses Bereichs\n\n**Fachgebiet:**")
           and "# Rolle des Bereichs" not in zk and "Diese Datei" not in zk, "Kern + Rolle nur wenn eingerichtet; ohne Datei-Kopf und Datei-Hinweis")
    g = rolle.fuer_gespraech(v)
    pruefe("Fachgebiet" in g and "# Rolle" not in g and "Diese Datei" not in g, "Kurzfassung fuer Stufe 2 ohne Kopf und Fussnote")
    pruefe("ROLLE DIESES BEREICHS" in gespraech.system_text(rolle=g) and "ROLLE DIESES BEREICHS" not in gespraech.system_text(), "Rolle im Systemtext des Gespraechsmodus")
    pruefe(all(rolle.ist_wunsch(x) for x in ("Rolle einrichten", "bitte die Rolle für den Bereich anpassen", "Prompt anpassen"))
           and not any(rolle.ist_wunsch(x) for x in ("Was ist die Rolle des Härters?", "Welche Rolle spielt Styrol?")), "Wunsch erkannt, Fachfragen mit 'Rolle' nicht")
    zp = rolle.zusammensetzen("KERN", v)
    pruefe("**Fachgebiet:**" in rolle.aus_prompt(zp) and rolle.aus_prompt(zp).startswith("# Rolle des Bereichs") and rolle.kern_aus_prompt(zp) == "KERN" and rolle.aus_prompt("nur Kern") == "", "Rolle aus dem in der Oberflaeche gespeicherten Prompt zurueckgewinnen")
    a = rolle.glaett_auftrag("Kunststoffprüfung", "Azubis, Wissenschaftler", "Normstellen, Reperaturen helfen")
    pruefe("Kunststoffprüfung" in a and "Azubis, Wissenschaftler" in a and "Reperaturen" in a and "Ursache" in a and "{" not in a.replace("{}", ""),
           "Modell-Auftrag traegt die drei Angaben und die Hinweise, keine offenen Platzhalter")
    st = rolle.vorlage("Prüflabor Werkstoffe", "Instandhalter an der Anlage", "Störfälle: Ursache und Maßnahme")
    pruefe("Ursache · Maßnahme" in st and "prüfungsnah" not in st, "Vorlage Labor: Stoerfall-Regel, keine Pruefungsregel")


def szenario_26_kategorien():
    print("\n[26] Kategorien und Themen aus dem Kopf der Aufnahme (Emrach 27.08.: 'wie erkennt das System, was was ist?')")
    import kategorie as kat
    import bestand
    kopf = kat.aus_kopf("# DVS 2290 praktischer Leitfaden\n\nQuelle: x.pdf\nDokumenttyp: Practical Guide / Manual\nSprache: German\nDomain: Production\n\n## Tags\n\n- Laminating Process\n\n## Keywords\n\n- Harz\n- Härter\n- Laminieren\n\n## Methoden\n\n- Handlaminieren\n\n## Inhalt\n\nText")
    pruefe(kopf["dokumenttyp"] == "Practical Guide / Manual" and kopf["keywords"] == ["Harz", "Härter", "Laminieren"] and kopf["tags"] == ["Laminating Process"], "Kopf der Aufnahme gelesen")
    pruefe(kat.themen(kopf) == ["Harz", "Härter", "Laminieren", "Laminating Process"], "Themen = Keywords, dann Tags")
    faelle = [(dict(kopf=kopf, dateiname="DVS 2290 praktischer Leitfaden.pdf"), "Handbuch/Anleitung"), (dict(kopf={}, dateiname="DVS_2213-1_Teil 1.pdf"), "Norm/Richtlinie"),
              (dict(kopf={}, kennung="DS-24-005"), "Dissertation"), (dict(kopf={}, dateiname="x.xlsx", ist_katalog=True), "Prüfungskatalog"),
              (dict(kopf={"dokumenttyp": "Textbook"}, dateiname="Kunststoffe.pdf"), "Fachbuch"), (dict(kopf={}, dateiname="Sicherheitsdatenblatt MEKP.pdf"), "Datenblatt"),
              (dict(kopf={"dokumenttyp": "Presentation"}, dateiname="Textbildprsrsentation DVS 1110-3.pdf"), "Präsentation"), (dict(kopf={}, dateiname="DVS 2290 Werkzeugliste.pdf"), "Handbuch/Anleitung"),
              (dict(kopf={}, dateiname="irgendwas.pdf"), "Sonstiges")]
    for args, soll in faelle:
        ist = kat.zuordnen(**args)
        pruefe(ist == soll, "%s -> %s" % (args.get("dateiname") or args.get("kennung"), ist))
    pruefe(kat.gefragte("Welche Normen haben wir?") == ("Norm/Richtlinie", "normen") and kat.gefragte("alle Prüfungskataloge") == ("Prüfungskatalog", "prüfungskataloge") and kat.gefragte("Was ist Laminieren?") == (None, None), "Kategorie-Frage erkannt")
    pruefe(assistent.ist_bestandsfrage_unscharf("Welche Normen haben wir?") and assistent.ist_bestandsfrage_unscharf("Zeig mir alle Prüfungskataloge") and assistent.ist_bestandsfrage_unscharf("Welche Handbücher gibt es") and not assistent.ist_bestandsfrage_unscharf("Was steht in der Norm zu Kleben?"), "Kategorie-Fragen sind Bestandsfragen")
    txt = kat.datei_text()
    pruefe(txt.startswith("# Kategorien") and "Norm/Richtlinie: " in txt and "Sonstiges:" in txt, "kategorien.txt-Vorlage")
    import tempfile
    d = tempfile.mkdtemp(); open(os.path.join(d, kat.DATEI), "w", encoding="utf-8").write("Sicherheitsunterlage: sicherheit, betriebsanweisung\nNorm/Richtlinie: dvs, din\n")
    pruefe(kat.namen(d) == ["Sicherheitsunterlage", "Norm/Richtlinie", "Sonstiges"] and kat.zuordnen({}, dateiname="Betriebsanweisung Harz.pdf", wurzel=d) == "Sicherheitsunterlage", "eigene Liste je Bereich gilt und ergaenzt Sonstiges")
    e = bestand.kategorie_bestimmen("DVS 2290 praktischer Leitfaden", "Dokumenttyp: Practical Guide / Manual\n## Keywords\n- Harz\n## Inhalt\n")
    pruefe(e["kategorie"] == "Handbuch/Anleitung" and e["themen"] == ["Harz"] and e["kategorie_quelle"] == "aufnahme", "Katalog: Kategorie aus dem Kopf, ohne Modell")
    e2 = bestand.kategorie_bestimmen("X", "Dokumenttyp: Manual\n## Inhalt\n", alt={"kategorie": "Fachbuch", "kategorie_quelle": "mensch"})
    pruefe(e2["kategorie"] == "Fachbuch" and e2["kategorie_quelle"] == "mensch", "von Hand gesetzte Kategorie bleibt")
    tab = assistent._liste(["DS-24-005"], {})
    pruefe("| Kennung | Titel | Verfasser | Jahr | Kategorie | Themen | Datei |" in tab, "Index traegt Kategorie und Themen")
    pruefe(isinstance(assistent._gruppieren(["DS-24-005", "DS-24-006", "DS-24-007"]), list), "Gruppierung laeuft ohne Katalog durch (liefert Liste)")
    j = bestand._json_aus('{"titel": "Untersuchung des Einflusses einer Mitteneinspannung auf das Ermüdungsverhalten Investigation of the Influence of a Centre Clamping on the Fatigue Behaviour", "verfasser": "Fabian Becker", "jahr": "1980 - 2026"}')
    pruefe(j["titel"] == "Untersuchung des Einflusses einer Mitteneinspannung auf das Ermüdungsverhalten" and j["jahr"] == "2026", "Deckblatt: englischer Anhang abgeschnitten, letztes Jahr einer Spanne")
    pruefe(bestand._json_aus('{"titel": "Leitfaden", "verfasser": "x", "jahr": ""}') is None and bestand._json_aus('{"titel": "DVS_2213-1_Teil 1_10_2025-WZ", "verfasser": "", "jahr": ""}') is None, "Einwort-Titel und Dateinamen werden verworfen (Dateiname bleibt Titel)")
    pruefe(bestand._englisch(["glass-fiber reinforced plastics", "leaf springs", "fatigue behavior"]) and not bestand._englisch(["Spritzgießverfahren", "Einspritzprofilierung", "Kunststoffverarbeitung"]), "englische Schlagworte erkannt")


def szenario_28_aufnahme_uebersicht():
    print("\n[28] Aufnahme-Uebersicht fuer /kpi (Zaehlung, Gruende, Log-Ausschluss)")
    import tempfile
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    start = quelle.index("def _aufnahme_uebersicht"); ende = quelle.index("\ndef ", start + 1)
    ns = {"os": os, "re": __import__("re"), "time": __import__("time"), "EINGANG_ORDNER": None}
    exec(quelle[start:ende], ns)
    wurzel = tempfile.mkdtemp()
    b = os.path.join(wurzel, "auw")
    for u in ("input/Normen", "archiv", "aussortiert"):
        os.makedirs(os.path.join(b, u))
    os.makedirs(os.path.join(wurzel, "kein-bereich"))          # ohne input/ -> ignoriert
    open(os.path.join(b, "input", "Normen", "wartet.pdf"), "w").write("x")
    for d in ("a.pdf", "b.docx"):
        open(os.path.join(b, "archiv", d), "w").write("x")
    open(os.path.join(b, "aussortiert", "kaputt.pdf"), "w").write("x")
    open(os.path.join(b, "aussortiert", "ohne-grund.pdf"), "w").write("x")
    with open(os.path.join(b, "aussortiert", "aussortiert.log"), "w", encoding="utf-8") as fh:
        fh.write("[2026-08-27 16:00:00] kaputt.pdf | alter Grund\n")
        fh.write("[2026-08-31 10:00:00] kaputt.pdf | juengster Grund gewinnt\n")
    aus = ns["_aufnahme_uebersicht"](wurzel)
    pruefe(len(aus) == 1 and aus[0]["bereich"] == "auw", "nur echte Bereiche (mit input/) tauchen auf")
    a = aus[0]
    pruefe(a["archiv"] == 2 and a["eingang"] == 1, "Archiv=2, Eingang=1 (auch im Unterordner) gezaehlt")
    namen = {x["datei"]: x for x in a["aussortiert"]}
    pruefe(set(namen) == {"kaputt.pdf", "ohne-grund.pdf"}, "aussortierte Dateien ohne die .log-Dateien")
    pruefe(namen["kaputt.pdf"]["grund"] == "juengster Grund gewinnt", "je Datei zaehlt die juengste Log-Zeile")
    pruefe(namen["ohne-grund.pdf"]["grund"] == "kein Log-Eintrag", "Datei ohne Log-Zeile wird trotzdem gelistet")
    pruefe(len(a["letzte_meldungen"]) == 2, "letzte Log-Meldungen kommen mit")


def szenario_29_bereich_isolation():
    print("\n[29] Ein Bereich antwortet nur aus seinen eigenen Dokumenten (leer bleibt leer)")
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    ns = {"_ohne_ki_sperre": lambda n: list(n or []), "BESTAND": type("B", (), {"titel": staticmethod(lambda: ["A", "B", "C"])})()}
    for fn in ("def titel_im_bereich", "def namen_der_anfrage"):
        start = quelle.index(fn); ende = quelle.index("\ndef ", start + 1)
        exec(quelle[start:ende], ns)
    ns["nur_erlaubte"] = lambda titel, kopf: ["A", "B"]
    ns["_titel_im_bereich_roh"] = lambda pfad, kopf: {"/api/workspace/leer/chat": [], "/api/workspace/auw/chat": ["A"]}.get(pfad)
    f = ns["namen_der_anfrage"]
    pruefe(f("/api/workspace/leer/chat", {}) == [], "leerer Bereich -> KEINE Dokumente (kein Rueckfall auf das ganze Konto)")
    pruefe(f("/api/workspace/auw/chat", {}) == ["A"], "Bereich mit Dokumenten -> nur seine")
    pruefe(f("/irgendwas", {}) == ["A", "B"], "Bereich unbekannt -> Rueckfall auf die erlaubte Menge")
    import re
    reste = re.findall(r"titel_im_bereich\(self\.path, self\.headers\)\s*or nur_erlaubte", quelle)
    pruefe(not reste, "kein 'titel_im_bereich(...) or nur_erlaubte(...)' mehr im Quelltext (%d)" % len(reste))
    # Der Bereichs-Abruf selbst: ein Bereich OHNE Dokumente ist [] (bekannt, leer), nicht None
    import io, json as _json, urllib.request as _ur
    start = quelle.index("def _titel_im_bereich_roh"); ende = quelle.index("\ndef ", start + 1)
    ns2 = {"re": re, "time": __import__("time"), "json": _json, "urllib": __import__("urllib"), "sys": sys,
           "_TITEL": {}, "ANZAHL_HALTBAR": 300, "ZIEL": "http://x", "_titel_aus_json": lambda p: ""}
    exec(quelle[start:ende], ns2)
    class _Antwort(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    alt_open = _ur.urlopen
    _ur.urlopen = lambda req, timeout=0: _Antwort(_json.dumps({"workspace": {"slug": "leer", "documents": []}}).encode())
    try:
        leer = ns2["_titel_im_bereich_roh"]("/api/workspace/leer/chat", {"Cookie": "x"})
    finally:
        _ur.urlopen = alt_open
    pruefe(leer == [], "Bereich ohne Dokumente -> [] (nicht None): %r" % (leer,))


def szenario_30_leerer_bereich():
    print("\n[30] Leerer Bereich: kein Stufe-1/2-Durchlauf, ein Hinweis statt zwei")
    import re as _re
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    start = quelle.index("    def _leerer_bereich(self, frage):"); ende = quelle.index("\n    def ", start + 1)
    src = "\n".join(z[4:] for z in quelle[start:ende].splitlines())
    ns = {"re": _re, "_ordnername": lambda s: s, "_rolle_lesen": lambda s: "", "rolle": type("R", (), {"fuer_prompt": staticmethod(lambda t: "")})()}
    exec(src, ns)
    class Fake:
        def __init__(self, pfad): self.path = pfad; self.headers = {}; self.gesendet = []; self.gefragt = []
        def _direkt_senden(self, art, frage, text, **k): self.gesendet.append((art, text))
        def _modell_fragen(self, auftrag, **k): self.gefragt.append(auftrag); return "Mehl, Zucker, Eier."
    Fake._leerer_bereich = ns["_leerer_bereich"]
    lage = {"titel": [], "modus": "query"}
    ns["titel_im_bereich"] = lambda p, k: lage["titel"]
    ns["_bereich_modus"] = lambda s: lage["modus"]
    f = Fake("/api/workspace/test/thread/x/stream-chat")
    pruefe(f._leerer_bereich("Wie backt man Kuchen?") and f.gesendet[-1][0] == "meta" and "keine Dokumente" in f.gesendet[-1][1] and not f.gefragt,
           "Abfrage-Modus, leer -> sofortiger Hinweis, kein Modellaufruf")
    lage["modus"] = "chat"; f = Fake("/api/workspace/test/thread/x/stream-chat")
    ok = f._leerer_bereich("Wie backt man Kuchen?")
    pruefe(ok and len(f.gefragt) == 1 and f.gesendet[-1][0] == "allgemein", "Chat-Modus, leer -> EIN direkter Modellaufruf")
    pruefe(f.gesendet[-1][1].count("Allgemeinwissen") == 1, "genau EIN Allgemeinwissen-Hinweis in der Antwort")
    lage["titel"] = ["A"]; f = Fake("/api/workspace/test/thread/x/stream-chat")
    pruefe(not f._leerer_bereich("Frage") and not f.gesendet, "Bereich mit Dokumenten -> normaler Weg")
    lage["titel"] = None; f = Fake("/api/workspace/test/thread/x/stream-chat")
    pruefe(not f._leerer_bereich("Frage"), "Bereich unbekannt -> normaler Weg")
    pruefe('fuss.append("⚠ enthält Allgemeinwissen' not in quelle, "doppelte Fusszeilen-Warnung entfernt")


def szenario_31_bereich_ordner_aufraeumen():
    print("\n[31] Geloeschter Bereich: Ordner mit nur anlage-eigenen Dateien verschwindet")
    import tempfile, kategorie, rolle
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    start = quelle.index("def bereich_ordner_aufraeumen"); ende = quelle.index("\ndef ", start + 1)
    wurzel = tempfile.mkdtemp()
    ns = {"os": os, "sys": sys, "EINGANG_ORDNER": wurzel, "_ordnername": lambda s: s, "rolle": rolle, "kategorie": kategorie}
    exec(quelle[start:ende], ns)
    b = os.path.join(wurzel, "test")
    for u in ("input", "archiv", "aussortiert", "loeschen", "parkplatz"):
        os.makedirs(os.path.join(b, u))
    for name, inhalt in (("bereich.json", "{}"), ("prompt.md", "# Rolle"), (kategorie.DATEI, "Norm: din"),
                         ("bilder-nachholen.txt", "x.pdf"), ("loeschen.log", "eine Zeile"), ("aussortiert/aussortiert.log", "z")):
        with open(os.path.join(b, name), "w") as fh: fh.write(inhalt)
    pruefe(ns["bereich_ordner_aufraeumen"]("test") == "geloescht" and not os.path.exists(b),
           "nur anlage-eigene Dateien (bereich.json, prompt.md, kategorien.txt, Vormerk, Logs) -> Ordner weg")
    os.makedirs(os.path.join(b, "archiv")); open(os.path.join(b, "archiv", "x.pdf"), "w").write("pdf")
    open(os.path.join(b, "bereich.json"), "w").write("{}")
    pruefe(ns["bereich_ordner_aufraeumen"]("test") == "behalten" and os.path.exists(b), "eine PDF im Archiv -> Ordner bleibt (verwaist gemeldet)")


def szenario_32_bestand_thema():
    print("\n[32] Bestandsfrage mit Thema: 'im Bereich X' wird erkannt, Wortstamm trifft")
    import bestand as _b
    pruefe(assistent._stichwort_aus("Welche Dokumente haben wir im Bereich Spritzgießen") == "Spritzgießen", "'im Bereich Spritzgießen' -> Thema erkannt")
    pruefe(assistent._stichwort_aus("Welche Unterlagen gibt es zum Thema Kleben?") == "Kleben", "'zum Thema Kleben' -> Thema erkannt")
    pruefe(assistent._stichwort_aus("Was haben wir im Bestand?") is None, "ohne Thema -> kein Stichwort")
    alt = _b.angaben
    _b.angaben = lambda n: {"DS-24-006": {"titel": "Geometrieabhängige Einspritzprofilierung für das Spritzgießverfahren", "verfasser": "K.", "jahr": "2024", "themen": ["Spritzgießverfahren"]},
                            "DS-24-001": {"titel": "Vorformlingsgeometrie beim Extrusionsblasformen", "verfasser": "F.", "jahr": "2024", "themen": ["Extrusionsblasformen"]},
                            "DS-24-003": {"titel": "Klebeverbindungen im Leichtbau", "verfasser": "C.", "jahr": "2024", "themen": []}}.get(n)
    try:
        t = assistent._treffer_im_katalog("Spritzgießen", ["DS-24-006", "DS-24-001", "DS-24-003"], bereich=True)
        pruefe(bool(t) and "DS-24-006" in t and "DS-24-001" not in t, "'Spritzgießen' trifft 'Spritzgießverfahren', nicht 'Extrusionsblasformen'")
        t2 = assistent._treffer_im_katalog("Kleben", ["DS-24-006", "DS-24-001", "DS-24-003"], bereich=True)
        pruefe(bool(t2) and "DS-24-003" in t2 and "DS-24-006" not in t2, "'Kleben' trifft 'Klebeverbindungen'")
    finally:
        _b.angaben = alt
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    pruefe("def _katalog_nachziehen" in quelle and "_katalog_nachziehen()" in quelle, "Katalog wird im Hintergrund nachgezogen (nicht erst bei der Frage)")
    import wortverzeichnis as _wv
    alt_wv = _wv.arbeiten_mit
    _wv.arbeiten_mit = lambda w, **k: {"DS-24-006", "DS-24-007"} if "spritzg" in w.lower() else set()
    _b.angaben = lambda n: {"DS-24-006": {"titel": "Einspritzprofilierung für das Spritzgießverfahren", "verfasser": "K.", "jahr": "2024", "themen": []},
                            "DS-24-007": {"titel": "Direktverschraubungen in duroplastischen Formmassen", "verfasser": "M.", "jahr": "2024", "themen": []}}.get(n)
    try:
        t3 = assistent._treffer_im_katalog("Spritzgießen", ["DS-24-006", "DS-24-007"], bereich=True)
        pruefe(bool(t3) and "Im Volltext" in t3 and "DS-24-007" in t3.split("Im Volltext")[1] and "DS-24-006" not in t3.split("Im Volltext")[1],
               "Volltext-Zusatz nennt nur Dokumente, die NICHT schon in der Katalog-Tabelle stehen")
    finally:
        _wv.arbeiten_mit = alt_wv
        _b.angaben = alt


def szenario_27_wegabgleich_und_bildarten():
    print("\n[27] A2 Rechtepruefung je Ausgabeweg (wegabgleich) · Bildarten · Kategorie-Vorgabe per Unterordner")
    import wegabgleich
    e = wegabgleich.pruefen(os.path.join(HIER, "pruef_proxy.py"))
    pruefe(not e["offen"], "kein Ausgabeweg ohne Rechtepruefung: %s" % ([o[0] for o in e["offen"]] or "keiner"))
    pruefe(not e["kaputt"], "keine scheinbare Pruefung (self.x): %s" % ([k[0] for k in e["kaputt"]] or "keine"))
    pruefe(len(e["geprueft"]) >= 15, "%d geprueftete Wege, %d begruendet ausgenommen" % (len(e["geprueft"]), len(e["ausgenommen"])))
    # Gegenprobe: eine Pruefung entfernen -> rot
    import tempfile
    quelle = open(os.path.join(HIER, "pruef_proxy.py"), encoding="utf-8").read()
    kaputt = quelle.replace('if not dokument_erlaubt(name, self.headers):\n            self._fehler(404, "Dieses Dokument liegt nicht vor.")   # wortgleich mit "unbekannt"', 'if False:\n            self._fehler(404, "x")', 1)
    pruefe(kaputt != quelle, "Gegenprobe vorbereitet (Pruefung in _pdf entfernt)")
    tmp = os.path.join(tempfile.mkdtemp(), "pruef_proxy.py"); open(tmp, "w", encoding="utf-8").write(kaputt)
    e2 = wegabgleich.pruefen(tmp)
    pruefe(any(o[0] == "_pdf" for o in e2["offen"]), "Gegenprobe: entfernte Pruefung wird als LOCH gemeldet")
    t = "[Seite 3]\n<!-- image -->\n\nLine chart\n\nBild 6.17: Erreichter Druck\n\n<!-- image -->\n\nLogo\n\nText\n\nBild 6.18: Spannungen\n\n<!-- image -->\n\nPhotograph\n\nBild 5.6: Probekörper"
    pruefe(fadenfrage.bildarten_aus_text(t) == {"6.17": "Diagramm", "5.6": "Foto"}, "Bildarten aus der Docling-Klassifikation (Logo zaehlt nicht)")
    import kategorie as kat
    pruefe(kat.zuordnen(kat.aus_kopf("Kategorie (Vorgabe): Normen\nDokumenttyp: Manual\n## Inhalt"), dateiname="x.pdf") == "Norm/Richtlinie"
           and kat.zuordnen(kat.aus_kopf("Kategorie (Vorgabe): Sicherheitsunterlagen\n## Inhalt"), dateiname="x.pdf") == "Sicherheitsunterlagen", "Unterordner-Vorgabe schlaegt Dokumenttyp; unbekannte Namen gelten woertlich")


if __name__ == "__main__":
    for s in (szenario_1_verfasser_und_folgefragen, szenario_2_beschwerde_reparatur,
              szenario_3_themenwechsel, szenario_4_rueckkehr, szenario_5_nicht_im_dokument,
              szenario_6_zitate_pruefen, szenario_7_fachwort_vs_alltag, szenario_8_bestand_tippfehler,
              szenario_9_klaerfrage, szenario_10_gedaechtnis_dauerhaft,
              szenario_11_dieses_dokument_kein_bestand, szenario_12_zielfrage_und_reparatur,
              szenario_13_zweifel_und_anlage, szenario_14_selbes_thema,
              szenario_15_vergleich, szenario_16_kennwerte_abkuerzung, szenario_17_export_kontakt_tippfehler,
              szenario_18_absichts_modell, szenario_19_gespraechsmodus, szenario_20_proxy_statisch,
              szenario_21_metadaten, szenario_22_stoerfall, szenario_23_kennzahlen,
              szenario_24_pruefungskatalog, szenario_25_rolle, szenario_26_kategorien,
              szenario_27_wegabgleich_und_bildarten,
              szenario_28_aufnahme_uebersicht,
              szenario_29_bereich_isolation,
              szenario_30_leerer_bereich,
              szenario_31_bereich_ordner_aufraeumen,
              szenario_32_bestand_thema):
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
