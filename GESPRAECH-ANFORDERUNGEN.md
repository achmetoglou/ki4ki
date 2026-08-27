# Was der Chat im Gespräch können muss — Anforderungen und Abgleich

Stand 25.08.2026. Grundlage: drei Recherchen (Laien-Erwartungen, Wissenschaftler/Ingenieure,
Stand der Technik für mehrstufige Dialoge über RAG) — alle Quellen unten verlinkt.
Anlass: ein realer Gesprächsfaden, der an fünf Stellen hintereinander scheiterte
(Dokument nicht erkannt, Folgefrage ohne Bezug, Bild aus falscher Arbeit, Beschwerde
als Frage behandelt, Wortsuche nach Alltagswörtern).

Legende Abgleich: ✅ vorhanden · 🟡 teilweise · ❌ fehlt

## 1 · Gesprächsführung (gilt für alle Nutzer)

| # | Anforderung | Beleg | KI4KI |
|---|---|---|---|
| 1 | **Kontext über mehrere Züge halten** — „die Arbeit", „daraus", „und die andere?" beziehen sich auf das, worum es gerade geht | HAX G12 „Remember recent interactions"; Hauptkritik bei Luger & Sellen [L2]; MTRAG: Folgezüge sind der Hauptfehlerherd (Recall 0,89 → 0,47) [T1] | 🟡 seit 25.08.: Faden-Dokument dauerhaft; Gegenstand nur 8 Schritte |
| 2 | **Themenwechsel erkennen** (Pivot vs. Vertiefung) — neuer Name/Titel = neues Thema, sonst weiter beim alten | Netflix Context-Switch: 8B-Modelle erkennen Wechsel schlecht, 87 % „alter Kontext klebt" → zweistufiger Controller außerhalb des Modells [T4] | 🟡 Regel „eigener Name → nicht umbiegen"; kein explizites Leeren |
| 3 | **Rückmeldung/Beschwerde erkennen** — „das ist falsch", „andere Dissertation!", „nicht danach gefragt" ist keine Frage; ab Zug 5 sind >50 % der Eingaben Feedback | Feedback-Taxonomie [T6]; Ashktorab: Reparatur mit Optionen + Erklärung [L5]; HAX G9 „Support efficient correction" | 🟡 seit 25.08.: Erkennung + Entschuldigung; **keine Reparatur** (erneute Suche mit Dokument-Filter) |
| 4 | **Rückfrage nur bei echter Mehrdeutigkeit — dann mit Optionen** | NN/g-Tagebuch: nur 3,8 % Rückfragen, Nutzer wollten mehr [L4]; Klärfrage nach Ambiguitätsgrad [T8]; Instruction-Tuning drückt Klärfragen um 85 % → im Proxy erzwingen [T7] | ✅ Dokumentwahl-Rückfrage; ❌ bei leerem Faden + unvollständiger Frage keine Klärfrage |
| 5 | **Ehrlich „steht nicht drin"** — nie auf den Gesamtbestand ausweichen, wenn ein Dokument gemeint ist | NotebookLM-Prinzip [W10]; MTRAG: „struggling to declare they do not know" [T1]; Model Spec „Express uncertainty" [L7] | 🟡 Bild-Weg seit 25.08. ehrlich; Textfragen weichen noch auf Bestand aus |
| 6 | **Korrektur muss billig sein** — ein Zug, keine Schleife | HAX G9; Følstad: Rückfragen-Schleifen als Top-Frust [L-B] | 🟡 |
| 7 | **Tippfehler, Umgangssprache, Groß/Klein tolerieren** | Følstad: „verstand mich nicht, ich musste wiederholen" [L-B] | 🟡 unscharfe Bildsuche; Bestand/Zusammenfassung regelbasiert, empfindlich |
| 8 | **Kurz, strukturiert, aufklappbar** — weder Textwüste noch leere Stichpunkte | NN/g Guidelines [L9] | 🟡 Tabellen ja; keine Aufklapp-Ebene |
| 9 | **Wartezeit ankündigen** („lese 180 Seiten, dauert …") | Gnewuch: Typing-Indicator [L12]; NN/g | ✅ Stand-Meldungen bei Zusammenfassung; 🟡 beim Bild-Weg |
| 10 | **Nächsten Schritt anbieten** („Soll ich die Tabelle zeigen?") | NN/g G4; userlutions [L11] | 🟡 nur Hinweise im Fuß |
| 11 | **Fehler mit Demut, dann Weg nach vorn** | PAIR „Errors + failing" [L8] | 🟡 seit 25.08. |
| 12 | **Recap des Standes** nach mehreren Zügen („Wir sind bei Becker, Kap. 4") | „LLMs get lost": −39 % bei Mehrschritt; Recap als Gegenmittel [T5] | ❌ |
| 13 | **Scope vorab** — was die Anlage kann und was nicht | HAX G1/G2 [L1] | 🟡 README; nicht im Chat |
| 14 | **Weg zum Menschen** | lime-Studie: 77 % nennen es als wichtigste Anforderung [L13] | ❌ (Kontakt/Verantwortlicher je Bereich) |

## 2 · Fachliche Fähigkeiten (Wissenschaftler, Ingenieure)

| # | Anforderung | Beleg | KI4KI |
|---|---|---|---|
| 15 | **Jede Aussage mit Fundstelle bis zur Passage/Seite** | Elicit, SciSpace Marktstandard [W1]; Traceability = Nr.-1-Wunsch [W2] | ✅ Kern der Anlage |
| 16 | **Beleg vs. Schlussfolgerung trennen** | Scite: supporting/contrasting/mentioning [W8] | 🟡 Konfidenz-Block; keine Kennzeichnung je Satz |
| 17 | **Vergleich über Dokumente als Tabelle** (Methodik, Kennwerte, Definitionen) | 38/56 User-Stories = Recherche + Vergleich [W2]; Elicit-Columns | 🟡 Vergleichs-Weg vorhanden, Tabellenform nicht erzwungen |
| 18 | **Kennwerte mit Einheit, Messbedingung, Herkunft (Text/Tabelle/Abbildung)** — fehlende Bedingung benennen | 94,9 % Text/Tabelle vs. 83,5 % Abbildung; nur 9 % der Tabellen nennen Bedingungen [W4] | ❌ keine Kennwert-Extraktion |
| 19 | **Tabellen als Struktur** (Kopfzeile, mehrseitig) | Tabellen = häufigste stille Retrieval-Fehler [W5] | 🟡 Docling accurate; Chunking zerreißt |
| 20 | **Formeln/Tabellen erklären** („was bedeutet Gl. 4.2") | SciSpace Snip→Explain [W6] | 🟡 Formel-OCR (LaTeX) vorhanden; kein gezielter Weg |
| 21 | **Diagramme deuten — mit Unsicherheit** („Ablesung ca. 240 °C, Text sagt 238 °C") | Figure↔Caption 73 % vs. Mensch 86 % [W7] | 🟡 Bildbeschreibung im Ingest; Deutung im Chat nur Unterschrift |
| 22 | **Widersprüche zwischen Arbeiten zeigen** (beide Passagen nebeneinander) | GPT-4 ~88 % bei Kontext-Widersprüchen [W9] | ❌ |
| 23 | **Vollständigkeits-Konfidenz bei Bestandsfragen** („4 Treffer, geschätzt vollständig") | Undermind [W11] | 🟡 Katalog-Treffer; keine Schätzung |
| 24 | **Deutsch/Englisch gemischt** (Titel englisch, Frage deutsch) | Hybrid-RAG >85 % [W12] | 🟡 bge-m3 mehrsprachig; Wortsuche einsprachig |
| 25 | **Abkürzungen aus DIESEM Dokument auflösen** | SciAD: 732 mehrdeutige Akronyme [W13] | ❌ |
| 26 | **Lücken nur belegt** („in diesen 4 Arbeiten nicht behandelt") | GAPMAP [W14] | 🟡 Negativ-Weg |
| 27 | **Export** (CSV, BibTeX/RIS, Markdown) | Elicit-Standard [W15] | ❌ |
| 28 | **Triage** („welche lohnen das Volllesen") | Ithaka [W16] | 🟡 Bestandstabelle + Kurzabriss |

## 3 · Vertrauens-Killer (was nie passieren darf)

- **Erfundene oder teilfalsche Zitate** — 18–55 % je Modell erfunden, 24–43 % der echten fehlerhaft [W-B1]. → Belegprüfung gegen das Original ist der Grund für die Anlage; **bleibt Pflicht für jeden Antwortweg**, auch kleines Modell.
- **Quellenvermischung** — Technik aus Paper A den Experimenten aus Paper B zugeschrieben [W-B2]. → Dokument-Filter im Faden **hart** am Abruf, nicht nur im Prompt.
- **Plausibel, aber falsch** — „irreführend für Nicht-Experten" [W-B2, L-B]. → Konfidenz muss kalibriert sein; „Konfidenz: Hoch" bei Schnipsel-Antwort (25.08.) ist genau dieser Fehler.
- **Unterschlagene Einschränkungen** — „diskutierte Effizienz, verfehlte den zentralen Punkt" [W-B2].
- **Kontext klebt / Themenwechsel verpasst** [T4]; **vorschnelle Antwort statt Rückfrage** [T5].

## 4 · Konsequenzen für den Router im Proxy (priorisiert)

1. **Feedback-Gate vor jeder Einordnung** — Beschwerde erkannt → nicht neu suchen, sondern Stand zeigen und **reparieren**: dieselbe Frage erneut, mit Dokument-Filter aus dem Faden. (Heute: nur Entschuldigung.) [T6, L5]
2. **Pivot-vs-Vertiefung als eigene Stufe** — neuer Name/Titel/Kennung = Pivot → Faden-Dokument wechseln; sonst Vertiefung → Faden-Dokument gilt. [T4]
3. **Dokumentbezug vor Bestandsfrage** — „Zusammenfassung", „Diagramm", „Kernaussagen" ohne Objekt = Faden-Dokument, nie Gesamtbestand. Bestandsfrage nur bei expliziten Markern. [T1]
4. **Klärfrage erzwingen**, wenn Faden leer UND Frage ohne Gegenstand („fasse zusammen" bei 10 Dokumenten) — mit 2–4 Optionen, nicht „welches?". [T7, T8, L3]
5. **Umschreiben konservativ** — Original-Frage behalten + Anhang „[Dokument: X; Gegenstand: Y]"; blindes Neu-Formulieren schadet messbar. [T1-Gegenbefund]
6. **Unanswerable-Pfad** — Filter-Abruf unter Schwelle → „in *X* nicht gefunden", nicht Bestand. [T1]
7. **Recap alle N Züge** im Systemprompt (Dokument, Gegenstand, letzte Belege). [T5]
8. **Konfidenz kalibrieren** — „Hoch" nur bei Volltext- oder belegtem Treffer; Schnipsel-Antwort auf eine Zusammenfassungs-Frage = „Niedrig" + Hinweis.

## 5 · Dialog-Testreihe (Pflicht vor jedem Push)

Format: eine Datei je Dialog (`tests/dialoge/*.json`), Züge mit `frage`, erwarteter
Einordnung (`art`), erwartetem Dokument (`dokument`), erwarteter Antwort-Eigenschaft
(z. B. `enthaelt: "DS-24-005"`, `nicht: "Bestandstabelle"`). **Schicht 1 deterministisch
ohne Modell** (Router-Klasse, Dokument, Faden-Zustand) — deckt die heutigen Fehler zu 100 %.
Schicht 2 (später) referenzbasierter Judge; referenzlose Relevanz-Metriken korrelieren in
Mehrzug-Dialogen nicht [T1]. Werkzeug-Kandidaten: DeepEval ConversationalTestCase, promptfoo
`_conversation`, RAGAS MultiTurnSample [T-D].

Pflichtszenarien (aus MTRAG-UN, Netflix, den Recherche-Dialogen und dem Vorfall vom 25.08.):
1. Dokument per Verfasser nennen → drei elliptische Folgefragen (gesamt, Kernaussagen, Diagramm daraus).
2. Beschwerde nach falschem Treffer → Reparatur mit richtigem Dokument.
3. Echter Themenwechsel (neuer Verfasser) → Faden wechselt.
4. Rückkehr zum ersten Thema nach Wechsel („und bei Becker?").
5. Frage ohne Antwort im Faden-Dokument → „in X nicht gefunden", kein Ausweichen.
6. Vergleich zweier Arbeiten → Tabelle, beide mit Seite.
7. Seltenes Fachwort → wörtliche Fundstelle; Alltagswort am Satzanfang → keine Wortsuche.
8. Bestandsfrage + Tippfehler („hab ihr was zu spritzgiessen von polyamid?").
9. Grenze („Wie viel kostet so eine Maschine?") → ehrlich + Alternative.
10. Bild + Wartezeit + „gibt es das als Tabelle?".

## 6 · Reihenfolge der Umsetzung

- **P1 (vor Partner-Freigabe):** Router-Punkte 1–4, Konfidenz-Kalibrierung (8), Dialog-Testreihe Schicht 1 mit den 10 Szenarien.
- **P2:** Recap (7), Unanswerable-Pfad (6), Vergleich als Tabelle (17), Wartezeit im Bild-Weg (9), nächster Schritt (10).
- **P3:** Kennwerte mit Einheit/Bedingung (18), Widersprüche (22), Abkürzungen (25), Export (27), Weg zum Menschen (14).

## Quellen

Laien: [L1] HAX Guidelines https://dl.acm.org/doi/10.1145/3290605.3300233 · [L2] Luger & Sellen https://www.microsoft.com/en-us/research/publication/like-having-a-really-bad-pa-the-gulf-between-user-expectation-and-experience-of-conversational-agents/ · [L4] NN/g Diary https://www.nngroup.com/articles/generative-ai-diary/ · [L5] Ashktorab et al. https://dl.acm.org/doi/10.1145/3290605.3300484 · [L7] OpenAI Model Spec https://model-spec.openai.com/ · [L8] PAIR Errors https://pair.withgoogle.com/chapter/errors-failing/ · [L9] NN/g Chatbot-Guidelines https://www.nngroup.com/articles/ai-chatbots-design-guidelines/ · [L11] userlutions https://userlutions.com/blog/usability-analyse/ki-chatbots-ux-tests/ · [L12] Gnewuch https://aisel.aisnet.org/sighci2018/14/ · [L13] lime https://connect.lime-technologies.com/de/blog/kunden-chatbots-studie/ · [L-B] Følstad & Skjuve https://link.springer.com/article/10.1007/s41233-020-00033-2 · AK Wien https://www.arbeiterkammer.at/beratung/konsument/HandyundInternet/Internet/Studie_Chatbots_2020.pdf

Wissenschaft: [W1] https://support.elicit.com/en/articles/3090497 · https://scispace.com/resources/chat-with-pdf-accuracy-2026-which-tools-cite-the-right-page/ · [W2] https://arxiv.org/html/2510.04749v1 · [W4] https://arxiv.org/html/2604.07584 · https://link.springer.com/article/10.1007/s40192-024-00362-6 · [W5] https://optyxstack.com/rag-reliability/why-your-rag-fails-on-pdf-tables-ocr-header-loss-row-boundary-fixes · https://arxiv.org/pdf/2506.16035 · [W6] https://scispace.com/help/en/articles/10719149-how-to-explain-math-and-tables-in-chat-with-pdf · [W7] https://arxiv.org/html/2405.08807 · [W8] https://direct.mit.edu/qss/article/2/3/882/102990/ · [W9] https://arxiv.org/pdf/2504.00180 · [W10] https://academictech.uchicago.edu/2026/04/06/google-notebooklm-an-ai-tool-for-research-and-studying/ · [W11] https://www.undermind.ai/whitepaper.pdf · [W12] https://arxiv.org/abs/2508.18093 · https://arxiv.org/html/2510.00908v1 · [W13] https://arxiv.org/pdf/2010.14678 · [W14] https://arxiv.org/pdf/2510.25055 · [W15] https://support.elicit.com/en/articles/1153857 · [W16] https://sr.ithaka.org/publications/making-ai-generative-for-higher-education/ · [W-B1] https://www.nature.com/articles/s41598-023-41032-5 · https://www.statnews.com/2026/05/07/lancet-study-finds-steep-rise-fraudulent-citations-academic-papers/ · [W-B2] https://arxiv.org/html/2602.21059 · https://arxiv.org/abs/2510.22242 · https://aarontay.substack.com/p/a-2025-deep-dive-of-consensus-promises

Technik: [T1] MTRAG https://arxiv.org/html/2501.03468 · https://github.com/IBM/mt-rag-benchmark · Gegenbefund Rewriting https://arxiv.org/html/2602.09552 · [T2] CORAL https://arxiv.org/html/2410.23090 · [T3] SemEval-2026 T8 https://research.ibm.com/publications/semeval-2026-task-8-mtrageval-evaluating-multi-turn-rag-conversations · [T4] Netflix Context-Switch https://arxiv.org/html/2605.09268 · [T5] LLMs get lost https://arxiv.org/pdf/2505.06120 · Intent Mismatch https://arxiv.org/pdf/2602.07338 · [T6] Feedback-Taxonomie https://arxiv.org/html/2507.23158v2 · [T7] Grounding https://arxiv.org/html/2311.09144 · RIFTS https://arxiv.org/pdf/2503.13975 · [T8] Klärfragen https://aclanthology.org/2025.acl-industry.63.pdf · Router https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades · Pinning https://docs.anythingllm.com/chatting-with-documents/introduction · ChatRAG-Bench https://huggingface.co/datasets/nvidia/ChatRAG-Bench · TopiOCQA https://aclanthology.org/2022.tacl-1.27.pdf · [T-D] DeepEval https://deepeval.com/guides/guides-multi-turn-evaluation-metrics · promptfoo https://www.promptfoo.dev/docs/configuration/chat/ · RAGAS https://docs.ragas.io/en/stable/howtos/applications/evaluating_multi_turn_conversations/

## Stand 26.08.2026 — umgesetzt

**Gesprächsführung (§1):** 1 Kontext dauerhaft je Faden ✅ · 2 Themenwechsel bei neuem Namen/Kennung ✅ · 3 Beschwerde/Zweifel → Reparatur Satz für Satz, bei Zusammenfassungs-Bitte Rückfrage „welche Aussage" ✅ · 4 Klärfrage mit Optionen bei leerem Faden ✅ · 5 „steht nicht drin" statt Ausweichen (Faden-Antwort, Bild) ✅ · 7 Tippfehler bei Verfassern (Beker→Becker) ✅ · 10 nächster Schritt unter Zusammenfassung/Faden-Antwort/Bild ✅ · 13 „Was kannst du?" beschreibt alle Fähigkeiten ✅ · 14 Weg zum Menschen (`KI4KI_KONTAKT`) ✅ · 12 Recap 🟡 (Fuß nennt das Faden-Dokument; kein eigener Recap-Zug) · 8/9 unverändert.

**Fachlich (§2):** 15 Fundstelle je Aussage ✅ (Faden-Antwort: wörtliche Zitate geprüft) · 17 Vergleich zweier Arbeiten als Tabelle mit Seite je Zelle, Denken an ✅ · 18 Kennwerte Wert·Einheit·Messbedingung·Seite, „fehlt" markiert ✅ · 22 Widersprüche (Bewertungsspalte, beide Zitate) ✅ · 25 Abkürzungen aus dem Dokument (deterministisch) ✅ · 27 Export BibTeX/CSV ✅ · 23 Themen-Nachbarn aus Katalog-Titeln 🟡 · 16/19/20/21/24/26/28 offen.

**Router (§4):** 1 Feedback-Gate mit Reparatur ✅ · 2 Pivot/Vertiefung ✅ · 3 Dokumentbezug vor Bestand (Veto gegen Auffangnetz) ✅ · 4 Klärfrage erzwungen ✅ · 5 kein freies Umschreiben ✅ · 6 Unanswerable-Pfad ✅ · 8 Konfidenz „Hoch" ohne geprüftes Zitat → „Mittel" ✅ · 7 Recap 🟡.

**Neu dazu:** Dokument-Fakten (Seiten/Abbildungen/Tabellen/Verfasser/Jahr) ohne Modell, einzeln oder als Tabelle über den Bereich · Fragen an die Anlage selbst („angedockt?") beantwortet der Proxy · Denken je Aufgabe (Vergleich, Widerspruch, Kennwerte) · Testreihe `pruef-proxy/dialogtest.py`: 17 Szenarien, 143 Prüfungen.


## 7 · Anforderungen aus den Partner-Unterlagen (Netzwerktreffen 2+3, Implementierungsleitfaden 141 S.)

Ausgewertet am 31.07.2026 (Session-Archiv), hier nachgetragen am 26.08., weil die Recherche
oben (§1–§6) generisch war und **nicht** gegen diese Unterlagen geprüft wurde. Der benannte
Pilot-Use-Case ist **nicht** „Fragen an Dissertationen", sondern:

> **UC 1: KI-gestützte Störfallassistenz** im Prozess **„Breakdown-to-Recovery"** —
> „sehr hoher Nutzen, hohe Prozessnähe, gute Datenbasis, beherrschbares Risiko,
> klarer MVP-Kandidat" (S. 102).

Damit ist der Zielzustand nicht mehr Auslegungssache. Konkret gefordert:

| Anforderung aus dem Leitfaden | Stand 31.07. → 26.08. |
|---|---|
| Antwort **immer mit Quellenbezug** (S. 103, 111, 115) | ✅ **besser als gefordert** — Belegprüfung + seitengenauer Sprung ins Original |
| „**Eskalation statt Schein-Sicherheit**", keine Antwort ohne Evidenz (S. 111) | ✅ vorhanden, inkl. „Wo nachgesehen wurde" |
| Human-in-the-loop, keine automatische Freigabe/Parametrierung (S. 109, 113) | ✅ per Bauart erfüllt |
| **„KI-Suche darf Berechtigungen nicht umgehen"** (S. 74) | ⚠ genau unser Rechteloch — produktiv geschlossen, **im Paket offen** |
| **Audit Gate: Logging aller Anfragen, Quellen und Antworten** (S. 100, 117, 139) | ⛔ **existiert nicht** |
| **Feedback im UI**: hilfreich / nicht hilfreich, Meldung falscher Quellen (S. 123, 128) | ⛔ existiert nicht |
| **Kontextparameter** Linie · Fehlercode · Symptom · Rolle werden mitgegeben (S. 115) | ⛔ heute freier Chat ohne Prozesskontext |
| **Metadaten je Wissensobjekt**: Freigabestatus, Owner, Version, Gültigkeit, Review-Zyklus (S. 51–55) | ⛔ keine Metadatenebene |
| Zustand **„Für KI ausschließen"** — Inhalt bleibt, wird aber nicht indexiert (S. 88, 95) | ⛔ heute wird alles indexiert |
| **Reaktionszeit < 5 Minuten** im Störfall (S. 60, 62) | ✅ 38–113 s |
| **KPIs**: Suchzeit bis zur ersten verwertbaren Quelle, MTTR, Eskalationsquote, Anteil quellenbasierter Antworten, Trefferquote, Nutzungsquote (S. 101, 105, 127) | ⛔ nichts davon wird gemessen |
| **Geregelte Re-Indexierung** bei Content-Änderungen, Incident-Prozess, Fallback (S. 117, 139) | teilweise (Zyklus/Wächter), nicht als Betriebsmodell |

**Der wichtigste inhaltliche Befund:** Die geforderten Wissensobjekte sind
**Known-Issue-Einträge, Troubleshooting Guides, Fehlerkataloge, Soll-Parameterblätter,
Schichtberichte und eine Expertenmatrix** (S. 46–47, 59–65) — überwiegend **strukturierte
Datensätze mit Metadaten**, ausdrücklich *keine* PDF-Sammlung. Die IKV-Bibliothek ist
Forschungsliteratur. Beides ist dieselbe Maschine, aber **nicht derselbe Bestand.**

**Und der Leitfaden warnt vor genau unserem Muster** (S. 7, 14, 82):
„KI verstärkt vorhandenes Wissen – sie ersetzt keine saubere Struktur, Ownership und
Methodik" · „Eine KI würde diese Unschärfen nicht lösen, sondern lediglich schneller
verbreiten" · „KI braucht nicht möglichst viel Content, sondern einen geprüften, führenden
und strukturierten Wissensbestand."

→ **Konsequenz für den Plan:** Der Bestand entscheidet, nicht die Antwortqualität. Ein
kleiner, sauber verschlagworteter Störfall-Bestand schlägt 1.259 Bibliotheks-PDFs.


**Stand 26.08. zu den fünf Arbeitspaketen K1–K5:** K1 Audit-Trail ✅ (Prüfprotokoll je Frage,
Kette, Verdikte) · K2 Feedback im UI ❌ · K3 Metadaten/„für KI ausschließen" ❌ · K4
Kontextparameter/Störfall-Modus ❌ · K5 KPI-Auswertung ❌ (Rohdaten im Protokoll vorhanden).

## K — Demonstrator-Anforderungen aus dem Leitfaden (bis 27.08.)

Diese fünf schließen die Lücken aus der Tabelle oben. **K1 und K2 sind Gate-Bedingungen**
des Leitfadens, keine Komfortfunktionen: ohne Logging kein bestandenes Audit Gate (S. 100).

| | Was | Warum |
|---|---|---|
| **K1** | **Audit-Trail**: jede Anfrage, jede herangezogene Quelle, jede Antwort, Zeitstempel, Konto, Bereich. Aufbewahrungsfrist konfigurierbar. Getrennt vom Chatverlauf, maschinenlesbar. | Audit Gate. Klärt zugleich die offene Frage aus den Rechteloch-Wellen: *was ist tatsächlich abgeflossen?* |
| **K2** | **Feedback im UI**: „hilfreich / nicht hilfreich" plus „falsche Quelle melden". Rückfluss in eine Liste, die jemand ansieht. | Nutzungs-KPI und der einzige Weg, an dem sich Content-Lücken zeigen (S. 128). |
| **K3** | **Metadatenebene je Dokument — Felder nicht erfinden, sie stehen fertig auf S. 86:** Relevanz · Gültigkeit · Aktualität · Freigabestatus · führende Quelle · dublettenfrei · Maschinenlesbarkeit · KI-Eignung · Rollenzuweisung. Dazu die sechs Zustände von S. 88 als Dokumentstatus: behalten · überarbeiten · konsolidieren · archivieren · löschen · **für KI ausschließen**. Retrieval filtert auf „freigegeben" **und** „für KI zugelassen". | Truth Gate + Freshness Gate. Ohne das ist jede Antwort so verbindlich wie der schlechteste Entwurf im Bestand. |
| **K4** | **Kontextparameter statt freier Chat**: Anlage/Linie, Fehlercode, Symptom, Rolle werden als Felder mitgegeben und ins Retrieval gehängt. Der siebte Fall der Einordnung wird damit `stoerfall`. | S. 115. Ist zugleich der sichtbarste Unterschied zu „noch ein Chatbot" in der Vorführung. |
| **K5** | **KPI-Erfassung** aus K1: Zeit bis zur ersten verwertbaren Quelle, Anteil quellenbasierter Antworten, Trefferquote, Eskalationsquote, Nutzungsquote. Eine Seite Auswertung. | Der Leitfaden macht die Go/No-Go-Entscheidung ausdrücklich an Zahlen fest (S. 124, 129). „Pilotbetrieb ohne Messung ist nur eine Demo" (S. 123). |

**Wo n8n zurückkommt — und zwar begründet.** Der Leitfaden verlangt durchgehend
*prozesseingebettete* Lösung, nicht Chatfenster: Anfrage aus dem Störfallkontext,
Kontextübergabe, Anbindung an CMMS/DMS/Schichtbuch, geregelte Re-Indexierung bei
Content-Änderungen, Feedback-Rückführung, Incident- und Supportprozess (S. 106–117, 139).
Das ist **exakt die Schicht, für die n8n da ist** — und sie ist heute die dünnste.
Die Hybrid-Festlegung vom 30.07. bleibt richtig: **Grafikkarte → Skripte, Anbindung und
Zeitsteuerung → n8n.** ⚠ Zu prüfen, nicht anzunehmen: ob der n8n-Ablauf gerade läuft;
laut Dokumentation ist er seit dem 30.07. wieder auf Stand (`mkmd-dienst`), nicht

**Konsequenz für die Gesprächsführung (§4):** Für Handbücher, Fehlerberichte und Prüfprotokolle
aus dem Labor braucht der Gesprächsmodus einen **Störfall-Weg**: Anlage/Fehlercode/Symptom als
Felder oder aus dem Satz erkannt → Suche in Fehlerkatalogen/Handbüchern → Antwort als Tabelle
Ursache · Maßnahme · Quelle (Seite) · Gültigkeit → bei Leerlauf **Eskalation** (Ansprechpartner)
statt Schein-Sicherheit. Der Bestand entscheidet: **ein kleiner, geprüfter Störfall-Bestand vor
dem Bau — nicht danach.**

## Stand 26.08.2026 (abends) — K1–K5 gebaut

| | Was | Wie es funktioniert | Prüfung |
|---|---|---|---|
| K1 | Audit-Trail | Prüfprotokoll je Frage (Konto pseudonym, Bereich, Faden, Quellen, Verdikt, Dauer, **Störfall-Kontext**), verkettet, 90 Tage | vorhanden, Ketten-Prüfung |
| K2 | Feedback | Daumen der Oberfläche werden am Proxy mitgeschrieben (`chat-feedback`-Route); Chat „Falsche Quelle: …" / „Feedback: …"; Liste unter `/rueckmeldungen` | Kennzahlen-Test |
| K3 | Metadaten | `dokumente/<bereich>/metadaten.json` (Freigabe, Owner, Version, Gültigkeit, `ki: nein`), `bereich.json` `nur_freigegebene` / `abgelaufene_ausschliessen`; greift in **jeder** Zugriffsprüfung (Listen, Suche, Zitat, Fundstellen-Link); Status und Warnung in Antworten | 10 Prüfungen |
| K4 | Störfall | Anlage/Fehlercode/Symptom aus Feldern oder Satz; Werkzeuge `stoerfall_suchen` + `bestand_durchsuchen` (Wortverzeichnis → Seitenwahl über alle Dokumente); Belege werden **vor** dem Modell geholt; Antwort als Tabelle Ursache · Maßnahme · Quelle · Gültigkeit; nichts Belegtes → Eskalation mit `KI4KI_KONTAKT` | Replay am Modell: Tabelle korrekt, Entwurf als „nicht freigegeben" markiert; ohne Treffer ehrliche Eskalation (1,2 s) |
| K5 | KPI | `/kpi`: quellenbasierte Antworten, Trefferquote, Eskalationsquote, Zeit bis zur ersten Quelle (Median je Faden), Störfälle, Rückmeldungen, Nutzung je Tag; `/kpi?format=json` | Kennzahlen-Test |

**Prüfungsfragen (AuW):** Optionen A–D (auch inline, auch Kleinbuchstaben) werden erkannt; je Option wird der Bestand **vorab** durchsucht, das Modell urteilt mit Denken und wörtlichem Vergleich. Replay: „Welche Aussage ist falsch? A) Mitteneinspannung erhöht die Lebensdauer …" → „A ist falsch — der Beleg sagt *verkürzt*" mit Zitaten, 4,7 s. Vorher (ohne Vorab-Belege) riet das Modell ein Dokument und erfand Zitate.

**Fußnoten:** eine `<sub>`-Zeile mit Quelle, Werkzeugen, geprüften Zitaten und Warnungen; Hinweise „Weiter: …" nur in den ersten zwei Zügen eines Fadens.

## Stand 26.08.2026 (nachts) — Prüfungskatalog, Nicht-PDF, Aufnahme-Zuordnung

**Befund (Bereich AuW, echter Faden):** „Kannst du mir Prüfungsfragen stellen?" → das Modell erfand
Fragen, Optionen und Zitate. Drei Ursachen, alle behoben:

1. **Die Excel kam nie in den Bestand.** Der Eintrag „Pruefungsfragen zu DVS 2291" trug den Text des
   Testfragen-PDFs (gleicher Hash). Ursache: Die Unterkette gibt je Datei ein Element zurück, die
   Hauptkette paarte **nach Position**; der Excel-Zweig lieferte nichts (kein `fileExtension` übergeben,
   Zeilen statt Text), also verschob sich die Zuordnung. Jetzt: `fileExtension` wird explizit übergeben,
   **ein Knoten „Nicht-PDF vereinheitlichen"** macht aus Excel/CSV/HTML/Text/Tika genau ein Element mit
   `docling_filename`, die Hauptkette paart **nach Dateinamen** (Position nur als Rückfall). Word,
   PowerPoint und alles Unbekannte laufen über **Tika** statt still zu verschwinden.
2. **Werkzeuge kannten nur PDF-Seiten.** `seiten_lesen`, `bestand_durchsuchen`, `abkuerzung` und die
   Aussagen-Prüfung lesen jetzt für Dokumente ohne PDF den Bestandstext (Seitenmarken `[Seite n]`,
   sonst eine Seite). Seitenbilder/Abbildungen gibt es dafür ehrlich nicht.
3. **Prüfungsfragen sind jetzt deterministisch** (`pruefungskatalog.py`, vor Stufe 1/2 im Proxy):
   Katalog erkennen (Tabelle mit `Frage | Antwort richtig | Antwort falsch …` oder a)/b)/c)-Blöcke),
   Frage **wörtlich** stellen (Optionen gemischt, Nr./Thema/LE), Antwort **gegen den Katalog** prüfen,
   Zustand je Faden (`notiz`), „weiter", „Frage 7", „zum Thema X", „warum?" → Gesprächsmodus mit dem
   Katalogeintrag als Vorwissen. Für das Modell zusätzlich Werkzeug `pruefungsfrage` + Regel 16.
   Ohne Lösungsspalte (gescannte Testbögen) wird **kein Urteil erfunden**.

Außerdem: **Bestandsliste** — liefert das Werkzeug die Tabelle mit Links und das Modell macht Fließtext
daraus, gilt die Tabelle. **Belege-Wächter für alle Kennungen** („(DVS 2213-1_neu, S. 12)"), nicht nur
`DS-24-xxx`; Klammertext ohne Dokumentbezug bleibt unangetastet.

Prüfung: `dialogtest.py` Szenario 24 (26 Prüfungen), Replay des Parsers gegen die echten AuW-Texte auf
der A40 (Testfragen-Scan: 12 Fragen erkannt, Werkzeugliste/Leitfaden: kein Katalog). Offen: Excel neu
aufnehmen (in `loeschen/`, dann wieder nach `input/`), Live-Faden mit dem echten Katalog.

**Nachtrag Phase 0 (Emrach: „auf der T4 wurden doc/pptx/xlsx vorher nach PDF gewandelt — geschieht das noch?"):**
Nein, das fehlte im Paket. Jetzt `office-dienst` (LibreOffice Writer+Impress, nur im Docker-Netz):
WF2 wandelt Word/PowerPoint vor Docling nach PDF und legt die PDF neben das Original ins Archiv
(`X-Ziel`, Rechte 664 · 1000:GID); der Original-Dateiname bleibt der Schlüssel (Paarung in WF1).
Excel/CSV wie auf der T4 **nicht** — Tabellen bleiben Tabellen. Index-Spalte „Art" zeigt „Word → PDF · n S.".

## Stand 27.08.2026 — Rolle je Bereich (Prompt-Generator)
Kern (`systemprompt.txt`) + Rolle (`dokumente/<bereich>/prompt.md`). Rolle entsteht im Chat aus drei
Fragen („Rolle einrichten", nur Konten mit Einsichtsrecht) oder per `arbeitsbereich_anlegen.sh`; Regeln
werden ohne Modell aus den Antworten abgeleitet (Prüfung/Norm/Sicherheit/Störfall/Wissenschaft/Sprache).
Der Proxy spielt Änderungen an der Datei alle 5 Minuten in AnythingLLM ein (`_rolle_einspielen`) und gibt
sie dem Gesprächsmodus als Abschnitt „ROLLE DIESES BEREICHS" mit. `prompt_aktualisieren.sh` rollt Kern +
Rolle je Bereich aus. Begründung: T4 hatte je Bereich 4 500–6 200 Zeichen Prompt, nur in der Datenbank,
nur von Hand — nicht partnertauglich.
