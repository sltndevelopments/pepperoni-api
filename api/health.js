export default async function handler(req, res) {
  const raw = Array.isArray(req.query?.u) ? req.query.u[0] : req.query?.u;

  // Proxy mode: /api/health?u=<cloudinary-url>
  if (raw) {
    let target;
    try {
      target = new URL(raw);
    } catch (_) {
      res.status(400).json({ error: 'Invalid target URL' });
      return;
    }

    if (target.hostname !== 'res.cloudinary.com' || !target.pathname.includes('/image/upload/')) {
      res.status(403).json({ error: 'Target URL is not allowed' });
      return;
    }

    try {
      const upstream = await fetch(target.toString(), {
        redirect: 'follow',
        headers: { Accept: 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8' },
      });
      if (!upstream.ok) {
        res.status(upstream.status).json({ error: 'Upstream image fetch failed' });
        return;
      }
      const contentType = upstream.headers.get('content-type') || 'image/jpeg';
      const arrayBuffer = await upstream.arrayBuffer();
      const body = Buffer.from(arrayBuffer);
      res.setHeader('Content-Type', contentType);
      res.setHeader('Cache-Control', 'public, max-age=86400, stale-while-revalidate=604800');
      res.status(200).send(body);
      return;
    } catch (_) {
      res.status(502).json({ error: 'Proxy request failed' });
      return;
    }
  }

  // Health mode
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
