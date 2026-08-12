#!/usr/bin/env python3
"""
Veredelung der Antworten aus der Wissensdatenbank.

Das Sprachmodell glaettet beim Zitieren - es laesst ein Wort weg, dreht einen
Buchstaben um, ersetzt einen Satzanfang. Und es ignoriert die Anweisung, die
Seitenzahl zu nennen, auch wenn die Marke [Seite N] direkt im Kontext steht.
Beides laesst sich nicht zuverlaessig ueber den Arbeitsauftrag loesen.

Also nachtraeglich, mit festen Regeln statt mit Zureden:

  1. Jedes Beleg-Zitat wird im Quelldokument nachgeschlagen.
  2. Weicht es ab, wird der ORIGINAL-Wortlaut eingesetzt.
  3. Die Fundstelle wird um Dokumentname und Seitenzahl ergaenzt.
  4. Findet sich ein Zitat oder ein Teil davon nicht, wird das GEKENNZEICHNET.

Grundlage ist der Text, den AnythingLLM selbst gespeichert hat - also genau
das, was das Modell zu sehen bekam.

Leitsatz fuer jede Entscheidung in dieser Datei: **Eine falsche Quellenangabe
ist schlimmer als gar keine.** Im Zweifel wird die Seite weggelassen, das
Zitat als ungeprueft markiert oder weitergesucht - nie geraten.
"""
import difflib
import glob
import json
import os
import pickle
import re
import time
import unicodedata
from array import array

BESTAND = (os.environ.get("KI4KI_BESTAND")
           or os.path.expanduser("~/ki4ki/anythingllm/storage/documents"))

# ab dieser Aehnlichkeit gilt eine Textstelle als dieselbe, nur geglaettet
SCHWELLE = 0.82
# Zitate unter dieser Laenge sind zu unspezifisch fuer eine sichere Zuordnung
MIN_LAENGE = 25
# Sekunden, die die Suche im ganzen Bestand hoechstens dauern darf
BUDGET = 8.0
# so viele Dokumente kommen aus der Vorauswahl hoechstens in die teure Pruefung
VORAUSWAHL = 80

_ERSATZ = {
    "­": "", "–": "-", "—": "-", "‐": "-", "‑": "-",
    "„": '"', "“": '"', "”": '"', "«": '"', "»": '"',
    "’": "'", "‘": "'", "′": "'", " ": " ", " ": " ",
    " ": " ", "​": "", "﻿": "",
}

_SEITENMARKE = re.compile(r"\[Seite \d+\]")

# Haken, um die Seitenzahl gegen das ORIGINAL-PDF zu pruefen.
# Doclings Marken [Seite N] sind eine Schaetzung: an 12 Arbeiten gemessen
# stimmten 7, zwei lagen eine Seite daneben, drei zwei Seiten. Wer den Haken
# setzt, bekommt die echte Seite; ohne Haken bleibt es bei der Marke.
# Aufruf: SEITENPRUEFER(dokumentname, vermutete_seite, zitat) -> Seite|None
SEITENPRUEFER = None

# Spuren einer misslungenen Formelerkennung. Formeln sind in wissenschaft-
# lichen Arbeiten der Kern der Aussage - wenn sie nicht sauber ausgelesen
# wurden, darf die Anlage nicht so tun, als haette sie sie gelesen. Dann
# gehoert ein ehrlicher Hinweis dazu und der Verweis ins PDF.
_FORMEL_KAPUTT = re.compile(
    r"(?:\\(?:quad|cdots|ldots|,|;)\s*){6,}"      # Wiederholungsschleife
    r"|(?:[A-Za-zÄÖÜäöü] ){10,}"                     # Buchstaben einzeln getrennt
    r"|\.notdef"                                     # fehlende Schriftzeichen
    r"|(?:g\d{1,3}){3,}")                            # Glyph-Nummern statt Text

# So weit um die Fundstelle herum wird nach Formelschaden gesehen.
# An 900 Zeichen gemessen: Von zufaelligen, sauberen Zitaten schlug KEIN
# einziges faelschlich an, waehrend die Trefferquote bei echtem Schaden
# steigt. Ein Fehlalarm waere teuer - er wuerde eine saubere Formel in
# Zweifel ziehen.
_UMFELD = 900


def _falte(text, mit_zeiger=True):
    """Normalisierte Fassung, wahlweise mit Rueckverweis aufs Original.

    Mit Zeiger gilt len(norm) == len(zeiger); zeiger[i] ist die Position des
    i-ten normalisierten Zeichens im Originaltext. Damit laesst sich jede
    Fundstelle wieder auf den echten Wortlaut abbilden.

    Wichtig:
    - Erst nach NFC vereinheitlichen. Sonst faellt ein Dokument in Zerlegungs-
      form (u + Trema) gegen ein Zitat in Kompositionsform (ü) komplett durch.
    - Seitenmarken [Seite 42] fliegen raus. Sie stehen mitten im Text und
      wuerden sonst im eingesetzten Zitat auftauchen und die Aehnlichkeit
      druecken - ein woertliches Zitat ueber eine Seitengrenze wuerde
      faelschlich als "berichtigt" gelten.
    """
    text = unicodedata.normalize("NFC", text)
    marken = _SEITENMARKE.finditer(text) if "[Seite " in text else iter(())
    verboten = set()
    for m in marken:
        verboten.update(range(m.start(), m.end()))

    norm = []
    zeiger = array("i") if mit_zeiger else None
    leer_offen = True   # verhindert fuehrende Leerzeichen
    for i, z in enumerate(text):
        if i in verboten:
            continue
        z = _ERSATZ.get(z, z)
        if z == "":
            continue
        if z.isspace():
            if leer_offen:
                continue
            norm.append(" ")
            if zeiger is not None:
                zeiger.append(i)
            leer_offen = True
            continue
        leer_offen = False
        z = z.lower()
        # Umlaute bleiben, sonstige Akzente fallen weg.
        # (lower() kann ein Zeichen verdoppeln - dann nichts weiter anfassen.)
        if len(z) == 1 and z not in "äöüß" and unicodedata.combining(z) == 0:
            zerlegt = unicodedata.normalize("NFD", z)
            z = "".join(c for c in zerlegt if unicodedata.combining(c) == 0) or z
        if zeiger is not None:
            for _ in z:
                zeiger.append(i)
        norm.append(z)
    fertig = "".join(norm)
    return (fertig, zeiger) if mit_zeiger else fertig


def _nur_falten(text):
    return _falte(text, mit_zeiger=False)


class Dokument:
    """Ein Quelldokument mit Suchindex und Seitenzuordnung."""

    def __init__(self, titel, text):
        self.titel = titel
        self.text = unicodedata.normalize("NFC", text)
        self.norm, self.zeiger = _falte(self.text)
        # Seitenmarken: Position im Original -> Seitenzahl.
        # Die Marke steht VOR dem Inhalt der Seite (so baut mk_md.py sie ein),
        # deshalb ist "letzte Marke vor der Fundstelle" die richtige Seite.
        self.marken = [(m.start(), int(m.group(1)))
                       for m in re.finditer(r"\[Seite (\d+)\]", self.text)]

    def seite_bei(self, pos):
        """Seitenzahl der letzten Marke vor pos, sonst None."""
        seite = None
        for p, n in self.marken:
            if p > pos:
                break
            seite = n
        return seite

    def _ist_verzeichnis(self, pos):
        """Steht die Fundstelle in einem Inhaltsverzeichnis?

        Erkennungsmerkmal sind Punktfuehrungen und Seitenzahlen am Zeilenende
        in der naeheren Umgebung. Nur eine Heuristik - deshalb entscheidet sie
        nie allein, sondern bevorzugt nur die Fliesstext-Fundstelle.
        """
        umfeld = self.text[max(0, pos - 300):pos + 300]
        if re.search(r"\.{4,}\s*\d", umfeld):
            return True
        # Literatur- und Schriftenreihenlisten. Sie sehen anders aus als ein
        # Inhaltsverzeichnis - keine Punktfuehrung, keine Seitenzahl am
        # Zeilenende - und wurden deshalb frueher fuer Fliesstext
        # gehalten:
        #     Bd. 149: Mustermann, T. <Titel> 1. Auflage 2004, 188 Seiten
        #     ISBN 3-86130-488-0
        # Ein Werktitel steht in solchen Listen in zwanzig anderen Arbeiten.
        # Als Fundort taugt das nicht: Dort steht ein VERWEIS auf die Arbeit,
        # nicht ihr Inhalt.
        if re.search(r"ISBN\s*[\d-]{9,}", umfeld):
            return True
        if re.search(r"\bBd\.\s*\d{1,4}\s*:", umfeld):
            return True
        if re.search(r"\d\.\s*Auflage\s+\d{4}", umfeld):
            return True
        zeilen = umfeld.splitlines()
        kurz = sum(1 for z in zeilen if 0 < len(z.strip()) < 70
                   and re.search(r"\s\d{1,3}\s*$", z))
        return kurz >= 3

    def alle_woertlich(self, nz, hoechstens=25):
        """Alle woertlichen Vorkommen als Positionen im Originaltext."""
        stellen, von = [], 0
        while len(stellen) < hoechstens:
            p = self.norm.find(nz, von)
            if p < 0:
                break
            stellen.append((self.zeiger[p], self.zeiger[p + len(nz) - 1] + 1))
            von = p + 1
        return stellen

    def _anker(self, woerter):
        """Kandidatenstellen ueber Wortfolgen, die woertlich vorkommen.

        Billiger Vorfilter: wo keine einzige Vierwortfolge des Zitats steht,
        muss gar nicht erst verglichen werden.
        """
        kandidaten = set()
        schritt = max(1, len(woerter) // 12)
        for i in range(0, max(1, len(woerter) - 3), schritt):
            nadel = " ".join(woerter[i:i + 4])
            vorlauf = len(" ".join(woerter[:i]))
            von, gefunden = 0, 0
            while gefunden < 25:
                p = self.norm.find(nadel, von)
                if p < 0:
                    break
                kandidaten.add(max(0, p - vorlauf - 15))
                von = p + 1
                gefunden += 1
        return kandidaten

    def suche(self, nz):
        """Findet nz (normalisiert) im Dokument.

        Liefert (guete, start, ende, mehrdeutig) mit Positionen im
        ORIGINALTEXT, oder None. guete 1.0 = woertlich.

        `mehrdeutig` heisst: die Stelle kommt mehrfach auf VERSCHIEDENEN
        Seiten vor - dann wird spaeter keine Seitenzahl genannt.

        Gemessen wird gegen die FUNDSTELLE, nicht gegen das Suchfenster:
        ein Fenster muss breiter sein als das Zitat, sonst findet man den
        Rand nicht - und genau diese Zugabe wuerde die Bewertung
        faelschlich druecken.
        """
        stellen = self.alle_woertlich(nz)
        if stellen:
            # Kapitelueberschriften stehen im Inhaltsverzeichnis UND im Text.
            # Das erste Vorkommen ist fast immer das Verzeichnis - und damit
            # die falsche Seite. Also Fliesstext bevorzugen.
            fliess = [s for s in stellen if not self._ist_verzeichnis(s[0])]
            gewaehlt = fliess or stellen
            seiten = {self.seite_bei(a) for a, _ in gewaehlt}
            a, e = gewaehlt[0]
            return 1.0, a, e, len(seiten) > 1

        woerter = nz.split()
        if len(woerter) < 4:
            return None
        kandidaten = self._anker(woerter)
        if not kandidaten:
            return None

        breite = int(len(nz) * 1.4) + 60
        beste = None
        for start in sorted(kandidaten):
            fenster = self.norm[start:start + breite]
            if len(fenster) < len(nz) * 0.6:
                continue
            v = difflib.SequenceMatcher(None, nz, fenster, autojunk=False)
            bloecke = [b for b in v.get_matching_blocks() if b.size > 0]
            if not bloecke:
                continue
            treffer = sum(b.size for b in bloecke)
            a, e = bloecke[0].b, bloecke[-1].b + bloecke[-1].size
            spanne = e - a
            if spanne <= 0:
                continue
            # Anteil des Zitats, der in der Fundstelle wirklich steht
            g = 2.0 * treffer / (len(nz) + spanne)
            if g < SCHWELLE or (beste and g <= beste[0]):
                continue
            beste = (g, start + a, min(start + e, len(self.norm)))
        if not beste:
            return None
        g, a, e = beste
        return (g, self.zeiger[a], self.zeiger[min(e, len(self.zeiger)) - 1] + 1,
                False)

    def formel_beschaedigt(self, a, e):
        """Steht rund um die Fundstelle eine misslungene Formel?"""
        umfeld = self.text[max(0, a - _UMFELD):e + _UMFELD]
        return bool(_FORMEL_KAPUTT.search(umfeld))

    def wortlaut(self, a, e):
        """Der echte Text der Fundstelle, ohne Seitenmarken."""
        roh = _SEITENMARKE.sub(" ", self.text[a:e])
        return re.sub(r"\s+", " ", roh).strip()


class Bestand:
    """Laedt Quelldokumente bei Bedarf und haelt sie vor."""

    def __init__(self, ordner=BESTAND, hoechstens_geladen=60, speicher=None):
        self.ordner = ordner
        self.abbrueche = 0        # wie oft die Zeitgrenze gegriffen hat
        self.doppelte = []        # Dateinamen, die auf denselben Titel fielen
        self.speicher = (speicher if speicher is not None
                         else os.environ.get("KI4KI_ZWISCHENSPEICHER")
                         or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         ".vorauswahl.pickle"))
        self._grenze = hoechstens_geladen
        self._pfade = {}
        self._reihe = []          # Ladereihenfolge, fuer das Aufraeumen
        self._geladen = {}
        self._roh = None
        # Rekursiv, weil die Dokumente je Abteilung in einem eigenen
        # Unterordner liegen (documents/<bereich-a>, documents/<bereich-b>, ...).
        # Vorher stand hier glob(ordner, "*.json") ueber eine Ebene - die
        # Abteilungsdokumente waren damit unsichtbar, und jede Antwort
        # daraus trug "Fundstelle nicht automatisch bestimmbar", obwohl
        # der Inhalt stimmte.
        gefunden = []
        for wurzel, _, dateien in os.walk(ordner):
            for d in dateien:
                if d.endswith(".json"):
                    gefunden.append(os.path.join(wurzel, d))
        for f in sorted(gefunden):
            titel = self._titel_aus(f)
            if titel in self._pfade:
                # Zwei Dateien mit gleichem Namen: die zweite waere sonst
                # unerreichbar und ihre Zitate wuerden der ersten
                # zugeschrieben. Lieber melden als still verschlucken.
                self.doppelte.append(os.path.basename(f))
                continue
            self._pfade[titel] = f

    @staticmethod
    def _titel_aus(pfad):
        """Aus '<Titel>-<UUID>.json' den Titel holen.

        Nur wenn hinten wirklich eine UUID steht - sonst bleibt der Name,
        wie er ist. Ein blindes rsplit('-', 5) wuerde aus 'Mein-Bericht-2024'
        einfach 'Mein' machen.
        """
        name = os.path.basename(pfad)
        if name.endswith(".json"):
            name = name[:-5]
        m = re.search(r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
                      r"-[0-9a-f]{4}-[0-9a-f]{12}$", name, re.I)
        return name[:m.start()] if m else name

    def titel(self):
        return sorted(self._pfade)

    def aktualisiere(self):
        """Neu hinzugekommene Dokumente nachtragen.

        Waehrend des Massenlaufs wachsen staendig Dokumente nach. Ein Dienst,
        der den Bestand nur beim Start einliest, wuerde ein frisch
        eingelesenes Werk nicht finden und ein echtes Zitat als unbelegbar
        melden. Kostet einen Verzeichnisblick je Frage.

        Liefert die Zahl der neu gefundenen Dokumente.
        """
        neue = 0
        geaendert = 0
        if not hasattr(self, "_zeiten"):
            self._zeiten = {}
        # Rekursiv, wie beim ersten Laden: Jede Abteilung hat einen eigenen
        # Unterordner (documents/<bereich-a>, documents/<bereich-b>, ...). Frueher stand
        # hier ein flaches glob - waehrend des Betriebs dazugekommene
        # Abteilungsdokumente wurden deshalb nie bemerkt.
        gefunden = []
        for wurzel, _, dateien in os.walk(self.ordner):
            for d in dateien:
                if d.endswith(".json"):
                    gefunden.append(os.path.join(wurzel, d))

        for f in sorted(gefunden):
            titel = self._titel_aus(f)
            if titel not in self._pfade:
                self._pfade[titel] = f
                self._zeiten[titel] = os.path.getmtime(f)
                neue += 1
                continue
            # Bekannt - aber vielleicht inzwischen geaendert. Ohne diese
            # Pruefung bliebe der alte Inhalt im Speicher stehen, und es
            # fehlten Belege, die in der Datei laengst stehen.
            try:
                zeit = os.path.getmtime(f)
            except OSError:
                continue
            if zeit > self._zeiten.get(titel, 0):
                self._zeiten[titel] = zeit
                self._geladen.pop(titel, None)
                if titel in self._reihe:
                    self._reihe.remove(titel)
                geaendert += 1

        if neue or geaendert:
            # Der Vorauswahl-Zwischenspeicher deckt die Aenderungen nicht ab
            # und wird beim naechsten Bedarf frisch gebaut.
            self._roh = None
        return neue

    def _kennung(self):
        """Fingerabdruck des Bestands: Anzahl und juengste Aenderung."""
        neuste = 0.0
        for pfad in self._pfade.values():
            try:
                neuste = max(neuste, os.path.getmtime(pfad))
            except OSError:
                pass
        return "%d-%.0f" % (len(self._pfade), neuste)

    def _rohtext(self):
        """Alle Quelltexte normalisiert, fuer die billige Vorauswahl.

        GENAU DIESELBE Faltung wie in der Suche - sonst wirft die Vorauswahl
        Dokumente weg, die die Suche gefunden haette (Zeilenumbruch mitten im
        Zitat, weiches Trennzeichen, typografische Anfuehrungszeichen).

        Das Falten von rund 90 MB dauert eine gute Dreiviertelminute. Das
        Ergebnis wird deshalb neben dem Bestand abgelegt und nur neu gebaut,
        wenn Dokumente dazugekommen oder geaendert worden sind - waehrend des
        Massenlaufs waechst der Bestand ja staendig.
        """
        if self._roh is not None:
            return self._roh
        kennung = self._kennung()
        if self.speicher and os.path.exists(self.speicher):
            try:
                with open(self.speicher, "rb") as fh:
                    abgelegt = pickle.load(fh)
                if abgelegt.get("kennung") == kennung:
                    self._roh = abgelegt["texte"]
                    return self._roh
            except Exception:
                pass   # kaputter Zwischenspeicher: einfach neu bauen

        self._roh = {}
        for t, pfad in self._pfade.items():
            try:
                d = json.load(open(pfad, encoding="utf-8"))
                self._roh[t] = _nur_falten(d.get("pageContent") or "")
            except Exception:
                self._roh[t] = ""
        if self.speicher:
            try:
                vorlaeufig = self.speicher + ".neu"
                with open(vorlaeufig, "wb") as fh:
                    pickle.dump({"kennung": kennung, "texte": self._roh}, fh,
                                protocol=4)
                os.replace(vorlaeufig, self.speicher)
            except Exception:
                pass   # ohne Zwischenspeicher laeuft es auch, nur langsamer
        return self._roh

    def hol(self, titel):
        if titel in self._geladen:
            return self._geladen[titel]
        pfad = self._pfade.get(titel)
        if not pfad:
            return None
        try:
            d = json.load(open(pfad, encoding="utf-8"))
            dok = Dokument(d.get("title") or titel, d.get("pageContent") or "")
        except Exception:
            dok = None
        self._geladen[titel] = dok
        self._reihe.append(titel)
        # Der Zeiger-Index kostet 4 Byte je Zeichen. Ohne Grenze liegt nach
        # kurzer Laufzeit der halbe Bestand mehrfach im Speicher - auf einer
        # Maschine, die schon einmal an zu wenig Speicher gescheitert ist.
        while len(self._reihe) > self._grenze:
            alt = self._reihe.pop(0)
            self._geladen.pop(alt, None)
        return dok

    def vorauswahl(self, nz, hoechstens=VORAUSWAHL):
        """Welche Dokumente kommen ueberhaupt in Frage?

        Gesucht werden mehrere kurze Wortfolgen des (bereits gefalteten)
        Zitats. Ein Dokument, in dem keine einzige davon steht, kann die
        Stelle nicht enthalten. Mehrere Nadeln, weil eine einzelne an einer
        Silbentrennung scheitern kann.
        """
        woerter = nz.split()
        if len(woerter) < 5:
            return []
        laenge = 5 if len(woerter) >= 12 else 4
        nadeln = []
        schritt = max(1, (len(woerter) - laenge) // 10) or 1
        for i in range(0, max(1, len(woerter) - laenge + 1), schritt):
            nadeln.append(" ".join(woerter[i:i + laenge]))
        punkte = {}
        for t, text in self._rohtext().items():
            n = sum(1 for nadel in nadeln if nadel in text)
            if n:
                punkte[t] = n
        return [t for t, _ in sorted(punkte.items(),
                                     key=lambda x: -x[1])][:hoechstens]

    def finde(self, zitat, zuerst=(), budget=BUDGET):
        """Sucht ein Zitat, bevorzugt in den genannten Dokumenten.

        Abgebrochen wird NUR bei einem woertlichen Treffer. Ein Wert von 0,95
        klingt sicher, ist es aber nicht: ein gestrichenes "nicht" oder eine
        geaenderte Ziffer kostet bei 90 Zeichen kaum 4 Prozent. Wer da
        aufhoert zu suchen, liefert die Nachbararbeit mit falscher Seite und
        umgekehrter Aussage aus.

        Liefert (dokument, guete, start, ende, mehrdeutig, mehrfach) oder None.
        `mehrfach` heisst: die Stelle steht woertlich in MEHREREN Arbeiten.
        Das ist bei Literaturverzeichnissen der Regelfall - eine Schriften-
        reihe oder Norm ist in vielen Arbeiten wortgleich abgedruckt. Eine davon
        herauszugreifen und als DIE Fundstelle auszuweisen, waere geraten.
        """
        nz = _nur_falten(zitat)
        if len(nz) < MIN_LAENGE:
            return None

        beste = None
        woertlich_in = 0
        # Alle woertlichen Treffer, nicht nur der beste: Steht die Stelle in
        # mehreren Arbeiten, sollen auch alle genannt werden - jede mit
        # ihrer eigenen Seite. Frueher blieb dann ein einziger Eintrag ohne
        # Seite uebrig, und der Beleg zeigte auf nichts.
        alle = []

        def merke(dok, tr):
            nonlocal beste, woertlich_in
            g, a, e, mehrdeutig = tr
            if g >= 0.999:
                woertlich_in += 1
                alle.append((dok, a, e, mehrdeutig))
            if not beste or g > beste[1]:
                beste = (dok, g, a, e, mehrdeutig)

        # Die genannten Quellen sind das, was das Modell wirklich gelesen hat.
        # Ein woertlicher Treffer dort ist massgeblich - kein Weitersuchen.
        genannt = list(dict.fromkeys(zuerst))
        for t in genannt:
            dok = self.hol(t)
            if not dok:
                continue
            tr = dok.suche(nz)
            if tr:
                merke(dok, tr)
                if tr[0] >= 0.999 and not tr[3]:
                    # Abgekuerzt wird, weil dies die Stelle ist, die das
                    # Modell gelesen hat - weiter zu suchen braucht es
                    # nicht. Aber: Was bis hierher gefunden wurde, ist
                    # bekannt. Frueher stand hier hart "False"; das stammte
                    # aus der Zeit, als die Abkuerzung hiess "wir haben
                    # aufgehoert, wir wissen es nicht". Der Zaehler steht
                    # daneben und weiss es sehr wohl.
                    #
                    # Ohne das blieb ein Zitat, das in der ersten Quelle
                    # mehrdeutig und in der zweiten eindeutig steht, als
                    # Einzelfundstelle ohne Seite uebrig - und damit ohne
                    # Link.
                    return beste + (woertlich_in > 1, alle)

        # Vorauswahl VOR der Uhr: sie baut beim ersten Mal den Zwischen-
        # speicher auf und wuerde das Budget sonst allein aufbrauchen.
        schon = set(genannt)
        rest = [t for t in self.vorauswahl(nz) if t not in schon]
        uhr = time.monotonic()
        for t in rest:
            if time.monotonic() - uhr > budget:
                self.abbrueche += 1
                break
            dok = self.hol(t)
            if not dok:
                continue
            tr = dok.suche(nz)
            if tr:
                merke(dok, tr)
                # Hier NICHT abbrechen: erst wenn feststeht, in wie vielen
                # Arbeiten die Stelle woertlich steht, laesst sich sagen, ob
                # eine eindeutige Fundstelle ueberhaupt existiert.
                # Frueher stand hier "> 1": Sobald die Stelle in einer
                # zweiten Arbeit auftauchte, war Schluss - man wusste nur
                # DASS sie mehrfach vorkommt, nicht wo. Jetzt werden bis zu
                # vier gesammelt; drei davon werden genannt, der Rest als
                # "u. a." zusammengefasst. Mehr zu suchen kostet Zeit, die
                # bei einem Literaturverzeichnis niemand hat.
                if woertlich_in >= 4:
                    break
        return beste + (woertlich_in > 1, alle) if beste else None


# ---------------------------------------------------------------- Zitatpruefung

# Auslassungen: [...] (...) … oder schlicht drei Punkte zwischen Leerzeichen
_TEILER = re.compile(r"\[\s*(?:\.{2,}|…)\s*\]|\(\s*(?:\.{2,}|…)\s*\)"
                     r"|\s\.{3,}\s|\s…\s|\.{4,}|…")


def _bruchstuecke(zitat):
    """Zitat an Auslassungen zerlegen.

    Geputzt werden nur die Reste der Auslassung - der Schlusspunkt eines
    Satzes bleibt stehen. Ein Zitat ohne seinen Punkt ist nicht woertlich.
    """
    teile = []
    for t in _TEILER.split(zitat):
        t = re.sub(r"^[\s\[\]]+|[\s\[\]]+$", "", t)
        t = re.sub(r"^\.{2,}\s*|\s*\.{2,}$", "", t)
        t = t.strip()
        if len(_nur_falten(t)) >= MIN_LAENGE:
            teile.append(t)
    return teile


def pruefe_zitat(bestand, zitat, quellen=()):
    """Prueft ein Beleg-Zitat gegen den Bestand.

    Liefert ein dict:
      urteil    woertlich | geglaettet | teilweise | ungedeckt | zu_kurz
      original  der echte Wortlaut aus der Quelle (bei Treffer)
      doku      Dokumentname der ersten Fundstelle
      orte      [(Dokument, (von, bis) oder None), ...] in Zitatreihenfolge
      offen     Bruchstuecke, die sich NICHT belegen liessen
      guete     Aehnlichkeit 0..1
    """
    leer = {"urteil": "ungedeckt", "original": zitat, "doku": None,
            "seiten": None, "orte": [], "offen": [zitat], "guete": 0.0,
            "formel_defekt": False}
    teile = _bruchstuecke(zitat)
    if not teile:
        return dict(leer, urteil="zu_kurz", offen=[])

    # Je Bruchstueck getrennt merken, aus welchem Dokument und welcher Seite es
    # stammt. Ein durch [...] zusammengesetztes Zitat kann durchaus aus zwei
    # verschiedenen Arbeiten stammen - dann muessen auch beide genannt werden.
    stuecke, orte, guten, offen = [], [], [], []
    formel_defekt = False
    mehrfach_gesamt = False
    for t in teile:
        tr = bestand.finde(t, quellen)
        if not tr:
            # Nicht belegbare Teile duerfen NICHT als geprueften Wortlaut
            # durchgehen. Sonst beglaubigt die Veredelung eine Erfindung.
            offen.append(t)
            stuecke.append("[nicht wiedergefunden: %s]" % t)
            continue
        dok, g, a, e, mehrdeutig, mehrfach, alle = tr
        formel_defekt = formel_defekt or dok.formel_beschaedigt(a, e)
        stuecke.append(dok.wortlaut(a, e))
        guten.append(g)

        def _seiten(d, von, bis, nur_bestaetigt=False):
            """Seitenbereich einer Fundstelle - oder None, wenn unklar.

            nur_bestaetigt=True: Ohne Bestaetigung im PDF wird KEINE Seite
            genannt. Fuer die zusaetzlichen Fundorte eines mehrfach
            vorkommenden Zitats - dort stammt der Treffer haeufig aus einer
            Literaturliste, und Doclings Seitenmarke liegt dann fast immer
            daneben. Ein Link auf die falsche Seite ist schlechter als
            keiner: Er sieht richtig aus.
            """
            s1, s2 = d.seite_bei(von), d.seite_bei(max(von, bis - 1))
            bestaetigt = False
            if SEITENPRUEFER and s1:
                try:
                    echt = SEITENPRUEFER(d.titel, s1, d.wortlaut(von, bis))
                    if echt:
                        s1, s2 = echt, echt
                        bestaetigt = True
                except Exception:
                    pass
            if nur_bestaetigt and not bestaetigt:
                return None
            return (s1, s2 or s1) if s1 else None

        mehrfach_gesamt = mehrfach_gesamt or mehrfach
        if mehrfach and alle:
            # Steht die Stelle wortgleich in mehreren Arbeiten, werden ALLE
            # genannt - jede mit ihrer eigenen Seite und damit anklickbar.
            # Frueher blieb ein einziger Eintrag ohne Seite uebrig ("u. a.
            # DS-00-000"); der Beleg zeigte auf nichts, und der genannte Band
            # war womoeglich gar nicht der gemeinte.
            # Fundorte, die nur in einer Literaturliste stehen, fliegen
            # raus: Dort steht ein Verweis auf die Arbeit, nicht ihr Inhalt.
            echte = [(d, va, ve, md) for d, va, ve, md in alle
                     if not d._ist_verzeichnis(va)]
            for d, va, ve, md in (echte or alle)[:3]:
                orte.append((d.titel, None if md
                             else _seiten(d, va, ve, nur_bestaetigt=True)))
            if len(alle) > 3:
                # Ehrlich statt vollstaendig: Die Suche haelt bei vier an.
                orte.append(("weitere Arbeiten", None))
            continue

        if mehrdeutig:
            # Im SELBEN Dokument auf mehreren Seiten: Jede Angabe waere eine
            # Auswahl unter gleichwertigen. Die Datei stimmt, die Seite nicht.
            orte.append((dok.titel, None))
            continue

        orte.append((dok.titel, _seiten(dok, a, e)))

    if not orte:
        return leer

    # gleiche Dokumente zusammenfassen, Reihenfolge des Zitats erhalten
    gebuendelt = []
    for name, s in orte:
        for i, (n2, s2) in enumerate(gebuendelt):
            if n2 == name:
                if s and s2:
                    gebuendelt[i] = (n2, (min(s[0], s2[0]), max(s[1], s2[1])))
                break
        else:
            gebuendelt.append((name, s))

    guete = min(guten) if guten else 0.0
    if offen:
        urteil = "teilweise"
    elif guete >= 0.999:
        urteil = "woertlich"
    else:
        urteil = "geglaettet"
    return {"urteil": urteil, "original": " […] ".join(stuecke),
            "doku": gebuendelt[0][0], "seiten": gebuendelt[0][1],
            "orte": gebuendelt, "offen": offen, "guete": guete,
            "formel_defekt": formel_defekt,
            # Damit fundstelle() den Verweis als Mehrfachvorkommen
            # kennzeichnen kann, ohne den Dokumentnamen zu verunstalten.
            "mehrfach": mehrfach_gesamt}


# ---------------------------------------------------------------- Antworttext

# Kein re.S und keine Anfuehrungszeichen im Rumpf: sonst frisst ein fehlendes
# Schlusszeichen ganze Absaetze samt dem naechsten Beleg. Das Apostroph gehoert
# NICHT in die Schlussklasse - sonst endet das Zitat bei "d'Alembert".
# Zwischen "Beleg" und dem Doppelpunkt darf eine Beschriftung stehen. Das
# Modell haelt sich naemlich nicht zuverlaessig an die Vorgabe und schreibt
# gern "Beleg fuer die Haftung: ..." statt "Beleg: ...". Ohne diese
# Freiheit wurde eine vollstaendige Antwort als "enthaelt keine
# woertlichen Belege" ausgewiesen - obwohl drei Zitate darin standen.
#
# Das Leerzeichen vor der Beschriftung ist Absicht: "Beleg[^:]*:" wuerde
# auch "Belegung:" und "Beleglage:" fangen und mitten im Fliesstext Zitate
# erfinden, wo keine gemeint sind.
_BELEG = re.compile(
    r'(?P<kopf>Beleg(?:[ \t][^:\n]{0,60})?:[ \t]*)'
    r'(?P<auf>[„"“])(?P<text>[^„"“”\n]{%d,1400})'
    r'(?P<zu>[“”"])' % MIN_LAENGE)

# Zitate im FLIESSTEXT, gefolgt von einer Quellenangabe in Klammern:
#
#     … eine „ausreichend niedrige Viskositaet" zu erreichen (S-00-000.x, S. 10)
#
# Seit der neuen Dienstanweisung ("Antworte zuerst, belege dann")
# ist das die uebliche Form - die alte verlangte eine eigene "Beleg:"-Zeile.
# Ohne dieses Muster fand die Pruefung NULL Zitate: Die Antwort galt als
# unbelegt, alle Verweise wurden kursiv gesetzt und sprangen nicht mehr auf
# die Seite.
#
# ⚠ Die Klammer wird MITGEFASST und damit ersetzt. Die Quellenangabe des
#   Modells ist geraten - es kennt die Seite nicht. An ihre Stelle tritt die
#   Fundstelle aus der Pruefung. Zwei Zahlen in einer Zeile, von denen eine
#   geraten ist, waeren schlimmer als keine.
_BELEG_FLIESSTEXT = re.compile(
    r'(?P<kopf>)(?P<auf>[„"“])(?P<text>[^„"“”\n]{%d,1400})(?P<zu>[“”"])'
    # Zwischen Zitat und Quelle stehen oft Woerter ("… zu erreichen (S-00-000,
    # S. 10)"). Sie werden mitgefasst UND beim Ersetzen zurueckgegeben -
    # sonst fehlen sie hinterher im Satz.
    r'(?P<zwischen>[^„"“”()\n]{0,90}?)'
    r'(?P<quelle>\((?:Quelle:[ \t]*)?[^)\n]{3,90}\))' % MIN_LAENGE)

# Quellenangaben des Modells, die keine sind:
#  - "(Quelle: [CONTEXT 0])" - interne Nummer, fuer Lesende bedeutungslos
#  - "(Quelle: [Seite 6])"   - eine GERATENE Seitenzahl. Das Modell kennt die
#    Seite nicht; steht sie neben der geprueften Fundstelle, widersprechen
#    sich zwei Zahlen in derselben Zeile und niemand weiss, welche gilt.
# Die eigene Ausgabe ("Quelle: DS-00-000, Seite 8") wird NICHT getroffen,
# weil zwischen "Quelle:" und "Seite" der Dokumentname steht.
_KONTEXT = re.compile(
    r"\(\s*Quelle:\s*\[?\s*(?:CONTEXT|Kontext|Context|Auszug|Abschnitt\s*Nr\.?"
    r"|Seiten?|S\.)\s*\d+(?:\s*[-–]\s*\d+)?\s*\]?"
    # Das Modell haengt gern noch eine eigene Ortsangabe an:
    # "(Quelle: [CONTEXT 0], Kapitel 4.3)". Die ist ungeprueft wie die
    # geratene Seitenzahl und faellt mit weg.
    r"(?:\s*,[^)\n]{0,80})?\s*\)", re.I)

# so weit darf ein Platzhalter hoechstens ueber dem Beleg stehen, der ihn erklaert
_NAEHE = 400


def fundstelle(pruefung):
    """Baut den Verweis: Dokument, Seite. Bei mehreren Quellen alle.

    Steht die Stelle wortgleich in mehreren Arbeiten, werden alle genannt -
    jede mit ihrer eigenen Seite - und der Verweis mit "u. a." markiert.
    Die Marke ist wichtig: Ohne sie liest sich eine Aufzaehlung wie eine
    Angabe von Zusatzquellen, dabei ist es dieselbe Stelle an mehreren
    Orten. Frueher wurde stattdessen GAR keine Seite genannt - der
    Beleg zeigte auf nichts.
    """
    orte = pruefung.get("orte")
    if not orte:
        if not pruefung.get("doku"):
            return ""
        orte = [(pruefung["doku"], pruefung.get("seiten"))]
    teile = []
    for name, s in orte:
        if name.endswith(".md"):
            name = name[:-3]
        if not s:
            teile.append(name)
        elif s[0] == s[1]:
            teile.append("%s, Seite %d" % (name, s[0]))
        else:
            teile.append("%s, Seite %d-%d" % (name, s[0], s[1]))
    text = " / ".join(teile)
    return ("u. a. " + text) if (pruefung.get("mehrfach") and text) else text


def veredele(antwort, quellen=(), bestand=None, belege_unten=False):
    """Prueft alle Beleg-Zitate einer Antwort und schreibt sie richtig.

    belege_unten=True stellt die Antwort um: statt des Zitatblocks hinter
    jedem Satz steht dort nur noch eine Nummer, die Zitate sammeln sich
    unter der Antwort. Geprueft wird dasselbe - es liest sich nur ruhiger.

    Liefert (neuer_text, liste_der_pruefungen).
    """
    bestand = bestand or Bestand()
    belege = list(_BELEG.finditer(antwort))
    # Dazu die Zitate im Fliesstext - aber keine doppelt: Ein Zitat hinter
    # "Beleg:" wuerde sonst von beiden Mustern gefunden.
    _bereiche = [(m.start(), m.end()) for m in belege]
    for m in _BELEG_FLIESSTEXT.finditer(antwort):
        if any(a <= m.start() < e for a, e in _bereiche):
            continue
        belege.append(m)
    belege.sort(key=lambda m: m.start())
    platzhalter = list(_KONTEXT.finditer(antwort))

    pruefungen, ersetzungen, anhang = [], [], []
    for m in belege:
        p = pruefe_zitat(bestand, m.group("text"), quellen)
        pruefungen.append(p)
        # Wortwahl mit Bedacht: "im Bestand nicht auffindbar" liest sich wie
        # das Eingestaendnis einer Erfindung - dabei ist es meistens nur die
        # Suche, die eine kurze oder tabellarische Stelle nicht zuordnen kann.
        # Der Zwischentext zwischen Zitat und Quellenangabe. Bei der
        # alten "Beleg:"-Form gibt es ihn nicht - dann ist er leer.
        _zw = m.groupdict().get("zwischen") or ""
        if p["urteil"] == "ungedeckt":
            neu = ('%s„%s"%s ⚠️ *(Fundstelle nicht automatisch bestimmbar — '
                   'das Zitat konnte keiner Textstelle zugeordnet werden)*'
                   % (m.group("kopf"), m.group("text"), _zw))
        elif p["urteil"] == "zu_kurz":
            neu = '%s„%s"%s *(zu kurz für eine sichere Zuordnung)*' % (
                m.group("kopf"), m.group("text"), _zw)
        else:
            # Wortwahl: "nur teilweise belegt" liest sich, als haette die
            # FORSCHUNG etwas nur teilweise belegt. Gemeint ist aber die
            # Pruefung: ein Teil des Zitats liess sich im Quelltext nicht
            # wiederfinden. Das muss unmissverstaendlich dastehen.
            marke = {"woertlich": "",
                     "geglaettet": " *(Wortlaut berichtigt)*",
                     "teilweise": " ⚠️ *(Teil des Zitats im Quelltext nicht "
                                  "wiedergefunden)*"}[p["urteil"]]
            # Formeln sind in Fachtexten die eigentliche Aussage. Wurde eine
            # an dieser Stelle nicht sauber ausgelesen, wird das gesagt - und
            # der Weg ins PDF gewiesen, statt so zu tun als sei alles klar.
            if p.get("formel_defekt"):
                marke += (" ⚠️ **Formel an dieser Stelle nicht sicher "
                          "ausgelesen — bitte im PDF nachsehen**")
            neu = ('%s„%s"%s — %s%s'
                   % (m.group("kopf"), p["original"], _zw,
                      fundstelle(p), marke))
        # ⚠ NUR die "Beleg:"-Form wandert nach unten. Ein Zitat MITTEN
        #   IM SATZ darf nicht herausgeschnitten werden - sonst bleibt
        #   ein Fragment stehen:
        #       "… eine im Rohzustand nicht vorhandene, [1]."
        #   (der Satz endete sonst im Nichts.)
        #   Erkennbar am kopf: "Beleg:" bei der Zeilenform, leer im Fliesstext.
        if belege_unten and m.group("kopf").strip():
            nr = len(anhang) + 1
            # Ein Haken am Satz reicht nicht, wenn mit dem Beleg etwas nicht
            # stimmt - das muss man oben sehen, ohne zu scrollen.
            heikel = (p["urteil"] in ("ungedeckt", "teilweise", "zu_kurz")
                      or p.get("formel_defekt"))
            anhang.append("**[%d]** %s"
                          % (nr, neu[len(m.group("kopf")):].strip()))
            # Die Nummer soll ans Ende des vorangehenden Satzes ruecken,
            # nicht auf eine eigene Zeile.
            a = m.start()
            while a > 0 and antwort[a - 1] in " \t\r\n":
                a -= 1
            ersetzungen.append((a, m.end(),
                                " [%d]%s" % (nr, " ⚠️" if heikel else "")))
        else:
            ersetzungen.append((m.start(), m.end(), neu))

    # "(Quelle: [CONTEXT 0])" ist fuer Lesende bedeutungslos. Ersetzt wird es
    # durch die Fundstelle des Belegs, der DIREKT DARUNTER steht - und nur
    # dann. Ohne Abstandsgrenze griffe sich ein Beleg den Platzhalter einer
    # ganz anderen Aussage weit oben im Text. Eine falsche Quellenangabe ist
    # schlimmer als der Platzhalter.
    vergeben = set()
    for m, p in zip(belege, pruefungen):
        if not p.get("doku"):
            continue
        nahe = [k for k in platzhalter
                if k.start() not in vergeben
                and k.end() <= m.start()
                and m.start() - k.end() <= _NAEHE
                and not _BELEG.search(antwort[k.end():m.start()])]
        if not nahe:
            continue
        k = nahe[-1]
        vergeben.add(k.start())
        ersetzungen.append((k.start(), k.end(), "(Quelle: %s)" % fundstelle(p)))
    for k in platzhalter:
        if k.start() not in vergeben:
            ersetzungen.append((k.start(), k.end(), ""))

    # Ueberlappungen aussortieren: ein Platzhalter INNERHALB eines Belegzitats
    # wuerde beim Ersetzen von rechts nach links den umgebenden Text zerreissen.
    ersetzungen.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    sauber, bis = [], -1
    for a, e, text in ersetzungen:
        if a < bis:
            continue
        sauber.append((a, e, text))
        bis = e

    neu = antwort
    for a, e, text in reversed(sauber):
        neu = neu[:a] + text + neu[e:]
    if belege_unten and anhang:
        neu = (neu.rstrip()
               + "\n\n---\n\n**Belege** — jede Stelle im Original "
                 "nachgeschlagen\n\n"
               + "\n\n".join(anhang) + "\n")
    return neu, pruefungen


def bilanz(pruefungen):
    z = {"woertlich": 0, "geglaettet": 0, "teilweise": 0,
         "ungedeckt": 0, "zu_kurz": 0}
    for p in pruefungen:
        z[p["urteil"]] = z.get(p["urteil"], 0) + 1
    return z


if __name__ == "__main__":
    import sys
    b = Bestand()
    print("Bestand: %d Dokumente" % len(b.titel()))
    if b.doppelte:
        print("ACHTUNG doppelte Dateinamen: %s" % ", ".join(b.doppelte[:5]))
    text = sys.stdin.read()
    neu, pr = veredele(text, bestand=b)
    print(neu)
    print("\n---\n", bilanz(pr))
