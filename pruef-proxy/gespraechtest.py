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
    pruefe(gespraech.ANTWORT_TOKEN >= 4096,
           "die Vorgabe ist hoch genug fuer mehrere ausfuehrliche Antworten "
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
    pruefe("KI4KI_ANTWORT_TOKEN=${KI4KI_ANTWORT_TOKEN:-8192}" in t,
           "die Antwortlaenge steht in der Compose und ist ueberschreibbar")
    pruefe("KI4KI_GESPRAECH_TIMEOUT=${KI4KI_GESPRAECH_TIMEOUT:-600}" in t,
           "die Zeitgrenze ebenso - sonst laeuft eine lange Antwort in "
           "die alten 240 s und stirbt ganz, statt nur gekuerzt zu werden")


if __name__ == "__main__":
    test_abschnitt_wird_erkannt()
    test_hinweis_wird_angehaengt()
    test_grenze_ist_einstellbar()
    test_der_hinweis_kommt_wirklich_im_gespraechszug_an()
    test_die_werte_kommen_auch_bei_partnern_an()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
