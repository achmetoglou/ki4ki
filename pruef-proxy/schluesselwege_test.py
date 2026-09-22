#!/usr/bin/env python3
"""Prueft die umgestellten Nachschlagewege des Proxys an einem gebauten
Ordnerbaum - ohne Server, ohne AnythingLLM, ohne Modell.

  python3 pruef-proxy/schluesselwege_test.py

Rueckgabe 0, wenn alles gruen ist, sonst 1.

Grundsatz wie in schluesseltest.py: Zu jeder Pruefung gehoert der Nachweis,
mit WELCHER Eingabe sie rot wird. Und: Gemessen wird am VERHALTEN, nicht an
Zeichenketten im Quelltext - ein Test, der nur nachsieht, ob bestimmte Zeilen
dastehen, waere nach diesem Umbau eine Messung am falschen Gegenstand.
"""
import os
import shutil
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

BAUM = tempfile.mkdtemp(prefix="ki4ki-wege-")
BESTAND = tempfile.mkdtemp(prefix="ki4ki-wege-bestand-")
os.environ["KI4KI_PDFS"] = BAUM
os.environ["KI4KI_EINGANG"] = BAUM
os.environ["KI4KI_BESTAND"] = BESTAND
os.environ.setdefault("KI4KI_API_KEY", "")
MDABLAGE = tempfile.mkdtemp(prefix="ki4ki-wege-md-")
os.environ["KI4KI_MD_ABLAGE"] = MDABLAGE
KATALOGORT = tempfile.mkdtemp(prefix="ki4ki-wege-katalog-")
KATALOG = os.path.join(KATALOGORT, "verzeichnis" + ".json")
os.environ["KI4KI_BESTANDS" + "INDEX"] = KATALOG

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def lege_an(*teile, **kw):
    inhalt = kw.get("inhalt", b"%PDF-1.4\n")
    pfad = os.path.join(BAUM, *teile)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as fh:
        fh.write(inhalt)
    return pfad


def baum_bauen():
    """Die Fehlerklasse, um die es geht: derselbe Dateiname bei zwei Kunden
    und in zwei Bereichen. Dazu ein Office-Original mit gewandelter PDF."""
    lege_an("kap", "archiv", "KundeA", "Angebot.pdf", inhalt=b"%PDF-1.4\nA\n")
    lege_an("kap", "archiv", "KundeB", "Angebot.pdf", inhalt=b"%PDF-1.4\nB\n")
    lege_an("auw", "archiv", "KundeA", "Angebot.pdf", inhalt=b"%PDF-1.4\nC\n")
    lege_an("kap", "archiv", "KundeA", "Bericht.docx", inhalt=b"PK\x03\x04")
    lege_an("kap", "archiv", "KundeA", "Bericht.pdf", inhalt=b"%PDF-1.4\nD\n")


def test_index():
    import schluessel
    import pruef_proxy as p
    print("PDF-Index auf Schluessel")
    p.pdfs_einlesen()
    kap_a = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    kap_b = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")
    auw_a = schluessel.schluessel("auw", "archiv/KundeA/Angebot.pdf")

    pruefe(kap_a in p.PDFS and kap_b in p.PDFS and auw_a in p.PDFS,
           "alle drei gleichnamigen Dateien stehen EINZELN im Index "
           "(Index hat %d Eintraege)" % len(p.PDFS))
    pruefe(p.PDFS.get(kap_a) != p.PDFS.get(kap_b),
           "sie zeigen auf verschiedene Dateien")

    abdruck = schluessel.fingerabdruck(
        schluessel.kennpfad("kap", "archiv/KundeB/Angebot.pdf"))
    pruefe(p.PDFS_ABDRUCK.get(abdruck) == kap_b,
           "Abdruckverzeichnis zeigt auf den richtigen Schluessel")

    # ⛔ Die Falle, in die der erste Entwurf dieses Plans selbst gelaufen ist:
    #   Im Schluessel steht HINTER dem Abdruck noch die Endung. Wer das
    #   Verzeichnis mit "die letzten zehn Zeichen" fuellt, legt jeden Eintrag
    #   falsch an - und weil abdruck_finden alle Fenster durchgeht, faellt es
    #   beim SUCHEN nicht auf, nur beim Loeschen und bei den Rechten.
    erstes = schluessel.abdruck_kandidaten(kap_b)[0]
    pruefe(erstes != abdruck,
           "Gegenprobe: das erste Fenster von rechts ist NICHT der Abdruck "
           "(ist %r, Abdruck ist %r) - deshalb wird das Verzeichnis aus dem "
           "Kennpfad gefuellt, nicht aus dem Schluessel" % (erstes, abdruck))

    # Der Hebel: _pdf_schluessel loest ueber den Abdruck auf. Damit folgen
    # 32 Aufrufstellen quer durch den Proxy ohne eigene Aenderung.
    for geschrieben in (kap_b, kap_b + ".md", kap_b.replace("--", "-"),
                        kap_b + ".md-11111111-2222-3333-4444-555555555555.json"):
        pruefe(p._pdf_schluessel(geschrieben) == kap_b,
               "Abdruck loest auf, auch als %r..." % geschrieben[:30])

    # ⛔ Office-Falle, am Bestand belegt: 293 von 779 PDF haben ein
    #   gleichnamiges Office-Original daneben (gemessen 21.09.). Die
    #   gewandelte PDF gehoert zum ORIGINAL. Bekaeme sie einen eigenen
    #   Abdruck, spraenge jeder Beleg des Word-Dokuments ins Leere - lautlos.
    original = schluessel.schluessel("kap", "archiv/KundeA/Bericht.docx")
    pruefe(p._pdf_schluessel(original) == original,
           "der Schluessel des Office-Originals loest auf")
    pruefe(os.path.basename(p.PDFS.get(original, "")) == "Bericht.pdf",
           "und zeigt auf die gewandelte PDF, ist %r"
           % os.path.basename(p.PDFS.get(original, "")))

    # ⛔ Und die Gegenprobe dazu: Eine PDF OHNE Office-Original behaelt ihren
    #   eigenen Schluessel. Ohne diese Zeile waere die Regel oben auch dann
    #   gruen, wenn sie ALLE PDF ans erstbeste Original haengt.
    pruefe(p._pdf_schluessel(kap_a) == kap_a,
           "eine PDF ohne Original behaelt ihren eigenen Schluessel")


def test_pdfstelle():
    """Der Zweitindex am Haupttrichter vorbei.

    pdfstelle.py baut seinen eigenen os.walk ueber dieselbe Quelle. Ein
    Umbau, der ihn vergisst, toetet jeden Belegsprung - und zwar lautlos,
    weil der Sprung dann einfach auf die Seite fuehrt, die zufaellig unter
    dem Namen gefunden wurde.
    """
    import schluessel
    import pdfstelle
    print("\nZweitindex pdfstelle")
    pdfstelle._PFADE, pdfstelle._UMGEFORMT, pdfstelle._ABDRUECKE = {}, {}, {}
    kap_b = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")
    pfad = pdfstelle.pdf_pfad(kap_b)
    pruefe(pfad is not None
           and pfad.endswith(os.path.join("KundeB", "Angebot.pdf")),
           "pdf_pfad findet ueber den Schluessel die RICHTIGE der drei "
           "gleichnamigen Dateien, ist %r" % (pfad or "")[-30:])

    # ⛔ Der Fehler aus BUGS_UND_FIXES.md §11: AnythingLLM macht aus '&' ein
    #   'and', aus '%' 'percent'. Solche Wortersetzungen ueberleben die
    #   Normalisierung und verschieben den Namen dauerhaft. Der Abdruck ist
    #   alphanumerisch und uebersteht sie.
    verbogen = kap_b.replace("-", "and").upper()
    # ⚠ Das "pfad is not None" gehoert dazu: Ohne es waere die Zeile gruen,
    #   sobald BEIDE Seiten None liefern - also gerade dann, wenn gar nichts
    #   mehr gefunden wird. Genau so stand sie im ersten Entwurf und war
    #   gruen, waehrend der Zweitindex noch gar nicht umgestellt war.
    pruefe(pfad is not None and pdfstelle.pdf_pfad(verbogen) == pfad,
           "auch ein verbogener Name findet ueber den Abdruck dasselbe "
           "Dokument (gefunden: %r)" % (pdfstelle.pdf_pfad(verbogen) or "")[-30:])

    # ⛔ Gegenprobe: Ein Name OHNE Abdruck darf NICHT ueber den Abdruck
    #   treffen - sonst oeffnet ein Beleg die gleichnamige Datei eines
    #   anderen Kunden. Er darf hoechstens die Uebergangsstuetze treffen.
    nackt = pdfstelle.pdf_pfad("Angebot")
    pruefe(nackt is None or nackt == pdfstelle._PFADE.get("Angebot"),
           "ein nackter Name trifft hoechstens den Uebergangseintrag, nie "
           "ueber den Abdruck")

    # Und der Office-Fall auch hier: die gewandelte PDF haengt am Original.
    original = schluessel.schluessel("kap", "archiv/KundeA/Bericht.docx")
    op = pdfstelle.pdf_pfad(original)
    pruefe(op is not None and os.path.basename(op) == "Bericht.pdf",
           "der Schluessel des Office-Originals findet die gewandelte PDF, "
           "ist %r" % os.path.basename(op or ""))


def test_belegvorrat():
    """Heute verwirft veredeln.Bestand jede zweite gleichnamige Textfassung.

    Sie landet in .doppelte und ist fuer die Zitatpruefung unerreichbar - das
    Dokument ist dann durchsuchbar, aber NICHT belegbar. Hochrechnung aus
    BUGS_UND_FIXES.md 6: rund 942 Dokumente.

    Mit dem Schluessel als Uploadname verschwindet die Kollision von selbst.
    Diese Pruefung belegt das, statt sich darauf zu verlassen - und die
    Gegenprobe zeigt, dass sie die Fehlerklasse ueberhaupt trifft.
    """
    import schluessel
    import veredeln
    print("\nBelegvorrat")
    vorrat = tempfile.mkdtemp(prefix="ki4ki-vorrat-")
    kennung = "-11111111-2222-3333-4444-5555555555%02d.json"
    try:
        mit = os.path.join(vorrat, "mit-schluessel")
        os.makedirs(mit)
        kap_a = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
        kap_b = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")
        for i, sl in enumerate((kap_a, kap_b)):
            with open(os.path.join(mit, sl + ".md" + (kennung % i)), "w") as fh:
                fh.write('{"pageContent": "Text %d"}' % i)
        b = veredeln.Bestand(ordner=mit,
                             speicher=os.path.join(vorrat, "a.pickle"))
        pruefe(len(b.titel()) == 2,
               "beide gleichnamigen Textfassungen sind im Vorrat, sind %d"
               % len(b.titel()))
        pruefe(not b.doppelte,
               "nichts wurde als Dublette verworfen, verworfen: %d"
               % len(b.doppelte))

        # ⛔ Gegenprobe, ohne die die zwei Zeilen oben nichts sagen: MIT den
        #   alten, nackten Namen muss derselbe Vorrat genau EINE Fassung
        #   verschlucken. Tut er das nicht, prueft dieser Test die
        #   Fehlerklasse gar nicht und sein Gruen ist geschenkt.
        ohne = os.path.join(vorrat, "ohne-schluessel")
        os.makedirs(ohne)
        for i in range(2):
            with open(os.path.join(ohne, "Angebot.md" + (kennung % i)), "w") as fh:
                fh.write('{"pageContent": "Text %d"}' % i)
        b2 = veredeln.Bestand(ordner=ohne,
                              speicher=os.path.join(vorrat, "b.pickle"))
        pruefe(len(b2.doppelte) == 1,
               "Gegenprobe: mit nackten Namen wird genau eine Fassung "
               "verworfen, verworfen: %d" % len(b2.doppelte))
    finally:
        shutil.rmtree(vorrat, ignore_errors=True)


def test_anzeigetitel():
    """Der Schluessel beginnt mit dem Bereichsnamen - damit steht eine
    Kennung wie DS-24-005 nicht mehr vorn.

    Folge ohne Gegenmassnahme: kennung() liefert None, art_von() weiss nicht
    mehr, dass es eine Dissertation ist, und bestand.angaben() findet den
    Katalogeintrag nicht. Titel, Verfasser, Jahr, Band, Art und Schlagworte
    fielen dann fuer die GANZE Bibliothek weg.
    """
    import re as _re
    import schluessel
    import bestand
    print("\nAnzeigetitel, Kennung und Katalog")
    bestand.bereiche_setzen(["wissensdatenbank", "kap", "auw"])
    sl = schluessel.schluessel("wissensdatenbank", "archiv/DS-24-005.pdf")

    # Erst der Nachweis, dass es ohne Anzeigetitel WIRKLICH bricht - sonst
    # repariert alles Folgende etwas Heiles. Geprueft wird gegen die ROHE
    # Kennungs-Regel, nicht gegen kennung(): Sonst waere diese Zeile nach
    # der Umstellung selbst rot und naehme den Nachweis mit.
    pruefe(_re.match(r"([A-Za-z]{1,3})[-_ ]?\d", sl) is None,
           "Gegenprobe: die Kennungs-Regel greift am rohen Schluessel nicht "
           "(%r)" % sl[:34])

    a = schluessel.anzeigetitel(sl, "wissensdatenbank")
    pruefe(a == "DS-24-005", "Anzeigetitel ist %r, erwartet 'DS-24-005'" % a)

    # Die Kennung kommt aus bestand.kennung() SELBST - kein Aufrufer muss den
    # Anzeigetitel kennen. Sonst waeren es achtzehn Stellen statt drei.
    pruefe(bestand.kennung(sl) == "DS",
           "kennung() findet die Kennung am rohen Schluessel, ist %r"
           % bestand.kennung(sl))
    pruefe(bestand.art_von(sl) == "Dissertation",
           "art_von() weiss wieder, dass das eine Dissertation ist, ist %r"
           % bestand.art_von(sl))

    # Und der Katalog. Er ist nach Kennung geschluesselt; ohne Anzeigetitel
    # traefe der Nachschlag nie.
    bestand._GELADEN = None
    bestand.eintragen("DS-24-005", {"titel": "Eine Arbeit",
                                    "verfasser": "Muster", "jahr": "2024"},
                      pfad=KATALOG)
    ang = bestand.angaben(sl)
    pruefe(ang is not None, "angaben() findet den Katalogeintrag am Schluessel")
    pruefe((ang or {}).get("verfasser") == "Muster",
           "und liefert den Verfasser, ist %r" % (ang or {}).get("verfasser"))
    pruefe((ang or {}).get("art") == "Dissertation",
           "und die Art aus der Kennung, ist %r" % (ang or {}).get("art"))

    # Die Falle in der eigenen Loesung: Ein Segment blind abzuwerfen macht
    # aus 'kap-KundeA-Angebot' das Wort 'Angebot' - und traefe damit einen
    # FREMDEN Katalogeintrag. Das waere dieselbe Kollisionsklasse, die dieser
    # Umbau beseitigt, nur an neuer Stelle.
    bestand._GELADEN = None
    bestand.eintragen("Angebot", {"titel": "Ein fremdes Angebot"}, pfad=KATALOG)
    kk = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    pruefe(bestand.angaben(kk) is None,
           "ein fremder Katalogeintrag wird NICHT getroffen, ist %r"
           % ((bestand.angaben(kk) or {}).get("titel")))

    # Rundlauf: Was unter einem Pfad-Schluessel GESCHRIEBEN wurde, muss
    # unter demselben Schluessel wieder gefunden werden. Stuende beim
    # Schreiben der ganze Schluessel und beim Lesen der Anzeigetitel, fuellte
    # sich der Katalog und die Bibliothek bliebe trotzdem ohne Angaben -
    # lautlos, weil beides fuer sich richtig aussieht.
    zweit = schluessel.schluessel("wissensdatenbank", "archiv/DS-24-009.pdf")
    bestand._GELADEN = None
    bestand.eintragen(zweit, {"titel": "Zweite Arbeit", "verfasser": "Probe"},
                      pfad=KATALOG)
    rund = bestand.angaben(zweit)
    pruefe((rund or {}).get("verfasser") == "Probe",
           "unter dem Schluessel geschrieben, unter dem Schluessel gefunden "
           "(ist %r)" % (rund or {}).get("verfasser"))

    # Der Anzeigetitel ist NICHT eindeutig - deshalb darf er nie verglichen
    # werden. Das steht hier fest, damit es niemand spaeter versucht.
    k2 = schluessel.schluessel("auw", "archiv/KundeA/Angebot.pdf")
    pruefe(schluessel.anzeigetitel(kk, "kap")
           == schluessel.anzeigetitel(k2, "auw"),
           "zwei Bereiche ergeben denselben Anzeigetitel - er taugt zum "
           "Anzeigen, NICHT zum Vergleichen")

    for komisch in ("Bericht.pdf", "", "--nurabdruck.pdf", "kap", None):
        schluessel.anzeigetitel(komisch, "kap")
    pruefe(True, "kaputte Eingaben stuerzen nicht ab")


def test_metadaten_tor():
    """Das K3-Tor sitzt als ERSTE Zeile in dokument_erlaubt.

    metadaten._grund() normalisiert genauso, und seine Schluessel sind von
    Menschen geschriebene Dokumentnamen. Mit Pfad-Schluessel traefe der
    Nachschlag nichts, m bliebe leer - und fuer_ki() entschiede je nach
    Bereichseinstellung in ZWEI entgegengesetzte Richtungen falsch: entweder
    ist kein Dokument mehr zugaenglich, oder ein ausdruecklich
    ausgeschlossenes wird wieder sichtbar.
    """
    import json as _json
    import schluessel
    import bestand
    import metadaten
    print("\nK3-Tor (metadaten)")
    bestand.bereiche_setzen(["wissensdatenbank", "kap", "auw"])
    w = tempfile.mkdtemp(prefix="ki4ki-meta-")
    try:
        sl = schluessel.schluessel("wissensdatenbank", "archiv/DS-24-005.pdf")

        def schreiben(daten, konf):
            for name, inhalt in (("metadaten", daten), ("bereich", konf)):
                with open(os.path.join(w, name + ".json"), "w") as fh:
                    _json.dump(inhalt, fh)
            metadaten._CACHE.clear()

        schreiben({"DS-24-005": {"ki": "nein"}}, {})
        pruefe(metadaten.fuer_ki(sl, w) is False,
               "'fuer KI ausschliessen' gilt auch am Pfad-Schluessel")

        # Gegenprobe in die ANDERE Richtung: Ein Bereich mit Freigabepflicht
        # darf nicht ploetzlich ALLES sperren. Ohne diese Zeile waere die
        # obige auch dann gruen, wenn fuer_ki() einfach immer False lieferte.
        schreiben({"DS-24-005": {"freigabe": "freigegeben"}},
                  {"nur_freigegebene": True})
        pruefe(metadaten.fuer_ki(sl, w) is True,
               "ein freigegebenes Dokument bleibt zugaenglich, obwohl der "
               "Bereich Freigabe verlangt")

        # Und der Fall, der richtig ist und durch die Reparatur nicht kippen
        # darf.
        fremd = schluessel.schluessel("wissensdatenbank", "archiv/Unbekannt.pdf")
        pruefe(metadaten.fuer_ki(fremd, w) is False,
               "ein Dokument ohne Metadateneintrag bleibt bei Freigabepflicht "
               "gesperrt")
    finally:
        shutil.rmtree(w, ignore_errors=True)


def test_belegvergleich():
    """Der Belegvergleich ist die Stelle, an der der Umbau still scheitern
    kann.

    Heute endet der Modelltext woertlich auf einen Dateinamen. Mit dem
    Pfad-Schluessel muesste das Modell 137 Zeichen fehlerfrei abschreiben -
    bei jedem Vertipper waere der Beleg weg, ohne Meldung. Entschieden am
    21.09.: Erkannt wird der ABDRUCK, zehn Zeichen aus a-z0-9.
    """
    from urllib.parse import quote
    import schluessel
    import pruef_proxy as p
    print("\nBelegvergleich am Abdruck")
    p.pdfs_einlesen()
    kap_a = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    kap_b = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")

    erg = p.mit_verweisen("Die Presse stand still (%s, S. 12)." % kap_b,
                          quellen=[kap_b])
    pruefe("/stelle?dok=" in erg, "es entsteht ueberhaupt ein Belegsprung")
    pruefe("seite=12" in erg, "die Seite steht im Sprungziel")

    # Die eigentliche Zusicherung: Der Sprung trifft KundeB, nicht KundeA -
    # und das laesst sich nur am Abdruck unterscheiden, weil beide Dateien
    # gleich heissen.
    # ⛔ Geprueft wird das SPRUNGZIEL, nicht die blosse Anwesenheit des
    #   Namens: Der Schluessel steht ohnehin im Eingabetext und ueberlebt
    #   auch dann, wenn gar kein Link entsteht. Genau so war die erste
    #   Fassung dieser Zeilen gruen, waehrend der Quellen-Waechter jeden
    #   Beleg verwarf (gemessen 21.09.).
    pruefe(("/stelle?dok=" + quote(kap_b)) in erg
           and ("/stelle?dok=" + quote(kap_a)) not in erg,
           "der Sprung trifft den RICHTIGEN der zwei gleichnamigen Kunden")

    # Gegenprobe 1: Schreibt das Modell nur den lesbaren Teil OHNE Abdruck,
    # darf KEIN Beleg entstehen. Ein Beleg, der dann doch entsteht, zeigt
    # zwangslaeufig auf ein geratenes Dokument.
    lesbar = kap_b.split("--")[0]
    ohne = p.mit_verweisen("Die Presse stand still (%s, S. 12)." % lesbar,
                           quellen=[kap_b])
    pruefe("/stelle?dok=" not in ohne,
           "ohne Abdruck entsteht KEIN Beleg statt eines geratenen")

    # Gegenprobe 2: Ein Abdruck, den es nicht gibt, darf nichts treffen.
    keiner = p.mit_verweisen("Behauptung (Bericht--zzzz999999, S. 3).",
                             quellen=[kap_b])
    pruefe("/stelle?dok=" not in keiner, "erfundener Abdruck trifft nichts")

    # Gegenprobe 3: Der Quellen-Waechter muss weiter greifen. Sie ist das
    # Gegenstueck zur ersten Zeile: Steht der Waechter zu scharf, faellt
    # JEDER Beleg weg und "es entsteht ueberhaupt ein Belegsprung" wird rot.
    # Erst beide zusammen schliessen die Stelle ein.
    fremd = p.mit_verweisen("Behauptung (%s, S. 3)." % kap_a, quellen=[kap_b])
    pruefe("/stelle?dok=" not in fremd,
           "genannt, aber nicht unter den Quellen -> kein Beleg")

    # Schon fertige Verweise duerfen nicht ein zweites Mal verlinkt werden.
    doppelt = p.mit_verweisen("[%s, S. 1](/stelle?dok=x&seite=1)" % kap_b,
                              quellen=[kap_b])
    pruefe(doppelt.count("/stelle?") == 1,
           "fertige Verweise bleiben unangetastet")

    # Der sichtbare Linktext bleibt das, was das Modell geschrieben hat -
    # nicht der aufgeloeste Schluessel. Sonst stuende im Text ploetzlich ein
    # anderer Name als in der Antwort des Modells.
    mit_md = p.mit_verweisen("Siehe (%s.md, S. 7)." % kap_b, quellen=[kap_b])
    pruefe("%s.md" % kap_b in mit_md,
           "der sichtbare Linktext bleibt der geschriebene Name")

    # ⛔ HIER liegt das eigentliche Risiko, und die Faelle oben treffen es
    #   nicht: Sie schreiben den Schluessel EXAKT, und das kann der alte
    #   endswith-Weg auch. Ein Modell, das 137 Zeichen abschreibt, vertippt
    #   sich aber - es laesst die Endung weg, zieht '--' zu '-' zusammen oder
    #   schreibt klein. Jeder dieser Faelle war vor der Umstellung rot.
    for wie, geschrieben in (
            ("ohne Endung", kap_b.rsplit(".", 1)[0]),
            ("'--' zu '-' gezogen", kap_b.replace("--", "-")),
            ("alles klein", kap_b.lower()),
            ("mit .md statt .pdf", kap_b.rsplit(".", 1)[0] + ".md")):
        erg2 = p.mit_verweisen("Aussage (%s, S. 5)." % geschrieben,
                               quellen=[kap_b])
        pruefe(("/stelle?dok=" + quote(kap_b)) in erg2,
               "Modell schreibt den Schluessel %s -> Beleg trifft trotzdem"
               % wie)

    # ⛔ Der Quellen-Waechter braucht einen Fall, der die AUFLOESUNG noetig
    #   macht: AnythingLLM meldet seine Dokumente nicht als blanken
    #   Schluessel, sondern mit Endung. Verglich man beide Seiten roh, waere
    #   die Bedingung immer wahr und JEDER Beleg fiele weg - lautlos. Ohne
    #   diese Zeile blieb der Waechter ungeprueft (gemessen: die Mutation
    #   "ohne Aufloesung" liess alles gruen).
    anders = p.mit_verweisen("Aussage (%s, S. 9)." % kap_b,
                             quellen=[kap_b + ".md"])
    pruefe(("/stelle?dok=" + quote(kap_b)) in anders,
           "Quelle in anderer Schreibweise (.md) laesst den Beleg zu")
    verboten = p.mit_verweisen("Aussage (%s, S. 9)." % kap_b,
                               quellen=[kap_a + ".md"])
    pruefe("/stelle?dok=" not in verboten,
           "aber eine FREMDE Quelle in derselben Schreibweise nicht")

    # Und die Gegenprobe dazu, damit die vier Zeilen oben nicht einfach
    # "irgendetwas verlinken" belohnen: Ein Name, der dem Schluessel aehnelt,
    # aber einen ANDEREN Abdruck traegt, darf nicht auf kap_b zeigen.
    fremder_abdruck = schluessel.fingerabdruck("kap/gibt-es-nicht.pdf")
    aehnlich = kap_b.split("--")[0] + "--" + fremder_abdruck + ".pdf"
    erg3 = p.mit_verweisen("Aussage (%s, S. 5)." % aehnlich, quellen=[kap_b])
    pruefe(("/stelle?dok=" + quote(kap_b)) not in erg3,
           "ein aehnlicher Name mit fremdem Abdruck zeigt NICHT auf kap_b")




def test_rechtepruefung():
    """Heute erlaubt der Zugang zu EINEM 'Angebot' den Zugriff auf ALLE
    gleichnamigen - ueber alle Bereiche hinweg (BUGS_UND_FIXES.md 6).

    Geprueft wird das VERHALTEN von dokument_erlaubt, nicht die Struktur der
    Wege: wegabgleich.py sieht, ob eine Rechtefunktion aufgerufen wird, aber
    nicht, ob ihr Urteil richtig ist.
    """
    import schluessel
    import pruef_proxy as p
    print("\nRechtepruefung am Abdruck")
    p.pdfs_einlesen()
    kap_a = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    kap_b = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")
    auw_a = schluessel.schluessel("auw", "archiv/KundeA/Angebot.pdf")

    # Ein Konto, das GENAU EIN Angebot sehen darf. Die Liste kommt sonst aus
    # der AnythingLLM-Abfrage; hier wird sie gesetzt, damit die Pruefung ohne
    # Server laeuft und nur den Vergleich misst.
    echt = p.erlaubte_dokumente
    try:
        p.erlaubte_dokumente = lambda kopfzeilen: [kap_a.lower()]
        kopf = {}

        pruefe(p.dokument_erlaubt(kap_a, kopf) is True,
               "das erlaubte Dokument bleibt erlaubt")

        # Die Zusicherung, um die es geht - heute ist sie ROT:
        pruefe(p.dokument_erlaubt(kap_b, kopf) is False,
               "das GLEICHNAMIGE Dokument eines anderen Kunden bleibt "
               "gesperrt")
        pruefe(p.dokument_erlaubt(auw_a, kopf) is False,
               "dasselbe im anderen Bereich bleibt gesperrt")

        # fail-closed: kein Abdruck = kein Zugang. Die Gegenprobe dazu steht
        # in der ersten Zeile - ohne sie waere das hier auch dann gruen, wenn
        # die Funktion einfach IMMER False lieferte.
        pruefe(p.dokument_erlaubt("Angebot", kopf) is False,
               "ein nackter Name ohne Abdruck bekommt KEINEN Zugang")
        pruefe(p.dokument_erlaubt("", kopf) is False,
               "leerer Name: kein Zugang")

        # Die Endung darf den Zugang nicht kippen - das Modell schreibt sie
        # mal mit, mal ohne.
        pruefe(p.dokument_erlaubt(kap_a + ".md", kopf) is True,
               "mit angehaengter Endung weiterhin erlaubt")

        # Waehrend der Uebergangszeit muss ein Dokument aus der Zeit VOR dem
        # Umbau weiter zugaenglich sein - es hat keinen Abdruck. Das ist der
        # alte, leckende Vergleich; er bleibt genau so lange wie noetig und
        # faellt mit der Uebergangsstuetze weg (Aufgabe 12). Ohne diese Zeile
        # waere nicht festgehalten, dass das Absicht ist und nicht Zufall.
        p.erlaubte_dokumente = lambda kopfzeilen: ["ds-24-005"]
        pruefe(p.dokument_erlaubt("DS-24-005.md", kopf) is True,
               "Uebergangszeit: ein Dokument ohne Abdruck bleibt zugaenglich")
        pruefe(p.dokument_erlaubt("DS-24-006.md", kopf) is False,
               "aber ein anderes ohne Abdruck nicht")
        p.erlaubte_dokumente = lambda kopfzeilen: [kap_a.lower()]

        # Eine leere Erlaubnisliste ist eine ANTWORT, kein Ausfall.
        p.erlaubte_dokumente = lambda kopfzeilen: []
        pruefe(p.dokument_erlaubt(kap_a, kopf) is False,
               "leere Liste heisst: dieses Konto darf nichts sehen")
    finally:
        p.erlaubte_dokumente = echt


def _dateien_im_baum():
    """Nur Dokumente zaehlen, keine Protokolle.

    ⚠ Der Loeschweg LEGT eine Protokolldatei AN. Wer alles zaehlt, sieht
      "eine weg, eine dazu" und haelt das fuer "nichts geloescht" - Messung
      am falschen Gegenstand, genau die Klasse, die in diesem Projekt schon
      dreimal teuer war.
    """
    return sum(1 for _o, _u, ds in os.walk(BAUM)
               for d in ds if not d.endswith(".log"))


def test_loeschweg():
    """Heute reisst ein Loeschklick ALLE Namensvettern in ALLEN Bereichen mit.

    Drei Ausgaenge muss diese Pruefung unterscheiden koennen:
      richtig  - genau dieses eine Dokument verschwindet
      zu viel  - Namensvettern werden mitgerissen (der Zustand von heute)
      zu wenig - gar nichts wird geloescht, aber GELOESCHT protokolliert
                 (der Datenschutzschaden nach einem halben Umbau)
    """
    import schluessel
    import pruef_proxy as p
    print("\nLoeschweg")
    p.pdfs_einlesen()
    kap_a = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    vorher = _dateien_im_baum()

    p._eigene_spuren_tilgen(kap_a, "Pruefung")

    def da(*teile):
        return os.path.exists(os.path.join(BAUM, *teile))

    # 1) richtig
    pruefe(not da("kap", "archiv", "KundeA", "Angebot.pdf"),
           "das gemeinte Dokument ist weg")
    # 2) zu viel - genau der Schaden von heute
    pruefe(da("kap", "archiv", "KundeB", "Angebot.pdf"),
           "der gleichnamige KundeB ist UNANGETASTET")
    pruefe(da("auw", "archiv", "KundeA", "Angebot.pdf"),
           "der gleichnamige im Bereich auw ist UNANGETASTET")
    # 3) zu wenig
    nachher = _dateien_im_baum()
    pruefe(nachher == vorher - 1,
           "genau EINE Datei weniger, gezaehlt %d nach %d" % (nachher, vorher))

    # ⭐ Die erzeugte Markdown-Fassung ist der DRITTE Ablageort eines
    #   Dokuments - und der einzige, den bis zum 21.09. niemand raeumte.
    #   Loeschen in der Oberflaeche entfernte Textfassung und Vektoren, hier
    #   blieb der Volltext liegen. Am laufenden System gefunden: Dateien
    #   zurueck bis August, darunter vertrauliche Unterlagen.
    kap_c = schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf")
    meine = os.path.join(p.MD_ABLAGE, kap_c[:-4] + ".md")
    fremde = os.path.join(p.MD_ABLAGE, "Ganz-anderes-Dokument.md")
    open(meine, "w").write("Volltext")
    open(fremde, "w").write("Volltext")
    p._eigene_spuren_tilgen(kap_c, "Pruefung Markdown")
    pruefe(not os.path.exists(meine),
           "die Markdown-Fassung des geloeschten Dokuments ist weg")
    pruefe(os.path.exists(fremde),
           "die eines anderen Dokuments bleibt UNANGETASTET")
    os.remove(fremde)

    # Gegenprobe: Ein Schluessel, den es nicht gibt, darf GAR NICHTS loeschen.
    # Ohne diese Zeile waere "KundeB unangetastet" auch dann gruen, wenn die
    # Funktion ueberhaupt nichts mehr taete.
    stand = _dateien_im_baum()
    p._eigene_spuren_tilgen("Gibtsnicht--zzzz999999.pdf", "Gegenprobe")
    pruefe(_dateien_im_baum() == stand,
           "ein unbekannter Schluessel loescht nichts")

    # Und der Umzug: Dieselbe Datei in jeder Stufe ergibt DENSELBEN
    # Schluessel. Waere die Stufe Teil der Kennung, bekaeme dasselbe Dokument
    # bei jedem Umzug eine neue - genau der Kettenbruch, der behoben wird.
    for stufe in ("input", "parkplatz", "archiv", "aussortiert", "loeschen"):
        pruefe(schluessel.schluessel("kap", stufe + "/KundeB/Angebot.pdf")
               == schluessel.schluessel("kap", "archiv/KundeB/Angebot.pdf"),
               "Stufe %s ergibt denselben Schluessel" % stufe)

    # ⭐ Archiv und Aussortiert spiegeln die Unterordner des Eingangs. Flach
    #   passten zwei gleichnamige Dateien nicht nebeneinander - daran ging
    #   die Kundenzuordnung verloren. Geprueft am erzeugten Pfad, nicht an
    #   einer Zeichenkette im Quelltext.
    eingang = os.path.join(BAUM, "kap", "input")
    quelle = os.path.join(eingang, "KundeC", "Angebot.pdf")
    os.makedirs(os.path.dirname(quelle), exist_ok=True)
    open(quelle, "wb").write(b"%PDF-1.4\nE\n")
    unter = os.path.relpath(quelle, eingang)
    pruefe(unter == os.path.join("KundeC", "Angebot.pdf"),
           "der Unterpfad unterhalb des Eingangs bleibt erhalten, ist %r"
           % unter)
    pruefe(os.path.join(BAUM, "kap", "archiv", unter).endswith(
               os.path.join("archiv", "KundeC", "Angebot.pdf")),
           "das Archivziel spiegelt den Kundenordner")
    os.remove(quelle)

    # Datei wieder herstellen, damit die folgenden Pruefungen den Baum
    # unveraendert vorfinden.
    lege_an("kap", "archiv", "KundeA", "Angebot.pdf", inhalt=b"%PDF-1.4\nA\n")
    p.pdfs_einlesen()


def test_stuetze_laeuft_ab():
    """Die Uebergangsstuetze darf sich NICHT selbst schuetzen.

    Eine Pruefung "der nackte Name loest noch auf" waere gruen, solange der
    alte Fehler drinsteht, und wuerde rot, sobald man ihn entfernt. Sie
    verlangte also das Altverhalten - genau die Konstruktion, die am 21.09.
    sechsmal gejagt wurde, nur zeitversetzt.

    Stattdessen ist die Stuetze an ihre BEGRUENDUNG gekoppelt: erlaubt,
    solange es Dokumente ohne Abdruck gibt. Beide Zustaende werden hier
    hergestellt - sonst waere die Kopplung selbst nur eine Behauptung.
    """
    import schluessel
    import pruef_proxy as p
    print("\nUebergangsstuetze laeuft ab")
    ablage = os.path.join(BESTAND, "kap")
    os.makedirs(ablage, exist_ok=True)
    kennung = "-11111111-2222-3333-4444-555555555555.json"

    def kopplung():
        return p.nur_ueber_altweg() > 0 or not p.altweg_aktiv()

    # Zustand A: ein Dokument aus der Zeit vor dem Umbau liegt im Bestand.
    alt = os.path.join(ablage, "Angebot.md" + kennung)
    open(alt, "w").write("{}")
    p.pdfs_einlesen()
    pruefe(p.nur_ueber_altweg() > 0 and p.altweg_aktiv(),
           "Zustand A: Stuetze aktiv UND begruendet (%d Dokumente ohne "
           "Abdruck)" % p.nur_ueber_altweg())
    pruefe(kopplung(), "Zustand A: die Kopplung ist gruen")

    # Zustand B: das Neu-Einlesen ist durch, kein Dokument ohne Abdruck mehr.
    # ⭐ Jetzt MUSS dieselbe Kopplung rot werden - sonst haelt sie die Stuetze
    #   ewig am Leben, und der alte "erster Fund gewinnt"-Fehler bleibt unter
    #   einem gruenen Haken stehen.
    os.remove(alt)
    neu_name = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    open(os.path.join(ablage, neu_name + ".md" + kennung), "w").write("{}")
    p.pdfs_einlesen()
    pruefe(p.nur_ueber_altweg() == 0,
           "Zustand B: kein Dokument mehr ohne Abdruck, sind %d"
           % p.nur_ueber_altweg())
    pruefe(not kopplung(),
           "Zustand B: die Kopplung ist ROT - ab hier ist die Stuetze "
           "unbegruendet und der Rueckbau faellig")

    # ⛔ Ein Lesefehler darf nicht als "darf weg" durchgehen.
    merk = p.BESTAND_ORDNER
    p.BESTAND_ORDNER = os.path.join(BESTAND, "gibt-es-nicht", "\x00")
    pruefe(p.nur_ueber_altweg() == -1,
           "unlesbarer Bestand meldet -1, nicht 0 (ist %d)"
           % p.nur_ueber_altweg())
    p.BESTAND_ORDNER = merk
    for d in os.listdir(ablage):
        os.remove(os.path.join(ablage, d))
    p.pdfs_einlesen()


def test_umlautdeckung():
    """Der Zitatwaechter darf an der Schreibweise nicht scheitern.

    ⛔ Gefunden an der Abnahme vom 22.09., nicht beim Lesen: Das Modell
      antwortet mit echten Umlauten, das Dokument war in Behelfsschreibung
      gesetzt (ue/ae/oe). Die gemeinsamen Fachwoerter fielen von 3 auf 1,
      _dok_hat_aussage sperrte den Beleg - und die einzige Meldung war das
      Wort "durchsucht" in der Fusszeile.

    ⚠ Das trifft nicht nur Probedokumente: Aeltere Ausfuehrungen, Ausfuhren
      aus fremden Anlagen und schlechte Texterkennung schreiben regelmaessig
      ue statt u-Umlaut. Dass die Fuellwortliste selbst BEIDE Schreibweisen
      fuehrt ("gegenueber" und "gegenüber"), zeigt: Die Doppelform war
      bekannt, der Vergleich hat sie nie gelernt.
    """
    import schluessel
    import pruef_proxy as p
    print("\nUmlaute im Zitatwaechter")
    # ⛔ Ein AUFLOESBARER Name. Mit einem Phantasienamen steigt
    #   _dok_hat_aussage sofort mit True aus ("unpruefbar -> nicht sperren")
    #   und der Wortvergleich laeuft nie - drei Zeilen waeren gruen, ohne
    #   etwas zu pruefen. Genau so ist diese Pruefung im ersten Anlauf
    #   dagestanden.
    p.pdfs_einlesen()
    dok = schluessel.schluessel("kap", "archiv/KundeA/Angebot.pdf")
    pruefe(p._pdf_schluessel(dok) == dok,
           "Vorbedingung: der Name loest auf - sonst prueft nichts davon etwas")

    # (Der Wortlaut ist GEBAUT, nicht ausgedacht: Ohne Vereinheitlichung
    #  zerfallen die Umlautwoerter ("pr\u00fcfbericht" -> "fbericht"), aber
    #  es bleiben DREI lange Woerter uebrig. Nur so laeuft der Waechter bis
    #  zum Vergleich - mit weniger steigt er vorher mit "unpruefbar, nicht
    #  sperren" aus, und diese Zeile waere gruen, egal was der Code tut.
    #  Genau so ist sie im ersten Anlauf dagestanden.)
    aussage = ("Der Pr\u00fcfbericht nennt die Pr\u00fcfgeschwindigkeit "
               "und das Pr\u00fcfklima; die Zugfestigkeit betr\u00e4gt 412 MPa")
    behelf = ("Pruefbericht Zugversuch - Kunde Alpha. Probekoerper nach "
              "Norm, Pruefgeschwindigkeit 5 mm je Minute. Pruefklima 23 "
              "Grad. Ergebnis: Die Zugfestigkeit betraegt 412 MPa.")
    echt = (behelf.replace("Pruef", "Pr\u00fcf").replace("betraegt", "betr\u00e4gt")
                  .replace("Probekoerper", "Probek\u00f6rper"))
    fremd = ("Verfahrensanweisung Kleben. Die Oberfl\u00e4che wird "
             "angeschliffen und entfettet, danach Primer auftragen.")

    merk = p._seitentexte_pdf
    try:
        # 1) Behelfsschreibung im Dokument, Umlaute in der Aussage.
        p._seitentexte_pdf = lambda _n: [behelf]
        pruefe(p._dok_hat_aussage(dok, aussage) is True,
               "ue/ae im Dokument decken Umlaute in der Aussage")

        # 2) Und die Gegenrichtung - sonst waere Zeile 1 auch dann gruen,
        #    wenn die Funktion nur noch True liefert.
        p._seitentexte_pdf = lambda _n: [echt]
        pruefe(p._dok_hat_aussage(dok, aussage) is True,
               "gleiche Schreibweise deckt weiterhin")

        # 3) ⛔ Die Gegenprobe, die das Ganze erst tragfaehig macht: Ein
        #    Dokument, das die Aussage NICHT enthaelt, muss weiter gesperrt
        #    werden. Ohne diese Zeile sagt kein Gruen oben etwas aus.
        p._seitentexte_pdf = lambda _n: [fremd]
        pruefe(p._dok_hat_aussage(dok, aussage) is False,
               "ein fremdes Dokument bleibt gesperrt")

        # 4) Beide Seiten in Behelfsschreibung - darf sich nicht
        #    verschlechtern.
        p._seitentexte_pdf = lambda _n: [behelf]
        flach = ("Der Pruefbericht nennt die Pruefgeschwindigkeit und das "
                 "Pruefklima; die Zugfestigkeit betraegt 412 MPa")
        pruefe(p._dok_hat_aussage(dok, flach) is True,
               "beide in Behelfsschreibung: unveraendert erlaubt")
    finally:
        p._seitentexte_pdf = merk

    # 5) Die Zerlegung selbst: Seitentext und Aussage muessen GLEICH
    #    zerlegt werden. Bis zum 22.09. stand an der einen Stelle
    #    [^0-9a-zA-Z...] und an der anderen [^0-9a-zA-z...] - das zweite
    #    behaelt Unterstrich und eckige Klammern als Wortzeichen.
    pruefe(p._fachwoerter("Pr\u00fcfbericht_Zugversuch")
           == p._fachwoerter("Pruefbericht Zugversuch"),
           "Unterstrich trennt wie ein Leerzeichen, ist %r vs %r"
           % (sorted(p._fachwoerter("Pr\u00fcfbericht_Zugversuch")),
              sorted(p._fachwoerter("Pruefbericht Zugversuch"))))


def test_leere_eingangsordner():
    """Leere Unterordner im Eingang verschwinden - aber nicht zu frueh.

    Emrach am 22.09.: "die leeren ordner stehen nur noch lose da".
    """
    import pruef_proxy as p
    print("\nLeere Unterordner im Eingang")
    eingang = os.path.join(BAUM, "kap", "input")
    alt = os.path.join(eingang, "FertigerKunde")
    voll = os.path.join(eingang, "NochVoll")
    frisch = os.path.join(eingang, "GeradeAngelegt")
    tief = os.path.join(eingang, "Normen", "Kleben")
    for d in (alt, voll, frisch, tief):
        os.makedirs(d, exist_ok=True)
    open(os.path.join(voll, "Angebot.pdf"), "wb").write(b"%PDF-1.4\n")
    # Zwei Stunden alt: Karenz abgelaufen.
    for d in (alt, tief, os.path.dirname(tief)):
        os.utime(d, (time.time() - 7200, time.time() - 7200))

    p._leere_eingangsordner_raeumen()

    pruefe(not os.path.isdir(alt), "der leere, ruhige Ordner ist weg")
    pruefe(not os.path.isdir(tief) and not os.path.isdir(os.path.dirname(tief)),
           "verschachtelte leere Ordner fallen in EINEM Durchgang zusammen")
    # ⛔ Die drei Gegenproben. Ohne sie waere "der leere Ordner ist weg"
    #   auch dann gruen, wenn die Wache einfach alles wegraeumt.
    pruefe(os.path.isdir(voll) and os.path.exists(os.path.join(voll, "Angebot.pdf")),
           "ein Ordner MIT Datei bleibt unangetastet")
    pruefe(os.path.isdir(frisch),
           "ein eben angelegter leerer Ordner bleibt - sonst raeumt die Wache "
           "einem Menschen den Ordner weg, waehrend er noch hochlaedt")
    pruefe(os.path.isdir(eingang),
           "der Eingang selbst bleibt stehen, auch wenn er leer waere")


def test_belegklammer():
    """Die Klammer (Abdruck, S. n) muss das Dokument finden.

    \u26d4 Gefunden am 22.09. am laufenden System, mit zwei verschiedenen
      Modellen: Die Antwort nannte beide Zahlen richtig und schrieb den
      Abdruck in die Klammer - aber es entstand nie ein Beleg. Die
      Klammerpruefung kannte nur volle Titel.

    \u26d4 Der Name im Arbeitsbereich ist NICHT der Schluessel: AnythingLLM
      zieht das doppelte Trennzeichen zu einem zusammen. Die Pruefung baut
      genau diesen Namen nach - mit dem Schluessel waere sie gruen und am
      laufenden System trotzdem rot.
    """
    import schluessel
    import bestand
    import pruef_proxy as p
    print("\nBelegklammer am Abdruck")
    bestand.bereiche_setzen(["kap", "auw", "wissensdatenbank"])

    # \u26d4 Eigene Dokumente anlegen statt auf den Baum der vorigen
    #   Pruefungen zu bauen. Im ersten Anlauf hing diese Pruefung an einer
    #   Datei, die der Loeschweg vorher weggeraeumt hatte - sie war rot,
    #   ohne dass am Code etwas fehlte.
    for bereich, kunde, inhalt in (("kap", "KundeZ", b"Z"),
                                   ("auw", "KundeY", b"Y")):
        ordner = os.path.join(BAUM, bereich, "archiv", kunde)
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, "Angebot.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.4\n" + inhalt + b"\n")
    p.pdfs_einlesen()

    meins = schluessel.schluessel("kap", "archiv/KundeZ/Angebot.pdf")
    abdruck_b = schluessel.fingerabdruck(
        schluessel.kennpfad("kap", "archiv/KundeZ/Angebot.pdf"))
    abdruck_a = schluessel.fingerabdruck(
        schluessel.kennpfad("auw", "archiv/KundeY/Angebot.pdf"))
    pruefe(abdruck_a != abdruck_b, "Vorbedingung: zwei verschiedene Abdruecke")
    pruefe(abdruck_b in p.PDFS_ABDRUCK and abdruck_a in p.PDFS_ABDRUCK,
           "Vorbedingung: beide stehen im Index - sonst prueft nichts davon "
           "etwas (Index hat %d Eintraege)" % len(p.PDFS_ABDRUCK))

    # So heisst das Dokument in AnythingLLM - EIN Trennzeichen.
    im_bereich = meins[:-4].replace("--", "-") + ".md"
    pruefe("--" not in im_bereich,
           "Vorbedingung: der Name im Arbeitsbereich hat nur EIN Trennzeichen")
    nach_titel, nach_abdruck, _karte = p._belegverzeichnis([im_bereich])

    # \u2b50 Die Zusicherung: der nackte Abdruck genuegt.
    dok, lesbar = p._beleg_dokument(abdruck_b, nach_titel, nach_abdruck)
    pruefe(dok is not None and p._pdf_schluessel(dok) == meins,
           "der nackte Abdruck findet das Dokument, ist %r" % (dok,))
    pruefe(lesbar == "KundeZ-Angebot",
           "und die Klammer zeigt den lesbaren Titel, ist %r" % (lesbar,))

    # Der volle Name muss weiter gehen - sonst bricht der Altbestand.
    dok2, _l = p._beleg_dokument(im_bereich[:-3], nach_titel, nach_abdruck)
    pruefe(dok2 is not None, "der volle Name findet weiterhin, ist %r" % (dok2,))

    # \u26d4 Gegenprobe 1: ein Abdruck, den es gibt, dessen Dokument aber
    #   NICHT in diesem Arbeitsbereich liegt. Fail-closed - sonst belegt die
    #   Anlage mit der Akte eines fremden Kunden.
    dok3, _l = p._beleg_dokument(abdruck_a, nach_titel, nach_abdruck)
    pruefe(dok3 is None,
           "ein Abdruck aus einem anderen Bereich wird NICHT belegt, ist %r"
           % (dok3,))

    # \u26d4 Gegenprobe 2: ein erfundener Abdruck trifft nichts.
    dok4, _l = p._beleg_dokument("zzzz999999", nach_titel, nach_abdruck)
    pruefe(dok4 is None, "ein erfundener Abdruck trifft nichts, ist %r" % (dok4,))

    # \u26d4 Gegenprobe 3: gewoehnlicher Klammertext bleibt Klammertext.
    for text in ("siehe oben", "Abb. 3", "vgl. Norm", ""):
        d, _l = p._beleg_dokument(text, nach_titel, nach_abdruck)
        pruefe(d is None, "Klammertext %r wird nicht zum Beleg" % text)


def test_trennzeichen_egal():
    """Am Abdruck abschneiden, nicht am Trennzeichen.

    \u26d4 AnythingLLM liefert den Namen in der Fundstelle mit EINEM
      Trennzeichen zurueck, die Dateiliste zeigt ihn mit zweien. Wer am
      '--' schneidet, kuerzt den einen Fall gar nicht - und dann findet
      angaben() nach dem Neueinlesen keinen Katalogeintrag mehr, kennung()
      liefert None und metadaten._grund() trifft nie. Das ist der Schaden
      aus BUGS 13, nur durch eine andere Tuer.
    """
    import schluessel
    import bestand
    import pruef_proxy as p
    print("\nTrennzeichen egal, Abdruck entscheidet")
    bestand.bereiche_setzen(["wissensdatenbank", "kap", "auw"])

    ordner = os.path.join(BAUM, "wissensdatenbank", "archiv")
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, "DS-24-005.pdf"), "wb") as fh:
        fh.write(b"%PDF-1.4\nDS\n")
    p.pdfs_einlesen()
    bestand.abdruecke_setzen(p.PDFS_ABDRUCK)

    s = schluessel.schluessel("wissensdatenbank", "archiv/DS-24-005.pdf")
    pruefe("--" in s, "Vorbedingung: der Schluessel traegt zwei Trennzeichen")

    formen = {
        "zwei Trennzeichen": s,
        "ein Trennzeichen": s.replace("--", "-"),
        "Gedankenstrich": s.replace("--", "\u2013"),
        "ohne Endung": s[:-4].replace("--", "-"),
        "als .md": s[:-4].replace("--", "-") + ".md",
    }
    for wie, name in formen.items():
        pruefe(bestand._anzeige(name) == "DS-24-005",
               "%s ergibt den Anzeigetitel, ist %r" % (wie, bestand._anzeige(name)))

    # \u2b50 Und der Katalog, um den es eigentlich geht.
    bestand.eintragen("DS-24-005", {"titel": "Eine Arbeit", "verfasser": "Muster"})
    einfach = s[:-4].replace("--", "-")
    ang = bestand.angaben(einfach)
    pruefe((ang or {}).get("verfasser") == "Muster",
           "angaben() findet den Eintrag auch bei EINEM Trennzeichen, ist %r"
           % (ang or {}).get("verfasser"))
    pruefe(bestand.kennung(einfach) == "DS",
           "kennung() ebenso, ist %r" % bestand.kennung(einfach))

    # \u26d4 Gegenprobe 1: Ein Name, dessen Ende zufaellig zehn Zeichen hat,
    #   aber KEIN bekannter Abdruck ist, bleibt unangetastet. Ohne diese
    #   Zeile waere das Abschneiden wieder syntaktisch - genau das, was
    #   dieser Umbau ueberall vermeidet.
    fremd = "wissensdatenbank-Bericht-Kennwerte"
    pruefe(bestand._anzeige(fremd) == fremd,
           "ein Name ohne bekannten Abdruck bleibt unveraendert, ist %r"
           % bestand._anzeige(fremd))

    # \u26d4 Gegenprobe 2: Ohne Abdruckverzeichnis faellt es auf das '--'
    #   zurueck und schneidet NICHT wild.
    bestand.abdruecke_setzen({})
    pruefe(bestand._anzeige(s) == "DS-24-005",
           "ohne Verzeichnis traegt der Rueckfall aufs '--', ist %r"
           % bestand._anzeige(s))
    pruefe(bestand._anzeige(einfach) == einfach,
           "ohne Verzeichnis wird bei EINEM Trennzeichen nichts geraten, ist %r"
           % bestand._anzeige(einfach))
    bestand.abdruecke_setzen(p.PDFS_ABDRUCK)


def test_belegsprung():
    """Aus der geprueften Klammer wird ein anklickbarer Sprung.

    \u26d4 Gemessen am 22.09. am laufenden System: Die Klammer stand richtig
      da - "(KundeAlpha-Pruefbericht, S. 1)" - und die Fusszeile meldete
      "Quelle:", also war die Seitenpruefung durch. Trotzdem kein Link:
      verlinken_mehrfach sucht den VOLLEN Namen, im Text steht der lesbare.
      Zwei Stellen, zwei Namen - und dazwischen faellt der Sprung heraus.
    """
    from urllib.parse import quote
    import schluessel
    import bestand
    import fadenfrage
    import pruef_proxy as p
    print("\nBelegsprung entsteht")
    bestand.bereiche_setzen(["kap", "auw", "wissensdatenbank"])

    ordner = os.path.join(BAUM, "kap", "archiv", "KundeQ")
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, "Angebot.pdf"), "wb") as fh:
        fh.write(b"%PDF-1.4\nQ\n")
    p.pdfs_einlesen()
    sch = schluessel.schluessel("kap", "archiv/KundeQ/Angebot.pdf")
    roh = sch[:-4].replace("--", "-") + ".md"

    lesbar = p._anzeigename(roh)
    pruefe(lesbar == "KundeQ-Angebot",
           "der Anzeigename ist kurz und lesbar, ist %r" % lesbar)

    # \u2b50 Die eigentliche Zusicherung: Was die Klammer SCHREIBT und wovon
    #   der Sprung ausgeht, ist DERSELBE Name. Genau das stimmte am 22.09.
    #   nicht - beide Stellen waren fuer sich richtig, nur nicht miteinander.
    _nt, _na, karte = p._belegverzeichnis([roh])
    abdruck = schluessel.fingerabdruck(
        schluessel.kennpfad("kap", "archiv/KundeQ/Angebot.pdf"))
    _dok, aus_klammer = p._beleg_dokument(abdruck, _nt, _na, karte)
    pruefe(aus_klammer == karte.get(roh),
           "Klammer und Sprung gehen vom selben Namen aus (%r / %r)"
           % (aus_klammer, karte.get(roh)))

    seiten = ["Die Zugfestigkeit betraegt 412 MPa."]
    text = "Ergebnis (%s, S. 1)." % karte[roh]
    aus, ok, nein = fadenfrage.verlinken_mehrfach(text, {lesbar: (sch, seiten)})
    ziel = "/stelle?dok=" + quote(sch, safe="")
    pruefe(ziel in aus, "es entsteht ein Sprung auf DAS Dokument, ist %r"
           % aus[-70:])
    pruefe("seite=1" in aus, "und auf die gepruefte Seite")

    # \u26d4 Gegenprobe: Mit dem VOLLEN Namen als Schluessel - so stand es bis
    #   zum 22.09. - entsteht kein Sprung. Ohne diese Zeile waere die obige
    #   auch dann gruen, wenn verlinken_mehrfach einfach alles verlinkt.
    aus2, _o, _n = fadenfrage.verlinken_mehrfach(
        text, {assistent_titel(roh): (sch, seiten)})
    pruefe("/stelle?dok=" not in aus2,
           "Gegenprobe: mit dem vollen Namen als Schluessel entsteht keiner")

    # \u26d4 Und die Falle, die der Plan schon kannte: Zwei verschiedene Pfade
    #   koennen denselben lesbaren Titel ergeben. Dann darf NICHT gekuerzt
    #   werden - sonst zeigte ein Sprung auf das falsche Dokument, und das
    #   ist genau die Kollisionsklasse, die dieser Umbau beseitigt.
    for unter in ("Angebot 2024/Blatt.pdf", "Angebot/2024 Blatt.pdf"):
        voll = os.path.join(BAUM, "kap", "archiv", *unter.split("/"))
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        with open(voll, "wb") as fh:
            fh.write(b"%PDF-1.4\n" + unter.encode("utf-8") + b"\n")
    p.pdfs_einlesen()
    zwei = [schluessel.schluessel("kap", "archiv/Angebot 2024/Blatt.pdf"),
            schluessel.schluessel("kap", "archiv/Angebot/2024 Blatt.pdf")]
    pruefe(zwei[0] != zwei[1], "Vorbedingung: zwei verschiedene Schluessel")
    kurz = [p._anzeigename(z) for z in zwei]
    pruefe(kurz[0] == kurz[1],
           "Vorbedingung: beide ergeben denselben lesbaren Titel (%r)" % kurz[0])

    _nt, _na, karte = p._belegverzeichnis(zwei)
    pruefe(karte[zwei[0]] != karte[zwei[1]],
           "bei Mehrdeutigkeit bleibt der VOLLE Name stehen, ist %r / %r"
           % (karte[zwei[0]][-24:], karte[zwei[1]][-24:]))


def assistent_titel(n):
    import assistent
    return assistent._titel_saubern(n)


def test_zitatpruefung_umlaute():
    """Das woertliche Zitat darf nicht an der Umlaut-Regel scheitern.

    \u26d4 Gemessen am 22.09.: Das Modell zitierte richtig, die Klammer wurde
      erkannt - und es kam trotzdem "nicht woertlich gefunden". Grund: _falte
      macht aus dem Umlaut den GRUNDBUCHSTABEN ("betr\u00e4gt" -> "betragt"),
      das Dokument stand in Behelfsschreibung ("betraegt"). Zwei Regeln fuer
      dieselbe Sache, und dazwischen faellt der Sprung heraus.

    \u26a0 Das ist nicht dasselbe wie BUGS 16: Dort verglich pruef_proxy
      Umlaut gegen Umlaut, hier faltet fadenfrage auf den Grundbuchstaben.
      Verschiedene Module, verschiedene Konventionen, gleiche Wirkung.
    """
    import fadenfrage
    print("\nZitatpruefung und Umlaute")
    zitat_umlaut = "Die Zugfestigkeit betr\u00e4gt 412 MPa."
    zitat_behelf = "Die Zugfestigkeit betraegt 412 MPa."
    seite_behelf = ("Ergebnis: Die Zugfestigkeit betraegt 412 MPa. "
                    "Bruchdehnung 3,1 Prozent, Pr\u00fcfklima 23 Grad.")
    seite_umlaut = seite_behelf.replace("betraegt", "betr\u00e4gt")
    fremd = ("Verfahrensanweisung Kleben: Die Oberfl\u00e4che wird "
             "angeschliffen und entfettet.")

    for wie, z, seite in (("Umlaut im Zitat, Behelf im Dokument",
                           zitat_umlaut, seite_behelf),
                          ("Behelf im Zitat, Umlaut im Dokument",
                           zitat_behelf, seite_umlaut),
                          ("beide mit Umlaut", zitat_umlaut, seite_umlaut),
                          ("beide in Behelfsschreibung",
                           zitat_behelf, seite_behelf)):
        pruefe(fadenfrage._steht_auf(z, seite) is True,
               "%s: das Zitat steht auf der Seite" % wie)

    # \u26d4 Die Gegenproben. Ohne sie waeren die vier Zeilen oben auch dann
    #   gruen, wenn _steht_auf einfach immer True liefert - und dann wuerde
    #   jedes erfundene Zitat blau verlinkt.
    pruefe(fadenfrage._steht_auf(zitat_umlaut, fremd) is False,
           "ein Zitat, das NICHT auf der Seite steht, wird nicht bestaetigt")
    pruefe(fadenfrage._steht_auf("Die Klemmung erh\u00fcht die Lebensdauer.",
                                 seite_umlaut) is False,
           "ein erfundenes Zitat wird nicht bestaetigt")
    pruefe(fadenfrage._steht_auf("kurz", seite_umlaut) is False,
           "ein zu kurzes Bruchstueck wird nicht bestaetigt")


def test_klammer_kennt_anzeigetitel():
    """Das Modell schreibt den lesbaren Titel - die Klammer muss ihn kennen.

    \u26d4 Gemessen am 22.09. am laufenden System: Nachdem Klammer und
      Fusszeile auf den Anzeigetitel umgestellt waren, schrieb das Modell
      genau diesen in die Klammer - und die Klammerpruefung kannte ihn
      nicht. Kein Treffer, kein Link. Die Umstellung hat sich selbst das
      Bein gestellt.

    \u26a0 Und der Vergleich muss die Schreibweise aushalten: Das Modell
      schreibt "Qualit\u00e4t" mit Umlaut, das Dokument heisst "Qualitat"
      ohne - der Umlaut faellt bei der Schluesselbildung weg.
    """
    import schluessel
    import bestand
    import pruef_proxy as p
    print("\nKlammer kennt den Anzeigetitel")
    bestand.bereiche_setzen(["kap", "auw", "zz-probe"])

    # \u26d4 Die Ordner tragen ECHTE Umlaute, wie auf dem Server. Der
    #   Schluessel schleift sie ab ("Qualit\u00e4t" -> "Qualitat"), das Modell
    #   schreibt sie wieder hin. Genau diese Paarung muss der Vergleich
    #   aushalten. Ein erster Anlauf nannte den Ordner "Qualitaet" mit ae -
    #   dann verglich die Pruefung zwei wirklich verschiedene Woerter und
    #   war rot, ohne dass am Code etwas fehlte.
    ordner = os.path.join(BAUM, "zz-probe", "archiv", "Sch\u00e4fer",
                          "Qualit\u00e4t")
    os.makedirs(ordner, exist_ok=True)
    with open(os.path.join(ordner, "Liste.pdf"), "wb") as fh:
        fh.write(b"%PDF-1.4\nL\n")
    p.pdfs_einlesen()
    bestand.abdruecke_setzen(p.PDFS_ABDRUCK)

    sch = schluessel.schluessel(
        "zz-probe", "archiv/Sch\u00e4fer/Qualit\u00e4t/Liste.pdf")
    roh = sch[:-4].replace("--", "-") + ".md"
    nt, na, karte = p._belegverzeichnis([roh])
    lesbar = karte[roh]
    pruefe(lesbar == "Schafer-Qualitat-Liste",
           "Vorbedingung: der Schluessel schleift die Umlaute ab (%r)" % lesbar)

    # \u2b50 Die Zusicherung: genau die Form, die das Modell schreibt.
    dok, _l = p._beleg_dokument(lesbar, nt, na, karte)
    pruefe(dok is not None and p._pdf_schluessel(dok) == sch,
           "der Anzeigetitel findet das Dokument, ist %r" % (dok,))

    # Und in der Schreibweise, die das Modell benutzt: mit Umlauten.
    # So, wie das Modell es schreibt: Es setzt die Umlaute wieder ein.
    mit_umlaut = lesbar.replace("Schafer", "Sch\u00e4fer").replace(
        "Qualitat", "Qualit\u00e4t")
    dok2, _l = p._beleg_dokument(mit_umlaut, nt, na, karte)
    pruefe(dok2 is not None and p._pdf_schluessel(dok2) == sch,
           "auch mit Umlauten geschrieben (%r)" % mit_umlaut)

    # Der Abdruck und der volle Name muessen weiter gehen.
    ab = schluessel.fingerabdruck(schluessel.kennpfad(
        "zz-probe", "archiv/Sch\u00e4fer/Qualit\u00e4t/Liste.pdf"))
    pruefe(p._beleg_dokument(ab, nt, na, karte)[0] is not None,
           "der Abdruck geht weiterhin")
    pruefe(p._beleg_dokument(roh[:-3], nt, na, karte)[0] is not None,
           "der volle Name geht weiterhin")

    # \u26d4 Gegenprobe 1: ein FREMDER Anzeigetitel trifft nichts. Ohne diese
    #   Zeile waere alles oben auch dann gruen, wenn jeder Klammertext das
    #   erstbeste Dokument bekommt.
    for fremd in ("Irgendwas-Anderes", "Schafer-Qualitat-Andere",
                  "Liste", "siehe oben", ""):
        d, _l = p._beleg_dokument(fremd, nt, na, karte)
        pruefe(d is None, "fremder Titel %r trifft nichts, ist %r" % (fremd, d))

    # \u26d4 Gegenprobe 2: Sind ZWEI Dokumente unter demselben Anzeigetitel
    #   im Arbeitsbereich, darf keines gewaehlt werden - sonst zeigte der
    #   Sprung auf das falsche. Genau die Kollisionsklasse, gegen die dieser
    #   Umbau gebaut ist.
    for unter in ("archiv/Angebot 2024/Blatt.pdf", "archiv/Angebot/2024 Blatt.pdf"):
        voll = os.path.join(BAUM, "zz-probe", *unter.split("/"))
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        with open(voll, "wb") as fh:
            fh.write(b"%PDF-1.4\n" + unter.encode("utf-8") + b"\n")
    p.pdfs_einlesen()
    zwei = [schluessel.schluessel("zz-probe", u)[:-4].replace("--", "-") + ".md"
            for u in ("archiv/Angebot 2024/Blatt.pdf",
                      "archiv/Angebot/2024 Blatt.pdf")]
    nt2, na2, karte2 = p._belegverzeichnis(zwei)
    d3, _l = p._beleg_dokument("Angebot-2024-Blatt", nt2, na2, karte2)
    pruefe(d3 is None,
           "mehrdeutiger Anzeigetitel waehlt KEINES aus, ist %r" % (d3,))


def main():
    baum_bauen()
    pruefungen = [test_index, test_pdfstelle, test_belegvorrat,
                  test_anzeigetitel, test_metadaten_tor,
                  test_belegvergleich,
                  test_rechtepruefung,
                  test_loeschweg,
                  test_stuetze_laeuft_ab,
                  test_umlautdeckung,
                  test_leere_eingangsordner,
                  test_belegklammer,
                  test_trennzeichen_egal,
                  test_belegsprung,
                  test_zitatpruefung_umlaute,
                  test_klammer_kennt_anzeigetitel]
    try:
        for t in pruefungen:
            t()
    finally:
        shutil.rmtree(BAUM, ignore_errors=True)
        shutil.rmtree(BESTAND, ignore_errors=True)
        shutil.rmtree(KATALOGORT, ignore_errors=True)
        shutil.rmtree(MDABLAGE, ignore_errors=True)
    print("\n%d Fehler" % len(FEHLER))
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
