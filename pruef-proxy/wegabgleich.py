#!/usr/bin/env python3
"""A2: Fuehrt JEDER Weg nach draussen an einer Rechtepruefung vorbei?

Zweimal ist im Projekt ein Rechteloch entstanden, beide Male gleich: Ein
neuer Weg wurde gebaut, und niemand merkte, dass er an der Pruefung vorbei-
geht (30.07.: JSON-Weg gab Bestandstitel an ein Konto ohne Bereich). Diese
Pruefung liest den Syntaxbaum von pruef_proxy.py und fragt fuer jede Methode
der Klasse Griff, die etwas ausgibt: Ruft sie eine Rechtefunktion? Wenn
nicht, muss sie hier ausdruecklich ausgenommen sein - mit Grund.

Vom Testserver (T4) uebernommen 28.08.; laeuft in dialogtest.py vor jedem Push.

  python3 wegabgleich.py [datei]        Rueckgabe 1 bei Befund
"""
import ast
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
DATEI = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "pruef_proxy.py")

# Die Funktionen, die ueber Zugang entscheiden (alle MODULFUNKTIONEN).
RECHTE = {"bereich_sichtbar", "erlaubte_dokumente", "dokument_erlaubt", "darf_sehen", "angemeldet",
          "marke_gilt", "_darf_rolle_setzen", "darf_einsehen"}
# Alles, womit Daten den Prozess verlassen.
AUSGABE = {"_json", "_json_antwort", "_sende_strom", "_strom_stueck", "_sende_html", "_weiterleiten",
           "_direkt_senden", "_strom_beginnen"}
# Ausgenommen - jede Zeile mit Grund.
AUSNAHMEN = {
    # Reine Ausgabehelfer: schreiben, was ihnen gegeben wird; die Pruefung sitzt beim Aufrufer.
    "_json": "Ausgabehelfer", "_json_antwort": "Ausgabehelfer", "_sende_strom": "Ausgabehelfer",
    "_strom_stueck": "Ausgabehelfer", "_strom_schliessen": "Ausgabehelfer", "_strom_beginnen": "Ausgabehelfer",
    "_sende_html": "Ausgabehelfer", "_direkt_senden": "Ausgabehelfer (Aufrufer pruefen)",
    "_abschluss_stueck": "Ausgabehelfer", "_stand": "Statusmeldung ohne Bestandsdaten", "_stand_weg": "raeumt Status weg",
    "_fehler": "Fehlermeldung ohne Bestandsdaten",
    "_weiterleiten": "reicht an AnythingLLM durch, das selbst prueft",
    "_bereich_neu": "reicht /workspace/new an AnythingLLM durch (prueft Rolle/Anmeldung selbst) und sichert erst nach dessen Antwort ab",
    "do_POST": "Verteiler - die Zielmethoden pruefen", "do_GET": "Verteiler - die Zielmethoden pruefen",
    "do_PUT": "reicht an AnythingLLM durch", "do_DELETE": "reicht an AnythingLLM durch (Bereich loeschen: AnythingLLM prueft)",
    "do_PATCH": "reicht an AnythingLLM durch", "do_OPTIONS": "reicht an AnythingLLM durch",
}
# Einstiege, die als Schutz fuer ihre Aufrufer-Kette gelten - mit Grund.
GESCHUETZTE_EINSTIEGE = {
    "_chat": "Chat-Einstieg: jeder Antwortweg darin prueft bereich_sichtbar selbst oder gibt nur den "
             "Faden-Zustand des fragenden Kontos aus; alles Uebrige geht per _weiterleiten an AnythingLLM",
}
# Wege, die einen Bereich entgegennehmen, muessen den BEREICH pruefen - Anmeldung reicht nicht.
BEREICHSPFLICHT = {"bereich_sichtbar"}


def nimmt_bereich(fn):
    return any(a.arg in ("bereich", "slug", "workspace") for a in fn.args.args)


def rechte_pruefungen(fn):
    echte, scheinbare = set(), set()
    for k in ast.walk(fn):
        if not isinstance(k, ast.Call):
            continue
        f = k.func
        if isinstance(f, ast.Name) and f.id in RECHTE:
            echte.add(f.id)
        elif isinstance(f, ast.Attribute) and f.attr in RECHTE:
            if isinstance(f.value, ast.Name) and f.value.id == "self":
                scheinbare.add("self.%s" % f.attr)       # keine Methode -> AttributeError
            else:
                echte.add(f.attr)
    return echte, scheinbare


def ausgaben(fn):
    raus = set()
    for k in ast.walk(fn):
        if isinstance(k, ast.Call):
            name = k.func.attr if isinstance(k.func, ast.Attribute) else getattr(k.func, "id", None)
            if name in AUSGABE:
                raus.add(name)
        if isinstance(k, ast.Attribute) and k.attr == "write" and isinstance(k.value, ast.Attribute) and k.value.attr == "wfile":
            raus.add("wfile.write")
    return raus


def aufrufer(klasse):
    """method -> Menge der Methoden, die sie aufrufen (self.x())."""
    wer = {}
    for fn in klasse.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for k in ast.walk(fn):
            if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute) and isinstance(k.func.value, ast.Name) and k.func.value.id == "self":
                wer.setdefault(k.func.attr, set()).add(fn.name)
    return wer


def pruefen(datei=DATEI):
    baum = ast.parse(open(datei, encoding="utf-8").read(), os.path.basename(datei))
    klasse = next((k for k in ast.walk(baum) if isinstance(k, ast.ClassDef) and k.name == "Griff"), None)
    if klasse is None:
        return {"offen": [("Griff", "", 0, "Klasse nicht gefunden")], "geprueft": [], "ausgenommen": [], "kaputt": []}
    wer = aufrufer(klasse)
    methoden = {fn.name: fn for fn in klasse.body if isinstance(fn, ast.FunctionDef)}

    def geschuetzt_ueber_aufrufer(name, tiefe=0, gesehen=None):
        """Wird diese Methode NUR aus Methoden erreicht, die selbst pruefen? (max. 3 Stufen)"""
        gesehen = gesehen or set()
        if tiefe > 3 or name in gesehen:
            return False
        gesehen.add(name)
        rufer = wer.get(name) or set()
        if not rufer:
            return False
        for r in rufer:
            if r.startswith("do_"):
                return False      # Verteiler zaehlt NIE als Schutz - auch wenn er anderswo prueft
            if r in GESCHUETZTE_EINSTIEGE:
                continue
            fn = methoden.get(r)
            if fn is None:
                return False
            echte, _ = rechte_pruefungen(fn)
            if echte:
                continue
            if not geschuetzt_ueber_aufrufer(r, tiefe + 1, gesehen):
                return False
        return True

    offen, geprueft, ausgenommen, kaputt = [], [], [], []
    for name, fn in methoden.items():
        raus = ausgaben(fn)
        if not raus:
            continue
        rechte, scheinbare = rechte_pruefungen(fn)
        if scheinbare:
            kaputt.append((name, fn.lineno, sorted(scheinbare)))
        if nimmt_bereich(fn) and not (rechte & BEREICHSPFLICHT):
            offen.append((name, sorted(raus), fn.lineno, "nimmt einen Bereich entgegen, prueft aber nur %s" % (", ".join(sorted(rechte)) or "gar nichts")))
        elif rechte:
            geprueft.append((name, sorted(rechte), sorted(raus)))
        elif name in AUSNAHMEN:
            ausgenommen.append((name, AUSNAHMEN[name]))
        elif name in GESCHUETZTE_EINSTIEGE:
            ausgenommen.append((name, GESCHUETZTE_EINSTIEGE[name]))
        elif geschuetzt_ueber_aufrufer(name):
            geprueft.append((name, ["ueber Aufrufer: " + ", ".join(sorted(wer.get(name) or []))[:60]], sorted(raus)))
        else:
            offen.append((name, sorted(raus), fn.lineno, "gibt aus ueber %s" % ", ".join(sorted(raus))))
    return {"offen": offen, "geprueft": geprueft, "ausgenommen": ausgenommen, "kaputt": kaputt}


def main():
    e = pruefen()
    print("== Wege MIT Rechtepruefung (%d)" % len(e["geprueft"]))
    for name, rechte, raus in sorted(e["geprueft"]):
        print("  ok   %-26s %s" % (name, ", ".join(rechte)))
    print("\n== Ausgenommen, mit Grund (%d)" % len(e["ausgenommen"]))
    for name, grund in sorted(e["ausgenommen"]):
        print("  --   %-26s %s" % (name, grund))
    print("\n== Wege OHNE Rechtepruefung (%d)" % len(e["offen"]))
    for name, raus, zeile, grund in sorted(e["offen"]):
        print("  LOCH %-26s Zeile %-5d %s" % (name, zeile, grund))
    print("\n== Scheinbare Pruefungen (self.x - stuerzt ab): %d" % len(e["kaputt"]))
    for name, zeile, welche in e["kaputt"]:
        print("  KAPUTT %-24s Zeile %d %s" % (name, zeile, ", ".join(welche)))
    return 1 if (e["offen"] or e["kaputt"]) else 0


if __name__ == "__main__":
    sys.exit(main())
