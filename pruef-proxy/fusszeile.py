#!/usr/bin/env python3
"""Die Fusszeile unter einer Antwort - was darin doppelt steht, fliegt raus.

⛔ Meldung vom 15.09.2026, woertlich: "steht fast bei jedem Output zwei
  mal die Modellangabe und die Dokumente die gesucht wurden". Die
  Modellzeile ist am 22.09. entfernt worden, die doppelte Dokumentnennung
  blieb. Gemessen 23.09. an einer echten Antwort:

    durchsucht: Pruefungsfragen zu DVS 2291 ... · zusammengefasst ·
    vollstaendig gelesen: Pruefungsfragen zu DVS 2291 ... (ganzer Text)

  Derselbe Titel zweimal in derselben Zeile. "Vollstaendig gelesen" sagt
  ohnehin mehr als "durchsucht" - wer den ganzen Text gelesen hat, hat
  ihn erst recht durchsucht.

⭐ Was hier NICHT wegfaellt und auch nicht wegfallen darf:
    - der Unterschied "Quelle:" (wirklich belegt) gegen "durchsucht:"
      (gesucht, nichts belegt) - genau der hat am 22.09. einen fehlenden
      Beleg gemeldet
    - "N Zitate geprueft, M nicht gefunden"
    - "⚠ erfundene Bildnummern gestrichen", "⚠ N Aussage(n) nicht belegt"
  Das steht nirgendwo sonst. Die Quellenliste von AnythingLLM zeigt
  gefundene Textstellen - sie kann nicht sagen, dass eine Aussage
  unbelegt blieb. Genau das ist der Produktanspruch: Schluesse UND Belege.
"""


def dokumente_fuer_zeile(dokumente, gelesen_titel, titel_von=None):
    """Titel fuer die 'durchsucht:'/'Quelle:'-Zeile.

    Ohne die, die weiter hinten ohnehin als "vollstaendig gelesen"
    genannt werden. Bleibt nichts uebrig, entfaellt die Zeile ganz.
    """
    t = titel_von or (lambda d: d)
    schon = set(gelesen_titel or ())
    return [t(d) for d in (dokumente or []) if t(d) not in schon]
