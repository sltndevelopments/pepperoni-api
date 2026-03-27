/**
 * Генерация HTML страницы товара (SKU) по спецификации PRODUCT-PAGE-SPEC.md.
 * Используется в sync-sheets при генерации статических страниц.
 */

const BASE = 'https://www.pepperoni.tatar';
const HALAL_CERT = '614A/2024';
const HALAL_ORG = 'ДУМ РТ';

function esc(s) {
  if (s == null || s === '') return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildDescription(product, locale) {
  const p = product;
  const isRu = locale === 'ru';
  const name = p.name || '';
  const category = p.category || p.section || '';
  const weight = p.weight || '';
  const shelfLife = p.shelfLife || '';
  const storage = p.storage || '';

  if (isRu) {
    return `${name} — ${category} от ООО «Казанские Деликатесы». Халяль продукция, сертификат Halal № ${HALAL_CERT} (${HALAL_ORG}). HACCP. Вес: ${weight}. Срок годности: ${shelfLife || 'см. на упаковке'}. Условия хранения: ${storage || 'см. на упаковке'}. Подходит для пиццерий, HoReCa, пищевого производства, розничных сетей. Поставка EXW Казань. Цены в рублях, долларах, тенге и других валютах. Оптовые партии, Private Label по запросу. Производитель — ООО «Казанские Деликатесы», Казань, Татарстан. Экспорт в Казахстан, Узбекистан, Кыргызстан, Беларусь, Азербайджан и другие страны.`;
  }
  return `${name} — ${category} by Kazan Delicacies. Halal certified (${HALAL_CERT}, ${HALAL_ORG}). HACCP. Weight: ${weight}. Shelf life: ${shelfLife || 'see packaging'}. Storage: ${storage || 'see packaging'}. Suitable for pizzerias, HoReCa, food production, retail. EXW Kazan delivery. Prices in RUB, USD, KZT, and other currencies. Wholesale, Private Label on request. Manufacturer: Kazan Delicacies LLC, Kazan, Tatarstan. Export to Kazakhstan, Uzbekistan, Kyrgyzstan, Belarus, Azerbaijan and other countries.`;
}

function getPrice(product) {
  const o = product.offers || {};
  return o.price || o.pricePerUnit || o.pricePerBox || '';
}

function getPriceCurrency(product) {
  return (product.offers && product.offers.priceCurrency) || 'RUB';
}

export function renderProductPage(product, slug, locale, relatedProducts = [], slugMap) {
  const isRu = locale === 'ru';
  const pathPrefix = isRu ? '' : '/en';
  const productPath = `${pathPrefix}/product/${slug}`;
  const canonicalUrl = `${BASE}${pathPrefix}/product/${slug}`;
  const ruUrl = `${BASE}/product/${slug}`;
  const enUrl = `${BASE}/en/product/${slug}`;

  const title = isRu
    ? `${product.name} | Казанские Деликатесы`
    : `${product.name} | Kazan Delicacies`;
  const description = buildDescription(product, locale);
  const descShort = description.slice(0, 157) + (description.length > 157 ? '…' : '');

  const breadcrumbHome = isRu ? 'Главная' : 'Home';
  const breadcrumbCatalog = isRu ? 'Каталог' : 'Catalog';
  const sectionName = product.section || '';
  const categoryName = product.category || product.section || '';

  const relatedItems = relatedProducts
    .slice(0, 5)
    .map((r) => {
      const s = slugMap ? slugMap.get(r.sku) : slug;
      const rPath = isRu ? `/product/${s}` : `/en/product/${s}`;
      return `<a href="${esc(rPath)}">${esc(r.name)}</a>`;
    })
    .join(' · ');

  const exportPrices = (product.offers && product.offers.exportPrices) || {};
  const currencies = ['RUB', 'USD', 'KZT', 'UZS', 'KGS', 'BYN', 'AZN'].filter(
    (c) => exportPrices[c]
  );
  const currenciesList = currencies.length ? currencies.join(', ') : 'RUB';

  const productSchema = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    sku: product.sku,
    brand: { '@type': 'Brand', name: product.brand || 'Kazan Delicacies' },
    category: categoryName,
    countryOfOrigin: 'RU',
    offers: {
      '@type': 'Offer',
      priceCurrency: getPriceCurrency(product),
      price: getPrice(product),
      availability: 'https://schema.org/InStock',
      url: canonicalUrl,
      priceSpecification: {
        '@type': 'PriceSpecification',
        priceCurrency: getPriceCurrency(product),
        valueAddedTaxIncluded: true,
      },
    },
  };

  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: breadcrumbHome, item: `${BASE}${pathPrefix || ''}/` },
      { '@type': 'ListItem', position: 2, name: sectionName, item: `${BASE}${pathPrefix || ''}/` },
      { '@type': 'ListItem', position: 3, name: product.name },
    ],
  };

  const navLinks = isRu
    ? `<a href="/">Каталог</a> · <a href="/about">О компании</a> · <a href="/delivery">Доставка</a>`
    : `<a href="/en/">Catalog</a> · <a href="/en/about">About</a> · <a href="/en/delivery">Delivery</a>`;

  const langSwitch = isRu
    ? `<a href="/en/product/${slug}" hreflang="en">English</a>`
    : `<a href="/product/${slug}" hreflang="ru">Русский</a>`;

  const footerText = isRu
    ? `© <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · <a href="https://www.pepperoni.tatar">pepperoni.tatar</a>`
    : `© <a href="https://kazandelikates.tatar">Kazan Delicacies</a> · <a href="https://www.pepperoni.tatar">pepperoni.tatar</a>`;

  const labels = {
    sku: isRu ? 'Артикул' : 'SKU',
    section: isRu ? 'Раздел' : 'Section',
    category: isRu ? 'Категория' : 'Category',
    weight: isRu ? 'Вес' : 'Weight',
    shelfLife: isRu ? 'Срок годности' : 'Shelf life',
    storage: isRu ? 'Хранение' : 'Storage',
    hsCode: isRu ? 'Код ТН ВЭД' : 'HS Code',
    halalCert: isRu ? 'Сертификат Halal' : 'Halal certificate',
    delivery: isRu ? 'Условия поставки' : 'Delivery terms',
    incoterms: isRu ? 'Incoterms' : 'Incoterms',
    moq: isRu ? 'Мин. партия' : 'MOQ',
    currencies: isRu ? 'Валюты' : 'Currencies',
    descBlock: isRu ? 'Описание' : 'Description',
    specBlock: isRu ? 'Техническая спецификация' : 'Technical specification',
    exportBlock: isRu ? 'Экспорт и B2B' : 'Export & B2B',
    related: isRu ? 'Похожие товары' : 'Related products',
  };

  const weightVal = product.weight || '—';
  const qtyPerBox = product.qtyPerBox || '—';
  const shelfLifeVal = product.shelfLife || '—';
  const storageVal = product.storage || '—';
  const hsCodeVal = product.hsCode || '160100';

  return `<!DOCTYPE html>
<html lang="${isRu ? 'ru' : 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="${BASE}/favicon.ico" type="image/x-icon">
  <link rel="canonical" href="${canonicalUrl}">
  <title>${esc(title)}</title>
  <meta name="description" content="${esc(descShort)}">
  <meta name="robots" content="index, follow">
  <meta property="og:type" content="product">
  <meta property="og:title" content="${esc(product.name)}">
  <meta property="og:url" content="${canonicalUrl}">
  <meta property="og:image" content="${BASE}/images/pepperoni-halal.png">
  <meta property="og:locale" content="${isRu ? 'ru_RU' : 'en_US'}">
  <link rel="alternate" hreflang="ru" href="${ruUrl}">
  <link rel="alternate" hreflang="en" href="${enUrl}">
  <script type="application/ld+json">${JSON.stringify(productSchema)}</script>
  <script type="application/ld+json">${JSON.stringify(breadcrumbSchema)}</script>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
    .container{max-width:800px;margin:0 auto;padding:40px 24px}
    nav{font-size:.85rem;color:#888;margin-bottom:32px}
    nav a{color:#0066cc;text-decoration:none}
    nav a:hover{text-decoration:underline}
    h1{font-size:2rem;font-weight:700;margin-bottom:8px}
    h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
    .badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0}
    .card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}
    table{width:100%;border-collapse:collapse;margin:12px 0}
    th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}
    th{background:#f5f5f5;font-weight:600;width:40%}
    p{margin-bottom:14px}
    .related{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
    .related a{color:#0066cc;text-decoration:none;font-size:.9rem}
    .related a:hover{text-decoration:underline}
    footer{margin-top:48px;padding-top:24px;border-top:1px solid #eee;font-size:.85rem;color:#666}
    footer a{color:#0066cc;text-decoration:none}
  </style>
</head>
<body>
  <div class="container">
    <nav>${navLinks} · ${langSwitch}</nav>
    <span class="badge">Halal</span>
    <h1>${esc(product.name)}</h1>
    <p style="color:#666;font-size:1rem">${esc(product.sku)} · ${esc(categoryName)}</p>

    <div class="card">
      <h2>${labels.sku} · ${labels.section} · ${labels.category}</h2>
      <table>
        <tr><th>${labels.sku}</th><td>${esc(product.sku)}</td></tr>
        <tr><th>${labels.section}</th><td>${esc(sectionName)}</td></tr>
        <tr><th>${labels.category}</th><td>${esc(categoryName)}</td></tr>
        <tr><th>${labels.weight}</th><td>${esc(weightVal)}</td></tr>
        <tr><th>${labels.shelfLife}</th><td>${esc(shelfLifeVal)}</td></tr>
        <tr><th>${labels.storage}</th><td>${esc(storageVal)}</td></tr>
        <tr><th>${labels.hsCode}</th><td>${esc(hsCodeVal)}</td></tr>
        <tr><th>${labels.halalCert}</th><td>${HALAL_CERT} (${HALAL_ORG})</td></tr>
        <tr><th>${labels.delivery}</th><td>EXW Kazan, Russia</td></tr>
      </table>
    </div>

    <div class="card">
      <h2>${labels.descBlock}</h2>
      <p>${esc(description)}</p>
    </div>

    <div class="card">
      <h2>${labels.specBlock}</h2>
      <table>
        <tr><th>${isRu ? 'Вес нетто' : 'Net weight'}</th><td>${esc(weightVal)}</td></tr>
        <tr><th>${isRu ? 'Штук в коробе' : 'Units per box'}</th><td>${esc(qtyPerBox)}</td></tr>
        <tr><th>${labels.shelfLife}</th><td>${esc(shelfLifeVal)}</td></tr>
        <tr><th>${labels.storage}</th><td>${esc(storageVal)}</td></tr>
        <tr><th>${labels.hsCode}</th><td>${esc(hsCodeVal)}</td></tr>
        <tr><th>${labels.halalCert}</th><td>${HALAL_CERT}</td></tr>
      </table>
    </div>

    <div class="card">
      <h2>${labels.exportBlock}</h2>
      <table>
        <tr><th>${labels.incoterms}</th><td>EXW Kazan</td></tr>
        <tr><th>${labels.moq}</th><td>${isRu ? 'По запросу' : 'On request'}</td></tr>
        <tr><th>${labels.currencies}</th><td>${esc(currenciesList)}</td></tr>
      </table>
      <p style="margin-top:12px">${isRu ? 'Актуальные цены:' : 'Current prices:'} <a href="${BASE}${pathPrefix || ''}/">${BASE}/</a></p>
    </div>

    ${relatedItems ? `<div class="card"><h2>${labels.related}</h2><div class="related">${relatedItems}</div></div>` : ''}

    <footer>
      <p>${footerText}</p>
    </footer>
  </div>
</body>
</html>`;
}
