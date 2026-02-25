const BASE_URL =
  'https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv';

const SHEETS = [
  { gid: '1087942289', section: 'Заморозка', type: 'standard' },
  { gid: '1589357549', section: 'Охлаждённая продукция', type: 'standard' },
  { gid: '26993021', section: 'Выпечка', type: 'bakery' },
];

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

function buildStandard(lines, section, startIdx) {
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
    const weight = cols[1] || '';
    const shelfLife = cols[4] || '';
    const storage = cols[5] || '';
    const hsCode = cols[6] || '';

    const prices = {};
    if (toNumber(cols[7])) prices.USD = toNumber(cols[7]);
    if (toNumber(cols[8])) prices.KZT = toNumber(cols[8]);
    if (toNumber(cols[9])) prices.UZS = toNumber(cols[9]);
    if (toNumber(cols[10])) prices.KGS = toNumber(cols[10]);
    if (toNumber(cols[11])) prices.BYN = toNumber(cols[11]);
    if (toNumber(cols[12])) prices.AZN = toNumber(cols[12]);

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight,
      brand: 'Казанские Деликатесы',
      certification: 'Halal',
      offers: {
        url: 'https://pepperoni.tatar',
        priceCurrency: 'RUB',
        price: priceVAT.toFixed(2),
        priceExclVAT: priceNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
        exportPrices: prices,
        deliveryTerms: 'EXW Kazan Russia',
      },
      shelfLife,
      storage,
      hsCode,
    });
  }

  return { products, nextIdx: idx };
}

function buildBakery(lines, section, startIdx) {
  let category = '';
  const products = [];
  let idx = startIdx;

  for (const cols of lines) {
    if (!cols || cols.length < 4) continue;
    const name = cols[0];
    if (!name || name === 'Наименование' || name.startsWith('ООО')) continue;

    const pricePerUnit = toNumber(cols[3]);
    const pricePerBox = toNumber(cols[4]);

    if (pricePerUnit === 0 && pricePerBox === 0) {
      if (name && !cols[1]) category = name;
      continue;
    }

    idx++;
    const weightGrams = cols[1] || '';
    const qtyPerBox = cols[2] || '';
    const priceBoxNoVAT = toNumber(cols[5]);
    const shelfLife = cols[6] || '';
    const storage = cols[7] || '';
    const hsCode = cols[8] || '';

    const prices = {};
    if (toNumber(cols[9])) prices.USD = toNumber(cols[9]);
    if (toNumber(cols[10])) prices.KZT = toNumber(cols[10]);
    if (toNumber(cols[11])) prices.UZS = toNumber(cols[11]);
    if (toNumber(cols[12])) prices.KGS = toNumber(cols[12]);
    if (toNumber(cols[13])) prices.BYN = toNumber(cols[13]);
    if (toNumber(cols[14])) prices.AZN = toNumber(cols[14]);

    products.push({
      name,
      sku: `KD-${String(idx).padStart(3, '0')}`,
      section,
      category: category || section,
      weight: weightGrams ? `${weightGrams} г` : '',
      qtyPerBox: qtyPerBox || '',
      brand: 'Казанские Деликатесы',
      certification: 'Halal',
      offers: {
        url: 'https://pepperoni.tatar',
        priceCurrency: 'RUB',
        pricePerUnit: pricePerUnit.toFixed(2),
        pricePerBox: pricePerBox.toFixed(2),
        pricePerBoxExclVAT: priceBoxNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
        exportPrices: prices,
        deliveryTerms: 'EXW Kazan Russia',
      },
      shelfLife,
      storage,
      hsCode,
    });
  }

  return { products, nextIdx: idx };
}

export default async function handler(req, res) {
  try {
    const fetches = SHEETS.map((s) =>
      fetch(`${BASE_URL}&gid=${s.gid}`).then((r) => r.text())
    );
    const csvs = await Promise.all(fetches);

    let allProducts = [];
    let idx = 0;

    for (let i = 0; i < SHEETS.length; i++) {
      const lines = parseCSV(csvs[i]);
      const sheet = SHEETS[i];
      let result;

      if (sheet.type === 'bakery') {
        result = buildBakery(lines, sheet.section, idx);
      } else {
        result = buildStandard(lines, sheet.section, idx);
      }

      allProducts = allProducts.concat(result.products);
      idx = result.nextIdx;
    }

    const { search, section, category, sku } = req.query || {};
    let filtered = allProducts;

    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.category && p.category.toLowerCase().includes(q)) ||
          (p.sku && p.sku.toLowerCase().includes(q))
      );
    }
    if (section) {
      const s = section.toLowerCase();
      filtered = filtered.filter((p) => p.section && p.section.toLowerCase().includes(s));
    }
    if (category) {
      const c = category.toLowerCase();
      filtered = filtered.filter((p) => p.category && p.category.toLowerCase().includes(c));
    }
    if (sku) {
      filtered = filtered.filter((p) => p.sku && p.sku.toUpperCase() === sku.toUpperCase());
    }

    const result = {
      '@context': 'https://schema.org',
      '@type': 'DataCatalog',
      name: 'Полный каталог — Казанские Деликатесы',
      url: 'https://api.pepperoni.tatar/api/products',
      publisher: {
        '@type': 'Organization',
        name: 'Казанские Деликатесы',
        url: 'https://kazandelikates.tatar',
        address: '420061, Казань, ул Аграрная, 2, оф 7',
        phone: '+79872170202',
        email: 'info@kazandelikates.tatar',
      },
      dateModified: new Date().toISOString(),
      source: 'Google Sheets (live sync — 3 sheets)',
      sections: SHEETS.map((s) => s.section),
      totalProducts: filtered.length,
      filters: { search: search || null, section: section || null, category: category || null, sku: sku || null },
      products: filtered,
    };

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
