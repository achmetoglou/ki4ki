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

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

BAUM = tempfile.mkdtemp(prefix="ki4ki-wege-")
BESTAND = tempfile.mkdtemp(prefix="ki4ki-wege-bestand-")
os.environ["KI4KI_PDFS"] = BAUM
os.environ["KI4KI_EINGANG"] = BAUM
os.environ["KI4KI_BESTAND"] = BESTAND
os.environ.setdefault("KI4KI_API_KEY", "")
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


def main():
    baum_bauen()
    pruefungen = [test_index, test_pdfstelle, test_belegvorrat,
                  test_anzeigetitel, test_metadaten_tor,
                  test_stuetze_laeuft_ab]
    try:
        for t in pruefungen:
            t()
    finally:
        shutil.rmtree(BAUM, ignore_errors=True)
        shutil.rmtree(BESTAND, ignore_errors=True)
        shutil.rmtree(KATALOGORT, ignore_errors=True)
    print("\n%d Fehler" % len(FEHLER))
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
