# Lizenzen — was das Paket kostet und was nicht

Ein häufiges Missverständnis betrifft die Docker-Lizenz: Reicht es, dass nur
eine Person Docker bedient, oder zählt die Größe des Unternehmens? Die Antwort
ist zweigeteilt, und der Unterschied entscheidet.

---

## Docker: zwei verschiedene Programme, zwei verschiedene Lizenzen

| | Docker **Engine** | Docker **Desktop** |
|---|---|---|
| Was | Kommandozeile, Linux | Oberfläche für Windows/macOS |
| Lizenz | Apache 2.0 | Docker Subscription Service Agreement |
| Kosten | **kostenlos, immer** | ab 250 Mitarbeitern **oder** 10 Mio USD Umsatz kostenpflichtig |
| Gewerblich | uneingeschränkt erlaubt | nur mit Abonnement (Pro/Team/Business) |

**Das Paket braucht nur Docker Engine.** Es läuft auf einem Linux-Server,
über `docker compose`, ohne Oberfläche. Damit stellt sich die Lizenzfrage
für den vorgesehenen Betrieb **nicht**.

## Zur ursprünglichen Frage

Bei Docker Desktop ist die Schwelle die **Größe des Unternehmens**, nicht
die Zahl der Nutzenden. Ein Betrieb mit über 250 Mitarbeitenden braucht ein
Abonnement, auch wenn nur eine einzige Person Docker Desktop öffnet.

Aber: Es wird **pro Sitzplatz** abgerechnet. Für eine Person ist es eine
Lizenz, nicht 250 — je nach Stufe rund 9 bis 24 US-Dollar im Monat.

Docker nennt außerdem *education* ausdrücklich als kostenfreien Fall. Ob
ein Hochschulinstitut darunter fällt, ist eine Frage an die Rechtsabteilung
und nicht hier zu entscheiden.

**Praktische Folge:** Solange das Paket auf einem Server läuft, ist der
einfachste Weg auch der lizenzfreie. Erst wenn jemand es auf einem
Windows-Arbeitsplatz betreiben will, wird Docker Desktop und damit die
Lizenzfrage relevant.

---

## Die übrigen Bausteine

Am laufenden System geprüft:

| Baustein | Lizenz | woher geprüft |
|---|---|---|
| Docling (7 Teilpakete) | **MIT** | Paket-Metadaten im Container |
| Gemma 4 12B | **Apache 2.0** | `ollama show gemma4:12b` |
| bge-m3 (Vektoren) | **MIT** | `ollama show bge-m3` |
| Apache Tika 3.3.1 | Apache 2.0 | Projekt der Apache Software Foundation |
| Prüf-Proxy, mkmd-Dienst | eigene Entwicklung | IKV |
| n8n 2.31.4 | Sustainable Use License | ⚠ siehe unten — **nicht** am System belegt |
| Ollama | vermutlich MIT | ⚠ **nicht geprüft** |

Die letzten zwei Zeilen sind ausdrücklich als ungeprüft markiert. Bei n8n
stand im Paketkopf keine Lizenzangabe; die genannte stammt aus allgemeiner
Kenntnis und ist vor einer Vermarktung am Original nachzulesen. Bei Ollama
ebenso — für den internen Betrieb spielt es keine Rolle, für ein Angebot
schon.

### ⚠ n8n verdient einen genaueren Blick

n8n steht **nicht** unter einer klassischen Open-Source-Lizenz, sondern
unter der *Sustainable Use License*. Erlaubt ist der interne
Geschäftsbetrieb. Nicht erlaubt ist, n8n als Teil eines Produkts an Dritte
weiterzugeben oder als Dienst anzubieten.

**Einordnung:** Der interne Geschäftsbetrieb ist gedeckt — auch der Betrieb
bei einem Netzwerkpartner in dessen eigenem Haus, denn der Partner betreibt
es für sich selbst.

**Wo es eng werden könnte:** Wenn das Paket als fertiges Produkt vermarktet
wird und n8n darin fest verbaut ist. Dann ist vorher zu klären, ob das noch
interner Gebrauch ist.

Diese Frage ist nicht dringend — sie wird es, wenn aus dem Paket ein
Angebot wird. Genau deshalb steht hier, dass sie existiert.

Umgehen ließe sie sich ohnehin leicht: Der Zeitplan-Teil, den n8n
übernimmt, ist bereits vollständig als Skript vorhanden (`zyklus.sh` und
`waechter.sh`). n8n ist im Hybridbetrieb die bequeme Oberfläche, nicht die
Voraussetzung. Ein Paket ohne n8n wäre kleiner, nicht schwächer.
