import { strict as assert } from 'node:assert';
import {
  acceptSheetPublicText,
  applySheetAliases,
  scrubSheetProducts,
} from './public_halal_language.mjs';

const ok = acceptSheetPublicText('Breakfast Sausages (skinless, for Pigs-in-Blankets)');
assert.equal(ok.hit, null);
assert.equal(ok.value, 'Breakfast Sausages (skinless, for Sausage Rolls)');

const ru = acceptSheetPublicText('Мраморная: отсутствие свинины и ГМО');
assert.equal(ru.value, null);
assert.match(ru.hit, /свин/i);
assert.equal(applySheetAliases('отсутствие свинины'), 'отсутствие свинины');

const pork = acceptSheetPublicText('pork-free');
assert.equal(pork.value, null);

assert.equal(acceptSheetPublicText('pigeon').hit, null);

const out = scrubSheetProducts(
  [{ sku: 'KD-039', name: 'Колбаса', seoDescriptionRU: 'отсутствие свинины' }],
  { 'KD-039': { sku: 'KD-039', name: 'Колбаса', seoDescriptionRU: 'Халяль говядина' } },
  () => {},
);
assert.equal(out[0].seoDescriptionRU, 'Халяль говядина');

console.log('test_sheet_public_text.mjs: ok');
