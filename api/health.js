export default function handler(req, res) {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache');
  res.status(200).json({
    status: 'healthy',
    service: 'Pepperoni.tatar API',
    version: '2.0.0',
    company: 'Казанские Деликатесы',
    endpoints: {
      products_live: '/api/products',
      products_static: '/products.json',
      health: '/api/health',
      openapi: '/openapi.yaml',
      llms: '/llms.txt',
      ai_plugin: '/.well-known/ai-plugin.json',
    },
  });
}
