#!/usr/bin/env python3
"""Angehaengte Dateien aus dem Chat zu EINEM Eintrag zusammenfuehren.

⛔ Meldung vom 17.09.2026, woertlich: "Es wurden 3 Dateien ueber das
  + Zeichen zusaetzlich in diesem Chat bereitgestellt allerdings nur eins
  bei der Anfrage ausgewertet."

  Ursache, im Quelltext belegt - der Anhang-Weg konnte nie mehr als eine
  Datei halten, und zwar gleich zweifach:
    1. `_parse_mitschnitt` nahm aus der Formularsendung nur `dateien[0]`.
       Die Formularzerlegung selbst lieferte immer ALLE Dateien.
    2. Der Merkspeicher `_ANHANG[(bereich, konto)]` war EIN Eintrag. Zwei
       Sendungen hintereinander ueberschrieben sich - die letzte gewann.
  Beide Wege enden gleich: genau ein Dokument erreicht die Antwort.

⭐ Warum die Zusammenfuehrung hier und nicht im Handler steht: Damit die
  Entscheidung "alle Dateien" pruefbar ist, ohne einen Server zu starten -
  und damit im Handler gar keine Stelle mehr existiert, an der man
  versehentlich wieder nur die erste nimmt.

Der zusammengefuehrte Text geht denselben Weg wie ein grosses Einzel-
dokument: `mehrstufig.stuecke()` zerlegt ihn, jedes Stueck wird gelesen,
am Ende steht eine Antwort ueber alles. Die Maschinerie dafuer gibt es
seit dem 28.08.; sie musste nur etwas zu lesen bekommen.
"""
import time


def _trennzeile(i, gesamt, name):
    return "--- Dokument %d von %d: %s ---" % (i, gesamt, name)


def _bauen(dokumente, jetzt, grenze):
    """Aus der Liste (name, text) EINEN Eintrag machen.

    Bei genau einem Dokument bleibt alles wie bisher: kein Vorspann, der
    Name ist der Dateiname. Sonst wuerde die Fusszeile der Antwort
    ("Antwort aus dem angehaengten Dokument X") ploetzlich anders lauten,
    obwohl sich am Fall nichts geaendert hat.
    """
    if len(dokumente) == 1:
        name, text = dokumente[0]
    else:
        text = "\n\n".join(
            _trennzeile(i, len(dokumente), n) + "\n" + t
            for i, (n, t) in enumerate(dokumente, 1))
        name = "%d Dokumente: %s" % (len(dokumente),
                                     ", ".join(n for n, _ in dokumente))
    return {"dokumente": list(dokumente),
            "text": text[:grenze],
            "roh_len": len(text),
            "name": name,
            "wann": jetzt}


def aufnehmen(dateien, text_aus, vorher=None, jetzt=None,
              haltbar=1200, grenze=4000000):
    """ALLE angehaengten Dateien aufnehmen und an einen noch frischen
    Vorgaenger anhaengen.

    dateien  - Liste (dateiname, rohbytes), so wie die Formularzerlegung
               sie liefert
    text_aus - Funktion rohbytes -> Text (im Betrieb: Tika)
    vorher   - der bisherige Eintrag desselben Bereichs und Kontos
    Rueckgabe: Eintrag oder None, wenn nichts Lesbares dabei war und es
               auch keinen frischen Vorgaenger gibt.
    """
    jetzt = time.time() if jetzt is None else jetzt

    neu = []
    for name, inhalt in (dateien or []):
        try:
            text = (text_aus(inhalt) or "").strip()
        except Exception:
            text = ""
        # ⭐ Eine unlesbare Datei darf die anderen NICHT mitnehmen. Genau
        #   diese Fehlerklasse hat am 23.09. die Aufnahmekette stillgelegt.
        if text:
            neu.append((name, text))

    frisch = (vorher or {}).get("dokumente") or []
    if not vorher or (jetzt - (vorher.get("wann") or 0)) > haltbar:
        frisch = []

    # Gleicher Dateiname = neuere Fassung ersetzt die aeltere, an ihrer Stelle.
    namen_neu = set(n for n, _ in neu)
    dokumente = [d for d in frisch if d[0] not in namen_neu] + neu
    if not dokumente:
        return None
    return _bauen(dokumente, jetzt, grenze)
