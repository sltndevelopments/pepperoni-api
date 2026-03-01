import { writeFileSync, mkdirSync } from 'fs';
const data = await fetch('https://pepperoni.tatar/api/products').then(r=>r.json());

const TR={'сосиски «из говядины» (80 г × 6 шт)':'Beef Sausages (80g×6)','сосиски «два мяса» (80 г × 6 шт)':'Two-Meat Sausages (80g×6)','сосиски «три перца с сыром» (80 г × 6 шт)':'Three Peppers & Cheese Sausages (80g×6)','сосиски «куриные» (80 г × 6 шт)':'Chicken Sausages (80g×6)','сосиски «с бараниной» (80 г × 6 шт)':'Lamb Sausages (80g×6)','сосиски «с травами» (130 г × 5 шт)':'Herb Sausages (130g×5)','сосиски «с сыром» (130 г × 5 шт)':'Cheese Sausages (130g×5)','котлета говяжья прожаренная (100 г × 3 шт)':'Fried Beef Patty (100g×3)','котлета говяжья прожаренная (150 г × 2 шт)':'Fried Beef Patty (150g×2)','ветчина из курицы в батоне':'Chicken Ham (whole)','ветчина из курицы в нарезке':'Chicken Ham (sliced)','ветчина из индейки в батоне':'Turkey Ham (whole)','ветчина из индейки в нарезке':'Turkey Ham (sliced)','пепперони вар-коп из конины':'Pepperoni Boiled-Smoked (horse meat)','пепперони вар-коп классика':'Pepperoni Classic (beef & chicken)','пепперони вар-коп классика целый батон':'Pepperoni Classic Whole Stick','пепперони сырокопчёный в нарезке':'Pepperoni Dry-Cured (sliced)','пепперони сырокопчёный целый батон':'Pepperoni Dry-Cured Whole Stick','грудка куриная варено-копченая':'Smoked Chicken Breast','филе куриное варное':'Boiled Chicken Fillet','фарш говяжий':'Beef Mince','фарш из куриной кожи':'Chicken Skin Mince','филе бедра куриного в кубике 1х1 см':'Diced Chicken Thigh 1×1cm','филе грудки куриной в кубике 1х1 см':'Diced Chicken Breast 1×1cm','говядина 1 сорт в кубике 1х1 см':'Diced Beef Grade 1 1×1cm','сосиски «к завтраку»':'Breakfast Sausages','сосиски «нежные»':'Tender Sausages','сосиски «казанские с молоком»':'Kazan Milk Sausages','сосиски «с сыром»':'Cheese Sausages','сосиски «из говядины»':'Beef Sausages','сосиски "из говядины"':'Beef Sausages','сосиски в/с премиум':'Premium Sausages','сосиски в/с сочные':'Juicy Sausages','сардельки «буинские"':'Buinsk Frankfurters','сардельки «буинские»':'Buinsk Frankfurters','вареная «из говядины»':'Boiled Beef Sausage','вареная ассорти':'Boiled Assorted Sausage','вареная нежная':'Boiled Tender Sausage','ветчина из индейки':'Turkey Ham','ветчина мраморная с говядиной':'Marbled Beef Ham','ветчина из курицы':'Chicken Ham','ветчина филейная':'Fillet Ham','сервелат ханский':'Khan Cervelat','сервелат по-татарски в/к':'Tatar-Style Smoked Cervelat','полукопченая из индейки':'Semi-Smoked Turkey Sausage','полукопченая из говядины':'Semi-Smoked Beef Sausage','колбаски с сыром':'Cheese Sausage Links','грудка куриная':'Chicken Breast','филе куриное':'Chicken Fillet','в/к рамазан':'Ramazan Smoked Sausage','в/к рамазан (половинка)':'Ramazan Smoked (half)','в/к мраморная':'Marbled Smoked Sausage','в/к мраморная (половинка)':'Marbled Smoked (half)','в/к филейный':'Fillet Smoked Sausage','в/к филейный (половинка)':'Fillet Smoked (half)','в/к княжеская':'Knyazheskaya Smoked Sausage','в/к княжеская (половинка)':'Knyazheskaya Smoked (half)','казылык «премиум» в подарочной упаковке':'Kazylyk Premium (gift box)','казылык «премиум» в нарезке в подарочной упаковке':'Kazylyk Premium Sliced (gift box)','губадия с кортом':'Gubadiya with Kort','чебурек жареный':'Fried Cheburek','перемяч жареный':'Fried Peremyach','самса с курицей':'Chicken Samsa','эчпочмак с говядиной и картофелем':'Echpochmak (beef & potato)','самса с говядиной':'Beef Samsa','элеш с курицей и картофелем':'Elesh (chicken & potato)','чак-чак в пластиковой упаковке':'Chak-Chak (plastic)','чак-чак в крафтовой подарочной упаковке':'Chak-Chak (gift box)','сочник с творогом':'Cottage Cheese Sochnik','пирожок печеный с картофелем':'Baked Potato Pie','сырник':'Syrnik','пирожок с яблоком':'Apple Pie','пирожок с зеленым луком и яйцом':'Spring Onion & Egg Pie','маффин апельсиновый':'Orange Muffin','сосиска в тесте':'Sausage Roll','пирожок с вишней':'Cherry Pie','круассан с шоколадом и орехами':'Chocolate & Nut Croissant','маффин шоколадный':'Chocolate Muffin'};
const CAT_TR={'Сосиски гриль для хот-догов':'Grill Sausages for Hot Dogs','Котлеты для бургеров':'Burger Patties','Топпинги':'Toppings','Мясные заготовки':'Meat Preparations','Сосиски, сардельки':'Sausages & Frankfurters','Вареные':'Boiled Sausages','Ветчины':'Hams','Копченые':'Smoked Meats','Премиум Казылык':'Premium Kazylyk','Национальная татарская выпечка':'Traditional Tatar Pastries','Классическая выпечка':'Classic Pastries','Заморозка':'Frozen Products','Охлаждённая продукция':'Refrigerated Products','Выпечка':'Bakery'};
const SHELF_TR={'30 суток':'30 days','60 суток':'60 days','180 суток':'180 days','360 суток':'360 days'};
function trName(n){return TR[n.toLowerCase().trim().replace(/\s+/g,' ')]||n}
function trCat(c){return CAT_TR[c]||c}
function trShelf(s){return SHELF_TR[s]||s.replace(/суток/,'days')}
function esc(s){return (s||'').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}

const CSS=`*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.6}
.container{max-width:900px;margin:0 auto;padding:40px 24px}
.badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600}
.detail-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:.9rem}
.detail-row dt{color:#767676}.detail-row dd{color:#1a1a1a;font-weight:500}
.cta-box{background:#f0f7f0;border:2px solid #1b7a3d;border-radius:10px;padding:24px;margin-top:24px}
.cta-box a{display:inline-block;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0}
footer{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}
footer a{color:#444;text-decoration:none}`;

function exportBlock(ep, sym) {
  if(!ep||!Object.keys(ep).length) return '';
  const syms={USD:'$',KZT:'₸',UZS:'UZS',KGS:'KGS',BYN:'BYN',AZN:'AZN'};
  let h=`<h3 style="margin-top:20px;font-size:1rem;color:#1b7a3d">${sym.exportTitle}</h3><div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0">`;
  for(const[c,v]of Object.entries(ep)){if(v)h+=`<span style="background:#fff;border:1px solid #ddd;padding:6px 12px;border-radius:6px;font-size:.85rem"><b>${v}</b> ${syms[c]||c}</span>`}
  return h+'</div>';
}

function genPage(p, lang) {
  const sku=p.sku, skuLow=sku.toLowerCase();
  const isEN=lang==='en';
  const isBakery=!!p.offers?.pricePerUnit;
  const priceRUB=isBakery?p.offers.pricePerUnit:p.offers.price;
  const priceNoVAT=p.offers?.priceExclVAT||p.offers?.pricePerBoxExclVAT||'';
  const ep=p.offers?.exportPrices||{};
  const priceUSD=ep.USD||'';
  const name=isEN?trName(p.name):p.name;
  const cat=isEN?trCat(p.category||''):p.category||'';
  const sec=isEN?trCat(p.section||''):p.section||'';
  const shelf=isEN?trShelf(p.shelfLife||''):p.shelfLife||'';

  const L=isEN?{
    lang:'en',title:`${name} — Kazan Delicacies | Halal`,brand:'Kazan Delicacies',
    back:'← Back to catalog',backHref:'/en/',catalog:'Catalog',pepperoni:'Pepperoni',about:'About',delivery:'Delivery',faq:'FAQ',
    langSwitch:`<a href="/products/${skuLow}" style="color:#595959;text-decoration:none;margin-left:auto">🇷🇺 Русский</a>`,
    navPfx:'/en/',inclVAT:'incl. VAT',exclVAT:'excl. VAT',perPc:'/pc',inStock:'✓ In stock',
    category:'Category',weight:'Unit weight',weightUnit:'kg',priceExclVAT:'Price excl. VAT',
    shelfLife:'Shelf life',storage:'Storage',hsCode:'HS Code',cert:'Certification',mfr:'Brand',
    order:'Order',orderDesc:'Wholesale, export, Private Label available',contact:'📧 Email',
    exportTitle:'Export Prices',priceBox:'Price per box',pcs:'pcs'
  }:{
    lang:'ru',title:`${name} — Казанские Деликатесы | Халяль`,brand:'Казанские Деликатесы',
    back:'← Каталог',backHref:'/',catalog:'Каталог',pepperoni:'Пепперони',about:'О компании',delivery:'Доставка',faq:'FAQ',
    langSwitch:`<a href="/en/products/${skuLow}" style="color:#595959;text-decoration:none;margin-left:auto">🇬🇧 English</a>`,
    navPfx:'/',inclVAT:'с НДС',exclVAT:'без НДС',perPc:'/шт',inStock:'✓ В наличии',
    category:'Категория',weight:'Вес расчёта',weightUnit:'',priceExclVAT:'Цена без НДС',
    shelfLife:'Срок годности',storage:'Хранение',hsCode:'ТН ВЭД',cert:'Сертификация',mfr:'Производитель',
    order:'Заказ',orderDesc:'Оптом, экспорт, Private Label',contact:'📧 Написать',
    exportTitle:'Экспортные цены',priceBox:'Цена за коробку',pcs:'шт'
  };

  return `<!DOCTYPE html>
<html lang="${L.lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(L.title)}</title>
<meta name="description" content="${esc(name+'. '+cat+'. '+(isEN?'Halal products by Kazan Delicacies.':'Халяль продукция от Казанских Деликатесов.'))}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://api.pepperoni.tatar/${isEN?'en/':''}products/${skuLow}">
<link rel="alternate" hreflang="ru" href="https://api.pepperoni.tatar/products/${skuLow}">
<link rel="alternate" hreflang="en" href="https://api.pepperoni.tatar/en/products/${skuLow}">
<meta property="og:type" content="product">
<meta property="og:title" content="${esc(name+' — '+L.brand)}">
<meta property="og:url" content="https://api.pepperoni.tatar/${isEN?'en/':''}products/${skuLow}">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"${name.replace(/"/g,'\\"')}","sku":"${sku}","brand":{"@type":"Brand","name":"${L.brand}"},"offers":{"@type":"Offer","priceCurrency":"${priceUSD?'USD':'RUB'}","price":"${priceUSD||priceRUB}","availability":"https://schema.org/InStock"}}
</script>
<style>${CSS}</style>
</head>
<body>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
<a href="${L.navPfx}" style="color:#0066cc;text-decoration:none">${L.catalog}</a>
<a href="${L.navPfx}pepperoni" style="color:#0066cc;text-decoration:none">${L.pepperoni}</a>
<a href="${L.navPfx}about" style="color:#0066cc;text-decoration:none">${L.about}</a>
<a href="${L.navPfx}delivery" style="color:#0066cc;text-decoration:none">${L.delivery}</a>
${L.langSwitch}
</div>
<a href="${L.backHref}" style="display:inline-block;margin-bottom:24px;color:#0066cc;text-decoration:none;font-size:.9rem">${L.back}</a>
<h1 style="font-size:1.6rem;margin-bottom:8px">${name}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
<span class="badge">HALAL</span>
<span class="badge" style="background:#0066cc">${sku}</span>
<span class="badge" style="background:#555">${sec}</span>
</div>
${priceUSD?`<div style="font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0">$${priceUSD} <span style="font-size:.85rem;color:#767676;font-weight:400">${isBakery?L.perPc:L.exclVAT}</span></div>`:''}
<div style="${priceUSD?'color:#767676;font-size:.9rem':'font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0'}">${parseFloat(priceRUB).toLocaleString(isEN?'en-US':'ru-RU')} ₽${isBakery?' '+L.perPc:' '+L.inclVAT}</div>
<div style="color:#1b7a3d;font-size:.9rem;margin:8px 0">${L.inStock}</div>
${isBakery&&p.offers?.pricePerBox?`<div style="margin-top:8px;font-size:.9rem;color:#444">${L.priceBox}: <b>${parseFloat(p.offers.pricePerBox).toLocaleString(isEN?'en-US':'ru-RU')} ₽</b>${p.qtyPerBox?' ('+p.qtyPerBox+' '+L.pcs+')':''}</div>`:''}
<div style="margin:20px 0">
${cat?`<dl class="detail-row"><dt>${L.category}</dt><dd>${cat}</dd></dl>`:''}
${p.weight?`<dl class="detail-row"><dt>${L.weight}</dt><dd>${p.weight}${L.weightUnit?' '+L.weightUnit:''}</dd></dl>`:''}
${priceNoVAT?`<dl class="detail-row"><dt>${L.priceExclVAT}</dt><dd>${priceNoVAT} ₽</dd></dl>`:''}
${shelf?`<dl class="detail-row"><dt>${L.shelfLife}</dt><dd>${shelf}</dd></dl>`:''}
${p.storage?`<dl class="detail-row"><dt>${L.storage}</dt><dd>${p.storage}</dd></dl>`:''}
${p.hsCode?`<dl class="detail-row"><dt>${L.hsCode}</dt><dd>${p.hsCode}</dd></dl>`:''}
<dl class="detail-row"><dt>${L.cert}</dt><dd>Halal</dd></dl>
<dl class="detail-row"><dt>${L.mfr}</dt><dd>${L.brand}</dd></dl>
</div>
${exportBlock(ep,L)}
<div class="cta-box">
<h3 style="margin:0 0 8px">${L.order}</h3>
<p style="color:#444;margin-bottom:12px">${L.orderDesc}</p>
<a href="tel:+79872170202" style="background:#1b7a3d;color:#fff">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject=${encodeURIComponent((isEN?'Order':'Заказ')+': '+name+' ('+sku+')')}" style="border:2px solid #1b7a3d;color:#1b7a3d">${L.contact}</a>
</div>
<footer>
<p><a href="${L.navPfx}pepperoni">${L.pepperoni}</a> · <a href="${L.navPfx}about">${L.about}</a> · <a href="${L.navPfx}faq">${L.faq}</a> · <a href="${L.navPfx}delivery">${L.delivery}</a></p>
<p>© <a href="https://kazandelikates.tatar">${L.brand}</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
</body>
</html>`;
}

mkdirSync('public/products',{recursive:true});
mkdirSync('public/en/products',{recursive:true});

for(const p of data.products){
  const f=p.sku.toLowerCase();
  writeFileSync(`public/products/${f}.html`,genPage(p,'ru'));
  writeFileSync(`public/en/products/${f}.html`,genPage(p,'en'));
}
console.log(`Generated ${data.products.length} RU + ${data.products.length} EN product pages`);
