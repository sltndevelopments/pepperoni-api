import { strict as assert } from 'node:assert';
import {
  parseCSV,
  buildColIndex,
  cellBy,
  parseBakery,
  certificatesForApi,
  alignSeoShelfLife,
} from './sync-sheets.mjs';

function emptyReg() {
  return { by_key: {}, next_n: 1, retired: {} };
}

// Header-only lookup: «без НДС» is not at index 5.
const reorderedCsv = [
  'Наименование,Вес,Квант,Цена шт,Короб НДС,Срок,Хранение,HS,USD,Цена за квант (короб) без НДС',
  'Губадия с кортом,100,48,"54,48","2615,04",360 суток,–18°C,190590,1.2,"2118,04"',
].join('\n');
const reorderedLines = parseCSV(reorderedCsv);
const reorderedIdx = buildColIndex(reorderedLines[0]);
assert.equal(reorderedIdx.priceBoxExclVAT, 9, 'без НДС must follow the header, not cols[5]');
assert.equal(cellBy(reorderedLines[1], reorderedIdx, 'priceBoxExclVAT'), '2118,04');
assert.notEqual(reorderedLines[1][5], '2118,04');

const reordered = parseBakery(reorderedLines, 'Выпечка', emptyReg()).products;
assert.equal(reordered.length, 1);
assert.equal(reordered[0].offers.pricePerBoxExclVAT, '2118.04');
assert.equal(reordered[0].offers.pricePerUnitExclVAT, '44.13');

// Blank cell = missing (do not invent 0.00). Header still present.
const blankCsv = [
  'Наименование,Вес,Квант,Цена шт,Короб НДС,Цена за квант (короб) без НДС,Срок,Хранение,HS',
  'Чак-чак в пластике,300,20,45,900,,180 суток,18°C,170490',
].join('\n');
const blankLines = parseCSV(blankCsv);
const blankIdx = buildColIndex(blankLines[0]);
assert.equal(blankIdx.priceBoxExclVAT, 5);
assert.equal(cellBy(blankLines[1], blankIdx, 'priceBoxExclVAT'), '');

const blank = parseBakery(blankLines, 'Выпечка', emptyReg()).products;
assert.equal(blank.length, 1);
assert.equal(blank[0].offers.pricePerBoxExclVAT, undefined);
assert.equal(blank[0].offers.pricePerUnitExclVAT, undefined);
assert.notEqual(blank[0].offers.pricePerBox, '0.00');

// Shelf-life column wins over the SEO description cell (chak-chak Sheet
// tab Выпечка / G = 90 суток, U/V still say 60).
const chakCsv = [
  'Наименование,Вес шт (гр),Кол-во в коробе шт,Цена за шт,Цена за квант (короб) с НДС,Срок годности,Хранение,SEO Описание RU,SEO Описание EN',
  'Чак-Чак в пластиковой упаковке,300,10,"211,80","2118,04",90 суток,до +18°C,Чак-чак срок хранения 60 суток при +18,Chak-chak shelf life 60 days at +18',
].join('\n');
const chakLines = parseCSV(chakCsv);
const chakIdx = buildColIndex(chakLines[0]);
assert.equal(chakIdx.shelfLife, 5, 'Срок годности follows the header, not the SEO cell');
assert.equal(chakIdx.seoRU, 7);
assert.equal(chakIdx.seoEN, 8);
const chak = parseBakery(chakLines, 'Выпечка', emptyReg()).products;
assert.equal(chak.length, 1);
assert.equal(chak[0].shelfLife, '90 суток');
assert.match(chak[0].seoDescriptionRU, /90 суток/);
assert.equal(false, /(?<!\d)60\s*суток/.test(chak[0].seoDescriptionRU));
assert.match(chak[0].seoDescriptionEN, /90 days/);
assert.equal(false, /(?<!\d)60\s*days/.test(chak[0].seoDescriptionEN));
const aligned = alignSeoShelfLife({
  shelfLife: '90 суток',
  seoDescriptionRU: 'Чак-чак 60 суток',
  seoDescriptionEN: 'Chak-chak 60 days',
});
assert.equal(aligned.seoDescriptionRU, 'Чак-чак 90 суток');
assert.equal(aligned.seoDescriptionEN, 'Chak-chak 90 days');

const certs = certificatesForApi();
const numbers = certs.map((c) => c.number);
assert.ok(numbers.includes('976A/2026'), 'certificatesForApi includes 976A/2026');
assert.ok(numbers.includes('1002/2026'), 'certificatesForApi includes 1002/2026');

console.log('test_bakery_excl_vat.mjs: ok');
