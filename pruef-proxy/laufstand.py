#!/usr/bin/env python3
"""Wie weit ist die Aufnahme? Anzahlen je Ablagestufe, sonst nichts.

  docker exec ki4ki-pruef-proxy python3 /app/laufstand.py
  docker exec ki4ki-pruef-proxy python3 /app/laufstand.py --warten 300

Mit --warten <Sekunden> misst das Skript zweimal und rechnet den
Durchsatz aus - daraus laesst sich die Restzeit schaetzen, statt sie zu
raten.

⛔ Gibt AUSSCHLIESSLICH Zahlen aus: keine Dateinamen, keine Ordnernamen
   unterhalb eines Bereichs, keine Inhalte. Mit der Datensperre vereinbar.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STUFEN = ("input", "parkplatz", "archiv", "aussortiert", "loeschen")
STEUER = {"bereich.json", "metadaten.json", "prompt.md", "kategorien.txt",
          "bilder-nachholen.txt", "aussortiert.log", "loeschen.log",
          "rolle.json"}


def zaehlen(wurzel):
    """{bereich: {stufe: anzahl}} - nur Dokumentdateien, kein Steuerkram."""
    stand = {}
    try:
        bereiche = sorted(os.listdir(wurzel))
    except Exception:
        return stand
    for b in bereiche:
        if not os.path.isdir(os.path.join(wurzel, b)):
            continue
        je_stufe = {}
        for stufe in STUFEN:
            n = 0
            for _o, _u, dateien in os.walk(os.path.join(wurzel, b, stufe)):
                n += sum(1 for d in dateien
                         if d not in STEUER and not d.startswith("."))
            je_stufe[stufe] = n
        if any(je_stufe.values()):
            stand[b] = je_stufe
    return stand


def zeige(stand, bestand):
    kopf = "%-24s" % "Bereich" + "".join("%12s" % s for s in STUFEN)
    print(kopf)
    print("-" * len(kopf))
    summe = dict.fromkeys(STUFEN, 0)
    for b, je in sorted(stand.items()):
        print("%-24s" % b[:24] + "".join("%12d" % je[s] for s in STUFEN))
        for s in STUFEN:
            summe[s] += je[s]
    print("-" * len(kopf))
    print("%-24s" % "zusammen" + "".join("%12d" % summe[s] for s in STUFEN))
    print("\nDokumente im Bestand: %d" % bestand)
    return summe


def bestandszahl():
    import pruef_proxy as p
    import veredeln
    try:
        if p.BESTAND is None:
            p.BESTAND = veredeln.Bestand()
            p.BESTAND._rohtext()
        return len(p.BESTAND.titel())
    except Exception:
        return -1


def main():
    import pruef_proxy as p
    warten = 0
    if "--warten" in sys.argv:
        try:
            warten = int(sys.argv[sys.argv.index("--warten") + 1])
        except (IndexError, ValueError):
            print("--warten braucht eine Zahl in Sekunden")
            return 1

    a = zaehlen(p.EINGANG_ORDNER)
    if not a:
        print("Kein Bereich mit Dateien gefunden - DIE MESSUNG IST UNGUELTIG "
              "(falscher Einhaengepunkt oder leerer Bestand).")
        return 1
    summe_a = zeige(a, bestandszahl())
    if not warten:
        return 0

    print("\n... %d Sekunden messen ...\n" % warten)
    begonnen = time.time()
    time.sleep(warten)
    dauer = time.time() - begonnen

    b = zaehlen(p.EINGANG_ORDNER)
    summe_b = zeige(b, bestandszahl())

    geschafft = (summe_a["input"] - summe_b["input"])
    print()
    if geschafft <= 0:
        # ⛔ Kein Fortschritt ist eine Aussage, keine fehlende. Eine
        #   Restzeit aus null Durchsatz waere unendlich - und eine
        #   hingeschriebene Zahl waere geraten.
        print("⛔ In %d Sekunden hat der Eingang NICHT abgenommen (%d -> %d). "
              "Entweder laeuft gerade nichts, oder die Kette haengt. Eine "
              "Restzeit laesst sich daraus nicht rechnen."
              % (dauer, summe_a["input"], summe_b["input"]))
        return 1
    je_datei = dauer / geschafft
    rest = summe_b["input"] * je_datei
    print("Durchsatz: %d Dateien in %d s  =  %.1f s je Datei"
          % (geschafft, dauer, je_datei))
    print("Rest: %d Dateien  ->  rund %.1f Stunden"
          % (summe_b["input"], rest / 3600.0))
    print("\n⚠ Hochgerechnet aus %d Dateien. Enthaelt der Rest andere Formate "
          "(Scans mit Bildbeschreibung dauern ein Vielfaches), stimmt die "
          "Zahl nicht - sie ist ein Anhaltspunkt, keine Zusage." % geschafft)
    return 0


if __name__ == "__main__":
    sys.exit(main())
