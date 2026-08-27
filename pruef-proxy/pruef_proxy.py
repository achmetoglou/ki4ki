#!/usr/bin/env python3
"""
Pruef-Proxy - die Belegpruefung direkt in der AnythingLLM-Oberflaeche.

Bisher lief die Pruefung in einem eigenen Fenster. Das ist fuer Netzwerk-
partner das falsche Gefaess: Niemand oeffnet zwei Reiter. Also derselbe
Kniff, den dieser Stack schon zwischen AnythingLLM und Ollama benutzt
(nothink-proxy), nur eine Etage hoeher.

    Browser  ->  Pruef-Proxy  ->  AnythingLLM  ->  Ollama
                      |
                      +-- faengt die Antwort ab, schlaegt jedes Zitat
                          im Quelltext nach, setzt den Original-Wortlaut
                          ein und haengt Dokument + Seite als Verweis an.

Alles andere - Oberflaeche, Anmeldung, Einstellungen - wird unveraendert
durchgereicht. AnythingLLM selbst bleibt unangetastet (kein Fork).

  ./pruef_proxy.py                hoert auf 0.0.0.0:3000, reicht an :3001
  ./pruef_proxy.py --port 3000 --ziel http://127.0.0.1:3001
"""
import argparse
import glob
import binascii
import hashlib
import hmac
import html
import json
import namen as namen_pruefen
import os
import re
import sqlite3
import subprocess
import sys
import time
import threading
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assistent
import absicht
import fadenfrage
import gespraech as gespraechsmodus   # nicht 'gespraech': so heisst die Faden-Kennung in _chat
import metadaten
import stoerfall
import pruefungskatalog
import rolle
import kategorie
import mehrstufig
import pdfstelle
import pruefprotokoll
import veredeln
import wortsuche

ZIEL = os.environ.get("KI4KI_ZIEL") or "http://127.0.0.1:3001"

# ============================================================================
#  KI4KI-BEREICH-HEILEN: Ein NEU angelegter Arbeitsbereich bekommt sofort die
#  gepruef-ten Werte (Prompt, Modus "query", topN/Schwelle/Verlauf/Temperatur)
#  - egal ob per Skript oder per Klick in der Oberflaeche. So ist jeder neue
#  Bereich von Geburt an beleg-faehig. BESTEHENDE Bereiche werden NIE
#  angefasst (der Haken sitzt nur am Anlegen). Fehlt der API-Schluessel oder
#  steht KI4KI_BEREICH_HEILEN=0, laeuft das Anlegen unveraendert durch.
# ============================================================================
API_SCHLUESSEL = (os.environ.get("KI4KI_API_KEY") or "").strip()
BEREICH_HEILEN = (os.environ.get("KI4KI_BEREICH_HEILEN", "1") != "0")
ROLLE_GLAETTEN = (os.environ.get("KI4KI_ROLLE_GLAETTEN", "1") != "0")   # Rolle vom Modell formulieren lassen
SYSTEMPROMPT_DATEI = (os.environ.get("KI4KI_SYSTEMPROMPT")
                      or "/systemprompt.txt")
# Muss mit arbeitsbereich_anlegen.sh uebereinstimmen - die eine Wahrheit
# fuer einen frisch angelegten Bereich.
GEPRUEFT_WERTE = {
    "chatMode": "query",
    "topN": 25,              # gemessen T4 04.08.: 25 > 9 > 100 (siehe arbeitsbereich_anlegen.sh)
    "similarityThreshold": 0.25,
    "openAiHistory": 20,     # 27.08.: 6 vergass das Gespraech nach drei Fragen
    "openAiTemp": 0.2,
}
_SYSTEMPROMPT = {"text": None, "wann": 0.0}


def _systemprompt_lesen():
    jetzt = time.time()
    if _SYSTEMPROMPT["text"] is not None and jetzt - _SYSTEMPROMPT["wann"] < 300:
        return _SYSTEMPROMPT["text"]
    try:
        with open(SYSTEMPROMPT_DATEI, encoding="utf-8") as fh:
            _SYSTEMPROMPT["text"] = fh.read()
    except Exception as e:
        print("[Bereich] systemprompt nicht lesbar (%s): %s"
              % (SYSTEMPROMPT_DATEI, str(e)[:120]), file=sys.stderr, flush=True)
        _SYSTEMPROMPT["text"] = None
    _SYSTEMPROMPT["wann"] = jetzt
    return _SYSTEMPROMPT["text"]


_ROLLEN_STAND = {}      # slug -> (mtime_ns, size) der eingespielten prompt.md
_MODUS_JE_BEREICH = {}  # slug -> (chatMode, wann)


def _bereich_modus(slug):
    """chatMode des Bereichs aus AnythingLLM (query/chat/automatic), 5 min gemerkt."""
    if not slug or not API_SCHLUESSEL:
        return "query"
    alt = _MODUS_JE_BEREICH.get(slug)
    if alt and time.time() - alt[1] < 300:
        return alt[0]
    modus = "query"
    try:
        w = (_api("GET", "/api/v1/workspace/%s" % slug, timeout=15) or {}).get("workspace")
        w = w[0] if isinstance(w, list) else (w or {})
        modus = str(w.get("chatMode") or "query")
    except Exception:
        pass
    _MODUS_JE_BEREICH[slug] = (modus, time.time())
    return modus
_ADMINS = {"wann": 0.0, "namen": set()}


def _ist_admin(kopfzeilen):
    """Hat dieses Konto in AnythingLLM die Admin-Rolle? (Liste alle 5 min
    ueber den Anlagen-Schluessel; ohne Schluessel: nein.)"""
    if not API_SCHLUESSEL:
        return False
    if time.time() - _ADMINS["wann"] > 300:
        try:
            d = _api("GET", "/api/v1/admin/users", timeout=15) or {}
            _ADMINS["namen"] = {str(u.get("username")) for u in (d.get("users") or []) if u.get("role") == "admin"}
        except Exception:
            pass
        _ADMINS["wann"] = time.time()
    return konto_aus_anfrage(kopfzeilen) in _ADMINS["namen"]


def _darf_rolle_setzen(kopfzeilen):
    konto = pruefprotokoll.pseudonym(konto_aus_anfrage(kopfzeilen))
    return pruefprotokoll.darf_einsehen(konto) or _ist_admin(kopfzeilen)


def _rolle_lesen(slug):
    """Text von dokumente/<slug>/prompt.md - oder ''."""
    if not slug:
        return ""
    try:
        with open(os.path.join(EINGANG_ORDNER, _ordnername(slug), rolle.DATEI), encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def _rolle_schreiben(slug, text):
    wurzel = os.path.join(EINGANG_ORDNER, _ordnername(slug))
    os.makedirs(wurzel, exist_ok=True)
    pfad = os.path.join(wurzel, rolle.DATEI)
    with open(pfad + ".neu", "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(pfad + ".neu", pfad)
    try:
        os.chown(pfad, 1000, int(os.environ.get("KI4KI_GID") or 1000))
        os.chmod(pfad, 0o664)
    except Exception:
        pass
    return pfad


def _bereich_konf(slug):
    try:
        with open(os.path.join(EINGANG_ORDNER, _ordnername(slug), "bereich.json"), encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _bereich_konf_schreiben(slug, konf):
    try:
        pfad = os.path.join(EINGANG_ORDNER, _ordnername(slug), "bereich.json")
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad + ".neu", "w", encoding="utf-8") as fh:
            json.dump(konf, fh, ensure_ascii=False, indent=1)
        os.replace(pfad + ".neu", pfad)
        try:
            os.chown(pfad, 1000, int(os.environ.get("KI4KI_GID") or 1000))
            os.chmod(pfad, 0o664)
        except Exception:
            pass
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _rolle_aus_oberflaeche(slug, prompt):
    """Der Mensch hat den Prompt in den Einstellungen gespeichert: den
    Rollen-Abschnitt daraus in prompt.md uebernehmen, damit Datei und
    Gespraechsmodus mitziehen - und den Stand merken, damit der 5-Minuten-
    Abgleich die Oberflaeche NICHT zurueck ueberschreibt."""
    text = rolle.aus_prompt(prompt)
    if not text.strip():
        return False
    alt = _rolle_lesen(slug)
    if alt.strip() == text.strip():
        return False
    _rolle_schreiben(slug, text)
    pfad = os.path.join(EINGANG_ORDNER, _ordnername(slug), rolle.DATEI)
    try:
        st = os.stat(pfad)
        _ROLLEN_STAND[slug] = (st.st_mtime_ns, st.st_size)
    except OSError:
        pass
    print("[Rolle] '%s': Rolle aus den Einstellungen der Oberflaeche uebernommen (%d Zeichen)" % (slug, len(text)),
          file=sys.stderr, flush=True)
    return True


def _prompt_fuer_bereich(slug):
    """Kern (systemprompt.txt) + Rolle (prompt.md) - der eine Prompt eines Bereichs."""
    return rolle.zusammensetzen(_systemprompt_lesen() or "", _rolle_lesen(slug))


def _rolle_einspielen(slug, erzwingen=False):
    """prompt.md geaendert? -> Prompt in AnythingLLM nachziehen. True = eingespielt."""
    if not (API_SCHLUESSEL and slug):
        return False
    pfad = os.path.join(EINGANG_ORDNER, _ordnername(slug), rolle.DATEI)
    try:
        st = os.stat(pfad)
        stempel = (st.st_mtime_ns, st.st_size)
    except OSError:
        stempel = None
    if not erzwingen and _ROLLEN_STAND.get(slug) == stempel:
        return False
    try:
        _api("POST", "/api/v1/workspace/%s/update" % slug, {"openAiPrompt": _prompt_fuer_bereich(slug)}, timeout=30)
        _ROLLEN_STAND[slug] = stempel
        print("[Rolle] '%s': Prompt eingespielt (%s)" % (
            slug, "Rolle eingerichtet" if rolle.ist_eingerichtet(_rolle_lesen(slug)) else "nur Kern"),
            file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print("[Rolle] '%s' nicht eingespielt: %s" % (slug, str(e)[:120]), file=sys.stderr, flush=True)
        return False


def bereich_setzen(slug):
    """Schreibt die gepruef-ten Werte in einen frisch angelegten Bereich."""
    if not (BEREICH_HEILEN and API_SCHLUESSEL and slug):
        return False
    werte = dict(GEPRUEFT_WERTE)
    # Hat das Formular seinen Modus schon abgelegt (Wettlauf: die Oberflaeche
    # schickt /rolle, waehrend hier noch abgesichert wird), gewinnt der Modus
    # des Menschen - sonst stand "Vertreter" oder "Chat" kurz danach wieder
    # auf "Abfrage" (gemessen 27.08.).
    _modus = (_bereich_konf(slug).get("rolle") or {}).get("modus")
    if _modus in rolle.MODI:
        werte["chatMode"] = _modus
    sp = _prompt_fuer_bereich(slug)
    if sp:
        werte["openAiPrompt"] = sp
    daten = json.dumps(werte).encode()
    req = urllib.request.Request(ZIEL + "/api/v1/workspace/" + slug + "/update",
                                 data=daten, method="POST")
    req.add_header("Authorization", "Bearer " + API_SCHLUESSEL)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        print("[Bereich] '%s' auf gepruefte Einstellungen gebracht" % slug,
              file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print("[Bereich] '%s' nicht gesetzt: %s" % (slug, str(e)[:150]),
              file=sys.stderr, flush=True)
        return False
# ============================================================================
#  KI4KI-LOESCHEN: Dokumente loeschen ohne zwei Handgriffe.
#
#  Ein Dokument lebt an mehreren Stellen (Textfassung + Vektoren in
#  AnythingLLM, Original-PDF im Archiv, Katalogeintrag, Vormerkliste).
#  Niemand raeumt vier Stellen von Hand auf. Deshalb: PDF nach
#  <bereich>/loeschen/ legen (FileZilla, ein Handgriff) - die Wache holt es
#  sich jede Minute, entfernt das Dokument ueberall und raeumt die PDF am
#  Ende weg. Jeder Schritt steht in <bereich>/loeschen.log.
#
#  ⚠ Nur DIESER Ordner loest ein Loeschen aus. Eine aus dem Archiv
#    verschwundene PDF loescht nie etwas - versehentlich verschieben darf
#    keine Belege toeten. Abschaltbar: KI4KI_LOESCHEN=0.
# ============================================================================
LOESCH_WACHE = (os.environ.get("KI4KI_LOESCHEN", "1") != "0")


def _api(methode, pfad, daten=None, timeout=60):
    """AnythingLLM-Schnittstelle mit dem Anlagen-Schluessel - direkt an
    AnythingLLM, nicht durch die eigene Positivliste."""
    roh = json.dumps(daten).encode() if daten is not None else None
    req = urllib.request.Request(ZIEL + pfad, data=roh, method=methode)
    req.add_header("Authorization", "Bearer " + API_SCHLUESSEL)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        antwort = r.read()
    try:
        return json.loads(antwort) if antwort else {}
    except Exception:
        return {}


def _loesch_grund(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_DOKUMENT_ENDUNGEN = (".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".pptx", ".ppt",
                      ".odt", ".ods", ".odp", ".txt", ".html", ".htm", ".md", ".rtf")


def _stamm(name):
    """Dateiname ohne Dokument-Endung: 'Katalog.xlsx' -> 'Katalog'. Gemessen
    26.08.: Die Loesch-Wache sah nur *.pdf - eine Excel in loeschen/ blieb
    einfach liegen, der Bestandseintrag dazu auch."""
    n = os.path.basename(str(name or ""))
    for e in _DOKUMENT_ENDUNGEN:
        if n.lower().endswith(e):
            return n[:-len(e)]
    return n


def _loesch_protokoll(wurzel, text):
    zeile = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), text)
    print("[Loeschen] " + text, file=sys.stderr, flush=True)
    try:
        with open(os.path.join(wurzel, "loeschen.log"), "a", encoding="utf-8") as fh:
            fh.write(zeile + "\n")
    except Exception:
        pass


def _eigene_spuren_tilgen(stamm, grund_log="geloescht"):
    """Alles, was DIE ANLAGE selbst ueber ein Dokument fuehrt, entfernen:
    Katalogeintrag, Volltext-Vorrat, Vormerkliste, Archiv-PDF - in jedem
    Bereich, in dem das Dokument liegt. Liefert die betroffenen Bereiche."""
    ziel = _loesch_grund(stamm)
    try:
        import bestand as _bst
        _bst.entfernen(stamm)
    except Exception:
        pass
    try:
        for t in [t for t in list(BESTAND._pfade)
                  if _loesch_grund(t[:-3] if t.endswith(".md") else t) == ziel]:
            BESTAND._pfade.pop(t, None)
            BESTAND._geladen.pop(t, None)
            if t in BESTAND._reihe:
                BESTAND._reihe.remove(t)
        BESTAND._roh = None
    except Exception:
        pass
    betroffen = []
    try:
        bereiche = sorted(os.listdir(EINGANG_ORDNER))
    except Exception:
        bereiche = []
    for bereich in bereiche:
        wurzel = os.path.join(EINGANG_ORDNER, bereich)
        if not os.path.isdir(os.path.join(wurzel, "archiv")):
            continue
        getan = False
        vormerk = os.path.join(wurzel, "bilder-nachholen.txt")
        try:
            if os.path.exists(vormerk):
                alt = open(vormerk, encoding="utf-8").read().splitlines()
                neu = [z for z in alt if _loesch_grund(_stamm(z.strip())) != ziel]
                if len(neu) != len(alt):
                    with open(vormerk, "w", encoding="utf-8") as fh:
                        fh.write("\n".join(neu) + ("\n" if neu else ""))
                    getan = True
        except Exception:
            pass
        try:
            for d in os.listdir(os.path.join(wurzel, "archiv")):
                if not d.startswith(".") and _loesch_grund(_stamm(d)) == ziel:
                    os.remove(os.path.join(wurzel, "archiv", d))
                    getan = True
        except Exception as e:
            _loesch_protokoll(wurzel, "%s: Archiv-PDF nicht loeschbar (%s)" % (stamm, str(e)[:80]))
        if getan:
            betroffen.append(wurzel)
            _loesch_protokoll(wurzel, "%s: Archiv-PDF/Vormerkliste/Katalog bereinigt (%s)" % (stamm, grund_log))
    _pdfs_erneuern_wenn_faellig()
    return betroffen


_LOESCH_UI = re.compile(r"^/api/(?:v1/)?system/remove-documents/?(?:\?.*)?$")


def _nach_ui_loeschung(names):
    """Nach einem Papierkorb-Klick in der Oberflaeche: AnythingLLM hat die
    Textfassung entfernt - jetzt die eigenen Spuren nachziehen. Nur, wenn
    die Textfassung wirklich weg ist (sonst hat AnythingLLM abgelehnt)."""
    for docpath in names or []:
        if os.path.exists(os.path.join(BESTAND_ORDNER, docpath)):
            continue
        stamm = os.path.basename(str(docpath)).split(".md-")[0]
        if stamm:
            _eigene_spuren_tilgen(stamm, "aus der Oberflaeche geloescht")


def _dokument_loeschen(pdf):
    """Eine Datei (PDF, Excel, Word, ...) aus <bereich>/loeschen/ ueberall
    entfernen. True = fertig."""
    wurzel = os.path.dirname(os.path.dirname(pdf))
    name = os.path.basename(pdf)
    stamm = _stamm(name)
    ziel = _loesch_grund(stamm)

    # 1) Textfassungen in AnythingLLM finden (ueber alle Ablageordner).
    docpaths = []
    for w, _, dateien in os.walk(BESTAND_ORDNER):
        for d in dateien:
            if d.endswith(".json") and _loesch_grund(d.split(".md-")[0]) == ziel:
                docpaths.append(os.path.relpath(os.path.join(w, d), BESTAND_ORDNER))
    # 2) Aus allen Arbeitsbereichen austragen (Vektoren weg), dann aus dem System.
    if docpaths:
        try:
            ws = (_api("GET", "/api/v1/workspaces") or {}).get("workspaces") or []
        except Exception as e:
            _loesch_protokoll(wurzel, "%s: Arbeitsbereiche nicht abfragbar (%s) - naechster Versuch in einer Minute" % (name, str(e)[:80]))
            return False
        for w in ws:
            slug = w.get("slug")
            if not slug:
                continue
            try:
                _api("POST", "/api/v1/workspace/%s/update-embeddings" % slug,
                     {"adds": [], "deletes": docpaths}, timeout=120)
            except Exception as e:
                _loesch_protokoll(wurzel, "%s: aus Bereich '%s' nicht ausgetragen (%s)" % (name, slug, str(e)[:80]))
        try:
            _api("DELETE", "/api/v1/system/remove-documents", {"names": docpaths})
            _loesch_protokoll(wurzel, "%s: Textfassung + Vektoren entfernt (%s)" % (name, ", ".join(docpaths)))
        except Exception as e:
            _loesch_protokoll(wurzel, "%s: Textfassung nicht entfernt (%s) - naechster Versuch in einer Minute" % (name, str(e)[:80]))
            return False
    else:
        _loesch_protokoll(wurzel, "%s: keine Textfassung im Bestand (war nie aufgenommen oder schon weg)" % name)
    # 3) Eigene Spuren ueberall tilgen (Katalog, Vorrat, Vormerkliste, Archiv-PDF).
    _eigene_spuren_tilgen(stamm, "ueber loeschen/")
    # 4) Zuletzt die Datei im Loesch-Ordner selbst.
    try:
        if os.path.exists(pdf):
            os.remove(pdf)
    except Exception as e:
        _loesch_protokoll(wurzel, "%s: %s nicht loeschbar (%s)" % (name, pdf, str(e)[:80]))
    _pdfs_erneuern_wenn_faellig()
    _loesch_protokoll(wurzel, "%s: GELOESCHT (Bereich %s)" % (name, os.path.basename(wurzel)))
    return True


def _gleicher_inhalt(a, b):
    """Zwei Dateien byteweise gleich? (Groesse zuerst, dann Hash.)"""
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        import hashlib
        h = []
        for p in (a, b):
            m = hashlib.md5()
            with open(p, "rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    m.update(block)
            h.append(m.hexdigest())
        return h[0] == h[1]
    except Exception:
        return True          # im Zweifel KEIN Tausch


def _liegengebliebene_einraeumen():
    """PDFs, die laenger als eine Stunde in input/ liegen, obwohl ihre
    Textfassung laengst im Bestand ist, an ihren Platz bringen.

    Der Aufnahme-Filter ueberspringt Dateien, deren Dokument schon im
    Bestand liegt - STUMM. Sie blieben in input/ liegen, bis die
    Claim-Garantie sie nach drei Stunden aussortierte (gemessen 25.08.:
    DS-24-004, eingebettet, nie abgelegt). Zwei Faelle:
      - archiv/ hat noch keine Datei dieses Namens -> dorthin (das Dokument
        IST im Bestand, die PDF gehoert ins Archiv).
      - archiv/ hat sie schon -> das ist eine ZWEITE Fassung gleichen
        Namens; die Aufnahme nimmt sie nie -> aussortiert/ mit Hinweis,
        wie man eine neue Fassung wirklich einspielt.
    Eine Stunde Karenz, damit ein laufender Durchgang nicht gestoert wird
    (dessen Ablage kommt binnen Minuten nach der Einbettung)."""
    try:
        bereiche = sorted(os.listdir(EINGANG_ORDNER))
    except Exception:
        return
    jetzt = time.time()
    for bereich in bereiche:
        wurzel = os.path.join(EINGANG_ORDNER, bereich)
        eingang = os.path.join(wurzel, "input")
        if not os.path.isdir(eingang):
            continue
        ablage = bereich
        try:
            with open(os.path.join(wurzel, "bereich.json"), encoding="utf-8") as fh:
                ablage = (json.load(fh).get("ablage") or bereich)
        except Exception:
            pass
        try:
            im_bestand = {_loesch_grund(d.split(".md-")[0])
                          for d in os.listdir(os.path.join(BESTAND_ORDNER, ablage))
                          if d.endswith(".json")}
        except Exception:
            continue
        for d in sorted(os.listdir(eingang)):
            if d.startswith(".") or _stamm(d) == d:
                continue          # keine Dokumentdatei
            pfad = os.path.join(eingang, d)
            if _loesch_grund(_stamm(d)) not in im_bestand:
                continue
            # ⭐ NEUE FASSUNG (26.08., T4 hatte dafuer ersetzen.py): Liegt im Archiv
            #   eine Datei gleichen Namens mit ANDEREM Inhalt, ist das eine neue
            #   Fassung - kein Doppel. Dann wandert die alte nach loeschen/ (die
            #   Wache raeumt Bestand + Archiv binnen einer Minute), und die
            #   Aufnahme nimmt die neue beim naechsten Durchgang. Ein Handgriff
            #   statt zwei. Sofort, ohne die Stunde Karenz.
            ziel_archiv = os.path.join(wurzel, "archiv", d)
            if os.path.exists(ziel_archiv) and not _gleicher_inhalt(pfad, ziel_archiv):
                try:
                    lo = os.path.join(wurzel, "loeschen")
                    os.makedirs(lo, exist_ok=True)
                    os.replace(ziel_archiv, os.path.join(lo, d))
                    zeit = time.strftime("%Y-%m-%d %H:%M:%S")
                    _loesch_protokoll(wurzel, "%s: NEUE FASSUNG im Eingang erkannt - alte Fassung wird "
                                      "entfernt, die neue kommt beim naechsten Durchgang in den Bestand" % d)
                    log = os.path.join(wurzel, "aussortiert", "aussortiert.log")
                    os.makedirs(os.path.dirname(log), exist_ok=True)
                    with open(log, "a", encoding="utf-8") as fh:
                        fh.write("[%s] %s | neue Fassung erkannt - alte geloescht, neue wird aufgenommen\n" % (zeit, d))
                except Exception as e:
                    print("[Eingang] %s: neue Fassung nicht tauschbar: %s" % (d, str(e)[:100]), file=sys.stderr, flush=True)
                continue
            try:
                if jetzt - os.stat(pfad).st_ctime < 3600:
                    continue
            except OSError:
                continue
            zeit = time.strftime("%Y-%m-%d %H:%M:%S")
            ziel_archiv = os.path.join(wurzel, "archiv", d)
            log = os.path.join(wurzel, "aussortiert", "aussortiert.log")
            try:
                os.makedirs(os.path.dirname(log), exist_ok=True)
                if not os.path.exists(ziel_archiv):
                    os.makedirs(os.path.dirname(ziel_archiv), exist_ok=True)
                    os.replace(pfad, ziel_archiv)
                    zeile = ("[%s] %s | war schon im Bestand (eingebettet, aber nie abgelegt) - "
                             "PDF ins Archiv gelegt, Belege funktionieren" % (zeit, d))
                else:
                    ziel_aus = os.path.join(wurzel, "aussortiert", d)
                    os.replace(pfad, ziel_aus)
                    zeile = ("[%s] %s | Dokument gleichen Namens ist schon im Bestand und im "
                             "Archiv - eine zweite Fassung nimmt die Aufnahme nicht. Neue "
                             "Fassung einspielen: erst das alte Dokument loeschen "
                             "(Papierkorb oder loeschen/), dann erneut hochladen." % (zeit, d))
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(zeile + "\n")
                print("[Eingang] " + zeile, file=sys.stderr, flush=True)
            except Exception as e:
                print("[Eingang] %s nicht einraeumbar: %s" % (d, str(e)[:100]),
                      file=sys.stderr, flush=True)
    _pdfs_erneuern_wenn_faellig()


def bereich_ordner_anlegen(slug):
    """dokumente/<slug>/{input,parkplatz,archiv,aussortiert,loeschen} + bereich.json
    mit den Rechten der Aufnahme (1000:KI4KI_GID, 2775). Gemessen 26.08.:
    Emrach legte AuW/KAP/KI4KI in der Oberflaeche an - per FileZilla gab es
    nur 'wissensdatenbank', weil der Ordner erst beim ersten Upload entstand.
    True = angelegt oder vorhanden."""
    if not slug:
        return False
    try:
        wurzel = os.path.join(EINGANG_ORDNER, _ordnername(slug))
        neu = not os.path.isdir(wurzel)
        gid = int(os.environ.get("KI4KI_GID") or 1000)
        for unter in ("", "input", "parkplatz", "archiv", "aussortiert", "loeschen"):
            d = os.path.join(wurzel, unter) if unter else wurzel
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
                try:
                    os.chown(d, 1000, gid)
                    os.chmod(d, 0o2775)
                except Exception:
                    pass
        konf = os.path.join(wurzel, "bereich.json")
        if not os.path.exists(konf):
            with open(konf, "w", encoding="utf-8") as fh:
                json.dump({"bereich": _ordnername(slug), "ablage": _ordnername(slug)}, fh, ensure_ascii=False)
            try:
                os.chown(konf, 1000, gid)
                os.chmod(konf, 0o664)
            except Exception:
                pass
        # Kategorien des Bereichs (Standardliste, zum Bearbeiten)
        kt = os.path.join(wurzel, kategorie.DATEI)
        if not os.path.exists(kt):
            with open(kt, "w", encoding="utf-8") as fh:
                fh.write(kategorie.datei_text())
            try:
                os.chown(kt, 1000, gid)
                os.chmod(kt, 0o664)
            except Exception:
                pass
        # Rolle des Bereichs: Datei mit Anleitung, solange nicht eingerichtet
        pr = os.path.join(wurzel, rolle.DATEI)
        if not os.path.exists(pr):
            with open(pr, "w", encoding="utf-8") as fh:
                fh.write(rolle.platzhalter(_ordnername(slug)))
            try:
                os.chown(pr, 1000, gid)
                os.chmod(pr, 0o664)
            except Exception:
                pass
        if neu:
            print("[Bereich] Ordner angelegt: dokumente/%s" % _ordnername(slug), file=sys.stderr, flush=True)
        return True
    except Exception as e:
        print("[Bereich] Ordner fuer %r nicht anlegbar: %s" % (slug, str(e)[:100]), file=sys.stderr, flush=True)
        return False


_BEREICHE_ABGLEICH = [0.0]
VERWAISTE_BEREICHE = []
BEREICH_LOESCHEN = re.compile(r"^/api/(?:v1/)?workspace/([^/]+)/?$")


def bereich_ordner_aufraeumen(slug):
    """Nach dem Loeschen eines Arbeitsbereichs: Ordner weg, wenn LEER
    (Emrach 26.08.: 'wenn ich mich vertippte und es loesche, dann geht das
    ja nicht weg in FileZilla'). Liegt irgendeine Datei mit Inhalt darin
    (PDF im Archiv, Eingang, Parkplatz, Logs mit Zeilen), bleibt er - und
    wird als verwaist gemeldet. Rueckgabe: 'geloescht' | 'behalten' | None."""
    if not slug:
        return None
    wurzel = os.path.join(EINGANG_ORDNER, _ordnername(slug))
    if not os.path.isdir(wurzel):
        return None
    inhalt = []
    for w, _dirs, dateien in os.walk(wurzel):
        for d in dateien:
            if d == "bereich.json":
                continue
            if d == rolle.DATEI or d.endswith(".neu"):
                continue          # Rolle/Verwaltung - kein Inhalt (Emrach 27.08.: Ordner soll weg)
            try:
                if os.path.getsize(os.path.join(w, d)) > 0:
                    inhalt.append(os.path.relpath(os.path.join(w, d), wurzel))
            except OSError:
                inhalt.append(d)
    if inhalt:
        print("[Bereich] dokumente/%s behalten - Bereich geloescht, aber %d Datei(en) darin (z.B. %s)"
              % (_ordnername(slug), len(inhalt), inhalt[0]), file=sys.stderr, flush=True)
        return "behalten"
    try:
        import shutil
        shutil.rmtree(wurzel)
        print("[Bereich] dokumente/%s geloescht (Bereich entfernt, Ordner war leer)" % _ordnername(slug),
              file=sys.stderr, flush=True)
        return "geloescht"
    except Exception as e:
        print("[Bereich] dokumente/%s nicht loeschbar: %s" % (_ordnername(slug), str(e)[:80]),
              file=sys.stderr, flush=True)
        return "behalten"


def _bereiche_abgleichen():
    """Alle fuenf Minuten: fuer jeden Arbeitsbereich in AnythingLLM den
    Ordnerbaum sicherstellen - auch fuer Bereiche, die vor dieser Fassung
    angelegt wurden oder an der Heilung vorbei entstanden sind."""
    if not API_SCHLUESSEL or time.time() - _BEREICHE_ABGLEICH[0] < 300:
        return
    _BEREICHE_ABGLEICH[0] = time.time()
    try:
        req = urllib.request.Request(ZIEL + "/api/v1/workspaces",
                                     headers={"Authorization": "Bearer " + API_SCHLUESSEL})
        with urllib.request.urlopen(req, timeout=20) as r:
            ws = (json.load(r) or {}).get("workspaces") or []
        slugs = set()
        for w in ws:
            if w.get("slug"):
                bereich_ordner_anlegen(w["slug"])
                slugs.add(_ordnername(w["slug"]))
                try:
                    _rolle_einspielen(w["slug"])      # prompt.md geaendert -> Prompt nachziehen
                except Exception:
                    traceback.print_exc(file=sys.stderr)
        # Verwaiste Ordner (Bereich geloescht oder neu angelegt): leer -> weg,
        # sonst nur melden - darin koennen Archiv-PDFs liegen.
        verwaist = []
        for d in sorted(os.listdir(EINGANG_ORDNER)):
            if os.path.isdir(os.path.join(EINGANG_ORDNER, d)) and d not in slugs and \
                    os.path.exists(os.path.join(EINGANG_ORDNER, d, "bereich.json")):
                if bereich_ordner_aufraeumen(d) == "behalten":
                    verwaist.append(d)
        VERWAISTE_BEREICHE[:] = verwaist
        if verwaist:
            print("[Bereich] verwaist (kein Arbeitsbereich mehr dazu): %s - belassen; "
                  "bei Bedarf von Hand verschieben" % ", ".join("dokumente/" + v for v in verwaist),
                  file=sys.stderr, flush=True)
    except Exception as e:
        print("[Bereich] Abgleich nicht moeglich: %s" % str(e)[:100], file=sys.stderr, flush=True)


def _seiten_vorwaermen(hoechstens=3):
    """Seitentexte neuer PDFs im Hintergrund lesen (pdftotext, 1-2 s je
    Dokument). Gemessen 25.08.: Die Belegpruefung der ERSTEN Antwort dauerte
    11 s, weil sechs Dokumente erst dann gelesen wurden - danach 0-2 s.
    Hoechstens drei je Minute, damit die Anlage nebenbei antwortfaehig bleibt."""
    getan = 0
    try:
        with pdfstelle._SPERRE:
            fehlend = [k for k in list(PDFS) if k not in pdfstelle._SEITEN]
    except Exception:
        return
    for k in fehlend[:hoechstens]:
        try:
            pdfstelle.seitentexte(k)
            getan += 1
        except Exception:
            continue
    if getan:
        print("[Vorwaermen] %d Dokument(e) fuer die Belegpruefung gelesen, %d offen"
              % (getan, max(0, len(fehlend) - getan)), file=sys.stderr, flush=True)


OLLAMA_URL = (os.environ.get("KI4KI_OLLAMA_URL") or "http://ollama:11434").rstrip("/")
GPU_STAND = {"wann": 0, "modelle": [], "warnung": ""}


def _gpu_pruefen():
    """Rechnen die geladenen Modelle auf der Grafikkarte? Ollama faellt bei
    einem Treiberproblem STILL auf die CPU zurueck - alles wird 10x langsamer,
    und niemand sieht es (T4: waechter.sh 'ollama_auf_cpu'). Hier: /api/ps
    liefert je Modell size und size_vram; liegt weniger als 90 % im VRAM,
    ist das eine Warnung - im Log und unter /pruef-status."""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/ps", timeout=8) as r:
            d = json.loads(r.read() or b"{}")
    except Exception as e:
        GPU_STAND.update({"wann": time.time(), "modelle": [],
                          "warnung": "Ollama nicht erreichbar (%s)" % str(e)[:60]})
        return GPU_STAND
    modelle, warn = [], []
    for m in d.get("models") or []:
        size = float(m.get("size") or 0)
        vram = float(m.get("size_vram") or 0)
        anteil = (vram / size) if size else 1.0
        modelle.append({"modell": m.get("name"), "gb": round(size / 1e9, 1),
                        "vram_gb": round(vram / 1e9, 1), "gpu_anteil": round(anteil, 2)})
        if size and anteil < 0.9:
            warn.append("%s rechnet %s auf der CPU (%.1f von %.1f GB im VRAM)" % (
                m.get("name"), "ganz" if vram == 0 else "teilweise", vram / 1e9, size / 1e9))
    neu = "; ".join(warn)
    if neu and neu != GPU_STAND.get("warnung"):
        print("[GPU] ⚠ " + neu, file=sys.stderr, flush=True)
    elif not neu and GPU_STAND.get("warnung"):
        print("[GPU] wieder alles auf der Grafikkarte", file=sys.stderr, flush=True)
    GPU_STAND.update({"wann": time.time(), "modelle": modelle, "warnung": neu})
    return GPU_STAND


def _loesch_wache():
    """Jede Minute nach <bereich>/loeschen/* sehen (jede Dokumentdatei) - und liegengebliebene
    Eingangsdateien einraeumen. Alle 10 Minuten: Grafikkarten-Pruefung."""
    runde = 0
    while True:
        runde += 1
        if runde % 10 == 1:
            try:
                _gpu_pruefen()
            except Exception:
                traceback.print_exc(file=sys.stderr)
        try:
            _liegengebliebene_einraeumen()
        except Exception:
            traceback.print_exc(file=sys.stderr)
        try:
            _seiten_vorwaermen()
        except Exception:
            traceback.print_exc(file=sys.stderr)
        try:
            _bereiche_abgleichen()
        except Exception:
            traceback.print_exc(file=sys.stderr)
        try:
            for bereich in sorted(os.listdir(EINGANG_ORDNER)):
                wurzel = os.path.join(EINGANG_ORDNER, bereich)
                lo = os.path.join(wurzel, "loeschen")
                # Bestehende Bereiche (vor dieser Fassung angelegt) bekommen
                # den Ordner hier nachgereicht - mit denselben Rechten wie
                # die anderen, damit der Mensch per SFTP hineinlegen kann.
                if os.path.isdir(os.path.join(wurzel, "archiv")) and not os.path.isdir(lo):
                    try:
                        os.makedirs(lo, exist_ok=True)
                        try:
                            os.chown(lo, 1000, int(os.environ.get("KI4KI_GID") or 1000))
                            os.chmod(lo, 0o2775)
                        except Exception:
                            pass
                    except Exception:
                        continue
                if not os.path.isdir(lo):
                    continue
                for f in sorted(os.listdir(lo)):
                    if not f.startswith(".") and f != "loeschen.log" and os.path.isfile(os.path.join(lo, f)):
                        try:
                            _dokument_loeschen(os.path.join(lo, f))
                        except Exception:
                            traceback.print_exc(file=sys.stderr)
        except Exception:
            traceback.print_exc(file=sys.stderr)
        time.sleep(60)


# Fuer Zusammenfassungen spricht der Proxy das Sprachmodell direkt an -
# ueber den nothink-Proxy, damit Gemma nicht laut denkt. AnythingLLM waere
# hier der falsche Weg: Es wuerde suchen, obwohl das ganze Dokument
# gemeint ist.
# Wo die abgelegten Dokument-JSONs liegen. Dieselbe Stelle, aus der auch
# veredeln.py seinen Bestand liest.
BESTAND_ORDNER = (os.environ.get("KI4KI_BESTAND")
                  or os.path.expanduser(
                      "~/ki4ki/anythingllm/storage/documents"))
MODELL_ZIEL = (os.environ.get("KI4KI_MODELL")
               or "http://nothink-proxy:11435/api/chat")
MODELL_NAME = os.environ.get("KI4KI_MODELL_NAME") or "gemma4:12b"
PDF_ORDNER = (os.environ.get("KI4KI_PDFS")
              or os.path.expanduser("~/ki4ki/dokumente"))
# Wohin der Hochladen-Knopf legt. Im Container ein eigener, SCHREIBBARER Weg
# in denselben Eingang - der Lesepfad oben bleibt schreibgeschuetzt.
EINGANG_ORDNER = os.environ.get("KI4KI_EINGANG") or PDF_ORDNER

# Wer fragt, braucht die Grafikkarte. Diese Marke sagt dem Massenlauf
# Bescheid, damit Docling zurueck tritt. Sie ersetzt das starre
# Sperrfenster Mo-Fr 7-19 Uhr, das abends genau die zwei Menschen
# aussperrte, fuer die die Anlage gebaut ist.
# Der Pfad folgt demselben Muster wie ZUGANG_DATEI weiter unten:
# im Container /app, auf dem Host ~/ki4ki/reextract - beides dasselbe
# Verzeichnis. Ein "~" waere hier falsch: im Container zeigt es woanders
# hin, und der Zyklus auf dem Host saehe die Marke nie.
CHAT_MARKE = (os.environ.get("KI4KI_CHAT_MARKE")
              or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              ".chat-aktiv"))


def chat_gemeldet():
    """Zeitstempel setzen: gerade fragt jemand.

    Schlaegt das fehl, tritt Docling nicht zurueck und die naechste
    Frage laeuft ins Zeitlimit. Deshalb wird der Fehler gemeldet und
    nicht verschluckt - eine Antwort kosten darf er trotzdem nicht.
    """
    try:
        with open(CHAT_MARKE, "w") as fh:
            fh.write(str(int(time.time())))
    except Exception as e:
        print("[Marke] konnte nicht geschrieben werden (%s): %s"
              % (CHAT_MARKE, str(e)[:100]), file=sys.stderr, flush=True)

# Genau diese Anfragen werden abgefangen. Alles andere fliesst durch.
#  - stream-chat: die Oberflaeche im Browser (Datenstrom, SSE)
#  - /api/v1/.../chat: der Weg fuer Maschinen, u. a. n8n (schlichtes JSON)
# Beide bekommen dieselbe Pruefung, damit die Belege ueberall gleich sind.
CHAT = re.compile(r"^/api/workspace/[^/]+(?:/thread/[^/]+)?/stream-chat/?$")
CHAT_JSON = re.compile(r"^/api/v1/workspace/[^/]+/chat/?$")
FEEDBACK = re.compile(r"^/api/workspace/([^/]+)/chat-feedback/(-?\d+)/?$")
_RUECKMELDUNG_CHAT = re.compile(
    r"^\s*(?:feedback|r(?:ü|ue)ckmeldung|falsche\s+quelle|falscher\s+beleg|quelle\s+falsch)\s*[:\-–]\s*(.+)$",
    re.I | re.S)

# KI4KI-BEREICH-HEILEN: das Anlegen eines neuen Arbeitsbereichs abfangen,
# um ihn direkt danach auf die gepruef-ten Werte zu bringen.
ERSTELLEN = re.compile(r"^/api/(?:v1/)?workspace/new/?$")
# Der geladene Gespraechsverlauf - hier werden die gemerkten gepruefton
# Fassungen wieder eingesetzt.
VERLAUF = re.compile(
    r"^/api/workspace/[^/]+(?:/thread/[^/]+)?/chats/?$"
    r"|^/api/workspace/workspace-chats/")

# Der Hochladen-Knopf der Oberflaeche. Wird abgefangen, damit die Datei
# durch unsere Aufbereitung laeuft statt durch AnythingLLMs einfachen
# Textauszug - sonst fehlen Seitenmarken, Formeln und Verschlagwortung.
UPLOAD = re.compile(r"^/api/workspace/([^/]+)/upload(?:-and-embed)?/?$")

# ============================================================================
#  KI4KI-ANHANG-WEG-A: Eine direkt an den Chat angehaengte Datei (Bueroklammer)
#  geht ueber /parse an AnythingLLM, landet dort aber im Agentenmodus, der sie
#  ignoriert. Deshalb: Der Proxy merkt sich den Text der Datei (ueber Tika) und
#  beantwortet die Folge-Frage DIREKT daraus - ohne Agent, ohne Suche, ohne
#  Belege. Gilt fuer JEDEN Bereich (Kennung aus der URL), auch kuenftige.
# ============================================================================
PARSE = re.compile(r"^/api/workspace/([^/]+)/parse/?$")
TIKA_ZIEL = os.environ.get("KI4KI_TIKA") or "http://tika:9998/tika"

# ============================================================================
#  KI4KI-META: Begruessungen und Fragen UEBER die Anlage selbst ("Was kannst
#  du?", "Wer bist du?", "Wie geht's?") freundlich beantworten - fest
#  hinterlegt, ohne Beleg, ohne Modell. Nur wenn die Nachricht GANZ so eine
#  Meta-Nachricht ist (End-Anker), damit echte Fachfragen NICHT abgefangen
#  werden. Abschaltbar mit KI4KI_META_ANTWORT=0.
# ============================================================================
META_ANTWORT = (os.environ.get("KI4KI_META_ANTWORT", "1") != "0")

# ============================================================================
#  KI4KI-ALLROUNDER: Findet die Suche keine einzige Fundstelle (0 Quellen),
#  verstummt die Anlage nicht mehr - das Sprachmodell antwortet dann aus
#  seinem ALLGEMEINWISSEN, klar als solches markiert (kein Beleg). Bei echten
#  Fundstellen bleibt die Belegpflicht unangetastet. So ist jeder Bereich ein
#  Allrounder (wie ChatGPT/Perplexity), ohne dass jemand Bereichs-
#  Einstellungen aendern muss. Abschaltbar mit KI4KI_ALLROUNDER=0.
# ============================================================================
ALLROUNDER = (os.environ.get("KI4KI_ALLROUNDER", "1") != "0")
ALLGEMEIN_KOPF = (
    "> \U0001F9E0 **Allgemeinwissen** \u2013 diese Antwort stammt aus dem "
    "Sprachmodell, **nicht** aus euren hinterlegten Dokumenten (kein Beleg)."
    "\n\n")
_META_GRUSS = re.compile(
    r"^\s*(hallo|hi|hey|moin|servus|na|danke(\s+dir)?|"
    r"guten\s+(tag|morgen|abend)|wie\s+geht'?s?(\s+dir|\s+ihnen)?|"
    r"wie\s+l(ae|\u00e4)uft'?s?)[\s,.!?]*$", re.I)
_META_KANN = re.compile(
    r"^\s*(was\s+kannst\s+du|was\s+(sind|ist)\s+deine\s+"
    r"funktion(en)?|wer\s+bist\s+du|was\s+bist\s+du|"
    r"wie\s+funktionierst\s+du|wobei\s+(kannst|hilfst)\s+du(\s+mir)?|"
    r"was\s+machst\s+du)[\s,.!?]*$", re.I)
META_TEXT_KANN = (
    "Ich bin die **Wissensdatenbank** dieser Anlage. Ich beantworte deine "
    "**Fachfragen zu den hinterlegten Dokumenten** \u2013 und belege **jede "
    "Aussage mit einer gepr\u00fcften Fundstelle im Original-PDF** (Seite, gelb "
    "markiert), damit du nichts glauben musst, sondern nachschlagen kannst.\n\n"
    "Au\u00dferdem:\n"
    "- **Bestandsfragen** wie \u201eWelche Dissertationen habt ihr zum Thema "
    "Kleben?\u201c beantworte ich direkt aus dem Katalog.\n"
    "- Du kannst im Chat eine **PDF anh\u00e4ngen** \u2013 dann lese ich sie "
    "komplett und erledige deine Aufgabe (z.\u202fB. eine Gliederung erstellen).\n"
    "- **Ein Dokument im Blick:** Nenn Kennung oder Verfasser (\u201edie Arbeit von "
    "Becker\u201c) \u2013 danach beziehen sich Folgefragen, Zusammenfassungen, "
    "\u201eZeig mir ein Diagramm\u201c, \u201eWie viele Seiten?\u201c und \u201eWof\u00fcr "
    "steht GFK?\u201c auf genau dieses Dokument, mit w\u00f6rtlich gepr\u00fcften Zitaten.\n"
    "- **Vergleichen:** \u201eVergleiche die Methodik von Becker und M\u00fcller\u201c "
    "\u2192 Tabelle mit Seite je Zelle; \u201eWidersprechen sich \u2026?\u201c pr\u00fcft "
    "Gegens\u00e4tze.\n"
    "- **Kennwerte:** \u201eWelche E-Modul-Werte nennt die Arbeit?\u201c \u2192 Tabelle "
    "Wert \u00b7 Einheit \u00b7 Messbedingung \u00b7 Seite.\n"
    "- **Export:** \u201eals CSV\u201c / \u201eals BibTeX\u201c.\n"
    "- **Korrigieren:** \u201edas ist falsch\u201c oder \u201esicher?\u201c \u2013 ich "
    "pr\u00fcfe die letzte Antwort Satz f\u00fcr Satz am Original.\n"
    "- **Alles durchsuchen:** Frage mit \u201eim ganzen Bestand:\u201c beginnen."
    "\n\nStell mir einfach eine Frage zu deinen Dokumenten!")
META_TEXT_GRUSS = (
    "Hallo! \U0001F642 Mir geht\u2019s gut, danke der Nachfrage. Ich bin die "
    "**Wissensdatenbank** \u2013 stell mir eine **Fachfrage zu deinen "
    "Dokumenten**, und ich beantworte sie mit belegten Fundstellen. Wenn du "
    "wissen willst, was ich alles kann, frag einfach \u201e**Was kannst "
    "du?**\u201c.")
_ANHANG = {}
_ANHANG_HALTBAR = 1200
_ANHANG_MAX = 4000000   # praktisch unbegrenzt; nur Schutz vor Extremen


def _tika_text(roh):
    # Content-Type MUSS gesetzt sein - sonst schickt urllib
    # form-urlencoded und Tika liefert leer. octet-stream laesst Tika den
    # Typ selbst erkennen (PDF, Word, PowerPoint, ...).
    req = urllib.request.Request(TIKA_ZIEL, data=roh, method="PUT",
                                 headers={"Accept": "text/plain",
                                          "Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode("utf-8", "replace")

BESTAND = None
PDFS = {}
# ⭐ Zweites Verzeichnis nach GRUNDFORM (klein, nur Buchstaben und Ziffern).
#   Vier Arbeiten heissen auf der Platte anders, als ein Modell sie
#   schreibt - "DS-00-000 " mit Leerzeichen, "DS-00-000\xa0" mit einem
#   GESCHUETZTEN Leerzeichen, das man nicht sieht. Der exakte Vergleich
#   findet sie nie, und der Verweis bleibt tot.
PDFS_GRUND = {}
# Ollama vertraegt keine zehn gleichzeitigen Pruefungen; die Pruefung selbst
# ist schnell, aber der Bestand soll nicht mehrfach parallel geladen werden.
PRUEFSPERRE = threading.Lock()


# Wie viele Seiten hat ein PDF? Mehr wird beim Upload nicht gemessen.
#
# ⚠ HIER STAND EINE ZEITVORHERSAGE. Sie wurde bewusst wieder entfernt -
#   mit gutem Grund: Bei DS-00-000 zaehlte
#   pdfimages 952 Bildobjekte, Docling erkannte daraus 27 Abbildungen. Die
#   Anzeige versprach "7,6 bis 18,8 Stunden", in Wahrheit waren es Minuten.
#   Der Fehler lag nicht in der Zeit je Bild, sondern in der Menge: Eine
#   einzige Kurvenschar besteht aus dreissig Bildobjekten.
#
#   Eine Vorhersage, die auf einem einzigen Dokument kalibriert ist, waere
#   wieder nur eine Vermutung mit Nachkommastelle. Keine Angabe ist besser
#   als eine, der man nicht trauen kann.
def _pdf_seiten(pfad):
    """Seitenzahl eines PDF, 0 wenn nicht lesbar."""
    try:
        aus = subprocess.run(["pdfinfo", pfad], capture_output=True,
                             text=True, timeout=30).stdout
        for z in aus.split("\n"):
            if z.startswith("Pages"):
                return int(z.split()[1])
    except Exception:
        pass
    return 0


def _ordnername(bereich):
    """Aus dem Arbeitsbereich wird der Unterordner im Eingang.

    Der Unterordner bestimmt spaeter, wohin das fertige Dokument gehoert -
    eine Regel, die man niemandem erklaeren muss.
    """
    sauber = re.sub(r"[^A-Za-z0-9_-]+", "-", unquote(bereich or "")).strip("-")
    return sauber or "sonstiges"


def _inhaltsgleich(wurzel, inhalt):
    """Liegt dieselbe Datei (byte-gleich) schon in diesem Bereich?

    Der Namensvergleich beim Hochladen kennt nur FERTIG aufgenommene
    Dokumente. Eine Datei, die noch in der Aufbereitung steckt (input/)
    oder als Original im Archiv liegt, sah er nicht - der zweite Klick
    auf dieselbe Datei wurde zu "-1" umbenannt und als NEUES Dokument
    eingebettet. Deshalb hier byteweise vergleichen, unabhaengig vom Namen.

    Erst die Groesse (billig, sortiert fast alles aus), dann SHA-256 -
    nur bei gleicher Groesse. Rueckgabe (unterordner, dateiname) oder
    None. Lesefehler gelten als "nicht vorhanden": Eine Stoerung darf
    das Hochladen nicht verhindern, die Aufnahmekette prueft ohnehin.
    """
    laenge = len(inhalt)
    pruefsumme = None
    for unter in ("input", "parkplatz", "archiv"):
        ordner = os.path.join(wurzel, unter)
        try:
            eintraege = sorted(os.listdir(ordner))
        except OSError:
            continue
        for name in eintraege:
            pfad = os.path.join(ordner, name)
            try:
                if (not os.path.isfile(pfad)
                        or os.path.getsize(pfad) != laenge):
                    continue
                if pruefsumme is None:
                    pruefsumme = hashlib.sha256(inhalt).hexdigest()
                h = hashlib.sha256()
                with open(pfad, "rb") as fh:
                    for stueck in iter(lambda: fh.read(1 << 20), b""):
                        h.update(stueck)
                if h.hexdigest() == pruefsumme:
                    return unter, name
            except OSError:
                continue
    return None


def _dateien_aus_formular(roh, art):
    """Dateien aus einem multipart/form-data-Rumpf holen.

    Von Hand, weil im Abbild nur die Standardbibliothek liegt - und weil die
    fertigen Helfer den Rumpf als Text behandeln wuerden. PDFs sind aber
    keine Zeichen, sondern Bytes; ein einziger falsch gedeuteter Wert macht
    die Datei unbrauchbar.
    """
    m = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", art or "")
    if not m:
        return []
    grenze = ("--" + (m.group(1) or m.group(2)).strip()).encode()
    dateien = []
    for teil in roh.split(grenze):
        if not teil or teil in (b"--\r\n", b"--", b"\r\n"):
            continue
        kopf, _, rumpf = teil.partition(b"\r\n\r\n")
        if not rumpf:
            continue
        kopftext = kopf.decode("utf-8", "replace")
        d = re.search(r'filename="([^"]*)"', kopftext)
        if not d or not d.group(1):
            continue
        # der Rumpf endet mit dem Zeilenumbruch vor der naechsten Grenze
        if rumpf.endswith(b"\r\n"):
            rumpf = rumpf[:-2]
        dateien.append((d.group(1), rumpf))
    return dateien


# Mehr als das nimmt der Hochladen-Knopf nicht an. Der Rumpf wird am Stueck
# in den Arbeitsspeicher gelesen - ohne Grenze koennte eine einzige Anfrage
# den Rechner zum Stillstand bringen.
HOECHSTGROESSE = int(os.environ.get("KI4KI_MAX_UPLOAD") or 200 * 1024 * 1024)


def angemeldet(kopfzeilen):
    """Ist die Anfrage angemeldet? AnythingLLM entscheidet, nicht wir.

    Der Proxy sitzt VOR AnythingLLM. Was er selbst beantwortet, prueft
    AnythingLLM nie - also muss er dort nachfragen. /system/check-token
    antwortet ohne gueltige Anmeldung mit 401.
    """
    erlaubnis = kopfzeilen.get("Authorization")
    if not erlaubnis:
        return False
    # Zwei Anmeldewege, zwei Pruefstellen: die Oberflaeche schickt ein
    # Benutzer-Token, Maschinen (n8n, eigene Skripte) einen API-Schluessel.
    for weg in ("/api/system/check-token", "/api/v1/auth"):
        req = urllib.request.Request(ZIEL + weg, method="GET")
        req.add_header("Authorization", erlaubnis)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except urllib.error.HTTPError:
            continue
        except Exception as e:
            # Erreichen wir AnythingLLM nicht, wird NICHT durchgewunken.
            print("[Zugang] Pruefung nicht moeglich: %s" % str(e)[:120],
                  file=sys.stderr, flush=True)
            return False
    return False


# --- Zugang zu den eigenen Routen ------------------------------------------
# Der Schluessel wird einmal erzeugt und bleibt liegen; sonst waeren nach
# jedem Neustart alle offenen Verweise ungueltig.
ZUGANG_DATEI = (os.environ.get("KI4KI_ZUGANG_SCHLUESSEL")
                or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".zugang-schluessel"))
ZUGANG_DAUER = int(os.environ.get("KI4KI_ZUGANG_DAUER") or 12 * 3600)
_ZUGANG = None


def zugang_schluessel():
    global _ZUGANG
    if _ZUGANG is None:
        try:
            with open(ZUGANG_DATEI, "rb") as fh:
                _ZUGANG = fh.read().strip()
        except Exception:
            _ZUGANG = binascii.hexlify(os.urandom(32))
            try:
                with open(ZUGANG_DATEI, "wb") as fh:
                    fh.write(_ZUGANG)
                os.chmod(ZUGANG_DATEI, 0o600)
                print("[Zugang] Schluessel neu erzeugt: %s" % ZUGANG_DATEI,
                      file=sys.stderr, flush=True)
            except Exception as e:
                print("[Zugang] Schluessel nicht ablegbar (%s) - nach einem "
                      "Neustart sind offene Verweise ungueltig"
                      % str(e)[:100], file=sys.stderr, flush=True)
    return _ZUGANG


def marke_bauen(kennung=""):
    """Zeitlich begrenzte Marke: <ablauf>.<kennung>.<unterschrift>.

    Die Kennung sagt, ZU WEM die Marke gehoert. Ohne sie wusste der Proxy
    beim Klick auf einen Beleg nur, dass irgendwer angemeldet war - nicht,
    welche Dokumente diese Sitzung sehen darf. Genau daran scheiterten
    sonst alle Fundstellen-Links.

    Ohne Kennung entsteht die alte Form. Alte Marken bleiben damit gueltig.
    """
    bis = str(int(time.time()) + ZUGANG_DAUER)
    kennung = re.sub(r"[^A-Za-z0-9]", "", kennung or "")[:16]
    stoff = bis + ("." + kennung if kennung else "")
    sig = hmac.new(zugang_schluessel(), stoff.encode(),
                   hashlib.sha256).hexdigest()[:32]
    return stoff + "." + sig


def marke_kennung(marke):
    """Die Kennung aus einer Marke - leer bei der alten Form."""
    teile = (marke or "").split(".")
    return teile[1] if len(teile) == 3 else ""


def marke_gilt(marke):
    """Gueltig? Beide Formen werden akzeptiert.

    Neu:  <ablauf>.<kennung>.<unterschrift>
    Alt:  <ablauf>.<unterschrift>   - solange gueltig, damit niemand
                                      ausgesperrt wird, der die Seite noch
                                      nicht neu geladen hat.
    """
    teile = (marke or "").split(".")
    if len(teile) == 3:
        bis, kennung, sig = teile
        stoff = bis + "." + kennung
    elif len(teile) == 2:
        bis, sig = teile
        stoff = bis
    else:
        return False
    try:
        if int(bis) < time.time():
            return False
    except ValueError:
        return False
    soll = hmac.new(zugang_schluessel(), stoff.encode(),
                    hashlib.sha256).hexdigest()[:32]
    # compare_digest, damit die Laufzeit nichts ueber den Schluessel verraet
    return hmac.compare_digest(soll, sig)


def marke_aus_kopf(kopfzeilen):
    for teil in (kopfzeilen.get("Cookie") or "").split(";"):
        name, _, wert = teil.strip().partition("=")
        if name == "ki4ki_zugang":
            return wert
    return ""


def darf_sehen(kopfzeilen):
    """Cookie ODER gueltige Kopfzeile - der Browser hat nur das eine, ein
    Maschinen-Aufruf nur das andere."""
    return (marke_gilt(marke_aus_kopf(kopfzeilen))
            or angemeldet(kopfzeilen))


# Wie viele Dokumente haengen im gefragten Arbeitsbereich? Kurz gemerkt,
# damit nicht jede Frage einen zusaetzlichen Aufruf kostet.
_ANZAHL = {}
# Titel je Arbeitsbereich, gleiche Haltbarkeit wie die Anzahl.
_TITEL = {}
# Was gerade besprochen wird - je Unterhaltung, damit Folgefragen wissen,
# worum es geht.
GESPRAECHE = assistent.Verlauf()
ANZAHL_HALTBAR = 300



# Welche Bereiche eine Anmeldung sehen darf. Getrennt vom Titel-Speicher,
# weil hier die ANTWORT des Servers zaehlt und nicht ihr Inhalt.
# ⚠ NICHT _ZUGANG nennen - der Name ist ab Zeile 198 fuer den
# Zugangs-Schluessel belegt, und eine zweite Zuweisung auf Modulebene
# haette ihn ueberdeckt.
_BEREICHSZUGANG = {}


def bereich_sichtbar(pfad, kopfzeilen):
    """Liefert AnythingLLM diesen Arbeitsbereich fuer diese Anmeldung?

    KI4KI-ZUGANGSPRUEFUNG. Notwendig, weil der Proxy zwei Faelle selbst
    beantwortet - Bestandsauskunft und Zusammenfassung - und AnythingLLM
    dabei nie zu Wort kommt. Ohne diese Pruefung bekam ein Konto ohne
    Bereichszuweisung sonst vier echte Dokumenttitel und die Groesse
    des Gesamtbestands.

    Rueckgabe True nur, wenn der Server den Bereich fuer genau diese
    Anmeldung ausliefert. Bei 401, 403, 404 und auch bei einem technischen
    Fehler False: Im Zweifel wird nicht gezeigt.

    Der Zwischenspeicher haengt an Bereich UND Anmeldung - sonst wuerde die
    Erlaubnis eines Berechtigten fuer den naechsten Fragenden gelten.
    """
    m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", pfad or "")
    if not m:
        return False
    slug = m.group(1)
    ausweis = (kopfzeilen.get("Authorization") or "") + "|" + \
              (kopfzeilen.get("Cookie") or "")
    if not ausweis.strip("|"):
        return False
    schluessel = (slug, hashlib.sha256(ausweis.encode()).hexdigest()[:16])
    jetzt = time.time()
    gemerkt = _BEREICHSZUGANG.get(schluessel)
    if gemerkt and jetzt - gemerkt[1] < ANZAHL_HALTBAR:
        return gemerkt[0]

    erlaubt = False
    for weg in ("/api/workspace/", "/api/v1/workspace/"):
        req = urllib.request.Request(ZIEL + weg + slug, method="GET")
        for kopf in ("Authorization", "Cookie"):
            wert = kopfzeilen.get(kopf)
            if wert:
                req.add_header(kopf, wert)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status == 200 and (json.load(r) or {}).get("workspace"):
                    erlaubt = True
                    break
        except urllib.error.HTTPError as e:
            # 401/403/404 sind eine Antwort, kein Ausfall: nicht erlaubt.
            if e.code in (401, 403, 404):
                continue
            print("[Zugang] %s%s: HTTP %s" % (weg, slug, e.code),
                  file=sys.stderr, flush=True)
        except Exception as e:
            print("[Zugang] %s%s: %s" % (weg, slug, str(e)[:90]),
                  file=sys.stderr, flush=True)
    _BEREICHSZUGANG[schluessel] = (erlaubt, jetzt)
    return erlaubt


# Welche Dokumente eine Anmeldung sehen darf. Wie _BEREICHSZUGANG an die
# Anmeldung gebunden, nicht nur an den Namen.
_DOKZUGANG = {}

# ⛔ A4-Fix: Den Dokumentzugang persistieren, damit er einen
#   Neustart ueberlebt. Ohne das war _DOKZUGANG nach jedem Neustart leer;
#   dokument_erlaubt fand dann zu einer GUELTIGEN Marke "nichts gemerkt"
#   und liess JEDES Dokument durch (das return True in dokument_erlaubt).
#   Der naheliegende Gegenfix - den Zugang beim Beleg-Klick neu aus der
#   Sitzung ermitteln - scheitert: Beim Klick kommt NUR das
#   ki4ki_zugang-Cookie (keine AnythingLLM-Sitzung), erlaubte_dokumente
#   gaebe dann None und ALLE Belege waeren tot (gemessen). Also den
#   einmal ermittelten Zugang auf Platte legen und beim Start zurueckholen.
#   Datei nur fuer den Proxy lesbar (0600); Eintraege verfallen mit der
#   Marke (ZUGANG_DAUER). Die return-True-Sicherung in dokument_erlaubt
#   bleibt als Uebergangsnetz fuer Marken, die vor diesem Fix ausgestellt
#   wurden - so stirbt in der Umstellung kein Beleg.
_DOKZUGANG_DATEI = (os.environ.get("KI4KI_DOKZUGANG")
                    or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    ".dokzugang.json"))


# Welches KONTO hinter einer Marke steht. Ein Browser-Tab (/kpi, /selbstcheck,
# Beleg-Link) schickt nur das Cookie - ohne diese Zuordnung kannte der Proxy
# dort nur "irgendwer angemeldet" und wies den Admin ab (gemessen 27.08.).
_KONTEN_JE_MARKE = {}


def _konten_speichern():
    try:
        jetzt = time.time()
        raus = {k: v for k, v in _KONTEN_JE_MARKE.items() if jetzt - v[1] < ZUGANG_DAUER}
        pfad = _DOKZUGANG_DATEI + ".konten.json"
        with open(pfad + ".neu", "w", encoding="utf-8") as f:
            json.dump(raus, f)
        os.chmod(pfad + ".neu", 0o600)
        os.replace(pfad + ".neu", pfad)
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _konten_laden():
    try:
        with open(_DOKZUGANG_DATEI + ".konten.json", encoding="utf-8") as f:
            roh = json.load(f) or {}
        jetzt = time.time()
        for k, v in roh.items():
            if isinstance(v, list) and len(v) == 2 and jetzt - float(v[1]) < ZUGANG_DAUER:
                _KONTEN_JE_MARKE[k] = (str(v[0]), float(v[1]))
    except Exception:
        pass


def _konto_merken(kopfzeilen):
    """Bei JEDER Anfrage, die Anmeldungskopfzeile UND Cookie-Marke traegt
    (alles, was die Oberflaeche tut), das Konto zur Marke merken - damit ein
    spaeterer Tab mit nur dem Cookie (/kpi, /selbstcheck) das Konto kennt.
    Gemessen 27.08.: nur beim Laden des Verlaufs zu merken reichte nicht."""
    try:
        if not (kopfzeilen.get("Authorization") or "").strip():
            return
        k = marke_kennung(marke_aus_kopf(kopfzeilen))
        if not k or k in _KONTEN_JE_MARKE:
            return
        konto = pruefprotokoll.konto_aus(kopfzeilen)
        if not konto or konto.startswith(("sitzung-", "dienst-", "unbekannt")):
            return
        _KONTEN_JE_MARKE[k] = (konto, time.time())
        _konten_speichern()
        print("[Einsicht] Marke %s gehoert zu Konto %s" % (k[:6], pruefprotokoll.pseudonym(konto)),
              file=sys.stderr, flush=True)
    except Exception:
        pass


def konto_aus_anfrage(kopfzeilen):
    """Das Konto hinter einer Anfrage - aus der Anmeldungskopfzeile, sonst
    ueber die Marke im Cookie (Browser-Tab ohne Kopfzeile)."""
    try:
        if (kopfzeilen.get("Authorization") or "").strip():
            return pruefprotokoll.konto_aus(kopfzeilen)
    except Exception:
        pass
    try:
        k = marke_kennung(marke_aus_kopf(kopfzeilen))
        if k and k in _KONTEN_JE_MARKE:
            return _KONTEN_JE_MARKE[k][0]
    except Exception:
        pass
    return pruefprotokoll.konto_aus(kopfzeilen)


def _dokzugang_speichern():
    """Den aktuellen Zugang atomar auf Platte schreiben (0600)."""
    try:
        jetzt = time.time()
        raus = {k: [sorted(v[0]), v[1]] for k, v in _DOKZUGANG.items()
                if jetzt - v[1] < ZUGANG_DAUER}
        vorlaeufig = _DOKZUGANG_DATEI + ".neu"
        with open(vorlaeufig, "w", encoding="utf-8") as f:
            json.dump(raus, f)
        os.chmod(vorlaeufig, 0o600)
        os.replace(vorlaeufig, _DOKZUGANG_DATEI)
    except Exception:
        traceback.print_exc(file=sys.stderr)


def _dokzugang_laden():
    """Beim Start den gemerkten Zugang zurueckholen, Abgelaufenes weglassen."""
    try:
        if not os.path.exists(_DOKZUGANG_DATEI):
            return
        with open(_DOKZUGANG_DATEI, encoding="utf-8") as f:
            d = json.load(f) or {}
        jetzt = time.time()
        geladen = 0
        for k, v in d.items():
            try:
                titel, wann = v[0], float(v[1])
            except (TypeError, ValueError, IndexError):
                continue
            if jetzt - wann < ZUGANG_DAUER:
                _DOKZUGANG[k] = (set(titel or []), wann)
                geladen += 1
        print("[Dokzugang] %d Zugaenge aus Platte geladen" % geladen,
              file=sys.stderr, flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)


_dokzugang_laden()
_konten_laden()


def erlaubte_dokumente(kopfzeilen):
    """Alle Dokumenttitel, die diese Anmeldung sehen darf.

    KI4KI-DOKZUGANG. Der Weg: erst die Arbeitsbereiche dieser Anmeldung
    erfragen, dann je Bereich die Dokumente. Ein Administrator bekommt so
    alle, ein Konto ohne Zuweisung keine - beides ohne Sonderfall im Code.

    Rueckgabe eine Menge kleingeschriebener Titel ohne Endung, oder None,
    wenn sich die Bereiche nicht ermitteln liessen. None bedeutet NICHT
    "alles erlaubt", sondern "unbekannt" - der Aufrufer lehnt dann ab.
    """
    ausweis = (kopfzeilen.get("Authorization") or "") + "|" + \
              (kopfzeilen.get("Cookie") or "")
    if not ausweis.strip("|"):
        return None
    marke = hashlib.sha256(ausweis.encode()).hexdigest()[:16]
    jetzt = time.time()
    gemerkt = _DOKZUGANG.get(marke)
    if gemerkt and jetzt - gemerkt[1] < ANZAHL_HALTBAR:
        return gemerkt[0]

    bereiche = None
    for weg in ("/api/workspaces", "/api/v1/workspaces"):
        req = urllib.request.Request(ZIEL + weg, method="GET")
        for kopf in ("Authorization", "Cookie"):
            wert = kopfzeilen.get(kopf)
            if wert:
                req.add_header(kopf, wert)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r) or {}
            liste = d.get("workspaces")
            if liste is None:
                continue
            bereiche = [w.get("slug") for w in liste if w.get("slug")]
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                continue
        except Exception as e:
            print("[Dokzugang] %s: %s" % (weg, str(e)[:80]),
                  file=sys.stderr, flush=True)
    if bereiche is None:
        return None

    erlaubt = set()
    for slug in bereiche:
        titel = titel_im_bereich("/api/workspace/" + slug, kopfzeilen)
        for t in (titel or []):
            stamm = re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", t,
                           flags=re.I).strip().lower()
            if stamm:
                erlaubt.add(stamm)
    _DOKZUGANG[marke] = (erlaubt, jetzt)
    _dokzugang_speichern()   # A4: den Zugang ueber Neustarts hinweg halten
    return erlaubt


def _wurzel_von(schluessel):
    """Der Bereichsordner (dokumente/<bereich>) zu einem PDF-Schluessel - oder None."""
    pfad = PDFS.get(schluessel or "")
    if not pfad:
        return None
    b = metadaten.bereich_von_pfad(pfad, PDF_ORDNER)
    return os.path.join(PDF_ORDNER, b) if b else None


def fuer_ki_freigegeben(name):
    """K3: Sperrt die Metadaten dieses Dokument fuer die KI? True = darf."""
    s = _pdf_schluessel_roh(name) or name
    w = _wurzel_von(s)
    if not w:
        return True
    try:
        return metadaten.fuer_ki(s, w)
    except Exception:
        return True


def dokument_status(name):
    """Kurzer Metadaten-Status fuer Listen ('freigegeben · v3 · gültig bis …') oder ''."""
    s = _pdf_schluessel_roh(name) or name
    w = _wurzel_von(s)
    if not w:
        return ""
    try:
        return metadaten.status_zeile(s, w)
    except Exception:
        return ""


def dokument_warnung(name):
    s = _pdf_schluessel_roh(name) or name
    w = _wurzel_von(s)
    if not w:
        return ""
    try:
        return metadaten.warnung(s, w)
    except Exception:
        return ""


def dokument_erlaubt(stamm, kopfzeilen):
    """Darf diese Anmeldung dieses Dokument sehen?

    Im Zweifel nein. Ohne diese Pruefung kam ein Konto ohne jeden
    Bereichszugang an das vollstaendige PDF (11,6 MB), sobald es
    den Namen kannte - und Richtliniennamen sind oeffentlich.

    ⚠ Beim Klick auf einen Beleg gibt es KEINE Kopfzeilen von AnythingLLM -
    der Browser oeffnet einen neuen Tab und schickt nur das Cookie. Deshalb
    zuerst ueber die Marke nachsehen: Beim Ausstellen wurde gemerkt, was
    diese Sitzung sehen darf. Ohne diesen Weg war jeder
    Fundstellen-Link tot.
    """
    # ⭐ K3: "fuer KI ausschliessen" / nicht freigegeben gilt fuer alle Wege,
    #   auch fuer den Fundstellen-Link.
    if not fuer_ki_freigegeben(stamm):
        return False
    erlaubt = None
    marke = marke_aus_kopf(kopfzeilen)
    if marke_gilt(marke):
        kennung = marke_kennung(marke)
        if kennung:
            gemerkt = _DOKZUGANG.get(kennung)
            if gemerkt is not None:
                # Auch eine LEERE Liste ist eine Antwort: Dieses Konto darf
                # nichts sehen. Nur "gar nichts gemerkt" ist ein Ausfall.
                erlaubt = gemerkt[0]
            else:
                print("[Dokzugang] Marke gueltig, aber nichts gemerkt - "
                      "lasse durch (%s)" % (stamm or "")[:40],
                      file=sys.stderr, flush=True)
                return True
        else:
            # Alte Marke ohne Kennung: durchlassen, sonst waeren alle
            # ausgesperrt, die die Seite noch nicht neu geladen haben.
            return True
    if erlaubt is None:
        erlaubt = erlaubte_dokumente(kopfzeilen)
    if not erlaubt:
        return False
    gesucht = re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", stamm or "",
                     flags=re.I).strip().lower()
    if not gesucht:
        return False
    if gesucht in erlaubt:
        return True
    # Der Bestand traegt Dateinamen ohne Umlaute, die Anzeige mit - und die
    # Endung .md haengt manchen Titeln noch an.
    flach = _flach_stamm(gesucht)
    return any(_flach_stamm(t) == flach for t in erlaubt)


def _flach_stamm(text):
    t = (text or "").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    return re.sub(r"[^a-z0-9]", "", t)


def _ohne_ki_sperre(namen):
    """K3: Dokumente ohne KI-Freigabe aus jeder Liste sieben."""
    try:
        return [n for n in (namen or []) if fuer_ki_freigegeben(n)]
    except Exception:
        return list(namen or [])


def nur_erlaubte(titel, kopfzeilen):
    """Aus einer Titelliste nur die, die diese Anmeldung sehen darf.

    ⛔ A2-Fix: Der Rueckfall auf den Gesamtbestand - wenn ein
    Bereich keine eigene Titelliste hat (leer oder Weltenkonflikt der
    beiden Anmeldearten) - oeffnete sonst ALLE 1256 Dokumente. Die Anlage
    fasste dann ein fremdes Dokument zusammen oder zaehlte fremde Titel
    auf, obwohl bereich_sichtbar nur den Bereich IM PFAD prueft, nicht das
    einzelne Dokument. Hier liegt die volle AnythingLLM-Sitzung vor (der
    Nutzer chattet gerade), darum sieben wir direkt ueber
    erlaubte_dokumente - nicht ueber den Marken-Weg mit seinem
    Uebergangsnetz, das im Chat-Kontext zu grosszuegig waere.

    Laesst sich der Zugang nicht ermitteln (None), wird nichts
    durchgelassen - im Zweifel nein.
    """
    erlaubt = erlaubte_dokumente(kopfzeilen)
    if not erlaubt:
        return []
    flach_erlaubt = {_flach_stamm(x) for x in erlaubt}
    raus = []
    for t in (titel or []):
        gesucht = re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", t or "",
                         flags=re.I).strip().lower()
        if gesucht and (gesucht in erlaubt
                        or _flach_stamm(gesucht) in flach_erlaubt):
            raus.append(t)
    return raus


def erlaubt_pruefer(kopfzeilen):
    """Ein Pruefer name->bool fuer die woertliche Suche (A3).

    Liefert None, wenn sich der Zugang nicht ermitteln laesst - dann soll
    der Aufrufer die woertliche Suche ganz auslassen (im Zweifel nichts
    beilegen), statt aus dem ganzen Bestand zu zitieren. Wie nur_erlaubte
    ueber die volle Chat-Sitzung, nicht ueber den Marken-Weg.
    """
    erlaubt = erlaubte_dokumente(kopfzeilen)
    if not erlaubt:
        return None
    flach_erlaubt = {_flach_stamm(x) for x in erlaubt}

    def pruef(name):
        g = re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", name or "",
                   flags=re.I).strip().lower()
        return bool(g) and (g in erlaubt or _flach_stamm(g) in flach_erlaubt)

    return pruef


# --- KI4KI-POSITIVLISTE: destruktive Verwaltungsbefehle -------------------
# AnythingLLM reicht ueber Schluessel + Port 3001 die VOLLE Verwaltung durch:
# Nutzer anlegen/loeschen, Instanz-Einstellungen aendern, API-Schluessel
# ausstellen. Der Proxy ist die einzige Tuer - hier gehoert der Riegel.
#
# ⚠ NICHT betroffen (bewusst): Chat, Belege, Dokument-Upload und Einbettung
#   (die Aufnahme ueber n8n braucht sie), und die Oberflaeche der Nutzer,
#   die ueber /api/... spricht - NICHT ueber /api/v1/admin. Getroffen wird
#   nur die entwickler-seitige Verwaltung (/api/v1/admin, /api/v1/system)
#   mit aendernden Methoden.
#
# Standard "melden": NICHTS wird gesperrt, jeder solche Aufruf steht nur im
# Protokoll. So bricht nichts Legitimes, bevor jemand die Meldungen gesehen
# hat. Erst wenn dort nur die erwarteten Aufrufe stehen, auf "sperren"
# stellen (KI4KI_POSITIVLISTE=sperren).
POSITIVLISTE = (os.environ.get("KI4KI_POSITIVLISTE") or "melden").strip().lower()
_VERWALTUNG = re.compile(r"^/api/v1/(admin|system)(/|$)")
_AENDERNDE_METHODEN = ("POST", "PUT", "PATCH", "DELETE")


def verwaltungsbefehl(methode, pfad):
    """Ein aendernder Verwaltungsbefehl an AnythingLLMs Entwickler-Schnittstelle?"""
    return methode in _AENDERNDE_METHODEN and \
        bool(_VERWALTUNG.match((pfad or "").split("?")[0]))


# Wohin n8n seinen Anstoss legt. Der Waechter sieht in dieselbe Datei.
ANSTOSS_DATEI = (os.environ.get("KI4KI_ANSTOSS")
                 or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 ".anstoss"))
ANSTOSS = re.compile(r"^/anstoss/?$")


# Der Weg, auf dem n8n von aussen angestossen wird. Leer = kein Aufruf.
#
# Zwei Anlagen, zwei Wege zur selben Sache:
#   Auf dem Ursprungssystem macht die Verarbeitung die Skript-Kette (Zyklus), und
#   der Waechter liest die Anstoss-Datei. n8n weckt nur.
#   Im Partner-Paket gibt es weder Waechter noch Zyklus - dort MUSS n8n
#   die Arbeit tun, und eine Datei liest niemand.
# Deshalb legt der Upload beides ab: die Datei fuer den Waechter UND, wenn
# dieser Weg gesetzt ist, einen Aufruf an n8n. Wer nur eins von beidem
# betreibt, setzt das andere einfach nicht.
AUFNAHME_HAKEN = os.environ.get("KI4KI_AUFNAHME_HAKEN") or ""


def aufnahme_anstossen(grund=""):
    """n8n von aussen anstossen. Wirft nie - ein Upload ist auch dann
    angekommen, wenn die Aufnahme gerade nicht erreichbar ist."""
    if not AUFNAHME_HAKEN:
        return False, "kein Aufnahme-Weg eingestellt"
    try:
        daten = json.dumps({"grund": (grund or "Upload")[:120]}).encode()
        a = urllib.request.Request(
            AUFNAHME_HAKEN, data=daten,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(a, timeout=20) as r:
            return True, "n8n angestossen (HTTP %s)" % r.status
    except Exception as e:
        # Kein Abbruch: Die Datei liegt im Eingang, der Zeitplan holt sie
        # spaetestens beim naechsten Durchgang.
        return False, str(e)[:120]


def anstoss_ablegen(grund=""):
    """Die Anstoss-Datei schreiben. Rueckgabe (ok, Meldung).

    KI4KI-ANSTOSS. Absichtlich nur eine Datei und kein Prozessstart: Der
    Proxy laeuft im Container als uid 1001 und koennte zyklus.sh gar nicht
    ausfuehren - das Skript steuert Docker-Container. Die Trennung ist also
    keine Vorsicht, sondern Notwendigkeit.
    """
    try:
        with open(ANSTOSS_DATEI, "w", encoding="utf-8") as fh:
            fh.write("%d %s\n" % (int(time.time()), (grund or "n8n")[:120]))
        return True, "Anstoss abgelegt"
    except Exception as e:
        return False, str(e)[:150]

def dokumente_im_bereich(pfad, kopfzeilen):
    """Zahl fuer die Zwischenstandszeile - oder None, wenn unbekannt."""
    m = re.match(r"^/api/workspace/([^/]+)/", pfad or "")
    if not m:
        return None
    slug = m.group(1)
    jetzt = time.time()
    gemerkt = _ANZAHL.get(slug)
    if gemerkt and jetzt - gemerkt[1] < ANZAHL_HALTBAR:
        return gemerkt[0]
    # AnythingLLM hat zwei getrennte Anmeldewelten:
    #   /api/v1/...  erwartet einen API-Schluessel  (n8n, Wartungsskripte)
    #   /api/...     erwartet den Sitzungs-Token    (Browser-Oberflaeche)
    # Gemessen: /api/v1/workspace/auw antwortet mit
    # API-Schluessel 200, ohne 403 - und /api/workspace/auw weist denselben
    # API-Schluessel mit 401 ab. Wer nur /api/v1/ fragt, bekommt aus dem
    # Browser also nie eine Antwort, und die Zwischenstandszeile faellt auf
    # den Gesamtbestand zurueck (1094 statt 47).
    # Deshalb beide Wege der Reihe nach - der erste, der antwortet, zaehlt.
    n = None
    letzter_fehler = "keine Antwort"
    for weg in ("/api/workspace/", "/api/v1/workspace/"):
        req = urllib.request.Request(ZIEL + weg + slug, method="GET")
        for kopf in ("Authorization", "Cookie"):
            wert = kopfzeilen.get(kopf)
            if wert:
                req.add_header(kopf, wert)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                w = json.load(r).get("workspace")
            w = w[0] if isinstance(w, list) else w
            n = len((w or {}).get("documents") or [])
            break
        except Exception as e:
            letzter_fehler = "%s -> %s" % (weg, str(e)[:70])
    try:
        if n is None:
            raise RuntimeError(letzter_fehler)
    except Exception as e:
        # Vorher still. Wenn das hier fehlschlaegt, nennt die
        # Zwischenstandszeile den Gesamtbestand statt der Dokumente des
        # Bereichs - und niemand sieht, warum.
        # Bleibt als Meldung stehen: Wenn diese Abfrage scheitert, nennt
        # die Zwischenstandszeile den Gesamtbestand statt der Dokumente des
        # Bereichs - und ohne diese Zeile sieht niemand, warum.
        print("[Anzahl] %s: %s" % (slug, str(e)[:150]),
              file=sys.stderr, flush=True)
        return None
    _ANZAHL[slug] = (n, jetzt)
    return n


def titel_im_bereich(pfad, kopfzeilen):
    return _ohne_ki_sperre(_titel_im_bereich_roh(pfad, kopfzeilen))


def _titel_im_bereich_roh(pfad, kopfzeilen):
    """Die Dokumenttitel eines Arbeitsbereichs - oder None.

    Fast dieselbe Abfrage wie dokumente_im_bereich, aber mit den Titeln
    statt nur der Zahl. Bewusst als eigene Funktion mit eigenem
    Zwischenspeicher: dokumente_im_bereich laeuft bei JEDER Anfrage und
    darf nicht umgebaut werden, nur damit Bestandsfragen (die selten sind)
    etwas mehr bekommen.

    Auch hier beide Anmeldewelten der Reihe nach - aus dem Browser kommt
    ein Sitzungs-Token, aus n8n ein API-Schluessel, und jede der beiden
    Routen weist die jeweils andere ab.
    """
    m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", pfad or "")
    if not m:
        return None
    slug = m.group(1)
    jetzt = time.time()
    gemerkt = _TITEL.get(slug)
    if gemerkt and jetzt - gemerkt[1] < ANZAHL_HALTBAR:
        return gemerkt[0]
    for weg in ("/api/workspace/", "/api/v1/workspace/"):
        req = urllib.request.Request(ZIEL + weg + slug, method="GET")
        for kopf in ("Authorization", "Cookie"):
            wert = kopfzeilen.get(kopf)
            if wert:
                req.add_header(kopf, wert)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                w = json.load(r).get("workspace")
            w = w[0] if isinstance(w, list) else w
            titel = []
            for d in ((w or {}).get("documents") or []):
                # Zuerst der lesbare Titel aus der abgelegten Datei. Was
                # ueber die Schnittstelle kommt, ist der normalisierte
                # Dateiname - fuer eine Liste, die jemand liest, ist das
                # die schlechtere Wahl.
                name = _titel_aus_json(d.get("docpath"))
                if not name:
                    name = d.get("title") or d.get("filename") or ""
                    if not name and d.get("metadata"):
                        try:
                            name = (json.loads(d["metadata"]) or {}).get("title") or ""
                        except Exception:
                            name = ""
                # Aus "BS-00-000.md-<uuid>.json" wieder "BS-00-000.md" machen.
                name = re.sub(r"\.md-[0-9a-f-]{36}\.json$", ".md", name)
                if name:
                    titel.append(name)
            if titel:
                _TITEL[slug] = (titel, jetzt)
                return titel
        except Exception as e:
            if "403" in str(e):
                continue     # kein Zugang dieser Sitzung zu dem Bereich - normal, kein Fehler
            print("[Titel] %s%s: %s" % (weg, slug, str(e)[:90]),
                  file=sys.stderr, flush=True)
    return None


_TITELNAMEN = {}
_TITELNAMEN_STAND = [0.0]


def titelnamen():
    """Lesbarer Titel -> Name, unter dem die Datei abgelegt ist.

    ⭐ Vorgabe: Das Modell soll den Titel lesen, die Verlinkungen
       aber immer an den Dateinamen haengen.

    Die Ablage traegt beides: Der Dateiname ist der Speichername, das Feld
    "title" darin ist, was das Modell zu sehen bekommt.

        XY00-Beispiel-Handbuch.md-<uuid>.json
        "title": "[XY00] Beispiel-Handbuch.md"

    ⚠ Es werden ZWEI Formen eingetragen: der Titel selbst und derselbe
      ohne fuehrendes Klammer-Kuerzel. Das Modell laesst "[HW14] " weg -
      es haelt die Klammer fuer eine Literaturangabe. Ohne die zweite Form
      bleibt genau der Fall unverlinkt, der am haeufigsten vorkommt.

    ⚠ Wird hoechstens alle fuenf Minuten neu gelesen. Bei 1249 Dokumenten
      sind das 1249 Dateizugriffe; bei jeder Antwort waere das zu teuer.
    """
    jetzt = time.time()
    if _TITELNAMEN and jetzt - _TITELNAMEN_STAND[0] < 300:
        return _TITELNAMEN
    mehrdeutig = set()
    neu = {}
    try:
        for wurzel, _, dateien in os.walk(BESTAND_ORDNER):
            for d in dateien:
                if not d.endswith(".json"):
                    continue
                stamm = re.sub(r"\.md-[0-9a-f-]{36}\.json$", "", d)
                if stamm == d:
                    continue
                titel = _titel_aus_json(
                    os.path.relpath(os.path.join(wurzel, d), BESTAND_ORDNER))
                if not titel:
                    continue
                if titel.endswith(".md"):
                    titel = titel[:-3]
                formen = [titel]
                # ⚠ Zweite Form: ohne fuehrendes "[XY] ". Genau die
                #   schreibt das Modell.
                ohne = re.sub(r"^\[[^\]]{1,12}\]\s*", "", titel)
                if ohne != titel and len(ohne) >= 6:
                    formen.append(ohne)
                for f in formen:
                    if f == stamm:
                        continue
                    if f in neu and neu[f] != stamm:
                        mehrdeutig.add(f)
                    neu[f] = stamm
    except Exception as e:
        print("[Titelnamen] %s" % str(e)[:100], file=sys.stderr, flush=True)
        return _TITELNAMEN
    for f in mehrdeutig:
        neu.pop(f, None)
    _TITELNAMEN.clear()
    _TITELNAMEN.update(neu)
    _TITELNAMEN_STAND[0] = jetzt
    return _TITELNAMEN


def bestandsschluessel(anzeigetitel):
    """Vom lesbaren Titel zurueck auf den Namen, unter dem der Bestand
    das Dokument fuehrt.

    Die Anzeige zeigt "LE Klangpruefung" (aus dem Feld "title"), der
    Bestand fuehrt "LE-Klangpruefung.md" (nach Dateiname). Ohne diese
    Umrechnung findet BESTAND.hol() nichts, und die Zusammenfassung faellt
    unbemerkt auf den gewoehnlichen Suchweg zurueck.
    """
    if not anzeigetitel:
        return None
    try:
        BESTAND.aktualisiere()
        alle = BESTAND.titel()
    except Exception:
        return anzeigetitel
    if anzeigetitel in alle:
        return anzeigetitel
    ziel = assistent._flach(
        anzeigetitel[:-3] if anzeigetitel.endswith(".md") else anzeigetitel)
    for t in alle:
        stamm = t[:-3] if t.endswith(".md") else t
        if assistent._flach(stamm) == ziel:
            return t
    return None


def _titel_aus_json(docpath):
    """Den lesbaren Titel aus der Dokument-Ablage holen.

    AnythingLLM gibt ueber die Schnittstelle den normalisierten Dateinamen
    zurueck ("DVS-2290-praktischer-Leitfaden"). Der lesbare Titel
    ("DVS 2290 praktischer Leitfaden") steht im Feld "title" der abgelegten
    JSON-Datei, und "docpath" sagt, wo sie liegt.

    Die Dateien tragen den vollen Dokumenttext; deshalb wird nur der Anfang
    gelesen. Der Titel steht in den ersten Zeilen, der Rest waere bei 1249
    Dokumenten unnoetiger Aufwand.
    """
    if not docpath:
        return None
    pfad = os.path.join(BESTAND_ORDNER, docpath)
    if not os.path.exists(pfad):
        return None
    try:
        with open(pfad, encoding="utf-8") as fh:
            kopf = fh.read(4000)
        m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', kopf)
        if not m:
            return None
        return json.loads('"%s"' % m.group(1))
    except Exception:
        return None


def pdfs_einlesen():
    """Alle Quell-PDFs einlesen - auch die in den Abteilungsordnern.

    Frueher stand hier glob("*.pdf") ueber die oberste Ebene. Damit fehlten
    dem Proxy alle Dokumente aus inbox/<abteilung>/: Ihre Zitate liessen
    sich nicht im Original nachschlagen, und jede Antwort daraus trug
    "Fundstelle nicht automatisch bestimmbar" - obwohl der Inhalt stimmte.

    os.walk statt glob hat einen zweiten Grund: In Dateinamen wie
    "[Ehr06] Faserverbundkunststoffe..." liest glob die eckigen Klammern
    als Zeichenklasse.
    """
    PDFS.clear()
    PDFS_GRUND.clear()
    for wurzel, _, dateien in os.walk(PDF_ORDNER):
        for d in dateien:
            if d.lower().endswith(".pdf"):
                # Bei gleichem Namen in mehreren Ordnern gewinnt der erste
                # Fund - die oberste Ebene wird zuerst durchlaufen.
                PDFS.setdefault(d[:-4], os.path.join(wurzel, d))
                PDFS_GRUND.setdefault(_grundform(d[:-4]), d[:-4])
    return len(PDFS)


def _grundform(name):
    """Kleinschreibung, nur Buchstaben und Ziffern.

    Damit fallen Leerzeichen (auch geschuetzte), Binde- und Unterstriche
    weg - genau die Zeichen, an denen der exakte Vergleich scheitert.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


_PDFS_SPERRE = threading.Lock()
_PDFS_STAND = [0.0]

# Die laufende Frage und ihre Quellen - fuer die Abbildungs-Auswahl unter
# der Antwort (ThreadingHTTPServer: ein Thread je Anfrage).
_ANFRAGE = threading.local()


def _pdfs_erneuern_wenn_faellig():
    """Das PDF-Verzeichnis nachladen - gedrosselt.

    Der Index entsteht beim Start. Auf einer frischen Anlage startet der
    Proxy aber IMMER, bevor das erste PDF existiert - ohne Nachladen
    blieben gelbe Markierung, Beleg-Sprung und Abbildungs-Ausgabe
    dauerhaft ohne Original ("Fundstelle nicht automatisch bestimmbar"),
    bis jemand den Proxy von Hand neu startet. Dieselbe Fehlerklasse wie
    beim Wortverzeichnis: abgesichert war, was da ist - nicht, was noch
    fehlt. Und: Die Aufnahme VERSCHIEBT Dateien (input/ -> archiv/), auch
    ein gemerkter Pfad kann also veralten.

    Hoechstens alle 15 Sekunden, sonst bezahlt jede vergebliche Suche
    einen kompletten Verzeichnislauf.
    """
    jetzt = time.time()
    with _PDFS_SPERRE:
        if jetzt - _PDFS_STAND[0] < 15:
            return
        _PDFS_STAND[0] = jetzt
        pdfs_einlesen()


def _pdf_schluessel_roh(name):
    """Den echten Schluessel in PDFS zu einem geschriebenen Namen finden.

    ⚠ EINE Funktion fuer ALLE sieben Nachschlagestellen. Vorher verglich
      jede fuer sich exakt; eine davon zu vergessen faellt jetzt beim
      Zaehlen auf, statt sich als toter Verweis zu zeigen.
    """
    if not name:
        return None
    if name in PDFS:
        return name
    for endung in (".pdf", ".md"):
        if name.lower().endswith(endung):
            kurz = name[:-len(endung)]
            if kurz in PDFS:
                return kurz
            name = kurz
            break
    return PDFS_GRUND.get(_grundform(name))


def _pdf_schluessel(name):
    """Wie _pdf_schluessel_roh - aber bei Fehlschlag einmal nachladen.

    Fehlschlag heisst: Schluessel unbekannt ODER der gemerkte Pfad
    existiert nicht mehr (Datei von der Aufnahme verschoben).
    """
    s = _pdf_schluessel_roh(name)
    if s and os.path.exists(PDFS.get(s, "")):
        return s
    if not name:
        return None
    _pdfs_erneuern_wenn_faellig()
    return _pdf_schluessel_roh(name)


_SEITENZAHLEN = {}


def _seitenzahl_schnell(pfad):
    """Seitenzahl per pdfinfo (Millisekunden) - NICHT ueber den Volltext,
    sonst zieht die Index-Tabelle eines Bereichs mit 60 Arbeiten beim
    ersten Aufruf minutenlang pdftotext hinter sich her."""
    if not pfad:
        return 0
    try:
        st = os.stat(pfad)
    except OSError:
        return 0
    k = (pfad, st.st_mtime_ns, st.st_size)
    if k in _SEITENZAHLEN:
        return _SEITENZAHLEN[k]
    n = 0
    try:
        import subprocess
        aus = subprocess.run(["pdfinfo", pfad], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"^Pages:\s+(\d+)", aus, re.M)
        n = int(m.group(1)) if m else 0
    except Exception:
        n = 0
    _SEITENZAHLEN[k] = n
    return n


def _archivdatei(name):
    """Die Originaldatei zu einem Stamm in irgendeinem <bereich>/archiv/ -
    fuer Dokumente ohne PDF (Excel, Word ...). None, wenn es keine gibt."""
    ziel = _loesch_grund(_stamm(name))
    if not ziel:
        return None
    try:
        bereiche = sorted(os.listdir(EINGANG_ORDNER))
    except Exception:
        return None
    for bereich in bereiche:
        archiv = os.path.join(EINGANG_ORDNER, bereich, "archiv")
        try:
            # Die Nicht-PDF-Datei zuerst (Original neben einer gewandelten PDF)
            for d in sorted(os.listdir(archiv), key=lambda x: x.lower().endswith(".pdf")):
                if not d.startswith(".") and _loesch_grund(_stamm(d)) == ziel:
                    return os.path.join(archiv, d)
        except Exception:
            continue
    return None


def _seiten_ohne_pdf(name):
    """Seitentexte aus dem Bestandstext - fuer Dokumente ohne PDF (Excel,
    Word, Text). Die Aufnahme setzt [Seite n]-Marken; fehlen sie, ist der
    ganze Text eine Seite. Gemessen 26.08.: Die Pruefungs-Excel im Bereich
    AuW war fuer seiten_lesen/bestand_durchsuchen unsichtbar - das Modell
    erfand daraufhin Fragen und Zitate."""
    try:
        s = bestandsschluessel(name)
        d = BESTAND.hol(s) if s else None
    except Exception:
        d = None
    return pruefungskatalog.seiten_aus_text((getattr(d, "text", "") or "") if d else "")


def _seitentexte_pdf(schluessel):
    """Seitentexte eines PDFs - pdftotext, und bei SCANS je Seite der OCR-Text
    aus dem Bestand (Docling). Gemessen 27.08. (AuW): Testfragen DVS 2290 =
    98 Zeichen auf 7 Seiten per pdftotext, 18 292 per OCR; DVS 2213-1 Teil 1 =
    5 609 gegen 75 457. Die Belegpruefung las nur pdftotext - jedes Zitat aus
    einem Scan galt als "nicht gefunden", jeder Beleg als "ohne Deckung".
    Regel: Seite unter 40 Zeichen -> OCR-Seite, wenn sie mehr hat."""
    if not schluessel:
        return []
    try:
        seiten = pdfstelle.seitentexte(schluessel) or []
    except Exception:
        seiten = []
    gesamt = sum(len((t or "").strip()) for t in seiten)
    if seiten and gesamt >= 60 * len(seiten):
        # Textlayer vorhanden: NUR pdftotext. ⛔ Keine seitenweise Mischung mit
        # dem OCR-Text (gemessen 27.08.: die [Seite n]-Marken der Aufnahme sind
        # GEDRUCKTE Seitenzahlen, pdftotext zaehlt physisch - eine duenne Seite 11
        # bekam die OCR-Seite 11 = Kapitel 2, und "Bild 2.1" wanderte von der
        # echten Seite 14 auf Seite 11: weisse Seite im Chat).
        return seiten
    ocr = _seiten_ohne_pdf(schluessel)
    if not ocr:
        return seiten
    if not seiten:
        return ocr
    # Scan (kein oder kaum Textlayer): OCR-Fassung als Ganzes - nur wenn die
    # Seitenzahlen zusammenpassen; sonst pdftotext, so duenn es ist.
    ocr_gesamt = sum(len(t.strip()) for t in ocr)
    if ocr_gesamt > gesamt and abs(len(ocr) - len(seiten)) <= 2:
        return ocr if len(ocr) == len(seiten) else (ocr + [""] * (len(seiten) - len(ocr)))[:len(seiten)]
    return seiten


def _seitentexte_von(name):
    """(pdf_schluessel oder None, Seitentexte) - PDF ueber pdfstelle (+OCR bei
    Scans), sonst aus dem Bestandstext. EINE Stelle fuer alle Werkzeuge."""
    sch = _pdf_schluessel(name)
    if sch:
        return sch, _seitentexte_pdf(sch)
    return None, _seiten_ohne_pdf(name)


STELLE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{dok}, Seite {seite}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin:0; background:#2b2b28; color:#e8e8e4;
         font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
  header {{ background:#3a3a3a; color:#fff; padding:.9rem 1.2rem;
        display:flex; gap:1.2rem; align-items:baseline; flex-wrap:wrap; }}
  header b {{ font-size:1rem; }}
  header span {{ opacity:.85; font-size:.85rem; }}
  header a {{ color:#fff; text-decoration:none; border-bottom:1px solid rgba(255,255,255,.5); }}
  nav {{ padding:.7rem 1.2rem; display:flex; gap:1.4rem; align-items:center;
        background:#3a3a36; font-size:.9rem; }}
  nav a {{ color:#9ec7ee; text-decoration:none; }}
  nav a:hover {{ text-decoration:underline; }}
  nav .aus {{ color:#7a7a74; }}
  main {{ padding:1.2rem; text-align:center; }}
  img {{ max-width:100%; height:auto; background:#fff;
        box-shadow:0 2px 18px rgba(0,0,0,.5); }}
  /* Der Hinweis stand frueher als blasses <span> im Kopf zwischen
     Seitenzahl und PDF-Verweis - und wurde uebersehen. Steht die belegte
     Stelle nicht auf der Seite, ist das die wichtigste Information der
     ganzen Ansicht: ohne sie haelt der Leser den Beleg fuer erfunden.
     Bernstein, nicht Rot - die Stelle fehlt nicht, sie steht woanders. */
  .lage {{ margin:0; padding:.6rem 1.2rem; font-size:.9rem;
        background:#33372f; color:#cfe8b8; }}
  .lage.weg {{ background:#7a4a00; color:#ffeccd; font-size:.98rem;
        font-weight:600; }}
  .lage a {{ color:#fff; }}
</style>
<header>
  <b>{dok}.pdf</b>
  <span>Seite {seite} von {gesamt}</span>
  <a href="{pdf}" target="_blank" rel="noopener">Original-PDF öffnen</a>
</header>
{hinweis}
<nav>{zurueck}<span class="aus">·</span>{vor}</nav>
<main><img src="{bild}" alt="Seite {seite} von {dok}"></main>
"""


# Kleines Skript, das in die ausgelieferte Oberflaeche gehaengt wird.
# AnythingLLM stellt die Quellenspalte selbst dar und macht aus dem Titel
# keinen Verweis. Statt AnythingLLM zu veraendern (Fork), wird die Seite
# beim Durchreichen um dieses Skript ergaenzt: Es erkennt Eintraege der
# Form "NAME.pdf . Seite 13" und macht sie anklickbar.
EINHAENGER = """
<script>
(function () {
// ⚠ Die alte Zeichenklasse kannte KEIN Leerzeichen.
  //   Nachgezaehlt: 61 von 1263 Arbeiten bekamen deshalb keinen Klick
  //   auf die Originalseite - 55 davon nur wegen eines Leerzeichens im
  //   Namen ("DS-0000 IV"), eine wegen eines GESCHUETZTEN
  //   Leerzeichens, das man gar nicht sieht.
  //   Jetzt: alles ausser dem Trennpunkt. Die Anker am Anfang und Ende
  //   halten das Muster trotzdem eng.
  var MUSTER = /^\\s*([^\u00b7\\n]+?)\\.pdf\\s*\u00b7\\s*Seite\\s*(\\d+)\\s*$/;

  function anklickbar(knoten) {
    if (knoten.dataset && knoten.dataset.stelleFertig) return;
    var m = MUSTER.exec(knoten.textContent || "");
    if (!m) return;
    knoten.dataset.stelleFertig = "1";
    var a = document.createElement("a");
    a.href = "/stelle?dok=" + encodeURIComponent(m[1]) + "&seite=" + m[2];
    a.target = "_blank";
    a.rel = "noopener";
    a.title = "Seite " + m[2] + " im Original-PDF ansehen";
    a.style.cssText = "color:inherit;text-decoration:underline;text-underline-offset:3px;cursor:pointer";
    a.textContent = knoten.textContent;
    knoten.textContent = "";
    knoten.appendChild(a);
  }

  function durchgehen() {
    var alle = document.querySelectorAll("div,span,p,h1,h2,h3,h4,li");
    for (var i = 0; i < alle.length; i++) {
      var k = alle[i];
      if (k.children.length === 0) anklickbar(k);
    }
  }

  // ki4ki-neuertab: Verweise auf PDFs im neuen Tab oeffnen.
  //
  // ⚠ Die Bestandsliste liefert Verweise als Markdown ([DS-00008](/pdf/…)).
  //   Markdown kennt kein Ziel-Attribut, der Klick wuerde also im selben
  //   Tab oeffnen - und der Gespraechsverlauf waere weg. Die Belegspruenge
  //   weiter oben setzen es selbst; hier wird es fuer alles Uebrige
  //   nachgeholt.
  function neueTabs() {
    var alle = document.querySelectorAll(
      'a[href^="/pdf/"], a[href^="/stelle"], a[href*="/pdf/"]');
    for (var i = 0; i < alle.length; i++) {
      if (alle[i].target === "_blank") continue;
      alle[i].target = "_blank";
      alle[i].rel = "noopener";
    }
  }

  var wartend = null;
  new MutationObserver(function () {
    clearTimeout(wartend);
    wartend = setTimeout(function () { durchgehen(); neueTabs(); }, 250);
  }).observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(function () { durchgehen(); neueTabs(); }, 1200);
})();
</script>

<script>
(function () {
  // ki4ki-kopieren-4: Kopieren ohne HTTPS - an DER Stelle, die der
  // Chat-Knopf wirklich benutzt.
  //
  // Die Oberflaeche kopiert per clipboard.write mit ClipboardItem:
  //     await navigator.clipboard.write([new ClipboardItem({...})])
  // Also clipboard.WRITE mit ClipboardItem, nicht writeText. Drei
  // Anlaeufe an writeText haben diese Stelle nie beruehrt.
  //
  // Der Fehler landet dort in einem catch, das ihn nur in die Konsole
  // schreibt - deshalb setzte die Oberflaeche den Haken, obwohl die
  // Zwischenablage leer blieb.
  //
  // ⚠ Ohne HTTPS ist navigator.clipboard zwar VORHANDEN, lehnt aber ab.
  //   Und die Ablehnung kommt asynchron: danach ist die Benutzergeste
  //   vorbei und execCommand darf nicht mehr. Deshalb wird hier gar nicht
  //   erst probiert, sondern sofort synchron kopiert.
  if (window.isSecureContext === true) return;   // mit HTTPS ist alles gut

  // --- Text mitschreiben, bevor er im Blob verschwindet -----------------
  // Einen Blob zu LESEN ist asynchron. Also merken wir uns die
  // Zeichenkette schon beim Bauen.
  var EchtBlob = window.Blob;
  var blobText = new WeakMap();
  if (EchtBlob) {
    var MeinBlob = function (teile, o) {
      var b = new EchtBlob(teile || [], o);
      try {
        if (teile && teile.length === 1 && typeof teile[0] === "string") {
          blobText.set(b, teile[0]);
        }
      } catch (e) {}
      return b;                       // ⚠ echter Blob, nur beobachtet
    };
    MeinBlob.prototype = EchtBlob.prototype;
    try { window.Blob = MeinBlob; } catch (e) {}
  }

  // ⚠ Ohne HTTPS gibt es ClipboardItem in Firefox nicht. Der Umschlag
  //   darf daher NICHT nur gebaut werden, wenn die Klasse schon existiert -
  //   sonst stuerzt bereits "new ClipboardItem({...})" mit
  //       ReferenceError: ClipboardItem is not defined
  //   ab, das catch schluckt es und setzt trotzdem den Haken. Regel:
  //   absichern, was FEHLT, nicht nur, was DA ist.
  var EchtItem = window.ClipboardItem;
  var itemDaten = new WeakMap();
  var MeinItem;
  if (EchtItem) {
    MeinItem = function (daten, o) {
      var it = new EchtItem(daten, o);
      try { itemDaten.set(it, daten); } catch (e) {}
      return it;
    };
    MeinItem.prototype = EchtItem.prototype;
  } else {
    // Fehlt die Klasse, stellen wir sie selbst - ein schlichter Behaelter,
    // der sich nur merkt, was hineingelegt wurde. Mehr braucht unser
    // write() nicht.
    MeinItem = function EigenerItem(daten, o) {
      this.types = [];
      try { this.types = Object.keys(daten || {}); } catch (e) {}
      this.presentationStyle = (o && o.presentationStyle) || "unspecified";
      try { itemDaten.set(this, daten); } catch (e) {}
    };
    MeinItem.prototype.getType = function (art) {
      var d = itemDaten.get(this) || {};
      return d[art] ? Promise.resolve(d[art])
                    : Promise.reject(new Error("kein " + art));
    };
  }
  try { window.ClipboardItem = MeinItem; } catch (e) {}

  // --- Synchron kopieren, mit Formatierung ------------------------------
  function kopiereSofort(text, html) {
    if (!text && !html) return false;
    var griff = function (e) {
      try {
        if (text) e.clipboardData.setData("text/plain", text);
        if (html) e.clipboardData.setData("text/html", html);
        e.preventDefault();
      } catch (x) {}
    };
    document.addEventListener("copy", griff, true);
    var geklappt = false;
    try {
      // Eine Auswahl muss bestehen, sonst tut execCommand nichts.
      var feld = document.createElement("textarea");
      feld.value = text || " ";
      feld.setAttribute("readonly", "");
      feld.style.cssText = "position:fixed;top:0;left:-9999px;opacity:0";
      document.body.appendChild(feld);
      var vorher = document.activeElement;
      feld.focus();
      feld.select();
      geklappt = document.execCommand && document.execCommand("copy");
      document.body.removeChild(feld);
      if (vorher && vorher.focus) { try { vorher.focus(); } catch (x) {} }
    } catch (x) {}
    document.removeEventListener("copy", griff, true);
    return !!geklappt;
  }

  function sagen(text) {
    var k = document.createElement("div");
    k.textContent = text;
    k.style.cssText =
      "position:fixed;bottom:26px;left:50%;transform:translateX(-50%);" +
      "z-index:2147483647;background:#11151c;color:#e8edf5;padding:11px 18px;" +
      "border:1px solid #b45309;border-radius:8px;" +
      "font:14px system-ui,-apple-system,Segoe UI,sans-serif";
    document.body.appendChild(k);
    setTimeout(function () { k.remove(); }, 6000);
  }

  var ersatz = {
    writeText: function (t) {
      return kopiereSofort(String(t == null ? "" : t), "")
             ? Promise.resolve()
             : (sagen("Kopieren hat nicht geklappt \u2014 bitte von Hand markieren."),
                Promise.reject(new Error("execCommand")));
    },
    write: function (stuecke) {
      var text = "", html = "";
      try {
        (stuecke || []).forEach(function (it) {
          var d = itemDaten.get(it);
          if (!d) return;
          if (d["text/plain"]) text = blobText.get(d["text/plain"]) || text;
          if (d["text/html"]) html = blobText.get(d["text/html"]) || html;
        });
      } catch (e) {}
      return kopiereSofort(text, html)
             ? Promise.resolve()
             : (sagen("Kopieren hat nicht geklappt \u2014 bitte von Hand markieren."),
                Promise.reject(new Error("execCommand")));
    },
    readText: function () { return Promise.reject(new Error("nicht verfuegbar")); },
    read: function () { return Promise.reject(new Error("nicht verfuegbar")); }
  };

  try {
    Object.defineProperty(navigator, "clipboard", {
      value: ersatz, configurable: true
    });
  } catch (e) {
    try { navigator.clipboard = ersatz; } catch (e2) {}
  }
})();
</script>

<script>
(function () {
  // Bleibender Hinweis nach dem Hochladen.
  // Das Upload-Feld der Anwendung verschwindet von selbst und ist schmal -
  // der Text war oft nicht zu Ende lesbar. Diese Karte
  // bleibt stehen, bis man sie wegklickt.
  var ID = "ki4ki-hinweis";

  function zeigen(art, text) {
    var alt = document.getElementById(ID);
    if (alt) alt.remove();
    var farbe = art === "dublette" ? "#b45309" : "#15803d";
    var titel = art === "dublette" ? "Nicht hochgeladen"
                                   : "Angenommen — die Aufbereitung läuft";
    var k = document.createElement("div");
    k.id = ID;
    k.setAttribute("role", "status");
    k.style.cssText =
      "position:fixed;top:24px;left:50%;transform:translateX(-50%);" +
      "z-index:2147483647;max-width:620px;width:calc(100% - 48px);" +
      "background:#11151c;color:#e8edf5;border:1px solid " + farbe + ";" +
      "border-left:5px solid " + farbe + ";border-radius:10px;" +
      "padding:18px 20px;box-shadow:0 12px 40px rgba(0,0,0,.55);" +
      "font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif";
    var h = document.createElement("div");
    h.textContent = titel;
    h.style.cssText = "font-weight:600;font-size:16px;margin-bottom:8px;color:" + farbe.replace("#15803d", "#4ade80").replace("#b45309", "#fbbf24");
    var p = document.createElement("div");
    p.textContent = text;
    var b = document.createElement("button");
    b.textContent = "Verstanden";
    b.style.cssText =
      "margin-top:14px;padding:8px 18px;border-radius:7px;cursor:pointer;" +
      "border:1px solid #3a4454;background:#1b212b;color:#e8edf5;font:inherit";
    b.onclick = function () { k.remove(); };
    k.appendChild(h); k.appendChild(p); k.appendChild(b);
    document.body.appendChild(k);
    // ⚠ KEIN Zeitschalter. Der Hinweis geht weg, wenn der Mensch das sagt -
    //   nicht wenn eine Uhr abgelaufen ist. Ein Zeitschalter war zuvor das Problem.
  }

  function istUpload(u) {
    return typeof u === "string" && /\\/api\\/workspace\\/[^/]+\\/upload/.test(u);
  }

  // KI4KI-KEIN-ROTER-KASTEN. Frueher gab der Upload 425/409 zurueck; damit
  // rendert AnythingLLMs Upload-Feld einen roten "Fehler"-Chip - alarmierend,
  // obwohl nichts schiefging, und sein Text WECHSELT (erst die Meldung, dann
  // nur der Dateiname), weshalb Ausblenden per Text-Suche nicht zuverlaessig
  // greift. Loesung: Der Upload liefert jetzt bewusst 200/Erfolg, sodass
  // AnythingLLM erst gar keinen Fehler-Chip zeigt. Der eigentliche Hinweis
  // ("angenommen, wird aufbereitet ...") steckt im Feld ki4ki_hinweis und
  // wird als EINE, lesbare gruene Karte gezeigt.
  function auswerten(roh) {
    var d = {};
    try { d = JSON.parse(roh) || {}; } catch (e) {}
    var hinweis = d.ki4ki_hinweis;
    if (!hinweis) return;
    zeigen(d.ki4ki_dublette ? "dublette" : "angenommen",
           String(hinweis).replace(/^✓\\s*/, ""));
  }

  var echtesFetch = window.fetch;
  if (echtesFetch) {
    window.fetch = function (eingabe, einst) {
      var weg = typeof eingabe === "string" ? eingabe
                : (eingabe && eingabe.url) || "";
      var antwort = echtesFetch.apply(this, arguments);
      if (istUpload(weg)) {
        antwort.then(function (a) {
          a.clone().text().then(function (t) { auswerten(t); });
        }).catch(function () {});
      }
      return antwort;
    };
  }

  var echtesOeffnen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (verb, weg) {
    this.__ki4kiUpload = istUpload(weg);
    if (this.__ki4kiUpload) {
      this.addEventListener("load", function () {
        auswerten(this.responseText);
      });
    }
    return echtesOeffnen.apply(this, arguments);
  };
})();
</script>

<script>
(function () {
  // ki4ki-rolle: Das Formular "Neuer Arbeitsbereich" bekommt die Felder fuer
  // die ROLLE des Bereichs (Fachgebiet, wer fragt, Besonderheiten) und die
  // Wahl des Modus mit Erklaerung. Nach dem Anlegen schickt das Skript die
  // Angaben an /rolle - der Proxy schreibt dokumente/<bereich>/prompt.md,
  // laesst das Modell den Text glaetten und spielt Prompt + Modus ein.
  // AnythingLLM selbst bleibt unveraendert (Emrach 27.08.: "die wichtigsten
  // Felder fuer den Prompt direkt in der Box 'Neues Workspace anlegen'").
  var ID = "ki4ki-rolle-felder";
  var werte = {fach: "", nutzer: "", besonderes: "", modus: "query"};
  var anmeldung = "";   // Authorization des Anlege-Aufrufs - ohne sie kennt der Proxy das Konto nicht (403)

  function kopfzeile(einst, name) {
    try {
      var h = einst && einst.headers;
      if (!h) return "";
      if (typeof h.get === "function") return h.get(name) || "";
      for (var k in h) if (k.toLowerCase() === name.toLowerCase()) return h[k];
    } catch (e) {}
    return "";
  }
  function gespeicherteAnmeldung() {
    try {
      var t = window.localStorage.getItem("anythingllm_authToken") || window.localStorage.getItem("anythingllm_authtoken");
      return t ? ("Bearer " + t.replace(/^"|"$/g, "")) : "";
    } catch (e) { return ""; }
  }

  function feld(name, beschriftung, hinweis) {
    var w = document.createElement("div");
    w.style.cssText = "margin-top:10px";
    var l = document.createElement("label");
    l.textContent = beschriftung;
    l.style.cssText = "display:block;font-size:13px;font-weight:600;margin-bottom:4px";
    var i = document.createElement("input");
    i.type = "text"; i.placeholder = hinweis; i.autocomplete = "off";
    i.setAttribute("data-ki4ki", name);
    i.style.cssText = "width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;" +
      "border:1px solid #3a4454;background:#11151c;color:#e8edf5;font:14px system-ui,sans-serif";
    i.addEventListener("input", function () { werte[name] = i.value; });
    i.addEventListener("keydown", function (e) { if (e.key === "Enter") e.preventDefault(); });
    w.appendChild(l); w.appendChild(i);
    return w;
  }

  function modusWahl() {
    var w = document.createElement("div");
    w.style.cssText = "margin-top:12px;font-size:13px";
    var t = document.createElement("div");
    t.textContent = "Modus";
    t.style.cssText = "font-weight:600;margin-bottom:4px";
    w.appendChild(t);
    var optionen = [
      ["query", "Abfrage", "antwortet nur aus den Dokumenten, jede Aussage mit Beleg — Standard"],
      ["chat", "Chat", "zusätzlich Allgemeinwissen des Modells; Antworten dann nicht mehr vollständig belegbar"],
      ["automatic", "Vertreter", "die Anlage entscheidet je Frage selbst zwischen Chat und Werkzeugen — ohne verlässliche Belege, nicht empfohlen"]
    ];
    optionen.forEach(function (o) {
      var z = document.createElement("label");
      z.style.cssText = "display:flex;gap:8px;align-items:flex-start;margin:3px 0;cursor:pointer;font-weight:400";
      var r = document.createElement("input");
      r.type = "radio"; r.name = "ki4ki-modus"; r.value = o[0]; r.checked = (o[0] === "query");
      r.addEventListener("change", function () { if (r.checked) werte.modus = o[0]; });
      var s = document.createElement("span");
      s.innerHTML = "<b>" + o[1] + "</b> — " + o[2];
      z.appendChild(r); z.appendChild(s); w.appendChild(z);
    });
    return w;
  }

  function einbauen() {
    if (document.getElementById(ID)) return;
    if (/\\/settings\\b/.test(location.pathname)) return;   // Einstellungsseiten: dort gehoert das nicht hin
    var eingaben = document.querySelectorAll('input[name="name"]');
    for (var i = 0; i < eingaben.length; i++) {
      var inp = eingaben[i];
      var form = inp.closest("form");
      if (!form) continue;
      // Nur der Dialog zum ANLEGEN (schwebendes Fenster) - nicht die
      // Einstellungsseite eines bestehenden Bereichs (gemessen 27.08.).
      var kasten = form.closest('[role="dialog"], [class*="modal"], [class*="Modal"], [id*="modal"]');
      if (!kasten) {
        var el = form, schwebt = false;
        for (var t = 0; el && t < 8; t++, el = el.parentElement) {
          var pos = window.getComputedStyle(el).position;
          if (pos === "fixed" || pos === "absolute") { schwebt = true; break; }
        }
        if (!schwebt) continue;
        kasten = form.parentElement;
      }
      var text = (kasten && kasten.textContent) || "";
      if (!/workspace|arbeitsbereich/i.test(text)) continue;
      if (/thread|faden|umbenennen|rename/i.test(text) && !/new|neu/i.test(text)) continue;
      var block = document.createElement("div");
      block.id = ID;
      block.style.cssText = "margin-top:8px;padding:12px;border:1px dashed #3a4454;border-radius:10px;color:#e8edf5";
      var kopf = document.createElement("div");
      kopf.innerHTML = "<b>Rolle dieses Bereichs</b> <span style='opacity:.7'>— wird zum Prompt; später änderbar in <code>dokumente/&lt;bereich&gt;/prompt.md</code></span>";
      kopf.style.cssText = "font-size:13px";
      block.appendChild(kopf);
      block.appendChild(feld("fach", "Fachgebiet", "z. B. Kunststoffschweißen und -kleben nach DVS"));
      block.appendChild(feld("nutzer", "Wer fragt hier?", "z. B. Prüflinge und Ausbilder / Wissenschaftler / Instandhalter"));
      block.appendChild(feld("besonderes", "Worauf achten?", "z. B. Normstellen nennen, Sicherheitshinweise immer dazu, Störfälle als Tabelle"));
      block.appendChild(modusWahl());
      var anker = inp.closest("label") || inp.parentElement;
      anker.parentElement.insertBefore(block, anker.nextSibling);
      return;
    }
  }

  function melden(text, gut) {
    var k = document.createElement("div");
    k.style.cssText = "position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:2147483647;" +
      "max-width:560px;background:#11151c;color:#e8edf5;border-left:5px solid " + (gut ? "#15803d" : "#b45309") +
      ";border-radius:10px;padding:14px 18px;font:14px/1.5 system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.55)";
    k.textContent = text;
    document.body.appendChild(k);
    setTimeout(function () { k.remove(); }, 9000);
  }

  function rolleSchicken(slug) {
    var w = {slug: slug, fach: werte.fach, nutzer: werte.nutzer, besonderes: werte.besonderes, modus: werte.modus};
    werte = {fach: "", nutzer: "", besonderes: "", modus: "query"};
    if (!w.fach && !w.nutzer && !w.besonderes && w.modus === "query") return;
    var kopf = {"Content-Type": "application/json"};
    var auth = anmeldung || gespeicherteAnmeldung();
    if (auth) kopf["Authorization"] = auth;
    fetch("/rolle", {method: "POST", headers: kopf, credentials: "include", body: JSON.stringify(w)})
      .then(function (a) { return a.json(); })
      .then(function (d) {
        if (d && d.ok) melden("Rolle für „" + slug + "“ gespeichert" + (d.geglaettet ? " (vom Modell formuliert)" : "") +
                              (d.datei ? " — " + d.datei : ""), true);
        else melden("Rolle nicht gespeichert: " + ((d && d.fehler) || "unbekannt"), false);
      })
      .catch(function () { melden("Rolle nicht gespeichert (Verbindung).", false); });
  }

  var echtesFetch = window.fetch;
  if (echtesFetch) {
    window.fetch = function (eingabe, einst) {
      var weg = typeof eingabe === "string" ? eingabe : (eingabe && eingabe.url) || "";
      var antwort = echtesFetch.apply(this, arguments);
      if (/\\/api\\/(v1\\/)?workspace\\/new\\/?(\\?|$)/.test(weg)) {
        anmeldung = kopfzeile(einst, "Authorization") || anmeldung;
        antwort.then(function (a) {
          a.clone().json().then(function (d) {
            var ws = d && d.workspace;
            if (Array.isArray(ws)) ws = ws[0];
            if (ws && ws.slug) rolleSchicken(ws.slug);
          }).catch(function () {});
        }).catch(function () {});
      }
      return antwort;
    };
  }

  // --- Einstellungen eines bestehenden Bereichs: dieselben Felder, vorausgefuellt,
  //     mit Knopf. Emrach 27.08.: "Die werden nie die Textdatei aendern -
  //     Bequemlichkeit kommt immer ueber die UI."
  var ID2 = "ki4ki-rolle-einstellungen";
  function slugAusPfad() {
    var m = /\\/workspace\\/([^\\/]+)\\/settings/.exec(location.pathname);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function einstellungenEinbauen() {
    if (document.getElementById(ID2)) return;
    var slug = slugAusPfad();
    if (!slug) return;
    var ta = document.querySelector('textarea[name="openAiPrompt"]');
    if (!ta) return;
    var block = document.createElement("div");
    block.id = ID2;
    block.style.cssText = "margin:8px 0 14px;padding:12px;border:1px dashed #3a4454;border-radius:10px;color:#e8edf5";
    var kopf = document.createElement("div");
    kopf.innerHTML = "<b>Rolle dieses Bereichs</b> <span style='opacity:.7'>— aus diesen drei Angaben entsteht der Abschnitt „Rolle dieses Bereichs“ im Prompt unten (das Modell formuliert ihn aus).</span>";
    kopf.style.cssText = "font-size:13px";
    block.appendChild(kopf);
    block.appendChild(feld("fach", "Fachgebiet", "z. B. Kunststoffanalyse und -prüfung"));
    block.appendChild(feld("nutzer", "Wer fragt hier?", "z. B. Azubis, Projektingenieure, Techniker"));
    block.appendChild(feld("besonderes", "Worauf achten?", "z. B. Normstellen, Sicherheitsdatenblätter, Reparaturen"));
    var knopf = document.createElement("button");
    knopf.type = "button";
    knopf.textContent = "Rolle speichern & neu formulieren";
    knopf.style.cssText = "margin-top:12px;padding:8px 16px;border-radius:7px;cursor:pointer;border:1px solid #3a4454;background:#1b212b;color:#e8edf5;font:inherit";
    knopf.onclick = function () {
      knopf.disabled = true; knopf.textContent = "Formuliere … (das Modell braucht ein paar Sekunden)";
      var w = {slug: slug, fach: werte.fach, nutzer: werte.nutzer, besonderes: werte.besonderes};
      var kopfz = {"Content-Type": "application/json"};
      var auth = anmeldung || gespeicherteAnmeldung();
      if (auth) kopfz["Authorization"] = auth;
      fetch("/rolle", {method: "POST", headers: kopfz, credentials: "include", body: JSON.stringify(w)})
        .then(function (a) { return a.json(); })
        .then(function (d) {
          if (d && d.ok) { melden("Rolle gespeichert — Seite wird neu geladen", true); setTimeout(function () { location.reload(); }, 1200); }
          else { melden("Rolle nicht gespeichert: " + ((d && d.fehler) || "unbekannt"), false); knopf.disabled = false; knopf.textContent = "Rolle speichern & neu formulieren"; }
        })
        .catch(function () { melden("Rolle nicht gespeichert (Verbindung).", false); knopf.disabled = false; knopf.textContent = "Rolle speichern & neu formulieren"; });
    };
    block.appendChild(knopf);
    ta.parentElement.insertBefore(block, ta);
    // vorausfuellen
    var kopfz = {};
    var auth = anmeldung || gespeicherteAnmeldung();
    if (auth) kopfz["Authorization"] = auth;
    fetch("/rolle?slug=" + encodeURIComponent(slug), {headers: kopfz, credentials: "include"})
      .then(function (a) { return a.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;
        ["fach", "nutzer", "besonderes"].forEach(function (k) {
          var i = block.querySelector('input[data-ki4ki="' + k + '"]');
          if (i && d[k]) { i.value = d[k]; werte[k] = d[k]; }
        });
        if (d.darf === false) { knopf.disabled = true; knopf.textContent = "Nur Betreiber/Admin darf die Rolle ändern"; }
      }).catch(function () {});
  }

  var wartend = null;
  new MutationObserver(function () {
    clearTimeout(wartend);
    wartend = setTimeout(function () { einbauen(); einstellungenEinbauen(); }, 200);
  }).observe(document.documentElement, {childList: true, subtree: true});
})();
</script>

<script>
(function () {
  // ki4ki-daumen: AnythingLLM zeigt nur "Gute Antwort" (Daumen hoch). Der
  // Leitfaden (K2) verlangt auch das Gegenteil - mit Grund. Neben jeden
  // Daumen hoch kommt ein Daumen runter; ein Klick fragt kurz "Was war falsch?"
  // und meldet es an den Proxy (/api/workspace/<slug>/chat-feedback/<id>),
  // der es ins Pruefprotokoll und auf /rueckmeldungen bringt.
  var SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" viewBox="0 0 256 256" class="mb-1" style="transform:scaleY(-1)"><path d="M234,80.12A24,24,0,0,0,216,72H160V56a40,40,0,0,0-40-40,8,8,0,0,0-7.16,4.42L75.06,96H32a16,16,0,0,0-16,16v88a16,16,0,0,0,16,16H204a24,24,0,0,0,23.82-21l12-96A24,24,0,0,0,234,80.12ZM32,112H72v88H32ZM223.94,97l-12,96a8,8,0,0,1-7.94,7H88V105.89l36.71-73.43A24,24,0,0,1,144,56V80a8,8,0,0,0,8,8h64a8,8,0,0,1,7.94,9Z"></path></svg>';
  function slug() {
    var m = /\\/workspace\\/([^\\/]+)/.exec(location.pathname);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function anmeldung() {
    try {
      var t = window.localStorage.getItem("anythingllm_authToken");
      return t ? ("Bearer " + t.replace(/^"|"$/g, "")) : "";
    } catch (e) { return ""; }
  }
  function chatIdVon(knopf) {
    var el = knopf;
    for (var i = 0; el && i < 8; i++, el = el.parentElement) {
      var t = el.querySelector && el.querySelector("[data-auto-play-chat-id]");
      if (t) return t.getAttribute("data-auto-play-chat-id");
    }
    return null;
  }
  function melden(text, gut) {
    var k = document.createElement("div");
    k.style.cssText = "position:fixed;top:24px;left:50%;transform:translateX(-50%);z-index:2147483647;max-width:520px;" +
      "background:#11151c;color:#e8edf5;border-left:5px solid " + (gut ? "#15803d" : "#b45309") +
      ";border-radius:10px;padding:12px 16px;font:14px/1.5 system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.55)";
    k.textContent = text; document.body.appendChild(k); setTimeout(function () { k.remove(); }, 6000);
  }
  function senden(id, kommentar, knopf) {
    var kopf = {"Content-Type": "application/json"};
    var a = anmeldung(); if (a) kopf["Authorization"] = a;
    fetch("/api/workspace/" + encodeURIComponent(slug()) + "/chat-feedback/" + id,
          {method: "POST", headers: kopf, credentials: "include", body: JSON.stringify({feedback: false, kommentar: kommentar || ""})})
      .then(function (r) { if (!r.ok) throw new Error(r.status); knopf.style.color = "#f87171"; melden("Notiert — danke. Landet in der Rückmeldungsliste des Betreibers.", true); })
      .catch(function () { melden("Rückmeldung nicht gespeichert (Verbindung).", false); });
  }
  function einbauen() {
    var alle = document.querySelectorAll('button[data-tooltip-id="feedback-button"]');
    for (var i = 0; i < alle.length; i++) {
      var hoch = alle[i];
      var halter = hoch.parentElement;
      if (!halter || halter.parentElement.querySelector(".ki4ki-daumen-runter")) continue;
      var w = document.createElement("div");
      w.className = "mt-3 relative ki4ki-daumen-runter";
      var b = document.createElement("button");
      b.type = "button"; b.title = "Schlechte Antwort — kurz sagen, was falsch war";
      b.setAttribute("aria-label", "Schlechte Antwort");
      b.className = hoch.className; b.innerHTML = SVG;
      b.addEventListener("click", function () {
        var id = chatIdVon(b);
        if (!id) { melden("Kennung der Antwort nicht gefunden.", false); return; }
        var k = window.prompt("Was war falsch? (optional — z. B. „falsche Quelle“, „Zahl stimmt nicht“, „Bild fehlt“)", "");
        if (k === null) return;
        senden(id, k, b);
      });
      w.appendChild(b);
      halter.parentElement.insertBefore(w, halter.nextSibling);
    }
  }
  var wartend = null;
  new MutationObserver(function () { clearTimeout(wartend); wartend = setTimeout(einbauen, 250); })
    .observe(document.documentElement, {childList: true, subtree: true});
  setTimeout(einbauen, 1500);
})();
</script>
"""


# Gedaechtnis der geprueften Fassungen.
#
# AnythingLLM legt die ROHE Antwort in seiner Datenbank ab. Nach dem
# Neuladen oder beim Wechsel des Gespraechsfadens waeren Belege, Seiten und
# Verweise wieder weg - genau das faellt beim erneuten Oeffnen auf.
#
# In die Datenbank schreiben geht nicht: Sie gehoert einem anderen Konto,
# und an fremden Rechten wird nichts gedreht. Also merkt sich
# der Proxy die gepruefte Fassung selbst und setzt sie beim Laden des
# Verlaufs wieder ein. Der Schluessel ist der Rohtext - der steht in der
# Datenbank und kommt beim Laden zurueck.
GEDAECHTNIS = (os.environ.get("KI4KI_GEDAECHTNIS")
               or os.path.expanduser("~/ki4ki/reextract/.geprueft.json"))
HOECHSTENS = 2000
_geprueft = {}
_gsperre = threading.Lock()



def _neue_marke(vorsilbe="ki4ki"):
    """Eine frische Nachrichtenkennung.

    KI4KI-MARKE. Die Oberflaeche gruppiert Chatnachrichten nach dieser
    Kennung. Feste Kennungen wie "geprueft" oder "zusammenfassung" fuehrten
    dazu, dass die Antwort auf eine Folgefrage in die Nachricht der ersten
    Frage rutschte - der Fehler trat bei jeder zweiten Frage eines
    Gespraechs auf.

    ⚠ Absichtlich ohne "import uuid": Im Chatweg gibt es eine lokale
    Variable dieses Namens mit der Kennung von AnythingLLM, und ein Import
    auf Modulebene wuerde sie ueberdecken.
    """
    return "%s-%s" % (vorsilbe, binascii.hexlify(os.urandom(8)).decode())


# ---------------------------------------------------------------------------
#  Direkte Antworten im Thread halten (Persistenz OHNE DB-Schreiben)
#  AnythingLLM speichert nur, was ES erzeugt - unsere "am Modell vorbei"-
#  Antworten (Bestand, Rueckfrage, Zusammenfassung, Abriss) verschwinden sonst
#  beim Thread-Umschalten. Hier gemerkt, in _verlauf wieder eingeblendet.
# ---------------------------------------------------------------------------
_nachtrag_sperre = threading.Lock()
NACHTRAG_DATEI = (os.environ.get("KI4KI_THREAD_NACHTRAG")
                  or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  ".thread-nachtrag.json"))


def _nachtrag_alle():
    try:
        with open(NACHTRAG_DATEI, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


ARBEITET_DATEI = (os.environ.get("KI4KI_THREAD_ARBEITET")
                  or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  ".thread-arbeitet.json"))
ARBEITET_TEXT = ("\u23f3 *Deine Frage wird noch bearbeitet \u2014 bei komplexen "
                 "Fragen kann das bis zu zwei Minuten dauern. Du kannst hier "
                 "bleiben oder sp\u00e4ter zur\u00fcckkommen; die Antwort "
                 "erscheint dann von selbst. Bitte nicht erneut abschicken.*")


WARTE_TEXT = ("\u23f3 *Die vorige Antwort wird gerade noch erstellt \u2014 pro Gespraech laeuft nur eine Frage gleichzeitig. Bitte warte, bis sie erscheint, und schicke deine Frage dann erneut.*")


def _arbeitet_alle():
    try:
        with open(ARBEITET_DATEI, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _arbeitet_schreiben(alle):
    tmp = ARBEITET_DATEI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(alle, fh, ensure_ascii=False)
    os.replace(tmp, ARBEITET_DATEI)


def _arbeitet_setzen(schluessel, frage):
    try:
        with _gsperre:
            alle = _arbeitet_alle()
            alle[schluessel] = {"frage": frage or "", "wann": time.time()}
            _arbeitet_schreiben(alle)
    except Exception:
        pass


def _arbeitet_weg(schluessel):
    try:
        with _gsperre:
            alle = _arbeitet_alle()
            if schluessel in alle:
                alle.pop(schluessel, None)
                _arbeitet_schreiben(alle)
    except Exception:
        pass


def _nachtrag_merken(schluessel, prompt, text, quellen, wann):
    """Eine direkt beantwortete Frage fuer den Thread festhalten. Wirft nie."""
    try:
        with _nachtrag_sperre:
            alle = _nachtrag_alle()
            liste = alle.get(schluessel) or []
            for e in liste:
                if e.get("prompt") == prompt and e.get("wann") == wann:
                    return
            liste.append({"prompt": prompt, "text": text,
                          "sources": list(quellen or []), "wann": wann})
            alle[schluessel] = liste[-200:]
            tmp = NACHTRAG_DATEI + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(alle, fh, ensure_ascii=False)
            os.replace(tmp, NACHTRAG_DATEI)
    except Exception as e:
        print("[Nachtrag] %s" % str(e)[:90], file=sys.stderr, flush=True)


def _nachtrag_einblenden(history, gespeichert):
    """Fehlende direkte Antworten chronologisch einfuegen, im selben Format
    wie AnythingLLMs convertToChatHistory (user- + assistant-Objekt). Wirft nie."""
    h = history if isinstance(history, list) else []
    paare = []
    vorhanden = set()
    i = 0
    while i < len(h):
        u = h[i]
        a = h[i + 1] if i + 1 < len(h) else None
        if (isinstance(u, dict) and u.get("role") == "user"
                and isinstance(a, dict) and a.get("role") == "assistant"):
            vorhanden.add((u.get("content"), u.get("sentAt")))
            paare.append((u.get("sentAt") or 0, [u, a]))
            i += 2
        else:
            paare.append(((u.get("sentAt") if isinstance(u, dict) else 0) or 0, [u]))
            i += 1
    n = 0
    for k, e in enumerate(gespeichert or []):
        wann = int(e.get("wann") or 0)
        if (e.get("prompt"), wann) in vorhanden:
            continue
        cid = -(1000000 + k)
        u = {"role": "user", "content": e.get("prompt") or "",
             "sentAt": wann, "attachments": [], "chatId": cid}
        a = {"type": "chart", "role": "assistant", "content": e.get("text") or "",
             "sources": e.get("sources") or [], "chatId": cid, "sentAt": wann,
             "feedbackScore": None, "metrics": {}}
        paare.append((wann, [u, a]))
        n += 1
    if not n:
        return history, 0
    paare.sort(key=lambda p: p[0])
    neu = []
    for _, gruppe in paare:
        neu.extend(gruppe)
    return neu, n

def _schluessel(rohtext):
    import hashlib
    return hashlib.sha1(re.sub(r"\s+", " ", rohtext).strip().encode()).hexdigest()


def gedaechtnis_laden():
    global _geprueft
    try:
        with open(GEDAECHTNIS, encoding="utf-8") as fh:
            _geprueft = json.load(fh)
    except Exception:
        _geprueft = {}
    return len(_geprueft)


def gedaechtnis_merken(roh, geprueft, quellen):
    if not roh.strip() or geprueft == roh:
        return
    with _gsperre:
        _geprueft[_schluessel(roh)] = {"text": geprueft, "sources": quellen}
        if len(_geprueft) > HOECHSTENS:
            for k in list(_geprueft)[:len(_geprueft) - HOECHSTENS]:
                _geprueft.pop(k, None)
        try:
            vorlaeufig = GEDAECHTNIS + ".neu"
            with open(vorlaeufig, "w", encoding="utf-8") as fh:
                json.dump(_geprueft, fh, ensure_ascii=False)
            os.replace(vorlaeufig, GEDAECHTNIS)
        except Exception as e:
            print("[Gedaechtnis] %s" % str(e)[:90], file=sys.stderr, flush=True)


# Der Block, den die woertliche Suche an die Frage haengt. Er muss dorthin -
# AnythingLLM nimmt keinen zweiten Kanal fuer Zusatzkontext. Er darf aber
# nicht im gespeicherten Verlauf als die Frage des Menschen erscheinen.
_ZUSATZ_MARKE = "WOERTLICHE FUNDSTELLEN zu"


def frage_saeubern(text):
    """Den angehaengten Fundstellen-Block aus einer Frage schneiden.

    Beim Umschalten des Threads landete der angehaengte Fundstellen-Block
    faelschlich als erste Frage des Menschen im Verlauf - ueber 6.000
    Zeichen Fundstellen als seine Frage.

    Der Schnitt ist verlustfrei: Die Fundstellen sind eine Kopie aus dem
    Bestand, was der Mensch geschrieben hat steht davor.
    """
    if not text or _ZUSATZ_MARKE not in text:
        return text
    return text.split(_ZUSATZ_MARKE)[0].rstrip()


MODELL_ANZEIGE = (os.environ.get("KI4KI_MODELL_ANZEIGE", "1") != "0")


def _modell_zeile(modell, sekunden=None, zeichen=None):
    """Sichtbare Fusszeile: WELCHES Modell die Antwort formuliert hat, mit
    Tempo und geschaetzter Tokenzahl. Tokens sind geschaetzt (~Zeichen/4),
    weil der Datenstrom von AnythingLLM keine echte Zahl mitliefert - lieber
    ehrlich geschaetzt als falsch genau. Abschaltbar: KI4KI_MODELL_ANZEIGE=0."""
    if not MODELL_ANZEIGE:
        return ""
    zusatz = ""
    if sekunden is not None:
        if sekunden >= 90:
            _z = "%d min %d s" % (int(sekunden // 60), int(sekunden % 60))
        else:
            _z = "%.0f s" % sekunden
        zusatz = " \u00b7 gesamt %s (inkl. Belegpr\u00fcfung)" % _z
    return ("\n\n---\n*\U0001F9E0 Antwort formuliert vom Sprachmodell "
            "**%s**%s*" % (modell, zusatz))


def _allgemein_zeile(modell, sekunden=None):
    """KI4KI-ALLROUNDER: Fusszeile fuer Allgemeinwissen-Antworten in EINER
    Zeile - WER geantwortet hat UND dass es NICHT belegt ist. Kein zweites
    Marken-Symbol und kein '(inkl. Belegpruefung)', weil nichts geprueft
    wurde. Abschaltbar wie die uebliche Zeile: KI4KI_MODELL_ANZEIGE=0."""
    if not MODELL_ANZEIGE:
        return ("\n\n---\n*\U0001F9E0 Allgemeinwissen \u2013 nicht aus "
                "euren Dokumenten belegt.*")
    z = ""
    if sekunden is not None:
        if sekunden >= 90:
            z = " \u00b7 gesamt %d min %d s" % (
                int(sekunden // 60), int(sekunden % 60))
        else:
            z = " \u00b7 gesamt %.0f s" % sekunden
    return ("\n\n---\n*\U0001F9E0 **Allgemeinwissen** vom Sprachmodell "
            "**%s** \u2013 nicht aus euren Dokumenten belegt%s*"
            % (modell, z))


def _katalog_zeile():
    """A: Katalog-Antworten sichtbar als 'ohne KI' kennzeichnen - damit klar
    ist, dass hier nichts formuliert, sondern nachgeschlagen wurde."""
    if not MODELL_ANZEIGE:
        return ""
    return ("\n\n---\n*\U0001F4C7 Direkt aus dem Katalog zusammengestellt "
            "\u2014 ohne KI-Sprachmodell.*")


E2B_ANTWORT = (os.environ.get("KI4KI_E2B_ANTWORT", "1") != "0")
# KI4KI-BILD: "Zeig mir Bild 2.1" / "Kannst du mir ein Diagramm zeigen?" direkt
# aus dem Dokument beantworten (Bildunterschrift-Seite suchen, Bild anhaengen),
# statt ueber die Aehnlichkeitssuche, die zu "2.1" nur Zufallsstellen liefert.
# Abschaltbar mit KI4KI_BILD_ANTWORT=0.
BILD_ANTWORT = (os.environ.get("KI4KI_BILD_ANTWORT", "1") != "0")

_DEF_MUSTER = re.compile(
    r"^\s*(was ist (ein|eine|der|die|das)?|was sind|was bedeutet|"
    r"was versteht man unter|wof\u00fcr steht|definiere|was hei\u00dft|"
    r"was heisst)\b", re.I)


def _ist_definitionsfrage(frage):
    """Eine kurze, einzelne 'Was ist X?'-Frage - der Fall, den das kleine
    Modell aus einer Fundstelle beantworten kann. Vergleiche/Verfahren
    ('Unterschied', 'wie', 'warum') gehoeren NICHT hierher."""
    f = (frage or "").strip()
    if not f or len(f) > 120 or f.count("?") > 1:
        return False
    if re.search(r"\b(unterschied|vergleich|wie |warum|weshalb|wieso)\b",
                 f, re.I):
        return False
    return bool(_DEF_MUSTER.match(f))


def _netz_hinweis_zeile():
    """Sichtbare Zeile, wenn die letzte Einordnung ueber das kleine Modell
    lief - damit man sieht, WANN E2B greift. Sonst leer. Wirft nie.
    (Abgeschaltet: verwirrte neben AnythingLLMs eigener Metrik; die
    Einordnung ist interne Mechanik, keine Nutzer-Info.)"""
    return ""


def verlauf_veredeln(daten):
    """Im geladenen Verlauf jede bekannte Rohantwort ersetzen.

    Geht blind durch die Struktur und ersetzt jedes Textfeld, dessen Inhalt
    wir schon einmal geprueft haben. Damit ist es gleichgueltig, wie
    AnythingLLM den Verlauf genau aufbaut.
    """
    ersetzt = [0]

    def gehe(x):
        if isinstance(x, dict):
            for feld in ("text", "content", "response", "prompt", "message"):
                wert = x.get(feld)
                # Erst den angehaengten Fundstellen-Block wegschneiden -
                # sonst steht er im Verlauf als die Frage des Menschen.
                if isinstance(wert, str) and _ZUSATZ_MARKE in wert:
                    x[feld] = wert = frage_saeubern(wert)
                    ersetzt[0] += 1
                if isinstance(wert, str) and wert.strip():
                    treffer = _geprueft.get(_schluessel(wert))
                    if treffer:
                        x[feld] = treffer["text"]
                        if treffer.get("sources"):
                            x["sources"] = treffer["sources"]
                        ersetzt[0] += 1
            for w in x.values():
                gehe(w)
        elif isinstance(x, list):
            for w in x:
                gehe(w)

    gehe(daten)
    return ersetzt[0]


def seite_pruefen(dokument, vermutung, zitat):
    """Die Seitenzahl gegen das Original-PDF pruefen.

    Doclings Marke ist nur eine Schaetzung. Das PDF ist die Instanz.
    """
    stamm = dokument[:-3] if dokument.endswith(".md") else dokument
    stamm = _pdf_schluessel(stamm)
    if not stamm:
        return None
    seite, _ = pdfstelle.finde_seite(stamm, zitat, vermutung)
    return seite


def _wort_norm(s):
    """Kennzeichnende Woerter (>=4 Zeichen, klein) einer Zeichenkette."""
    return set(re.findall(r"[a-zA-Z0-9À-ɏ]{4,}", (s or "").lower()))


def _zitat_disambig(treffer, kontext):
    """Bei mehreren Zitaten auf DERSELBEN Seite den passenden waehlen.

    Jeder Beleg schreibt sein Zitat unmittelbar VOR die Seitenangabe - also
    steht das richtige Zitat im Fliesstext direkt vor DIESEM Link. Wir nehmen
    das Zitat, dessen kennzeichnende Woerter in diesem Textstueck am
    staerksten vorkommen - und NUR bei klarem Treffer (sonst lieber keins,
    damit nie die falsche Stelle markiert wird).
    """
    kw = _wort_norm(kontext)
    if not kw:
        return ""
    best, best_anteil = "", 0.0
    for z in treffer:
        zw = _wort_norm(z)
        if len(zw) < 3:
            continue
        anteil = len(zw & kw) / float(len(zw))
        if anteil > best_anteil:
            best_anteil, best = anteil, z
    return best if best_anteil >= 0.6 else ""


def _zitat_zu(pruefungen, name, seite, kontext=""):
    """Das Zitat, das zu genau diesem Dokument und dieser Seite gehoert.

    Vorher wurde ueber einen Laufindex gepaart: der n-te Fund von
    ", Seite N" bekam das n-te Zitat. Das haelt nur, solange das Modell
    JEDE Quelle mit Seitenzahl nennt. An einer echten Antwort
    gemessen: Von fuenf Belegen trug nur einer ", Seite 376" im
    Fliesstext - der bekam damit das Zitat von Beleg 1, das auf Seite 377
    steht. Der Link zeigte auf die falsche Seite, die Markierung blieb
    aus, und der Nutzer haelt den Beleg fuer erfunden.

    Bei mehreren gleich guten Treffern wird bewusst KEIN Zitat angehaengt:
    Dann fuehrt der Verweis ohne Markierung auf die richtige Seite - das
    ist besser als eine Markierung auf der falschen.
    """
    treffer = []
    for p in pruefungen or []:
        orte = p.get("orte") or []
        if not orte and p.get("doku"):
            orte = [(p["doku"], p.get("seiten"))]
        for doku, seiten in orte:
            if not doku or not seiten:
                continue
            if doku.endswith(".md"):
                doku = doku[:-3]
            if doku != name:
                continue
            if str(seite) in [str(s) for s in seiten]:
                zitat = p.get("original", "")
                if zitat and zitat not in treffer:
                    treffer.append(zitat)
    if len(treffer) == 1:
        return treffer[0]
    # ⭐ Mehrere Zitate auf EINER Seite: frueher blieb die Markierung ganz aus
    #   (siehe oben). Jetzt den passenden am Fliesstext vor DIESEM Link
    #   erkennen - jeder Beleg schreibt sein Zitat direkt davor. Nur bei
    #   klarem Treffer; sonst weiterhin lieber keine als die falsche Marke.
    if len(treffer) > 1 and kontext:
        b = _zitat_disambig(treffer, kontext)
        if b:
            return b
    return ""


def _csv_feld(wert):
    """Ein Feld fuer die Ausfuhr als Tabelle.

    Semikolon als Trenner, weil Excel in deutscher Einstellung nichts
    anderes ohne Nachfrage oeffnet. Anfuehrungszeichen werden verdoppelt,
    Zeilenumbrueche zu Leerzeichen - sonst zerreisst eine mehrzeilige
    Frage die Tabelle und die Spalten verrutschen ab da fuer alles
    Folgende.
    """
    if wert is None:
        return ""
    text = str(wert).replace("\r", " ").replace("\n", " ")
    if any(z in text for z in (";", '"')):
        return '"%s"' % text.replace('"', '""')
    return text


def _wahl_beantwortet(gespraech, frage, art):
    """Antwortet der Fragende auf unsere eigene Rueckfrage?

    Stellt die Anlage "Dazu passen mehrere Dokumente. Welches meinst du?"
    und nennt der Naechste einen der aufgezaehlten Titel, dann ist das
    keine neue Frage, sondern die Wahl. Ohne diesen Schritt landet
    "DVS 2213-1_neu" als gewoehnliche Suche und liefert "keine belastbare
    Information" - die Anlage versteht ihre eigene Rueckfrage nicht.

    Bestandsfragen bleiben unangetastet: "Welche Dokumente habt ihr?" ist
    auch dann eine Bestandsfrage, wenn gerade eine Wahl offen ist.
    """
    if not gespraech or art == "bestand":
        return art
    wahl = GESPRAECHE.offene_wahl(gespraech)
    if not wahl:
        return art
    # "alle" ist eine Antwort auf die Rueckfrage, nur keine, die sich
    # erfuellen laesst. Sie gehoert trotzdem hierher - sonst laeuft sie
    # als gewoehnliche Suche und das Modell antwortet ratlos.
    if assistent.ist_alle_wahl(frage):
        print("[Assistent] Rueckfrage mit 'alle' beantwortet",
              file=sys.stderr, flush=True)
        return "zusammenfassung"
    gewaehlt, _ = assistent.dokument_gemeint(frage, wahl)
    if not gewaehlt:
        return art
    print("[Assistent] Antwort auf die Rueckfrage: %r" % gewaehlt[:70],
          file=sys.stderr, flush=True)
    return "zusammenfassung"


NENNUNG_TILGEN = (os.environ.get("KI4KI_NENNUNG_TILGEN", "1") != "0")


def _themenfremde_nennungen_tilgen(text):
    """Entfernt Dokument-Nennungen, deren Dokument zum Thema der Antwort
    NACHWEISLICH nichts beitraegt (vom Modell falsch zugeordnet). Entscheidung
    PRO DOKUMENT (nicht pro Nennung): <3 Content-Fachwoerter Deckung ueber ALLE
    Nennungen -> themenfremd, alle Nennungen raus; gedeckte Quellen im selben
    Klammerausdruck bleiben. Der Satz bleibt. Abschaltbar. Wirft nie."""
    if not NENNUNG_TILGEN or not text:
        return text
    try:
        _code = re.compile(r"[A-Z]{1,3}-\d{2}-\d{3}(?:\.[a-z0-9]+)?")
        _paren = re.compile(r" ?\(([^()]*[A-Z]{1,3}-\d{2}-\d{3}[^()]*)\)")

        def _woerter(x):
            return {w for w in re.sub(r"[^0-9a-zA-ZäöüÄÖÜß]+", " ",
                                      (x or "").lower()).split()
                    if len(w) > 6 and w not in _FUELLWOERTER}

        def _seiten(code):
            for kand in (_pdf_schluessel(code), code):
                if not kand:
                    continue
                try:
                    seiten = _seitentexte_pdf(kand) or []
                except Exception:
                    seiten = []
                if seiten:
                    return seiten
            return []

        best = {}
        for m in _paren.finditer(text):
            ziel = _woerter(text[max(0, m.start() - 260):m.start()])
            if len(ziel) < 3:
                continue
            for cm in _code.finditer(m.group(1)):
                seiten = _seiten(cm.group(0))
                if not seiten:
                    continue
                d = max((len(ziel & _woerter(t)) for t in seiten), default=0)
                best[cm.group(0)] = max(best.get(cm.group(0), -1), d)
        themenfremd = {c for c, v in best.items() if v >= 0 and v < 3}
        if not themenfremd:
            return text

        def _ersetze(m):
            innen = m.group(1)
            for code in themenfremd:
                innen = re.sub(
                    r"\s*(?:[;,]|und|sowie|&)?\s*" + re.escape(code)
                    + r"(?:\s*,?\s*S(?:eite)?\.?\s*\d+(?:\s*[-\u2013]\s*\d+)?)?",
                    "", innen)
            innen = re.sub(r"^\s*(?:[;,]|und|sowie)\s*", "", innen)
            innen = re.sub(r"\s*(?:[;,]|und|sowie)\s*$", "", innen).strip()
            return (" (" + innen + ")") if innen else ""

        return _paren.sub(_ersetze, text)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return text


def mit_verweisen(text, pruefungen=None, quellen=None):
    """Fundstellen in anklickbare Verweise auf die Fundstellen-Ansicht.

    AnythingLLM stellt Markdown dar. Der Verweis fuehrt nicht auf das nackte
    PDF, sondern auf eine Seite, die genau die belegte Stelle gelb markiert
    zeigt - das ist der Unterschied zwischen "irgendwo auf Seite 13" und
    "genau hier".
    """
    pruefungen = pruefungen or []

    # Rueckwaerts suchen statt den Namen raten: An jeder Fundstelle
    # ", Seite N" wird geprueft, welcher der wirklich vorhandenen
    # Dokumentnamen unmittelbar davorsteht. Das alte Zeichenmuster
    # ([A-Za-z0-9...]+) kannte weder Leerzeichen noch eckige Klammern -
    # aus "[Ehr06] Faserverbundkunststoffe_..._Eigenschaften, Seite 65"
    # blieb "Eigenschaften", das in keinem Bestand steht. Kein Link, kein
    # Hinweis, warum. Der laengste Treffer gewinnt, damit ein kurzer Name
    # keinen laengeren zerschneidet.
    ergebnis = []
    bis = 0
    for m in re.finditer(r", Seite (\d+)(?:-\d+)?", text):
        davor = text[:m.start()]
        name = None
        for kandidat in PDFS:
            if davor.endswith(kandidat) and (name is None
                                             or len(kandidat) > len(name)):
                name = kandidat
        if name and quellen is not None and name not in quellen:
            name = None   # genannt, aber nicht unter den Quellen -> nicht belegt
        if name and not _dok_hat_aussage(
                name, text[max(0, m.start() - 260):m.start()]):
            name = None   # Dok deckt die Aussage nicht -> Modell halluziniert
        if not name or m.start() - len(name) < bis:
            continue
        ergebnis.append(text[bis:m.start() - len(name)])
        # Kontext = der Fliesstext dieses Belegs (vom Ende des vorigen Links
        # bis hierher). Enthaelt das Zitat, das das Modell direkt vor die
        # Seitenangabe geschrieben hat - so lassen sich mehrere Zitate auf
        # derselben Seite dem richtigen Link zuordnen.
        zitat = _zitat_zu(pruefungen, name, m.group(1), text[bis:m.start()])
        ziel = "/stelle?dok=%s&seite=%s" % (quote(name), m.group(1))
        if zitat:
            ziel += "&zitat=" + quote(zitat[:400])
        # Eckige Klammern im Linktext muessen escaped werden, sonst
        # zerlegt der Markdown-Darsteller "[[Ehr06] ...](...)" an der
        # inneren Klammer und es bleibt kein Link uebrig. Genau solche
        # Namen kommen aus der Fachliteratur.
        sichtbar = (name + m.group(0)).replace("[", "\\[").replace("]", "\\]")
        ergebnis.append("[%s](%s)" % (sichtbar, ziel))
        bis = m.end()
    ergebnis.append(text[bis:])
    return "".join(ergebnis)


def marken_verlinken(text, pruefungen):
    """Die Fussnotenmarken [1], [2] ... im Fliesstext anklickbar machen.

    Die Belegliste unten fuehrt schon ins Original. Wer aber mitten im
    Satz "(Quelle: Tabelle 2.1, Seite 62) [4]" liest, will nicht erst
    nach unten scrollen. Die Marke kennt ihre Pruefung, die Pruefung
    kennt Dokument und Seite - mehr braucht es nicht.
    """
    if not pruefungen:
        return text
    # Nur oberhalb der Belegliste. Darunter stehen dieselben Marken als
    # Ueberschriften, die bereits verlinkt sind.
    schnitt = text.find("**Belege**")
    if schnitt < 0:
        schnitt = len(text)
    kopf, schwanz = text[:schnitt], text[schnitt:]

    def ersetze(m):
        try:
            i = int(m.group(1))
        except ValueError:
            return m.group(0)
        if not 1 <= i <= len(pruefungen):
            return m.group(0)
        p = pruefungen[i - 1]
        orte = p.get("orte")
        if not orte:
            if not p.get("doku"):
                return m.group(0)
            orte = [(p["doku"], p.get("seiten"))]
        name, seiten = orte[0]
        if name.endswith(".md"):
            name = name[:-3]
        name = _pdf_schluessel(name) or name
        if name not in PDFS or not seiten:
            return m.group(0)
        ziel = "/stelle?dok=%s&seite=%s" % (quote(name), seiten[0])
        zitat = p.get("original", "")
        if zitat:
            ziel += "&zitat=" + quote(zitat[:400])
        return "[\\[%d\\]](%s)" % (i, ziel)

    return re.sub(r"\[(\d{1,2})\]", ersetze, kopf) + schwanz



# Ein bereits gesetzter Link - dort darf nicht noch einmal hineingegriffen
# werden, sonst entsteht "[[Name](a)](b)".
# ⚠ Der Linktext kann GESCHUETZTE Klammern enthalten: marken_verlinken
#   macht aus der Fussnotenmarke [1] den Linktext "\\[1\\]". Ein Muster
#   mit [^\]]* zerbricht daran - der Bereich gilt als ungeschuetzt, und
#   nennungen_verlinken ersetzte den Dokumentnamen MITTEN IN DER ADRESSE:
#       /stelle?dok=[*S-00-000*](/pdf/S-00-000)&seite=8&zitat=…
#   Im Browser: "Dieses Dokument liegt nicht vor."
_SCHON_LINK = re.compile(r"\[(?:[^\[\]\\]|\\.)*\]\([^)]*\)")


def _wortartig(name):
    """Ist der Name ein gewoehnliches Wort statt einer Arbeitskennung?

    Kennungen tragen Ziffern: DS-00-000, DVS 2290, richtlinie-dvs-2213-1.
    Ein Name ganz ohne Ziffer, aus hoechstens zwei Woertern, ist im
    Zweifel ein Wort der Fachsprache - "Reparatur", "Versagensarten",
    "Sicht- und Masskontrolle".
    """
    if any(c.isdigit() for c in name):
        return False
    return len(name.replace("-", " ").replace("_", " ").split()) <= 3


# ⭐ Das Zeichen VOR einer nur genannten (ungeprueften) Quellenangabe.
#   Ein Symbol, das die Fusszeile erklaert -
#   nicht mehr bloss Kursivschrift. Ein Zeichen ohne Markdown-Sonderrolle
#   und mit geschuetztem Leerzeichen, damit es am Namen klebt.
#   ⚠ Wird die Fusszeile geaendert, muss das Zeichen dort dasselbe sein.
# ⛔ NUR-GENANNTE DOKUMENTE VERLINKEN - Standard: AUS.
#   Grund: Das Modell nennt Dokumente ohne woertliches Zitat ("laut
#   DS-00-000, Seite 96") - die Seitenzahl ist GERATEN.
#   Gemessen: die genannte Seite traegt die Aussage zu 29 %, andere
#   Seiten zu 43 %. Frei erfunden. Regel: keine geratenen
#   Sachen. Eine Seitenzahl erscheint NUR, wenn ein woertliches Zitat
#   sie belegt (mit_verweisen, mit Sprung und Gelbmarkierung). Alles
#   andere wird NICHT verlinkt - ein klickbarer Verweis ohne gepruefte
#   Fundstelle sieht aus wie ein Beleg und ist keiner.
#   ⭐ REVERSIBEL: True legt es wieder an. Die GEPRUEFTEN Belege sind
#     davon voellig unberuehrt.
NENNUNGEN_VERLINKEN = True   # wieder an - jetzt VERIFIZIERTE Seite
NENNUNG_MARKER = "° "     # ° + geschuetztes Leerzeichen


def nennungen_verlinken(text, quellen=None):
    """Dokumentnamen, die nur genannt sind, zum Original verlinken.

    ⛔ Standardmaessig AUS (NENNUNGEN_VERLINKEN = False): Nennungen ohne
      gepruefte Fundstelle werden nicht verlinkt, damit sie nicht wie ein
      Beleg aussehen. Siehe Begruendung an der Konstante oben.

    Verlinkt wird, was die Belegpruefung bestaetigt hat - das sind die
    blauen Verweise mit Seitenzahl. Daneben nennt das Modell haeufig
    weitere Dokumente in seiner Begruendung, ohne sie zu zitieren. Die
    waren bisher gar nicht erreichbar.

    Sie bekommen jetzt einen Link auf das Original - aber KURSIV und ohne
    Seite, damit der Unterschied sichtbar bleibt. Eine Nennung ist keine
    gepruefte Fundstelle: In einem Fall fuehrte eine davon
    in ein Literaturverzeichnis, nicht zum Inhalt.
    """
    if not NENNUNGEN_VERLINKEN:
        return text, 0
    if not PDFS:
        return text, 0
    # Bereiche, die schon ein Link sind, werden ausgespart.
    tabu = [(m.start(), m.end()) for m in _SCHON_LINK.finditer(text)]

    def geschuetzt(a, e):
        return any(a >= s and e <= t for s, t in tabu)

    # Laengste Namen zuerst, damit ein kurzer keinen langen zerschneidet.
    #
    # Dazu die KURZFORMEN: Die Arbeit heisst "S-00-000.x", das Modell (und
    # die Arbeit selbst) schreibt "S-00-000". Ohne diese Zuordnung bleibt
    # jede solche Nennung unverlinkt - Beispiel: DS-00-000 blau
    # verlinkt, S-00-000 nicht.
    #
    # ⚠ NUR WENN EINDEUTIG. Gaebe es "S-00-000.x" und "S-00-000.y", waere
    #   die Kurzform mehrdeutig; dann bleibt sie unverlinkt. Lieber kein
    #   Link als einer, der auf die falsche Arbeit fuehrt.
    kurzformen = {}
    for voll in PDFS:
        kurz = voll.rsplit(".", 1)[0]
        if kurz != voll and len(kurz) >= 4 and kurz not in PDFS:
            kurzformen.setdefault(kurz, []).append(voll)
    eindeutig = {k: v[0] for k, v in kurzformen.items() if len(v) == 1}
    # ⭐ Dazu die TITELFORMEN. Das Modell sieht nicht den Dateinamen,
    #   sondern den Titel aus der Ablage - und laesst ein fuehrendes
    #   Klammer-Kuerzel weg. Gemessen: 6 von 10 Belegen blieben
    #   deshalb unverlinkt. Verlinkt wird trotzdem auf den DATEINAMEN,
    #   so wie vorgegeben.
    for anzeige, stamm in titelnamen().items():
        # ⚠ NICHT "stamm in PDFS" pruefen. Die Ablage bereinigt den Namen
        #   ("HW14-Handbuch-..."), die Datei auf der Platte heisst aber
        #   "[HW14] Handbuch ....pdf". Ein direkter Vergleich findet nichts
        #   und meldet faelschlich "kein PDF vorhanden" - so wurden
        #   faelschlich 41 Dokumente fuer originallos gehalten.
        #   _pdf_schluessel() vergleicht ueber die Grundform (alle
        #   Sonderzeichen weg) und trifft deshalb jede Schreibweise.
        echt = _pdf_schluessel(stamm) or _pdf_schluessel(anzeige)
        if echt and anzeige not in PDFS and anzeige not in eindeutig:
            eindeutig[anzeige] = echt
    namen = sorted(set(PDFS) | set(eindeutig), key=len, reverse=True)
    stellen = []
    belegt = []
    for name in namen:
        if len(name) < 4:
            continue
        # ⚠ Trennzeichen flexibel. AnythingLLM zeigt dem Modell einen
        #   TITEL, in dem Bindestriche durch Leerzeichen ersetzt sind
        #   ("Textbildprsrsentation DVS 1110-3 Maerz 2019"), die Datei
        #   heisst aber "Textbildprsrsentation-DVS-1110-3-Maerz-2019".
        #   Gemessen: 41 von 51 Dokumenten eines Bereichs sind betroffen, und
        #   13 von 15 Belegen blieben deshalb unverlinkt. Das Modell macht
        #   dabei NICHTS falsch - es kennt den Dateinamen nicht.
        #   Die Titel sind nicht mechanisch ableitbar (mal der erste
        #   Bindestrich, mal der zweite), also wird nicht umgerechnet,
        #   sondern beim Suchen jedes Trennzeichen gleich behandelt.
        gesucht = r"[\s\-_]+".join(
            re.escape(t) for t in re.split(r"[\s\-_]+", name) if t)
        # ".md" gehoert zum Dateinamen, nicht zur Aussage. Ohne es endet der
        # Link vor dem Punkt und ".md, S. 10" steht unverlinkt daneben -
        # es sieht aus wie ein zerbrochener Link.
        # ", S. 10" wird mitgenommen, damit der Klick dort landet.
        # ⚠ Auch ".x" mitnehmen, nicht nur ".md". Im Prompt stand als
        #   Beispiel "(S-00-000.x, S. 10)" - das Modell schreibt das .x ab
        #   und haengt es an JEDEN Namen. Der Link endete davor, und
        #   ".x, S. 59" stand unverlinkt daneben: sieht aus wie ein
        #   zerbrochener Link. Dasselbe Problem trat zuvor schon mit
        #   ".md" auf.
        muster = (r"(?<![\w-])" + gesucht + r"(?P<md>\.(?:md|x|pdf))?"
                  r"(?P<seite>,\s*S(?:eite)?\.?\s*(?P<nr>\d{1,4}))?(?![\w-])")
        for m in re.finditer(muster, text):
            a, e = m.start(), m.end()
            if geschuetzt(a, e) or any(a < t and e > s for s, t in belegt):
                continue
            # ", Seite N" ausgeschrieben schreibt UNSERE Pruefung - dort
            # steht schon ein geprueftes Zitat, das unangetastet bleibt.
            if re.match(r",\s*Seite\s*\d", text[e:e + 12]):
                continue
            # ⚠ Ein Dokumentname, der ein gewoehnliches Wort ist, wird nur
            #   verlinkt, wenn er WIE EINE QUELLE auftritt - also mit
            #   Seitenangabe. Im Bestand gibt es "Reparatur.pdf"; ohne diese
            #   Regel wurde jedes Vorkommen des Wortes "Reparatur" zum Link.
            #   Ein fehlender Link kostet einen Klick, ein
            #   falscher behauptet einen Beleg, den es nicht gibt.
            if _wortartig(name) and not m.group("nr"):
                continue
            _nm = eindeutig.get(name, name)
            # ⭐ Nur verlinken, wenn das Dokument WIRKLICH unter den
            #   gefundenen Quellen war - sonst hat das Modell den Namen
            #   halluziniert (M-00-000 = Plasma, nie abgerufen).
            if quellen is not None and _nm not in quellen and name not in quellen:
                continue
            _kontext = text[max(0, a - 250):a]
            # ⭐ VERIFIZIEREN statt der genannten Seite blind trauen - aber
            #   die Modell-Seite MITGEBEN: Nennt das Modell eine Seite, hat
            #   es oft die Seitenmarke seiner Fundstelle gesehen. Vorher
            #   wurde eine RICHTIGE 43 zu einer falschen 42 "korrigiert",
            #   weil eine fruehere Seite zufaellig aehnliche Woerter trug.
            #   Ersetzt wird die Modell-Seite nur noch, wenn die Aussage
            #   dort NICHT wiederzufinden ist.
            _modellseite = None
            if m.group("nr"):
                try:
                    _modellseite = int(m.group("nr"))
                except (TypeError, ValueError):
                    _modellseite = None
            _seite = _verifizierte_seite(_nm, _kontext,
                                         bevorzugt=_modellseite)
            if _seite is None:
                # Dokument enthaelt die Aussage nicht auf einer klaren Seite
                # -> gar kein Link, lieber schweigen als falsch belegen.
                continue
            stellen.append((a, e, _nm, _seite, _kontext))
            belegt.append((a, e))

    if not stellen:
        return text, 0
    stellen.sort()
    raus, bis = [], 0
    for a, e, name, seite, kontext in stellen:
        raus.append(text[bis:a])
        sicher = name.replace("[", "\\[").replace("]", "\\]")
        # Kursiv bleibt kursiv - die Seitenzahl stammt vom Modell, nicht aus
        # unserer Pruefung. Sie fuehrt aber immerhin auf die richtige Seite.
        # ⭐ Ueber /stelle statt ueber das rohe PDF: Nur dort koennen wir
        #   die Seite ALS BILD zeigen und die Fundstelle einfaerben. Die
        #   PDF-Anzeige des Browsers kann gar nichts markieren - deshalb
        #   war nie etwas gelb.
        # ⭐ Die Kernbegriffe der Aussage mitgeben, damit /stelle
        #   sie gelb markiert (Stichwort-Rueckfall in pdfstelle.kaesten) -
        #   auch ohne woertliches Zitat.
        # ⚠ NUR Fachwoerter, nicht den rohen Antwort-Markdown: Der
        #   Stichwort-Rueckfall markierte sonst Allerweltswoerter wie
        #   "folgende" quer ueber die Seite - das sah aus wie ein Beleg
        #   fuer nichts. Bleibt kein Fachwort uebrig, wird die Seite ohne
        #   Markierung gezeigt - ehrlicher als bunte Zufallstreffer.
        _fachworte = [w for w in re.sub(r"[^0-9a-zA-ZäöüÄÖÜß]+", " ",
                                        kontext).split()
                      if len(w) > 6 and w.lower() not in _FUELLWOERTER][:12]
        ziel = "/stelle?dok=%s&seite=%s&zitat=%s" % (
            quote(name), seite, quote(" ".join(_fachworte)))
        # \u2b50 SICHTBARE KENNZEICHNUNG: Der
        #   Unterschied geprueft/genannt lag bisher NUR in der Kursivschrift
        #   und "S." statt "Seite" - das war im Text kaum zu erkennen.
        #   Jetzt steht ein Symbol IM Verweis, das
        #   die Fusszeile erklaert. Kursiv bleibt zusaetzlich.
        #   \u26a0 MARKER als Konstante, damit das Zeichen mit einer Aenderung
        #     tauschbar ist, falls es im Browser nicht auffaellt.
        # VERIFIZIERT: Die Seite ist nachgeschlagen (hoechste
        #   Wortdeckung), nicht geraten - deshalb ein normaler Verweis mit
        #   Seitenzahl, kein \u00b0-Marker, keine Kursivschrift.
        raus.append("[%s, Seite\u00a0%s](%s)" % (sicher, seite, ziel))
        bis = e
    raus.append(text[bis:])
    return "".join(raus), len(stellen)



def _seite_glaubhaft(name, nr):
    """Ist die vom Modell behauptete Seitenzahl ueberhaupt moeglich?

    ⛔ Die Zahl kommt UNGEPRUEFT aus dem Antworttext. Weiss das Modell
      keine Seite, schreibt es gern "S. 1" - und Seite 1 ist bei jeder
      Arbeit das DECKBLATT. Ein Verweis darauf sieht aus wie ein Beleg und
      fuehrt aufs Titelblatt - das tritt immer wieder auf,
      auch in anderen Chats.

    Zwei Pruefungen:
      - Seite 1 bei einer Arbeit mit mehr als drei Seiten: verworfen.
        Faustregel, keine Messung - aber sie ersetzt eine Behauptung durch
        Schweigen, und das ist die richtige Richtung.
      - Seite groesser als die Arbeit: verworfen.

    Rueckgabe: die Zahl, oder None. Dann wird die ARBEIT verlinkt, nicht
    die Seite.
    """
    if not nr:
        return None
    try:
        zahl = int(nr)
    except (TypeError, ValueError):
        return None
    if zahl < 1:
        return None
    seiten = 0
    try:
        # ⚠ seitenzahl() will den NAMEN, nicht den Pfad. Bei Uebergabe
        #   des Pfades liefert sie still 0, und die Pruefung "Seite groesser
        #   als die Arbeit" griff nie.
        schluessel = _pdf_schluessel(name)
        if schluessel:
            seiten = pdfstelle.seitenzahl(schluessel) or 0
    except Exception:
        seiten = 0
    if zahl == 1 and (seiten == 0 or seiten > 3):
        return None
    if seiten and zahl > seiten:
        return None
    return nr


# Generische lange Woerter, die KEIN Fachbegriff sind. Gemessen:
# ohne diese Liste teilte die Plasma-Arbeit M-00-000 mit einer Heisskanal-
# Frage nur "innerhalb, zwischen, thermische, unterschieden" - lauter Fueller -
# und wurde faelschlich verlinkt. Mit Liste bleibt nur der Fachbegriff-Kern.
_FUELLWOERTER = {
    "innerhalb", "zwischen", "unterschieden", "unterschied", "unterschiede",
    "unterschiedliche", "unterschiedlichen", "unterschiedlicher", "verschiedene",
    "verschiedenen", "verschieden", "verschiedener", "beispielsweise",
    "insbesondere", "allerdings", "hinsichtlich", "entsprechend", "entsprechende",
    "entsprechenden", "gegenueber", "gegenüber", "weiterhin", "ausserdem",
    "außerdem", "waehrend", "während", "wodurch", "worden", "werden", "wurde",
    "wurden", "welche", "welcher", "welches", "dadurch", "deshalb", "deswegen",
    "jeweils", "mehrere", "mehreren", "saemtliche", "sämtliche", "gesamten",
    "gesamte", "allgemeine", "allgemeinen", "allgemein", "wesentliche",
    "wesentlichen", "wesentlich", "folgenden", "folgende", "folgender", "sowohl",
    "naemlich", "nämlich", "sondern", "entweder", "thermische", "thermischen",
    "thermisch", "moeglich", "möglich", "moegliche", "mögliche", "moeglichen",
    "möglichen", "ermoeglicht", "ermöglicht", "ermoeglichen", "ermöglichen",
    "verwendet", "verwendung", "dargestellt", "betrachtet", "betrachtung",
    "zusaetzliche", "zusätzliche", "zusaetzlich", "zusätzlich", "besonders",
    "bezueglich", "bezüglich", "aufgrund", "entstehen", "entsteht", "erforderlich",
    "geschlossenen", "geschlossene", "offenen", "wurden", "koennen", "können",
    "sollte", "sollten", "muessen", "müssen", "verwendeten", "verwendeter",
    "grundsaetzlich", "grundsätzlich", "typischerweise", "beziehungsweise",
    "vergleich", "vergleichen", "gegenuebergestellt", "gegenübergestellt",
}


def _dok_hat_aussage(name, kontext):
    """True, wenn das Dokument die Aussage plausibel enthaelt - zum Sperren
    halluzinierter Inline-Zitate. Grundlage (gemessen): FACHWOERTER
    (>6 Z.) trennen das richtige Dokument (>=3 Treffer je Seite) sauber vom
    falschen (<=2). Unpruefbar (keine Seitentexte, z.B. Literatur; oder zu
    wenig Fachwoerter in der Aussage) -> True, also NICHT sperren."""
    schluessel = _pdf_schluessel(name)
    if not schluessel:
        return True
    try:
        seiten = _seitentexte_pdf(schluessel) or []
    except Exception:
        return True
    if not seiten:
        return True
    ziel6 = {w for w in re.sub(r"[^0-9a-zA-ZäöüÄÖÜß]+",
                               " ", (kontext or "").lower()).split()
             if len(w) > 6 and w not in _FUELLWOERTER}
    if len(ziel6) < 3:
        return True
    for txt in seiten:
        sw6 = {w for w in re.sub(r"[^0-9a-zA-ZäöüÄÖÜß]+",
                                 " ", (txt or "").lower()).split()
               if len(w) > 6 and w not in _FUELLWOERTER}
        if len(ziel6 & sw6) >= 3:
            return True
    return False


def _verifizierte_seite(name, kontext, bevorzugt=None):
    """Die Seite im Dokument, auf der die AUSSAGE wirklich steht - oder None.

    ⭐ Gemessen an echten Antworten nennt das Modell zu 94% das
    richtige DOKUMENT, aber nur zu 11% die richtige SEITE (oft geraten,
    meist "S. 1"). Statt der genannten Seite zu trauen, suchen wir hier die
    Seite mit der hoechsten Wortdeckung zur Aussage DAVOR und verlinken
    DIESE - ein verifizierter Verweis auf die Stelle, wo es wirklich steht.
    Deckt sich keine Seite genug (Dokument enthaelt die Aussage nicht),
    kommt None: dann kein Link, lieber schweigen als auf die falsche Seite
    zeigen.

    ⭐ `bevorzugt` = die Seite, die das MODELL genannt hat. Besteht sie
    dieselbe Deckungspruefung wie alle anderen, gewinnt SIE - auch wenn
    eine andere Seite rechnerisch knapp hoeher deckt. Gemessen (C1/C2 im
    WLF-Ansatz): Das Modell nannte richtig Seite 43, die reine
    Bestwahl "korrigierte" auf die falsche 42, weil eine fruehere Seite
    zufaellig aehnliche Allerweltswoerter trug. Eine Modell-Seite, die die
    Pruefung NICHT besteht (z. B. das notorische "S. 1"), wird weiterhin
    ersetzt oder verworfen.
    """
    _sch, seiten = _seitentexte_von(name)
    if not seiten:
        return None
    ziel = {w for w in re.sub(r"[^0-9a-zA-zäöüÄÖÜß]+", " ",
                              (kontext or "").lower()).split() if len(w) > 4}
    if len(ziel) < 4:
        return None
    # ⭐ >4-Woerter trennten das richtige Dokument nicht vom falschen
    #   (M-00-000 Plasma riss die 0.25 bei einer Heisskanal-Frage). Gemessen
    #   trennen FACHWOERTER (>6 Z.) sauber: richtig >=3, falsch <=2. Also muss
    #   die gewaehlte Seite zusaetzlich >=3 unterscheidende Woerter decken -
    #   aber nur, wenn die Aussage ueberhaupt genug Fachwoerter hat.
    ziel6 = {w for w in ziel if len(w) > 6 and w not in _FUELLWOERTER}
    streng = len(ziel6) >= 3
    beste, wert = None, 0.0
    bestanden = set()          # Seiten, die die volle Pruefung bestehen
    for i, txt in enumerate(seiten, 1):
        sw = {w for w in re.sub(r"[^0-9a-zA-zäöüÄÖÜß]+", " ",
                                (txt or "").lower()).split() if len(w) > 4}
        if not sw:
            continue
        if streng and len(ziel6 & {w for w in sw
                                   if len(w) > 6 and w not in _FUELLWOERTER}) < 3:
            continue   # zu wenig unterscheidende Deckung -> diese Seite nicht
        d = len(ziel & sw) / len(ziel)
        if d >= 0.25:
            bestanden.add(i)
        if d > wert:
            beste, wert = i, d
    if bevorzugt in bestanden:
        return bevorzugt
    return beste if wert >= 0.25 else None


def nennungshinweis(anzahl):
    """Was der kursive Verweis bedeutet - einmal unter der Antwort."""
    if not anzahl:
        return ""
    # Keine Sternchen im Satzinneren: Markdown zerlegt eine kursive Zeile
    # am naechsten Paar, und der Hinweis stuende halb kursiv da.
    # ⚠ Gekuerzt: Der alte Text erklaerte, was ein kursiver
    #   Verweis ist - ein Gestaltungsmittel, nicht die Sache. Wichtig ist
    #   nur, was er BEDEUTET: dort wurde nichts nachgeschlagen.
    # ⚠ "N Verweise ohne Seitenzahl" benannte eine Eigenschaft
    #   statt der Sache - niemand wusste, welche Verweise gemeint sind.
    # ⚠ "kursiv" beschrieb die Schriftart, nicht die Sache - die
    #   kursiven Verweise waren im Text kaum zu erkennen.
    return ("*%d Quellenangaben wurden im Original nachgeschlagen — der "
            "Klick führt auf die gefundene Stelle.*" % anzahl)


def zusammenfassungs_fuss(titel, gesamt, gelesen, auftrag=False):
    """Der ehrliche Fuss unter einer Zusammenfassung.

    Frueher stand dort "Zusammenfassung des vollstaendigen
    Dokuments" - auch dann, wenn der Mittelteil ausgelassen war. Bei
    DS-00-000 war das nur ein kleiner Teil des Dokuments, als
    Ganzes ausgegeben. Wer den Zusatz ueberliest, haelt sie fuer
    vollstaendig.
    """
    name = assistent._titel_saubern(titel)
    if auftrag and gelesen >= gesamt:
        return ("*Aus dem vollständigen Dokument „%s“ (%d Zeichen) "
                "erarbeitet — nicht aus einzelnen Fundstellen. Inhalte nur "
                "aus dem Dokument, Form frei aufbereitet.*" % (name, gesamt))
    if auftrag:
        return ("*Aus „%s“ erarbeitet — gelesen wurden %d von %d Zeichen "
                "(Anfang und Schluss); der Mittelteil ist ausgelassen.*"
                % (name, gelesen, gesamt))
    if gelesen >= gesamt:
        return ("*Zusammenfassung des vollständigen Dokuments „%s“ "
                "(%d Zeichen) — nicht aus einzelnen Fundstellen, sondern "
                "aus dem ganzen Text.*" % (name, gesamt))
    anteil = 100.0 * gelesen / max(1, gesamt)
    return ("*Zusammenfassung von „%s“ — gelesen wurden Anfang und Schluss, "
            "%d von %d Zeichen (%.0f %%). Der Mittelteil ist ausgelassen; "
            "für Einzelheiten daraus bitte gezielt nachfragen.*"
            % (name, gelesen, gesamt, anteil))


def nachtraege(art, frage, roh, quellen, modell=None,
               pruefungen=None, geprueft=None):
    """Was unter die gepruefte Antwort gehoert. Liste von Abschnitten.

    KI4KI-NACHTRAG. Drei Faelle, alle als Anhang - der Antworttext bleibt
    unberuehrt:

      Negativfrage: Der Abgleich der Optionen gegen die Fundstellen. Was
      sich nicht belegen laesst, ist die gesuchte Antwort - ausdruecklich
      als Schluss aus dem Nichtfinden gekennzeichnet.

      Auswahlfrage: Der Buchstabe. Frueher antwortete die Anlage
      bei "tex" inhaltlich richtig, benannte aber nie das B - bei einem
      Katalog mit hundert Fragen die halbe Arbeit.

      Ablehnung: Wo nachgesehen wurde. "Keine belastbare Information" ist
      ehrlich, aber eine Sackgasse; der Nutzer kann nicht unterscheiden,
      ob die Suche am Thema vorbeiging oder ob nichts da ist.

    modell ist eine Funktion (Auftrag -> Text) oder None. Ohne sie bleibt
    alles regelbasiert, nur die Zuordnung wird dann seltener eindeutig.
    """
    raus = []
    try:
        optionen = assistent.optionen_finden(frage)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return raus

    try:
        if art == "negativfrage":
            # Zuerst das Modell fragen. Es hat die Fundstellen gelesen und
            # kann "Einbringen" und "Einarbeiten" als dasselbe erkennen -
            # eine Wortzaehlung kann das nicht und hat schon eine
            # richtige Antwort fuer nicht eindeutig erklaert.
            b = ""
            if optionen and modell and not assistent.ist_ablehnung(roh):
                try:
                    auftrag = assistent.negativ_auftrag(frage, roh, optionen)
                    b = assistent.buchstaben_lesen(modell(auftrag), optionen)
                except Exception:
                    traceback.print_exc(file=sys.stderr)
            if b:
                raus.append(assistent.auswahl_nachtrag(
                    optionen, b,
                    "Die Frage verlangt das, was *nicht* zutrifft. Der "
                    "Buchstabe folgt aus der belegten Antwort darüber — "
                    "bitte am Original gegenprüfen."))
            elif not optionen:
                # Freie Verneinung ohne Antwortmoeglichkeiten. Frueher
                # hing der ganze Zweig an `optionen` - "Was ist
                # keine Aufgabe des Extruders?" bekam deshalb gar keinen
                # Nachtrag. Der Hinweis kommt bewusst AUCH bei einer
                # Ablehnung: an drei Laeufen gemessen ist sie dort der
                # Regelfall, und ohne Begruendung sieht sie nach einer
                # Wissensluecke aus, obwohl es an der Frageform liegt.
                raus.append(assistent.negativ_ohne_optionen(
                    frage, abgelehnt=assistent.ist_ablehnung(roh)))
            else:
                # Rueckfall auf den Abgleich mit den Fundstellen. Er
                # schweigt, wenn er nichts Eindeutiges findet.
                h = assistent.negativ_schluss(optionen, quellen or [])
                if h:
                    raus.append(h)
        elif optionen and not assistent.ist_ablehnung(roh):
            # Nur wenn ueberhaupt geantwortet wurde. Einen Buchstaben unter
            # eine Ablehnung zu setzen waere die schlimmste Variante:
            # sicher aussehend und unbelegt.
            _b, sicher = assistent.option_zur_antwort(optionen, roh)
            b = [_b] if _b else []
            if not sicher and modell:
                try:
                    auftrag = assistent.auswahl_auftrag(frage, roh, optionen)
                    b = assistent.buchstaben_lesen(modell(auftrag), optionen)
                except Exception:
                    traceback.print_exc(file=sys.stderr)
            raus.append(assistent.auswahl_nachtrag(optionen, b))
    except Exception:
        traceback.print_exc(file=sys.stderr)

    try:
        h = assistent.trotzdem_gefunden(roh, quellen or [])
        if h:
            raus.append(h)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    # KI4KI-WIDERSPRUCH: Sagt der Fliesstext das Gegenteil seines eigenen
    # Belegs? In einem Fall behauptete eine Antwort "Erhoehung der
    # Materialkosten", waehrend das Zitat darunter - korrekt geprueft -
    # "Verringerung" sagte. Die Belegpruefung schlaegt ZITATE nach und hat
    # den Fliesstext nie dagegen gehalten.
    try:
        if pruefungen and geprueft:
            # Nur der Fliesstext, nicht der Belege-Abschnitt: sonst wird
            # jedes Zitat gegen sich selbst geprueft.
            schnitt = geprueft.find("**Belege**")
            fliess = geprueft[:schnitt] if schnitt > 0 else geprueft
            h = assistent.widerspruchshinweis(fliess, pruefungen)
            if h:
                raus.append(h)
                print("[Widerspruch] Text und Beleg gehen auseinander",
                      file=sys.stderr, flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    # KI4KI-LUECKE: Aussagen, die eine Quelle NENNEN, aber keine belegen.
    # In einer Antwort standen neun Aussagen; sechs kamen mit
    # Zitat und wurden nachgeschlagen, drei nicht - und sahen im Text
    # genauso aus. Eine Pruefung, die ueber ihre eigenen Luecken schweigt,
    # erzeugt Vertrauen, das sie nicht deckt.
    try:
        if geprueft:
            schnitt = geprueft.find("**Belege**")
            fliess = geprueft[:schnitt] if schnitt > 0 else geprueft
            h = assistent.unbelegt_hinweis(fliess)
            if h:
                raus.append(h)
                print("[Unbelegt] %d Aussage(n) ohne Zitat"
                      % len(assistent.unbelegte_aussagen(fliess)),
                      file=sys.stderr, flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)
    return raus

def quellen_veredeln(quellen):
    """Quellenliste auf die Original-PDFs umschreiben.

    AnythingLLM zeigt dort den Namen der eingelesenen Markdown-Fassung
    ("PA-00-000.md"). Fuer einen Wissenschaftler ist das die falsche
    Auskunft - er will die Arbeit, nicht unser Zwischenformat. Also wird
    der Titel auf das PDF samt Seitenzahl umgeschrieben und die Adresse
    des PDFs in den Text vorangestellt.
    """
    for q in quellen:
        titel = q.get("title") or ""
        stamm = titel[:-3] if titel.endswith(".md") else titel
        stamm = _pdf_schluessel(stamm)
        if not stamm:
            continue
        seite = None
        text = q.get("text") or ""
        try:
            dok = BESTAND.hol(stamm + ".md") or BESTAND.hol(stamm)
            for zeile in text.split("\n") if text else []:
                zeile = zeile.strip()
                if len(zeile) < 60:
                    continue
                # Doclings Marke nur als Vermutung nehmen und gegen das
                # PDF pruefen - sonst nennt die Quellenspalte eine andere
                # Seite als der Beleg daneben.
                vermutung = None
                if dok:
                    tr = dok.suche(veredeln._nur_falten(zeile))
                    if tr:
                        vermutung = dok.seite_bei(tr[1])
                echt, _ = pdfstelle.finde_seite(stamm, zeile, vermutung)
                seite = echt or vermutung
                if seite:
                    break
        except Exception:
            pass
        q["title"] = ("%s.pdf · Seite %d" % (stamm, seite) if seite
                      else "%s.pdf" % stamm)
        adresse = "/pdf/%s%s" % (stamm, "#page=%d" % seite if seite else "")
        q["url"] = adresse
        q["docSource"] = adresse
        kopf = ("Original-PDF: %s%s\n"
                "%s\n\n" % (adresse, " (Seite %d)" % seite if seite else "",
                             "-" * 40))
        if not text.startswith("Original-PDF:"):
            q["text"] = kopf + text
    return quellen


class Griff(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass          # keine Mitschrift der Fragen

    # ---------------------------------------------------------------- Hilfen
    def _koerper(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else None

    def _ist_seite(self):
        """Ist das eine Seite (bekommt unser Skript) oder Beiwerk?

        An der Adresse zu erkennen: etwas mit Dateiendung (.js, .css, .png)
        ist Beiwerk und darf zwischengespeichert werden. Alles andere ist
        eine Seite - und Seiten veraendern wir, also duerfen sie NICHT aus
        dem Zwischenspeicher kommen.
        """
        weg = self.path.split("?")[0].rstrip("/")
        letztes = weg.rsplit("/", 1)[-1]
        return ("." not in letztes) or letztes.lower().endswith(".html")

    def _weiterleiten(self, methode, koerper=None):
        # KI4KI-POSITIVLISTE: destruktive Verwaltungsbefehle abfangen.
        if verwaltungsbefehl(methode, self.path):
            gesperrt = (POSITIVLISTE == "sperren")
            print("[Positivliste] %s %s -> %s"
                  % (methode, self.path.split("?")[0],
                     "GESPERRT" if gesperrt else "nur gemeldet (Standard)"),
                  file=sys.stderr, flush=True)
            if gesperrt:
                self._json({"error": "Not allowed."}, code=403)
                return
        if koerper is None:
            koerper = self._koerper()
        req = urllib.request.Request(ZIEL + self.path, data=koerper,
                                     method=methode)
        seite = self._ist_seite()
        for k, v in self.headers.items():
            # ⛔ Bei SEITEN duerfen die Nachfrage-Kopfzeilen NICHT durch.
            #   Sonst antwortet AnythingLLM mit "304 nicht geaendert" - und
            #   der Browser behaelt seine alte Fassung samt unserem ALTEN
            #   eingespritzten Skript. Genau daran sind VIER
            #   Reparaturen am Kopier-Knopf gescheitert: Sie lagen auf dem
            #   Server und erreichten den Browser nie.
            if seite and k.lower() in ("if-none-match", "if-modified-since"):
                continue
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                art = (r.headers.get("Content-Type") or "").lower()
                # Die Oberflaeche bekommt unser Skript angehaengt, alles
                # andere (Bilder, Skripte, Daten) fliesst unveraendert.
                if "text/html" in art:
                    daten = r.read()
                    try:
                        seite = daten.decode("utf-8")
                        if "</body>" in seite:
                            seite = seite.replace("</body>",
                                                  EINHAENGER + "</body>", 1)
                        else:
                            seite += EINHAENGER
                        daten = seite.encode("utf-8")
                    except UnicodeDecodeError:
                        pass
                    self.send_response(r.status)
                    for k, v in r.headers.items():
                        # ⛔ ETag und Last-Modified beschreiben die
                        #   ORIGINALSEITE (786 Bytes) - wir senden aber
                        #   unsere veraenderte Fassung (11.715 Bytes). Sie
                        #   durchzureichen verspricht eine Gleichheit, die
                        #   es nicht gibt, und der Browser holt beim
                        #   naechsten Mal nichts Neues.
                        if k.lower() in ("etag", "last-modified",
                                         "cache-control", "expires"):
                            continue
                        if k.lower() not in ("transfer-encoding", "connection",
                                             "content-length"):
                            self.send_header(k, v)
                    self.send_header("Cache-Control",
                                     "no-store, no-cache, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Content-Length", str(len(daten)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(daten)
                    return
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection",
                                         "content-length"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    stueck = r.read(16384)
                    if not stueck:
                        break
                    self.wfile.write(stueck)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            daten = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "connection",
                                     "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
        except Exception as e:
            self._fehler(502, str(e))

    def _json(self, koerper, code=200):
        """Eine JSON-Antwort schicken - mit Laengenangabe, sonst wartet der
        Browser auf ein Ende, das nie kommt."""
        daten = json.dumps(koerper, ensure_ascii=False).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
        except Exception:
            pass

    def _fehler(self, code, text):
        daten = json.dumps({"error": text[:300]}).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
        except Exception:
            pass

    # ------------------------------------------------------------ PDF-Ausgabe
    def _pdf(self, name):
        """Quell-PDF ausliefern - nur was in der Liste steht.

        Der Name wird nachgeschlagen, nie zu einem Pfad zusammengesetzt.
        Damit laufen Pfad-Tricks ins Leere.
        """
        name = _stamm(name)
        pfad = PDFS.get(_pdf_schluessel(name) or "")
        if not pfad or not os.path.exists(pfad):
            # Kein PDF: die Originaldatei (Excel, Word, ...) aus dem Archiv
            # eines Bereichs - nachgeschlagen ueber den Stamm, nie als Pfad
            # zusammengesetzt.
            pfad = _archivdatei(name)
        if not pfad or not os.path.exists(pfad):
            self._fehler(404, "Dieses Dokument liegt nicht vor.")
            return
        # KI4KI-TOR-PDF: Angemeldet zu sein genuegt nicht. Das Dokument
        # muss in einem Bereich dieser Anmeldung liegen - sonst kam ein
        # Konto ohne jede Zuweisung an das vollstaendige PDF, sobald es den
        # Namen kannte. Antwort wie bei einem unbekannten Namen.
        if not dokument_erlaubt(name, self.headers):
            self._fehler(404, "Dieses PDF liegt nicht vor.")
            return
        try:
            with open(pfad, "rb") as fh:
                daten = fh.read()
        except OSError as e:
            self._fehler(500, str(e))
            return
        import mimetypes
        typ = "application/pdf" if pfad.lower().endswith(".pdf") else \
            (mimetypes.guess_type(pfad)[0] or "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Content-Disposition",
                         '%s; filename="%s"' % ("inline" if typ == "application/pdf" else "attachment",
                                                os.path.basename(pfad).replace('"', "")))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)

    # ----------------------------------------------------------- Chat abfangen
    def _chat(self):
        print("[Chat] %s" % self.path, file=sys.stderr, flush=True)
        koerper = self._koerper()
        try:
            frage = (json.loads(koerper or b"{}") or {}).get("message") or ""
        except Exception:
            frage = ""
        # KI4KI-ANHANG-WEG-A: frisch angehaengte Datei -> direkt daraus antworten
        try:
            if self._anhang_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # ⭐ K2: "Falsche Quelle: ..." / "Feedback: ..." als Chatzeile - landet im
        #   Protokoll und in /rueckmeldungen, nicht beim Modell.
        _rm = _RUECKMELDUNG_CHAT.match(frage or "")
        if _rm:
            try:
                gespraech_k = GESPRAECHE.kennung(self.path, self.headers)
                lf = GESPRAECHE.letzte_frage(gespraech_k)
                pruefprotokoll.schreibe(
                    art="rueckmeldung",
                    konto=pruefprotokoll.pseudonym(pruefprotokoll.konto_aus(self.headers)),
                    bereich=(re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "") or [None, None])[1]
                    if re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "") else None,
                    bewertung="falsche Quelle" if re.search(r"quelle|beleg", frage, re.I) else "nicht hilfreich",
                    text=_rm.group(1).strip()[:600], faden=gespraech_k.split("|")[1] if "|" in gespraech_k else None,
                    frage_original=lf[0] if lf else None)
                _text = ("Danke — notiert%s. Das landet in der Rückmeldungsliste, die der Betreiber sieht. "
                         "Wenn du magst, sag mir gleich, was richtig wäre, dann suche ich noch einmal gezielt."
                         % (" als „falsche Quelle“" if re.search(r"quelle|beleg", frage, re.I) else ""))
                self._direkt_senden("meta", frage, _text)
                print("[Rueckmeldung] Chat: %s" % _rm.group(1)[:60], file=sys.stderr, flush=True)
                return
            except Exception:
                traceback.print_exc(file=sys.stderr)
        # ⭐ ROLLE EINRICHTEN (27.08.): drei Fragen im Chat -> dokumente/<bereich>/prompt.md
        try:
            if self._rolle_antwort(frage) or self._kategorie_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # 'Tu das Dokument raus' / Vergleich zweier Dokumente / 'Zeig Bild 2.1' - ohne Modell
        try:
            _weg = self._faden_raus(frage)
            if _weg and len(re.sub(r"[^\wäöüÄÖÜß]+", " ", frage).split()) <= 8:
                self._direkt_senden("meta", frage, "In Ordnung — %s ist nicht mehr das Faden-Dokument. Die nächste Frage geht wieder über den ganzen Bestand." % assistent._titel_saubern(_weg))
                return
            if self._vergleich_vorab(frage):
                return
            if self._bild_vorab(frage):
                return
            if self._fakten_vorab(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # ⭐ PRUEFUNGSKATALOG (26.08.): exakte Fragen aus der Datei, Antwort gegen
        #   den Katalog - deterministisch, ohne Modell. Emrach: "er sollte doch
        #   exakte Fragen aus der Datei mir nennen ... pruefst du anhand des
        #   Katalogs, ob das richtig ist."
        try:
            if self._pruefung_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # ⭐ BESTANDSFRAGE ist eine Abfrage, keine Modellaufgabe: Tabelle mit
        #   Kennung/Titel/Verfasser/Jahr und Links (gemessen 26.08.: Stufe 2
        #   antwortete aus der Dokumentliste im Kopf - nackte Aufzaehlung).
        try:
            if self._bestand_vorab(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # ⭐ STUFE 2 (ARCHITEKTUR-GESPRAECH §4): Das Modell fuehrt das Gespraech
        #   selbst - mit Werkzeugen und dem ganzen Faden. Faellt es aus, laeuft
        #   der bisherige Weg (Absicht/Regeln) weiter.
        if gespraechsmodus.AN and not assistent.export_frage(frage):
            try:
                if self._gespraech_antwort(frage):
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)
        # KI4KI-META: Begruessung / "Was kannst du?" freundlich beantworten
        try:
            if self._meta_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # KI4KI-BILD: "Zeig mir Bild 2.1" direkt aus dem Dokument
        try:
            if self._bild_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # ---- Was fuer eine Frage ist das ueberhaupt? --------------------
        # AnythingLLM sucht im Modus "query" mit dem ROHEN Fragetext und
        # kennt den Gespraechsverlauf dabei nicht.
        # Deshalb entscheidet sich hier, ob die Frage so weitergereicht
        # wird, angereichert werden muss oder gar nicht erst zu
        # AnythingLLM gehoert.
        gesucht_text, begonnen = None, time.time()
        gespraech, art, gegenstand = None, "normal", None
        _vorher_best = None
        try:
            gespraech = GESPRAECHE.kennung(self.path, self.headers)
            try:
                _mb = re.match(r"^/api/(?:v1/)?workspace/([^/]+)"
                               r"(?:/thread/([^/]+))?", self.path or "")
                _sch = (_mb.group(1) + "|" + (_mb.group(2) or "default")) \
                    if _mb else None
            except Exception:
                _sch = None
            if _sch:
                _lauf = _arbeitet_alle().get(_sch)
                if _lauf and time.time() - (_lauf.get("wann") or 0) < 240:
                    # ⭐ Fuer diesen Thread laeuft schon eine Antwort. Die
                    #   zweite NICHT still verwerfen, sondern um Geduld bitten.
                    try:
                        self._sende_strom([{
                            "uuid": _neue_marke("warten"),
                            "type": "textResponseChunk",
                            "textResponse": WARTE_TEXT, "sources": [],
                            "close": True, "error": False}])
                    except Exception:
                        pass
                    return
                _arbeitet_setzen(_sch, frage)
                self._besitzt_sperre = _sch
            gegenstand = GESPRAECHE.letzter_gegenstand(gespraech)
            # ⭐ BESCHWERDE zuerst: "Das ist ein Diagramm aus einer anderen
            #   Dissertation!!!!!" ist keine Frage. Gemessen 25.08.: ging als
            #   Bestands-Verfeinerung durch -> Bestandstabelle; die naechste
            #   ("ich habe nicht nach einem Bestand gefragt!") wurde zur
            #   Wortsuche nach "Bestand".
            _faden_dok_jetzt = GESPRAECHE.letztes_dokument(gespraech)
            self._absicht = None
            if assistent.ist_beschwerde(frage):
                art = "beschwerde"
            elif assistent.ist_zweifel(frage):
                art = "zweifel"
            elif assistent.ist_anlagefrage(frage):
                art = "anlage"
            elif assistent.export_frage(frage):
                art = "normal"     # der Export-Weg im Faden-Block
            else:
                # ⭐ STUFE 1: Das Modell erkennt die Absicht - mit Gespraech,
                #   Faden-Zustand und Dokumentliste (ARCHITEKTUR-GESPRAECH §3).
                #   Faellt es aus oder ist es unsicher, greift der Regel-Router.
                art = None
                if absicht.AN:
                    try:
                        _namen_abs = (titel_im_bereich(self.path, self.headers)
                                      or nur_erlaubte(BESTAND.titel(), self.headers) or [])
                        _zeilen = [assistent.dokument_zeile(n) for n in sorted(_namen_abs)[:40]]
                        _a, _grund, _ms = absicht.erkennen(
                            frage, GESPRAECHE.verlauf_kurz(gespraech), _faden_dok_jetzt,
                            GESPRAECHE.letzte_art(gespraech), GESPRAECHE.offene_wahl(gespraech),
                            _zeilen, _namen_abs)
                        print("[Absicht] %s dok=%s aspekt=%r sicher=%.2f %d ms (%s) <- %r"
                              % (_a["aktion"] if _a else "-", _a.get("dokument") if _a else "-",
                                 _a.get("aspekt") if _a else "", _a["sicherheit"] if _a else 0,
                                 _ms, _grund, frage[:60]), file=sys.stderr, flush=True)
                        self._absicht = _a
                        self._absicht_protokoll = ({"aktion": _a["aktion"], "dokument": _a.get("dokument"),
                                                    "sicherheit": _a["sicherheit"], "ms": _ms, "grund": _grund}
                                                   if _a else {"aktion": None, "ms": _ms, "grund": _grund})
                        if _a:
                            art = absicht.als_art(_a)
                    except Exception:
                        traceback.print_exc(file=sys.stderr)
                        self._absicht = None
                if art is None:
                    art = assistent.einordnen(frage, hat_verlauf=bool(gegenstand))
                    art = _wahl_beantwortet(gespraech, frage, art)
                # ⭐ VETO: "... hat diese Arbeit?" bei gesetztem Faden-Dokument ist
                #   eine Frage an DIESES Dokument, keine Bestandsfrage - auch wenn
                #   das Auffangnetz "bestand" sagt (gemessen 26.08.).
                if art == "bestand" and not getattr(self, "_absicht", None) and \
                        not assistent.ist_thema_bezug(frage) and (
                        (_faden_dok_jetzt and assistent.meint_dieses_dokument(frage))
                        or assistent.dokument_fakten_frage(frage)):
                    print("[Assistent] Veto: meint das Faden-Dokument, nicht den Bestand",
                          file=sys.stderr, flush=True)
                    art = "normal"
            _vorher_best = GESPRAECHE.letzte_bestand(gespraech)
            # Verfeinerung nur, wenn der UNMITTELBAR vorige Schritt eine
            # Bestandsfrage war - nicht irgendeine im Faden davor.
            if art not in ("bestand", "beschwerde", "zweifel", "anlage", "klaerfrage", "smalltalk") \
                    and not getattr(self, "_absicht", None) and _vorher_best and \
                    GESPRAECHE.letzte_art(gespraech) == "bestand" and \
                    assistent.ist_bestand_verfeinerung(frage):
                art = "bestand"
            if art != "normal":
                print("[Assistent] %s: %r" % (art, frage[:70]),
                      file=sys.stderr, flush=True)
        except Exception:
            # Faellt die Einordnung aus, laeuft alles wie vorher weiter.
            traceback.print_exc(file=sys.stderr)
            art = "normal"

        # ---- Bestandsfragen beantwortet der Proxy selbst ----------------
        # KI4KI-TOR-JSON: Derselbe Riegel wie im Browser-Weg.
        # Ohne ihn gab dieser Weg einem Konto ohne
        # Bereichszuweisung Bestandsauskunft und Dokumenttitel -
        # der Torwaechter sass nur in den Methoden, die allein
        # der Browser-Weg aufruft.
        if art in ("bestand", "zusammenfassung") and not \
                bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."},
                       code=404)
            return

        # ⭐ STUFE 1: Was das Modell erkannt hat, wird hier ausgefuehrt - mit
        #   den vorhandenen Werkzeugen. Gibt False zurueck, wenn der alte Weg
        #   (nach `art`) weitermachen soll.
        if getattr(self, "_absicht", None):
            try:
                if self._absicht_ausfuehren(frage):
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "bestand" and gespraech and assistent.ist_thema_bezug(frage) \
                and GESPRAECHE.letztes_dokument(gespraech):
            try:
                _dok = GESPRAECHE.letztes_dokument(gespraech)
                _namen = (titel_im_bereich(self.path, self.headers)
                          or nur_erlaubte(BESTAND.titel(), self.headers) or [])
                _aehnl = assistent.aehnliche_titel(_dok, _namen)
                if _aehnl:
                    _zeilen = "\n".join("- %s *(gemeinsam: %s)*"
                                        % (assistent.dokument_zeile(n), ", ".join(g[:3]))
                                        for n, g in _aehnl)
                    _text = ("Zum Thema von **%s** passen nach Titel:\n\n%s\n\n"
                             "*Verglichen wurden die Titel im Katalog — nicht der "
                             "Volltext. Für eine inhaltliche Suche: „im ganzen "
                             "Bestand: …“ mit dem konkreten Begriff.*"
                             % (assistent._titel_saubern(_dok), _zeilen))
                else:
                    _text = ("Zum Thema von **%s** finde ich im Katalog keinen "
                             "weiteren Titel mit gemeinsamen Begriffen. Inhaltlich "
                             "suchen: „im ganzen Bestand: <Begriff>“."
                             % assistent._titel_saubern(_dok))
                self._festhalten("bestand", frage, _text)
                GESPRAECHE.merken(gespraech, frage, "bestand", [])
                self._sende_strom([
                    {"uuid": _neue_marke("bestand"), "type": "textResponseChunk",
                     "textResponse": _text, "sources": [], "close": False,
                     "error": False},
                    {"uuid": _neue_marke("bestand"), "type": "textResponseChunk",
                     "textResponse": "", "sources": [], "close": True,
                     "error": False},
                ])
                print("[Assistent] Themen-Nachbarn zu %r: %d" % (_dok, len(_aehnl)),
                      file=sys.stderr, flush=True)
                return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "bestand":
            try:
                if self._bestandsauskunft(frage, _vorher_best):
                    GESPRAECHE.merken(gespraech, frage, "bestand", [])
                    return
            except Exception:
                # Kein Abbruch - die Frage geht dann eben den normalen Weg.
                traceback.print_exc(file=sys.stderr)

        if art in ("vergleich", "normal", "folgefrage") and gespraech:
            # ⭐ VERGLEICH ZWEIER DOKUMENTE als Tabelle mit Seitenbeleg je Zelle
            #   (GESPRAECH-ANFORDERUNGEN §2.17/§2.22) - Denken eingeschaltet.
            try:
                _namen = (titel_im_bereich(self.path, self.headers)
                          or nur_erlaubte(BESTAND.titel(), self.headers) or [])
                _vgl = assistent.vergleichs_dokumente(frage, _namen)
                if _vgl and self._vergleich_antwort(frage, _vgl[0], _vgl[1], _vgl[2]):
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "anlage":
            # Fragen an die Anlage selbst beantwortet der Proxy - ehrlich und
            # mit dem echten Faden-Zustand. Das Modell weiss davon nichts.
            try:
                _anz = dokumente_im_bereich(self.path, self.headers)
                _text = assistent.anlage_antwort(
                    GESPRAECHE.letztes_dokument(gespraech), _anz)
                self._festhalten("anlage", frage, _text)
                GESPRAECHE.merken(gespraech, frage, "anlage", [])
                self._sende_strom([
                    {"uuid": _neue_marke("anlage"), "type": "textResponseChunk",
                     "textResponse": _text, "sources": [], "close": False,
                     "error": False},
                    {"uuid": _neue_marke("anlage"), "type": "textResponseChunk",
                     "textResponse": "", "sources": [], "close": True,
                     "error": False},
                ])
                print("[Assistent] Anlage-Frage beantwortet", file=sys.stderr,
                      flush=True)
                return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art in ("beschwerde", "zweifel"):
            # ⭐ REPARATUR statt nur Entschuldigung (GESPRAECH-ANFORDERUNGEN
            #   §4.1): die letzte inhaltliche Frage noch einmal - diesmal
            #   NUR aus dem Faden-Dokument, Satz fuer Satz mit Seitenbeleg.
            #   Gemessen 26.08.: Eine wiederholte Zusammenfassung ist keine
            #   Reparatur (kam identisch aus dem Speicher). Bei einer reinen
            #   Zusammenfassungs-Bitte fragt die Anlage, WELCHE Aussage
            #   falsch ist - dann wird genau die geprueft.
            try:
                _dok = GESPRAECHE.letztes_dokument(gespraech)
                _letzte = GESPRAECHE.letzte_frage(gespraech)
                if _dok and _letzte:
                    _lf, _la = _letzte
                    _vor = (("Entschuldige — das war daneben. Noch einmal, "
                             "diesmal nur aus **%s**, Satz für Satz belegt:\n\n")
                            if art == "beschwerde" else
                            ("Ich prüfe das noch einmal — diesmal Satz für Satz "
                             "am Original von **%s**:\n\n")) \
                           % assistent._titel_saubern(_dok)
                    GESPRAECHE.merken(gespraech, frage, art, [])
                    if _la == "bild" or _ist_bildwunsch(_lf):
                        # Nicht dieselben drei noch einmal: die naechsten zeigen,
                        # bei "letzte/Kern..." in der Rueckmeldung danach waehlen.
                        _ab = 0 if re.search(r"letzte|kern|ergebnis|wichtig", frage, re.I) else 3
                        _fr = frage if _ab == 0 else _lf
                        if self._bild_antwort(_fr, erzwinge=_dok, vorspann=_vor, ab=_ab):
                            return
                    elif fadenfrage.suchwoerter(_lf):
                        if self._faden_antwort(_lf, _dok, vorspann=_vor):
                            return
                    else:
                        _text = assistent.rueckfrage_welche_aussage(_dok)
                        self._festhalten(art, frage, _text)
                        self._sende_strom([
                            {"uuid": _neue_marke(art), "type": "textResponseChunk",
                             "textResponse": _text, "sources": [], "close": False,
                             "error": False},
                            {"uuid": _neue_marke(art), "type": "textResponseChunk",
                             "textResponse": "", "sources": [], "close": True,
                             "error": False},
                        ])
                        return
                elif art == "zweifel":
                    _text = assistent.zweifel_antwort_ohne()
                    self._festhalten(art, frage, _text)
                    GESPRAECHE.merken(gespraech, frage, art, [])
                    self._sende_strom([
                        {"uuid": _neue_marke(art), "type": "textResponseChunk",
                         "textResponse": _text, "sources": [], "close": False,
                         "error": False},
                        {"uuid": _neue_marke(art), "type": "textResponseChunk",
                         "textResponse": "", "sources": [], "close": True,
                         "error": False},
                    ])
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)
            try:
                _text = assistent.beschwerde_antwort(
                    GESPRAECHE.letztes_dokument(gespraech))
                self._festhalten("beschwerde", frage, _text)
                GESPRAECHE.merken(gespraech, frage, "beschwerde", [])
                self._sende_strom([
                    {"uuid": _neue_marke("beschwerde"),
                     "type": "textResponseChunk", "textResponse": _text,
                     "sources": [], "close": False, "error": False},
                    {"uuid": _neue_marke("beschwerde"),
                     "type": "textResponseChunk", "textResponse": "",
                     "sources": [], "close": True, "error": False},
                ])
                print("[Assistent] Beschwerde beantwortet", file=sys.stderr,
                      flush=True)
                return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # ---- Dokumentwechsel (Pivot) und Faden-Antwort ------------------
        # ⭐ Nennt eine gewoehnliche Frage ein Dokument (Verfasser, Kennung,
        #   Titelwoerter), wird DAS zum Faden-Dokument. Ohne Nennung gilt das
        #   bisherige. Und in beiden Faellen wird NUR aus diesem Dokument
        #   geantwortet - nicht aus dem Gesamtbestand (Quellenvermischung).
        #   Heraus kommt man ausdruecklich: "im ganzen Bestand: ...".
        if art in ("normal", "folgefrage", "verfahren") and gespraech:
            try:
                _gesamt, _frage_rein = fadenfrage.will_gesamtbestand(frage)
                if getattr(self, "_absicht", None) and self._absicht["aktion"] == "gesamtbestand":
                    _gesamt = True
                _dok = GESPRAECHE.letztes_dokument(gespraech)
                _hit = None
                if not _gesamt and not assistent.bezieht_sich_auf_vorheriges(frage):
                    _namen = (titel_im_bereich(self.path, self.headers)
                              or nur_erlaubte(BESTAND.titel(), self.headers))
                    _hit, _ = assistent.dokument_gemeint(frage, _namen or [])
                    if _hit and _hit != _dok:
                        GESPRAECHE.dokument_merken(gespraech, _hit)
                        print("[Assistent] Dokumentwechsel: %r" % _hit,
                              file=sys.stderr, flush=True)
                        _dok = _hit
                # Export ("als CSV", "als BibTeX") - aus Katalog oder letzter Tabelle.
                if assistent.export_frage(frage):
                    if self._export_antwort(frage, _dok):
                        return
                # Abkuerzung aus DIESEM Dokument aufloesen ("Wofuer steht GFK?").
                _abk = assistent.abkuerzungs_frage(frage)
                if _abk and _dok and not _gesamt:
                    if self._abkuerzung_antwort(frage, _abk, _dok):
                        return
                # Zaehlbares (Seiten, Abbildungen, Tabellen, Verfasser, Jahr)
                # braucht kein Modell - PDF und Katalog wissen es.
                if assistent.dokument_fakten_frage(frage) and (
                        assistent.bezieht_sich_auf_vorheriges(frage)
                        or (_hit is not None and _dok == _hit)):
                    # Mit Faden-/genanntem Dokument: dieses. Ohne: alle im Bereich.
                    if self._fakten_antwort(frage, None if (_gesamt or not _dok) else _dok):
                        return
                if _gesamt and _frage_rein != frage:
                    # Vorspann "im ganzen Bestand:" abstreifen, Rest normal.
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = _frage_rein
                    koerper = json.dumps(d, ensure_ascii=False).encode()
                    frage = _frage_rein
                elif _dok and not _gesamt and (
                        art == "folgefrage"
                        or assistent.bezieht_sich_auf_vorheriges(frage)
                        or (_hit is not None and _dok == _hit)):
                    if self._faden_antwort(frage, _dok):
                        return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # ---- Zusammenfassungen brauchen das ganze Dokument --------------
        if art == "zusammenfassung" and gespraech and assistent.ist_zielfrage(frage):
            # "Was ist das Ziel der Arbeit?" ist eine Frage an das Dokument -
            # gezielt von den passenden Seiten (Sekunden), nicht der
            # Volltext-Lauf (Minuten) mit allgemeiner Zusammenfassung.
            try:
                _dok = None
                if not assistent.bezieht_sich_auf_vorheriges(frage):
                    _namen = (titel_im_bereich(self.path, self.headers)
                              or nur_erlaubte(BESTAND.titel(), self.headers) or [])
                    _dok, _ = assistent.dokument_gemeint(frage, _namen)
                    if _dok:
                        GESPRAECHE.dokument_merken(gespraech, _dok)
                else:
                    _dok = GESPRAECHE.letztes_dokument(gespraech)
                if _dok and self._faden_antwort(frage, _dok):
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "zusammenfassung":
            try:
                if self._zusammenfassung(frage):
                    GESPRAECHE.merken(gespraech, frage, "zusammenfassung", [])
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # ---- Folgefragen bekommen ihren Gegenstand zurueck --------------
        if art == "folgefrage" and gegenstand:
            try:
                gesucht = assistent.anreichern(frage, gegenstand)
                if gesucht != frage:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = gesucht
                    gesucht_text = gesucht
                    koerper = json.dumps(d, ensure_ascii=False).encode()
                    print("[Assistent] gesucht wird: %r" % gesucht[:110],
                          file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # ---- Verfahrensfragen: Fachbegriffe nach vorn -------------------
        # "wie vergleicht man X mit Y" sucht auch nach Text ueber das
        # Vergleichen - und Methodik-Fliesstext verdraengt die Tabelle, in
        # der die Zahlen stehen. Belegt: dieselbe Information
        # wurde bei anderer Formulierung sofort gefunden.
        if art == "negativfrage":
            # KI4KI-NEGATIV-SUCHE: Positive Form plus Optionstexte.
            # "Was ist keine Aufgabe des Extruders" findet nichts -
            # "keine Aufgabe" steht in keinem Dokument. Gesucht wird
            # nach den Aufgaben und nach jeder Option einzeln.
            try:
                _neg = assistent.negativ_suchtext(frage)
                if _neg:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = _neg
                    gesucht_text = _neg
                    koerper = json.dumps(
                        d, ensure_ascii=False).encode()
                    print("[Assistent] Negativfrage, Suche umgedreht: %r"
                          % _neg[:90], file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "verfahren":
            try:
                kern = assistent.such_verdichten(frage)
                if kern:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = "%s — %s" % (kern, frage)
                    gesucht_text = d["message"]
                    koerper = json.dumps(d, ensure_ascii=False).encode()
                    print("[Assistent] Fachbegriffe vorangestellt: %r"
                          % kern[:90], file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # B: Einfache Definitionsfrage? -> kleines Modell antwortet grounded
        #    aus den Fundstellen. Fail-safe: bei Misserfolg normaler Weg.
        try:
            if self._e2b_antwort(frage):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # ⭐ WOERTLICHE FUNDSTELLEN BEILEGEN
        #
        # Die Aehnlichkeitssuche findet seltene Fachbegriffe nicht: Gemessen
        # enthielt bei "Was ist Mastizieren?" KEINE der 100
        # gelieferten Textstellen das Wort - es steht aber in vier Arbeiten,
        # eine davon mit eigener Ueberschrift. Alle 100 Bewertungen lagen in
        # einem Band von 0,078; die Suche unterscheidet dort nicht.
        #
        # Deshalb hier: Fachwoerter aus der Frage ziehen, im Wortverzeichnis
        # nachschlagen, welche Arbeiten sie enthalten, und die woertlichen
        # Stellen beilegen. Ueber das Verzeichnis dauert das rund eine
        # Sekunde; ohne es waeren es zweieinhalb Minuten.
        #
        # ⚠ Nur bei SELTENEN Woertern. Ein Wort aus 68 Arbeiten
        #   unterscheidet nichts - dort loest die Suche nichts aus.
        try:
            _d = json.loads(koerper or b"{}") or {}
            # A3: nur in erlaubten Arbeiten woertlich suchen. Kein
            # ermittelbarer Zugang -> keine woertliche Suche (nichts beilegen).
            _pruef = erlaubt_pruefer(self.headers)
            _zusatz = "" if _pruef is None else wortsuche.zusatz_zur_frage(
                BESTAND, _d.get("message") or frage, erlaubt=_pruef,
                melden=lambda m: print("[Wortsuche] %s" % m,
                                       file=sys.stderr, flush=True))
            if _zusatz:
                _d["message"] = "%s\n\n%s" % (_d.get("message") or frage,
                                                 _zusatz)
                koerper = json.dumps(_d, ensure_ascii=False).encode()
        except Exception:
            traceback.print_exc(file=sys.stderr)

        req = urllib.request.Request(ZIEL + self.path, data=koerper,
                                     method="POST")
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding"):
                req.add_header(k, v)

        text, quellen, uuid, letzte = [], [], None, None
        stand = "pruefung-%d" % id(self)
        gestartet = False
        # KI4KI-MITLESEN: Wann wurde der Zwischenstand zuletzt gesendet und
        # wie viel stand dann darin? Gedrosselt, damit aus einer langen
        # Antwort nicht hunderte Statusmeldungen werden.
        zuletzt_gezeigt, zeichen_gezeigt = 0.0, 0
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                self._strom_beginnen()
                gestartet = True
                anzahl = dokumente_im_bereich(self.path, self.headers)
                if anzahl is None:
                    anzahl = len(BESTAND.titel())
                self._stand(stand, "Durchsuche %d %s …"
                            % (anzahl, "Dokument" if anzahl == 1
                               else "Dokumente"))

                puffer = b""
                while True:
                    stueck = r.read(4096)
                    if not stueck:
                        break
                    puffer += stueck
                    while b"\n\n" in puffer:
                        zeile, puffer = puffer.split(b"\n\n", 1)
                        zeile = zeile.strip()
                        if not zeile.startswith(b"data:"):
                            continue
                        try:
                            d = json.loads(zeile[5:].strip())
                        except Exception:
                            continue
                        letzte = d
                        uuid = d.get("uuid") or uuid
                        if d.get("textResponse"):
                            text.append(d["textResponse"])
                            # KI4KI-MITLESEN: Den entstehenden Text im
                            # Zwischenstand zeigen, damit der Fragende sieht,
                            # WAS geschrieben wird - statt 60 Sekunden lang
                            # nur "Durchsuche 1249 Dokumente".
                            #
                            # Bewusst im Status und nicht als Nachricht: Die
                            # Oberflaeche haengt Nachrichtenstuecke
                            # aneinander, und die gepruefte Fassung muss am
                            # Ende die ganze Antwort sein - mit berichtigten
                            # Zitaten und klickbaren Fundstellen.
                            jetzt = time.time()
                            gesamt = sum(len(x) for x in text)
                            if (gesamt >= 60
                                    and gesamt - zeichen_gezeigt >= 40
                                    and jetzt - zuletzt_gezeigt >= 0.4):
                                try:
                                    self._stand(stand, _mitlesen(
                                        "".join(text)))
                                    zuletzt_gezeigt = jetzt
                                    zeichen_gezeigt = gesamt
                                except Exception:
                                    pass    # ein Zwischenstand ist kein Grund
                                            # abzubrechen
                        if d.get("sources") and not quellen:
                            quellen = d["sources"]
                            # Vier Ausschnitte koennen aus zwei Arbeiten sein
                            werke = len({(q.get("title") or "").rsplit(".", 1)[0]
                                         for q in quellen if q.get("title")})
                            self._stand(stand,
                                        "%d Textstellen aus %d %s — das "
                                        "Sprachmodell formuliert die Antwort …"
                                        % (len(quellen), werke,
                                           "Arbeit" if werke == 1 else "Arbeiten"))
                        elif d.get("sources"):
                            quellen = d["sources"]
        except urllib.error.HTTPError as e:
            # Fehler von AnythingLLM unveraendert durchreichen - eine
            # abgelaufene Sitzung muss als 401 ankommen, nicht als
            # Chat-Nachricht "die Anlage antwortet nicht".
            daten = e.read()
            print("[Chat] AnythingLLM meldet HTTP %d" % e.code,
                  file=sys.stderr, flush=True)
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "connection",
                                     "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)
            return
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self._sende_strom([{"uuid": _neue_marke("fehler"), "type": "textResponseChunk",
                                "textResponse": "Die Anlage antwortet nicht: %s"
                                                % str(e)[:200],
                                "sources": [], "close": True, "error": False}])
            return

        roh = "".join(text)
        print("[Chat] Rohantwort %d Zeichen, %d Quellen"
              % (len(roh), len(quellen)), file=sys.stderr, flush=True)
        # KI4KI-ALLROUNDER: 0 Quellen = die Dokumente haben nichts. Statt einer
        # Absage antwortet das Modell aus Allgemeinwissen (unten klar markiert).
        _allrounder = False
        if ALLROUNDER and not quellen and (roh or "").strip():
            try:
                _allg = self._modell_fragen(frage, zeitgrenze=300)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                _allg = ""
            if _allg:
                roh, art, _allrounder = _allg, "allgemein", True
                print("[Allrounder] Allgemeinwissen statt Absage: %r"
                      % (frage or "")[:40], file=sys.stderr, flush=True)
        if gestartet and not _allrounder:
            self._stand(stand, "Schlage jede Fundstelle im Original-PDF nach "
                        "und prüfe die Zitate …")

        namen = []
        for q in quellen:
            t = q.get("title") or q.get("docSource") or ""
            if t and t not in namen:
                namen.append(t)
        _quellstaemme = {(t[:-3] if t.endswith(".md") else t) for t in namen}

        try:
            with PRUEFSPERRE:
                BESTAND.aktualisiere()
                geprueft, pruefungen = veredeln.veredele(roh, namen, BESTAND, belege_unten=True)
            geprueft = _themenfremde_nennungen_tilgen(geprueft)
            geprueft = mit_verweisen(geprueft, pruefungen, _quellstaemme)
            geprueft = marken_verlinken(geprueft, pruefungen)
            # Was nur genannt und nicht belegt ist, wird kursiv zum Original
            # verlinkt - erreichbar, aber sichtbar anders als ein Beleg.
            schnitt = geprueft.find("**Belege**")
            kopf = geprueft[:schnitt] if schnitt > 0 else geprueft
            rest = geprueft[schnitt:] if schnitt > 0 else ""
            kopf, wieviele = nennungen_verlinken(kopf, _quellstaemme)
            geprueft = kopf + rest
            if wieviele:
                geprueft += "\n\n" + nennungshinweis(wieviele)
            _ANFRAGE.frage, _ANFRAGE.namen = frage, list(namen)
            geprueft += "\n\n" + bilanzzeile(pruefungen, roh)
            geprueft = ohne_bildleugnung(geprueft, "/abbildung?dok=" in geprueft)
            # Live-Modellhinweis OHNE Zahlen (AnythingLLMs graue Metrik
            #   liefert Zeit/Token erst beim Neuladen; hier nur der Name,
            #   damit im Direkt-Output steht, WER geantwortet hat).
            geprueft += _modell_zeile(MODELL_NAME, time.time() - begonnen)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            geprueft = roh      # im Zweifel die Rohantwort, nie gar nichts

        # Streuen die Fundstellen ueber viele Werke, ohne dass eines
        # heraussticht, hat die Suche das Thema nicht getroffen. Dann ist
        # eine Rueckfrage ehrlicher als eine Antwort, die Eindeutigkeit
        # vortaeuscht.
        try:
            # Bei einem Vergleich sagt die Deckungswarnung weiter unten
            # genauer, was fehlt. Zwei Warnungen uebereinander lesen sich
            # wie ein Defekt.
            if art != "vergleich":
                hinweis = assistent.mehrdeutig(quellen)
                if hinweis:
                    geprueft += "\n\n" + hinweis
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # Bei einem Vergleich nachsehen, ob wirklich BEIDE Seiten gedeckt
        # sind. Eine Antwort, die nur die eine Haelfte belegt, sich aber
        # wie ein vollstaendiger Vergleich liest, ist der gefaehrlichste
        # Fehler, den die Anlage machen kann.
        try:
            if art == "vergleich":
                seiten = assistent.vergleichsteile(frage)
                luecke = assistent.vergleich_gedeckt(seiten, quellen, roh)
                if luecke:
                    geprueft += "\n\n" + luecke
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # KI4KI-NACHTRAG-CHAT: Buchstabe, Negativschluss, Fundstellen.
        try:
            for _n in nachtraege(
                    art, frage, roh, quellen,
                    modell=lambda a: self._modell_fragen(a, 120),
                    pruefungen=pruefungen, geprueft=geprueft):
                geprueft += "\n\n" + _n
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # ⭐ KONFIDENZ KALIBRIEREN: "Konfidenz: Hoch" ohne ein einziges
        #   woertlich geprueftes Zitat ist der Vertrauens-Killer "plausibel,
        #   aber falsch" (GESPRAECH-ANFORDERUNGEN §3). Dann hoechstens Mittel.
        try:
            if HINWEIS_OHNE.strip() in geprueft and re.search(
                    r"\*?\*?Konfidenz:?\*?\*?\s*\*?\*?Hoch", geprueft, re.I):
                geprueft = re.sub(r"(\*?\*?Konfidenz:?\*?\*?\s*)\*?\*?Hoch\*?\*?",
                                  r"\1**Mittel** (kein wörtliches Zitat geprüft)",
                                  geprueft, count=1, flags=re.I)
        except Exception:
            pass

        # Fuer die naechste Folgefrage festhalten, worum es ging.
        try:
            if gespraech:
                GESPRAECHE.merken(gespraech, frage, art, quellen)
        except Exception:
            traceback.print_exc(file=sys.stderr)

        try:
            quellen = quellen_veredeln(quellen)
        except Exception:
            traceback.print_exc(file=sys.stderr)
        # KI4KI-ALLROUNDER: die geprueften Zusaetze (Belegblock, Bilanz)
        # passen nicht zu einer Allgemeinwissen-Antwort - klar markieren.
        if _allrounder:
            geprueft = roh + _allgemein_zeile(
                MODELL_NAME, time.time() - begonnen)
        print("[Chat] geprueft, sende %d Zeichen" % len(geprueft),
              file=sys.stderr, flush=True)
        # Nachtragen im Hintergrund: der Browser soll nicht darauf warten.
        gedaechtnis_merken(roh, geprueft, quellen)
        # Festgehalten wird die GEPRUEFTE Fassung. AnythingLLM speichert an
        # dieser Stelle die rohe Modellantwort - ohne Belegblock, ohne
        # Fundstellen, ohne die Berichtigungen der Pruefung. An
        # einer echten Antwort gemessen: 2.196 gegen 8.164 Zeichen.
        self._festhalten(art, frage, geprueft, gesucht=gesucht_text,
                         quellen=quellen, pruefungen=pruefungen, seit=begonnen)
        if gestartet:
            self._stand_weg(stand)          # Meldung wieder wegraeumen
            self._strom_stueck({"uuid": uuid or _neue_marke("geprueft"), "type": "textResponseChunk",
                                "textResponse": geprueft, "sources": quellen,
                                "close": False, "error": False})
            self._strom_stueck({"uuid": uuid or _neue_marke("geprueft"), "type": "textResponseChunk",
                                "textResponse": "", "sources": quellen,
                                "close": True, "error": False})
            self._strom_schliessen()
        else:
            self._sende_strom([
                {"uuid": uuid or _neue_marke("geprueft"), "type": "textResponseChunk",
                 "textResponse": geprueft, "sources": quellen,
                 "close": False, "error": False},
                {"uuid": uuid or _neue_marke("geprueft"), "type": "textResponseChunk",
                 "textResponse": "", "sources": quellen,
                 "close": True, "error": False},
            ])

    def _kennzahlen_seite(self, pfad, felder):
        """K2: /rueckmeldungen - alle Daumen und 'falsche Quelle'-Meldungen.
        K5: /kpi - die eine Seite Auswertung (Leitfaden S. 101, 105, 127).
        Beide nur mit Einsichtsrecht (KI4KI_PROTOKOLL_EINSICHT)."""
        if not darf_sehen(self.headers):
            self._fehler(401, "Nicht angemeldet. Bitte zuerst in der Oberflaeche anmelden.")
            return
        konto = pruefprotokoll.pseudonym(konto_aus_anfrage(self.headers))
        if not pruefprotokoll.darf_einsehen(konto):
            print("[Einsicht] %s abgewiesen: Konto %s nicht in KI4KI_PROTOKOLL_EINSICHT" % (pfad, konto),
                  file=sys.stderr, flush=True)
            self._fehler(404, "Nicht gefunden.")
            return
        seit = (felder.get("seit") or [None])[0]
        bis = (felder.get("bis") or [None])[0]
        if pfad == "/selbstcheck":
            # Der letzte Selbst-Check-Bericht (docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py)
            ordner = os.path.join(os.path.dirname(os.environ.get("KI4KI_PROTOKOLL") or "/daten/pruefung/protokoll"), "selbstcheck")
            datei = os.path.join(ordner, "ergebnis.json" if (felder.get("format") or [""])[0] == "json" else "bericht.html")
            try:
                with open(datei, "rb") as fh:
                    roh = fh.read()
            except OSError:
                self._sende_html("<p>Noch kein Selbst-Check gelaufen. Auf dem Server: "
                                 "<code>docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py</code></p>")
                return
            if datei.endswith(".json"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)
            return
        if pfad == "/rueckmeldungen":
            eintraege = [e for e in pruefprotokoll.alle_eintraege(seit, bis) if e.get("art") == "rueckmeldung"]
            if (felder.get("format") or [""])[0] == "json":
                self._json({"rueckmeldungen": eintraege})
                return
            zeilen = []
            for e in reversed(eintraege):
                _fund = ", ".join(("%s S.%s" % (f.get("dok"), f.get("seiten"))) if f.get("seiten") else str(f.get("dok"))
                                  for f in (e.get("fundstellen") or [])[:4])
                _faden = str(e.get("faden") or "")
                _link = ("<a href='/workspace/%s/t/%s'>Faden öffnen</a>" % (html.escape(str(e.get("bereich") or "")), html.escape(_faden))) \
                    if _faden and _faden != "-" else ""
                zeilen.append("<tr><td>%s</td><td>%s<br><span style='color:#666'>%s</span></td><td><b>%s</b></td><td>%s</td>"
                              "<td style='color:#444'>%s</td><td>%s</td><td>%s<br>%s</td></tr>" % (
                    html.escape(str(e.get("ts", ""))[:16].replace("T", " ")), html.escape(str(e.get("bereich") or "")),
                    html.escape(str(e.get("regel") or "")),
                    html.escape(str(e.get("bewertung") or "")), html.escape(str(e.get("frage_original") or "")[:200]),
                    html.escape(str(e.get("antwort") or "")[:400]),
                    html.escape(str(e.get("text") or "")[:300]),
                    html.escape(_fund), _link))
            seite = ("<h1>Rückmeldungen</h1><p>%d Einträge. <a href='/kpi'>Kennzahlen</a> · <a href='/protokoll'>Protokoll</a></p>"
                     "<table border=1 cellpadding=6 style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>"
                     "<tr><th>Zeit</th><th>Bereich · Weg</th><th>Bewertung</th><th>Frage</th><th>Antwort (Auszug)</th><th>Hinweis der Person</th><th>Fundstellen · Faden</th></tr>%s</table>"
                     % (len(eintraege), "".join(zeilen) or "<tr><td colspan=6>noch keine</td></tr>"))
            self._sende_html(seite)
            return
        z = pruefprotokoll.kennzahlen(seit, bis)
        if (felder.get("format") or [""])[0] == "json":
            self._json({"kennzahlen": z})
            return

        def zeile(k, v, hinweis="", roh=False):
            return "<tr><td>%s</td><td><b>%s</b></td><td style='color:#666'>%s</td></tr>" % (
                html.escape(k), html.escape(str(v)), hinweis if roh else html.escape(hinweis))
        if not z.get("vorgaenge"):
            self._sende_html("<h1>Kennzahlen</h1><p>Noch keine Vorgänge im Zeitraum.</p>")
            return
        ms = z.get("zeit_bis_erste_quelle_median_ms")
        r = z.get("rueckmeldungen") or {}
        zeilen = "".join([
            zeile("Vorgänge (Fragen)", z["vorgaenge"], "Zeitraum: %s – %s" % (seit or "Anfang", bis or "heute")),
            zeile("Gesprächsfäden", z.get("faeden", "-")),
            zeile("Fragende (Kennungen, pseudonym)", z.get("fragende", "-")),
            zeile("Anteil belegter Antworten", "%s %%" % z["belegt_anteil"], "Antworten mit mindestens einem im Original nachgeschlagenen Zitat oder Beleg (Leitfaden-KPI)"),
            zeile("Trefferquote", "%s %%" % z.get("trefferquote", "-"), "Anteil der Fragen mit einer Antwort aus dem Bestand"),
            zeile("Eskalationsquote", "%s %% (%d)" % (z.get("eskalationsquote", "-"), z.get("eskaliert", 0)), "ehrlich „nicht gefunden“ statt Schein-Sicherheit"),
            zeile("Zeit bis zur ersten verwertbaren Quelle (Median)", ("%.0f s" % (ms / 1000.0)) if ms else "-", "je Faden die erste belegte Antwort"),
            zeile("Antwortzeit Median / langsamste", "%s s / %s s" % (
                round((z.get("dauer_median_ms") or 0) / 1000.0), round((z.get("dauer_langsamste_ms") or 0) / 1000.0))),
            zeile("Störfall-Anfragen (mit Kontext)", z.get("stoerfaelle", 0), "Anlage / Fehlercode / Symptom erkannt"),
            zeile("Rückmeldungen", "%d hilfreich · %d nicht hilfreich / falsche Quelle" % (r.get("hilfreich", 0), r.get("nicht_hilfreich", 0)),
                  "<a href='/rueckmeldungen'>Liste</a> — Daumen in der Oberfläche oder „Feedback: …“ im Chat", roh=True),
            zeile("Nutzung je Tag (Kennungen)", ", ".join("%s: %d" % (t, n) for t, n in list((z.get("nutzung_je_tag") or {}).items())[-14:]) or "-"),
            zeile("Wege", ", ".join("%s: %d" % kv for kv in (z.get("regeln") or {}).items())),
            zeile("Meistgenutzte Quellen", ", ".join("%s (%d)" % kv for kv in (z.get("meistgenutzte_quellen") or [])[:8])),
        ])
        seite = ("<h1>KI4KI — Kennzahlen</h1>"
                 "<p style='font-family:sans-serif;font-size:14px;max-width:900px'><b>Lesehilfe:</b> Trefferquote = Frage bekam eine Antwort aus dem "
                 "Bestand · Eskalation = ehrliches „nicht gefunden“ · belegt = Zitat/Beleg im Original nachgeschlagen · "
                 "Wege = welcher Antwortweg (gespraech = Gesprächsmodus, pruefung = Prüfungskatalog, bestand = Index-Tabelle).</p>"
                 "<p>Ohne Personenbezug (Kennungen pseudonym). "
                 "<a href='/rueckmeldungen'>Rückmeldungen</a> · <a href='/protokoll'>Protokoll (JSON)</a> · "
                 "<a href='/kpi?format=json'>JSON</a> · Zeitraum: <code>/kpi?seit=2026-08-01&bis=2026-08-31</code></p>"
                 "<table border=1 cellpadding=6 style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>%s</table>" % zeilen)
        self._sende_html(seite)

    def _protokoll(self, pfad, felder):
        """Die Protokoll-Ansicht: Kennzahlen, Ausfuhr, eigene Auskunft.

        Drei Wege mit drei verschiedenen Rechten:
          /protokoll          Kennzahlen ohne Personenbezug - Einsichtsrecht
          /protokoll/ausfuhr  Vollstaendiger Auszug - Einsichtsrecht
          /protokoll/eigenes  Nur die eigenen Vorgaenge - jeder Angemeldete

        Das Einsichtsrecht haengt bewusst NICHT an der Administratorrolle:
        Wer die Anlage betreibt, muss nicht sehen koennen, wer was gefragt
        hat.
        """
        # ⛔ A1-Fix (live bestaetigt): Ein Authorization-Kopf stiftet
        #   nur dann Identitaet, wenn AnythingLLM ihn bestaetigt. darf_sehen
        #   ist ein ODER - ein gueltiger ki4ki_zugang-Cookie sagt
        #   "angemeldet", aber NICHT wer, und konto_aus liest genau diesen
        #   ungeprueften Kopf (base64, keine Signatur). Ohne diese Zeile
        #   uebernimmt ein selbstgebauter Kopf eine fremde Identitaet und
        #   liest fremde Vorgaenge. Cookie-only (kein Kopf) laeuft
        #   unveraendert und faellt auf die an den Cookie gebundene Kennung.
        if (self.headers.get("Authorization") or "").strip() and \
                not angemeldet(self.headers):
            self._fehler(401, "Nicht angemeldet. Bitte in der Oberflaeche "
                              "anmelden.")
            return
        if not darf_sehen(self.headers):
            self._fehler(401, "Nicht angemeldet. Bitte zuerst in der "
                              "Oberflaeche anmelden.")
            return
        konto = pruefprotokoll.pseudonym(
            pruefprotokoll.konto_aus(self.headers))

        # Die eigene Auskunft braucht kein Einsichtsrecht - sie liefert
        # ausschliesslich die Vorgaenge des Fragenden selbst.
        if pfad == "/protokoll/eigenes":
            self._json({"kennung": konto,
                        "vorgaenge": pruefprotokoll.eigene_eintraege(konto)})
            return

        if not pruefprotokoll.darf_einsehen(konto):
            # Wortgleich mit "nicht vorhanden": Wer kein Einsichtsrecht
            # hat, soll nicht einmal erfahren, dass es die Ansicht gibt.
            self._fehler(404, "Nicht gefunden.")
            return

        seit = (felder.get("seit") or [None])[0]
        bis = (felder.get("bis") or [None])[0]

        if pfad == "/protokoll/ausfuhr":
            eintraege = pruefprotokoll.alle_eintraege(seit, bis)
            if (felder.get("format") or [""])[0] == "csv":
                zeilen = ["nr;zeitpunkt;kennung;bereich;weg;regel;verdikt;"
                          "frage;gesuchte_fassung;fundstellen;dauer_ms"]
                for e in eintraege:
                    if e.get("art") != "frage":
                        continue
                    zeilen.append(";".join(_csv_feld(w) for w in (
                        e.get("seq"), e.get("ts"), e.get("konto"),
                        e.get("bereich"), e.get("weg"), e.get("regel"),
                        e.get("verdikt"), e.get("frage_original"),
                        e.get("frage_gesucht"),
                        " | ".join("%s S.%s" % (f.get("dok"), f.get("seiten"))
                                   for f in (e.get("fundstellen") or [])),
                        e.get("dauer_ms"))))
                daten = "\n".join(zeilen).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition",
                                 'attachment; filename="protokoll.csv"')
                self.send_header("Content-Length", str(len(daten)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(daten)
                return
            self._json({"eintraege": eintraege})
            return

        # Uebersicht: Kennzahlen plus der Nachweis, dass die Kette haelt.
        zahlen = pruefprotokoll.kennzahlen(seit, bis)
        ketten = []
        try:
            for d in sorted(os.listdir(pruefprotokoll.ORDNER)):
                if not d.endswith(".jsonl"):
                    continue
                heil, n, zeile = pruefprotokoll.kette_pruefen(
                    os.path.join(pruefprotokoll.ORDNER, d))
                ketten.append({"tag": d[:10], "eintraege": n,
                               "lueckenlos": heil,
                               "bruch_in_zeile": zeile})
        except Exception:
            traceback.print_exc(file=sys.stderr)
        self._json({"kennzahlen": zahlen, "ketten": ketten,
                    "einstellungen": pruefprotokoll.EINSTELLUNG})

    def _festhalten(self, art, frage, antwort, gesucht=None, quellen=None,
                    pruefungen=None, seit=None):
        """Einen Vorgang ins eigene Protokoll schreiben.

        Hier und nicht in AnythingLLMs Verlauf, weil dort weder die
        gepruefte Fassung noch die selbst beantworteten Faelle ankommen -
        gemessen. Wirft nie: Ein Protokollfehler darf keine
        Antwort verhindern.
        """
        try:
            GESPRAECHE.antwort_merken(
                GESPRAECHE.kennung(self.path, self.headers), antwort)
        except Exception:
            pass
        try:
            m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)"
                         r"(?:/thread/([^/]+))?", self.path or "")
            fund = []
            try:
                if art in ("bestand", "zusammenfassung", "rueckfrage",
                           "wahl-alle", "e2b", "anhang", "meta", "allgemein",
                           "bild", "faden", "fakten", "beschwerde", "zweifel",
                           "anlage", "vergleich", "abkuerzung", "export",
                           "gespraech", "pruefung", "rolle"):
                    import time as _t
                    _ws = (m.group(1) if m else "") or ""
                    _th = (m.group(2) if (m and m.group(2)) else "default")
                    _schl = _ws + "|" + _th
                    _erste = not (_nachtrag_alle().get(_schl))
                    _nachtrag_merken(_schl, frage or "", antwort or "",
                                     quellen or [], int(_t.time()))
                    if _erste and m and m.group(2):
                        self._thread_benennen(_ws, m.group(2), frage or "")
            except Exception:
                pass
            for p in (pruefungen or []):
                if not p.get("doku"):
                    continue
                fund.append({"dok": p["doku"], "seiten": p.get("seiten"),
                             "urteil": p.get("urteil")})
            if not fund:
                for q in (quellen or [])[:9]:
                    if q.get("title"):
                        fund.append({"dok": q["title"]})
            # Die Urteile heissen woertlich, geglaettet, teilweise,
            # ungedeckt, zu_kurz (veredeln.bilanz). Ein erfundenes
            # "belegt" abzufragen liefert immer False - dann steht im
            # Protokoll jede belegte Antwort als unbelegt, und das ist
            # schlimmer als gar keine Angabe. Genau so ist es passiert.
            zaehlung = {}
            for p in (pruefungen or []):
                u = p.get("urteil")
                if u:
                    zaehlung[u] = zaehlung.get(u, 0) + 1
            if zaehlung.get("woertlich") or zaehlung.get("geglaettet"):
                urteil = "belegt"
            elif zaehlung.get("teilweise"):
                urteil = "teilweise"
            elif zaehlung:
                urteil = "unbelegt"
            elif quellen:
                urteil = "ohne_zitate"
            else:
                urteil = "eigen"
            pruefprotokoll.schreibe(
                art="frage",
                konto=pruefprotokoll.pseudonym(
                    pruefprotokoll.konto_aus(self.headers)),
                bereich=m.group(1) if m else None,
                faden=(m.group(2) if m else None) or "-",
                weg="browser" if "/v1/" not in (self.path or "") else "dienst",
                regel=art,
                absicht=getattr(self, "_absicht_protokoll", None),
                kontext=(lambda k: {a: b for a, b in k.items() if b} or None)(stoerfall.erkennen(frage or "")),
                frage_original=frage,
                # Beide Fassungen, immer: Ohne die umgeschriebene Suche
                # laesst sich spaeter nicht nachvollziehen, warum eine
                # Frage gefunden hat oder eben nicht.
                frage_gesucht=gesucht if gesucht and gesucht != frage else None,
                antwort=antwort,
                verdikt=urteil,
                # Die Zaehlung je Urteil ist die Grundlage fuer die
                # Wirksamkeitsmessung (K5) - ohne sie liesse sich spaeter
                # nur sagen, DASS geprueft wurde, nicht mit welchem Ergebnis.
                bilanz=zaehlung or None,
                fundstellen=fund or None,
                dauer_ms=int((time.time() - seit) * 1000) if seit else None)
        except Exception:
            traceback.print_exc(file=sys.stderr)

    def _json_antwort(self, text, art, frage=None):
        """Eine fertige Antwort ausliefern, ohne AnythingLLM zu fragen."""
        text = (text or "") + _katalog_zeile() + _netz_hinweis_zeile()
        # Genau diese Faelle fehlen in AnythingLLMs Verlauf vollstaendig -
        # Bestandsauskunft, Zusammenfassung, Rueckfrage. Das hier ist der
        # JSON-Weg; der Browser-Weg haengt in _bestandsauskunft und
        # _zusammenfassung, weil er ueber den Datenstrom antwortet.
        self._festhalten(art, frage, text)
        daten = json.dumps({
            "id": art,
            "type": "textResponse",
            "textResponse": text,
            "sources": [],
            "close": True,
            "error": None,
        }, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)

    def _chat_json(self):
        """Der Weg fuer Maschinen: eine JSON-Antwort, geprueft zurueck."""
        koerper = self._koerper()
        try:
            _leib = json.loads(koerper or b"{}") or {}
            frage_roh = _leib.get("message") or ""
            # sessionId (AnythingLLM-API) = eigener Gespraechsfaden mit Gedaechtnis,
            # wie ein Thread im Browser. Ohne sessionId teilen sich alle Aufrufe mit
            # demselben Schluessel EIN Gedaechtnis (gemessen 27.08.: der Selbst-Check
            # schleppte das Faden-Dokument der vorigen Frage mit).
            _sitzung = str(_leib.get("sessionId") or "").strip()
            if _sitzung and self.headers.get("X-KI4KI-Faden") is None:
                self.headers["X-KI4KI-Faden"] = re.sub(r"[^A-Za-z0-9_.:-]", "_", _sitzung)[:80]
        except Exception:
            frage_roh = ""

        # ⭐ Erst die Wege, die auch der Browser nimmt (Katalog, Bestand, Stufe 2).
        try:
            if frage_roh and self._json_ueber_gespraech(frage_roh):
                return
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # Dieselbe Einordnung wie im Browser-Weg - damit n8n und das
        # Partner-Paket nicht auf halbem Stand bleiben.
        gesucht_text, begonnen = None, time.time()
        gespraech, art, gegenstand = None, "normal", None
        try:
            gespraech = GESPRAECHE.kennung(self.path, self.headers)
            gegenstand = GESPRAECHE.letzter_gegenstand(gespraech)
            art = assistent.einordnen(frage_roh, hat_verlauf=bool(gegenstand))
            art = _wahl_beantwortet(gespraech, frage_roh, art)
            if art != "normal":
                print("[Assistent/json] %s: %r" % (art, frage_roh[:70]),
                      file=sys.stderr, flush=True)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            art = "normal"

        # KI4KI-TOR-JSON2: Der Riegel fuer den JSON-Weg (n8n und eigene
        # Skripte). Der erste Einbau landete im Browser-Weg, weil der
        # Textanker in beiden Methoden vorkommt - dieser hier wurde ueber
        # den Syntaxbaum in _chat_json gesetzt.
        if art in ("bestand", "zusammenfassung") and not \
                bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return

        if art == "bestand":
            try:
                titel = titel_im_bereich(self.path, self.headers)
                bereich = bool(titel)
                if not titel:
                    BESTAND.aktualisiere()
                    # A2: nicht der ganze Bestand, nur was erlaubt ist
                    titel = nur_erlaubte(BESTAND.titel(), self.headers)
                text = assistent.bestandsauskunft(frage_roh, titel,
                                                  bereich=bereich or None)
                if text:
                    GESPRAECHE.merken(gespraech, frage_roh, "bestand", [])
                    self._json_antwort(text, "bestand", frage_roh)
                    return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "zusammenfassung":
            try:
                BESTAND.aktualisiere()
                # A2: der Rueckfall siebt nach Recht, sonst fasst die
                # Anlage ein fremdes Dokument zusammen.
                auswahl = (titel_im_bereich(self.path, self.headers)
                           or nur_erlaubte(BESTAND.titel(), self.headers))
                # Steht eine Rueckfrage offen, wird nur noch unter den
                # aufgezaehlten Titeln gewaehlt - sonst streut dieselbe
                # Frage erneut ueber den ganzen Bestand und die Anlage
                # fragt zum zweiten Mal dasselbe.
                vorwahl = GESPRAECHE.offene_wahl(gespraech)
                if vorwahl and assistent.ist_alle_wahl(frage_roh):
                    _abriss = self._alle_kurzabriss(vorwahl)
                    self._json_antwort(
                        _abriss or assistent.alle_nicht_moeglich(vorwahl),
                        "wahl-alle", frage_roh)
                    return
                gewaehlt, kandidaten = assistent.dokument_gemeint(
                    frage_roh, vorwahl or auswahl)
                if not gewaehlt and len(kandidaten) > 1:
                    liste = "\n".join("- %s" % assistent._titel_saubern(k)
                                       for k in kandidaten[:10])
                    GESPRAECHE.wahl_merken(gespraech, kandidaten[:10])
                    GESPRAECHE.merken(gespraech, frage_roh,
                                      "zusammenfassung", [])
                    self._json_antwort(
                        "Dazu passen mehrere Dokumente. Welches meinst "
                        "du?\n\n" + liste, "rueckfrage", frage_roh)
                    return
                if gewaehlt:
                    GESPRAECHE.wahl_vergessen(gespraech)
                if not gewaehlt and not kandidaten:
                    _faden_dok = GESPRAECHE.letztes_dokument(gespraech)
                    if _faden_dok and _faden_dok in auswahl and \
                            assistent.bezieht_sich_auf_vorheriges(frage_roh):
                        gewaehlt = _faden_dok
                if gewaehlt:
                    schluessel = bestandsschluessel(gewaehlt)
                    dok = BESTAND.hol(schluessel) if schluessel else None
                    if dok and (dok.text or "").strip():
                        text, _gelesen, _ganz = self._zusammenfassung_ganz(
                            dok, gewaehlt)
                        if text:
                            text += "\n\n---\n" + zusammenfassungs_fuss(
                                gewaehlt, _ganz, _gelesen)
                            GESPRAECHE.merken(gespraech, frage_roh,
                                              "zusammenfassung", [])
                            GESPRAECHE.dokument_merken(gespraech, gewaehlt)
                            self._json_antwort(text, "zusammenfassung", frage_roh)
                            return
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "folgefrage" and gegenstand:
            try:
                gesucht = assistent.anreichern(frage_roh, gegenstand)
                if gesucht != frage_roh:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = gesucht
                    gesucht_text = gesucht
                    koerper = json.dumps(d, ensure_ascii=False).encode()
                    print("[Assistent/json] gesucht wird: %r" % gesucht[:110],
                          file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "negativfrage":
            # KI4KI-NEGATIV-SUCHE: Positive Form plus Optionstexte.
            # "Was ist keine Aufgabe des Extruders" findet nichts -
            # "keine Aufgabe" steht in keinem Dokument. Gesucht wird
            # nach den Aufgaben und nach jeder Option einzeln.
            try:
                _neg = assistent.negativ_suchtext(frage_roh)
                if _neg:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = _neg
                    gesucht_text = _neg
                    koerper = json.dumps(
                        d, ensure_ascii=False).encode()
                    print("[Assistent/json] Negativfrage, Suche umgedreht: %r"
                          % _neg[:90], file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        if art == "verfahren":
            try:
                kern = assistent.such_verdichten(frage_roh)
                if kern:
                    d = json.loads(koerper or b"{}") or {}
                    d["message"] = "%s — %s" % (kern, frage_roh)
                    gesucht_text = d["message"]
                    koerper = json.dumps(d, ensure_ascii=False).encode()
                    print("[Assistent/json] Fachbegriffe vorangestellt: %r"
                          % kern[:90], file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)

        # ⭐ WOERTLICHE FUNDSTELLEN BEILEGEN
        #
        # Die Aehnlichkeitssuche findet seltene Fachbegriffe nicht: Gemessen
        # enthielt bei "Was ist Mastizieren?" KEINE der 100
        # gelieferten Textstellen das Wort - es steht aber in vier Arbeiten,
        # eine davon mit eigener Ueberschrift. Alle 100 Bewertungen lagen in
        # einem Band von 0,078; die Suche unterscheidet dort nicht.
        #
        # Deshalb hier: Fachwoerter aus der Frage ziehen, im Wortverzeichnis
        # nachschlagen, welche Arbeiten sie enthalten, und die woertlichen
        # Stellen beilegen. Ueber das Verzeichnis dauert das rund eine
        # Sekunde; ohne es waeren es zweieinhalb Minuten.
        #
        # ⚠ Nur bei SELTENEN Woertern. Ein Wort aus 68 Arbeiten
        #   unterscheidet nichts - dort loest die Suche nichts aus.
        try:
            _d = json.loads(koerper or b"{}") or {}
            # A3: auch im JSON-Weg nur in erlaubten Arbeiten woertlich suchen.
            _pruef = erlaubt_pruefer(self.headers)
            _zusatz = "" if _pruef is None else wortsuche.zusatz_zur_frage(
                BESTAND, _d.get("message") or frage_roh, erlaubt=_pruef,
                melden=lambda m: print("[Wortsuche/json] %s" % m,
                                       file=sys.stderr, flush=True))
            if _zusatz:
                _d["message"] = "%s\n\n%s" % (_d.get("message") or frage_roh,
                                                 _zusatz)
                koerper = json.dumps(_d, ensure_ascii=False).encode()
        except Exception:
            traceback.print_exc(file=sys.stderr)

        req = urllib.request.Request(ZIEL + self.path, data=koerper,
                                     method="POST")
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                antwort = json.load(r)
        except urllib.error.HTTPError as e:
            daten = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
            return
        except Exception as e:
            self._fehler(502, str(e))
            return

        roh = antwort.get("textResponse") or ""
        try:
            frage = (json.loads(koerper or b"{}") or {}).get("message") or ""
        except Exception:
            frage = ""
        namen = []
        for q in antwort.get("sources") or []:
            t = q.get("title") or q.get("docSource") or ""
            if t and t not in namen:
                namen.append(t)
        _quellstaemme = {(t[:-3] if t.endswith(".md") else t) for t in namen}
        try:
            with PRUEFSPERRE:
                BESTAND.aktualisiere()
                geprueft, pruefungen = veredeln.veredele(roh, namen, BESTAND, belege_unten=True)
            geprueft = _themenfremde_nennungen_tilgen(geprueft)
            _g = marken_verlinken(mit_verweisen(geprueft, pruefungen, _quellstaemme),
                                  pruefungen)
            # Wie im Browser-Weg: genannte Dokumente verifiziert verlinken.
            _schnitt = _g.find("**Belege**")
            _kopf = _g[:_schnitt] if _schnitt > 0 else _g
            _rest = _g[_schnitt:] if _schnitt > 0 else ""
            _kopf, _wieviele = nennungen_verlinken(_kopf, _quellstaemme)
            _g = _kopf + _rest
            if _wieviele:
                _g += "\n\n" + nennungshinweis(_wieviele)
            _ANFRAGE.frage, _ANFRAGE.namen = frage, list(namen)
            antwort["textResponse"] = _g + "\n\n" + bilanzzeile(pruefungen, roh)
            antwort["textResponse"] = ohne_bildleugnung(
                antwort["textResponse"], "/abbildung?dok=" in antwort["textResponse"])
            antwort["belegpruefung"] = veredeln.bilanz(pruefungen)
            antwort["fundstellen"] = [veredeln.fundstelle(p)
                                      for p in pruefungen if p.get("doku")]
            antwort["sources"] = quellen_veredeln(antwort.get("sources") or [])
            gedaechtnis_merken(roh, antwort["textResponse"],
                               antwort["sources"])
            # Der Weg fuer n8n und eigene Dienste gehoert genauso ins
            # Protokoll wie der Browser - das ist der automatisierte
            # Verkehr, nach dem bei einer Pruefung als Erstes gefragt wird.
            self._festhalten(art, frage_roh, antwort["textResponse"],
                             gesucht=gesucht_text,
                             quellen=antwort.get("sources"),
                             pruefungen=pruefungen, seit=begonnen)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            # im Zweifel die Rohantwort - nie gar nichts

        # Dieselben Hinweise wie im Browser-Weg: Rueckfrage, wenn die
        # Fundstellen streuen; Warnung, wenn ein Vergleich nur einseitig
        # gedeckt ist.
        try:
            zusatz = []
            if art != "vergleich":
                hinweis = assistent.mehrdeutig(antwort.get("sources") or [])
                if hinweis:
                    zusatz.append(hinweis)
            if art == "vergleich":
                luecke = assistent.vergleich_gedeckt(
                    assistent.vergleichsteile(frage_roh),
                    antwort.get("sources") or [], roh)
                if luecke:
                    zusatz.append(luecke)
            # KI4KI-NACHTRAG-JSON: derselbe Nachtrag wie im Browser. Beide
            # Wege muessen dasselbe antworten, sonst weichen n8n-Ergebnis
            # und Bildschirm voneinander ab - ein Fehler, der lange
            # unbemerkt bleibt.
            zusatz.extend(nachtraege(
                art, frage_roh, roh, antwort.get("sources") or [],
                modell=lambda a: self._modell_fragen(a, 120),
                pruefungen=pruefungen,
                geprueft=antwort.get("textResponse") or ""))
            if zusatz:
                antwort["textResponse"] = (
                    (antwort.get("textResponse") or "")
                    + "\n\n" + "\n\n".join(zusatz))
            if gespraech:
                GESPRAECHE.merken(gespraech, frage_roh, art,
                                  antwort.get("sources") or [])
        except Exception:
            traceback.print_exc(file=sys.stderr)
        daten = json.dumps(antwort, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)

    def _alle_kurzabriss(self, kandidaten):
        """Auf "alle": je Dokument ein kurzer eigener Abriss statt einer
        Sackgasse. KEINE Mega-Zusammenfassung aller Werke in einem Zug (das
        waere "alles und nichts"), sondern ein knapper Abriss pro Werk.
        Liefert den zusammengesetzten Text oder "" - dann faellt der Aufrufer
        auf den bisherigen Hinweistext zurueck (fail-safe)."""
        teile = []
        for k in (kandidaten or [])[:5]:
            try:
                schluessel = bestandsschluessel(k)
                dok = BESTAND.hol(schluessel) if schluessel else None
                text = (dok.text or "") if dok else ""
                if not text.strip():
                    continue
                titel = assistent._titel_saubern(k)
                auftrag = ("Fasse den Anfang dieses Fachdokuments in 2 bis 4 "
                           "Saetzen zusammen: worum geht es, was sind die "
                           "Kernpunkte. Nur der Abriss, keine Einleitung, "
                           "nichts erfinden." + chr(10) + chr(10)
                           + "TITEL: " + titel + chr(10) + chr(10)
                           + "TEXT:" + chr(10) + text[:10000])
                abriss = (self._modell_fragen(auftrag, zeitgrenze=120) or "").strip()
                if abriss:
                    teile.append("**" + titel + "**" + chr(10) + abriss)
            except Exception:
                traceback.print_exc(file=sys.stderr)
        if not teile:
            return ""
        kopf = ("Ein kurzer Abriss je Dokument (fuer eine ausfuehrliche "
                "Fassung nenne bitte eines davon):" + chr(10) + chr(10))
        return kopf + (chr(10) + chr(10)).join(teile)

    def _zusammenfassung_ganz(self, dok, titel, melden=None, auftrag=None):
        """Ein Dokument VOLLSTAENDIG zusammenfassen - notfalls in Etappen.

        Liefert (text, gelesen, gesamt). "gelesen" geht in den Fuss unter
        der Antwort und muss deshalb die wirklich gelesene Menge sein, nicht
        die erhoffte.

        mehrstufig.zusammenfassen() zerlegt den Text in Stuecke von je
        110.000 Zeichen, fasst jedes einzeln zusammen und verbindet die
        Teile. Gemessen: Die Zeit je Stueck ist nahezu gleich, ob
        18.000 oder 72.000 Zeichen darin stehen - der Aufwand steckt im
        Aufruf, nicht in der Textmenge. Deshalb wenige grosse Stuecke.

        melden() darf None sein. Im Browser haengt daran die Statuszeile:
        Wer bei einer Dissertation zehn Minuten wartet, muss sehen, dass
        etwas passiert - sonst haelt er die Anlage fuer haengengeblieben.
        """
        ganz = (dok.text or "") if dok else ""
        try:
            e = mehrstufig.zusammenfassen(ganz, titel, self._modell_fragen,
                                          melden, auftrag=auftrag)
            if e and (e.get("text") or "").strip():
                return e["text"], int(e.get("zeichen") or 0), len(ganz)
            print("mehrstufig lieferte nichts fuer %r" % (titel,),
                  file=sys.stderr)
        except Exception:
            traceback.print_exc(file=sys.stderr)

        # Rueckfallweg: lieber eine gekuerzte Zusammenfassung als gar keine.
        # Der Fuss nennt dann die 48.000 - stillschweigend auf sieben
        # Prozent zurueckzufallen waere genau der alte Fehler.
        if auftrag:
            gekuerzt = ganz[:48000]
            return (self._modell_fragen(
                mehrstufig.auftrag_direkt(gekuerzt, titel, auftrag)),
                len(gekuerzt), len(ganz))
        _auftrag, _ = assistent.zusammenfassungs_auftrag(ganz, titel)
        return self._modell_fragen(_auftrag), min(len(ganz), 48000), len(ganz)

    def _modell_fragen(self, auftrag, zeitgrenze=900, modell=None, denken=False):
        """Das Sprachmodell direkt fragen - ohne Suche, ohne AnythingLLM.

        Nur fuer Faelle, in denen der Text schon feststeht und gar nicht
        gesucht werden soll. Alles andere gehoert weiter durch die
        gewoehnliche Kette, damit Belegpruefung und Quellen erhalten
        bleiben.
        """
        daten = json.dumps({
            "model": modell or MODELL_NAME,
            "messages": [{"role": "user", "content": auftrag}],
            "stream": False,
            # Denken nur fuer die schweren Aufgaben (Vergleich, Widerspruch,
            # Kennwerte) - dort lohnt es; fuer "was steht auf S. 12" kostet
            # es nur Zeit. Die Denkspur kommt getrennt und landet nicht im Text.
            "think": bool(denken),
            "options": {"temperature": 0.2, "num_ctx": 65536},
            "keep_alive": "24h",
        }).encode()
        req = urllib.request.Request(
            MODELL_ZIEL, data=daten, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=zeitgrenze) as r:
            antwort = json.load(r)
        return ((antwort.get("message") or {}).get("content") or "").strip()

    def _zusammenfassung(self, frage, erzwinge=None):
        """Ein ganzes Dokument zusammenfassen.

        Rueckgabe True, wenn erledigt (auch bei einer Rueckfrage). Bei
        False laeuft die Frage den gewoehnlichen Weg - dann bekommt der
        Nutzer wenigstens eine Antwort aus Fundstellen.
        """
        # KI4KI-TOR: Ohne Zugang zu diesem Bereich wird nichts
        # beantwortet - auch nicht "hilfsweise" aus dem Gesamtbestand.
        # Wortgleich mit AnythingLLM, damit der Unterschied nicht verraet,
        # dass der Bereich existiert.
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True

        BESTAND.aktualisiere()
        im_bereich = titel_im_bereich(self.path, self.headers)
        # Erst im Arbeitsbereich suchen, dann im Gesamtbestand. Sonst
        # wuerde ein Dokument zusammengefasst, das der Fragende in seinem
        # Bereich gar nicht sehen darf.
        # KI4KI-KEIN-AUSWEICHEN: Der Gesamtbestand ist nur
        # erlaubt, wenn der Zugang zum Bereich bestaetigt ist.
        auswahl = im_bereich or (
            nur_erlaubte(BESTAND.titel(), self.headers)
            if bereich_sichtbar(self.path, self.headers) else [])
        # Wie im Browser-Weg: Steht eine Rueckfrage offen, wird nur noch
        # unter den aufgezaehlten Titeln gewaehlt. Der Riegel gehoert in
        # BEIDE Wege - zuvor sass der Torwaechter nur in den Methoden,
        # die allein der Browser aufruft, und der JSON-Weg blieb offen.
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        vorwahl = GESPRAECHE.offene_wahl(gespraech)
        if vorwahl and assistent.ist_alle_wahl(frage):
            _antwort_alle = (self._alle_kurzabriss(vorwahl)
                             or assistent.alle_nicht_moeglich(vorwahl))
            self._festhalten("wahl-alle", frage, _antwort_alle)
            self._sende_strom([
                {"uuid": _neue_marke("zusammenfassung"),
                 "type": "textResponseChunk",
                 "textResponse": _antwort_alle,
                 "sources": [], "close": False, "error": False},
                {"uuid": _neue_marke("zusammenfassung"),
                 "type": "textResponseChunk", "textResponse": "",
                 "sources": [], "close": True, "error": False},
            ])
            return True
        gewaehlt, kandidaten = assistent.dokument_gemeint(
            frage, vorwahl or auswahl)
        if erzwinge and erzwinge in auswahl:
            gewaehlt, kandidaten = erzwinge, [erzwinge]
        if gewaehlt:
            GESPRAECHE.wahl_vergessen(gespraech)
        # ⭐ FADEN-DOKUMENT: Nennt die Frage kein Dokument ("Schreib mir eine
        #   gesamte Zusammenfassung"), ist das gemeint, worum es in diesem
        #   Faden zuletzt ging.
        if not gewaehlt and not kandidaten:
            _faden_dok = GESPRAECHE.letztes_dokument(gespraech)
            if _faden_dok and _faden_dok in auswahl and \
                    assistent.bezieht_sich_auf_vorheriges(frage):
                gewaehlt = _faden_dok
                print("[Assistent] Faden-Dokument: %r" % _faden_dok,
                      file=sys.stderr, flush=True)

        # ⭐ KLAERFRAGE statt Schnipsel: "Fasse die Dissertation zusammen" bei
        #   zehn Dokumenten und leerem Faden lief bisher still als gewoehnliche
        #   Suche - mit "Konfidenz: Hoch" auf neun Schnipseln (25.08.). Modelle
        #   fragen von sich aus fast nie nach; hier erzwingt es der Proxy, mit
        #   Optionen (GESPRAECH-ANFORDERUNGEN §4.4).
        _klaer = False
        if not gewaehlt and not kandidaten and len(auswahl) > 1 and \
                assistent.bezieht_sich_auf_vorheriges(frage):
            kandidaten = list(auswahl)[:10]
            _klaer = True

        if not gewaehlt and len(kandidaten) > 1:
            liste = "\n".join("- %s" % assistent.dokument_zeile(k)
                               for k in kandidaten[:10])
            _kopf = ("Welches Dokument meinst du? Nenn mir Kennung oder "
                     "Verfasser — oder wähle:" if _klaer
                     else "Dazu passen mehrere Dokumente. Welches meinst du?")
            if _klaer and len(auswahl) > 10:
                _kopf += " (die ersten 10 von %d)" % len(auswahl)
            GESPRAECHE.wahl_merken(gespraech, kandidaten[:10])
            GESPRAECHE.merken(gespraech, frage, "zusammenfassung", [])
            self._festhalten("rueckfrage", frage, _kopf + " " + liste)
            self._sende_strom([
                {"uuid": _neue_marke("zusammenfassung"), "type": "textResponseChunk",
                 "textResponse": (_kopf + "\n\n" + liste),
                 "sources": [], "close": False, "error": False},
                {"uuid": _neue_marke("zusammenfassung"), "type": "textResponseChunk",
                 "textResponse": "", "sources": [],
                 "close": True, "error": False},
            ])
            return True

        if not gewaehlt:
            return False

        schluessel = bestandsschluessel(gewaehlt)
        dok = BESTAND.hol(schluessel) if schluessel else None
        if not dok or not (dok.text or "").strip():
            print("[Assistent] kein Volltext zu %r (Schluessel %r) - "
                  "gewoehnlicher Weg" % (gewaehlt, schluessel),
                  file=sys.stderr, flush=True)
            return False

        self._strom_beginnen()
        stand = "zusammenfassung-%d" % id(self)
        # Docling setzt [[SEITE]] nur ZWISCHEN den Seiten: ein einseitiges
        # Dokument hat null Marken, ein zweiseitiges eine. Die Zahl waere
        # also immer um eins zu niedrig - und bei kurzen Dokumenten sagt
        # sie ohnehin nichts ueber die Wartezeit. Deshalb erst ab drei.
        seiten = len(dok.marken) + 1 if dok.marken else 0
        # Ein DOKUMENT-AUFTRAG (Praesentation, Gliederung, Handout ...) nutzt
        # denselben Volltext-Weg - die Frage selbst ist die Aufgabe.
        _auftrag = frage if assistent.ist_dokument_auftrag(frage) else None
        self._stand(stand, "Lese *%s* vollständig%s und %s — "
                    "das dauert länger als eine gewöhnliche Frage …"
                    % (assistent._titel_saubern(gewaehlt),
                       " (%d Seiten)" % seiten if seiten >= 3 else "",
                       "bereite daraus auf, was du wünschst" if _auftrag
                       else "fasse zusammen"))
        try:
            text, _gelesen, _ganz = self._zusammenfassung_ganz(
                dok, gewaehlt, lambda m: self._stand(stand, m),
                auftrag=_auftrag)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self._stand_weg(stand)
            self._strom_stueck(
                {"uuid": _neue_marke("zusammenfassung"), "type": "textResponseChunk",
                 "textResponse": "Die Zusammenfassung ist nicht "
                                 "zustande gekommen: %s" % str(e)[:150],
                 "sources": [], "close": True, "error": False})
            self._strom_schliessen()
            return True

        if not text:
            self._stand_weg(stand)
            self._strom_schliessen()
            return False

        text += "\n".join(["", "---",
                           zusammenfassungs_fuss(gewaehlt, _ganz, _gelesen,
                                                 auftrag=bool(_auftrag))])
        if len(GESPRAECHE.verlauf_kurz(gespraech, 10)) < 2:
            text += "\n" + assistent.naechste_schritte("zusammenfassung", gewaehlt)

        self._festhalten("zusammenfassung", frage, text)
        GESPRAECHE.dokument_merken(gespraech, gewaehlt)
        self._stand_weg(stand)
        self._strom_stueck(
            {"uuid": _neue_marke("zusammenfassung"), "type": "textResponseChunk",
             "textResponse": text, "sources": [],
             "close": False, "error": False})
        self._strom_stueck(
            {"uuid": _neue_marke("zusammenfassung"), "type": "textResponseChunk",
             "textResponse": "", "sources": [],
             "close": True, "error": False})
        self._strom_schliessen()
        print("[Assistent] Zusammenfassung %s: %d Zeichen Vorlage, %d Antwort"
              % (gewaehlt, len(dok.text), len(text)),
              file=sys.stderr, flush=True)
        return True

    def _bilder_auswaehlen(self, dok, frage, aspekt="", ab=0, hoechstens=3):
        """Welche Abbildungen? 'die letzte' -> letzte; 'weitere' -> ab Offset;
        Aspekt ('Kernergebnis', 'Steifigkeit') -> Unterschriften, die dazu
        passen, sonst bei Ergebnis-Woertern die Abbildungen aus dem hinteren
        Drittel (Ergebniskapitel). Gemessen 26.08.: immer die ersten drei."""
        liste = self._abbildungen_liste(dok)
        if not liste:
            return []
        f = (frage or "").lower() + " " + (aspekt or "").lower()
        if re.search(r"\bletzte[snr]?\b", f):
            return liste[-hoechstens:] if "letzten" in f else liste[-1:]
        if re.search(r"\berste[snr]?\b", f) and not aspekt:
            return liste[:1]
        terme = fadenfrage.suchwoerter(aspekt or "")
        if terme:
            passend = [x for x in liste if any(t in fadenfrage._falte(x[2]) for t in terme)]
            if passend:
                return passend[ab:ab + hoechstens]
        if re.search(r"kern|ergebnis|wichtigst|zentral|haupt|fazit|schluss", f):
            hinten = liste[int(len(liste) * 0.6):] or liste
            return hinten[ab:ab + hoechstens]
        return liste[ab:ab + hoechstens]

    def _bild_antwort(self, frage, erzwinge=None, vorspann="", ab=0, aspekt=""):
        """KI4KI-BILD: Bildwunsch direkt aus dem Dokument beantworten.

        Gemessen (Demo 24.08.): "Zeig mir Bild 2.1" - die Aehnlichkeitssuche
        lieferte den Abschnitt zu Figure 2.2, das Modell schrieb "Bild 2.1
        ist nicht enthalten", und der Proxy haengte darunter das RICHTIGE
        Bild 2.1 an. Text und Bild kamen aus zwei Quellen. Hier kommt beides
        aus einer: die Seite mit der Bildunterschrift.

        True = beantwortet. False = normaler Weg (der haengt Abbildungen der
        belegten Seiten ohnehin an).
        """
        if not BILD_ANTWORT or not (erzwinge or _ist_bildwunsch(frage)):
            return False
        if not erzwinge and assistent.ist_beschwerde(frage):
            return False
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True
        # Nur Dokumente, die dieser Nutzer sehen darf (A2/A3).
        namen = titel_im_bereich(self.path, self.headers) or []
        if not namen:
            BESTAND.aktualisiere()
            namen = nur_erlaubte(BESTAND.titel(), self.headers)
        if not namen:
            return False
        try:
            gewaehlt, _ = assistent.dokument_gemeint(frage, namen)
        except Exception:
            gewaehlt = None
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        # ⭐ FADEN-DOKUMENT: "ein Diagramm aus der Arbeit" meint die Arbeit,
        #   um die es gerade geht - NUR die. Gemessen 25.08.: ohne das kamen
        #   die Diagramme aus dem ersten Dokument der Liste (fremde Arbeit).
        nur_faden = None
        if erzwinge and erzwinge in namen:
            gewaehlt = nur_faden = erzwinge
        if not gewaehlt:
            _faden_dok = GESPRAECHE.letztes_dokument(gespraech)
            if _faden_dok and _faden_dok in namen and \
                    assistent.bezieht_sich_auf_vorheriges(frage):
                gewaehlt = nur_faden = _faden_dok
                print("[Bild] Faden-Dokument: %r" % _faden_dok,
                      file=sys.stderr, flush=True)
        if nur_faden:
            reihe = [nur_faden]
        elif gewaehlt:
            reihe = [gewaehlt] + [n for n in namen if n != gewaehlt]
        else:
            reihe = list(namen)
        _pdfs_erneuern_wenn_faellig()
        treffer = _abbildungs_seiten(frage, [], reihe)
        try:
            import abbildung
        except Exception:
            return False
        gute = []
        for doku, seite in treffer:
            pfad = PDFS.get(_pdf_schluessel(doku) or "")
            try:
                if pfad and abbildung.hat_abbildung(pfad, seite):
                    gute.append((doku, seite))
            except Exception:
                continue
            if len(gute) >= 3:
                break
        # ⭐ Auswahl nach Aspekt/Position, wenn ein Dokument feststeht und keine
        #   Bildnummer genannt ist (sonst gilt die Nummer).
        if gewaehlt and not _BILDNUMMER.search(frage or ""):
            _aspekt = aspekt or ((getattr(self, "_absicht", None) or {}).get("aspekt") or "")
            _wahl = self._bilder_auswaehlen(gewaehlt, frage, _aspekt, ab=ab)
            if _wahl:
                gute = [(gewaehlt, s_) for _, s_, _ in _wahl]
        if not gute and nur_faden:
            # Ehrlich bleiben statt in fremde Dokumente auszuweichen.
            _leer = vorspann + (
                     "In **%s** habe ich keine Abbildung mit Bildunterschrift "
                     "gefunden. Falls du ein anderes Dokument meinst: nenn "
                     "mir Kennung oder Verfasser."
                     % assistent._titel_saubern(nur_faden))
            self._festhalten("bild", frage, _leer)
            GESPRAECHE.merken(gespraech, frage, "bild", [])
            self._sende_strom([
                {"uuid": _neue_marke("bild"), "type": "textResponseChunk",
                 "textResponse": _leer, "sources": [], "close": False,
                 "error": False},
                {"uuid": _neue_marke("bild"), "type": "textResponseChunk",
                 "textResponse": "", "sources": [], "close": True,
                 "error": False},
            ])
            return True
        if not gute:
            return False
        # "das erste Diagramm" -> genau eines (das erste mit Unterschrift).
        if re.search(r"\b(?:das|die|den)\s+erste[nsr]?\b", frage or "", re.I):
            gute = gute[:1]
        nummer = _BILDNUMMER.search(frage)
        begonnen = time.time()
        modell_benutzt = False
        bloecke = []
        for doku, seite in gute:
            try:
                seiten = _seitentexte_pdf(_pdf_schluessel(doku)) or []
            except Exception:
                seiten = []
            seitentext = seiten[seite - 1] if 0 < seite <= len(seiten) else ""
            unterschrift = _bildunterschrift(
                seitentext, nummer.group(1) if nummer else None)
            dq = quote(str(doku), safe="")
            stelle = "/stelle?dok=%s&seite=%d" % (dq, seite)
            name = (unterschrift.split(":", 1)[0].strip()
                    if unterschrift and ":" in unterschrift[:20]
                    else (unterschrift[:24].strip() if unterschrift else "Abbildung"))
            kopf = "**%s** — %s, [Seite %d](%s)" % (
                name, assistent._titel_saubern(doku), seite, stelle)
            teile = [kopf]
            if unterschrift:
                teile.append("*%s*" % unterschrift.strip())
            # Nur bei einem GEZIELTEN Bild das Modell bemuehen (kostet ~10 s);
            # bei "irgendein Diagramm" reichen Unterschrift und Bild.
            if nummer and seitentext.strip():
                beschreibung = self._bild_beschreiben(unterschrift, seitentext)
                if beschreibung:
                    teile.append(beschreibung)
                    modell_benutzt = True
            teile.append("[![Abbildung aus %s, Seite %d](%s)](%s)"
                         % (doku, seite, self._bild_url(_pdf_schluessel(doku) or doku, seite), stelle))
            bloecke.append("\n\n".join(teile))
        if nummer:
            text = "\n\n".join(bloecke)
        else:
            text = ("Abbildungen (%d ausgewählt%s):\n\n"
                    % (len(bloecke), (" ab Position %d" % (ab + 1)) if ab else "")
                    + "\n\n---\n\n".join(bloecke))
        if len(GESPRAECHE.verlauf_kurz(gespraech, 10)) < 2:
            text += "\n\n*Klick auf Bild oder Seite öffnet das Original.*"
            if gewaehlt:
                text += "\n" + assistent.naechste_schritte("bild", gewaehlt)
        text = vorspann + text
        if modell_benutzt:
            text += _modell_zeile(MODELL_NAME, time.time() - begonnen)
        self._festhalten("bild", frage, text)
        self._sende_strom([
            {"uuid": _neue_marke("bild"), "type": "textResponseChunk",
             "textResponse": text, "sources": [], "close": False, "error": False},
            {"uuid": _neue_marke("bild"), "type": "textResponseChunk",
             "textResponse": "", "sources": [], "close": True, "error": False},
        ])
        print("[Bild] %d Abbildung(en) zu %r" % (len(gute), (frage or "")[:50]),
              file=sys.stderr, flush=True)
        GESPRAECHE.merken(gespraech, frage, "bild", [])
        _dokus = {d for d, _ in gute}
        if gewaehlt or len(_dokus) == 1:
            GESPRAECHE.dokument_merken(gespraech, gewaehlt or _dokus.pop())
        return True

    # ------------------------------------------------ Stufe 2: Gespraech

    def _abbildungen_liste(self, dok):
        """[(nummer, seite, unterschrift)] - nur Seiten, auf denen wirklich
        ein Bild liegt. Einmal je Dokument berechnet, dann gemerkt."""
        cache = getattr(self.__class__, "_abb_cache", None)
        if cache is None:
            cache = self.__class__._abb_cache = {}
        schluessel = _pdf_schluessel(dok)
        if not schluessel:
            return []
        if schluessel in cache:
            return cache[schluessel]
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            seiten = []
        # ⚠ KEINE Filterung nach Rasterbild (gemessen 26.08.: Vektorgrafiken
        #   wie Figure 1.1/2.1 fielen weg, drei Werkzeuge nannten drei
        #   verschiedene Zahlen, und der Waechter strich echte Bilder als
        #   "gibt es nicht"). Die Bildunterschrift ist die Wahrheit; ob ein
        #   Rasterbild da ist, entscheidet nur, WIE es gezeigt wird.
        aus = fadenfrage.abbildungen_aus_seiten(seiten)
        cache[schluessel] = aus
        return aus

    def _bild_url(self, schluessel, seite):
        """Freigestellte Abbildung, wenn ein Rasterbild da ist - sonst die
        gerenderte Seite (Vektorgrafiken, Diagramme aus Linien)."""
        dq = quote(str(schluessel), safe="")
        try:
            import abbildung
            if abbildung.hat_abbildung(PDFS.get(schluessel, ""), seite):
                return "/abbildung?dok=%s&seite=%d" % (dq, seite)
        except Exception:
            pass
        return "/seitenbild?dok=%s&seite=%d" % (dq, seite)

    def _bild_block(self, dok, nummer, seite, unterschrift):
        schluessel = _pdf_schluessel(dok) or dok
        dq = quote(str(schluessel), safe="")
        stelle = "/stelle?dok=%s&seite=%d" % (dq, seite)
        return ("**Bild %s** — %s, [Seite %d](%s)\n\n*%s*\n\n"
                "[![Abbildung aus %s, Seite %d](%s)](%s)"
                % (nummer, assistent._titel_saubern(dok), seite, stelle,
                   ("Bild %s: %s" % (nummer, unterschrift)) if unterschrift else "Bild %s" % nummer,
                   assistent._titel_saubern(dok), seite, self._bild_url(schluessel, seite), stelle))

    def _seiten_block(self, dok, seite):
        schluessel = _pdf_schluessel(dok) or dok
        dq = quote(str(schluessel), safe="")
        stelle = "/stelle?dok=%s&seite=%d" % (dq, seite)
        return ("**%s, [Seite %d](%s)**\n\n[![Seite %d aus %s](/seitenbild?dok=%s&seite=%d)](%s)"
                % (assistent._titel_saubern(dok), seite, stelle, seite, assistent._titel_saubern(dok), dq, seite, stelle))

    def _werkzeug(self, name, args, zustand):
        """Ein Werkzeugaufruf des Modells. Liefert Text fuers Modell."""
        namen = zustand["namen"]

        def dok_von(kennung):
            n = absicht._kennung_finden(kennung, namen)
            if not n:
                try:
                    n, _ = assistent.dokument_gemeint(str(kennung or ""), namen)
                except Exception:
                    n = None
            if n and n not in zustand["dokumente"]:
                zustand["dokumente"].append(n)
            return n

        if name == "dokument_finden":
            g, kand = assistent.dokument_gemeint(str(args.get("suche") or ""), namen)
            if g:
                zustand["dokumente"].append(g) if g not in zustand["dokumente"] else None
                return "Gefunden: %s" % assistent.dokument_zeile(g)
            if kand:
                return "Mehrere passen: " + "; ".join(assistent.dokument_zeile(k) for k in kand[:5])
            return "Nichts gefunden. Bestand: " + "; ".join(assistent._titel_saubern(n) for n in sorted(namen)[:20])
        if name == "bestand":
            thema = str(args.get("thema") or "").strip()
            frage = ("Welche Dokumente haben wir zum Thema %s?" % thema) if thema else "Welche Dokumente haben wir?"
            t = assistent.bestandsauskunft(frage, namen, bereich=True, zusatz=self._bestand_zusatz(namen))
            if not t:
                t = assistent._liste(sorted(assistent._titel_saubern(n) for n in namen), self._bestand_zusatz(namen))
            _stati = [(assistent._titel_saubern(n), dokument_status(n)) for n in sorted(namen)]
            _stati = [(k, st) for k, st in _stati if st]
            if _stati:
                t += "\n\nStatus (Metadaten): " + "; ".join("%s: %s" % kv for kv in _stati[:40])
            zustand["bestand_text"] = t
            return t
        if name == "pruefungsfrage":
            return self._pruefungsfrage_werkzeug(args, zustand)
        if name in ("bestand_durchsuchen", "stoerfall_suchen"):
            if name == "stoerfall_suchen":
                kontext = {"anlage": str(args.get("anlage") or ""), "fehlercode": str(args.get("fehlercode") or ""),
                           "symptom": str(args.get("symptom") or "")}
                begriffe = " ".join(stoerfall.suchbegriffe(kontext))
            else:
                begriffe = str(args.get("begriffe") or "")
            treffer = self._bestand_durchsuchen(begriffe, namen)
            if not treffer:
                if zustand.get("allgemeinwissen"):
                    return ("Zu '%s' keine belegte Stelle in den %d Dokumenten des Bereichs. Sag das in einem Satz - und "
                            "antworte dann aus Allgemeinwissen in einem eigenen Absatz, der mit 'Aus Allgemeinwissen "
                            "(nicht aus den Dokumenten):' beginnt (dieser Bereich steht auf Modus Chat)."
                            % (begriffe, len(namen)))
                return ("Zu '%s' keine belegte Stelle in den %d Dokumenten des Bereichs. Sag das ehrlich; "
                        "Ansprechpartner: %s" % (begriffe, len(namen), assistent.kontakt_zeile() or "nicht hinterlegt"))
            aus = []
            _kat = set(self._kataloge_im_bereich(namen))
            # Katalogseiten (Antwortoptionen!) ans Ende und gekennzeichnet
            treffer = sorted(treffer, key=lambda t: t[0] in _kat)
            for dok, seite, text in treffer:
                st = dokument_status(dok)
                warn = dokument_warnung(dok)
                if dok in _kat:
                    warn = (warn + "; " if warn else "") + "PRUEFUNGSKATALOG - Antwortoptionen, keine belegten Aussagen"
                aus.append("=== %s, Seite %d%s ===\n%s" % (
                    assistent._titel_saubern(dok), seite,
                    (" [%s]" % (warn or st)) if (warn or st) else "", text[:2500]))
                if dok not in zustand["dokumente"]:
                    zustand["dokumente"].append(dok)
            return "\n\n".join(aus)
        if name == "exportieren":
            if args.get("format") == "bibtex":
                return assistent.bibtex_eintraege(sorted(namen)) or "kein Katalog"
            csv = assistent.tabelle_zu_csv(GESPRAECHE.letzte_antwort(zustand["gespraech"]))
            return csv or "Keine Tabelle in der letzten Antwort."
        dok = dok_von(args.get("dokument"))
        if not dok:
            return ("Dokument '%s' unbekannt. Nutze dokument_finden oder eine Kennung aus der Liste."
                    % args.get("dokument"))
        schluessel = _pdf_schluessel(dok)
        if schluessel and not dokument_erlaubt(schluessel, self.headers):
            return "Dieses Dokument liegt nicht vor."
        if not schluessel and name in ("abbildungen_auflisten", "abbildung_zeigen", "seite_zeigen"):
            return ("%s liegt nicht als PDF vor (Excel/Word/Text) - es gibt keine Seitenbilder oder "
                    "Abbildungen dazu. Lies stattdessen mit seiten_lesen." % assistent._titel_saubern(dok))
        if name == "seiten_lesen":
            _sch, seiten = _seitentexte_von(dok)
            such = str(args.get("frage") or "")
            nummern, terme = fadenfrage.seiten_waehlen(such, seiten)
            if not nummern:
                return ("Zu '%s' keine passende Seite in %s gefunden (gesucht: %s). Andere Begriffe "
                        "probieren oder zusammenfassen nutzen." % (such, assistent._titel_saubern(dok), ", ".join(terme) or "-"))
            zustand["seiten"].setdefault(dok, []).extend(n for n in nummern if n not in zustand["seiten"].get(dok, []))
            return "\n\n".join("=== %s, Seite %d ===\n%s" % (assistent._titel_saubern(dok), n, (seiten[n - 1] or "")[:3500])
                                 for n in nummern if 0 < n <= len(seiten))
        if name == "abbildungen_auflisten":
            liste = self._abbildungen_liste(dok)
            zustand["abbildungen"][dok] = liste
            ab = int(args.get("ab") or 0)
            teil = liste[ab:ab + 80]
            if not liste:
                return "Keine Abbildung mit nummerierter Unterschrift in %s." % assistent._titel_saubern(dok)
            aus = "%d Abbildungen in %s. Die Zahl %d ist die einzige gueltige Anzahl. Tabelle (Markdown, unveraendert uebernehmen):\n\n" % (
                len(liste), assistent._titel_saubern(dok), len(liste))
            aus += "| Bild | Seite | Unterschrift |\n|---|---|---|\n"
            aus += "\n".join("| %s | %d | %s |" % (n, s, u[:110].replace("|", "/")) for n, s, u in teil)
            if len(liste) > ab + 80:
                aus += "\n\n(weitere %d mit ab=%d)" % (len(liste) - ab - 80, ab + 80)
            return aus
        if name == "seite_zeigen":
            try:
                seite = int(args.get("seite") or 0)
            except Exception:
                seite = 0
            try:
                anzahl = pdfstelle.seitenzahl(schluessel)
            except Exception:
                anzahl = 0
            if seite < 1 or (anzahl and seite > anzahl):
                return "Seite %s gibt es in %s nicht (1-%d)." % (args.get("seite"), assistent._titel_saubern(dok), anzahl)
            zustand["seiten_gezeigt"].append((dok, seite))
            return "[[SEITE:%s:%d]] — Seite %d von %s. Setze den Platzhalter in deine Antwort." % (
                assistent._titel_saubern(dok), seite, seite, assistent._titel_saubern(dok))
        if name == "abbildung_zeigen":
            liste = self._abbildungen_liste(dok)
            zustand["abbildungen"][dok] = liste
            nummer = str(args.get("nummer") or "").replace("-", ".").strip()
            for n, s, u in liste:
                if n == nummer:
                    zustand["gezeigt"].append((dok, n, s, u))
                    return "[[BILD:%s:%d:%s]] — Bild %s, S. %d: %s. Setze den Platzhalter in deine Antwort." % (
                        assistent._titel_saubern(dok), s, n, n, s, u)
            return "Bild %s gibt es in %s nicht. Vorhanden: %s" % (
                nummer, assistent._titel_saubern(dok), ", ".join(n for n, _, _ in liste[:30]) or "keine")
        if name == "zusammenfassen":
            d = BESTAND.hol(bestandsschluessel(dok)) if bestandsschluessel(dok) else None
            if not d or not (d.text or "").strip():
                return "Kein Volltext zu %s." % dok
            auftrag = str(args.get("auftrag") or "").strip() or None
            try:
                text, _g, _z = self._zusammenfassung_ganz(
                    d, dok, lambda m: self._stand(zustand["stand"], m), auftrag=auftrag)
            except Exception as e:
                return "Zusammenfassung nicht moeglich: %s" % str(e)[:100]
            zustand["zusammengefasst"].append(dok)
            zustand.setdefault("gelesen", {})[dok] = (_g, _z)
            return text or "Zusammenfassung nicht moeglich."
        if name == "zaehlen":
            w = self._fakten_zaehlen(dok, str(args.get("was") or "seiten"))
            return "%s: %s" % (args.get("was"), w if w not in (None, "") else "unbekannt")
        if name == "abkuerzung":
            _sch, seiten = _seitentexte_von(dok)
            t = assistent.abkuerzung_aufloesen(str(args.get("kurz") or ""), seiten)
            if not t:
                return "Abkuerzung %s wird in %s nicht ausgeschrieben eingefuehrt." % (args.get("kurz"), dok)
            return "; ".join("%s = %s (S. %d)" % (args.get("kurz"), lang, s) for s, lang, _ in t[:3])
        return "Unbekanntes Werkzeug " + name

    def _bestand_durchsuchen(self, begriffe, namen, hoechstens=6):
        """Seiten ueber ALLE erlaubten Dokumente: erst das Wortverzeichnis
        (welche Arbeiten tragen die Begriffe), dann Seitenwahl je Dokument.
        [(dok, seite, text)] - bestes zuerst. Ohne Verzeichnis: hoechstens
        40 Dokumente direkt (Seitentexte sind vorgewaermt)."""
        terme = fadenfrage.suchwoerter(begriffe) or [fadenfrage._falte(w) for w in begriffe.split() if len(w) >= 3]
        if not terme:
            return []
        kandidaten = []
        try:
            import wortsuche as _ws
            for w in [x for x in re.findall(r"[A-Za-zÄÖÜäöüß0-9][\w\-]{2,}", begriffe)][:4]:
                gef, _n = _ws.ueber_verzeichnis(BESTAND, w, hoechstens_arbeiten=12, je_arbeit=1,
                                                erlaubt=(lambda t, _namen=set(namen): t in _namen))
                for g in gef or []:
                    t = g.get("titel")
                    if t and t not in kandidaten:
                        kandidaten.append(t)
        except Exception:
            pass
        if not kandidaten:
            kandidaten = list(namen)[:40]
        punkte = []
        for dok in kandidaten[:40]:
            sch, seiten = _seitentexte_von(dok)
            if (sch and not dokument_erlaubt(sch, self.headers)) or not seiten:
                continue
            nummern, _t = fadenfrage.seiten_waehlen(begriffe, seiten, hoechstens=2)
            for n in nummern:
                g = fadenfrage._falte(seiten[n - 1])
                gewicht = sum(g.count(t) for t in terme)
                punkte.append((gewicht, dok, n, seiten[n - 1]))
        punkte.sort(key=lambda x: -x[0])
        return [(d, n, t) for _, d, n, t in punkte[:hoechstens]]

    def _gespraech_antwort(self, frage):
        """Stufe 2: Das Modell fuehrt den Zug - mit Werkzeugen und Faden.
        True = beantwortet. False = alter Weg."""
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True
        gespraech_k = GESPRAECHE.kennung(self.path, self.headers)
        BESTAND.aktualisiere()
        namen = (titel_im_bereich(self.path, self.headers)
                 or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        if not namen:
            return False
        faden_dok = GESPRAECHE.letztes_dokument(gespraech_k)
        zeilen = [assistent.dokument_zeile(n) for n in sorted(namen)[:40]]
        begonnen = time.time()
        self._strom_beginnen()
        stand = "gespraech-%d" % id(self)
        self._stand(stand, "Denke nach …")
        _m0 = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "")
        zustand = {"namen": namen, "dokumente": [], "seiten": {}, "abbildungen": {},
                   "gezeigt": [], "seiten_gezeigt": [], "zusammengefasst": [], "stand": stand, "gespraech": gespraech_k,
                   "bestand_text": "", "allgemeinwissen": (_bereich_modus(_m0.group(1) if _m0 else None) == "chat")}
        _melde = {"seiten_lesen": "Lese Seiten in %s …", "abbildungen_auflisten": "Suche Abbildungen in %s …",
                  "abbildung_zeigen": "Hole Bild aus %s …", "zusammenfassen": "Lese %s vollständig …",
                  "zaehlen": "Zähle in %s …", "bestand": "Sehe im Katalog nach …",
                  "dokument_finden": "Suche das Dokument …", "abkuerzung": "Suche die Abkürzung in %s …",
                  "exportieren": "Stelle den Export zusammen …", "seite_zeigen": "Hole Seite aus %s …",
                  "bestand_durchsuchen": "Durchsuche alle Dokumente …", "stoerfall_suchen": "Suche in Fehlerkatalogen und Handbüchern …",
                  "pruefungsfrage": "Hole die Frage aus dem Katalog …"}

        def melden(name, args):
            t = _melde.get(name, name)
            self._stand(stand, t % args.get("dokument") if "%s" in t else t)

        _kx = {k: v for k, v in stoerfall.erkennen(frage).items() if v}
        _frage_modell = frage
        if _kx and stoerfall.ist_stoerfall(frage):
            _frage_modell = frage + "\n[Erkannter Störfall-Kontext: %s]" % stoerfall.kontext_zeile(_kx)
        # ⭐ VORAB BELEGE HOLEN (deterministisch), damit das Modell nicht raet:
        #   Pruefungsfrage -> je Option; Stoerfall -> Stoerfallsuche; sonst ohne
        #   Faden-Dokument -> Bestandssuche mit den Fachwoertern der Frage.
        vorwissen = []
        try:
            # Offene Pruefungsfrage ("warum ist b richtig?"): der Katalogeintrag
            # samt Loesung liegt dem Modell vor - es muss nichts raten.
            _pf = GESPRAECHE.notiz(gespraech_k, "pruefung") or {}
            if _pf.get("dok") and _pf.get("nr"):
                _f = self._katalogfrage(_pf["dok"], _pf["nr"])
                if _f:
                    vorwissen.append(("pruefungsfrage", {"dokument": assistent._titel_saubern(_pf["dok"]), "nummer": _pf["nr"]},
                                      pruefungskatalog.zeile_fuer_modell(_f, assistent._titel_saubern(_pf["dok"]))))
                    if _pf["dok"] not in zustand["dokumente"]:
                        zustand["dokumente"].append(_pf["dok"])
            # Zusammenfassung gewuenscht: die VOLLSTAENDIGE Lesung (mehrstufig, mit Vorrat)
            # liegt dem Modell vor, bevor es antwortet - es kann sie mit Belegen aus
            # seiten_lesen ergaenzen und weitere Wuensche im selben Satz erledigen.
            _zdok = None
            if self._will_zusammenfassung(frage) and not assistent.ist_bestandsfrage_unscharf(frage):
                _zdok = assistent.dokument_gemeint(frage, namen)[0] or faden_dok
            if _zdok:
                self._stand(stand, "Lese %s vollständig …" % assistent._titel_saubern(_zdok))
                _zerg = self._werkzeug("zusammenfassen", {"dokument": _zdok}, zustand)
                vorwissen.append(("zusammenfassen", {"dokument": assistent._titel_saubern(_zdok)}, _zerg))
                if _zdok not in zustand["dokumente"]:
                    zustand["dokumente"].append(_zdok)
            optionen = assistent.optionen_finden(frage)
            if len(optionen) >= 2:
                self._stand(stand, "Prüfungsfrage: suche Belege je Option …")
                for buchstabe, text_opt in optionen[:6]:
                    erg = self._werkzeug("bestand_durchsuchen", {"begriffe": text_opt}, zustand)
                    vorwissen.append(("bestand_durchsuchen", {"begriffe": "Option %s: %s" % (buchstabe, text_opt)}, erg))
            elif _kx and stoerfall.ist_stoerfall(frage):
                self._stand(stand, "Störfall: suche in Fehlerkatalogen und Handbüchern …")
                args = {"anlage": _kx.get("anlage", ""), "fehlercode": _kx.get("fehlercode", ""), "symptom": _kx.get("symptom", "")}
                vorwissen.append(("stoerfall_suchen", args, self._werkzeug("stoerfall_suchen", args, zustand)))
            elif not assistent.ist_anlagefrage(frage) and not assistent._ist_bestandsfrage(frage) \
                    and fadenfrage.suchwoerter(frage) and not any(assistent.dokument_gemeint(frage, namen)) \
                    and not re.search(r"\b(?:bild|abbildung|grafik|diagramm|foto|zeig)\w*", frage, re.I):
                # Gemessen 27.08. (Selbst-Check): Mit Faden-Dokument bekam das Modell
                # keine Belege vorab, rief kein Werkzeug und schrieb in 1,7 s "nicht
                # enthalten" - bei 'Laminieren' in einem Laminier-Bestand. Deshalb:
                # erst im Faden-Dokument lesen; findet sich dort nichts, der ganze Bestand.
                gefunden = False
                if faden_dok:
                    self._stand(stand, "Lese Seiten in %s …" % assistent._titel_saubern(faden_dok))
                    erg = self._werkzeug("seiten_lesen", {"dokument": faden_dok, "frage": frage}, zustand)
                    if erg and not erg.startswith(("Zu '", "Dokument '", "Dieses Dokument")):
                        vorwissen.append(("seiten_lesen", {"dokument": assistent._titel_saubern(faden_dok), "frage": frage}, erg))
                        gefunden = True
                if not gefunden:
                    self._stand(stand, "Durchsuche alle Dokumente …")
                    vorwissen.append(("bestand_durchsuchen", {"begriffe": frage}, self._werkzeug("bestand_durchsuchen", {"begriffe": frage}, zustand)))
        except Exception:
            traceback.print_exc(file=sys.stderr)
        _m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "")
        _slug = _m.group(1) if _m else None
        e = gespraechsmodus.fuehren(
            _frage_modell, GESPRAECHE.verlauf_kurz(gespraech_k, hoechstens=20), assistent._titel_saubern(faden_dok) if faden_dok else None,
            zeilen, lambda n, a: self._werkzeug(n, a, zustand), kontakt=assistent.kontakt_zeile(),
            rolle=rolle.fuer_gespraech(_rolle_lesen(_slug)),
            allgemeinwissen=(_bereich_modus(_slug) == "chat"),
            melden=melden, vorwissen=vorwissen,
            denken=True if (len(assistent.optionen_finden(frage)) >= 2 or assistent.ist_negativfrage(frage)) else None,
            kennungen=[assistent._titel_saubern(n) for n in namen])
        self._stand_weg(stand)
        text = e.get("text") or ""
        if e.get("fehler") and not text:
            print("[Gespraech] ausgefallen: %s" % e["fehler"], file=sys.stderr, flush=True)
            self._strom_stueck({"uuid": _neue_marke("gespraech"), "type": "textResponseChunk",
                                "textResponse": "Die Antwort ist nicht zustande gekommen (%s). Bitte noch einmal."
                                % e["fehler"], "sources": [], "close": True, "error": False})
            self._strom_schliessen()
            return True
        # ⭐ Bestandsliste: Liefert das Werkzeug eine Tabelle (mit Links) und das
        #   Modell macht Fliesstext daraus (gemessen 26.08.: nackte Liste ohne
        #   Verlinkung), gilt die Tabelle - unveraendert.
        _werkzeugnamen = {n for n, _, _ in e["aufrufe"] if n != "waechter"}
        if zustand.get("bestand_text") and _werkzeugnamen and _werkzeugnamen <= {"bestand", "dokument_finden"} \
                and ("|" in zustand["bestand_text"] or "](" in zustand["bestand_text"]) \
                and "|" not in text and "](" not in text:
            text = zustand["bestand_text"]
        # ---- Pruefen und einbetten: Bilder nur, wenn es sie gibt ----------
        gezeigt = set()

        def _platzhalter(m):
            k, seite, nummer = m.group(1), int(m.group(2)), m.group(3)
            dok = absicht._kennung_finden(k, namen) or k
            for n, s, u in self._abbildungen_liste(dok):
                if n == nummer or s == seite:
                    gezeigt.add((dok, n))
                    return "\n\n" + self._bild_block(dok, n, s, u) + "\n\n"
            return ""
        text = gespraechsmodus.BILD_MARKE.sub(_platzhalter, text)

        def _seiten_platzhalter(m):
            k, seite = m.group(1), int(m.group(2))
            dok = absicht._kennung_finden(k, namen) or k
            return "\n\n" + self._seiten_block(dok, seite) + "\n\n"
        text = re.sub(r"\[\[SEITE:([^:\]]+):(\d{1,4})\]\]", _seiten_platzhalter, text)
        # 1) Was per Werkzeug ANGEFORDERT wurde, kommt sicher - auch wenn das
        #    Modell den Platzhalter vergessen hat (gemessen 26.08.: "zeig 6.3"
        #    -> Modell schrieb nur Text, eingebettet wurden 2.2/2.3/2.6).
        for dok, n, s, u in zustand["gezeigt"]:
            if (dok, n) not in gezeigt:
                text += "\n\n" + self._bild_block(dok, n, s, u)
                gezeigt.add((dok, n))
        for dok, seite in zustand["seiten_gezeigt"]:
            if "/seitenbild?dok=%s&seite=%d" % (quote(str(_pdf_schluessel(dok) or dok), safe=""), seite) not in text:
                text += "\n\n" + self._seiten_block(dok, seite)
        # 2) Genannte Nummern: Seitenzahlen berichtigen, erfundene streichen,
        #    einbetten nur, wenn noch nichts angefordert war.
        dok_fuer_bilder = zustand["dokumente"][-1] if zustand["dokumente"] else faden_dok
        gestrichen = []
        if dok_fuer_bilder:
            liste = {n: (s, u) for n, s, u in self._abbildungen_liste(dok_fuer_bilder)}
            def _seite_richtig(m):
                n = m.group(2).replace("-", ".")
                if n in liste and int(m.group(3)) != liste[n][0]:
                    return "%s%s — [S. %d]" % (m.group(1), n, liste[n][0])
                return m.group(0)
            text = re.sub(r"((?:Bild|Abbildung|Figure)\s*)(\d{1,2}[.\-]\d{1,3})\s*(?:—|-|–)\s*\[?S\.\s*(\d{1,4})\]?", _seite_richtig, text)
            for nummer in gespraechsmodus.bildnennungen(text)[:12]:
                if (dok_fuer_bilder, nummer) in gezeigt:
                    continue
                if nummer in liste:
                    if not gezeigt and len([1 for g in gezeigt]) < 3 and not zustand["gezeigt"]:
                        s, u = liste[nummer]
                        text += "\n\n" + self._bild_block(dok_fuer_bilder, nummer, s, u)
                        gezeigt.add((dok_fuer_bilder, nummer))
                else:
                    gestrichen.append(nummer)
            if gestrichen:
                text = re.sub(r"\[?\b(?:Abbildung|Abb\.?|Bild)\s*(%s)\b\]?" % "|".join(re.escape(g) for g in gestrichen),
                              lambda m: "~~Bild %s~~ (gibt es nicht)" % m.group(1), text)
                echte = self._abbildungen_liste(dok_fuer_bilder)[:8]
                if echte:
                    dq = quote(str(_pdf_schluessel(dok_fuer_bilder) or dok_fuer_bilder), safe="")
                    text += ("\n\n**Die echten Abbildungen in %s** (die ersten %d von %d):\n"
                             % (assistent._titel_saubern(dok_fuer_bilder), len(echte), len(self._abbildungen_liste(dok_fuer_bilder))))
                    text += "\n".join("- Bild %s — [S. %d](/stelle?dok=%s&seite=%d): %s" % (n, s_, dq, s_, u)
                                       for n, s_, u in echte)
                    text += "\n\n*„Zeig mir Bild %s“ holt eine davon.*" % echte[0][0]
        # Kennungen mit Endung ("(X.md, S. 32)") auf die nackte Kennung bringen -
        # sonst greifen Belegpruefung und Verlinkung nicht (gemessen 27.08.).
        text = re.sub(r"\(\s*([^(),\n]{2,90}?)\.(?:md|pdf)\s*,\s*S\.", r"(\1, S.", text)
        # Belege OHNE Klammern ("... Testfragen DVS 2290, S. 1.") einklammern - sonst
        # weder geprueft noch verlinkt (gemessen 27.08.). Laengste Kennung zuerst.
        _kenn = sorted({assistent._titel_saubern(n) for n in namen if n}, key=len, reverse=True)
        if _kenn:
            text = re.sub(r"(?<![\(\[\w])(%s)\s*,\s*S\.?\s*(\d{1,4})(?![\w)])" % "|".join(re.escape(k) for k in _kenn),
                          r"(\1, S. \2)", text)
        # Doppelte Zeilen (das Modell wiederholt "Bild 4.11 - ..., Seite 51" neben dem Block)
        _gesehen, _zeilen = set(), []
        for _z in text.split("\n"):
            _k = _z.strip().lower()
            if len(_k) > 12 and not _k.startswith(("|", "-", "*", "#")) and _k in _gesehen:
                continue
            _gesehen.add(_k)
            _zeilen.append(_z)
        text = "\n".join(_zeilen)
        # ---- Jede Aussage mit Seitenangabe gegen die Seite pruefen --------
        # Gemessen 26.08.: Das Modell schrieb "die Klemmung erhoeht die
        # Lebensdauer (DS-24-005, S. 12)" - erfunden, Gegenteil der Arbeit.
        # Deckt die genannte Seite (oder eine andere) die Aussage nicht,
        # bleibt die Aussage stehen, aber als "nicht belegt" markiert.
        unbelegt = 0
        belegt_z = 0
        _bekannt = {assistent._titel_saubern(n).strip().lower(): n for n in namen}

        def _beleg(m):
            nonlocal unbelegt, belegt_z
            k, n = m.group(1).strip(), int(m.group(2))
            if k.lower() not in _bekannt and not re.fullmatch(r"[A-Z]{1,4}-\d{2}-\d{3}", k):
                return m.group(0)          # Klammertext, kein Dokument des Bereichs
            k = assistent._titel_saubern(_bekannt.get(k.lower(), k))
            anfang = max(text.rfind(x, 0, m.start()) for x in (". ", "\n", "! ", "? ", "• ", "- "))
            satz = text[anfang + 1:m.start()].strip(" *:„“\"")
            if len(satz) < 25:
                return m.group(0)
            try:
                seite = _verifizierte_seite(k, satz, bevorzugt=n)
            except Exception:
                seite = None
            if seite is None:
                unbelegt += 1
                return "(%s, S. %d — nicht belegt)" % (k, n)
            belegt_z += 1
            return "(%s, S. %d)" % (k, seite)
        text = gespraechsmodus._BELEG.sub(_beleg, text)
        # ---- Zitate und Seiten pruefen ------------------------------------
        beruehrt = {}
        for dok in zustand["dokumente"] or ([faden_dok] if faden_dok else []):
            sch = _pdf_schluessel(dok)
            if sch:
                try:
                    beruehrt[assistent._titel_saubern(dok)] = (sch, _seitentexte_pdf(sch) or [])
                except Exception:
                    pass
        ok = nein = 0
        if beruehrt:
            text, ok, nein = fadenfrage.verlinken_mehrfach(text, beruehrt)
        # ---- Fuss --------------------------------------------------------
        # ⭐ Fuss: EINE kurze Zeile, nur mit Inhalt, der sich aendert (Emrach 26.08.:
        #   "die Fussnoten nerven, da steht eh immer das selbe").
        _kurz = {"seiten_lesen": "gelesen", "abbildungen_auflisten": "Bilder gelistet", "abbildung_zeigen": "Bild",
                 "zusammenfassen": "zusammengefasst", "zaehlen": "gezählt", "bestand": "Katalog", "dokument_finden": "gesucht",
                 "abkuerzung": "Abkürzung", "exportieren": "Export", "seite_zeigen": "Seite", "bestand_durchsuchen": "Bestand durchsucht",
                 "stoerfall_suchen": "Störfallsuche", "pruefungsfrage": "Katalogfrage"}
        _doks = ", ".join(assistent._titel_saubern(d) for d in zustand["dokumente"][:3])
        _was = sorted({_kurz.get(n, n) for n, _, _ in e["aufrufe"] if n != "waechter"})
        fuss = []
        if _doks:
            fuss.append("Quelle: %s" % _doks)
        if _was:
            fuss.append(", ".join(_was))
        for _d, (_g, _z) in (zustand.get("gelesen") or {}).items():
            fuss.append("vollständig gelesen: %s (%s)" % (assistent._titel_saubern(_d), ("%d von %d Zeichen" % (_g, _z)) if _g and _z and _g < _z else "ganzer Text"))
        if ok or nein:
            fuss.append("%d Zitat%s geprüft%s" % (ok + nein, "" if ok + nein == 1 else "e", (", %d nicht gefunden" % nein) if nein else ""))
        if gestrichen:
            fuss.append("⚠ erfundene Bildnummern gestrichen: %s" % ", ".join(gestrichen))
        if unbelegt:
            fuss.append("⚠ %d Aussage(n) nicht belegt" % unbelegt)
        _warn = [dokument_warnung(d) for d in zustand["dokumente"][:3]]
        _warn = [w for w in _warn if w]
        if _warn:
            fuss.append("⚠ " + "; ".join(_warn))
        if "Aus Allgemeinwissen" in text:
            fuss.append("⚠ enthält Allgemeinwissen des Modells (nicht aus den Dokumenten)")
        if fuss:
            text += "\n\n*" + " · ".join(fuss) + "*"
        # ---- Merken und senden -------------------------------------------
        if zustand["dokumente"]:
            GESPRAECHE.dokument_merken(gespraech_k, zustand["dokumente"][-1])
        # Protokoll (K5): geprüfte Zitate und verifizierte Belege zaehlen als
        # "belegt" - vorher stand jede Stufe-2-Antwort als "eigen" da und die
        # Kennzahl "quellenbasiert" zeigte 2,9 % bei 91 % Trefferquote (27.08.).
        _pruef = ([{"urteil": "woertlich"}] * ok + [{"urteil": "geglaettet"}] * belegt_z
                  + [{"urteil": "ungedeckt"}] * (nein + unbelegt))
        self._festhalten("gespraech", frage, text, quellen=[{"title": d} for d in zustand["dokumente"][:5]],
                         pruefungen=_pruef or None, seit=begonnen)
        GESPRAECHE.merken(gespraech_k, frage, "gespraech",
                          [{"title": d} for d in zustand["dokumente"][:3]],
                          antwort=re.sub(r"\n\n\*(?:Quelle:|Bestand|Katalog|gelesen|Bilder|Störfall)[^\n]*\*\s*$", "", text.split("\n\n---\n")[0]).strip())
        _marke = _neue_marke("gespraech")
        self._strom_stueck({"uuid": _marke, "type": "textResponseChunk",
                            "textResponse": text, "sources": [], "close": False, "error": False})
        self._strom_stueck(self._abschluss_stueck(_marke, self._quellen_fuer_oberflaeche(zustand), e.get("nutzung"), e.get("ms")))
        self._strom_schliessen()
        print("[Gespraech] %d Werkzeuge in %d ms, Zitate %d/%d, unbelegt %d, Bilder %d%s <- %r"
              % (len(e["aufrufe"]), e["ms"], ok, ok + nein, unbelegt, len(gezeigt),
                 (", gestrichen " + ",".join(gestrichen)) if gestrichen else "", frage[:60]),
              file=sys.stderr, flush=True)
        return True

    def _bestand_zusatz(self, namen, hoechstens=120):
        """Spalte 'Art' des Index: Dissertation/Norm-Art aus der Kennung, sonst
        Dateiart (PDF · n S. / Excel / Word / Text) und ob es ein
        Pruefungskatalog ist. Schluessel = Anzeigetitel (wie in der Tabelle)."""
        aus = {}
        try:
            import bestand as _bst
        except Exception:
            _bst = None
        for n in list(namen or [])[:hoechstens]:
            anzeige = assistent._titel_saubern(n)
            teile = []
            try:
                art = _bst.art_von(anzeige) if _bst else None
            except Exception:
                art = None
            if art:
                teile.append(art)
            sch = _pdf_schluessel(n)
            if sch:
                seiten = _seitenzahl_schnell(PDFS.get(sch, ""))
                # Word/PowerPoint, das die Aufnahme nach PDF gewandelt hat (Phase 0)
                original = _archivdatei(anzeige) or ""
                herkunft = {".docx": "Word", ".doc": "Word", ".odt": "Word", ".rtf": "Word",
                            ".pptx": "PowerPoint", ".ppt": "PowerPoint", ".odp": "PowerPoint"}.get(
                    os.path.splitext(original)[1].lower(), "")
                teile.append(("%s → " % herkunft if herkunft else "") + ("PDF · %d S." % seiten if seiten else "PDF"))
            else:
                datei = _archivdatei(anzeige) or _archivdatei(n) or ""
                endung = os.path.splitext(datei)[1].lower()
                teile.append({".xlsx": "Excel", ".xls": "Excel", ".csv": "Tabelle (CSV)", ".docx": "Word", ".doc": "Word",
                              ".pptx": "PowerPoint", ".ppt": "PowerPoint", ".txt": "Text", ".html": "HTML",
                              ".htm": "HTML", ".md": "Text", ".odt": "Text (ODT)"}.get(endung, "Datei" if datei else "Text"))
            try:
                fragen = self._katalog_fragen(n)
                if len(fragen) >= 3:
                    teile.append("Prüfungskatalog (%d Fragen)" % len(fragen))
            except Exception:
                pass
            aus[anzeige] = " · ".join(teile)
        return aus

    # ------------------------------------------------------ Pruefungskatalog
    _KATALOGE = {}      # bestandsschluessel -> (textlaenge, fragen)

    def _katalog_fragen(self, dok):
        """Die Fragen eines Dokuments - [] wenn es kein Katalog ist."""
        try:
            s = bestandsschluessel(dok)
            d = BESTAND.hol(s) if s else None
        except Exception:
            return []
        t = (getattr(d, "text", "") or "") if d else ""
        if not t.strip():
            return []
        alt = Griff._KATALOGE.get(s)
        if alt and alt[0] == len(t):
            return alt[1]
        fragen = pruefungskatalog.fragen_aus_text(t)
        Griff._KATALOGE[s] = (len(t), fragen)
        return fragen

    def _kataloge_im_bereich(self, namen):
        return [n for n in sorted(namen) if len(self._katalog_fragen(n)) >= 3]

    def _katalogfrage(self, dok, nr):
        for f in self._katalog_fragen(dok):
            if f["nr"] == nr:
                return f
        return None

    def _pruefungsfrage_stellen(self, gespraech_k, dok, nummer=None, thema=""):
        """Die naechste (oder gewuenschte) Frage als Chat-Text; merkt sie im Faden."""
        fragen = self._katalog_fragen(dok)
        titel = assistent._titel_saubern(dok)
        if not fragen:
            return None
        alt = GESPRAECHE.notiz(gespraech_k, "pruefung") or {}
        gestellt = list(alt.get("gestellt") or []) if alt.get("dok") == dok else []
        f = pruefungskatalog.waehlen(fragen, gestellt, nummer, thema)
        if not f:
            return "Frage %s gibt es in %s nicht — der Katalog hat die Fragen 1 bis %d." % (nummer, titel, len(fragen))
        text, z = pruefungskatalog.stellen(f, gesamt=len(fragen), kennung=titel, quelle=self._katalog_quelle(dok, f))
        z.update({"dok": dok, "gestellt": (gestellt + [f["nr"]])[-500:]})
        GESPRAECHE.notiz_setzen(gespraech_k, "pruefung", z)
        GESPRAECHE.dokument_merken(gespraech_k, dok)
        return text

    def _katalog_quelle(self, dok, f):
        """Quellenangabe mit Link: PDF -> Seite, sonst die Originaldatei."""
        titel = assistent._titel_saubern(dok)
        sch = _pdf_schluessel(dok)
        if sch:
            seite = int(f.get("seite") or 0)
            if seite > 0:
                return "[%s, S. %d](/stelle?dok=%s&seite=%d) — Frage %d" % (
                    titel, seite, quote(str(sch), safe=""), seite, f.get("nr", 0))
            return "[%s](/pdf/%s) — Frage %d" % (titel, quote(str(sch), safe=""), f.get("nr", 0))
        return "[%s](/pdf/%s) — Frage %d (Zeile %d der Tabelle)" % (
            titel, quote(titel, safe=""), f.get("nr", 0), f.get("nr", 0))

    def _pruefungsfrage_werkzeug(self, args, zustand):
        """Werkzeug fuer das Modell (Stufe 2) - derselbe Weg wie der direkte."""
        namen = zustand["namen"]
        kat = self._kataloge_im_bereich(namen)
        dok = None
        wunsch = str(args.get("dokument") or "").strip()
        if wunsch:
            dok = absicht._kennung_finden(wunsch, namen) or assistent.dokument_gemeint(wunsch, namen)[0]
            if dok and dok not in kat:
                return "%s ist kein Pruefungskatalog (keine Fragen mit Optionen darin)." % assistent._titel_saubern(dok)
        if not dok:
            if len(kat) == 1:
                dok = kat[0]
            elif not kat:
                return "Im Bereich liegt kein Pruefungskatalog (keine Datei mit Fragen und Antwortoptionen)."
            else:
                return "Mehrere Kataloge im Bereich: " + "; ".join(assistent._titel_saubern(k) for k in kat) + \
                       " - frag den Menschen, welcher gemeint ist."
        if dok not in zustand["dokumente"]:
            zustand["dokumente"].append(dok)
        try:
            nummer = int(args.get("nummer") or 0) or None
        except Exception:
            nummer = None
        t = self._pruefungsfrage_stellen(zustand["gespraech"], dok, nummer, str(args.get("thema") or ""))
        return (t + "\n\n[Gib diesen Text UNVERAENDERT aus - Frage und Optionen woertlich.]") if t else "Katalog leer."

    def _pruefung_antwort(self, frage):
        """Deterministischer Pruefungsweg: Frage aus dem Katalog stellen,
        Antwort gegen den Katalog pruefen. True = erledigt."""
        offen = None
        gespraech_k = GESPRAECHE.kennung(self.path, self.headers)
        try:
            offen = GESPRAECHE.notiz(gespraech_k, "pruefung") or {}
        except Exception:
            offen = {}
        wunsch = pruefungskatalog.ist_wunsch(frage)
        if not wunsch and not offen:
            return False
        if not bereich_sichtbar(self.path, self.headers):
            return False
        BESTAND.aktualisiere()
        namen = (titel_im_bereich(self.path, self.headers)
                 or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        if not namen:
            return False
        kat = self._kataloge_im_bereich(namen)
        nennung = pruefungskatalog.genanntes_dokument(frage)
        genannt = assistent.dokument_gemeint(nennung, namen)[0] if nennung else None
        if nennung and not genannt:
            genannt = assistent.dokument_gemeint(frage, kat)[0] if kat else None

        def _kataloge_zeile():
            return "\n".join("- %s (%d Fragen)" % (assistent._titel_saubern(k), len(self._katalog_fragen(k))) for k in kat) \
                or "- (keiner)"
        # 0) Ein genanntes Dokument, das es nicht gibt oder kein Katalog ist -
        #    nie stillschweigend einen anderen Katalog nehmen (gemessen 26.08.:
        #    "aus den Pruefungsfragen zu DVS 2291" -> Frage aus "Testfragen DVS 2290").
        _sachfrage = re.search(r"\b(?:zeig|bild|abbildung|was|wie|warum|wieso|welche|erkl(?:ä|ae)r|fasse|vergleich|liste)\w*", frage, re.I)
        if nennung and (wunsch or (offen and not _sachfrage)) and (not genannt or genannt not in kat):
            if genannt and genannt not in kat:
                t = ("**%s** ist kein Prüfungskatalog — darin stehen keine Fragen mit Antwortoptionen.\n\n"
                     "Kataloge in diesem Bereich:\n%s" % (assistent._titel_saubern(genannt), _kataloge_zeile()))
            else:
                t = ("Einen Katalog „%s“ finde ich in diesem Bereich nicht — vielleicht noch nicht aufgenommen oder gelöscht.\n\n"
                     "Kataloge in diesem Bereich:\n%s\n\nSag mir, aus welchem ich fragen soll." % (nennung, _kataloge_zeile()))
            if kat:
                GESPRAECHE.notiz_setzen(gespraech_k, "pruefung", {"auswahl": kat})
            self._direkt_senden("pruefung", frage, t)
            print("[Pruefung] genanntes Dokument %r nicht als Katalog gefunden" % nennung, file=sys.stderr, flush=True)
            return True
        # 1) Es liegt eine Frage vor: Antwort pruefen / weiter / Quelle / Beschwerde / anderer Katalog
        if offen.get("dok") and offen.get("nr") and not wunsch:
            f = self._katalogfrage(offen["dok"], offen["nr"])
            if f:
                if genannt and genannt in kat and genannt != offen["dok"] and not _sachfrage:
                    t = self._pruefungsfrage_stellen(gespraech_k, genannt)
                    if t:
                        self._direkt_senden("pruefung", frage, t, dok=genannt)
                        return True
                if pruefungskatalog.will_link(frage) or pruefungskatalog.ist_beschwerde(frage):
                    t = ("Die Frage %d steht wörtlich in **%s** — Quelle: %s.\n\n"
                         % (f["nr"], assistent._titel_saubern(offen["dok"]), self._katalog_quelle(offen["dok"], f)))
                    if f.get("richtig") is None:
                        t += ("Der Katalog ist ein gescanntes Dokument ohne Lösungen; der Text kann an dieser Stelle "
                              "lückenhaft sein — im Link siehst du das Original. ")
                    t += "Nächste Frage: „weiter“."
                    self._direkt_senden("pruefung", frage, t, dok=offen["dok"])
                    return True
                if pruefungskatalog.ist_weiter(frage):
                    t = self._pruefungsfrage_stellen(gespraech_k, offen["dok"])
                    if t:
                        self._direkt_senden("pruefung", frage, t, dok=offen["dok"])
                        print("[Pruefung] naechste Frage aus %s" % offen["dok"], file=sys.stderr, flush=True)
                        return True
                urteil = pruefungskatalog.pruefen(frage, f, offen, kennung=assistent._titel_saubern(offen["dok"]))
                if urteil:
                    self._direkt_senden("pruefung", frage, urteil, dok=offen["dok"])
                    print("[Pruefung] Antwort %r zu Frage %d geprueft" % (frage[:20], f["nr"]), file=sys.stderr, flush=True)
                    return True
            return False        # "warum?", andere Frage -> Gespraech mit Vorwissen
        # 1b) Es wurde nach dem Katalog gefragt (mehrere): Auswahl
        if offen.get("auswahl") and not wunsch:
            g, _k = assistent.dokument_gemeint(frage, offen["auswahl"])
            if not g:
                return False
            t = self._pruefungsfrage_stellen(gespraech_k, g)
            if t:
                self._direkt_senden("pruefung", frage, t, dok=g)
                return True
            return False
        if not wunsch:
            return False
        # 2) Wunsch nach einer Frage
        dok = assistent.dokument_gemeint(frage, kat)[0] if kat else None
        if not dok and len(kat) == 1:
            dok = kat[0]
        if not dok:
            if not kat:
                t = ("Im Bereich liegt kein Prüfungskatalog — keine Datei, in der Fragen mit Antwortoptionen stehen. "
                     "Vorhanden: %s." % ", ".join(assistent._titel_saubern(n) for n in sorted(namen)[:8]))
                self._direkt_senden("pruefung", frage, t)
                return True
            GESPRAECHE.notiz_setzen(gespraech_k, "pruefung", {"auswahl": kat})
            t = "Es gibt mehrere Kataloge — welcher?\n\n" + "\n".join("- %s (%d Fragen)" % (
                assistent._titel_saubern(k), len(self._katalog_fragen(k))) for k in kat)
            self._direkt_senden("pruefung", frage, t)
            return True
        t = self._pruefungsfrage_stellen(gespraech_k, dok, pruefungskatalog.gewuenschte_nummer(frage),
                                         pruefungskatalog.gewuenschtes_thema(frage))
        if not t:
            return False
        self._direkt_senden("pruefung", frage, t, dok=dok)
        print("[Pruefung] Frage aus %s gestellt <- %r" % (dok, frage[:50]), file=sys.stderr, flush=True)
        return True

    def _absicht_ausfuehren(self, frage):
        """Die vom Modell erkannte Absicht mit den vorhandenen Werkzeugen
        ausfuehren. True = erledigt. False = der Regel-Weg macht weiter."""
        a = self._absicht
        if not a:
            return False
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        aktion = a["aktion"]
        dok = a.get("dokument")
        frage_um = a.get("frage") or frage
        # Ein genanntes Dokument wird zum Faden-Dokument (Pivot).
        if dok and dok != GESPRAECHE.letztes_dokument(gespraech) and aktion not in ("vergleich", "bestand"):
            GESPRAECHE.dokument_merken(gespraech, dok)
            print("[Absicht] Dokumentwechsel: %r" % dok, file=sys.stderr, flush=True)
        if aktion == "klaerfrage":
            namen = (titel_im_bereich(self.path, self.headers)
                     or nur_erlaubte(BESTAND.titel(), self.headers) or [])
            kand = sorted(namen)[:10]
            if not kand:
                return False
            liste = "\n".join("- %s" % assistent.dokument_zeile(k) for k in kand)
            kopf = "Welches Dokument meinst du? Nenn mir Kennung oder Verfasser — oder wähle:"
            if len(namen) > 10:
                kopf += " (die ersten 10 von %d)" % len(namen)
            GESPRAECHE.wahl_merken(gespraech, kand)
            self._direkt_senden("rueckfrage", frage, kopf + "\n\n" + liste, merk_art="zusammenfassung")
            return True
        if aktion == "smalltalk":
            self._direkt_senden("meta", frage, META_TEXT_GRUSS)
            return True
        if aktion == "bild":
            _ab = 3 if re.search(r"\b(?:andere|weitere|mehr|noch)\b", frage, re.I) and \
                GESPRAECHE.letzte_art(gespraech) == "bild" else 0
            return self._bild_antwort(frage, erzwinge=dok, ab=_ab, aspekt=a.get("aspekt") or "")
        if aktion == "fakten":
            return self._fakten_antwort(frage, dok)
        if aktion == "abkuerzung":
            kurz = assistent.abkuerzungs_frage(frage) or assistent.abkuerzungs_frage(frage_um) \
                or (a.get("aspekt") if a.get("aspekt") and sum(1 for c in a["aspekt"] if c.isupper()) >= 2 else None)
            if kurz and dok:
                return self._abkuerzung_antwort(frage, kurz, dok)
            return False
        if aktion == "vergleich":
            return self._vergleich_antwort(frage, dok, a.get("zweites_dokument"), a.get("aspekt") or "")
        if aktion == "export":
            return self._export_antwort(frage, dok)
        if aktion == "zusammenfassung":
            return self._zusammenfassung(frage, erzwinge=dok)
        if aktion == "frage_an_dokument":
            if not dok:
                return False
            if assistent.dokument_fakten_frage(frage):
                return self._fakten_antwort(frage, dok)
            # "welches Diagramm ist das Kernergebnis?" ist eine Bildfrage mit Aspekt.
            if re.search(r"\b(?:diagramm|grafik|abbildung|bild|figur|plot|kurve)\w*", frage, re.I):
                if self._bild_antwort(frage, erzwinge=dok, aspekt=a.get("aspekt") or ""):
                    return True
            # "Worum geht es?" traegt keine Inhaltswoerter - dann ist die
            # Zusammenfassung die richtige Antwort, nicht "keine Seite gefunden".
            if not fadenfrage.suchwoerter(frage_um) and not fadenfrage.suchwoerter(frage):
                return self._zusammenfassung(frage, erzwinge=dok)
            return self._faden_antwort(frage_um, dok)
        # bestand, rueckmeldung, anlage, gesamtbestand: die bestehenden Wege nach `art`
        return False

    def _rolle_festlegen(self, slug, fach, nutzer, besonderes, modus=None, glaetten=True):
        """Rolle schreiben (Vorlage, optional vom Modell geglaettet), Prompt und
        Modus einspielen. Rueckgabe (text, eingespielt, geglaettet)."""
        name = _ordnername(slug)
        text = rolle.vorlage(fach, nutzer, besonderes, slug=name)
        konf = _bereich_konf(slug)
        konf["rolle"] = {"fach": fach or "", "nutzer": nutzer or "", "besonderes": besonderes or "", "modus": modus or konf.get("rolle", {}).get("modus", "")}
        _bereich_konf_schreiben(slug, konf)
        # 1) SOFORT: Vorlage + Modus eintragen - wer gleich die Einstellungen
        #    oeffnet, sieht schon Rolle und Modus (gemessen 27.08.: Emrach sah
        #    den alten Stand, weil das Glaetten noch lief).
        _rolle_schreiben(slug, text)
        eingespielt = _rolle_einspielen(slug, erzwingen=True)
        if modus in rolle.MODI and API_SCHLUESSEL:
            try:
                _api("POST", "/api/v1/workspace/%s/update" % slug, {"chatMode": modus}, timeout=30)
                _MODUS_JE_BEREICH[slug] = (modus, time.time())
            except Exception as e:
                print("[Rolle] Modus '%s' fuer '%s' nicht gesetzt: %s" % (modus, slug, str(e)[:80]), file=sys.stderr, flush=True)
        # 2) DANN: das Modell den Regelteil formulieren lassen und nachziehen
        geglaettet = False
        if glaetten and ROLLE_GLAETTEN:
            try:
                antwort = self._modell_fragen(rolle.glaett_auftrag(fach, nutzer, besonderes), zeitgrenze=120)
                if rolle.geglaettet_brauchbar(antwort, fach, nutzer):
                    text = rolle.vorlage_mit_glaettung(fach, nutzer, besonderes, antwort, slug=name)
                    _rolle_schreiben(slug, text)
                    eingespielt = _rolle_einspielen(slug, erzwingen=True) or eingespielt
                    geglaettet = True
            except Exception as e:
                print("[Rolle] Glaetten nicht moeglich (%s) - Vorlage bleibt" % str(e)[:80], file=sys.stderr, flush=True)
        return text, eingespielt, geglaettet

    def _rolle_route(self):
        """POST /rolle  {slug, fach, nutzer, besonderes, modus} - vom Formular
        'Neuer Arbeitsbereich' (Skript in der Oberflaeche). Nur Einsichtsrecht."""
        if not darf_sehen(self.headers):
            print("[Rolle] /rolle abgewiesen: nicht angemeldet", file=sys.stderr, flush=True)
            self._json({"ok": False, "fehler": "Nicht angemeldet."}, code=401)
            return
        konto = pruefprotokoll.pseudonym(pruefprotokoll.konto_aus(self.headers))
        if not _darf_rolle_setzen(self.headers):
            print("[Rolle] /rolle abgewiesen: Konto %s ohne Einsichtsrecht (Authorization %s)" % (
                konto, "vorhanden" if self.headers.get("Authorization") else "FEHLT"), file=sys.stderr, flush=True)
            self._json({"ok": False, "fehler": "Nur Betreiber/Admin darf die Rolle eines Bereichs setzen."}, code=403)
            return
        try:
            leib = json.loads(self._koerper() or b"{}") or {}
        except Exception:
            leib = {}
        slug = re.sub(r"[^A-Za-z0-9_-]", "", str(leib.get("slug") or ""))[:80]
        if not slug or not bereich_sichtbar("/api/workspace/%s" % slug, self.headers):
            self._json({"ok": False, "fehler": "Bereich unbekannt."}, code=404)
            return
        fach, nutzer, bes = (str(leib.get(k) or "").strip()[:300] for k in ("fach", "nutzer", "besonderes"))
        modus = str(leib.get("modus") or "").strip().lower() or None
        if not (fach or nutzer or bes):
            if modus in rolle.MODI:
                try:
                    _api("POST", "/api/v1/workspace/%s/update" % slug, {"chatMode": modus}, timeout=30)
                except Exception:
                    pass
            self._json({"ok": True, "rolle": "", "hinweis": "keine Angaben - nur Kern-Prompt"})
            return
        bereich_ordner_anlegen(slug)
        text, eingespielt, geglaettet = self._rolle_festlegen(slug, fach, nutzer, bes, modus=modus)
        print("[Rolle] '%s' per Formular gesetzt von %s (%s)" % (slug, konto, "geglaettet" if geglaettet else "Vorlage"),
              file=sys.stderr, flush=True)
        self._json({"ok": True, "rolle": text, "eingespielt": eingespielt, "geglaettet": geglaettet,
                    "datei": "dokumente/%s/%s" % (_ordnername(slug), rolle.DATEI)})

    def _rolle_antwort(self, frage):
        """Einrichtungsdialog fuer die Rolle des Bereichs - nur fuer Konten mit
        Einsichtsrecht (dieselbe Regel wie /kpi), weil die Rolle fuer ALLE im
        Bereich gilt. True = erledigt."""
        gespraech_k = GESPRAECHE.kennung(self.path, self.headers)
        offen = GESPRAECHE.notiz(gespraech_k, "rolle")
        wunsch = rolle.ist_wunsch(frage)
        if not wunsch and not offen:
            return False
        m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "")
        slug = m.group(1) if m else None
        if not slug or not bereich_sichtbar(self.path, self.headers):
            return False
        konto = pruefprotokoll.pseudonym(pruefprotokoll.konto_aus(self.headers))
        if not _darf_rolle_setzen(self.headers):
            if wunsch:
                self._direkt_senden("meta", frage, "Die Rolle eines Bereichs darf nur ein Konto mit Einsichtsrecht "
                                    "(Betreiber/Admin) einrichten — sie gilt für alle, die hier fragen.")
                return True
            return False
        if wunsch and not offen:
            zustand, text, _ = rolle.schritt(None, "")
            vorhanden = _rolle_lesen(slug)
            if rolle.ist_eingerichtet(vorhanden):
                text = ("Für diesen Bereich ist schon eine Rolle hinterlegt (`dokumente/%s/prompt.md`). "
                        "Ich frage die drei Punkte neu ab und ersetze sie.\n\n" % _ordnername(slug)) + text
            GESPRAECHE.notiz_setzen(gespraech_k, "rolle", zustand)
            self._direkt_senden("rolle", frage, text)
            return True
        zustand, text, fertig = rolle.schritt(offen, frage)
        if fertig is None:
            GESPRAECHE.notiz_setzen(gespraech_k, "rolle", zustand)
            self._direkt_senden("rolle", frage, text)
            return True
        GESPRAECHE.notiz_setzen(gespraech_k, "rolle", None)
        try:
            neu, eingespielt, _g = self._rolle_festlegen(slug, fertig.get("fach"), fertig.get("nutzer"), fertig.get("besonderes"))
        except Exception as e:
            self._direkt_senden("rolle", frage, "Die Rolle ließ sich nicht speichern (%s)." % str(e)[:100])
            return True
        print("[Rolle] '%s' eingerichtet von %s" % (slug, konto), file=sys.stderr, flush=True)
        text = ("**Rolle gespeichert** — `dokumente/%s/prompt.md`%s. Sie gilt ab jetzt in diesem Bereich, "
                "in der Oberfläche und im Gesprächsmodus. Zum Anpassen die Datei bearbeiten oder erneut "
                "„Rolle einrichten“ sagen.\n\n---\n\n%s" % (
                    _ordnername(slug), "" if eingespielt else " (Einspielen in die Oberfläche folgt binnen 5 Minuten)", neu))
        self._direkt_senden("rolle", frage, text)
        return True

    _KATEGORIE_BEFEHL = re.compile(r"^\s*kategorie\s+(?:von|für|fuer)\s+(.+?)\s+(?:ist|=|:)\s+(.+?)\s*[.!]?\s*$", re.I)

    def _kategorie_antwort(self, frage):
        """'Kategorie von DVS 2290 Werkzeugliste ist Handbuch/Anleitung' - von Hand,
        bleibt gegen jede Neuberechnung bestehen. Nur Betreiber/Admin."""
        m = self._KATEGORIE_BEFEHL.match(frage or "")
        if not m:
            return False
        if not _darf_rolle_setzen(self.headers):
            self._direkt_senden("meta", frage, "Kategorien setzt nur ein Konto mit Einsichtsrecht (Betreiber/Admin).")
            return True
        namen = (titel_im_bereich(self.path, self.headers) or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        dok, kand = assistent.dokument_gemeint(m.group(1), namen)
        slug = (re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "") or [None, None])[1] \
            if re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "") else None
        wurzel = os.path.join(EINGANG_ORDNER, _ordnername(slug)) if slug else None
        erlaubt = kategorie.namen(wurzel)
        ziel = next((k for k in erlaubt if k.lower() == m.group(2).strip().lower()), None)
        if not dok:
            self._direkt_senden("meta", frage, "Welches Dokument? %s" % (
                ("Mehrere passen: " + "; ".join(assistent._titel_saubern(k) for k in kand[:5])) if kand else "Kennung aus der Bestandsliste nennen."))
            return True
        if not ziel:
            self._direkt_senden("meta", frage, "„%s“ ist keine Kategorie dieses Bereichs. Möglich: %s — die Liste steht in `dokumente/%s/kategorien.txt`."
                                % (m.group(2).strip(), ", ".join(erlaubt), _ordnername(slug) if slug else "<bereich>"))
            return True
        try:
            import bestand as _bst
            _bst.kategorie_setzen(assistent._titel_saubern(dok), ziel)
        except Exception as e:
            self._direkt_senden("meta", frage, "Nicht gespeichert (%s)." % str(e)[:80])
            return True
        print("[Kategorie] %s -> %s (von Hand)" % (dok, ziel), file=sys.stderr, flush=True)
        self._direkt_senden("meta", frage, "Notiert: **%s** ist ab jetzt **%s** — von Hand gesetzt, bleibt bei jeder Neuberechnung." % (assistent._titel_saubern(dok), ziel), dok=dok)
        return True

    def _bestand_vorab(self, frage):
        return bool(assistent.ist_bestandsfrage_unscharf(frage) and not assistent.ist_beschwerde(frage)
                    and self._bestandsauskunft(frage))

    def _faden_raus(self, frage):
        """'Tu das Dokument raus' - Faden-Dokument vergessen; der Rest der Frage laeuft weiter."""
        if not assistent.ist_faden_raus(frage):
            return None
        k = GESPRAECHE.kennung(self.path, self.headers)
        alt = GESPRAECHE.letztes_dokument(k)
        GESPRAECHE.dokument_vergessen(k)
        return alt

    def _vergleich_vorab(self, frage):
        """'Vergleiche DS-24-005 und DS-24-007' -> die feste Vergleichstabelle, nicht das Modell
        (gemessen 27.08.: Stufe 2 las stur im alten Faden-Dokument und verglich Titel)."""
        if not assistent._VERGLEICH.search(frage or ""):
            return False
        namen = (titel_im_bereich(self.path, self.headers) or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        v = assistent.vergleichs_dokumente(frage, namen)
        if not v:
            return False
        a, b = v[0], v[1]
        aspekt = v[2] if len(v) > 2 else ""
        return bool(self._vergleich_antwort(frage, a, b, aspekt or ""))

    @staticmethod
    def _will_zusammenfassung(frage):
        return bool(assistent._ZUSAMMENFASSUNG.search(frage or "") or re.search(
            r"\b(?:komplett|vollst(?:ä|ae)ndig|ganz(?:es)?)\b.{0,40}\b(?:les|zusammenfass)|\bkernaussage|\bzusammenfass", frage or "", re.I))

    @staticmethod
    def _mehrfachauftrag(frage):
        """Zwei Wuensche in einem Satz ('Kernaussage und danach eine Bilderliste')
        -> nichts abkuerzen, Stufe 2 erledigt beide (gemessen 27.08.: der
        Zusammenfassungs-Kurzweg liess den zweiten Teil unter den Tisch fallen)."""
        f = (frage or "").lower()
        absichten = sum(1 for m in (r"zusammenfass|kernaussage|worum geht", r"bild|abbildung|grafik|diagramm", r"vergleich",
                                    r"wie viele|anzahl", r"liste|tabelle", r"zitat|beleg|seite") if re.search(m, f))
        return absichten >= 2 or bool(re.search(r"\b(?:und (?:dann|danach|anschließend|anschliessend|außerdem|zeig)|anschließend|anschliessend|danach)\b", f))

    def _fakten_vorab(self, frage):
        """'Wie viele Abbildungen/Seiten/Tabellen hat ...' -> gezaehlt, nicht geraten
        (gemessen 27.08.: das Modell nannte 38 und 91 in einer Antwort)."""
        if not assistent.dokument_fakten_frage(frage) or self._mehrfachauftrag(frage):
            return False
        namen = (titel_im_bereich(self.path, self.headers) or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        dok = assistent.dokument_gemeint(frage, namen)[0] or GESPRAECHE.letztes_dokument(GESPRAECHE.kennung(self.path, self.headers))
        if not dok:
            return False
        return bool(self._fakten_antwort(frage, dok))

    def _bild_vorab(self, frage):
        """'Zeig mir Bild 2.1' mit Faden-Dokument -> direkt das Bild (kein Modell)."""
        m = re.match(r"^\s*(?:ok\s+|okay\s+|dann\s+|ja\s+|gut\s+)*zeig\w*\s+(?:mir\s+)?(?:mal\s+|bitte\s+)*(?:das\s+|die\s+)?(?:bild|abbildung|abb\.?|grafik|diagramm)\s*(\d{1,2}[.\-]\d{1,3})\b",
                     frage or "", re.I)
        if not m and len((frage or "").split()) <= 8:
            # "Danke und jetzt Bild 1.1?" / "und 4.4?" nach einem Bild
            m = re.search(r"\b(?:bild|abbildung|abb\.?|grafik|diagramm)\s*(\d{1,2}[.\-]\d{1,3})\b", frage or "", re.I)
            if not m and GESPRAECHE.letzte_art(GESPRAECHE.kennung(self.path, self.headers)) == "bild":
                m = re.search(r"(?<![\d.])(\d{1,2}[.\-]\d{1,3})(?![\d.])", frage or "")
        if not m:
            return False
        k = GESPRAECHE.kennung(self.path, self.headers)
        dok = GESPRAECHE.letztes_dokument(k)
        if not dok:
            return False
        nummer = m.group(1).replace("-", ".")
        liste = self._abbildungen_liste(dok)
        for n, s, u in liste:
            if n == nummer:
                text = self._bild_block(dok, n, s, u) + "\n\n*Klick auf Bild oder Seite öffnet das Original.*"
                self._direkt_senden("bild", frage, text, dok=dok)
                return True
        if liste:
            self._direkt_senden("bild", frage, "Bild %s gibt es in %s nicht. Vorhanden: %s%s" % (
                nummer, assistent._titel_saubern(dok), ", ".join(n for n, _, _ in liste[:30]),
                " …" if len(liste) > 30 else ""), dok=dok)
            return True
        return False

    def _json_ueber_gespraech(self, frage):
        """⭐ Der JSON-Weg (/api/v1/workspace/<slug>/chat - n8n, Partner-
        Anbindungen, Selbst-Check) bekommt DIESELBE Antwort wie der Browser:
        Pruefungskatalog, Bestandstabelle, Stufe 2. Die Antwortwege schreiben
        in den Datenstrom - hier wird er gesammelt und als ein JSON zurueck-
        gegeben. Gemessen 27.08.: Der Selbst-Check lief ueber die alte
        Logik und mass etwas anderes als das, was ein Mensch im Chat sieht.
        True = beantwortet."""
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True
        self._sammeln = []
        try:
            getroffen = False
            for hook in (self._rolle_antwort, self._kategorie_antwort, self._pruefung_antwort, self._vergleich_vorab, self._bild_vorab,
                         self._fakten_vorab, self._bestand_vorab,
                         (self._gespraech_antwort if gespraechsmodus.AN else None)):
                if hook is None:
                    continue
                try:
                    if hook(frage):
                        getroffen = True
                        break
                except Exception:
                    traceback.print_exc(file=sys.stderr)
            if not getroffen:
                return False
            stuecke = self._sammeln
        finally:
            self._sammeln = None
        text = "".join(str(s.get("textResponse") or "") for s in stuecke
                       if isinstance(s, dict) and s.get("type") in ("textResponseChunk", "textResponse"))
        quellen = []
        for s in stuecke:
            for q in (s.get("sources") or []) if isinstance(s, dict) else []:
                if q not in quellen:
                    quellen.append(q)
        daten = json.dumps({"id": "gespraech", "type": "textResponse", "textResponse": text,
                            "sources": quellen, "close": True, "error": None}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)
        return True

    def _direkt_senden(self, art, frage, text, merk_art=None, dok=None, pruefungen=None):
        """Eine fertige Antwort senden, festhalten, merken. Wirft nie."""
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        if art == "pruefung" and dok and pruefungen is None:
            pruefungen = [{"urteil": "woertlich"}]        # Frage/Loesung woertlich aus dem Katalog
        self._festhalten(art, frage, text, quellen=[{"title": dok}] if dok else None, pruefungen=pruefungen)
        GESPRAECHE.merken(gespraech, frage, merk_art or art,
                          [{"title": dok}] if dok else [])
        self._sende_strom([
            {"uuid": _neue_marke(art), "type": "textResponseChunk",
             "textResponse": text, "sources": [], "close": False, "error": False},
        ], quellen=[{"title": assistent._titel_saubern(dok), "text": "", "chunkSource": assistent._titel_saubern(dok)}] if dok else [])

    def _vergleich_antwort(self, frage, dok_a, dok_b, aspekt):
        """Zwei Dokumente nebeneinander - Tabelle, jede Zelle mit Seite."""
        ka, kb = _pdf_schluessel(dok_a), _pdf_schluessel(dok_b)
        if not ka or not kb:
            return False
        if not (dokument_erlaubt(ka, self.headers) and dokument_erlaubt(kb, self.headers)):
            return False
        try:
            sa = _seitentexte_pdf(ka) or []
            sb = _seitentexte_pdf(kb) or []
        except Exception:
            return False
        if not sa or not sb:
            return False
        modus = "widerspruch" if assistent.ist_widerspruchsfrage(frage) else "vergleich"
        such = aspekt or ""
        na, _ = fadenfrage.seiten_waehlen(such, sa, hoechstens=4) if such else ([], [])
        nb, _ = fadenfrage.seiten_waehlen(such, sb, hoechstens=4) if such else ([], [])
        if not na:
            na = fadenfrage.uebersichtsseiten(sa)
        if not nb:
            nb = fadenfrage.uebersichtsseiten(sb)
        ta, tb = assistent._titel_saubern(dok_a), assistent._titel_saubern(dok_b)
        begonnen = time.time()
        self._strom_beginnen()
        stand = "vergleich-%d" % id(self)
        self._stand(stand, "Vergleiche *%s* (S. %s) mit *%s* (S. %s) — mit Bedenkzeit …"
                    % (ta, ", ".join(map(str, na)), tb, ", ".join(map(str, nb))))
        try:
            roh = self._modell_fragen(
                fadenfrage.vergleichs_auftrag(frage, such, (ta, ta, na, sa), (tb, tb, nb, sb), modus=modus),
                zeitgrenze=600, denken=True)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            roh = ""
        self._stand_weg(stand)
        if not (roh or "").strip():
            text = "Der Vergleich ist nicht zustande gekommen (Modell antwortete nicht). Bitte noch einmal."
            ok = nein = 0
        else:
            text, ok, nein = fadenfrage.verlinken_mehrfach(roh.strip(), {ta: (ka, sa), tb: (kb, sb)})
        text += ("\n\n---\n*%s von **%s** und **%s** — nur aus den geprüften Seiten "
                 "(%s: S. %s · %s: S. %s). %s*"
                 % ("Widerspruchsprüfung" if modus == "widerspruch" else "Vergleich", ta, tb,
                    ta, ", ".join(map(str, na)), tb, ", ".join(map(str, nb)),
                    ("%d Zitat(e) wörtlich geprüft%s." % (ok, ", %d nicht gefunden" % nein if nein else ""))
                    if (ok or nein) else "Seitenangaben verlinkt, Zitate nicht wörtlich geprüft."))
        text += "\n*Weiter: „Exportiere das als CSV“ · anderer Aspekt: „Vergleiche die Methodik von %s und %s“*" % (ta, tb)
        text += _modell_zeile(MODELL_NAME, time.time() - begonnen)
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        self._festhalten("vergleich", frage, text)
        GESPRAECHE.merken(gespraech, frage, "vergleich", [{"title": dok_a}, {"title": dok_b}])
        self._strom_stueck({"uuid": _neue_marke("vergleich"), "type": "textResponseChunk",
                            "textResponse": text, "sources": [], "close": True, "error": False})
        self._strom_schliessen()
        print("[Vergleich] %s vs %s (%s), %d ok / %d nicht" % (dok_a, dok_b, modus, ok, nein),
              file=sys.stderr, flush=True)
        return True

    def _abkuerzung_antwort(self, frage, kurz, dok):
        schluessel = _pdf_schluessel(dok)
        if not schluessel or not dokument_erlaubt(schluessel, self.headers):
            return False
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            seiten = []
        if not seiten:
            return False
        titel = assistent._titel_saubern(dok)
        treffer = assistent.abkuerzung_aufloesen(kurz, seiten)
        dq = quote(str(schluessel), safe="")
        if treffer:
            zeilen = []
            gesehen = set()
            for s, lang, roh in treffer:
                if lang.lower() in gesehen:
                    continue
                gesehen.add(lang.lower())
                zeilen.append("- **%s** = %s — [S. %d](/stelle?dok=%s&seite=%d&zitat=%s)"
                              % (kurz, lang, s, dq, s, quote(roh[:200], safe="")))
            text = "So wird **%s** in **%s** eingeführt:\n\n%s" % (kurz, titel, "\n".join(zeilen))
            if len(gesehen) > 1:
                text += "\n\n*Mehrere Auflösungen im selben Dokument — die Seite entscheidet.*"
        else:
            text = ("In **%s** wird **%s** nirgends ausgeschrieben eingeführt (Muster „Langform (%s)“ "
                    "oder „%s: Langform“). Möglich: im Abkürzungsverzeichnis anders gesetzt — "
                    "„Zeig mir das Abkürzungsverzeichnis“ — oder Fachbegriff: „Was ist %s?“"
                    % (titel, kurz, kurz, kurz, kurz))
        text += "\n\n📇 *Direkt aus dem Dokumenttext — ohne Sprachmodell.*"
        self._direkt_senden("abkuerzung", frage, text, merk_art="normal", dok=dok)
        print("[Abkuerzung] %s in %s: %d" % (kurz, dok, len(treffer)), file=sys.stderr, flush=True)
        return True

    def _export_antwort(self, frage, dok):
        was = assistent.export_frage(frage)
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        namen = (titel_im_bereich(self.path, self.headers)
                 or nur_erlaubte(BESTAND.titel(), self.headers) or [])
        if was == "bibtex":
            ziel = [dok] if (dok and re.search(r"\b(?:diese|dieses|das|die|der)\s+(?:arbeit|dokument|dissertation)\b", frage, re.I)) else namen
            inhalt = assistent.bibtex_eintraege(ziel)
            if not inhalt:
                return False
            text = ("BibTeX für %d Dokument(e) — markieren, kopieren, in Zotero/Citavi/LaTeX einfügen:\n\n```bibtex\n%s\n```"
                    % (len(ziel), inhalt))
        else:
            letzte = GESPRAECHE.letzte_antwort(gespraech)
            csv = assistent.tabelle_zu_csv(letzte)
            if csv:
                text = "Die letzte Tabelle als CSV (Semikolon-getrennt, Excel-tauglich):\n\n```csv\n%s\n```" % csv
            else:
                try:
                    import bestand as _b
                    zeilen = ["Kennung;Verfasser;Jahr;Titel"]
                    for n in sorted(namen):
                        ang = _b.angaben(n) or {}
                        zeilen.append(";".join('"%s"' % str(x).replace('"', '""') for x in
                                               (assistent._titel_saubern(n), ang.get("verfasser") or "", ang.get("jahr") or "", ang.get("titel") or "")))
                    text = "Keine Tabelle in der letzten Antwort — hier der Bestand als CSV:\n\n```csv\n%s\n```" % "\n".join(zeilen)
                except Exception:
                    return False
        text += "\n\n📇 *Direkt zusammengestellt — ohne Sprachmodell. Datei-Download gibt es im Chat nicht; Text kopieren.*"
        self._direkt_senden("export", frage, text, merk_art="normal", dok=dok)
        print("[Export] %s" % was, file=sys.stderr, flush=True)
        return True

    def _fakten_zaehlen(self, dok, was):
        """(Seiten, Anzahl/Wert, Zusatz) fuer ein Dokument - oder None."""
        schluessel = _pdf_schluessel(dok)
        if not schluessel or not dokument_erlaubt(schluessel, self.headers):
            return None
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            seiten = []
        if was == "seiten":
            return len(seiten)
        if was == "abbildungen":
            return len(self._abbildungen_liste(dok))
        if was == "tabellen":
            muster = r"(?m)^\s*(?:Tabelle|Tab\.?|Table)\s*(\d{1,2}[.\-]\d{1,3})\b"
            nummern = set()
            for s in seiten:
                for m in re.finditer(muster, s or "", re.I):
                    nummern.add(m.group(1).replace("-", "."))
            return len(nummern)
        try:
            import bestand as _b
            ang = _b.angaben(dok) or {}
        except Exception:
            ang = {}
        return ang.get(was) or ""

    def _fakten_antwort(self, frage, dok):
        """Seiten, Abbildungen, Tabellen, Verfasser, Jahr, Titel - gezaehlt
        aus dem PDF-Text und dem Katalog, ohne Modell. dok=None: Tabelle
        ueber alle Dokumente des Bereichs (allgemeine Funktion, kein
        Sonderfall fuer ein bestimmtes Dokument)."""
        was = assistent.dokument_fakten_frage(frage)
        if not was:
            return False
        if dok is None:
            namen = (titel_im_bereich(self.path, self.headers)
                     or nur_erlaubte(BESTAND.titel(), self.headers) or [])
            if not namen:
                return False
            spalte = {"seiten": "Seiten", "abbildungen": "Abbildungen (mit Unterschrift)",
                      "tabellen": "Tabellen", "verfasser": "Verfasser", "jahr": "Jahr",
                      "titel": "Titel"}[was]
            zeilen = []
            for n in sorted(namen)[:40]:
                w = self._fakten_zaehlen(n, was)
                zeilen.append("| %s | %s |" % (assistent._titel_saubern(n),
                                              "–" if w in (None, "") else w))
            text = ("**%s je Dokument** (%d im Bereich)\n\n| Kennung | %s |\n|---|---|\n%s"
                    % (spalte, len(namen), spalte, "\n".join(zeilen)))
            if len(namen) > 40:
                text += "\n\n*Die ersten 40 von %d.*" % len(namen)
            text += "\n\n📇 *Direkt aus PDF und Katalog — ohne Sprachmodell. Ein bestimmtes Dokument: Kennung oder Verfasser nennen.*"
            gespraech = GESPRAECHE.kennung(self.path, self.headers)
            self._festhalten("fakten", frage, text)
            GESPRAECHE.merken(gespraech, frage, "bestand", [])
            self._sende_strom([
                {"uuid": _neue_marke("fakten"), "type": "textResponseChunk",
                 "textResponse": text, "sources": [], "close": False, "error": False},
                {"uuid": _neue_marke("fakten"), "type": "textResponseChunk",
                 "textResponse": "", "sources": [], "close": True, "error": False},
            ])
            print("[Fakten] %s fuer %d Dokumente" % (was, len(namen)), file=sys.stderr, flush=True)
            return True
        schluessel = _pdf_schluessel(dok)
        if not schluessel or not dokument_erlaubt(schluessel, self.headers):
            return False
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            seiten = []
        try:
            import bestand as _b
            ang = _b.angaben(dok) or {}
        except Exception:
            ang = {}
        titel = assistent._titel_saubern(dok)
        kopf = "**%s**" % assistent.dokument_zeile(dok)
        if was == "seiten":
            text = "%s hat **%d Seiten** (gezählt im PDF)." % (kopf, len(seiten))
        elif was in ("abbildungen", "tabellen"):
            wort = "Abbildung" if was == "abbildungen" else "Tabelle"
            muster = (r"(?m)^\s*(?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*(\d{1,2}[.\-]\d{1,3})\b"
                      if was == "abbildungen" else
                      r"(?m)^\s*(?:Tabelle|Tab\.?|Table)\s*(\d{1,2}[.\-]\d{1,3})\b")
            nummern = {}
            if was == "abbildungen":
                for n_, s_, _u in self._abbildungen_liste(dok):
                    nummern.setdefault(n_, s_)
            else:
                for i, s in enumerate(seiten, 1):
                    for m in re.finditer(muster, s or "", re.I):
                        nummern.setdefault(m.group(1).replace("-", "."), i)
            if nummern:
                sortiert = sorted(nummern.items(), key=lambda kv: [int(x) for x in kv[0].split(".")])
                erste, letzte = sortiert[0], sortiert[-1]
                text = ("%s enthält **%d %sen mit Unterschrift** (%s %s auf S. %d bis %s %s auf S. %d)."
                        % (kopf, len(nummern), wort, wort, erste[0], erste[1], wort, letzte[0], letzte[1]))
                if was == "abbildungen":
                    text += " „Zeig mir Bild %s“ holt eine davon." % erste[0]
            else:
                text = "%s: keine %s mit nummerierter Unterschrift im Text gefunden." % (kopf, wort)
            text += "\n\n*Gezählt aus dem PDF-Text — %sen ohne nummerierte Unterschrift werden nicht erfasst.*" % wort
        elif was == "verfasser":
            text = ("%s — Verfasser: **%s**." % (kopf, ang.get("verfasser") or "im Katalog nicht hinterlegt"))
        elif was == "jahr":
            text = ("%s — Jahr: **%s**." % (kopf, ang.get("jahr") or "im Katalog nicht hinterlegt"))
        else:
            text = ("%s — Titel: **%s**." % (kopf, ang.get("titel") or titel))
        text += "\n\n📇 *Direkt aus PDF und Katalog — ohne Sprachmodell.*"
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        self._festhalten("fakten", frage, text)
        GESPRAECHE.merken(gespraech, frage, "normal", [{"title": dok}])
        self._sende_strom([
            {"uuid": _neue_marke("fakten"), "type": "textResponseChunk",
             "textResponse": text, "sources": [], "close": False, "error": False},
            {"uuid": _neue_marke("fakten"), "type": "textResponseChunk",
             "textResponse": "", "sources": [], "close": True, "error": False},
        ])
        print("[Fakten] %s zu %r" % (was, dok), file=sys.stderr, flush=True)
        return True

    def _faden_antwort(self, frage, dok, vorspann=""):
        """Eine Frage NUR aus dem Faden-Dokument beantworten (fadenfrage.py).
        True = beantwortet (auch "steht nicht drin"). False = normaler Weg."""
        schluessel = _pdf_schluessel(dok)
        if not schluessel or not dokument_erlaubt(schluessel, self.headers):
            return False
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            seiten = []
        if not seiten:
            return False
        gespraech = GESPRAECHE.kennung(self.path, self.headers)
        titel = assistent._titel_saubern(dok)
        begonnen = time.time()
        nummern, terme = fadenfrage.seiten_waehlen(frage, seiten)
        if not nummern:
            text = vorspann + fadenfrage.nichts_gefunden(titel, terme, frage)
            self._festhalten("faden", frage, text)
            GESPRAECHE.merken(gespraech, frage, "normal", [{"title": dok}])
            self._sende_strom([
                {"uuid": _neue_marke("faden"), "type": "textResponseChunk",
                 "textResponse": text, "sources": [], "close": False,
                 "error": False},
                {"uuid": _neue_marke("faden"), "type": "textResponseChunk",
                 "textResponse": "", "sources": [], "close": True,
                 "error": False},
            ])
            print("[Faden] nichts in %r zu %r" % (dok, frage[:50]),
                  file=sys.stderr, flush=True)
            return True
        self._strom_beginnen()
        stand = "faden-%d" % id(self)
        self._stand(stand, "Lese in *%s* die Seiten %s …"
                    % (titel, ", ".join(str(n) for n in nummern)))
        try:
            _modus = "kennwerte" if assistent.ist_kennwertfrage(frage) else "frage"
            roh = self._modell_fragen(
                fadenfrage.auftrag(frage, titel, nummern, seiten, modus=_modus),
                zeitgrenze=300, denken=(_modus == "kennwerte"))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            roh = ""
        self._stand_weg(stand)
        if not (roh or "").strip():
            text = vorspann + ("Die Antwort aus **%s** ist nicht zustande "
                               "gekommen (Modell antwortete nicht). Bitte "
                               "noch einmal fragen." % titel)
            ok = nein = 0
        else:
            text, ok, nein = fadenfrage.verlinken(roh.strip(), schluessel,
                                                  seiten, nummern)
            text = vorspann + text
        _schritte = len(GESPRAECHE.verlauf_kurz(gespraech, 10))
        text += "\n\n*Quelle: %s · S. %s%s%s*" % (
            titel, ", ".join(str(n) for n in nummern),
            (" · %d Zitat%s geprüft" % (ok + nein, "" if ok + nein == 1 else "e")) if (ok or nein) else "",
            (" · ⚠ %d nicht gefunden" % nein) if nein else "")
        if _schritte < 2:
            text += "\n" + assistent.naechste_schritte("faden", dok)
        self._festhalten("faden", frage, text)
        GESPRAECHE.merken(gespraech, frage, "normal", [{"title": dok}])
        self._strom_stueck(
            {"uuid": _neue_marke("faden"), "type": "textResponseChunk",
             "textResponse": text, "sources": [], "close": True,
             "error": False})
        self._strom_schliessen()
        print("[Faden] %r aus %r, Seiten %s, Zitate %d ok / %d nicht"
              % (frage[:40], dok, nummern, ok, nein), file=sys.stderr, flush=True)
        return True

    def _bild_beschreiben(self, unterschrift, seitentext):
        """Zwei, drei Saetze zur Abbildung - nur aus dem Seitentext. Wirft nie."""
        auftrag = (
            "Unten steht der Text einer Seite aus einem Fachdokument, darauf "
            "die Bildunterschrift „%s“. Beschreibe in zwei bis drei Sätzen, "
            "was diese Abbildung laut Unterschrift und Seitentext zeigt. Nur "
            "aus dem Text, nichts erfinden, keine Einleitung, keine "
            "Quellenangaben.\n\n%s" % ((unterschrift or "")[:200], seitentext[:3000]))
        try:
            roh = self._modell_fragen(auftrag, zeitgrenze=120)
        except Exception:
            return ""
        roh = (roh or "").strip()
        return roh if 20 < len(roh) < 1200 else ""

    def _e2b_antwort(self, frage):
        """B: Einfache 'Was ist X?'-Frage vom kleinen Modell (E2B) GROUNDED
        aus den woertlichen Fundstellen beantworten. True, wenn beantwortet.
        Bei JEDEM Zweifel (kein Zugang, keine distinkte Fundstelle, leere oder
        unsichere Antwort) -> False: dann laeuft die Frage den normalen Weg
        ueber das grosse Modell. Abschaltbar: KI4KI_E2B_ANTWORT=0."""
        if not E2B_ANTWORT or not _ist_definitionsfrage(frage):
            return False
        pruef = erlaubt_pruefer(self.headers)
        if pruef is None:
            return False
        try:
            BESTAND.aktualisiere()
            zusatz = wortsuche.zusatz_zur_frage(BESTAND, frage, erlaubt=pruef)
        except Exception:
            return False
        if not zusatz:
            return False   # keine distinkte Quelle -> grosses Modell
        auftrag = (
            "Du bist ein Nachschlagewerk. Beantworte die Frage KURZ (2-3 "
            "Saetze) und AUSSCHLIESSLICH aus den folgenden Fundstellen. Steht "
            "die Antwort nicht darin, antworte nur mit dem Wort NICHTS. "
            "Erfinde nichts und nenne bei jeder Aussage das Dokument in "
            "Klammern.\n\nFrage: %s\n\n%s" % (frage, zusatz))
        seit = time.time()
        try:
            roh = self._modell_fragen(auftrag, zeitgrenze=120,
                                      modell=assistent.NETZ_MODELL)
        except Exception:
            return False
        roh = (roh or "").strip()
        # Das Modell haelt sich nicht immer an "antworte NUR mit dem Wort
        # NICHTS" - gemessen: "Der Text enthaelt keine Informationen
        # darueber, was ein Wendelverteiler ist. NICHTS" - das Steuerwort
        # stand am ENDE und landete roh beim Nutzer. Fehlanzeige gilt
        # deshalb, sobald das grossgeschriebene Steuerwort irgendwo als
        # eigenes Wort steht; in einer echten Kurzantwort kommt es nicht
        # vor. Rueckfall bleibt das grosse Modell.
        if len(roh) < 25 or re.search(r"\bNICHTS\b", roh):
            return False   # Fail-safe -> grosses Modell
        namen = list(dict.fromkeys(re.findall(r"\[([^\],]+)", zusatz)))
        quellstaemme = {(t[:-3] if t.endswith(".md") else t) for t in namen}
        try:
            with PRUEFSPERRE:
                geprueft, pruefungen = veredeln.veredele(
                    roh, namen, BESTAND, belege_unten=True)
            geprueft = mit_verweisen(geprueft, pruefungen, quellstaemme)
            geprueft = marken_verlinken(geprueft, pruefungen)
            schnitt = geprueft.find("**Belege**")
            kopf = geprueft[:schnitt] if schnitt > 0 else geprueft
            rest = geprueft[schnitt:] if schnitt > 0 else ""
            kopf, wieviele = nennungen_verlinken(kopf, quellstaemme)
            geprueft = kopf + rest
            if wieviele:
                geprueft += "\n\n" + nennungshinweis(wieviele)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            geprueft = roh
        geprueft += ("\n\n---\n*\U0001F9E0 Kurzantwort vom kleinen Modell "
                     "**%s** \u00b7 %.1f\u00a0s*"
                     % (assistent.NETZ_MODELL, time.time() - seit))
        self._festhalten("e2b", frage, geprueft)
        self._sende_strom([
            {"uuid": _neue_marke("e2b"), "type": "textResponseChunk",
             "textResponse": geprueft, "sources": [],
             "close": False, "error": False},
            {"uuid": _neue_marke("e2b"), "type": "textResponseChunk",
             "textResponse": "", "sources": [],
             "close": True, "error": False},
        ])
        print("[E2B] Definitionsfrage grounded beantwortet: %r"
              % frage[:60], file=sys.stderr, flush=True)
        return True

    def _bestandsauskunft(self, frage, vorher=None):
        """Auskunft ueber den eigenen Bestand, ohne Suche und ohne Modell.

        "Welche Dokumente habt ihr?" ist fuer jeden neuen Nutzer die
        allererste Frage - und die einzige, die die Anlage bisher gar
        nicht beantworten konnte: Sie kennt den Inhalt einzelner
        Textstellen, aber nicht ihren eigenen Bestand.

        Rueckgabe True, wenn beantwortet. Bei False laeuft die Frage den
        gewoehnlichen Weg weiter - besser eine langsame Antwort als gar
        keine.
        """
        # KI4KI-TOR: Ohne Zugang zu diesem Bereich wird nichts
        # beantwortet - auch nicht "hilfsweise" aus dem Gesamtbestand.
        # Wortgleich mit AnythingLLM, damit der Unterschied nicht verraet,
        # dass der Bereich existiert.
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True

        titel = titel_im_bereich(self.path, self.headers)
        bereich = True
        if not titel:
            # Ohne Auskunft von AnythingLLM auf den Gesamtbestand
            # zurueckfallen - aber A2: nur auf den ERLAUBTEN Teil, sonst
            # zaehlt die Anlage fremde Titel auf.
            BESTAND.aktualisiere()
            titel = nur_erlaubte(BESTAND.titel(), self.headers)
            bereich = False
        text = assistent.bestandsauskunft(frage, titel,
                                          bereich=bereich or None,
                                          vorher=vorher, zusatz=self._bestand_zusatz(titel))
        if not text:
            return False
        self._festhalten("bestand", frage, text)
        if not bereich:
            text += ("\n\n*(Hinweis: Diese Liste umfasst den gesamten "
                     "Bestand, nicht nur diesen Arbeitsbereich.)*")
        text += _katalog_zeile()
        self._sende_strom([
            {"uuid": _neue_marke("bestand"), "type": "textResponseChunk",
             "textResponse": text, "sources": [],
             "close": False, "error": False},
            {"uuid": _neue_marke("bestand"), "type": "textResponseChunk",
             "textResponse": "", "sources": [],
             "close": True, "error": False},
        ])
        print("[Assistent] Bestandsauskunft: %d Titel" % len(titel),
              file=sys.stderr, flush=True)
        return True

    _sammeln = None      # Liste -> Sammelmodus (JSON-Weg): Stuecke werden gepuffert
    _CHAT_ZAEHLER = [0]

    def _abschluss_stueck(self, uuid, quellen=None, nutzung=None, ms=None):
        """Das letzte Stueck, wie AnythingLLM es sendet: mit Chat-Kennung (-> Daumen
        hoch/runter), Quellenliste (-> Quellenleiste) und Kennzahlen (-> graue
        Fusszeile). Gemessen 27.08.: ohne dieses Stueck fehlten alle drei bei
        jeder Antwort der Anlage. Dieselbe uuid wie die Antwort - sonst ordnet
        die Oberflaeche es nicht zu."""
        Griff._CHAT_ZAEHLER[0] += 1
        cid = -(2000000 + (int(time.time()) % 100000000) * 10 + (Griff._CHAT_ZAEHLER[0] % 10))
        metr = {}
        if nutzung and (nutzung.get("antwort") or nutzung.get("prompt")):
            dauer_s = max(0.001, (ms or nutzung.get("dauer_ms") or 0) / 1000.0)
            metr = {"prompt_tokens": int(nutzung.get("prompt") or 0), "completion_tokens": int(nutzung.get("antwort") or 0),
                    "total_tokens": int(nutzung.get("prompt") or 0) + int(nutzung.get("antwort") or 0),
                    "outputTps": round(int(nutzung.get("antwort") or 0) / dauer_s, 1), "duration": round(dauer_s, 2)}
        elif ms:
            metr = {"duration": round(ms / 1000.0, 2)}
        return {"uuid": uuid, "type": "finalizeResponseStream", "textResponse": "", "close": True, "error": False,
                "chatId": cid, "sources": quellen or [], "metrics": metr}

    def _quellen_fuer_oberflaeche(self, zustand):
        """Die beruehrten Seiten als Quellen fuer die Quellenleiste der Oberflaeche."""
        aus = []
        for dok in zustand.get("dokumente") or []:
            titel = assistent._titel_saubern(dok)
            seiten = (zustand.get("seiten") or {}).get(dok) or []
            if seiten:
                _sch, texte = _seitentexte_von(dok)
                for n in seiten[:4]:
                    t = (texte[n - 1] if 0 < n <= len(texte) else "") or ""
                    aus.append({"title": "%s · Seite %d" % (titel, n), "text": re.sub(r"\s+", " ", t)[:600], "chunkSource": "%s.pdf · Seite %d" % (titel, n)})
            else:
                aus.append({"title": titel, "text": "", "chunkSource": titel})
        return aus[:12]

    def _strom_beginnen(self):
        """Antwort in Stuecken senden (chunked).

        Ohne bestimmbare Laenge bricht der Browser unter HTTP/1.1 ab -
        deshalb die Stueckelung. Nur so kann waehrend der Arbeit schon
        etwas ankommen: Der Nutzer soll sehen, WORAN gerade gearbeitet
        wird, statt eine Minute lang drei Punkte anzustarren.
        """
        if self._sammeln is not None:
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def _strom_stueck(self, nachricht):
        if self._sammeln is not None:
            self._sammeln.append(nachricht)
            return
        roh = b"data: " + json.dumps(nachricht, ensure_ascii=False).encode() + b"\n\n"
        self.wfile.write(b"%x\r\n" % len(roh) + roh + b"\r\n")
        self.wfile.flush()

    def _strom_schliessen(self):
        if self._sammeln is not None:
            return
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _stand(self, uuid, text):
        """Zwischenstand anzeigen.

        AnythingLLM kennt dafuer eine eigene Nachrichtenart: statusResponse.
        Bei gleicher Kennung ersetzt die neue Meldung die vorige, und
        removeStatusResponse raeumt sie am Ende weg. Der Umweg ueber einen
        <think>-Block war falsch - davon stellte die Oberflaeche nur das
        erste Stueck dar und schrieb den Rest roh in die Antwort.
        """
        self._strom_stueck({"uuid": uuid, "type": "statusResponse",
                            "textResponse": text, "sources": [],
                            "close": True, "error": None, "animate": True})

    def _stand_weg(self, uuid):
        self._strom_stueck({"uuid": uuid, "type": "removeStatusResponse",
                            "content": "", "sources": [],
                            "close": True, "error": None})

    def _sende_strom(self, nachrichten, quellen=None, nutzung=None, ms=None):
        """SSE-Antwort ueber den chunked-Weg - GENAU wie die normalen
        Antworten (Bestandsauskunft, Zusammenfassung), damit der Sende-Knopf
        sauber zurueckspringt und die Formatierung greift. Der fruehere
        Content-Length-Weg liess das Frontend die Antwort nie als "fertig"
        erkennen: der Knopf blieb auf "Stop".
        """
        marke = _neue_marke("ki4ki")
        _hinw = _netz_hinweis_zeile()
        for n in nachrichten:
            if isinstance(n, dict) and n.get("type") in (
                    "textResponseChunk", "textResponse"):
                n["uuid"] = marke
                if _hinw and n.get("textResponse"):
                    n["textResponse"] = n["textResponse"] + _hinw
                    _hinw = ""
        self._strom_beginnen()
        for n in nachrichten:
            self._strom_stueck(n)
        # Das Frontend beendet das Laden (Sende-Knopf) NUR bei
        # finalizeResponseStream mit passender uuid - NICHT bei
        # close=True eines textResponseChunk. Ohne dies haengt der Knopf
        # auf "Stop".
        self._strom_stueck(self._abschluss_stueck(marke, quellen, nutzung, ms))
        self._strom_schliessen()

    # ------------------------------------------------------------ Einstiege
    # ------------------------------------------------- Fundstellen-Ansicht
    def _stelle(self, felder):
        """Die PDF-Seite als Bild, das belegte Zitat gelb hinterlegt."""
        dok = (felder.get("dok") or [""])[0]
        stamm = dok[:-4] if dok.endswith(".pdf") else dok
        try:
            seite = int((felder.get("seite") or ["1"])[0])
        except ValueError:
            seite = 1
        zitat = (felder.get("zitat") or [""])[0]
        stamm = _pdf_schluessel(stamm)
        if not stamm:
            self._sende_html("<p>Dieses Dokument liegt nicht vor.</p>", 404)
            return
        # KI4KI-TOR-STELLE: siehe _pdf. Die Fundstellenseite zeigt das
        # Zitat im Klartext und verlinkt das Seitenbild.
        if not dokument_erlaubt(stamm, self.headers):
            self._sende_html("<p>Dieses Dokument liegt nicht vor.</p>", 404)
            return
        gesamt = pdfstelle.seitenzahl(stamm) or seite
        seite = max(1, min(seite, gesamt))
        bild = "/seitenbild?dok=%s&seite=%d%s" % (
            quote(stamm), seite, "&zitat=" + quote(zitat[:400]) if zitat else "")
        vor = seite - 1 if seite > 1 else None
        zurueck = seite + 1 if seite < gesamt else None

        def blaettern(ziel, text):
            if not ziel:
                return '<span class="aus">%s</span>' % text
            return ('<a href="/stelle?dok=%s&seite=%d%s">%s</a>'
                    % (quote(stamm), ziel,
                       "&zitat=" + quote(zitat[:400]) if zitat else "", text))

        # Beim Blaettern steht die belegte Stelle nicht mehr auf der Seite.
        # Das muss dabeistehen, sonst sieht die fehlende Markierung nach
        # einem Defekt aus.
        hinweis = '<p class="lage">Keine Textstelle übergeben.</p>'
        if zitat:
            rechtecke, _ = pdfstelle.kaesten(stamm, seite, zitat)
            if rechtecke:
                hinweis = ('<p class="lage">Die belegte Stelle ist gelb '
                           'hinterlegt.</p>')
            elif not pdfstelle.hat_textlayer(stamm):
                # Gescanntes oder als Bild abgelegtes PDF. Hier waere
                # "steht nicht auf dieser Seite" schlicht falsch: Die
                # Stelle steht da, nur nicht maschinenlesbar. Der Text im
                # Bestand stammt aus Docling, gesucht wird im PDF-Text.
                hinweis = ('<p class="lage weg">Dieses PDF enthält keinen '
                           'durchsuchbaren Text — es ist gescannt oder als '
                           'Bild abgelegt. Die belegte Stelle lässt sich '
                           'deshalb nicht hervorheben. Sie steht auf der '
                           'Seite, ist maschinell aber nicht auffindbar; '
                           'bitte mit dem Auge nachsehen.</p>')
            else:
                belegseite, _ = pdfstelle.finde_seite(stamm, zitat)
                text = ("Auf dieser Seite steht die belegte Stelle nicht — "
                        "sie ist auf Seite %d." % belegseite if belegseite
                        else "Auf dieser Seite steht die belegte Stelle nicht.")
                if belegseite and belegseite != seite:
                    text += (' <a href="/stelle?dok=%s&seite=%d&zitat=%s">'
                             'zur richtigen Seite springen</a>' % (
                                 quote(stamm), belegseite, quote(zitat[:400])))
                hinweis = '<p class="lage weg">⚠ %s</p>' % text

        self._sende_html(STELLE.format(
            dok=html.escape(stamm), seite=seite, gesamt=gesamt, bild=bild,
            zurueck=blaettern(vor, "← vorherige Seite"),
            vor=blaettern(zurueck, "nächste Seite →"),
            pdf="/pdf/%s#page=%d" % (quote(stamm), seite),
            hinweis=hinweis))

    def _abbildung(self, felder):
        """Die freigestellte Abbildung einer Seite als PNG.

        ⚠ Rechte wie beim Seitenbild: Ein Bild aus einem Dokument ist
          dasselbe wie das Dokument.
        """
        stamm = (felder.get("dok") or [""])[0]
        stamm = _pdf_schluessel(stamm)
        if not stamm:
            self._fehler(404, "unbekanntes Dokument")
            return
        # ⚠ dokument_erlaubt ist eine Funktion des MODULS mit zwei
        #   Argumenten, keine Methode. Der erste Einbau schrieb
        #   self.dokument_erlaubt(stamm) - die Route stuerzte bei JEDEM
        #   Aufruf ab, und im Chat blieb das Bild leer. Genauso wie
        #   _seitenbild es macht:
        if not dokument_erlaubt(stamm, self.headers):
            self._fehler(404, "unbekanntes Dokument")
            return
        try:
            seite = int((felder.get("seite") or ["1"])[0])
        except ValueError:
            seite = 1
        pfad = PDFS.get(stamm)
        try:
            import abbildung
            daten, was = abbildung.freistellen(pfad, seite)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            daten, was = None, "Fehler beim Freistellen"
        if not daten:
            print("[Abbildung] %s S.%d: %s" % (stamm, seite, was),
                  file=sys.stderr, flush=True)
            self._fehler(404, str(was))
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)

    def _seitenbild(self, felder):
        dok = (felder.get("dok") or [""])[0]
        stamm = dok[:-4] if dok.endswith(".pdf") else dok
        try:
            seite = int((felder.get("seite") or ["1"])[0])
        except ValueError:
            seite = 1
        zitat = (felder.get("zitat") or [""])[0] or None
        stamm = _pdf_schluessel(stamm)
        if not stamm:
            self._fehler(404, "unbekanntes Dokument")
            return
        # KI4KI-TOR-DATEI: Angemeldet zu sein genuegt nicht - das
        # Dokument muss in einem Bereich dieser Anmeldung liegen.
        # Mit 404 abweisen, nicht mit 403: ein 403 verraet, dass es
        # das Dokument gibt.
        if not dokument_erlaubt(stamm, self.headers):
            self._fehler(404, "unbekanntes Dokument")
            return
        try:
            daten = pdfstelle.seitenbild(stamm, seite, zitat)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self._fehler(500, str(e))
            return
        if not daten:
            self._fehler(404, "Seite liess sich nicht darstellen")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(daten)

    def _sende_html(self, inhalt, code=200):
        roh = inhalt.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(roh)

    def _thread_benennen(self, ws, th, frage):
        """Einen frischen Thread aus der ersten Frage benennen - nur wenn er
        bei AnythingLLM noch KEINEN Verlauf hat (also mit einer direkten
        Antwort begann). Ueber AnythingLLMs eigene Schnittstelle, KEIN
        DB-Schreiben, kein Ueberschreiben bestehender Namen. Wirft nie."""
        try:
            name = " ".join((frage or "").split())
            if len(name) < 8:
                return
            basis = ZIEL + "/api/workspace/" + ws + "/thread/" + th
            req = urllib.request.Request(basis + "/chats", method="GET")
            for _k in ("Authorization", "Cookie"):
                if self.headers.get(_k):
                    req.add_header(_k, self.headers.get(_k))
            with urllib.request.urlopen(req, timeout=8) as r:
                hist = (json.loads(r.read()) or {}).get("history") or []
            if hist:
                return
            leib = json.dumps({"name": name[:48]}).encode()
            req2 = urllib.request.Request(basis + "/update", data=leib,
                                          method="POST")
            req2.add_header("Content-Type", "application/json")
            for _k in ("Authorization", "Cookie"):
                if self.headers.get(_k):
                    req2.add_header(_k, self.headers.get(_k))
            urllib.request.urlopen(req2, timeout=8).read()
            print("[Thread] benannt: %r" % name[:48], file=sys.stderr, flush=True)
        except Exception:
            pass

    def _verlauf(self):
        """Verlauf laden und die gemerkten gepruefton Fassungen einsetzen."""
        req = urllib.request.Request(ZIEL + self.path, method="GET")
        for k, v in self.headers.items():
            # ⭐ If-None-Match/If-Modified-Since NICHT weiterreichen.
            #   Sonst antwortet AnythingLLM mit 304 (sein eigener, bei reinen
            #   Direkt-Antwort-Threads leerer Body) und die eingeblendeten
            #   Antworten kaemen nie an (ETag/304-Falle).
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding",
                                 "if-none-match", "if-modified-since"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                kopf = dict(r.headers)
                roh = r.read()
                code = r.status
        except urllib.error.HTTPError as e:
            daten = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type",
                             e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
            return
        except Exception as e:
            self._fehler(502, str(e))
            return

        try:
            daten = json.loads(roh)
            n = verlauf_veredeln(daten)
            if n:
                print("[Verlauf] %d Antworten aus dem Gedaechtnis ersetzt" % n,
                      file=sys.stderr, flush=True)
                roh = json.dumps(daten, ensure_ascii=False).encode()
            try:
                _mth = re.match(r"^/api/(?:v1/)?workspace/([^/]+)"
                                r"(?:/thread/([^/]+))?", self.path or "")
                _ws = _mth.group(1) if _mth else ""
                _th = (_mth.group(2) if (_mth and _mth.group(2)) else "default")
                _gesp = _nachtrag_alle().get(_ws + "|" + _th) or []
                if _gesp and isinstance(daten, dict) and isinstance(daten.get("history"), list):
                    daten["history"], _z = _nachtrag_einblenden(daten["history"], _gesp)
                    if _z:
                        print("[Verlauf] %d direkte Antworten eingeblendet" % _z,
                              file=sys.stderr, flush=True)
                        roh = json.dumps(daten, ensure_ascii=False).encode()
                # ⭐ "arbeitet noch"-Platzhalter, solange keine Antwort da ist
                _arb = _arbeitet_alle().get(_ws + "|" + _th)
                if _arb and isinstance(daten, dict) \
                        and isinstance(daten.get("history"), list):
                    _hist = daten["history"]
                    _fertig = (bool(_hist) and isinstance(_hist[-1], dict)
                               and _hist[-1].get("role") == "assistant")
                    if _fertig or (time.time() - (_arb.get("wann") or 0) > 300):
                        _arbeitet_weg(_ws + "|" + _th)
                    else:
                        _w = int(_arb.get("wann") or 0)
                        if not _hist:
                            _hist.append({"role": "user",
                                          "content": _arb.get("frage") or "",
                                          "sentAt": _w, "attachments": [],
                                          "chatId": -999998})
                        _hist.append({"type": "chart", "role": "assistant",
                                      "content": ARBEITET_TEXT, "sources": [],
                                      "chatId": -999998, "sentAt": _w + 1,
                                      "feedbackScore": None, "metrics": {}})
                        roh = json.dumps(daten, ensure_ascii=False).encode()
            except Exception:
                traceback.print_exc(file=sys.stderr)
        except Exception:
            pass          # kein JSON oder unerwarteter Aufbau: unveraendert

        self.send_response(code)
        if code == 200:
            # Den Verlauf bekommt nur, wer angemeldet ist - AnythingLLM hat
            # das gerade entschieden. Also darf diese Sitzung auch die
            # Original-PDFs sehen.
            # KI4KI-MARKE-MERKEN: Jetzt liegt eine gueltige Anmeldung vor -
            # der einzige Zeitpunkt, zu dem sich die erlaubten Dokumente
            # ermitteln lassen. Beim spaeteren Klick auf einen Beleg
            # schickt der Browser nur noch dieses Cookie.
            _kennung = ""
            try:
                _ausweis = ((self.headers.get("Authorization") or "") + "|"
                            + (self.headers.get("Cookie") or ""))
                if _ausweis.strip("|"):
                    _kennung = hashlib.sha256(
                        _ausweis.encode()).hexdigest()[:16]
                    # fuellt _DOKZUGANG[_kennung]
                    erlaubte_dokumente(self.headers)
                    _k = pruefprotokoll.konto_aus(self.headers)
                    if _k and not _k.startswith(("sitzung-", "dienst-", "unbekannt")):
                        _KONTEN_JE_MARKE[_kennung] = (_k, time.time())
                        _konten_speichern()
            except Exception:
                traceback.print_exc(file=sys.stderr)
            self.send_header("Set-Cookie",
                             "ki4ki_zugang=%s; Path=/; Max-Age=%d; "
                             "HttpOnly; SameSite=Lax"
                             % (marke_bauen(_kennung), ZUGANG_DAUER))
        # ⭐ ETag/Cache nicht durchreichen. Der Browser wuerde sonst
        #   den injizierten Verlauf unter AnythingLLMs (leerem) ETag cachen
        #   und beim naechsten Mal 304 revalidieren -> wieder leer.
        self.send_header("Cache-Control", "no-store")
        for k, v in kopf.items():
            if k.lower() not in ("transfer-encoding", "connection",
                                 "content-length", "etag", "cache-control",
                                 "last-modified", "expires"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(roh)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(roh)

    def do_GET(self):
        _konto_merken(self.headers)
        pfad = self.path.split("?")[0].split("#")[0]
        felder = parse_qs(urlparse(self.path).query)
        if VERLAUF.match(pfad):
            self._verlauf()
            return
        if pfad == "/protokoll" or pfad.startswith("/protokoll/"):
            self._protokoll(pfad, felder)
            return
        if pfad in ("/rueckmeldungen", "/kpi", "/selbstcheck"):
            self._kennzahlen_seite(pfad, felder)
            return
        if pfad == "/rolle":
            # Die gespeicherten Angaben eines Bereichs (fuer die Felder in den Einstellungen)
            slug = re.sub(r"[^A-Za-z0-9_-]", "", (felder.get("slug") or [""])[0])[:80]
            if not slug or not darf_sehen(self.headers) or not bereich_sichtbar("/api/workspace/%s" % slug, self.headers):
                self._json({"ok": False}, code=404)
                return
            r = (_bereich_konf(slug).get("rolle") or {})
            self._json({"ok": True, "slug": slug, "fach": r.get("fach", ""), "nutzer": r.get("nutzer", ""),
                        "besonderes": r.get("besonderes", ""), "modus": r.get("modus", ""),
                        "eingerichtet": rolle.ist_eingerichtet(_rolle_lesen(slug)), "darf": _darf_rolle_setzen(self.headers)})
            return
        if pfad in ("/stelle", "/seitenbild", "/abbildung") or pfad.startswith("/pdf/"):
            # Diese Routen beantwortet der Proxy selbst - AnythingLLM sieht sie
            # nie und kann sie deshalb auch nicht schuetzen.
            if not darf_sehen(self.headers):
                self._fehler(401, "Nicht angemeldet. Bitte zuerst in der "
                                  "Oberflaeche anmelden.")
                return
        if pfad == "/stelle":
            self._stelle(felder)
            return
        if pfad == "/abbildung":
            self._abbildung(felder)
            return
        if pfad == "/seitenbild":
            self._seitenbild(felder)
            return
        if pfad.startswith("/pdf/"):
            self._pdf(unquote(pfad[5:]))
            return
        if pfad == "/pruef-strom-test":
            # Prueft die Stueckelung des Datenstroms, ohne das Modell zu
            # bemuehen. Ein kaputter Strom faellt sonst erst beim Nutzer auf.
            self._strom_beginnen()
            self._stand("test", "Durchsuche 715 Dokumente …")
            self._stand("test", "4 Textstellen aus 2 Arbeiten …")
            self._stand_weg("test")
            self._strom_stueck({"uuid": _neue_marke("test"), "type": "textResponseChunk",
                                "textResponse": "Fertig.", "sources": [],
                                "close": False, "error": False})
            self._strom_stueck({"uuid": _neue_marke("test"), "type": "textResponseChunk",
                                "textResponse": "", "sources": [],
                                "close": True, "error": False})
            self._strom_schliessen()
            return
        if pfad == "/pruef-status":
            # Live zaehlen, nicht den Startzustand: Auf einer frischen
            # Anlage waren beide Zahlen sonst so lange 0, bis jemand den
            # Proxy neu startete - und die 0 sah aus wie ein Defekt.
            try:
                BESTAND.aktualisiere()
            except Exception:
                pass
            _pdfs_erneuern_wenn_faellig()
            if time.time() - GPU_STAND.get("wann", 0) > 300:
                try:
                    _gpu_pruefen()
                except Exception:
                    pass
            daten = json.dumps({"bestand": len(BESTAND.titel()),
                                "verwaiste_bereiche": list(VERWAISTE_BEREICHE),
                                "pdfs": len(PDFS),
                                "gpu": {"modelle": GPU_STAND.get("modelle"), "warnung": GPU_STAND.get("warnung")}},
                               ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(daten)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(daten)
            return
        self._weiterleiten("GET")

    # ------------------------------------------------------- Hochladen-Knopf
    def _upload(self, bereich):
        """Datei aus der Oberflaeche in den Eingangsordner legen."""
        if not angemeldet(self.headers):
            self._json({"success": False,
                        "error": "Nicht angemeldet. Bitte in der Oberflaeche "
                                 "anmelden und erneut versuchen."}, code=401)
            return
        # KI4KI-TOR-UPLOAD: Angemeldet zu sein genuegt NICHT. Ohne diese
        # Pruefung konnte ein Konto in jeden beliebigen Arbeitsbereich
        # hochladen - auch in einen, den es nicht einmal oeffnen darf.
        # Lesen konnte es dort nichts, aber Dokumente EINSCHLEUSEN. In
        # einer Anlage, die jede Aussage belegt, heisst das: Belege
        # faelschen. Vom Wegabgleich gefunden.
        # Wortgleiche Antwort wie AnythingLLM, damit der Unterschied nicht
        # verraet, dass der Bereich existiert.
        if not bereich_sichtbar("/api/workspace/%s" % bereich, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return
        try:
            laenge = int(self.headers.get("Content-Length") or 0)
            if laenge > HOECHSTGROESSE:
                self._json({"success": False,
                            "error": "Die Datei ist zu gross (%.0f MB). "
                                     "Hoechstens %.0f MB - groessere Arbeiten "
                                     "bitte ueber den Eingangsordner."
                                     % (laenge / 1048576.0,
                                        HOECHSTGROESSE / 1048576.0)},
                           code=413)
                return
            roh = self.rfile.read(laenge) if laenge else b""
            art = self.headers.get("Content-Type") or ""
            dateien = _dateien_aus_formular(roh, art)
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            self._json({"success": False,
                        "error": "Die Datei konnte nicht gelesen werden: %s"
                                 % str(e)[:150]})
            return

        if not dateien:
            self._json({"success": False,
                        "error": "Es war keine Datei in der Anfrage."})
            return

        # In input/, nicht daneben: Jeder Arbeitsbereich hat
        # vier Unterordner, und abgeholt wird nur aus input/.
        ziel = os.path.join(EINGANG_ORDNER, _ordnername(bereich), "input")
        try:
            # Die ganze Struktur, nicht nur input/: Ein Arbeitsbereich, der
            # zum ersten Mal etwas bekommt, richtet sich damit selbst ein.
            # Sonst muesste fuer jeden neuen Partner jemand auf dem Server
            # Ordner anlegen - genau der Handgriff, den das Paket vermeiden
            # soll.
            wurzel = os.path.dirname(ziel)
            for unter in ("input", "parkplatz", "archiv", "aussortiert", "loeschen"):
                os.makedirs(os.path.join(wurzel, unter), exist_ok=True)
            # ⭐ bereich.json anlegen, falls sie fehlt. Ohne sie bricht die
            #   Aufnahme im Node "Bereichskarte bauen" ab ("Keine bereich.json
            #   gefunden") - auf einer FRISCHEN Anlage legt sie sonst niemand
            #   an, und der erste Durchgang scheitert. Sie verknuepft den
            #   Ordner <slug> mit dem AnythingLLM-Ablageordner; fuer einen neu
            #   angelegten Bereich ist beides der slug.
            _konf = os.path.join(wurzel, "bereich.json")
            if not os.path.exists(_konf):
                _slug = _ordnername(bereich)
                with open(_konf, "w", encoding="utf-8") as fh:
                    json.dump({"bereich": _slug, "ablage": _slug}, fh,
                              ensure_ascii=False)
            # Der Proxy laeuft als root, n8n als node (1000). Frisch
            # angelegte Ordner gehoeren sonst root - dann kann n8n hier
            # keine Datei nach archiv/ verschieben, und die Aufnahme eines
            # NEU angelegten Bereichs scheitert still. Also den Ordner
            # gleich an node uebergeben. Nur-lesbar? Dann sind wir nicht
            # root (Entwicklung); der Rechte-Vorlauf beim Start faengt es.
            # Gruppe = die des Server-Nutzers (KI4KI_GID aus der .env), Modus
            # 2775 mit setgid: n8n (1000) verschiebt, der Mensch legt per
            # SFTP Dateien ab. Mit 1000:1000/755 war ihm sein eigener
            # Dokumentordner verschlossen ("Uebertragung konnte nicht
            # gestartet werden").
            try:
                _gid = int(os.environ.get("KI4KI_GID") or 1000)
            except ValueError:
                _gid = 1000
            try:
                for _p in [wurzel] + [os.path.join(wurzel, u) for u in
                                      ("input", "parkplatz", "archiv", "aussortiert", "loeschen")]:
                    os.chown(_p, 1000, _gid)
                    os.chmod(_p, 0o2775)
                os.chown(_konf, 1000, _gid)
                os.chmod(_konf, 0o664)
            except (PermissionError, OSError):
                pass
        except Exception as e:
            self._json({"success": False,
                        "error": "Eingangsordner nicht beschreibbar: %s"
                                 % str(e)[:150]})
            return

        # Schon im Bestand? Dann sofort sagen, statt stumm abzulegen.
        # Beispiel: DS-00-000.pdf wurde hochgeladen, lag aber bereits
        # byteweise identisch im Bestand. Die Kette wies es korrekt ab, aber
        # in der Oberflaeche stand nichts und die Datei blieb im Eingang
        # liegen. Die Abweisung war richtig, das Schweigen war der Fehler.
        #
        # ⚠ Faellt die Pruefung aus, wird NICHT blockiert: Eine Stoerung im
        #   Bestand darf das Hochladen nicht verhindern. Dann geht es wie
        #   bisher weiter - die Kette faengt die Dublette ohnehin ab.
        # ⚠ NUR IM EIGENEN BEREICH VERGLEICHEN.
        #   Die erste Fassung nahm BESTAND.titel() - das sind alle 1253
        #   Titel ueber alle Ablagen hinweg, und ein Dokument traegt keine
        #   Herkunft. Gemessen: Ein Dokument aus einem Bereich haette
        #   den Upload in jeden anderen Bereich abgewiesen, auch in einen
        #   leeren. Fuers Partnerpaket waere das ein Auslieferungshindernis
        #   - und die Meldung haette die Existenz eines fremden Dokuments
        #   verraten, das der Nutzer gar nicht sehen darf.
        #
        #   Welcher Ablageordner zu diesem Bereich gehoert, steht in
        #   bereich.json ("ablage") - dieselbe Quelle, aus der auch die
        #   Aufnahmekette ihr Ziel nimmt (Bereich -> zugehoeriger Ablageordner).
        bekannt = {}
        try:
            ablage = _ordnername(bereich)
            konf = os.path.join(wurzel, "bereich.json")
            if os.path.exists(konf):
                with open(konf, encoding="utf-8") as fh:
                    ablage = (json.load(fh).get("ablage") or ablage)
            ordner = os.path.join(BESTAND_ORDNER, ablage)
            for eintrag in os.listdir(ordner):
                if not eintrag.endswith(".json"):
                    continue
                # <titel>.md-<kennung>.json  ->  <titel>
                roh = eintrag.split(".md-")[0]
                schluessel = pdfstelle._wie_anythingllm(roh)
                if schluessel:
                    bekannt.setdefault(schluessel, roh)
        except Exception:
            # Kein Ablageordner (neuer Bereich) oder nicht lesbar: dann wird
            # nicht geprueft und normal abgelegt. Die Aufnahmekette faengt
            # eine Dublette ohnehin ab - eine Stoerung darf das Hochladen
            # nicht verhindern.
            bekannt = {}

        namen = []
        doppelt = []
        in_arbeit = []
        geaendert = []
        for name, inhalt in dateien:
            # ⭐ Name saeubern, BEVOR irgendetwas damit passiert. Der Name
            #   taucht spaeter an sechs Stellen auf - Platte, Docling,
            #   Markdown, Arbeitsbereich, Belegadresse, Wortverzeichnis -
            #   und jede geht anders mit ihm um. Was hier durchrutscht,
            #   muss spaeter an sechs Stellen ausgebuegelt werden.
            sicher, was = namen_pruefen.saeubern(
                os.path.basename(name).replace("\\", "_"))
            if was:
                geaendert.append((os.path.basename(name), sicher, was))
                print("[Upload] Name gesaeubert: %r -> %r (%s)"
                      % (os.path.basename(name), sicher, ", ".join(was)),
                      file=sys.stderr, flush=True)
            if not sicher:
                continue
            schon = bekannt.get(
                pdfstelle._wie_anythingllm(os.path.splitext(sicher)[0]))
            if schon:
                doppelt.append((sicher, schon))
                continue
            # ⭐ INHALTS-DUBLETTE, byteweise. Genau so entstanden auf einer
            #   frischen Anlage drei Fassungen desselben Dokuments
            #   (Original, "-1", "-2"): Waehrend die erste noch aufbereitet
            #   wurde, kam derselbe Klick noch zweimal - der Namensvergleich
            #   oben griff nicht (noch nichts im Bestand), und die
            #   Umbenennung machte aus jeder Kopie ein "neues" Dokument.
            gleich = _inhaltsgleich(wurzel, inhalt)
            if gleich:
                unter, vorhanden = gleich
                if unter == "archiv":
                    doppelt.append((sicher, vorhanden))
                else:
                    in_arbeit.append((sicher, vorhanden))
                print("[Upload] Inhalts-Dublette: %s = %s/%s"
                      % (sicher, unter, vorhanden),
                      file=sys.stderr, flush=True)
                continue
            # nicht ueberschreiben: sonst ist eine gleichnamige aeltere Fassung
            # weg, bevor jemand sie vermisst
            stamm, endung = os.path.splitext(sicher)
            kandidat, n = sicher, 1
            while os.path.exists(os.path.join(ziel, kandidat)):
                kandidat = "%s-%d%s" % (stamm, n, endung)
                n += 1
            with open(os.path.join(ziel, kandidat), "wb") as fh:
                fh.write(inhalt)
            namen.append(kandidat)
            print("[Upload] %s -> %s" % (kandidat, ziel),
                  file=sys.stderr, flush=True)

        # Bescheid sagen, dass etwas angekommen ist.
        #
        # Frueher legte der Hochladen-Knopf die Datei nur ab und
        # sagte niemandem Bescheid. Gemerkt hat es erst der naechste Lauf
        # von n8n - also bis zu fuenf Minuten spaeter, und nur solange
        # jener Ablauf ueberhaupt eingeschaltet ist. Dabei ist der
        # Waechter genau dafuer gebaut: Er sieht im Schlaf alle 15
        # Sekunden nach dieser Notiz nach ("Ohne das wartet ein Upload bis
        # zu zehn Minuten", waechter.sh).
        #
        # Der Umweg ueber eine Datei ist Absicht und keine Bequemlichkeit:
        # Der Proxy laeuft als uid 1001 und koennte den Zyklus, der
        # Docker-Container steuert, gar nicht selbst starten.
        if namen:
            grund = "Upload: %s" % ", ".join(namen[:3])
            ok, meldung = anstoss_ablegen(grund)
            print("[Upload] Anstoss: %s" % meldung,
                  file=sys.stderr, flush=True)
            # Und, falls eingestellt, n8n direkt anrufen - im Partner-Paket
            # gibt es keinen Waechter, der die Datei je lesen wuerde.
            if AUFNAHME_HAKEN:
                ok2, meldung2 = aufnahme_anstossen(grund)
                print("[Upload] Aufnahme: %s" % meldung2,
                      file=sys.stderr, flush=True)

        # Alles waren Dubletten: nichts abgelegt - und das wird gesagt.
        if (doppelt or in_arbeit) and not namen:
            saetze = []
            if len(doppelt) == 1:
                saetze.append(
                    "\u201e%s\u201c liegt bereits in diesem Arbeitsbereich "
                    "(als \u201e%s\u201c)."
                    % (doppelt[0][0],
                       assistent._titel_saubern(doppelt[0][1])))
            elif doppelt:
                saetze.append(
                    "Diese %d Dateien liegen bereits in diesem Arbeitsbereich: "
                    "%s." % (len(doppelt),
                             ", ".join(d[0] for d in doppelt[:8])))
            if len(in_arbeit) == 1:
                saetze.append(
                    "\u201e%s\u201c wurde bereits hochgeladen und wird gerade "
                    "aufbereitet \u2014 es erscheint von selbst, bitte nicht "
                    "erneut hochladen." % in_arbeit[0][0])
            elif in_arbeit:
                saetze.append(
                    "Diese %d Dateien wurden bereits hochgeladen und werden "
                    "gerade aufbereitet: %s \u2014 bitte nicht erneut "
                    "hochladen." % (len(in_arbeit),
                                    ", ".join(d[0] for d in in_arbeit[:8])))
            saetze.append("Es wurde nichts hochgeladen.")
            text = " ".join(saetze)
            print("[Upload] abgewiesen, Dublette: %s"
                  % ", ".join(d[0] for d in (doppelt + in_arbeit)[:8]),
                  file=sys.stderr, flush=True)
            # ⚠ 409, NICHT 200. Die Oberflaeche entscheidet am HTTP-Status,
            #   nicht am Inhalt. Mit 200 sieht der Nutzer ein gruenes Haken und liest den Text
            #   NIE. Genau so passiert: Die Abweisung griff, die
            #   Meldung ging raus - und der Nutzer sah ein Haken.
            # 200/Erfolg statt 409: sonst roter Fehler-Chip. Der Hinweis
            # (liegt bereits, nichts hochgeladen) kommt als Karten-Text ueber
            # ki4ki_hinweis; ki4ki_dublette steuert die Farbe. Nichts abgelegt.
            self._json({"success": True, "error": None, "documents": [],
                        "ki4ki_hinweis": text, "ki4ki_dublette": True},
                       code=200)
            return

        # Die Oberflaeche kennt nur zwei Zustaende:
        # Gruenes Haken OHNE Text (2xx) - oder roter Kasten MIT Text (4xx/5xx).
        # Ein drittes
        # "laeuft gerade" gibt es nicht.
        #
        # Entscheidung: lieber der rote Kasten mit der
        # Wahrheit als das gruene Haken, das "fertig" behauptet. Der
        # Irrtum sonst: man laedt hoch und denkt, es sei direkt da.
        # Der Text beginnt mit einem Haken, damit er nicht wie
        # ein Fehler wirkt.
        #
        # ⚠ 425 statt 200: 202 waere semantisch richtig, ist aber 2xx und
        #   damit fuer die Oberflaeche "fertig". Diese Route benutzt NUR die
        #   Oberflaeche - im Quelltext der Anwendung nachgesehen.
        teile = []
        for name in namen:
            seiten = 0
            if name.lower().endswith(".pdf"):
                try:
                    seiten = _pdf_seiten(os.path.join(ziel, name))
                except Exception:
                    traceback.print_exc(file=sys.stderr)
            # ⚠ Wenn der Name gesaeubert wurde, MUSS es dastehen. Ein
            #   Werkzeug, das im Stillen umbenennt, ist schlimmer als
            #   eines, das es gar nicht tut - der Mensch sucht sonst nach
            #   einem Namen, den es nicht mehr gibt.
            hinweis = next((w for a, s, w in geaendert if s == name), None)
            teile.append("%s%s%s" % (
                name, " (%d Seiten)" % seiten if seiten else "",
                " \u2014 Name bereinigt: %s" % ", ".join(hinweis) if hinweis else ""))
            print("[Upload] %s: %s Seiten" % (name, seiten),
                  file=sys.stderr, flush=True)

        # Die Oberflaeche kennt nur zwei Zustaende:
        # Gruenes Haken OHNE Text (2xx) - oder roter Kasten MIT Text (4xx/5xx).
        # Ein drittes
        # "laeuft gerade" gibt es nicht. Deshalb 425 statt 200: Ein gruenes
        # Haken behauptet "fertig", und genau das ist der Irrtum, den die
        # Meldung ausraeumen soll.
        self._json({"success": True, "error": None, "documents": [], "ki4ki_hinweis":
                    # ⚠ Kurz halten. Die alte Fassung war 330 Zeichen lang
                    #   und erklaerte in fuenf Nebensaetzen, warum der Weg
                    #   so gewollt ist - das interessiert beim Hochladen
                    #   niemanden. Es bleibt, was der Mensch WISSEN MUSS.
                    "\u2713 %s wurde angenommen und wird jetzt aufbereitet "
                    "(Seiten, Formeln, Abbildungen). Das Dokument erscheint "
                    "danach von selbst hier \u2014 bitte nicht erneut "
                    "hochladen."
                    % ", ".join(teile)
                    # Gemischter Fall: manches angenommen, manches Dublette.
                    # Ohne diesen Satz verschwaenden die uebergangenen
                    # Dateien wortlos - der Mensch wartet dann auf ein
                    # Dokument, das nie kommt.
                    + ("" if not (doppelt or in_arbeit) else
                       " \u00dcbergangen, weil schon vorhanden oder in "
                       "Aufbereitung: %s."
                       % ", ".join(d[0] for d in (doppelt + in_arbeit)[:8]))},
                   code=200)

    def _bereich_neu(self):
        """Neuen Bereich anlegen lassen und ihn danach absichern.

        KI4KI-BEREICH-HEILEN. Das Anlegen wird unveraendert an AnythingLLM
        weitergereicht und die Antwort 1:1 zurueckgegeben - die Oberflaeche
        merkt nichts. ERST danach bekommt der frische Bereich die
        gepruef-ten Werte. Scheitert das, bleibt der Bereich eben blank;
        das Anlegen selbst ist nie gefaehrdet.
        """
        koerper = self._koerper()
        req = urllib.request.Request(ZIEL + self.path, data=koerper,
                                     method="POST")
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                status = r.status
                daten = r.read()
                kopf = [(k, v) for k, v in r.headers.items()
                        if k.lower() not in ("transfer-encoding",
                                             "connection", "content-length")]
        except urllib.error.HTTPError as e:
            status = e.code
            daten = e.read()
            kopf = [(k, v) for k, v in e.headers.items()
                    if k.lower() not in ("transfer-encoding",
                                         "connection", "content-length")]
        except Exception as e:
            self._fehler(502, str(e))
            return
        self.send_response(status)
        for k, v in kopf:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(daten)
        except Exception:
            pass
        # Antwort ist raus, Oberflaeche zufrieden - JETZT absichern.
        try:
            if status in (200, 201):
                w = (json.loads(daten or b"{}") or {}).get("workspace") or {}
                w = w[0] if isinstance(w, list) else w
                bereich_setzen((w or {}).get("slug"))
                bereich_ordner_anlegen((w or {}).get("slug"))
        except Exception:
            traceback.print_exc(file=sys.stderr)

    def _parse_mitschnitt(self, slug):
        """AnythingLLMs /parse normal durchreichen UND den Text der
        angehaengten Datei fuer die naechste Chat-Frage merken (Weg A)."""
        laenge = int(self.headers.get("Content-Length") or 0)
        roh = self.rfile.read(laenge) if laenge else b""
        # ZUERST merken (vor der Antwort), damit die sofort folgende Chat-Frage
        # den Text garantiert schon vorfindet - kein Wettlauf.
        try:
            dateien = _dateien_aus_formular(
                roh, self.headers.get("Content-Type") or "")
            if dateien:
                name, inhalt = dateien[0]
                text = _tika_text(inhalt)
                if text and text.strip():
                    _voll = text.strip()
                    _ANHANG[slug] = {"text": _voll[:_ANHANG_MAX],
                                     "roh_len": len(_voll),
                                     "name": os.path.basename(name),
                                     "wann": time.time()}
                    print("[Anhang] '%s' gemerkt fuer %s (%d Zeichen)"
                          % (name, slug, len(text)),
                          file=sys.stderr, flush=True)
        except Exception:
            traceback.print_exc(file=sys.stderr)
        req = urllib.request.Request(ZIEL + self.path, data=roh, method="POST")
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection",
                                 "accept-encoding"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                status = r.status
                daten = r.read()
                kopf = [(k, v) for k, v in r.headers.items()
                        if k.lower() not in ("transfer-encoding",
                                             "connection", "content-length")]
        except urllib.error.HTTPError as e:
            status = e.code
            daten = e.read()
            kopf = [(k, v) for k, v in e.headers.items()
                    if k.lower() not in ("transfer-encoding",
                                         "connection", "content-length")]
        except Exception as e:
            self._fehler(502, str(e))
            return
        self.send_response(status)
        for k, v in kopf:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(daten)
        except Exception:
            pass

    def _anhang_antwort(self, frage):
        """Weg A: Wurde gerade eine Datei an den Chat angehaengt, antworte
        direkt aus ihrem Text - kein Agent, keine Suche, keine Belege.
        True, wenn beantwortet."""
        m = re.match(r"^/api/(?:v1/)?workspace/([^/]+)", self.path or "")
        if not m:
            return False
        eintrag = _ANHANG.get(m.group(1))
        if not eintrag or time.time() - eintrag["wann"] > _ANHANG_HALTBAR:
            return False
        if not bereich_sichtbar(self.path, self.headers):
            self._json({"error": "Workspace does not exist."}, code=404)
            return True
        if not (frage or "").strip():
            return False
        text = eintrag["text"]
        name = eintrag["name"]
        seit = time.time()
        eintrag["wann"] = seit   # solange gefragt wird, bleibt das Dokument aktiv
        # Das GANZE Dokument lesen UND die ECHTE Aufgabe erfuellen (nicht nur
        # zusammenfassen). Der Inhalt darf aufbereitet/gegliedert werden.
        _regel = ("Stuetze dich AUSSCHLIESSLICH auf das Dokument und erfinde "
                  "keine Inhalte. Du DARFST den vorhandenen Inhalt aber frei "
                  "aufbereiten, gliedern und in die gewuenschte Form bringen "
                  "(z.B. Praesentations-Gliederung, Stichpunkte, Tabelle).")
        try:
            st = mehrstufig.stuecke(text)
        except Exception:
            st = [text] if text else []
        if not st:
            return False
        try:
            if len(st) == 1:
                roh = (self._modell_fragen(
                    "%s\n\nAUFGABE: %s\n\nDOKUMENT (%s):\n%s"
                    % (_regel, frage, name, text)) or "").strip()
            else:
                _teile = []
                for _i, _s in enumerate(st, 1):
                    _t = self._modell_fragen(
                        mehrstufig.teil_auftrag(_s, name, _i, len(st)))
                    _teile.append((_t or "").strip() or "[Teil nicht lesbar]")
                _zus = "\n\n".join("--- Teil %d ---\n%s" % (_i, _t)
                                    for _i, _t in enumerate(_teile, 1))
                roh = (self._modell_fragen(
                    "Unten stehen Zusammenfassungen ALLER %d Teile des Dokuments "
                    "(es wurde vollstaendig gelesen). %s\n\nAUFGABE: %s\n\n%s"
                    % (len(st), _regel, frage, _zus)) or "").strip()
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return False
        if not roh:
            return False
        _gelesen = ("das komplette Dokument (%d Zeichen)" % len(text)
                    if eintrag.get("roh_len", 0) <= len(text)
                    else "die ersten %d von %d Zeichen (Dokument extrem gross)"
                         % (len(text), eintrag.get("roh_len", 0)))
        roh = "*(Gelesen: %s.)*\n\n%s" % (_gelesen, roh)
        roh += ("\n\n---\n*📎 Antwort aus dem angehaengten Dokument "
                "**%s** · %.1f s · Chat-Upload, ohne "
                "Fundstellen-Belege*" % (eintrag["name"], time.time() - seit))
        self._festhalten("anhang", frage, roh)
        self._sende_strom([
            {"uuid": _neue_marke("anhang"), "type": "textResponseChunk",
             "textResponse": roh, "sources": [], "close": False,
             "error": False},
            {"uuid": _neue_marke("anhang"), "type": "textResponseChunk",
             "textResponse": "", "sources": [], "close": True,
             "error": False},
        ])
        print("[Anhang] direkt beantwortet aus '%s' (%r)"
              % (eintrag["name"], frage[:50]), file=sys.stderr, flush=True)
        return True

    def _meta_antwort(self, frage):
        """KI4KI-META: Begruessung/Selbstauskunft beantworten. True=erledigt."""
        f = (frage or "").strip()
        if not META_ANTWORT or not f:
            return False
        if _META_KANN.match(f):
            text = META_TEXT_KANN
        elif _META_GRUSS.match(f):
            text = META_TEXT_GRUSS
        else:
            return False
        self._festhalten("meta", frage, text)
        self._sende_strom([
            {"uuid": _neue_marke("meta"), "type": "textResponseChunk",
             "textResponse": text, "sources": [], "close": False,
             "error": False},
            {"uuid": _neue_marke("meta"), "type": "textResponseChunk",
             "textResponse": "", "sources": [], "close": True, "error": False},
        ])
        print("[Meta] Konversation beantwortet: %r" % f[:40],
              file=sys.stderr, flush=True)
        return True

    def do_POST(self):
        _konto_merken(self.headers)
        pfad = self.path.split("?")[0]
        if ANSTOSS.match(pfad):
            # KI4KI-ANSTOSS-ROUTE: n8n stoesst die Verarbeitung an. Nur mit
            # Anmeldung - sonst koennte jeder im Netz Rechenlast ausloesen.
            if not angemeldet(self.headers):
                self._json({"ok": False, "fehler": "Nicht angemeldet."},
                           code=401)
                return
            try:
                laenge = int(self.headers.get("Content-Length") or 0)
                roh = self.rfile.read(laenge) if laenge else b""
                grund = (json.loads(roh or b"{}") or {}).get("grund") or ""
            except Exception:
                grund = ""
            ok, meldung = anstoss_ablegen(grund)
            print("[Anstoss] %s (%s)" % (meldung, grund[:60]),
                  file=sys.stderr, flush=True)
            self._json({"ok": ok, "meldung": meldung}, code=200 if ok else 500)
            return

        if pfad == "/rolle":
            self._rolle_route()
            return

        _wu = re.match(r"^/api/workspace/([^/]+)/update/?$", pfad)
        if _wu:
            # Einstellungen aus der Oberflaeche gespeichert: weiterreichen, dann
            # den Rollen-Abschnitt des Prompts in prompt.md uebernehmen.
            try:
                laenge = int(self.headers.get("Content-Length") or 0)
                koerper = self.rfile.read(laenge) if laenge else b""
            except Exception:
                koerper = b""
            self._weiterleiten("POST", koerper)
            try:
                leib = json.loads(koerper or b"{}") or {}
                if isinstance(leib.get("openAiPrompt"), str):
                    _rolle_aus_oberflaeche(_wu.group(1), leib["openAiPrompt"])
                if leib.get("chatMode") in rolle.MODI:
                    konf = _bereich_konf(_wu.group(1))
                    konf.setdefault("rolle", {})["modus"] = leib["chatMode"]
                    _bereich_konf_schreiben(_wu.group(1), konf)
                    _MODUS_JE_BEREICH[_wu.group(1)] = (leib["chatMode"], time.time())
            except Exception:
                traceback.print_exc(file=sys.stderr)
            return

        # ⭐ K2 (Leitfaden S. 123, 128): Daumen hoch/runter der Oberflaeche
        #   laeuft hier durch - mitschreiben, dann weiterreichen.
        _fb = FEEDBACK.match(pfad)
        if _fb:
            try:
                laenge = int(self.headers.get("Content-Length") or 0)
                koerper = self.rfile.read(laenge) if laenge else b""
            except Exception:
                koerper = b""
            try:
                _leib = json.loads(koerper or b"{}") or {}
                wert = _leib.get("feedback")
                _kommentar = str(_leib.get("kommentar") or "").strip()[:600]
                bewertung = ("hilfreich" if wert in (1, True, "1", "true") else
                             "nicht hilfreich" if wert in (-1, False, "-1", "false", 0, "0") else
                             "zurueckgenommen")
                letzte = None
                try:
                    for e in reversed(pruefprotokoll.alle_eintraege()):
                        if e.get("art") == "frage" and e.get("bereich") == _fb.group(1) and \
                                e.get("konto") == pruefprotokoll.pseudonym(pruefprotokoll.konto_aus(self.headers)):
                            letzte = e
                            break
                except Exception:
                    letzte = None
                pruefprotokoll.schreibe(
                    art="rueckmeldung",
                    konto=pruefprotokoll.pseudonym(pruefprotokoll.konto_aus(self.headers)),
                    bereich=_fb.group(1), chat_id=_fb.group(2), bewertung=bewertung,
                    text=_kommentar or None,
                    faden=(letzte or {}).get("faden"),
                    frage_original=(letzte or {}).get("frage_original"),
                    antwort=re.sub(r"\s+", " ", (letzte or {}).get("antwort") or "")[:500] or None,
                    regel=(letzte or {}).get("regel"),
                    fundstellen=(letzte or {}).get("fundstellen"))
                print("[Rueckmeldung] %s in %s (Chat %s)" % (bewertung, _fb.group(1), _fb.group(2)),
                      file=sys.stderr, flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)
            if _fb.group(2).startswith("-"):
                # Antwort der Anlage (nicht in AnythingLLMs Datenbank): Daumen ist notiert,
                # AnythingLLM kennt die Kennung nicht - selbst bestaetigen.
                self._json({"success": True, "error": None})
                return
            self._weiterleiten("POST", koerper)
            return

        if CHAT.match(pfad):
            chat_gemeldet()
            self._besitzt_sperre = None
            try:
                self._chat()
            finally:
                if getattr(self, "_besitzt_sperre", None):
                    _arbeitet_weg(self._besitzt_sperre)
            return
        if CHAT_JSON.match(pfad):
            chat_gemeldet()
            self._chat_json()
            return
        mp = PARSE.match(pfad)
        if mp:
            self._parse_mitschnitt(mp.group(1))
            return
        m = UPLOAD.match(pfad)
        if m:
            self._upload(m.group(1))
            return
        if ERSTELLEN.match(pfad) and BEREICH_HEILEN and API_SCHLUESSEL:
            self._bereich_neu()
            return
        self._weiterleiten("POST")

    def do_PUT(self):
        self._weiterleiten("PUT")

    def do_DELETE(self):
        # KI4KI-LOESCHEN aus der Oberflaeche: Der Papierkorb im Dokumente-
        # Dialog loescht in AnythingLLM die Textfassung - die eigenen Spuren
        # (Archiv-PDF, Katalog, Vormerkliste, Vorrat) zieht die Anlage danach
        # selbst nach. Kein zweiter Handgriff mehr.
        if LOESCH_WACHE and _LOESCH_UI.match(self.path or ""):
            koerper = self._koerper()
            self._weiterleiten("DELETE", koerper=koerper)
            try:
                names = (json.loads(koerper or b"{}") or {}).get("names") or []
                _nach_ui_loeschung(names)
            except Exception:
                traceback.print_exc(file=sys.stderr)
            return
        _wl = BEREICH_LOESCHEN.match((self.path or "").split("?")[0])
        if _wl:
            self._weiterleiten("DELETE")
            try:
                # Kurz warten, bis AnythingLLM den Bereich wirklich entfernt hat,
                # dann den Ordner pruefen - leer weg, sonst melden.
                threading.Timer(3.0, bereich_ordner_aufraeumen, args=(_wl.group(1),)).start()
                _BEREICHE_ABGLEICH[0] = 0.0
            except Exception:
                traceback.print_exc(file=sys.stderr)
            return
        self._weiterleiten("DELETE")

    def do_PATCH(self):
        self._weiterleiten("PATCH")

    def do_OPTIONS(self):
        self._weiterleiten("OPTIONS")



def _mitlesen(roh, hoechstens=320):
    """Der entstehende Text, gekuerzt fuer die Statuszeile.

    KI4KI-MITLESEN-FN. Gezeigt wird das ENDE des Textes: Dort schreibt das
    Modell gerade, und dort will man hinsehen. Vorne steht eine Andeutung,
    dass es weitergeht.

    Absaetze werden zu Leerzeichen - eine Statuszeile ist einzeilig, und
    Umbrueche wuerden sie zerreissen.
    """
    t = " ".join((roh or "").split())
    if len(t) <= hoechstens:
        return t
    return "… " + t[-hoechstens:]

def bilanzzeile(pruefungen, rohtext=""):
    """Bilanz plus Erklaerung, was die Woerter bedeuten.

    Ohne Erklaerung liest sich "nur teilweise belegt" wie eine Aussage
    ueber die FORSCHUNG. Gemeint ist die Pruefung dieser Anlage.

    rohtext dient nur dazu, den Agentenmodus zu erkennen: Dort fehlen
    Belege nicht, weil nichts zu finden waere, sondern weil gar nicht
    gesucht wurde.
    """
    z = veredeln.bilanz(pruefungen)
    if not sum(z.values()):
        # ⚠ HIER geht es raus, wenn es GAR KEINE Zitatpruefungen gab -
        #   und das ist der haeufige Fall. Die Abbildungen muessen also
        #   auch auf DIESEM Weg angehaengt werden, nicht nur unten.
        if AGENT_MARKER in (rohtext or ""):
            return _mit_abbildungen(HINWEIS_AGENT, pruefungen, rohtext)
        return _mit_abbildungen(HINWEIS_OHNE, pruefungen, rohtext)
    # ⚠ Auf einen Satz gekuerzt. Vorher stand hier
    #   "2 woertlich im Original gefunden · 1 ohne Fundstelle" - das liest
    #   sich wie ein Widerspruch, wenn man nicht weiss, dass es um zwei
    #   VERSCHIEDENE Zitate geht: Wie kann etwas gefunden sein, aber ohne
    #   Fundstelle? Verwirrend.
    gesamt = sum(z.values())
    gefunden = z["woertlich"] + z["geglaettet"]
    zeilen = ["---", "",
              "**Belegprüfung:** %d von %d Zitat%s im Original "
              "wiedergefunden." % (gefunden, gesamt,
                                   "en" if gesamt != 1 else ""),
              ""]
    # Nur wenn etwas nicht stimmt, und dann konkret.
    offen = z["teilweise"] + z["ungedeckt"] + z["zu_kurz"]
    if offen:
        zeilen += ["*⚠ %d Zitat%s nicht wiedergefunden. Die Aussage kann "
                   "trotzdem richtig sein — nur das Zitat passt nicht dazu.*"
                   % (offen, "e" if offen != 1 else ""), ""]

    return _mit_abbildungen("\n".join(zeilen) + "\n" + HINWEIS,
                            pruefungen, rohtext)


def _seiten_aus_text(text):
    """(Dokument, Seite) aus den Quellenangaben im Antworttext.

    ⚠ Die ZITAT-PRUEFUNGEN sind oft LEER - dann hat das Modell zwar
      Quellen genannt, aber nichts woertlich zitiert. Die Seiten stehen
      trotzdem im Text: "(DS-00-000, S. 52)". Das ist ohnehin die
      richtige Quelle: genau die Seiten, auf die die Antwort verweist.
    """
    raus = []
    for m in re.finditer(r"\*?([A-Za-z0-9][\w.\- ]{2,40}?)\*?,\s*S\.\s*(\d{1,4})",
                         text or ""):
        name, seite = m.group(1).strip(), m.group(2)
        try:
            raus.append((name, int(seite)))
        except ValueError:
            pass
    return raus


def _mit_abbildungen(text, pruefungen, rohtext):
    """Abbildungen anhaengen - EINE Stelle fuer ALLE Ausgaenge.

    ⚠ Vorher haing das an einem der beiden Ausgaenge von bilanzzeile().
      Der andere - der ohne Zitatpruefungen, also der haeufige - lief
      daran vorbei. Eine Ergaenzung an EINEM Weg ist keine Ergaenzung.
    """
    zusatz = _abbildungen_zeigen(pruefungen, rohtext)
    return text + ("\n".join(zusatz) if zusatz else "")


# Nur Saetze mit VERNEINUNG ("kann keine", "nicht moeglich"): "Das Diagramm
# kann die Verteilung zeigen" ist eine Sachaussage und bleibt stehen.
_LEUGNUNG = re.compile(
    r"[^.\n]*\b(?:ich|es|mir)\b[^.\n]*\b(?:kann|können|ist|sind)\b[^.\n]*"
    r"\b(?:keine?|kein|nicht)\b[^.\n]*"
    r"\b(?:Bild(?:er)?|Grafik(?:en)?|Diagramm(?:e)?|Abbildung(?:en)?)\b"
    r"[^.\n]*\.\s*", re.I)


def ohne_bildleugnung(text, hat_bilder):
    """Saetze wie "Ich kann keine Bilder anzeigen" streichen - wenn die
    Anlage gerade Bilder anhaengt. Sonst steht die Leugnung direkt ueber
    dem Bild, und der Leser haelt die Anlage fuer kaputt."""
    if not hat_bilder:
        return text
    return _LEUGNUNG.sub("", text or "")


def _abbildungen_zeigen(pruefungen, rohtext="", hoechstens=2):
    """Abbildungen der belegten Seiten als Markdown-Bilder.

    ⚠ Es wird nur die ADRESSE eingesetzt, nichts erzeugt. Freistellen
      kostet ein bis drei Sekunden je Seite; zwei Bilder wuerden jede
      Antwort entsprechend verzoegern. Das Bild holt der Browser,
      waehrend der Mensch schon liest.

    ⚠ Hoechstens zwei. Bei sechs Fundstellen waeren es sechs Vollbilder,
      und die Antwort selbst waere nicht mehr zu finden.
    """
    from urllib.parse import quote
    # ⭐ AUSDRUECKLICHER BILDWUNSCH ("zeig mir ein Diagramm", "Bild 2.1"):
    #   Dann reichen die belegten Seiten nicht - die Suche liefert zu so
    #   einer Frage Vorwort und Inhaltsverzeichnis, und dort gibt es keine
    #   Bilder. Stattdessen die Seiten mit Bildunterschriften im Dokument
    #   suchen (bei einer Nummer genau diese), und bis zu drei zeigen.
    anfrage = getattr(_ANFRAGE, "frage", "") or ""
    bildwunsch = bool(_BILDWUNSCH.search(anfrage))
    if bildwunsch:
        hoechstens = max(hoechstens, 3)
    gesehen, raus = set(), []
    kandidaten = []
    for p in pruefungen or []:
        if p.get("urteil") == "zu_kurz":
            continue
        seiten = p.get("seiten") or []
        s = seiten[0] if isinstance(seiten, (list, tuple)) and seiten else seiten
        if p.get("doku") and s:
            kandidaten.append((p["doku"], s))
    kandidaten += _seiten_aus_text(rohtext)
    if bildwunsch:
        try:
            kandidaten = _abbildungs_seiten(
                anfrage, kandidaten,
                getattr(_ANFRAGE, "namen", None) or []) + kandidaten
        except Exception:
            traceback.print_exc(file=sys.stderr)
    for doku, seite in kandidaten:
        # ⚠ Frueher nur zu GEPRUEFTEN Zitaten. Zu streng: Eine Antwort
        #   ohne woertliche Zitate ("Diese Antwort
        #   enthaelt keine Zitate") - also kam auch kein Bild, obwohl die
        #   genannten Seiten Abbildungen tragen. Wenn eine Seite genannt
        #   ist und dort eine Abbildung steht, gehoert sie gezeigt; ob das
        #   Zitat geprueft ist, sagt der Text daneben ohnehin.
        try:
            seite = int(seite)
        except (TypeError, ValueError):
            continue
        if not doku or seite < 1:
            continue
        schluessel = (doku, seite)
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        # ⚠ NUR wenn es dort wirklich eine Abbildung gibt. Sonst liefert
        #   die Route 404 und im Chat steht ein KAPUTTES Bildsymbol -
        #   schlimmer als gar kein Bild. Die Pruefung ist billig (0,04-0,6 s,
        #   ohne Rendern); das teure Rendern macht weiter der Browser.
        try:
            import abbildung
            pfad = PDFS.get(_pdf_schluessel(doku) or "")
            if not pfad or not abbildung.hat_abbildung(pfad, seite):
                continue
        except Exception:
            continue
        # ⭐ KLICKBAR: Das Bild in einen Link auf die Quellseite
        #   wickeln - auch die Bilder sollen verlinkt sein.
        _dq = quote(str(doku), safe="")
        raus.append("[![Abbildung aus %s, Seite %d]"
                    "(/abbildung?dok=%s&seite=%d)](/stelle?dok=%s&seite=%d)"
                    % (doku, seite, _dq, seite, _dq, seite))
        if len(raus) >= hoechstens:
            break
    if not raus:
        return []
    kopf = ("*Abbildungen aus dem Dokument:*" if bildwunsch
            else "*Abbildungen von den belegten Seiten:*")
    return ["", kopf, ""] + raus + [""]


# ⚠ Schreibvarianten tolerieren: Gemessen "Zeig mir das erste Diagram" (ein m)
#   fiel durch und landete in der Bestandsliste.
_BILDWORT = (r"(?:bild(?:er)?|abbildung(?:en)?|abb\.?|diagram\w*|gra(?:f|ph)ik\w*|"
             r"schaubild\w*|figur\w*|figure|fig\.|skizze\w*|zeichnung\w*)")
_BILDWUNSCH = re.compile(r"\b(?:zeig\w*|" + _BILDWORT + r")\b", re.I)
_BILDNUMMER = re.compile(
    r"\b(?:bild|abbildung|abb\.?|figure|fig\.?)\s*(\d{1,2}(?:[.\-]\d{1,3})?)", re.I)
_BILDUNTERSCHRIFT = re.compile(
    r"^\s*(?:Bild|Abbildung|Abb\.|Figure|Fig\.)\s*\d{1,2}(?:[.\-]\d{1,3})?\b",
    re.I | re.M)


# Ausdruecklicher Wunsch, ein Bild zu SEHEN - nicht eine Sachfrage, in der
# ein Diagramm vorkommt ("Welche Mischertypen zeigt das Diagramm?" bleibt
# eine Fachfrage). Deshalb am Satzanfang verankert; eine genannte Bildnummer
# zaehlt immer.
_BILD_ZEIGEN = re.compile(
    r"^\s*(?:"
    r"welche\s+(?:bilder|abbildungen|diagramme|grafiken|graphiken|schaubilder|skizzen)\b|"
    r"(?:zeig\w*\b|kannst\s+du\b|könntest\s+du\b|koenntest\s+du\b|"
    r"gibt\s+es\b|hast\s+du\b|habt\s+ihr\b|"
    r"ich\s+(?:möchte|moechte|will|würde\s+gern\w*|wuerde\s+gern\w*)\b)"
    r"[^?]*?\b" + _BILDWORT + r")", re.I)


_BILDWOERTER = ("bild", "bilder", "abbildung", "abbildungen", "diagramm",
                "diagramme", "grafik", "grafiken", "graphik", "schaubild",
                "skizze", "zeichnung", "figur", "figure", "chart", "picture",
                "image", "graph", "plot")
_ZEIGWOERTER = ("zeig", "zeige", "zeigen", "zeigst", "anzeigen", "sehen",
                "show", "display")
_FRAGEWOERTER = ("kannst", "könntest", "koenntest", "gibt", "gibts", "hast",
                 "habt", "can", "could")


def _unscharf(wort, liste, mindest=0.8, minlaenge=4):
    """Tippfehler-tolerant: 'diagrm', 'abbildng', 'zeg mir'."""
    import difflib
    w = wort.lower()
    if len(w) < minlaenge:
        return False
    return any(difflib.SequenceMatcher(None, w, z).ratio() >= mindest
               for z in liste)


def _ist_bildwunsch(frage):
    """Bildwunsch erkennen - in drei Stufen.

    1. Regel (klare Formen, genannte Bildnummer).
    2. Unscharf: Tippfehler und Fremdwoerter ('Zeig mir ein Diagrm',
       'show me a picture') - Wortvergleich, ohne Modell.
    3. Kleines Modell als Ja/Nein-Instanz, wenn ein Zeig-Verb da ist, aber
       kein Bildwort erkannt wurde - fuer alles, was Regeln nicht ahnen.
    ⚠ Sachfragen, in denen ein Diagramm nur vorkommt ("Welche Typen zeigt
      das Diagramm?"), bleiben in allen drei Stufen Fachfragen.
    """
    f = frage or ""
    if _BILDNUMMER.search(f) or _BILD_ZEIGEN.search(f):
        return True
    woerter = re.findall(r"[A-Za-zÄÖÜäöüß]+", f)
    if not woerter:
        return False
    # Das Zeig- oder Frageverb muss VORN stehen (Befehl/Frage an die Anlage:
    # "Zeig mir ...", "Kanst du mir ..."). Ein "zeigt" mitten im Satz
    # ("Welche Typen zeigt das Diagramm?") ist eine Sachfrage. Tippfehler
    # sind in beiden Verben erlaubt.
    zeig_vorn = (_unscharf(woerter[0], _ZEIGWOERTER, 0.75, 3)
                 or _unscharf(woerter[0], _FRAGEWOERTER, 0.75, 3))
    bildwort = any(_unscharf(w, _BILDWOERTER) for w in woerter)
    if zeig_vorn and bildwort:
        return True
    if zeig_vorn and not bildwort:
        try:
            return bool(assistent.netz_bildwunsch(f))
        except Exception:
            return False
    return False


def _bildunterschrift(seitentext, nummer=None):
    """Die Bildunterschrift auf der Seite - zu einer Nummer oder die erste."""
    muster = (r"(?m)^\s*((?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*%s(?![\d.])[^\n]*)"
              % re.escape(nummer.replace("-", ".")) if nummer
              else r"(?m)^\s*((?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*\d{1,2}(?:[.\-]\d{1,3})?\b[^\n]*)")
    m = re.search(muster, seitentext or "", re.I)
    if not m:
        return ""
    zeile = re.sub(r"\s+", " ", m.group(1)).strip()
    # Umbrochene Unterschrift: die Folgezeile gehoert oft noch dazu.
    rest = (seitentext or "")[m.end():].split("\n", 2)
    if len(rest) > 1 and rest[1].strip() and not re.match(
            r"^\s*(?:Bild|Abbildung|Abb\.?|Figure|Fig\.?|\d)", rest[1]) \
            and not zeile.endswith((".", ":")) and len(zeile) < 90:
        zeile += " " + re.sub(r"\s+", " ", rest[1]).strip()
    return zeile[:300]


def _abbildungs_seiten(anfrage, kandidaten, namen):
    """Seiten mit Abbildungen fuer einen ausdruecklichen Bildwunsch.

    Reihenfolge der Dokumente: erst die aus Belegen/Nennungen, dann die
    Quellen der Suche. Bei "Bild 2.1" genau diese Unterschrift - und zwar
    am ZEILENANFANG (die Unterschrift steht bei der Abbildung; "siehe Bild
    2.1" im Fliesstext steht woanders). Ohne Nummer: alle Seiten mit einer
    Bildunterschrift. Nur EIN Dokument, sonst wird es ein Bilderbuch.
    """
    dokus = []
    for d, _ in kandidaten:
        if d and d not in dokus:
            dokus.append(d)
    for n in namen:
        s = n[:-3] if n.endswith(".md") else n
        if s not in dokus:
            dokus.append(s)
    gewuenscht = _BILDNUMMER.search(anfrage)
    for doku in dokus[:3]:
        schluessel = _pdf_schluessel(doku)
        if not schluessel:
            continue
        try:
            seiten = _seitentexte_pdf(schluessel) or []
        except Exception:
            continue
        if gewuenscht:
            nr = re.escape(gewuenscht.group(1).replace("-", "."))
            muster = re.compile(
                r"(?m)^\s*(?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*" + nr
                + r"(?![\d.])", re.I)
            lose = re.compile(
                r"\b(?:Bild|Abbildung|Abb\.?|Figure|Fig\.?)\s*" + nr
                + r"(?![\d.])", re.I)
            genau = [i for i, t in enumerate(seiten, 1) if muster.search(t or "")]
            treffer = genau or [i for i, t in enumerate(seiten, 1)
                                if lose.search(t or "")]
        else:
            treffer = [i for i, t in enumerate(seiten, 1)
                       if _BILDUNTERSCHRIFT.search(t or "")]
        if treffer:
            return [(schluessel, i) for i in treffer[:12]]
    return []


# Steht unter jeder Antwort. Der EU AI Act (Art. 50) verlangt ab dem
# 02.08.2026, dass erkennbar ist, wenn man mit einer KI spricht. Bei einem
# sichtbaren Chat ist das erfuellt - der Hinweis auf moegliche Fehler ist
# keine Pflicht, bei einem Forschungswerkzeug aber selbstverstaendlich.
HINWEIS = ("\n*Klick auf eine Fundstelle zeigt die Stelle im Original. "
           "Antworten können Fehler enthalten.*\n")

# Kam gar kein Zitat in der Antwort vor, wurde auch nichts geprueft. Das muss
# dastehen, sonst verspricht die Anlage eine Sicherheit, die sie nicht hat.
HINWEIS_OHNE = ("\n*In dieser Antwort hat das Modell nicht wörtlich zitiert. "
                "Verlinkte Quellenangaben führen auf die im Original "
                "nachgeschlagene Stelle.*\n")

# AnythingLLM kann in einen Agentenmodus wechseln. Dort wird nicht in den
# Dokumenten gesucht - es kommt also weder eine Antwort aus dem Bestand
# noch ein Beleg. Der Faden bleibt in diesem Zustand, bis jemand /exit
# tippt. Ohne diesen Hinweis sieht das aus wie eine Wissensluecke.
AGENT_MARKER = "Swapping over to agent chat"
HINWEIS_AGENT = (
    "\n> ⚠️ **Dieser Gesprächsfaden läuft im Agentenmodus.** In diesem Modus "
    "durchsucht die Anlage die Dokumente nicht — es gibt daher weder eine "
    "Antwort aus dem Bestand noch Belege.\n>\n"
    "> Zurück zur geprüften Antwort: **`/exit`** eingeben oder einen neuen "
    "Gesprächsfaden beginnen.\n")


def main():
    global BESTAND, ZIEL
    p = argparse.ArgumentParser(description="Belegpruefung vor AnythingLLM")
    p.add_argument("--port", type=int, default=3000)
    p.add_argument("--ziel", default=ZIEL)
    p.add_argument("--adresse", default="0.0.0.0")
    a = p.parse_args()
    ZIEL = a.ziel.rstrip("/")

    veredeln.SEITENPRUEFER = seite_pruefen
    print("gemerkte gepruefte Antworten: %d" % gedaechtnis_laden(), flush=True)
    print("lade Quellbestand ...", flush=True)
    # ⚠ ZUSTANDS-WACHE: Alles, was der Proxy sich merkt (Gespraechs-
    #   Nachtraege, Beleg-Marken, Dokumentzugaenge, Wortverzeichnis,
    #   Protokoll), muss im Daten-Volume liegen. Liegt eine dieser Dateien
    #   im Programmordner, ist sie beim naechsten Neubau des Containers
    #   weg - gemessen 25.08.: ganze Gespraechsfaeden verschwunden. Lieber
    #   laut beim Start als still beim Update.
    _hier = os.path.dirname(os.path.abspath(__file__))
    for _name, _pfad in (("Gespraechs-Nachtraege", NACHTRAG_DATEI),
                         ("Beleg-Marken", ZUGANG_DATEI),
                         ("Dokumentzugaenge", _DOKZUGANG_DATEI),
                         ("Protokoll", pruefprotokoll.ORDNER),
                         ("Wortverzeichnis", os.environ.get("KI4KI_WORTVERZEICHNIS") or ""),
                         ("Zusammenfassungs-Speicher", getattr(mehrstufig, "SPEICHER", "")),
                         ("Faden-Gedaechtnis", getattr(assistent, "GEDAECHTNIS_DATEI", ""))):
        if _pfad and os.path.abspath(_pfad).startswith(_hier + os.sep):
            print("⚠ ZUSTAND IM CONTAINER: %s liegt unter %s - geht beim "
                  "naechsten Neubau verloren. Im Compose per Umgebungs-"
                  "variable ins Daten-Volume legen." % (_name, _pfad),
                  file=sys.stderr, flush=True)
    BESTAND = veredeln.Bestand()
    if LOESCH_WACHE and API_SCHLUESSEL:
        threading.Thread(target=_loesch_wache, daemon=True).start()
        print("Loesch-Wache: <bereich>/loeschen/ wird jede Minute geleert", flush=True)
    elif LOESCH_WACHE:
        print("Loesch-Wache AUS: kein KI4KI_API_KEY", flush=True)
    BESTAND._rohtext()
    print("  %d Dokumente, %d Quell-PDFs" % (len(BESTAND.titel()),
                                             pdfs_einlesen()), flush=True)
    # Beim Start festhalten, WIE protokolliert wird, und abgelaufene
    # Tagesdateien wegraeumen. Ohne den ersten Eintrag laesst sich spaeter
    # nicht unterscheiden, ob eine Luecke im Protokoll eine Luecke ist oder
    # eine abgeschaltete Aufzeichnung.
    try:
        pruefprotokoll.einstellungen_festhalten()
        weg = pruefprotokoll.aufraeumen()
        print("Protokoll: %s, %d Tage Aufbewahrung%s"
              % ("an" if pruefprotokoll.EINSTELLUNG["an"] else "AUS",
                 pruefprotokoll.EINSTELLUNG["tage"],
                 ", %d Tage abgelaufen entfernt" % len(weg) if weg else ""),
              flush=True)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    srv = ThreadingHTTPServer((a.adresse, a.port), Griff)
    print("Pruef-Proxy auf http://%s:%d  ->  %s" % (a.adresse, a.port, ZIEL),
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbeendet")


if __name__ == "__main__":
    main()
