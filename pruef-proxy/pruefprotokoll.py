#!/usr/bin/env python3
"""Das Protokoll der Anlage - eigene Aufzeichnung, nicht AnythingLLMs Verlauf.

Warum eigen und nicht der vorhandene Verlauf: Am System wurde
gemessen, dass `workspace_chats.response` NICHT die Antwort enthaelt,
die der Nutzer gesehen hat. Gespeichert werden 2.196 Zeichen rohe
Modellantwort statt der 8.164 Zeichen geprueften Fassung - ohne
Belegblock, ohne Fundstellen, ohne Bilanz. Und alles, was der Proxy
selbst beantwortet (Bestandsauskunft, Zusammenfassung, Rueckfrage),
steht dort ueberhaupt nicht. Ein Protokoll auf dieser Grundlage haette
Luecken UND falsche Eintraege, und man sieht ihm beides nicht an.

## Aufbau

JSONL ist die Wahrheit, tagesweise getrennt, nur angehaengt. Ein Absturz
kann hoechstens die letzte Zeile beschaedigen - der Leser ueberspringt
sie. Das ist der Unterschied zu `.geprueft.json`, das bei jedem Merken
die ganze Datei ueberschreibt und bei einem Absturz alles kostet.

Jede Zeile traegt `hash` ueber ihren Inhalt und `prev_hash` der
Vorgaengerzeile. Damit laesst sich spaeter belegen, dass nichts
herausgeschnitten wurde. Nachtraeglich ist das wertlos, deshalb von
Anfang an.

## Personenbezug

Standardmaessig steht KEIN Klarname im Protokoll, sondern ein stabiles
Pseudonym. Grund: Ein Protokoll aus Konto, Zeit und Fragetext ist eine
Einrichtung, die zur Verhaltens- und Leistungskontrolle geeignet ist -
und nach Paragraf 72 Absatz 4 Satz 1 Nummer 1 LPVG NRW genuegt die
Eignung, damit die Personalvertretung zu beteiligen ist. Ob je
ausgewertet wird, spielt rechtlich keine Rolle.

Fachlich kostet das Pseudonym nichts: Wie oft jemand fragte und was er
fragte, bleibt nachvollziehbar. Nur die Zuordnung zur Person braucht
einen getrennt verwahrten Schluessel.
"""
import hashlib
import hmac
import json
import re
import os
import re
import threading
import time

# ------------------------------------------------------------- Einstellungen
# Bewusst keine Moeglichkeit, die Aufbewahrung auf "unbegrenzt" zu stellen:
# Artikel 5 Absatz 1 Buchstabe e DSGVO verlangt eine Begrenzung, und eine
# Voreinstellung, die man versehentlich ins Unendliche schiebt, ist keine.
ORDNER = os.environ.get("KI4KI_PROTOKOLL") or "/app/.protokoll"
TAGE_VORGABE = 90
TAGE_HOECHSTENS = 365


def _zahl(name, vorgabe, hoechstens=None):
    try:
        wert = int(os.environ.get(name, "") or vorgabe)
    except ValueError:
        return vorgabe
    if wert < 0:
        return vorgabe
    return min(wert, hoechstens) if hoechstens else wert


def _schalter(name, vorgabe):
    roh = (os.environ.get(name) or "").strip().lower()
    if roh in ("1", "an", "ja", "true", "on"):
        return True
    if roh in ("0", "aus", "nein", "false", "off"):
        return False
    return vorgabe


EINSTELLUNG = {
    # Aufzeichnung an. Ohne sie gibt es keinen Nachweis, dass eine Antwort
    # belegt war - und keine Zahlen fuer die Wirksamkeitsmessung.
    "an": _schalter("KI4KI_PROTOKOLL_AN", True),
    # Klarname aus. Siehe Kopf.
    "klarname": _schalter("KI4KI_PROTOKOLL_KLARNAME", False),
    # Der Fragetext ist ein eigener Schalter, nicht an die Aufzeichnung
    # gekoppelt: In einer Frage koennen Namen Dritter stehen - der
    # Verfasser einer Studienarbeit, ein Auftraggeber aus einem
    # Pruefbericht. Wer die Belegkette nachweisen will, braucht dafuer
    # nicht zwingend den Wortlaut.
    "fragetext": _schalter("KI4KI_PROTOKOLL_FRAGETEXT", True),
    # Antworttext ist umfangreich; wer nur Kennzahlen braucht, schaltet ihn ab.
    "antworttext": _schalter("KI4KI_PROTOKOLL_ANTWORT", True),
    "tage": _zahl("KI4KI_PROTOKOLL_TAGE", TAGE_VORGABE, TAGE_HOECHSTENS),
}

_SPERRE = threading.Lock()
_STAND = {"seq": 0, "prev": ""}
_BEREIT = False


def _pfad(name):
    return os.path.join(ORDNER, name)


def _heute():
    return time.strftime("%Y-%m-%d", time.gmtime())


def _jetzt():
    # UTC mit ausgeschriebenem Versatz. Container ohne Zeitabgleich driften,
    # und die Reihenfolge darf nicht an der Uhr haengen - dafuer ist `seq` da.
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + \
        ".%03dZ" % (int(time.time() * 1000) % 1000)


def _salz():
    """Der Schluessel, aus dem die Pseudonyme entstehen.

    Liegt neben dem Protokoll, aber in einer eigenen Datei - wer nur die
    Protokolle bekommt (Sicherung, Auswertung, Weitergabe), kann daraus
    keine Person zurueckrechnen.
    """
    p = _pfad(".pseudonym-schluessel")
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return fh.read().strip()
    schluessel = os.urandom(32).hex().encode()
    alt = os.umask(0o077)
    try:
        with open(p, "wb") as fh:
            fh.write(schluessel)
    finally:
        os.umask(alt)
    return schluessel


def pseudonym(konto):
    """Stabil je Person, aber nicht zurueckrechenbar ohne den Schluessel."""
    if not konto:
        return "unbekannt"
    if EINSTELLUNG["klarname"]:
        return konto
    return "n-" + hashlib.sha256(_salz() + konto.encode()).hexdigest()[:12]


def darf_einsehen(konto):
    """Wer darf das Protokoll als Ganzes lesen?

    Bewusst eine eigene Liste und NICHT die Administratorrolle: Wer die
    Anlage betreibt, muss nicht sehen koennen, wer was gefragt hat - und
    wer im Protokoll steht, darf es nicht aendern koennen. Die Trennung
    ist der Kern der Zusage an die Personalvertretung; kaeme sie
    automatisch mit der Adminrolle, waere sie keine.

    Leere Liste heisst: niemand. Die eigene Auskunft (Artikel 15) laeuft
    ueber einen anderen Weg und braucht diese Erlaubnis nicht.
    """
    erlaubt = [k.strip() for k in
               (os.environ.get("KI4KI_PROTOKOLL_EINSICHT") or "").split(",")
               if k.strip()]
    if not konto or not erlaubt:
        return False
    # ⚠ Die Aufrufer reichen das PSEUDONYM ("n-c814...") herein, die Liste
    #   traegt Klarnamen ("admin"). Gemessen 27.08.: /kpi, /rueckmeldungen und
    #   /rolle wiesen den Admin ab. Deshalb gelten beide Schreibweisen.
    return konto in erlaubt or konto in {pseudonym(k) for k in erlaubt}


def konto_aus(kopfzeilen):
    """Wer fragt? Aus dem Sitzungs-Token gelesen, nicht geraten.

    Der Token der Oberflaeche traegt die Kennung im Mittelteil. Er wird
    hier NICHT geprueft - das tut AnythingLLM, und zwar bevor ueberhaupt
    eine Antwort entsteht. Hier geht es nur darum, zwei Vorgaenge derselben
    Person einander zuzuordnen.

    Ohne diesen Schritt bliebe nur der Fingerabdruck des Tokens - der
    wechselt bei jeder Neuanmeldung, und dieselbe Person waere im
    Protokoll jedes Mal jemand anderes.

    Der n8n-Weg meldet sich mit einem Schluessel statt mit einem Token;
    dort steht "dienst" plus ein kurzer Fingerabdruck, damit sich mehrere
    angebundene Dienste unterscheiden lassen.
    """
    roh = ""
    try:
        roh = (kopfzeilen.get("Authorization") or "").strip()
    except Exception:
        return "unbekannt"
    marke = roh.split(None, 1)[-1] if roh else ""
    teile = marke.split(".")
    if len(teile) == 3:
        try:
            import base64
            mitte = teile[1] + "=" * (-len(teile[1]) % 4)
            d = json.loads(base64.urlsafe_b64decode(mitte))
            name = d.get("username") or d.get("id")
            if name:
                return str(name)
        except Exception:
            pass
    if marke:
        return "dienst-" + hashlib.sha256(marke.encode()).hexdigest()[:8]
    try:
        keks = (kopfzeilen.get("Cookie") or "").strip()
    except Exception:
        keks = ""
    if keks:
        return "sitzung-" + hashlib.sha256(keks.encode()).hexdigest()[:8]
    return "unbekannt"


def _bereit():
    global _BEREIT
    if _BEREIT:
        return True
    try:
        os.makedirs(ORDNER, exist_ok=True)
    except Exception:
        return False
    # Stand aus der letzten Zeile des juengsten Tages holen - die Zaehlung
    # darf einen Neustart ueberleben, sonst ist die Reihenfolge nach dem
    # ersten `docker compose up` nicht mehr rekonstruierbar.
    try:
        tage = sorted(d for d in os.listdir(ORDNER)
                      if re.match(r"^\d{4}-\d\d-\d\d\.jsonl$", d))
        if tage:
            letzte = None
            with open(_pfad(tage[-1]), "r", encoding="utf-8") as fh:
                for zeile in fh:
                    if zeile.strip():
                        letzte = zeile
            if letzte:
                d = json.loads(letzte)
                _STAND["seq"] = int(d.get("seq", 0))
                _STAND["prev"] = d.get("hash", "")
    except Exception:
        # Ein unlesbares Protokoll darf den Betrieb nicht aufhalten. Die
        # Kette bricht dann sichtbar - besser als ein stiller Neuanfang.
        pass
    _BEREIT = True
    return True


def _kettenschluessel():
    """Schluessel fuer die HMAC-Kette - eigene Datei, genau wie der
    Pseudonym-Schluessel. Wer nur die Protokollzeilen bekommt (Sicherung,
    Auswertung, Weitergabe), hat ihn NICHT und kann darum keinen gueltigen
    Hash nachrechnen - die Kette wird faelschungssicher gegen jeden, der
    nur die Zeilen hat."""
    p = _pfad(".protokoll-schluessel")
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return fh.read().strip()
    schluessel = os.urandom(32).hex().encode()
    alt = os.umask(0o077)
    try:
        with open(p, "wb") as fh:
            fh.write(schluessel)
    finally:
        os.umask(alt)
    return schluessel


def _hash(satz):
    """Kettenhash eines Satzes.

    ⛔ HMAC statt blossem sha256. Ein blosser Hash laesst sich
    nach einer Aenderung KOMPLETT neu durchrechnen - die Kette waere dann
    "heil", obwohl jemand eine Zeile getauscht oder entfernt hat. Mit einem
    Schluessel, den ein Export nicht enthaelt, geht das nicht mehr.

    Alte Zeilen (v==1) tragen noch einen reinen sha256; sie bleiben
    nachpruefbar, weil hier nach der Version verzweigt wird. Die Kette
    laeuft ueber die Grenze hinweg weiter (prev_hash haengt nur am Wert des
    vorigen Hashes, nicht an seiner Bauart).
    """
    roh = json.dumps(satz, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if satz.get("v", 1) >= 2:
        return hmac.new(_kettenschluessel(), roh, hashlib.sha256).hexdigest()
    return hashlib.sha256(roh).hexdigest()


def schreibe(**felder):
    """Einen Vorgang festhalten. Wirft nie - Protokollieren darf eine
    Antwort niemals verhindern."""
    if not EINSTELLUNG["an"]:
        return None
    try:
        if not _bereit():
            return None
        if not EINSTELLUNG["fragetext"]:
            felder.pop("frage_original", None)
            felder.pop("frage_gesucht", None)
        if not EINSTELLUNG["antworttext"]:
            felder.pop("antwort", None)
        with _SPERRE:
            _STAND["seq"] += 1
            satz = {"v": 2, "seq": _STAND["seq"], "ts": _jetzt(),
                    "prev_hash": _STAND["prev"]}
            satz.update({k: v for k, v in felder.items() if v is not None})
            satz["hash"] = _hash(satz)
            _STAND["prev"] = satz["hash"]
            ziel = _pfad(_heute() + ".jsonl")
            with open(ziel, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(satz, ensure_ascii=False) + "\n")
                fh.flush()
                # Ohne fsync sind die letzten Eintraege bei jedem
                # `docker compose down` weg - und ein verlorener Eintrag
                # ist dieselbe Luecke, die dieses Modul beheben soll.
                os.fsync(fh.fileno())
        return satz["seq"]
    except Exception:
        return None


def kette_pruefen(datei):
    """Ist die Kette lueckenlos? Liefert (heil, geprueft, erste_fehlerzeile).

    Das ist der Nachweis, den AnythingLLMs Verlauf nicht fuehren kann:
    dass zwischen zwei Eintraegen keiner entfernt wurde.
    """
    prev, n = "", 0
    with open(datei, "r", encoding="utf-8") as fh:
        for nr, zeile in enumerate(fh, 1):
            if not zeile.strip():
                continue
            try:
                d = json.loads(zeile)
            except Exception:
                return False, n, nr
            eigen = d.pop("hash", "")
            if d.get("prev_hash", "") != prev or _hash(d) != eigen:
                return False, n, nr
            prev = eigen
            n += 1
    return True, n, None


def aufraeumen(tage=None):
    """Abgelaufene Tagesdateien loeschen.

    Der Loeschvorgang wird selbst festgehalten, aber ohne Personenbezug -
    nur Zeitraum, Anzahl, Zeitpunkt. Ein Loeschprotokoll, das die Daten
    konserviert, die es zu loeschen behauptet, waere sinnlos.
    """
    tage = tage if tage is not None else EINSTELLUNG["tage"]
    if not _bereit() or tage <= 0:
        return []
    grenze = time.time() - tage * 86400
    weg = []
    for d in sorted(os.listdir(ORDNER)):
        if not re.match(r"^\d{4}-\d\d-\d\d\.jsonl$", d):
            continue
        try:
            wann = time.mktime(time.strptime(d[:10], "%Y-%m-%d"))
        except ValueError:
            continue
        if wann < grenze:
            try:
                os.remove(_pfad(d))
                weg.append(d[:10])
            except Exception:
                pass
    if weg:
        schreibe(art="aufraeumen", bereich=None, konto=None,
                 geloeschte_tage=weg, frist_tage=tage)
    return weg


def eigene_eintraege(konto_pseudonym):
    """Alles zu einem Pseudonym - fuer die Selbstauskunft nach Artikel 15.

    Absichtlich nur ueber das Pseudonym: Wer Auskunft will, bekommt seinen
    eigenen Vorgang, ohne dass jemand die Zuordnungstabelle oeffnen muss.
    """
    if not _bereit():
        return []
    raus = []
    for d in sorted(os.listdir(ORDNER)):
        if not re.match(r"^\d{4}-\d\d-\d\d\.jsonl$", d):
            continue
        try:
            with open(_pfad(d), "r", encoding="utf-8") as fh:
                for zeile in fh:
                    if not zeile.strip():
                        continue
                    try:
                        satz = json.loads(zeile)
                    except Exception:
                        continue
                    if satz.get("konto") == konto_pseudonym:
                        raus.append(satz)
        except Exception:
            continue
    return raus


def _ohne_endung(name):
    """Ein Dokument, ein Eintrag in der Zaehlung.

    Derselbe Titel kommt in zwei Schreibweisen an: aus der Belegpruefung
    mit ".md" (so liegt der Bestand), aus den Quellen von AnythingLLM mit
    ".pdf". Ohne diese Angleichung stand dasselbe Werk schon einmal zweimal
    in der Liste der meistgenutzten Quellen - einmal mit 3, einmal mit 2
    Treffern statt einmal mit 5. Eine Kennzahl, die doppelt zaehlt, ist
    schlimmer als keine: Sie sieht richtig aus.
    """
    if not name:
        return ""
    for endung in (".md", ".pdf", ".txt", ".docx", ".xlsx"):
        if name.lower().endswith(endung):
            return name[:-len(endung)]
    return name


def alle_eintraege(seit=None, bis=None):
    """Alle Vorgaenge, zeitlich eingegrenzt. Aelteste zuerst."""
    if not _bereit():
        return []
    raus = []
    for d in sorted(os.listdir(ORDNER)):
        if not re.match(r"^\d{4}-\d\d-\d\d\.jsonl$", d):
            continue
        tag = d[:10]
        if (seit and tag < seit) or (bis and tag > bis):
            continue
        try:
            with open(_pfad(d), "r", encoding="utf-8") as fh:
                for zeile in fh:
                    if not zeile.strip():
                        continue
                    try:
                        raus.append(json.loads(zeile))
                    except Exception:
                        continue
        except Exception:
            continue
    return raus


def kennzahlen(seit=None, bis=None):
    """Die Zahlen fuer die Wirksamkeitsmessung (K5).

    Die Partner haben protokolliert, dass ihnen die Quantifizierung des
    Mehrwerts fehlt. Genau die steht hier - und zwar ohne Personenbezug:
    gezaehlt werden Vorgaenge, nicht Personen. Die Zahl der Fragenden wird
    nur als Anzahl unterschiedlicher Kennungen ausgewiesen, ohne sie zu
    benennen.
    """
    alle = alle_eintraege(seit, bis)
    fragen = [e for e in alle if e.get("art") == "frage"]
    rueck = [e for e in alle if e.get("art") == "rueckmeldung"]
    if not fragen:
        return {"vorgaenge": 0, "rueckmeldungen": len(rueck)}
    verdikte, regeln, bereiche, wege = {}, {}, {}, {}
    dauern, koepfe, quellen = [], set(), {}
    for e in fragen:
        for topf, feld in ((verdikte, "verdikt"), (regeln, "regel"),
                           (bereiche, "bereich"), (wege, "weg")):
            w = e.get(feld)
            if w:
                topf[w] = topf.get(w, 0) + 1
        if e.get("dauer_ms"):
            dauern.append(e["dauer_ms"])
        if e.get("konto"):
            koepfe.add(e["konto"])
        for f in (e.get("fundstellen") or []):
            d = _ohne_endung(f.get("dok"))
            if d:
                quellen[d] = quellen.get(d, 0) + 1
    dauern.sort()
    # ⭐ K5 (Leitfaden S. 101, 105, 127): belegt = woertlich/geglaettet/teilweise
    #   (die echten Urteile von veredeln) ODER direkte Antworten aus dem
    #   Katalog/Dokument (eigen). Eskaliert = die Anlage hat ehrlich "nicht
    #   gefunden" gesagt statt zu raten. Zeit bis zur ersten verwertbaren
    #   Quelle = Dauer der ersten belegten Antwort je Faden.
    belegt = sum(verdikte.get(k, 0) for k in ("belegt", "woertlich", "geglaettet", "teilweise"))
    eskaliert, stoerfaelle, erste = 0, 0, {}
    tage = {}
    for e in fragen:
        a = (e.get("antwort") or "")
        if re.search(r"nicht gefunden|steht .{0,40}nichts|keine (?:passende )?seite|nicht belegt|Ansprechpartner|"
                     r"keine belastbare Information|nicht auf den gepr", a, re.I):
            eskaliert += 1
        if e.get("kontext"):
            stoerfaelle += 1
        tag = (e.get("ts") or "")[:10]
        if tag:
            tage.setdefault(tag, set()).add(e.get("konto"))
        f = e.get("faden") or "-"
        if f not in erste and e.get("verdikt") in ("belegt", "woertlich", "geglaettet", "teilweise") and e.get("dauer_ms"):
            erste[f] = e["dauer_ms"]
    erste_dauern = sorted(erste.values())
    rueck_pos = sum(1 for e in rueck if e.get("bewertung") == "hilfreich")
    rueck_neg = sum(1 for e in rueck if e.get("bewertung") in ("nicht hilfreich", "falsche Quelle"))
    return {
        "vorgaenge": len(fragen),
        "fragende": len(koepfe),
        "belegt_anteil": round(100.0 * belegt / len(fragen), 1),
        "eskaliert": eskaliert,
        "eskalationsquote": round(100.0 * eskaliert / len(fragen), 1),
        "stoerfaelle": stoerfaelle,
        "zeit_bis_erste_quelle_median_ms": erste_dauern[len(erste_dauern) // 2] if erste_dauern else None,
        "faeden": len({e.get("faden") or "-" for e in fragen}),
        "nutzung_je_tag": {t: len(k) for t, k in sorted(tage.items())},
        "rueckmeldungen": {"hilfreich": rueck_pos, "nicht_hilfreich": rueck_neg, "gesamt": len(rueck)},
        "trefferquote": round(100.0 * (len(fragen) - eskaliert) / len(fragen), 1),
        "verdikte": verdikte,
        "regeln": regeln,
        "bereiche": bereiche,
        "wege": wege,
        # Der Mittelwert wird von einzelnen Ausreissern verzogen - beim
        # Median steht, was die Haelfte der Fragenden wirklich erlebt.
        "dauer_median_ms": dauern[len(dauern) // 2] if dauern else None,
        "dauer_langsamste_ms": dauern[-1] if dauern else None,
        "meistgenutzte_quellen": sorted(quellen.items(), key=lambda x: -x[1])[:10],
    }


def einstellungen_festhalten():
    """Beim Start festhalten, wie protokolliert wird.

    Aenderungen an der Protokollierung gehoeren ins Protokoll - sonst
    laesst sich spaeter nicht sagen, ob eine Luecke eine Luecke ist oder
    eine abgeschaltete Aufzeichnung.
    """
    return schreibe(art="einstellungen", **{
        k: v for k, v in EINSTELLUNG.items()})
