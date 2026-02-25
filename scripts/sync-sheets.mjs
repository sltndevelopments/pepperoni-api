#!/usr/bin/env node

import { writeFileSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const PUBLIC = join(ROOT, 'public');

const BASE_URL =
  'https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv';

const SHEETS = [
  { gid: '1087942289', section: 'Заморозка', type: 'standard' },
  { gid: '1589357549', section: 'Охлаждённая продукция', type: 'standard' },
  { gid: '26993021', section: 'Выпечка', type: 'bakery' },
];

// --- CSV parser ---

function parseCSV(text) {
  const rows = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (inQuotes && text[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      rows.push(current);
      current = '';
    } else if (ch === '\n' && !inQuotes) {
      rows.push(current);
      current = '';
      rows.push(null);
    } else {
      current += ch;
    }
  }
  if (current) rows.push(current);

  const lines = [];
  let line = [];
  for (const cell of rows) {
    if (cell === null) {
      lines.push(line);
      line = [];
    } else {
      line.push(cell.trim());
    }
  }
  if (line.length) lines.push(line);
  return lines;
}

function toNumber(s) {
  if (!s) return 0;
  return parseFloat(s.replace(/\s/g, '').replace(',', '.')) || 0;
}

// --- Parsers for each sheet type ---

function parseStandard(lines, section, startIdx) {
  let category = '';
  const products = [];
  let idx = startIdx;

  for (const cols of lines) {
    if (!cols || cols.length < 3) continue;
    const name = cols[0];
    if (!name || name === 'Наименование' || name === 'Номенклатура' || name.startsWith('ООО')) continue;

    const priceVAT = toNumber(cols[2]);
    const priceNoVAT = toNumber(cols[3]);

    if (priceVAT === 0 && priceNoVAT === 0) {
      if (name && !cols[1]) category = name;
      continue;
    }

    idx++;

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight: cols[1] || '',
      brand: 'Казанские Деликатесы',
      offers: {
        priceCurrency: 'RUB',
        price: priceVAT.toFixed(2),
        priceExclVAT: priceNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
      },
      shelfLife: cols[4] || '',
      storage: cols[5] || '',
      hsCode: cols[6] || '',
    });
  }

  return { products, nextIdx: idx };
}

function parseBakery(lines, section, startIdx) {
  let category = '';
  const products = [];
  let idx = startIdx;

  for (const cols of lines) {
    if (!cols || cols.length < 5) continue;
    const name = cols[0];
    if (!name || name === 'Наименование' || name.startsWith('ООО')) continue;

    const pricePerUnit = toNumber(cols[3]);
    const pricePerBox = toNumber(cols[4]);

    if (pricePerUnit === 0 && pricePerBox === 0) {
      if (name && !cols[1]) category = name;
      continue;
    }

    idx++;

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight: cols[1] ? `${cols[1]} г` : '',
      qtyPerBox: cols[2] || '',
      brand: 'Казанские Деликатесы',
      offers: {
        priceCurrency: 'RUB',
        pricePerUnit: pricePerUnit.toFixed(2),
        pricePerBox: pricePerBox.toFixed(2),
        pricePerBoxExclVAT: toNumber(cols[5]).toFixed(2),
        availability: 'https://schema.org/InStock',
      },
      shelfLife: cols[6] || '',
      storage: cols[7] || '',
      hsCode: cols[8] || '',
    });
  }

  return { products, nextIdx: idx };
}

// --- Generate products.json ---

function generateProductsJSON(allProducts) {
  const today = new Date().toISOString().split('T')[0];

  return {
    '@context': 'https://schema.org',
    source:
      'https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pubhtml',
    liveEndpoint: 'https://api.pepperoni.tatar/api/products',
    publisher: {
      name: 'Казанские Деликатесы',
      url: 'https://kazandelikates.tatar',
      address: '420061, Республика Татарстан, г Казань, ул Аграрная, дом 2, офис 7',
      phone: '+79872170202',
      email: 'info@kazandelikates.tatar',
    },
    lastSynced: today,
    deliveryTerms: 'EXW Kazan Russia',
    certification: 'Halal',
    sections: ['Заморозка', 'Охлаждённая продукция', 'Выпечка'],
    totalProducts: allProducts.length,
    products: allProducts,
  };
}

// --- Generate llms-full.txt ---

function generateLlmsFullTxt(allProducts) {
  const today = new Date().toISOString().split('T')[0];
  const sections = {};
  for (const p of allProducts) {
    const sec = p.section;
    if (!sections[sec]) sections[sec] = {};
    const cat = p.category;
    if (!sections[sec][cat]) sections[sec][cat] = [];
    sections[sec][cat].push(p);
  }

  let txt = `# Pepperoni.tatar API — полная документация

> Каталог халяль продукции от ООО «Казанские Деликатесы» (Kazan Delicacies).
> Последняя синхронизация: ${today}. Всего товаров: ${allProducts.length}.

## О компании

ООО «Казанские Деликатесы» — производитель халяль мясных изделий и выпечки.

- Адрес: 420061, Республика Татарстан, г Казань, ул Аграрная, дом 2, офис 7
- Телефон: +79872170202
- Email: info@kazandelikates.tatar
- Сайт компании: https://kazandelikates.tatar
- Сайт пепперони: https://pepperoni.tatar
- API: https://api.pepperoni.tatar
- Сертификация: Halal

## Каталог продукции (${allProducts.length} товаров)
`;

  for (const [secName, categories] of Object.entries(sections)) {
    const secProducts = Object.values(categories).flat();
    txt += `\n### ${secName} (${secProducts.length} товаров)\n`;

    for (const [catName, products] of Object.entries(categories)) {
      txt += `\n#### ${catName}\n\n`;

      if (products[0].offers.pricePerUnit) {
        txt += '| Название | SKU | Вес | Цена/шт (₽) | Цена/кор (₽) | Срок годности |\n';
        txt += '|----------|-----|-----|-------------|-------------|---------------|\n';
        for (const p of products) {
          txt += `| ${p.name} | ${p.sku} | ${p.weight} | ${p.offers.pricePerUnit} | ${p.offers.pricePerBox} | ${p.shelfLife} |\n`;
        }
      } else {
        txt += '| Название | SKU | Вес | Цена с НДС (₽) | Срок годности | Хранение |\n';
        txt += '|----------|-----|-----|----------------|---------------|----------|\n';
        for (const p of products) {
          txt += `| ${p.name} | ${p.sku} | ${p.weight} | ${p.offers.price} | ${p.shelfLife} | ${p.storage} |\n`;
        }
      }
    }
  }

  txt += `
## Экспортные цены

Все цены доступны в 7 валютах: RUB, USD, KZT, UZS, KGS, BYN, AZN.
Условия поставки: EXW Казань, Россия.
Данные автоматически синхронизируются с Google Sheets ежедневно.

## API

### GET /api/products (LIVE)

Возвращает актуальные данные, синхронизированные с Google Sheets.
Кешируется на 1 час. Аутентификация не требуется.

### GET /products.json (статический)

Статический каталог, обновляемый ежедневно через GitHub Actions.

## Интеграция

- OpenAPI: https://api.pepperoni.tatar/openapi.yaml
- AI Plugin: https://api.pepperoni.tatar/.well-known/ai-plugin.json
- AI Meta: https://api.pepperoni.tatar/.well-known/ai-meta.json
- Краткая версия: https://api.pepperoni.tatar/llms.txt
- Прайс-лист: https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pubhtml

## Контакты

По вопросам закупок и сотрудничества: info@kazandelikates.tatar, +79872170202
`;

  return txt;
}

// --- Main ---

async function main() {
  console.log('📥 Загрузка данных из Google Sheets...');

  const csvs = await Promise.all(
    SHEETS.map((s) =>
      fetch(`${BASE_URL}&gid=${s.gid}`)
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status} for ${s.section}`);
          return r.text();
        })
    )
  );

  let allProducts = [];
  let idx = 0;

  for (let i = 0; i < SHEETS.length; i++) {
    const lines = parseCSV(csvs[i]);
    const sheet = SHEETS[i];
    let result;

    if (sheet.type === 'bakery') {
      result = parseBakery(lines, sheet.section, idx);
    } else {
      result = parseStandard(lines, sheet.section, idx);
    }

    console.log(`  ✅ ${sheet.section}: ${result.products.length} товаров`);
    allProducts = allProducts.concat(result.products);
    idx = result.nextIdx;
  }

  console.log(`\n📊 Всего: ${allProducts.length} товаров\n`);

  const productsJSON = generateProductsJSON(allProducts);
  const productsPath = join(PUBLIC, 'products.json');
  writeFileSync(productsPath, JSON.stringify(productsJSON, null, 2), 'utf-8');
  console.log(`✅ ${productsPath}`);

  const llmsFullTxt = generateLlmsFullTxt(allProducts);
  const llmsFullPath = join(PUBLIC, 'llms-full.txt');
  writeFileSync(llmsFullPath, llmsFullTxt, 'utf-8');
  console.log(`✅ ${llmsFullPath}`);

  const today = new Date().toISOString().split('T')[0];
  const sitemapPath = join(PUBLIC, 'sitemap.xml');
  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://api.pepperoni.tatar/</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/api/products</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/products.json</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/openapi.yaml</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/llms.txt</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/llms-full.txt</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/about</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/faq</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/delivery</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/yml.xml</loc>
    <lastmod>${today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/pepperoni</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/pepperoni</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/about</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/faq</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/delivery</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>
`;
  writeFileSync(sitemapPath, sitemap, 'utf-8');
  console.log(`✅ ${sitemapPath}`);

  console.log('\n🎉 Синхронизация завершена!');
}

main().catch((err) => {
  console.error('❌ Ошибка:', err.message);
  process.exit(1);
});
