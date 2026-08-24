# KI4KI — belegprüfende Wissensdatenbank

Fragen an die eigene Forschungsliteratur stellen — und **jede Antwort mit einer
geprüften Fundstelle im Original-PDF** belegt bekommen, Seite für Seite, gelb
markiert.

Die Anlage läuft **vollständig im eigenen Haus**. Kein Dokument, keine Frage und
keine Antwort verlässt den Rechner. Nach draußen gehen nur beim **ersten Start**
die Programm-Abbilder und das Sprachmodell (siehe §12 für die genauen Ziele).

> **Kurz-Glossar** (Begriffe, die hier immer wieder vorkommen):
> **Terminal** = das schwarze Text-Eingabefenster auf dem Server ·
> **Docker** = das Programm, das die Bausteine als „Container" laufen lässt ·
> **Compose** = startet alle Container zusammen (`docker compose …`) ·
> **Volume** = ein Daten-Topf, in dem Docker die Daten eines Containers dauerhaft ablegt ·
> **Prüf-Proxy** = die Prüf-Tür vor der Oberfläche ·
> **Ablaufplan (Workflow)** = ein automatischer Ablauf in „n8n", der die Aufnahme steuert ·
> **API-Schlüssel** = ein Passwort für Programme (kein Login-Passwort).

---

## 1 · Was es ist

Eine lokale KI-Wissensdatenbank für Fachliteratur. Der Unterschied zu „einfach
ChatGPT fragen":

- **Belegpflicht:** Jede Aussage wird gegen das Original-PDF geprüft, mit Link auf
  die richtige Seite und **gelber Markierung**. Was sich nicht belegen lässt, wird
  nicht behauptet.
- **Bestandsfragen ohne Modell:** „Was habt ihr an Dissertationen zu X?" → direkt
  aus dem Katalog, sofort.
- **Alles lokal:** eigenes Sprachmodell (Ollama/Gemma), keine Cloud.

**Was die Anlage kann — auf einen Blick** (und wer es jeweils erledigt):

| Fähigkeit | Wer arbeitet |
|---|---|
| Fachfragen mit Belegen, Link + gelbe Markierung im Original | Antwort: **gemma4:12b** · Prüfung: **Programmcode**, kein Modell — kann nicht halluzinieren |
| Volltext-Zusammenfassung ganzer Dokumente (nicht nur Fundstellen) | gemma4:12b liest das Dokument in Teilen komplett |
| **Aufträge über ein ganzes Dokument:** Präsentations-Gliederung, Folien-Stichpunkte, Handout, Vortrag, Lernkarten („Bereite mir aus der Dissertation eine Präsentation vor") | derselbe Volltext-Weg; Inhalte nur aus dem Dokument, Form frei |
| Abbildungen/Diagramme der belegten Seiten direkt im Chat | Programmcode (schneidet sie aus der PDF-Seite aus) |
| Bestandslisten („was habt ihr an …") in unter einer Sekunde | Katalog-Abfrage, **ganz ohne KI** |
| Wörtliche Suche nach seltenen Fachbegriffen | Wortverzeichnis (baut sich selbst); Ähnlichkeitssuche: **bge-m3** |
| Frage-Einordnung bei Umschreibungen („Auffangnetz", s. 5.1) | **gemma4:e2b** (klein, ~1 s) |
| Kurzantworten auf schlichte Definitionsfragen | **gemma4:e2b**, gestützt auf Fundstellen |
| Begrüßung / „Was kannst du?" | feste Antworten, ohne Modell |
| Allgemeinwissen NUR wenn die Suche nichts findet — sichtbar markiert | gemma4:12b, Fußzeile „nicht aus euren Dokumenten belegt" |
| Aufnahme: OCR, Formeln (CodeFormulaV2), Bildbeschreibung; Dubletten-Sperre (byte-genau) und Selbst-Aufräumen hängengebliebener Läufe | Docling + Vision-Modell + n8n-Ablauf |

---

## 2 · Voraussetzungen

| | |
|---|---|
| Betriebssystem | Linux mit **Docker** und **Docker Compose v2** |
| Arbeitsspeicher | **32 GB**, besser 64 GB |
| Festplatte | **100 GB** frei, plus etwa das Doppelte der eigenen PDF-Menge |
| Grafikkarte | **empfohlen** — NVIDIA ab 16 GB. Einzige Voraussetzung: der **NVIDIA-Treiber** ist installiert (`nvidia-smi` zeigt die Karte — bei GPU-Servern der Normalfall). Die Docker-GPU-Brücke (Container Toolkit) richtet `start.sh` **selbst** ein. |

**Ohne Grafikkarte läuft alles**, nur deutlich langsamer (aus ~1,5 Min je Antwort
werden zehn und mehr). `start.sh` erkennt selbst, was da ist: NVIDIA → GPU-Betrieb,
AMD → ROCm-Fassung (vorbereitet, auf echter AMD-Hardware noch ungetestet),
sonst CPU.

**Windows Server:** Es ist derselbe Code, kein eigenes Paket — die Container sind
Linux-Container. Zwei Wege: eine **Linux-VM** auf dem Windows-Server (Hyper-V,
sauberster Weg; GPU-Durchreichung per DDA möglich) oder **WSL2** mit Docker.
Beides ist mit diesem Paket noch nicht praktisch erprobt — die erste
Windows-Installation bitte als begleiteten Test einplanen. Native
Windows-Container funktionieren **nicht**.

---

## 3 · Installation — Schritt für Schritt

> Zeit: ~20–40 Min (der Großteil ist das einmalige Herunterladen der Modelle).
> Alle Befehle werden im **Terminal auf dem Server** eingegeben.

> ### ⚡ In einem Befehl (wenn der Server-Zugang zum Repo eingerichtet ist)
> ```bash
> git clone git@github.com:achmetoglou/ki4ki.git ~/ki4ki && cd ~/ki4ki && ./start.sh
> ```
> Das **lädt herunter und installiert alles** in einem Rutsch — inklusive
> Admin-Konto, API-Schlüssel, erstem Arbeitsbereich und den aktivierten
> Ablaufplänen. Der einzige menschliche Schritt: **einmal ein Admin-Passwort
> festlegen** (start.sh fragt danach). Die Abschnitte 3.2–3.5 sind **nur
> Rückfall-Anleitungen**, falls die Automatik im start.sh-Verlauf eine
> ⚠-Meldung zeigt.
>
> **Später aktualisieren** — ebenfalls ein Befehl (Details §11):
> ```bash
> cd ~/ki4ki && ./aktualisiere.sh
> ```
>
> Der Zugang zum privaten Repo wird **einmal pro Rechner** eingerichtet (ein
> read-only Deploy-Key, ~3 Min — siehe unten „Zugang zum Repo einrichten"). Wer
> das nicht will, lädt das Paket als **ZIP** herunter, entpackt es und macht bei
> 3.1 weiter — dann entfällt `git` ganz.

### 3.0 · Vorbereitung: auf den Server kommen, Docker prüfen, Dateien holen

1. **Auf den Server verbinden** (falls du nicht direkt davor sitzt): von deinem PC
   per SSH, z.B. `ssh benutzer@<server-ip>`. Du bekommst dann das Terminal.
2. **Docker prüfen:**
   ```bash
   docker --version && docker compose version
   ```
   Kommen zwei Versionen → alles da, weiter zu 3.0.3. **Fehlermeldung** („command
   not found") → Docker fehlt:
   ```bash
   curl -fsSL https://get.docker.com | sh          # Docker installieren
   sudo usermod -aG docker $USER && newgrp docker  # ohne sudo nutzen dürfen
   ```
   Die **GPU-Brücke** (NVIDIA Container Toolkit) muss **nicht** von Hand
   installiert werden — `start.sh` erkennt die Karte und richtet sie selbst ein.
   Auch fehlendes Docker versucht `start.sh` selbst zu installieren; die Befehle
   oben sind der manuelle Weg, falls das fehlschlägt.
3. **Dieses Projekt holen und hineinwechseln:**
   ```bash
   git clone git@github.com:achmetoglou/ki4ki.git ~/ki4ki && cd ~/ki4ki
   ```
   (Oder das ZIP herunterladen, entpacken, und mit `cd` in den Ordner wechseln.)

#### Zugang zum Repo einrichten (nur bei `git clone` eines privaten Repos, einmal pro Rechner)

Ist das Repo privat, muss sich der Rechner einmalig ausweisen. Am einfachsten mit
einem **read-only Deploy-Key**:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ki4ki_repo -N "" -C "ki4ki-server"   # Schlüssel erzeugen
cat ~/.ssh/ki4ki_repo.pub                                             # öffentlichen Teil anzeigen
```
Den angezeigten öffentlichen Schlüssel bei GitHub eintragen:
**Repo → Settings → Deploy keys → Add deploy key** (Häkchen „Allow write access"
**weglassen** = nur lesen). Danach git anweisen, diesen Schlüssel zu nutzen:
```bash
echo -e "Host github.com\n  IdentityFile ~/.ssh/ki4ki_repo\n  IdentitiesOnly yes" >> ~/.ssh/config
```
Ab jetzt funktioniert `git clone`/`git pull` ohne weitere Eingabe. **Wer keinen
Schlüssel einrichten will:** ZIP von der Repo-Weboberfläche laden, entpacken,
weiter bei 3.1.

### 3.1 · Anlage starten

```bash
./start.sh
```

Macht **alles** in einem Rutsch: prüft/installiert Docker und die GPU-Brücke,
erzeugt **einmalig** die Zugangsschlüssel (`.secrets.env`), erkennt die
Grafikkarte, baut die Belegprüfung, startet alle Dienste, holt die Modelle
(gemma4:12b, gemma4:e2b, bge-m3, CodeFormulaV2), **legt das Admin-Konto an**
(fragt einmal nach einem Passwort), erzeugt den API-Schlüssel, legt den ersten
Arbeitsbereich „Wissensdatenbank" an und **importiert + aktiviert die drei
Ablaufpläne**. Auch das n8n-Konto (`admin@ki4ki.local`, gleiches Passwort)
entsteht automatisch.

**Erfolg erkennst du daran:** am Ende erscheint eine Liste der Dienste, jeder mit
Status `Up`/`running`. Die Oberfläche ist dann erreichbar (nächster Schritt).

> ⚠️ **`.secrets.env` sofort sichern.** Geht sie verloren, ist **jeder Benutzer
> ausgesperrt**. Die Datei hat absichtlich `chmod 600` (nur der Besitzer darf sie
> lesen) — **nie in Git, nie in ein unverschlüsseltes Backup.**

**Wo erreiche ich die Oberfläche?**
- **Am Server selbst:** `http://localhost:3001`
- **Von einem anderen PC im Haus:** `http://<server-ip>:3001` — die IP findest du
  mit `hostname -I`. *(Die spitzen Klammern nicht mit-eintippen.)*
- Ablaufpläne (n8n): dieselbe Adresse mit `:5678`. Anmeldung dort:
  **`admin@ki4ki.local`** mit demselben Admin-Passwort wie an der
  Oberfläche (das Konto legt `start.sh` automatisch an). Für den
  Alltag ist n8n nicht nötig — nur zum Nachschauen der Aufnahme-Läufe.

### 3.2 · Anmelden (das Konto hat start.sh schon angelegt)

1. Im Browser die Oberfläche (Port **3001**) öffnen.
2. Anmelden als **`admin`** mit dem Passwort aus start.sh (bzw. aus
   `zugangsdaten.txt`, wenn du es hast erzeugen lassen).

> **Rückfall** — nur wenn start.sh „⚠ Automatische Einrichtung nicht moeglich"
> gemeldet hat: Dann fragt die Oberfläche beim ersten Öffnen selbst nach einem
> Admin-Konto (E-Mail/Passwort). Zugangsdaten notieren.

> ℹ️ **Zu Bereichen (Workspaces):** Am saubersten legt Schritt 3.4 den ersten
> Bereich per Skript an (das bestätigt zugleich, dass der API-Schlüssel sitzt).
> **Später darf man Bereiche auch bequem per Klick in der Oberfläche anlegen** —
> die Anlage bringt jeden **neu** angelegten Bereich automatisch auf die
> geprüften Einstellungen (Prompt, Modus, Trefferzahl, Schwelle). Siehe §7.

### 3.3 · API-Schlüssel erzeugen — **Rückfall, normalerweise schon erledigt**

start.sh erzeugt den Schlüssel automatisch und trägt ihn in `.secrets.env` ein.
Nur wenn das laut start.sh-Verlauf **nicht** geklappt hat, von Hand:

1. In der Oberfläche als Admin anmelden.
2. **Einstellungen** (Zahnrad) → **Werkzeuge** → **API-Schlüssel**
   *(englische Oberfläche: **Settings → Tools → API Keys**)*.
3. **Neuen Schlüssel erzeugen** (*Generate New API Key*) → Schlüssel **kopieren**.
4. Die Datei `.secrets.env` bearbeiten (sie liegt im Projektordner, beginnt mit
   einem Punkt = „versteckt"):
   ```bash
   nano .secrets.env
   ```
   Die Zeile `KI4KI_API_KEY=` suchen und den kopierten Schlüssel dahinter setzen:
   ```
   KI4KI_API_KEY=DEIN-KOPIERTER-SCHLUESSEL
   ```
   Speichern mit **Strg+O**, Enter, schließen mit **Strg+X**.
5. Anlage neu starten, damit der Schlüssel greift:
   ```bash
   docker compose up -d
   ```

> Ohne diesen Schritt läuft die Anlage, **nimmt aber keine Dokumente auf**.

### 3.4 · Arbeitsbereich anlegen — **Rückfall, normalerweise schon erledigt**

start.sh legt den Bereich „Wissensdatenbank" automatisch an. Falls nicht:

```bash
./arbeitsbereich_anlegen.sh DEIN-KOPIERTER-SCHLUESSEL
```
*(denselben Schlüssel wie in 3.3, ohne Anführungszeichen)*

Legt den Arbeitsbereich mit der **geprüften Einstellung** an.

### 3.5 · Ablaufpläne (n8n-Workflows) — **Rückfall, normalerweise schon erledigt**

start.sh importiert die drei Ablaufpläne und **aktiviert alle drei**. Nur falls
der start.sh-Verlauf „⚠ Nicht alle Workflows aktiviert" gemeldet hat:

1. Die n8n-Oberfläche (Port **5678**) öffnen — Anmeldung `admin@ki4ki.local` mit
   dem Admin-Passwort (das Konto legt start.sh an).
2. **⋯**-Menü (oben rechts) → **Import from File** / „Aus Datei importieren".
3. Die drei Dateien aus `n8n-workflows/` importieren:
   `1_KI4KI-Masse-Ingest.json`, `2_Dateien-in-JSON-umwandeln.json`,
   `3_Markdown-Datei-erzeugen.json`.
4. ⚠ **ALLE DREI aktivieren** (Schalter oben rechts auf **an**) — auch die zwei
   Unter-Abläufe! n8n führt **inaktive** Unter-Abläufe nicht aus; bleiben sie
   aus, landet jedes Dokument **ohne Fehlermeldung mit leerem Text im
   Aussortiert-Ordner**. (Genau dieser Fehler hat bei einem Testaufbau einen
   halben Tag Fehlersuche gekostet — deshalb macht start.sh es automatisch.)

### ✅ Fertig-Checkliste — kurz prüfen, dass die Automatik alles erledigt hat

- [ ] `./start.sh` durchgelaufen, alle Dienste `Up` (3.1)
- [ ] Anmeldung an der Oberfläche funktioniert (`admin` + dein Passwort)
- [ ] `curl -s http://localhost:3001/pruef-status` antwortet, z. B. `{"bestand": 0, "pdfs": 0}`
- [ ] In n8n (Port 5678): alle **drei** Ablaufpläne vorhanden und **aktiv**
- [ ] Probe-Upload: ein PDF über die Oberfläche hochladen → grüne Karte
      „… wird jetzt aufbereitet"

---

## 4 · Erste Nutzung (Rundgang)

1. **Dokumente hochladen:** am einfachsten über den **Hochladen-Knopf** der
   Oberfläche. Wer Dateien direkt auf den Server legt: in
   **`./dokumente/<bereich>/input/`** (z. B.
   `./dokumente/wissensdatenbank/input/`) — **nicht** in die `./dokumente`-Wurzel,
   dort schaut niemand nach. Die Aufnahme startet automatisch (alle 5 Min wird
   geschaut).
   **Fertig erkennst du daran**, dass das Dokument in der Oberfläche durchsuchbar
   ist bzw. in `dokumente/<bereich>/archiv/` gewandert ist. Bildreiche Scans
   dauern einige Minuten.
2. **Frage stellen**, z.B. *„Wie wirkt sich die Werkzeugtemperatur beim
   Spritzgießen aus?"*
3. **Antwort mit Beleg lesen:** die Beleg-Links öffnen das Original-PDF auf der
   **richtigen Seite**, die Stelle ist **gelb markiert**. Darunter steht, **welches
   Modell** geantwortet hat.
4. **Kopieren:** der Kopier-Knopf übernimmt Antwort samt Formatierung.
5. **Bestandsfrage:** *„Was habt ihr an Dissertationen zu Kleben?"* → sofortige
   Liste aus dem Katalog, ohne Modell.

---

## 5 · So arbeitet die Anlage

AnythingLLM (Oberfläche + Suche) bleibt **unverändert**. Davor sitzt der **Prüf-
Proxy** (Tor 3001) — die **einzige Nutzer-Tür**. Er bereitet die Frage vor und
prüft die Antwort gegen die Originale.

```
Frage → Prüf-Proxy → AnythingLLM (Suche) → Gemma (über nothink-proxy) → Prüf-Proxy → Antwort mit Beleg
```

Zwischen AnythingLLM und dem Modell sitzt ein winziger **nothink-proxy**: er hängt
`"think": false` an jede Anfrage, damit Gemma nicht erst seitenweise „laut denkt"
(gemessen: ~4× schneller). Wenn „das Modell antwortet nicht", lohnt auch ein Blick
auf diesen Dienst.

### 5.1 · Das kleine Modell (Gemma E2B) — das „Auffangnetz"

- **Frage einordnen (`KI4KI_AUFFANGNETZ`):** Zuerst versuchen es die **Regeln**
  (Auslöser-Wörter aus `wortlisten.txt` plus Satzform-Erkennung: „Was ist
  KEINE…", „Vergleiche…", „Fasse…"). Erkennen die nichts, bekommt das kleine
  Modell die Frage zusammen mit einer **festen Liste der sechs Kategorien**
  (bestand · negativfrage · vergleich · zusammenfassung · verfahren · normal)
  und antwortet mit **genau einem Kategorie-Wort** (Temperatur 0, ~1 s). So
  landet auch „gib mir mal einen Überblick, was ihr da habt" beim
  Bestands-Weg. Die **Antwort** formuliert weiterhin das große Modell; die
  Fußzeile nennt den Weg („Einordnung über gemma4:e2b als …"). Fällt das
  kleine Modell aus oder antwortet es Unbrauchbares, läuft die Frage einfach
  den normalen Weg — das Netz kann nie blockieren.
- **Definitionen beantworten (`KI4KI_E2B_ANTWORT`):** eine schlichte „**Was ist
  X?**"-Frage zu einem **seltenen** Fachbegriff beantwortet das kleine Modell
  direkt — **grounded aus den Fundstellen** und **nur aus Dokumenten, die der
  Nutzer sehen darf**. Häufige/analytische Fragen gehen ans große Modell.

**Einstellen:** beide Schalter in der `docker-compose.yml` beim `pruef-proxy`,
Standard **an** (`=1`). Abschalten: `=0` + `docker compose up -d pruef-proxy`.
Unter jeder Antwort steht das verantwortliche Modell (`KI4KI_MODELL_ANZEIGE`).

### 5.2 · Bestandslisten (der Katalog)

„Was habt ihr an …?", „wie viele … gibt es?" → **direkt aus dem Katalog**, ohne
Modell. Der Katalog ist **eine Datei** `bestandsindex.json` (Titel, Verfasser,
Jahr, Art) im Daten-Volume `pruefdaten`. **Er füllt sich selbst:** Fehlt zu
einem Dokument der Eintrag (frische Anlage, Fremddokument), liest das kleine
Modell Titel, Verfasser und Jahr vom Deckblatt und trägt sie ein — in der
Liste mit **°** markiert. Regel: Katalog vor Modell, das Modell füllt nur
Leerstellen. Wer eine eigene Metadaten-Tabelle hat, kann die Datei damit
überschreiben. **Wann eine Liste kommt**,
steuern die **Auslöser-Wörter** in `wortlisten.txt` (ohne Neustart änderbar); dort
stehen auch die **Kennungen** (DS = Dissertation, BS = …).

**Wo die Datei liegt:** `~/ki4ki/pruef-proxy/wortlisten.txt` auf dem Server —
einfach mit einem Texteditor ändern, sie wird bei der nächsten Frage neu
gelesen. Ist die Datei kaputt oder fehlt sie, gelten eingebaute Vorgaben; ein
Tippfehler kann die Anlage also nie lahmlegen.

---

## 6 · Bausteine — welches Skript macht was

Rund **20 Bausteine** im Betrieb. „Neustart?" = muss man nach dem Ändern *dieser
Datei* etwas neu starten.

| Datei | Aufgabe | Neustart? |
|---|---|---|
| `pruef_proxy.py` | **Der Kern** — einzige Tür, prüft jede Antwort, Beleglinks + gelbe Marken, Rechte | Proxy neu |
| `assistent.py` | Ordnet jede Frage in 7 Fälle ein + E2B-Auffangnetz | Proxy neu |
| `bestand.py` | Bestandsfragen aus dem Katalog, ohne Modell | Proxy neu |
| `wortlisten.py` | Liest die Auslöser-Wortliste — die **Textdatei** `wortlisten.txt` ohne Neustart änderbar | Proxy / .txt: **nein** |
| `wortsuche.py` + `wortverzeichnis.py` | Wörtliche Suche für seltene Fachbegriffe | Proxy neu |
| `veredeln.py` | Prüft jedes Zitat gegen den Bestand, ergänzt Seiten/Belege | Proxy neu |
| `pdfstelle.py` | Findet die Stelle im PDF (Seite + Markierung) | Proxy neu |
| `abbildung.py` | Schneidet eine einzelne Abbildung für den Chat frei | Proxy neu |
| `mehrstufig.py` | Zusammenfassung über den Volltext | Proxy neu |
| `namen.py` | Säubert Dokumentnamen beim Hochladen | Proxy neu |
| `pruefprotokoll.py` | Fälschungssicheres Protokoll (Hash-Kette) | Proxy neu |
| `mkmd_dienst.py` + `mk_md.py` | **Aufnahme:** baut aus einem Dokument das Markdown | Dienst neu |
| `bildbeschreibung.py` | Beschreibt Abbildungen, damit sie durchsuchbar sind | Dienst neu |
| `seiten_echt.py` + `vorspann_finden.py` | Echte Seitenzahlen + Verzeichnisse | Dienst neu |

**Ohne Neustart änderbar:** `wortlisten.txt`, der Bereichs-Prompt (Oberfläche),
topN/Schwelle/Temperatur/Modell je Bereich (Oberfläche).

---

## 7 · Nutzer & Bereiche

- **Mitarbeiter anlegen:** in der Oberfläche als Admin unter **Einstellungen →
  Benutzer** (*Settings → Users*). AnythingLLM kennt Rollen (**Admin / Manager /
  Standard**). Das läuft über die Oberfläche — die externe Fern-Verwaltung ist
  bewusst gesperrt (§12).
- **„Bereich" (Workspace) = ein eigenes Regal** mit eigenen Dokumenten und Regeln.
- **Neue Bereiche sind von Geburt an richtig eingestellt:** Egal ob per Skript
  (§3.4) oder **per Klick in der Oberfläche** — jeder **neu** angelegte Bereich
  bekommt automatisch die geprüften Werte (Systemprompt, Modus `query`,
  Trefferzahl, Schwelle, Verlauf, Temperatur). So kann er sofort Belege liefern,
  ohne dass jemand etwas von Hand einstellen muss. **Bestehende Bereiche werden
  dabei nie verändert.** Steuerung: `KI4KI_BEREICH_HEILEN` (Standard **an**);
  braucht den `KI4KI_API_KEY` aus §3.3. Wer einen Bereich bewusst „nackt" lassen
  will, schaltet den Schalter ab.
- **Zugriff:** Ein neuer Nutzer soll **nur** die Bereiche sehen, die ihm der Admin
  ausdrücklich zuweist — nach dem Prinzip „erst freigeben, dann sichtbar". Prüft
  nach dem Anlegen eines Nutzers, welche Bereiche er sieht.
- **Durchsetzung:** Die Belegprüfung bindet die Berechtigung an **jede Anfrage**
  (über die angemeldete Sitzung) und erzwingt sie an **jedem** Ausgabeweg — auch
  beim kleinen Modell (§5.1) und bei Beleg-/Bild-Abrufen.

---

## 8 · Verwaltung (was man wie einstellt)

| Stellschraube | Wo | Neustart? |
|---|---|---|
| Auslöser-Wörter (Bestandsfragen) | `wortlisten.txt` | **nein** |
| Bereichs-Prompt | Oberfläche, je Bereich | **nein** |
| topN / Schwelle / Temperatur / Modell | Oberfläche, je Bereich | **nein** |
| Verhaltens-Schalter (`AUFFANGNETZ`, `E2B_ANTWORT`, `MODELL_ANZEIGE`, `NENNUNG_TILGEN`, `POSITIVLISTE`, `BEREICH_HEILEN`) | `docker-compose.yml`, `pruef-proxy` | Proxy neu |
| Katalog | `bestandsindex.json` neu bauen | wird geladen |
| Geheimnisse | `.secrets.env` | Container neu |

---

## 9 · Backup & Wiederherstellung ⭐

**Was gesichert werden MUSS** (unvollständiges Backup = kein Wiederaufbau):

1. **`.secrets.env`** — ohne sie **jeder ausgesperrt**. (Am wichtigsten.)
2. **Das ganze Projektverzeichnis** (`docker-compose.yml`, Dockerfiles,
   `wortlisten.txt`, `systemprompt.txt`, `bestandsindex.json`, `n8n-workflows/`) —
   nur damit lässt sich die Anlage neu bauen. Am besten in **Git**.
3. **Die Daten-Volumes:**
   - `ki4ki_anythingllm-daten` — Wissensspeicher
   - `ki4ki_n8n-daten` — Ablaufpläne
   - **`ki4ki_pruefdaten`** — das **fälschungssichere Protokoll** (§13) + Prüf-Speicher
4. Der Ordner **`./dokumente`** (die PDFs), falls nicht ohnehin anderswo.

*(Die Modell-Volumes `ki4ki_modelle`, `ki4ki_docling-modelle` müssen nicht
gesichert werden — sie werden bei Bedarf neu geladen.)*

**Konsistent sichern** (n8n/AnythingLLM schreiben laufend — ein „Hot-tar" kann
inkonsistent sein): erst kurz stoppen, sichern, wieder starten:
```bash
docker compose stop
for v in anythingllm-daten n8n-daten pruefdaten; do
  docker run --rm -v ki4ki_$v:/v -v "$PWD/backup":/b alpine tar czf /b/$v.tgz -C /v .
done
docker compose start
```
**Zurückspielen:** Volume anlegen und das `.tgz` hineinentpacken, z.B.
```bash
docker run --rm -v ki4ki_pruefdaten:/v -v "$PWD/backup":/b alpine \
  tar xzf /b/pruefdaten.tgz -C /v
```
dann `docker compose up -d`.

> **Regelmäßig** sichern (z.B. nächtlicher `cron`-Lauf) und die **Wiederherstellung
> einmal geübt** haben — ein nie zurückgespieltes Backup ist kein Backup.

---

## 10 · Monitoring & Betrieb

- **Läuft es?** `docker compose ps` — auf die **Health**-Spalte achten (der
  Prüf-Proxy hat einen Healthcheck auf `/pruef-status`).
- **Was ist los / was ging schief?** `docker compose logs -f <dienst>`
  (z.B. `pruef-proxy`, `n8n`, `docling`, `ollama`).
- **Startet nach Server-Neustart selbst** (`restart: unless-stopped`).
- **Platte im Blick behalten** (häufigste Ausfallursache!): `df -h` und
  `docker system df`. Die **n8n-Ausführungshistorie** wächst (alle 5 Min ein Lauf)
  — beim n8n-Dienst begrenzen mit `EXECUTIONS_DATA_PRUNE=true` und
  `EXECUTIONS_DATA_MAX_AGE=336` (14 Tage), und Docker-Log-Rotation einrichten.

---

## 11 · Updates

**Der einfache Weg — ein Befehl:**
```bash
cd ~/ki4ki && ./aktualisiere.sh
```
Holt die neueste Paketfassung (`git pull`), baut die selbstgebauten Dienste neu
und startet alles aktualisiert. Daten, Modelle und `.secrets.env` bleiben
unangetastet. (Wer das Paket als ZIP geholt hat: neue ZIP über den Ordner legen
und `docker compose up -d --build` ausführen.)

**Warum das sicher ist:** Alle fremden Abbilder sind auf den **Fingerabdruck
(`@sha256`) festgenagelt** — ein `git pull` ändert daran nichts, der Partner
bekommt **exakt** die geprüfte Anlage, nicht die jeweils neueste vom Anbieter.

**Ein einzelnes fremdes Abbild bewusst anheben** (nur wenn nötig, ein Dienst nach
dem anderen):

1. **Vorher das betroffene Volume sichern** (§9) und den **alten `@sha256`-Wert
   notieren** (Rückweg).
2. Neuen `@sha256`-Wert eintragen → `docker compose up -d <dienst>`.
3. Prüfen (`ps`/`logs`), erst dann den nächsten Dienst.

> ⚠️ **n8n und AnythingLLM fahren beim Start DB-Migrationen.** Ein Downgrade *nach*
> einer Migration kann die Datenbank unbrauchbar machen — deshalb Volume-Backup
> vor jedem Update. Die selbstgebauten Images (`ki4ki-pruef-proxy:1`, `-mkmd:1`)
> aktualisiert `docker compose build …`.

---

## 12 · Härtung & Sicherheit

Das Konzept: **der Prüf-Proxy ist die einzige Nutzer-Tür**, AnythingLLM hat keinen
offenen Anschluss, die Rechteprüfung sitzt an **jedem** Ausgabeweg, Images sind
gepinnt, die externe Fern-Verwaltung (`/api/v1/admin`, `/api/v1/system`) ist per
`KI4KI_POSITIVLISTE=sperren` gesperrt. **Nutzer anlegen/verwalten über die
Oberfläche funktioniert normal.**

**Für den Produktivbetrieb mit vertraulichen Daten dringend empfohlen** (durch die
Standort-IT einzurichten, da standortspezifisch):

1. **HTTPS davor:** Ein Reverse-Proxy (Caddy/nginx) mit TLS vor Port 3001 — sonst
   laufen Login-Passwörter und Antworten **im Klartext** übers Netz. (Die Anlage
   selbst spricht bewusst HTTP; `N8N_SECURE_COOKIE=false` ist genau dafür gesetzt.)
2. **Ports begrenzen:** **3001** (Nutzer) und **5678** (n8n) **nicht** offen auf
   allen Interfaces lassen, sondern per Firewall auf **LAN/VPN** beschränken bzw.
   nur über den Reverse-Proxy erreichbar machen.
3. **n8n ist eine zweite Admin-Tür:** Port **5678** hat Datei-/Ausführungszugriff
   und hält den `KI4KI_API_KEY` — **stärker** absichern als die Nutzer-Oberfläche
   (eigenes Konto, nur über VPN/localhost).
4. **Kein Datenabfluss:** Im Betrieb spricht kein Dienst nach draußen. Wer es
   **erzwingen** will: ausgehenden Verkehr per Firewall sperren (nach dem
   Erststart) — die Container brauchen dann kein Internet mehr. Telemetrie ist
   bereits aus: `DISABLE_TELEMETRY=true` (AnythingLLM), `N8N_DIAGNOSTICS_ENABLED=false`,
   `N8N_VERSION_NOTIFICATIONS_ENABLED=false`.
5. **Geheimnisse:** `.secrets.env` bleibt `chmod 600`, **nie in Git/Backups im
   Klartext**.

**Ausgehende Verbindungen — nur beim ersten Start** (danach Offline-Betrieb möglich;
wer Air-Gap braucht, spiegelt Images + Modelle vorab):

| Zweck | Ziel |
|---|---|
| Programm-Abbilder | Docker Hub, `ghcr.io` |
| Sprachmodelle (gemma4:12b, gemma4:e2b) + Embedder bge-m3 | Ollama-Registry (`ollama.com`) |
| Formelerkennungs-Modell CodeFormulaV2 | `huggingface.co` |
| GPU-Brücke (nur bei NVIDIA, einmalig) | `nvidia.github.io`, Ubuntu/Debian-Paketquellen |

---

## 13 · Datenschutz

Alles läuft **lokal** (Ollama/Gemma, kein ChatGPT). Dokumente, Fragen und Antworten
verlassen den Rechner nicht (Ausnahme Erststart: §12).

**Protokoll (`pruefprotokoll.py`, Volume `pruefdaten`):**
- **Zweck:** Nachweis, welche Antwort mit welchem Beleg ausgeliefert wurde.
- **Inhalt:** Frage, Antwort, Belege — **pseudonymisiert** (Nutzer-Kennung statt
  Klarname).
- ⚠️ **Aufbewahrung/Löschung:** Das Protokoll ist eine **Hash-Kette** (fälschungs­
  sicher) — einzelne Einträge lassen sich **nicht** herauslöschen, ohne die Kette
  zu brechen. Für Betroffenenrechte (Auskunft/Löschung) daher **Aufbewahrungsdauer
  festlegen** und die Kette **turnusmäßig rotieren/verschlüsselt verwerfen**
  (Krypto-Shredding) statt Zeilen zu löschen. Diese Frist ist vom Betreiber zu
  bestimmen.

**Für den Datenschutzbeauftragten** sind über diese README hinaus üblich: ein
**Verzeichnis von Verarbeitungstätigkeiten** (Art. 30), ein **TOM-Dokument**
(TLS, Zugriffsbeschränkung, Backup-Verschlüsselung — §12), ein **Datenfluss­
diagramm** inkl. der Erststart-Verbindungen, sowie — falls der KI4KI-Partner
Fernzugriff für Support erhält — eine **Klärung zur Auftragsverarbeitung**.

---

## 14 · Support & Lizenzen

- **Support:** über euren KI4KI-Ansprechpartner. Ferndiagnose läuft über einen
  **definierten, verschlüsselten Kanal** (VPN oder SSH mit eigenen, benannten
  Konten) — die Anlage muss dafür nichts nach außen öffnen. Zugriffe sollten
  protokolliert sein.
- **Lizenzen:** siehe `LIZENZEN.md`.

---

> **Reifegrad:** maschinell geprüft (Rechteprüfungen an jedem Ausgabeweg, alle
> Module vollständig, Images bauen, Compose valide). Die Freigabe zur Auslieferung
> erfolgt nach der ersten vollständigen Installation auf der Zielumgebung.
