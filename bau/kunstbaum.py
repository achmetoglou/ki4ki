"""Legt einen kuenstlichen Ordnerbaum aus LEEREN Dateien an.

Kein Bezug zum echten Bestand - nur Struktur, damit die Messung aus
schluesseltest.py getestet werden kann, bevor sie auf dem Server laeuft.
"""
import os
import shutil
import sys

WURZEL = sys.argv[1]
MIT_STOERUNG = len(sys.argv) > 2 and sys.argv[2] == "stoerung"

shutil.rmtree(WURZEL, ignore_errors=True)


def leer(*teile):
    p = os.path.join(WURZEL, *teile)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()


for bereich in ("bereichA", "bereichB"):
    for stufe in ("input", "parkplatz", "archiv", "aussortiert", "loeschen"):
        # dieselbe Datei in jeder Stufe -> Doppelablagen
        leer(bereich, stufe, "KundeEins", "Angebot.pdf")
        leer(bereich, stufe, "KundeZwei", "Angebot.pdf")
        leer(bereich, stufe, "KundeDrei", "Angebot.pdf")
    # Steuerdateien, die nicht mitgezaehlt werden duerfen
    leer(bereich, "bereich.json")
    leer(bereich, "prompt.md")
    leer(bereich, "aussortiert.log")
    leer(bereich, "irgendwas.log")
    # Sonderzeichen, die AnythingLLM zu Woertern macht
    leer(bereich, "archiv", "Bericht & Anlage", "Messung 100%",
         "Preis 50€", "Übersicht.pdf")
    # nicht-lateinisch -> lesbarer Teil schrumpft auf den Bereichsnamen
    leer(bereich, "archiv", "中文文件.pdf")
    # Punktname, der keine Endung ist
    leer(bereich, "archiv", "Angebot Nr. 4711")
    # acht Ebenen tief mit langen Namen
    leer(bereich, "archiv", *(["o" * 40] * 8 + ["datei.pdf"]))
    # Trennzeichen-Falle: Die Normalisierung wirft alle Trennzeichen weg,
    # "Angebot 2024/x" und "Angebot/2024 x" werden dadurch gleich. Ohne
    # diesen Fall kann keine Pruefung zeigen, dass der Abdruck sie trennt.
    leer(bereich, "archiv", "KundeVier", "Angebot 2024", "x.pdf")
    leer(bereich, "archiv", "KundeVier", "Angebot", "2024 x.pdf")
    # Office-Original mit gewandelter PDF daneben: Das Dokument ist das
    # ORIGINAL, die PDF nur die Quelle fuer den Belegsprung. Beide haben
    # verschiedene Kennpfade - ohne Sonderregel bekaeme dasselbe Dokument
    # zwei Abdruecke, und der Beleg des Word-Dokuments zeigte ins Leere.
    leer(bereich, "archiv", "KundeEins", "Bericht.docx")
    leer(bereich, "archiv", "KundeEins", "Bericht.pdf")
    # lange Punkt-Kette: bleibt nur unter 200 Byte, solange die Endungsregel
    # kurz ist. Ohne diesen Fall koennte die Pruefung "kein Schluessel ueber
    # 200 Byte" am Bestand gar nicht rot werden.
    leer(bereich, "archiv", "datei." + "x" * 200)

if MIT_STOERUNG:
    # Datei direkt in der Wurzel: kein Bereich, muss als unzerlegbar zaehlen
    leer("liegt-ohne-bereich-herum.pdf")

# ⚠ Beide Bereiche haben denselben Aufbau. Unter dem HEUTIGEN Schluessel
#   (nackter Dateiname) kollidiert deshalb jede Datei mindestens mit ihrem
#   Gegenstueck - die Quote in schluesseltest.py steht bei 100 %. Das ist
#   strukturell und kein kaputtes Werkzeug: An einem Baum ohne gleichnamige
#   Dateien meldet dieselbe Pruefung 0 und wird rot (nachgemessen).
anzahl = sum(len(d) for _o, _u, d in os.walk(WURZEL))
print("Kunstbaum angelegt: %d leere Dateien%s"
      % (anzahl, " (mit Stoerung)" if MIT_STOERUNG else ""))
