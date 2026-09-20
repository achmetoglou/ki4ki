#!/usr/bin/env python3
"""Messung vor dem Umbau auf Pfad-Identitaet - rechnet, aendert nichts.

⚠ Gibt AUSSCHLIESSLICH Zahlen aus. Keine Dateinamen, keine Ordnernamen,
  keine Inhalte. Damit ist der Lauf mit der Datensperre vereinbar und das
  Ergebnis kann bedenkenlos in einen Chat kopiert werden.

Hintergrund: Ein Dokument wird heute allein ueber seinen DATEINAMEN
identifiziert. Der Umbau will den relativen PFAD zur Identitaet machen.
Ob das traegt, haengt an einer einzigen Zahl: Wie viele Pfade fallen
nach der Normalisierung trotzdem zusammen? Alle Vergleichsfunktionen der
Anlage werfen alles ausser Buchstaben und Ziffern weg - "Kunde/Angebot",
"Kunde - Angebot" und "Kunde Angebot" sind fuer sie dasselbe. Ist diese
Zahl nicht 0, loest der Umbau das Problem nicht.

Aufruf:  python3 bau/pfad-messung.py [wurzel]
         Vorgabe fuer wurzel: ~/ki4ki/dokumente
"""
import hashlib
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

# Was AnythingLLM auf den Namen legt: ".md" plus "-<uuid>.json" = 45 Byte.
AUFSCHLAG = 45
NAME_MAX = 255

# Variante 4: lesbarer Teil + Fingerabdruck des Pfades. Der Fingerabdruck
# besteht aus Ziffern und Kleinbuchstaben und ueberlebt deshalb JEDE der
# acht Normalisierungen - anders als Trennzeichen, die alle weggeworfen
# werden. Damit darf der lesbare Teil beliebig gekuerzt werden, ohne die
# Eindeutigkeit zu verlieren.
FINGER_STELLEN = 10
LESBAR_MAX = 120        # Byte, vor dem Fingerabdruck


def fingerabdruck(relpfad):
    return hashlib.sha256(relpfad.encode("utf-8")).hexdigest()[:FINGER_STELLEN]


def anzeigename(bereich, relpfad):
    """Lesbarer, gekuerzter Name + Fingerabdruck des vollen Pfades."""
    roh = os.path.splitext(bereich + "/" + relpfad)[0]
    lesbar = re.sub(r"[^A-Za-z0-9]+", "-", unicodedata.normalize("NFKD", roh))
    lesbar = "".join(c for c in lesbar if not unicodedata.combining(c)).strip("-")
    b = lesbar.encode("utf-8")[:LESBAR_MAX]
    lesbar = b.decode("utf-8", "ignore").strip("-")
    return lesbar + "-" + fingerabdruck(bereich + "/" + relpfad)


def grundform(s):
    """pruef_proxy._grundform - Kleinschreibung, nur a-z0-9."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def loesch_grund(s):
    """pruef_proxy._loesch_grund - NFKD, ss fuer scharfes s, nur a-z0-9."""
    s = unicodedata.normalize("NFKD", (s or "").lower()).replace("ß", "ss")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def wie_anythingllm(s):
    """pdfstelle._wie_anythingllm - NFKD, Nicht-Alphanumerisches zu '-'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


def sammeln(wurzel):
    """Je Bereich die Dateien mit ihrem Weg unterhalb des Bereichs."""
    aus = defaultdict(list)
    if not os.path.isdir(wurzel):
        return aus
    for bereich in sorted(os.listdir(wurzel)):
        b = os.path.join(wurzel, bereich)
        if not os.path.isdir(b):
            continue
        for ordner, _unter, dateien in os.walk(b):
            for d in dateien:
                if d.startswith(".") or d.endswith(".log") or d in (
                        "bereich.json", "kategorien.txt", "prompt.md",
                        "metadaten.json", "bilder-nachholen.txt"):
                    continue
                voll = os.path.join(ordner, d)
                aus[bereich].append(os.path.relpath(voll, b))
    return aus


def gruppen(paare):
    """Wie viele Schluessel tragen mehr als einen Pfad - und wie viele
    Pfade sind davon betroffen."""
    nach = defaultdict(set)
    for pfad, k in paare:
        nach[k].add(pfad)
    mehrfach = {k: p for k, p in nach.items() if len(p) > 1}
    betroffen = sum(len(p) for p in mehrfach.values())
    groesste = max((len(p) for p in mehrfach.values()), default=0)
    return len(mehrfach), betroffen, groesste


def zeile(text, *werte):
    print(("%-46s" % text) + "  ".join("%8s" % w for w in werte))


def main():
    wurzel = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1
                                else "~/ki4ki/dokumente")
    je_bereich = sammeln(wurzel)
    if not je_bereich:
        print("Keine Bereiche unter %s gefunden." % wurzel)
        return 1

    alle = [(b, p) for b, pfade in je_bereich.items() for p in pfade]
    print("=" * 78)
    print("MESSUNG VOR DEM UMBAU AUF PFAD-IDENTITAET")
    print("Nur Zahlen. Keine Namen, keine Inhalte.")
    print("=" * 78)

    print("\n1 . UMFANG")
    zeile("Bereiche", len(je_bereich))
    zeile("Dateien gesamt", len(alle))
    for i, b in enumerate(sorted(je_bereich), 1):
        zeile("   Bereich %d" % i, len(je_bereich[b]))

    print("\n2 . HEUTIGER SCHLUESSEL (nackter Dateiname, ueber ALLE Bereiche)")
    print("    So arbeitet die Anlage jetzt. Jede Gruppe > 1 ist eine Kollision.")
    namen = [(b + "/" + p, loesch_grund(os.path.splitext(os.path.basename(p))[0]))
             for b, p in alle]
    g, betroffen, groesste = gruppen(namen)
    zeile("mehrfach vergebene Schluessel", g)
    zeile("betroffene Dateien", betroffen)
    zeile("groesste Gruppe", groesste)
    zeile("=> stiller Verlust bei Aufnahme", max(0, betroffen - g))

    print("\n3 . NEUER SCHLUESSEL (relativer Pfad) - DIE ENTSCHEIDENDE ZAHL")
    print("    Ist 'betroffene Dateien' hier nicht 0, loest der Umbau es nicht.")
    for titel, mit_bereich in (("ohne Bereich im Schluessel", False),
                               ("mit Bereich im Schluessel", True)):
        print("\n   Variante: %s" % titel)
        for name, fn in (("_grundform / bestand / metadaten", grundform),
                         ("_loesch_grund (Loeschweg!)", loesch_grund),
                         ("_wie_anythingllm (Belegsprung)", wie_anythingllm)):
            stoff = [((b + "/" + p) if mit_bereich else p,
                      fn(((b + "/") if mit_bereich else "")
                         + os.path.splitext(p)[0]))
                     for b, p in alle]
            g, betroffen, groesste = gruppen(stoff)
            zeile("   " + name, g, betroffen, groesste)
        print("      (Spalten: Schluessel mehrfach | betroffene Dateien | groesste Gruppe)")

    print("\n4 . LAENGE DES SCHLUESSELS IN BYTE (Grenze ext4: %d)" % NAME_MAX)
    laengen = sorted(len((b + "/" + p).encode("utf-8")) + AUFSCHLAG
                     for b, p in alle)
    zeile("kuerzester", laengen[0])
    zeile("Mitte", laengen[len(laengen) // 2])
    zeile("laengster", laengen[-1])
    zeile("ueber %d Byte (reissen die Grenze)" % NAME_MAX,
          sum(1 for x in laengen if x > NAME_MAX))
    zeile("ueber 200 Byte (knapp)", sum(1 for x in laengen if x > 200))

    print("\n5 . VERSCHACHTELUNG (Ebenen unterhalb des Bereichs)")
    tiefen = Counter(p.count(os.sep) for _b, p in alle)
    for t in sorted(tiefen):
        zeile("   %d Ebene(n)" % t, tiefen[t])

    print("\n6 . VARIANTE MIT FINGERABDRUCK (lesbar gekuerzt + %d Stellen)"
          % FINGER_STELLEN)
    print("    Der Fingerabdruck ist alphanumerisch und ueberlebt jede")
    print("    Normalisierung. Hier MUESSEN alle drei Zeilen 0 zeigen.")
    namen4 = [(b + "/" + p, anzeigename(b, p)) for b, p in alle]
    for name, fn in (("_grundform / bestand / metadaten", grundform),
                     ("_loesch_grund (Loeschweg!)", loesch_grund),
                     ("_wie_anythingllm (Belegsprung)", wie_anythingllm)):
        g4, betroffen4, groesste4 = gruppen([(pf, fn(k)) for pf, k in namen4])
        zeile("   " + name, g4, betroffen4, groesste4)
    laengen4 = sorted(len(k.encode("utf-8")) + AUFSCHLAG for _pf, k in namen4)
    zeile("laengster Schluessel in Byte", laengen4[-1])
    zeile("ueber %d Byte" % NAME_MAX, sum(1 for x in laengen4 if x > NAME_MAX))

    print("\n" + "=" * 78)
    stoff = [(b + "/" + p, loesch_grund(b + "/" + os.path.splitext(p)[0]))
             for b, p in alle]
    g, betroffen, _ = gruppen(stoff)
    zu_lang = sum(1 for x in laengen if x > NAME_MAX)
    rest4 = max(gruppen([(pf, fn(k)) for pf, k in namen4])[1]
                for fn in (grundform, loesch_grund, wie_anythingllm))
    lang4 = sum(1 for x in laengen4 if x > NAME_MAX)
    if betroffen == 0 and zu_lang == 0:
        print("URTEIL: Der Pfad als Schluessel ist eindeutig. Der Umbau traegt.")
    else:
        print("URTEIL: Der Pfad allein reicht NICHT.")
        if betroffen:
            print("  %d Dateien fallen trotz Pfad zusammen (%d Gruppen)."
                  % (betroffen, g))
        if zu_lang:
            print("  %d Schluessel reissen die %d-Byte-Grenze."
                  % (zu_lang, NAME_MAX))
        print("  Der Entwurf braucht eine zusaetzliche Unterscheidung.")
    if rest4 == 0 and lang4 == 0:
        print("\n  ABER: Mit Fingerabdruck (Abschnitt 6) sind alle %d Dateien"
              % len(alle))
        print("  eindeutig und kein Schluessel reisst die Grenze. DAS traegt.")
    else:
        print("\n  AUCH mit Fingerabdruck bleiben %d Dateien mehrdeutig"
              % rest4)
        print("  und %d Schluessel zu lang. Stellenzahl erhoehen." % lang4)
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
