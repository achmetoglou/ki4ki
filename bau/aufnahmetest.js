// Faehrt die geaenderten Code-Bausteine von Ablaufplan 1 mit erfundenen
// Eingaben durch - ohne n8n, ohne Bestand, ohne Kundendaten.
//   node aufnahmetest.js  [pfad-zur-workflow-json]
const fs = require('fs');
const path = require('path');
// ⛔ Hier stand ein fester Pfad in ein /tmp-Arbeitsverzeichnis - auf dem
//   echten Rechner (~/ki4ki) war die Probe damit ohne Argument gar nicht
//   lauffaehig. Gesucht wird der Plan jetzt neben dem Skript.
const P = process.argv[2] ||
  path.join(__dirname, '..', 'n8n-workflows', '1_KI4KI-Masse-Ingest.json');
const wf = JSON.parse(fs.readFileSync(P, 'utf8'));
const code = {};
const shell = {};
for (const n of wf.nodes) {
  if (n.parameters && n.parameters.jsCode) code[n.name] = n.parameters.jsCode;
  // Die Befehls-Bausteine tragen ihren Text in 'command'. Er laesst sich
  // nicht ausfuehren (er verschiebt Dateien), aber lesen und pruefen.
  if (n.parameters && n.parameters.command) shell[n.name] = n.parameters.command;
}

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
const JETZT = { toFormat: () => '2026-10-05 08:00:00' };
// Eine Konsole, die mitschreibt - das Protokoll ist Teil des Ergebnisses.
const mitschrift = () => { const z = []; return { z, log: (...a) => z.push(a.join(' ')), error: () => {} }; };

// ⭐ EINE QUELLE, ZWEI LESER. Die Positivliste der vorgesehenen Endungen
//   steht im Baustein "Nur ein Bereich je Durchgang" - dort, wo auch der
//   Wegraeum-Befehl entsteht. "Code" liest sie von dort. Diese Probe baut
//   sie deshalb NICHT nach, sondern faehrt erst den besitzenden Baustein und
//   reicht dessen echte Ausgabe weiter. Eine zweite Liste in der Probe waere
//   genau die doppelte Wahrheit, vor der der Ablaufplan warnt.
const filterLaufen = async (eingang, konsole) => await fahre('Nur ein Bereich je Durchgang', {
  $input: { all: () => eingang },
  $: () => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
  $now: JETZT, console: konsole || { log() {}, error() {} },
});
// Der $-Platzhalter fuer "Code": Listen vom Filter, Bereichskarte wie gehabt.
const codeUmgebung = (vomFilter, roh, quellen) => ({
  $input: { all: () => roh },
  $: (n) => ({ all: () => (n === 'Dateien in JSON umwandeln' ? roh : quellen),
               first: () => (n === 'Nur ein Bereich je Durchgang'
                 ? vomFilter : { json: { karte: { kap: 'kap' } } }) }),
});

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
    $now: JETZT,
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
  const vomFilter2 = (await filterLaufen(quellen))[0];
  const r2 = await fahre('Code', Object.assign(
    codeUmgebung(vomFilter2, roh, quellen), dienst));
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

  // ---------------------------------------------------------------- 5
  // ⛔ DER BEFUND vom 05.10.: Vier 'bilder-nachholen.txt' lagen elf Tage im
  //   Eingang. Sie wurden in JEDEM Durchgang richtig als Nicht-Dokument
  //   erkannt - und in jedem Durchgang nur uebersprungen. Rund 3.000
  //   Leerlaeufe. Hier wird geprueft, dass sie den Eingang jetzt verlassen.
  console.log('\n5) "Nur ein Bereich je Durchgang" - Nicht-Dokumente verlassen den Eingang');
  const UNTER = '/files/dokumente/kap/input/KundeA/Unterordner';
  const eingang5 = [
    datei(DIR, 'Angebot.docx'),
    datei(DIR, 'bilder-nachholen.txt'),          // Buchhaltung der Anlage
    datei(UNTER, 'Thumbs.db'),                   // Ordner-Merkdatei, tiefer Ordner
    datei('/files/dokumente/awu/input', '~$Folien.pptx'),  // Sperrdatei, anderer Bereich
    datei(DIR, 'Zeichnung.pdf'),
  ];
  const mit5 = mitschrift();
  const r5 = await fahre('Nur ein Bereich je Durchgang', {
    $input: { all: () => eingang5 },
    $: (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
    $now: JETZT, console: mit5,
  });
  const ABFALL = ['bilder-nachholen.txt', 'Thumbs.db', '~$Folien.pptx'];
  const namen5 = r5.map(e => (e.binary && e.binary.data.fileName) || '');
  const auf5 = String((r5[0] && r5[0].json && r5[0].json.aufraeumen) || '');
  pruefe(r5.length === 2 && !ABFALL.some(n => namen5.indexOf(n) !== -1),
         '5a kein Nicht-Dokument geht in die Kette (uebrig: ' + namen5.join(', ') + ')');
  pruefe(auf5.indexOf('mv -f "' + UNTER + '/Thumbs.db" ' +
                      '"/files/dokumente/kap/aussortiert/KundeA/Unterordner/Thumbs.db"') !== -1,
         '5b der Unterordner bleibt erhalten: KundeA/Unterordner/Thumbs.db');
  pruefe(auf5.indexOf('mv -f "' + DIR + '/bilder-nachholen.txt" ' +
                      '"/files/dokumente/kap/aussortiert/KundeA/bilder-nachholen.txt"') !== -1,
         '5c die gemeldete Datei wird nach <bereich>/aussortiert/ verschoben');
  pruefe(auf5.indexOf('kein Dokument (Buchhaltung der Anlage)') !== -1
         && auf5.indexOf('kein Dokument (Ordner-Merkdatei)') !== -1
         && auf5.indexOf('kein Dokument (Office-Sperrdatei)') !== -1,
         '5d die ART steht als Grund im Protokoll');
  pruefe(auf5.indexOf('>> "/files/dokumente/kap/aussortiert/aussortiert.log"') !== -1
         && auf5.indexOf('>> "/files/dokumente/awu/aussortiert/aussortiert.log"') !== -1,
         '5e der Grund landet im aussortiert.log DES JEWEILIGEN Bereichs');
  // ⚠ Die drei Gegenproben verlangen ZUERST, dass ueberhaupt ein Befehl da
  //   ist. Ohne das waeren sie gegen eine Fassung, die gar nichts wegraeumt,
  //   gruen - eine Pruefung, die nie rot werden kann, prueft nichts.
  pruefe(auf5.length > 0 && auf5.indexOf('/input/aussortiert/') === -1,
         '5f Gegenprobe: kein Ziel unterhalb von input/ (der doppelte dirname)');
  pruefe(auf5.length > 0 && auf5.indexOf('"/files/dokumente/kap/aussortiert/Thumbs.db"') === -1,
         '5g Gegenprobe: der Unterordner wird NICHT plattgemacht');
  pruefe(auf5.length > 0 && auf5.indexOf('mv -n ') === -1,
         '5h Gegenprobe: kein mv -n - es taete bei vorhandenem Ziel still nichts');
  pruefe(/3 keine Dokumente \(alle Bereiche\) - davon 3 in diesem Durchgang nach aussortiert\//
           .test(mit5.z.join('\n')),
         '5i der Zaehler kein_dokument steht im Protokoll');

  // Bis zum Upload durchgerechnet: Was dieser Baustein nicht weiterreicht,
  // kann der Uploader nicht sehen.
  const dienst5 = { helpers: { httpRequest: async (o) => ({
    schluessel: o.body.dateien.map(x => ({
      bereich: x.bereich, unterpfad: x.unterpfad,
      schluessel: 'kap-' + x.unterpfad.replace(/\W+/g, '-'),
      abdruck: 'ab' + x.unterpfad.replace(/\W+/g, '').toLowerCase().slice(-8),
      nur_beleg: false, traeger: '' })), fehler: [] }) } };
  const roh5 = r5.map(q => ({ json: {
    docling_filename: q.binary.data.fileName,
    data: 'Ein hinreichend langer Text zum Pruefen.' } }));
  const r5code = await fahre('Code', Object.assign(
    codeUmgebung(r5[0], roh5, r5), dienst5));
  const hoch5 = (await fahre('Nur Dokumente hochladen', { $input: { all: () => r5code } }))
    .map(e => e.json.filename);
  pruefe(hoch5.length === 2 && !ABFALL.some(n => hoch5.indexOf(n) !== -1),
         '5j bis zum Upload gerechnet: kein Nicht-Dokument dabei (' + hoch5.join(', ') + ')');

  // ---------------------------------------------------------------- 6
  // ⛔ DER SCHWERE FALL: Im Eingang liegt NUR Abfall. Genau so war es elf
  //   Tage lang. Haenge man den Weg wie bei der Belegquelle an "Ablage
  //   entscheiden", gaebe "Nur Dokumente hochladen" eine leere Liste
  //   zurueck, die Schleife liefe nicht an - und die Sperre bliebe gesetzt.
  console.log('\n6) Nur Abfall im Eingang - aufraeumen OHNE Sperre');
  const mit6 = mitschrift();
  const r6 = await fahre('Nur ein Bereich je Durchgang', {
    $input: { all: () => [datei(DIR, 'bilder-nachholen.txt'), datei(DIR, '.DS_Store')] },
    $: (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
    $now: JETZT, console: mit6,
  });
  pruefe(r6.length === 1 && r6[0].json.nur_aufraeumen === true && !r6[0].binary,
         '6a genau ein Auftrags-Element ohne Datei geht weiter (' + r6.length + ')');
  // Ohne Klammergriff: Gegen die alte Fassung ist r6 leer, und die Pruefung
  // soll rot werden - nicht die ganze Probe abbrechen.
  pruefe(String((r6[0] && r6[0].json && r6[0].json.aufraeumen) || '')
           .indexOf('bilder-nachholen.txt') !== -1,
         '6b es traegt den Wegraeum-Befehl');
  const sp = String(shell['Sperre setzen'] || '');
  pruefe(sp.indexOf('{{ $json.aufraeumen') !== -1,
         '6c "Sperre setzen" fuehrt den Befehl aus');
  pruefe(sp.indexOf('$json.nur_aufraeumen === true') !== -1
         && sp.indexOf('KI4KI-ABBRUCH: Im Eingang lagen nur Nicht-Dokumente') !== -1,
         '6d und bricht danach ab, wenn es sonst nichts zu tun gab');
  // Auch hier: erst da sein, dann an der richtigen Stelle stehen.
  pruefe(sp.indexOf('{{ $json.aufraeumen') >= 0
         && sp.indexOf('$json.nur_aufraeumen === true') >= 0
         && sp.indexOf('{{ $json.aufraeumen') < sp.indexOf('mkdir "$L"')
         && sp.indexOf('$json.nur_aufraeumen === true') < sp.indexOf('mkdir "$L"'),
         '6e beides steht VOR dem Setzen der Sperre - sonst bliebe sie liegen');
  pruefe(sp.indexOf('{{ $json.aufraeumen') >= 0
         && sp.indexOf('{{ $json.aufraeumen') < sp.indexOf('find /files/dokumente/*/input'),
         '6f und vor der Leerlauf-Pruefung, damit "Eingang leer" dann auch stimmt');
  // ⚠ Mit Fangnetz: Ohne die ABBRUCH-Wache wirft dieser Baustein ("Nach der
  //   Sperre keine Dateien mehr da"). Das soll die Pruefung ROT machen, nicht
  //   die ganze Probe abbrechen.
  let r6ab;
  try {
    r6ab = await fahre('Dateien zurueckholen', {
      $input: { first: () => ({ json: { stdout:
        'KI4KI-ABBRUCH: Im Eingang lagen nur Nicht-Dokumente - weggeraeumt, kein Durchgang noetig.' } }) },
      $: (n) => ({ all: () => [] }),
    });
  } catch (e) { r6ab = 'Wurf: ' + e.message; }
  pruefe(Array.isArray(r6ab) && r6ab.length === 0,
         '6g "Dateien zurueckholen" beendet den Zweig still - ohne Wurf, ohne Sperre');

  // ---------------------------------------------------------------- 7
  console.log('\n7) Gegenproben - nicht mehr wegraeumen als noetig');
  const r7 = await fahre('Nur ein Bereich je Durchgang', {
    $input: { all: () => [datei(DIR, 'Angebot.docx'), datei(DIR, 'Zeichnung.pdf')] },
    $: (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
    $now: JETZT,
  });
  pruefe(r7.length === 2 && r7[0].json.aufraeumen === undefined,
         '7a ohne Nicht-Dokumente entsteht gar kein Wegraeum-Befehl');
  const mit7 = mitschrift();
  const r7b = await fahre('Nur ein Bereich je Durchgang', {
    // Der Parkplatz ist Kundenbestand - dort steht kein 'input' im Pfad.
    $input: { all: () => [datei('/files/dokumente/kap/parkplatz/KundeA', 'Thumbs.db'),
                          datei(DIR, 'Angebot.docx')] },
    $: (n) => ({ first: () => ({ json: { localFiles: { items: [] } } }) }),
    $now: JETZT, console: mit7,
  });
  pruefe(r7b.length === 1 && r7b[0].json.aufraeumen === undefined
         && mit7.z.join('\n').indexOf('1 ohne input/ im Pfad liegen gelassen') !== -1,
         '7b ausserhalb von input/ wird NICHTS verschoben, aber gezaehlt');

  // ---------------------------------------------------------------- 8
  // ⛔ DER BEFUND vom 05.10., zweiter Teil: Eine Charge aus lauter nicht
  //   vorgesehenen Endungen (jpg, tif, asc, tsx ...) fiel durch ALLE Siebe
  //   dieses Bausteins und wurde erst hinter dem Upload in "Ablage
  //   entscheiden" weggeraeumt. Besteht die Charge NUR aus solchen Dateien,
  //   liefert "Nur Dokumente hochladen" ein leeres [], die Schleife laeuft
  //   nicht an, "Ablage entscheiden" und "Sperre freigeben" laufen nie -
  //   die Sperre bleibt bis zum 120-Minuten-Notnagel liegen, und danach
  //   wiederholt sich dieselbe Charge identisch.
  //   Nachgerechnet an der echten Dateiliste: 85 von 247 Durchgaengen (34 %)
  //   enthalten kein einziges hochladbares Dokument, der erste als Nr. 3.
  console.log('\n8) Eine Charge aus lauter unvorgesehenen Endungen (25x .jpg)');
  const eingang8 = [];
  for (let i = 1; i <= 25; i++) eingang8.push(datei(DIR, 'Foto_' + i + '.jpg'));
  const mit8 = mitschrift();
  const r8 = await filterLaufen(eingang8, mit8);
  const auf8 = String((r8[0] && r8[0].json && r8[0].json.aufraeumen) || '');
  const mv8 = (auf8.match(/mv -f /g) || []).length;
  pruefe(r8.length === 1 && r8[0].json.nur_aufraeumen === true && !r8[0].binary,
         '8a die Charge macht die Schleife nicht leer - ein Auftrags-Element '
         + 'statt 25 Dateien (' + r8.length + ')');
  pruefe(mv8 === 25, '8b alle 25 Dateien verlassen den Eingang (' + mv8 + ')');
  pruefe(auf8.indexOf('"/files/dokumente/kap/aussortiert/KundeA/Foto_7.jpg"') !== -1,
         '8c sie landen in <bereich>/aussortiert/, der Unterordner bleibt');
  pruefe(auf8.indexOf('Format nicht vorgesehen (.jpg)') !== -1,
         '8d der Grund nennt die Endung - nicht "kein Dokument"');
  pruefe(auf8.indexOf('>> "/files/dokumente/kap/aussortiert/aussortiert.log"') !== -1,
         '8e und steht im aussortiert.log des Bereichs');
  pruefe(mit8.z.join('\n').indexOf('Nur Abfall im Eingang') !== -1,
         '8f das Protokoll sagt, dass dieser Durchgang nur aufraeumt');
  // ⛔ Und der Weg danach: "Sperre setzen" raeumt auf und bricht ab, OHNE
  //   die Sperre zu setzen. Ohne das bliebe genau hier die Sperre liegen.
  const sp8 = String(shell['Sperre setzen'] || '');
  pruefe(sp8.indexOf('{{ $json.aufraeumen') >= 0
         && sp8.indexOf('{{ $json.aufraeumen') < sp8.indexOf('mkdir "$L"'),
         '8g der Wegraeum-Befehl laeuft VOR der Sperre');

  // ---------------------------------------------------------------- 9
  // ⛔ DIE GEGENPROBE. Wer die Positivliste zu scharf zieht, raeumt den
  //   Bestand weg - und das faellt erst auf, wenn er weg ist.
  console.log('\n9) Gegenprobe - eine gemischte Charge verliert kein Dokument');
  const GUT = ['Bericht.pdf', 'Angebot.docx', 'Liste.txt', 'Werte.xlsm',
               'Praesentation.odp', 'Notiz.md', 'Seite.htm'];
  const WEG = ['Foto.jpg', 'Messung.tra', 'Anbau.tsx'];
  const eingang9 = GUT.concat(WEG).concat(['Post.msg'])
    .map(n => datei(DIR, n));
  const r9 = await filterLaufen(eingang9);
  const namen9 = r9.map(e => (e.binary && e.binary.data.fileName) || '');
  const auf9 = String((r9[0] && r9[0].json && r9[0].json.aufraeumen) || '');
  pruefe(GUT.every(n => namen9.indexOf(n) !== -1),
         '9a alle vorgesehenen Dateien gehen weiter (' + namen9.join(', ') + ')');
  pruefe(auf9.length > 0 && GUT.every(n => auf9.indexOf(n) === -1),
         '9b ⛔ und KEINE davon steht im Wegraeum-Befehl');
  pruefe(WEG.every(n => namen9.indexOf(n) === -1 && auf9.indexOf(n) !== -1),
         '9c nur die unvorgesehenen Endungen werden geraeumt');
  // ⚠ Korrespondenz (.msg/.eml) ist bewusst NICHT betroffen: Sie ist
  //   erkannt und vertagt und bekommt in "Ablage entscheiden" ihre eigene
  //   Begruendung. Wer das aendert, aendert eine Entscheidung vom 22.09.
  pruefe(namen9.indexOf('Post.msg') !== -1 && auf9.indexOf('Post.msg') === -1,
         '9d Korrespondenz bleibt unberuehrt (eigene Behandlung, 22.09.)');
  // Bis zum Upload durchgerechnet - die Charge ist eben NICHT leer.
  const dienst9 = { helpers: { httpRequest: async (o) => ({
    schluessel: o.body.dateien.map(x => ({
      bereich: x.bereich, unterpfad: x.unterpfad,
      schluessel: 'kap-' + x.unterpfad.replace(/\W+/g, '-'),
      abdruck: 'ab' + x.unterpfad.replace(/\W+/g, '').toLowerCase().slice(-8),
      nur_beleg: false, traeger: '' })), fehler: [] }) } };
  const roh9 = r9.map(q => ({ json: {
    docling_filename: q.binary.data.fileName,
    data: 'Ein hinreichend langer Text zum Pruefen.' } }));
  const r9code = await fahre('Code', Object.assign(
    codeUmgebung(r9[0], roh9, r9), dienst9));
  const hoch9 = (await fahre('Nur Dokumente hochladen', { $input: { all: () => r9code } }))
    .map(e => e.json.filename);
  pruefe(hoch9.length === GUT.length && GUT.every(n => hoch9.indexOf(n) !== -1),
         '9e bis zum Upload gerechnet: genau die vorgesehenen Dokumente '
         + '(' + hoch9.join(', ') + ')');
  pruefe(String((r9[0].json || {}).vorgesehen_liste || r9code[0].json.vorgesehen_liste || '')
           .indexOf('xlsm') !== -1,
         '9f "Ablage entscheiden" bekommt die Liste weiterhin als Text');

  // ---------------------------------------------------------------- 10
  // ⛔ DAS FAIL-CLOSED MUSS ZUFALLEN, NICHT AUFFALLEN.
  //   "Code" traegt onError: "continueRegularOutput". n8n reicht in dem Fall
  //   die EINGANGSDATEN unveraendert weiter (workflow-execute.js bei
  //   continuesOnError) - ein `throw` wirkt hier also nicht wie ein Riegel,
  //   sondern wie ein Durchlass: Die Elemente kaemen ohne jede Marke bei
  //   "Nur Dokumente hochladen" an, und dessen Filter prueft
  //   `hochladen !== false` - undefined ist nicht false. Gemessen vor der
  //   Reparatur: 4 von 4 unmarkierten Elementen gingen in den Upload.
  //   Deshalb wird der Riegel in die DATEN geschrieben, nicht in den
  //   Kontrollfluss.
  // ⛔ onError: "stopWorkflow" waere falsch: "Code" liegt zwischen
  //   "Sperre setzen" und "Sperre freigeben" - ein echter Abbruch liesse die
  //   Sperre bis zum 120-Minuten-Notnagel liegen (der Fehler vom 04.08.).
  console.log('\n10) Positivliste kommt nicht an - der Riegel faellt ZU');
  const knotenCode = wf.nodes.find(n => n.name === 'Code') || {};
  pruefe(knotenCode.onError === 'continueRegularOutput',
         '10a Kontrolle: "Code" laeuft bei Fehler weiter - deshalb darf er nicht werfen'
         + ' (ist: ' + knotenCode.onError + ')');
  const quellen10 = ['Messung.tra', 'Post.msg', 'Leer.pdf', 'Beleg.pdf']
    .map(n => datei(DIR, n));
  const roh10 = quellen10.map(q => ({ json: {
    docling_filename: q.binary.data.fileName,
    data: 'Ein hinreichend langer Text zum Pruefen.' } }));
  const dienst10 = { helpers: { httpRequest: async (o) => ({
    schluessel: o.body.dateien.map(x => ({
      bereich: x.bereich, unterpfad: x.unterpfad,
      schluessel: 'kap-' + x.unterpfad.replace(/\W+/g, '-'),
      abdruck: 'ab' + x.unterpfad.replace(/\W+/g, '').toLowerCase().slice(-8),
      nur_beleg: false, traeger: '' })), fehler: [] }) } };
  // Der besitzende Baustein hat die Listen NICHT mitgeliefert (leeres json).
  const ohneListen = Object.assign(
    codeUmgebung({ json: {} }, roh10, quellen10), dienst10);
  let r10 = null, geworfen = null;
  try { r10 = await fahre('Code', ohneListen); } catch (e) { geworfen = e; }
  pruefe(geworfen === null,
         '10b "Code" wirft NICHT - ein Wurf wuerde hier zum Durchlass'
         + (geworfen ? ' (geworfen: ' + geworfen.message.slice(0, 80) + ')' : ''));
  if (r10) {
    pruefe(r10.length === quellen10.length,
           '10c alle Elemente kommen weiter (fuer die Ablage) (' + r10.length + ')');
    pruefe(r10.every(e => e.json.hochladen === false),
           '10d KEINES ist zum Hochladen freigegeben');
    pruefe(r10.every(e => e.json.nicht_vorgesehen === true),
           '10e jedes traegt nicht_vorgesehen - "Ablage entscheiden" laesst es draussen');
    pruefe(r10.every(e => e.json.listen_fehlen === true),
           '10f und den WAHREN Grund, damit das Protokoll nicht "Format nicht vorgesehen" luegt');
    const hoch10 = await fahre('Nur Dokumente hochladen', { $input: { all: () => r10 } });
    pruefe(hoch10.length === 0,
           '10g bis zum Upload gerechnet: NICHTS geht hoch (' + hoch10.length + ' von '
           + r10.length + ')');
    // Und das Protokoll muss den WAHREN Grund nennen - eine .pdf ist kein
    // unvorgesehenes Format, der Fehler steckt eine Stelle frueher.
    const r10ab = await fahre('Ablage entscheiden', {
      $input: { all: () => [{ json: { workspace: { documents: [] } } }] },
      $: (n) => ({ all: () => (n === 'Code' ? r10 : quellen10),
                   first: () => ({ json: { stdout: 'Normallauf: 4 Dateien' } }) }),
      $now: { toFormat: () => '2026-10-05 08:00:00' },
    });
    const je10 = {}; for (const x of r10ab[0].json.dokumente) je10[x.datei] = x;
    pruefe(Object.keys(je10).every(k => je10[k].ziel === 'aussortiert'),
           '10i keines wandert ins Archiv');
    pruefe(String(r10ab[0].json.befehl || '').indexOf('Positivliste nicht angekommen') !== -1,
           '10j das aussortiert.log nennt die Positivliste, nicht die Endung');
    pruefe(String(r10ab[0].json.befehl || '').indexOf('Format nicht vorgesehen (.pdf)') === -1,
           '10k GEGENPROBE: und behauptet NICHT, eine .pdf sei ein unvorgesehenes Format');
  }
  // ⛔ Die Gegenprobe zum Riegel: so sieht es aus, wenn er faellt statt
  //   zuzufallen - n8n reicht die Eingangsdaten unveraendert weiter.
  const durchgereicht = await fahre('Nur Dokumente hochladen',
                                    { $input: { all: () => roh10 } });
  pruefe(durchgereicht.length === roh10.length,
         '10h GEGENPROBE: unmarkierte Elemente wuerden ALLE hochgeladen ('
         + durchgereicht.length + ' von ' + roh10.length + ') - genau deshalb '
         + 'muss "Code" sie markieren, statt zu werfen');

  console.log('\n' + fehler + ' Fehler');
  process.exit(fehler ? 1 : 0);
})().catch(e => { console.error('ABBRUCH:', e); process.exit(2); });
