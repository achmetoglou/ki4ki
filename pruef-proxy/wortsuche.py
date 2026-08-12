#!/usr/bin/env python3
"""Woertliche Suche neben der Aehnlichkeitssuche.

⛔ DER ANLASS - an einer echten Nutzerfrage gemessen:

    "Was ist Mastizieren?"   ->  100 Textstellen geliefert, 0 mit dem Wort
    "Mastizieren"            ->  100 Textstellen geliefert, 2 mit dem Wort
                                 (Platz 10 und 18)
    "Mastizieren Kautschuk"  ->  100 Textstellen geliefert, 0 mit dem Wort

Das Wort steht in VIER Arbeiten, eine davon (S-12-004.x) hat eine eigene
Ueberschrift "3.1.1 Mastizieren". Die Anlage antwortete "Dazu finde ich in
den vorliegenden Unterlagen keine belastbare Information" - und das war
nicht gelogen: Das Modell hat das Wort nie gesehen.

WARUM: Gesucht wird rein bedeutungsaehnlich. Fuer das Suchmodell liegen
"Mastizieren" und "Plastifizieren" fast aufeinander. Die Bewertungen aller
100 Stellen lagen in einem Band von 0,078 - die Suche unterscheidet nicht.
Bei SELTENEN Fachbegriffen ist das am schlimmsten: Genau die Woerter, die
eine Frage eindeutig machen, haben im Bedeutungsraum am wenigsten Halt.

  Fuer den Nutzer heisst das: Selbst auf die einfachsten Fragen kommt eine
  unguenstige Antwort - und bei komplizierteren Fachfragen wird es nicht
  besser.

WAS DIESES MODUL TUT: Es zieht aus der Frage die auffaelligen Fachwoerter
und sucht sie WOERTLICH im Bestand - dieselbe Maschinerie, mit der der
Pruef-Proxy ohnehin jedes Zitat gegen das Original prueft.

⚠ NUR BEI SELTENEN WOERTERN. Kommt ein Wort in vielen Arbeiten vor, ist es
  kein Unterscheidungsmerkmal, und die Aehnlichkeitssuche ist ohnehin
  besser. Die woertliche Suche ergaenzt sie, sie ersetzt sie nicht.

⚠ INHALTSVERZEICHNISSE WERDEN UEBERSPRUNGEN. Ein Wort in einem
  Verzeichnis belegt nichts - es sagt nur, dass es weiter hinten vorkommt.
  Dokument._ist_verzeichnis() erkennt sie.
"""
import os
import re
import unicodedata

# ⛔ NICHT die Faltungsregel hier nachbauen. Genau daran ist die woertliche
#   Suche gescheitert: Es gab zwei Regeln, sie liefen auseinander, und
#   niemand hat es gemerkt. Siehe _suchformen().
import veredeln

# Woerter, die nichts unterscheiden. Bewusst knapp gehalten: Was hier
# faelschlich drinsteht, wird nie woertlich gesucht.
HAEUFIG = set("""
der die das dem den des ein eine einen einer eines und oder aber wenn dann
ist sind war waren wird werden wurde wurden kann koennen könnte muss muessen
müssen soll sollen hat haben hatte hatten sich nicht auch noch nur schon
sehr mehr viel viele alle beim beim beim durch fuer für mit von vom zum zur
bei auf aus als wie was wer wo wann warum wieso weshalb welche welcher
welches welchen welchem ob dass man sie ihr ihre ihren wir uns euch
diese dieser dieses diesem diesen jene jener jenes solche solcher
bitte danke okay fasse fasst zusammen zusammenfassung erklaere erklaer
erklaeren erkläre erklären nenne nennen gib gibt sag sage sagen zeige
zeigen wichtigsten wichtige wichtig sachen dinge punkte thema themen
information informationen unterlagen dokument dokumente arbeit arbeiten
steht stehen ueber über
""".split())

# Zu kurze Woerter sind fast nie Fachbegriffe - und ein kurzes Wort kommt
# ueberall vor, die woertliche Suche liefert dann Rauschen.
MINDESTLAENGE = 6


def _falte(s):
    """Wie veredeln._falte: Kleinschreibung ohne Zeichensetzung.

    ⚠ Hier bewusst nur fuer den VERGLEICH von Woertern - die Positionssuche
      im Dokument macht weiterhin veredeln, mit seinem eigenen Zeiger.
    """
    n = unicodedata.normalize("NFKD", s or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()


def _suchformen(wort):
    """Alle Schreibweisen, unter denen ein Wort im Dokumentindex stehen kann.

    ⛔ DER ANLASS: ZWEI UNVERTRAEGLICHE FALTUNGEN.

      veredeln._falte() baut den Suchindex des Dokuments (dok.norm) und
      BEHAELT ae/oe/ue/ss - sie stehen dort ausdruecklich in einer
      Ausnahmeliste. _falte() hier macht ss->ss und wirft die Umlaute weg.
      dok.alle_woertlich() sucht aber IM veredeln-Index.

      Gemessen an einem Blatt, das die Woerter nachweislich enthaelt:

        Wort              gesucht als          gefunden
        Massnahmen        'massnahmen'         2 Stellen
        Massnahmen        'maßnahmen'          5 Stellen
        Oberflaeche       'oberflache'         0 Stellen
        Oberflaeche       'oberfläche'         1 Stelle

      Wer nur eine Form sucht, verliert die andere Schreibweise
      VOLLSTAENDIG. Bei Woertern, die nur mit ss oder Umlaut vorkommen,
      findet die woertliche Suche gar nichts - lautlos.

    ⚠ Warum hier veredeln._nur_falten() aufgerufen wird, statt die Regel
      abzuschreiben: Eine abgeschriebene Regel laeuft irgendwann wieder
      auseinander, und dieser Fehler war von aussen nicht zu sehen.
    """
    formen = []
    for f in (_falte(wort), veredeln._nur_falten(wort)):
        if f and f not in formen:
            formen.append(f)
    return formen


def _stellen(dok, wort, hoechstens):
    """Woertliche Stellen unter ALLEN Schreibweisen, nach Position sortiert.

    Dieselbe Stelle kann ueber zwei Formen kommen - dann zaehlt sie einmal.
    """
    alle = []
    for form in _suchformen(wort):
        try:
            alle.extend(dok.alle_woertlich(form, hoechstens=hoechstens))
        except Exception:
            pass          # eine kaputte Form darf die andere nicht mitreissen
    gesehen, raus = set(), []
    for a, e in sorted(alle):
        if a in gesehen:
            continue
        gesehen.add(a)
        raus.append((a, e))
    return raus[:hoechstens]


TITEL_MINDESTLAENGE = 6


def _titel_passt(titel, wort):
    """Traegt der Dateiname des Dokuments dieses Fachwort?

    ⚠ REINE GLEICHHEIT VERLIERT IM DEUTSCHEN SYSTEMATISCH. Die Frage beugt
      ("Kunststoffen"), der Titel traegt die Grundform ("Kunststoffe").
      Deshalb Wort fuer Wort und mit gemeinsamem Anfang - sechs Zeichen
      sind lang genug, um kein Zufall zu sein.

    ⚠ Beide Schreibweisen, aus demselben Grund wie in _suchformen().
    """
    if not titel:
        return False
    teile = set()
    for gefaltet in (_falte(titel), veredeln._nur_falten(titel)):
        teile.update(w for w in gefaltet.split()
                     if len(w) >= TITEL_MINDESTLAENGE)
    if not teile:
        return False
    for form in _suchformen(wort):
        if len(form) < TITEL_MINDESTLAENGE:
            continue
        for teil in teile:
            if teil.startswith(form) or form.startswith(teil):
                return True
    return False


def _groesse(bestand, titel):
    """Wie gross ist das Dokument - ohne es zu laden.

    ⚠ Greift auf bestand._pfade zu. Das ist bewusst: Die Alternative waere,
      das Dokument zu OEFFNEN, um zu entscheiden, ob es sich zu oeffnen
      lohnt. Faellt der Zugriff weg, wird nach Groesse eben nicht mehr
      sortiert - dann bleibt der Titeltreffer als Kriterium, und die Suche
      ist nicht schlechter als vor dieser Aenderung.
    """
    if not titel:
        return float("inf")
    try:
        return os.path.getsize(bestand._pfade[titel])
    except Exception:
        return float("inf")


def auffaellige_woerter(frage, hoechstens=4):
    """Die Fachwoerter einer Frage - lang, selten, gross geschrieben.

    Grossschreibung mitten im Satz ist im Deutschen ein starkes Signal fuer
    ein Substantiv; ein langes Substantiv ist meist der Fachbegriff.
    """
    if not frage:
        return []
    # Bindestrichwoerter zusammenhalten: "Laser-Durchstrahlschweissen"
    roh = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\-]{2,}", frage)
    kandidaten = []
    for w in roh:
        k = w.strip("-")
        if len(k) < MINDESTLAENGE:
            continue
        if _falte(k) in HAEUFIG:
            continue
        # Gross geschrieben ODER auffaellig lang
        if k[:1].isupper() or len(k) >= 9:
            kandidaten.append(k)
    # Reihenfolge erhalten, Doppelte raus
    gesehen, raus = set(), []
    for k in kandidaten:
        s = _falte(k)
        if s in gesehen:
            continue
        gesehen.add(s)
        raus.append(k)
    return raus[:hoechstens]


def finde(bestand, wort, hoechstens_arbeiten=6, je_arbeit=2, umfeld=700,
          zu_haeufig_ab=40, melden=None):
    """Woertliche Fundstellen zu einem Wort.

    Liefert (liste, arbeiten) - liste aus dicts mit titel, seite, text.
    `arbeiten` ist die Zahl der Arbeiten, in denen das Wort vorkommt; ist
    sie groesser als zu_haeufig_ab, wird eine leere Liste geliefert: Das
    Wort unterscheidet dann nichts.

    ⚠ Der Bestand haelt nur wenige Dokumente gleichzeitig geladen
      (hoechstens_geladen=60). Ueber ALLE 1253 zu gehen laedt sie
      nacheinander - das kostet Zeit. Deshalb wird zuerst im schon
      geladenen Bestand gesucht und der Rest nur bis zur Obergrenze.
    """
    nz = _falte(wort)
    if not nz:
        return [], 0

    gefunden = []
    arbeiten = 0
    for titel in bestand.titel():
        dok = bestand.hol(titel)
        if dok is None:
            continue
        stellen = _stellen(dok, wort, je_arbeit + 3)
        if not stellen:
            continue
        arbeiten += 1
        if arbeiten > zu_haeufig_ab:
            if melden:
                melden("%r kommt in mehr als %d Arbeiten vor - kein "
                       "Unterscheidungsmerkmal" % (wort, zu_haeufig_ab))
            return [], arbeiten
        if len(gefunden) >= hoechstens_arbeiten * je_arbeit:
            continue
        genommen = 0
        for a, e in stellen:
            if genommen >= je_arbeit:
                break
            # Ein Wort im Inhaltsverzeichnis belegt nichts.
            try:
                if dok._ist_verzeichnis(a):
                    continue
            except Exception:
                pass
            von = max(0, a - umfeld // 3)
            bis = min(len(dok.text), e + umfeld)
            gefunden.append({
                "titel": titel,
                "seite": dok.seite_bei(a),
                "text": dok.wortlaut(von, bis),
            })
            genommen += 1
    return gefunden, arbeiten


def block(treffer, wort):
    """Die Fundstellen als Textblock fuer das Sprachmodell."""
    if not treffer:
        return ""
    zeilen = ["WOERTLICHE FUNDSTELLEN zu „%s“ "
              "(im Volltext der Arbeiten gefunden, nicht ueber die "
              "Aehnlichkeitssuche):" % wort]
    for t in treffer:
        ort = t["titel"]
        if t.get("seite"):
            ort += ", Seite %s" % t["seite"]
        zeilen.append("[%s] %s" % (ort, t["text"]))
    return "\n\n".join(zeilen)


# --------------------------------------------------------- ueber das Verzeichnis

def ueber_verzeichnis(bestand, wort, je_arbeit=2, umfeld=700,
                      hoechstens_arbeiten=5, melden=None, erlaubt=None):
    """Woertliche Fundstellen - aber nur in den Arbeiten, die das Wort haben.

    ⚠ DAS IST DER UNTERSCHIED ZWISCHEN 158 SEKUNDEN UND 23 MILLISEKUNDEN.
      finde() geht alle 1.253 Arbeiten durch und laedt sie dabei nacheinander.
      Hier fragt erst das Verzeichnis, WELCHE Arbeiten das Wort enthalten -
      dann werden nur diese wenigen geladen.

    Liefert (liste, arbeiten). arbeiten=None heisst: Das Verzeichnis konnte
    keine Auskunft geben (fehlt oder ist veraltet) - dann wird NICHT
    stillschweigend die langsame Suche genommen, sondern nichts geliefert.
    Ein Frageweg darf nicht ploetzlich zweieinhalb Minuten dauern.
    """
    try:
        import wortverzeichnis
    except Exception:
        return [], None

    namen = wortverzeichnis.arbeiten_mit(wort)
    if namen is None:
        if melden:
            melden("Wortverzeichnis nicht verfuegbar - keine woertliche Suche")
        return [], None
    # ⛔ RECHTE-FILTER: Nur in den Arbeiten suchen, die diese Anmeldung
    #   sehen darf. Ohne den Filter legte die woertliche Suche Zitate aus
    #   JEDEM Dokument bei - der Nutzer bekam Woertliches aus Arbeiten, die
    #   er im Bereich gar nicht sehen kann. erlaubt(name)->bool kommt vom
    #   Proxy aus der Chat-Sitzung; ohne Filter (None) bleibt alles beim
    #   Alten (z.B. fuer eigene Werkzeuge ohne Anmeldung).
    if erlaubt is not None:
        vorher = len(namen)
        namen = [n for n in namen if erlaubt(n)]
        if melden and len(namen) != vorher:
            melden("Recht: %d von %d Arbeiten bleiben fuer %r"
                   % (len(namen), vorher, wort))
    if not namen:
        return [], 0
    if not _suchformen(wort):
        return [], len(namen)

    # Die Titel im Verzeichnis sind Stammnamen ("DS-00-000"), der Bestand
    # kennt sie mit Endung ("DS-00-000.md"). Beides zusammenbringen.
    alle = {t: t for t in bestand.titel()}
    stamm = {}
    for t in alle:
        stamm.setdefault(t.rsplit(".", 1)[0], t)

    # ⭐ RANGFOLGE STATT SCHWELLE
    #
    # ⛔ DER ANLASS, an einer echten Frage gemessen: Auf
    #   "Welche Schutzmassnahmen sind beim Umgang mit Kunststoffen zu
    #   beachten?" antwortete die Anlage mit einer Absage - und BEGRUENDETE
    #   sie selbst:
    #
    #     "Die im Kontext enthaltenen Fundstellen zum Begriff 'Umgang'
    #      beziehen sich ausschliesslich auf den Umgang mit
    #      Produktanforderungen, der Umwelt oder Daten in Projekten."
    #
    #   Beigelegt wurde das FALSCHE Wort. "Schutzmassnahmen" steht in 57
    #   Arbeiten und fiel an der Schwelle (hoechstens_arbeiten * 4 = 20)
    #   heraus; "Umgang" mit 20 Arbeiten kam durch - und steht im
    #   Zieldokument gar nicht. Das Blatt heisst "Schutzmassnahmen_SKZ".
    #
    # ⚠ DIE SCHWELLE WAR NIE DAS PROBLEM, DIE REIHENFOLGE WAR ES.
    #   Geladen werden ohnehin nur hoechstens_arbeiten (5) Werke - aber
    #   bisher die ERSTEN FUENF IN DATEIREIHENFOLGE. Von 57 passenden
    #   Arbeiten waren das fuenf beliebige; das richtige Blatt hatte eine
    #   Chance von etwa 1:11. Die Ladearbeit bleibt gleich, nur die
    #   Auswahl wird begruendet:
    #
    #     1. Traegt der DATEINAME das Fragewort? Dann hat jemand das
    #        Dokument danach benannt - das staerkste Signal, das es gibt.
    #     2. Sonst das kleinere Dokument zuerst. Ein einseitiges Blatt zum
    #        Thema schlaegt ein 524-Seiten-Handbuch, das es streift.
    mit_titel = [n for n in namen if _titel_passt(n, wort)]

    # ⚠ Ein Titeltreffer hebt die Haeufigkeitsschwelle auf. Ein Wort, das
    #   in 57 Arbeiten steht, unterscheidet als Volltext-Treffer wenig -
    #   als NAME eines Dokuments unterscheidet es sehr wohl.
    if len(namen) > hoechstens_arbeiten * 4 and not mit_titel:
        if melden:
            melden("%r steht in %d Arbeiten und in keinem Titel - "
                   "unterscheidet nichts" % (wort, len(namen)))
        return [], len(namen)

    def _rang(name):
        return (0 if name in set(mit_titel) else 1,
                _groesse(bestand, alle.get(name) or stamm.get(name)))

    namen = sorted(namen, key=_rang)
    if melden and mit_titel:
        melden("Titeltreffer fuer %r: %s" % (wort, mit_titel[:4]))

    gefunden = []
    for name in namen[:hoechstens_arbeiten]:
        titel = alle.get(name) or stamm.get(name)
        if not titel:
            continue
        dok = bestand.hol(titel)
        if dok is None:
            continue
        genommen = 0
        for a, e in _stellen(dok, wort, je_arbeit + 4):
            if genommen >= je_arbeit:
                break
            try:
                if dok._ist_verzeichnis(a):
                    continue      # ein Wort im Inhaltsverzeichnis belegt nichts
            except Exception:
                pass
            von = max(0, a - umfeld // 3)
            bis = min(len(dok.text), e + umfeld)
            gefunden.append({"titel": titel, "seite": dok.seite_bei(a),
                             "text": dok.wortlaut(von, bis)})
            genommen += 1
    return gefunden, len(namen)


# ⛔ HARTE OBERGRENZE FUER DEN BEIGELEGTEN BLOCK
#
# Der Block wird an d["message"] angehaengt. Das hat drei Folgen, die
# alle erst gemessen wurden, als jemand hinsah:
#
#   1. Er steht SICHTBAR im Chatverlauf des Nutzers. Aus einer Frage von
#      70 Zeichen ("Wie werden Druckspeicher ... ausgelegt?") wird dort
#      "... WOERTLICHE FUNDSTELLEN zu 'Faserwickelverfahren' ..." -
#      11.200 Zeichen Maschinerie.
#   2. AnythingLLM baut aus message AUCH den Suchvektor. Gemessen: der
#      Block verdraengte im grossen Bereich 18 von 23 Werken aus den
#      Fundstellen. Er zieht die Suche auf die Werke zu, die er selbst
#      mitbringt.
#   3. Er kostet rund 3.000 der 23.000-37.000 Prompt-Token je Frage - und
#      das Lesen des Prompts ist hier der Flaschenhals, nicht das
#      Schreiben der Antwort.
#
# ⚠ Der Block bleibt trotzdem, denn er wirkt: Ohne ihn taucht
#   Schutzmassnahmen_SKZ nicht unter den Fundstellen auf, mit ihm schon.
#   Begrenzt wird die MENGE, nicht die Sache. Die Rangfolge in
#   ueber_verzeichnis() sortiert das Wichtigste nach vorn - abgeschnitten
#   wird also hinten, wo das Schwaechste steht.
HOECHSTENS_ZEICHEN = 2500
UMFELD_KNAPP = 320


def zusatz_zur_frage(bestand, frage, hoechstens_woerter=2,
                     hoechstens_zeichen=HOECHSTENS_ZEICHEN, melden=None,
                     erlaubt=None):
    """Der Textblock, der einer Frage beigelegt wird - oder "".

    Genau hier wird die Luecke der Aehnlichkeitssuche geschlossen: Sie
    verwechselt seltene Fachbegriffe mit ihren haeufigen Nachbarn
    ("Mastizieren" mit "Plastifizieren"). Gemessen: Von 100
    gelieferten Textstellen enthielt KEINE das gesuchte Wort.
    """
    woerter = auffaellige_woerter(frage, hoechstens=hoechstens_woerter + 2)
    bloecke = []
    for w in woerter:
        if len(bloecke) >= hoechstens_woerter:
            break
        treffer, arbeiten = ueber_verzeichnis(bestand, w, umfeld=UMFELD_KNAPP,
                                              melden=melden, erlaubt=erlaubt)
        if not treffer:
            continue
        if melden:
            melden("woertlich: %r in %d Arbeiten, %d Stellen beigelegt"
                   % (w, arbeiten, len(treffer)))
        bloecke.append(block(treffer, w))

    ganz = "\n\n".join(bloecke)
    if len(ganz) <= hoechstens_zeichen:
        return ganz
    # ⚠ An einer Absatzgrenze schneiden, nicht mitten im Satz - ein halbes
    #   Zitat im Kontext ist schlimmer als eines weniger.
    schnitt = ganz.rfind("\n\n", 0, hoechstens_zeichen)
    if schnitt < hoechstens_zeichen // 2:
        schnitt = hoechstens_zeichen
    gekuerzt = ganz[:schnitt].rstrip()
    if melden:
        melden("Block gekuerzt: %d -> %d Zeichen" % (len(ganz), len(gekuerzt)))
    return gekuerzt
