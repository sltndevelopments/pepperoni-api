const CACHE_NAME = 'kd-catalog-v15';
const STATIC_URLS = [
  '/',
  '/en/',
  '/products/',
  '/en/products/',
  '/about',
  '/faq',
  '/delivery',
  '/kazylyk',
  '/bakery',
  '/pizzeria',
  '/en/about',
  '/en/faq',
  '/en/delivery',
  '/products.json',
  '/manifest.json',
];

// Ads / lead landings + their JS must never be served stale from SW cache.
// Old cache-first /pepperoni hid the AW conversion tag and broke Tag Assistant.
function isFreshHtmlPath(pathname) {
  const p = pathname.replace(/\/+$/, '') || '/';
  if (p === '/pepperoni' || p.endsWith('/pepperoni')) return true;
  if (p === '/' || p === '/en') return true;
  return false;
}

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);

  // Never intercept third-party (Google Ads / GTM / etc.)
  if (url.origin !== self.location.origin) return;

  // Tracking / form script — always network
  if (
    url.pathname === '/assets/lead-form.js' ||
    url.pathname === '/assets/gmp-track.js'
  ) {
    e.respondWith(fetch(e.request));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  if (
    url.pathname.startsWith('/products/') ||
    url.pathname.startsWith('/en/products/') ||
    url.pathname === '/products' ||
    url.pathname === '/en/products'
  ) {
    e.respondWith(fetch(e.request));
    return;
  }

  const acceptsHtml = (e.request.headers.get('accept') || '').includes('text/html');
  if (acceptsHtml && isFreshHtmlPath(url.pathname)) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
          }
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetched = fetch(e.request).then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(e.request, clone));
        }
        return res;
      });
      return cached || fetched;
    })
  );
});
