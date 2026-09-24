// Faehrt die geaenderten Code-Bausteine von Ablaufplan 1 mit erfundenen
// Eingaben durch - ohne n8n, ohne Bestand, ohne Kundendaten.
//   node aufnahmetest.js  [pfad-zur-workflow-json]
const fs = require('fs');
const P = process.argv[2] ||
  '/tmp/claude-1000/-home-runlvl89/b80e3ade-1035-419c-9733-360f6be0bd17/scratchpad/repo/n8n-workflows/1_KI4KI-Masse-Ingest.json';
const wf = JSON.parse(fs.readFileSync(P, 'utf8'));
const code = {};
for (const n of wf.nodes) if (n.parameters && n.parameters.jsCode) code[n.name] = n.parameters.jsCode;

let fehler = 0;
const pruefe = (b, t) => { console.log((b ? '  ok   ' : '  FEHL ') + t); if (!b) fehler++; };

async function fahre(name, umgebung) {
  if (!code[name]) { console.log('  FEHL Baustein "' + name + '" gibt es in dieser Fassung nicht'); fehler++; return []; }
  const f = new Function('$input', '$', '$now', 'console',
    '"use strict"; return (async () => {\n' + code[name] + '\n})();');
  return await f.call({ helpers: umgebung.helpers || {} },
    umgebung.$input, umgebung.$, umgebung.$now, umgebung.console || { log() {}, error() {} });
}

const datei = (dir, name, json) => ({ json: json || {}, binary: { data: { directory: dir, fileName: name } } });
const DIR = '/files/dokumente/kap/input/KundeA';

(async () => {
  // ---------------------------------------------------------------- 1
  console.log('\n1) "Nur ein Bereich je Durchgang" - erkennt die mitgelieferte PDF');
  const eingang = [
    datei(DIR, 'Angebot.docx'), datei(DIR, 'Angebot.pdf'),
    datei(DIR, 'Zeichnung.pdf'), datei(DIR, 'bilder-nachholen.txt'),
    datei('/files/dokumente/kap/input/KundeB', 'Angebot.pdf'),
  ];
  const r1 = await fahre('Nur ein Bereich je Durchgang', {
    $input: { all: () => eingang },
    $: (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
  });
  const marke = {};
  for (const e of r1) marke[e.binary.data.directory + '/' + e.binary.data.fileName] = e.json.belegquelle === true;
  pruefe(r1.length === 4, '1a Buchhaltung (bilder-nachholen.txt) faellt raus, 4 uebrig (%d)'.replace('%d', r1.length));
  pruefe(marke[DIR + '/Angebot.pdf'] === true, '1b PDF neben dem Word-Original ist als Belegquelle markiert');
  pruefe(marke[DIR + '/Angebot.docx'] === false, '1c das Original selbst ist KEINE Belegquelle');
  pruefe(marke[DIR + '/Zeichnung.pdf'] === false, '1d Gegenprobe: PDF ohne Original bleibt unmarkiert');
  pruefe(marke['/files/dokumente/kap/input/KundeB/Angebot.pdf'] === false,
         '1e Gegenprobe: gleicher Name in einem ANDEREN Ordner zaehlt nicht');

  // ---------------------------------------------------------------- 2
  console.log('\n2) "Code" - Positivliste und Belegquelle VOR dem Upload');
  const quellen = [
    datei(DIR, 'Angebot.docx'), datei(DIR, 'Angebot.pdf'),
    datei(DIR, 'Post.msg'), datei(DIR, 'Messung.001'), datei(DIR, 'Leer.pdf'),
  ];
  const roh = quellen.map((q, i) => ({ json: {
    docling_filename: q.binary.data.fileName,
    data: q.binary.data.fileName === 'Leer.pdf' ? '' : 'Ein hinreichend langer Text zum Pruefen.',
  } }));
  // Der Schluessel-Dienst, nachgebildet: die PDF neben dem Original traegt
  // dessen Schluessel und ist nur_beleg.
  const dienst = { helpers: { httpRequest: async (o) => ({
    schluessel: o.body.dateien.map(x => {
      const beleg = x.unterpfad === 'KundeA/Angebot.pdf';
      // Der TRAEGER bestimmt Schluessel UND Abdruck - genau wie in
      // mkmd_dienst.eintrag_rechnen.
      const q = beleg ? 'KundeA/Angebot.docx' : x.unterpfad;
      const ab = 'ab' + q.replace(/\W+/g, '').toLowerCase().slice(-8);
      return { bereich: x.bereich, unterpfad: x.unterpfad,
               schluessel: 'kap-' + q.replace(/\W+/g, '-') + '--' + ab,
               abdruck: ab,
               nur_beleg: beleg, traeger: beleg ? 'KundeA/Angebot.docx' : '' };
    }), fehler: [] }) } };
  const r2 = await fahre('Code', Object.assign({
    $input: { all: () => roh },
    $: (n) => ({ all: () => (n === 'Dateien in JSON umwandeln' ? roh : quellen),
                 first: () => ({ json: { karte: { kap: 'kap' } } }) }),
  }, dienst));
  const nach = {}; for (const e of r2) nach[e.json.filename] = e.json;
  pruefe(nach['Angebot.pdf'].abdruck === nach['Angebot.docx'].abdruck,
         '2a Belegquelle und Original tragen denselben Abdruck');
  pruefe(nach['Angebot.pdf'].hochladen === false, '2b Belegquelle wird nicht hochgeladen');
  pruefe(nach['Angebot.docx'].hochladen === true, '2c das Original schon');
  pruefe(nach['Post.msg'].hochladen === false, '2d Korrespondenz wird nicht hochgeladen');
  pruefe(nach['Messung.001'].hochladen === false, '2e unvorgesehenes Format wird nicht hochgeladen');
  pruefe(nach['Leer.pdf'].hochladen === false, '2f Datei ohne Text wird nicht hochgeladen');
  pruefe(nach['Angebot.docx'].vormerk_path === '/files/dokumente/kap/bilder-nachholen.txt',
         '2g Vormerkliste zeigt auf den BEREICH');

  // ---------------------------------------------------------------- 3
  console.log('\n3) "Nur Dokumente hochladen" - der Filter vor dem Upload');
  const r3 = await fahre('Nur Dokumente hochladen', { $input: { all: () => r2 } });
  pruefe(r3.length === 1 && r3[0].json.filename === 'Angebot.docx',
         '3a von fuenf Dateien geht genau das Original in den Upload (%d)'.replace('%d', r3.length));

  // ---------------------------------------------------------------- 4
  console.log('\n4) "Ablage entscheiden" - Ort und Befehl');
  const eingebettet = [{ json: { workspace: { documents: [
    { docpath: 'kap/' + nach['Angebot.docx'].schluessel.replace(/\.[^.]+$/, '') +
               '.md-11111111-2222-3333-4444-555555555555.json' }] } } }];
  const r4 = await fahre('Ablage entscheiden', {
    $input: { all: () => eingebettet },
    $: (n) => ({ all: () => (n === 'Code' ? r2 : quellen),
                 first: () => ({ json: { stdout: 'MASSENLAUF: 99 Dateien' } }) }),
    $now: { toFormat: () => '2026-09-24 12:00:00' },
  });
  const zus = r4[0].json;
  const proDatei = {}; for (const x of zus.dokumente) proDatei[x.datei] = x;
  pruefe(proDatei['Angebot.docx'].ziel === 'archiv', '4a das Original geht ins Archiv');
  pruefe(proDatei['Angebot.pdf'].ziel.indexOf('Belegquelle') !== -1,
         '4b die Belegquelle geht ins Archiv, als Belegquelle gekennzeichnet');
  pruefe(proDatei['Post.msg'].ziel === 'aussortiert' && proDatei['Messung.001'].ziel === 'aussortiert'
         && proDatei['Leer.pdf'].ziel === 'aussortiert', '4c die drei Nicht-Dokumente gehen nach aussortiert');
  pruefe(zus.befehl.indexOf('/files/dokumente/kap/bilder-nachholen.txt') !== -1,
         '4d die Vormerkliste wird im Bereich gefuehrt');
  pruefe(zus.befehl.indexOf('$(dirname "$(dirname') === -1,
         '4e Gegenprobe: das alte zweifache dirname kommt nicht mehr vor');
  pruefe(/if \[ -e .*Angebot\.pdf.* \]; then/.test(zus.befehl),
         '4f die Belegquelle ueberschreibt eine vorhandene Wandlung nicht');
  pruefe(zus.befehl.indexOf('bilder-nachholen.txt" && printf') === -1
         && !/Angebot\.pdf"? >> "?\/files\/dokumente\/kap\/bilder-nachholen/.test(zus.befehl),
         '4g Gegenprobe: die Belegquelle steht NICHT in der Vormerkliste');

  console.log('\n' + fehler + ' Fehler');
  process.exit(fehler ? 1 : 0);
})().catch(e => { console.error('ABBRUCH:', e); process.exit(2); });
