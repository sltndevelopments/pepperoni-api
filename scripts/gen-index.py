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

TODAY = datetime.now().strftime("%Y-%m-%d")
YEAR = datetime.now().year

GTM = (
    '<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({"gtm.start":'
    'new Date().getTime(),event:"gtm.js"});var f=d.getElementsByTagName(s)[0],'
    'j=d.createElement(s),dl=l!="dataLayer"?"&l="+l:"";j.async=true;j.src='
    '"https://www.googletagmanager.com/gtm.js?id="+i+dl;f.parentNode.insertBefore(j,f);'
    '})(window,document,"script","dataLayer","GTM-W2Q5S8HF");</script>'
)

YM = (
    '<script>(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};'
    'm[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return}'
    'k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);'
    '})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
    'ym(107064141,"init",{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:"dataLayer"});</script>'
    '<noscript><div><img src="https://mc.yandex.ru/watch/107064141" style="position:absolute;left:-9999px" alt=""/></div></noscript>'
)

CSS = """
<style>
:root{--green:#1b7a3d;--green-dark:#145c2e;--green-light:#e8f5e9;--text:#1a1a1a;--muted:#666;--border:#e5e5e5;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.08)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:var(--text);line-height:1.6}
a{text-decoration:none;color:inherit}
img{max-width:100%;height:auto}
.container{max-width:1100px;margin:0 auto;padding:0 20px}

/* Nav */
.nav{background:#fff;border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100}
.nav__inner{display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.nav__logo{font-weight:700;font-size:1.1rem;color:var(--green)}
.nav__links{display:flex;gap:20px;flex-wrap:wrap;font-size:.9rem}
.nav__links a{color:var(--muted);transition:color .2s}
.nav__links a:hover{color:var(--green)}
.nav__lang{margin-left:auto;font-size:.85rem;color:var(--muted)}

/* Hero */
.hero{background:linear-gradient(135deg,#0f4d22 0%,var(--green) 60%,#2d9e56 100%);color:#fff;padding:72px 0 60px;text-align:center}
.hero__badge{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);color:#fff;padding:5px 14px;border-radius:20px;font-size:.8rem;font-weight:600;letter-spacing:.5px;margin-bottom:20px}
.hero h1{font-size:clamp(1.7rem,4vw,2.8rem);font-weight:800;line-height:1.2;margin-bottom:16px;max-width:800px;margin-left:auto;margin-right:auto}
.hero__sub{font-size:1.05rem;opacity:.88;max-width:580px;margin:0 auto 32px}
.hero__btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.btn{display:inline-block;padding:13px 28px;border-radius:8px;font-weight:600;font-size:.95rem;cursor:pointer;transition:all .2s}
.btn-primary{background:#fff;color:var(--green)}
.btn-primary:hover{background:var(--green-light);transform:translateY(-1px)}
.btn-outline{background:transparent;border:2px solid rgba(255,255,255,.6);color:#fff}
.btn-outline:hover{background:rgba(255,255,255,.1);transform:translateY(-1px)}

/* Badges strip */
.badges{background:#fff;border-bottom:1px solid var(--border);padding:14px 0}
.badges__inner{display:flex;justify-content:center;gap:28px;flex-wrap:wrap;font-size:.85rem;font-weight:600;color:var(--muted)}
.badges__item{display:flex;align-items:center;gap:6px}
.badges__item span.dot{width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0}

/* USPs */
.usps{padding:60px 0}
.section-title{font-size:1.5rem;font-weight:700;text-align:center;margin-bottom:8px}
.section-sub{text-align:center;color:var(--muted);margin-bottom:36px;font-size:.95rem}
.usps__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:20px}
.usp-card{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:24px;transition:box-shadow .2s,border-color .2s}
.usp-card:hover{box-shadow:var(--shadow);border-color:var(--green)}
.usp-card__icon{font-size:2rem;margin-bottom:12px}
.usp-card__title{font-weight:700;margin-bottom:6px;font-size:.95rem}
.usp-card__text{color:var(--muted);font-size:.88rem;line-height:1.5}

/* Categories */
.categories{padding:0 0 60px}
.cat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:20px}
.cat-card{background:#fff;border:1px solid var(--border);border-radius:var(--radius);padding:28px 24px;text-align:center;transition:all .2s;display:block}
.cat-card:hover{box-shadow:var(--shadow);border-color:var(--green);transform:translateY(-2px)}
.cat-card__icon{font-size:2.4rem;margin-bottom:14px}
.cat-card__name{font-weight:700;font-size:1rem;color:var(--text);margin-bottom:6px}
.cat-card__desc{font-size:.83rem;color:var(--muted)}

/* Certs */
.certs{background:var(--green-light);padding:40px 0}
.certs__inner{display:flex;justify-content:center;gap:40px;flex-wrap:wrap;align-items:center}
.cert-item{text-align:center}
.cert-item__name{font-weight:700;font-size:.9rem;color:var(--green)}
.cert-item__desc{font-size:.78rem;color:var(--muted)}

/* Partners */
.partners{padding:48px 0;background:#fff;border-top:1px solid var(--border)}
.partners__logos{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;align-items:center;margin-top:24px;font-size:.9rem;color:var(--muted)}

/* Footer */
.footer{background:#1a1a1a;color:#ccc;padding:40px 0 24px}
.footer__grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:28px;margin-bottom:28px}
.footer__col-title{color:#fff;font-weight:600;margin-bottom:12px;font-size:.9rem}
.footer__col p,.footer__col a{font-size:.84rem;color:#aaa;display:block;margin-bottom:6px}
.footer__col a:hover{color:#fff}
.footer__bottom{border-top:1px solid #333;padding-top:16px;text-align:center;font-size:.8rem;color:#666}

@media(max-width:600px){
  .hero{padding:48px 0 40px}
  .usps{padding:40px 0}
  .categories{padding:0 0 40px}
  .nav__links{gap:12px}
  .certs__inner{gap:20px}
}
</style>
"""

SCHEMA_RU = f"""<script type="application/ld+json">
{{
  "@context":"https://schema.org",
  "@type":"Organization",
  "name":"Казанские Деликатесы",
  "alternateName":"Kazan Delicacies",
  "url":"https://pepperoni.tatar",
  "logo":"https://pepperoni.tatar/images/logo.png",
  "telephone":"+78005509076",
  "email":"info@kazandelikates.tatar",
  "address":{{"@type":"PostalAddress","streetAddress":"ул. Мусина 83А","addressLocality":"Казань","addressRegion":"Татарстан","postalCode":"420061","addressCountry":"RU"}},
  "hasCredential":{{"@type":"EducationalOccupationalCredential","name":"Halal","identifier":"614A/2024","recognizedBy":{{"@type":"Organization","name":"ДУМ РТ","url":"https://dumrt.ru"}}}},
  "sameAs":["https://pepperoni.tatar","https://kazandelikates.tatar"]
}}
</script>"""

SCHEMA_EN = f"""<script type="application/ld+json">
{{
  "@context":"https://schema.org",
  "@type":"Organization",
  "name":"Kazan Delicacies",
  "alternateName":"Казанские Деликатесы",
  "url":"https://pepperoni.tatar/en/",
  "logo":"https://pepperoni.tatar/images/logo.png",
  "telephone":"+78005509076",
  "email":"info@kazandelikates.tatar",
  "address":{{"@type":"PostalAddress","streetAddress":"Musina St. 83A","addressLocality":"Kazan","addressRegion":"Tatarstan","postalCode":"420061","addressCountry":"RU"}},
  "hasCredential":{{"@type":"EducationalOccupationalCredential","name":"Halal","identifier":"614A/2024","recognizedBy":{{"@type":"Organization","name":"DUM RT","url":"https://dumrt.ru"}}}}
}}
</script>"""


def gen_ru() -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Производитель мясных деликатесов Халяль оптом | Казанские Деликатесы</title>
<meta name="description" content="Халяль пепперони, сосиски, котлеты, выпечка оптом от производителя в Казани. ХАССП, FSSC 22000. Сертификат ДУМ РТ. Экспорт СНГ. EXW Казань. Для HoReCa и ретейла.">
<meta name="keywords" content="халяль пепперони оптом, сосиски халяль, котлеты для бургеров, татарская выпечка, мясные изделия казань, производитель халяль">
<meta name="robots" content="index, follow">
<meta name="yandex-verification" content="d0a735c825c78ddf">
<link rel="canonical" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<meta property="og:type" content="website">
<meta property="og:title" content="Производитель мясных деликатесов Халяль оптом | Казанские Деликатесы">
<meta property="og:description" content="Халяль пепперони, сосиски, котлеты, выпечка оптом от производителя. ХАССП, FSSC 22000, ДУМ РТ. Экспорт. EXW Казань.">
<meta property="og:url" content="https://pepperoni.tatar/">
<meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<meta property="og:locale" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Производитель халяль мясных изделий оптом | Казанские Деликатесы">
<meta name="twitter:description" content="Пепперони, сосиски, котлеты, выпечка. 100% Халяль. EXW Казань.">
<meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
{SCHEMA_RU}
{CSS}
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<nav class="nav">
  <div class="container nav__inner">
    <span class="nav__logo">🥩 Казанские Деликатесы</span>
    <div class="nav__links">
      <a href="/pepperoni">Пепперони</a>
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
    <p class="section-sub">77 позиций. Производство в Татарстане. Поставки по России и на экспорт.</p>
    <div class="usps__grid">
      <div class="usp-card">
        <div class="usp-card__icon">🏭</div>
        <div class="usp-card__title">Собственное производство</div>
        <div class="usp-card__text">Производим в Казани с 2022 года. Полный контроль качества от сырья до отгрузки. ХАССП на всех этапах.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">🌍</div>
        <div class="usp-card__title">Экспорт EXW Казань</div>
        <div class="usp-card__text">Поставляем в Казахстан, Беларусь, Узбекистан, ОАЭ. Ветеринарные сертификаты, таможенное оформление.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">🏷️</div>
        <div class="usp-card__title">Private Label (СТМ)</div>
        <div class="usp-card__text">Производим под вашим брендом. Разработка рецептуры, дизайн упаковки. От 100 кг партия.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">☪️</div>
        <div class="usp-card__title">Строгий стандарт Халяль</div>
        <div class="usp-card__text">Только говядина, курица, конина, индейка. Без свинины, без ГМО, без нитрита натрия. Сертификат ДУМ РТ.</div>
      </div>
    </div>
  </div>
</section>

<section class="categories" id="catalog">
  <div class="container">
    <h2 class="section-title">Каталог продукции</h2>
    <p class="section-sub">Нажмите на категорию, чтобы увидеть все позиции с ценами.</p>
    <div class="cat-grid">
      <a href="/pepperoni" class="cat-card">
        <div class="cat-card__icon">🍕</div>
        <div class="cat-card__name">Пепперони</div>
        <div class="cat-card__desc">Говяжий, куриный, из конины. Батоны и нарезка. Ø40–75 мм.</div>
      </a>
      <a href="/products/kd-001.html" class="cat-card">
        <div class="cat-card__icon">🌭</div>
        <div class="cat-card__name">Сосиски для фастфуда</div>
        <div class="cat-card__desc">Хот-дог, корн-дог, гриль. 7 вкусов. Идеально для уличной еды.</div>
      </a>
      <a href="/products/kd-014.html" class="cat-card">
        <div class="cat-card__icon">🥩</div>
        <div class="cat-card__name">Деликатесы и колбасы</div>
        <div class="cat-card__desc">Казылык, ветчины, сервелат, копчёные изделия. Без нитрита натрия.</div>
      </a>
      <a href="/products/kd-020.html" class="cat-card">
        <div class="cat-card__icon">🥐</div>
        <div class="cat-card__name">Татарская выпечка</div>
        <div class="cat-card__desc">Эчпочмак, перемяч, губадия, самса, чак-чак. Замороженные п/ф.</div>
      </a>
      <a href="/products/kd-010.html" class="cat-card">
        <div class="cat-card__icon">🍔</div>
        <div class="cat-card__name">Котлеты для бургеров</div>
        <div class="cat-card__desc">Говяжьи и куриные. 90–180г. IQF заморозка. Для ресторанов и HoReCa.</div>
      </a>
      <a href="/products/kd-021.html" class="cat-card">
        <div class="cat-card__icon">🫙</div>
        <div class="cat-card__name">Мясные заготовки</div>
        <div class="cat-card__desc">Фарш говяжий и куриный, кубик, филе. Для производства и кулинарий.</div>
      </a>
    </div>
  </div>
</section>

<section class="certs">
  <div class="container">
    <h2 class="section-title" style="margin-bottom:24px">Сертификаты и стандарты</h2>
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

<section class="partners">
  <div class="container">
    <h2 class="section-title">Наши партнёры</h2>
    <div class="partners__logos">
      <span>АЗС Татнефть</span>
      <span>EuroSpar</span>
      <span>Бэхетле</span>
      <span>Сети пиццерий</span>
      <span>HoReCa по России</span>
    </div>
  </div>
</section>

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
        <a href="tel:+78005509076">8-800-550-90-76 (бесплатно)</a>
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
</body>
</html>"""


def gen_en() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GTM}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Halal Meat Products Wholesale Manufacturer | Kazan Delicacies</title>
<meta name="description" content="Halal pepperoni, sausages, burger patties, Tatar pastries wholesale from the manufacturer in Kazan, Russia. HACCP, FSSC 22000, Halal DUM RT certified. Export available (EXW Kazan).">
<meta name="keywords" content="halal pepperoni wholesale, halal meat manufacturer Russia, halal sausages supplier, burger patties halal, Tatar bakery wholesale">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/en/">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<meta property="og:type" content="website">
<meta property="og:title" content="Halal Meat Products Wholesale Manufacturer | Kazan Delicacies">
<meta property="og:description" content="Halal pepperoni, sausages, burger patties, Tatar pastries wholesale from manufacturer. HACCP, FSSC 22000. Export (EXW Kazan).">
<meta property="og:url" content="https://pepperoni.tatar/en/">
<meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="ru_RU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Halal Meat Manufacturer | Kazan Delicacies">
<meta name="twitter:description" content="Halal pepperoni, sausages, patties wholesale. HACCP, FSSC 22000. Export EXW Kazan.">
<meta name="twitter:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
{SCHEMA_EN}
{CSS}
</head>
<body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<nav class="nav">
  <div class="container nav__inner">
    <span class="nav__logo">🥩 Kazan Delicacies</span>
    <div class="nav__links">
      <a href="/en/products/kd-001.html">Pepperoni</a>
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
    <p class="section-sub">77 product lines. Production in Tatarstan, Russia. Delivery across Russia and export worldwide.</p>
    <div class="usps__grid">
      <div class="usp-card">
        <div class="usp-card__icon">🏭</div>
        <div class="usp-card__title">Own Manufacturing</div>
        <div class="usp-card__text">We produce in Kazan since 2022. Full quality control from raw materials to shipment. HACCP at every stage.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">🌍</div>
        <div class="usp-card__title">Export EXW Kazan</div>
        <div class="usp-card__text">We supply to Kazakhstan, Belarus, Uzbekistan, UAE, Saudi Arabia. Veterinary certificates included.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">🏷️</div>
        <div class="usp-card__title">Private Label (OEM)</div>
        <div class="usp-card__text">Production under your brand. Recipe development, packaging design. From 100 kg minimum order.</div>
      </div>
      <div class="usp-card">
        <div class="usp-card__icon">☪️</div>
        <div class="usp-card__title">Strict Halal Standard</div>
        <div class="usp-card__text">Only beef, chicken, horse meat, turkey. No pork, no GMO, no sodium nitrite. DUM RT Certificate.</div>
      </div>
    </div>
  </div>
</section>

<section class="categories" id="catalog">
  <div class="container">
    <h2 class="section-title">Product Catalog</h2>
    <p class="section-sub">Click a category to see all products with prices.</p>
    <div class="cat-grid">
      <a href="/en/pepperoni.html" class="cat-card">
        <div class="cat-card__icon">🍕</div>
        <div class="cat-card__name">Halal Pepperoni</div>
        <div class="cat-card__desc">Beef, chicken, horse meat. Sticks and sliced. Ø40–75 mm.</div>
      </a>
      <a href="/en/products/kd-001.html" class="cat-card">
        <div class="cat-card__icon">🌭</div>
        <div class="cat-card__name">Fast Food Sausages</div>
        <div class="cat-card__desc">Hot dog, corn dog, grill sausages. 7 flavors. Perfect for street food.</div>
      </a>
      <a href="/en/products/kd-014.html" class="cat-card">
        <div class="cat-card__icon">🥩</div>
        <div class="cat-card__name">Deli &amp; Sausages</div>
        <div class="cat-card__desc">Kazylyk, ham, servelat, smoked products. No sodium nitrite.</div>
      </a>
      <a href="/en/products/kd-020.html" class="cat-card">
        <div class="cat-card__icon">🥐</div>
        <div class="cat-card__name">Tatar Pastries</div>
        <div class="cat-card__desc">Echpochmak, peremyach, gubadiya, samsa, chak-chak. Frozen.</div>
      </a>
      <a href="/en/products/kd-010.html" class="cat-card">
        <div class="cat-card__icon">🍔</div>
        <div class="cat-card__name">Burger Patties</div>
        <div class="cat-card__desc">Beef &amp; chicken. 90–180g. IQF frozen. For restaurants and HoReCa.</div>
      </a>
      <a href="/en/products/kd-021.html" class="cat-card">
        <div class="cat-card__icon">🫙</div>
        <div class="cat-card__name">Raw Meat &amp; Mince</div>
        <div class="cat-card__desc">Beef &amp; chicken mince, diced meat, fillet. For production &amp; catering.</div>
      </a>
    </div>
  </div>
</section>

<section class="certs">
  <div class="container">
    <h2 class="section-title" style="margin-bottom:24px">Certifications &amp; Standards</h2>
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
        <a href="tel:+78005509076">+7-800-550-90-76 (free)</a>
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
</body>
</html>"""


def main():
    # RU index
    ru_path = PUBLIC / "index.html"
    ru_path.write_text(gen_ru(), encoding="utf-8")
    print(f"✅ {ru_path}")

    # EN index
    en_dir = PUBLIC / "en"
    en_dir.mkdir(exist_ok=True)
    en_path = en_dir / "index.html"
    en_path.write_text(gen_en(), encoding="utf-8")
    print(f"✅ {en_path}")

    print("\n✅ Done. Run: git add public/index.html public/en/index.html && git commit -m 'feat: regenerate RU/EN index pages' && git push")


if __name__ == "__main__":
    main()
