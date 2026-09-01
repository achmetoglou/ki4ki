# KI4KI — Wissensdatenbank mit Belegpflicht

Fragen an die eigene Fachliteratur stellen — Normen, Handbücher, Dissertationen,
Prüfungsunterlagen — und jede Antwort mit einer **geprüften Fundstelle im
Original** zurückbekommen: Klick auf den Beleg öffnet die Seite, die Stelle ist
gelb markiert. Was sich nicht belegen lässt, sagt die Anlage ehrlich.

Alles läuft **im eigenen Haus** auf einem Server. Kein Dokument, keine Frage und
keine Antwort verlässt das Gebäude.

**Was die Anlage kann**

- Fachfragen beantworten — mit Zitat, Seite und Link ins Original
- Ganze Dokumente zusammenfassen oder aufbereiten (Präsentation, Handout, Stichpunkte)
- Abbildungen und Diagramme aus den Dokumenten zeigen
- Den Bestand als Tabelle auflisten: Titel, Verfasser, Jahr, Kategorie, Themen
- Prüfungsfragen aus hinterlegten Fragenkatalogen stellen und die Antwort bewerten
- Störfälle: Anlage, Fehlercode, Symptom → Ursache, Maßnahme, Quelle

---

## 1 · Installieren

Voraussetzung: ein Linux-Server mit 32 GB Arbeitsspeicher, 100 GB freier Platte
(plus etwa das Doppelte der eigenen Dokumentenmenge) und möglichst einer
NVIDIA-Grafikkarte. Ohne Grafikkarte läuft alles, nur deutlich langsamer.

```bash
git clone git@github.com:achmetoglou/ki4ki.git ~/ki4ki && cd ~/ki4ki && ./start.sh
```

Ein Befehl, ein Passwort (danach fragt `start.sh`), 25–40 Minuten Wartezeit —
fertig. Danach:

- **Oberfläche:** `http://<server-ip>:3001` · Benutzer `admin` + das gewählte Passwort
- **`.secrets.env` sichern** (liegt im Projektordner). Ohne diese Datei kommt
  niemand mehr an die Anlage.

Der Zugang zum Paket-Repository wird einmal pro Server eingerichtet — Anleitung in
[`doku/BETRIEB.md`](doku/BETRIEB.md), Abschnitt 2.

---

## 2 · Dokumente hineinlegen

**Einzelne Dokumente:** Hochladen-Knopf in der Oberfläche.

**Viele Dokumente:** per SFTP (z. B. FileZilla) auf den Server in den Ordner
`dokumente/<bereich>/input/`, etwa `dokumente/auw/input/`. Die Aufnahme startet
von selbst; fertig aufgenommene Dateien wandern nach `dokumente/<bereich>/archiv/`.

| Gut zu wissen | |
|---|---|
| **Ordner = Kategorie** | Wer Dateien in Unterordner legt (`input/Normen/`, `input/Handbücher/`), gibt damit die Kategorie vor. Tiefere Unterordner werden zu Themen. |
| **Zwischenlager** | `dokumente/<bereich>/parkplatz/` wird nie angefasst — dort kann man Dateien ablegen und ordnerweise nach `input/` schieben. |
| **Dateiformate** | PDF, Word, PowerPoint, Excel, CSV, Text, HTML. Word und PowerPoint werden zusätzlich als PDF abgelegt, damit Belege ins Original zeigen. Excel-Tabellen bleiben Tabellen. |
| **Gleicher Dateiname** | gilt als dasselbe Dokument. Eine neue Fassung unter gleichem Namen nach `input/` legen ersetzt die alte. |
| **Dauer** | Eine Dissertation braucht 1–3 Minuten. Bei vielen Dateien auf einmal schaltet die Aufnahme automatisch in einen schnellen Massenlauf. |
| **Ist alles angekommen?** | `http://<server-ip>:3001/kpi` zeigt unten je Bereich, was im Archiv liegt, was noch wartet und was aussortiert wurde — mit Grund. |

---

## 3 · Fragen stellen

| Sie wollen … | So fragen Sie |
|---|---|
| eine Fachfrage beantwortet haben | „Welche Prüfverfahren nennt die DVS 2213 für Klebeverbindungen?" — Antwort mit Belegen; Klick auf einen Beleg öffnet das Original auf der richtigen Seite |
| ein Dokument zusammengefasst oder aufbereitet | „Fasse die Dissertation von Becker zusammen", „Bereite mir daraus ein Handout vor" |
| eine Abbildung sehen | „Zeig mir Bild 2.1", „Zeig mir ein Diagramm aus der Arbeit" |
| bei einem Dokument bleiben | Einmal das Dokument nennen (Kennung, Verfasser oder Titelwörter). Danach beziehen sich „daraus", „die Arbeit", „gesamte Zusammenfassung" auf genau dieses Dokument — im ganzen Gesprächsfaden. Alles durchsuchen: Frage mit „im ganzen Bestand:" beginnen. |
| wissen, was da ist | „Was haben wir im Bestand?", „Welche Normen haben wir?", „Was habt ihr zum Thema Laminieren?" |
| abgefragt werden | „Stell mir eine Prüfungsfrage", danach „b" oder „Antwort: c", dann „weiter", „warum?" — die Fragen kommen wörtlich aus dem hinterlegten Katalog, die Bewertung ebenso |
| einen Störfall klären | „An der SGM-3 kommt E42, die Düse tropft" — Tabelle mit Ursache, Maßnahme, Quelle; gibt es keinen Beleg, nennt die Anlage den Ansprechpartner |
| etwas melden | Daumen runter unter der Antwort (mit kurzem Grund) — oder im Chat „Falsche Quelle: …" / „Feedback: …" |

Steht etwas nicht in den Dokumenten, sagt die Anlage das — und rät nicht.

---

## 4 · Bereiche und Benutzer

Ein **Bereich** (Arbeitsbereich) ist ein eigenes Regal mit eigenen Dokumenten.
Beim Anlegen in der Oberfläche („Neuer Arbeitsbereich") füllt man drei Felder aus:
Fachgebiet, wer fragt, worauf zu achten ist — daraus entsteht die Rolle des
Bereichs. Dazu die Wahl des Modus:

- **Abfrage** (Standard): nur Antworten aus den Dokumenten, mit Beleg
- **Chat**: zusätzlich Allgemeinwissen, sichtbar getrennt gekennzeichnet

Der Ordner `dokumente/<bereich>/` entsteht automatisch. Ändern lässt sich die Rolle
später in den Chat-Einstellungen des Bereichs.

Ein Bereich antwortet **nur aus seinen eigenen Dokumenten** — auch für Administratoren,
die alle Bereiche sehen. Ein Bereich im Modus „Chat" ohne Dokumente ist damit ein
reiner Modell-Chat ohne Bezug auf Unterlagen.

**Benutzer** legt ein Administrator unter Einstellungen → Benutzer an. Ein
Benutzer sieht nur die Bereiche, die ihm zugewiesen wurden; Administratoren sehen
alle. Die Kennzahlen-Seite (`/kpi`) sehen alle Administratoren; weitere Konten
lassen sich in der `.env` freigeben (siehe Betriebshandbuch).

---

## 5 · Dokumente ersetzen und löschen

- **Ersetzen:** neue Fassung unter demselben Dateinamen nach `input/` legen — die
  alte wird entfernt, die neue aufgenommen.
- **Löschen:** in der Oberfläche (Zahnrad → Dokumente → Papierkorb) oder die Datei
  nach `dokumente/<bereich>/loeschen/` legen. Die Anlage entfernt das Dokument
  vollständig; jeder Schritt steht in `loeschen.log`.

---

## 6 · Aktualisieren und sichern

```bash
cd ~/ki4ki && ./aktualisiere.sh
```

Holt die neue Fassung und startet neu; Dokumente, Gespräche und Einstellungen
bleiben. Nicht während eine Aufnahme läuft (`input/` erst leer werden lassen).

Gesichert werden müssen: `.secrets.env`, der Ordner `dokumente/` und die
Datenspeicher der Anlage — genaue Anleitung in [`doku/BETRIEB.md`](doku/BETRIEB.md),
Abschnitt 8.

---

## 7 · Wenn etwas hakt

1. `http://<server-ip>:3001/kpi` — unten steht, ob Dokumente hängen und warum.
2. `cd ~/ki4ki && docker compose ps` — läuft alles? Jede Zeile muss „Up" zeigen.
3. `df -h` — eine volle Platte ist die häufigste Ursache.

Alles Weitere: [`doku/BETRIEB.md`](doku/BETRIEB.md), Abschnitt 10.

---

## Weitere Unterlagen

- [`doku/BETRIEB.md`](doku/BETRIEB.md) — Betriebshandbuch: Installation im Detail, Dienste, Ordner, Rechte, Schalter, Sicherung, Sicherheit, Datenschutz, Abnahme
- [`doku/ENTWICKLUNG.md`](doku/ENTWICKLUNG.md) — wie die Anlage innen arbeitet (für Entwickler)
- [`LIZENZEN.md`](LIZENZEN.md) — Lizenzen der verwendeten Bausteine
