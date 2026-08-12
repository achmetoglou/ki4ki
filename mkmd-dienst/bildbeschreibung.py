#!/usr/bin/env python3
"""Ergaenzt das Markdown um das, was zur Bildbeschreibung fehlt.

Die Beschreibung selbst steht bereits im Markdown - Docling setzt sie
direkt hinter die Marke "<!-- image -->". Das ist an einem
frischen Lauf nachgesehen worden.

Was FEHLT, sind zwei Dinge, nach denen jemand tatsaechlich sucht:

  * Die BILDUNTERSCHRIFT. Sie steht nicht am Bild, sondern als Verweis
    auf einen Textabschnitt ("#/texts/9") und taucht im Markdown an
    ganz anderer Stelle auf - getrennt von der Beschreibung. Dabei ist
    sie der Begriff, den ein Fachnutzer eingeben wuerde
    ("Herstellungskette und Aufgaben der Qualitaetssicherung").
  * Die ART der Abbildung aus der Klassifikation (flow_chart,
    line_chart, engineering_drawing ...). Wer "Diagramm" oder
    "Zeichnung" sucht, findet sonst nichts.

Dazu ein Hinweis, wenn das Modell auf Englisch geantwortet hat - das
tut es trotz deutscher Anweisung regelmaessig. Ohne den Hinweis haelt
man die Luecke fuer einen Fehler im Bestand.

  python3 bildbeschreibung.py <docling-antwort.json> <ziel.md>
"""
import json
import re
import sys

# Die Marke, die Docling anstelle eines Bildes setzt.
MARKE = re.compile(r"<!--\s*image\s*-->")

# Woran man erkennt, dass eine Beschreibung nicht auf Deutsch kam. Das
# Modell antwortet trotz deutscher Anweisung regelmaessig englisch -
# gemessen ("This German diagram illustrates ..."). Wer nach
# "Diagramm" sucht, findet einen englischen Text nicht.
ENGLISCH = re.compile(
    r"\b(the|this|that|shows?|illustrates?|depicts?|diagram|chart|figure|"
    r"image|axis|values?|between|with|and|of)\b", re.I)


def wirkt_abgeschnitten(text):
    """Grobe Einschaetzung: wurde die Beschreibung mitten im Satz gekappt?

    ⛔ Erreicht das Modell die Token-Grenze, kommt die Antwort
    ABGESCHNITTEN - und der Weg darunter (nothink-proxy -> Docling) meldet
    trotzdem "200 OK". Ein halber Satz wandert dann als vollstaendige
    Beschreibung in den Bestand. Hier kein Eingriff in den Chat-Weg
    (der laeuft ueber denselben Proxy), sondern nur ein ehrlicher Hinweis am
    Ergebnis: Eine gekappte Beschreibung endet mitten im Satz - nach einem
    Komma oder einem kleingeschriebenen Wort, nicht auf einem Satzzeichen.
    """
    t = (text or "").rstrip()
    if len(t) < 40:
        return False
    return t[-1] == "," or t[-1].islower()


def ist_englisch(text):
    """Grobe Einschaetzung: mehr englische Signalwoerter als deutsche.

    Absichtlich einfach gehalten - es geht nicht um Spracherkennung,
    sondern um einen Hinweis im Text, damit niemand sich wundert, warum
    eine Suche auf Deutsch nichts findet.
    """
    if not text or len(text) < 40:
        return False
    englisch = len(ENGLISCH.findall(text))
    deutsch = len(re.findall(
        r"\b(die|der|das|und|zeigt|Abbildung|Diagramm|Achse|Werte|mit|"
        r"zwischen|von|eine|ein)\b", text, re.I))
    return englisch > deutsch


def beschreibungen(antwort):
    """Alle Bildbeschreibungen in Dokumentreihenfolge.

    Liefert eine Liste von (Text, Klasse, Bildunterschrift). Fehlt eine
    Beschreibung, steht None an ihrer Stelle - so bleibt die Reihenfolge
    mit den Marken im Markdown erhalten.
    """
    doc = antwort.get("document") or antwort
    inhalt = doc.get("json_content") or {}
    if isinstance(inhalt, str):
        try:
            inhalt = json.loads(inhalt)
        except Exception:
            return []
    texte = inhalt.get("texts") or []
    raus = []
    for bild in (inhalt.get("pictures") or []):
        text, klasse = None, None
        for a in (bild.get("annotations") or []):
            if a.get("kind") == "description" and (a.get("text") or "").strip():
                text = a["text"].strip()
            elif a.get("kind") == "classification":
                treffer = a.get("predicted_classes") or []
                if treffer:
                    klasse = treffer[0].get("class_name")
        # Die Bildunterschrift steht nicht am Bild, sondern als Verweis
        # auf einen Textabschnitt. Ohne Aufloesen fehlt genau der Begriff,
        # nach dem jemand suchen wuerde.
        unterschrift = None
        for verweis in (bild.get("captions") or []):
            ziel = (verweis or {}).get("$ref") or ""
            m = re.match(r"#/texts/(\d+)$", ziel)
            if m and int(m.group(1)) < len(texte):
                roh = texte[int(m.group(1))]
                unterschrift = (roh.get("text") or "").strip() or None
        raus.append((text, klasse, unterschrift))
    return raus


def einweben(md, bilder):
    """Jede Bildmarke durch Marke plus Beschreibung ersetzen."""
    if not bilder:
        return md, 0
    zaehler = {"i": 0, "gesetzt": 0}

    def ersetze(_):
        i = zaehler["i"]
        zaehler["i"] += 1
        if i >= len(bilder):
            return "<!-- image -->"
        text, klasse, unterschrift = bilder[i]
        if not text and not unterschrift and not klasse:
            return "<!-- image -->"
        zaehler["gesetzt"] += 1
        # NUR ergaenzen, nicht wiederholen: Der Beschreibungstext folgt
        # unmittelbar nach dieser Marke und steht schon im Markdown. Ihn
        # hier noch einmal einzusetzen wuerde ihn verdoppeln - genau das
        # ist in einer frueheren Fassung passiert.
        teile = ["<!-- image -->", ""]
        kopf = "**Abbildung"
        if unterschrift:
            kopf += ": %s" % unterschrift
        kopf += "**"
        teile.append(kopf)
        if klasse:
            teile.append("*Art der Abbildung: %s*" % klasse)
        if text and ist_englisch(text):
            # Ehrlich kennzeichnen statt still hinnehmen: Wer auf Deutsch
            # sucht, findet den folgenden Absatz nicht und haelt die Luecke
            # fuer einen Fehler im Bestand.
            teile.append("*Die folgende Beschreibung wurde vom Modell auf "
                         "Englisch erzeugt.*")
        if text and wirkt_abgeschnitten(text):
            # An der Token-Grenze gekappt - ehrlich kennzeichnen, statt
            # einen halben Satz als ganze Beschreibung stehen zu lassen.
            teile.append("*Diese Beschreibung wirkt abgeschnitten (das "
                         "Modell hat vermutlich die maximale Laenge erreicht).*")
        teile.append("")
        return "\n".join(teile)

    return MARKE.sub(ersetze, md), zaehler["gesetzt"]


def main():
    antwort = json.load(open(sys.argv[1], encoding="utf-8"))
    doc = antwort.get("document") or antwort
    md = ""
    for k in ("md_content", "markdown", "text"):
        if isinstance(doc.get(k), str) and doc[k].strip():
            md = doc[k]
            break
    if not md:
        print("LEER, keys: %s" % list(doc.keys())[:10])
        sys.exit(2)

    bilder = beschreibungen(antwort)
    md, gesetzt = einweben(md, bilder)

    # ⭐ ECHTE SEITEN: Doclings Markdown setzt zu wenige
    # Seitentrenner, das spaetere Durchzaehlen in mk_md lief darum mit dem
    # Dokument immer weiter daneben. Hier - wo das JSON mit den echten
    # Seiten (prov[].page_no) noch vorliegt - jedem Trenner seine wirkliche
    # Seite geben ([[SEITE]] -> [[SEITE:37]]). Ein sauberes Dokument bleibt
    # unangetastet (Waechter in seiten_echt).
    try:
        import seiten_echt
        inhalt = doc.get("json_content") or {}
        if isinstance(inhalt, str):
            inhalt = json.loads(inhalt)
        md, _erste = seiten_echt.nummeriere(md, inhalt)
    except Exception as e:
        print("WARNUNG echte Seiten uebersprungen:", e, file=sys.stderr)

    open(sys.argv[2], "w", encoding="utf-8").write(md)

    mit_text = sum(1 for b in bilder if b[0])
    englisch = sum(1 for b in bilder if b[0] and ist_englisch(b[0]))
    mit_unterschrift = sum(1 for b in bilder if b[2])
    print("%d Zeichen | %d Seiten | %d Formeln | %d Abbildungen, "
          "%d beschrieben, %d mit Bildunterschrift, %d ergaenzt%s"
          % (len(md), md.count("[[SEITE]]"), md.count("$"), len(bilder),
             mit_text, mit_unterschrift, gesetzt,
             ", %d davon englisch" % englisch if englisch else ""))


if __name__ == "__main__":
    main()
