import handler from './products.js';

export default async function searchHandler(req, res) {
  const q = req.query.q || req.query.search || '';
  const lang = req.query.lang || 'ru';
  const limit = Math.min(parseInt(req.query.limit) || 10, 50);

  req.query.search = q;
  req.query.lang = lang;

  const capture = {
    body: null,
    headers: {},
    setHeader(k, v) { this.headers[k] = v; },
    status(c) { this.code = c; return this; },
    json(d) { this.body = d; },
  };

  await handler(req, capture);

  if (!capture.body) {
    res.status(500).json({ error: 'Failed to fetch products' });
    return;
  }

  const products = capture.body.products || [];
  const items = products.slice(0, limit).map((p) => ({
    id: p.sku,
    sku: p.sku,
    name: p.name,
    name_ru: p.name_ru || undefined,
    category: p.category,
    section: p.section,
    weight: p.weight,
    meatType: p.meatType || undefined,
    price: parseFloat(p.offers?.price || p.offers?.pricePerUnit || 0),
    priceCurrency: 'RUB',
    availability: 'InStock',
    url: `https://api.pepperoni.tatar/products/${(p.sku || '').toLowerCase()}`,
  }));

  const result = {
    dateModified: capture.body.dateModified,
    dataVersion: new Date().toISOString().split('T')[0],
    query: q,
    lang,
    totalMatches: capture.body.totalProducts,
    returned: items.length,
    items,
    _links: {
      self: `/api/search?q=${encodeURIComponent(q)}&lang=${lang}&limit=${limit}`,
      fullCatalog: '/api/products',
      openapi: '/openapi.yaml',
    },
  };

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json(result);
}
