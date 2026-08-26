#!/usr/bin/env python3
"""Schicht 2 der Dialog-Testreihe: das Absichts-Modell gegen echte Dialoge.

Laeuft AUF der Anlage (braucht das Modell und den Katalog):

    docker exec ki4ki-pruef-proxy python3 /app/absichttest.py

Jeder Fall: Gespraechszustand + neue Eingabe -> erwartete Aktion (und ggf.
Dokument). Trefferquote >= 90 % ist die Bedingung, den Schalter
KI4KI_ABSICHT_MODELL standardmaessig auf 1 zu stellen (ARCHITEKTUR-GESPRAECH §3).
Die Faelle stammen aus den Live-Dialogen vom 25./26.08. und den Szenarien
in GESPRAECH-ANFORDERUNGEN.md §5.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import absicht      # noqa: E402

try:
    import assistent    # noqa: E402
    import bestand      # noqa: E402
except Exception:
    assistent = bestand = None

DOKUMENTE_STANDARD = [
    "DS-23-004 — Malte Schön (2023): Eine simulationsgestützte Methodik zur Dimensionierung von statischen und dynamischen Mischteilen für die Extrusion",
    "DS-23-005 — Jonas Maximilian Müller (2023): Vorhersage des dehnratenabhängigen Schädigungsverhaltens von endlosfaserverstärkten Kunststoffen",
    "DS-24-005 — Fabian Becker (2024): Untersuchung des Einflusses einer Mitteneinspannung auf das statische und Ermüdungsverhalten von glasfaserverstärkten Kunststoffblattfedern",
    "DS-24-006 — Thilo Köbel (2024): Geometrieabhängige Einspritzprofilierung für das Spritzgießverfahren",
    "DS-24-007 — Maximilian Kramer (2024): Werkstoffgerechte Auslegung von Direktverschraubungen in duroplastischen Formmassen",
]
NAMEN = ["DS-23-004.md", "DS-23-005.md", "DS-24-005.md", "DS-24-006.md", "DS-24-007.md"]

B = "DS-24-005.md"
FAELLE = [
    # (Beschreibung, schritte, faden_dok, letzte_art, eingabe, erwartete Aktion, erwartetes Dokument oder None/"*")
    ("Verfasser nennen", [], None, None, "Kannst du mir von der Dissertation von Fabian Becker eine Zusammenfassung machen?", "zusammenfassung", B),
    ("Folge: gesamte Zusammenfassung", [("Fasse Becker zusammen", "zusammenfassung", "Die Arbeit untersucht ...")], B, "zusammenfassung", "Schreib mir eine gesamte Zusammenfassung", "zusammenfassung", B),
    ("Folge: Diagramm", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Kannst du mir ein Diagramm aus der Arbeit zeigen?", "bild", B),
    ("Folge: zaehlen", [("zeig ein Diagramm", "bild", "Bild 1.1 ...")], B, "bild", "Wieviele Diagramme hat diese Arbeit?", "fakten", B),
    ("Folge: Ziel", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Was ist das Ziel der Arbeit?", "frage_an_dokument", B),
    ("Rueckmeldung falsch", [("Was ist das Ziel der Arbeit?", "faden", "Das Ziel ist ...")], B, "faden", "das ist falsch!", "rueckmeldung", "*"),
    ("Rueckmeldung sicher", [("Was ist das Ziel?", "faden", "...")], B, "faden", "Sicher", "rueckmeldung", "*"),
    ("Selbes Thema", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Haben wir Dissertationen zum selben Thema?", "bestand", "*"),
    ("Anlage-Frage", [("Was ist das Ziel?", "faden", "...")], B, "faden", "Hast du jetzt nur diese eine Dissertation angedockt und kann dich nur damit sachen fragen?", "anlage", "*"),
    ("Themenwechsel Mueller", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Was sagt Müller zum Schädigungsverhalten?", "frage_an_dokument", "DS-23-005.md"),
    ("Tippfehler Verfasser", [], None, None, "fasse mal die arbeit von beker zusammen", "zusammenfassung", B),
    ("Kennung", [], None, None, "Worum geht es in DS-24-006?", "zusammenfassung", "DS-24-006.md"),
    ("Kennung Frage", [], None, None, "Welche Einspritzprofile untersucht DS-24-006?", "frage_an_dokument", "DS-24-006.md"),
    ("Bestand", [], None, None, "Welche Dokumente haben wir?", "bestand", "*"),
    ("Bestand Thema", [], None, None, "Was habt ihr zum Thema Spritzgießen?", "bestand", "*"),
    ("Klaerfrage leer", [], None, None, "Fasse die Dissertation zusammen", "klaerfrage", "*"),
    ("Klaerfrage Bild leer", [], None, None, "Zeig mir ein Diagramm", "klaerfrage", "*"),
    ("Vergleich", [], None, None, "Vergleiche die Methodik von Becker und Müller", "vergleich", B),
    ("Widerspruch", [], None, None, "Widersprechen sich Becker und Müller beim Ermüdungsverhalten?", "vergleich", B),
    ("Export CSV", [("Vergleiche Becker und Müller", "vergleich", "| Aspekt | ...")], B, "vergleich", "Exportiere das als CSV", "export", "*"),
    ("BibTeX", [], None, None, "Gib mir den Bestand als BibTeX", "export", "*"),
    ("Abkuerzung", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Wofür steht GFK?", "abkuerzung", B),
    ("Kennwert", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Welche E-Modul-Werte nennt die Arbeit?", "frage_an_dokument", B),
    ("Ganzer Bestand", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "im ganzen Bestand: welche Arbeiten nennen Schwindung?", "gesamtbestand", "*"),
    ("Andere Arbeiten", [("Was ist das Ziel?", "faden", "...")], B, "faden", "Gibt es dazu auch andere Arbeiten?", "bestand", "*"),
    ("Rueckkehr", [("Fasse Becker zusammen", "zusammenfassung", "..."), ("Was sagt Müller dazu?", "faden", "...")], "DS-23-005.md", "faden", "und bei Becker?", "frage_an_dokument", B),
    ("Bild Nummer", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "Zeig mir Bild 3.2", "bild", B),
    ("Seiten", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "wie viele seiten hat das ding", "fakten", B),
    ("Verfasser-Frage", [("Worum geht es in DS-24-006?", "zusammenfassung", "...")], "DS-24-006.md", "zusammenfassung", "wer hat das geschrieben?", "fakten", "DS-24-006.md"),
    ("Smalltalk", [], None, None, "Hallo, wie geht's?", "smalltalk", "*"),
    ("Was kannst du", [], None, None, "Was kannst du alles?", "anlage", "*"),
    ("Umgangssprache", [("Fasse Becker zusammen", "zusammenfassung", "...")], B, "zusammenfassung", "jo und was kam dabei raus?", "frage_an_dokument", B),
]


def main():
    dokumente = DOKUMENTE_STANDARD
    namen = NAMEN
    # Auf der Anlage: den echten Katalog nehmen, wenn er die Testdokumente kennt
    if assistent and bestand:
        try:
            ang = bestand.angaben("DS-24-005")
            if ang and "Becker" in (ang.get("verfasser") or ""):
                pass    # Testliste bleibt - sie enthaelt genau die Faelle
        except Exception:
            pass
    treffer, gesamt, dauer = 0, 0, []
    fehl = []
    for beschr, schritte, faden_dok, letzte_art, eingabe, erw_aktion, erw_dok in FAELLE:
        a, grund, ms = absicht.erkennen(eingabe, schritte, faden_dok, letzte_art, [], dokumente, namen)
        dauer.append(ms)
        gesamt += 1
        ok = bool(a) and a["aktion"] == erw_aktion and (erw_dok in ("*", None) or a.get("dokument") == erw_dok)
        if ok:
            treffer += 1
        else:
            fehl.append((beschr, eingabe, erw_aktion, erw_dok, a and a["aktion"], a and a.get("dokument"), a and a.get("sicherheit"), grund))
        print("%s %-24s %-60s -> %s %s (%.2f) %d ms%s" % (
            "ok  " if ok else "FEHL", beschr, eingabe[:60], a and a["aktion"], a and a.get("dokument"),
            a["sicherheit"] if a else 0, ms, "" if ok else "   erwartet %s %s [%s]" % (erw_aktion, erw_dok, grund)))
    quote = 100.0 * treffer / max(1, gesamt)
    print("\nTrefferquote: %d/%d = %.0f %%  |  Dauer: Ø %d ms, max %d ms  |  Modell: %s" % (
        treffer, gesamt, quote, sum(dauer) / max(1, len(dauer)), max(dauer or [0]), absicht.MODELL))
    print("Bedingung fuer Standard 'an': >= 90 %% -> %s" % ("ERFUELLT" if quote >= 90 else "NICHT erfuellt"))
    return 0 if quote >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
