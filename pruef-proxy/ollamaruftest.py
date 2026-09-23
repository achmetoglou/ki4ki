#!/usr/bin/env python3
"""Pruefreihe: eine aufgegebene Anfrage muss bei Ollama ABGESAGT werden.

⛔ Gemessen 23.09. abends im Ollama-Protokoll, waehrend `ollama stop`
  haengen blieb:

      slot id 0 | task 764  | n_gen = 1131 | tg = 0.41 t/s
      slot id 1 | task 434  | n_gen = 1459 | tg = 0.41 t/s

  Zwei Auftraege rechneten weiter, obwohl die Anfragen laengst
  abgebrochen waren. Jeder Zombie belegt einen Rechenplatz; die naechste
  Frage teilt ihn sich mit ihm und wird langsamer - mehr Abbrueche, mehr
  Zombies. Deshalb wurde der Abend immer schlimmer statt besser.

⭐ Ollama bricht eine Erzeugung ab, wenn der Client GEHT. `urlopen` mit
  Zeitgrenze wirft aber nur eine Ausnahme; die Verbindung wird dem
  Aufraeumer ueberlassen. Wir muessen sie selbst und sofort schliessen.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ollamaruf      # noqa: E402

FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


class Antwort:
    def __init__(self, inhalt=b'{"message": {"content": "gut"}}', fehler=None):
        self._inhalt = inhalt
        self._fehler = fehler

    def read(self, *a):
        if self._fehler:
            raise self._fehler
        return self._inhalt


class Leitung:
    """Ein vorgetaeuschter Draht, der mitschreibt, ob er geschlossen wurde."""

    def __init__(self, fehler_beim_lesen=None, fehler_beim_holen=None):
        self.geschlossen = 0
        self.gesendet = None
        self._lesefehler = fehler_beim_lesen
        self._holfehler = fehler_beim_holen

    def request(self, verb, pfad, body=None, headers=None):
        self.gesendet = (verb, pfad, body)

    def getresponse(self):
        if self._holfehler:
            raise self._holfehler
        return Antwort(fehler=self._lesefehler)

    def close(self):
        self.geschlossen += 1


def test_normale_antwort():
    print("\nEine normale Antwort kommt durch")
    draht = Leitung()
    erg = ollamaruf.fragen("http://ollama:11434/api/chat", b"{}", 30,
                           verbinden=lambda *a, **k: draht)
    pruefe(erg.get("message", {}).get("content") == "gut",
           "die Antwort wird gelesen und ausgepackt")
    pruefe(draht.geschlossen == 1,
           "und die Leitung wird danach geschlossen - nicht liegengelassen")


def test_zeitgrenze_sagt_ollama_ab():
    """DER Fall, um den es geht."""
    print("\nBei Zeitueberschreitung wird die Leitung geschlossen")
    draht = Leitung(fehler_beim_holen=TimeoutError("timed out"))
    try:
        ollamaruf.fragen("http://ollama:11434/api/chat", b"{}", 1,
                         verbinden=lambda *a, **k: draht)
        pruefe(False, "die Zeitueberschreitung haette durchkommen muessen")
    except TimeoutError:
        pruefe(True, "die Zeitueberschreitung kommt beim Aufrufer an")
    pruefe(draht.geschlossen == 1,
           "⛔ und die Leitung ist ZU - nur daran merkt Ollama, dass "
           "niemand mehr zuhoert, und bricht die Erzeugung ab")


def test_auch_ein_lesefehler_schliesst():
    print("\nAuch ein Fehler beim Lesen laesst nichts offen")
    draht = Leitung(fehler_beim_lesen=OSError("Verbindung weg"))
    try:
        ollamaruf.fragen("http://ollama:11434/api/chat", b"{}", 30,
                         verbinden=lambda *a, **k: draht)
        pruefe(False, "der Fehler haette durchkommen muessen")
    except OSError:
        pruefe(True, "der Fehler kommt beim Aufrufer an")
    pruefe(draht.geschlossen == 1, "die Leitung ist trotzdem zu")


def test_der_leib_geht_wirklich_raus():
    print("\nGegenprobe: es wird auch wirklich gesendet")
    draht = Leitung()
    ollamaruf.fragen("http://ollama:11434/api/chat", b'{"model":"x"}', 30,
                     verbinden=lambda *a, **k: draht)
    verb, pfad, leib = draht.gesendet
    pruefe(verb == "POST", "als POST")
    pruefe(pfad == "/api/chat",
           "an den Pfad aus der Adresse (ist: %r)" % pfad)
    pruefe(leib == b'{"model":"x"}', "mit dem uebergebenen Leib")


if __name__ == "__main__":
    test_normale_antwort()
    test_zeitgrenze_sagt_ollama_ab()
    test_auch_ein_lesefehler_schliesst()
    test_der_leib_geht_wirklich_raus()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
