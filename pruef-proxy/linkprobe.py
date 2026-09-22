#!/usr/bin/env python3
"""Fuer jedes Dokument im Bestand: Laesst sich der Link, den die Antwort
anbietet, ueberhaupt einloesen?

Hintergrund (22.09.): Im Arbeitsbereich zz-schluesselprobe fuehrten alle
Links auf "Dieses Dokument liegt nicht vor." Die Anlage beantwortet einen
unbekannten Namen und ein gesperrtes Dokument absichtlich WORTGLEICH, damit
niemand ueber die Fehlermeldung Namen erraten kann. Von aussen sind die
beiden Faelle deshalb nicht zu unterscheiden - von innen schon.

Zwei Wege kann ein Link nehmen:
  Seitenansicht  /stelle   -> braucht einen Eintrag in PDFS (eine echte PDF)
  Originaldatei  (Ausgabe) -> braucht eine Datei ueber _archivdatei()

Ist BEIDES None, ist der Link tot - unabhaengig von jedem Recht.

⛔ Gibt AUSSCHLIESSLICH Zahlen und Dateiendungen aus. Keine Dokumentnamen,
   keine Ordner, keine Inhalte. Mit der Datensperre vereinbar.

  docker exec ki4ki-pruef-proxy python3 /app/linkprobe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import pruef_proxy as p
    import schluessel
    import veredeln

    if p.BESTAND is None:
        # Genau wie beim echten Start: BESTAND entsteht erst in main(), nicht
        # beim Import. Ohne diese beiden Zeilen ist es None - die Messung ist
        # daran am 22.09. ausgefallen und hat sich richtigerweise selbst fuer
        # ungueltig erklaert, statt "0 tote Links" zu melden.
        p.BESTAND = veredeln.Bestand()
        p.BESTAND._rohtext()
    p.pdfs_einlesen()
    try:
        titel = list(p.BESTAND.titel())
    except Exception as e:
        print("Bestand nicht lesbar (%s) - DIE MESSUNG IST UNGUELTIG"
              % str(e)[:120])
        return 1
    if not titel:
        print("Der Bestand ist leer - DIE MESSUNG IST UNGUELTIG: 'kein toter "
              "Link' hiesse dann nur, dass es ueberhaupt keine Links gibt.")
        return 1

    # Klassen, die sich gegenseitig ausschliessen.
    mit_pdf = 0        # Seitenansicht moeglich (Sprung mit gelber Markierung)
    nur_datei = 0      # keine Seitenansicht, aber die Originaldatei liegt da
    tot = 0            # weder noch: der Link fuehrt ins Leere
    ohne_abdruck = 0   # nicht einmal wiederzufinden (Altbestand)
    je_endung = {}

    for t in titel:
        stamm = p._stamm(t)
        sch = p._pdf_schluessel(stamm)
        ab = schluessel.abdruck_finden(stamm, p.PDFS_ABDRUCK)
        endung = os.path.splitext(sch or stamm)[1].lower() or "(ohne)"

        if ab is None:
            ohne_abdruck += 1
            lage = "ohne_abdruck"
        elif sch and p.PDFS.get(sch) and os.path.exists(p.PDFS[sch]):
            mit_pdf += 1
            lage = "seitenansicht"
        else:
            try:
                datei = p._archivdatei(stamm)
            except Exception:
                datei = None
            if datei and os.path.exists(datei):
                nur_datei += 1
                lage = "nur_datei"
            else:
                tot += 1
                lage = "TOT"
        je_endung.setdefault(endung, {}).setdefault(lage, 0)
        je_endung[endung][lage] += 1

    gesamt = len(titel)
    print("Dokumente im Bestand: %d" % gesamt)
    print("  Seitenansicht moeglich (PDF da) : %4d" % mit_pdf)
    print("  nur Originaldatei (kein Sprung) : %4d" % nur_datei)
    print("  TOTER LINK (nichts auszuliefern): %4d" % tot)
    print("  ohne Abdruck (Altbestand)       : %4d" % ohne_abdruck)
    print()
    print("Je Endung:")
    for e in sorted(je_endung):
        teile = ", ".join("%s %d" % (k, v)
                          for k, v in sorted(je_endung[e].items()))
        print("  %-8s %s" % (e, teile))

    # ⛔ Die Gegenprobe. Ohne sie sagt "0 tote Links" nichts: Sie waere auch
    #    dann 0, wenn der Bestand leer ist oder jede Datei fehlt und alles
    #    unter "ohne Abdruck" verbucht wird.
    print()
    if mit_pdf + nur_datei == 0:
        print("⛔ DIE MESSUNG IST UNGUELTIG: Kein einziges Dokument ist "
              "auslieferbar. Dann misst dieses Skript nicht die Linkqualitaet, "
              "sondern einen Ausfall an ganz anderer Stelle (Einhaengepunkt, "
              "Rechte, leeres Archiv).")
        return 1
    print("Messung gueltig: %d Dokumente sind auslieferbar, die Klassen "
          "unterscheiden also wirklich." % (mit_pdf + nur_datei))
    print()
    if tot:
        print("⛔ %d Dokument(e) bieten einen Link an, den die Anlage nicht "
              "einloesen kann. Das ist der Fehler aus den Bildschirmfotos." % tot)
    else:
        print("Kein toter Link. Fuehrt ein Klick trotzdem auf 'liegt nicht "
              "vor', liegt es NICHT an der Datei, sondern am Rechte-Tor "
              "(dokument_erlaubt) - dann dort weitersuchen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
