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
        raise SystemExit("node-Fehler:\n" + (e.stderr or "")[:2000])
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
const faelle = [
  ["Text da, Name gefunden",      {filename:"Bericht.pdf", abdruck:A, text_length:5000}, gemeldet],
  ["Text LEER, Name gefunden",    {filename:"Bericht.pdf", abdruck:A, text_length:0},    gemeldet],
  ["Text 5 Zeichen, Name gef.",   {filename:"Bericht.pdf", abdruck:A, text_length:5},    gemeldet],
  ["Text 20 Zeichen, Name gef.",  {filename:"Bericht.pdf", abdruck:A, text_length:20},   gemeldet],
  ["Text da, Name NICHT gefunden",{filename:"Bericht.pdf", abdruck:A, text_length:5000}, fremd],
  ["Text leer, Name nicht gef.",  {filename:"Bericht.pdf", abdruck:A, text_length:0},    fremd],
  ["text_length fehlt ganz",      {filename:"Bericht.pdf", abdruck:A},                   gemeldet],
  ["OHNE Abdruck, Name gefunden", {filename:"Bericht.pdf", text_length:5000},            gemeldet],
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
    kern = ausschnitt(quelle, "const bereichVon", "const nameVon", "bereichVon")
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


def test_positivliste():
    """Nur vorgesehene Formate kommen in den Bestand.

    Gemessen am KAP-Bestand (22.09.): 2.093 von 4.325 Dateien gehen an die
    "sonst"-Weiche zu Tika - 1.707 Bilder und rund 190 in Formaten, die
    niemand vorgesehen hat. Entschieden hat bisher allein die Textlaenge;
    aus einer Binaerdatei kommt fast immer irgendein Zeichensalat, und der
    landete als "Dokument" im Bestand.
    """
    print("\nNur vorgesehene Formate")
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
""" + kern + """
  return { drin, grund: begruendung };
}
const A = "ab12cd34ef";
const G = ["kap-kundeb-bericht-" + A + "-md"];
const faelle = [
  ["pdf", "Bericht.pdf"], ["docx", "Bericht.docx"], ["doc", "Bericht.doc"],
  ["pptx", "Folien.pptx"], ["xlsx", "Werte.xlsx"], ["xlsm", "Werte.xlsm"],
  ["txt", "Liste.txt"], ["csv", "Werte.csv"], ["md", "Notiz.md"],
  ["jpg", "Foto.jpg"], ["tif", "Mikroskop.tif"], ["zip", "Anhang.zip"],
  ["tra", "Messung.tra"], ["001", "Teil.001"], ["msg", "Post.msg"],
  ["eml", "Post.eml"], ["ohne", "LIESMICH"],
];
console.log(JSON.stringify(faelle.map(([k, n]) =>
  [k, entscheide({filename: n, abdruck: A, text_length: 5000}, G, grund)])));
"""
    erg = dict((k, e) for k, e in json.loads(node_lauf(js)))

    # 1. Was hinein soll, kommt hinein - auch mit reichlich Text.
    for k in ("pdf", "docx", "doc", "pptx", "xlsx", "xlsm", "txt", "csv", "md"):
        pruefe(erg[k]["drin"] is True,
               "%-5s wird aufgenommen" % k)

    # 2. ⛔ Was Text LIEFERN KOENNTE, aber nicht vorgesehen ist, bleibt
    #    draussen. Genau hier lag der Fehler: text_length ist in allen
    #    Faellen 5000, die Entscheidung darf also NICHT daran haengen.
    for k in ("jpg", "tif", "zip", "tra", "001", "ohne"):
        pruefe(erg[k]["drin"] is False,
               "%-5s bleibt draussen, obwohl Text da waere" % k)
        pruefe("nicht vorgesehen" in erg[k]["grund"],
               "%-5s nennt den WAHREN Grund, nicht 'kein Text'" % k)

    # 3. Korrespondenz bekommt eine EIGENE Begruendung - sie ist nicht
    #    "nicht vorgesehen", sondern vertagt.
    for k in ("msg", "eml"):
        pruefe(erg[k]["drin"] is False, "%-5s bleibt draussen" % k)
        pruefe("Korrespondenz" in erg[k]["grund"],
               "%-5s wird als Korrespondenz benannt, nicht als Formatfehler" % k)

    # 4. ⛔ Die Gegenprobe, ohne die alles oben nichts sagt: Die Liste darf
    #    nicht einfach ALLES abweisen. Ohne diese Zeile waere Nummer 2 auch
    #    dann gruen, wenn `drin` immer false ist - und der ganze Bestand
    #    bliebe leer, ohne dass eine Pruefung rot wird.
    pruefe(any(erg[k]["drin"] for k in erg),
           "Gegenprobe: mindestens ein Format kommt ueberhaupt durch")


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
    print("\nAblaufplan 2 gibt immer genau ein Element zurueck")
    plan = _plan_lesen("2_Dateien-in-JSON-umwandeln.json")
    if plan is None:
        return

    # 1 - Genau ein Ausgang, und der heisst Return.
    ausgaenge = [n["name"] for n in plan["nodes"]
                 if not any(any(z or []) for z in
                            (plan["connections"].get(n["name"], {}).get("main") or []))
                 and not n["type"].endswith("stickyNote")]
    pruefe(ausgaenge == ["Return"],
           "genau ein Ausgang, und der heisst Return (ist: %s)" % ausgaenge)

    # 2 - Der zugesicherte Weg. DAS ist die eigentliche Pruefung.
    pruefe(_zugesicherter_weg(plan, "Return"),
           "es gibt einen Weg zum Return, auf dem kein Baustein das "
           "Element verlieren kann")

    # 3 - Gegenprobe zu 2: ohne den Rueckfall-Zweig muss derselbe Test
    #     FEHLSCHLAGEN. Sonst prueft er nichts.
    ohne = json.loads(json.dumps(plan))
    ohne["connections"] = dict(
        (q, v) for q, v in ohne["connections"].items() if q != "Rueckfall")
    pruefe(not _zugesicherter_weg(ohne, "Return"),
           "Gegenprobe: ohne den Rueckfall-Zweig ist der Weg NICHT mehr "
           "zugesichert - die Pruefung kann also rot werden")

    # 4 - Kein Baustein darf die Unterausfuehrung abbrechen.
    for n in plan["nodes"]:
        if n["type"].split(".")[-1] in ABBRUCHFAEHIG:
            pruefe(n.get("onError") in ("continueRegularOutput",
                                        "continueErrorOutput"),
                   "%-38s kann die Ausfuehrung nicht abbrechen"
                   % n["name"][:38])

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


def test_plaene_unversehrt():
    """Die Plaene muessen ladbar und vollstaendig bleiben."""
    print("\nAblaufplaene unversehrt")
    for datei, knotenzahl in (("1_KI4KI-Masse-Ingest.json", 30),
                              ("2_Dateien-in-JSON-umwandeln.json", 22)):
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


if __name__ == "__main__":
    test_nichtdokumente()
    test_leere_aussortieren()
    test_positivliste()
    test_unterkette_reisst_nicht_mit()
    test_docling_einstellungen()
    test_bereichserkennung()
    test_office_pdf_liegt_neben_dem_original()
    test_rueckgabe_garantiert()
    test_stiller_durchgang_meldet_sich()
    test_plaene_unversehrt()
    test_was_n8n_wirklich_geladen_hat()
    print("\nGeprueft wurden die Plaene in: %s" % PLAENE)
    print("%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
