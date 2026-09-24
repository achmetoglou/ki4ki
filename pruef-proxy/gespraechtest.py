#!/usr/bin/env python3
"""Pruefreihe fuer den Gespraechsmodus - Teil: abgeschnittene Antworten.

⛔ Meldung vom 18.09.2026, woertlich: "In der Anweisung sind 11 Fragen
  gestellt und laut erster Antwortzeile auch erkannt, die bearbeitung
  bricht aber in der 4ten Frage ab. => Unvollstaendig"

⭐ Am 23.09. nachgestellt, in einem FRISCHEN Faden, Bereich auw:
    kurze Antworten verlangt  -> alle 11 beantwortet
    lange Antworten verlangt  -> Abbruch MITTEN IM WORT:
        "... Du hast 12 Stifte und bekommst"
  Ein Modell, das selbst aufhoert, endet sauber. Ein Schnitt mitten im
  Wort ist die Unterschrift einer Token-Grenze (num_predict).

Aufruf:   python3 gespraechtest.py     (Exit 0 = alle gruen)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gespraech      # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def test_abschnitt_wird_erkannt():
    """Ollama sagt selbst, ob es an der Grenze aufgehoert hat."""
    print("\nEin Abschnitt an der Token-Grenze wird erkannt")
    pruefe(gespraech.abgeschnitten({"done_reason": "length"}) is True,
           "done_reason 'length' heisst abgeschnitten")
    pruefe(gespraech.abgeschnitten({"done_reason": "stop"}) is False,
           "Gegenprobe: 'stop' heisst sauber zu Ende")
    pruefe(gespraech.abgeschnitten({}) is False,
           "ohne Angabe wird nichts behauptet")
    # Aeltere Ollama-Fassungen melden kein done_reason - dann hilft die Zahl.
    pruefe(gespraech.abgeschnitten({"eval_count": gespraech.ANTWORT_TOKEN}) is True,
           "auch ohne done_reason: genau ausgereizte Token sind verdaechtig")
    pruefe(gespraech.abgeschnitten({"eval_count": 5}) is False,
           "Gegenprobe: wenige Token sind unverdaechtig")


def test_hinweis_wird_angehaengt():
    """Abgeschnitten darf nicht stillschweigend passieren."""
    print("\nDer Nutzer erfaehrt vom Abschnitt")
    t = gespraech.abschnitt_vermerken("... und bekommst", True)
    pruefe("... und bekommst" in t, "der Text bleibt erhalten")
    pruefe(t != "... und bekommst", "und bekommt einen Hinweis")
    pruefe("abgeschnitten" in t.lower(),
           "der Hinweis sagt beim Namen, was passiert ist")
    unberuehrt = gespraech.abschnitt_vermerken("fertig.", False)
    pruefe(unberuehrt == "fertig.",
           "Gegenprobe: ohne Abschnitt wird nichts angehaengt")


def test_grenze_ist_einstellbar():
    """Die Grenze muss ohne Neubau aenderbar sein."""
    print("\nDie Token-Grenze ist einstellbar")
    pruefe(gespraech.ANTWORT_TOKEN >= 2048,
           "die Vorgabe im Code ist hoch genug fuer eine ganze Antwort "
           "(ist: %s)" % gespraech.ANTWORT_TOKEN)
    pruefe("KI4KI_ANTWORT_TOKEN" in open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "gespraech.py"), encoding="utf-8").read(),
           "und ueber eine Umgebungsvariable zu aendern")


def test_der_hinweis_kommt_wirklich_im_gespraechszug_an():
    """Die Funktion zu haben genuegt nicht - sie muss gerufen werden.

    ⛔ Beim ersten Anlauf pruefte diese Reihe nur `abgeschnitten()` und
      `abschnitt_vermerken()` fuer sich. Als ich die EINE Zeile entfernte,
      die beide im Gespraechszug verbindet, blieb sie **gruen**. Das ist
      zum vierten Mal an einem Tag dieselbe Falle: die richtige Sache
      gemessen, aber nicht dort, wo sie wirken muss.

    Deshalb laeuft hier ein echter Gespraechszug - mit einem
    vorgetaeuschten Modell, das eine abgeschnittene Antwort liefert.
    """
    print("\nDer Hinweis kommt im echten Gespraechszug an")

    def rufen_abgeschnitten(msgs):
        return {"role": "assistant",
                "content": "... Du hast 12 Stifte und bekommst",
                "_nutzung": {"prompt": 10, "antwort": gespraech.ANTWORT_TOKEN,
                             "dauer_ms": 1},
                "_abgeschnitten": True}

    def rufen_sauber(msgs):
        return {"role": "assistant", "content": "Fertige Antwort.",
                "_nutzung": {"prompt": 10, "antwort": 12, "dauer_ms": 1},
                "_abgeschnitten": False}

    erg = gespraech.fuehren("Frage?", [], None, [], lambda n, a: "",
                            rufen=rufen_abgeschnitten)
    pruefe("abgeschnitten" in (erg.get("text") or "").lower(),
           "der Zug meldet den Abschnitt an den Nutzer")
    pruefe("Du hast 12 Stifte und bekommst" in (erg.get("text") or ""),
           "und behaelt den bereits geschriebenen Teil")
    pruefe(erg.get("nutzung", {}).get("abgeschnitten") == 1,
           "die Nutzung haelt den Abschnitt fest - auswertbar im Protokoll")

    sauber = gespraech.fuehren("Frage?", [], None, [], lambda n, a: "",
                               rufen=rufen_sauber)
    pruefe("abgeschnitten" not in (sauber.get("text") or "").lower(),
           "Gegenprobe: eine fertige Antwort bekommt keinen Hinweis")


def test_die_werte_kommen_auch_bei_partnern_an():
    """Eine Vorgabe im Code nuetzt nichts, wenn die Anlage sie nicht setzt.

    ⛔ Die Grenzen stehen in gespraech.py als Vorgabe - aber eine
      Partner-Installation startet ueber docker-compose.yml. Steht der
      Wert dort nicht, laeuft der Partner weiter mit der Vorgabe, und
      der Befund vom 18.09. waere fuer ihn nicht behoben.

    ⭐ Deshalb gehoeren beide Werte in die Compose - mit ${VAR:-...},
      damit ein Partner sie ohne Aenderung an der Datei ueberschreiben
      kann. Genau dieser Stil steht dort schon fuer neun andere Werte.
    """
    print("\nDie Werte stehen in der Compose, nicht nur im Code")
    hier = os.path.dirname(os.path.abspath(__file__))
    compose = os.path.join(os.path.dirname(hier), "docker-compose.yml")
    if not os.path.exists(compose):
        pruefe(False, "docker-compose.yml nicht gefunden - NICHT geprueft")
        return
    t = open(compose, encoding="utf-8").read()
    pruefe("KI4KI_ANTWORT_TOKEN=${KI4KI_ANTWORT_TOKEN:-2048}" in t,
           "die Antwortlaenge steht in der Compose und ist ueberschreibbar")
    pruefe("num_predict gilt JE MODELLAUFRUF" in t,
           "und daneben steht, WARUM nicht mehr - die Grenze gilt je\n           Aufruf, ein Zug hat bis zu fuenf davon")
    pruefe("KI4KI_GESPRAECH_TIMEOUT=${KI4KI_GESPRAECH_TIMEOUT:-600}" in t,
           "die Zeitgrenze ebenso - sonst laeuft eine lange Antwort in "
           "die alten 240 s und stirbt ganz, statt nur gekuerzt zu werden")


def test_lange_antwort_haelt_die_leitung_wach():
    """Waehrend das Modell schreibt, darf die Leitung nicht verstummen.

    ⛔ Gemessen 23.09. am laufenden System: Nach dem Hochsetzen der
      Antwortlaenge auf 8192 Token starb die Chat-Verbindung nach
      92.432 ms mit NS_ERROR_NET_PARTIAL_TRANSFER, im Proxy-Protokoll
      ein BrokenPipeError. Keine Antwort, kein Hinweis.

    ⛔ Ursache: `"stream": False` - der Proxy wartet die KOMPLETTE Antwort
      von Ollama ab und schickt in dieser Zeit nichts an den Browser. Bei
      1800 Token waren das rund 33 s und blieben unter der Zeitgrenze der
      Gegenstelle; bei 8192 sind es ueber zwei Minuten. Die Gegenstelle
      kappte die stille Leitung, und der Proxy schrieb danach ins Leere.

    ⭐ Warum nicht einfach streamen: Die Antwort wird NACH dem Erzeugen
      gegen die Dokumente geprueft (Zitate, unbelegte Aussagen). Wer den
      Rohtext durchreicht, sendet Ungeprueftes - genau das, was diese
      Anlage nicht tut. Also ein Lebenszeichen statt Rohtext.

    ⭐ Die Lebenszeichen gehen vom SELBEN Faden wie die Antwort raus:
      Zwei Faeden auf derselben Leitung koennten sich mitten in einem
      Stueck ins Wort fallen.
    """
    print("\nEine lange Antwort haelt die Leitung wach")
    gesendet = []

    def langsam():
        time.sleep(0.35)
        return "fertig"

    erg = gespraech.mit_lebenszeichen(langsam, lambda: gesendet.append(1),
                                      abstand=0.1)
    pruefe(erg == "fertig", "das Ergebnis kommt unveraendert zurueck")
    pruefe(len(gesendet) >= 2,
           "waehrend des Wartens kamen Lebenszeichen (ist: %d)"
           % len(gesendet))

    gesendet2 = []
    erg2 = gespraech.mit_lebenszeichen(lambda: "sofort",
                                       lambda: gesendet2.append(1),
                                       abstand=0.1)
    pruefe(erg2 == "sofort", "auch eine schnelle Antwort kommt durch")
    pruefe(not gesendet2,
           "Gegenprobe: eine schnelle Antwort braucht kein Lebenszeichen")


def test_fehler_gehen_nicht_verloren():
    """Wirft die Arbeit, muss der Fehler beim Aufrufer ankommen."""
    print("\nEin Fehler im Warten geht nicht verloren")

    def kaputt():
        raise ValueError("absichtlich")

    try:
        gespraech.mit_lebenszeichen(kaputt, lambda: None, abstand=0.1)
        pruefe(False, "der Fehler haette geworfen werden muessen")
    except ValueError as e:
        pruefe("absichtlich" in str(e),
               "der urspruengliche Fehler kommt durch, nicht ein Ersatz")


def test_das_lebenszeichen_macht_keine_leeren_nachrichten():
    """Das Lebenszeichen darf den Chat nicht zumuellen.

    ⛔ Gemessen 23.09.: Die erste Fassung schickte ein leeres
      textResponseChunk mit NEUER Kennung. AnythingLLM macht daraus jedes
      Mal eine eigene, leere Nachricht - der Chat war voller riesiger
      Leerflaechen, und die Antwort kam trotzdem nicht.

    ⭐ Richtig ist statusResponse mit GLEICHER Kennung: Die ersetzt die
      vorige Meldung, erzeugt keinen neuen Block und wird am Ende mit
      removeStatusResponse weggeraeumt.

    ⚠ Diese Pruefung liest den Quelltext, weil die Stelle in einem
      HTTP-Griff steckt, der ohne Server nicht aufrufbar ist. Sie ist
      damit schwaecher als eine Verhaltenspruefung - aber sie faengt
      genau den Rueckfall, der heute passiert ist.
    """
    print("\nDas Lebenszeichen erzeugt keine leeren Nachrichten")
    hier = os.path.dirname(os.path.abspath(__file__))
    quelle = open(os.path.join(hier, "pruef_proxy.py"), encoding="utf-8").read()
    i = quelle.find("def _wachhalten():")
    pruefe(i > 0, "die Stelle gibt es noch")
    if i <= 0:
        return
    block = quelle[i:i + 400]
    pruefe("self._stand(stand," in block,
           "das Lebenszeichen geht ueber die Statuszeile mit fester Kennung")
    pruefe("_neue_marke" not in block,
           "⛔ und NICHT mit einer neuen Kennung - das gaebe je "
           "Lebenszeichen eine leere Nachricht")
    pruefe("textResponseChunk" not in block,
           "⛔ und nicht als Antwort-Stueck")


def test_kontextfenster_passt_sich_an():
    """Ein 64k-Fenster kostet bei JEDEM Token Rechenzeit.

    ⛔ Gemessen 23.09. spaet, qwen3.8 zu 100 % auf der Karte:
      **15,5 Token/s** - fuer eine Frage, deren Fundstellen keine 64k
      brauchen. Der Zwischenspeicher fuer die Aufmerksamkeit waechst mit
      dem eingestellten Fenster, nicht mit dem, was wirklich drinsteht.

    ⭐ Also das Fenster an die Anfrage anpassen: klein fuer einen
      gewoehnlichen Chat-Zug, gross fuer eine Zusammenfassung.

    ⛔ Aber NIE kleiner als noetig. Passt der Prompt nicht hinein,
      wirft Ollama den Anfang weg - still, ohne Meldung, und die Antwort
      stuetzt sich auf Dokumente, die gar nicht mehr dastehen. Genau die
      Sorte stiller Fehler, die dieses Projekt sonst jagt. Deshalb gibt
      die Funktion auch zurueck, OB es passt.
    """
    print("\nDas Kontextfenster passt sich an")
    # 2,1 Zeichen je Token (gemessen, steht in mehrstufig.py)
    klein, passt = gespraech.kontextfenster(10000, 2048)
    pruefe(klein == 8192, "kurze Frage -> kleinstes Fenster (ist: %s)" % klein)
    pruefe(passt is True, "und es passt")

    mittel, _ = gespraech.kontextfenster(30000, 2048)
    pruefe(mittel == 16384, "mittlere Frage -> 16k (ist: %s)" % mittel)

    gross, _ = gespraech.kontextfenster(100000, 2048)
    pruefe(gross == 65536, "grosses Dokument -> volles Fenster (ist: %s)"
           % gross)

    # ⛔ Der Fall, der still schiefgehen wuerde
    zuviel, passt2 = gespraech.kontextfenster(200000, 2048)
    pruefe(zuviel == 65536, "mehr als 64k gibt es nicht")
    pruefe(passt2 is False,
           "⛔ und es wird GESAGT, dass es nicht passt - sonst wirft "
           "Ollama den Anfang still weg")


def test_das_fenster_ist_nie_zu_klein():
    """Gegenprobe: lieber ein Fenster zu gross als ein Beleg zu wenig."""
    print("\nGegenprobe: das Fenster ist nie zu klein")
    for zeichen in (5000, 12000, 25000, 40000, 80000):
        fenster, passt = gespraech.kontextfenster(zeichen, 2048)
        gebraucht = int(zeichen / 2.1) + 2048
        pruefe(not passt or fenster >= gebraucht,
               "%6d Zeichen brauchen ~%5d Token, Fenster %5d"
               % (zeichen, gebraucht, fenster))



def waechter_kennt_das_kuerzel():
    """\u26d4 Der Halluzinationswaechter war am 24.09. einen Tag lang TOT.

    Seit der Umstellung schreibt das Modell das zehnstellige Kuerzel,
    waehrend `kennungen` die vollen Namen fuehrt. Kein Beleg stand mehr in
    `bekannt`, _KENNUNG trifft nur die alte Form - die Liste wurde leer und
    waechter_belege kehrte mit None zurueck. Niemand pruefte mehr, ob eine
    zitierte Seite ueberhaupt von einem Werkzeug kam.

    \u26a0 Aufgefallen ist es NICHT, weil ein stiller Waechter genauso
      aussieht wie ein zufriedener. Deshalb steht hier fuer beide
      Zitierformen eine Zeile - und eine Gegenprobe, dass er nicht einfach
      alles anmeckert.
    """
    print("\n[W] Halluzinationswaechter kennt beide Zitierformen")
    voll = "kap-Lanxess-Rechnung-274821--cu86lj1edg"
    pruefe(gespraech.waechter_belege(
        "Die Einspannung erhoeht die Lebensdauer (cu86lj1edg, S. 12).",
        aufrufe=[], kennungen=[voll]) is not None,
        "erfundener Beleg in der KUERZEL-Form wird bemerkt")
    pruefe(gespraech.waechter_belege(
        "Aussage (DS-24-005, S. 12).",
        aufrufe=[], kennungen=["DS-24-005.md"]) is not None,
        "erfundener Beleg in der ALTEN Form weiterhin")
    # Gegenprobe: ohne sie waere die Reihe auch dann gruen, wenn der
    # Waechter ausnahmslos jeden Klammerausdruck anmeckerte.
    pruefe(gespraech.waechter_belege(
        "Ein Satz (Stand: 2024, S. 3).",
        aufrufe=[], kennungen=[voll]) is None,
        "Gegenprobe: Fliesstext in Klammern loest ihn NICHT aus")


if __name__ == "__main__":
    test_abschnitt_wird_erkannt()
    test_hinweis_wird_angehaengt()
    test_grenze_ist_einstellbar()
    test_der_hinweis_kommt_wirklich_im_gespraechszug_an()
    test_die_werte_kommen_auch_bei_partnern_an()
    test_lange_antwort_haelt_die_leitung_wach()
    test_fehler_gehen_nicht_verloren()
    test_das_lebenszeichen_macht_keine_leeren_nachrichten()
    test_kontextfenster_passt_sich_an()
    test_das_fenster_ist_nie_zu_klein()
    waechter_kennt_das_kuerzel()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
