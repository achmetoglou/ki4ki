# KI4KI — Betriebshandbuch

Für die Person, die die Anlage technisch betreut. Die Bedienung steht in der
[`README.md`](../README.md); wie die Anlage innen arbeitet, in
[`ENTWICKLUNG.md`](ENTWICKLUNG.md).

> **Kurz-Glossar:** **Terminal** = Text-Eingabefenster auf dem Server ·
> **Docker** = lässt die Bausteine als „Container" laufen · **Compose** = startet
> alle Container zusammen (`docker compose …`) · **Volume** = Daten-Topf, in dem
> Docker die Daten eines Containers dauerhaft ablegt · **Prüf-Proxy** = die
> Prüf-Tür vor der Oberfläche · **Ablaufplan** = automatischer Ablauf in n8n, der
> die Aufnahme steuert · **API-Schlüssel** = Passwort für Programme.

## 1 · Voraussetzungen

| | |
|---|---|
| Betriebssystem | Linux mit Docker und Docker Compose v2 (`start.sh` installiert Docker bei Bedarf selbst) |
| Arbeitsspeicher | 32 GB, besser 64 GB |
| Festplatte | 100 GB frei, plus etwa das Doppelte der eigenen Dokumentenmenge |
| Grafikkarte | empfohlen: NVIDIA ab 16 GB. Einzige Voraussetzung ist der NVIDIA-Treiber (`nvidia-smi` zeigt die Karte); die Docker-GPU-Brücke richtet `start.sh` selbst ein. |

Ohne Grafikkarte läuft alles auf dem Prozessor, aus ~1,5 Minuten je Antwort werden
zehn und mehr. `start.sh` erkennt selbst, was da ist (NVIDIA → GPU, AMD → ROCm-Fassung,
auf echter AMD-Hardware noch ungetestet, sonst CPU).

**Windows Server:** derselbe Code, keine eigene Fassung — die Container sind
Linux-Container. Möglich per Linux-VM (Hyper-V, GPU-Durchreichung per DDA) oder
WSL2 mit Docker; beides mit diesem Paket noch nicht erprobt, die erste
Windows-Installation als begleiteten Test einplanen.

## 2 · Installation im Detail

### 2.1 Zugang zum Paket (einmal pro Server)

Das Repository ist privat. Am einfachsten mit einem Deploy-Key, der nur lesen darf:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ki4ki_repo -N "" -C "ki4ki-server"
cat ~/.ssh/ki4ki_repo.pub        # bei GitHub eintragen: Repo → Settings → Deploy keys (ohne Schreibrecht)
echo -e "Host github.com\n  IdentityFile ~/.ssh/ki4ki_repo\n  IdentitiesOnly yes" >> ~/.ssh/config
```

Wer keinen Schlüssel will, lädt das Paket als ZIP und entpackt es nach `~/ki4ki`.

### 2.2 Start

```bash
git clone git@github.com:achmetoglou/ki4ki.git ~/ki4ki && cd ~/ki4ki && ./start.sh
```

`start.sh` prüft Docker und die GPU-Brücke, erzeugt einmalig die Zugangsschlüssel
(`.secrets.env`), baut die eigenen Dienste, startet alles, lädt die Modelle
(gemma4:12b, gemma4:e2b, bge-m3), legt das Admin-Konto an (fragt einmal nach einem
Passwort), erzeugt den API-Schlüssel, legt den ersten Bereich „Wissensdatenbank" an
und importiert und aktiviert die drei Ablaufpläne. Am Ende erscheint eine Liste der
Dienste, jeder mit Status `Up`.

- Oberfläche: `http://<server-ip>:3001` (`admin` + Passwort)
- Ablaufpläne (n8n): `http://<server-ip>:5678` (`admin@ki4ki.local` + dasselbe Passwort). Für den Alltag nicht nötig.
- **`.secrets.env` sofort sichern.** Sie hat `chmod 600` — nie in Git, nie in ein unverschlüsseltes Backup.

### 2.3 Rückfall, falls `start.sh` eine ⚠-Meldung zeigt

| Meldung | Was tun |
|---|---|
| Automatische Einrichtung nicht möglich | Die Oberfläche fragt beim ersten Öffnen selbst nach einem Admin-Konto. |
| API-Schlüssel fehlt | Oberfläche → Einstellungen → Werkzeuge → API-Schlüssel → neuen erzeugen → in `.secrets.env` bei `KI4KI_API_KEY=` eintragen → `docker compose up -d`. Ohne Schlüssel nimmt die Anlage keine Dokumente auf. |
| Arbeitsbereich fehlt | `./arbeitsbereich_anlegen.sh <Kürzel> <Name> <Fachgebiet> <Wer fragt> <Besonderes>` |
| Nicht alle Workflows aktiviert | In n8n die drei Dateien aus `n8n-workflows/` importieren und **alle drei** aktivieren — auch die zwei Unter-Abläufe. Inaktive Unter-Abläufe führen dazu, dass jedes Dokument ohne Fehlermeldung mit leerem Text aussortiert wird. |

### 2.4 Fertig-Prüfung

- [ ] Anmeldung an der Oberfläche funktioniert
- [ ] `curl -s http://localhost:3001/pruef-status` antwortet (z. B. `{"bestand": 0, "pdfs": 0}`)
- [ ] n8n zeigt drei aktive Ablaufpläne
- [ ] Probe-Upload über die Oberfläche → Dokument erscheint nach wenigen Minuten in `dokumente/wissensdatenbank/archiv/`

## 3 · Dienste

| Container | Aufgabe |
|---|---|
| `ki4ki-pruef-proxy` | Die einzige Tür für Nutzer (Port 3001). Bereitet Fragen vor, prüft jede Antwort gegen die Originale, setzt Beleglinks und Markierungen, prüft Rechte. |
| `ki4ki-anythingllm` | Oberfläche, Suche, Benutzerverwaltung. Unverändert; nur über den Proxy erreichbar. |
| `ki4ki-ollama` | Die Sprachmodelle (gemma4:12b für Antworten, gemma4:e2b für kleine Aufgaben, bge-m3 für die Ähnlichkeitssuche). |
| `ki4ki-nothink` | Kleiner Zwischendienst, der dem Modell das „laute Denken" abschaltet (~4× schneller). |
| `ki4ki-docling` | Liest PDFs: Layout, Tabellen, OCR auf der Grafikkarte (Deutsch/Englisch). |
| `ki4ki-office` | LibreOffice: wandelt Word und PowerPoint nach PDF. Nur im Docker-Netz. |
| `ki4ki-tika` | Rückfall für sonstige Dateiformate. |
| `ki4ki-mkmd` | Baut aus dem gelesenen Dokument die Textfassung mit Kopfdaten (Kategorie, Themen, Kurzfassung). |
| `ki4ki-n8n` | Die Ablaufpläne der Aufnahme (Port 5678). |
| `ki4ki-rechte-init` | Setzt beim Start die Ordnerrechte, endet dann. |

Alle Dienste starten nach einem Server-Neustart von selbst (`restart: unless-stopped`).

## 4 · Ordner je Bereich

```
dokumente/<bereich>/
  input/          Eingang — hier hinein; Unterordner = Kategorie (tiefer = Themen)
  parkplatz/      Zwischenlager, wird nie angefasst
  archiv/         fertig aufgenommene Originale (Word/PowerPoint zusätzlich als PDF)
  aussortiert/    was nicht aufgenommen werden konnte, mit aussortiert.log (Grund je Datei)
  loeschen/       Datei hineinlegen = vollständig löschen; Quittung in loeschen.log
  prompt.md       die Rolle des Bereichs (Fachgebiet, wer fragt, worauf achten)
  bereich.json    Einstellungen des Bereichs (Modus, Ablage, Rolle)
  kategorien.txt  die Kategorienliste des Bereichs (Zeile „Name: Stichwort, Stichwort")
  metadaten.json  optional: Freigabestatus, Owner, Version, Gültigkeit je Dokument
  bilder-nachholen.txt  Dokumente, deren Bildbeschreibungen später nachgereicht werden
```

Ein neuer Bereich in der Oberfläche legt den Ordner automatisch an; fehlende Ordner
bestehender Bereiche ergänzt die Anlage alle 5 Minuten. Beim Löschen eines Bereichs
verschwindet sein Ordner nur, wenn er leer ist — sonst wird er unter
`curl localhost:3001/pruef-status` als `verwaiste_bereiche` gemeldet.

## 5 · Wie die Aufnahme läuft

1. Jede Minute sieht n8n in `dokumente/*/input/` nach (auch in Unterordnern).
2. Ein Durchgang nimmt bis zu 25 Dateien (`KI4KI_MENGE_JE_LAUF`) eines Bereichs; eine
   Laufsperre verhindert parallele Durchgänge. Liegen 6 oder mehr Dateien im Eingang
   (`KI4KI_MASSENLAUF_AB`), läuft der Durchgang ohne Bildbeschreibung (Massenlauf);
   die Dokumente stehen dann in `bilder-nachholen.txt`.
3. Word/PowerPoint → PDF (office) → Docling; PDF → Docling (OCR nur bei Scans);
   Excel/CSV → Tabelle mit Klartext je Zeile; Rest → Tika.
4. Das Modell verschlagwortet (Dokumenttyp, Sprache, Tags, Keywords, Kurzfassung),
   `mkmd` baut die Textfassung, sie wird in den Bereich eingebettet.
5. Ablage: Original nach `archiv/`. Dateien, die schon im Bestand sind, räumt der
   Proxy nach einer Stunde ein (gleicher Inhalt → `aussortiert/`, PDF-Fassung → `archiv/`).
6. Was länger als 3 Stunden im Eingang liegt, wandert nach `aussortiert/` (`claim.log`).

**Wichtig:** n8n zeigt einen Durchgang auch dann als „succeeded", wenn einzelne
Dateien gescheitert sind. Die Wahrheit steht auf `http://<server>:3001/kpi` unten
(„Aufnahme") und in `aussortiert/aussortiert.log`. Aussortierte Dateien nach dem
Beheben einfach zurück nach `input/` legen.

Ein `./aktualisiere.sh` während eines Durchgangs bricht ihn ab; die betroffenen
Dateien bleiben im Eingang und werden beim nächsten Durchgang erneut genommen.

## 6 · Schalter (`.env` im Projektordner, danach `docker compose up -d`)

| Schalter | Standard | Wirkung |
|---|---|---|
| `KI4KI_PROTOKOLL_EINSICHT` | `admin` | Konten (Komma-getrennt), die `/kpi`, `/rueckmeldungen`, `/protokoll`, `/selbstcheck` sehen dürfen — auch ohne Admin-Rolle. |
| `KI4KI_EINSICHT_ADMINS` | `1` | Jeder AnythingLLM-Administrator sieht diese Seiten automatisch. `0` = nur die Liste oben (strikte Trennung: der Betreiber sieht nicht, wer was gefragt hat). |
| `KI4KI_KONTAKT` | leer | Name/Mail des Ansprechpartners, den die Anlage bei Störfällen ohne Beleg nennt. |
| `KI4KI_GESPRAECH` | `1` | Gesprächsmodus (das Modell führt das Gespräch mit Werkzeugen des Proxys). `0` = alter Regel-Router. |
| `KI4KI_ABSICHT_MODELL` | `1` | Das Modell erkennt die Absicht einer Frage (Stufe 1). |
| `KI4KI_BILDBESCHREIBUNG` | `aus` | Abbildungen bei der Aufnahme beschreiben lassen (~6 s je Bild). |
| `KI4KI_FORMELN` | `aus` | Formeln als LaTeX erkennen (~6 min je Dissertation). |
| `KI4KI_MASSENLAUF_AB` | `6` | Ab so vielen Dateien im Eingang läuft die Aufnahme ohne Bildbeschreibung. |
| `KI4KI_MENGE_JE_LAUF` | `25` | Dateien je Durchgang. |
| `KI4KI_DOCLING_THREADS` | `12` | Prozessorkerne für Docling. |
| `KI4KI_GID` | `1000` | Gruppe, der die Dokumentordner gehören (für SFTP-Zugang). |
| `KI4KI_ROLLE_GLAETTEN` | an | Das Modell formuliert aus den drei Rollen-Feldern den Rollen-Absatz; `0` = die Vorlage gilt wörtlich. |

Weitere Schalter mit Standardwerten stehen kommentiert in der `docker-compose.yml`
beim Dienst `pruef-proxy` (`AUFFANGNETZ`, `E2B_ANTWORT`, `MODELL_ANZEIGE`,
`BEREICH_HEILEN`, `LOESCHEN`, `POSITIVLISTE`).

**Ohne Neustart änderbar:** `pruef-proxy/wortlisten.txt` (Auslöser-Wörter für
Bestandsfragen, Kennungen), die Rolle je Bereich (Oberfläche oder `prompt.md`,
wirkt binnen 5 Minuten), `kategorien.txt`, `metadaten.json`.

## 7 · Rechte

- **Rollen** kommen aus AnythingLLM: Administrator, Manager, Standard. Ein
  Standard-Benutzer sieht nur die Bereiche, die ihm ein Administrator zuweist
  („erst freigeben, dann sichtbar"); Administratoren sehen alle Bereiche, ohne dass
  sie in der Mitgliederliste eines Bereichs stehen.
- **Durchsetzung:** Der Proxy bindet die Berechtigung an jede Anfrage und prüft sie
  an jedem Ausgabeweg (Antwort, Beleg-Link, Seitenbild, Abbildung, Bestandsliste,
  Export). `python3 pruef-proxy/wegabgleich.py` prüft das maschinell im Quelltext.
- **Einsicht in Protokoll und Kennzahlen** haben alle Administratoren sowie die Konten
  in `KI4KI_PROTOKOLL_EINSICHT`. Soll der Betreiber nicht sehen können, wer was gefragt
  hat (Zusage an eine Personalvertretung), `KI4KI_EINSICHT_ADMINS=0` setzen — dann gilt
  nur die Liste.
- **Rolle eines Bereichs ändern** dürfen Konten mit Einsichtsrecht.
- **Metadaten je Dokument** (`metadaten.json`): `freigabe` (entwurf/geprüft/freigegeben/archiviert),
  `owner`, `version`, `gueltig_bis`, `ki: nein` (für die KI ausschließen). In `bereich.json`:
  `"nur_freigegebene": true`, `"abgelaufene_ausschliessen": true`. Greift in jeder Zugriffsprüfung.
- Die externe Fernverwaltung von AnythingLLM (`/api/v1/admin`, `/api/v1/system`) ist
  gesperrt; Benutzerverwaltung über die Oberfläche funktioniert normal.

## 8 · Sichern und zurückspielen

**Was gesichert werden muss** — ein unvollständiges Backup lässt sich nicht wiederherstellen:

1. `.secrets.env` (ohne sie ist jeder ausgesperrt)
2. der Projektordner `~/ki4ki` (ohne `dokumente/`, das ist Punkt 4)
3. die Volumes `ki4ki_anythingllm-daten` (Wissensspeicher), `ki4ki_n8n-daten`
   (Ablaufpläne), `ki4ki_pruefdaten` (Protokoll, Katalog, Belege)
4. der Ordner `dokumente/`

Die Modell-Volumes (`ki4ki_modelle`, `ki4ki_docling-modelle`) laden sich bei Bedarf neu.

**Konsistent sichern** (die Dienste schreiben laufend, deshalb kurz anhalten):

```bash
cd ~/ki4ki && docker compose stop
for v in anythingllm-daten n8n-daten pruefdaten; do
  docker run --rm -v ki4ki_$v:/v -v "$PWD/backup":/b alpine tar czf /b/$v.tgz -C /v .
done
docker compose start
```

**Zurückspielen:** Volume anlegen, Archiv hineinentpacken, starten:

```bash
docker run --rm -v ki4ki_pruefdaten:/v -v "$PWD/backup":/b alpine tar xzf /b/pruefdaten.tgz -C /v
docker compose up -d
```

Regelmäßig sichern (nächtlicher `cron`) und die Wiederherstellung einmal geübt
haben — ein nie zurückgespieltes Backup ist kein Backup.

## 9 · Aktualisieren

```bash
cd ~/ki4ki && ./aktualisiere.sh
```

Holt die neue Fassung, baut die eigenen Dienste, spielt die Ablaufpläne ein und
startet neu. Daten, Gespräche, Belege, Protokoll und `.secrets.env` bleiben. Nicht
während eine Aufnahme läuft. Hat sich der Kern-Prompt geändert:
`./prompt_aktualisieren.sh` rollt ihn auf bestehende Bereiche aus;
`./bereiche_nachziehen.sh` bringt bestehende Bereiche auf die geprüften Einstellwerte
(die Anlage fasst bestehende Bereiche sonst nie an).

Alle fremden Programm-Abbilder sind auf ihren Fingerabdruck (`@sha256`) festgelegt —
ein Update bringt exakt die geprüfte Fassung, nicht die jeweils neueste vom Anbieter.
Ein einzelnes Abbild anheben: vorher das Volume sichern und den alten Wert notieren,
neuen Wert eintragen, `docker compose up -d <dienst>`, prüfen. n8n und AnythingLLM
fahren beim Start Datenbank-Migrationen; ein Rückschritt danach kann die Datenbank
unbrauchbar machen.

## 10 · Wenn etwas hakt

| Symptom | Nachsehen |
|---|---|
| Dokumente kommen nicht an | `http://<server>:3001/kpi` unten; `dokumente/<bereich>/aussortiert/aussortiert.log`; `docker compose logs -f n8n` bzw. `docling` |
| Läuft alles? | `docker compose ps` — Spalte Status/Health; `curl -s localhost:3001/pruef-status` |
| Antworten ohne Belege | Bereich prüfen: Modus „Abfrage", Prompt enthält den Kern (`./prompt_aktualisieren.sh`) |
| Alles plötzlich 10× langsamer | Grafikkarte: `curl -s localhost:3001/pruef-status` → `gpu.warnung`; im Log `[GPU] ⚠`. Der Proxy prüft alle 10 Minuten, ob die Modelle im Grafikspeicher liegen. |
| Modell antwortet nicht | `docker compose logs -f ollama` und `nothink-proxy` |
| Platte voll | `df -h`, `docker system df`. Die n8n-Ausführungshistorie wächst (jede Minute ein Lauf): `EXECUTIONS_DATA_PRUNE=true`, `EXECUTIONS_DATA_MAX_AGE=336`. |
| Aufnahme steht seit Stunden | Laufsperre `/files/json/.lauf.sperre` im n8n-Container; löst sich nach 120 Minuten selbst, `aktualisiere.sh` räumt sie nach dem Neustart weg |

**Selbst-Check:** `docker exec ki4ki-pruef-proxy python3 /app/selbstcheck.py [<bereich> <anzahl>]`
stellt zufällige Fragen aus dem eigenen Bestand und prüft mechanisch, ob Belege
und Bestandslisten stimmen. Ampel-Bericht unter `http://<server>:3001/selbstcheck`.

## 11 · Kennzahlen und Protokoll

- `/kpi` — eine Seite: Anteil belegter Antworten, Trefferquote, Eskalationsquote,
  Zeit bis zur ersten Quelle, Störfälle, Rückmeldungen, Nutzung je Tag, Aufnahme je
  Bereich. `/kpi?format=json`, Zeitraum `/kpi?seit=2026-08-01&bis=2026-08-31`.
- `/rueckmeldungen` — alle Daumen und Meldungen mit Frage, Antwortauszug, Fundstellen.
- `/protokoll` — Rohdaten; `/protokoll/ausfuhr?format=csv` als Tabelle;
  `/protokoll/eigenes` zeigt jedem Angemeldeten nur die eigenen Vorgänge.
- Das Protokoll ist eine Hash-Kette (fälschungssicher, pseudonymisierte Konten),
  Aufbewahrung `KI4KI_PROTOKOLL_TAGE` (90).

## 12 · Sicherheit

1. **HTTPS davor:** ein Reverse-Proxy (Caddy/nginx) mit TLS vor Port 3001 — sonst
   laufen Passwörter und Antworten im Klartext übers Netz.
2. **Ports begrenzen:** 3001 (Nutzer) und 5678 (n8n) nur im LAN/VPN. n8n ist eine
   zweite Admin-Tür mit Dateizugriff und dem API-Schlüssel — stärker absichern.
3. **Kein Datenabfluss:** Nach dem ersten Start braucht kein Dienst Internet;
   ausgehenden Verkehr per Firewall sperren ist möglich. Telemetrie ist aus.
4. `.secrets.env` bleibt `chmod 600`, nie in Git oder Klartext-Backups.

Ausgehende Verbindungen nur beim ersten Start: Docker Hub und `ghcr.io`
(Programm-Abbilder), `ollama.com` (Modelle), `huggingface.co` (Docling-Modelle),
`nvidia.github.io` (GPU-Brücke). Wer Air-Gap braucht, spiegelt das vorab.

## 13 · Datenschutz

Dokumente, Fragen und Antworten verlassen den Server nicht. Das Protokoll enthält
Frage, Antwort und Belege mit pseudonymisierter Konto-Kennung. Weil es eine
Hash-Kette ist, lassen sich einzelne Einträge nicht herauslöschen — für
Betroffenenrechte deshalb eine Aufbewahrungsfrist festlegen und die Kette
turnusmäßig verwerfen statt Zeilen zu löschen.

Für den Datenschutzbeauftragten üblich: Verzeichnis von Verarbeitungstätigkeiten,
TOM-Dokument (TLS, Zugriffsbeschränkung, Backup-Verschlüsselung), Datenflussdiagramm
inklusive der Erststart-Verbindungen; bei Fernzugriff für Support eine Klärung zur
Auftragsverarbeitung. Ferndiagnose läuft über VPN oder SSH mit benannten Konten —
die Anlage muss dafür nichts nach außen öffnen.

## 14 · Abnahme von null (Wipe-Test)

Die Lieferzusage ist: ein Partner wird mit dem Paket allein startklar. Vor einer
Weitergabe deshalb einmal alles wegwerfen und von vorn aufbauen.

**Wegwerfen** (als der Benutzer, dem `~/ki4ki` gehört):
```bash
cd ~/ki4ki && docker compose down -v     # Container und Datenvolumes; ki4ki_modelle darf bleiben (spart ~20 min)
docker volume ls | grep ki4ki
cd ~ && mv ki4ki ki4ki.alt-$(date +%F)    # Dokumente liegen darin unter dokumente/
```

**Aufbauen:** `git clone … ~/ki4ki && cd ~/ki4ki && ./start.sh`, ein Passwort.

**Prüfen, in dieser Reihenfolge:**
1. Anmeldung `admin`, Bereich „Wissensdatenbank" vorhanden, `dokumente/wissensdatenbank/` mit Unterordnern.
2. Bereich anlegen mit den drei Rollen-Feldern, Modus Abfrage → Chat-Einstellungen zeigen Modus und Prompt mit „Rolle dieses Bereichs".
3. Nach `input/` legen: drei PDFs (Norm, Scan, Leitfaden), eine Prüfungs-Excel, eine `.docx`, eine `.pptx`, eine PDF in `input/Normen/`. Nach 5–10 Minuten: alles in `archiv/`, `aussortiert.log` leer, `/kpi` zeigt „alles eingeräumt".
4. „Was haben wir im Bestand" → Tabelle mit Kategorie und Themen; die Datei aus `input/Normen/` als Norm/Richtlinie; Word/PowerPoint als „Word → PDF · n S.".
5. „Stell mir eine Prüfungsfrage" → Antwort → „weiter" → „warum?".
6. Fachfrage → belegte Antwort, Beleg-Link klicken, gelbe Markierung. „Zeig mir ein Diagramm aus …".
7. „Welche Normen haben wir?", „Was habt ihr zum Thema …?".
8. Daumen runter mit Grund → `/rueckmeldungen` zeigt den Eintrag; `/kpi` und `/protokoll` laden; `/selbstcheck` nach einem Selbst-Check-Lauf.
9. Bereich löschen → Ordner verschwindet; Datei nach `loeschen/` → verschwindet aus Bestand und Archiv.
10. `./aktualisiere.sh` läuft ohne Fehler durch, alle Container „Up".

## 15 · Support und Lizenzen

Support über den KI4KI-Ansprechpartner. Lizenzen der Bausteine: [`LIZENZEN.md`](../LIZENZEN.md)
— dort auch die Frage Docker Engine (frei) gegen Docker Desktop (lizenzpflichtig ab
Unternehmensgröße) und die n8n-Lizenz (interner Betrieb gedeckt; ein vermarktetes
Produkt mit fest verbautem n8n wäre vorher zu prüfen).
