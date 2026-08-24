#!/usr/bin/env python3
"""Zusammenfassung in mehreren Durchgaengen - damit wirklich ALLES gelesen wird.

ZIEL: Das Dokument soll vollstaendig gelesen werden, nicht nur ein kleiner
Anteil (frueher rund 7 %). Fuer die Wissensdatenbank eines
Forschungsinstituts ist Teil-Lektuere zu wenig.

WAS DEM IM WEG STAND: Das Kontextfenster fasst 65.536 Token. Deutscher
Fachtext braucht rund 2,1 Zeichen je Token (gemessen: 48.000 Zeichen =
22.825 Token) - es passen also etwa 135.000 Zeichen in EINEN Durchgang,
abzueglich Anweisung und Antwort rund 110.000.

Gemessen am Bestand:
    kleinstes 628 | Median 151.117 | groesstes 1.370.571 Zeichen
    Bei 110.000 je Durchgang passen rund ein Drittel der Dokumente ganz
    hinein. Der Rest braucht zwei bis dreizehn Durchgaenge.

DER WEG ZU 100 %: Das Dokument wird in Stuecke geteilt, die je fuer sich
hineinpassen. Jedes Stueck wird zusammengefasst, und aus diesen
Teilzusammenfassungen entsteht die endgueltige. Nichts wird ausgelassen.

DER PREIS: Ein Dokument von 668.000 Zeichen braucht sieben Durchgaenge
plus einen zum Zusammenfuehren. Bei rund vier Minuten je Durchgang sind
das gut eine halbe Stunde - niemand wartet das im Chat ab.

DESHALB GEHOERT DAS ERGEBNIS IN DEN BESTAND, nicht in die Frage: Die
Zusammenfassung wird EINMAL erzeugt und gemerkt. Die erste Frage nach
einem grossen Dokument dauert; jede weitere ist sofort da. Auf Dauer
gehoert sie in die naechtliche Aufnahme - dann ist sie schon fertig,
bevor jemand fragt.

Dieses Modul liefert die Bausteine; eingehaengt wird es im naechsten
Schritt.
"""
import hashlib
import json
import os
import re

# Wie viel Text in EINEN Durchgang geht. Bewusst unter dem rechnerischen
# Maximum: Anweisung, Antwort und die Ungenauigkeit der Schaetzung
# brauchen Luft. Ueber die Umgebung aenderbar, ohne den Code anzufassen.
JE_DURCHGANG = int(os.environ.get("KI4KI_ZUSAMMENFASSUNG_STUECK") or 110000)

# Wo die fertigen Zusammenfassungen liegen. Eine Datei je Dokument, damit
# ein beschaedigter Eintrag nicht alle anderen mitnimmt.
# NEBEN DAS MODUL, nicht ins Heimatverzeichnis: Im Container gibt es fuer
# die Kennung 1001 keines, "~" loest dort nicht auf das Heimatverzeichnis
# des Entwicklers auf. Der
# Pfad zeigte ins Nirgendwo, das Anlegen scheiterte, und weil merken()
# jeden Fehler still schluckt, fiel es nicht auf - der zweite Aufruf
# rechnete acht Minuten lang alles neu.
# Dieselbe Falle ist bekannt; deshalb setzt die Compose auch
# KI4KI_GEDAECHTNIS=/app/.geprueft.json ausdruecklich.
SPEICHER = os.environ.get("KI4KI_ZUSAMMENFASSUNGEN") or \
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".zusammenfassungen")


def _kennung(titel, text):
    """Kennung aus Titel UND Inhalt.

    Der Inhalt gehoert hinein: Wird ein Dokument neu eingelesen - etwa nach
    einem Bilddurchlauf -, aendert sich der Text, und die alte
    Zusammenfassung waere falsch. Ueber die Kennung faellt sie von selbst
    weg, statt still weiterbenutzt zu werden.
    """
    h = hashlib.sha1()
    h.update((titel or "").encode("utf-8", "replace"))
    h.update(b"\x00")
    h.update((text or "").encode("utf-8", "replace"))
    sauber = re.sub(r"[^A-Za-z0-9_.-]+", "-", titel or "unbenannt")[:60]
    return "%s.%s.json" % (sauber, h.hexdigest()[:16])


def gemerkt(titel, text):
    """Die fertige Zusammenfassung, falls sie schon einmal erzeugt wurde."""
    p = os.path.join(SPEICHER, _kennung(titel, text))
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def merken(titel, text, ergebnis):
    """Die Zusammenfassung ablegen. Fehler hier duerfen nichts kosten."""
    try:
        os.makedirs(SPEICHER, exist_ok=True)
        p = os.path.join(SPEICHER, _kennung(titel, text))
        # Erst daneben schreiben, dann umbenennen: Ein Abbruch mitten im
        # Schreiben hinterlaesst sonst eine halbe Datei, die beim naechsten
        # Mal als gueltig gelesen wird.
        vor = p + ".teil"
        with open(vor, "w", encoding="utf-8") as f:
            json.dump(ergebnis, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(vor, p)
        return True
    except Exception:
        return False


def stuecke(text, je=None):
    """Den Text in Stuecke teilen, die einzeln hineinpassen.

    Getrennt wird an Absatzgrenzen, nicht mitten im Satz: Ein Stueck, das
    mit einem halben Satz beginnt, liefert eine Zusammenfassung, die mit
    einem halben Gedanken beginnt.
    """
    je = je or JE_DURCHGANG
    text = text or ""
    if len(text) <= je:
        return [text] if text else []
    raus, rest = [], text
    while len(rest) > je:
        schnitt = rest.rfind("\n\n", int(je * 0.6), je)
        if schnitt < 0:
            schnitt = rest.rfind("\n", int(je * 0.6), je)
        if schnitt < 0:
            schnitt = je
        raus.append(rest[:schnitt])
        rest = rest[schnitt:].lstrip("\n")
    if rest:
        raus.append(rest)
    return raus


def teil_auftrag(stueck, titel, nr, gesamt):
    """Auftrag fuer EIN Stueck. Bewusst sachlich, nicht schon verdichtet."""
    return (
        "Das folgende ist Teil %d von %d des Dokuments „%s“.\n\n"
        "Fasse NUR diesen Teil zusammen, auf Deutsch:\n"
        "1. Welche Themen und Ergebnisse kommen darin vor?\n"
        "2. Nenne Zahlen, Verfahren und Bezeichnungen, die im Text stehen.\n"
        "3. Erfinde nichts und ergaenze kein Allgemeinwissen.\n"
        "4. Schreibe sachlich und knapp - dieser Text wird spaeter mit den "
        "uebrigen Teilen zu einer Gesamtzusammenfassung verbunden.\n"
        "5. Wirkt der Teil unlesbar oder abgeschnitten, sage das in einem "
        "Satz.\n\n%s" % (nr, gesamt, titel, stueck))


AUFTRAG_REGEL = (
    "Stuetze dich AUSSCHLIESSLICH auf das Dokument und erfinde keine "
    "Inhalte. Du DARFST den vorhandenen Inhalt aber frei aufbereiten, "
    "gliedern und in die gewuenschte Form bringen (z.B. Praesentations-"
    "Gliederung mit Folientiteln und Stichpunkten je Folie, Handout, "
    "Tabelle, Lernkarten). Antworte auf Deutsch.")


def auftrag_direkt(text, titel, auftrag):
    """Ein Dokument, das in einen Durchgang passt, mit der Aufgabe des
    Nutzers bearbeiten."""
    return ("%s\n\nAUFGABE: %s\n\nDOKUMENT „%s“:\n%s"
            % (AUFTRAG_REGEL, auftrag, titel, text))


def gesamt_auftrag(teile, titel, auftrag=None):
    """Aus den Teilzusammenfassungen die endgueltige bauen - oder, wenn
    eine AUFGABE gestellt ist, diese aus ALLEN Teilen erfuellen."""
    zusammen = "\n\n".join("--- Teil %d ---\n%s" % (i, t)
                           for i, t in enumerate(teile, 1))
    if auftrag:
        return (
            "Unten stehen Zusammenfassungen ALLER %d Teile des Dokuments "
            "„%s“ - es wurde vollstaendig gelesen. %s\n\n"
            "AUFGABE: %s\n\n%s" % (len(teile), titel, AUFTRAG_REGEL,
                                    auftrag, zusammen))
    return (
        "Unten stehen die Zusammenfassungen ALLER %d Teile des Dokuments "
        "„%s“. Verbinde sie zu einer einzigen Zusammenfassung auf Deutsch.\n\n"
        "1. Beginne mit einem Satz, worum es insgesamt geht.\n"
        "2. Danach die wichtigsten Punkte als Aufzaehlung, in der "
        "Reihenfolge des Dokuments.\n"
        "3. Nenne nur, was in den Teilen steht. Erfinde nichts.\n"
        "4. Wiederhole dich nicht - was in mehreren Teilen vorkommt, "
        "gehoert einmal genannt.\n"
        "5. Melden mehrere Teile unlesbare Stellen, sage das am Ende in "
        "einem Satz.\n\n%s" % (len(teile), titel, zusammen))


def zusammenfassen(volltext, titel, frage_modell, melden=None, auftrag=None):
    """Ein Dokument vollstaendig zusammenfassen - ueber so viele Durchgaenge
    wie noetig.

    frage_modell(auftrag) -> Text. Wird von aussen gereicht, damit dieses
    Modul nichts ueber Ollama, Zeitgrenzen oder den Proxy wissen muss.
    melden(text) darf None sein; sonst wird der Fortschritt gemeldet -
    wer eine halbe Stunde wartet, will wissen, dass etwas passiert.

    Liefert ein dict: text, teile, zeichen, vollstaendig.
    """
    volltext = volltext or ""
    # Der Speicher kennt nur ZUSAMMENFASSUNGEN. Eine Praesentations-
    # Gliederung ist etwas anderes - die wird immer frisch gebaut.
    alt = None if auftrag else gemerkt(titel, volltext)
    if alt:
        return dict(alt, aus_dem_speicher=True)

    st = stuecke(volltext)
    if not st:
        return {"text": "", "teile": 0, "zeichen": 0, "vollstaendig": False,
                "aus_dem_speicher": False}

    if len(st) == 1:
        if melden:
            melden("Lese das Dokument (%d Zeichen) …" % len(volltext))
        text = frage_modell(auftrag_direkt(st[0], titel, auftrag) if auftrag
                            else teil_auftrag(st[0], titel, 1, 1))
        ergebnis = {"text": text or "", "teile": 1, "zeichen": len(volltext),
                    "vollstaendig": bool(text)}
        if text and not auftrag:
            merken(titel, volltext, ergebnis)
        return dict(ergebnis, aus_dem_speicher=False)

    teile = []
    for i, s in enumerate(st, 1):
        if melden:
            melden("Lese Teil %d von %d (%d Zeichen) …" % (i, len(st), len(s)))
        t = frage_modell(teil_auftrag(s, titel, i, len(st)))
        if not t:
            # Ein ausgefallener Teil macht die Zusammenfassung
            # unvollstaendig. Das wird gesagt, nicht verschwiegen - sonst
            # ist es wieder eine Zusammenfassung, die mehr verspricht als
            # sie gelesen hat.
            teile.append("[Teil %d konnte nicht gelesen werden.]" % i)
        else:
            teile.append(t)

    if melden:
        melden(("Erfülle die Aufgabe aus allen %d Teilen …" if auftrag
                else "Verbinde %d Teile zur Gesamtzusammenfassung …") % len(st))
    text = frage_modell(gesamt_auftrag(teile, titel, auftrag))
    fehlend = sum(1 for t in teile if t.startswith("[Teil "))
    ergebnis = {"text": text or "", "teile": len(st),
                "zeichen": len(volltext),
                "vollstaendig": bool(text) and fehlend == 0,
                "fehlende_teile": fehlend}
    if text and fehlend == 0 and not auftrag:
        merken(titel, volltext, ergebnis)
    return dict(ergebnis, aus_dem_speicher=False)
