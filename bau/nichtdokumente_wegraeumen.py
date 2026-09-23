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


def _gruende(namen):
    """Jeden Namen von der EINEN Regel beurteilen lassen. Ein node-Aufruf."""
    if not namen:
        return {}
    import ablauf_pruefen
    js = _regel_js() + ("\nconsole.log(JSON.stringify(%s.map("
                        "n => [n, NICHTDOKUMENT(n)])));"
                        % json.dumps(namen, ensure_ascii=False))
    return dict((n, g) for n, g in json.loads(ablauf_pruefen.node_lauf(js)) if g)


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


def _eingaenge(wurzel):
    """Alle Dateien, die unterhalb eines input/-Ordners liegen."""
    for ordner, _, dateien in os.walk(wurzel):
        teile = ordner.split(os.sep)
        if "input" not in teile:
            continue
        for d in dateien:
            yield os.path.join(ordner, d)


def wegraeumen(wurzel, wirklich=False, jetzt=None, namen_zeigen=False):
    jetzt = jetzt or time.strftime("%Y-%m-%d %H:%M:%S")
    alle = list(_eingaenge(wurzel))
    treffer = _gruende(sorted(set(os.path.basename(p) for p in alle)))

    erg = {"gesehen": len(alle), "erkannt": 0, "verschoben": 0,
           "gruende": {}, "namen": []}
    for pfad in alle:
        grund = treffer.get(os.path.basename(pfad))
        if not grund:
            continue
        erg["erkannt"] += 1
        erg["gruende"][grund] = erg["gruende"].get(grund, 0) + 1
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


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wirklich = "--wirklich" in sys.argv
    zeigen = "--namen" in sys.argv
    wurzel = args[0] if args else "dokumente"
    if not os.path.isdir(wurzel):
        raise SystemExit("Kein Ordner: %s" % wurzel)
    e = wegraeumen(wurzel, wirklich=wirklich, namen_zeigen=zeigen)
    print("Dateien in den Eingaengen : %d" % e["gesehen"])
    print("davon keine Dokumente     : %d" % e["erkannt"])
    for g, n in sorted(e["gruende"].items(), key=lambda x: -x[1]):
        print("    %-22s %d" % (g, n))
    if zeigen:
        for n, g in e["namen"]:
            print("    %-40s %s" % (n[:40], g))
    print("verschoben                : %d%s"
          % (e["verschoben"],
             "" if wirklich else "   (Trockenlauf - mit --wirklich raeumen)"))
