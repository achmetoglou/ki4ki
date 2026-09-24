"""Wird rot, wenn jemand die Listen der Dokumentarten wieder SCHLIESST.

⛔ WOZU: Die Anlage wurde fuer HOCHSCHULSCHRIFTEN gebaut. Im Bestand liegen
   inzwischen die Geschaeftsunterlagen eines Auftragslabors - Rechnungen,
   Angebote, Anschreiben, Bestellungen, Auftragsbestaetigungen, Laufzettel,
   Reisekostenabrechnungen. Ueberall, wo die Liste der Dokumentarten
   geschlossen ist, wird eine Rechnung zu etwas ANDEREM gemacht, statt
   unbekannt zu bleiben:

     - kategorie.STANDARD kannte 15 Arten, keine einzige geschaeftliche
     - die Kennung aus dem Dateinamen gewann blind: "PA-2026-001" (eine
       Preisanfrage) wurde zur "Projektarbeit", "M-2026-0042" (Mahnung) zur
       "Masterarbeit"
     - _FRAGEWORTE kannte "normen" und "dissertationen", aber nicht
       "rechnungen" - die Frage bekam keinen Filter
     - bestand.art_von() behauptete dasselbe noch einmal

   Das Ergebnis wird BEI DER AUFNAHME in die Dateien geschrieben. Faellt es
   falsch aus, steht es dort, bis das Dokument neu aufgenommen wird - eine
   Korrektur an der Frage kommt zu spaet.

⭐ ZU JEDER PRUEFUNG GEHOERT DIE GEGENPROBE. Dieses Programm prueft nicht
   nur, dass heute alles stimmt. Es schliesst die Listen anschliessend
   ABSICHTLICH wieder - eine nach der anderen - und verlangt, dass genau die
   dazugehoerigen Pruefungen rot werden. Eine Pruefung, die auch dann gruen
   bleibt, prueft nichts und wird hier als Fehler gemeldet.

Aufruf:   python3 kategorietest.py
          python3 kategorietest.py -a      (auch die Gegenproben einzeln zeigen)
"""
import json
import os
import re
import sys
import tempfile

import bestand
import kategorie

HIER = os.path.dirname(os.path.abspath(__file__))
WORKFLOW = os.path.join(HIER, "..", "n8n-workflows", "1_KI4KI-Masse-Ingest.json")

# Kategorien, in denen eine Rechnung NIE landen darf.
HOCHSCHUL = {"Dissertation", "Masterarbeit", "Bachelorarbeit", "Projektarbeit",
             "Diplomarbeit", "Studienarbeit"}


def _kopf(dokumenttyp="", tags=()):
    """Der Kopf, den die Aufnahme dem Dokument voranstellt (kategorie.aus_kopf)."""
    return {"dokumenttyp": dokumenttyp, "tags": list(tags), "keywords": [],
            "methoden": [], "vorgabe": "", "themen_vorgabe": []}


# ---------------------------------------------------------------- Pruefungen
#
# Jede gibt (ist_gut, Befund) zurueck. Der Befund steht auch im gruenen Fall
# da: wer ihn liest, sieht die gemessene Antwort, nicht nur ein "ok".

def p_rechnung_nicht_hochschule():
    """Eine Rechnung landet in KEINER Hochschulkategorie."""
    ist = kategorie.zuordnen(_kopf("Invoice"), dateiname="Rechnung_274821.pdf",
                             titel="Rechnung Nr. 274821", kennung="Rechnung_274821.pdf")
    return ist == "Rechnung", "Rechnung_274821.pdf -> %s" % ist


def p_rechnung_ohne_dokumenttyp():
    """Auch ohne brauchbaren Dokumenttyp bleibt eine Rechnung eine Rechnung.

    Das ist der Fall, den das Modell heute liefert: es MUSS einen Typ aus
    einer geschlossenen Liste vergeben und schreibt "Other" - oder, schlimmer,
    "Datasheet", weil die Rechnung Zahlen und eine Tabelle traegt.
    """
    ist = kategorie.zuordnen(_kopf("Other"), dateiname="Rechnung 2026-0041.pdf",
                             titel="", kennung="Rechnung 2026-0041.pdf")
    return ist == "Rechnung", "Dokumenttyp 'Other' + Dateiname -> %s" % ist


def p_pa_ist_keine_projektarbeit():
    """PA-2026-001-Preisanfrage ist KEINE Projektarbeit.

    Die Kennung "PA" gehoert im Hochschulbestand zur Projektarbeit und im
    Geschaeftsverkehr zur Preisanfrage. Unterschieden wird an der Jahreszahl:
    zweistellig = Hochschule, vierstellig = Geschaeft.
    """
    ist = kategorie.zuordnen(_kopf(), dateiname="PA-2026-001-Preisanfrage.pdf",
                             titel="", kennung="PA-2026-001-Preisanfrage.pdf")
    return ist != "Projektarbeit" and ist == "Preisanfrage", \
        "PA-2026-001-Preisanfrage.pdf -> %s" % ist


def p_m_ist_keine_masterarbeit():
    """M-2026-0042 (Mahnung) ist keine Masterarbeit."""
    ist = kategorie.zuordnen(_kopf(), dateiname="M-2026-0042-Mahnung.pdf",
                             titel="", kennung="M-2026-0042-Mahnung.pdf")
    return ist == "Mahnung", "M-2026-0042-Mahnung.pdf -> %s" % ist


def p_hochschulkennung_traegt_weiter():
    """Der echte Hochschulbestand wird weiterhin richtig zugeordnet."""
    faelle = [("DS-24-005.pdf", "Dissertation"), ("BS-00-000.pdf", "Bachelorarbeit"),
              ("M-24-003.pdf", "Masterarbeit"), ("D-00-000.pdf", "Masterarbeit"),
              ("S-23-001.pdf", "Projektarbeit"), ("PA-24-002.pdf", "Projektarbeit")]
    schlecht = []
    for name, soll in faelle:
        ist = kategorie.zuordnen(_kopf(), dateiname=name, titel="", kennung=name)
        if ist != soll:
            schlecht.append("%s -> %s statt %s" % (name, ist, soll))
    return not schlecht, ("; ".join(schlecht) if schlecht
                          else "6 Kennungen geprueft, alle richtig (DS-24-005 -> Dissertation)")


def p_geschaeftstyp_schlaegt_kennung():
    """Meldet die Aufnahme eine Rechnung, gewinnt sie gegen die Kennung.

    Eine Mahnung mit zweistelliger Jahreszahl ("M-24-0042") sieht von aussen
    aus wie eine Masterarbeit. Nur die Aufnahme kann das noch auseinander
    halten - also muss ihr Wort hier schwerer wiegen.
    """
    ist = kategorie.zuordnen(_kopf("Invoice"), dateiname="M-24-0042.pdf",
                             titel="", kennung="M-24-0042.pdf")
    return ist == "Rechnung", "Dokumenttyp 'Invoice' + Kennung M-24-0042 -> %s" % ist


def p_fragewoerter():
    """Wer nach Geschaeftsunterlagen fragt, bekommt einen Kategoriefilter."""
    faelle = [("Zeig mir alle Angebote", "Angebot"),
              ("Welche Rechnungen haben wir von 2026?", "Rechnung"),
              ("Liste aller Laufzettel", "Laufzettel"),
              ("Was haben wir an Bestellungen?", "Bestellung"),
              ("Welche Geheimhaltungsvereinbarungen gibt es?", "Geheimhaltungsvereinbarung"),
              ("Welche Normen haben wir?", "Norm/Richtlinie")]
    schlecht = []
    for frage, soll in faelle:
        ist, _wort = kategorie.gefragte(frage)
        if ist != soll:
            schlecht.append("%r -> %s statt %s" % (frage, ist, soll))
    return not schlecht, ("; ".join(schlecht) if schlecht
                          else "6 Fragen geprueft, alle mit Filter")


def p_art_von_raet_nicht():
    """bestand.art_von() sagt bei einer Geschaeftsnummer lieber nichts."""
    falsch = bestand.art_von("PA-2026-001-Preisanfrage.pdf")
    richtig = bestand.art_von("DS-24-005.pdf")
    return falsch is None and richtig == "Dissertation", \
        "PA-2026-001-... -> %s | DS-24-005 -> %s" % (falsch, richtig)


def p_geschaeftswort_erkannt_ohne_kennungsfilter():
    """"Rechnungen" ist als Dokumentart bekannt - aber nicht als Kennung.

    (None, "rechnungen") ist genau richtig: das Wort ist erkannt, gefiltert
    wird aber ueber die Kategorie. Eine Kennung "RE" waere hier falsch - sie
    steht in keinem Dateinamen und die Auskunft meldete "keine gefunden".
    """
    kennzeichen, wort = bestand.gefragte_art("Was haben wir alles an Rechnungen?")
    hochschule = bestand.gefragte_art("Welche Dissertationen haben wir?")
    return (wort == "rechnungen" and kennzeichen is None and hochschule[0] == "DS"), \
        "Rechnungen -> (%s, %s) | Dissertationen -> %s" % (kennzeichen, wort, hochschule[0])


def p_alte_kategorienliste_sperrt_nicht_aus():
    """Eine kategorien.txt von gestern darf die neuen Arten nicht aussperren.

    Jeder Bereich kann eine eigene kategorien.txt fuehren. Die vorhandenen
    wurden geschrieben, als es die Geschaeftsarten noch nicht gab - ohne
    diesen Nachtrag waere die Liste dort weiterhin geschlossen.
    """
    with tempfile.TemporaryDirectory() as ordner:
        with open(os.path.join(ordner, kategorie.DATEI), "w", encoding="utf-8") as fh:
            fh.write("# Stand von gestern - nur Hochschulschriften\n")
            fh.write("Dissertation: dissertation, doktorarbeit\n")
            fh.write("Norm/Richtlinie: norm, richtlinie\n")
            fh.write("Sonstiges:\n")
        namen = kategorie.namen(ordner)
        ist = kategorie.zuordnen(_kopf("Invoice"), dateiname="Rechnung_274821.pdf",
                                 titel="", kennung="Rechnung_274821.pdf", wurzel=ordner)
        eigene_zuerst = namen[0] == "Dissertation"
    return ist == "Rechnung" and eigene_zuerst, \
        "Bereichsliste mit 3 Zeilen -> %d Kategorien, Rechnung -> %s" % (len(namen), ist)


def p_workflow_typen_haben_eine_kategorie():
    """Jeder document_type aus der Aufnahme muss hier ankommen.

    Die Aufnahme (n8n, Knoten "HTTP Request1") schreibt ihren Wert als
    Kopfzeile "Dokumenttyp:" in die Markdown-Datei, und das ist die erste und
    hoechstrangige Stoffquelle von zuordnen(). Ein Typ, den diese Datei nicht
    kennt, faellt auf "Sonstiges" - die Anlage wuesste dann von einer Rechnung,
    koennte sie aber nicht einsortieren. "Other" MUSS "Sonstiges" werden: das
    ist die ehrliche Antwort, wenn nichts passt.
    """
    try:
        with open(WORKFLOW, encoding="utf-8") as fh:
            daten = json.load(fh)
    except OSError as fehler:
        return False, "Workflow nicht lesbar, Pruefung nicht durchfuehrbar: %s" % fehler
    koerper = [n for n in daten["nodes"] if n.get("name") == "HTTP Request1"]
    if len(koerper) != 1:
        return False, "Knoten 'HTTP Request1' nicht eindeutig (%d)" % len(koerper)
    m = re.search(r"document_type is English and one of: (.+?), Other\.",
                  koerper[0]["parameters"]["jsonBody"])
    if not m:
        return False, "Typenliste im Systemtext nicht gefunden"
    typen = [t.strip() for t in m.group(1).split(",") if t.strip()]
    ohne = [t for t in typen
            if kategorie.zuordnen(_kopf(t), dateiname="", titel="", kennung="") == "Sonstiges"]
    andere = kategorie.zuordnen(_kopf("Other"), dateiname="", titel="", kennung="")
    return (not ohne and andere == "Sonstiges"), \
        ("ohne Kategorie: %s" % ", ".join(ohne) if ohne
         else "%d Typen, alle zugeordnet; 'Other' -> %s" % (len(typen), andere))


PRUEFUNGEN = [
    ("rechnung", p_rechnung_nicht_hochschule),
    ("rechnung-ohne-typ", p_rechnung_ohne_dokumenttyp),
    ("pa-preisanfrage", p_pa_ist_keine_projektarbeit),
    ("m-mahnung", p_m_ist_keine_masterarbeit),
    ("hochschulkennung", p_hochschulkennung_traegt_weiter),
    ("typ-schlaegt-kennung", p_geschaeftstyp_schlaegt_kennung),
    ("fragewoerter", p_fragewoerter),
    ("art-von", p_art_von_raet_nicht),
    ("bestandswort", p_geschaeftswort_erkannt_ohne_kennungsfilter),
    ("alte-bereichsliste", p_alte_kategorienliste_sperrt_nicht_aus),
    ("workflow-typen", p_workflow_typen_haben_eine_kategorie),
]


# --------------------------------------------------------------- Gegenproben
#
# ⭐ Hier wird die Anlage ABSICHTLICH kaputt gemacht - jede Liste einmal
#   wieder so geschlossen, wie sie vorher war. Danach MUESSEN die genannten
#   Pruefungen rot werden. Wird eine davon gruen, prueft sie nichts.

def _frage_muster_neu():
    """_FRAGE_MUSTER aus _FRAGEWORTE neu bauen (wie kategorie.py:60)."""
    woerter = {w for ws in kategorie._FRAGEWORTE.values() for w in ws}
    kategorie._FRAGE_MUSTER = re.compile(
        r"\b(%s)\b" % "|".join(sorted(woerter, key=len, reverse=True)), re.I)


def _art_muster_neu():
    """bestand._ART_MUSTER neu bauen (wie bestand.py:83)."""
    bestand._ART_MUSTER = re.compile(
        r"\b(%s)\b" % "|".join(sorted(bestand._WORT_ZU_ART, key=len, reverse=True)), re.I)


def m_listen_geschlossen():
    """Die Geschaeftskategorien wieder aus STANDARD streichen."""
    kategorie.STANDARD = [(n, w) for n, w in kategorie.STANDARD
                          if n not in kategorie.GESCHAEFTLICH]


def m_kennung_blind():
    """Das alte Muster: ein bis drei Buchstaben vor irgendeiner Ziffer."""
    kategorie._KENNUNG_MUSTER = re.compile(r"([A-Za-z]{1,3})[-_ ]?\d")


def m_geschaeftssperre_weg():
    """Die Kennung wieder ueber den gemeldeten Dokumenttyp stellen."""
    kategorie.GESCHAEFTLICH = set()


def m_fragewoerter_geschlossen():
    """Nur die Hochschul-Fragewoerter uebrig lassen."""
    kategorie._FRAGEWORTE = {n: w for n, w in kategorie._FRAGEWORTE.items()
                             if n not in kategorie.GESCHAEFTLICH}
    _frage_muster_neu()


def m_bestand_kennung_blind():
    """bestand.kennung() wieder blind machen."""
    bestand._KENNUNG_MUSTER = re.compile(r"([A-Za-z]{1,3})[-_ ]?\d")


def m_bestandswoerter_geschlossen():
    """Die Woerter ohne Kennung aus der Wortliste entfernen."""
    for wort in bestand._OHNE_KENNUNG:
        bestand._WORT_ZU_ART.pop(wort, None)
    _art_muster_neu()


GEGENPROBEN = [
    ("Geschaeftskategorien aus kategorie.STANDARD gestrichen", m_listen_geschlossen,
     ["rechnung", "rechnung-ohne-typ", "pa-preisanfrage", "m-mahnung",
      "typ-schlaegt-kennung", "alte-bereichsliste", "workflow-typen"]),
    ("kategorie._KENNUNG_MUSTER wieder blind", m_kennung_blind,
     ["pa-preisanfrage", "m-mahnung"]),
    ("kategorie.GESCHAEFTLICH geleert", m_geschaeftssperre_weg,
     ["typ-schlaegt-kennung"]),
    ("kategorie._FRAGEWORTE wieder geschlossen", m_fragewoerter_geschlossen,
     ["fragewoerter"]),
    ("bestand._KENNUNG_MUSTER wieder blind", m_bestand_kennung_blind,
     ["art-von"]),
    ("Geschaeftswoerter aus bestand._WORT_ZU_ART entfernt", m_bestandswoerter_geschlossen,
     ["bestandswort"]),
]


def _sicherung():
    """Alles merken, was eine Gegenprobe anfasst - danach zurueckstellen."""
    return {
        "STANDARD": list(kategorie.STANDARD),
        "GESCHAEFTLICH": set(kategorie.GESCHAEFTLICH),
        "KAT_MUSTER": kategorie._KENNUNG_MUSTER,
        "FRAGEWORTE": dict(kategorie._FRAGEWORTE),
        "FRAGE_MUSTER": kategorie._FRAGE_MUSTER,
        "BST_MUSTER": bestand._KENNUNG_MUSTER,
        "WORT_ZU_ART": dict(bestand._WORT_ZU_ART),
        "ART_MUSTER": bestand._ART_MUSTER,
    }


def _zuruecksetzen(alt):
    kategorie.STANDARD = list(alt["STANDARD"])
    kategorie.GESCHAEFTLICH = set(alt["GESCHAEFTLICH"])
    kategorie._KENNUNG_MUSTER = alt["KAT_MUSTER"]
    kategorie._FRAGEWORTE = dict(alt["FRAGEWORTE"])
    kategorie._FRAGE_MUSTER = alt["FRAGE_MUSTER"]
    bestand._KENNUNG_MUSTER = alt["BST_MUSTER"]
    bestand._WORT_ZU_ART.clear()
    bestand._WORT_ZU_ART.update(alt["WORT_ZU_ART"])
    bestand._ART_MUSTER = alt["ART_MUSTER"]


def _lauf():
    """Alle Pruefungen einmal durchlaufen -> {kuerzel: (gut, Befund)}."""
    aus = {}
    for kuerzel, fkt in PRUEFUNGEN:
        try:
            aus[kuerzel] = fkt()
        except Exception as fehler:                      # eine Ausnahme ist rot
            aus[kuerzel] = (False, "Ausnahme: %r" % (fehler,))
    return aus


def main(ausfuehrlich=False):
    print("=== Pruefung: sind die Listen der Dokumentarten offen?")
    ergebnis = _lauf()
    schlecht = 0
    for kuerzel, fkt in PRUEFUNGEN:
        gut, befund = ergebnis[kuerzel]
        schlecht += not gut
        print("   %-6s %-22s %s" % ("ok" if gut else "FALSCH", kuerzel, befund))
        if not gut and fkt.__doc__:
            print("          -> %s" % fkt.__doc__.strip().splitlines()[0])

    print()
    print("=== Gegenprobe: womit wird jede Pruefung rot?")
    print("    Jede Zeile schliesst EINE Liste wieder und nennt, was dann faellt.")
    alt = _sicherung()
    for beschreibung, mutation, erwartet in GEGENPROBEN:
        try:
            mutation()
            nachher = _lauf()
        finally:
            _zuruecksetzen(alt)
        gefallen = [k for k, (gut, _b) in nachher.items() if not gut]
        stumm = [k for k in erwartet if k not in gefallen]
        gut = not stumm
        schlecht += not gut
        print("   %-6s %s" % ("ok" if gut else "FALSCH", beschreibung))
        print("          rot: %s" % (", ".join(sorted(gefallen)) or "KEINE"))
        if stumm:
            print("          ⛔ bleibt gruen, obwohl sie fallen muesste: %s"
                  % ", ".join(stumm))
        if ausfuehrlich:
            for k in sorted(gefallen):
                print("            %-20s %s" % (k, nachher[k][1]))

    print()
    if schlecht:
        print("=== %d von %d Zeilen falsch." % (schlecht, len(PRUEFUNGEN) + len(GEGENPROBEN)))
    else:
        print("=== Alles gruen: %d Pruefungen, %d Gegenproben."
              % (len(PRUEFUNGEN), len(GEGENPROBEN)))
        print("    Die Listen sind offen - und jede Pruefung kann rot werden.")
    return 1 if schlecht else 0


if __name__ == "__main__":
    raise SystemExit(main("-a" in sys.argv or "--alles" in sys.argv))
