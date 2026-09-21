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
    # lange Punkt-Kette: bleibt nur unter 200 Byte, solange die Endungsregel
    # kurz ist. Ohne diesen Fall koennte die Pruefung "kein Schluessel ueber
    # 200 Byte" am Bestand gar nicht rot werden.
    leer(bereich, "archiv", "datei." + "x" * 200)

if MIT_STOERUNG:
    # Datei direkt in der Wurzel: kein Bereich, muss als unzerlegbar zaehlen
    leer("liegt-ohne-bereich-herum.pdf")

anzahl = sum(len(d) for _o, _u, d in os.walk(WURZEL))
print("Kunstbaum angelegt: %d leere Dateien%s"
      % (anzahl, " (mit Stoerung)" if MIT_STOERUNG else ""))
