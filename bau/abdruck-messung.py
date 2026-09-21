#!/usr/bin/env python3
"""Die Zahlen, die vor dem Umbau auf den Pfad-Schluessel feststehen muessen.

⛔ Gibt AUSSCHLIESSLICH Zahlen aus - keine Datei- und keine Ordnernamen.
   Mit der Datensperre vereinbar.

Warum ueberhaupt: Am 20.09. kippte ein zwanzigzeiliges Skript einen bereits
abgenommenen Plan - nach zwei Minuten Laufzeit. Haengt der Nutzen eines
Umbaus an einer Eigenschaft der echten Daten, wird sie ZUERST ausgerechnet.

  python3 bau/abdruck-messung.py                      (auf dem HOST)
  KI4KI_PDFS=<wurzel> python3 bau/abdruck-messung.py  (anderer Ort)

⚠ NICHT den Pfad aus dem Container einsetzen. Das Compose haengt den
  Dokumentenordner dort unter einem anderen Namen ein; auf dem Host gibt es
  ihn nicht, und die Messung faellt aus. Ohne KI4KI_PDFS trifft der
  Vorgabewert den richtigen Ordner.

Rueckgabe 0 = Messung gueltig, 1 = ungueltig (dann sagt die letzte Zeile,
warum). Eine ungueltige Messung sieht beim Ueberfliegen aus wie ein Befund -
deshalb sagt das Skript es selbst, statt es in eine Fussnote zu schreiben.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "pruef-proxy"))
import schluessel   # noqa: E402

STEUER = {"bereich.json", "metadaten.json", "prompt.md", "kategorien.txt",
          "bilder-nachholen.txt", "aussortiert.log", "loeschen.log"}
OFFICE = (".doc", ".docx", ".odt", ".rtf", ".ppt", ".pptx", ".odp")


def _zaehlbar(name):
    return not (name in STEUER or name.endswith(".log") or name.startswith("."))


def main():
    wurzel = os.environ.get("KI4KI_PDFS") or os.path.expanduser("~/ki4ki/dokumente")
    if not os.path.isdir(wurzel):
        print("Bestandswurzel nicht gefunden.")
        if wurzel.startswith(os.sep + "daten" + os.sep):
            # Klassiker: der Pfad IM Container, auf dem Host eingegeben.
            # Dieselbe Fehlerklasse wie "127.0.0.1:3001 im Container gemessen"
            # - Container-innen ist nicht Host.
            print("   Das ist der Pfad IM Container. Das Compose haengt den")
            print("   Dokumentenordner dorthin ein; auf dem Host liegt er")
            print("   woanders.")
        print("   Auf dem Host OHNE KI4KI_PDFS aufrufen - der Vorgabewert")
        print("   trifft den richtigen Ordner.")
        print("\n⛔ DIE MESSUNG IST UNGUELTIG - es wurde nichts gemessen.")
        return 1

    je_abdruck, kennpfade, schluessel_je_kp = {}, set(), {}
    dokumente = unzerlegbar = pdf_gesamt = pdf_mit_office = 0
    for ordner, _unter, namen in os.walk(wurzel):
        vorhanden = {n.lower() for n in namen}
        for n in namen:
            if not _zaehlbar(n):
                continue
            rel = os.path.relpath(os.path.join(ordner, n), wurzel)
            teile = rel.replace(os.sep, "/").split("/", 1)
            if len(teile) < 2:
                unzerlegbar += 1
                continue
            try:
                kp = schluessel.kennpfad_aus_bestandspfad(rel)
                s = schluessel.schluessel(teile[0], teile[1])
            except ValueError:
                unzerlegbar += 1
                continue
            dokumente += 1
            kennpfade.add(kp)
            je_abdruck.setdefault(schluessel.fingerabdruck(kp), set()).add(kp)
            schluessel_je_kp[kp] = s
            if n.lower().endswith(".pdf"):
                pdf_gesamt += 1
                stamm = n[:-4].lower()
                if any((stamm + e) in vorhanden for e in OFFICE):
                    pdf_mit_office += 1

    abdruecke = set(je_abdruck)
    # ⚠ Gezaehlt wird gegen KENNPFADE, nicht gegen Dateien. Dieselbe Datei in
    #   input und archiv hat DENSELBEN Kennpfad - das ist ein Dokument, keine
    #   Kollision, und genau so gewollt (die Stufe faellt aus der Kennung).
    #   Waere der Nenner die Dateizahl, meldete das Skript am Kunstbaum 24
    #   Kollisionen, wo keine sind - Messung am falschen Gegenstand.
    doppelablagen = dokumente - len(kennpfade)
    kollisionen = sum(len(m) - 1 for m in je_abdruck.values() if len(m) > 1)
    print("1  Dateien: %d  ->  Dokumente (Kennpfade): %d  (unzerlegbar: %d)"
          % (dokumente, len(kennpfade), unzerlegbar))
    print("   davon Doppelablagen (dieselbe Datei in mehreren Stufen): %d"
          % doppelablagen)
    print("2  verschiedene Abdruecke: %d  ->  ECHTE Kollisionen "
          "(zwei Kennpfade, ein Abdruck): %d" % (len(abdruecke), kollisionen))
    print("   ⚠ Zeile 2 ist SHA-256-Arithmetik, keine Eigenschaft dieses "
          "Entwurfs.\n     Sie steht als Zahl da, nicht als Zusicherung - "
          "rot werden kann sie nicht.")

    # Die Zahl, an der der Entwurf haengt: Wie oft trifft ein Fenster im
    # LESBAREN Teil eines Schluessels zufaellig den Abdruck eines ANDEREN
    # Dokuments? Rechnerisch rund 1,5e-10 - aber gerechnet ist nicht gemessen.
    falsch = geprueft = 0
    for a, menge in je_abdruck.items():
        for kp in menge:
            geprueft += 1
            if schluessel.abdruck_finden(schluessel_je_kp[kp], abdruecke) != a:
                falsch += 1
    print("3  Fehlzuordnungen ueber Fenster: %d von %d geprueften Schluesseln"
          % (falsch, geprueft))

    # Gewandelte Office-PDF liegen neben ihrem Original und haben einen
    # ANDEREN Kennpfad. Ohne Sonderregel bekaeme dasselbe Dokument zwei
    # Abdruecke - und der Beleg des Word-Dokuments spraenge ins Leere.
    print("4  PDF mit gleichnamigem Office-Original daneben: %d von %d PDF"
          % (pdf_mit_office, pdf_gesamt))

    # ⛔ Gegenprobe: Die Messung sagt nur etwas, wenn der HEUTIGE Schluessel
    #    an denselben Daten scheitert. Tut er das nicht, enthaelt dieser
    #    Bestand die Fehlerklasse gar nicht - dann sind die Zeilen 2 und 3
    #    geschenkt und beweisen nichts ueber den Umbau.
    heute = {}
    for ordner, _unter, namen in os.walk(wurzel):
        for n in namen:
            if not _zaehlbar(n):
                continue
            k = re.sub(r"[^a-z0-9]", "", os.path.splitext(n)[0].lower())
            heute[k] = heute.get(k, 0) + 1
    kollidiert = sum(v for v in heute.values() if v > 1)
    print("5  Gegenprobe - heutiger Schluessel: %d von %d Dateien kollidieren"
          % (kollidiert, dokumente))

    # ⛔ KONTROLLE, unabhaengig vom Bestand. Zeile 3 ist am echten Bestand
    #    praktisch immer 0 - ohne diesen gebauten Fall waere sie eine
    #    Behauptung mit gruenem Haken. Hier steht das Ergebnis vorher fest:
    #    Ein Schluessel, dessen LESBARER Teil den Abdruck eines anderen
    #    Dokuments traegt, muss trotzdem sich selbst treffen (der echte
    #    Abdruck steht rechts). Sucht das Fensterverfahren von links, ist
    #    diese Kontrolle rot - und damit die ganze Messung ungueltig.
    a_echt = schluessel.fingerabdruck("pruef/echt.pdf")
    a_fremd = schluessel.fingerabdruck("pruef/fremd.pdf")
    gebaut = "bereich-" + a_fremd + "-Name--" + a_echt + ".pdf"
    kontrolle = schluessel.abdruck_finden(gebaut, {a_echt: 1, a_fremd: 1})
    print("6  Kontrolle (gebauter Fall, Ergebnis steht vorher fest): "
          "%s" % ("richtig" if kontrolle == a_echt else
                  "FALSCH - traf %r statt %r" % (kontrolle, a_echt)))
    if kontrolle != a_echt:
        print("\n⛔ DIE MESSUNG IST UNGUELTIG: Die Kontrolle schlaegt fehl. "
              "Das Fensterverfahren\n   findet den falschen Abdruck - dann "
              "sagen die Zeilen 2 und 3 nichts.")
        return 1

    if kollidiert == 0:
        print("\n⛔ DIE MESSUNG IST UNGUELTIG: Der heutige Schluessel kollidiert "
              "hier nirgends.\n   Dieser Bestand enthaelt die Fehlerklasse "
              "nicht, also sagen die Zeilen 2\n   und 3 nichts ueber den Umbau.")
        return 1
    print("\nMessung gueltig - die Fehlerklasse ist im Bestand vorhanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
