/** Shared public-surface swine gate. Keep in lockstep with public_halal_language.py. */

export const SHEET_ALIASES = [
  ['Pigs-in-Blankets', 'Sausage Rolls'],
  ['Pigs-in-Blanket', 'Sausage Roll'],
  ['pigs-in-blankets', 'sausage rolls'],
  ['pigs-in-blanket', 'sausage roll'],
];

export const UNSAFE_PATTERNS = [
  /свин(?!ц)/i,
  /шпик/i,
  /(?<![а-яё])сало(?![а-яё])/i,
  /pork/i,
  /\bporcine\b/i,
  /\bpigs?\b/i,
  /\bswine\b/i,
  /\bhogs?\b/i,
  /\blard\b/i,
  /\bfatback\b/i,
  /خنزير/,
];

export const SHEET_TEXT_FIELDS = [
  'name',
  'category',
  'seoDescriptionRU',
  'seoDescriptionEN',
  'ingredientsRU',
  'ingredientsEN',
  'cookingMethods',
  'nutrition',
  'packageType',
  'casing',
];

export function applySheetAliases(text) {
  if (!text) return text;
  let out = String(text);
  for (const [src, dst] of SHEET_ALIASES) out = out.replaceAll(src, dst);
  return out;
}

export function firstUnsafeHit(text) {
  if (!text) return null;
  const s = String(text);
  for (const rx of UNSAFE_PATTERNS) {
    const m = s.match(rx);
    if (m) return m[0];
  }
  return null;
}

export function acceptSheetPublicText(text) {
  if (text == null) return { value: '', hit: null };
  const rewritten = applySheetAliases(String(text));
  const hit = firstUnsafeHit(rewritten);
  if (hit) return { value: null, hit };
  return { value: rewritten, hit: null };
}

export function loadPreviousBySku(productsJson) {
  const out = {};
  for (const p of productsJson?.products || []) {
    if (p?.sku) out[p.sku] = p;
  }
  return out;
}

export function scrubSheetProducts(products, previousBySku = {}, log = console.log) {
  const kept = [];
  let rejected = 0;
  for (const raw of products) {
    const p = raw;
    const sku = p.sku || '?';
    const prev = previousBySku[p.sku] || {};
    let skip = false;
    for (const field of SHEET_TEXT_FIELDS) {
      const cell = p[field];
      if (cell == null || cell === '') continue;
      const { value, hit } = acceptSheetPublicText(cell);
      if (!hit) {
        p[field] = value;
        continue;
      }
      rejected += 1;
      const fb = prev[field] ? acceptSheetPublicText(prev[field]) : { value: null, hit: 'empty' };
      if (fb.value && !fb.hit) {
        p[field] = fb.value;
        log(`     ⛔ ${sku} ${field}: sheet «${hit}» — kept previous clean cell`);
        continue;
      }
      if (field === 'name') {
        if (prev.name) {
          log(`     ⛔ ${sku} name: sheet «${hit}» — kept previous product snapshot`);
          kept.push({ ...prev });
          skip = true;
          break;
        }
        log(`     ⛔ ${sku} name: sheet «${hit}» — no previous name, skip product`);
        skip = true;
        break;
      }
      delete p[field];
      log(`     ⛔ ${sku} ${field}: sheet «${hit}» — dropped, no clean fallback`);
    }
    if (!skip) kept.push(p);
  }
  if (rejected) log(`  ⛔ Sheet public-language: ${rejected} unsafe cell(s) rejected`);
  return kept;
}
