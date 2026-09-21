"""Pruefungen fuer das Schluesselmodul.

Laeuft ohne Testrahmen: python3 schluesseltest.py
Rueckgabewert 0, wenn alles gruen ist, sonst 1.

Grundsatz dieser Datei: Zu jeder Pruefung gehoert der Nachweis, mit WELCHER
Eingabe sie rot wird. Eine Pruefung, die per Konstruktion immer gruen ist,
beweist nichts - in vier Planfassungen standen vier solche Pruefungen.
"""
import hashlib
import os
import re
import sys
import unicodedata

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


def test_abdruck_lesen():
    """Findet die Anlage den Abdruck wieder, nachdem ein Name durch eine der
    neun Normalisierungen des Hauses gelaufen ist?

    Die Formen unten sind die echten Funktionen, nachgebaut - je EINZELN,
    damit beim Fehlschlag dasteht, WELCHE den Abdruck frisst.
    """
    print("\nAbdruck wiederfinden")
    S, K, F = schluessel.schluessel, schluessel.kennpfad, schluessel.fingerabdruck
    pfad = "archiv/KundeA/Angebot 2024/Bericht.pdf"
    s = S("kap", pfad)
    echt = F(K("kap", pfad))

    def _nfkd(t):
        n = unicodedata.normalize("NFKD", t)
        return "".join(c for c in n if not unicodedata.combining(c))

    def _umlaute(t):
        for alt, neu in (("ä", "ae"), ("ö", "oe"),
                         ("ü", "ue"), ("ß", "ss")):
            t = t.replace(alt, neu)
        return t

    formen = {
        "roh": lambda t: t,
        "_loesch_grund": lambda t: re.sub(
            r"[^a-z0-9]", "", _nfkd(t).lower().replace("ß", "ss")),
        "_grundform": lambda t: re.sub(r"[^a-z0-9]", "", t.lower()),
        "_flach_stamm": lambda t: re.sub(r"[^a-z0-9]", "", _umlaute(t.lower())),
        "assistent._flach": lambda t: re.sub(
            r"[^a-z0-9]", "", _umlaute(t.lower())),
        "bestand._grund": lambda t: re.sub(r"[^a-z0-9]", "", t.lower()),
        "metadaten._grund": lambda t: re.sub(
            r"[^a-z0-9]", "",
            t.lower().replace(".pdf", "").replace(".md", "")),
        "_wie_anythingllm": lambda t: re.sub(
            r"[^A-Za-z0-9]+", "-", _nfkd(t).replace("ß", "ss")).strip("-").lower(),
        "n8n grund()": lambda t: re.sub(
            r"[^A-Za-z0-9]+", "-", _nfkd(t).replace("ß", "ss")).strip("-").lower(),
        "AnythingLLM-Ablage": lambda t: (
            t + ".md-11111111-2222-3333-4444-555555555555.json"),
    }
    for wie, f in formen.items():
        gefunden = schluessel.abdruck_finden(f(s), {echt: "x"})
        pruefe(gefunden == echt,
               "Abdruck ueberlebt %s: gefunden %r, erwartet %r"
               % (wie, gefunden, echt))

    # Die Gegenprobe, ohne die alles oben wertlos waere: Ein Name OHNE
    # Abdruck darf NICHTS treffen. Sonst ordnet die Anlage jedem alten
    # Dokumentnamen still ein fremdes Dokument zu.
    for alt in ("DS-24-005.pdf", "Pruefbericht Ultraschall 2024.pdf",
                "LE Klangpruefung.md", "Angebot.pdf"):
        pruefe(schluessel.abdruck_finden(alt, {echt: "x"}) is None,
               "alter Name %r trifft nichts" % alt)

    # Richtung: der ECHTE Abdruck steht rechts. Ein zufaellig passendes
    # Fenster im lesbaren Teil darf ihn nicht ueberholen. Dieser Fall ist
    # gebaut, nicht gefunden - genau deshalb kann die Pruefung rot werden:
    # Sucht abdruck_kandidaten von LINKS, liefert sie hier den falschen.
    fremd = F(K("auw", "archiv/Fremd.pdf"))
    gebastelt = "kap-" + fremd + "-Bericht--" + echt + ".pdf"
    pruefe(schluessel.abdruck_finden(gebastelt, {echt: "a", fremd: "b"}) == echt,
           "der Abdruck RECHTS gewinnt (links steckt %r)" % fremd)

    # ⛔ ohne_uuid ist NICHT Kosmetik - und die erste Fassung dieser Datei
    #   konnte das nicht zeigen: Wird ohne_uuid unschaedlich gemacht, bleibt
    #   "Abdruck ueberlebt AnythingLLM-Ablage" gruen, weil das Fensterverfahren
    #   den Abdruck auch weiter links noch findet (gemessen 21.09.).
    #   Wozu ohne_uuid also da ist, zeigt erst dieser Fall: Die 32 Hexzeichen
    #   der Kennung sind alphanumerisch und werden von RECHTS zuerst geprueft -
    #   rund 23 Fenster vor dem echten Abdruck. Faellt eines davon mit dem
    #   Abdruck eines anderen Dokuments zusammen, gewinnt das falsche.
    in_kennung = "abcdef0123"
    kennung = "-11111111-2222-3333-4444-9" + in_kennung + "9"
    pruefe(schluessel.abdruck_finden(s + ".md" + kennung + ".json",
                                     {echt: "richtig", in_kennung: "falsch"})
           == echt,
           "ein Abdruck IN der AnythingLLM-Kennung ueberholt den echten nicht")

    # Zu kurz, leer, None: kein Absturz, kein Treffer.
    for nichts in ("", None, "abc.pdf", "---"):
        pruefe(schluessel.abdruck_finden(nichts, {echt: "x"}) is None,
               "zu kurz/leer trifft nichts: %r" % nichts)


STEUER = {"bereich.json", "metadaten.json", "prompt.md", "kategorien.txt",
          "bilder-nachholen.txt", "aussortiert.log"}


def test_beide_kopien_gleich():
    """Zwei Dienste, eine Rechnung.

    pdfstelle.py liegt schon zweimal im Repo, byteweise identisch; mit
    schluessel.py kommt eine zweite solche Kopie dazu. Beide Container bauen
    mit COPY *.py - wer nur eine Kopie aendert, hat im anderen Dienst
    stillschweigend die alte Fassung. Die Aufnahme vergaebe dann Schluessel,
    die die Auswertung nicht kennt.
    """
    print("\nBeide Kopien identisch")
    hier = os.path.dirname(os.path.abspath(__file__))
    for a, b in (("schluessel.py", "../mkmd-dienst/schluessel.py"),
                 ("pdfstelle.py", "../mkmd-dienst/pdfstelle.py")):
        pa, pb = os.path.join(hier, a), os.path.join(hier, b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            pruefe(False, "Kopie fehlt: %s oder %s" % (a, b))
            continue
        ha = hashlib.sha256(open(pa, "rb").read()).hexdigest()
        hb = hashlib.sha256(open(pb, "rb").read()).hexdigest()
        pruefe(ha == hb, "%s ist in beiden Diensten gleich (%s / %s)"
               % (a, ha[:8], hb[:8]))


def test_baum_enthaelt_die_fehlerklasse():
    """Taugt der Pruefbaum ueberhaupt als Grundlage?

    Ein Baum, an dem alles gruen ist, beweist nur dann etwas, wenn der
    HEUTIGE Schluessel (der nackte Dateiname) daran scheitert. Ist diese
    Zahl 0, ist der Baum zu brav und jedes Gruen darauf ist geschenkt.
    """
    print("\nTaugt der Pruefbaum?")
    wurzel = os.environ.get("KI4KI_PRUEFBAUM", "")
    if not os.path.isdir(wurzel):
        pruefe(False, "Pruefbaum fehlt - der Lauf ist NICHT gueltig")
        return
    heute, dateien = {}, 0
    for ordner, _unter, namen in os.walk(wurzel):
        for n in namen:
            if n in STEUER or n.endswith(".log"):
                continue
            dateien += 1
            k = re.sub(r"[^a-z0-9]", "", os.path.splitext(n)[0].lower())
            heute[k] = heute.get(k, 0) + 1
    kollidiert = sum(v for v in heute.values() if v > 1)
    print("  heutiger Schluessel: %d von %d Dateien kollidieren"
          % (kollidiert, dateien))
    pruefe(kollidiert > 0,
           "der Baum enthaelt die Fehlerklasse (kollidierende Dateien: %d) - "
           "sonst ist jede gruene Zusicherung darauf wertlos" % kollidiert)


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
    test_abdruck_lesen()
    test_beide_kopien_gleich()
    test_baum_enthaelt_die_fehlerklasse()
    test_invariante_am_bestand()
    print("\n%d Fehler" % len(FEHLER))
    sys.exit(1 if FEHLER else 0)
