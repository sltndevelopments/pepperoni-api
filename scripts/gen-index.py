#!/usr/bin/env python3
"""
Generate public/index.html and public/en/index.html
Halal B2B landing pages for pepperoni.tatar — Kazan Delicacies.
Usage: python3 scripts/gen-index.py
"""

from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "public"

YEAR = datetime.now().year

GTM = (
    "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':"
    "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],"
    "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src="
    "'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);"
    "})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>"
)

YM = (
    "<script>(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
    "m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return}"
    "k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);"
    "})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');"
    "ym(107064141,'init',{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:'dataLayer'});</script>"
    "<noscript><div><img src='https://mc.yandex.ru/watch/107064141' style='position:absolute;left:-9999px' alt=''/></div></noscript>"
)


def gen_ru() -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<meta http-equiv="content-language" content="ru">
<title>Производитель мясных деликатесов Халяль оптом | Казанские Деликатесы</title>
<meta name="description" content="Халяль пепперони, сосиски, котлеты для бургеров, татарская выпечка оптом от производителя в Казани. ХАССП, FSSC 22000, сертификат ДУМ РТ. EXW Казань. HoReCa, ретейл, экспорт СНГ.">
<meta name="keywords" content="халяль пепперони оптом, сосиски халяль, котлеты для бургеров халяль, татарская выпечка, мясные изделия казань, производитель халяль, ХАССП, FSSC 22000">
<meta name="author" content="Казанские Деликатесы">
<meta name="robots" content="index, follow">
<meta name="yandex-verification" content="d0a735c825c78ddf">
<link rel="canonical" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/">
<link rel="llms" href="/llms.txt" type="text/plain" title="LLM instructions">
<link rel="alternate" type="application/json" title="Live Product Catalog (JSON)" href="https://pepperoni.tatar/products.json">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1b7a3d">
<meta property="og:type" content="website">
<meta property="og:title" content="Производитель мясных деликатесов Халяль оптом | Казанские Деликатесы">
<meta property="og:description" content="Халяль пепперони, сосиски, котлеты, выпечка оптом. ХАССП, FSSC 22000, ДУМ РТ. Экспорт. EXW Казань.">
<meta property="og:url" content="https://pepperoni.tatar/">
<meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Производитель халяль мясных изделий оптом | Казанские Деликатесы">
<meta name="twitter:description" content="Пепперони, сосиски, котлеты, выпечка. 100% Халяль. EXW Казань.">
<meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<script type="application/ld+json">
{{
  "@context":"https://schema.org","@type":"Organization",
  "name":"Казанские Деликатесы","alternateName":["Kazan Delicacies","ООО «Казанские Деликатесы»"],
  "legalName":"ООО «Казанские Деликатесы»","url":"https://pepperoni.tatar",
  "logo":"https://pepperoni.tatar/images/logo.png",
  "email":"info@kazandelikates.tatar","telephone":"+79872170202",
  "description":"Производитель халяль мясных изделий в Татарстане. Пепперони, сосиски, котлеты для бургеров, татарская выпечка. ХАССП, FSSC 22000. СТМ.",
  "address":{{"@type":"PostalAddress","streetAddress":"ул. Мусина 83А","addressLocality":"Казань","postalCode":"420061","addressRegion":"Татарстан","addressCountry":"RU"}},
  "hasCredential":{{"@type":"EducationalOccupationalCredential","name":"Halal","identifier":"614A/2024","recognizedBy":{{"@type":"Organization","name":"ДУМ РТ","url":"https://dumrt.ru"}}}},
  "contactPoint":[
    {{"@type":"ContactPoint","telephone":"+79872170202","contactType":"sales","areaServed":["RU","KZ","UZ","BY","AM","AZ","KG"],"availableLanguage":["Russian","English"]}},
    {{"@type":"ContactPoint","url":"https://wa.me/79872170202","contactType":"customer support","areaServed":"RU","availableLanguage":"Russian"}}
  ],
  "sameAs":["https://pepperoni.tatar","https://kazandelikates.tatar"]
}}
</script>
<style>
:root{{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.08)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:var(--text);line-height:1.6;font-size:16px}}
a{{text-decoration:none;color:inherit}}
img{{max-width:100%;height:auto}}
.container{{max-width:960px;margin:0 auto;padding:0 20px}}

/* Nav */
.nav{{background:#fff;border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100}}
.nav__inner{{display:flex;align-items:center;gap:20px;flex-wrap:wrap}}
.nav__logo{{font-weight:700;font-size:1.05rem;color:var(--green)}}
.nav__links{{display:flex;gap:16px;flex-wrap:wrap;font-size:.88rem}}
.nav__links a{{color:var(--muted);transition:color .2s}}
.nav__links a:hover{{color:var(--green)}}
.nav__lang{{margin-left:auto;font-size:.85rem}}

/* Hero */
.hero{{background:linear-gradient(135deg,#0f4d22 0%,var(--green) 60%,#2d9e56 100%);color:#fff;padding:56px 0 48px;text-align:center}}
.hero__badge{{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);color:#fff;padding:5px 14px;border-radius:20px;font-size:.8rem;font-weight:600;letter-spacing:.5px;margin-bottom:18px}}
.hero h1{{font-size:clamp(1.5rem,3.5vw,2.4rem);font-weight:800;line-height:1.2;margin-bottom:14px;max-width:750px;margin-left:auto;margin-right:auto}}
.hero__sub{{font-size:1rem;opacity:.88;max-width:560px;margin:0 auto 28px}}
.hero__btns{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.btn{{display:inline-block;padding:12px 26px;border-radius:8px;font-weight:600;font-size:.92rem;cursor:pointer;transition:all .2s}}
.btn-primary{{background:#fff;color:var(--green)}}
.btn-primary:hover{{background:var(--green-light);transform:translateY(-1px)}}
.btn-outline{{background:transparent;border:2px solid rgba(255,255,255,.6);color:#fff}}
.btn-outline:hover{{background:rgba(255,255,255,.1);transform:translateY(-1px)}}

/* Badges strip */
.badges{{background:#fff;border-bottom:1px solid var(--border);padding:12px 0}}
.badges__inner{{display:flex;justify-content:center;gap:24px;flex-wrap:wrap;font-size:.83rem;font-weight:600;color:var(--muted)}}
.badges__item{{display:flex;align-items:center;gap:6px}}
.badges__item .dot{{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0}}

/* USPs */
.usps{{padding:48px 0 0}}
.section-title{{font-size:1.4rem;font-weight:700;text-align:center;margin-bottom:6px}}
.section-sub{{text-align:center;color:var(--muted);margin-bottom:28px;font-size:.9rem}}
.usps__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-bottom:48px}}
.usp-card{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:22px;transition:box-shadow .2s,border-color .2s}}
.usp-card:hover{{box-shadow:var(--shadow);border-color:var(--green)}}
.usp-card__icon{{font-size:1.8rem;margin-bottom:10px}}
.usp-card__title{{font-weight:700;margin-bottom:5px;font-size:.92rem}}
.usp-card__text{{color:var(--muted);font-size:.85rem;line-height:1.5}}

/* Catalog section */
.catalog-section{{padding:0 0 48px}}
.catalog-header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:4px}}
.category-title{{font-size:1.1rem;font-weight:700;margin:28px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--green);color:var(--green)}}
.products-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-bottom:6px}}
a.product-card-link{{text-decoration:none;color:inherit;display:block}}
.product-card{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:18px;transition:box-shadow .2s,border-color .2s;cursor:pointer;height:100%}}
.product-card:hover{{box-shadow:var(--shadow);border-color:var(--green)}}
.product-name{{font-size:.92rem;font-weight:600;margin-bottom:4px}}
.product-sku{{font-size:.72rem;color:#767676;margin-bottom:7px;display:flex;flex-wrap:wrap;gap:5px;align-items:center}}
.product-sku .prop{{display:inline-block;padding:2px 6px;background:#e8e8e8;color:#333;border-radius:4px;font-size:.68rem}}
.product-price{{font-size:1.2rem;font-weight:700;color:var(--green)}}
.product-price-vat{{font-size:.7rem;color:var(--muted);font-weight:400}}
.product-avail{{font-size:.78rem;color:var(--green);margin-top:5px}}

/* Certs */
.certs{{background:var(--green-light);padding:32px 0}}
.certs__inner{{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;align-items:center}}
.cert-item__name{{font-weight:700;font-size:.88rem;color:var(--green)}}
.cert-item__desc{{font-size:.75rem;color:var(--muted)}}

/* Download & API blocks */
.info-block{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin:20px 0}}
.info-block h2{{font-size:1.1rem;font-weight:700;margin-bottom:10px}}
.info-block p{{font-size:.88rem;color:var(--muted);margin-bottom:12px}}
.info-block a{{color:var(--green);font-weight:600}}
.btn-dl{{display:inline-block;padding:9px 20px;border-radius:7px;font-weight:600;font-size:.85rem;margin:3px 4px 3px 0;cursor:pointer;text-decoration:none}}
.btn-dl-solid{{background:#0066cc;color:#fff;border:none}}
.btn-dl-outline{{border:2px solid #0066cc;color:#0066cc;background:#fff}}
select.dl-select{{padding:6px 10px;border-radius:6px;border:1px solid #ddd;font-size:.83rem}}

/* Capabilities */
.capabilities-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:16px}}
.capability-card{{background:var(--green-light);border-radius:var(--radius);padding:18px}}
.capability-card h3{{font-size:.92rem;margin-bottom:6px}}
.capability-card p{{font-size:.82rem;color:#444;line-height:1.5}}

/* Footer */
.footer{{background:#1a1a1a;color:#ccc;padding:36px 0 20px}}
.footer__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:24px;margin-bottom:24px}}
.footer__col-title{{color:#fff;font-weight:600;margin-bottom:10px;font-size:.88rem}}
.footer__col p,.footer__col a{{font-size:.82rem;color:#aaa;display:block;margin-bottom:5px}}
.footer__col a:hover{{color:#fff}}
.footer__bottom{{border-top:1px solid #333;padding-top:14px;text-align:center;font-size:.78rem;color:#666}}

/* Endpoint list */
.endpoint-list{{list-style:none;font-size:.85rem}}
.endpoint-list li{{padding:5px 0;border-bottom:1px solid var(--border)}}
.endpoint-list a{{color:#0066cc}}
.live-badge{{display:inline-block;background:#1b7a3d;color:#fff;font-size:.65rem;font-weight:700;padding:1px 6px;border-radius:3px;margin-left:6px;vertical-align:middle}}
.endpoint-desc{{color:var(--muted);font-size:.8rem}}

@media(max-width:600px){{
  .hero{{padding:40px 0 32px}}
  .usps{{padding:32px 0 0}}
  .nav__links{{gap:10px;font-size:.82rem}}
  .certs__inner{{gap:16px}}
}}
</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<nav class="nav">
  <div class="container nav__inner">
    <span class="nav__logo">🥩 Казанские Деликатесы</span>
    <div class="nav__links">
      <a href="/pepperoni">Пепперони</a>
      <a href="/kazylyk">Казылык</a>
      <a href="/bakery">Выпечка</a>
      <a href="/about">О компании</a>
      <a href="/faq">FAQ</a>
      <a href="/delivery">Доставка</a>
      <a href="/blog">Блог</a>
      <a href="/openapi.yaml">API</a>
    </div>
    <div class="nav__lang"><a href="/en/">🇬🇧 English</a></div>
  </div>
</nav>

<section class="hero">
  <div class="container">
    <div class="hero__badge">🌿 100% ХАЛЯЛЬ · ХАССП · FSSC 22000</div>
    <h1>Производитель халяль мясных деликатесов для HoReCa и ретейла</h1>
    <p class="hero__sub">Пепперони, сосиски, котлеты для бургеров, татарская выпечка. Сделано в Казани. Экспорт по СНГ и Ближнему Востоку.</p>
    <div class="hero__btns">
      <a href="#catalog" class="btn btn-primary">Смотреть каталог</a>
      <a href="mailto:info@kazandelikates.tatar" class="btn btn-outline">Связаться с нами</a>
    </div>
  </div>
</section>

<div class="badges">
  <div class="container badges__inner">
    <span class="badges__item"><span class="dot"></span>Сертификат Халяль ДУМ РТ №614A/2024</span>
    <span class="badges__item"><span class="dot"></span>ХАССП + FSSC 22000</span>
    <span class="badges__item"><span class="dot"></span>ТР ТС 021/2011</span>
    <span class="badges__item"><span class="dot"></span>EXW Казань · Склад Люберцы</span>
    <span class="badges__item"><span class="dot"></span>Private Label / СТМ</span>
  </div>
</div>

<section class="usps">
  <div class="container">
    <h2 class="section-title">Почему выбирают нас</h2>
    <p class="section-sub">Производство в Татарстане. Поставки по России и на экспорт.</p>
    <div class="usps__grid">
      <div class="usp-card"><div class="usp-card__icon">🏭</div><div class="usp-card__title">Собственное производство</div><div class="usp-card__text">Производим в Казани с 2022 года. Полный контроль качества от сырья до отгрузки. ХАССП на всех этапах.</div></div>
      <div class="usp-card"><div class="usp-card__icon">🌍</div><div class="usp-card__title">Экспорт EXW Казань</div><div class="usp-card__text">Поставляем в Казахстан, Беларусь, Узбекистан, ОАЭ. Ветеринарные сертификаты, таможенное оформление.</div></div>
      <div class="usp-card"><div class="usp-card__icon">🏷️</div><div class="usp-card__title">Private Label (СТМ)</div><div class="usp-card__text">Производим под вашим брендом. Разработка рецептуры, дизайн упаковки. От 100 кг партия.</div></div>
      <div class="usp-card"><div class="usp-card__icon">☪️</div><div class="usp-card__title">Строгий стандарт Халяль</div><div class="usp-card__text">Только говядина, курица, конина, индейка. Без свинины, без ГМО, без нитрита натрия. Сертификат ДУМ РТ.</div></div>
    </div>
  </div>
</section>

<section class="catalog-section" id="catalog">
  <div class="container">
    <h2 class="section-title" style="margin-top:48px">Полный каталог продукции</h2>
    <p class="section-sub">Актуальные цены · переключайте валюту и НДС</p>
    <div id="catalog-inner" style="min-height:400px">
      <div id="loading" style="text-align:center;padding:40px;color:var(--muted)">Загрузка каталога...</div>
    </div>
  </div>
</section>

<section class="certs">
  <div class="container">
    <h2 class="section-title" style="margin-bottom:20px">Сертификаты и стандарты</h2>
    <div class="certs__inner">
      <div class="cert-item"><div class="cert-item__name">☪️ Халяль</div><div class="cert-item__desc">ДУМ РТ №614A/2024</div></div>
      <div class="cert-item"><div class="cert-item__name">✅ ХАССП</div><div class="cert-item__desc">Hazard Analysis</div></div>
      <div class="cert-item"><div class="cert-item__name">🏆 FSSC 22000</div><div class="cert-item__desc">Food Safety</div></div>
      <div class="cert-item"><div class="cert-item__name">📋 ISO 22000</div><div class="cert-item__desc">Food Management</div></div>
      <div class="cert-item"><div class="cert-item__name">🇷🇺 ТР ТС 021/2011</div><div class="cert-item__desc">Таможенный союз</div></div>
      <div class="cert-item"><div class="cert-item__name">🐄 Ветеринарные</div><div class="cert-item__desc">Свидетельства РФ</div></div>
    </div>
  </div>
</section>

<div class="container">
  <div class="info-block" style="background:#f5f5ff;border-color:#0066cc">
    <h2>📥 Скачать прайс-лист</h2>
    <p>Полный каталог — откроется в Excel, Google Sheets, Numbers.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px">
      <label style="font-size:.83rem;color:#555">Язык:</label>
      <select id="dl-lang" class="dl-select"><option value="ru" selected>Русский</option><option value="en">English</option></select>
      <label style="font-size:.83rem;color:#555;margin-left:8px">Валюта:</label>
      <select id="dl-cur" class="dl-select"><option value="RUB" selected>RUB ₽</option><option value="USD">USD $</option><option value="KZT">KZT ₸</option><option value="UZS">UZS</option><option value="KGS">KGS</option><option value="BYN">BYN</option><option value="AZN">AZN</option></select>
      <span id="dl-vat-wrap" style="margin-left:8px">
        <label style="font-size:.83rem;color:#555">НДС:</label>
        <select id="dl-vat" class="dl-select"><option value="true" selected>С НДС</option><option value="false">Без НДС</option></select>
      </span>
    </div>
    <a href="#" onclick="event.preventDefault();downloadFile('xlsx')" class="btn-dl btn-dl-solid">📊 Скачать Excel (.xlsx)</a>
    <a href="#" onclick="event.preventDefault();downloadFile('csv')" class="btn-dl btn-dl-outline">📄 Скачать CSV</a>
    <script>
      document.getElementById('dl-cur').addEventListener('change',function(){{document.getElementById('dl-vat-wrap').style.display=this.value==='RUB'?'':'none';}});
      function downloadFile(fmt){{const lang=document.getElementById('dl-lang').value,cur=document.getElementById('dl-cur').value,vat=document.getElementById('dl-vat').value,vatParam=cur==='RUB'?`&vat=${{vat}}`:'';window.location.href=`/api/export?lang=${{lang}}&currency=${{cur}}&format=${{fmt}}${{vatParam}}`;}}
    </script>
  </div>

  <div class="info-block" style="background:var(--green-light);border-color:var(--green)">
    <h2 style="color:var(--green)">🤝 Производственные решения для HoReCa и Ритейла</h2>
    <p>Мы не просто поставляем продукцию — адаптируем под бизнес-процессы вашей сети.</p>
    <div class="capabilities-grid">
      <div class="capability-card"><h3>🏷️ Private Label (СТМ)</h3><p>Производство под вашей торговой маркой. От разработки рецептуры до брендирования упаковки.</p></div>
      <div class="capability-card"><h3>🎯 Кастомизация под меню</h3><p>Пепперони из курицы, говядины или конины — в батонах и нарезках. Нужна пепперони для 350°C? Меняем остроту, диаметр, состав.</p></div>
      <div class="capability-card"><h3>✅ 100% Халяль и ХАССП</h3><p>Только говядина, курица, конина, индейка. Сертификат ДУМ РТ. Без свинины, без ГМО.</p></div>
      <div class="capability-card"><h3>🚚 Экспорт и Логистика</h3><p>Поставки на условиях EXW и DAP. Строгое соблюдение температурного режима до вашего РЦ.</p></div>
    </div>
  </div>

  <div class="info-block">
    <h2>Наши партнёры</h2>
    <p>АЗС Татнефть · EuroSpar · Бэхетле · пиццерии и HoReCa по России.</p>
  </div>

  <div class="info-block">
    <h2>Связаться</h2>
    <p>Оптовые поставки, экспорт, Private Label — обсудим условия.</p>
    <a href="tel:+79872170202" class="btn-dl btn-dl-solid">📞 +7 987 217-02-02</a>
    <a href="mailto:info@kazandelikates.tatar" class="btn-dl btn-dl-outline" style="border-color:var(--green);color:var(--green)">📧 info@kazandelikates.tatar</a>
    <a href="https://wa.me/79872170202" class="btn-dl btn-dl-outline" style="border-color:#25d366;color:#25d366">💬 WhatsApp</a>
  </div>

  <div class="info-block">
    <h2>API для партнёров</h2>
    <p>Интегрируйте каталог халяль товаров напрямую в ERP, 1С, iiko или МойСклад. Цены обновляются в реальном времени. <a href="/openapi.yaml">OpenAPI</a> · <a href="/api/products">JSON</a></p>
    <ul class="endpoint-list" style="margin-top:12px">
      <li><a href="/api/products">/api/products</a><span class="live-badge">LIVE</span><span class="endpoint-desc"> — актуальные цены из Google Sheets</span></li>
      <li><a href="/products.json">/products.json</a><span class="endpoint-desc"> — статический каталог</span></li>
      <li><a href="/openapi.yaml">/openapi.yaml</a><span class="endpoint-desc"> — OpenAPI спецификация</span></li>
      <li><a href="/.well-known/ai-plugin.json">/.well-known/ai-plugin.json</a><span class="endpoint-desc"> — манифест AI-плагина</span></li>
      <li><a href="/llms.txt">/llms.txt</a><span class="endpoint-desc"> — инструкции для LLM</span></li>
      <li><a href="/sitemap.xml">/sitemap.xml</a><span class="endpoint-desc"> — карта сайта</span></li>
    </ul>
  </div>
</div>

<footer class="footer">
  <div class="container">
    <div class="footer__grid">
      <div class="footer__col">
        <div class="footer__col-title">Казанские Деликатесы</div>
        <p>Производитель халяль мясных изделий в Татарстане.</p>
        <p>© 2022–{YEAR} ООО «Казанские Деликатесы»</p>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Производство</div>
        <p>г. Казань, ул. Мусина 83А</p>
        <p>Татарстан, 420061</p>
        <a href="tel:+79872170202">+7 987 217-02-02</a>
        <a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Склад и отгрузка</div>
        <p>Москва (Люберцы) — наш склад</p>
        <p>EXW Казань</p>
        <p>Отгрузка: Пн–Пт 9:00–18:00</p>
        <a href="https://wa.me/79872170202">WhatsApp: +7 987 217-02-02</a>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Разделы</div>
        <a href="/pepperoni">Пепперони</a>
        <a href="/kazylyk">Казылык</a>
        <a href="/bakery">Выпечка</a>
        <a href="/faq">FAQ</a>
        <a href="/delivery">Доставка</a>
        <a href="/blog">Блог</a>
        <a href="/en/">English version</a>
        <a href="/openapi.yaml">API для партнёров</a>
      </div>
    </div>
    <div class="footer__bottom">
      <a href="https://kazandelikates.tatar">kazandelikates.tatar</a> &nbsp;·&nbsp;
      <a href="https://pepperoni.tatar">pepperoni.tatar</a> &nbsp;·&nbsp;
      Халяль · ХАССП · FSSC 22000 · EXW Казань
    </div>
  </div>
</footer>

{YM}
<script>
const CUR_SYM={{RUB:'₽',USD:'$',KZT:'₸',UZS:'сум',KGS:'сом',BYN:'Br',AZN:'₼'}};
let CUR='RUB',VAT=true,ALL_GROUPS=[];

function getPrice(p){{
  if(CUR==='RUB')return VAT?p.price:p.priceNoVAT;
  const m={{USD:p.usd,KZT:p.kzt,UZS:p.uzs,KGS:p.kgs,BYN:p.byn,AZN:p.azn}};
  let v=m[CUR]||0;
  if(p.isBakery&&p.qty){{const q=parseFloat(p.qty)||1;if(q>0)v=v/q;}}
  return v;
}}
function fmtPrice(v){{if(!v)return'—';return v.toLocaleString('ru-RU',{{minimumFractionDigits:v<10?2:0,maximumFractionDigits:2}})}}
const fmtWeight=w=>{{if(!w)return'';const s=String(w).trim();return/[\s]*(г|g|кг|kg)\s*$/i.test(s)?s:s+' кг'}};
const fmtQty=q=>{{if(!q)return'';const s=String(q).trim();return/\d+\s*шт/i.test(s)?s:s+' шт/кор'}};
const looksLikePrice=v=>/^\d{{2,}}[.,]\d{{2}}$/.test(String(v||'').trim());

function renderGroups(allGroups){{
  let html='';
  const sym=CUR_SYM[CUR]||CUR;
  const vatLabel=CUR==='RUB'?(VAT?'с НДС':'без НДС'):'';
  for(const{{section,icon,groups}}of allGroups){{
    html+=`<h2 style="font-size:1.3rem;margin:36px 0 4px;color:#333">${{icon}} ${{section}}</h2>`;
    for(const[cat,products]of Object.entries(groups)){{
      html+=`<h3 class="category-title">${{cat}}</h3><div class="products-grid">`;
      for(const p of products){{
        const pr=getPrice(p);
        const priceCur=CUR==='RUB'?'RUB':CUR;
        const priceLabel=p.isBakery
          ?`${{fmtPrice(pr)}} ${{sym}}/шт`
          :`${{fmtPrice(pr)}} ${{sym}} <span class="product-price-vat">${{vatLabel}}</span>`;
        const props=[];
        if(p.weight&&!looksLikePrice(p.weight))props.push(`<span class="prop" title="Вес расчёта">${{fmtWeight(p.weight)}}</span>`);
        if(p.isBakery&&p.qty)props.push(`<span class="prop" title="Штук в коробке">${{fmtQty(p.qty)}}</span>`);
        if(p.shelf&&!looksLikePrice(p.shelf))props.push(`<span class="prop" title="Срок годности">${{p.shelf}}</span>`);
        if(p.storage&&!looksLikePrice(p.storage))props.push(`<span class="prop" title="Хранение">${{p.storage}}</span>`);
        if(p.hsCode&&!looksLikePrice(p.hsCode))props.push(`<span class="prop" title="ТН ВЭД">${{p.hsCode}}</span>`);
        const propsHtml=props.length?props.join(''):'';
        const href=p.sku?`/products/${{p.sku.toLowerCase()}}`:'#';
        const altText=(p.name||'Продукт').replace(/"/g,'&quot;').replace(/</g,'&lt;');
        html+=`<a href="${{href}}" class="product-card-link"><div class="product-card" itemscope itemtype="https://schema.org/Product">
          <meta itemprop="sku" content="${{p.sku||''}}">
          <span itemprop="brand" itemscope itemtype="https://schema.org/Brand"><meta itemprop="name" content="Казанские Деликатесы"></span>
          <div class="product-name" itemprop="name">${{p.name}}</div>
          <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
            <meta itemprop="price" content="${{pr}}">
            <meta itemprop="priceCurrency" content="${{priceCur}}">
            <link itemprop="availability" href="https://schema.org/InStock">
            <div class="product-price">${{priceLabel}}</div>
          </div>
          <div class="product-sku">${{propsHtml}}</div>
          <div class="product-avail">✓ В наличии</div>
        </div></a>`;
      }}
      html+='</div>';
    }}
  }}
  return html;
}}

function renderControls(){{
  const currencies=['RUB','USD','KZT','UZS','KGS','BYN','AZN'];
  let html='<div style="display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px;align-items:center">';
  html+='<span style="font-size:.83rem;color:#595959">Валюта:</span>';
  for(const c of currencies){{
    const active=c===CUR?'background:#1b7a3d;color:#fff;border:none':'background:#fff;color:#333;border:1px solid #ddd';
    html+=`<button onclick="setCur('${{c}}')" style="${{active}};padding:5px 12px;border-radius:6px;cursor:pointer;font-size:.82rem;font-weight:600">${{c}}</button>`;
  }}
  if(CUR==='RUB'){{
    html+='<span style="margin-left:10px;font-size:.83rem;color:#595959">НДС:</span>';
    const onA=VAT?'background:#1b7a3d;color:#fff;border:none':'background:#fff;color:#333;border:1px solid #ddd';
    const offA=!VAT?'background:#1b7a3d;color:#fff;border:none':'background:#fff;color:#333;border:1px solid #ddd';
    html+=`<button onclick="setVAT(true)" style="${{onA}};padding:5px 12px;border-radius:6px;cursor:pointer;font-size:.82rem;font-weight:600">С НДС</button>`;
    html+=`<button onclick="setVAT(false)" style="${{offA}};padding:5px 12px;border-radius:6px;cursor:pointer;font-size:.82rem;font-weight:600">Без НДС</button>`;
  }}
  html+='</div>';
  return html;
}}

function setCur(c){{CUR=c;if(c!=='RUB')VAT=false;else VAT=true;render()}}
function setVAT(v){{VAT=v;render()}}

function render(){{
  const total=ALL_GROUPS.reduce((s,g)=>s+Object.values(g.groups).reduce((a,b)=>a+b.length,0),0);
  document.getElementById('catalog-inner').innerHTML=renderControls()
    +`<div style="font-size:.83rem;color:#595959;margin-bottom:8px">${{total}} товаров · актуальные цены</div>`
    +renderGroups(ALL_GROUPS);
}}

async function loadCatalog(){{
  try{{
    const d=await fetch('/products.json').then(r=>r.json());
    const groups={{}};
    for(const p of d.products||[]){{
      const sec=p.section||'Прочее',cat=p.category||sec;
      if(!groups[sec])groups[sec]={{}};if(!groups[sec][cat])groups[sec][cat]=[];
      const pr=parseFloat(p.offers?.price||p.offers?.pricePerUnit||0);
      const pnv=parseFloat(p.offers?.priceExclVAT||p.offers?.pricePerBoxExclVAT||0);
      const isBakery=!!p.offers?.pricePerUnit;
      groups[sec][cat].push({{name:p.name,sku:p.sku||'',weight:p.weight||'',price:pr,priceNoVAT:pnv,shelf:p.shelfLife||'',storage:p.storage||'',hsCode:p.hsCode||'',usd:p.offers?.exportPrices?.USD||0,kzt:p.offers?.exportPrices?.KZT||0,uzs:p.offers?.exportPrices?.UZS||0,kgs:p.offers?.exportPrices?.KGS||0,byn:p.offers?.exportPrices?.BYN||0,azn:p.offers?.exportPrices?.AZN||0,isBakery,qty:p.qtyPerBox||''}});
    }}
    const icons={{'Заморозка':'❄️','Охлаждённая продукция':'🧊','Выпечка':'🥐'}};
    ALL_GROUPS=[];
    for(const[sec,cats]of Object.entries(groups))ALL_GROUPS.push({{section:sec,icon:icons[sec]||'📦',groups:cats}});
    render();
  }}catch(e){{
    try{{
      const d=await fetch('/api/products').then(r=>r.json());
      const groups={{}};
      for(const p of d.products){{
        const sec=p.section||'Прочее',cat=p.category||sec;
        if(!groups[sec])groups[sec]={{}};if(!groups[sec][cat])groups[sec][cat]=[];
        const pr=parseFloat(p.offers?.price||p.offers?.pricePerUnit||0);
        const pnv=parseFloat(p.offers?.priceExclVAT||0);
        const isBakery=!!p.offers?.pricePerUnit;
        groups[sec][cat].push({{name:p.name,sku:p.sku||'',weight:p.weight||'',price:pr,priceNoVAT:pnv,shelf:p.shelfLife||'',storage:p.storage||'',hsCode:p.hsCode||'',usd:p.offers?.exportPrices?.USD||0,kzt:p.offers?.exportPrices?.KZT||0,uzs:p.offers?.exportPrices?.UZS||0,kgs:p.offers?.exportPrices?.KGS||0,byn:p.offers?.exportPrices?.BYN||0,azn:p.offers?.exportPrices?.AZN||0,isBakery,qty:p.qtyPerBox||''}});
      }}
      const icons={{'Заморозка':'❄️','Охлаждённая продукция':'🧊','Выпечка':'🥐'}};
      ALL_GROUPS=[];
      for(const[sec,cats]of Object.entries(groups))ALL_GROUPS.push({{section:sec,icon:icons[sec]||'📦',groups:cats}});
      render();
    }}catch(e2){{document.getElementById('loading').textContent='Ошибка загрузки каталога.';}}
  }}
}}
loadCatalog();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{{}});
document.addEventListener('click',function(e){{
  var link=e.target.closest('a');if(!link)return;
  var href=link.getAttribute('href')||'';
  if(href.indexOf('tel:')===0)typeof ym==='function'&&ym(107064141,'reachGoal','click_phone');
  if(href.indexOf('mailto:')===0)typeof ym==='function'&&ym(107064141,'reachGoal','click_email');
}});
</script>
</body>
</html>"""


def gen_en() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<title>Halal Meat Products Wholesale Manufacturer | Kazan Delicacies</title>
<meta name="description" content="Halal pepperoni, sausages, burger patties, Tatar pastries wholesale from the manufacturer in Kazan, Russia. HACCP, FSSC 22000, Halal DUM RT certified. Export available (EXW Kazan). HoReCa and retail.">
<meta name="keywords" content="halal pepperoni wholesale, halal meat manufacturer Russia, halal sausages supplier, burger patties halal, Tatar bakery wholesale, HACCP FSSC 22000">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/en/">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<meta property="og:type" content="website">
<meta property="og:title" content="Halal Meat Products Wholesale Manufacturer | Kazan Delicacies">
<meta property="og:description" content="Halal pepperoni, sausages, burger patties wholesale from manufacturer. HACCP, FSSC 22000. Export (EXW Kazan).">
<meta property="og:url" content="https://pepperoni.tatar/en/">
<meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Halal Meat Manufacturer | Kazan Delicacies">
<meta name="twitter:description" content="Halal pepperoni, sausages, patties wholesale. HACCP, FSSC 22000. Export EXW Kazan.">
<meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<script type="application/ld+json">
{{
  "@context":"https://schema.org","@type":"Organization",
  "name":"Kazan Delicacies","alternateName":"Казанские Деликатесы",
  "url":"https://pepperoni.tatar/en/",
  "logo":"https://pepperoni.tatar/images/logo.png",
  "email":"info@kazandelikates.tatar","telephone":"+79872170202",
  "address":{{"@type":"PostalAddress","streetAddress":"Musina St. 83A","addressLocality":"Kazan","postalCode":"420061","addressRegion":"Tatarstan","addressCountry":"RU"}},
  "hasCredential":{{"@type":"EducationalOccupationalCredential","name":"Halal","identifier":"614A/2024","recognizedBy":{{"@type":"Organization","name":"DUM RT","url":"https://dumrt.ru"}}}}
}}
</script>
<style>
:root{{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.08)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:var(--text);line-height:1.6;font-size:16px}}
a{{text-decoration:none;color:inherit}}
img{{max-width:100%;height:auto}}
.container{{max-width:960px;margin:0 auto;padding:0 20px}}
.nav{{background:#fff;border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100}}
.nav__inner{{display:flex;align-items:center;gap:20px;flex-wrap:wrap}}
.nav__logo{{font-weight:700;font-size:1.05rem;color:var(--green)}}
.nav__links{{display:flex;gap:16px;flex-wrap:wrap;font-size:.88rem}}
.nav__links a{{color:var(--muted);transition:color .2s}}
.nav__links a:hover{{color:var(--green)}}
.nav__lang{{margin-left:auto;font-size:.85rem}}
.hero{{background:linear-gradient(135deg,#0f4d22 0%,var(--green) 60%,#2d9e56 100%);color:#fff;padding:56px 0 48px;text-align:center}}
.hero__badge{{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);color:#fff;padding:5px 14px;border-radius:20px;font-size:.8rem;font-weight:600;letter-spacing:.5px;margin-bottom:18px}}
.hero h1{{font-size:clamp(1.5rem,3.5vw,2.4rem);font-weight:800;line-height:1.2;margin-bottom:14px;max-width:750px;margin-left:auto;margin-right:auto}}
.hero__sub{{font-size:1rem;opacity:.88;max-width:560px;margin:0 auto 28px}}
.hero__btns{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.btn{{display:inline-block;padding:12px 26px;border-radius:8px;font-weight:600;font-size:.92rem;cursor:pointer;transition:all .2s}}
.btn-primary{{background:#fff;color:var(--green)}}
.btn-primary:hover{{background:var(--green-light);transform:translateY(-1px)}}
.btn-outline{{background:transparent;border:2px solid rgba(255,255,255,.6);color:#fff}}
.btn-outline:hover{{background:rgba(255,255,255,.1);transform:translateY(-1px)}}
.badges{{background:#fff;border-bottom:1px solid var(--border);padding:12px 0}}
.badges__inner{{display:flex;justify-content:center;gap:24px;flex-wrap:wrap;font-size:.83rem;font-weight:600;color:var(--muted)}}
.badges__item{{display:flex;align-items:center;gap:6px}}
.badges__item .dot{{width:7px;height:7px;border-radius:50%;background:var(--green);flex-shrink:0}}
.usps{{padding:48px 0 0}}
.section-title{{font-size:1.4rem;font-weight:700;text-align:center;margin-bottom:6px}}
.section-sub{{text-align:center;color:var(--muted);margin-bottom:28px;font-size:.9rem}}
.usps__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-bottom:48px}}
.usp-card{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:22px;transition:box-shadow .2s,border-color .2s}}
.usp-card:hover{{box-shadow:var(--shadow);border-color:var(--green)}}
.usp-card__icon{{font-size:1.8rem;margin-bottom:10px}}
.usp-card__title{{font-weight:700;margin-bottom:5px;font-size:.92rem}}
.usp-card__text{{color:var(--muted);font-size:.85rem;line-height:1.5}}
.catalog-section{{padding:0 0 48px}}
.category-title{{font-size:1.1rem;font-weight:700;margin:28px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--green);color:var(--green)}}
.products-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-bottom:6px}}
a.product-card-link{{text-decoration:none;color:inherit;display:block}}
.product-card{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:18px;transition:box-shadow .2s,border-color .2s;cursor:pointer;height:100%}}
.product-card:hover{{box-shadow:var(--shadow);border-color:var(--green)}}
.product-name{{font-size:.92rem;font-weight:600;margin-bottom:4px}}
.product-sku{{font-size:.72rem;color:#767676;margin-bottom:7px;display:flex;flex-wrap:wrap;gap:5px;align-items:center}}
.product-sku .prop{{display:inline-block;padding:2px 6px;background:#e8e8e8;color:#333;border-radius:4px;font-size:.68rem}}
.product-price{{font-size:1.2rem;font-weight:700;color:var(--green)}}
.product-price-vat{{font-size:.7rem;color:var(--muted);font-weight:400}}
.product-avail{{font-size:.78rem;color:var(--green);margin-top:5px}}
.certs{{background:var(--green-light);padding:32px 0}}
.certs__inner{{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;align-items:center}}
.cert-item__name{{font-weight:700;font-size:.88rem;color:var(--green)}}
.cert-item__desc{{font-size:.75rem;color:var(--muted)}}
.info-block{{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin:20px 0}}
.info-block h2{{font-size:1.1rem;font-weight:700;margin-bottom:10px}}
.info-block p{{font-size:.88rem;color:var(--muted);margin-bottom:12px}}
.info-block a{{color:var(--green);font-weight:600}}
.btn-dl{{display:inline-block;padding:9px 20px;border-radius:7px;font-weight:600;font-size:.85rem;margin:3px 4px 3px 0;cursor:pointer;text-decoration:none}}
.btn-dl-solid{{background:var(--green);color:#fff;border:none}}
.btn-dl-outline{{border:2px solid var(--green);color:var(--green);background:#fff}}
.capabilities-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:16px}}
.capability-card{{background:var(--green-light);border-radius:var(--radius);padding:18px}}
.capability-card h3{{font-size:.92rem;margin-bottom:6px}}
.capability-card p{{font-size:.82rem;color:#444;line-height:1.5}}
.footer{{background:#1a1a1a;color:#ccc;padding:36px 0 20px}}
.footer__grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:24px;margin-bottom:24px}}
.footer__col-title{{color:#fff;font-weight:600;margin-bottom:10px;font-size:.88rem}}
.footer__col p,.footer__col a{{font-size:.82rem;color:#aaa;display:block;margin-bottom:5px}}
.footer__col a:hover{{color:#fff}}
.footer__bottom{{border-top:1px solid #333;padding-top:14px;text-align:center;font-size:.78rem;color:#666}}
@media(max-width:600px){{.hero{{padding:40px 0 32px}}.usps{{padding:32px 0 0}}.nav__links{{gap:10px;font-size:.82rem}}.certs__inner{{gap:16px}}}}
</style>
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<nav class="nav">
  <div class="container nav__inner">
    <span class="nav__logo">🥩 Kazan Delicacies</span>
    <div class="nav__links">
      <a href="/en/pepperoni.html">Pepperoni</a>
      <a href="/en/about.html">About</a>
      <a href="/en/faq.html">FAQ</a>
      <a href="/en/delivery.html">Delivery</a>
      <a href="/openapi.yaml">API</a>
    </div>
    <div class="nav__lang"><a href="/">🇷🇺 Русский</a></div>
  </div>
</nav>

<section class="hero">
  <div class="container">
    <div class="hero__badge">🌿 100% HALAL · HACCP · FSSC 22000</div>
    <h1>Halal Meat Products Manufacturer for HoReCa &amp; Retail</h1>
    <p class="hero__sub">Pepperoni, sausages, burger patties, traditional Tatar pastries — made in Kazan, Russia. Export to CIS and Middle East.</p>
    <div class="hero__btns">
      <a href="#catalog" class="btn btn-primary">View Catalog</a>
      <a href="mailto:info@kazandelikates.tatar" class="btn btn-outline">Contact Us</a>
    </div>
  </div>
</section>

<div class="badges">
  <div class="container badges__inner">
    <span class="badges__item"><span class="dot"></span>Halal Cert DUM RT #614A/2024</span>
    <span class="badges__item"><span class="dot"></span>HACCP + FSSC 22000</span>
    <span class="badges__item"><span class="dot"></span>ISO 22000</span>
    <span class="badges__item"><span class="dot"></span>EXW Kazan · Moscow Warehouse</span>
    <span class="badges__item"><span class="dot"></span>Private Label Available</span>
  </div>
</div>

<section class="usps">
  <div class="container">
    <h2 class="section-title">Why Choose Us</h2>
    <p class="section-sub">Production in Tatarstan, Russia. Delivery across Russia and export worldwide.</p>
    <div class="usps__grid">
      <div class="usp-card"><div class="usp-card__icon">🏭</div><div class="usp-card__title">Own Manufacturing</div><div class="usp-card__text">We produce in Kazan since 2022. Full quality control from raw materials to shipment. HACCP at every stage.</div></div>
      <div class="usp-card"><div class="usp-card__icon">🌍</div><div class="usp-card__title">Export EXW Kazan</div><div class="usp-card__text">We supply to Kazakhstan, Belarus, Uzbekistan, UAE, Saudi Arabia. Veterinary certificates included.</div></div>
      <div class="usp-card"><div class="usp-card__icon">🏷️</div><div class="usp-card__title">Private Label (OEM)</div><div class="usp-card__text">Production under your brand. Recipe development, packaging design. From 100 kg minimum order.</div></div>
      <div class="usp-card"><div class="usp-card__icon">☪️</div><div class="usp-card__title">Strict Halal Standard</div><div class="usp-card__text">Only beef, chicken, horse meat, turkey. No pork, no GMO, no sodium nitrite. DUM RT Certificate.</div></div>
    </div>
  </div>
</section>

<section class="catalog-section" id="catalog">
  <div class="container">
    <h2 class="section-title" style="margin-top:48px">Full Product Catalog</h2>
    <p class="section-sub">Live prices · switch currency</p>
    <div id="catalog-inner" style="min-height:400px">
      <div id="loading" style="text-align:center;padding:40px;color:var(--muted)">Loading catalog...</div>
    </div>
  </div>
</section>

<section class="certs">
  <div class="container">
    <h2 class="section-title" style="margin-bottom:20px">Certifications &amp; Standards</h2>
    <div class="certs__inner">
      <div class="cert-item"><div class="cert-item__name">☪️ Halal</div><div class="cert-item__desc">DUM RT #614A/2024</div></div>
      <div class="cert-item"><div class="cert-item__name">✅ HACCP</div><div class="cert-item__desc">Hazard Analysis</div></div>
      <div class="cert-item"><div class="cert-item__name">🏆 FSSC 22000</div><div class="cert-item__desc">Food Safety</div></div>
      <div class="cert-item"><div class="cert-item__name">📋 ISO 22000</div><div class="cert-item__desc">Food Management</div></div>
      <div class="cert-item"><div class="cert-item__name">🇷🇺 TR CU 021/2011</div><div class="cert-item__desc">Customs Union</div></div>
      <div class="cert-item"><div class="cert-item__name">🐄 Veterinary</div><div class="cert-item__desc">RF Certificates</div></div>
    </div>
  </div>
</section>

<div class="container">
  <div class="info-block">
    <h2>🤝 Solutions for HoReCa &amp; Retail</h2>
    <p>We don't just supply — we adapt production to your business needs.</p>
    <div class="capabilities-grid">
      <div class="capability-card"><h3>🏷️ Private Label (OEM)</h3><p>Production under your trademark. Full support: recipe development to branded packaging.</p></div>
      <div class="capability-card"><h3>🎯 Menu Customization</h3><p>Pepperoni from beef, chicken or horse meat — sticks and sliced. Need pepperoni for 350°C? We adjust spice, diameter, composition.</p></div>
      <div class="capability-card"><h3>✅ 100% Halal &amp; HACCP</h3><p>Only beef, chicken, horse, turkey. DUM RT Certificate. No pork, no GMO.</p></div>
      <div class="capability-card"><h3>🚚 Export &amp; Logistics</h3><p>Shipments EXW and DAP. Strict cold chain to your distribution center.</p></div>
    </div>
  </div>

  <div class="info-block">
    <h2>Contact Us</h2>
    <p>Wholesale supply, export, Private Label — let's discuss terms.</p>
    <a href="tel:+79872170202" class="btn-dl btn-dl-solid">📞 +7 987 217-02-02</a>
    <a href="mailto:info@kazandelikates.tatar" class="btn-dl btn-dl-outline">📧 info@kazandelikates.tatar</a>
    <a href="https://wa.me/79872170202" class="btn-dl btn-dl-outline" style="border-color:#25d366;color:#25d366">💬 WhatsApp</a>
  </div>
</div>

<footer class="footer">
  <div class="container">
    <div class="footer__grid">
      <div class="footer__col">
        <div class="footer__col-title">Kazan Delicacies</div>
        <p>Halal meat products manufacturer in Tatarstan, Russia.</p>
        <p>© 2022–{YEAR} Kazan Delicacies LLC</p>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Production</div>
        <p>Kazan, Musina St. 83A</p>
        <p>Tatarstan, 420061, Russia</p>
        <a href="tel:+79872170202">+7 987 217-02-02</a>
        <a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Warehouse &amp; Shipment</div>
        <p>Moscow (Lyubertsy) — our warehouse</p>
        <p>EXW Kazan</p>
        <p>Mon–Fri 9:00–18:00 MSK</p>
        <a href="https://wa.me/79872170202">WhatsApp: +7 987 217-02-02</a>
      </div>
      <div class="footer__col">
        <div class="footer__col-title">Navigation</div>
        <a href="/en/pepperoni.html">Pepperoni</a>
        <a href="/en/faq.html">FAQ</a>
        <a href="/en/delivery.html">Delivery</a>
        <a href="/">🇷🇺 Russian version</a>
        <a href="/openapi.yaml">API for Partners</a>
      </div>
    </div>
    <div class="footer__bottom">
      <a href="https://kazandelikates.tatar">kazandelikates.tatar</a> &nbsp;·&nbsp;
      <a href="https://pepperoni.tatar/en/">pepperoni.tatar</a> &nbsp;·&nbsp;
      Halal · HACCP · FSSC 22000 · EXW Kazan
    </div>
  </div>
</footer>

{YM}
<script>
const CUR_SYM={{RUB:'₽',USD:'$',KZT:'₸',UZS:'сум',KGS:'сом',BYN:'Br',AZN:'₼'}};
let CUR='USD',VAT=false,ALL_GROUPS=[];

function getPrice(p){{
  if(CUR==='RUB')return VAT?p.price:p.priceNoVAT;
  const m={{USD:p.usd,KZT:p.kzt,UZS:p.uzs,KGS:p.kgs,BYN:p.byn,AZN:p.azn}};
  let v=m[CUR]||0;
  if(p.isBakery&&p.qty){{const q=parseFloat(p.qty)||1;if(q>0)v=v/q;}}
  return v;
}}
function fmtPrice(v){{if(!v)return'—';return v.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}
const looksLikePrice=v=>/^\d{{2,}}[.,]\d{{2}}$/.test(String(v||'').trim());

function renderGroups(allGroups){{
  let html='';
  const sym=CUR_SYM[CUR]||CUR;
  for(const{{section,icon,groups}}of allGroups){{
    html+=`<h2 style="font-size:1.3rem;margin:36px 0 4px;color:#333">${{icon}} ${{section}}</h2>`;
    for(const[cat,products]of Object.entries(groups)){{
      html+=`<h3 class="category-title">${{cat}}</h3><div class="products-grid">`;
      for(const p of products){{
        const pr=getPrice(p);
        const href=p.sku?`/en/products/${{p.sku.toLowerCase()}}`:'#';
        html+=`<a href="${{href}}" class="product-card-link"><div class="product-card" itemscope itemtype="https://schema.org/Product">
          <meta itemprop="sku" content="${{p.sku||''}}">
          <div class="product-name" itemprop="name">${{p.name}}</div>
          <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
            <meta itemprop="price" content="${{pr}}">
            <meta itemprop="priceCurrency" content="${{CUR}}">
            <link itemprop="availability" href="https://schema.org/InStock">
            <div class="product-price">${{fmtPrice(pr)}} ${{sym}}</div>
          </div>
          <div class="product-avail">✓ In stock</div>
        </div></a>`;
      }}
      html+='</div>';
    }}
  }}
  return html;
}}

function renderControls(){{
  const currencies=['USD','RUB','KZT','UZS','KGS','BYN','AZN'];
  let html='<div style="display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px;align-items:center">';
  html+='<span style="font-size:.83rem;color:#595959">Currency:</span>';
  for(const c of currencies){{
    const active=c===CUR?'background:#1b7a3d;color:#fff;border:none':'background:#fff;color:#333;border:1px solid #ddd';
    html+=`<button onclick="setCur('${{c}}')" style="${{active}};padding:5px 12px;border-radius:6px;cursor:pointer;font-size:.82rem;font-weight:600">${{c}}</button>`;
  }}
  html+='</div>';
  return html;
}}

function setCur(c){{CUR=c;VAT=c==='RUB';render()}}

function render(){{
  const total=ALL_GROUPS.reduce((s,g)=>s+Object.values(g.groups).reduce((a,b)=>a+b.length,0),0);
  document.getElementById('catalog-inner').innerHTML=renderControls()
    +`<div style="font-size:.83rem;color:#595959;margin-bottom:8px">${{total}} products · live prices</div>`
    +renderGroups(ALL_GROUPS);
}}

async function loadCatalog(){{
  try{{
    const d=await fetch('/products.json').then(r=>r.json());
    const groups={{}};
    for(const p of d.products||[]){{
      const sec=p.section||'Other',cat=p.category||sec;
      if(!groups[sec])groups[sec]={{}};if(!groups[sec][cat])groups[sec][cat]=[];
      const pr=parseFloat(p.offers?.price||p.offers?.pricePerUnit||0);
      const pnv=parseFloat(p.offers?.priceExclVAT||p.offers?.pricePerBoxExclVAT||0);
      const isBakery=!!p.offers?.pricePerUnit;
      groups[sec][cat].push({{name:p.name,sku:p.sku||'',weight:p.weight||'',price:pr,priceNoVAT:pnv,shelf:p.shelfLife||'',storage:p.storage||'',hsCode:p.hsCode||'',usd:p.offers?.exportPrices?.USD||0,kzt:p.offers?.exportPrices?.KZT||0,uzs:p.offers?.exportPrices?.UZS||0,kgs:p.offers?.exportPrices?.KGS||0,byn:p.offers?.exportPrices?.BYN||0,azn:p.offers?.exportPrices?.AZN||0,isBakery,qty:p.qtyPerBox||''}});
    }}
    const icons={{'Заморозка':'❄️','Охлаждённая продукция':'🧊','Выпечка':'🥐'}};
    ALL_GROUPS=[];
    for(const[sec,cats]of Object.entries(groups))ALL_GROUPS.push({{section:sec,icon:icons[sec]||'📦',groups:cats}});
    render();
  }}catch(e){{document.getElementById('loading').textContent='Failed to load catalog.';}}
}}
loadCatalog();
</script>
</body>
</html>"""


def main():
    ru_path = PUBLIC / "index.html"
    ru_path.write_text(gen_ru(), encoding="utf-8")
    print(f"✅ {ru_path}")

    en_dir = PUBLIC / "en"
    en_dir.mkdir(exist_ok=True)
    en_path = en_dir / "index.html"
    en_path.write_text(gen_en(), encoding="utf-8")
    print(f"✅ {en_path}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
