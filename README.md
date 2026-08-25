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
| **Viele Dokumente (Massenlauf)** | Alle nach `input/` legen. Ab 6 Dateien läuft der Durchgang automatisch **ohne** Bildbeschreibung (Minuten statt Stunden); die Dokumente stehen dann in `bilder-nachholen.txt` fürs spätere Nachreichen der Bilder. `parkplatz/` = Zwischenlager, wird nie angefasst. |
| **Dokument löschen** | In der Oberfläche: Zahnrad → Dokumente → Papierkorb — die Anlage räumt Archiv-PDF, Katalog und Vormerkliste selbst nach. Oder per SFTP: PDF nach `dokumente/<bereich>/loeschen/` legen, alles Weitere passiert von selbst (Quittung in `loeschen.log`). |
| **Fragen** | Fachfrage stellen → Antwort mit Belegen; Klick auf einen Beleg öffnet die Seite im Original, gelb markiert. Diagramme der belegten Seiten erscheinen im Chat. |
| **Zusammenfassen / aufbereiten** | „Fasse die Dissertation zusammen", „Bereite mir daraus eine Präsentation vor", „Stichpunkte für ein Handout" → liest das ganze Dokument. |
| **Bilder** | „Zeig mir Bild 2.1" / „Zeig mir ein Diagramm" → Bildunterschrift, Seite, Bild. |
| **Folgefragen** | Ein Dokument benennen — per Kennung (DS-24-005), Verfasser („die Arbeit von Becker") oder Titelwörtern. Danach meinen „die Arbeit", „daraus", „gesamte Zusammenfassung", „ein Diagramm aus der Arbeit" genau dieses Dokument — dauerhaft je Gesprächsfaden, auch nächste Woche noch. Antworten kommen dann **nur aus diesem Dokument** (mit geprüften Zitaten); steht etwas nicht drin, sagt die Anlage das. Alle Dokumente durchsuchen: Frage mit „im ganzen Bestand:" beginnen. Ohne genanntes Dokument fragt die Anlage nach, welches gemeint ist. Rückmeldung wie „das ist falsch" → sie wiederholt die letzte Frage aus dem richtigen Dokument. |
| **Bestand** | „Welche Dokumente haben wir?" → Tabelle aus dem Katalog (Titel/Autor/Jahr liest die Anlage selbst vom Deckblatt). |
| **Neuer Arbeitsbereich** | Per Klick in der Oberfläche anlegen — bekommt automatisch die geprüften Einstellungen. Ordner `dokumente/<bereich>/` entsteht beim ersten Upload. |
| **Nutzer** | Oberfläche → Einstellungen → Benutzer. Ein Nutzer sieht nur zugewiesene Bereiche. |

Wo etwas nicht ankam, steht der Grund in `dokumente/<bereich>/aussortiert/aussortiert.log`
(bzw. `claim.log`, wenn eine Datei nach 3 Stunden aus `input/` geräumt wurde).

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
