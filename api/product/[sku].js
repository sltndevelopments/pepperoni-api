import handler from '../products.js';

export default async function productHandler(req, res) {
  const { sku } = req.query;
  const lang = req.query.lang || 'ru';

  req.query.sku = sku;
  req.query.lang = lang;
  delete req.query.search;

  const capture = {
    body: null,
    headers: {},
    setHeader(k, v) { this.headers[k] = v; },
    status(c) { this.code = c; return this; },
    json(d) { this.body = d; },
  };

  await handler(req, capture);

  if (!capture.body || !capture.body.products?.length) {
    res.status(404).json({
      error: 'Product not found',
      sku,
      hint: 'Use /api/search?q=pepperoni to find products',
    });
    return;
  }

  const p = capture.body.products[0];
  const result = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    dateModified: capture.body.dateModified,
    dataVersion: new Date().toISOString().split('T')[0],
    source: 'Google Sheets (live)',
    ...p,
    _links: {
      self: `/api/product/${sku}`,
      catalog: '/api/products',
      search: '/api/search',
      html: `/products/${(sku || '').toLowerCase()}`,
    },
  };

  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json(result);
}
