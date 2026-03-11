#!/usr/bin/env python3
"""
Generate commercial landing pages for halal pepperoni.
5 pages: optom, dlya-pizzerii, dlya-horeca, private-label, v-narezke
"""

from pathlib import Path

PUBLIC = Path(__file__).parent.parent / "public"

GTM = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_NOSCRIPT = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

CSS = """
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.8}
    .container{max-width:800px;margin:0 auto;padding:40px 24px}
    nav{font-size:.85rem;color:#888;margin-bottom:32px}
    nav a{color:#0066cc;text-decoration:none}
    h1{font-size:2rem;font-weight:700;margin-bottom:8px}
    h2{font-size:1.3rem;font-weight:700;margin:36px 0 12px;color:#1b7a3d}
    h3{font-size:1.05rem;font-weight:600;margin:20px 0 8px}
    p{margin-bottom:14px}
    .badge{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;margin:6px 4px 20px 0;letter-spacing:.5px}
    .badge-outline{background:transparent;border:1.5px solid #1b7a3d;color:#1b7a3d}
    .hero-subtitle{color:#666;font-size:1.05rem;margin-bottom:4px}
    .card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:24px;margin:16px 0}
    .grid-2{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin:16px 0}
    .feat-card{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px}
    .feat-card .icon{font-size:1.6rem;margin-bottom:6px}
    .feat-card .title{font-weight:600;font-size:.9rem}
    .feat-card .desc{font-size:.82rem;color:#666;margin-top:4px}
    .prices-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:16px 0}
    .price-card{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:16px;text-align:center}
    .price-card .name{font-size:.85rem;font-weight:600;margin-bottom:4px}
    .price-card .weight{font-size:.75rem;color:#888}
    .price-card .price{font-size:1.4rem;font-weight:700;color:#1b7a3d;margin-top:8px}
    table{width:100%;border-collapse:collapse;margin:12px 0}
    th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem}
    th{background:#f5f5f5;font-weight:600}
    ul{margin:8px 0 14px 24px}
    li{margin-bottom:4px}
    .spec-value{font-weight:600;color:#1b7a3d}
    .cta{background:#1b7a3d;color:#fff;display:inline-block;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 8px 8px 0;font-size:.95rem}
    .cta:hover{background:#15652f}
    .cta-outline{background:transparent;border:2px solid #1b7a3d;color:#1b7a3d}
    .cta-outline:hover{background:#1b7a3d;color:#fff}
    footer{text-align:center;color:#aaa;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}
    footer a{color:#888;text-decoration:none}
    @media(max-width:600px){.grid-2,.prices-grid{grid-template-columns:1fr}}
"""

NAV = """    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
      <a href="/" style="color:#0066cc;text-decoration:none;font-weight:600">Каталог</a>
      <a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
      <a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
      <a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
      <a href="/faq" style="color:#0066cc;text-decoration:none">FAQ</a>
    </div>"""

FOOTER = """    <footer>
      <p><a href="/">← Каталог</a> &middot; <a href="/pepperoni">Пепперони</a> &middot; <a href="/about">О компании</a> &middot; <a href="/delivery">Доставка</a> &middot; <a href="/faq">FAQ</a></p>
      <p>&copy; <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> &middot; <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
    </footer>"""

CONTACT_BLOCK = """    <h2>Обсудить поставки</h2>
    <p>Ответим в течение нескольких часов. Подберём условия под ваш объём и формат работы.</p>
    <a href="tel:+79872170202" class="cta">📞 +7 987 217-02-02</a>
    <a href="mailto:info@kazandelikates.tatar" class="cta cta-outline">📧 info@kazandelikates.tatar</a>"""

RELATED_BLOCK = """    <h2>Смотрите также</h2>
    <div class="grid-2">
      <a href="/pepperoni-optom" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Пепперони оптом</strong><br><span style="color:#666;font-size:.82rem">Условия оптовых поставок</span></a>
      <a href="/pepperoni-dlya-pizzerii" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Для пиццерий</strong><br><span style="color:#666;font-size:.82rem">Форматы и условия для кухонь</span></a>
      <a href="/pepperoni-dlya-horeca" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Для HoReCa</strong><br><span style="color:#666;font-size:.82rem">Рестораны, отели, кейтеринг</span></a>
      <a href="/pepperoni-private-label" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Private Label / СТМ</strong><br><span style="color:#666;font-size:.82rem">Производство под вашим брендом</span></a>
      <a href="/pepperoni-v-narezke" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Пепперони в нарезке</strong><br><span style="color:#666;font-size:.82rem">Готовые слайсы для пиццы</span></a>
      <a href="/pepperoni" style="display:block;background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:14px;text-decoration:none;color:#1a1a1a;font-size:.9rem"><strong>Всё о пепперони</strong><br><span style="color:#666;font-size:.82rem">Ассортимент, состав, сертификаты</span></a>
    </div>"""


def page(slug, title, desc, keywords, h1, hero_sub, badges, body_html, breadcrumb_name):
    url = f"https://pepperoni.tatar/{slug}"
    badges_html = "".join(
        f'    <span class="badge{"" if i == 0 else " badge-outline"}">{b}</span>\n'
        for i, b in enumerate(badges)
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
{GTM}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="/favicon.ico" type="image/x-icon">
  <meta http-equiv="content-language" content="ru">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <meta name="keywords" content="{keywords}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{url}">
  <link rel="alternate" hreflang="ru" href="{url}">

  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://pepperoni.tatar/images/pepperoni-halal.png">
  <meta property="og:locale" content="ru_RU">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{"@type": "ListItem", "position": 1, "name": "Каталог", "item": "https://pepperoni.tatar/"}},
      {{"@type": "ListItem", "position": 2, "name": "Пепперони", "item": "https://pepperoni.tatar/pepperoni"}},
      {{"@type": "ListItem", "position": 3, "name": "{breadcrumb_name}", "item": "{url}"}}
    ]
  }}
  </script>

  <style>{CSS}</style>
</head>
<body>
{GTM_NOSCRIPT}
  <div class="container">
{NAV}
    <nav aria-label="Breadcrumb">
      <a href="/">Каталог</a> &rsaquo; <a href="/pepperoni">Пепперони</a> &rsaquo; <span>{breadcrumb_name}</span>
    </nav>

    <h1>{h1}</h1>
    <p class="hero-subtitle">{hero_sub}</p>
{badges_html}
{body_html}

{RELATED_BLOCK}

{CONTACT_BLOCK}

{FOOTER}
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────
# PAGE 1: Пепперони оптом
# ─────────────────────────────────────────────────────────
OPTOM_BODY = """    <p>«Казанские Деликатесы» — производитель халяль пепперони в Татарстане. Работаем <strong>напрямую с оптовыми покупателями</strong>: дистрибьюторами, торговыми сетями, агрегаторами HoReCa. Никаких посредников — цена производителя, стабильные отгрузки, полный пакет документов.</p>

    <h2>Ассортимент для оптовых поставок</h2>
    <div class="prices-grid">
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Нарезка 0,5 кг</div><div class="price">274 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Батон 1 кг</div><div class="price">457 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп из конины</div><div class="weight">Нарезка 0,5 кг</div><div class="price">315 ₽</div></div>
      <div class="price-card"><div class="name">Сырокопчёный</div><div class="weight">Нарезка 0,5 кг</div><div class="price">380 ₽</div></div>
      <div class="price-card"><div class="name">Сырокопчёный</div><div class="weight">Батон 1 кг</div><div class="price">608 ₽</div></div>
    </div>
    <p style="font-size:.85rem;color:#888">Цены указаны без НДС. Объёмные скидки — по запросу. Экспортные цены в USD, KZT, UZS, KGS, BYN, AZN — на странице <a href="/pepperoni">пепперони</a>.</p>

    <h2>Условия оптовой работы</h2>
    <div class="card">
      <table>
        <tbody>
          <tr><td>Минимальный заказ</td><td class="spec-value">от 1 коробки (2,5 кг)</td></tr>
          <tr><td>Упаковок в коробке</td><td class="spec-value">6 шт × 0,5 кг или 2 шт × 1 кг</td></tr>
          <tr><td>Отгрузка</td><td class="spec-value">EXW Казань (ул. Аграрная, 2)</td></tr>
          <tr><td>Логистика</td><td class="spec-value">Самовывоз или организуем доставку</td></tr>
          <tr><td>Оплата</td><td class="spec-value">Безналичный расчёт, НДС 20%</td></tr>
          <tr><td>Документы</td><td class="spec-value">Декларация ЕАЭС, ветсвидетельства, ФГИС ВЕТИС, Halal</td></tr>
          <tr><td>Экспорт</td><td class="spec-value">Казахстан, Узбекистан, Беларусь, Армения, Азербайджан, Кыргызстан</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Почему выбирают нас как оптового поставщика</h2>
    <div class="grid-2">
      <div class="feat-card"><div class="icon">🏭</div><div class="title">Прямой производитель</div><div class="desc">Никаких перекупщиков. Цены производителя. Управляем качеством от сырья до отгрузки.</div></div>
      <div class="feat-card"><div class="icon">📦</div><div class="title">Стабильные объёмы</div><div class="desc">Производство в Татарстане обеспечивает регулярные поставки без перебоев.</div></div>
      <div class="feat-card"><div class="icon">☪️</div><div class="title">Halal № 614A/2024</div><div class="desc">Официальная сертификация ДУМ РТ. Актуальный сертификат на каждую партию.</div></div>
      <div class="feat-card"><div class="icon">🏷️</div><div class="title">Private Label</div><div class="desc">Производство под маркой дистрибьютора или торговой сети. Гибкая рецептура.</div></div>
      <div class="feat-card"><div class="icon">📋</div><div class="title">Полный пакет документов</div><div class="desc">Декларация ЕАЭС, ветеринарные свидетельства, ХАССП, ФГИС ВЕТИС — всё готово.</div></div>
      <div class="feat-card"><div class="icon">🌍</div><div class="title">Экспорт в СНГ</div><div class="desc">Работаем с партнёрами в Казахстане, Узбекистане, Беларуси, Армении, Азербайджане.</div></div>
    </div>

    <h2>Форматы для оптовиков</h2>
    <div class="card">
      <ul>
        <li><strong>Нарезка 0,5 кг</strong> — вакуумная упаковка, 6 шт в коробке, удобно для HoReCa и розницы</li>
        <li><strong>Батоны 1 кг</strong> — для партнёров со слайсерами, 2–4 шт в коробке</li>
        <li><strong>Блок-форматы до 5 кг</strong> — под заказ, для крупных производств и dark kitchen</li>
        <li><strong>Private Label</strong> — ваша упаковка, ваш штрих-код, ваш бренд</li>
      </ul>
    </div>"""

# ─────────────────────────────────────────────────────────
# PAGE 2: Пепперони для пиццерий
# ─────────────────────────────────────────────────────────
PIZZA_BODY = """    <p>Пепперони — самый популярный топпинг для пиццы в России. Но для профессиональной кухни важны детали: <strong>не скручивается при запекании, держит форму, даёт равномерный цвет</strong>. Именно под эти задачи разработан халяль пепперони от «Казанских Деликатесов».</p>

    <h2>Почему пиццерии выбирают наш пепперони</h2>
    <div class="grid-2">
      <div class="feat-card"><div class="icon">🍕</div><div class="title">Не скручивается</div><div class="desc">Термостабильный продукт. Ломтики не скручиваются при 350°C — пицца выглядит профессионально.</div></div>
      <div class="feat-card"><div class="icon">💧</div><div class="title">Сохраняет сочность</div><div class="desc">Правильное соотношение жира и белка — пепперони не пересыхает в печи.</div></div>
      <div class="feat-card"><div class="icon">🔵</div><div class="title">Диаметр 50–55 мм</div><div class="desc">Оптимальный размер для пиццы 30–40 см. Слайсы покрывают поверхность равномерно.</div></div>
      <div class="feat-card"><div class="icon">⚖️</div><div class="title">10 слайсов = 26–30 г</div><div class="desc">Предсказуемый выход продукта. Удобно нормировать вложение на пиццу.</div></div>
      <div class="feat-card"><div class="icon">☪️</div><div class="title">100% Halal</div><div class="desc">Сертификат № 614A/2024. Подходит для пиццерий, работающих в халяль-сегменте.</div></div>
      <div class="feat-card"><div class="icon">🧊</div><div class="title">Длительное хранение</div><div class="desc">360 суток при −18°C. Можно держать запас и не зависеть от частых поставок.</div></div>
    </div>

    <h2>Форматы для пиццерий</h2>
    <div class="card">
      <table>
        <thead><tr><th>Формат</th><th>Для кого</th><th>Цена</th></tr></thead>
        <tbody>
          <tr><td>Нарезка 0,5 кг (вакуум)</td><td>Небольшие пиццерии, работающие готовой нарезкой</td><td class="spec-value">274 ₽</td></tr>
          <tr><td>Батон 1 кг</td><td>Пиццерии со слайсером — нарезка под нужную толщину</td><td class="spec-value">457 ₽</td></tr>
          <tr><td>Блок до 5 кг</td><td>Крупные производства, dark kitchen, сетевые проекты</td><td class="spec-value">по запросу</td></tr>
          <tr><td>Private Label</td><td>Сети пиццерий с собственным брендом</td><td class="spec-value">по запросу</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Виды пепперони</h2>
    <div class="card">
      <table>
        <thead><tr><th>Вид</th><th>Состав</th><th>Особенность</th></tr></thead>
        <tbody>
          <tr><td>Варёно-копчёный классика</td><td>Говядина + курица</td><td>Нежный вкус, умеренная острота</td></tr>
          <tr><td>Варёно-копчёный из конины</td><td>Конина</td><td>Насыщенный вкус, халяльная экзотика</td></tr>
          <tr><td>Сырокопчёный</td><td>Говядина + курица</td><td>Выраженный аромат копчения</td></tr>
          <tr><td>Миксы (Private Label)</td><td>По рецептуре заказчика</td><td>Любой состав и острота под запрос</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Как заказать пробную партию</h2>
    <div class="card">
      <p>Для новых партнёров доступна <strong>тестовая поставка</strong> — минимальный заказ от 1 коробки (2,5 кг). Пробуйте на своей кухне перед оптовым заказом.</p>
      <ol style="margin-left:20px;margin-top:8px">
        <li>Свяжитесь с нами по телефону или email</li>
        <li>Укажите, какой вид пепперони интересует</li>
        <li>Мы отправим тестовую партию или организуем самовывоз из Казани</li>
      </ol>
    </div>

    <h2>Для сетевых пиццерий</h2>
    <p>Работаем с сетями по всей России и СНГ. Предлагаем:</p>
    <ul>
      <li>Фиксированные цены при регулярных заказах</li>
      <li>Private Label — ваш бренд, наше производство</li>
      <li>Кастомизацию: острота, диаметр, толщина нарезки, состав</li>
      <li>Регулярные рейсы в Москву, СПб, другие города</li>
      <li>Интеграцию с iiko, 1С через API</li>
    </ul>"""

# ─────────────────────────────────────────────────────────
# PAGE 3: Пепперони для HoReCa
# ─────────────────────────────────────────────────────────
HORECA_BODY = """    <p>HoReCa — отели, рестораны, кейтеринг — предъявляют особые требования к поставщикам: стабильность, документация, гибкость. Мы работаем с HoReCa-операторами по всей России и поставляем <strong>халяль пепперони</strong> в форматах, удобных для профессиональных кухонь.</p>

    <h2>HoReCa-форматы</h2>
    <div class="grid-2">
      <div class="feat-card"><div class="icon">🍕</div><div class="title">Пиццерии</div><div class="desc">Нарезка 0,5 кг или батоны под слайсер. Термостабильный — не скручивается в печи.</div></div>
      <div class="feat-card"><div class="icon">🏨</div><div class="title">Отели и кейтеринг</div><div class="desc">Готовая нарезка для шведских столов, банкетов, room service. Халяль-статус для гостей из мусульманских стран.</div></div>
      <div class="feat-card"><div class="icon">🌯</div><div class="title">Фастфуд и стритфуд</div><div class="desc">Пепперони для хот-догов, сэндвичей, врапов, пицца-слайс. Быстрая выдача, стабильный вкус.</div></div>
      <div class="feat-card"><div class="icon">🍳</div><div class="title">Dark kitchen</div><div class="desc">Крупные форматы до 5 кг для высокой проходимости. Точный выход продукта, удобная логистика.</div></div>
      <div class="feat-card"><div class="icon">🎪</div><div class="title">Мероприятия и кейтеринг</div><div class="desc">Готовая нарезка — удобно для выездных кухонь и банкетного сервиса.</div></div>
      <div class="feat-card"><div class="icon">🛒</div><div class="title">Корпоративное питание</div><div class="desc">Халяль-продукция для столовых компаний с мусульманскими сотрудниками.</div></div>
    </div>

    <h2>Почему выбирают нас в HoReCa</h2>
    <div class="card">
      <ul style="list-style:none;margin-left:0">
        <li>✅ <strong>Стабильные поставки</strong> — регулярные рейсы по России, никаких перебоев</li>
        <li>✅ <strong>Полная документация</strong> — декларация ЕАЭС, ветсвидетельства, ФГИС ВЕТИС, сертификат Halal</li>
        <li>✅ <strong>ХАССП</strong> — система контроля качества на производстве</li>
        <li>✅ <strong>Разные форматы</strong> — нарезка 0,5 кг, батоны 1 кг, блоки до 5 кг</li>
        <li>✅ <strong>Кастомизация</strong> — состав, острота, диаметр под ваши рецептуры</li>
        <li>✅ <strong>Private Label</strong> — под вашим брендом для сетевых проектов</li>
        <li>✅ <strong>Халяль для любой аудитории</strong> — одновременно подходит и для мусульман, и для всех остальных</li>
      </ul>
    </div>

    <h2>Ассортимент для HoReCa</h2>
    <div class="prices-grid">
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Нарезка 0,5 кг</div><div class="price">274 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Батон 1 кг</div><div class="price">457 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп из конины</div><div class="weight">Нарезка 0,5 кг</div><div class="price">315 ₽</div></div>
      <div class="price-card"><div class="name">Сырокопчёный</div><div class="weight">Нарезка 0,5 кг</div><div class="price">380 ₽</div></div>
    </div>

    <h2>Логистика для HoReCa</h2>
    <div class="card">
      <table>
        <tbody>
          <tr><td>Отгрузка</td><td class="spec-value">EXW Казань, или доставка до вашего склада</td></tr>
          <tr><td>Москва</td><td class="spec-value">Еженедельные рейсы</td></tr>
          <tr><td>Регионы РФ</td><td class="spec-value">Через транспортные компании (ТК)</td></tr>
          <tr><td>Хранение</td><td class="spec-value">Заморозка: 360 суток при −18°C</td></tr>
          <tr><td>После разморозки</td><td class="spec-value">5 суток при +4°C (невскрытый)</td></tr>
        </tbody>
      </table>
    </div>"""

# ─────────────────────────────────────────────────────────
# PAGE 4: Private Label / СТМ
# ─────────────────────────────────────────────────────────
PL_BODY = """    <p>Производим халяль пепперони <strong>под торговой маркой заказчика</strong>. СТМ (собственная торговая марка) — это ваш бренд, ваша упаковка, ваш штрих-код. Наше производство, контроль качества и сертификация.</p>

    <h2>Кому подходит Private Label</h2>
    <div class="grid-2">
      <div class="feat-card"><div class="icon">🏪</div><div class="title">Торговые сети</div><div class="desc">Запустите СТМ-пепперони под брендом своей сети. Отличительный продукт в категории.</div></div>
      <div class="feat-card"><div class="icon">🍕</div><div class="title">Сети пиццерий</div><div class="desc">Фирменный пепперони с уникальной рецептурой — ваше конкурентное преимущество.</div></div>
      <div class="feat-card"><div class="icon">🌍</div><div class="title">Дистрибьюторы</div><div class="desc">Региональные и экспортные дистрибьюторы, которым нужен продукт под собственным именем.</div></div>
      <div class="feat-card"><div class="icon">🏨</div><div class="title">HoReCa-операторы</div><div class="desc">Отели, корпоративное питание, кейтеринговые компании с брендированной продукцией.</div></div>
    </div>

    <h2>Что можно кастомизировать</h2>
    <div class="card">
      <table>
        <thead><tr><th>Параметр</th><th>Варианты</th></tr></thead>
        <tbody>
          <tr><td>Состав мяса</td><td class="spec-value">Говядина, курица, конина, индейка, баранина или миксы</td></tr>
          <tr><td>Острота</td><td class="spec-value">Mild / Medium / Spicy — по вашей рецептуре</td></tr>
          <tr><td>Диаметр</td><td class="spec-value">Стандартный 50–55 мм или под заказ</td></tr>
          <tr><td>Толщина нарезки</td><td class="spec-value">Тонкая, стандартная или заказная</td></tr>
          <tr><td>Нитрит натрия</td><td class="spec-value">Возможен вариант без нитрита (по запросу)</td></tr>
          <tr><td>Формат упаковки</td><td class="spec-value">Вакуум: от 0,5 кг до 5 кг</td></tr>
          <tr><td>Маркировка</td><td class="spec-value">Ваш дизайн, состав, штрих-код, ТУ</td></tr>
          <tr><td>Сертификация</td><td class="spec-value">Halal, ХАССП, декларация ЕАЭС</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Как работает процесс</h2>
    <div class="card">
      <ol style="margin-left:20px">
        <li style="margin-bottom:10px"><strong>Переговоры</strong> — обсуждаем рецептуру, объёмы, упаковку, цены</li>
        <li style="margin-bottom:10px"><strong>Разработка рецептуры</strong> — при необходимости корректируем состав и вкус под ваши требования</li>
        <li style="margin-bottom:10px"><strong>Пробная партия</strong> — производим образцы для дегустации и согласования</li>
        <li style="margin-bottom:10px"><strong>Регистрация ТУ</strong> — оформляем техническую документацию под вашу марку</li>
        <li style="margin-bottom:10px"><strong>Серийное производство</strong> — запускаем регулярные поставки</li>
      </ol>
    </div>

    <h2>Сертификация для вашего СТМ</h2>
    <div class="card">
      <p>Весь необходимый пакет для запуска СТМ:</p>
      <ul>
        <li>Сертификат Halal (ДУМ РТ) на вашу марку</li>
        <li>Декларация о соответствии ЕАЭС</li>
        <li>Ветеринарные свидетельства (ФГИС ВЕТИС)</li>
        <li>Разработка и регистрация ТУ</li>
        <li>Штрих-код GS1</li>
      </ul>
    </div>

    <h2>Минимальные объёмы</h2>
    <div class="card">
      <p>Минимальный заказ на Private Label обсуждается индивидуально — зависит от рецептуры и формата упаковки. Свяжитесь с нами для расчёта.</p>
    </div>"""

# ─────────────────────────────────────────────────────────
# PAGE 5: Пепперони в нарезке
# ─────────────────────────────────────────────────────────
NAREZKA_BODY = """    <p>Нарезка пепперони — самый удобный формат для пиццерий, HoReCa и розницы. Готовые слайсы правильной круглой формы, упакованные под вакуумом. Открыл — использовал. Никакого слайсера, никаких потерь.</p>

    <h2>Характеристики нарезки</h2>
    <div class="card">
      <table>
        <tbody>
          <tr><td>Форма слайсов</td><td class="spec-value">Правильная круглая (диаметр колбасы 50–55 мм)</td></tr>
          <tr><td>Масса 10 слайсов</td><td class="spec-value">26–30 г</td></tr>
          <tr><td>Упаковка</td><td class="spec-value">Вакуумная, 0,5 кг</td></tr>
          <tr><td>Упаковок в коробке</td><td class="spec-value">6 шт (коробка 2,5 кг)</td></tr>
          <tr><td>Размер короба</td><td class="spec-value">260 × 235 × 180 мм</td></tr>
          <tr><td>Хранение</td><td class="spec-value">360 суток при −18°C</td></tr>
          <tr><td>После вскрытия</td><td class="spec-value">72 часа при +4°C</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Виды нарезки в ассортименте</h2>
    <div class="prices-grid">
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Говядина + курица, 0,5 кг</div><div class="price">274 ₽</div></div>
      <div class="price-card"><div class="name">Вар-коп из конины</div><div class="weight">Конина, 0,5 кг</div><div class="price">315 ₽</div></div>
      <div class="price-card"><div class="name">Сырокопчёный</div><div class="weight">Говядина + курица, 0,5 кг</div><div class="price">380 ₽</div></div>
    </div>

    <h2>Нарезка vs батон: как выбрать</h2>
    <div class="card">
      <table>
        <thead><tr><th>Параметр</th><th>Нарезка 0,5 кг</th><th>Батон 1 кг</th></tr></thead>
        <tbody>
          <tr><td>Нужен слайсер</td><td>Нет</td><td>Да</td></tr>
          <tr><td>Толщина нарезки</td><td>Стандартная</td><td>Любая (настраиваемая)</td></tr>
          <tr><td>Для кого</td><td>Небольшие пиццерии, розница</td><td>Крупные кухни, dark kitchen</td></tr>
          <tr><td>Потери при нарезке</td><td>Нет</td><td>Зависит от оборудования</td></tr>
          <tr><td>Удобство открытия</td><td>Вакуум, сразу к использованию</td><td>Нужна нарезка перед сменой</td></tr>
        </tbody>
      </table>
    </div>

    <h2>Для каких блюд</h2>
    <div class="grid-2">
      <div class="feat-card"><div class="icon">🍕</div><div class="title">Пицца</div><div class="desc">Диаметр 50–55 мм идеален для стандартной пиццы. Не скручивается при 350°C.</div></div>
      <div class="feat-card"><div class="icon">🥪</div><div class="title">Сэндвичи и врапы</div><div class="desc">Пикантный мясной акцент. Подходит для горячих и холодных сэндвичей.</div></div>
      <div class="feat-card"><div class="icon">🧀</div><div class="title">Нарезка к столу</div><div class="desc">Готов к подаче прямо из упаковки. Удобно для шведских столов и банкетов.</div></div>
      <div class="feat-card"><div class="icon">🍳</div><div class="title">Горячие блюда</div><div class="desc">Паста, омлеты, запечённые блюда — добавляет аромат копчения и пряностей.</div></div>
    </div>

    <h2>Также доступны батоны</h2>
    <p>Если вы используете собственный слайсер — выгоднее брать <strong>целые батоны 1 кг</strong>. Нарезка под нужную толщину, цена ниже за грамм.</p>
    <div class="prices-grid">
      <div class="price-card"><div class="name">Вар-коп классика</div><div class="weight">Батон 1 кг</div><div class="price">457 ₽</div></div>
      <div class="price-card"><div class="name">Сырокопчёный</div><div class="weight">Батон 1 кг</div><div class="price">608 ₽</div></div>
    </div>"""


PAGES = [
    {
        "slug": "pepperoni-optom",
        "title": "Халяль пепперони оптом — поставки от производителя | Казанские Деликатесы",
        "desc": "Пепперони халяль оптом от производителя в Казани. Говядина, курица, конина, миксы. Нарезка и батоны. Private Label. EXW Казань. Экспорт в СНГ. ХАССП. Halal № 614A/2024.",
        "keywords": "пепперони оптом, купить пепперони оптом, пепперони от производителя, халяль пепперони оптом, пепперони производитель казань, пепперони для дистрибьюторов",
        "h1": "Халяль пепперони оптом — прямые поставки от производителя",
        "hero_sub": "EXW Казань. Декларация ЕАЭС. Экспорт в Казахстан, Узбекистан, Беларусь и СНГ.",
        "badges": ["HALAL № 614A/2024", "ХАССП", "EXW Казань", "СТМ / Private Label"],
        "body": OPTOM_BODY,
        "breadcrumb": "Пепперони оптом",
    },
    {
        "slug": "pepperoni-dlya-pizzerii",
        "title": "Халяль пепперони для пиццерий — не скручивается, термостабильный",
        "desc": "Профессиональный халяль пепперони для пиццерий. Не скручивается при 350°C. Говядина, курица, конина. Нарезка и батоны. Private Label для сетей. ХАССП. Halal № 614A/2024.",
        "keywords": "пепперони для пиццерий, пепперони для пиццы, термостабильный пепперони, пепперони не скручивается, халяль пепперони для пиццерий, пепперони поставки пиццерии",
        "h1": "Халяль пепперони для пиццерий — термостабильный, не скручивается",
        "hero_sub": "Не скручивается при 350°C. Говядина, курица, конина. Диаметр 50–55 мм.",
        "badges": ["HALAL № 614A/2024", "Термостабильный", "ХАССП", "Private Label"],
        "body": PIZZA_BODY,
        "breadcrumb": "Для пиццерий",
    },
    {
        "slug": "pepperoni-dlya-horeca",
        "title": "Халяль пепперони для HoReCa — рестораны, отели, кейтеринг, dark kitchen",
        "desc": "Пепперони халяль для HoReCa: рестораны, отели, кейтеринг, dark kitchen, фастфуд. Говядина, курица, конина. Форматы 0,5–5 кг. ХАССП. Halal № 614A/2024. Стабильные поставки.",
        "keywords": "пепперони для horeca, пепперони для ресторанов, пепперони для отелей, халяль пепперони horeca, пепперони dark kitchen, пепперони фастфуд",
        "h1": "Халяль пепперони для HoReCa — рестораны, отели, кейтеринг",
        "hero_sub": "Стабильные поставки. Полная документация. Форматы от 0,5 до 5 кг.",
        "badges": ["HALAL № 614A/2024", "ХАССП", "EXW Казань", "Private Label"],
        "body": HORECA_BODY,
        "breadcrumb": "Для HoReCa",
    },
    {
        "slug": "pepperoni-private-label",
        "title": "Пепперони Private Label / СТМ — производство под вашим брендом | Казанские Деликатесы",
        "desc": "Производство халяль пепперони под вашей торговой маркой (Private Label / СТМ). Кастомизация рецептуры, упаковки, состава. Говядина, курица, конина. Halal. ХАССП. Казань.",
        "keywords": "пепперони private label, пепперони СТМ, пепперони под своим брендом, производство пепперони на заказ, халяль пепперони private label, СТМ колбаса казань",
        "h1": "Пепперони Private Label — производство под вашей торговой маркой",
        "hero_sub": "Ваш бренд, ваша рецептура, наше производство. Говядина, курица, конина, миксы.",
        "badges": ["HALAL № 614A/2024", "ХАССП", "Кастомизация рецептуры", "СТМ / Private Label"],
        "body": PL_BODY,
        "breadcrumb": "Private Label",
    },
    {
        "slug": "pepperoni-v-narezke",
        "title": "Пепперони в нарезке халяль — готовые слайсы для пиццы и HoReCa",
        "desc": "Халяль пепперони в нарезке: готовые слайсы диаметром 50–55 мм. Говядина, курица, конина. Вакуумная упаковка 0,5 кг. 360 суток при −18°C. ХАССП. Halal № 614A/2024.",
        "keywords": "пепперони в нарезке, пепперони слайсы, нарезка пепперони для пиццы, халяль пепперони нарезка, пепперони в вакуумной упаковке, купить пепперони нарезку",
        "h1": "Пепперони в нарезке — готовые слайсы для пиццы и HoReCa",
        "hero_sub": "Диаметр 50–55 мм. Вакуум 0,5 кг. Говядина, курица, конина. 360 суток хранения.",
        "badges": ["HALAL № 614A/2024", "Вакуум 0,5 кг", "ХАССП", "Диаметр 50–55 мм"],
        "body": NAREZKA_BODY,
        "breadcrumb": "Пепперони в нарезке",
    },
]


def update_sitemap(slugs):
    import re
    sitemap_path = PUBLIC / "sitemap.xml"
    content = sitemap_path.read_text(encoding="utf-8")

    # Remove existing commercial page entries
    for slug in slugs:
        content = re.sub(
            rf'\s*<url>\s*<loc>https://pepperoni\.tatar/{slug}</loc>.*?</url>',
            '', content, flags=re.DOTALL
        )

    today = "2026-03-11"
    new_urls = ""
    for slug in slugs:
        new_urls += f"""  <url>
    <loc>https://pepperoni.tatar/{slug}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
"""
    content = content.replace("</urlset>", new_urls + "</urlset>")
    sitemap_path.write_text(content, encoding="utf-8")
    print(f"✅ sitemap.xml обновлён ({len(slugs)} коммерческих страниц)")


def main():
    print(f"📄 Генерация коммерческих страниц ({len(PAGES)} шт.)...")
    slugs = []
    for p in PAGES:
        html = page(
            p["slug"], p["title"], p["desc"], p["keywords"],
            p["h1"], p["hero_sub"], p["badges"], p["body"], p["breadcrumb"]
        )
        out = PUBLIC / f"{p['slug']}.html"
        out.write_text(html, encoding="utf-8")
        print(f"  ✅ {out.name}")
        slugs.append(p["slug"])

    update_sitemap(slugs)
    print(f"\n🎉 Готово! Страницы в: public/")


if __name__ == "__main__":
    main()
