#!/usr/bin/env python3
"""Nichtdokumente aus den Eingaengen nach aussortiert/ raeumen.

⛔ Gemessen am 23.09.2026 am laufenden System: Eine 'Thumbs.db' im Eingang
  wird bei JEDEM Durchgang erneut als "kein Dokument" uebersprungen - und
  bleibt liegen. Ueber zehn Durchgaenge: input 1, aussortiert 0. Sie
  blockiert nichts (das war der alte Fehler), aber der Eingang wird nie
  leer. Bei 41 .db und 54 Office-Sperrdateien im KAP-Bestand heisst das:
  "Eingang leer" taugt nicht mehr als Zeichen, dass ein Lauf durch ist.

⭐ EINE Regel, zwei Leser. Die Entscheidung "ist das ein Dokument?" wird
  hier NICHT nachgebaut, sondern aus dem Ablaufplan geholt und mit node
  ausgefuehrt - derselbe Code, den n8n im Betrieb nutzt. Eine zweite
  Fassung in Python waere genau der Fehler, den der mkmd-Dienst
  vermeidet: zwei Rechnungen, die auseinanderlaufen, ohne dass es
  jemandem auffaellt.

⭐ Warum ausserhalb des Ablaufplans: Der Weg nach aussortiert/ braucht
  Felder (aussortiert_path, bereich, source_path), die erst NACH der
  Unterkette entstehen - ein uebersprungenes Nichtdokument kommt da nie
  hin. Und ein executeCommand mitten im Datenstrom verschluckt die
  Binaerdaten (gemessen 04.08.). Also lieber ein eigenes Werkzeug, das
  den laufenden Betrieb nicht anfasst.

Aufruf:
    python3 bau/nichtdokumente_wegraeumen.py dokumente            # nur zaehlen
    python3 bau/nichtdokumente_wegraeumen.py dokumente --wirklich # raeumen
    ... --namen    zeigt zusaetzlich die Dateinamen (VERTRAULICH)
    ... --alles    zaehlt auch ausserhalb der Eingaenge (Parkplatz) - als
                   Vorschau, WIE VIEL sich stauen wird, wenn der Parkplatz
                   in den Eingang wandert. Verschoben wird trotzdem nur
                   aus input/.
"""
import io
import json
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)


def _regel_js():
    """Den Nichtdokument-Filter aus dem Ablaufplan holen."""
    plan = os.path.join(os.path.dirname(HIER), "n8n-workflows",
                        "1_KI4KI-Masse-Ingest.json")
    d = json.load(io.open(plan, encoding="utf-8"))
    for k in d["nodes"]:
        if k.get("name") == "Nur ein Bereich je Durchgang":
            js = k["parameters"]["jsCode"]
            a, b = js.find("const NICHTDOKUMENT"), js.find("const ersterBereich")
            if a < 0 or b <= a:
                raise SystemExit(
                    "Der Filter steht nicht mehr zwischen den erwarteten "
                    "Zeilen - bitte bau/ablauf_pruefen.py ansehen.")
            return js[a:b]
    raise SystemExit("Baustein 'Nur ein Bereich je Durchgang' nicht gefunden.")


def _pakete(namen, grenze=60000):
    """Die Namen in Haeppchen teilen, die in eine Befehlszeile passen.

    ⛔ Gemessen 23.09.: 6.435 Namen sind als JSON 135.135 Zeichen - mehr
      als ARG_MAX (typisch 131.072). Der Aufruf starb mit
      "Argument list too long". Auf dem Server laeuft node ueber
      `docker exec`, was zusaetzlich kostet; die Grenze liegt also
      bewusst deutlich darunter.
    """
    raus, jetzt, laenge = [], [], 2
    for n in namen:
        # +2, nicht +1: json.dumps trennt mit Komma UND Leerzeichen.
        # Der Unterschied sind bei 3.000 Namen genau 3.000 Zeichen - und
        # damit die Pruefung rot (gemessen: 62.979 statt <= 60.000).
        kosten = len(json.dumps(n, ensure_ascii=False)) + 2
        if jetzt and laenge + kosten > grenze:
            raus.append(jetzt)
            jetzt, laenge = [], 2
        jetzt.append(n)
        laenge += kosten
    if jetzt:
        raus.append(jetzt)
    return raus


def _gruende(namen):
    """Jeden Namen von der EINEN Regel beurteilen lassen. Ein node-Aufruf."""
    if not namen:
        return {}
    import ablauf_pruefen
    regel = _regel_js()
    treffer = {}
    for paket in _pakete(namen):
        js = regel + ("\nconsole.log(JSON.stringify(%s.map("
                      "n => [n, NICHTDOKUMENT(n)])));"
                      % json.dumps(paket, ensure_ascii=False))
        for n, g in json.loads(ablauf_pruefen.node_lauf(js)):
            if g:
                treffer[n] = g
    return treffer


def ziel_fuer(pfad):
    """input/ -> aussortiert/, der Unterordner bleibt.

    ⛔ Ohne 'input' im Pfad: None. Der Parkplatz ist Kundenbestand und
      wird NIE angefasst.
    """
    teile = pfad.split(os.sep)
    if "input" not in teile:
        return None
    i = len(teile) - 1 - teile[::-1].index("input")
    if i == 0:
        return None
    return os.sep.join(teile[:i] + ["aussortiert"] + teile[i + 1:])


STUFEN = ("input", "parkplatz", "archiv", "aussortiert", "loeschen")


def _stufe(pfad):
    """In welcher Ablagestufe liegt die Datei? '' wenn in keiner."""
    for teil in pfad.split(os.sep):
        if teil in STUFEN:
            return teil
    return ""


def _eingaenge(wurzel, alles=False):
    """Alle Dateien unterhalb eines input/-Ordners - oder, mit alles=True,
    ueberall.

    ⛔ alles=True ist NUR zum Zaehlen. Verschoben wird trotzdem nur aus
      input/, weil ziel_fuer() ausserhalb davon None liefert. Der
      Parkplatz ist Kundenbestand und wird nie angefasst.
    """
    for ordner, _, dateien in os.walk(wurzel):
        if not alles and "input" not in ordner.split(os.sep):
            continue
        for d in dateien:
            yield os.path.join(ordner, d)


def wegraeumen(wurzel, wirklich=False, jetzt=None, namen_zeigen=False,
               alles=False):
    jetzt = jetzt or time.strftime("%Y-%m-%d %H:%M:%S")
    alle = list(_eingaenge(wurzel, alles=alles))
    treffer = _gruende(sorted(set(os.path.basename(p) for p in alle)))

    erg = {"gesehen": len(alle), "erkannt": 0, "verschoben": 0,
           "gruende": {}, "stufen": {}, "namen": []}
    for pfad in alle:
        grund = treffer.get(os.path.basename(pfad))
        if not grund:
            continue
        erg["erkannt"] += 1
        erg["gruende"][grund] = erg["gruende"].get(grund, 0) + 1
        # ⭐ Je Ablagestufe zaehlen. Die Gesamtzahl allein taugt nicht zur
        #   Planung: Nichtdokumente in archiv/ und aussortiert/ stoeren
        #   niemanden. Was vor dem grossen Lauf zaehlt, ist der PARKPLATZ -
        #   die wandern in den Eingang und bleiben dort liegen.
        _st = _stufe(pfad) or "(sonst)"
        erg["stufen"][_st] = erg["stufen"].get(_st, 0) + 1
        if namen_zeigen:
            erg["namen"].append((os.path.basename(pfad), grund))
        ziel = ziel_fuer(pfad)
        if not ziel or not wirklich:
            continue
        # ⛔ Nie ueberschreiben: liegt dort schon etwas gleichen Namens,
        #   bleibt das Original liegen und faellt beim naechsten Lauf auf.
        if os.path.exists(ziel):
            continue
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        teile = ziel.split(os.sep)
        i = len(teile) - 1 - teile[::-1].index("aussortiert")
        log = os.sep.join(teile[:i + 1] + ["aussortiert.log"])
        with io.open(log, "a", encoding="utf-8") as f:
            f.write(u"[%s] %s | %s\n" % (jetzt, os.path.basename(pfad), grund))
        os.rename(pfad, ziel)
        erg["verschoben"] += 1
    return erg


def bericht(e, alles=False, wirklich=False, zeigen=False):
    """Die Ausgabe als Zeilen - damit sie pruefbar ist.

    ⛔ Die Aufschluesselung stand frueher nur bei MEHR ALS EINER Stufe da.
      Lagen alle Treffer in einer, fehlte sie genau dann, wenn die Frage
      "wo liegen sie?" eine eindeutige Antwort gehabt haette. Eine
      Ausgabe, die sich bei Eindeutigkeit versteckt, ist schlechter als
      gar keine - man haelt die Zahl fuer unaufgeschluesselt.
    """
    z = ["Dateien %-18s: %d"
         % ("ueberall" if alles else "in den Eingaengen", e["gesehen"]),
         "davon keine Dokumente     : %d" % e["erkannt"]]
    for g, n in sorted(e["gruende"].items(), key=lambda x: -x[1]):
        z.append("    %-22s %d" % (g, n))
    if e["stufen"]:
        z.append("je Ablagestufe:")
        for st, n in sorted(e["stufen"].items(), key=lambda x: -x[1]):
            hinweis = ""
            if st == "parkplatz":
                hinweis = "   <- wandern in den Eingang und bleiben liegen"
            elif st in ("archiv", "aussortiert"):
                hinweis = "   (stoeren dort niemanden)"
            elif st == "input":
                hinweis = "   <- werden mit --wirklich geraeumt"
            z.append("    %-22s %d%s" % (st, n, hinweis))
    if zeigen:
        for n, g in e["namen"]:
            z.append("    %-40s %s" % (n[:40], g))
    z.append("verschoben                : %d%s"
             % (e["verschoben"],
                "" if wirklich else "   (Trockenlauf - mit --wirklich raeumen)"))
    return z


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wirklich = "--wirklich" in sys.argv
    zeigen = "--namen" in sys.argv
    alles = "--alles" in sys.argv
    wurzel = args[0] if args else "dokumente"
    if not os.path.isdir(wurzel):
        raise SystemExit("Kein Ordner: %s" % wurzel)
    e = wegraeumen(wurzel, wirklich=wirklich, namen_zeigen=zeigen,
                   alles=alles)
    for _z in bericht(e, alles=alles, wirklich=wirklich, zeigen=zeigen):
        print(_z)
