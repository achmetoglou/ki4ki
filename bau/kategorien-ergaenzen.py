#!/usr/bin/env python3
"""Welche Kategorien fehlen in den kategorien.txt der Bereiche?

⛔ WARUM ES DIESES WERKZEUG GIBT (25.09.). Eine eigene kategorien.txt
   ERSETZT die Standardliste - das ist Absicht und bleibt so: Die Wahl des
   Betreibers gehoert dem Betreiber. Nur: Die vorhandenen Dateien wurden
   geschrieben, als es die Geschaeftsarten (Rechnung, Angebot, Bestellung,
   ...) noch nicht gab. In ihrem Bereich bleibt die Liste deshalb
   GESCHLOSSEN, und jede Rechnung landet auf "Sonstiges" - obwohl die
   Reparatur im Standard laengst greift.

   Gemessen am 25.09.: In ALLEN ZEHN Bereichen lag eine solche Datei.
   Ohne diesen Zwischenschritt waere ein Lauf ueber 6.395 Dokumente
   gelaufen und haette jede Geschaeftsunterlage falsch einsortiert.

⭐ Deshalb zeigt dieses Werkzeug zuerst nur AN. Geschrieben wird
   ausschliesslich mit --schreiben. Eine Anlage, die die Liste des
   Betreibers stillschweigend erweitert, ist schlimmer als eine, die zu
   wenig kennt: Die eine faellt auf, die andere nicht.

⛔ Gibt KEINE Dokumentnamen und keine Inhalte aus - nur Bereichsnamen
   (die kennt der Betreiber) und Kategorien.

  python3 bau/kategorien-ergaenzen.py               # nur ansehen
  python3 bau/kategorien-ergaenzen.py --schreiben   # fehlende ergaenzen
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "pruef-proxy"))

import kategorie  # noqa: E402

EINGANG = os.environ.get("KI4KI_EINGANG_HOST") or os.path.expanduser(
    "~/ki4ki/dokumente")


def bereiche():
    try:
        return sorted(d for d in os.listdir(EINGANG)
                      if os.path.isfile(os.path.join(d and os.path.join(
                          EINGANG, d) or "", kategorie.DATEI)))
    except Exception:
        return []


def fehlende(wurzel):
    """Kategorien des Standards, die in diesem Bereich fehlen."""
    eigene = {n for n, _ in kategorie.liste(wurzel)}
    return [(n, w) for n, w in kategorie.STANDARD
            if n not in eigene and n != "Sonstiges"]


def main():
    schreiben = "--schreiben" in sys.argv
    liste = bereiche()
    if not liste:
        print("Keine kategorien.txt gefunden unter %s - "
              "DANN IST NICHTS ZU TUN (der Standard gilt ueberall)."
              % EINGANG)
        return 0

    print("Bereiche mit eigener Kategorienliste: %d" % len(liste))
    print()
    gesamt = 0
    for b in liste:
        wurzel = os.path.join(EINGANG, b)
        weg = fehlende(wurzel)
        gesamt += len(weg)
        print("  %-34s %2d eigene, %2d fehlen"
              % (b, len(kategorie.liste(wurzel)), len(weg)))
        if weg:
            print("      %s" % ", ".join(n for n, _ in weg))
        if weg and schreiben:
            pfad = os.path.join(wurzel, kategorie.DATEI)
            with open(pfad, "a", encoding="utf-8") as fh:
                fh.write("\n# Ergaenzt am %s: Kategorien aus dem Standard,\n"
                         "# die diese Datei noch nicht kannte.\n"
                         % __import__("datetime").date.today().isoformat())
                for n, w in weg:
                    fh.write("%s: %s\n" % (n, ", ".join(x.strip() for x in w)))
            print("      -> ergaenzt")

    print()
    if not gesamt:
        print("Nichts zu tun: Jeder Bereich kennt alle Standardkategorien.")
        return 0
    if schreiben:
        print("%d Kategorien in %d Bereichen ergaenzt." % (gesamt, len(liste)))
        # ⛔ Die Gegenprobe: Nach dem Schreiben darf nichts mehr fehlen.
        #   Ohne sie waere "ergaenzt" eine Behauptung ueber eine Datei, die
        #   niemand nachgelesen hat.
        rest = sum(len(fehlende(os.path.join(EINGANG, b))) for b in liste)
        if rest:
            print("⛔ DIE ERGAENZUNG HAT NICHT GEGRIFFEN: %d fehlen weiterhin."
                  % rest)
            return 1
        print("Nachgelesen: 0 fehlen noch.")
        return 0
    print("%d Kategorien fehlen insgesamt." % gesamt)
    print("⛔ Es wurde NICHTS geaendert. Zum Ergaenzen:")
    print("   python3 bau/kategorien-ergaenzen.py --schreiben")
    return 0


if __name__ == "__main__":
    sys.exit(main())
