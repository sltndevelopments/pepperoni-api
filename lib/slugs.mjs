/**
 * Стабильная генерация slug для страниц товаров.
 * Slug не должен меняться при изменении названия в Sheets.
 * Использует slug-map.json для сохранения существующих slug.
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, '..', 'data');
const SLUG_MAP_PATH = join(DATA_DIR, 'slug-map.json');

// Транслитерация RU → EN (для slug)
const TRANSLIT = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
  и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
  с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch',
  ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
};

function transliterate(text) {
  return [...(text || '').toLowerCase()]
    .map((c) => TRANSLIT[c] || (/[a-z0-9]/.test(c) ? c : '-'))
    .join('');
}

function slugify(text) {
  const t = transliterate(text);
  return t
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .replace(/-+/g, '-');
}

/**
 * Генерирует slug из SKU и названия.
 * Пример: KD-015 + "Пепперони вар-коп классика" → kd-015-pepperoni-var-kop-klassika
 */
export function generateSlug(sku, name) {
  const skuPart = (sku || '').toLowerCase().replace(/\s/g, '-');
  const namePart = slugify(name || '');
  const combined = namePart ? `${skuPart}-${namePart}` : skuPart;
  return combined.slice(0, 80); // разумный лимит
}

/**
 * Загружает slug-map, применяет для существующих SKU, добавляет новые.
 * Возвращает Map: sku -> slug
 */
export function getOrCreateSlugMap(products) {
  let map = {};
  try {
    const data = readFileSync(SLUG_MAP_PATH, 'utf-8');
    map = JSON.parse(data);
  } catch {
    // файл не существует — создаём с нуля
  }

  const result = new Map();
  let changed = false;

  for (const p of products) {
    const sku = p.sku;
    if (map[sku]) {
      result.set(sku, map[sku]);
    } else {
      const slug = generateSlug(sku, p.name);
      map[sku] = slug;
      result.set(sku, slug);
      changed = true;
    }
  }

  if (changed) {
    try {
      mkdirSync(DATA_DIR, { recursive: true });
    } catch {}
    writeFileSync(SLUG_MAP_PATH, JSON.stringify(map, null, 2), 'utf-8');
  }

  return result;
}
