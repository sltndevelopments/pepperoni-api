const DEFAULT_BASE = process.env.PEPPERONI_API_BASE || 'https://api.pepperoni.tatar';

async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${DEFAULT_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const msg = data?.error || data?.message || res.statusText;
    throw new Error(`${res.status}: ${msg}`);
  }
  return data;
}

export function searchProducts({ q, lang = 'ru', limit = 10 }) {
  const params = new URLSearchParams({ q, lang, limit: String(limit) });
  return apiFetch(`/api/search?${params}`);
}

export function getProduct(sku, lang = 'ru') {
  const params = new URLSearchParams({ lang });
  return apiFetch(`/api/product/${encodeURIComponent(sku)}?${params}`);
}

export function getCatalog({ search, section, category, sku, lang = 'ru' } = {}) {
  const params = new URLSearchParams({ lang });
  if (search) params.set('search', search);
  if (section) params.set('section', section);
  if (category) params.set('category', category);
  if (sku) params.set('sku', sku);
  return apiFetch(`/api/products?${params}`);
}

export function submitInquiry({ contact, lang, message, page }) {
  const note = message ? ` | note: ${message}` : '';
  return apiFetch('/api/price-lead', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contact: `${contact}${note}`.slice(0, 200),
      lang: lang || 'ru',
      page: page || 'mcp://kazan-delicacies',
      format: 'mcp',
    }),
  });
}

export const DELIVERY_INFO = {
  terms: 'EXW Kazan, Russia (Incoterms 2020)',
  origin: 'Kazan, Republic of Tatarstan, Russia',
  currencies: ['RUB', 'USD', 'KZT', 'UZS', 'KGS', 'BYN', 'AZN'],
  exportMarkets: ['UAE', 'GCC', 'Kazakhstan', 'Uzbekistan', 'Kyrgyzstan', 'Belarus', 'Armenia', 'Azerbaijan', 'Africa', 'China'],
  storage: {
    frozen: '−18°C',
    chilled: '0–6°C',
    bakery: 'ambient / chilled per SKU',
  },
  hsCodes: ['160100', '1602', '190590', '1905', '040490'],
  contact: {
    email: 'info@kazandelikates.tatar',
    phone: '+79872170202',
    url: 'https://kazandelikates.tatar',
  },
  detailsUrl: 'https://pepperoni.tatar/delivery',
  note: 'No freight calculator API — request a quote via submit_inquiry.',
};

export const ISO_22000_VERIFY_URL =
  'https://www.iafcertsearch.org/certification/Y10VN21OAQGYY0PBRaTGYfPx';
