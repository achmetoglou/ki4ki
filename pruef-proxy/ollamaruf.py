#!/usr/bin/env python3
"""Ollama fragen - und bei Aufgabe die Verbindung WIRKLICH schliessen.

⛔ Gemessen 23.09. abends im Ollama-Protokoll, waehrend `ollama stop`
  haengen blieb:

      slot id 0 | task 764  | n_gen = 1131 | tg = 0.41 t/s
      slot id 1 | task 434  | n_gen = 1459 | tg = 0.41 t/s

  Zwei Auftraege rechneten weiter, obwohl die Anfragen laengst
  abgebrochen waren - bei 0,41 Token je Sekunde. Jeder Zombie belegt
  einen Rechenplatz; die naechste Frage teilt ihn sich mit ihm und wird
  langsamer. Mehr Abbrueche, mehr Zombies: Der Abend wurde immer
  schlimmer statt besser.

⭐ Ollama bricht eine Erzeugung ab, wenn der Client GEHT. `urlopen` mit
  Zeitgrenze wirft aber nur eine Ausnahme und ueberlaesst die Verbindung
  dem Aufraeumer - Ollama merkt davon nichts und rechnet ins Leere.
  Deshalb fuehren wir die Verbindung hier selbst und schliessen sie in
  einem `finally`.

⭐ `verbinden` ist einhaengbar, damit sich das OHNE Ollama pruefen
  laesst: Die Pruefreihe gibt einen Draht hinein, der mitschreibt, ob er
  geschlossen wurde.
"""
import http.client
import json
import urllib.parse


def _verbinden(wirt, port, timeout):
    return http.client.HTTPConnection(wirt, port, timeout=timeout)


def fragen(url, leib, timeout, verbinden=None):
    """POST an Ollama, Antwort als ausgepacktes JSON.

    Wirft weiter, was schiefgeht (Zeitgrenze, Netz, kaputtes JSON) - der
    Aufrufer entscheidet, was das bedeutet. Zugesichert ist nur eines:
    Die Verbindung ist danach zu, in JEDEM Fall.
    """
    teile = urllib.parse.urlsplit(url)
    pfad = teile.path or "/"
    if teile.query:
        pfad += "?" + teile.query
    auf = verbinden or _verbinden
    draht = auf(teile.hostname, teile.port or 80, timeout)
    try:
        draht.request("POST", pfad, body=leib,
                      headers={"Content-Type": "application/json"})
        antwort = draht.getresponse()
        roh = antwort.read()
    finally:
        # ⛔ Das ist der ganze Punkt dieser Datei. Ohne dieses close()
        #   rechnet Ollama nach einer Zeitueberschreitung weiter.
        try:
            draht.close()
        except Exception:
            pass
    return json.loads(roh.decode("utf-8", "replace") or "{}")
