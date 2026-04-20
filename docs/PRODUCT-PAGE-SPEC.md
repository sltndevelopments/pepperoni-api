# Спецификация страницы товара (SKU)

Production-ready шаблон, размножается на 77 позиций при sync.

**Пример URL:** `https://www.pepperoni.tatar/product/kd-015-pepperoni-var-kop-klassika`  
**EN:** `https://www.pepperoni.tatar/en/product/kd-015-pepperoni-var-kop-klassika`

---

## 1. URL

| Путь | Язык |
|------|------|
| `/product/{slug}` | ru (default) |
| `/en/product/{slug}` | en |

**Slug:** стабильный, не меняется при sync. Формат: `{sku-lower}-{transliterated-name}`.  
Карта slug хранится в `data/slug-map.json` — при первом запуске генерируется, затем только добавляются новые SKU.

---

## 2. Head

- `title`: `{Product Name} | Kazan Delicacies` / `{Название} | Казанские Деликатесы`
- `canonical`: `https://www.pepperoni.tatar/{locale}/product/{slug}`
- `meta description`: 150–160 символов
- `og:type`: `product`
- `og:url`, `og:title`, `og:image`
- `hreflang`: ru, en

---

## 3. Body

### H1
Один H1: полное название товара.

### Блок 1 — Ключевые характеристики (above the fold)
SKU, Section, Category, Weight, Shelf life, Storage, HS Code, Halal cert, Delivery (EXW Kazan).

### Блок 2 — Краткое описание
150–300 слов. Применение, преимущества, формат поставки, экспорт.  
Генерируется из шаблона + `short_description_ru` (если есть в Sheets), иначе из name/category.

### Блок 3 — Техническая спецификация
Таблица: Net weight, Units per box, Shelf life, Storage, HS Code, Halal cert.

### Блок 4 — B2B / Export
Incoterms (EXW), MOQ, Pallet, Currencies (RUB, USD, KZT…).

### Блок 5 — Schema.org Product
JSON-LD с name, sku, brand, category, countryOfOrigin, offers (price, availability).

### Блок 6 — BreadcrumbList
Главная → Section → Product. Ссылки на `/` и `/en/`.

### Блок 7 — Related products
3–5 SKU из той же категории. Ссылки на их страницы.

---

## 4. Минимальный вес

800–1500 слов совокупного текста. Уникальный контент, не только таблицы.

---

## 5. Генерация

- **Метод:** static HTML при `npm run sync`.
- **Файлы:** `public/product/{slug}.html`, `public/en/product/{slug}.html`.
- **Sitemap:** автоматически добавляются в sitemap.xml.
