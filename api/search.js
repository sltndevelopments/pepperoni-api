const PRODUCTS_URL = 'https://api.pepperoni.tatar/api/products';

export default async function handler(req, res) {
  try {
    const q = req.query.q || req.query.search || '';
    const lang = req.query.lang || 'ru';
    const limit = Math.min(parseInt(req.query.limit) || 10, 50);

    const apiUrl = `${PRODUCTS_URL}?search=${encodeURIComponent(q)}&lang=${lang}`;
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error(`API ${response.status}`);
    const data = await response.json();

    const products = data.products || [];
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

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json({
      dateModified: data.dateModified,
      dataVersion: new Date().toISOString().split('T')[0],
      query: q,
      lang,
      totalMatches: data.totalProducts,
      returned: items.length,
      items,
      _links: {
        self: `/api/search?q=${encodeURIComponent(q)}&lang=${lang}&limit=${limit}`,
        fullCatalog: '/api/products',
        openapi: '/openapi.yaml',
      },
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
