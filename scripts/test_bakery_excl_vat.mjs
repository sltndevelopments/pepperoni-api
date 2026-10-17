import { strict as assert } from 'node:assert';
import {
  parseCSV,
  buildColIndex,
  cellBy,
  parseBakery,
  certificatesForApi,
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

const certs = certificatesForApi();
const numbers = certs.map((c) => c.number);
assert.ok(numbers.includes('976A/2026'), 'certificatesForApi includes 976A/2026');
assert.ok(numbers.includes('1002/2026'), 'certificatesForApi includes 1002/2026');

console.log('test_bakery_excl_vat.mjs: ok');
