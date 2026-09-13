import { readFile } from 'node:fs/promises';

const SITE_ORIGIN = 'https://pepperoni.tatar';
const LOCAL_CATALOG_CANDIDATES = [
  process.env.PEPPERONI_PRODUCTS_JSON,
  '/var/www/pepperoni/data/products.json',
  new URL('../public/products.json', import.meta.url).pathname,
].filter(Boolean);

const LEAD_BASE = process.env.PEPPERONI_LEAD_BASE || SITE_ORIGIN;

let catalogCache = { at: 0, data: null };
const CATALOG_TTL_MS = 60_000;

async function loadCatalogFile() {
  for (const path of LOCAL_CATALOG_CANDIDATES) {
    try {
      const raw = await readFile(path, 'utf8');
      const data = JSON.parse(raw);
      if (Array.isArray(data.products)) return data;
    } catch {
      /* try next */
    }
  }
  const res = await fetch(`${SITE_ORIGIN}/products.json`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`${res.status}: catalog unavailable`);
  }
  return res.json();
}

export async function getCatalogData() {
  const now = Date.now();
  if (catalogCache.data && now - catalogCache.at < CATALOG_TTL_MS) {
    return catalogCache.data;
  }
  const data = await loadCatalogFile();
  catalogCache = { at: now, data };
  return data;
}

function haystack(p) {
  return [
    p.sku,
    p.articleNumber,
    p.name,
    p.name_en,
    p.category,
    p.section,
    p.meatType,
    p.brand,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function compactProduct(p) {
  return {
    id: p.sku,
    sku: p.sku,
    name: p.name,
    category: p.category,
    section: p.section,
    weight: p.weight,
    meatType: p.meatType,
    price: parseFloat(p.offers?.price || p.offers?.pricePerUnit || 0),
    priceCurrency: p.offers?.priceCurrency || 'RUB',
    availability: p.offers?.availability || 'InStock',
    url: `${SITE_ORIGIN}/product/${String(p.sku || '').toLowerCase()}`,
  };
}

const SEARCH_ALIASES = {
  pepperoni: 'пепперони',
  sausage: 'сосиск',
  sausages: 'сосиск',
  hotdog: 'хот-дог',
  bakery: 'выпеч',
  ham: 'ветчин',
  kazylyk: 'казылык',
};

function searchNeedles(search) {
  const q = String(search || '').toLowerCase().trim();
  if (!q) return [];
  const extra = SEARCH_ALIASES[q] || SEARCH_ALIASES[q.replace(/s$/, '')];
  return extra ? [q, extra] : [q];
}

function filterProducts(products, { search, section, category, sku } = {}) {
  let list = products;
  if (sku) {
    const needle = String(sku).toLowerCase();
    list = list.filter((p) => String(p.sku || '').toLowerCase() === needle);
  }
  if (section) list = list.filter((p) => p.section === section);
  if (category) {
    const c = String(category).toLowerCase();
    list = list.filter((p) => String(p.category || '').toLowerCase().includes(c));
  }
  if (search) {
    const needles = searchNeedles(search);
    list = list.filter((p) => {
      const hay = haystack(p);
      return needles.some((n) => hay.includes(n));
    });
  }
  return list;
}

export async function searchProducts({ q, lang = 'ru', limit = 10 }) {
  const data = await getCatalogData();
  const items = filterProducts(data.products || [], { search: q })
    .slice(0, Math.min(Number(limit) || 10, 50))
    .map(compactProduct);
  return {
    query: q,
    lang,
    lastSynced: data.lastSynced,
    totalMatches: items.length,
    returned: items.length,
    items,
  };
}

export async function getProduct(sku, lang = 'ru') {
  const data = await getCatalogData();
  const product = (data.products || []).find(
    (p) => String(p.sku || '').toLowerCase() === String(sku || '').toLowerCase()
  );
  if (!product) {
    return { error: 'not_found', sku, lang };
  }
  return { lang, lastSynced: data.lastSynced, product };
}

export async function getCatalog({ search, section, category, sku, lang = 'ru' } = {}) {
  const data = await getCatalogData();
  const products = filterProducts(data.products || [], { search, section, category, sku });
  return {
    lastSynced: data.lastSynced,
    totalProducts: data.totalProducts || (data.products || []).length,
    returned: products.length,
    lang,
    b2b: {
      manufacturer: data.publisher?.name || 'ООО «Казанские Деликатесы»',
      deliveryTerms: data.deliveryTerms || 'EXW Kazan, Russia',
      halal_cert: { number: '614A/2024', body: 'DUM RT' },
      quality_system: 'HACCP',
      no_pork: true,
      private_label: true,
    },
    products,
  };
}

export async function submitInquiry({ contact, lang, message, page }) {
  const note = message ? ` | note: ${message}` : '';
  const res = await fetch(`${LEAD_BASE}/api/price-lead`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      contact: `${contact}${note}`.slice(0, 200),
      lang: lang || 'ru',
      page: page || 'mcp://kazan-delicacies',
      format: 'mcp',
    }),
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    throw new Error(`${res.status}: ${data?.error || data?.message || res.statusText}`);
  }
  return data;
}

export const DELIVERY_INFO = {
  terms: 'EXW Kazan, Russia (Incoterms 2020)',
  origin: 'Kazan, Republic of Tatarstan, Russia',
  currencies: ['RUB', 'USD', 'KZT', 'UZS', 'KGS', 'BYN', 'AZN'],
  exportMarkets:
    'Commercial destinations are confirmed per buyer inquiry. Do not assume a listed country, importer or approval.',
  storage: {
    frozen: '−18°C',
    chilled: '0–6°C',
    bakery: 'ambient / chilled per SKU',
  },
  hsCodes: 'Only 6–10 digit codes from the live catalog SKU card. Incomplete headings are not used as claims.',
  contact: {
    email: 'info@kazandelikates.tatar',
    phone: '+79872170202',
    url: 'https://kazandelikates.tatar',
  },
  detailsUrl: 'https://pepperoni.tatar/export',
  note: 'No freight calculator API — request a quote via submit_inquiry. Terms are EXW Kazan unless a written offer says otherwise.',
};

export const ISO_22000_VERIFY_URL =
  'https://www.iafcertsearch.org/certification/Y10VN21OAQGYY0PBRaTGYfPx';
