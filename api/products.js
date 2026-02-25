const SHEET_CSV_URL =
  'https://docs.google.com/spreadsheets/d/e/2PACX-1vRWKnx70tXlapgtJsR4rw9WLeQlksXAaXCQzZP1RBh9G7H9lQK4rt0ga9DaJkV28F7q8GDgkRZM3Arj/pub?output=csv';

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

function generateSKU(name, index) {
  const slug = name
    .replace(/[«»"]/g, '')
    .replace(/[^\w\sа-яёА-ЯЁ]/g, '')
    .trim()
    .substring(0, 20)
    .replace(/\s+/g, '-')
    .toUpperCase();
  return `KD-${String(index).padStart(3, '0')}`;
}

function buildProducts(lines) {
  let category = '';
  const products = [];
  let idx = 0;

  for (const cols of lines) {
    if (!cols || cols.length < 3) continue;
    const name = cols[0];
    if (!name) continue;

    if (name === 'Наименование') continue;
    if (name.startsWith('ООО')) continue;

    const priceVAT = toNumber(cols[2]);
    const priceNoVAT = toNumber(cols[3]);

    if (priceVAT === 0 && priceNoVAT === 0) {
      if (name && !cols[1]) {
        category = name;
      }
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
      sku: generateSKU(name, idx),
      category: category || 'Мясные изделия',
      weight,
      brand: 'Казанские Деликатесы',
      description: `${name}. Халяль продукция от Казанских Деликатесов.${shelfLife ? ' Срок годности: ' + shelfLife + '.' : ''}${storage ? ' Хранение: ' + storage + '.' : ''}`,
      certification: 'Halal',
      offers: {
        url: 'https://pepperoni.tatar',
        priceCurrency: 'RUB',
        price: priceVAT.toFixed(2),
        priceExclVAT: priceNoVAT.toFixed(2),
        availability: 'https://schema.org/InStock',
        priceValidUntil: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
        exportPrices: prices,
        deliveryTerms: 'EXW Kazan Russia',
      },
      shelfLife,
      storage,
      hsCode,
    });
  }

  return products;
}

export default async function handler(req, res) {
  try {
    const response = await fetch(SHEET_CSV_URL);
    if (!response.ok) throw new Error(`Google Sheets HTTP ${response.status}`);
    const csv = await response.text();
    const lines = parseCSV(csv);
    const products = buildProducts(lines);

    const result = {
      '@context': 'https://schema.org',
      '@type': 'DataCatalog',
      name: 'Каталог продуктов — Казанские Деликатесы',
      url: 'https://api.pepperoni.tatar/api/products',
      publisher: {
        '@type': 'Organization',
        name: 'Казанские Деликатесы',
        url: 'https://kazandelikates.tatar',
      },
      dateModified: new Date().toISOString(),
      source: 'Google Sheets (live sync)',
      totalProducts: products.length,
      products,
    };

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
