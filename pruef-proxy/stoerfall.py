"""K4 - Stoerfall-Kontext (Implementierungsleitfaden S. 115, UC 1
"KI-gestuetzte Stoerfallassistenz, Breakdown-to-Recovery").

Aus einer Eingabe werden die Kontextparameter gelesen - als Felder
("Anlage: SGM-3 · Fehlercode: E42 · Symptom: Duese tropft") oder aus dem
Satz ("an der SGM-3 kommt E42, die Duese tropft"). Damit wird die Suche
gezielt (Fehlerkataloge, Handbuecher, Berichte) und die Antwort bekommt die
Form Ursache · Massnahme · Quelle · Gueltigkeit - oder eine Eskalation,
wenn nichts belegt ist.

Reine Textfunktionen, ohne Modell - pruefbar in dialogtest.py.
"""
import re

_FELD = re.compile(
    r"\b(anlage|maschine|linie|aggregat|fehlercode|fehler-?nr\.?|code|alarm|symptom|"
    r"rolle|material|bauteil)\s*[:=]\s*([^;,\n·|]{1,80})", re.I)
_CODE = re.compile(
    r"\b(?:fehler(?:code|nummer|nr\.?)?|alarm|error|störung|stoerung|code|meldung)\s*[:#]?\s*"
    r"([A-Z]{0,4}[-_ ]?\d{2,6}[A-Z]?)\b|\b([A-Z]{1,3}[-_]?\d{3,5})\b", re.I)
_STOERWORT = re.compile(
    r"\b(st(ö|oe)rung|st(ö|oe)rfall|fehler(?:code|meldung|bild)?|alarm|ausfall|defekt|"
    r"stillstand|blockiert|l(ä|ae)uft nicht|geht nicht|tropft|leckt|quietscht|"
    r"(ü|ue)berhitzt|vibriert|ausschuss|troubleshoot|fehlersuche|ursache|abhilfe|"
    r"ma(ß|ss)nahme|was tun|wie beheb)", re.I)
_ANLAGE_IM_SATZ = re.compile(
    r"\b(?:an|bei|auf)\s+(?:der|dem|die|unserer|unserem)?\s*"
    r"((?:[A-ZÄÖÜ][\w\-]{1,20}\s?){1,3}\d{0,4}|[A-Z]{2,6}[- ]?\d{1,4})", re.I)


def erkennen(frage):
    """{'anlage','fehlercode','symptom','rolle','material'} - leere Strings, wenn nichts."""
    f = frage or ""
    aus = {"anlage": "", "fehlercode": "", "symptom": "", "rolle": "", "material": ""}
    for m in _FELD.finditer(f):
        k, v = m.group(1).lower(), m.group(2).strip()
        if k in ("anlage", "maschine", "linie", "aggregat"):
            aus["anlage"] = aus["anlage"] or v
        elif k in ("fehlercode", "fehler-nr", "fehler-nr.", "fehlernr", "code", "alarm"):
            aus["fehlercode"] = aus["fehlercode"] or v
        elif k == "symptom":
            aus["symptom"] = aus["symptom"] or v
        elif k == "rolle":
            aus["rolle"] = v
        elif k in ("material", "bauteil"):
            aus["material"] = v
    if not aus["fehlercode"]:
        m = _CODE.search(f)
        if m:
            aus["fehlercode"] = (m.group(1) or m.group(2) or "").strip()
    if not aus["anlage"]:
        m = _ANLAGE_IM_SATZ.search(f)
        if m and not _STOERWORT.match(m.group(1)):
            aus["anlage"] = m.group(1).strip()
    if not aus["symptom"]:
        # Der Satzteil mit dem Stoerwort, ohne Feldangaben
        rest = _FELD.sub(" ", f)
        m = _STOERWORT.search(rest)
        if m:
            anfang = max(rest.rfind(",", 0, m.start()), rest.rfind(".", 0, m.start()), -1) + 1
            ende = min([x for x in (rest.find(".", m.end()), rest.find("?", m.end()), rest.find(",", m.end())) if x > 0] or [len(rest)])
            aus["symptom"] = rest[anfang:ende].strip(" .?!")[:120]
    return aus


def ist_stoerfall(frage):
    """Stoerfall-Eingabe? Ein Fehlercode oder ein Stoerwort mit Anlagenbezug."""
    k = erkennen(frage)
    if k["fehlercode"]:
        return True
    return bool(_STOERWORT.search(frage or "")) and bool(k["anlage"] or k["symptom"])


def suchbegriffe(kontext, frage=""):
    """Die Begriffe fuer die Suche in Fehlerkatalogen und Handbuechern."""
    aus = []
    for k in ("fehlercode", "anlage", "symptom", "material"):
        v = (kontext or {}).get(k) or ""
        if v:
            aus.append(v)
    if not aus and frage:
        aus.append(frage)
    return aus


def kontext_zeile(kontext):
    teile = [("%s: %s" % (k.capitalize(), v)) for k, v in (kontext or {}).items() if v]
    return " · ".join(teile)
