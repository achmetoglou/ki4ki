#!/usr/bin/env python3
"""Trennt die Schwelle 3 aus _aussage_gedeckt() im heutigen Bestand noch?

Hintergrund (24.09.): _aussage_gedeckt(name, kontext) nimmt die FACHWOERTER
(>6 Z., _fachwoerter) aus dem Kontext und urteilt "ja", sobald auf
IRGENDEINER Seite des Dokuments mindestens 3 davon vorkommen. Der Kommentar
dort nennt die Grundlage: ">=3 Treffer je Seite trennt das richtige Dokument
vom falschen (<=2)".

⛔ Diese Zahl ist an DISSERTATIONEN gemessen - langen Arbeiten, die sich
  stark unterscheiden. Heute liegen im Bestand Rechnungen, Angebote und
  Reisekostenbelege: kurz, wiederholt, teils fast gleich. Am 24.09. bekam
  von zwei fast gleichen Rechnungen (274821 TS-1 und TS-2) die eine ihren
  Beleg-Link, die andere nicht. Die Schwelle ist an einer Dokumentenwelt
  kalibriert, die es so nicht mehr gibt. Dieses Skript rechnet nach, ob sie
  im heutigen Bestand noch trennt.

MESSPLAN. Je Dokument wird EINE Seite zur "Aussage" erklaert (der Kontext).
Dann zaehlen wir die gemeinsamen Fachwoerter auf der besten Seite:
  RICHTIGER Fall - gegen die EIGENEN Seiten des Dokuments. Erwartet hoch.
  FALSCHER Fall  - gegen die Seiten ANDERER Dokumente. Erwartet niedrig.
Die Zahl, um die es geht, ist die dritte Zeile im Abschnitt "Schwelle 3":
wie viele FALSCHE Faelle die 3 trotzdem reissen. Das sind die Fehlurteile.

⛔ Gerechnet wird mit den ECHTEN Funktionen des Proxys (_fachwoerter,
  _seitentexte_pdf) - nichts ist nachgebaut. Eine nachgebaute Messung misst
  das falsche Artefakt und kann gruen sein, waehrend die eingesetzte rot
  ist. Gegenprobe 1 unten weist genau das nach: Das gezaehlte Urteil muss
  Fall fuer Fall mit dem uebereinstimmen, was _aussage_gedeckt() selbst
  sagt. Weicht ein einziger Fall ab, ist die Messung UNGUELTIG.

⚠ Vorbehalt zur Kontextgroesse: Als Aussage dient hier eine GANZE Seite.
  Eine echte Modellaussage ist kuerzer und hat weniger Fachwoerter. Die
  Zahlen gelten fuer diese Kontextgroesse, und die Ausgabe sagt es dazu.

⛔ Gibt AUSSCHLIESSLICH Zahlen aus. Keine Dokumentnamen, keine Woerter aus
   den Dokumenten, keine Textausschnitte - auch keine Fehlermeldungen, die
   einen Pfad enthalten koennten (gemeldet wird nur die Fehlerart). Mit der
   Datensperre vereinbar.

  docker exec ki4ki-pruef-proxy python3 /app/schwellenprobe.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Die Schwelle, die heute im Einsatz ist (_aussage_gedeckt).
SCHWELLE = 3

# Stichprobe. Alle gegen alle waere quadratisch: bei 4 000 Dokumenten
# 16 Millionen Vergleiche und jedes Mal pdftotext. Die Groessen stehen
# deshalb hier oben und werden in der Ausgabe mitgedruckt - eine
# Stichprobe, deren Groesse man nicht sieht, ist keine Messung.
SAAT = 20250924           # feste Saat: zwei Laeufe sind vergleichbar
STICHPROBE_DOK = 40       # so viele Dokumente werden verwertet
ANSEHEN_MAX = 400         # so viele Titel werden dafuer hoechstens geoeffnet
GEGEN_JE = 12             # fremde Dokumente je Aussage
ABGLEICH_MAX = 60         # Faelle fuer den Abgleich mit _aussage_gedeckt


def _quantil(werte, q):
    """q-Quantil einer Liste ganzer Zahlen (0.0 = kleinster Wert)."""
    if not werte:
        return 0
    s = sorted(werte)
    return s[int(round((len(s) - 1) * q))]


def _verteilung(bezeichnung, werte):
    """Haeufigkeitstabelle der Trefferzahlen. Nur Zahlen.

    ⚠ Der Parameter heisst BEZEICHNUNG, nicht titel: In dieser
      Datei ist "Titel" der Dokumenttitel, und der darf nie in eine
      Ausgabe. Ein gleichnamiger Parameter, der etwas anderes meint,
      laesst den naechsten Leser beim Pruefen zweimal hinsehen - und
      beim zweiten Mal vielleicht nicht mehr.
    """
    n = len(werte)
    print("  %s  n=%d  min=%d  10%%=%d  Median=%d  90%%=%d  max=%d"
          % (bezeichnung, n, min(werte), _quantil(werte, 0.10),
             _quantil(werte, 0.50), _quantil(werte, 0.90), max(werte)))
    for k in range(0, 10):
        c = sum(1 for w in werte if w == k)
        if c:
            print("      %4d Treffer: %5d  (%5.1f %%)" % (k, c, 100.0 * c / n))
    c = sum(1 for w in werte if w >= 10)
    if c:
        print("      >=10 Treffer: %5d  (%5.1f %%)" % (c, 100.0 * c / n))


def main():
    import pruef_proxy as p
    import veredeln

    if p.BESTAND is None:
        # Genau wie beim echten Start: BESTAND entsteht erst in main(), nicht
        # beim Import. Ohne diese beiden Zeilen ist er None - und die Messung
        # meldete Nullen, statt sich fuer ungueltig zu erklaeren.
        p.BESTAND = veredeln.Bestand()
        p.BESTAND._rohtext()
    p.pdfs_einlesen()
    try:
        titel = list(p.BESTAND.titel())
    except Exception as e:
        # ⛔ Nur die Fehlerart, nicht der Text: eine Ausnahmemeldung
        #   transportiert regelmaessig einen Dateipfad, und der gehoert
        #   nicht in ein Protokoll, das weitergereicht wird.
        print("Bestand nicht lesbar (%s) - DIE MESSUNG IST UNGUELTIG"
              % type(e).__name__)
        return 1
    if not titel:
        print("Der Bestand ist leer - DIE MESSUNG IST UNGUELTIG: Ohne "
              "Dokumente laesst sich ueber keine Schwelle etwas sagen.")
        return 1

    # --- Stichprobe ziehen -------------------------------------------------
    # Erst mischen, dann der Reihe nach oeffnen, bis genug verwertbare
    # Dokumente zusammen sind. So bleibt die Zahl der pdftotext-Laeufe
    # beschraenkt, und die Auswahl ist trotzdem nicht die Sortierung.
    misch = list(titel)
    random.Random(SAAT).shuffle(misch)

    seiten_je_dok = []     # Liste von Seitentexten je verwertetem Dokument
    namen_je_dok = []      # Stamm - NUR intern, wird nie gedruckt
    angesehen = 0
    ohne_schluessel = 0
    ohne_seiten = 0

    for t in misch[:ANSEHEN_MAX]:
        if len(seiten_je_dok) >= STICHPROBE_DOK:
            break
        angesehen += 1
        stamm = p._stamm(t)
        sch = p._pdf_schluessel(stamm)
        if not sch:
            ohne_schluessel += 1
            continue
        try:
            seiten = p._seitentexte_pdf(sch) or []
        except Exception:
            seiten = []
        seiten = [s for s in seiten if (s or "").strip()]
        if not seiten:
            ohne_seiten += 1
            continue
        seiten_je_dok.append(seiten)
        namen_je_dok.append(stamm)

    anzahl_dok = len(seiten_je_dok)
    if anzahl_dok < 2:
        print("Nur %d Dokument(e) mit Seitentexten gefunden (%d Titel "
              "angesehen) - DIE MESSUNG IST UNGUELTIG: Ohne ein ZWEITES "
              "Dokument gibt es keinen falschen Fall, und ohne falschen Fall "
              "keine Aussage ueber eine Trennschwelle." % (anzahl_dok, angesehen))
        return 1

    # --- Fachwoerter je Seite, einmal ------------------------------------
    # p._fachwoerter ist die ECHTE Zerlegung des Proxys. Sie wird je Seite
    # genau einmal aufgerufen und das Ergebnis gemerkt; gerechnet wird
    # danach nur noch mit Mengenschnitten.
    fw_je_dok = [[p._fachwoerter(s) for s in seiten] for seiten in seiten_je_dok]

    # --- Aussagen waehlen -------------------------------------------------
    # Als Aussage dient die erste Seite, die die Vorbedingung von
    # _aussage_gedeckt() ueberhaupt erfuellt: mindestens 3 Fachwoerter.
    # Seiten darunter urteilt die eingesetzte Funktion "unpruefbar", sie
    # gehoeren also nicht in diese Messung.
    aussagen = []          # (dok_index, seiten_index)
    ohne_fachwoerter = 0
    for i in range(anzahl_dok):
        gewaehlt = None
        for j, menge in enumerate(fw_je_dok[i]):
            if len(menge) >= SCHWELLE:
                gewaehlt = j
                break
        if gewaehlt is None:
            ohne_fachwoerter += 1
            continue
        aussagen.append((i, gewaehlt))

    if not aussagen:
        print("Kein einziges Dokument hat eine Seite mit mindestens %d "
              "Fachwoertern (%d Dokumente angesehen) - DIE MESSUNG IST "
              "UNGUELTIG: _aussage_gedeckt() urteilt hier durchweg "
              "'unpruefbar', es gibt also gar kein Urteil zu pruefen."
              % (SCHWELLE, anzahl_dok))
        return 1

    # --- Messen -----------------------------------------------------------
    richtig = []           # Treffer gegen die EIGENEN Seiten
    richtig_ohne = []      # dasselbe, aber ohne die Quellseite (mehrseitig)
    falsch = []            # Treffer gegen FREMDE Seiten
    abgleich_faelle = []   # (dok_index_ziel, dok_index_aussage, seite, wert)

    wuerfel = random.Random(SAAT + 1)
    for (i, j) in aussagen:
        ziel6 = fw_je_dok[i][j]

        eigen = [len(ziel6 & m) for m in fw_je_dok[i]]
        richtig.append(max(eigen))
        abgleich_faelle.append((i, i, j, max(eigen)))
        if len(eigen) >= 2:
            richtig_ohne.append(max(w for k, w in enumerate(eigen) if k != j))

        andere = [k for k in range(anzahl_dok) if k != i]
        wuerfel.shuffle(andere)
        for k in andere[:GEGEN_JE]:
            wert = max([len(ziel6 & m) for m in fw_je_dok[k]] or [0])
            falsch.append(wert)
            abgleich_faelle.append((k, i, j, wert))

    if not falsch:
        print("Kein einziger falscher Vergleich zustande gekommen - DIE "
              "MESSUNG IST UNGUELTIG: gemessen wuerde dann nur, dass ein "
              "Dokument sich selbst deckt.")
        return 1

    # --- Ausgabe: Stichprobe ---------------------------------------------
    print("Schwellenprobe fuer _aussage_gedeckt() - Schwelle im Einsatz: %d"
          % SCHWELLE)
    print()
    print("Stichprobe (Saat %d, damit zwei Laeufe vergleichbar sind)" % SAAT)
    print("  Dokumente im Bestand insgesamt   : %6d" % len(titel))
    print("  davon geoeffnet (Obergrenze %4d): %6d" % (ANSEHEN_MAX, angesehen))
    print("    davon ohne PDF-Schluessel      : %6d" % ohne_schluessel)
    print("    davon ohne Seitentext          : %6d" % ohne_seiten)
    print("  verwertete Dokumente             : %6d" % anzahl_dok)
    print("    davon ohne Seite mit >=%d Fachwoertern: %d"
          % (SCHWELLE, ohne_fachwoerter))
    print("  Aussagen (je Dokument eine Seite): %6d" % len(aussagen))
    print("  Vergleiche RICHTIG (eigenes Dok.): %6d" % len(richtig))
    print("  Vergleiche FALSCH (fremde Dok.)  : %6d  (bis zu %d je Aussage)"
          % (len(falsch), GEGEN_JE))
    print("  Kontext je Aussage = eine GANZE Seite. Eine echte Modellaussage")
    print("  ist kuerzer und hat weniger Fachwoerter; die Zahlen unten gelten")
    print("  fuer diese Kontextgroesse.")
    print()

    # --- Ausgabe: Verteilungen -------------------------------------------
    print("Verteilung der Treffer (gemeinsame Fachwoerter auf der besten Seite)")
    _verteilung("RICHTIG", richtig)
    _verteilung("FALSCH ", falsch)
    if richtig_ohne:
        print("  Zusatz - RICHTIG ohne die Quellseite (nur mehrseitige Dok.):")
        _verteilung("RICHTIG*", richtig_ohne)
    else:
        print("  Zusatz RICHTIG ohne Quellseite: nicht moeglich, kein "
              "mehrseitiges Dokument in der Stichprobe.")
    print()

    # --- Ausgabe: die Zahl, um die es geht -------------------------------
    r_ja = sum(1 for w in richtig if w >= SCHWELLE)
    f_ja = sum(1 for w in falsch if w >= SCHWELLE)
    # Trennung an der eingesetzten Schwelle - unten im Befund noch gebraucht.
    tr_einsatz = r_ja / float(len(richtig)) - f_ja / float(len(falsch))
    print("Schwelle %d - so urteilt die Anlage heute" % SCHWELLE)
    print("  RICHTIG als gedeckt erkannt : %6d von %6d = %5.1f %%"
          % (r_ja, len(richtig), 100.0 * r_ja / len(richtig)))
    print("  FEHLURTEILE (FALSCH reisst %d): %6d von %6d = %5.1f %%"
          % (SCHWELLE, f_ja, len(falsch), 100.0 * f_ja / len(falsch)))
    print("  -> %d fremde Dokumente haetten eine Aussage 'gedeckt', die sie "
          "nicht decken." % f_ja)
    print()

    # --- Ausgabe: Schwellenvergleich -------------------------------------
    # Trennung = Anteil richtig erkannt MINUS Anteil Fehlurteile. 1.000 waere
    # vollstaendige Trennung, 0.000 heisst: die Schwelle unterscheidet die
    # beiden Faelle ueberhaupt nicht.
    hoechste = max(max(richtig), max(falsch))
    print("Schwellen im Vergleich")
    print("  Schwelle  richtig erkannt  Fehlurteile   Trennung")
    beste_s, beste_tr = None, None
    for s in range(1, hoechste + 2):
        rq = sum(1 for w in richtig if w >= s) / float(len(richtig))
        fq = sum(1 for w in falsch if w >= s) / float(len(falsch))
        tr = rq - fq
        if beste_tr is None or tr > beste_tr:
            beste_s, beste_tr = s, tr
        if s <= 15:
            print("  %8d  %13.1f %%  %9.1f %%   %+7.3f"
                  % (s, 100.0 * rq, 100.0 * fq, tr))
    if hoechste + 1 > 15:
        print("  (Schwellen ueber 15 gerechnet, aber nicht gedruckt; "
              "hoechster gemessener Trefferwert: %d)" % hoechste)
    print("  Beste Trennung bei Schwelle %d (Trennung %+.3f). Im Einsatz "
          "ist %d." % (beste_s, beste_tr, SCHWELLE))
    print()

    # --- Gegenprobe 1: misst dieses Skript ueberhaupt das Richtige? -------
    # ⛔ Ohne diese Gegenprobe ist die ganze Messung wertlos. Sie ruft die
    #   EINGESETZTE Funktion _aussage_gedeckt() auf und vergleicht deren
    #   Urteil mit dem, was die Zaehlung oben ergibt. Stimmen sie nicht
    #   ueberein, misst dieses Skript ein anderes Artefakt als die Anlage -
    #   dann sind alle Zahlen oben hinfaellig, egal wie gut sie aussehen.
    #
    #   Womit sie ROT wird: sobald SCHWELLE hier oben von der 3 in
    #   _aussage_gedeckt() abweicht, sobald dort die Vorbedingung oder die
    #   Zerlegung geaendert wird, oder sobald jemand die Zaehlung oben
    #   nachbaut statt p._fachwoerter zu benutzen. Im Trockenlauf mit einer
    #   Attrappe nachgestellt: Anlagenschwelle 5 gegen gezaehlte 3, Treffer
    #   durchweg 4 -> 60 von 60 Faellen abweichend, Rueckgabe 1.
    #
    # ⚠ WAS SIE NICHT SIEHT, und das gehoert dazu: Sie faellt nur auf,
    #   wenn die gemessenen Trefferzahlen ZWISCHEN den beiden Schwellen
    #   liegen. Derselbe Trockenlauf mit Treffern von 6 und 8 blieb bei
    #   Anlagenschwelle 5 gegen gezaehlte 3 gruen - beide urteilen dort
    #   "ja". Eine gruene Gegenprobe 1 heisst also: in DIESER Stichprobe
    #   kein Unterschied nachweisbar, nicht: die Schwellen sind gleich.
    wuerfel.shuffle(abgleich_faelle)
    proben = abgleich_faelle[:ABGLEICH_MAX]
    abweichung = 0
    unpruefbar = 0
    for (ziel, aussage_dok, seite, wert) in proben:
        kontext = seiten_je_dok[aussage_dok][seite]
        try:
            urteil = p._aussage_gedeckt(namen_je_dok[ziel], kontext)
        except Exception:
            urteil = "(fehler)"
        erwartet = "ja" if wert >= SCHWELLE else "nein"
        if urteil == "unpruefbar":
            unpruefbar += 1
            abweichung += 1
        elif urteil != erwartet:
            abweichung += 1

    print("Gegenprobe 1 - zaehlt dieses Skript dasselbe wie die Anlage?")
    print("  Faelle gegen _aussage_gedeckt() geprueft: %d" % len(proben))
    print("  davon abweichend                        : %d" % abweichung)
    print("  davon 'unpruefbar' (zaehlt als Abweichung): %d" % unpruefbar)
    if abweichung:
        print("⛔ DIE MESSUNG IST UNGUELTIG: Die Zaehlung oben und die "
              "eingesetzte Funktion urteilen in %d von %d Faellen "
              "verschieden. Dann misst dieses Skript nicht die Schwelle, "
              "die im Einsatz ist, sondern eine andere - und jede Zahl "
              "oben waere ein Ergebnis ueber das falsche Artefakt."
              % (abweichung, len(proben)))
        return 1
    print("  Gueltig: alle %d Faelle stimmen ueberein. Gemessen wird die "
          "Funktion, die auch die Anlage benutzt." % len(proben))
    print()

    # --- Gegenprobe 2: kann die Messung ueberhaupt einen Treffer finden? --
    # Ein Dokument gegen sich selbst muss deutlich ueber der Schwelle liegen.
    # ⚠ Die Quellseite deckt sich per Definition mit sich selbst; der Wert
    #   in `richtig` ist deshalb immer mindestens so gross wie die Zahl der
    #   Fachwoerter der Aussage. Beweiskraft hat daher nur die Fassung OHNE
    #   die Quellseite: dort kann die Probe wirklich rot werden.
    print("Gegenprobe 2 - liegt ein Dokument gegen sich selbst klar oben?")
    if not richtig_ohne:
        print("  NICHT DURCHGEFUEHRT: kein mehrseitiges Dokument in der "
              "Stichprobe (%d Dokumente). Die Fassung MIT Quellseite taugt "
              "nicht als Nachweis - sie ist rechnerisch immer >= der Zahl "
              "der Fachwoerter der Aussage und kann gar nicht rot werden."
              % anzahl_dok)
        print("  Median RICHTIG (mit Quellseite, ohne Beweiskraft): %d"
              % _quantil(richtig, 0.50))
    else:
        med = _quantil(richtig_ohne, 0.50)
        ueber = sum(1 for w in richtig_ohne if w >= SCHWELLE)
        print("  mehrseitige Dokumente in der Stichprobe : %d" % len(richtig_ohne))
        print("  Median der Treffer ohne Quellseite      : %d" % med)
        print("  davon >= Schwelle %d                     : %d = %5.1f %%"
              % (SCHWELLE, ueber, 100.0 * ueber / len(richtig_ohne)))
        if med < SCHWELLE:
            print("⛔ DIE MESSUNG IST UNGUELTIG: Ein Dokument deckt nicht "
                  "einmal seine eigene Aussage. Dann sind die Seitentexte "
                  "zu duenn oder die Zerlegung greift nicht - die "
                  "Fehlurteilsquote oben misst dann nicht die Schwelle, "
                  "sondern einen Ausfall beim Textlesen.")
            return 1
        print("  Gueltig: die Messung findet Treffer, wo Treffer sein muessen.")
    print()

    # --- Befund -----------------------------------------------------------
    if f_ja == 0:
        print("Befund: Kein Fehlurteil in dieser Stichprobe. Die Schwelle %d "
              "trennt hier noch. Das schliesst Einzelfaelle nicht aus - die "
              "Stichprobe umfasst %d falsche Vergleiche aus %d Dokumenten."
              % (SCHWELLE, len(falsch), anzahl_dok))
    else:
        print("Befund: %d von %d falschen Vergleichen (%.1f %%) reissen die "
              "Schwelle %d. In so vielen Faellen kann die Anlage ein fremdes "
              "Dokument nicht vom richtigen unterscheiden."
              % (f_ja, len(falsch), 100.0 * f_ja / len(falsch), SCHWELLE))
    if beste_s != SCHWELLE:
        print("        Am besten getrennt haette in dieser Stichprobe die "
              "Schwelle %d (Trennung %+.3f gegen %+.3f bei Schwelle %d)."
              % (beste_s, beste_tr, tr_einsatz, SCHWELLE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
