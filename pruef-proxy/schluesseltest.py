"""Pruefungen fuer das Schluesselmodul.

Laeuft ohne Testrahmen: python3 schluesseltest.py
Rueckgabewert 0, wenn alles gruen ist, sonst 1.

Grundsatz dieser Datei: Zu jeder Pruefung gehoert der Nachweis, mit WELCHER
Eingabe sie rot wird. Eine Pruefung, die per Konstruktion immer gruen ist,
beweist nichts - in vier Planfassungen standen vier solche Pruefungen.
"""
import os
import sys

import schluessel

FEHLER = []

# Absichtlich hier NOCHMAL definiert und nicht aus dem Modul geholt: sonst
# pruefte der Test gegen die eigene Konstante und koennte nicht rot werden.
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def pruefe(bedingung, text):
    print(("  ok   " if bedingung else "  FEHL ") + text)
    if not bedingung:
        FEHLER.append(text)


def test_kennpfad():
    print("Kennpfad - Bereich explizit, die Stufe faellt raus")
    k, kb = schluessel.kennpfad, schluessel.kennpfad_aus_bestandspfad
    pruefe(k("kap", "archiv/KundeA/Angebot.pdf") == "kap/KundeA/Angebot.pdf",
           "archiv faellt raus")
    pruefe(k("kap", "parkplatz/KundeA/A.pdf") == k("kap", "archiv/KundeA/A.pdf"),
           "parkplatz und archiv ergeben denselben Kennpfad")
    pruefe(k("kap", "KundeA/A.pdf") == k("kap", "archiv/KundeA/A.pdf"),
           "mit und ohne Stufe ergeben denselben Kennpfad")
    pruefe(k("kap", "archiv/KundeA/A.pdf") != k("auw", "archiv/KundeA/A.pdf"),
           "zwei Bereiche bleiben getrennt")
    pruefe(k("kap", "archiv/archiv/x.pdf") == "kap/archiv/x.pdf",
           "nur die ERSTE Stufe faellt raus, ein Unterordner 'archiv' bleibt")
    # Der gefaehrlichste Fall: falscher Bezugspunkt. MUSS abbrechen, nicht raten.
    for schlecht in (("", "archiv/x.pdf"), ("kap", ""), ("kap", "archiv/")):
        try:
            k(*schlecht)
            pruefe(False, "haette abbrechen muessen: %r" % (schlecht,))
        except ValueError:
            pruefe(True, "bricht ab statt zu raten: %r" % (schlecht,))
    pruefe(kb("kap/archiv/KundeA/A.pdf") == "kap/KundeA/A.pdf",
           "Bestandspfad-Hilfe zerlegt <bereich>/<stufe>/<rest>")
    # Die Hintertuer: ein bereichsrelativer Pfad darf NICHT durchrutschen.
    # Genau hier wuerde sonst still der "Bereich archiv" entstehen - und diese
    # Funktion ist die, die die Messung am Bestand benutzt.
    for schlecht in ("archiv/KundeA/A.pdf", "parkplatz/x.pdf", "input/KundeA/A.pdf"):
        try:
            erg = kb(schlecht)
            pruefe(False, "haette abbrechen muessen, lieferte %r fuer %r"
                   % (erg, schlecht))
        except ValueError:
            pruefe(True, "Stufenname als Bereich wird abgewiesen: %r" % schlecht)


def test_fingerabdruck():
    print("\nFingerabdruck")
    a = schluessel.fingerabdruck("kap/KundeA/Angebot.pdf")
    pruefe(len(a) == 10, "genau 10 Zeichen, ist %d" % len(a))
    pruefe(all(c in ALPHABET for c in a), "nur a-z0-9: %r" % a)
    pruefe(a == schluessel.fingerabdruck("kap/KundeA/Angebot.pdf"), "stabil")
    pruefe(a != schluessel.fingerabdruck("kap/KundeB/Angebot.pdf"),
           "zwei Kunden, gleicher Dateiname: zwei Abdruecke")
    pruefe(schluessel.fingerabdruck("Kunde/Angebot 2024/x.pdf")
           != schluessel.fingerabdruck("Kunde/Angebot/2024 x.pdf"),
           "Trennzeichen-Falle bleibt unterscheidbar")


def test_schluessel():
    print("\nSchluessel")
    S, K, F = schluessel.schluessel, schluessel.kennpfad, schluessel.fingerabdruck
    s = S("kap", "archiv/kunde/angebot/bericht.pdf")
    pruefe(s.count(".pdf") == 1, "Endung steht genau einmal drin: %r" % s)
    pruefe(len(s.encode("utf-8")) <= 200,
           "hoechstens 200 Byte, ist %d" % len(s.encode("utf-8")))
    pruefe(all(ord(c) < 128 for c in s), "reines ASCII")
    pruefe(F(K("kap", "archiv/kunde/angebot/bericht.pdf")) in s, "Abdruck steckt drin")
    # Der Umzug - das Kernstueck des Vertrags
    pruefe(S("kap", "parkplatz/KundeA/A.pdf") == S("kap", "archiv/KundeA/A.pdf"),
           "parkplatz und archiv ergeben EINEN Schluessel")
    pruefe(S("kap", "archiv/KundeA/A.pdf") != S("auw", "archiv/KundeA/A.pdf"),
           "zwei Bereiche ergeben ZWEI Schluessel")
    # Punktnamen, die keine Endung sind (in Kundenordnern die Regel)
    for name, erwartet in (("Angebot Nr. 4711", ""), ("Pruefbericht v1.2 final", ""),
                           ("2024.09.20 Protokoll", ""), ("Bericht.pdf", ".pdf"),
                           ("Tabelle.XLSX", ".xlsx")):
        sn = S("kap", "archiv/" + name)
        endet = sn[sn.rindex("--") + 12:]
        pruefe(endet == erwartet,
               "Endung von %r ist %r (erwartet %r)" % (name, endet, erwartet))
    # Ueberlaenge
    lang = "archiv/" + "/".join("o" * 40 for _ in range(8)) + "/datei.pdf"
    sl = S("kap", lang)
    pruefe(len(sl.encode("utf-8")) <= 200,
           "acht tiefe Ebenen unter 200 Byte, ist %d" % len(sl.encode("utf-8")))
    pruefe(F(K("kap", lang)) in sl, "Abdruck ueberlebt die Kuerzung")
    # Lange Punkt-Kette darf die Zusicherung nicht sprengen.
    # ACHTUNG: Die naechsten zwei Pruefungen allein reichen NICHT. Gegenprobe
    # am 21.09.: Entfernt man das max(0, ...) in schluessel(), bleiben sie
    # gruen - weil die Endungsregel den Fall schon ausschliesst. Rot wird erst
    # die dritte, und sie bewacht genau die Bedingung, von der die anderen
    # beiden still abhaengen.
    kette = "archiv/datei." + "x" * 200
    sx = S("kap", kette)
    pruefe(len(sx.encode("utf-8")) <= 200,
           "lange Punkt-Kette bleibt unter 200, ist %d" % len(sx.encode("utf-8")))
    pruefe(sx.split("--")[0] != "", "lesbarer Teil ist nicht leer")
    pruefe(len(schluessel._endung_von(K("kap", kette)).encode("utf-8")) <= 9,
           "eine 200-Zeichen-Punkt-Kette gilt NICHT als Endung - sonst wird der "
           "Platz fuer den lesbaren Teil negativ und die 200 Byte fallen")
    # Die Wort-Ersetzungen aus der Messung
    for z in ("&", "%", "€", "ü"):
        p = "archiv/Bericht %s Anlage/x.pdf" % z
        sp = S("kap", p)
        pruefe(F(K("kap", p)) in sp, "Abdruck unversehrt bei %r" % z)
        pruefe(all(ord(ch) < 128 for ch in sp), "Ergebnis bleibt ASCII bei %r" % z)
    # Nicht-lateinische Namen: Identitaet heil, aber der lesbare Teil ist weg.
    # NICHT "... or sc.startswith('kap')" schreiben - das ist immer wahr, weil
    # der lesbare Teil stets mit dem Bereichsnamen beginnt. Genau festschreiben,
    # was herauskommt, sonst kann die Pruefung nicht rot werden.
    for name in ("中文文件.pdf", "Документ.pdf", "___.pdf"):
        lesbar = S("kap", "archiv/" + name).split("--")[0]
        pruefe(lesbar == "kap",
               "nicht-lateinisch %r: lesbarer Teil ist GENAU der Bereich, ist %r"
               % (name, lesbar))
    pruefe(S("kap", "archiv/Bericht.pdf").split("--")[0] != "kap",
           "lateinischer Name behaelt dagegen seinen lesbaren Teil")


STEUER = {"bereich.json", "metadaten.json", "prompt.md", "kategorien.txt",
          "bilder-nachholen.txt", "aussortiert.log"}


def test_invariante_am_bestand():
    """Ueber einen echten Ordnerbaum. Gibt AUSSCHLIESSLICH Zahlen aus -
    keine Datei- und keine Ordnernamen. Mit der Datensperre vereinbar.

    Was hier NICHT geprueft wird: Kollisionsfreiheit. Der Abdruck geht ueber
    den unbereinigten Kennpfad und wird immer vollstaendig angehaengt - zwei
    verschiedene Kennpfade koennen deshalb gar nicht denselben Schluessel
    ergeben. Das ist Arithmetik ueber SHA-256, keine Eigenschaft dieses
    Entwurfs, und eine Pruefung darauf waere immer gruen. Die Zahl wird
    ausgegeben, aber nicht als Zusicherung verkauft.
    """
    print("\nAm echten Bestand")
    wurzel = os.environ.get("KI4KI_PRUEFBAUM", "/daten/pdfs")
    if not os.path.isdir(wurzel):
        pruefe(False, "Pruefbaum fehlt - der Lauf ist NICHT gueltig")
        return
    kennpfade, schluessel_menge, dokumente, tiefste = set(), set(), 0, 0
    zu_lang, nicht_ascii, nur_bereich, uebersprungen, fehler = 0, 0, 0, 0, 0
    # Ohne diese Verteilung ist "kein Schluessel ueber 200 Byte" wertlos: Sind
    # alle Schluessel 60 Byte lang, ist das Gruen geschenkt und die Zusicherung
    # hat am Bestand nichts geprueft. Erst der Abstand zur Grenze sagt, ob sie
    # ueberhaupt rot werden KONNTE.
    laengster_s, laengster_kp, nah_an_grenze, gekuerzt = 0, 0, 0, 0
    ohne_abdruck = 0
    for ordner, _unter, namen in os.walk(wurzel):
        for n in namen:
            if n in STEUER or n.endswith(".log"):
                uebersprungen += 1
                continue
            rel = os.path.relpath(os.path.join(ordner, n), wurzel)
            teile = rel.replace(os.sep, "/").split("/", 1)
            if len(teile) < 2:
                # Datei direkt in der Wurzel: kein Bereich, nicht zerlegbar.
                fehler += 1
                continue
            try:
                kp = schluessel.kennpfad_aus_bestandspfad(rel)
                s = schluessel.schluessel(teile[0], teile[1])
            except ValueError:
                fehler += 1
                continue
            dokumente += 1
            tiefste = max(tiefste, rel.count(os.sep) + 1)
            kennpfade.add(kp)
            schluessel_menge.add(s)
            byte_s = len(s.encode("utf-8"))
            if byte_s > 200:
                zu_lang += 1
            if byte_s > 150:
                nah_an_grenze += 1
            laengster_s = max(laengster_s, byte_s)
            laengster_kp = max(laengster_kp, len(kp.encode("utf-8")))
            # Der lesbare Teil wurde gestutzt, wenn er genau an der Schranke
            # endet - dann greift die Kuerzung ueberhaupt.
            if len(s.split("--")[0].encode("utf-8")) >= schluessel.LESBAR_BYTE:
                gekuerzt += 1
            if any(ord(c) > 127 for c in s):
                nicht_ascii += 1
            # Die eigentliche Zusicherung am Bestand: Der Abdruck ist das
            # Einzige, was verglichen wird. Frisst die Kuerzung ihn an, ist das
            # Dokument nicht mehr identifizierbar - und zwar still.
            if schluessel.fingerabdruck(kp) not in s:
                ohne_abdruck += 1
            # NICHT auf den Rueckfall pruefen: der Bereichsname ueberlebt die
            # Bereinigung immer, der lesbare Teil wird deshalb nie leer und der
            # Rueckfall nie erreicht. Ein Zaehler darauf meldete dauerhaft 0 und
            # behauptete "kein Problem". Die Zahl, die wirklich etwas sagt:
            if s.split("--")[0] == schluessel._bereinigen(kp.split("/")[0]):
                nur_bereich += 1
    print("  %d Dokumente (%d Steuerdateien uebersprungen, %d unzerlegbar)"
          % (dokumente, uebersprungen, fehler))
    print("  %d Kennpfade, %d Schluessel, tiefste Ebene %d"
          % (len(kennpfade), len(schluessel_menge), tiefste))
    print("  Doppelablagen (dieselbe Datei in zwei Stufen): %d"
          % (dokumente - len(kennpfade)))
    print("  laengster Schluessel %d Byte (Grenze 200), laengster Kennpfad %d Byte"
          % (laengster_s, laengster_kp))
    print("  ueber 150 Byte: %d · lesbarer Teil gestutzt: %d"
          % (nah_an_grenze, gekuerzt))
    # Die vier Zusicherungen, die am Bestand WIDERLEGBAR sind:
    pruefe(dokumente > 0, "der Pruefbaum enthaelt Dokumente")
    pruefe(zu_lang == 0, "kein Schluessel ueber 200 Byte, darueber: %d" % zu_lang)
    pruefe(nicht_ascii == 0,
           "alle Schluessel reines ASCII, mit Sonderzeichen: %d" % nicht_ascii)
    pruefe(fehler == 0, "jeder Pfad zerlegbar, unzerlegbar: %d" % fehler)
    pruefe(ohne_abdruck == 0,
           "in jedem Schluessel steckt der Abdruck seines Kennpfads, ohne: %d"
           % ohne_abdruck)
    # ⛔ Die 200-Byte-Zusicherung oben ist STRUKTURELL immer gruen: der lesbare
    #    Teil ist auf LESBAR_BYTE gedeckelt, der Schwanz auf 2 + 10 + hoechstens
    #    9 Byte Endung. Mehr als die Summe kann nie herauskommen - an keinem
    #    Bestand. Gemessen 21.09.: laengster Schluessel 137 Byte bei 4.484
    #    Dokumenten, und 137 = 120 + 2 + 10 + 5.
    #    Scharf ist deshalb erst der Vergleich mit DIESER Obergrenze. Sie wird
    #    rot, sobald die Kuerzung nicht mehr greift, LESBAR_BYTE steigt oder die
    #    Endungsregel aufgeweicht wird - also genau dann, wenn etwas kaputt ist.
    obergrenze = schluessel.LESBAR_BYTE + len("--") + 10 + 9
    pruefe(laengster_s <= obergrenze,
           "laengster Schluessel %d Byte, Obergrenze aus den Konstanten %d"
           % (laengster_s, obergrenze))
    print("  Abstand zur 200-Byte-Grenze: %d Byte ungenutzt. Die Grenze wird"
          " nicht von GRENZE_BYTE erzwungen, sondern von LESBAR_BYTE."
          % (200 - laengster_s))
    # Keine Zusicherung, sondern die Kennzahl, die wirklich etwas aussagt:
    print("  Hinweis: bei %d Dokumenten besteht der lesbare Teil NUR noch aus dem"
          " Bereichsnamen - dort ist die Zuordnung im Schluessel verloren"
          % nur_bereich)


if __name__ == "__main__":
    test_kennpfad()
    test_fingerabdruck()
    test_schluessel()
    test_invariante_am_bestand()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
