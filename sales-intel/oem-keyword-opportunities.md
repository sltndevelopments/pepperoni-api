# OEM / B2B Keyword Opportunities — Pepperoni.tatar

> Source: `data/seo_data.db` (Google Search Console, `gsc_queries`, 1764 rows, snapshot date **2026-03-09**).
> Yandex (`yandex_queries`, 500 rows) carries no impression/position data in this snapshot (all zeros), so all scoring below is GSC-based.
> Generated for the OEM/contract-manufacturing contour. Focus: queries ranking **position 11–60 with real impressions** = the biggest, cheapest wins.

## Method

`scripts/analyze_queries.py` filters on `date >= date('now','-30 days')`. The snapshot is from 2026-03-09 (>30 days before today), so the script returns **0 rows** against this DB without a date override — that is expected, not a bug. The ranking below was produced by querying the DB directly:

```sql
SELECT query, SUM(impressions) impr, ROUND(AVG(position),1) pos
FROM gsc_queries GROUP BY query
HAVING pos BETWEEN 11 AND 60 AND impr >= 10
ORDER BY impr DESC;
```

**Opportunity score** = impressions × position-gap weight (queries at pos 20–60 with high impressions are under-served demand we already nearly rank for). Trust/AIO questions ("это халяль?") are scored separately because the win is an answer block / FAQ, not a commercial landing.

## Top commercial clusters (ranked)

### 1. Burger patties wholesale — **NEW LANDING** `/oem/burger-patties`
Combined ~230 impressions, avg position ~28 — strong, scattered across near-duplicate queries with no dedicated page.

| Query | Impr | Avg pos |
|---|---|---|
| котлеты для гамбургеров оптом | 62 | 30.0 |
| котлеты для бургеров оптом | 51 | 31.8 |
| котлеты для бургеров купить оптом | 49 | 21.6 |
| котлеты для бургеров опт | 43 | 29.6 |
| купить котлеты для бургеров оптом | 24 | 26.4 |

- **Target page:** `/oem/burger-patties` (+ `/en/oem/burger-patties`)
- **H1:** Котлеты для бургеров и гамбургеров оптом — контрактное производство под СТМ
- **Title:** Котлеты для бургеров оптом — паттисы говяжьи под СТМ, халяль | Pepperoni.tatar
- **Meta:** Производство котлет для бургеров и гамбургеров (говяжьи паттисы) под вашим брендом. Калибр и вес паттиса под сеть. Халяль, ХАССП, ISO 22000:2018. Оптом от 500 кг/мес. Поставщик из Казани.

### 2. Hot-dog sausages wholesale — **NEW LANDING** `/oem/hotdog-sausages`
Combined ~290 impressions, avg position ~40 — the single biggest commercial query ("сосиски для хот догов оптом", 121 impr) has no targeted page, plus a strong halal sub-cluster and a supplier-intent query.

| Query | Impr | Avg pos |
|---|---|---|
| сосиски для хот догов оптом | 121 | 36.2 |
| халяльные сосиски для хот догов | 51 | 49.5 |
| халяль сосиски для хот догов | 48 | 52.0 |
| сосиски для хот догов купить оптом в москве | 37 | 38.4 |
| сосиски для хот догов купить оптом | 16 | 40.0 |
| поставщик сосисок для хот догов | 14 | 41.6 |

- **Target page:** `/oem/hotdog-sausages` (+ `/en/oem/hotdog-sausages`)
- **H1:** Сосиски для хот-догов оптом — халяльный поставщик под СТМ
- **Title:** Сосиски для хот-догов оптом — халяльный поставщик под СТМ | Pepperoni.tatar
- **Meta:** Сосиски для хот-догов оптом под вашим брендом: говяжьи, куриные, с сыром, с бараниной. Термостабильные, для АЗС и стритфуда. Халяль, ХАССП, ISO 22000:2018. Поставщик из Казани, отгрузка по РФ.

### 3. Pepperoni HoReCa / pizzeria — strengthen existing `/oem/toppings`
| Query | Impr | Avg pos |
|---|---|---|
| пепперони хорека | 34 | 51.7 |
| хорека пепперони | 18 | 60.0 |

- **Decision:** No new page — `/oem/toppings` and the existing `/pepperoni-dlya-pizzerii` / `/pepperoni-dlya-horeca` already own this intent. Added a HoReCa/pizzeria FAQ + copy reinforcement to `/oem/toppings`.

### 4. Halal trust / "это халяль?" — **AIO answer blocks** (FAQPage on relevant pages)
High-impression informational demand. Win = a cited answer, not a landing.

| Query | Impr | Avg pos | Where answered |
|---|---|---|---|
| пепперони халяль (+ варианты) | 198+67+65 | 48–59 | toppings FAQ + existing pepperoni pages |
| ветчина это халал / халяль курицы / индейки | 54+20+19+12 | 28–34 | toppings + meat FAQ |
| халяльные сосиски для хот догов | 51+48 | 49–52 | new hotdog-sausages FAQ |
| фарш говяжий халяль | 13 | 43.2 | raw-meat |
| мраморная говядина халяль | 12 | 16.5 | meat FAQ |

### 5. Tatar/national informational ("казылык это", "эчпочмак это", "что такое казылык")
High impressions (275 + 41 for казылык; эчпочмак ~26) but **purely informational / B2C discovery**, already partly served by existing product/category pages (`/kazylyk`, `/bakery`). **Decision:** not B2B/OEM intent — out of scope for new OEM landings; left to existing pages.

## Predictive coverage decisions (Task 3)

Checked the DB for the speculative future clusters named in the brief:

| Candidate topic | DB demand found | Decision |
|---|---|---|
| Замороженные тестовые заготовки оптом (frozen dough blanks) | ~0 direct impressions | **No new page.** Added a focused section + FAQ to existing `/oem/bakery`. |
| Пепперони нарезка для пиццы оптом (pizza slices) | covered by "пепперони хорека/пиццерий" cluster | **No new page** — already the core of `/oem/toppings` + `/pepperoni-v-narezke`. Reinforced FAQ only. |
| Чизкейк / pastry private label | ~0 direct impressions | **No new page.** Added private-label cheesecake FAQ/section to `/oem/pastry`. |
| Халяльные пельмени / манты оптом | negligible (пельмени тульские, 2 impr) | **No new page.** Already covered by `/oem/raw-meat`; reinforced FAQ. |

**Rationale:** the brief explicitly says not to create thin duplicate pages. None of the predictive topics show distinct, strong query demand in the data that a dedicated narrow landing would capture better than a focused section on the parent direction page. So predictive coverage was delivered as on-page sections + FAQPage trust answers, concentrating link equity on the two data-validated landings (burger patties, hot-dog sausages).

## Summary of actions

- **2 new narrow landings** (RU+EN): `/oem/burger-patties`, `/oem/hotdog-sausages` — data-validated, highest under-served impressions.
- **Predictive on-page coverage** added to `/oem/toppings`, `/oem/bakery`, `/oem/pastry`, `/oem/raw-meat`, `/oem/meat` (FAQPage trust blocks + focused sections).
- **AIO:** "это халяль?" trust answers wired into FAQPage JSON-LD on the relevant pages.
- **Plumbing:** new URLs added to `public/sitemap.xml`, internal links from `/oem` hub and parent direction pages.
- **llms.txt:** NOT hand-edited — both `public/llms.txt` and `public/en/llms.txt` are auto-generated catalog files ("Last synced … Total SKUs: 77"); editing them by hand would be overwritten by the next sync. Noted for the catalog-generation pipeline instead.
