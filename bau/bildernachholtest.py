#!/usr/bin/env python3
"""Pruefreihe fuer bilder_nachholen.py.

⛔ Ausgangslage, gemessen am 08.10.2026 auf der A40: Im Bereich kap liegen
  3.671 freistehende Bilddateien (jpg 2.847 · tif 690 · jpeg 118 · tiff 9 ·
  png 7), zusammen 11,3 GB, die groesste 372,8 MB. Beschrieben sind
  davon NULL. Sie erreichen Docling nie - die Positivliste im Ablaufplan
  ("Nur ein Bereich je Durchgang", jsCode-Zeile 177) kennt keine
  Bildendung, und 257 Zeilen im aussortiert.log tragen den Grund
  "Format nicht vorgesehen".

⭐ Emrachs Entscheidung vom 08.10.: Bildbeschreibungen duerfen in den
  Bestand - aber GEKENNZEICHNET. Sie sind vom Modell erzeugt, nicht aus
  einem Dokument belegt. Die Belegpruefung darf sie nie als Fundstelle
  behandeln, und der Leser muss es sehen.

Aufruf:   python3 bildernachholtest.py      (Exit 0 = alle gruen)
"""
import io
import json
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "pruef-proxy"))

import bilder_nachholen as bn    # noqa: E402

# ⛔ Eine ECHTE Beschreibung ist lang. Kurze Vorlagen liefen in die
#   Mindestlaenge des Skripts und liessen sieben Pruefungen scheitern -
#   die Vorlage war unrealistisch, nicht die Grenze falsch.
BESCHREIBUNG = ("Die Abbildung zeigt einen Sprödbruch im Lagersitz mit\n"
                "deutlich erkennbarer Rastlinienstruktur, Massstab 200 µm.")

FEHLER = []
ZAEHLER = [0]


def pruefe(bedingung, text):
    ZAEHLER[0] += 1
    if not bedingung:
        FEHLER.append(text)
        print("  FEHLER  " + text)
    else:
        print("  ok      " + text)


def _bild(pfad, groesse=(40, 30), farbe=(200, 30, 30)):
    from PIL import Image
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    Image.new("RGB", groesse, farbe).save(pfad)
    return pfad


def _bereich(wurzel, name="kap"):
    for ordner in ("parkplatz", "aussortiert", "archiv", "input"):
        os.makedirs(os.path.join(wurzel, name, ordner), exist_ok=True)
    return os.path.join(wurzel, name)


def fall_1_nur_bilder_und_nur_aus_den_quellen():
    print("\n[1] Gefunden wird, was ein Bild ist - und nur in den Quellen")
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        _bild(os.path.join(b, "parkplatz", "Kiekert-276804-Bruchbild.jpg"))
        _bild(os.path.join(b, "parkplatz", "tief", "Vossloh-Schliff.TIF"))
        _bild(os.path.join(b, "aussortiert", "Johnson-Pumpe.png"))
        _bild(os.path.join(b, "archiv", "schon-drin.jpg"))
        open(os.path.join(b, "parkplatz", "Bericht.pdf"), "w").write("x")
        open(os.path.join(b, "parkplatz", "Notiz.md"), "w").write("x")
        gefunden = bn.bilder_finden(w, "kap", ("parkplatz", "aussortiert"))
        namen = sorted(os.path.basename(p) for p in gefunden)
        pruefe(namen == ["Johnson-Pumpe.png", "Kiekert-276804-Bruchbild.jpg",
                         "Vossloh-Schliff.TIF"],
               "drei Bilder aus parkplatz und aussortiert, auch aus\n"
               "           Unterordnern und mit GROSSER Endung (ist: %r)" % namen)
        pruefe(all(not p.endswith((".pdf", ".md")) for p in gefunden),
               "PDF und Markdown bleiben draussen")
        pruefe("schon-drin.jpg" not in namen,
               "archiv wird nicht angefasst - was dort liegt, ist aufgenommen")


def fall_2_grosse_bilder_werden_verkleinert_nicht_uebersprungen():
    print("\n[2] Grosse Bilder werden verkleinert, nicht uebersprungen")
    # ⛔ Die groesste Datei im Bestand hat 372,8 MB. Base64 davon waeren
    #   rund 497 MB Nutzlast - kein Modell nimmt das an. Ueberspringen
    #   waere aber die falsche Antwort: dann bliebe genau das groesste
    #   Bild unauffindbar. Pillow liegt im Abbild (pruef-proxy/Dockerfile),
    #   also wird verkleinert.
    with tempfile.TemporaryDirectory() as w:
        p = _bild(os.path.join(w, "gross.png"), groesse=(4000, 3000))
        roh = os.path.getsize(p)
        klein = bn.bild_vorbereiten(p, kante=1280)
        pruefe(klein[:2] == b"\xff\xd8", "heraus kommt ein JPEG")
        from PIL import Image
        bild = Image.open(io.BytesIO(klein))
        pruefe(max(bild.size) == 1280,
               "die lange Kante ist genau 1280 (ist: %r)" % (bild.size,))
        pruefe(bild.size[0] > bild.size[1],
               "das Seitenverhaeltnis bleibt erhalten")
        pruefe(len(klein) < roh,
               "und es ist kleiner als das Original (%d < %d)" % (len(klein), roh))

        kl = _bild(os.path.join(w, "klein.png"), groesse=(100, 80))
        erg = Image.open(io.BytesIO(bn.bild_vorbereiten(kl, kante=1280)))
        pruefe(erg.size == (100, 80),
               "ein kleines Bild wird NICHT aufgeblasen (ist: %r)" % (erg.size,))


def fall_3_die_anfrage_traegt_das_bild():
    print("\n[3] Die Anfrage traegt wirklich das Bild")
    # ⛔ Ohne diese Pruefung koennte das Modell einen leeren Auftrag
    #   bekommen und trotzdem etwas antworten - erfunden, aus dem Nichts.
    import base64
    jpeg = b"\xff\xd8\xff\xe0 tu was"
    a = bn.anfrage_bauen(jpeg, "Beschreibe dies.", "gemma4:12b")
    pruefe(a.get("model") == "gemma4:12b", "das Modell steht drin")
    pruefe(a.get("stream") is False, "kein Strom - wir wollen die ganze Antwort")
    nachricht = (a.get("messages") or [{}])[0]
    pruefe("Beschreibe dies." in (nachricht.get("content") or ""),
           "der Auftragstext steht drin")
    bilder = nachricht.get("images") or []
    pruefe(len(bilder) == 1, "genau ein Bild haengt dran (ist: %d)" % len(bilder))
    pruefe(bilder and base64.b64decode(bilder[0]) == jpeg,
           "und zwar GENAU dieses, unveraendert")


def fall_4_die_kennzeichnung_steht_im_text():
    print("\n[4] Jede Beschreibung traegt ihre Kennzeichnung")
    t = bn.markdown_bauen("Kiekert-276804-Bruchbild",
                          "parkplatz/Kiekert-276804-Bruchbild.jpg",
                          "Die Abbildung zeigt einen Sprödbruch.",
                          "gemma4:12b", "2026-10-11")
    # ⛔ NICHT `bn.MARKE in t` pruefen: Setzt jemand MARKE auf "", ist
    #   das immer wahr und die Pruefung gruen, waehrend die Kennzeichnung
    #   verschwunden ist. Gemessen am 08.10. - die Mutation "MARKE = ''"
    #   lief glatt durch. Der WORTLAUT gehoert in die Pruefung.
    WORTLAUT = "Maschinell erzeugte Bildbeschreibung"
    pruefe(bn.MARKE == WORTLAUT,
           "die Marke lautet unveraendert „%s“ (ist: %r)" % (WORTLAUT, bn.MARKE))
    pruefe(WORTLAUT in t, "und sie steht im Text")
    pruefe("keine belegte" in t.lower(),
           "und der Satz, dass es KEINE belegte Fundstelle ist")
    pruefe("Die Abbildung zeigt einen Sprödbruch." in t,
           "die Beschreibung selbst steht da")
    pruefe("parkplatz/Kiekert-276804-Bruchbild.jpg" in t,
           "und von welcher Datei sie stammt")
    pruefe("gemma4:12b" in t and "2026-10-11" in t,
           "Modell und Datum stehen dabei - sonst weiss spaeter niemand,\n"
           "           womit sie erzeugt wurde")
    pruefe(t.index(WORTLAUT) < t.index("Die Abbildung zeigt"),
           "die Kennzeichnung steht VOR der Beschreibung, nicht darunter")


def fall_5_metadaten_und_warnung():
    print("\n[5] Der Eintrag in metadaten.json loest die Warnung aus")
    import metadaten
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        datei = os.path.join(b, "metadaten.json")
        json.dump({"Alt-Dokument": {"freigabe": "freigegeben"}},
                  open(datei, "w", encoding="utf-8"))
        bn.metadaten_ergaenzen(datei, "Kiekert-276804-Bruchbild", "gemma4:12b")
        d = json.load(open(datei, encoding="utf-8"))
        pruefe("Alt-Dokument" in d,
               "der vorhandene Eintrag bleibt erhalten")
        e = d.get("Kiekert-276804-Bruchbild") or {}
        pruefe(e.get("herkunft") == "bildbeschreibung",
               "der neue traegt herkunft=bildbeschreibung (ist: %r)" % e)
        pruefe(metadaten.FREIGABEN and "warnung" in dir(metadaten),
               "metadaten.warnung gibt es")
        metadaten._CACHE.clear()
        w_text = metadaten.warnung("Kiekert-276804-Bruchbild", b)
        pruefe("maschinell erzeugte bildbeschreibung" in (w_text or "").lower(),
               "und die Fusszeile warnt bei jeder Antwort daraus\n"
               "           (ist: %r)" % w_text)
        pruefe("keine belegte" in (w_text or "").lower(),
               "mit demselben Satz wie im Text: keine belegte Fundstelle")
        metadaten._CACHE.clear()
        pruefe(not metadaten.warnung("Alt-Dokument", b),
               "Gegenprobe: ein gewoehnliches Dokument bekommt KEINE Warnung")


def fall_6_trockenlauf_schreibt_nichts():
    print("\n[6] Der Trockenlauf schreibt nichts")
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        _bild(os.path.join(b, "parkplatz", "A.jpg"))
        gerufen = []

        def senden(a):
            gerufen.append(a)
            return BESCHREIBUNG

        bericht = bn.nachholen(w, "kap", senden=senden, trocken=True)
        ziel = os.path.join(b, "bilder-md")
        pruefe(not os.path.exists(ziel) or not os.listdir(ziel),
               "kein Markdown geschrieben")
        pruefe(not gerufen, "und das Modell wurde gar nicht erst gefragt")
        pruefe(bericht.get("gefunden") == 1,
               "gezaehlt wird trotzdem (ist: %r)" % bericht.get("gefunden"))


def fall_7_fortsetzen_statt_von_vorn():
    print("\n[7] Ein zweiter Lauf macht nicht alles noch einmal")
    # ⛔ Bei 3.671 Bildern und einer Nacht Laufzeit MUSS ein Abbruch
    #   fortsetzbar sein. Sonst faengt ein Stromausfall um 4 Uhr alles
    #   von vorn an.
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        _bild(os.path.join(b, "parkplatz", "A.jpg"))
        _bild(os.path.join(b, "parkplatz", "B.jpg"))
        gerufen = []

        def senden(a):
            gerufen.append(a)
            return BESCHREIBUNG

        bn.nachholen(w, "kap", senden=senden)
        pruefe(len(gerufen) == 2, "erster Lauf: beide Bilder (ist: %d)" % len(gerufen))
        gerufen.clear()
        bericht = bn.nachholen(w, "kap", senden=senden)
        pruefe(not gerufen,
               "zweiter Lauf: kein einziges noch einmal (ist: %d)" % len(gerufen))
        pruefe(bericht.get("uebersprungen") == 2,
               "und er sagt, dass er 2 uebersprungen hat (ist: %r)"
               % bericht.get("uebersprungen"))


def fall_8_ein_fehler_hinterlaesst_keine_halbe_datei():
    print("\n[8] Ein Fehler hinterlaesst keine halbe Datei")
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        _bild(os.path.join(b, "parkplatz", "A.jpg"))
        _bild(os.path.join(b, "parkplatz", "B.jpg"))

        def senden(a):
            if len(a["messages"][0]["images"]) and not senden.erste:
                senden.erste = True
                raise RuntimeError("Modell antwortet nicht")
            return BESCHREIBUNG
        senden.erste = False

        bericht = bn.nachholen(w, "kap", senden=senden)
        ziel = os.path.join(b, "bilder-md")
        da = sorted(os.listdir(ziel)) if os.path.exists(ziel) else []
        pruefe(len(da) == 1,
               "genau eine Datei geschrieben, nicht zwei (ist: %r)" % da)
        pruefe(bericht.get("fehler") == 1,
               "der Fehler wird gezaehlt (ist: %r)" % bericht.get("fehler"))
        pruefe(bericht.get("fertig") == 1,
               "und das gelungene Bild auch (ist: %r)" % bericht.get("fertig"))
        # Der naechste Lauf muss das gescheiterte nachholen
        bericht2 = bn.nachholen(w, "kap", senden=lambda a: BESCHREIBUNG)
        pruefe(bericht2.get("fertig") == 1,
               "und ein weiterer Lauf holt genau das gescheiterte nach")


def fall_9_leere_antwort_gilt_nicht_als_beschreibung():
    print("\n[9] Eine leere oder unbrauchbare Antwort wird nicht abgelegt")
    # ⛔ Dieselbe Falle wie bei _bild_beschreiben im Proxy: Ein Modell, das
    #   nichts erkennt, antwortet gern mit einem Wort. Eine .md mit "Ja."
    #   waere ein Dokument im Bestand, das nichts aussagt - und in der
    #   Volltextsuche Treffer erzeugt.
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        _bild(os.path.join(b, "parkplatz", "A.jpg"))
        bericht = bn.nachholen(w, "kap", senden=lambda a: "   ")
        ziel = os.path.join(b, "bilder-md")
        pruefe(not os.path.exists(ziel) or not os.listdir(ziel),
               "leere Antwort: nichts abgelegt")
        pruefe(bericht.get("fehler") == 1, "als Fehler gezaehlt")

        bericht = bn.nachholen(w, "kap", senden=lambda a: "Ja.")
        pruefe(not os.path.exists(ziel) or not os.listdir(ziel),
               "zu kurze Antwort: ebenfalls nichts abgelegt")


def fall_10_probe_mischt_die_groessen():
    print("\n[10] Der Probelauf nimmt nicht nur die kleinsten")
    # ⛔ Zweck der Probe ist, die ECHTE Sekundenzahl je Bild zu messen.
    #   Nimmt sie die ersten N alphabetisch, misst sie womoeglich nur
    #   Miniaturen - und die Hochrechnung auf 3.671 ist wertlos.
    with tempfile.TemporaryDirectory() as w:
        b = _bereich(w)
        for i, g in enumerate([(60, 60), (1200, 900), (90, 90), (2400, 1800),
                               (70, 70), (1600, 1200)]):
            _bild(os.path.join(b, "parkplatz", "bild%d.png" % i), groesse=g)
        gewaehlt = bn.probe_waehlen(
            bn.bilder_finden(w, "kap", ("parkplatz",)), 3)
        pruefe(len(gewaehlt) == 3, "drei Bilder gewaehlt (ist: %d)" % len(gewaehlt))
        groessen = sorted(os.path.getsize(p) for p in gewaehlt)
        alle = sorted(os.path.getsize(p)
                      for p in bn.bilder_finden(w, "kap", ("parkplatz",)))
        pruefe(groessen[-1] == alle[-1],
               "das GROESSTE ist dabei - sonst misst die Probe zu guenstig")
        pruefe(groessen[0] == alle[0],
               "das kleinste auch - die Spanne soll sichtbar werden")



def fall_11_abbildungen_in_dokumenten_eine_schwelle_eine_bedingung():
    print("\n[11] Abbildungen IN Dokumenten: eine Schwelle, eine Bedingung")
    # ⛔ 08.10. gemessen: Die Bildbeschreibung fuer Abbildungen INNERHALB
    #   von Dokumenten ist AUS. docker-compose.yml setzt
    #   KI4KI_BILDBESCHREIBUNG=${KI4KI_BILDBESCHREIBUNG:-aus}, und die
    #   .env auf der A40 setzt sie nicht. Damit war Commit 53edd7c
    #   (Schwelle 0,08 -> 0,01, 4.353 zusaetzliche Abbildungen)
    #   WIRKUNGSLOS - der Schalter davor stand auf aus.
    #   Den Schalter kann nur Emrach umlegen (eine Zeile in der .env auf
    #   dem Server). Was HIER repariert werden kann, sind die zwei
    #   Nebenschaeden:
    import re as _re
    wurzel = os.path.dirname(HIER)

    # a) Drei Schwellenwerte an drei Stellen - genau der Fehler, vor dem
    #    der Kommentar an NICHTDOKUMENT warnt. Der wirksame steht auf
    #    0.01; die beiden anderen laufen daneben her und greifen, sobald
    #    jemand den Handweg benutzt.
    def _schwellen(datei, muster):
        text = open(os.path.join(wurzel, datei), encoding="utf-8").read()
        return [m.group(1) for m in _re.finditer(muster, text)]

    gefunden = {}
    gefunden["extract.sh"] = _schwellen(
        "mkmd-dienst/extract.sh", r"picture[_a-z]*area[_a-z]*threshold[\"'=: ]+([0-9.]+)")
    gefunden["extract_gross.sh"] = _schwellen(
        "mkmd-dienst/extract_gross.sh", r"picture[_a-z]*area[_a-z]*threshold[\"'=: ]+([0-9.]+)")
    gefunden["bildmodell.json"] = [str(json.load(open(
        os.path.join(wurzel, "mkmd-dienst/bildmodell.json"),
        encoding="utf-8")).get("picture_area_threshold"))]
    alle = [w for liste in gefunden.values() for w in liste]
    pruefe(bool(alle), "Schwellenwerte gefunden (ist: %r)" % gefunden)
    pruefe(all(float(w) == 0.01 for w in alle if w not in ("None",)),
           "alle Schwellen stehen auf 0.01 wie der wirksame Weg\n"
           "           (ist: %r)" % gefunden)

    # b) Die Merkliste haengt an den FORMELN mit. Weil KI4KI_FORMELN
    #    ebenfalls auf aus steht, landet JEDES Dokument darauf - deshalb
    #    ist sie von 97 auf 906 Zeilen gewachsen. Sie soll heissen, was
    #    ihr Name sagt: Bilder fehlen.
    plan = json.load(open(os.path.join(
        wurzel, "n8n-workflows/2_Dateien-in-JSON-umwandeln.json"),
        encoding="utf-8"))
    code = ""
    for k in plan.get("nodes", []):
        c = (k.get("parameters") or {}).get("jsCode") or ""
        if "ohne_bilder: (() =>" in c:
            i = c.index("ohne_bilder: (() =>")
            # Bis zum Ende der Klammerfunktion, nicht nach Zeichenzahl:
            # ein zusaetzlicher Kommentar darf die Pruefung nicht blenden.
            ende = c.find("})()", i)
            code = c[i:ende if ende > i else i + 1200]
    pruefe(bool(code), "die Stelle im Ablaufplan ist auffindbar")
    # ⛔ NICHT den ersten `return` nehmen - der gehoert zum Massenlauf
    #   ("return true"). Der ganze Block zaehlt.
    # ⛔ Nur den CODE pruefen, nicht die Kommentare. Derselbe Fehler
    #   wie beim CSS am selben Tag: Die Begruendung, WARUM die Formeln
    #   raus sind, enthaelt zwangslaeufig das Wort.
    ohne_kommentar = "\n".join(
        z for z in code.split("\n") if not z.strip().startswith("//"))
    pruefe("formeln" not in ohne_kommentar.lower(),
           "im ausgefuehrten Teil von ohne_bilder kommen die Formeln"
           " nicht mehr vor (ist: %r)" % ohne_kommentar[-220:])
    pruefe("KI4KI_BILDBESCHREIBUNG" in code,
           "aber die Bildbeschreibung sehr wohl")
    pruefe(_re.search(r"return\s+bilder\s*===\s*'aus'\s*;", code) is not None,
           "und die Bedingung lautet genau: return bilder === 'aus';")


if __name__ == "__main__":
    for f in (fall_1_nur_bilder_und_nur_aus_den_quellen,
              fall_2_grosse_bilder_werden_verkleinert_nicht_uebersprungen,
              fall_3_die_anfrage_traegt_das_bild,
              fall_4_die_kennzeichnung_steht_im_text,
              fall_5_metadaten_und_warnung,
              fall_6_trockenlauf_schreibt_nichts,
              fall_7_fortsetzen_statt_von_vorn,
              fall_8_ein_fehler_hinterlaesst_keine_halbe_datei,
              fall_9_leere_antwort_gilt_nicht_als_beschreibung,
              fall_10_probe_mischt_die_groessen,
              fall_11_abbildungen_in_dokumenten_eine_schwelle_eine_bedingung):
        try:
            f()
        except Exception as e:
            import traceback
            traceback.print_exc()
            FEHLER.append("%s: Ausnahme %s" % (f.__name__, e))
    print("\n%d Pruefungen, %d Fehler" % (ZAEHLER[0], len(FEHLER)))
    for x in FEHLER:
        print("  - " + x)
    sys.exit(1 if FEHLER else 0)
