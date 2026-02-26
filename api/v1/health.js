export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache');
  res.status(200).json({
    status: 'healthy',
    service: 'Pepperoni.tatar API',
    version: '2.1.0',
    apiVersion: 'v1',
    company: 'Казанские Деликатесы',
    endpoints: {
      products: '/api/v1/products',
      products_legacy: '/api/products',
      export: '/api/export',
      health: '/api/v1/health',
      stats: '/api/stats',
      static_catalog: '/products.json',
      openapi: '/openapi.yaml',
      llms: '/llms.txt',
      ai_plugin: '/.well-known/ai-plugin.json',
    },
    params: {
      search: 'Filter by name, category, SKU, meatType (?search=pepperoni)',
      section: 'Filter by section (?section=Frozen)',
      category: 'Filter by category (?category=Toppings)',
      sku: 'Exact SKU match (?sku=KD-015)',
      lang: 'Language: ru (default) or en (?lang=en)',
    },
  });
}
