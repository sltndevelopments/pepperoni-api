#!/usr/bin/env node

import { writeFileSync, readFileSync, mkdirSync, existsSync } from 'fs';
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
    const ep = {};
    if (toNumber(cols[7])) ep.USD = toNumber(cols[7]);
    if (toNumber(cols[8])) ep.KZT = toNumber(cols[8]);
    if (toNumber(cols[9])) ep.UZS = toNumber(cols[9]);
    if (toNumber(cols[10])) ep.KGS = toNumber(cols[10]);
    if (toNumber(cols[11])) ep.BYN = toNumber(cols[11]);
    if (toNumber(cols[12])) ep.AZN = toNumber(cols[12]);

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
        exportPrices: Object.keys(ep).length ? ep : undefined,
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
    const ep = {};
    if (toNumber(cols[9])) ep.USD = toNumber(cols[9]);
    if (toNumber(cols[10])) ep.KZT = toNumber(cols[10]);
    if (toNumber(cols[11])) ep.UZS = toNumber(cols[11]);
    if (toNumber(cols[12])) ep.KGS = toNumber(cols[12]);
    if (toNumber(cols[13])) ep.BYN = toNumber(cols[13]);
    if (toNumber(cols[14])) ep.AZN = toNumber(cols[14]);

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
        exportPrices: Object.keys(ep).length ? ep : undefined,
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

// --- YML Feed for Yandex.Market ---

const YML_CATEGORIES = {
  'Сосиски гриль для хот-догов': { id: 2, parent: 1 },
  'Котлеты для бургеров': { id: 3, parent: 1 },
  'Топпинги': { id: 4, parent: 1 },
  'Мясные заготовки': { id: 5, parent: 1 },
  'Сосиски, сардельки': { id: 7, parent: 6 },
  'Вареные': { id: 8, parent: 6 },
  'Ветчины': { id: 9, parent: 6 },
  'Копченые': { id: 10, parent: 6 },
  'Премиум Казылык': { id: 11, parent: 6 },
  'Национальная татарская выпечка': { id: 13, parent: 12 },
  'Классическая выпечка': { id: 14, parent: 12 },
};

function escapeXml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function generateYML(allProducts) {
  const today = new Date().toISOString().split('T')[0];
  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE yml_catalog SYSTEM "shops.dtd">
<yml_catalog date="${today}">
<shop>
<name>Казанские Деликатесы</name>
<company>ООО «Казанские Деликатесы»</company>
<url>https://kazandelikates.tatar</url>
<currencies><currency id="RUB" rate="1"/></currencies>
<categories>
<category id="1">Заморозка</category>
<category id="2" parentId="1">Сосиски гриль для хот-догов</category>
<category id="3" parentId="1">Котлеты для бургеров</category>
<category id="4" parentId="1">Топпинги</category>
<category id="5" parentId="1">Мясные заготовки</category>
<category id="6">Охлаждённая продукция</category>
<category id="7" parentId="6">Сосиски, сардельки</category>
<category id="8" parentId="6">Вареные</category>
<category id="9" parentId="6">Ветчины</category>
<category id="10" parentId="6">Копченые</category>
<category id="11" parentId="6">Премиум Казылык</category>
<category id="12">Выпечка</category>
<category id="13" parentId="12">Национальная татарская выпечка</category>
<category id="14" parentId="12">Классическая выпечка</category>
</categories>
<delivery>true</delivery>
<offers>
`;
  for (const p of allProducts) {
    const price = p.offers.price || p.offers.pricePerUnit;
    if (!price || parseFloat(price) === 0) continue;
    const catInfo = YML_CATEGORIES[p.category];
    const catId = catInfo ? catInfo.id : (p.section === 'Заморозка' ? 1 : p.section === 'Выпечка' ? 12 : 6);
    const desc = `${p.name}. Халяль продукция от Казанских Деликатесов.${p.shelfLife ? ' Срок годности: ' + p.shelfLife + '.' : ''}${p.storage ? ' Хранение: ' + p.storage + '.' : ''}`;
    xml += `<offer id="${escapeXml(p.sku)}" available="true">
<name>${escapeXml(p.name)}</name>
<url>https://pepperoni.tatar</url>
<price>${parseFloat(price)}</price>
<currencyId>RUB</currencyId>
<categoryId>${catId}</categoryId>
<vendor>Казанские Деликатесы</vendor>
<description>${escapeXml(desc)}</description>
<param name="Сертификация">Halal</param>
${p.weight ? `<param name="Вес">${escapeXml(p.weight)}</param>` : ''}
${p.shelfLife ? `<param name="Срок годности">${escapeXml(p.shelfLife)}</param>` : ''}
${p.hsCode ? `<param name="ТН ВЭД">${escapeXml(p.hsCode)}</param>` : ''}
</offer>
`;
  }
  xml += `</offers>
</shop>
</yml_catalog>`;
  return xml;
}

// --- Google Merchant Feed ---

function generateGoogleFeed(allProducts) {
  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
<channel>
<title>Kazan Delicacies — Halal Products</title>
<link>https://kazandelikates.tatar</link>
<description>Halal meat products and Tatar pastries from Kazan, Russia. 77 products.</description>
`;
  for (const p of allProducts) {
    const price = p.offers.price || p.offers.pricePerUnit;
    if (!price || parseFloat(price) === 0) continue;
    xml += `<item>
<g:id>${escapeXml(p.sku)}</g:id>
<g:title>${escapeXml(p.name)}</g:title>
<g:description>${escapeXml(p.name + '. Halal. Kazan Delicacies.')}</g:description>
<g:link>https://api.pepperoni.tatar/products/${p.sku.toLowerCase()}</g:link>
<g:price>${parseFloat(price)} RUB</g:price>
<g:availability>in_stock</g:availability>
<g:condition>new</g:condition>
<g:brand>Kazan Delicacies</g:brand>
<g:product_type>${escapeXml(p.section + ' > ' + p.category)}</g:product_type>
${p.hsCode ? `<g:gtin>${escapeXml(p.hsCode)}</g:gtin>` : ''}
</item>
`;
  }
  xml += `</channel>
</rss>`;
  return xml;
}

// --- RSS Feed ---

function generateRSS(allProducts) {
  const today = new Date().toUTCString();
  let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Казанские Деликатесы — Каталог продукции</title>
<link>https://api.pepperoni.tatar</link>
<description>Каталог халяль продукции: 77 товаров — пепперони, сосиски, ветчина, колбасы, татарская выпечка.</description>
<language>ru</language>
<lastBuildDate>${today}</lastBuildDate>
<atom:link href="https://api.pepperoni.tatar/rss.xml" rel="self" type="application/rss+xml"/>
`;
  for (const p of allProducts) {
    const price = p.offers.price || p.offers.pricePerUnit || '0';
    xml += `<item>
<title>${escapeXml(p.name)} — ${price} ₽</title>
<link>https://api.pepperoni.tatar/products/${p.sku.toLowerCase()}</link>
<guid>https://api.pepperoni.tatar/products/${p.sku.toLowerCase()}</guid>
<description>${escapeXml(p.name + '. ' + p.category + '. ' + (p.weight || '') + '. Halal. Казанские Деликатесы.')}</description>
<category>${escapeXml(p.section + ' / ' + p.category)}</category>
</item>
`;
  }
  xml += `</channel>
</rss>`;
  return xml;
}

// --- Individual Product Pages ---

function generateProductPages(allProducts) {
  const dir = join(PUBLIC, 'products');
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

  const syms = { USD: '$', KZT: '₸', UZS: 'UZS', KGS: 'KGS', BYN: 'BYN', AZN: 'AZN' };

  for (const p of allProducts) {
    const slug = p.sku.toLowerCase();
    const isBakery = !!p.offers?.pricePerUnit;
    const priceRUB = isBakery ? p.offers.pricePerUnit : p.offers.price;
    const priceNoVAT = p.offers.priceExclVAT || p.offers.pricePerBoxExclVAT || '';
    const priceUSD = p.offers?.exportPrices?.USD || '';
    const ep = p.offers?.exportPrices || {};
    let exportHtml = '';
    if (Object.keys(ep).length) {
      exportHtml = '<h3 style="margin-top:20px;font-size:1rem;color:#1b7a3d">Экспортные цены</h3><div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0">';
      for (const [cur, val] of Object.entries(ep)) {
        if (val) exportHtml += `<span style="background:#fff;border:1px solid #ddd;padding:6px 12px;border-radius:6px;font-size:.85rem"><b>${val}</b> ${syms[cur] || cur}</span>`;
      }
      exportHtml += '</div>';
    }

    const html = `<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${p.name} — Казанские Деликатесы | Халяль</title>
<meta name="description" content="${p.name}. ${p.category}. Халяль продукция от Казанских Деликатесов. ${p.weight ? 'Вес: ' + p.weight + '.' : ''} Цена: ${priceRUB} ₽. ${p.shelfLife ? 'Срок годности: ' + p.shelfLife + '.' : ''}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://api.pepperoni.tatar/products/${slug}">
<meta property="og:type" content="product">
<meta property="og:title" content="${p.name} — Казанские Деликатесы">
<meta property="og:description" content="${p.category}. ${priceRUB} ₽. Халяль.">
<meta property="og:url" content="https://api.pepperoni.tatar/products/${slug}">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" hreflang="ru" href="https://api.pepperoni.tatar/products/${slug}">
<link rel="alternate" hreflang="en" href="https://api.pepperoni.tatar/en/products/${slug}">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"${p.name.replace(/"/g, '\\"')}","sku":"${p.sku}","brand":{"@type":"Brand","name":"Казанские Деликатесы"},"offers":{"@type":"Offer","priceCurrency":"RUB","price":"${priceRUB}","availability":"https://schema.org/InStock"},"manufacturer":{"@type":"Organization","name":"Казанские Деликатесы","url":"https://kazandelikates.tatar"}}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.6}
.container{max-width:900px;margin:0 auto;padding:40px 24px}
.badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;letter-spacing:.5px}
.detail-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:.9rem}
.detail-row dt{color:#767676}
.detail-row dd{color:#1a1a1a;font-weight:500}
.cta-box{background:#f0f7f0;border:2px solid #1b7a3d;border-radius:10px;padding:24px;margin-top:24px}
.cta-box a{display:inline-block;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0}
footer{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}
footer a{color:#444;text-decoration:none}
</style>
</head>
<body>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
<a href="/" style="color:#0066cc;text-decoration:none">Каталог</a>
<a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
<a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
<a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
<a href="/en/products/${slug}" style="color:#595959;text-decoration:none;margin-left:auto">🇬🇧 English</a>
</div>
<a href="/" style="display:inline-block;margin-bottom:24px;color:#0066cc;text-decoration:none;font-size:.9rem">← Каталог</a>
<h1 style="font-size:1.6rem;margin-bottom:8px">${p.name}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
<span class="badge">HALAL</span>
<span class="badge" style="background:#0066cc">${p.sku}</span>
<span class="badge" style="background:#555">${p.section || ''}</span>
</div>
<div style="font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0">${parseFloat(priceRUB).toLocaleString('ru-RU')} ₽<span style="font-size:.85rem;color:#767676;font-weight:400">${isBakery ? ' /шт' : ' с НДС'}</span></div>
<div style="color:#1b7a3d;font-size:.9rem;margin:8px 0">✓ В наличии</div>
${isBakery && p.offers.pricePerBox ? `<div style="margin-top:8px;font-size:.9rem;color:#444">Цена за коробку: <b>${parseFloat(p.offers.pricePerBox).toLocaleString('ru-RU')} ₽</b>${p.qtyPerBox ? ' (' + p.qtyPerBox + ' шт)' : ''}</div>` : ''}
<div style="margin:20px 0">
${p.category ? `<dl class="detail-row"><dt>Категория</dt><dd>${p.category}</dd></dl>` : ''}
${p.weight ? `<dl class="detail-row"><dt>Вес расчёта</dt><dd>${p.weight}${p.weight.includes(' г') || p.weight.includes(' кг') ? '' : ' кг'}</dd></dl>` : ''}
${priceNoVAT ? `<dl class="detail-row"><dt>Цена без НДС</dt><dd>${priceNoVAT} ₽</dd></dl>` : ''}
${p.shelfLife ? `<dl class="detail-row"><dt>Срок годности</dt><dd>${p.shelfLife}</dd></dl>` : ''}
${p.storage ? `<dl class="detail-row"><dt>Хранение</dt><dd>${p.storage}</dd></dl>` : ''}
${p.hsCode ? `<dl class="detail-row"><dt>ТН ВЭД</dt><dd>${p.hsCode}</dd></dl>` : ''}
<dl class="detail-row"><dt>Сертификация</dt><dd>Halal</dd></dl>
<dl class="detail-row"><dt>Производитель</dt><dd>Казанские Деликатесы</dd></dl>
</div>
${exportHtml}
<div class="cta-box">
<h3 style="margin:0 0 8px">Заказ</h3>
<p style="color:#444;margin-bottom:12px">Опт, экспорт, Private Label</p>
<a href="tel:+79872170202" style="background:#1b7a3d;color:#fff">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject=Заказ:%20${encodeURIComponent(p.name)}%20(${p.sku})" style="border:2px solid #1b7a3d;color:#1b7a3d">📧 Написать</a>
</div>
<footer>
<p><a href="/pepperoni">Пепперони</a> · <a href="/about">О компании</a> · <a href="/faq">FAQ</a> · <a href="/delivery">Доставка</a></p>
<p>© <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
</body>
</html>`;
    writeFileSync(join(dir, `${slug}.html`), html, 'utf-8');
  }
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

  const ymlPath = join(PUBLIC, 'yml.xml');
  writeFileSync(ymlPath, generateYML(allProducts), 'utf-8');
  console.log(`✅ ${ymlPath}`);

  const feedPath = join(PUBLIC, 'feed.xml');
  writeFileSync(feedPath, generateGoogleFeed(allProducts), 'utf-8');
  console.log(`✅ ${feedPath}`);

  const rssPath = join(PUBLIC, 'rss.xml');
  writeFileSync(rssPath, generateRSS(allProducts), 'utf-8');
  console.log(`✅ ${rssPath}`);

  generateProductPages(allProducts);
  console.log(`✅ ${allProducts.length} product pages in public/products/`);

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
  <url>
    <loc>https://api.pepperoni.tatar/kazylyk</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/bakery</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/pizzeria</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/kazylyk</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/bakery</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://api.pepperoni.tatar/en/pizzeria</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
${allProducts.map(p => `  <url>
    <loc>https://api.pepperoni.tatar/products/${p.sku.toLowerCase()}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>`).join('\n')}
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
