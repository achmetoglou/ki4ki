"""Prueft die geaenderten Code-Knoten der Ablaufplaene - ohne n8n.

Warum das noetig ist: Die Knoten enthalten JavaScript, das nur im
laufenden n8n ausgefuehrt wird. Eine Aenderung daran ist sonst erst im
Betrieb pruefbar - also genau dort, wo ein Fehler teuer ist. Der
Ablaufplan hat 30 Knoten, 20 davon laufen bei Fehler einfach weiter; ein
falscher Vergleich faellt dort NICHT auf.

Das Skript schneidet die geaenderten Entscheidungen aus dem JSON heraus,
fuehrt sie mit node aus und prueft sie gegen Faelle mit bekanntem
Ergebnis. Zu jedem Fall gehoert die Angabe, was herauskommen MUSS.

⚠ Dieses Skript gehoert auf den HOST. Die Ablaufplaene liegen im Repo
(n8n-workflows/), nicht im Proxy-Container - ein Aufruf per docker exec
scheitert daran. node holt sich das Skript notfalls aus dem n8n-Container.

Aufruf:
    cd ~/ki4ki && python3 bau/ablauf_pruefen.py
"""
import json
import io
import os
import subprocess
import sys

def _plaene_finden():
    """Wo liegen die Ablaufplaene?

    Ueber die Standardeingabe gestartet (python3 - < datei) kennt das
    Skript seinen eigenen Ort NICHT: __file__ ist dann "<stdin>", und der
    daraus abgeleitete Pfad landet im Wurzelverzeichnis. Deshalb mehrere
    Wege - und am Ende eine Meldung, die sagt was zu tun ist, statt eines
    Traceback.
    """
    kandidaten = []
    if os.environ.get("PLAENE"):
        kandidaten.append(os.environ["PLAENE"])
    hier = os.path.abspath(globals().get("__file__", ""))
    if os.path.basename(hier) == "ablauf_pruefen.py":
        kandidaten.append(os.path.join(os.path.dirname(os.path.dirname(hier)),
                                       "n8n-workflows"))
    kandidaten.append(os.path.join(os.getcwd(), "n8n-workflows"))
    kandidaten.append(os.path.join(os.getcwd(), "..", "n8n-workflows"))
    for k in kandidaten:
        if os.path.isdir(k):
            return os.path.abspath(k)
    raise SystemExit(
        "Die Ablaufplaene sind nicht zu finden. Gesucht in:\n  "
        + "\n  ".join(os.path.abspath(k) for k in kandidaten)
        + "\n\nDieses Skript gehoert auf den HOST - im Proxy-Container"
          " liegen die Plaene nicht.\nAufruf:  cd ~/ki4ki && python3"
          " bau/ablauf_pruefen.py")


PLAENE = _plaene_finden()


def _node_aufruf():
    """node wird gebraucht, um die Knoten-Logik wirklich AUSZUFUEHREN statt
    sie zu lesen. Fehlt es auf dem Host, tut es der n8n-Container - der hat
    per Definition eines."""
    for befehl in (["node"], ["docker", "exec", "-i", "ki4ki-n8n", "node"]):
        try:
            e = subprocess.run(befehl + ["-e", "console.log('da')"],
                               capture_output=True, text=True, timeout=30)
            if e.returncode == 0 and "da" in e.stdout:
                return befehl
        except (OSError, subprocess.SubprocessError):
            continue
    raise SystemExit("Kein node gefunden - weder auf dem Host noch im"
                     " n8n-Container.")


NODE = None
FEHLER = []


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def knoten(datei, name):
    d = json.load(io.open(os.path.join(PLAENE, datei), encoding="utf-8"))
    for k in d["nodes"]:
        if k.get("name") == name:
            return k
    raise SystemExit("Knoten %r in %s nicht gefunden" % (name, datei))


def node_lauf(js):
    global NODE
    if NODE is None:
        NODE = _node_aufruf()
    e = subprocess.run(NODE + ["-e", js], capture_output=True, text=True,
                       timeout=60)
    if e.returncode != 0:
        raise SystemExit("node-Fehler:\n" + (e.stderr or "")[:2000])
    return e.stdout.strip()


# --------------------------------------------------------------------------
def test_nichtdokumente():
    """Der Filter aus 'Nur ein Bereich je Durchgang'."""
    print("Filter fuer Nichtdokumente")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Nur ein Bereich je Durchgang")["parameters"]["jsCode"]
    anfang = quelle.index("const NICHTDOKUMENT")
    ende = quelle.index("const ersterBereich")
    js = quelle[anfang:ende] + """
const faelle = ["._Bericht.pdf", "._Angebot 2024.pdf", ".DS_Store",
                "Thumbs.db", "desktop.ini", ".localized", ".versteckt",
                "Bericht.pdf", "Angebot Nr. 4711", "2024.09.20 Protokoll.pdf",
                "Zeichnung_._Detail.pdf"];
console.log(JSON.stringify(faelle.map(n => [n, NICHTDOKUMENT(n)])));
"""
    ergebnis = dict((n, a) for n, a in json.loads(node_lauf(js)))
    # Was RAUSFLIEGEN muss
    for name, erwartet in (("._Bericht.pdf", "macOS-Metadatei"),
                           ("._Angebot 2024.pdf", "macOS-Metadatei"),
                           (".DS_Store", "Ordner-Merkdatei"),
                           ("Thumbs.db", "Ordner-Merkdatei"),
                           ("desktop.ini", "System-Merkdatei")):
        pruefe(ergebnis.get(name) == erwartet,
               "%-24s wird erkannt als %r (ist %r)"
               % (name, erwartet, ergebnis.get(name)))
    # ⭐ Die Gegenprobe: echte Dokumente duerfen NICHT rausfliegen. Ohne sie
    #    waere ein Filter, der einfach alles wegwirft, ebenso "bestanden".
    for name in ("Bericht.pdf", "Angebot Nr. 4711", "2024.09.20 Protokoll.pdf",
                 "Zeichnung_._Detail.pdf"):
        pruefe(ergebnis.get(name) == "",
               "%-24s bleibt drin (ist %r)" % (name, ergebnis.get(name)))


def test_leere_aussortieren():
    """Die Entscheidung Archiv/Aussortiert aus 'Ablage entscheiden'."""
    print("\nArchiv oder Aussortiert")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Ablage entscheiden")["parameters"]["jsCode"]
    anfang = quelle.index("const MINDESTZEICHEN")
    ende = quelle.index("  const quelle = d.source_path;")
    kern = quelle[anfang:ende]
    # Die Schleife durch eine Funktion ersetzen, die einen Fall entscheidet.
    kern = kern.replace("const abgelegt = dokumente.map((d) => {",
                        "function entscheide(d, gefunden, grund) {")
    js = """
const grund = (s) => String(s)
  .normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '')
  .replace(/\\u00df/g, 'ss')
  .replace(/[^A-Za-z0-9]+/g, '-')
  .replace(/^-+|-+$/g, '')
  .toLowerCase();
""" + kern + """
  return { drin, leer, laenge };
}
const faelle = [
  ["Text da, Name gefunden",      {filename:"Bericht.pdf", text_length:5000}, ["bericht"]],
  ["Text LEER, Name gefunden",    {filename:"Bericht.pdf", text_length:0},    ["bericht"]],
  ["Text 5 Zeichen, Name gef.",   {filename:"Bericht.pdf", text_length:5},    ["bericht"]],
  ["Text 20 Zeichen, Name gef.",  {filename:"Bericht.pdf", text_length:20},   ["bericht"]],
  ["Text da, Name NICHT gefunden",{filename:"Bericht.pdf", text_length:5000}, ["anderes"]],
  ["Text leer, Name nicht gef.",  {filename:"Bericht.pdf", text_length:0},    ["anderes"]],
  ["text_length fehlt ganz",      {filename:"Bericht.pdf"},                   ["bericht"]],
];
console.log(JSON.stringify(faelle.map(([t, d, g]) => [t, entscheide(d, g, grund)])));
"""
    ergebnis = dict((t, e) for t, e in json.loads(node_lauf(js)))

    def ziel(t):
        return "archiv" if ergebnis[t]["drin"] else "aussortiert"

    pruefe(ziel("Text da, Name gefunden") == "archiv",
           "Text da + Name gefunden -> archiv")
    # ⭐ Der eigentliche Fix. Vorher ging genau dieser Fall ins Archiv.
    pruefe(ziel("Text LEER, Name gefunden") == "aussortiert",
           "Text LEER + Name gefunden -> aussortiert  (war vorher archiv)")
    pruefe(ziel("Text 5 Zeichen, Name gef.") == "aussortiert",
           "5 Zeichen -> aussortiert")
    # Gegenprobe zur Schwelle: knapp darueber MUSS durchgehen, sonst waere
    # "alles unter Verdacht" das Ergebnis und die Pruefung wertlos.
    pruefe(ziel("Text 20 Zeichen, Name gef.") == "archiv",
           "20 Zeichen (Mindestmass) -> archiv")
    pruefe(ziel("Text da, Name NICHT gefunden") == "aussortiert",
           "Name nicht gefunden -> aussortiert (unveraendert)")
    pruefe(ziel("text_length fehlt ganz") == "aussortiert",
           "fehlendes Textmass gilt als leer, nicht als in Ordnung")


def test_docling_einstellungen():
    """Schwelle und Massenlauf-Schalter in der Docling-Extraktion."""
    print("\nDocling-Einstellungen")
    k = knoten("2_Dateien-in-JSON-umwandeln.json", "Docling PDF-Extraktion")
    werte = dict((p["name"], str(p.get("value", "")))
                 for p in k["parameters"]["bodyParameters"]["parameters"]
                 if "name" in p)
    pruefe(werte.get("picture_description_area_threshold") == "0.01",
           "Schwelle ist 0.01 (ist %r)"
           % werte.get("picture_description_area_threshold"))
    pd = werte.get("do_picture_description", "")
    pruefe("massenlauf" not in pd,
           "Massenlauf schaltet die Bildbeschreibung NICHT mehr ab")
    pruefe("KI4KI_BILDBESCHREIBUNG" in pd,
           "der Schalter KI4KI_BILDBESCHREIBUNG wirkt weiterhin")
    # Gegenprobe: der Zweitversuch soll unveraendert OHNE Bildbeschreibung
    # laufen - er ist die Rueckfallebene, nicht der Hauptweg.
    k2 = knoten("2_Dateien-in-JSON-umwandeln.json",
                "Docling Zweitversuch (pypdfium2)")
    w2 = dict((p["name"], str(p.get("value", "")))
              for p in k2["parameters"]["bodyParameters"]["parameters"]
              if "name" in p)
    pruefe(w2.get("do_picture_description") == "false",
           "Zweitversuch bleibt ohne Bildbeschreibung")


def test_was_n8n_wirklich_geladen_hat():
    """Die Repo-Datei ist nicht der Betrieb.

    Alle Pruefungen oben lesen die JSON-Dateien im Repo. Dass die stimmen,
    heisst nicht, dass n8n sie auch benutzt - der Import kann scheitern,
    waehrend aktualisiere.sh "eingespielt und aktiviert" meldet.

    ⛔ Und NICHT per grep in database.sqlite nachsehen. Frisch Importiertes
    steht zunaechst im Write-Ahead-Log (database.sqlite-wal) und noch gar
    nicht in der Datenbankdatei. Am 21.09. ergab so ein grep: der eine
    Marker gefunden, der andere nicht - beide aus demselben Commit. Die
    Datenbank war nur nicht auf dem Stand, den sie zu haben schien.
    (Dieselbe Falle wie beim n8n-Dauerneustart am 12.09.)

    Richtig ist, n8n selbst exportieren zu lassen: Das liest die Daten
    ueber die Datenbankschicht, also samt WAL.
    """
    print("\nWas n8n WIRKLICH geladen hat")
    befehl = ["docker", "exec", "ki4ki-n8n", "sh", "-c",
              "rm -rf /tmp/ist; mkdir -p /tmp/ist;"
              " n8n export:workflow --all --separate --output=/tmp/ist"
              " >/dev/null 2>&1; cat /tmp/ist/*.json"]
    try:
        e = subprocess.run(befehl, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as f:
        print("  uebersprungen: n8n nicht erreichbar (%s)" % f.__class__.__name__)
        return
    if e.returncode != 0 or not e.stdout.strip():
        print("  uebersprungen: kein Export moeglich - dieser Teil ist damit"
              " NICHT geprueft")
        return
    geladen = e.stdout

    # Erst die Kontrolle: Findet der Abgleich ueberhaupt etwas? Ohne sie
    # wuerde ein leerer Export als "alles in Ordnung" durchgehen.
    pruefe("VERLUST-WAECHTER" in geladen,
           "Kontrolle: unveraenderter Knoten ist im Export enthalten")
    if "VERLUST-WAECHTER" not in geladen:
        print("  -> Ohne Kontrolle sagen die naechsten Zeilen nichts.")
        return
    pruefe("macOS-Metadatei" in geladen,
           "n8n kennt den Filter fuer Nichtdokumente")
    pruefe("MINDESTZEICHEN" in geladen,
           "n8n kennt die Mindestzeichen-Regel")
    pruefe('"picture_description_area_threshold","value":"0.01"' in
           geladen.replace(", ", ",").replace('" :', '":'),
           "n8n hat die Schwelle 0.01 geladen")


def test_plaene_unversehrt():
    """Die Plaene muessen ladbar und vollstaendig bleiben."""
    print("\nAblaufplaene unversehrt")
    for datei, knotenzahl in (("1_KI4KI-Masse-Ingest.json", 30),
                              ("2_Dateien-in-JSON-umwandeln.json", 20)):
        d = json.load(io.open(os.path.join(PLAENE, datei), encoding="utf-8"))
        pruefe(len(d["nodes"]) == knotenzahl,
               "%s hat %d Knoten (erwartet %d)"
               % (datei, len(d["nodes"]), knotenzahl))
        leer = [k.get("name") for k in d["nodes"]
                if k.get("type", "").endswith(".code")
                and not (k.get("parameters", {}).get("jsCode") or "").strip()]
        pruefe(not leer, "%s: kein Code-Knoten ist leer" % datei)


if __name__ == "__main__":
    test_nichtdokumente()
    test_leere_aussortieren()
    test_docling_einstellungen()
    test_plaene_unversehrt()
    test_was_n8n_wirklich_geladen_hat()
    print("\nGeprueft wurden die Plaene in: %s" % PLAENE)
    print("%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
