#!/usr/bin/env python3
"""Wie viele Ablagedateien liegen im Bestand, auf die KEIN Arbeitsbereich
mehr verweist - und gibt es den umgekehrten Fall?

Hintergrund (Befund des Betreibers, 24.09.): In /daten/bestand/documents
liegen 1.224 Dateien im Ordner custom-documents, waehrend der gesamte
Bestand ueber alle Arbeitsbereiche keine 200 Dokumente hat. Die Zahl
waechst ueber Tage: /pruef-status meldete nur_altweg mit 84 (23.09.),
1276 (24.09.), 1328 (heute) - zweimal binnen Minuten gestiegen, ohne
dass eine Aufnahme lief.

Warum das keine Kosmetik ist: veredeln.Bestand laeuft mit os.walk ueber
den GANZEN Bestandsordner (veredeln.py, Bestand.__init__) und
pruef_proxy.nur_ueber_altweg() ebenso. Eine Datei ohne Arbeitsbereich ist
deshalb nicht nur Platz - sie ist Teil der Vorauswahl, sie zaehlt in
nur_altweg mit, und damit haelt sie die Uebergangsstuetze am Leben.

Zwei Richtungen werden gemessen:
  Datei ohne Verweis = WAISE              (liegt da, niemand braucht sie)
  Verweis ohne Datei = TREFFER INS LEERE  (schlimmer: bei jeder Frage)

Ohne Netz: Die Zuordnung Datei -> Arbeitsbereich steht in der
SQLite-Datei von AnythingLLM, und die liegt im selben Volume
(docker-compose.yml, pruef-proxy: anythingllm-daten:/daten/bestand:ro).
Es wird KEINE API gebraucht - ein Messwerkzeug, das ein Netz braucht, ist
unzuverlaessiger als eines, das nachsieht. Das Schema wird nicht geraten,
sondern zur Laufzeit gesucht und an den Dateien auf der Platte geprueft.

⛔ NUR MESSEN. Es gibt keinen Schalter zum Aufraeumen. Die Datenbank wird
   vor dem Lesen kopiert und nur die Kopie geoeffnet - die laufende Anlage
   bekommt nicht einmal einen Lesevorgang ab.

⛔ Gibt AUSSCHLIESSLICH Zahlen und Ablageordnernamen aus. Keine
   Dokumentnamen, keine Dateinamen, keine Inhalte. Das wird nicht
   behauptet, sondern bei JEDEM Lauf am eigenen Quelltext geprueft
   (dieselbe Pruefung einzeln: --datensperre).

  docker cp bau/waisenprobe.py ki4ki-pruef-proxy:/app/waisenprobe.py
  docker exec ki4ki-pruef-proxy python3 /app/waisenprobe.py

  python3 bau/waisenprobe.py --gegenprobe    (beweist am Baukasten, dass
                                              die Probe rot werden kann;
                                              braucht keine Anlage)
  python3 bau/waisenprobe.py --datensperre   (nur die Quelltext-Pruefung)

Rueckgabe 0 = Messung gueltig, 1 = ungueltig. Eine ungueltige Messung
sieht beim Ueberfliegen aus wie ein Befund - deshalb sagt das Skript es
selbst, statt es in eine Fussnote zu schreiben.
"""
import ast
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "pruef-proxy"))
sys.path.insert(0, "/app")

import schluessel   # noqa: E402


# --------------------------------------------------------------- Ausgabe
#
# ⛔ ALLE Ausgabe laeuft durch diese drei Stellen. Das ist der Grund,
#   warum die Datensperre ueberhaupt pruefbar ist: "Kommt print woanders
#   vor?" ist eine Ja/Nein-Frage fuer eine Maschine. "Kann dieser f-String
#   einen Dateinamen enthalten?" waere keine.
#
#   sag()        nimmt eine Vorlage (Literal) und nur ZAHLEN.
#   sag_ordner() nimmt zusaetzlich EINEN Namen, und der muss in der
#                Liste der gefundenen Ablageordner stehen.
#   sag_leer()   eine Leerzeile.

ERLAUBT = {"ordner": set()}

WURZEL_MARKE = "(Wurzel)"
FREMD_MARKE = "(unbekannte Ordner)"


def sag(vorlage, *zahlen):
    """Eine Ausgabezeile. vorlage ist im Quelltext ein Literal, alles
    Eingesetzte ist eine ZAHL - zur Laufzeit geprueft, nicht zugesichert."""
    for z in zahlen:
        if isinstance(z, bool) or not isinstance(z, (int, float)):
            raise TypeError("sag(): eingesetzt werden duerfen nur Zahlen. "
                            "Die Datensperre haelt diesen Wert zurueck.")
    print(vorlage % zahlen if zahlen else vorlage)


def sag_ordner(ordner, vorlage, *zahlen):
    """Eine Zeile, die mit einem ABLAGEORDNERNAMEN beginnt.

    ⛔ Der Name muss in ERLAUBT["ordner"] stehen. Damit kann hier kein
      Dateiname durchrutschen, auch nicht durch einen Programmfehler:
      Ablageordner sind die Unterordner des Bestands, ein Dateiname steht
      nie in dieser Menge. Die Fehlermeldung nennt den Namen ABSICHTLICH
      nicht - sonst waere sie selbst das Leck.
    """
    if ordner not in ERLAUBT["ordner"]:
        raise ValueError("sag_ordner(): dieser Name steht nicht in der Liste "
                         "der Ablageordner - die Datensperre haelt ihn zurueck.")
    for z in zahlen:
        if isinstance(z, bool) or not isinstance(z, (int, float)):
            raise TypeError("sag_ordner(): eingesetzt werden duerfen nur Zahlen.")
    print("  %-26s %s" % (ordner[:26], (vorlage % zahlen) if zahlen else vorlage))


def sag_leer():
    print("")


# ------------------------------------------------- Datensperre am Quelltext
#
# ⭐ Hausregel: Zu jeder Pruefung gehoert der Nachweis, mit WELCHER Eingabe
#   sie rot wird. Fuer diese hier sind es drei Eingaben - ein print()
#   ausserhalb der drei Ausgabefunktionen, eine zusammengesetzte Vorlage
#   (sag("Datei " + name)) und ein f-String. Alle drei werden in
#   --gegenprobe, Fall 6, an einem absichtlich undichten Quelltext
#   vorgefuehrt.

_AUSGABE_FUNKTIONEN = ("sag", "sag_ordner", "sag_leer")

# Wer den Bildschirm selbst anfassen darf. Nur die Gegenprobe, und nur, um
# ihn WEGZUNEHMEN (sie misst die Rueckgabe von berichten(), nicht den Text).
_BILDSCHIRM_ERLAUBT = ("_stumm_berichten",)


def datensperre_pruefen(quelldatei=None):
    """Den Quelltext durchgehen. Rueckgabe: (Zeilennummern der
    Beanstandungen, Zahl der geprueften Ausgabestellen)."""
    pfad = quelldatei or os.path.abspath(__file__)
    with open(pfad, encoding="utf-8") as fh:
        quelle = fh.read()
    baum = ast.parse(quelle)

    def bereiche_von(namen):
        aus = []
        for k in ast.walk(baum):
            if isinstance(k, ast.FunctionDef) and k.name in namen:
                aus.append((k.lineno,
                            getattr(k, "end_lineno", None) or k.lineno))
        return aus

    ausgabe_bereiche = bereiche_von(_AUSGABE_FUNKTIONEN)
    bildschirm_bereiche = bereiche_von(_BILDSCHIRM_ERLAUBT)

    def drinnen(bereiche, zeile):
        return any(a <= zeile <= e for a, e in bereiche)

    def ist_bildschirm(knoten):
        """Zeigt dieser Ausdruck auf stdout/stderr?

        ⚠ Ein fh.write() in eine DATEI ist keine Ausgabe - die erste
          Fassung dieser Pruefung verbot jedes .write() und wurde dadurch
          an zwei harmlosen Stellen rot. Eine Pruefung, die immer rot ist,
          schaltet man ab; dann bewacht sie nichts mehr.
        """
        while isinstance(knoten, ast.Attribute):
            if knoten.attr in ("stdout", "stderr"):
                return True
            knoten = knoten.value
        return isinstance(knoten, ast.Name) and knoten.id in ("stdout", "stderr")

    maengel = set()
    stellen = 0
    for k in ast.walk(baum):
        # 1) f-Strings gar nicht erst zulassen. Ein f-String ist im
        #    Quelltext kein Literal mehr - genau die Form, in der sonst ein
        #    Dateiname in eine Zeile wandert.
        if isinstance(k, ast.JoinedStr):
            maengel.add(k.lineno)
            continue
        # 2) stdout/stderr gehoeren niemandem ausser der Gegenprobe.
        if isinstance(k, ast.Attribute) and k.attr in ("stdout", "stderr"):
            if not drinnen(bildschirm_bereiche, k.lineno):
                maengel.add(k.lineno)
            continue
        if not isinstance(k, ast.Call):
            continue
        name = None
        if isinstance(k.func, ast.Name):
            name = k.func.id
        elif isinstance(k.func, ast.Attribute):
            name = k.func.attr
        # 3) print nur in den drei Ausgabefunktionen.
        if name == "print" and not drinnen(ausgabe_bereiche, k.lineno):
            maengel.add(k.lineno)
            continue
        # 4) Am Bildschirm vorbei schreiben ist auch Ausgabe - aber nur,
        #    wenn wirklich der Bildschirm gemeint ist.
        if (name == "write" and isinstance(k.func, ast.Attribute)
                and ist_bildschirm(k.func.value)):
            maengel.add(k.lineno)
            continue
        # 5) Ein Traceback nennt Pfade.
        if name in ("print_exc", "print_exception", "print_stack",
                    "format_exc"):
            maengel.add(k.lineno)
            continue
        # 6) Die Vorlage muss ein Zeichenketten-Literal sein. Damit faellt
        #    sag("Datei " + name) auf, ohne dass jemand wissen muss, was in
        #    name steht.
        if name in ("sag", "sag_ordner"):
            stellen += 1
            i = 1 if name == "sag_ordner" else 0
            if len(k.args) <= i:
                maengel.add(k.lineno)
                continue
            v = k.args[i]
            if not (isinstance(v, ast.Constant) and isinstance(v.value, str)):
                maengel.add(k.lineno)
    return sorted(maengel), stellen


# -------------------------------------------------------- Die Datenbank
#
# Der Bestandsordner ist <speicher>/documents. Die SQLite-Datei von
# AnythingLLM liegt im selben Speicher eine Ebene darueber; im Proxy ist
# das ganze Volume eingehaengt. Belegt in docker-compose.yml:
#   anythingllm:  STORAGE_DIR=/app/server/storage,
#                 anythingllm-daten:/app/server/storage
#   pruef-proxy:  KI4KI_BESTAND=/daten/bestand/documents,
#                 anythingllm-daten:/daten/bestand:ro

_SQLITE_MARKE = b"SQLite format 3\x00"


def db_kandidaten(speicher):
    """Alle SQLite-Dateien im Speicherordner - an der Dateimarke erkannt,
    nicht an der Endung. Ein Name ist kein Beweis."""
    fest = os.environ.get("KI4KI_ANYTHINGLLM_DB")
    wege = []
    if fest:
        wege = [fest]
    else:
        try:
            for n in sorted(os.listdir(speicher)):
                wege.append(os.path.join(speicher, n))
        except OSError:
            return []
    aus = []
    for w in wege:
        if not os.path.isfile(w):
            continue
        try:
            with open(w, "rb") as fh:
                if fh.read(len(_SQLITE_MARKE)) == _SQLITE_MARKE:
                    aus.append(w)
        except OSError:
            continue
    return aus


def db_kopie_oeffnen(pfad, arbeitsordner):
    """Die Datenbank kopieren und die KOPIE oeffnen.

    ⛔ Nicht die Originaldatei, aus zwei Gruenden. Erstens laeuft die
      Anlage waehrenddessen; ein Messwerkzeug hat auf ihrer Datenbank
      nichts verloren. Zweitens haengt das Volume schreibgeschuetzt
      (":ro"): Liegt ein -wal daneben, verweigert SQLite auch das
      Nur-Lese-Oeffnen, weil es die Wiederherstellung nicht schreiben
      kann. Die Kopie hat beide Probleme nicht.

    ⚠ Die Kopie einer laufenden Datenbank kann einen Augenblick alt sein.
      Fuer eine Mengenmessung ist das in Ordnung - fuer einen Loeschlauf
      waere es das NICHT. Ein weiterer Grund, warum hier nichts geloescht
      wird.
    """
    ziel = os.path.join(arbeitsordner, "kopie.db")
    shutil.copy2(pfad, ziel)
    for anhang in ("-wal", "-shm", "-journal"):
        if os.path.exists(pfad + anhang):
            shutil.copy2(pfad + anhang, ziel + anhang)
    return sqlite3.connect(ziel)


def _tabellen(db):
    return [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]


def _spalten(db, tabelle):
    return [(r[1], (r[2] or "").upper())
            for r in db.execute('PRAGMA table_info("%s")' % tabelle)]


def _pfad_normal(wert):
    """Einen Eintrag aus der Datenbank auf die Form bringen, in der er
    unterhalb des Bestandsordners steht."""
    p = str(wert or "").replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def verweis_tabelle_finden(db, bestand):
    """Tabelle und Spalte suchen, in der die Zuordnung
    Arbeitsbereich -> Ablagedatei steht.

    ⛔ Das Schema wird NICHT geraten. Eine Spalte gilt erst dann als die
      richtige, wenn ihre Werte als Dateien unter dem Bestandsordner
      WIRKLICH existieren. Passt keine, wird das gemeldet und die Messung
      ist ungueltig - eine geratene Spalte wuerde jede Datei zur Waise
      erklaeren UND jeden Verweis fuer tot, und beides saehe aus wie ein
      dramatischer Befund.

    Rueckgabe: (tabelle, pfadspalte, bereichsspalte, treffer, form) oder None.
      form    = Werte, die wie ein Ablagepfad aussehen
      treffer = davon die, die es auf der Platte gibt
    """
    beste = None
    for t in _tabellen(db):
        if "document" not in t.lower():
            continue
        spalten = _spalten(db, t)
        bereichsspalte = None
        for name, _typ in spalten:
            if "workspace" in name.lower():
                bereichsspalte = name
                break
        if bereichsspalte is None:
            # Ohne Bezug zum Arbeitsbereich ist es die falsche Tabelle.
            continue
        for name, typ in spalten:
            if typ not in ("TEXT", "VARCHAR", "CLOB", ""):
                continue
            try:
                werte = [r[0] for r in db.execute(
                    'SELECT DISTINCT "%s" FROM "%s" LIMIT 2000' % (name, t))]
            except sqlite3.DatabaseError:
                continue
            form = 0
            treffer = 0
            for w in werte:
                p = _pfad_normal(w)
                if not p or "/" not in p or not p.lower().endswith(".json"):
                    continue
                form += 1
                if os.path.isfile(os.path.join(bestand, p)):
                    treffer += 1
            if form == 0:
                continue
            kandidat = (t, name, bereichsspalte, treffer, form)
            if beste is None or treffer > beste[3] or (
                    treffer == beste[3] and form > beste[4]):
                beste = kandidat
    return beste


def bereiche_zaehlen(db):
    """Wie viele Arbeitsbereiche kennt die Datenbank? -1 = keine Tabelle.

    Gebraucht fuer die Gegenprobe: Ohne Arbeitsbereich ist "niemand
    verweist darauf" keine Aussage ueber die Dateien, sondern ueber die
    Anlage.
    """
    for t in _tabellen(db):
        if t.lower() != "workspaces":
            continue
        try:
            return int(list(db.execute('SELECT COUNT(*) FROM "%s"' % t))[0][0])
        except (sqlite3.DatabaseError, IndexError, TypeError, ValueError):
            return -1
    return -1


# ------------------------------------------------------------- Die Messung

class Befund(object):
    """Alles, was gezaehlt wurde. Reine Zahlen - bis auf die Ordnernamen,
    die als Schluessel dienen."""

    def __init__(self):
        self.ordner = []              # Ablageordnernamen, sortiert
        self.dateien = {}             # Ordner -> Dateien insgesamt
        self.ablage = {}              # Ordner -> echte Ablagedateien
        self.verwiesen = {}           # Ordner -> davon mit Verweis
        self.waisen = {}              # Ordner -> davon ohne Verweis
        self.waisen_byte = {}         # Ordner -> Platz der Waisen
        self.groesste_waise = 0
        self.mit_schluessel = 0       # Waise mit Pfad-Schluessel, Quelle da
        self.verschollen = 0          # Waise mit Pfad-Schluessel, Quelle weg
        self.alter_name = 0           # Waise aus der Zeit vor dem Umbau
        self.fremde = 0               # .json ohne Kennung: nicht von der Ablage
        self.verweise = 0             # Verweise in der Datenbank insgesamt
        self.verweise_leer = {}       # Ordner -> Verweise ohne Datei
        self.verweise_leer_fremd = 0  # Verweise auf unbekannte Ordner
        self.bereiche = -1            # Arbeitsbereiche in der Datenbank

    def summe(self, feld):
        return sum(getattr(self, feld).values())


def ist_ablagedatei(dateiname):
    """Eine echte Ablagedatei von AnythingLLM - oder etwas Fremdes?

    Dieselbe Unterscheidung wie in pruef_proxy.nur_ueber_altweg(): An jeden
    Uploadnamen wird "-<kennung>.json" gehaengt. Wird davon nichts
    abgeschnitten, hat die Datei jemand anderes dort abgelegt - gefunden,
    weil die Pruefung ihren eigenen Katalog dort ablegte. Solche Dateien
    sind keine Waisen; sie gehoeren nur nicht dazu.
    """
    if not dateiname.endswith(".json"):
        return False
    return schluessel.ohne_uuid(dateiname) != dateiname[:-len(".json")]


def messen(bestand, verwiesene_pfade, abdruecke, bereichsnamen):
    """Der Zaehlkern. Nimmt fertige Mengen entgegen, damit er ohne Anlage
    und ohne Datenbank pruefbar ist (--gegenprobe)."""
    b = Befund()
    verwiesen_offen = set(verwiesene_pfade)

    for wurzel, _unter, dateien in os.walk(bestand):
        rel = os.path.relpath(wurzel, bestand).replace("\\", "/")
        teile = [t for t in rel.split("/") if t and t != "."]
        ordner = teile[0] if teile else WURZEL_MARKE
        for feld in (b.dateien, b.ablage, b.verwiesen, b.waisen, b.waisen_byte):
            feld.setdefault(ordner, 0)
        for d in dateien:
            if d.startswith("."):
                continue
            b.dateien[ordner] += 1
            if not ist_ablagedatei(d):
                b.fremde += 1
                continue
            b.ablage[ordner] += 1
            pfad = os.path.relpath(os.path.join(wurzel, d),
                                   bestand).replace("\\", "/")
            if pfad in verwiesen_offen:
                b.verwiesen[ordner] += 1
                verwiesen_offen.discard(pfad)
                continue

            # Eine Waise.
            b.waisen[ordner] += 1
            try:
                gross = os.path.getsize(os.path.join(wurzel, d))
            except OSError:
                gross = 0
            b.waisen_byte[ordner] += gross
            if gross > b.groesste_waise:
                b.groesste_waise = gross
            # Woher stammt sie? Gleiche Unterscheidung wie linkprobe.py:
            # Ein Pfad-Schluessel traegt einen Abdruck, den das
            # Abdruckverzeichnis kennt. Ist keiner bekannt, entscheidet der
            # Bereichsvorspann - ein alter Name ("DS-24-005") hat keinen.
            stamm = schluessel.ohne_uuid(d)
            if schluessel.abdruck_finden(stamm, abdruecke):
                b.mit_schluessel += 1
            elif any(stamm.startswith(n + "-") for n in bereichsnamen):
                b.verschollen += 1
            else:
                b.alter_name += 1

    b.ordner = sorted(b.dateien)
    # ⛔ Die andere Richtung: Was von den Verweisen uebrig bleibt, zeigt auf
    #   eine Datei, die es nicht gibt. Das ist der schlimmere Fall - er
    #   trifft bei JEDER Frage, nicht nur beim Platz.
    for p in sorted(verwiesen_offen):
        kopf = p.split("/")[0] if "/" in p else WURZEL_MARKE
        if kopf in b.dateien:
            b.verweise_leer[kopf] = b.verweise_leer.get(kopf, 0) + 1
        else:
            b.verweise_leer_fremd += 1
    b.verweise = len(verwiesene_pfade)
    return b


# ------------------------------------------------------------- Der Bericht

def berichten(b):
    """Zahlen ausgeben, danach sagen, ob die Messung gueltig war.
    Rueckgabe: 0 oder 1."""
    ERLAUBT["ordner"] = set(b.ordner) | {WURZEL_MARKE, FREMD_MARKE}

    sag("Ablageordner im Bestand               : %d", len(b.ordner))
    sag("Arbeitsbereiche laut Datenbank        : %d", b.bereiche)
    sag("Verweise Arbeitsbereich -> Ablagedatei: %d", b.verweise)
    sag_leer()
    sag("Je Ablageordner:           Dateien  Ablage  Verweis  WAISEN")
    for o in b.ordner:
        sag_ordner(o, "%7d %7d %8d %7d",
                   b.dateien.get(o, 0), b.ablage.get(o, 0),
                   b.verwiesen.get(o, 0), b.waisen.get(o, 0))
    sag("  zusammen                 %7d %7d %8d %7d",
        b.summe("dateien"), b.summe("ablage"),
        b.summe("verwiesen"), b.summe("waisen"))
    if b.fremde:
        sag("  nicht mitgezaehlt: %d .json ohne AnythingLLM-Kennung - die "
            "hat jemand anderes dort abgelegt", b.fremde)
    sag_leer()

    waisen = b.summe("waisen")
    sag("WAISEN (Datei da, kein Arbeitsbereich verweist darauf): %d", waisen)
    sag("  mit Pfad-Schluessel, Quelldatei vorhanden  : %6d", b.mit_schluessel)
    sag("  mit Pfad-Schluessel, Quelldatei verschollen: %6d", b.verschollen)
    sag("  mit altem Namen (vor dem Umbau)            : %6d", b.alter_name)
    sag("  Platz zusammen: %.1f MB, groesste einzelne: %.1f MB",
        b.summe("waisen_byte") / 1048576.0, b.groesste_waise / 1048576.0)
    sag_leer()

    leer = sum(b.verweise_leer.values()) + b.verweise_leer_fremd
    sag("TREFFER INS LEERE (Arbeitsbereich verweist, Datei fehlt): %d", leer)
    for o in sorted(b.verweise_leer):
        sag_ordner(o, "%7d", b.verweise_leer[o])
    if b.verweise_leer_fremd:
        sag_ordner(FREMD_MARKE, "%7d", b.verweise_leer_fremd)
    sag_leer()

    # ⛔ Die Gegenprobe. Ohne sie sagt "0 Waisen" nichts: Sie waere auch
    #   dann 0, wenn der Bestand leer ist, wenn es keinen Arbeitsbereich
    #   gibt, oder wenn eine falsch geratene Spalte jede Datei als
    #   verwiesen erscheinen liesse.
    if not b.ordner:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Es gibt keinen einzigen "
            "Ablageordner. Dann wurde der falsche Ordner gemessen - "
            "KI4KI_BESTAND pruefen.")
        return 1
    if b.summe("ablage") == 0:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Keine einzige Ablagedatei. "
            "'Keine Waisen' hiesse dann nur, dass es ueberhaupt nichts "
            "gibt, was verwaisen koennte.")
        return 1
    if b.bereiche <= 0:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Die Datenbank nennt keinen "
            "einzigen Arbeitsbereich. Dann ist 'niemand verweist darauf' "
            "keine Aussage ueber die Dateien, sondern ueber die Anlage.")
        return 1
    if b.summe("verwiesen") == 0:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Kein einziger Verweis trifft "
            "eine vorhandene Datei. Entweder wurde die falsche Spalte "
            "gelesen, oder der ganze Bestand haengt ab - beides muss ein "
            "Mensch ansehen, bevor irgendjemand diese Waisenzahl glaubt.")
        return 1
    sag("Messung gueltig: %d Verweise treffen eine vorhandene Datei - die "
        "Unterscheidung Waise/verwiesen trifft also wirklich.",
        b.summe("verwiesen"))
    sag_leer()

    if waisen:
        sag("⛔ %d Ablagedatei(en) liegen im Bestand, ohne dass ein "
            "Arbeitsbereich darauf verweist.", waisen)
        sag("   Das ist nicht nur Platz: veredeln.Bestand liest den GANZEN "
            "Bestandsordner ein, und nur_ueber_altweg() zaehlt hier mit.")
        sag("   ⛔ NICHT loeschen, bevor die Aufteilung oben geklaert ist. "
            "Eine Waise mit vorhandener Quelldatei kann auch ein Dokument "
            "sein, das aufgenommen, aber nie eingebettet wurde - das "
            "gehoert eingebettet, nicht geloescht.")
    else:
        sag("Keine Waise. Waechst nur_altweg trotzdem, liegt es NICHT an "
            "herumliegenden Ablagedateien - dann dort weitersuchen, wo die "
            "Abdruecke entstehen (pdfs_einlesen).")
    if leer:
        sag("⛔ %d Verweis(e) zeigen auf eine Datei, die es nicht gibt. Das "
            "trifft bei JEDER Frage: Der Arbeitsbereich fuehrt das "
            "Dokument, die Textfassung fehlt.", leer)
    return 0


# ---------------------------------------------------------------- Der Lauf

def main():
    maengel, _stellen = datensperre_pruefen()
    if maengel:
        sag("⛔ DIE DATENSPERRE IST VERLETZT: %d Ausgabestelle(n) im "
            "eigenen Quelltext koennen mehr als Zahlen ausgeben.",
            len(maengel))
        for z in maengel:
            sag("   Zeile %d", z)
        sag("Es wird nichts gemessen.")
        return 1

    try:
        import pruef_proxy as p
    except ImportError:
        # Der haeufigste Bedienfehler, und er soll nicht als
        # "unerwarteter Abbruch" enden: Das Skript wurde auf dem HOST
        # gestartet. Dort gibt es weder pruef_proxy noch den Bestand -
        # der liegt in einem Docker-Volume.
        sag("⛔ DIE MESSUNG IST UNGUELTIG: pruef_proxy ist nicht zu "
            "importieren. Dieses Skript gehoert IN den Proxy-Container:")
        sag("     docker cp bau/waisenprobe.py "
            "ki4ki-pruef-proxy:/app/waisenprobe.py")
        sag("     docker exec ki4ki-pruef-proxy python3 /app/waisenprobe.py")
        sag("   Ohne Anlage laeuft nur --gegenprobe; die braucht nichts.")
        return 1

    bestand = p.BESTAND_ORDNER
    if not os.path.isdir(bestand):
        sag("Der Bestandsordner ist nicht da - DIE MESSUNG IST UNGUELTIG.")
        sag("   Dieses Skript gehoert IN den Proxy-Container; dort haengt "
            "das AnythingLLM-Volume unter /daten/bestand.")
        return 1

    # Das Abdruckverzeichnis - genau wie linkprobe.py es aufbaut. Ohne
    # diesen Aufruf ist PDFS_ABDRUCK leer, und JEDE Waise saehe nach
    # "alter Name" aus: eine Messung, die einen Fehler als Normalzustand
    # verbucht.
    p.pdfs_einlesen()
    abdruecke = p.PDFS_ABDRUCK
    if not abdruecke:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Das Abdruckverzeichnis ist leer. "
            "Jede Waise wuerde als 'alter Name' gezaehlt, auch die mit "
            "Pfad-Schluessel - und niemand saehe es der Zahl an.")
        return 1

    # Bereichsnamen aus BEIDEN Quellen: dem Eingang (wie linkprobe) und den
    # Ablageordnern. bereich.json darf die Ablage anders nennen als den
    # Bereich (pruef_proxy.ablage_sicherstellen); nur die Vereinigung
    # verhindert, dass ein echter Pfad-Schluessel als alter Name gilt.
    bereichsnamen = set()
    for ort in (p.EINGANG_ORDNER, bestand):
        try:
            for n in os.listdir(ort):
                if os.path.isdir(os.path.join(ort, n)):
                    bereichsnamen.add(n)
        except OSError:
            pass

    speicher = os.path.dirname(os.path.abspath(bestand))
    kandidaten = db_kandidaten(speicher)
    if not kandidaten:
        sag("⛔ DIE MESSUNG IST UNGUELTIG: Im Speicherordner liegt keine "
            "SQLite-Datei. Ohne sie ist die Zuordnung Datei -> "
            "Arbeitsbereich nicht zu lesen, und JEDE Datei saehe aus wie "
            "eine Waise. Notfalls KI4KI_ANYTHINGLLM_DB setzen.")
        return 1

    arbeitsordner = tempfile.mkdtemp(prefix="waisenprobe-")
    try:
        gewaehlt = None
        for k in kandidaten:
            try:
                db = db_kopie_oeffnen(k, arbeitsordner)
            except (OSError, sqlite3.DatabaseError):
                continue
            fund = None
            try:
                fund = verweis_tabelle_finden(db, bestand)
            except sqlite3.DatabaseError:
                fund = None
            if fund is not None:
                gewaehlt = (db, fund)
                break
            db.close()
        if gewaehlt is None:
            sag("⛔ DIE MESSUNG IST UNGUELTIG: In keiner der %d gefundenen "
                "SQLite-Dateien steht eine Tabelle, die einen "
                "Arbeitsbereich mit einem Ablagepfad verbindet.",
                len(kandidaten))
            sag("   Das Schema wird hier bewusst nicht geraten. Eine "
                "geratene Spalte wuerde jede Datei zur Waise erklaeren - "
                "ein Befund, der falsch ist und dramatisch aussieht.")
            return 1

        db, (tabelle, pfadspalte, _bereichsspalte, treffer, form) = gewaehlt
        sag("Datenbank gelesen (aus einer Kopie): In der Stichprobe liegen "
            "%d von %d Pfadeintraegen wirklich auf der Platte.",
            treffer, form)
        if treffer == 0:
            sag("⛔ DIE MESSUNG IST UNGUELTIG: Kein einziger Pfadeintrag "
                "der Stichprobe ist auf der Platte zu finden. Entweder ist "
                "es die falsche Spalte, oder jeder Verweis ist tot.")
            return 1
        sag_leer()

        pfade = set()
        for zeile in db.execute('SELECT "%s" FROM "%s"'
                                % (pfadspalte, tabelle)):
            p_ = _pfad_normal(zeile[0])
            if p_:
                pfade.add(p_)
        b = messen(bestand, pfade, abdruecke, bereichsnamen)
        b.bereiche = bereiche_zaehlen(db)
        db.close()
        return berichten(b)
    finally:
        shutil.rmtree(arbeitsordner, ignore_errors=True)


# ------------------------------------------------------------- Gegenprobe
#
# ⭐ Hausregel: Zu jeder Pruefung gehoert der Nachweis, mit WELCHER Eingabe
#   sie rot wird. Hier ist er ausfuehrbar und braucht keine Anlage: ein
#   Baukasten-Bestand mit von Hand ausgerechnetem Ergebnis, daneben die
#   Faelle, in denen sich die Probe fuer ungueltig erklaeren MUSS. Faellt
#   einer davon aus, endet die Gegenprobe mit 1.

_UUID_A = "11111111-2222-3333-4444-555555555555"
_UUID_B = "66666666-7777-8888-9999-aaaaaaaaaaaa"


def _baukasten(ort, ordner_zu_dateien):
    for ordner in ordner_zu_dateien:
        os.makedirs(os.path.join(ort, ordner), exist_ok=True)
        for n, inhalt in ordner_zu_dateien[ordner]:
            with open(os.path.join(ort, ordner, n), "w",
                      encoding="utf-8") as fh:
                fh.write(inhalt)


def _db_baukasten(pfad, pfadliste, bereiche, nur_basisnamen=False):
    """Eine SQLite-Datei bauen, die aussieht wie die von AnythingLLM -
    mitsamt Lockvoegeln: eine Tabelle OHNE Bezug zum Arbeitsbereich und
    eine Spalte, die nur den Dateinamen fuehrt. Beide muessen liegen
    bleiben, sonst zaehlt die Probe die falsche Spalte."""
    db = sqlite3.connect(pfad)
    db.execute("CREATE TABLE workspaces "
               "(id INTEGER PRIMARY KEY, name TEXT, slug TEXT)")
    for i in range(bereiche):
        db.execute("INSERT INTO workspaces (id, name, slug) VALUES (?,?,?)",
                   (i + 1, "Bereich", "bereich"))
    db.execute("CREATE TABLE document_vectors "
               "(id INTEGER PRIMARY KEY, docId TEXT, vectorId TEXT)")
    db.execute("CREATE TABLE workspace_documents "
               "(id INTEGER PRIMARY KEY, docId TEXT, filename TEXT, "
               "docpath TEXT, workspaceId INTEGER, metadata TEXT)")
    for i, p in enumerate(sorted(pfadliste)):
        basis = p.split("/")[-1]
        db.execute("INSERT INTO workspace_documents (id, docId, filename, "
                   "docpath, workspaceId, metadata) VALUES (?,?,?,?,?,?)",
                   (i + 1, "doc-%d" % (i + 1), basis,
                    basis if nur_basisnamen else p, 1,
                    '{"title": "Titel", "wordCount": 100}'))
        db.execute("INSERT INTO document_vectors (id, docId, vectorId) "
                   "VALUES (?,?,?)", (i + 1, "doc-%d" % (i + 1), "v%d" % i))
    db.commit()
    db.close()


def _stumm_berichten(b):
    """berichten() laufen lassen, ohne den Bildschirm vollzuschreiben.
    Nur in der Gegenprobe - gemessen wird die RUECKGABE."""
    import io
    merk = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return berichten(b)
    finally:
        sys.stdout = merk


def gegenprobe():
    ERLAUBT["ordner"] = {"bereicha", "bereichb", "custom-documents",
                         WURZEL_MARKE, FREMD_MARKE}
    abdruecke = {"abcdefghij", "bbbbbbbbbb", "cccccccccc", "dddddddddd"}
    bereichsnamen = {"bereicha", "bereichb"}
    fehler = [0]

    def gleich(ist, soll):
        if ist != soll:
            fehler[0] += 1
        return (ist, soll)

    ort = tempfile.mkdtemp(prefix="waisenprobe-gegenprobe-")
    try:
        # --- Fall 1: Bestand mit von Hand ausgerechnetem Ergebnis.
        #     9 Ablagedateien + 1 fremde .json; 4 verwiesen, 5 Waisen;
        #     6 Verweise, davon 2 ins Leere (einer in einen Ordner, den es
        #     gar nicht gibt).
        bestand = os.path.join(ort, "documents")
        _baukasten(bestand, {
            "bereicha": [
                ("bereicha-Akte-A--abcdefghij.md-%s.json" % _UUID_A, "x" * 1000),
                ("bereicha-Akte-B--bbbbbbbbbb.md-%s.json" % _UUID_A, "x" * 1000),
                ("bereicha-Akte-C--cccccccccc.md-%s.json" % _UUID_A, "x" * 1000),
            ],
            "bereichb": [
                ("bereichb-Akte-D--dddddddddd.md-%s.json" % _UUID_A, "x" * 1000),
                ("DS-24-005.md-%s.json" % _UUID_A, "x" * 2000),
            ],
            "custom-documents": [
                ("bereicha-Akte-A--abcdefghij.md-%s.json" % _UUID_B, "x" * 3000),
                ("bereicha-Akte-B--bbbbbbbbbb.md-%s.json" % _UUID_B, "x" * 1000),
                ("bereicha-Akte-X--zzzzzzzzzz.md-%s.json" % _UUID_B, "x" * 1000),
                ("DS-24-006.md-%s.json" % _UUID_B, "x" * 1000),
                ("eigener-katalog.json", "x" * 10),
            ],
        })
        verweise = set([
            "bereicha/bereicha-Akte-A--abcdefghij.md-%s.json" % _UUID_A,
            "bereicha/bereicha-Akte-B--bbbbbbbbbb.md-%s.json" % _UUID_A,
            "bereicha/bereicha-Akte-C--cccccccccc.md-%s.json" % _UUID_A,
            "bereichb/bereichb-Akte-D--dddddddddd.md-%s.json" % _UUID_A,
            "bereicha/laengst-geloescht--eeeeeeeeee.md-%s.json" % _UUID_A,
            "weg-mit-dem-ordner/auch-weg--ffffffffff.md-%s.json" % _UUID_A,
        ])
        b = messen(bestand, verweise, abdruecke, bereichsnamen)
        b.bereiche = 2
        sag("Fall 1 - Baukasten mit von Hand ausgerechnetem Ergebnis:")
        sag("   Dateien insgesamt           %5d (erwartet %d)",
            *gleich(b.summe("dateien"), 10))
        sag("   echte Ablagedateien         %5d (erwartet %d)",
            *gleich(b.summe("ablage"), 9))
        sag("   fremde .json                %5d (erwartet %d)",
            *gleich(b.fremde, 1))
        sag("   mit Verweis                 %5d (erwartet %d)",
            *gleich(b.summe("verwiesen"), 4))
        sag("   Waisen                      %5d (erwartet %d)",
            *gleich(b.summe("waisen"), 5))
        sag("   davon in custom-documents   %5d (erwartet %d)",
            *gleich(b.waisen.get("custom-documents", 0), 4))
        sag("   Pfad-Schluessel, Quelle da  %5d (erwartet %d)",
            *gleich(b.mit_schluessel, 2))
        sag("   Pfad-Schluessel verschollen %5d (erwartet %d)",
            *gleich(b.verschollen, 1))
        sag("   alter Name                  %5d (erwartet %d)",
            *gleich(b.alter_name, 2))
        sag("   Treffer ins Leere           %5d (erwartet %d)",
            *gleich(sum(b.verweise_leer.values()) + b.verweise_leer_fremd, 2))
        sag("   davon in unbekanntem Ordner %5d (erwartet %d)",
            *gleich(b.verweise_leer_fremd, 1))
        # 2000 (DS-24-005 in bereichb) + 3000 + 1000 + 1000 + 1000
        # (custom-documents) = 8000. Die erste Fassung stand hier auf 6000,
        # weil die Waise in bereichb beim Nachrechnen vergessen wurde - die
        # Gegenprobe hat den Rechenfehler gefunden, nicht das Skript.
        sag("   Platz der Waisen in Byte    %5d (erwartet %d)",
            *gleich(b.summe("waisen_byte"), 8000))
        sag("   groesste Waise in Byte      %5d (erwartet %d)",
            *gleich(b.groesste_waise, 3000))
        sag_leer()

        # --- Fall 2: dieselben Dateien, aber jede verwiesen. Der Nachweis,
        #     dass die Zahl nicht einfach immer gross ist.
        alles = set()
        for w, _u, dat in os.walk(bestand):
            for d in dat:
                if ist_ablagedatei(d):
                    alles.add(os.path.relpath(os.path.join(w, d),
                                              bestand).replace("\\", "/"))
        b2 = messen(bestand, alles, abdruecke, bereichsnamen)
        b2.bereiche = 2
        sag("Fall 2 - dieselben Dateien, jede verwiesen:")
        sag("   Waisen %d (erwartet 0), Treffer ins Leere %d (erwartet 0)",
            b2.summe("waisen"),
            sum(b2.verweise_leer.values()) + b2.verweise_leer_fremd)
        if b2.summe("waisen") or b2.verweise_leer or b2.verweise_leer_fremd:
            fehler[0] += 1
            sag("   ⛔ falsch.")
        else:
            sag("   richtig - die Probe wird gruen, wenn nichts zu melden ist.")
        sag_leer()

        # --- Fall 3: Bestandsordner ohne Ablageordner.
        leerer = os.path.join(ort, "leer")
        os.makedirs(leerer, exist_ok=True)
        b3 = messen(leerer, set(), abdruecke, bereichsnamen)
        b3.bereiche = 2
        sag("Fall 3 - Bestandsordner ohne Ablageordner:")
        if _stumm_berichten(b3) == 1:
            sag("   richtig ungueltig (Rueckgabe 1) statt '0 Waisen'.")
        else:
            fehler[0] += 1
            sag("   ⛔ falsch: haette 0 Waisen gemeldet.")
        sag_leer()

        # --- Fall 4: Dateien da, aber KEIN Verweis trifft eine davon.
        #     Genau der Fall, in dem eine geratene Spalte "1.224 Waisen"
        #     melden wuerde.
        b4 = messen(bestand,
                    set(["nichts/passt--gggggggggg.md-%s.json" % _UUID_A]),
                    abdruecke, bereichsnamen)
        b4.bereiche = 2
        sag("Fall 4 - Dateien da, kein Verweis trifft eine davon:")
        if _stumm_berichten(b4) == 1:
            sag("   richtig ungueltig (Rueckgabe 1).")
        else:
            fehler[0] += 1
            sag("   ⛔ falsch: haette jede Datei zur Waise erklaert.")
        sag_leer()

        # --- Fall 5: alles in Ordnung, aber kein Arbeitsbereich.
        b5 = messen(bestand, verweise, abdruecke, bereichsnamen)
        b5.bereiche = 0
        sag("Fall 5 - kein Arbeitsbereich in der Datenbank:")
        if _stumm_berichten(b5) == 1:
            sag("   richtig ungueltig (Rueckgabe 1).")
        else:
            fehler[0] += 1
            sag("   ⛔ falsch.")
        sag_leer()

        # --- Fall 6: die Datensperre selbst, an einem absichtlich
        #     undichten Quelltext. Drei Lecks, drei Beanstandungen.
        probe = os.path.join(ort, "leck.py")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("def sag(v, *z):\n"
                     "    print(v % z)\n"
                     "\n"
                     "def zeigen(name):\n"
                     "    print(name)\n"
                     "    sag('Datei ' + name)\n"
                     "    sag(f'{name}')\n")
        maengel, _s = datensperre_pruefen(probe)
        sag("Fall 6 - Datensperre an einem undichten Quelltext:")
        sag("   Beanstandungen %d (erwartet %d)", *gleich(len(maengel), 3))
        if len(maengel) == 3:
            sag("   richtig: nacktes print(), zusammengesetzte Vorlage und "
                "f-String werden alle drei gefunden.")
        eigene, stellen = datensperre_pruefen()
        sag("   am eigenen Quelltext: %d Beanstandung(en) bei %d "
            "Ausgabestellen (erwartet 0)", len(eigene), stellen)
        if eigene:
            fehler[0] += 1
        sag_leer()

        # --- Fall 7: Die Datensperre haelt auch zur Laufzeit. sag_ordner()
        #     muss einen Namen zurueckweisen, der kein Ablageordner ist -
        #     das ist die Sperre gegen Dateinamen in der Ausgabe.
        sag("Fall 7 - sag_ordner() mit einem Namen, der kein Ablageordner ist:")
        abgewiesen = 0
        try:
            sag_ordner("irgendeine-datei.md-x.json", "%d", 1)
        except ValueError:
            abgewiesen = 1
        sag("   abgewiesen: %d (erwartet %d)", *gleich(abgewiesen, 1))
        gelaufen = 0
        try:
            sag_ordner("bereicha", "%d", 1)
            gelaufen = 1
        except ValueError:
            gelaufen = 0
        sag("   erlaubter Ordner durchgelassen: %d (erwartet %d)",
            *gleich(gelaufen, 1))
        sag_leer()

        # --- Fall 8: der Weg durch die Datenbank. Das ist der Teil, den
        #     kein Blick in den Quelltext des Proxys belegen kann - also
        #     wird er hier an einer gebauten Datenbank vorgefuehrt, mit
        #     denselben Lockvoegeln, die auch in der echten stehen.
        dbdatei = os.path.join(ort, "anythingllm.db")
        _db_baukasten(dbdatei, verweise, 2)
        sag("Fall 8 - Zuordnung aus einer SQLite-Datei lesen, ohne Netz:")
        kand = db_kandidaten(ort)
        sag("   SQLite-Dateien gefunden        %5d (erwartet %d)",
            *gleich(len(kand), 1))
        arbeit = tempfile.mkdtemp(prefix="waisenprobe-db-")
        try:
            db = db_kopie_oeffnen(dbdatei, arbeit)
            fund = verweis_tabelle_finden(db, bestand)
            sag("   Tabelle gefunden               %5d (erwartet %d)",
                *gleich(1 if fund else 0, 1))
            if fund:
                _t, spalte, _bs, treffer, form = fund
                sag("   Pfadspalte richtig gewaehlt    %5d (erwartet %d)",
                    *gleich(1 if spalte == "docpath" else 0, 1))
                sag("   Eintraege in Pfadform          %5d (erwartet %d)",
                    *gleich(form, 6))
                sag("   davon auf der Platte           %5d (erwartet %d)",
                    *gleich(treffer, 4))
            sag("   Arbeitsbereiche gezaehlt       %5d (erwartet %d)",
                *gleich(bereiche_zaehlen(db), 2))
            # Und jetzt der ganze Weg: Datenbank -> Mengen -> Zaehlkern.
            gelesen = set()
            for zeile in db.execute("SELECT docpath FROM workspace_documents"):
                gelesen.add(_pfad_normal(zeile[0]))
            b8 = messen(bestand, gelesen, abdruecke, bereichsnamen)
            b8.bereiche = bereiche_zaehlen(db)
            db.close()
            sag("   Waisen ueber den ganzen Weg    %5d (erwartet %d)",
                *gleich(b8.summe("waisen"), 5))
            sag("   Treffer ins Leere              %5d (erwartet %d)",
                *gleich(sum(b8.verweise_leer.values())
                        + b8.verweise_leer_fremd, 2))
            sag("   Rueckgabe des Berichts         %5d (erwartet %d)",
                *gleich(_stumm_berichten(b8), 0))
        finally:
            shutil.rmtree(arbeit, ignore_errors=True)
        sag_leer()

        # --- Fall 9: eine Datenbank, in der KEINE Spalte einen Ablagepfad
        #     fuehrt (nur Dateinamen). Die Probe muss sich weigern, statt
        #     die naechstbeste Spalte zu nehmen - sonst waere jede Datei
        #     eine Waise und jeder Verweis tot.
        db9datei = os.path.join(ort, "nur-namen.db")
        _db_baukasten(db9datei, verweise, 2, nur_basisnamen=True)
        arbeit9 = tempfile.mkdtemp(prefix="waisenprobe-db9-")
        try:
            db9 = db_kopie_oeffnen(db9datei, arbeit9)
            fund9 = verweis_tabelle_finden(db9, bestand)
            db9.close()
        finally:
            shutil.rmtree(arbeit9, ignore_errors=True)
        sag("Fall 9 - Datenbank ohne Pfadspalte (nur Dateinamen):")
        sag("   Tabelle gewaehlt               %5d (erwartet %d)",
            *gleich(1 if fund9 else 0, 0))
        if fund9 is None:
            sag("   richtig: lieber keine Messung als eine geratene Spalte.")
        sag_leer()
    finally:
        shutil.rmtree(ort, ignore_errors=True)

    if fehler[0]:
        sag("⛔ GEGENPROBE FEHLGESCHLAGEN: %d Punkt(e) stimmen nicht. Dem "
            "Messwerkzeug ist nicht zu trauen.", fehler[0])
        return 1
    sag("Gegenprobe bestanden: Der Zaehlkern trifft ein bekanntes Ergebnis, "
        "meldet bei heilem Bestand 0, erklaert sich in drei verschiedenen "
        "Ausfaellen fuer ungueltig, und die Datensperre haelt im Quelltext "
        "wie zur Laufzeit.")
    return 0


if __name__ == "__main__":
    _arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if _arg == "--gegenprobe":
            sys.exit(gegenprobe())
        if _arg == "--datensperre":
            _m, _s = datensperre_pruefen()
            sag("Ausgabestellen geprueft: %d, Beanstandungen: %d",
                _s, len(_m))
            for _z in _m:
                sag("   Zeile %d", _z)
            sys.exit(1 if _m else 0)
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # ⛔ Kein Traceback: Der nennt Pfade. Die Zeilennummer reicht, um
        #   die Stelle zu finden, und ist eine Zahl.
        _tb = sys.exc_info()[2]
        _zeile = 0
        while _tb is not None:
            _zeile = _tb.tb_lineno
            _tb = _tb.tb_next
        sag("⛔ Unerwarteter Abbruch in Zeile %d - DIE MESSUNG IST "
            "UNGUELTIG.", _zeile)
        sys.exit(1)
