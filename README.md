# KI4KI — belegprüfende Wissensdatenbank

Fragen an die eigene Fachliteratur stellen — jede Antwort kommt mit geprüfter
Fundstelle im Original-PDF, gelb markiert. Läuft komplett im eigenen Haus.
*(Ausführliche Fassung mit allen Hintergründen: `README-ausfuehrlich.md`.)*

## 1 · Installieren

Voraussetzung: Linux-Server, 32 GB RAM, 100 GB Platte + 2× die eigene PDF-Menge.
NVIDIA-Karte empfohlen (Treiber muss da sein — `nvidia-smi` zeigt sie); ohne
Karte läuft alles auf dem Prozessor, nur langsamer.

```bash
git clone git@github.com:achmetoglou/ki4ki.git ~/ki4ki && cd ~/ki4ki && ./start.sh
```

Ein Befehl, **ein Passwort** (start.sh fragt danach) — fertig. Docker, GPU-Brücke,
Modelle, Konto, Arbeitsbereich „Wissensdatenbank", Ablaufpläne: alles automatisch.
Dauer 25–40 Minuten (Modelle laden). Danach:

- Oberfläche: `http://<server-ip>:3001` · Benutzer `admin` + dein Passwort
- Ablaufpläne (n8n, meist nicht nötig): `:5678` · `admin@ki4ki.local` + dasselbe Passwort
- **`.secrets.env` sichern** — ohne sie kommt niemand mehr rein.

Zugang zum privaten Repo einmal pro Server: `ssh-keygen -t ed25519 -f ~/.ssh/ki4ki_repo -N ""`,
den `.pub`-Inhalt bei GitHub als Deploy-Key (nur lesen) eintragen, dann
`echo -e "Host github.com\n  IdentityFile ~/.ssh/ki4ki_repo\n  IdentitiesOnly yes" >> ~/.ssh/config`.

## 2 · Bedienen

| Was | Wie |
|---|---|
| **Dokument hochladen** | Hochladen-Knopf in der Oberfläche — oder per SFTP/FileZilla nach `dokumente/<bereich>/input/`. Aufnahme startet von selbst (jede Minute nachgesehen), fertig = liegt in `archiv/`. |
| **Viele Dokumente (Massenlauf)** | Alle nach `input/` legen. `parkplatz/` = Zwischenlager, wird nie angefasst. |
| **Bilder/Diagramme** | Die Aufnahme liest Text, Tabellen und Formeln (eine Dissertation in 1–3 Minuten). Bildbeschreibungen (~6 s je Bild) und Formel-Erkennung als LaTeX (~6 min je Dissertation) sind deshalb standardmäßig **aus**; die Dokumente stehen in `bilder-nachholen.txt` und bekommen beides nachgelagert. Sofort: `KI4KI_BILDBESCHREIBUNG=an` bzw. `KI4KI_FORMELN=an` in die `.env`. |
| **Rückmeldung geben** | Unter jeder Antwort: Daumen hoch (AnythingLLM) und **Daumen runter mit kurzem Grund** (von der Anlage ergänzt — AnythingLLM kennt nur den hoch). Beides landet im Prüfprotokoll und unter `/rueckmeldungen` bzw. `/kpi`. Die Anlage trainiert sich damit **nicht** selbst; der Betreiber sieht, wo sie schwach war, und die Einträge sind die Grundlage für gezielte Verbesserungen. Im Chat geht auch „Feedback: …" oder „Falsche Quelle: …". |
| **Dokument löschen** | In der Oberfläche: Zahnrad → Dokumente → Papierkorb — die Anlage räumt Archiv-PDF, Katalog und Vormerkliste selbst nach. Oder per SFTP: die Datei (PDF, Excel, Word …) nach `dokumente/<bereich>/loeschen/` legen, alles Weitere passiert von selbst (Quittung in `loeschen.log`). |
| **Fragen** | Fachfrage stellen → Antwort mit Belegen; Klick auf einen Beleg öffnet die Seite im Original, gelb markiert. Diagramme der belegten Seiten erscheinen im Chat. |
| **Zusammenfassen / aufbereiten** | „Fasse die Dissertation zusammen", „Bereite mir daraus eine Präsentation vor", „Stichpunkte für ein Handout" → liest das ganze Dokument. |
| **Bilder** | „Zeig mir Bild 2.1" / „Zeig mir ein Diagramm" → Bildunterschrift, Seite, Bild. |
| **Folgefragen** | Ein Dokument benennen — per Kennung (DS-24-005), Verfasser („die Arbeit von Becker") oder Titelwörtern. Danach meinen „die Arbeit", „daraus", „gesamte Zusammenfassung", „ein Diagramm aus der Arbeit" genau dieses Dokument — dauerhaft je Gesprächsfaden, auch nächste Woche noch. Antworten kommen dann **nur aus diesem Dokument** (mit geprüften Zitaten); steht etwas nicht drin, sagt die Anlage das. Alle Dokumente durchsuchen: Frage mit „im ganzen Bestand:" beginnen. Ohne genanntes Dokument fragt die Anlage nach, welches gemeint ist. Rückmeldung wie „das ist falsch" → sie wiederholt die letzte Frage aus dem richtigen Dokument. |
| **Bestand** | „Welche Dokumente haben wir?" → Tabelle aus dem Katalog (Titel/Autor/Jahr liest die Anlage selbst vom Deckblatt). |
| **Neuer Arbeitsbereich** | Per Klick in der Oberfläche anlegen — bekommt automatisch die geprüften Einstellungen und sofort den Ordner `dokumente/<bereich>/` (input, parkplatz, archiv, aussortiert, loeschen). Fehlende Ordner bestehender Bereiche legt die Anlage alle 5 Minuten nach. **Umbenennen** ändert nur den Anzeigenamen — Kürzel, Adresse und Ordner bleiben. Vertippt beim Anlegen? Solange der Bereich leer ist: löschen und neu anlegen. Beim Löschen eines Bereichs verschwindet sein Ordner mit — **wenn er leer ist**. Liegen Dateien darin (Archiv, Eingang, Parkplatz), bleibt er und wird im Log und unter `curl localhost:3001/pruef-status` als `verwaiste_bereiche` gemeldet; verschieben oder löschen tut dann ein Mensch. |
| **Nutzer** | Oberfläche → Einstellungen → Benutzer. Ein Nutzer sieht nur zugewiesene Bereiche. |

Wo etwas nicht ankam, steht der Grund in `dokumente/<bereich>/aussortiert/aussortiert.log`
(bzw. `claim.log`, wenn eine Datei nach 3 Stunden aus `input/` geräumt wurde).

## 2b · Störfall, Metadaten, Rückmeldungen, Kennzahlen (Leitfaden K1–K5)

| Was | Wie |
|---|---|
| **Störfall** (Use-Case 1) | Im Chat: `Anlage: SGM-3 · Fehlercode: E42 · Symptom: Düse tropft` — oder im Satz („an der SGM-3 kommt E42, Düse tropft"). Antwort als Tabelle Ursache · Maßnahme · Quelle (Seite) · Gültigkeit; nichts Belegtes → Eskalation an den Ansprechpartner (`KI4KI_KONTAKT` in der `.env`). |
| **Metadaten je Dokument** | `dokumente/<bereich>/metadaten.json`: je Kennung `freigabe` (entwurf/geprüft/freigegeben/archiviert), `owner`, `version`, `gueltig_bis`, `review_am`, `ki` (`nein` = für KI ausschließen), `anlage`, `fehlercodes`, `art`. Wirkt sofort. In `bereich.json`: `"nur_freigegebene": true` (nur freigegebene Dokumente sichtbar), `"abgelaufene_ausschliessen": true`. |
| **Rückmeldung** | Daumen hoch/runter unter jeder Antwort (Oberfläche) — oder im Chat `Falsche Quelle: …` / `Feedback: …`. Landet im Protokoll. |
| **Kennzahlen & Liste** | `http://<server>:3001/kpi` (eine Seite: quellenbasierte Antworten, Trefferquote, Eskalationsquote, Zeit bis zur ersten Quelle, Störfälle, Rückmeldungen, Nutzung je Tag) · `/rueckmeldungen` (alle Rückmeldungen) · `/protokoll` (Rohdaten, CSV-Export). Sichtbar für die Konten in `KI4KI_PROTOKOLL_EINSICHT` (Standard `admin`), nach Anmeldung in der Oberfläche. |
| **Audit-Trail** | Jede Frage, Quelle, Antwort, Konto (pseudonym), Bereich, Dauer, Störfall-Kontext — manipulationssicher verkettet, Aufbewahrung `KI4KI_PROTOKOLL_TAGE` (90). |

**Rolle je Bereich (Prompt).** Der Prompt eines Bereichs besteht aus dem **Kern** (`systemprompt.txt`,
19 Zeilen: Belegpflicht, Zitierform, Verbote — gleich für alle) und der **Rolle** (`dokumente/<bereich>/prompt.md`:
Fachgebiet, wer fragt, worauf achten). **Beim Anlegen eines Bereichs in der Oberfläche** stehen die drei
Felder direkt im Formular „Neuer Arbeitsbereich", dazu die Wahl des Modus mit Erklärung (Abfrage = nur
Dokumente mit Beleg, Standard · Chat = plus Allgemeinwissen · Vertreter = ohne Quellen, nicht empfohlen).
Das lokale Modell formuliert aus den Angaben den Rollen-Absatz (ohne neue Fakten; `KI4KI_ROLLE_GLAETTEN=0`
schaltet das ab, dann gilt die Vorlage). **Später ändern:** in den Chat-Einstellungen des Bereichs stehen dieselben drei Felder vorausgefüllt mit
dem Knopf „Rolle speichern & neu formulieren"; wer den Prompt dort direkt im Textfeld ändert, dessen
Rollen-Abschnitt übernimmt die Anlage ebenfalls (die Oberfläche ist die Wahrheit). Alternativ: im Chat
„Rolle einrichten" (drei Fragen) oder `./arbeitsbereich_anlegen.sh <Key> <Name> <Fach> <Wer> <Besonderes>`;
die Datei `prompt.md` kann auch mit einem Editor geändert werden (wirkt binnen fünf Minuten). Solange
keine Rolle eingerichtet ist, gilt nur der Kern. Gedächtnis je Faden: 20 Züge.

**Index eines Bereichs.** „Was haben wir im Bestand?" liefert in jedem Bereich dieselbe Tabelle —
Kennung (Link zur Datei) · Titel · Verfasser · Jahr · Art (Dissertation / PDF mit Seitenzahl / Excel /
Word / Prüfungskatalog) — egal, was hochgeladen wurde. Titel, Verfasser und Jahr liest das kleine
Modell aus dem Deckblatt nach (° in der Tabelle); bis dahin steht ein „—".

**Neue Fassung eines Dokuments.** Einfach die neue Datei unter demselben Namen nach `input/` legen:
Erkennt die Anlage im Archiv eine Datei gleichen Namens mit anderem Inhalt, entfernt sie die alte
Fassung (Bestand, Vektoren, Archiv) und nimmt die neue beim nächsten Durchgang auf — ein Handgriff.
Eine byteweise identische Datei gilt als Doppel und wandert nach einer Stunde nach `aussortiert/`.

**Selbst-Check.** `docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py` (optional `<bereich> <anzahl>`)
zieht je Lauf zufällige Fachwörter aus dem eigenen Bestand, stellt daraus Bestands- und Inhaltsfragen
über die Anlage und urteilt mechanisch: Kommt die Index-Tabelle? Deckt jede belegte Seite die Aussage
davor? Ampel-Bericht im Browser unter `/selbstcheck` (Einsichtsrecht wie `/kpi`). Kein externer Dienst.

**Grafikkarten-Wächter.** Alle 10 Minuten prüft der Proxy bei Ollama, ob die geladenen Modelle im
VRAM liegen. Rechnet eines auf der CPU (Treiberproblem — alles wird 10× langsamer, ohne dass man es
sieht), steht das im Log (`[GPU] ⚠`) und unter `curl localhost:3001/pruef-status` (`gpu.warnung`).

**Gemessene Werte nachziehen.** Neue Bereiche bekommen topN 25 · Schwelle 0,25 · Modus query · Verlauf 6 ·
Temperatur 0,2 (auf dem Testserver gemessen: 25 Textstellen liefern mehr Inhalt als 9, 100 bringen nur Wartezeit).
Bestehende Bereiche fasst die Anlage nie an — `./bereiche_nachziehen.sh` holt sie einmalig nach.

**Prüfungskatalog (Fragen abfragen).** Liegt im Bereich eine Datei mit Fragen und Antwortoptionen
(Excel mit Spalten `Frage | Antwort richtig | Antwort falsch | … | Bereich | LE`, oder ein Katalog mit
a)/b)/c)-Optionen), stellt die Anlage auf „stell mir eine Prüfungsfrage", „frag mich ab", „Frage 7",
„zum Thema Kleben" die **exakte Frage aus der Datei** mit gemischten Optionen — und prüft die Antwort
(„b", „Antwort: c", oder der Optionstext) **gegen den Katalog**: ✅/❌ mit der Katalog-Lösung und
Fundstelle (Frage-Nr., Thema, LE). „weiter" = nächste noch nicht gestellte Frage; „warum?" erklärt aus den
Dokumenten. Enthält der Katalog keine Lösungen (gescannte Testbögen), sagt die Anlage das statt zu urteilen.
Das läuft ohne Sprachmodell — Fragen und Optionen kommen wörtlich aus der Datei.

**Andere Dateiformate.** PDF geht durch Docling (Layout, OCR, Tabellen). **Word und PowerPoint
(doc/docx/odt/rtf, ppt/pptx/odp) wandelt die Anlage zuerst nach PDF** (LibreOffice im Container
`ki4ki-office`, Phase 0): eine Folie wird eine Seite, die PDF liegt neben dem Original im Archiv —
Fundstellen-Links, Seitenbilder und die gelbe Markierung zeigen ins Original. **Excel/CSV bleiben
bewusst Tabellen** (eine nach PDF gedruckte Tabelle verliert, welche Spalte was bedeutet — und
Prüfungskataloge brauchen genau das): Tabelle mit Kopfzeile plus Klartext je Zeile. HTML/Text direkt,
alles andere über Tika. Jede Datei kommt als genau ein Eintrag in den Bestand; die Zuordnung Datei ↔
Text läuft über den Dateinamen. Dokumente ohne PDF haben keine Seitenbilder — Lesen, Suchen und
Zitieren funktionieren trotzdem.

## 3 · Aktualisieren

```bash
cd ~/ki4ki && ./aktualisiere.sh
```
Holt die neue Fassung, baut, spielt Ablaufpläne ein, startet neu. Daten,
Gespräche, Belege, Protokoll und `.secrets.env` bleiben. **Nicht** während eine
Aufnahme läuft (`input/` erst leer werden lassen). Hat sich der Systemprompt
geändert: `./prompt_aktualisieren.sh` rollt ihn auf bestehende Bereiche aus.

## 4 · Sichern

Was reicht, um alles wieder aufzubauen: `.secrets.env` · der Projektordner ·
die Docker-Volumes `ki4ki_anythingllm-daten`, `ki4ki_n8n-daten`, `ki4ki_pruefdaten`
· der Ordner `dokumente/`. Konsistent so:
```bash
cd ~/ki4ki && docker compose stop
for v in anythingllm-daten n8n-daten pruefdaten; do
  docker run --rm -v ki4ki_$v:/v -v "$PWD/backup":/b alpine tar czf /b/$v.tgz -C /v .
done
docker compose start
```
Modell-Volumes müssen nicht gesichert werden (laden sich nach). Rückspielen: siehe
ausführliche Fassung §9.

## 5 · Sicherheit (Kurzfassung)

1. **HTTPS davor** (Reverse-Proxy) — sonst gehen Passwörter im Klartext übers Netz.
2. Ports **3001** und **5678** nur im LAN/VPN erreichbar machen; 5678 ist eine Admin-Tür.
3. Nach dem Erststart braucht kein Dienst Internet (Abbilder/Modelle sind geladen).

## 6 · Wenn etwas hakt

- `docker compose ps` — läuft alles? · `docker compose logs -f pruef-proxy` (oder `n8n`, `docling`)
- `curl -s localhost:3001/pruef-status` → z. B. `{"bestand": 12, "pdfs": 12}`
- Platte voll ist die häufigste Ursache: `df -h`
- Alles Weitere, Schalter und Hintergründe: **`README-ausfuehrlich.md`** · Lizenzen: `LIZENZEN.md`
- Wie das Gespräch funktioniert und wohin es sich entwickelt: **`ARCHITEKTUR-GESPRAECH.md`** · Anforderungen aus der Recherche: `GESPRAECH-ANFORDERUNGEN.md`
