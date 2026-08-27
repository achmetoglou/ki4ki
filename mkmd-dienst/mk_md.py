#!/usr/bin/env python3
"""Baut aus Rohtext und Verschlagwortung die fertige Markdown-Datei.

Der Inhalt steckt jetzt in einer Funktion statt im Skriptrumpf. Grund:
Derselbe Aufbau wird an zwei Stellen gebraucht - von der Skript-Kette
(phase2 ueber tag.sh) und von n8n. Im n8n-Ablauf lag bisher eine eigene
Nachbildung in JavaScript, sogar in zwei Fassungen ("Markdown erzeugen"
und "Markdown erzeugen-fix"), und beide kannten die spaeteren Verbesserungen nicht:
durchnummerierte Seitenmarken, Verzeichnisputz, einseitige
Dokumente.

Zwei Nachbildungen derselben Sache driften auseinander - in einem
frueheren Fall waren es schon 325 Zeilen Unterschied. Deshalb hier eine
Fassung, die beide benutzen: das Skript direkt, n8n ueber den kleinen
Dienst in mkmd_dienst.py.

Aufruf unveraendert:
    mk_md.py <rohtext> <tagging.json> <basisname> <ziel.md>
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def seiten_nummerieren(content):
    """Aus Doclings Trennern werden Seitenmarken [Seite N].

    ⭐ ECHTE SEITEN: Traegt der Text nummerierte Trenner
    ([[SEITE:37]]), stammen die Zahlen aus bildbeschreibung.py, das sie am
    Docling-JSON (prov[].page_no) ausgerichtet hat. Sie werden DIREKT
    uebernommen. Grund: Docling setzt in die Markdown zu wenige Trenner
    (gemessen 41 statt 44) - das blosse Durchzaehlen lief darum mit dem
    Dokument immer weiter daneben (+1, +2, +3 ...). Betraf 17,5% der
    Dokumente, wachsend.
    """
    if "[[SEITE:" in content:
        teile = re.split(r"\[\[SEITE:(\d+)\]\]", content)
        # teile: [vor_erster_marke, "n1", text1, "n2", text2, ...]
        neu = []
        if teile[0].strip():
            neu.append(teile[0])          # seltener Vorspann ohne Seite
        for i in range(1, len(teile) - 1, 2):
            neu.append("\n\n[Seite " + teile[i] + "]\n\n")
            neu.append(teile[i + 1])
        return "".join(neu).lstrip("\n")

    # ALTER WEG (raw.md ohne echte Nummern): durchzaehlen wie bisher.
    if "[[SEITE]]" in content:
        teile = content.split("[[SEITE]]")
        neu = ["[Seite 1]\n"]
        for i, t in enumerate(teile):
            neu.append(t)
            if i < len(teile) - 1:
                neu.append("\n\n[Seite " + str(i + 2) + "]\n\n")
        return "".join(neu)
    # Kein Trenner im Text heisst: ein einseitiges Dokument. Docling setzt
    # die Marke nur ZWISCHEN Seiten. Ohne Marke gibt es spaeter keine
    # Seitenzahl im Beleg - und ohne Seitenzahl keinen Sprung ins Original.
    # Betraf 27 Dokumente, fast alles einseitige
    # AuW-Lerneinheiten.
    return "[Seite 1]\n\n" + content


def verzeichnisse_putzen(content):
    """Inhalts-, Abbildungs- und Tabellenverzeichnisse entfernen.

    Sie enthalten keine Aussage, aber sehr viele Fachbegriffe auf engem
    Raum - bei der Suche gewinnen sie deshalb gegen echten Fliesstext. Eine
    Fachfrage lieferte aus der einschlaegigsten Arbeit
    ausgerechnet das Inhaltsverzeichnis zurueck.

    Entfernt werden NUR Navigationszeilen (Punktfuehrung mit Seitenzahl);
    Kurzfassung und Abstract bleiben stehen, die sind inhaltlich wertvoll.
    """
    try:
        from vorspann_finden import putze
        content, weg = putze(content)
        if weg:
            print("  Verzeichniszeilen entfernt:", weg, "Zeichen",
                  file=sys.stderr)
        return content
    except Exception as e:
        print("  WARNUNG Verzeichnisputz uebersprungen:", e, file=sys.stderr)
        return content


def baue_markdown(rohtext, tagging, basisname, jetzt=None):
    """Die fertige Markdown-Datei als Zeichenkette.

    rohtext   Doclings Ausgabe, noch mit [[SEITE]]-Trennern
    tagging   das Ergebnis der Verschlagwortung als dict (darf leer sein)
    basisname Dateiname ohne Endung - wird Titel und Quellenangabe
    jetzt     Zeitstempel; nur fuer Tests, sonst die aktuelle Zeit
    """
    content = seiten_nummerieren(rohtext)
    content = verzeichnisse_putzen(content)

    tags = tagging if isinstance(tagging, dict) else {}

    def lst(key):
        v = tags.get(key)
        return [str(i) for i in v] if isinstance(v, list) else []

    meta = ["Quelle: " + basisname + ".pdf"]
    for label, key in (("Dokumenttyp", "document_type"),
                       ("Sprache", "language"),
                       ("Domain", "domain"), ("Subdomain", "subdomain")):
        if tags.get(key):
            meta.append(label + ": " + str(tags[key]))
    if tags.get("kategorie_vorgabe"):
        meta.append("Kategorie (Vorgabe): " + str(tags["kategorie_vorgabe"]))   # Unterordner im Eingang
    meta.append("Verarbeitet am: "
                + (jetzt or datetime.datetime.now().isoformat()))

    parts = ["# " + basisname, ""] + meta + [""]
    for title, key in (("Tags", "tags"), ("Keywords", "keywords"),
                       ("Methoden", "methods")):
        items = lst(key)
        if items:
            parts.append("\n".join(["## " + title, ""]
                                   + ["- " + i for i in items] + [""]))
    # Kurzfassung der Verschlagwortung: bisher erzeugt und verworfen (28.08.)
    kurz = str(tags.get("summary") or "").strip()
    if kurz:
        parts.append("\n".join(["## Kurzfassung (Aufnahme)", "", kurz[:1500], ""]))
    parts += ["## Inhalt", "", content]
    return "\n".join(parts), content, tags


def tagging_lesen(pfad):
    """Das Ergebnis der Verschlagwortung aus Ollamas Antwortdatei holen."""
    try:
        resp = json.load(open(pfad, encoding="utf-8"))
        return json.loads(resp.get("message", {}).get("content", "{}"))
    except Exception as e:
        print("WARNUNG Tagging unbrauchbar:", e, file=sys.stderr)
        return {}


def main():
    raw_path, ollama_path, base, out_path = sys.argv[1:5]
    rohtext = open(raw_path, encoding="utf-8", errors="replace").read()
    tags = tagging_lesen(ollama_path)
    text, content, tags = baue_markdown(rohtext, tags, base)
    open(out_path, "w", encoding="utf-8").write(text)

    def lst(key):
        v = tags.get(key)
        return [str(i) for i in v] if isinstance(v, list) else []

    print("OK", len(content), "Zeichen |", len(lst("tags")), "Tags |",
          len(lst("keywords")), "Keywords |", content.count("[Seite "),
          "Seiten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
