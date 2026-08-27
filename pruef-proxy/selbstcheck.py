#!/usr/bin/env python3
"""KI4KI Selbst-Check - arbeitet die Anlage noch richtig? (vom Testserver
uebernommen, 26.08.; dort selbstcheck.py + selbstcheck_bericht.py)

Reproduzierbar, LOKAL, ohne externe Dienste - fuer Betreiber und Partner.

  1. ROTIERENDE FRAGEN: je Lauf werden Fachwoerter zufaellig aus dem
     eigenen Bestand des Bereichs gezogen (plus feste Haertefaelle als
     Regressionswaechter) - nie derselbe Lauf.
  2. Jede Frage laeuft durch die Anlage (den Pruef-Proxy, JSON-Weg
     /api/v1/workspace/<bereich>/chat - dieselbe Pruefschicht wie im Chat).
  3. MECHANISCHES URTEIL, ohne die "richtige Antwort" zu kennen:
       - Bestandsfrage -> kommt die Index-Tabelle?
       - Inhaltsfrage  -> zeigt jeder Beleg (Kennung, S. n) auf eine Seite,
         die die Aussage davor wirklich deckt (>= 3 Fachwoerter)?
         Beleg ohne Deckung -> WARN. Antwort ohne Beleg -> INFO.
  4. Ampel-Bericht: /daten/pruefung/selbstcheck/{ergebnis.json,bericht.html}
     -> im Browser unter /selbstcheck (Einsichtsrecht wie /kpi).

Aufruf im Container:
  docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py            alle Bereiche, 8 Fragen je Bereich
  docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py auw 12     ein Bereich, 12 Fragen
"""
import datetime
import html
import json
import os
import random
import re
import sys
import time
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

API = (os.environ.get("KI4KI_SELBSTCHECK_API") or "http://127.0.0.1:3001/api/v1").rstrip("/")
SCHLUESSEL = (os.environ.get("KI4KI_API_KEY") or "").strip()
BESTAND_ORDNER = os.environ.get("KI4KI_BESTAND") or "/daten/bestand/documents"
ZIEL = os.path.join(os.path.dirname(os.environ.get("KI4KI_PROTOKOLL") or "/daten/pruefung/protokoll"), "selbstcheck")
BELEG = re.compile(r"\(\s*([A-Za-z0-9ÄÖÜäöüß][^(),\n]{1,90}?)\s*,\s*S\.?\s*(\d{1,4})\s*\)")
FUELL = {"werden", "wurden", "zwischen", "sowie", "dieser", "dieses", "diesem", "welche", "welcher", "koennen",
         "können", "sollte", "sollten", "jedoch", "dadurch", "hierbei", "bereits", "weitere", "weiteren", "innerhalb",
         "während", "waehrend", "aufgrund", "anhand", "hinsichtlich", "beispielsweise", "insbesondere", "verschiedene",
         "verschiedenen", "entsprechend", "entsprechende", "folgende", "folgenden", "jeweils", "jeweiligen", "gesamte",
         "abbildung", "tabelle", "kapitel", "abschnitt", "dokument", "seite"}


def ruf(pfad, koerper=None, timeout=300):
    daten = json.dumps(koerper).encode() if koerper is not None else None
    req = urllib.request.Request(API + pfad, data=daten, method="POST" if daten else "GET",
                                 headers={"Authorization": "Bearer " + SCHLUESSEL, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _worte(s):
    return {w for w in re.sub(r"[^0-9a-zA-ZäöüÄÖÜß]+", " ", (s or "").lower()).split() if len(w) > 6 and w not in FUELL}


# ---- 1) Fragen aus dem eigenen Bestand -------------------------------------
def texte_des_bereichs(ablage):
    aus = []
    ordner = os.path.join(BESTAND_ORDNER, ablage)
    try:
        for d in sorted(os.listdir(ordner)):
            if d.endswith(".json"):
                with open(os.path.join(ordner, d), encoding="utf-8") as fh:
                    j = json.load(fh)
                aus.append((str(j.get("title") or d.split(".md-")[0]), j.get("pageContent") or ""))
    except Exception:
        pass
    return aus


def fachwoerter(texte, n):
    """Grossgeschriebene Woerter >= 8 Zeichen, die in mindestens zwei
    Dokumenten (oder 4x in einem) vorkommen - das sind die Fachbegriffe."""
    zaehl, je_dok = {}, {}
    for titel, t in texte:
        gesehen = set()
        for w in re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{7,}\b", t):
            zaehl[w] = zaehl.get(w, 0) + 1
            if w not in gesehen:
                je_dok[w] = je_dok.get(w, 0) + 1
                gesehen.add(w)
    allgemein = {"forschung", "lehrgang", "verbesserung", "digitale", "beschreibung", "bedeutung", "grundlagen",
                 "anwendung", "anwendungen", "einleitung", "uebersicht", "übersicht", "zusammenfassung", "ergebnisse",
                 "erfahrungen", "hinweise", "allgemeines", "einführung", "einfuehrung", "beispiele", "vorschriften"}
    kand = [w for w, c in zaehl.items() if (je_dok.get(w, 0) >= 2 or c >= 4) and w.lower() not in FUELL
            and w.lower() not in allgemein and c >= 3]
    random.shuffle(kand)
    return kand[:n]


def titelwoerter(texte):
    """Woerter aus den Dokumentnamen/-titeln - dazu MUSS die Bestandsliste
    etwas finden (sie sucht in Titeln, nicht im Text)."""
    aus = []
    for titel, _ in texte:
        for w in re.findall(r"[A-Za-zÄÖÜäöüß]{6,}", titel):
            if w.lower() not in FUELL and w not in aus:
                aus.append(w)
    random.shuffle(aus)
    return aus


def fragen_bauen(texte, anzahl):
    sw = fachwoerter(texte, 40)
    tw = titelwoerter(texte)
    fragen = [("Welche Dokumente habt ihr?", "bestand")]
    for w in (tw[:1] + sw[:1]):
        fragen.append(("Was habt ihr zum Thema %s?" % w, "bestand"))
    for w in sw[2:2 + max(2, anzahl - 4)]:
        fragen.append(("Was ist %s?" % w, "inhalt"))
    if sw[10:11]:
        fragen.append(("Wo wird %s beschrieben?" % sw[10], "inhalt"))
    random.shuffle(fragen)
    return fragen[:anzahl]


# ---- 2) Anlage fragen + 3) mechanisch urteilen ------------------------------
def seiten_von(name):
    try:
        import pruef_proxy as pp
        _sch, seiten = pp._seitentexte_von(name)
        return seiten or []
    except Exception:
        return []


def belege_pruefen(text):
    gedeckt, offen = [], []
    for m in BELEG.finditer(text or ""):
        kennung, seite = re.sub(r"\.(?:md|pdf)$", "", m.group(1).strip(), flags=re.I), int(m.group(2))
        satz = text[max(0, m.start() - 260):m.start()]
        ziel = _worte(satz)
        if len(ziel) < 3:
            continue
        seiten = seiten_von(kennung)
        if not seiten:
            offen.append("%s (Dokument nicht lesbar)" % kennung)
            continue
        kandidaten = [seiten[seite - 1]] if 0 < seite <= len(seiten) else []
        kandidaten += seiten
        beste = max((len(ziel & _worte(s)) for s in kandidaten), default=0)
        (gedeckt if beste >= 3 else offen).append("%s, S. %d" % (kennung, seite))
    return sorted(set(gedeckt)), sorted(set(offen))


def pruefen(slug, frage, erwartet, lauf="", nr=0):
    t0 = time.time()
    try:
        # eigener Faden je Frage - sonst schleppt die Anlage das Dokument der
        # vorigen Frage als Gespraechskontext mit
        res = ruf("/workspace/%s/chat" % slug, {"message": frage, "mode": "query",
                                               "sessionId": "selbstcheck-%s-%d" % (lauf, nr)})
    except Exception as e:
        return {"frage": frage, "art": erwartet, "urteil": "FEHLER", "detail": str(e)[:80], "gedeckt": [], "offen": [], "s": round(time.time() - t0, 1)}
    text = res.get("textResponse") or ""
    dauer = round(time.time() - t0, 1)
    kurz = re.sub(r"\s+", " ", text)[:700]
    if erwartet == "bestand":
        tabelle = "| Kennung |" in text or re.search(r"\|\s*Kennung", text) is not None
        ehrlich = re.search(r"finde ich .{0,40}keinen Dokumenttitel|keine .{0,30}zum Thema", text, re.I) is not None
        return {"frage": frage, "art": erwartet, "urteil": "PASS" if (tabelle or ehrlich) else "WARN",
                "detail": "Index-Tabelle geliefert" if tabelle else ("ehrlich: kein Titel zum Thema" if ehrlich else "keine Tabelle"),
                "gedeckt": [], "offen": [], "s": dauer, "antwort": kurz}
    gedeckt, offen = belege_pruefen(text)
    verneint = re.search(r"nicht enthalten|nichts Belegtes|keine (?:belegte|passende) Stelle|nicht im Bestand|liegt nicht vor", text, re.I) is not None
    if verneint and not gedeckt:
        # Der Begriff wurde AUS dem Bestand gezogen - er steht dort. "Nicht
        # enthalten" ist dann keine ehrliche Absage, sondern ein Fehlschlag.
        urteil, detail = "WARN", "Begriff steht im Bestand, Antwort sagt 'nicht enthalten'"
    elif offen and not gedeckt:
        urteil, detail = "WARN", "Beleg(e) ohne Deckung"
    elif offen:
        urteil, detail = "WARN", "%d gedeckt, %d ohne Deckung" % (len(gedeckt), len(offen))
    elif gedeckt:
        urteil, detail = "PASS", "%d Beleg(e) gedeckt" % len(gedeckt)
    else:
        urteil, detail = "INFO", "Antwort ohne pruefbaren Beleg"
    return {"frage": frage, "art": erwartet, "urteil": urteil, "detail": detail, "gedeckt": gedeckt, "offen": offen, "s": dauer, "antwort": kurz}


# ---- 4) Bericht ------------------------------------------------------------
FARBE = {"PASS": "#1e7d34", "WARN": "#b3261e", "FEHLER": "#8a5a00", "INFO": "#555"}


def bericht(alle, wann):
    n = len(alle)
    n_ok = sum(1 for o in alle if o["urteil"] == "PASS")
    n_warn = sum(1 for o in alle if o["urteil"] == "WARN")
    n_fehler = sum(1 for o in alle if o["urteil"] == "FEHLER")
    rows = []
    for o in alle:
        u = o["urteil"]
        det = html.escape(o.get("detail") or "")
        if o.get("offen"):
            det += " — ohne Deckung: " + html.escape(", ".join(o["offen"]))
        rows.append('<tr><td style="font-size:16pt;color:%s">●</td><td>%s</td><td><b>%s</b><br><span style="color:#666;font-size:9pt">%s · %s s</span>'
                    '<details style="font-size:9pt;color:#444;margin-top:4px"><summary>Antwort</summary>%s</details></td>'
                    '<td style="color:%s"><b>%s</b><br><span style="font-size:9pt;color:#444">%s</span></td><td style="font-size:9pt;color:#333">%s</td></tr>'
                    % (FARBE.get(u, "#333"), html.escape(o.get("bereich", "")), html.escape(o["frage"]), html.escape(o["art"]), o.get("s", ""),
                       html.escape(o.get("antwort") or ""),
                       FARBE.get(u, "#333"), u, det, html.escape(", ".join(o.get("gedeckt") or [])) or "—"))
    ampel = "#1e7d34" if not n_warn and not n_fehler else "#b3261e"
    return """<!doctype html><html><head><meta charset="utf-8"><title>KI4KI Selbst-Check</title></head>
<body style="font-family:'Liberation Sans',Arial,sans-serif;color:#1a1a1a;font-size:11pt;max-width:1100px;margin:20px auto">
<p style="font-size:19pt;font-weight:bold;margin:0">KI4KI · Selbst-Check der Anlage</p>
<p style="color:#666;margin:2px 0 10px">%s · rotierende Fragen aus dem eigenen Bestand · rein lokal geprüft</p>
<p style="background:%s;color:#fff;font-size:15pt;font-weight:bold;padding:8px 14px;margin:0 0 12px;border-radius:6px">%d von %d bestanden%s%s</p>
<table cellspacing="0" cellpadding="6" style="width:100%%;border-collapse:collapse;border:1px solid #ddd">
<tr style="background:#f0f1f3"><td></td><td><b>Bereich</b></td><td><b>Frage</b></td><td><b>Urteil</b></td><td><b>Gedeckte Belege</b></td></tr>
%s</table>
<p style="background:#eef2f8;border:1px solid #c8d4e6;padding:10px 14px;margin-top:14px;font-size:9.5pt">
<b>Was geprüft wird:</b> Zeigt jeder Beleg (Kennung, S. n) auf eine Seite, die die Aussage davor wirklich deckt (mind. 3 Fachwörter)?
Beleg ohne Deckung → ⚠. Bestandsfragen → kommt die Index-Tabelle? Die Fragen werden bei jedem Lauf zufällig aus dem eigenen Bestand
gezogen (plus feste Härtefälle). Alles läuft über die lokale Anlage — kein externer Dienst.</p></body></html>""" % (
        wann, ampel, n_ok, n, (" · %d ⚠" % n_warn) if n_warn else "", (" · %d ✖" % n_fehler) if n_fehler else "", "\n".join(rows))


def main():
    if not SCHLUESSEL:
        print("KI4KI_API_KEY fehlt - der Selbst-Check braucht den Anlagen-Schluessel (steht im Proxy-Container).")
        sys.exit(2)
    nur = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else None
    anzahl = int(next((a for a in sys.argv[1:] if a.isdigit()), 8))
    ws = (ruf("/workspaces") or {}).get("workspaces") or []
    alle = []
    for w in ws:
        slug = w.get("slug")
        if not slug or (nur and slug != nur):
            continue
        ablage = slug
        try:
            with open(os.path.join(os.environ.get("KI4KI_EINGANG") or "/daten/eingang", slug, "bereich.json"), encoding="utf-8") as fh:
                ablage = json.load(fh).get("ablage") or slug
        except Exception:
            pass
        texte = texte_des_bereichs(ablage)
        if not texte:
            print("-- %s: kein Bestand, uebersprungen" % slug)
            continue
        print("== %s (%d Dokumente)" % (slug, len(texte)))
        lauf = time.strftime("%Y%m%d%H%M%S")
        for nr, (frage, erw) in enumerate(fragen_bauen(texte, anzahl), 1):
            r = pruefen(slug, frage, erw, lauf, nr)
            r["bereich"] = slug
            alle.append(r)
            print("  %s %-50s [%s] %s (%s s)" % ({"PASS": "OK ", "WARN": "!! ", "FEHLER": "XX ", "INFO": ".. "}.get(r["urteil"], "?? "),
                                                frage[:50], r["art"], r["detail"], r.get("s")))
            if r["urteil"] in ("WARN", "FEHLER") and r.get("antwort"):
                print("      Antwort: " + r["antwort"][:220])
    wann = datetime.datetime.now().strftime("%d.%m.%Y, %H:%M")
    os.makedirs(ZIEL, exist_ok=True)
    with open(os.path.join(ZIEL, "ergebnis.json"), "w", encoding="utf-8") as fh:
        json.dump({"wann": wann, "ergebnisse": alle}, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(ZIEL, "bericht.html"), "w", encoding="utf-8") as fh:
        fh.write(bericht(alle, wann))
    n_ok = sum(1 for r in alle if r["urteil"] == "PASS")
    print("== %d/%d PASS, %d WARN, %d FEHLER -> %s/bericht.html (im Browser: /selbstcheck)" % (
        n_ok, len(alle), sum(1 for r in alle if r["urteil"] == "WARN"), sum(1 for r in alle if r["urteil"] == "FEHLER"), ZIEL))
    sys.exit(1 if any(r["urteil"] in ("WARN", "FEHLER") for r in alle) else 0)


if __name__ == "__main__":
    main()
