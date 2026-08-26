"""K3 - Metadaten je Dokument (Implementierungsleitfaden S. 51-55, 86, 88).

Jeder Bereich kann eine Datei `dokumente/<bereich>/metadaten.json` fuehren:

    {
      "HW14-Handbuch": {"freigabe": "freigegeben", "owner": "M. Schmitz",
                        "version": "3", "gueltig_bis": "2027-06-30",
                        "review_am": "2026-12-01", "ki": "ja",
                        "anlage": "Spritzgiessmaschine A3", "art": "Handbuch"},
      "Pruefbericht-2024-117": {"freigabe": "entwurf", "ki": "nein"}
    }

Felder (alle optional): freigabe = entwurf | geprueft | freigegeben | archiviert ·
owner · version · gueltig_bis (JJJJ-MM-TT) · review_am · ki = ja | nein
("fuer KI ausschliessen": Dokument bleibt liegen, wird aber weder gelistet
noch durchsucht noch zitiert) · anlage · fehlercodes (Liste) · art.

Schalter je Bereich in bereich.json: "nur_freigegebene": true -> nur Dokumente
mit freigabe = freigegeben sind fuer die KI sichtbar (Truth Gate).

Die Schluessel sind die Kennungen (Dateiname ohne .pdf); Gross/Klein und
Satzzeichen sind egal. Die Datei wird bei jeder Frage auf ihren Zeitstempel
geprueft - Aenderungen wirken sofort, ohne Neustart.
"""
import datetime
import json
import os
import re
import threading

_SPERRE = threading.Lock()
_CACHE = {}          # wurzel -> (mtime, daten, mtime_bereich, konf)

FREIGABEN = ("entwurf", "geprueft", "freigegeben", "archiviert")


def _grund(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower().replace(".pdf", "").replace(".md", ""))


def bereich_von_pfad(pdf_pfad, pdf_ordner):
    """/daten/pdfs/<bereich>/archiv/X.pdf -> <bereich>, sonst None."""
    try:
        rel = os.path.relpath(os.path.abspath(pdf_pfad), os.path.abspath(pdf_ordner))
    except Exception:
        return None
    teile = rel.split(os.sep)
    return teile[0] if len(teile) >= 2 and not teile[0].startswith("..") else None


def _laden(wurzel):
    """(daten, konf) fuer einen Bereichsordner - mit Zeitstempel-Cache."""
    if not wurzel:
        return {}, {}
    pfad = os.path.join(wurzel, "metadaten.json")
    konf_pfad = os.path.join(wurzel, "bereich.json")
    def _stempel(p):
        try:
            st = os.stat(p)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None
    m1, m2 = _stempel(pfad), _stempel(konf_pfad)
    with _SPERRE:
        alt = _CACHE.get(wurzel)
        if alt and alt[0] == m1 and alt[2] == m2:
            return alt[1], alt[3]
    daten, konf = {}, {}
    if m1 is not None:
        try:
            with open(pfad, encoding="utf-8") as fh:
                roh = json.load(fh) or {}
            daten = {_grund(k): (v if isinstance(v, dict) else {}) for k, v in roh.items()}
        except Exception:
            daten = {}
    if m2 is not None:
        try:
            with open(konf_pfad, encoding="utf-8") as fh:
                konf = json.load(fh) or {}
        except Exception:
            konf = {}
    with _SPERRE:
        _CACHE[wurzel] = (m1, daten, m2, konf)
    return daten, konf


def angaben(kennung, wurzel):
    """Die Metadaten eines Dokuments - oder {}."""
    daten, _ = _laden(wurzel)
    return dict(daten.get(_grund(kennung)) or {})


def _abgelaufen(gueltig_bis, heute=None):
    if not gueltig_bis:
        return False
    try:
        d = datetime.date.fromisoformat(str(gueltig_bis)[:10])
    except Exception:
        return False
    return d < (heute or datetime.date.today())


def fuer_ki(kennung, wurzel, heute=None):
    """Darf die KI dieses Dokument listen, durchsuchen, zitieren?
    Gruende fuer NEIN: ki = nein · archiviert · Bereich verlangt Freigabe und
    das Dokument ist nicht freigegeben · Gueltigkeit abgelaufen (dann nur,
    wenn der Bereich 'abgelaufene_ausschliessen' setzt)."""
    daten, konf = _laden(wurzel)
    m = daten.get(_grund(kennung)) or {}
    if str(m.get("ki", "ja")).strip().lower() in ("nein", "no", "false", "0"):
        return False
    if str(m.get("freigabe", "")).strip().lower() == "archiviert":
        return False
    if konf.get("nur_freigegebene") and str(m.get("freigabe", "")).strip().lower() != "freigegeben":
        return False
    if konf.get("abgelaufene_ausschliessen") and _abgelaufen(m.get("gueltig_bis"), heute):
        return False
    return True


def grund_ausschluss(kennung, wurzel, heute=None):
    daten, konf = _laden(wurzel)
    m = daten.get(_grund(kennung)) or {}
    if str(m.get("ki", "ja")).strip().lower() in ("nein", "no", "false", "0"):
        return "für KI ausgeschlossen"
    if str(m.get("freigabe", "")).strip().lower() == "archiviert":
        return "archiviert"
    if konf.get("nur_freigegebene") and str(m.get("freigabe", "")).strip().lower() != "freigegeben":
        return "nicht freigegeben (Bereich verlangt Freigabe)"
    if konf.get("abgelaufene_ausschliessen") and _abgelaufen(m.get("gueltig_bis"), heute):
        return "Gültigkeit abgelaufen"
    return ""


def status_zeile(kennung, wurzel, heute=None):
    """Kurz fuer Listen und Fusszeilen: 'freigegeben · v3 · gültig bis 2027-06-30'."""
    m = angaben(kennung, wurzel)
    if not m:
        return ""
    teile = []
    if m.get("freigabe"):
        teile.append(str(m["freigabe"]))
    if m.get("version"):
        teile.append("v%s" % m["version"])
    if m.get("gueltig_bis"):
        teile.append(("⚠ abgelaufen seit %s" if _abgelaufen(m["gueltig_bis"], heute) else "gültig bis %s") % m["gueltig_bis"])
    if m.get("owner"):
        teile.append("Owner %s" % m["owner"])
    return " · ".join(teile)


def warnung(kennung, wurzel, heute=None):
    """Was der Mensch bei einer Antwort aus diesem Dokument wissen muss."""
    m = angaben(kennung, wurzel)
    aus = []
    f = str(m.get("freigabe", "")).strip().lower()
    if f and f != "freigegeben":
        aus.append("Status „%s“ — nicht freigegeben" % f)
    if _abgelaufen(m.get("gueltig_bis"), heute):
        aus.append("Gültigkeit abgelaufen (%s)" % m["gueltig_bis"])
    return "; ".join(aus)


def stoerfall_felder(kennung, wurzel):
    """anlage / fehlercodes / art - fuer die Stoerfallsuche."""
    m = angaben(kennung, wurzel)
    codes = m.get("fehlercodes") or m.get("fehlercode") or []
    if isinstance(codes, str):
        codes = [c.strip() for c in re.split(r"[,;\s]+", codes) if c.strip()]
    return {"anlage": str(m.get("anlage") or ""), "fehlercodes": [str(c) for c in codes],
            "art": str(m.get("art") or "")}
