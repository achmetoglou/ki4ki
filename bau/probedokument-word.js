// Ein Word-Probedokument mit echten Umlauten.
//
// Warum ausgerechnet Word: Die Aufnahme schickt doc/docx/odt/rtf ZUERST durch
// den Office-Dienst nach PDF. Die gewandelte PDF liegt danach neben dem
// Original im Archiv - und das Dokument ist das ORIGINAL. Bekaeme die PDF
// einen eigenen Abdruck, zeigte jeder Beleg des Word-Dokuments ins Leere,
// ohne Meldung. Genau diese Sonderregel steckt in _schluessel_der_datei()
// und in pdfstelle._index_bauen(); hier wird sie am laufenden System
// geprueft statt nur im Testbaum.
//
// Die Zahl 371 kommt in keinem anderen Probedokument vor. Antwortet die
// Anlage mit einer anderen, hat sie das falsche Dokument erwischt.
//
//   npm install docx && node bau/probedokument-word.js <zieldatei.docx>

const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel } = require('docx');

const ZEILEN = [
  'Werkstoff: Polyamid 6.6, glasfaserverstärkt (35 Prozent).',
  'Prüfklima während der Messung: 23 °C bei 50 % Feuchte.',
  '',
  'Die Zugfestigkeit beträgt 371 MPa.',
  'Bruchdehnung 2,9 Prozent bei fünf geprüften Körpern.',
  'Für die Freigabe war die Prüfstelle Süd zuständig.',
];

const ziel = process.argv[2];
if (!ziel) {
  console.error('Aufruf: node bau/probedokument-word.js <zieldatei.docx>');
  process.exit(1);
}

const doc = new Document({
  sections: [{
    children: [
      new Paragraph({
        text: 'Prüfprotokoll Zugversuch – Charge 11',
        heading: HeadingLevel.HEADING_1,
      }),
      // ⛔ Kein '\n' in einem TextRun - je Zeile ein eigener Paragraph.
      ...ZEILEN.map((z) => new Paragraph({ children: [new TextRun(z)] })),
      new Paragraph({
        children: [new TextRun({
          text: 'Erfundenes Probedokument – keine echten Daten.',
          italics: true, size: 16,
        })],
      }),
    ],
  }],
});

fs.mkdirSync(path.dirname(ziel), { recursive: true });
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(ziel, buf);
  console.log('%d Byte  %s', buf.length, ziel);
});
