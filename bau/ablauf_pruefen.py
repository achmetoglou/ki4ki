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
import re
import subprocess
import sys
import time

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


class NodeFehler(Exception):
    """Ein Ausschnitt lief nicht durch node - ROT, aber kein Abbruch."""


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def ausschnitt(quelle, von, bis, wofuer):
    """Codeblock zwischen zwei Markern - oder eine rote Pruefung.

    ⛔ Vorher stand hier quelle.index(...). Verschiebt jemand die Markerzeile,
      bricht das Skript mit ValueError ab. Ein Absturz ist kein
      Pruefergebnis: Beim Ueberfliegen sieht er aus wie "ging nicht", nicht
      wie "die Pruefung greift nicht mehr".
    """
    a, b = quelle.find(von), quelle.find(bis)
    if a < 0 or b < 0 or b <= a:
        pruefe(False, "Marker fuer %s nicht gefunden (%r / %r) - dieser Teil "
                      "ist NICHT geprueft" % (wofuer, von, bis))
        return None
    return quelle[a:b]


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
        # ⛔ KEIN SystemExit. Ein node-Fehler in EINEM Test hat bis zum
        #   05.10. den ganzen Pruefstand beendet: Ausgangsstand d9d4ff9 starb
        #   im zweiten von dreizehn Tests, die elf dahinter liefen nie - und
        #   der Abbruch sah beim Ueberfliegen aus wie "ging nicht", nicht wie
        #   "wir pruefen seit Wochen nichts mehr". Ein Test, der platzt, wird
        #   ROT gemeldet; die uebrigen laufen weiter.
        raise NodeFehler("node-Fehler:\n" + (e.stderr or "")[:2000])
    return e.stdout.strip()


# --------------------------------------------------------------------------
def test_nichtdokumente():
    """Der Filter aus 'Nur ein Bereich je Durchgang'."""
    print("Filter fuer Nichtdokumente")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Nur ein Bereich je Durchgang")["parameters"]["jsCode"]
    kern = ausschnitt(quelle, "const NICHTDOKUMENT", "const ersterBereich",
                      "Nichtdokumente")
    if kern is None:
        return
    anfang = quelle.index("const NICHTDOKUMENT")
    ende = quelle.index("const ersterBereich")
    js = quelle[anfang:ende] + """
const faelle = ["._Bericht.pdf", "._Angebot 2024.pdf", ".DS_Store",
                "Thumbs.db", "desktop.ini", ".localized", ".versteckt",
                "~$Angebot_275603.docx", "~$Bericht.doc", "~$Folien.pptx",
                "Bericht.pdf", "Angebot Nr. 4711", "2024.09.20 Protokoll.pdf",
                "Zeichnung_._Detail.pdf", "Angebot ~$ Nachtrag.docx",
                "Messreihe=1.docx"];
console.log(JSON.stringify(faelle.map(n => [n, NICHTDOKUMENT(n)])));
"""
    ergebnis = dict((n, a) for n, a in json.loads(node_lauf(js)))
    # Was RAUSFLIEGEN muss
    for name, erwartet in (("._Bericht.pdf", "macOS-Metadatei"),
                           ("._Angebot 2024.pdf", "macOS-Metadatei"),
                           (".DS_Store", "Ordner-Merkdatei"),
                           ("Thumbs.db", "Ordner-Merkdatei"),
                           ("desktop.ini", "System-Merkdatei"),
                           ("~$Angebot_275603.docx", "Office-Sperrdatei"),
                           ("~$Bericht.doc", "Office-Sperrdatei"),
                           ("~$Folien.pptx", "Office-Sperrdatei")):
        pruefe(ergebnis.get(name) == erwartet,
               "%-24s wird erkannt als %r (ist %r)"
               % (name, erwartet, ergebnis.get(name)))
    # ⭐ Die Gegenprobe: echte Dokumente duerfen NICHT rausfliegen. Ohne sie
    #    waere ein Filter, der einfach alles wegwirft, ebenso "bestanden".
    # ⛔ "Angebot ~$ Nachtrag.docx" ist ein echtes Dokument, in dessen NAMEN
    #   die Zeichenfolge vorkommt. Nur der Anfang zaehlt - sonst wirft der
    #   Filter Dokumente weg, die jemand so benannt hat.
    for name in ("Bericht.pdf", "Angebot Nr. 4711", "2024.09.20 Protokoll.pdf",
                 "Zeichnung_._Detail.pdf", "Angebot ~$ Nachtrag.docx",
                 "Messreihe=1.docx"):
        pruefe(ergebnis.get(name) == "",
               "%-24s bleibt drin (ist %r)" % (name, ergebnis.get(name)))


def test_leere_aussortieren():
    """Die Entscheidung Archiv/Aussortiert aus 'Ablage entscheiden'."""
    print("\nArchiv oder Aussortiert")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Ablage entscheiden")["parameters"]["jsCode"]
    kern = ausschnitt(quelle, "const MINDESTZEICHEN",
                      "  const quelle = d.source_path;", "Ablage entscheiden")
    if kern is None:
        return
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
// ⛔ 'dokumente' ENTSTEHT IM BAUSTEIN, VOR dem Ausschnitt: die erste Zeile
//   des Ausschnitts liest daraus die Mindestzeichen. Ohne diese Stellvertretung
//   starb node an "ReferenceError: dokumente is not defined" - und weil
//   node_lauf() dabei SystemExit wirft, brach der GANZE Pruefstand nach dem
//   ersten Test ab. Elf von dreizehn Tests liefen seither nie (nachgestellt
//   05.10., Ausgangsstand d9d4ff9). Ein Pruefstand, der mittendrin abbricht,
//   meldet keine Fehler - er meldet gar nichts.
// ⚠ Der Wert von vorgesehen_liste ist hier reiner Platzhalter: Er steht
//   NUR in der Begruendungs-Zeile, und auf seinen Inhalt prueft hier nichts.
//   Die echte Liste steht an genau einer Stelle im Ablaufplan - das prueft
//   test_positivliste_hat_genau_eine_quelle().
const dokumente = [{ mindestzeichen: 20, vorgesehen_liste: '(Platzhalter)' }];
""" + kern + """
  return { drin, leer, laenge };
}
// Entschieden wird ueber den ABDRUCK, nicht ueber den Namen. Die gemeldeten
// Namen sind so geschrieben, wie der Arbeitsbereich sie zurueckgibt - mit
// umgeformtem Namen drumherum, damit die Pruefung den Teilstring wirklich
// misst und nicht nur einen Gleichheitsvergleich.
const A = "ab12cd34ef";
const gemeldet = ["kap-kundeb-bericht-" + A + "-md"];
const fremd = ["kap-kundea-anderes-zz99zz99zz-md"];
// ⛔ SEIT DEM 24.09. ENTSCHEIDET HIER DIE MARKE, NICHT DIE TEXTLAENGE.
//   "Ablage entscheiden" liest nur noch d.leer; gerechnet wird die Marke im
//   Baustein "Code" (leer = text_length < MINDESTZEICHEN). Die Faelle unten
//   tragen deshalb BEIDES - so, wie "Code" es liefern wuerde. Dass "Code"
//   die Marke wirklich so rechnet, prueft test_leer_marke_kommt_aus_code()
//   und, bis zum Upload durchgerechnet, bau/aufnahmetest.js (Fall 2f).
const mitLeer = (d) => Object.assign({}, d,
  { leer: Number(d.text_length || 0) < 20 });
const faelle = [
  ["Text da, Name gefunden",      mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:5000}), gemeldet],
  ["Text LEER, Name gefunden",    mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:0}),    gemeldet],
  ["Text 5 Zeichen, Name gef.",   mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:5}),    gemeldet],
  ["Text 20 Zeichen, Name gef.",  mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:20}),   gemeldet],
  ["Text da, Name NICHT gefunden",mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:5000}), fremd],
  ["Text leer, Name nicht gef.",  mitLeer({filename:"Bericht.pdf", abdruck:A, text_length:0}),    fremd],
  ["text_length fehlt ganz",      mitLeer({filename:"Bericht.pdf", abdruck:A}),                   gemeldet],
  ["OHNE Abdruck, Name gefunden", mitLeer({filename:"Bericht.pdf", text_length:5000}),            gemeldet],
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
    # ⛔ Ohne Abdruck darf nichts ins Archiv: Ein Dokument ohne Schluessel
    #   ist im Bestand nicht wiederzufinden, gaelte aber als aufgenommen.
    pruefe(ziel("OHNE Abdruck, Name gefunden") == "aussortiert",
           "ohne Abdruck -> aussortiert, nie ins Archiv")
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


_FINDET_JS = r"""
const path = require('path'), cp = require('child_process');
const { createRequire } = require('module');

// --- UNSER Code, woertlich aus dem Ablaufplan herausgeschnitten ---------
__ENTSCHAERFEN__

// --- n8ns Code, aus dem laufenden Container, NICHT nachgebaut -----------
const r = createRequire('/usr/local/lib/node_modules/n8n/package.json');
const pkg = path.dirname(r.resolve('n8n-nodes-base'));
const B = path.join(pkg, 'dist/nodes/Files/ReadWriteFile');
const { normalizeFileSelector } = require(path.join(B, 'helpers/utils.js'));
// fast-glob genau so aufgeloest, wie read.operation.js es tut.
const rr = createRequire(path.join(B, 'actions/read.operation.js'));
const fgm = rr('fast-glob');
const fg = fgm.default || fgm;

// Der Eingang, mit dem Befehl aus dem Plan selbst gelesen - nur Namen.
const roh = cp.execSync(__FINDBEFEHL__, { maxBuffer: 1 << 28 }).toString('utf8');
const pfade = roh.split('\u0000')
                 .map(s => s.replace(/^[\r\n]+|[\r\n]+$/g, ''))
                 .filter(Boolean);

(async () => {
  const messe = async (f) => {
    let ok = 0, leer = 0, leerMitKlammern = 0;
    for (const p of pfade) {
      // GENAU die Kette aus dem Betrieb: unser entschaerfen, dann n8ns
      // normalizeFileSelector, dann fast-glob - async wie read.operation.js.
      const treffer = await fg(normalizeFileSelector(f(p)));
      if (treffer.length > 0) { ok++; }
      else { leer++; if (/[()[\]]/.test(p)) leerMitKlammern++; }
    }
    return { ok: ok, leer: leer, leerMitKlammern: leerMitKlammern };
  };
  const jetzt = await messe(entschaerfen);
  // Eingebaute Gegenprobe: dieselbe Kette, aber ( ) [ ] ein zweites Mal
  // entschaerft - der Zustand vor dem 06.10. Sie MUSS Treffer verlieren,
  // sonst misst diese Pruefung nichts.
  const mutant = await messe((s) => entschaerfen(s).replace(/[()[\]]/g, '\\$&'));
  console.log(JSON.stringify({
    n: pfade.length,
    mitKlammern: pfade.filter(p => /[()[\]]/.test(p)).length,
    jetzt: jetzt, mutant: mutant,
  }));
})().catch(e => { console.error('ABBRUCH ' + e.message); process.exit(3); });
"""


def test_findet_n8n_die_dateien_auch_wirklich():
    """Faehrt die Kette entschaerfen -> normalizeFileSelector -> fast-glob
    im ECHTEN Container ueber die echten Pfade des Eingangs.

    ⛔ WARUM DAS SEIN MUSS - und warum _glob_treffer() es nicht kann.
    _glob_treffer() ist ein Modell. Es kennt nur unser entschaerfen() und
    nimmt an, dass n8n den Dateiwaehler unveraendert an fast-glob gibt.
    Das tut n8n nicht: read.operation.js ruft normalizeFileSelector(), und
    die ruft escapeSpecialCharacters(), die ( ) [ ] NOCH EINMAL mit \\
    versieht. Aus 'Angebot \\(2\\).pdf' wird 'Angebot \\\\(2\\\\).pdf' - in
    picomatch ein literaler Backslash plus Gruppe, also null Treffer. Das
    Modell hat diese doppelte Entschaerfung abgesegnet und haette sie auch
    nach dem Fix abgesegnet; die halb richtige Fassung M4b hat es sogar
    ROT bestraft. Ein Modell kann seinen eigenen blinden Fleck nicht
    sehen - deshalb hier das Original.

    ⚠ UND ES IST VERSIONSABHAENGIG. Faellt escapeSpecialCharacters bei
    einem n8n-Update weg, muessten ( ) [ ] wieder in entschaerfen() hinein.
    Diese Pruefung merkt beides: zu viel entschaerft wie zu wenig
    entschaerft endet in KEIN_TREFFER.

    ⛔ SCHREIBT NICHTS. Kein n8n-Lauf, keine Datei, kein /tmp im Container -
    das Programm kommt ueber stdin herein, der Befehl aus dem Plan liest
    nur Namen.
    """
    print("\nFindet n8n die Dateien des Eingangs auch wirklich")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Dateiliste aufbereiten")["parameters"]["jsCode"]
    m = re.search(r"^const entschaerfen = .*$", quelle, re.M)
    if m is None:
        pruefe(False, "entschaerfen() steht nicht mehr im Plan - diese"
                      " Pruefung weiss nicht mehr, was sie messen soll")
        return
    befehl = knoten("1_KI4KI-Masse-Ingest.json",
                    "Dateiliste einlesen")["parameters"]["command"]
    if befehl.startswith("="):
        pruefe(False, "der find-Befehl ist zu einem Ausdruck geworden -"
                      " diese Pruefung kann ihn nicht mehr fahren")
        return
    js = (_FINDET_JS.replace("__ENTSCHAERFEN__", m.group(0))
                    .replace("__FINDBEFEHL__", json.dumps(befehl)))
    try:
        e = subprocess.run(["docker", "exec", "-i", "ki4ki-n8n", "node"],
                           input=js, capture_output=True, text=True,
                           timeout=600)
    except (OSError, subprocess.SubprocessError) as f:
        print("  uebersprungen: n8n nicht erreichbar (%s)"
              " - DAS IST KEIN GRUEN, der Dateiwaehler ist hier NICHT"
              " geprueft" % f.__class__.__name__)
        return
    if e.returncode != 0 or not e.stdout.strip():
        print("  uebersprungen: im Container nicht lauffaehig (%s)"
              " - DAS IST KEIN GRUEN, der Dateiwaehler ist hier NICHT"
              " geprueft"
              % (e.stderr.strip().splitlines() or ["rc=%d" % e.returncode])[-1][:160])
        return
    z = json.loads(e.stdout.strip().splitlines()[-1])

    # Erst die Kontrolle. Ohne Pfade mit ( ) [ ] im Eingang sagt alles
    # Folgende nichts - dann war der Eingang nur gerade harmlos.
    pruefe(z["n"] > 0, "Kontrolle: der Eingang ist nicht leer (%d Pfade)"
                       % z["n"])
    pruefe(z["mitKlammern"] > 0,
           "Kontrolle: %d der %d Pfade tragen ( ) [ ]"
           % (z["mitKlammern"], z["n"]))
    if not z["n"] or not z["mitKlammern"]:
        print("  -> Ohne Kontrolle sagen die naechsten Zeilen nichts.")
        return
    # Und die Gegenprobe: kann diese Messung ueberhaupt rot werden?
    pruefe(z["mutant"]["leer"] > 0,
           "Gegenprobe: doppelt entschaerft verliert die Messung %d Treffer"
           % z["mutant"]["leer"])

    pruefe(z["jetzt"]["leer"] == 0,
           "n8n findet JEDE der %d Dateien des Eingangs wieder"
           " (ohne Treffer: %d, davon mit Klammern: %d)"
           % (z["n"], z["jetzt"]["leer"], z["jetzt"]["leerMitKlammern"]))


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


def test_bereichserkennung():
    """BUGS_UND_FIXES.md 7.2: 'Nur ein Bereich je Durchgang' las das
    VORLETZTE Pfadsegment. Bei einer Datei in einem Unterordner ergab das
    'Normen' oder 'input' - Dokumente landeten im falschen Arbeitsbereich,
    weil die Ablage der ersten Datei fuer alle galt."""
    print("\nBereichserkennung bei Unterordnern")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Nur ein Bereich je Durchgang")["parameters"]["jsCode"]
    # ⚠ DER AUSSCHNITT BEGINNT BEI 'const angabe', NICHT BEI 'const
    #   bereichVon'. Seit dem 06.10. holt bereichVon seine Angaben ueber
    #   angabe() - stuende der Marker weiter hinten, liefe der Ausschnitt
    #   allein nicht mehr ("ReferenceError: angabe is not defined"), und der
    #   Pruefstand meldete einen Absturz statt eines Ergebnisses. Genau so
    #   ist er am 24.09. elf Tage unbemerkt gestorben.
    kern = ausschnitt(quelle, "const angabe", "const nameVon", "bereichVon")
    if kern is None:
        return
    js = kern + """
const f = (dir) => bereichVon({binary:{data:{directory:dir}}});
console.log(JSON.stringify([
  f('/files/dokumente/kap/input'),
  f('/files/dokumente/kap/input/Normen'),
  f('/files/dokumente/kap/input/Normen/Kleben'),
  f('/files/dokumente/auw/input/Normen')]));
"""
    erg = json.loads(node_lauf(js))
    pruefe(erg == ["kap", "kap", "kap", "auw"],
           "Bereich stimmt auf jeder Ordnertiefe, ist %r" % (erg,))
    # ⭐ UND AUS BEIDEN QUELLEN. Seit dem 06.10. kommt die Dateiliste ohne
    #   Inhalte herein; Name und Ordner stehen dann im json statt in
    #   binary.data. Beide Wege muessen dasselbe ergeben - sonst landen
    #   Dokumente wieder im falschen Arbeitsbereich.
    js2 = kern + """
const f = (item) => bereichVon(item);
console.log(JSON.stringify([
  f({json:{directory:'/files/dokumente/kap/input/Normen'}}),
  f({json:{directory:'/files/dokumente/auw/input'}}),
  // binary gewinnt, wenn es etwas hergibt - die Probe faehrt diesen
  // Baustein auch mit Elementen aus "Daten vom Server laden".
  f({json:{directory:'/files/dokumente/auw/input'},
     binary:{data:{directory:'/files/dokumente/kap/input'}}}),
  // ein leeres binary darf den json-Weg NICHT verstellen
  f({json:{directory:'/files/dokumente/kap/input'}, binary:{data:{}}})]));
"""
    erg2 = json.loads(node_lauf(js2))
    pruefe(erg2 == ["kap", "auw", "kap", "kap"],
           "Bereich kommt aus json ODER binary, ist %r" % (erg2,))
    # ⛔ Gegenprobe: Die ALTE Zeile muss an denselben Faellen scheitern -
    #   sonst prueft das hier nichts.
    alt = """
const bereichVon = (item) => {
  const b = (item.binary && item.binary.data) || {};
  const teile = String(b.directory || '').split('/').filter(Boolean);
  return teile[teile.length - 2] || '';
};
const f = (dir) => bereichVon({binary:{data:{directory:dir}}});
console.log(JSON.stringify([
  f('/files/dokumente/kap/input'),
  f('/files/dokumente/kap/input/Normen')]));
"""
    alt_erg = json.loads(node_lauf(alt))
    pruefe(alt_erg != ["kap", "kap"],
           "Gegenprobe: die alte Zeile liefert %r statt ['kap','kap'] - die "
           "Pruefung trifft die Fehlerklasse" % (alt_erg,))


def test_leer_marke_kommt_aus_code():
    """Die Marken entstehen im Baustein 'Code' - und die Liste steht NICHT dort.

    ⛔ Seit dem 24.09. rechnet "Code" leer/korrespondenz/nicht_vorgesehen und
      haengt sie an jedes Dokument; "Ablage entscheiden" liest sie nur noch ab.
      Geprueft hat das bis zum 05.10. nichts.

    ⭐ Zugleich die Gegenprobe gegen die DOPPELTE WAHRHEIT: Die Positivliste
      wird hier als Stellvertreter hereingereicht (nur pdf/docx/txt). Baut
      "Code" sich seine eigene Liste, faellt das hier auf - 'Werte.csv' waere
      dann vorgesehen, obwohl es in der hereingereichten Liste nicht steht.
    """
    print("\nMarken entstehen in 'Code' (und die Liste kommt von aussen)")
    quelle = knoten("1_KI4KI-Masse-Ingest.json", "Code")["parameters"]["jsCode"]
    kern = ausschnitt(quelle, "const MINDESTZEICHEN = 20;", "return _ausgabe;",
                      "Marken in Code")
    if kern is None:
        return
    js = """
// Die Listen kommen aus dem Baustein, der sie BESITZT. Hier steht bewusst
// eine kurze Stellvertreter-Liste: csv fehlt darin absichtlich.
const _stellvertreter = { vorgesehen: ['pdf', 'docx', 'txt'],
                          korrespondenz_formate: ['msg', 'eml'] };
const $ = (n) => ({ first: () => ({ json: _stellvertreter }) });
const _ausgabe = [
  {json:{filename:'Bericht.pdf',  text_length:5000, nur_beleg:false}},
  {json:{filename:'Leer.pdf',     text_length:0,    nur_beleg:false}},
  {json:{filename:'Kurz.pdf',     text_length:5,    nur_beleg:false}},
  {json:{filename:'Knapp.pdf',    text_length:20,   nur_beleg:false}},
  {json:{filename:'Foto.jpg',     text_length:5000, nur_beleg:false}},
  {json:{filename:'Post.msg',     text_length:5000, nur_beleg:false}},
  {json:{filename:'Werte.csv',    text_length:5000, nur_beleg:false}},
  {json:{filename:'Beleg.pdf',    text_length:5000, nur_beleg:true}},
];
""" + kern + """
console.log(JSON.stringify(_ausgabe.map(e => [e.json.filename, {
  leer: e.json.leer, korrespondenz: e.json.korrespondenz,
  nicht_vorgesehen: e.json.nicht_vorgesehen, hochladen: e.json.hochladen,
  endung: e.json.endung }])));
"""
    erg = dict((n, m) for n, m in json.loads(node_lauf(js)))
    pruefe(erg["Leer.pdf"]["leer"] is True, "0 Zeichen gilt als leer")
    pruefe(erg["Kurz.pdf"]["leer"] is True, "5 Zeichen gilt als leer")
    # Gegenprobe zur Schwelle - sonst waere "alles ist leer" ebenso gruen.
    pruefe(erg["Knapp.pdf"]["leer"] is False, "20 Zeichen gilt NICHT als leer")
    pruefe(erg["Bericht.pdf"]["hochladen"] is True,
           "ein lesbares PDF wird hochgeladen")
    pruefe(erg["Leer.pdf"]["hochladen"] is False, "ein leeres nicht")
    pruefe(erg["Foto.jpg"]["nicht_vorgesehen"] is True
           and erg["Foto.jpg"]["hochladen"] is False,
           "jpg ist nicht vorgesehen und wird nicht hochgeladen")
    pruefe(erg["Post.msg"]["korrespondenz"] is True
           and erg["Post.msg"]["nicht_vorgesehen"] is False,
           "msg ist Korrespondenz, nicht 'unvorgesehenes Format'")
    pruefe(erg["Beleg.pdf"]["hochladen"] is False,
           "die Belegquelle wird nicht hochgeladen")
    # ⛔ DIE EIGENTLICHE FRAGE: Liest 'Code' die Liste, oder fuehrt er eine
    #   zweite? Steht csv noch in einer eigenen Liste im Baustein, ist das
    #   hier gruen-falsch.
    pruefe(erg["Werte.csv"]["nicht_vorgesehen"] is True,
           "'Code' benutzt die hereingereichte Liste - er fuehrt keine eigene")


def test_positivliste():
    """'Ablage entscheiden' liest die Marken und nennt den WAHREN Grund.

    ⛔ Dieser Test schickte bis zum 05.10. Faelle OHNE Marken hinein (nur
      filename + text_length) und pruefte damit eine Entscheidung, die der
      Baustein seit dem 24.09. gar nicht mehr trifft. Aufgefallen ist es
      nicht, weil er schon vorher an "dokumente is not defined" starb.
    """
    print("\nOrt und Begruendung aus den Marken")
    quelle = knoten("1_KI4KI-Masse-Ingest.json",
                    "Ablage entscheiden")["parameters"]["jsCode"]
    # Bis HINTER die Begruendung schneiden - sie ist der halbe Befund.
    kern = ausschnitt(quelle, "const MINDESTZEICHEN",
                      "  const zeile =", "Positivliste")
    if kern is None:
        return
    kern = kern.replace("const abgelegt = dokumente.map((d) => {",
                        "function entscheide(d, gefunden, grund) {")
    js = """
const grund = (s) => String(s).toLowerCase();
const dokumente = [{ mindestzeichen: 20, vorgesehen_liste: 'pdf, docx, txt' }];
""" + kern + """
  return { drin, grund: begruendung };
}
const A = "ab12cd34ef";
const G = ["kap-kundeb-bericht-" + A + "-md"];
// Die Marken, wie "Code" sie setzt. Hier wird NICHT noch einmal entschieden,
// was ein vorgesehenes Format ist - das waere die zweite Wahrheit.
const faelle = [
  ["in Ordnung",       {}],
  ["nicht vorgesehen", {nicht_vorgesehen:true}],
  ["Korrespondenz",    {korrespondenz:true}],
  ["ohne Text",        {leer:true}],
];
console.log(JSON.stringify(faelle.map(([t, m]) =>
  [t, entscheide(Object.assign({filename:"X", endung:"pdf", abdruck:A,
                                text_length:5000}, m), G, grund)])));
"""
    erg = dict((k, e) for k, e in json.loads(node_lauf(js)))
    pruefe(erg["in Ordnung"]["drin"] is True,
           "ohne Marke geht das Dokument ins Archiv")
    pruefe(erg["nicht vorgesehen"]["drin"] is False
           and "nicht vorgesehen" in erg["nicht vorgesehen"]["grund"],
           "Marke nicht_vorgesehen -> aussortiert, mit dem WAHREN Grund")
    pruefe(erg["Korrespondenz"]["drin"] is False
           and "Korrespondenz" in erg["Korrespondenz"]["grund"],
           "Korrespondenz bekommt eine EIGENE Begruendung, keinen Formatfehler")
    pruefe(erg["ohne Text"]["drin"] is False
           and "kein Text gewonnen" in erg["ohne Text"]["grund"],
           "Marke leer -> aussortiert, mit dem Grund 'kein Text gewonnen'")
    # ⛔ Die Gegenprobe, ohne die alles oben nichts sagt: Der Baustein darf
    #   nicht einfach ALLES abweisen - sonst bliebe der Bestand leer, und
    #   keine einzige Zeile hier wuerde rot.
    pruefe(any(e["drin"] for e in erg.values()),
           "Gegenprobe: mindestens ein Fall kommt ueberhaupt ins Archiv")
    # Und die Liste im Text kommt aus dem Dokument, nicht aus diesem Baustein.
    pruefe("pdf, docx, txt" in erg["nicht vorgesehen"]["grund"],
           "die genannte Liste stammt aus vorgesehen_liste, nicht aus "
           "'Ablage entscheiden'")


# --------------------------------------------------------------------------
# Die Positivliste VOR der Sperre (Befund 05.10.)
# --------------------------------------------------------------------------
def _ingest_js():
    return knoten("1_KI4KI-Masse-Ingest.json",
                  "Nur ein Bereich je Durchgang")["parameters"]["jsCode"]


def test_positivliste_hat_genau_eine_quelle():
    """Die Liste der vorgesehenen Endungen darf es nur EINMAL geben.

    ⛔ Der Ablaufplan warnt an zwei Stellen selbst davor, dieselbe Liste
      doppelt zu fuehren ("sonst laufen sie wieder auseinander"). Seit die
      Liste auch VOR der Sperre gebraucht wird, ist die Versuchung, sie
      einfach nachzubauen, am groessten - also wird hier gezaehlt.
    """
    print("\nDie Positivliste steht an genau einer Stelle")
    roh = io.open(os.path.join(PLAENE, "1_KI4KI-Masse-Ingest.json"),
                  encoding="utf-8").read()
    # ⚠ NICHT 'odp' oder 'htm' zaehlen: Die stehen zu Recht auch in
    #   OFFICE_ORIGINAL (Belegquellen-Paarung) und in "Dateien
    #   klassifizieren" (Weichenstellung) - andere Listen, anderer Zweck.
    #   Gezaehlt wird die Signatur DIESER Liste und eine Endung, die es nur
    #   in ihr gibt.
    for stueck in ("'xlsm'", "'pdf', 'doc', 'docx', 'odt', 'rtf'"):
        pruefe(roh.count(stueck) == 1,
               "%s steht genau einmal im ganzen Plan (ist: %d)"
               % (stueck, roh.count(stueck)))
    besitzer = _ingest_js()
    pruefe("const VORGESEHEN" in besitzer,
           "die Liste steht im Baustein 'Nur ein Bereich je Durchgang' - "
           "demselben, der auch den Wegraeum-Befehl baut")
    nutzer = knoten("1_KI4KI-Masse-Ingest.json", "Code")["parameters"]["jsCode"]
    pruefe("$('Nur ein Bereich je Durchgang')" in nutzer,
           "'Code' LIEST sie von dort, statt sie nachzubauen")


def test_positivliste_vor_der_sperre():
    """Unvorgesehene Endungen muessen VOR der Sperre erkannt werden.

    ⛔ Gemessen an der echten Dateiliste: 85 von 247 Chargen enthalten kein
      einziges hochladbares Dokument (die erste schon als Nr. 3). Eine solche
      Charge laesst "Nur Dokumente hochladen" leer; die Schleife laeuft nicht
      an, "Sperre freigeben" wird nie erreicht - die Sperre bleibt bis zum
      120-Minuten-Notnagel liegen, und danach wiederholt sich dieselbe Charge.

    ⚠ Geprueft wird GENAU der Ausschnitt, den auch
      bau/nichtdokumente_wegraeumen.py allein mit node faehrt.
    """
    print("\nUnvorgesehene Endungen schon im Filter")
    quelle = _ingest_js()
    kern = ausschnitt(quelle, "const NICHTDOKUMENT", "const ersterBereich",
                      "Positivliste vor der Sperre")
    if kern is None:
        return
    js = kern + """
const faelle = ["Bericht.pdf", "Angebot.docx", "Folien.pptx", "Werte.xlsm",
                "Praesentation.odp", "Liste.txt", "Werte.csv", "Notiz.md",
                "Seite.htm", "Foto.jpg", "Foto.jpeg", "Mikroskop.tif",
                "Teil.001", "Messung.tra", "Anbau.tsx", "Schluessel.asc",
                "LIESMICH", "Post.msg", "Post.eml", "Thumbs.db"];
console.log(JSON.stringify(faelle.map(n => [n, NICHT_VORGESEHEN(n)])));
"""
    erg = dict((n, g) for n, g in json.loads(node_lauf(js)))
    # 1. Was raus muss, bevor die Sperre faellt.
    for name in ("Foto.jpg", "Foto.jpeg", "Mikroskop.tif", "Teil.001",
                 "Messung.tra", "Anbau.tsx", "Schluessel.asc", "LIESMICH"):
        pruefe(bool(erg.get(name)),
               "%-18s wird als unvorgesehenes Format erkannt (ist %r)"
               % (name, erg.get(name)))
    pruefe("jpg" in str(erg.get("Foto.jpg", "")),
           "und der Grund nennt die Endung")
    # 2. ⛔ DIE GEGENPROBE (C2): Wer die Liste zu scharf zieht, raeumt den
    #    Bestand weg. Vorgesehene Formate muessen hier LEER bleiben.
    for name in ("Bericht.pdf", "Angebot.docx", "Folien.pptx", "Werte.xlsm",
                 "Praesentation.odp", "Liste.txt", "Werte.csv", "Notiz.md",
                 "Seite.htm"):
        pruefe(erg.get(name) == "",
               "%-18s bleibt drin (ist %r)" % (name, erg.get(name)))
    # 3. Korrespondenz ist KEIN unvorgesehenes Format - sie hat ihre eigene,
    #    bewusst vertagte Behandlung und ihre eigene Begruendung.
    for name in ("Post.msg", "Post.eml"):
        pruefe(erg.get(name) == "",
               "%-18s zaehlt nicht als unvorgesehenes Format" % name)


def test_aufraeumbefehl_bleibt_unter_der_befehlsgrenze():
    """Der Wegraeum-Befehl darf die Befehlszeile nicht sprengen.

    ⛔ "Sperre setzen" ist ein executeCommand-Baustein: n8n gibt den ganzen
      Text als EIN Argument an `sh -c`. Ein einzelnes Argument darf unter
      Linux hoechstens MAX_ARG_STRLEN (32 Seiten = 131.072 Byte) gross sein -
      darueber scheitert schon das Starten mit E2BIG.

    ⛔ Gerechnet am Bestand: Die Begruendungszeile je Datei ist rund 600
      Zeichen lang. Mit der alten Obergrenze von 200 Dateien je Durchgang
      waeren das ueber 150.000 Zeichen - der Baustein kaeme gar nicht mehr
      zum Laufen, und zwar JEDE Minute neu. Allein die 151 versteckten
      Dateien im Bestand reichen dafuer aus.

    ⛔ UND ZWEIMAL, MIT UND OHNE ASCII (05.10.). Diese Pruefung mass zwar
      schon Byte, fuetterte aber nur ASCII - damit war sie gruen-falsch:
      Der Baustein zaehlte sein Budget in `b.length`, und das sind
      UTF-16-ZEICHEN. MAX_ARG_STRLEN zaehlt BYTE. Ein CJK-Zeichen ist
      3 Byte, ein Umlaut 2. Mit chinesischen Dateinamen gemessen:
      56.121 Zeichen = 153.681 Byte - E2BIG, genau der Fehler, den der
      Baustein verhindern soll, eine Tuer weiter.
    """
    print("\nDer Wegraeum-Befehl passt in eine Befehlszeile")
    js = _ingest_js().replace("__STAND__", "pruefstand")

    def _messen(eingang):
        # Der Baustein wird gefahren wie in bau/aufnahmetest.js: als Funktion
        # mit untergeschobenem $input/$/$now/console - nicht per Textsuche.
        probe = """
const EINGANG = %s;
const JS = %s;
const alle = EINGANG.map(e => ({ json: {},
  binary: { data: { directory: e.dir, fileName: e.name } } }));
const f = new Function('$input', '$', '$now', 'console',
  '"use strict"; return (async () => {\\n' + JS + '\\n})();');
f({ all: () => alle },
  (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
  { toFormat: () => '2026-10-05 08:00:00' },
  { log() {}, error() {} }).then(r => {
    const b = (r[0] && r[0].json && r[0].json.aufraeumen) || '';
    const teile = b ? b.split(' ; ') : [];
    console.log(JSON.stringify({ laenge: Buffer.byteLength(b, 'utf8'),
                                 zeichen: b.length,
                                 groesster: teile.reduce(
                                   (m, t) => Math.max(m, Buffer.byteLength(t, 'utf8')), 0),
                                 befehle: teile.length }));
  });
""" % (json.dumps(eingang), json.dumps(js))
        return json.loads(node_lauf(probe))

    # Das Budget steht im Baustein. Es wird hier HERAUSGELESEN, nicht
    # nachgebaut - sonst prueft dieser Test zwei Zahlen gegeneinander, die
    # auseinanderlaufen koennen.
    m = re.search(r"const HOECHSTENS_\w+ = (\d+);", js)
    if not m:
        pruefe(False, "das Byte-Budget steht nicht mehr als 'const HOECHSTENS_... = <Zahl>;'"
                      " im Baustein - diese Pruefung misst dann nichts")
        return
    grenze = int(m.group(1))

    eingang = []
    for i in range(400):
        eingang.append({"dir": "/files/dokumente/kap/input/Kunde%03d" % i,
                        "name": "Thumbs.db"})
        eingang.append({"dir": "/files/dokumente/kap/input/Kunde%03d" % i,
                        "name": "Bild_%03d.jpg" % i})
    # ⛔ Und dieselbe Menge mit Nicht-ASCII-Namen. Im Bestand liegen Dateien
    #   von Zulieferern; ein Ordner "検査報告書" ist nichts Ausgefallenes.
    cjk = []
    for i in range(400):
        cjk.append({"dir": u"/files/dokumente/kap/input/検査報告"
                           u"書-プロジェクト%03d" % i,
                    "name": u"超音波検査報告書"
                            u"・測定データ%03d.jpg" % i})
    for kennung, eing in (("ASCII", eingang), ("CJK", cjk)):
        try:
            erg = _messen(eing)
        except NodeFehler as f:
            pruefe(False, "%s: der Baustein lief nicht: %s" % (kennung, str(f)[:200]))
            continue
        pruefe(erg["befehle"] > 0,
               "%s Kontrolle: es entsteht ueberhaupt ein Wegraeum-Befehl (%d Befehle)"
               % (kennung, erg["befehle"]))
        # 131.072 ist die harte Grenze; der Rest des Bausteins braucht auch Platz.
        pruefe(erg["laenge"] <= 100000,
               "%s 800 Dateien ergeben hoechstens 100.000 BYTE Befehl "
               "(ist: %d Byte aus %d Zeichen)"
               % (kennung, erg["laenge"], erg["zeichen"]))
        # ⛔ UND DAS BUDGET SELBST IN BYTE. Zaehlt der Baustein Zeichen
        #   (b.length sind UTF-16-Zeichen), haelt er seine eigene Zusage bei
        #   Nicht-ASCII nicht ein - und gegen MAX_ARG_STRLEN zaehlen Byte.
        #   "Mindestens einer geht immer durch" erlaubt genau EINEN
        #   Ueberhang, deshalb der groesste Einzelbefehl als Zugabe.
        pruefe(erg["laenge"] <= grenze + erg["groesster"] + 3,
               "%s das Budget von %d gilt in BYTE (ist: %d Byte, erlaubt %d; "
               "%d Zeichen)"
               % (kennung, grenze, erg["laenge"],
                  grenze + erg["groesster"] + 3, erg["zeichen"]))


# --------------------------------------------------------------------------
# "Sperre setzen" wirklich ausfuehren - mit echtem find in einem Probebaum
# --------------------------------------------------------------------------
def _sperre_block():
    """Claim-Garantie, Leerlauf-Wache und Sperre - der ausfuehrbare Teil."""
    cmd = knoten("1_KI4KI-Masse-Ingest.json",
                 "Sperre setzen")["parameters"]["command"]
    return ausschnitt(cmd, "# Claim-Garantie:", "# Massenlauf-Automatik:",
                      "Sperre setzen")


def _sperre_fahren(block, dateien, umgebung=None, cmin_weg=False,
                   sperre_alter=None):
    """Den Block in einem Probebaum fahren - mit echtem find.

    ⭐ `find` wird dabei durch einen Mitschreiber ersetzt, der jedes Argument
      protokolliert und danach das ECHTE find aufruft. Nur so laesst sich
      beantworten, WELCHE Schwelle wirklich bei find ankommt - der ctime
      einer Datei laesst sich nicht zurueckdatieren, ein echter 180-Minuten-
      Fall also nicht herstellen.

    ⭐ sperre_alter (Minuten): legt .lauf.sperre VOR dem Lauf an und datiert
      sie zurueck. Der Notnagel fragt nach -mmin, und mtime laesst sich -
      anders als ctime - mit utime setzen; ein echter 120-Minuten-Fall ist
      damit herstellbar.
    ⭐ Ein Eintrag in `dateien`, der auf "/" endet, wird ein LEERER Ordner.
      Nur so entsteht ein Eingang, den es gibt und in dem nichts liegt.
    """
    import shutil
    import tempfile
    echt = shutil.which("find")
    if not echt:
        pruefe(False, "kein find vorhanden - dieser Teil ist NICHT geprueft")
        return None
    wurzel = tempfile.mkdtemp(prefix="ki4ki-sperre-")
    try:
        os.makedirs(os.path.join(wurzel, "json"))
        os.makedirs(os.path.join(wurzel, "bin"))
        for rel in dateien:
            p = os.path.join(wurzel, "dokumente", rel)
            if rel.endswith("/"):
                if not os.path.isdir(p):
                    os.makedirs(p)
                continue
            if not os.path.isdir(os.path.dirname(p)):
                os.makedirs(os.path.dirname(p))
            io.open(p, "w", encoding="utf-8").write(u"x")
        if sperre_alter is not None:
            alt = os.path.join(wurzel, "json", ".lauf.sperre")
            os.makedirs(alt)
            frueher = time.time() - sperre_alter * 60
            os.utime(alt, (frueher, frueher))
        mit = os.path.join(wurzel, "find.mitschrift")
        stub = os.path.join(wurzel, "bin", "find")
        io.open(stub, "w", encoding="utf-8").write(u"""#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
with open(os.environ["MITSCHRIFT"], "a") as f:
    for a in args:
        f.write(a + "\\n")
    f.write("--\\n")
if os.environ.get("CMIN_WEG") == "1":
    raus, i = [], 0
    while i < len(args):
        if args[i] == "-cmin":
            i += 2
            continue
        raus.append(args[i])
        i += 1
    args = raus
os.execv(%s, [%s] + args)
""" % (json.dumps(echt), json.dumps(echt)))
        os.chmod(stub, 0o755)
        skript = (block.replace("/files/dokumente",
                                os.path.join(wurzel, "dokumente"))
                       .replace("/files/json", os.path.join(wurzel, "json")))
        env = dict(os.environ)
        env["PATH"] = os.path.join(wurzel, "bin") + os.pathsep + env["PATH"]
        env["MITSCHRIFT"] = mit
        env["CMIN_WEG"] = "1" if cmin_weg else "0"
        for k in ("KI4KI_CLAIM_MINUTEN",):
            env.pop(k, None)
        env.update(umgebung or {})
        e = subprocess.run(["sh", "-c", skript], env=env, cwd=wurzel,
                           capture_output=True, text=True, timeout=120)
        argumente = []
        if os.path.exists(mit):
            argumente = io.open(mit, encoding="utf-8").read().splitlines()
        uebrig, protokoll = [], ""
        for ordner, _, dn in os.walk(os.path.join(wurzel, "dokumente")):
            for d in dn:
                voll = os.path.join(ordner, d)
                uebrig.append(os.path.relpath(voll,
                                              os.path.join(wurzel,
                                                           "dokumente")))
                if d.endswith(".log"):
                    protokoll += io.open(voll, encoding="utf-8").read()
        return {"stdout": e.stdout, "stderr": e.stderr, "code": e.returncode,
                "args": argumente, "dateien": sorted(uebrig),
                "protokoll": protokoll,
                "sperre": os.path.isdir(os.path.join(wurzel, "json",
                                                     ".lauf.sperre"))}
    finally:
        shutil.rmtree(wurzel, ignore_errors=True)


def _cmin_werte(args):
    """Welche Schwellen sind bei find angekommen?"""
    return [args[i + 1] for i, a in enumerate(args)
            if a == "-cmin" and i + 1 < len(args)]


def test_claim_schwelle_aus_der_umgebung():
    """Die Claim-Schwelle muss einstellbar sein - und Unsinn abfangen.

    ⛔ 180 Minuten sind fuer einen Massenlauf rechnerisch unhaltbar: Bei
      hoechstens 25 Dateien je Durchgang und einem Durchgang je Minute
      braucht ein Eingang von 6.151 Dateien mindestens 247 Minuten; gemessen
      wurden 34-49 Dokumente je Stunde. Nach drei Stunden sind rund 100-150
      Dateien durch - die uebrigen rund 6.000 haben nahezu denselben ctime
      und wandern in EINEM Rutsch nach aussortiert/.

    ⛔ Und ein unsinniger Wert darf die Sperre nicht zerstoeren: Unquotiert
      wuerde `-cmin +$WERT` bei "abc" einen find-Syntaxfehler ergeben und bei
      "180 -delete" ein zusaetzliches Argument einschleusen.
    """
    print("\nClaim-Schwelle kommt aus der Umgebung")
    block = _sperre_block()
    if block is None:
        return
    eingang = ["kap/input/Bericht.pdf"]

    ohne = _sperre_fahren(block, eingang)
    if ohne is None:
        return
    pruefe(_cmin_werte(ohne["args"])[:1] == ["+180"],
           "ohne Variable bleibt es bei +180 (ist: %r)"
           % (_cmin_werte(ohne["args"])[:1],))
    pruefe(ohne["sperre"] is True and "Sperre gesetzt." in ohne["stdout"],
           "und die Sperre wird gesetzt")

    hoch = _sperre_fahren(block, eingang, {"KI4KI_CLAIM_MINUTEN": "2880"})
    pruefe(_cmin_werte(hoch["args"])[:1] == ["+2880"],
           "KI4KI_CLAIM_MINUTEN=2880 kommt bei find an (ist: %r)"
           % (_cmin_werte(hoch["args"])[:1],))
    pruefe(hoch["sperre"] is True, "und die Sperre wird weiterhin gesetzt")

    # ⚠ DIE OBERGRENZE, gemessen statt behauptet. Sieben Stellen gehen
    #   durch (9.999.999 Minuten = 19 Jahre), ab acht faellt der Wert auf
    #   180 zurueck - leise, die Warnung steht nur in der n8n-Ausgabe. Wer
    #   "10000000" tippt, um die Garantie abzuschalten, bekommt also das
    #   Gegenteil. Deshalb hier beide Seiten der Grenze; die Doku nennt sie
    #   (test_claim_minuten_ist_durchgereicht prueft das).
    hoechst = _sperre_fahren(block, eingang, {"KI4KI_CLAIM_MINUTEN": "9999999"})
    pruefe(_cmin_werte(hoechst["args"])[:1] == ["+9999999"],
           "sieben Stellen (9999999 = 19 Jahre) kommen bei find an (ist: %r)"
           % (_cmin_werte(hoechst["args"])[:1],))

    # ⛔ Unsinn: leer, Buchstaben, Null, und der Einschleus-Versuch.
    for wert, was in (("", "leer"), ("abc", "Buchstaben"), ("0", "Null"),
                      ("180 -delete", "eingeschleustes Argument"),
                      ("-5", "negativ"), ("10000000", "acht Stellen")):
        e = _sperre_fahren(block, eingang, {"KI4KI_CLAIM_MINUTEN": wert})
        pruefe(_cmin_werte(e["args"])[:1] == ["+180"],
               "%-24s faellt auf 180 zurueck (ist: %r)"
               % (was, _cmin_werte(e["args"])[:1]))
        pruefe("-delete" not in e["args"],
               "%-24s schleust kein zweites Argument ein" % was)
        pruefe(e["sperre"] is True,
               "%-24s zerstoert die Sperre nicht" % was)
        pruefe(e["dateien"] == ["kap/input/Bericht.pdf"],
               "%-24s raeumt nichts weg (uebrig: %r)" % (was, e["dateien"]))


def _umgebung_des_dienstes(compose, dienst):
    """Die environment-Zeilen EINES Dienstes aus der Compose-Datei.

    ⛔ Nicht einfach im ganzen Text suchen: Eine Variable, die beim
      falschen Dienst steht, erreicht n8n nie - und der Ablaufplan laeuft
      dann still mit der Vorgabe weiter.
    """
    zeilen, aktuell, raus = compose.splitlines(), None, []
    for z in zeilen:
        if z[:2] == "  " and z[2:3] not in (" ", "#", "") and z.rstrip().endswith(":"):
            aktuell = z.strip().rstrip(":")
        if aktuell == dienst:
            t = z.strip()
            if t.startswith("- ") and "=" in t:
                raus.append(t[2:])
    return raus


def test_claim_minuten_ist_durchgereicht():
    """Die Schwelle nuetzt nur, wenn sie im Container ankommt.

    ⛔ Ein Schalter, den der Ablaufplan liest, den die Compose aber nicht
      weitergibt, ist schlimmer als keiner: Man setzt ihn in der .env, hakt
      ihn ab und laeuft trotzdem in die 180 Minuten.
    """
    print("\nKI4KI_CLAIM_MINUTEN kommt im Container an")
    wurzel = os.path.dirname(PLAENE)
    pfad = os.path.join(wurzel, "docker-compose.yml")
    if not os.path.exists(pfad):
        pruefe(False, "docker-compose.yml fehlt - NICHT geprueft")
        return
    umgebung = _umgebung_des_dienstes(io.open(pfad, encoding="utf-8").read(),
                                      "n8n")
    # Kontrolle: Findet der Leser ueberhaupt etwas? Sonst sagt alles weitere
    # nichts - eine leere Liste waere gegen jede Behauptung "gruen".
    pruefe("KI4KI_MENGE_JE_LAUF=${KI4KI_MENGE_JE_LAUF:-25}" in umgebung,
           "Kontrolle: die bekannten Schalter stehen beim Dienst n8n (%d "
           "Eintraege gelesen)" % len(umgebung))
    pruefe("KI4KI_CLAIM_MINUTEN=${KI4KI_CLAIM_MINUTEN:-180}" in umgebung,
           "KI4KI_CLAIM_MINUTEN wird genauso weitergereicht wie "
           "KI4KI_MASSENLAUF_AB und KI4KI_MENGE_JE_LAUF")
    cmd = knoten("1_KI4KI-Masse-Ingest.json",
                 "Sperre setzen")["parameters"]["command"]
    pruefe("${KI4KI_CLAIM_MINUTEN:-180}" in cmd,
           "und der Ablaufplan liest genau diesen Namen, mit derselben "
           "Vorgabe 180")
    for datei, was in ((".env.beispiel", "die .env-Vorlage"),
                       (os.path.join("doku", "BETRIEB.md"), "die Doku")):
        p = os.path.join(wurzel, datei)
        t = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        pruefe("KI4KI_CLAIM_MINUTEN" in t, "%s nennt den Schalter" % was)
        # ⛔ UND DIE OBERGRENZE. Ein Wert mit acht oder mehr Stellen faellt
        #   still auf 180 zurueck (die Warnung geht nur in die n8n-Ausgabe,
        #   die im Urlaub niemand liest). Wer die Garantie abschalten will
        #   und "10000000" tippt, bekommt das Gegenteil des Gewollten -
        #   also muss die Zahl dort stehen, wo man sie setzt.
        pruefe("9999999" in t,
               "%s nennt den hoechsten gueltigen Wert 9999999 (sieben "
               "Stellen) - sonst faellt ein groesserer still auf 180" % was)
    doku = io.open(os.path.join(wurzel, "doku", "BETRIEB.md"),
                   encoding="utf-8").read()
    pruefe("Massenlauf" in doku.split("KI4KI_CLAIM_MINUTEN")[1][:2000],
           "und die Doku sagt, WARUM man ihn fuer einen Massenlauf hochsetzt")


def test_claim_garantie_raeumt_wirklich():
    """Gegenprobe: Greift die Schwelle, wird auch wirklich aussortiert.

    ⛔ Ohne diese Probe waere die Pruefung oben auch dann gruen, wenn die
      Claim-Garantie gar nichts mehr taete - der ctime einer frischen Datei
      ist nie ueber 180 Minuten alt. Hier faellt deshalb die Schwelle weg,
      und es wird geprueft, WOHIN die Datei dann geht.
    """
    print("\nGegenprobe: die Claim-Garantie raeumt wirklich auf")
    block = _sperre_block()
    if block is None:
        return
    e = _sperre_fahren(block, ["kap/input/Kunde/Alt.pdf",
                               "kap/input/.DS_Store"], cmin_weg=True)
    if e is None:
        return
    pruefe("kap/aussortiert/Kunde/Alt.pdf" in e["dateien"],
           "die liegengebliebene Datei landet in aussortiert/, "
           "mit Unterordner (ist: %r)" % e["dateien"])
    pruefe("kap/aussortiert/claim.log" in e["dateien"],
           "und der Grund steht im claim.log")
    pruefe("lag laenger als 180 Minuten" in e["protokoll"],
           "das claim.log nennt die Vorgabe-Schwelle (ist: %r)"
           % e["protokoll"].strip()[:160])
    # ⛔ Und bei einer gesetzten Schwelle nennt es DIESE - sonst stuende im
    #   Protokoll eine Zahl, nach der niemand gehandelt hat. Der Wert muss
    #   dafuer in das Kind-sh des -exec durchgereicht werden (export).
    gesetzt = _sperre_fahren(block, ["kap/input/Alt.pdf"],
                             {"KI4KI_CLAIM_MINUTEN": "4320"}, cmin_weg=True)
    pruefe("lag laenger als 4320 Minuten" in gesetzt["protokoll"],
           "und bei gesetzter Schwelle DIESE (ist: %r)"
           % gesetzt["protokoll"].strip()[:160])
    pruefe("kap/input/Kunde/Alt.pdf" not in e["dateien"],
           "sie liegt nicht mehr im Eingang")
    # ⛔ Gegenprobe zur Gegenprobe: versteckte Dateien fasst die
    #   Claim-Garantie NICHT an - sonst liefe sie der Leerlauf-Wache davon.
    pruefe("kap/input/.DS_Store" in e["dateien"],
           "versteckte Dateien laesst sie liegen")


def test_leerlauf_wache_uebersieht_versteckte():
    """Die Leerlauf-Wache muss dieselben Dateien sehen wie alle anderen.

    ⛔ Sie ist die EINZIGE von vier Stellen, die auch versteckte Dateien
      zaehlt (fast-glob mit dot:false, die Claim-Garantie und der
      ANZ-Zaehler schliessen sie aus). Im Bestand liegen 151 versteckte
      Dateien (66x .DS_Store, 66x ._.DS_Store, 19 weitere ._*). Bleiben am
      Ende nur noch die uebrig, haelt diese Wache den Eingang fuer belegt,
      setzt die Sperre und schickt ein Phantom-Element weiter - und der
      naechste Durchgang findet die Sperre besetzt vor. Dauerleerlauf.
    """
    print("\nLeerlauf-Wache sieht dieselben Dateien wie alle anderen")
    block = _sperre_block()
    if block is None:
        return
    nur_versteckt = _sperre_fahren(block, ["kap/input/.DS_Store",
                                           "kap/input/Kunde/._Bericht.pdf"])
    if nur_versteckt is None:
        return
    pruefe("KI4KI-ABBRUCH" in nur_versteckt["stdout"],
           "nur versteckte Dateien im Eingang = nichts zu tun (ist: %r)"
           % nur_versteckt["stdout"].strip()[:120])
    pruefe(nur_versteckt["sperre"] is False,
           "⛔ und die Sperre wird NICHT gesetzt")
    # ⛔ Die Gegenprobe: Ein echtes Dokument MUSS die Wache passieren -
    #   sonst waere eine Wache, die immer abbricht, ebenso gruen.
    mit_arbeit = _sperre_fahren(block, ["kap/input/.DS_Store",
                                        "kap/input/Bericht.pdf"])
    pruefe("KI4KI-ABBRUCH" not in mit_arbeit["stdout"]
           and mit_arbeit["sperre"] is True,
           "Gegenprobe: liegt ein echtes Dokument daneben, laeuft der "
           "Durchgang an (ist: %r)" % mit_arbeit["stdout"].strip()[:120])


def test_notnagel_greift_auch_bei_leerem_eingang():
    """Eine haengengebliebene Sperre muss auch dann fallen, wenn nichts ansteht.

    ⛔ Der Notnagel stand HINTER der Leerlauf-Wache. Ist der Eingang leer,
      bricht die Wache mit exit 0 ab - der Notnagel wurde nie erreicht. Eine
      Sperre, die ein abgestuerzter Durchgang liegengelassen hat, blieb also
      genau so lange liegen, wie nichts Neues eintrifft: Der Zeitplan kommt
      jede Minute, sieht einen leeren Eingang, geht wieder - und raeumt die
      Sperre nie weg. Kommt dann Arbeit, steht sie vor der alten Sperre und
      muss selbst erst 120 Minuten warten.

    ⛔ Und unser eigener Commit 2384d25 hat das verschaerft: Vorher sah die
      Leerlauf-Wache auch versteckte Dateien (151 im Bestand, .DS_Store &
      Co.) und lief dadurch bis zum Notnagel weiter. Seit die Wache dieselbe
      Sicht hat wie alle anderen, steigt sie frueher aus - richtig fuer die
      Wache, aber der Notnagel dahinter fiel damit ganz aus.

    ⭐ Reihenfolge seither: Claim-Garantie, NOTNAGEL, Leerlauf-Wache,
      mkdir. Das mkdir muss hinter der Wache bleiben, sonst setzt ein
      Leerlauf wieder eine Sperre, die niemand freigibt.
    """
    print("\nDer 120-Minuten-Notnagel greift auch bei leerem Eingang")
    block = _sperre_block()
    if block is None:
        return

    # 1) Leerer Eingang (den Ordner gibt es, er ist leer) + alte Sperre.
    leer = _sperre_fahren(block, ["kap/input/"], sperre_alter=180)
    if leer is None:
        return
    pruefe("KI4KI-ABBRUCH" in leer["stdout"],
           "leerer Eingang bleibt ein Abbruch (ist: %r)"
           % leer["stdout"].strip()[:120])
    pruefe(leer["sperre"] is False,
           "⛔ und die 180 Minuten alte Sperre ist trotzdem weg")

    # 2) Derselbe Fall mit nur versteckten Dateien - der Zustand, in dem der
    #    Bestand nach einem Durchgang tatsaechlich zurueckbleibt.
    versteckt = _sperre_fahren(block, ["kap/input/.DS_Store",
                                       "kap/input/Kunde/._Bericht.pdf"],
                               sperre_alter=180)
    pruefe(versteckt["sperre"] is False,
           "⛔ auch wenn nur versteckte Dateien uebrig sind, faellt sie")

    # 3) GEGENPROBE: Eine junge Sperre bleibt. Ohne das waere der Schutz
    #    gegen zwei gleichzeitige Durchgaenge eingerissen - und eine Fassung,
    #    die die Sperre IMMER wegraeumt, waere bei 1) und 2) ebenfalls gruen.
    jung = _sperre_fahren(block, ["kap/input/"], sperre_alter=5)
    pruefe(jung["sperre"] is True,
           "GEGENPROBE: eine 5 Minuten junge Sperre bleibt liegen")

    # 4) GEGENPROBE mit Arbeit: Liegt Arbeit an und die Sperre ist jung,
    #    muss der Durchgang abbrechen statt sie zu uebernehmen.
    belegt = _sperre_fahren(block, ["kap/input/Bericht.pdf"], sperre_alter=5)
    pruefe("Es laeuft bereits ein Durchgang" in belegt["stdout"]
           and belegt["sperre"] is True,
           "GEGENPROBE: junge Sperre + Arbeit = Abbruch, Sperre bleibt "
           "(ist: %r)" % belegt["stdout"].strip()[:120])

    # 5) Alte Sperre UND Arbeit: der Durchgang uebernimmt - das ist der
    #    Fall, den der Notnagel bisher schon konnte, und er muss bleiben.
    uebernahme = _sperre_fahren(block, ["kap/input/Bericht.pdf"],
                                sperre_alter=180)
    pruefe("Sperre gesetzt." in uebernahme["stdout"]
           and uebernahme["sperre"] is True,
           "alte Sperre + Arbeit: der Durchgang uebernimmt (ist: %r)"
           % uebernahme["stdout"].strip()[:120])

    # 6) Und die Reihenfolge im Quelltext selbst - damit niemand das mkdir
    #    versehentlich mit nach vorn zieht.
    cmd = knoten("1_KI4KI-Masse-Ingest.json",
                 "Sperre setzen")["parameters"]["command"]
    i_not = cmd.find('-mmin +120')
    i_wache = cmd.find('if [ -z "$(find /files/dokumente/*/input')
    i_mkdir = cmd.find('mkdir "$L"')
    pruefe(min(i_not, i_wache, i_mkdir) >= 0,
           "Kontrolle: alle drei Stellen sind ueberhaupt da (%d/%d/%d)"
           % (i_not, i_wache, i_mkdir))
    pruefe(i_not < i_wache < i_mkdir,
           "Notnagel vor der Leerlauf-Wache, mkdir dahinter (%d < %d < %d)"
           % (i_not, i_wache, i_mkdir))


def _plan_lesen(datei):
    """Einen Ablaufplan laden - oder eine rote Pruefung statt eines Absturzes."""
    pfad = os.path.join(PLAENE, datei)
    if not os.path.exists(pfad):
        pruefe(False, "Ablaufplan fehlt: %s - NICHT geprueft" % datei)
        return None
    return json.load(open(pfad, encoding="utf-8"))


def test_unterkette_reisst_nicht_mit():
    """Eine stoerrische Datei darf nicht den ganzen Stapel mitnehmen.

    ⛔ Gemessen am 22.09. an n8n 2.31.4: Zehn Dateien, zehn
      Unterausfuehrungen, EIN Ergebnis - und im Protokoll
      "Cannot read properties of undefined (reading 'entries')" aus
      WorkflowExecute.assignPairedItems. Eine Unterausfuehrung gab nichts
      zurueck, der Elternbaustein stuerzte beim Einsammeln ab, und ALLE
      zehn Dateien kamen mit null Zeichen heraus - bei gemeldetem Erfolg.

    ⭐ Warum es vorher nie auffiel: Von allen Wegen war NUR der
      PDF-Weg abgesichert. Solange ausschliesslich PDF im Eingang lagen,
      konnte nichts passieren. Beim ersten Word-, Excel- oder
      Outlook-Dokument schon. Bei 4.300 Dateien ist eine stoerrische Datei
      keine Moeglichkeit, sondern eine Gewissheit.
    """
    print("\nKeine Datei reisst den Stapel mit")
    plan = _plan_lesen("2_Dateien-in-JSON-umwandeln.json")
    if plan is None:
        return
    riskant = [n for n in plan["nodes"]
               if n["type"].split(".")[-1] in ("httpRequest", "extractFromFile")]
    pruefe(len(riskant) >= 6,
           "Vorbedingung: es gibt ueberhaupt riskante Bausteine (%d)"
           % len(riskant))
    for n in riskant:
        pruefe(n.get("onError") == "continueRegularOutput",
               "%-38s faengt Fehler ab" % n["name"][:38])

    # ⛔ Die Gegenprobe: onError allein genuegt nicht. Ein Baustein, der
    #   im Fehlerfall gar kein Element weitergibt, laesst den
    #   Elternbaustein genauso abstuerzen wie einer, der abbricht.
    for n in riskant:
        if n["name"].startswith(("Extract from File", "Tika", "Office nach")):
            pruefe(n.get("alwaysOutputData") is True,
                   "%-38s gibt auch im Fehlerfall ein Element weiter"
                   % n["name"][:38])


def _zugesicherter_weg(plan, ausgang):
    """Gibt es einen Weg vom Ausloeser zum Ausgang, auf dem kein Knoten
    das Element verlieren kann?

    Durchlassend ist nur, was ein Element hineinbekommt und dasselbe
    wieder herausgibt: ein Set-Baustein, ein No-Op, ein Merge im Modus
    "anhaengen". Eine Weiche (If/Switch/Filter) schickt das Element
    woanders hin, ein Aufruf (HTTP, Code, Extract) kann scheitern oder
    eine leere Liste liefern - ueber beide fuehrt kein zugesicherter Weg.
    """
    knoten_nach_name = {n["name"]: n for n in plan["nodes"]}
    rand = [n["name"] for n in plan["nodes"]
            if n["type"].endswith("executeWorkflowTrigger")]
    gesehen = set(rand)
    while rand:
        akt = rand.pop()
        for zweig in (plan["connections"].get(akt, {}).get("main") or []):
            for c in (zweig or []):
                ziel = c["node"]
                if ziel == ausgang:
                    return True
                if ziel in gesehen:
                    continue
                k = knoten_nach_name.get(ziel) or {}
                typ = k.get("type", "").split(".")[-1]
                if typ == "merge":
                    if (k.get("parameters") or {}).get("mode") not in (None, "append"):
                        continue
                elif typ not in ("set", "noOp"):
                    continue
                gesehen.add(ziel)
                rand.append(ziel)
    return False


# Bausteine, die eine Unterausfuehrung ABBRECHEN koennen, wenn sie
# scheitern - und damit gar nichts zurueckgeben.
ABBRUCHFAEHIG = ("httpRequest", "extractFromFile", "code", "if", "switch",
                 "filter", "merge", "executeWorkflow")


def test_rueckgabe_garantiert():
    """Ablaufplan 2 muss IMMER genau ein Element zurueckgeben.

    ⛔ Gemessen am 23.09.: Eine einzige .db im Eingang gab kein Element
      zurueck. Im Elternteil brach assignPairedItems, der Baustein "Code"
      las eine leere Liste und lieferte return [] - der Durchgang endete
      GRUEN und leer, und zwar jede Minute neu, solange die Datei lag.

    ⭐ Warum test_unterkette_reisst_nicht_mit das nicht gefangen hat:
      Der prueft Bausteine EINZELN (Fehlerabfang je Baustein) und war am
      23.09. gruen, waehrend der Fehler lief. Eine Rueckgabe ist erst
      zugesichert, wenn es einen WEG vom Ausloeser zum Ausgang gibt, auf
      dem kein Baustein sie verschlucken kann - und wenn kein Baustein
      die Ausfuehrung vorher abbrechen kann.
    """
    print("\nJede Unterkette gibt immer genau ein Element zurueck")
    # \u26d4 NICHT nur Ablaufplan 2. Genau dieser fest eingetragene
    #   Dateiname hat am 23.09. abends den naechsten Ausfall durchgelassen:
    #   Ablaufplan 3 hatte denselben Fehler - kein Return, kein
    #   Fehlerabfang - und von 40 Dokumenten kam EINES im Bestand an.
    #   Eine Pruefung, die nur EINE Fundstelle einer Fehlerklasse ansieht,
    #   findet die anderen nie ("13 Stellen, 3 gefunden", 04.08.).
    unterketten = [d for d in sorted(os.listdir(PLAENE))
                   if d.endswith(".json")
                   and any(k["type"].endswith("executeWorkflowTrigger")
                           for k in (_plan_lesen(d) or {"nodes": []})["nodes"])]
    pruefe(len(unterketten) >= 2,
           "Vorbedingung: es gibt mehrere Unterketten (%d: %s)"
           % (len(unterketten), ", ".join(x[:1] for x in unterketten)))
    for _datei in unterketten:
        _pruefe_unterkette(_datei)


def _pruefe_unterkette(datei):
    print("  --- %s" % datei)
    plan = _plan_lesen(datei)
    if plan is None:
        return

    # 1 - Genau ein Ausgang, und der heisst Return.
    ausgaenge = [n["name"] for n in plan["nodes"]
                 if not any(any(z or []) for z in
                            (plan["connections"].get(n["name"], {}).get("main") or []))
                 and not n["type"].endswith("stickyNote")]
    pruefe(ausgaenge == ["Return"],
           "%s: genau ein Ausgang namens Return (ist: %s)"
           % (datei[:1], ausgaenge))

    # 2 - Der zugesicherte Weg. DAS ist die eigentliche Pruefung.
    pruefe(_zugesicherter_weg(plan, "Return"),
           "%s: ein Weg zum Return, auf dem kein Baustein das Element "
           "verlieren kann" % datei[:1])

    # 3 - Gegenprobe zu 2: ohne den Rueckfall-Zweig muss derselbe Test
    #     FEHLSCHLAGEN. Sonst prueft er nichts.
    ohne = json.loads(json.dumps(plan))
    ohne["connections"] = dict(
        (q, v) for q, v in ohne["connections"].items() if q != "Rueckfall")
    pruefe(not _zugesicherter_weg(ohne, "Return"),
           "%s: Gegenprobe - ohne den Rueckfall-Zweig ist der Weg NICHT "
           "mehr zugesichert" % datei[:1])

    # 4 - Kein Baustein darf die Unterausfuehrung abbrechen.
    for n in plan["nodes"]:
        if n["type"].split(".")[-1] in ABBRUCHFAEHIG:
            pruefe(n.get("onError") in ("continueRegularOutput",
                                        "continueErrorOutput"),
                   "%s: %-30s kann die Ausfuehrung nicht abbrechen"
                   % (datei[:1], n["name"][:30]))

    # 5 - Das Verhalten des Return-Bausteins, ausgefuehrt statt gelesen.
    kn = [n for n in plan["nodes"] if n.get("name") == "Return"]
    if not kn:
        pruefe(False, "Return-Baustein fehlt - Punkt 5 ist NICHT geprueft")
        return
    js = ausschnitt(kn[0].get("parameters", {}).get("jsCode", "") or "",
                    "// --- WAEHLEN ---", "// --- ENDE WAEHLEN ---",
                    "die Auswahl im Return-Baustein")
    if js is None:
        return
    faelle = """
      const echt   = {json: {data: 'Text', docling_filename: 'a.pdf'}};
      const rueck  = {json: {__rueckfall: true, grund: 'nichts geliefert'}};
      const raus = [];
      raus.push(_waehlen([echt, rueck], 'a.pdf').length);
      raus.push(_waehlen([rueck], 'a.pdf').length);
      raus.push(_waehlen([], 'a.pdf').length);
      raus.push(_waehlen([echt, rueck], 'a.pdf')[0].json.data);
      raus.push(_waehlen([rueck], 'a.pdf')[0].json.ok);
      raus.push(_waehlen([rueck], 'a.pdf')[0].json.docling_filename);
      raus.push(String(_waehlen([rueck], 'a.pdf')[0].json.fehler || '') !== '');
      raus.push(_waehlen([rueck], 'a.pdf')[0].json.data);
      console.log(JSON.stringify(raus));
    """
    e = json.loads(node_lauf(js + faelle))
    pruefe(e[0] == 1, "echtes Ergebnis + Rueckfall -> genau 1 Element")
    pruefe(e[1] == 1, "nur der Rueckfall -> genau 1 Element")
    pruefe(e[2] == 1, "gar nichts angekommen -> genau 1 Element")
    pruefe(e[3] == "Text", "das echte Ergebnis gewinnt, nicht der Rueckfall")
    pruefe(e[4] is False, "im Fehlerfall steht ok: false drin")
    pruefe(e[5] == "a.pdf",
           "der Fehlerfall traegt den Dateinamen - sonst findet die "
           "Paarung im Elternteil ihn nicht wieder")
    pruefe(e[6] is True, "im Fehlerfall steht ein Grund drin")
    pruefe(e[7] == "", "im Fehlerfall ist der Text leer -> aussortiert")


def test_stiller_durchgang_meldet_sich():
    """Ein Durchgang, der nichts ablegt, darf das nicht verschweigen.

    ⛔ Gemessen 22./23.09.: Gab die Unterkette nichts zurueck, lieferte
      "Code" still `return []`. Der Durchgang endete gruen und leer, jede
      Minute neu. Das hat zwei Tage gekostet - nicht weil es kaputt war,
      sondern weil es still war.

    ⭐ Kein Wurf. Ein Wurf beendet den Durchgang vor "Sperre freigeben",
      die Laufsperre bliebe liegen und blockierte alles bis zum
      120-Minuten-Notnagel (schon passiert am 04.08.). Also: melden und
      weitermachen wie bisher.

    ⛔ Und die Meldung muss HOERBAR sein. Laut n8n-Doku ist
      CODE_ENABLE_STDOUT per Vorgabe `false`; console.log aus einem
      Code-Baustein geht dann nur in die Browser-Konsole, nicht ins
      Container-Protokoll. Ohne den Schalter waeren die beiden bereits
      vorhandenen console.log in Ablaufplan 1 ebenfalls nie zu sehen
      gewesen - und genau das war der Fall.
    """
    print("\nEin stiller Durchgang meldet sich")
    plan = _plan_lesen("1_KI4KI-Masse-Ingest.json")
    if plan is None:
        return
    kn = [n for n in plan["nodes"] if n.get("name") == "Code"]
    if not kn:
        pruefe(False, "Baustein 'Code' fehlt - NICHT geprueft")
        return
    js = ausschnitt(kn[0].get("parameters", {}).get("jsCode", "") or "",
                    "// --- STILLE MELDEN ---", "// --- ENDE STILLE MELDEN ---",
                    "die Leerlauf-Meldung im Baustein Code")
    if js is not None:
        faelle = """
          const zeilen = [];
          const melden = m => zeilen.push(String(m));
          const raus = [];
          raus.push(_stille_melden([], [1,2,3], melden));
          raus.push(zeilen.length);
          raus.push(/\\b3\\b/.test(zeilen[0] || '') && /\\b0\\b/.test(zeilen[0] || ''));
          raus.push(_stille_melden([1,2,3], [1,2,3], melden));
          raus.push(zeilen.length);
          raus.push(_stille_melden([], [], melden));
          console.log(JSON.stringify(raus));
        """
        e = json.loads(node_lauf(js + faelle))
        pruefe(e[0] is True, "leeres Ergebnis bei 3 Dateien wird gemeldet")
        pruefe(e[1] == 1, "genau eine Zeile, nicht je Datei eine")
        pruefe(e[2] is True,
               "die Zeile nennt BEIDE Zahlen (0 von 3) - sonst sagt sie "
               "nicht, wie gross der Verlust war")
        pruefe(e[3] is False, "vollstaendiges Ergebnis meldet nichts")
        pruefe(e[4] == 1, "Gegenprobe: dabei kommt keine Zeile dazu")
        pruefe(e[5] is False, "gar keine Dateien ist kein Leerlauf")

    # ⛔ Die Meldung nuetzt nichts, wenn n8n sie nicht durchlaesst.
    wurzel = os.path.dirname(PLAENE)
    compose = os.path.join(wurzel, "docker-compose.yml")
    if not os.path.exists(compose):
        pruefe(False, "docker-compose.yml nicht gefunden - Hoerbarkeit "
                      "NICHT geprueft")
        return
    text = io.open(compose, encoding="utf-8").read()
    pruefe("CODE_ENABLE_STDOUT=true" in text,
           "CODE_ENABLE_STDOUT=true steht in der Compose - sonst geht die "
           "Meldung nur in die Browser-Konsole und nie ins Protokoll")


def test_stand_steht_im_protokoll():
    """Jeder Durchgang muss sagen, AUS WELCHEM Commit er stammt.

    ⛔ Am 23.09. konnte niemand beantworten, ob die gepushten Aenderungen
      im Betrieb ueberhaupt ankommen. In n8n stand der Publish-Knopf
      orange; `import:workflow` schreibt moeglicherweise nur den Entwurf,
      waehrend der Ausloeser die veroeffentlichte Fassung fuehrt (so
      gemessen 2026-06-25 am Telegram-Briefing). Drei Reparaturen lagen
      auf dem System, und ihre Abnahme waere wertlos gewesen, wenn gar
      nicht sie laufen.

    ⭐ Der Stempel beantwortet das fuer immer und kostet nichts: Der
      Baustein, der ohnehin jede Minute eine Zeile schreibt, stellt den
      Commit voran. Ein Blick ins Protokoll sagt, welche Fassung laeuft.
    """
    print("\nDer laufende Ablaufplan nennt seinen Stand")
    plan = _plan_lesen("1_KI4KI-Masse-Ingest.json")
    if plan is None:
        return
    kn = [n for n in plan["nodes"] if n.get("name") == "Nur ein Bereich je Durchgang"]
    if not kn:
        pruefe(False, "Baustein fehlt - NICHT geprueft")
        return
    js = kn[0]["parameters"]["jsCode"]
    pruefe(js.count("__STAND__") == 1,
           "der Platzhalter steht genau einmal im Baustein (ist: %d)"
           % js.count("__STAND__"))
    zeile = [z for z in js.splitlines() if "console.log" in z]
    pruefe(bool(zeile) and "__STAND__" in "\n".join(zeile[:3]),
           "und zwar in der Zeile, die JEDER Durchgang schreibt")

    # Das Einspielen muss ihn ersetzen - sonst steht der Platzhalter im Log.
    wurzel = os.path.dirname(PLAENE)
    skript = os.path.join(wurzel, "aktualisiere.sh")
    if not os.path.exists(skript):
        pruefe(False, "aktualisiere.sh fehlt - NICHT geprueft")
        return
    sh = io.open(skript, encoding="utf-8").read()
    pruefe("__STAND__" in sh and "rev-parse" in sh,
           "aktualisiere.sh setzt den Commit ein")
    # ⚠ NICHT auf 'docker cp "$wf"' pruefen - die Zeile bleibt zu Recht
    #   stehen. Entscheidend ist, WORUEBER die Schleife laeuft: ueber die
    #   gestempelten Kopien, nicht ueber die Dateien im Repo.
    pruefe("for wf in n8n-workflows/*.json; do docker cp" not in sh,
           "die Einspiel-Schleife laeuft NICHT mehr ueber die Repo-Dateien "
           "- sonst liesse sich der Stempel ueberspringen")
    pruefe('for wf in "${_wfdir}"/*.json; do docker cp' in sh,
           "sondern ueber die gestempelten Kopien")

    # Gegenprobe, ausgefuehrt: ersetzt der Befehl wirklich?
    quelle = os.path.join(PLAENE, "1_KI4KI-Masse-Ingest.json")
    e = subprocess.run(["sed", "s/__STAND__/pruefstand9/g", quelle],
                       capture_output=True, text=True, timeout=60)
    pruefe(e.returncode == 0 and "__STAND__" not in e.stdout
           and "pruefstand9" in e.stdout,
           "Gegenprobe: der Ersetzungsbefehl entfernt den Platzhalter "
           "wirklich und setzt den Stand ein")


def test_docling_laesst_der_grafikkarte_luft():
    """Docling darf der Sprachmaschine nicht den Speicher wegnehmen.

    ⛔ Gemessen 23.09. abends auf der A40 (46.068 MiB):

        gemma4:12b   8,9 GB   49%/51% CPU/GPU   <- haelbe Antwort auf CPU
        qwen3.8      17  GB   100% GPU
        gemma4:e2b   2,0 GB   100% GPU
        ki4ki-docling        12.222 MiB
        frei:                   927 MiB

      Das Modell, das die Chats beantwortet, rechnete zur HAELFTE auf der
      CPU. Genau dieser Zustand steht seit dem 04.08. in der Doku:
      "Ollama bekam 931 MiB und rechnete auf der CPU (4,4 statt ~40 t/s)"
      - damals 931 MiB frei, jetzt 927.

    ⭐ Die Ursache stand danebengeschrieben:
      DOCLING_SERVE_ENG_LOC_NUM_WORKERS=5. Jeder Worker haelt seine
      eigenen Modelle; fuenf davon sind die 12,2 GB. Das Heilmittel (1)
      war am 04.08. dokumentiert und irgendwann auf 5 hochgesetzt - ohne
      Begruendung in der Compose.

    ⚠ Es ist ein Tausch: Ein Worker wandelt Dokumente langsamer. Fuer
      einen grossen Aufnahmelauf darf man ihn hochsetzen - aber nicht
      dauerhaft, denn der Chat laeuft jeden Tag und die Aufnahme nicht.
      Deshalb: Vorgabe 1, ueber KI4KI_DOCLING_WORKERS hebbar.
    """
    print("\nDocling laesst der Grafikkarte Luft")
    wurzel = os.path.dirname(PLAENE)
    compose = os.path.join(wurzel, "docker-compose.yml")
    if not os.path.exists(compose):
        pruefe(False, "docker-compose.yml fehlt - NICHT geprueft")
        return
    t = io.open(compose, encoding="utf-8").read()
    pruefe("DOCLING_SERVE_ENG_LOC_NUM_WORKERS=5" not in t,
           "⛔ nicht mehr fest auf 5 - das nahm der Sprachmaschine "
           "10 GB weg und schob sie zur Haelfte auf die CPU")
    pruefe("DOCLING_SERVE_ENG_LOC_NUM_WORKERS="
           "${KI4KI_DOCLING_WORKERS:-1}" in t,
           "Vorgabe 1, fuer einen Aufnahmelauf ueber "
           "KI4KI_DOCLING_WORKERS hebbar")


def test_plaene_unversehrt():
    """Die Plaene muessen ladbar und vollstaendig bleiben."""
    print("\nAblaufplaene unversehrt")
    # ⚠ 31, nicht 30: "Nur Dokumente hochladen" kam am 24.09. dazu. Die alte
    #   Zahl stand seither falsch da und ist nie aufgefallen - der
    #   Pruefstand starb vorher im zweiten Test (siehe node_lauf).
    # ⚠ 34, nicht 31: "Dateiliste einlesen", "Dateiliste aufbereiten" und
    #   "Angaben wieder anheften" kamen am 06.10. dazu - der Umbau, der die
    #   Dateiliste VOR dem Laden begrenzt.
    for datei, knotenzahl in (("1_KI4KI-Masse-Ingest.json", 34),
                              ("2_Dateien-in-JSON-umwandeln.json", 22),
                              ("3_Markdown-Datei-erzeugen.json", 6)):
        d = json.load(io.open(os.path.join(PLAENE, datei), encoding="utf-8"))
        pruefe(len(d["nodes"]) == knotenzahl,
               "%s hat %d Knoten (erwartet %d)"
               % (datei, len(d["nodes"]), knotenzahl))
        leer = [k.get("name") for k in d["nodes"]
                if k.get("type", "").endswith(".code")
                and not (k.get("parameters", {}).get("jsCode") or "").strip()]
        pruefe(not leer, "%s: kein Code-Knoten ist leer" % datei)


def test_office_pdf_liegt_neben_dem_original():
    """Die gewandelte PDF muss im SELBEN Ordner landen wie ihr Original.

    ⛔ Gemessen am 22.09.: Ablaufplan 1 legt das Original seit dem
      Schluessel-Umbau mit Unterordnern ab (archiv/<Kunde>/<Auftrag>/x.docx),
      Ablaufplan 2 schrieb die gewandelte PDF weiter FLACH nach archiv/x.pdf.
      Damit lagen sie nicht mehr nebeneinander - und genau das setzt die
      Office-Regel im Proxy voraus (_schluessel_der_datei sucht das Original
      im selben Ordner). Folge: Das Word-Dokument hatte keine Seitenansicht,
      und die gewandelte PDF bekam einen eigenen Schluessel - ein Dokument,
      das niemand kennt. Bei 1.137 Office-Dateien im KAP-Bestand waeren das
      1.137 solche Geisterdokumente.

    ⭐ Ein Umbau an einer Stelle, der eine Annahme an einer anderen
      bricht. Die beiden Plaene laufen getrennt, und kein Werkzeug hat sie
      verglichen - deshalb steht der Vergleich jetzt hier.

    ⭐ Die Rechnung muss DIESELBE sein wie in Ablaufplan 1, Knoten
      "Code": wurzel = /files/dokumente/<bereich> mit bereich = Segment VOR
      dem letzten "input", unter = alle Segmente dahinter. "Aehnlich" reicht
      nicht - dann laufen sie beim naechsten Sonderfall wieder auseinander.
    """
    print("\nGewandelte PDF liegt neben dem Original")
    k = knoten("2_Dateien-in-JSON-umwandeln.json", "Office nach PDF")
    ziel = ""
    for kopf in k["parameters"]["headerParameters"]["parameters"]:
        if kopf.get("name") == "X-Ziel":
            ziel = kopf.get("value") or ""
    if not ziel.startswith("={{") or not ziel.rstrip().endswith("}}"):
        pruefe(False, "X-Ziel ist kein Ausdruck - dieser Teil ist NICHT "
                      "geprueft (%r)" % ziel[:40])
        return
    js = ziel.strip()[3:-2]

    def ziel_fuer(verzeichnis, name):
        aus = node_lauf(
            "const $binary = {data:{directory:%s, fileName:%s}};\n"
            "const w = (%s);\n"
            "console.log(w ? decodeURIComponent(w) : '(kein Ziel)');"
            % (json.dumps(verzeichnis), json.dumps(name), js))
        return aus.strip()

    # ⭐ Die Zusicherung: derselbe Ordner wie das Original.
    tief = ziel_fuer("/files/dokumente/kap/input/Kunde/Auftrag", "Bericht.docx")
    pruefe(tief == "/files/dokumente/kap/archiv/Kunde/Auftrag/Bericht.pdf",
           "drei Ebenen tief: %r" % tief)

    flach = ziel_fuer("/files/dokumente/kap/input", "Bericht.docx")
    pruefe(flach == "/files/dokumente/kap/archiv/Bericht.pdf",
           "ohne Unterordner: %r" % flach)

    # ⛔ Gegenprobe 1: Ohne "input" im Pfad KEIN Ziel. Ein geratenes Ziel
    #   legte die PDF unter den Eingang - und der naechste Durchgang sammelte
    #   sie wieder ein. Der Riegel gegen Endlosschleifen erzeugte dann eine.
    pruefe(ziel_fuer("/files/dokumente/kap/archiv", "Bericht.docx")
           == "(kein Ziel)",
           "ohne Eingangsordner wird KEIN Ziel genannt")

    # ⛔ Gegenprobe 2: Der Bereich wird am LETZTEN "input" bestimmt -
    #   genau wie in Ablaufplan 1. Ein Kundenordner, der selbst "input"
    #   heisst, darf die beiden nicht auseinanderlaufen lassen.
    doppelt = ziel_fuer("/files/dokumente/kap/input/input", "Bericht.docx")
    pruefe(doppelt == "/files/dokumente/input/archiv/Bericht.pdf",
           "zweimal 'input': dieselbe Rechnung wie Plan 1, ist %r" % doppelt)

    # ⛔ Gegenprobe 3: Die Endung wird getauscht, nicht angehaengt -
    #   sonst hiesse die Datei "Bericht.docx.pdf" und traefe das Original
    #   nicht mehr.
    pruefe(not tief.endswith(".docx.pdf"),
           "die Endung wird getauscht, nicht angehaengt")


# ==========================================================================
# ⭐ DER KOPF DER KETTE - AN EINEM ECHTEN VERZEICHNIS GEFAHREN (06.10.)
#
# ⛔ Warum das sein muss: Der Kopf hat die Platte des Produktivservers
#   vollgeschrieben. "Daten vom Server laden" las JEDE Datei des Eingangs
#   vollstaendig in den Speicher und erst DANACH schnitt "Menge begrenzen"
#   auf 25 zu. Mit N8N_DEFAULT_BINARY_DATA_MODE=filesystem landet alles
#   Gelesene je Ausfuehrung auf der Platte. Gemessen auf dem Server:
#   116,8 GB in 8.355 Ausfuehrungsordnern, /dev/sda3 zu 100 % voll, und
#   danach "ENOSPC: no space left on device, mkdir .../executions/59564".
#   Der Baustein brach ab, onError machte daraus ein leeres Ergebnis, und
#   die Kette meldete stundenlang "0 zu verarbeiten" bei vollem Eingang.
#
# ⚠ Eine Pruefung auf die REIHENFOLGE allein genuegt hier nicht - sie waere
#   auch dann gruen, wenn hinter dem Begrenzer wieder ein Platzhalter
#   stuende und doch alles laedt. Gezaehlt wird deshalb, wie viele Dateien
#   wirklich von der Platte gelesen werden; dafuer laeuft der Kopf an einem
#   echten Verzeichnisbaum.
# ==========================================================================
SONDERNAME = "Angebot (2) [alt] {neu}.pdf"
GLOB_SONDER = r"[*?\[\]{}()!@+|^$]"


def _schreibe(pfad, text="x"):
    ordner = os.path.dirname(pfad)
    if not os.path.isdir(ordner):
        os.makedirs(ordner)
    io.open(pfad, "w", encoding="utf-8").write(text)


def _eingangsbaum(dokumente=500, abfall=40):
    """Ein Eingang wie auf dem Server - echte Dateien, kein Nachbau.

    ⛔ DER ABFALL LIEGT IM BEREICH, DER ZUERST EINGELESEN WIRD, und es ist
      mehr als eine Charge voll (40 > 25). Wer die Menge VOR dem Filter
      begrenzt, sieht damit ausschliesslich Abfall: kein Dokument wird je
      gelesen, und der Rest des Abfalls bleibt fuer immer liegen. Genau das
      prueft die Gegenprobe.
    """
    import tempfile
    w = tempfile.mkdtemp(prefix="ki4ki-kopf-")
    for bereich in ("auw", "kap"):
        _schreibe(os.path.join(w, bereich, "bereich.json"),
                  '{"ablage": "%s"}' % bereich)
    for i in range(abfall):
        _schreibe(os.path.join(w, "auw", "input", "ordner%02d" % i, "Thumbs.db"))
    for i in range(dokumente):
        _schreibe(os.path.join(w, "kap", "input", "Dok-%03d.pdf" % i))
    # ⛔ SONDERZEICHEN IM NAMEN. n8n gibt den Dateiwaehler an fast-glob -
    #   also an einen MUSTERLESER. '(2)' ist dort eine Gruppe, '[alt]' eine
    #   Zeichenklasse: ein Pfad, der so heisst, wird als Muster NICHT
    #   gefunden. Die Datei verschwaende dann lautlos aus dem Durchgang und
    #   bliebe liegen, bis die Claim-Garantie sie aussortiert.
    _schreibe(os.path.join(w, "kap", "input", SONDERNAME))
    # ⛔ VERSTECKT. fast-glob laeuft mit dot:false; Claim-Garantie,
    #   Leerlauf-Wache und ANZ-Zaehler schliessen versteckte Dateien
    #   ausdruecklich aus ("DIESELBE SICHT WIE ALLE ANDERE"). Wer die
    #   Dateiliste anders beschafft, darf diese Sicht nicht weiten - sonst
    #   laufen die 151 versteckten Dateien des Bestands auf einmal in die
    #   Wegraeum-Maschinerie.
    _schreibe(os.path.join(w, "kap", "input", ".DS_Store"))
    return w


def _ausdruck(wert, item):
    """Einen n8n-Ausdruck auf EIN Element anwenden.

    Verstanden wird nur, was im Plan wirklich vorkommt: ein fester Text
    oder {{ $json.<feld> }}. Alles andere gibt None zurueck und wird vom
    Aufrufer ROT gemeldet - ein unverstandener Ausdruck darf nicht
    stillschweigend als fester Text durchgehen.
    """
    t = str(wert)
    if not t.startswith("="):
        return t
    t = re.sub(r"\{\{\s*\$json\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}",
               lambda m: str((item.get("json") or {}).get(m.group(1), "")),
               t[1:])
    return None if "{{" in t else t


def _glob_treffer(muster):
    """Was fast-glob zu diesem Dateiwaehler findet.

    ⚠ MODELL, NICHT DAS ECHTE fast-glob - das liegt nur im n8n-Container.
      Nachgebildet sind genau die beiden Faelle, die im Plan vorkommen:

      1. ein Platzhalter-Muster (/files/dokumente/*/input/**) - Dateien,
         keine Ordner, keine versteckten (dot:false);
      2. ein einzelner Pfad, in dem jedes Sonderzeichen mit \\ entschaerft
         ist - ein solches Muster trifft genau diesen einen Pfad.

      Bleibt in Fall 2 ein UNENTSCHAERFTES Sonderzeichen uebrig, gibt diese
      Funktion None zurueck: dann waere die Datei im Betrieb lautlos nicht
      gefunden worden, und das soll rot werden statt gruen.

    ⛔ WAS DIESES MODELL NICHT KANN - und warum es am 06.10. einen echten
      Fehler abgesegnet hat. Es nahm an, der Dateiwaehler ginge
      unveraendert an fast-glob. Tut er nicht: "Daten vom Server laden"
      ruft erst normalizeFileSelector(). Seitdem das hier nachgebildet
      ist, faellt die doppelte Entschaerfung auf - aber das bleibt eine
      NACHBILDUNG nach dem Stand von n8n 2.31.4. Sie weiss nicht, was
      eine andere n8n-Fassung tut, sie kennt picomatch nicht, und sie
      sieht nur die Pfade, die dieser Pruefstand selbst erfindet, nicht
      den echten Bestand. Dafuer gibt es
      test_findet_n8n_die_dateien_auch_wirklich: die faehrt dieselbe
      Kette im laufenden Container ueber die echten Pfade des Eingangs.
      Wird hier etwas gruen, das dort rot ist, gilt dort.
    """
    # ⛔ n8n legt noch einmal nach: normalizeFileSelector() ->
    #   escapeSpecialCharacters() setzt vor ( ) [ ] einen weiteren
    #   Backslash (nodes-base .../ReadWriteFile/helpers/utils.js, 2.31.4).
    #   Ohne diesen Schritt segnete das Modell eine doppelt entschaerfte
    #   Liste ab, die im Betrieb KEINE Datei mit Klammern findet.
    muster = re.sub(r"[()\[\]]", lambda m: "\\" + m.group(0), muster)
    if "\\" in muster:
        if re.search(GLOB_SONDER, re.sub(r"\\.", "", muster)):
            return None
        roh = re.sub(r"\\(.)", r"\1", muster)
        return [roh] if os.path.isfile(roh) else []
    if re.search(GLOB_SONDER, muster):
        import glob as _g
        return sorted(p for p in _g.glob(muster, recursive=True)
                      if os.path.isfile(p)
                      and not any(t.startswith(".") for t in p.split(os.sep)))
    return [muster] if os.path.isfile(muster) else []


def _kette_ab(plan, start, ende):
    """Die Bausteine zwischen start und ende, entlang Ausgang 0.

    ⚠ AUS DEM PLAN GELESEN, nicht fest eingetragen: Verschiebt jemand einen
      Baustein, faehrt diese Probe den NEUEN Weg - sonst wuerde sie den
      Umbau gar nicht bemerken.
    """
    weg, akt, gesehen = [], start, set()
    while True:
        folge = ((plan["connections"].get(akt, {}).get("main") or [[]])[0]) or []
        if not folge:
            return weg, False
        akt = folge[0]["node"]
        if akt == ende:
            return weg, True
        if akt in gesehen:
            return weg, False
        gesehen.add(akt)
        weg.append(akt)


def _code_fahren(k, ein, vor):
    """Einen Code-Baustein mit node fahren - echte Eingangsdaten, echte
    Ausgaben der Vorgaenger."""
    js = (
        "const EIN = " + json.dumps(ein) + ";\n"
        "const VOR = " + json.dumps(vor) + ";\n"
        "const _log = [];\n"
        "const console = { log: function () {"
        " _log.push(Array.prototype.join.call(arguments, ' ')); },"
        " error: function () {} };\n"
        "const $input = { all: () => EIN, first: () => EIN[0],"
        " last: () => EIN[EIN.length - 1] };\n"
        "const $ = (n) => { if (!(n in VOR)) { throw new Error("
        "'Referenced node is unexecuted: \"' + n + '\"'); }\n"
        "  const a = VOR[n];"
        " return { all: () => a, first: () => a[0], last: () => a[a.length - 1] }; };\n"
        "const $now = { toFormat: () => '2026-10-06 08:00:00' };\n"
        "const _raus = (function () {\n" + k["parameters"]["jsCode"] + "\n})();\n"
        "process.stdout.write(JSON.stringify({ raus: _raus || [], log: _log }));\n")
    return json.loads(node_lang(js))


def node_lang(js):
    """Wie node_lauf, aber ueber die Standardeingabe.

    ⛔ NICHT als Befehlsargument: Der Kopf der Kette wird mit 541 Dateien
      gefahren; Programm und Daten zusammen sprengen MAX_ARG_STRLEN
      (131.072 Byte), und der Aufruf scheiterte mit E2BIG - also genau so,
      wie der Wegraeum-Befehl es im Betrieb getan haette.
    """
    global NODE
    if NODE is None:
        NODE = _node_aufruf()
    e = subprocess.run(NODE, input=js, capture_output=True, text=True,
                       timeout=180)
    if e.returncode != 0:
        raise NodeFehler("node-Fehler:\n" + (e.stderr or "")[:2000])
    return e.stdout


# Was die Probe NICHT ausfuehrt: alles, was Dateien bewegt. "Sperre setzen"
# legt /files/json/.lauf.sperre an und verschiebt Dateien - sein Inhalt hat
# eine eigene Pruefreihe (_sperre_fahren, test_claim_*). Hier zaehlt nur,
# WAS BEI IHM ANKOMMT und wie viele Dateien bis dahin gelesen wurden.
BEWEGT = ("mkdir", "mv ", "rm ", "rmdir")


def _ohne_kommentar(befehl):
    """Die Shell-Kommentare raus, bevor nach mkdir/mv gesucht wird.

    ⛔ Ohne das galt "Dateiliste einlesen" als gefaehrlich und wurde nicht
      ausgefuehrt - allein weil in seinem Kommentar die gemessene
      Fehlermeldung "mkdir .../executions/59564" steht. Die Probe bekam
      dann eine leere Dateiliste und meldete "die Kette ist unterbrochen",
      also einen Fehler, den es gar nicht gab.
    """
    return "\n".join(z for z in str(befehl).splitlines()
                     if not z.lstrip().startswith("#"))


def _kopf_fahren(plan, wurzel, grenze):
    """Den Kopf der Kette an einem echten Verzeichnis fahren.

    Gibt zurueck, wie viele Dateien dabei WIRKLICH von der Platte gelesen
    wurden - die Zahl, an der die Platte vollgelaufen ist.
    """
    nach = dict((n["name"], n) for n in plan["nodes"])
    weg, heil = _kette_ab(plan, "Bestand abfragen", "Dateien klassifizieren")
    if not heil:
        return {"fehler": "Vom Bestand fuehrt kein gerader Weg zur "
                          "Klassifizierung (gelaufen: %s)" % " -> ".join(weg)}
    vor = {"Bestand abfragen": [{"json": {"localFiles": {"items": []}}}]}
    items, gelesen, dateien, mitschrift = vor["Bestand abfragen"], 0, [], []
    eingang_sperre = None
    for name in weg:
        k = nach[name]
        typ = k["type"].split(".")[-1]
        p = k.get("parameters") or {}
        if typ == "readWriteFile":
            neu = []
            for e in items:
                sel = _ausdruck(p.get("fileSelector", ""), e)
                if sel is None:
                    return {"fehler": "Den Dateiwaehler von %r versteht diese "
                            "Probe nicht: %r" % (name, p.get("fileSelector"))}
                treffer = _glob_treffer(sel.replace("/files/dokumente", wurzel))
                if treffer is None:
                    return {"fehler": "Im Dateiwaehler von %r steht ein "
                            "unentschaerftes Sonderzeichen - fast-glob "
                            "faende die Datei nicht: %r" % (name, sel)}
                for d in treffer:
                    gelesen += 1
                    dateien.append(d)
                    neu.append({"json": {}, "binary": {"data": {
                        "fileName": os.path.basename(d),
                        "directory": os.path.dirname(d)}}})
            items = neu
        elif typ == "limit":
            items = items[:grenze]
        elif typ == "code":
            if p.get("mode") not in (None, "runOnceForAllItems"):
                return {"fehler": "%r laeuft im Modus %r - diese Probe kennt "
                        "ihn nicht" % (name, p.get("mode"))}
            try:
                erg = _code_fahren(k, items, vor)
            except NodeFehler as f:
                # ⛔ KEIN Durchreichen des Absturzes. Ein Baustein, der
                #   wirft, ist ein ERGEBNIS dieser Probe ("die Kette ist
                #   unterbrochen") - beim Ueberfliegen sieht ein Traceback
                #   dagegen aus wie "die Probe ging nicht".
                return {"fehler": "%r ist beim Fahren gescheitert: %s"
                        % (name, str(f).replace("\n", " ")[:300])}
            items, _ = erg["raus"], mitschrift.extend(erg["log"])
        elif typ == "executeCommand":
            roh = str(p.get("command", ""))
            if any(b in _ohne_kommentar(roh) for b in BEWEGT):
                # Bewegt Dateien - wird NICHT ausgefuehrt, nur abgefangen.
                eingang_sperre = items
                items = [{"json": {"stdout": "Sperre gesetzt.", "exitCode": 0}}]
            else:
                befehl = _ausdruck(roh, items[0] if items else {})
                if befehl is None:
                    return {"fehler": "Den Befehl von %r versteht diese Probe "
                            "nicht: %r" % (name, roh[:120])}
                e = subprocess.run(["sh", "-c",
                                    befehl.replace("/files/dokumente", wurzel)],
                                   capture_output=True, text=True, timeout=120)
                items = [{"json": {"stdout": e.stdout, "exitCode": e.returncode}}]
        else:
            return {"fehler": "Baustein %r (%s) steht im Kopf der Kette - "
                    "diese Probe kennt ihn nicht" % (name, typ)}
        vor[name] = items
    return {"gelesen": gelesen, "dateien": dateien, "items": items,
            "weg": weg, "log": mitschrift, "sperre": eingang_sperre}


def _menge_je_lauf():
    """Die Charge je Durchgang - aus dem Plan, nicht geraten."""
    roh = str(knoten("1_KI4KI-Masse-Ingest.json",
                     "Menge begrenzen (Testlauf)")["parameters"]["maxItems"])
    m = re.search(r"\|\|\s*(\d+)", roh)
    return (roh, "KI4KI_MENGE_JE_LAUF" in roh, int(m.group(1)) if m else None)


def test_nur_die_begrenzte_menge_wird_gelesen():
    """D1: Bei 500 Dateien im Eingang duerfen hoechstens KI4KI_MENGE_JE_LAUF
    Dateien GELESEN werden - nicht 500.

    ⛔ Das ist der Fehler, der die Platte vollgeschrieben hat. 5.837 Dateien
      im Eingang waren 18 GB; die wurden bei JEDEM Durchgang vollstaendig
      gelesen und mit binary-mode=filesystem auf die Platte geschrieben.
    """
    print("\nD1 - wie viele Dateien ein Durchgang wirklich liest")
    roh, nennt_schalter, vorgabe = _menge_je_lauf()
    pruefe(nennt_schalter and vorgabe == 25,
           "Vorbedingung: der Begrenzer liest KI4KI_MENGE_JE_LAUF, Vorgabe "
           "25 (ist: %r)" % roh)
    grenze = vorgabe or 25
    plan = _plan_lesen("1_KI4KI-Masse-Ingest.json")
    if plan is None:
        return
    wurzel = _eingangsbaum()
    try:
        e = _kopf_fahren(plan, wurzel, grenze)
        if e.get("fehler"):
            pruefe(False, e["fehler"] + " - D1 ist damit NICHT geprueft")
            return
        # Kontrolle: Liegt ueberhaupt etwas im Probebaum? Ohne sie waere
        # "hoechstens 25 gelesen" auch bei einem leeren Ordner gruen.
        vorhanden = sum(len(f) for _, _, f in os.walk(wurzel))
        pruefe(vorhanden >= 540,
               "Kontrolle: im Probebaum liegen %d Dateien" % vorhanden)
        pruefe(e["gelesen"] <= grenze,
               "hoechstens %d Dateien werden von der Platte gelesen "
               "(gelesen: %d von %d)" % (grenze, e["gelesen"], vorhanden))
        # Gegenprobe zur Obergrenze: Es muessen auch wirklich welche
        # ankommen - "gar nichts lesen" waere sonst die beste Note.
        pruefe(e["gelesen"] == grenze,
           "und es sind genau %d - der Durchgang arbeitet (ist: %d)"
               % (grenze, e["gelesen"]))
        pruefe(all("/kap/input/" in d for d in e["dateien"]),
               "gelesen wird nur im Bereich, der an der Reihe ist")
        pruefe(len(e["items"]) == grenze,
               "und genau %d Elemente erreichen die Klassifizierung (ist: %d)"
               % (grenze, len(e["items"])))
    finally:
        import shutil
        shutil.rmtree(wurzel, ignore_errors=True)

    # ⛔ UND DIE DATEI MIT SONDERZEICHEN IM NAMEN. Passt die ganze Charge in
    #   einen Durchgang, muss JEDE Datei ankommen - auch
    #   'Angebot (2) [alt] {neu}.pdf'. Wird ein Pfad als fast-glob-Muster
    #   weitergereicht, ohne entschaerft zu werden, faellt genau sie lautlos
    #   heraus: sie bliebe im Eingang liegen, bis die Claim-Garantie sie
    #   aussortiert, und niemand saehe einen Fehler.
    klein = _eingangsbaum(dokumente=2, abfall=0)
    try:
        e = _kopf_fahren(plan, klein, grenze)
        if e.get("fehler"):
            pruefe(False, e["fehler"] + " - der Sonderfall ist NICHT geprueft")
            return
        pruefe(e["gelesen"] == 3,
               "eine kleine Charge wird vollstaendig gelesen (3 Dateien, "
               "gelesen: %d)" % e["gelesen"])
        pruefe(any(os.path.basename(d) == SONDERNAME for d in e["dateien"]),
               "darunter %r - Sonderzeichen im Namen gehen nicht verloren"
               % SONDERNAME)
    finally:
        import shutil
        shutil.rmtree(klein, ignore_errors=True)


def test_wegraeumen_sieht_weiterhin_alle_dateien():
    """D2 (Gegenprobe): Bereichswahl und Wegraeum-Befehl muessen weiter auf
    ALLEN Dateien arbeiten, nicht nur auf der Charge.

    ⛔ Wer die Menge zu frueh begrenzt, macht aus dem Plattenfehler einen
      Dauerzustand: Im Probebaum liegen 40 Merkdateien im zuerst
      eingelesenen Bereich - mehr als eine Charge. Begrenzt man vor dem
      Filter, besteht die Charge nur aus Abfall, kein Dokument wird je
      gelesen, und die uebrigen 15 Merkdateien bleiben fuer immer liegen.
      Genau so lagen vier 'bilder-nachholen.txt' elf Tage im Eingang.
    """
    print("\nD2 - der Wegraeum-Befehl arbeitet weiter auf allen Dateien")
    plan = _plan_lesen("1_KI4KI-Masse-Ingest.json")
    if plan is None:
        return
    wurzel = _eingangsbaum()
    try:
        e = _kopf_fahren(plan, wurzel, 25)
        if e.get("fehler"):
            pruefe(False, e["fehler"] + " - D2 ist damit NICHT geprueft")
            return
        ein = e.get("sperre") or []
        pruefe(len(ein) > 0,
               "Kontrolle: beim Baustein, der die Sperre setzt, kommt etwas an")
        befehl = ""
        for x in ein:
            befehl = befehl or str((x.get("json") or {}).get("aufraeumen") or "")
        geraeumt = set(re.findall(r"/auw/aussortiert/(ordner\d\d)/Thumbs\.db",
                                  befehl))
        pruefe(len(geraeumt) == 40,
               "alle 40 Merkdateien des anderen Bereichs stehen im "
               "Wegraeum-Befehl (sind: %d)" % len(geraeumt))
        pruefe(len(geraeumt) > 25,
               "und das sind MEHR als eine Charge - der Filter hat also die "
               "ganze Liste gesehen, nicht nur die begrenzte")
        pruefe("/kap/" not in befehl,
               "aus dem Bereich, der an der Reihe ist, wird nichts weggeraeumt")
        # Die Bereichswahl: der erste ECHTE Eintrag entscheidet, nicht der
        # Abfall - auch wenn der Abfall zuerst eingelesen wird.
        pruefe(any("Bereich kap" in z for z in e["log"]),
               "die Bereichswahl faellt auf 'kap' (Protokoll: %r)"
               % (e["log"][:1] or [""])[0][:120])
        # ⛔ Und die Sicht darf sich nicht geweitet haben.
        pruefe(".DS_Store" not in befehl,
               "versteckte Dateien bleiben unsichtbar - dieselbe Sicht wie "
               "Claim-Garantie, Leerlauf-Wache und ANZ-Zaehler")
    finally:
        import shutil
        shutil.rmtree(wurzel, ignore_errors=True)


def _leser(plan):
    """Der Baustein, der Dateien aus dem Eingang laedt."""
    for n in plan["nodes"]:
        if not n["type"].endswith(".readWriteFile"):
            continue
        sel = str((n.get("parameters") or {}).get("fileSelector", ""))
        if "/input" in sel or "$json" in sel:
            return n
    return None


def test_begrenzen_steht_vor_dem_laden():
    """D3: Erst begrenzen, dann laden - und zwar auf JEDEM Weg.

    ⛔ Heute war es umgekehrt. Eine Pruefung "der Begrenzer steht
      irgendwo davor" genuegt nicht: Es darf KEINEN Weg vom Ausloeser zum
      Lade-Baustein geben, der am Begrenzer vorbeifuehrt.
    """
    print("\nD3 - begrenzen vor laden")
    plan = _plan_lesen("1_KI4KI-Masse-Ingest.json")
    if plan is None:
        return
    leser = _leser(plan)
    if leser is None:
        pruefe(False, "kein Baustein laedt mehr aus dem Eingang - NICHT geprueft")
        return
    sel = str((leser.get("parameters") or {}).get("fileSelector", ""))
    pruefe(not re.search(r"[*?]", sel),
           "der Lade-Baustein nennt keinen Platzhalter mehr, sondern genau "
           "eine Datei je Element (ist: %r)" % sel)
    pruefe(sel.startswith("=") and "$json" in sel,
           "der Pfad kommt aus dem Element selbst (ist: %r)" % sel)
    begrenzer = "Menge begrenzen (Testlauf)"
    rand = [n["name"] for n in plan["nodes"]
            if n["type"].split(".")[-1] in ("manualTrigger", "scheduleTrigger",
                                            "webhook")]
    pruefe(len(rand) >= 3, "Vorbedingung: es gibt Ausloeser (%d)" % len(rand))
    gesehen, warte, vorbei = set(rand), list(rand), []
    while warte:
        akt = warte.pop()
        for zweig in (plan["connections"].get(akt, {}).get("main") or []):
            for c in (zweig or []):
                ziel = c["node"]
                if ziel == leser["name"]:
                    vorbei.append(akt)
                    continue
                if ziel == begrenzer or ziel in gesehen:
                    continue
                gesehen.add(ziel)
                warte.append(ziel)
    pruefe(not vorbei,
           "kein Weg vom Ausloeser zum Lade-Baustein fuehrt am Begrenzer "
           "vorbei (vorbei ueber: %r)" % (vorbei,))
    # Gegenprobe: Ohne den Begrenzer MUSS der Lade-Baustein erreichbar sein -
    # sonst haette die Suche oben auch bei heiler Kette nichts gefunden.
    gesehen, warte, erreicht = set(rand), list(rand), False
    while warte:
        akt = warte.pop()
        for zweig in (plan["connections"].get(akt, {}).get("main") or []):
            for c in (zweig or []):
                if c["node"] == leser["name"]:
                    erreicht = True
                if c["node"] in gesehen:
                    continue
                gesehen.add(c["node"])
                warte.append(c["node"])
    pruefe(erreicht,
           "GEGENPROBE: ohne diese Sperre ist der Lade-Baustein sehr wohl "
           "erreichbar - die Suche greift also")


def test_aufraeumen_der_ausfuehrungen_ist_durchgereicht():
    """D4: Die Aufraeum-Einstellungen muessen im Container ankommen.

    ⛔ Ohne sie reicht der Umbau nicht. Rechnung am nachgemessenen
      Bestand (06.10. im Container, find + fs.statSync - die alte Zahl
      "3,2 MB" war aus 5.837 Dateien = 18 GB geschaetzt und zu klein):
      6.798 Dateien = 28,67 GB, also 4,22 MB je Datei. 25 Dateien je
      Durchgang sind rund 106 MB; bei 1.440 Durchgaengen am Tag waeren
      das 153 GB taeglich auf einer 251-GB-Platte. Ab Werk raeumt n8n
      erst bei 10.000 Ausfuehrungen oder 336 Stunden auf - gemessen lagen
      8.355 Ordner da, der Deckel war also nie erreicht.

    ⚠ UND DER DECKEL ZAEHLT DURCHGAENGE, KEINE BYTES. Die 25 schwersten
      Dateien des Bestands wiegen zusammen 7,71 GB - so schwer kann EIN
      Durchgang sein. Gedeckelt wird das nur ueber MAX_AGE (48 Stunden x
      hoechstens 49 Dokumenten je Stunde = 2.352 Dokumente = 27,3 GB).
      Die Rechnung steht ausfuehrlich in der docker-compose.yml.
    """
    print("\nD4 - die Aufraeum-Einstellungen kommen im Container an")
    wurzel = os.path.dirname(PLAENE)
    pfad = os.path.join(wurzel, "docker-compose.yml")
    if not os.path.exists(pfad):
        pruefe(False, "docker-compose.yml fehlt - NICHT geprueft")
        return
    umgebung = _umgebung_des_dienstes(io.open(pfad, encoding="utf-8").read(),
                                      "n8n")
    pruefe("KI4KI_MENGE_JE_LAUF=${KI4KI_MENGE_JE_LAUF:-25}" in umgebung,
           "Kontrolle: die bekannten Schalter stehen beim Dienst n8n (%d "
           "Eintraege gelesen)" % len(umgebung))
    namen = [z.split("=")[0] for z in umgebung]
    for schalter in ("EXECUTIONS_DATA_PRUNE",
                     "EXECUTIONS_DATA_MAX_AGE",
                     "EXECUTIONS_DATA_PRUNE_MAX_COUNT",
                     "EXECUTIONS_DATA_PRUNE_SOFT_DELETE_INTERVAL",
                     "EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL"):
        pruefe(schalter in namen,
               "%s wird an n8n weitergereicht" % schalter)
    # ⛔ Und die Werte muessen ENGER sein als die Vorgabe - ein Schalter,
    #   der nur die Werkseinstellung wiederholt, aendert nichts.
    werte = dict(z.split("=", 1) for z in umgebung if "=" in z)

    def zahl(s):
        m = re.search(r"(\d+)\s*\}?$", werte.get(s, ""))
        return int(m.group(1)) if m else None

    for schalter, werk, was in (
            ("EXECUTIONS_DATA_PRUNE_MAX_COUNT", 10000,
             "der Deckel liegt unter der Werkseinstellung 10.000"),
            ("EXECUTIONS_DATA_MAX_AGE", 336,
             "das Hoechstalter liegt unter der Werkseinstellung 336 Stunden"),
            ("EXECUTIONS_DATA_PRUNE_SOFT_DELETE_INTERVAL", 60,
             "der Vormerk-Takt liegt unter der Werkseinstellung 60 Minuten"),
            ("EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL", 15,
             "der Loesch-Takt liegt unter der Werkseinstellung 15 Minuten")):
        w = zahl(schalter)
        if w is None:
            pruefe(False, "%s hat keinen lesbaren Wert (%r) - NICHT geprueft"
                   % (schalter, werte.get(schalter)))
            continue
        pruefe(w < werk, "%s (ist: %d)" % (was, w))
    # Der Betriebsmodus fuer Binaerdaten bleibt eine bewusste Entscheidung
    # und muss begruendet in der Doku stehen.
    pruefe("N8N_DEFAULT_BINARY_DATA_MODE=filesystem" in umgebung,
           "und die Binaerdaten bleiben auf der Platte (nicht in der "
           "Datenbank - die gibt geloeschten Platz nie zurueck)")
    for datei, was in ((".env.beispiel", "die .env-Vorlage"),
                       (os.path.join("doku", "BETRIEB.md"), "die Doku")):
        p = os.path.join(wurzel, datei)
        t = io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        pruefe("EXECUTIONS_DATA_PRUNE_MAX_COUNT" in t,
               "%s nennt den Deckel" % was)
    doku = io.open(os.path.join(wurzel, "doku", "BETRIEB.md"),
                   encoding="utf-8").read()
    for wort, was in (("ENOSPC", "woran man es erkennt"),
                      ("0 zu verarbeiten", "den Phantom-Durchgang"),
                      ("storage/workflows", "wo der Platz liegt")):
        pruefe(wort in doku, "die Doku nennt %s" % was)


if __name__ == "__main__":
    ALLE = [
        test_nichtdokumente,
        test_leere_aussortieren,
        test_leer_marke_kommt_aus_code,
        test_positivliste,
        test_positivliste_hat_genau_eine_quelle,
        test_positivliste_vor_der_sperre,
        test_aufraeumbefehl_bleibt_unter_der_befehlsgrenze,
        test_claim_schwelle_aus_der_umgebung,
        test_claim_minuten_ist_durchgereicht,
        test_claim_garantie_raeumt_wirklich,
        test_leerlauf_wache_uebersieht_versteckte,
        test_notnagel_greift_auch_bei_leerem_eingang,
        test_unterkette_reisst_nicht_mit,
        test_docling_einstellungen,
        test_bereichserkennung,
        test_office_pdf_liegt_neben_dem_original,
        test_rueckgabe_garantiert,
        test_stiller_durchgang_meldet_sich,
        test_stand_steht_im_protokoll,
        test_docling_laesst_der_grafikkarte_luft,
        test_plaene_unversehrt,
        test_nur_die_begrenzte_menge_wird_gelesen,
        test_wegraeumen_sieht_weiterhin_alle_dateien,
        test_begrenzen_steht_vor_dem_laden,
        test_aufraeumen_der_ausfuehrungen_ist_durchgereicht,
        test_was_n8n_wirklich_geladen_hat,
        test_findet_n8n_die_dateien_auch_wirklich,
    ]
    # ⛔ JEDER Test einzeln eingefasst. Platzt einer, ist ER rot - die
    #   uebrigen laufen trotzdem. Vorher beendete ein einziger node-Fehler
    #   den ganzen Lauf, und elf Tests meldeten sich elf Tage lang gar nicht.
    for _t in ALLE:
        try:
            _t()
        except Exception as _f:                                  # noqa: BLE001
            pruefe(False, "%s ist geplatzt: %s: %s"
                   % (_t.__name__, _f.__class__.__name__,
                      str(_f).replace("\n", " ")[:300]))
    print("\nGeprueft wurden die Plaene in: %s" % PLAENE)
    print("%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
