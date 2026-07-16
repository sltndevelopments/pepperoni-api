/**
 * Stable SKU registry — product URLs must not reshuffle when Google Sheets
 * rows are deleted/reordered. Fingerprint = normalized name + weight.
 *
 * File: data/sku_registry.json
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const REGISTRY_PATH = path.join(ROOT, 'data', 'sku_registry.json');
const PRODUCTS_PATH = path.join(ROOT, 'public', 'products.json');

function norm(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[«»"'″]/g, '')
    .trim();
}

export function productKey(name, weight = '') {
  return `${norm(name)}|${norm(weight)}`;
}

function emptyRegistry() {
  return { version: 1, next_n: 1, by_key: {}, retired: {} };
}

export function loadRegistry() {
  try {
    const data = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
    if (!data.by_key) data.by_key = {};
    if (!data.retired) data.retired = {};
    if (!Number.isInteger(data.next_n) || data.next_n < 1) data.next_n = 1;
    return data;
  } catch {
    return emptyRegistry();
  }
}

export function saveRegistry(reg) {
  fs.mkdirSync(path.dirname(REGISTRY_PATH), { recursive: true });
  fs.writeFileSync(REGISTRY_PATH, JSON.stringify(reg, null, 2) + '\n', 'utf8');
}

/** Bootstrap from current products.json so existing URLs stay put. */
export function bootstrapFromProducts(reg) {
  if (Object.keys(reg.by_key).length > 0) return reg;
  try {
    const data = JSON.parse(fs.readFileSync(PRODUCTS_PATH, 'utf8'));
    const products = data.products || [];
    let maxN = 0;
    for (const p of products) {
      const m = String(p.sku || '').match(/^KD-(\d+)$/i);
      if (!m) continue;
      const n = parseInt(m[1], 10);
      if (n > maxN) maxN = n;
      const key = productKey(p.name, p.weight);
      // Prefer first occupant if collision
      if (!reg.by_key[key]) reg.by_key[key] = p.sku.toUpperCase();
    }
    reg.next_n = Math.max(reg.next_n, maxN + 1);
    console.log(`  🔑 sku_registry bootstrapped from products.json: ${Object.keys(reg.by_key).length} keys, next=KD-${String(reg.next_n).padStart(3, '0')}`);
  } catch (e) {
    console.warn(`  ⚠️  sku_registry bootstrap skipped: ${e.message}`);
  }
  return reg;
}

/**
 * Assign a stable SKU for this product. Reuses registry entry; never
 * reassigns an existing SKU to a different fingerprint.
 */
export function assignSku(reg, name, weight = '') {
  const key = productKey(name, weight);
  if (reg.by_key[key]) return reg.by_key[key];

  // Find free KD-NNN starting at next_n (skip any still mapped)
  const used = new Set(Object.values(reg.by_key));
  for (const sku of Object.keys(reg.retired || {})) used.add(sku);

  let n = reg.next_n;
  let sku;
  do {
    sku = `KD-${String(n).padStart(3, '0')}`;
    n += 1;
  } while (used.has(sku));

  reg.by_key[key] = sku;
  reg.next_n = n;
  return sku;
}

/** Mark SKUs absent from this sync as retired (do not reuse). */
export function retireMissing(reg, liveKeys) {
  const live = new Set(liveKeys);
  let retired = 0;
  for (const [key, sku] of Object.entries(reg.by_key)) {
    if (!live.has(key)) {
      reg.retired[sku] = key;
      delete reg.by_key[key];
      retired += 1;
    }
  }
  if (retired) {
    console.log(`  🗄  sku_registry: retired ${retired} SKU(s) (kept reserved, not reused)`);
  }
  return retired;
}
