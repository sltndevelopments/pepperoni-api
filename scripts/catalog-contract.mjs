#!/usr/bin/env node

import { createHash } from 'crypto';
import { existsSync, readFileSync, readdirSync } from 'fs';
import { basename, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const DEFAULT_GUARD = join(ROOT, 'data', 'catalog-sku-identity.json');
const SKU_RE = /^KD-\d{3}$/;
const PAGE_RE = /^kd-\d{3}\.html$/;

function cleanIdentity(value) {
  return String(value || '').trim().replace(/\s+/g, ' ');
}

export function identityPayload(products) {
  return products
    .map((product) => `${product.sku}\t${cleanIdentity(product.section)}\t${cleanIdentity(product.name)}`)
    .join('\n') + '\n';
}

export function identityDigest(products) {
  return createHash('sha256').update(identityPayload(products), 'utf8').digest('hex');
}

export function loadIdentityGuard(path = DEFAULT_GUARD) {
  const guard = JSON.parse(readFileSync(path, 'utf8'));
  if (guard.algorithm !== 'sha256' || !/^[a-f0-9]{64}$/.test(guard.digest || '')) {
    throw new Error(`Invalid SKU identity guard: ${path}`);
  }
  return guard;
}

export function validateCatalog(products, guard = loadIdentityGuard()) {
  const errors = [];
  const seenSkus = new Set();

  if (!Array.isArray(products) || products.length === 0) {
    return ['catalog must contain at least one product'];
  }

  for (const [index, product] of products.entries()) {
    const label = product?.sku || `row ${index + 1}`;
    if (!SKU_RE.test(product?.sku || '')) errors.push(`${label}: sku must match KD-NNN`);
    if (seenSkus.has(product?.sku)) errors.push(`${label}: duplicate sku`);
    seenSkus.add(product?.sku);
    if (!cleanIdentity(product?.name)) errors.push(`${label}: name is required`);
    if (!cleanIdentity(product?.section)) errors.push(`${label}: section is required`);

    const usd = product?.offers?.exportPrices?.USD;
    if (typeof usd !== 'number' || !Number.isFinite(usd) || usd < 0.1 || usd > 10000) {
      errors.push(`${label}: offers.exportPrices.USD must be a number from 0.1 to 10000 (got ${JSON.stringify(usd)})`);
    }

    const hsCode = cleanIdentity(product?.hsCode);
    if (!/^\d{6,10}$/.test(hsCode)) {
      errors.push(`${label}: hsCode must contain 6-10 digits (got ${JSON.stringify(hsCode)})`);
    }

    const storage = cleanIdentity(product?.storage);
    if (!storage.includes('°C')) {
      errors.push(`${label}: storage must contain °C (got ${JSON.stringify(storage)})`);
    }

    const shelfLife = cleanIdentity(product?.shelfLife).toLocaleLowerCase('ru');
    if (!/(?:сут|дн)/.test(shelfLife)) {
      errors.push(`${label}: shelfLife must contain сут or дн (got ${JSON.stringify(shelfLife)})`);
    }

    const boxWeight = cleanIdentity(product?.boxWeightGross);
    if (boxWeight) {
      const parsed = Number(boxWeight.replace(',', '.'));
      if (!Number.isFinite(parsed) || parsed <= 0 || parsed > 1000) {
        errors.push(`${label}: boxWeightGross must be a number from 0 to 1000 (got ${JSON.stringify(boxWeight)})`);
      }
    }

    const barcode = cleanIdentity(product?.barcode);
    if (barcode && !/^\d{8,14}$/.test(barcode)) {
      errors.push(`${label}: barcode must contain 8-14 digits without scientific notation (got ${JSON.stringify(barcode)})`);
    }
  }

  const digest = identityDigest(products);
  if (products.length !== guard.productCount || digest !== guard.digest) {
    errors.push(
      `SKU identity guard mismatch: expected ${guard.productCount} products/${guard.digest}, ` +
      `got ${products.length}/${digest}; review row additions, removals, renames, or reordering and update ` +
      'data/catalog-sku-identity.json only after approving the new stable SKU identities'
    );
  }

  return errors;
}

export function assertCatalog(products, guard = loadIdentityGuard()) {
  const errors = validateCatalog(products, guard);
  if (errors.length) {
    throw new Error(`Catalog contract failed (${errors.length} violation${errors.length === 1 ? '' : 's'}):\n- ${errors.join('\n- ')}`);
  }
}

function pageSet(directory) {
  if (!existsSync(directory)) return new Set();
  return new Set(readdirSync(directory).filter((name) => PAGE_RE.test(name)));
}

export function validatePageBijection(products, directories) {
  const expected = new Set(products.map((product) => `${product.sku.toLowerCase()}.html`));
  const errors = [];
  for (const directory of directories) {
    const actual = pageSet(directory);
    const missing = [...expected].filter((name) => !actual.has(name)).sort();
    const orphaned = [...actual].filter((name) => !expected.has(name)).sort();
    if (missing.length || orphaned.length) {
      errors.push(
        `${basename(directory)}: missing=[${missing.join(', ')}], orphaned=[${orphaned.join(', ')}]`
      );
    }
  }
  return errors;
}

export function assertPageBijection(products, directories) {
  const errors = validatePageBijection(products, directories);
  if (errors.length) throw new Error(`Catalog/page bijection failed:\n- ${errors.join('\n- ')}`);
}

function main() {
  const catalogPath = join(ROOT, 'public', 'products.json');
  const data = JSON.parse(readFileSync(catalogPath, 'utf8'));
  const products = data.products || [];
  assertCatalog(products);
  assertPageBijection(products, [
    join(ROOT, 'public', 'products'),
    join(ROOT, 'public', 'en', 'products'),
  ]);
  console.log(`catalog-contract: ${products.length} products valid; RU/EN page bijection valid`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
