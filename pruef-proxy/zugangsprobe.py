#!/usr/bin/env python3
"""Der Link ist einloesbar - aber DARF die Sitzung ihn auch einloesen?

Hintergrund (23.09. abends): linkprobe.py meldete 50 von 120 Dokumenten als
auslieferbar, nur 3 VERSCHOLLEN und 0 TOT. Trotzdem endete beim Nutzer JEDER
Beleg-Klick auf "Dieses Dokument liegt nicht vor."

⭐ Das ist kein Widerspruch, sondern die Arbeitsteilung der beiden Proben:
   linkprobe fragt "ist etwas auszuliefern?" - ausdruecklich "unabhaengig
   von jedem Recht". Diese Probe fragt das Recht. Und die Anlage beantwortet
   "unbekannt" und "gesperrt" absichtlich WORTGLEICH, damit niemand ueber
   die Fehlermeldung Namen erraten kann. Von aussen sind die beiden Faelle
   deshalb nicht zu unterscheiden - von innen schon.

⛔ Gemessen wird mit der ECHTEN dokument_erlaubt(), nicht mit einer
   Nachbildung ihrer Logik. Eine nachgebaute Pruefung misst das falsche
   Artefakt: Sie kann gruen sein, waehrend die eingesetzte rot ist. Zu jeder
   gemerkten Kennung laesst sich mit marke_bauen() eine gueltige Marke
   herstellen - damit geht der Aufruf denselben Weg wie ein Browser-Klick.

⛔ Gibt AUSSCHLIESSLICH Zahlen aus. Keine Dokumentnamen, keine Kennungen,
   keine Bereiche. Mit der Datensperre vereinbar.

  docker exec ki4ki-pruef-proxy python3 /app/zugangsprobe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _kopf(p, kennung):
    """Dieselbe Kopfzeile, die ein Browser beim Beleg-Klick schickt."""
    return {"Cookie": "ki4ki_zugang=" + p.marke_bauen(kennung)}


def _grund(p, schluessel, stamm, erlaubt):
    """Warum hat die echte Pruefung Nein gesagt? NUR zur Einfaerbung.

    ⚠ Das Urteil faellt oben die echte dokument_erlaubt(). Diese Funktion
      sortiert ein bereits gefallenes Nein nur in einen Topf - sie darf es
      nie ersetzen.
    """
    if not p.fuer_ki_freigegeben(stamm):
        return "ki_gesperrt"
    if not erlaubt:
        return "liste_leer"
    # Wortgleich mit dokument_erlaubt(): dieselbe Endungsliste, dieselbe
    # Kleinschreibung. Weicht das ab, faerbt die Probe falsch ein.
    gesucht = p.re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", stamm or "",
                       flags=p.re.I).strip().lower()
    if schluessel.abdruck_finden(gesucht, p.PDFS_ABDRUCK):
        return "abdruck_nicht_in_liste"
    return "altweg_daneben"


def main():
    import pruef_proxy as p
    import schluessel
    import veredeln

    if p.BESTAND is None:
        p.BESTAND = veredeln.Bestand()
        p.BESTAND._rohtext()
    p.pdfs_einlesen()

    try:
        titel = list(p.BESTAND.titel())
    except Exception as e:
        print("Bestand nicht lesbar (%s) - DIE MESSUNG IST UNGUELTIG"
              % str(e)[:120])
        return 1

    # Nur die Dokumente ansehen, die linkprobe als auslieferbar gemeldet hat.
    # Bei allen anderen waere ein Nein ohnehin richtig, und sie wuerden die
    # Zahlen verwaessern.
    lieferbar = []
    for t in titel:
        stamm = p._stamm(t)
        sch = p._pdf_schluessel(stamm)
        if sch and p.PDFS.get(sch) and os.path.exists(p.PDFS[sch]):
            lieferbar.append(stamm)
        else:
            try:
                datei = p._archivdatei(stamm)
            except Exception:
                datei = None
            if datei and os.path.exists(datei):
                lieferbar.append(stamm)

    zugaenge = sorted(p._DOKZUGANG.keys())
    if not lieferbar or not zugaenge:
        print("lieferbare Dokumente: %d, gemerkte Zugaenge: %d - DIE MESSUNG "
              "IST UNGUELTIG" % (len(lieferbar), len(zugaenge)))
        return 1

    print("lieferbare Dokumente: %d" % len(lieferbar))
    print("gemerkte Zugaenge   : %d" % len(zugaenge))
    print()

    gruende = {}
    blind = 0        # Zugaenge, die KEIN einziges Dokument oeffnen duerfen
    sehend = 0
    summe_ja = 0
    leere_listen = 0

    for kennung in zugaenge:
        erlaubt = p._DOKZUGANG[kennung][0]
        if not erlaubt:
            leere_listen += 1
        kopf = _kopf(p, kennung)
        ja = 0
        for stamm in lieferbar:
            if p.dokument_erlaubt(stamm, kopf):
                ja += 1
            else:
                g = _grund(p, schluessel, stamm, erlaubt)
                gruende[g] = gruende.get(g, 0) + 1
        summe_ja += ja
        if ja:
            sehend += 1
        else:
            blind += 1

    paare = len(zugaenge) * len(lieferbar)
    print("Paare (Zugang x Dokument): %d" % paare)
    print("  darf oeffnen : %6d  (%.1f %%)"
          % (summe_ja, 100.0 * summe_ja / paare))
    print("  gesperrt     : %6d" % (paare - summe_ja))
    print()
    print("Zugaenge, die GAR NICHTS oeffnen duerfen: %d von %d"
          % (blind, len(zugaenge)))
    print("Zugaenge mit mindestens einem Dokument  : %d" % sehend)
    print("davon mit LEERER gemerkter Liste        : %d" % leere_listen)
    print()
    print("Gruende der Sperren:")
    for g in sorted(gruende, key=lambda x: -gruende[x]):
        print("  %-24s %6d" % (g, gruende[g]))

    # ⛔ DIE GEGENPROBE. Ohne sie sagt jede Zahl oben nichts: Sie waere auch
    #   dann zu lesen, wenn die Probe gar nicht messen KANN, was sie behauptet
    #   - etwa weil die gebaute Marke ungueltig ist und alles pauschal
    #   durchfaellt. Zwei kuenstliche Faelle, deren Ausgang feststeht:
    probe = "zz-probe-dieses-dokument-gibt-es-nicht"
    # \u26a0 Der Pruefling muss KI-freigegeben sein, sonst sperrt schon das
    #   erste Tor und die Gegenprobe erklaerte die Messung grundlos fuer
    #   ungueltig - ein Fehlalarm ist so teuer wie ein uebersehener Fehler.
    pruefling = next((x for x in lieferbar if p.fuer_ki_freigegeben(x)), None)
    if pruefling is None:
        print("Kein einziges lieferbares Dokument ist KI-freigegeben - "
              "DIE MESSUNG IST UNGUELTIG")
        return 1
    # \u26a0 Genau so abgelegt, wie erlaubte_dokumente() es ablegt: Endung
    #   weg, kleingeschrieben. Eine andere Schreibweise pruefte einen Weg,
    #   den es im Betrieb nicht gibt.
    wie_gemerkt = p.re.sub(r"\.(md|pdf|docx?|xlsx?)$", "", pruefling,
                           flags=p.re.I).strip().lower()
    p._DOKZUGANG["zzprobeblind"] = (set(), p.time.time())
    p._DOKZUGANG["zzprobesehend"] = ({wie_gemerkt}, p.time.time())
    try:
        muss_nein = p.dokument_erlaubt(pruefling, _kopf(p, "zzprobeblind"))
        muss_ja = p.dokument_erlaubt(pruefling, _kopf(p, "zzprobesehend"))
        unbekannt = p.dokument_erlaubt(probe, _kopf(p, "zzprobesehend"))
    finally:
        p._DOKZUGANG.pop("zzprobeblind", None)
        p._DOKZUGANG.pop("zzprobesehend", None)

    print()
    if muss_nein is False and muss_ja is True and unbekannt is False:
        print("Messung gueltig: leere Liste sperrt, passende Liste oeffnet, "
              "unbekannter Name sperrt - die Probe kann rot UND gruen.")
    else:
        print("⛔ DIE MESSUNG IST UNGUELTIG: leere Liste -> %s (erwartet "
              "False), passende Liste -> %s (erwartet True), unbekannter "
              "Name -> %s (erwartet False). Die Zahlen oben sagen nichts."
              % (muss_nein, muss_ja, unbekannt))
        return 1

    if summe_ja == 0:
        print()
        print("⛔ KEIN einziges Paar darf oeffnen - genau das Bild, das der "
              "Nutzer sieht: jeder Beleg endet auf 'liegt nicht vor'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
