const res = await fetch('https://pepperoni.tatar/api/products?lang=en');
const data = await res.json();
import { writeFileSync, mkdirSync } from 'fs';

mkdirSync('public/en/products', { recursive: true });

for (const p of data.products) {
  const sku = p.sku;
  const skuLow = sku.toLowerCase();
  const isBakery = !!p.offers?.pricePerUnit;
  const priceRUB = isBakery ? p.offers.pricePerUnit : p.offers.price;
  const priceUSD = p.offers?.exportPrices?.USD || '';
  const name = p.name;
  const desc = `${name}. ${p.category || p.section}. Halal products by Kazan Delicacies. Price: ${priceUSD ? '$'+priceUSD : priceRUB+' ₽'}.`;

  const ep = p.offers?.exportPrices || {};
  const syms = {USD:'$',KZT:'₸',UZS:'UZS',KGS:'KGS',BYN:'BYN',AZN:'AZN'};
  let exportHtml = '';
  if (Object.keys(ep).length) {
    exportHtml = '<h3 style="margin-top:20px;font-size:1rem;color:#1b7a3d">Export Prices</h3><div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0">';
    for (const [cur, val] of Object.entries(ep)) {
      if (val) exportHtml += `<span style="background:#fff;border:1px solid #ddd;padding:6px 12px;border-radius:6px;font-size:.85rem"><b>${val}</b> ${syms[cur]||cur}</span>`;
    }
    exportHtml += '</div>';
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${name} — Kazan Delicacies | Halal</title>
<meta name="description" content="${desc.replace(/"/g, '&quot;')}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://api.pepperoni.tatar/en/products/${skuLow}">
<meta property="og:type" content="product">
<meta property="og:title" content="${name} — Kazan Delicacies">
<meta property="og:url" content="https://api.pepperoni.tatar/en/products/${skuLow}">
<link rel="alternate" hreflang="ru" href="https://api.pepperoni.tatar/products/${skuLow}">
<link rel="alternate" hreflang="en" href="https://api.pepperoni.tatar/en/products/${skuLow}">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"${name.replace(/"/g,'\\"')}","sku":"${sku}","brand":{"@type":"Brand","name":"Kazan Delicacies"},"offers":{"@type":"Offer","priceCurrency":"${priceUSD?'USD':'RUB'}","price":"${priceUSD||priceRUB}","availability":"https://schema.org/InStock"}}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.6}
.container{max-width:900px;margin:0 auto;padding:40px 24px}
.badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;letter-spacing:.5px}
.detail-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:.9rem}
.detail-row dt{color:#767676}
.detail-row dd{color:#1a1a1a;font-weight:500}
.cta-box{background:#f0f7f0;border:2px solid #1b7a3d;border-radius:10px;padding:24px;margin-top:24px}
.cta-box a{display:inline-block;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0}
footer{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}
footer a{color:#444;text-decoration:none}
</style>
</head>
<body>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
<a href="/en/" style="color:#0066cc;text-decoration:none">Catalog</a>
<a href="/en/pepperoni" style="color:#0066cc;text-decoration:none">Pepperoni</a>
<a href="/en/about" style="color:#0066cc;text-decoration:none">About</a>
<a href="/en/delivery" style="color:#0066cc;text-decoration:none">Delivery</a>
<a href="/products/${skuLow}" style="color:#595959;text-decoration:none;margin-left:auto">🇷🇺 Русский</a>
</div>
<a href="/en/" style="display:inline-block;margin-bottom:24px;color:#0066cc;text-decoration:none;font-size:.9rem">← Back to catalog</a>
<h1 style="font-size:1.6rem;margin-bottom:8px">${name}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
<span class="badge">HALAL</span>
<span class="badge" style="background:#0066cc">${sku}</span>
<span class="badge" style="background:#555">${p.section||''}</span>
</div>
${priceUSD ? `<div style="font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0">$${priceUSD} <span style="font-size:.85rem;color:#767676;font-weight:400">${isBakery?'/pc':'excl. VAT'}</span></div>` : `<div style="font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0">${parseFloat(priceRUB).toLocaleString('en-US')} ₽<span style="font-size:.85rem;color:#767676;font-weight:400">${isBakery?' /pc':' incl. VAT'}</span></div>`}
<div style="color:#1b7a3d;font-size:.9rem;margin:8px 0">✓ In stock</div>
${isBakery&&p.offers.pricePerBox?`<div style="margin-top:8px;font-size:.9rem;color:#444">Price per box: <b>${parseFloat(p.offers.pricePerBox).toLocaleString('en-US')} ₽</b>${p.qtyPerBox?' ('+p.qtyPerBox+' pcs)':''}</div>`:''}
<div style="margin:20px 0">
${p.category?`<dl class="detail-row"><dt>Category</dt><dd>${p.category}</dd></dl>`:''}
${p.weight?`<dl class="detail-row"><dt>Unit weight</dt><dd>${p.weight.includes(' g')||p.weight.includes(' kg')?p.weight:(p.weight.replace(',','.')+' kg')}</dd></dl>`:''}
${p.offers?.priceExclVAT?`<dl class="detail-row"><dt>Price excl. VAT</dt><dd>${p.offers.priceExclVAT} ₽</dd></dl>`:''}
${p.shelfLife?`<dl class="detail-row"><dt>Shelf life</dt><dd>${p.shelfLife}</dd></dl>`:''}
${p.storage?`<dl class="detail-row"><dt>Storage</dt><dd>${p.storage}</dd></dl>`:''}
${p.hsCode?`<dl class="detail-row"><dt>HS Code</dt><dd>${p.hsCode}</dd></dl>`:''}
<dl class="detail-row"><dt>Certification</dt><dd>Halal</dd></dl>
<dl class="detail-row"><dt>Brand</dt><dd>Kazan Delicacies</dd></dl>
</div>
${exportHtml}
<div class="cta-box">
<h3 style="margin:0 0 8px">Order</h3>
<p style="color:#444;margin-bottom:12px">Wholesale, export, Private Label</p>
<a href="tel:+79872170202" style="background:#1b7a3d;color:#fff">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject=Order:%20${encodeURIComponent(name)}%20(${sku})" style="border:2px solid #1b7a3d;color:#1b7a3d">📧 Email</a>
</div>
<footer>
<p><a href="/en/pepperoni">Pepperoni</a> · <a href="/en/about">About</a> · <a href="/en/faq">FAQ</a> · <a href="/en/delivery">Delivery</a></p>
<p>© <a href="https://kazandelikates.tatar">Kazan Delicacies</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
</body>
</html>`;

  writeFileSync(`public/en/products/${skuLow}.html`, html);
}
console.log(`Generated ${data.products.length} EN product pages`);
