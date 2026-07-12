#!/usr/bin/env node

import assert from 'assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import {
  identityDigest,
  validateCatalog,
  validatePageBijection,
} from './catalog-contract.mjs';

function product(overrides = {}) {
  return {
    name: 'Test product',
    sku: 'KD-001',
    section: 'Заморозка',
    offers: { exportPrices: { USD: 1.25 } },
    shelfLife: '180 суток',
    storage: '−18°C',
    hsCode: '160100',
    boxWeightGross: '5.5',
    barcode: '4680638721049',
    ...overrides,
  };
}

function guardFor(products) {
  return {
    algorithm: 'sha256',
    productCount: products.length,
    digest: identityDigest(products),
  };
}

const valid = [product()];
assert.deepEqual(validateCatalog(valid, guardFor(valid)), []);

const invalid = [product({
  offers: { exportPrices: { USD: 160100 } },
  shelfLife: '180',
  storage: '−18C',
  hsCode: '1602',
  boxWeightGross: '999942',
  barcode: '4,68E+12',
})];
const fieldErrors = validateCatalog(invalid, guardFor(invalid)).join('\n');
for (const field of ['USD', 'shelfLife', 'storage', 'hsCode', 'boxWeightGross', 'barcode']) {
  assert.match(fieldErrors, new RegExp(field), `expected fail-hard error for ${field}`);
}

const reordered = [
  product(),
  product({ sku: 'KD-002', name: 'Second product' }),
];
const stableGuard = guardFor(reordered);
assert.match(
  validateCatalog([...reordered].reverse(), stableGuard).join('\n'),
  /SKU identity guard mismatch/
);

const temp = mkdtempSync(join(tmpdir(), 'catalog-contract-'));
try {
  const ru = join(temp, 'products');
  const en = join(temp, 'en-products');
  mkdirSync(ru);
  mkdirSync(en);
  writeFileSync(join(ru, 'kd-001.html'), 'ok');
  writeFileSync(join(en, 'kd-002.html'), 'orphan');
  const pageErrors = validatePageBijection(valid, [ru, en]).join('\n');
  assert.match(pageErrors, /missing=\[kd-001\.html\]/);
  assert.match(pageErrors, /orphaned=\[kd-002\.html\]/);
  writeFileSync(join(en, 'kd-001.html'), 'ok');
  rmSync(join(en, 'kd-002.html'));
  assert.deepEqual(validatePageBijection(valid, [ru, en]), []);
} finally {
  rmSync(temp, { recursive: true, force: true });
}

console.log('catalog-contract tests: field validation, SKU identity guard, and page bijection passed');
