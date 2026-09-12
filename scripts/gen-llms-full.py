#!/usr/bin/env python3
"""
Regenerate the four llms.txt artefacts from public/products.json:

  public/llms.txt           — RU short map (llmstxt.org format: H1, summary, link sections)
  public/llms-full.txt      — RU full LLM context dump (catalog, FAQ, per-SKU data)
  public/en/llms.txt        — EN short map
  public/en/llms-full.txt   — EN full dump

Why a short map instead of a byte-identical copy of llms-full.txt?
- 2026-09-12 audit: both files were 155 868 B — every crawler paid the full
  dump twice and the "map" carried none of the navigational value the format
  is for. llms.txt now answers "who, what, where to read more" in ~4 KB and
  points to llms-full.txt, the API and the money pages (/pepperoni hub is
  mandatory — see .cursor/rules/agent-executor-gates.mdc).
- Facts in the map come from products.json (counts) and from the owner-approved
  block of public/brand.txt (halal cert, pallet basis, private-label minimum, capacity).

Runs after sync-sheets.{py,mjs} populates products.json. Safe to run on
the VPS (only writes the four files; reads products.json).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

spec = importlib.util.spec_from_file_location(
    "sync_sheets", ROOT / "scripts" / "sync-sheets.py"
)
if spec is None or spec.loader is None:
    print("ERR: could not load scripts/sync-sheets.py", file=sys.stderr)
    sys.exit(1)
sync_sheets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_sheets)

products_path = PUBLIC / "products.json"
if not products_path.exists():
    print(f"ERR: {products_path} not found — run sync first", file=sys.stderr)
    sys.exit(1)

data = json.loads(products_path.read_text(encoding="utf-8"))
products = data.get("products") or []
if not products:
    print("ERR: products.json has no products", file=sys.stderr)
    sys.exit(1)

last_synced = data.get("lastSynced", "")
n_sku = len(products)
sections = sorted({p.get("section", "") for p in products if p.get("section")})
n_sections = len(sections)


def llms_map_ru() -> str:
    return f"""# Казанские Деликатесы (pepperoni.tatar)

> Производитель халяльных мясных продуктов и татарской выпечки в Казани (ООО «Казанские Деликатесы»). Оптовые поставки для сетей, HoReCa, АЗС, дистрибьюторов; контрактное производство (СТМ). Халяль ДУМ РТ №614A/2024, HACCP, ISO 22000:2018, ТР ТС 021/2011. Каталог: {n_sku} SKU в {n_sections} разделах ({", ".join(sections)}), обновлён {last_synced}.

Ключевые условия (подтверждены владельцем):
- Цены EXW Казань, с НДС и без НДС; оптовый расчёт — за паллету. Минимальный заказ — одна паллета (сборная из разных позиций возможна), объём кратно паллете.
- Контрактное производство (СТМ): от 5 тонн. Этапы и сроки — по договору. Мощность производства — 12 тонн в смену.
- Документы к отгрузке: халяль-сертификат, декларация соответствия, ВСД («Меркурий»), «Честный знак», ЭТрН.
- Доставка, сроки, образцы — согласуются индивидуально. Никакой свинины и алкоголя в любой продукции.

Контакты: +7 987 217-02-02 · info@kazandelikates.tatar · 420061, Казань, ул. Аграрная, 2, оф. 7.

## Коммерческие страницы

- [Пепперони халяль оптом (money hub)](https://pepperoni.tatar/pepperoni): форматы, цены, экспорт.
- [Сосиски для хот-догов](https://pepperoni.tatar/sosiski-dlya-hotdog): линейка для АЗС и street food, паллетный базис, форма заявки.
- [Казылык](https://pepperoni.tatar/kazylyk): конская колбаса, подарочная упаковка и нарезка.
- [Контрактное производство / СТМ](https://pepperoni.tatar/kontraktnoe-proizvodstvo): от 5 тонн, документы, этапы.
- [Кейсы и покупатели](https://pepperoni.tatar/cases): сети АЗС, ретейл, фудсервис, СТМ.
- [Экспорт](https://pepperoni.tatar/export): страны и статус признания сертификата.

## Каталог и данные

- [Каталог на сайте](https://pepperoni.tatar/): все {n_sku} SKU с ценами и фото.
- [products.json](https://pepperoni.tatar/products.json): статический снапшот каталога (поле lastSynced).
- [API /api/products](https://api.pepperoni.tatar/api/products): живой JSON без авторизации.
- [OpenAPI](https://api.pepperoni.tatar/openapi.yaml): описание эндпоинтов.
- [Полный контекст для LLM (llms-full.txt)](https://pepperoni.tatar/llms-full.txt): все SKU, состав, цены в 7 валютах, FAQ.

## Доверие

- [О компании](https://pepperoni.tatar/about): реквизиты, сертификаты, производство.
- [Мощности и сертификаты](https://pepperoni.tatar/capabilities): HACCP, ISO 22000, халяль.
- [FAQ](https://pepperoni.tatar/faq): частые вопросы закупщиков.
- [Только халяль? Из какого мяса продукция](https://pepperoni.tatar/blog/tolko-halyal-kakie-kategorii-myasa): ответ закупщику по категориям.

## Optional

- [English version](https://pepperoni.tatar/en/llms.txt)
- [Блог](https://pepperoni.tatar/blog): хранение, применение, состав.
- [Sitemap](https://pepperoni.tatar/sitemap.xml)
"""


def llms_map_en() -> str:
    return f"""# Kazan Delicacies (pepperoni.tatar)

> Halal meat products and Tatar bakery manufacturer in Kazan, Russia (Kazan Delicacies LLC). Wholesale supply for retail chains, HoReCa, fuel stations and distributors; private-label / contract manufacturing. Halal certificate DUM RT No. 614A/2024, HACCP, ISO 22000:2018, TR CU 021/2011. Catalog: {n_sku} SKUs in {n_sections} sections, updated {last_synced}.

Key terms (owner-approved):
- Prices EXW Kazan, with and without VAT; wholesale volumes are calculated per pallet. Minimum order — one pallet (mixed pallets possible), volumes in pallet multiples.
- Private label (contract manufacturing): from 5 tonnes. Stages and lead times per contract. Production capacity — 12 tonnes per shift.
- Shipping documents: halal certificate, declaration of conformity, veterinary certificate (Mercury), Chestny Znak marking, electronic waybill.
- Delivery, lead times and samples are agreed individually. No pork and no alcohol in any product.

Contacts: +7 987 217-02-02 · info@kazandelikates.tatar · 2 Agrarnaya St., office 7, Kazan 420061, Russia.

## Commercial pages

- [Halal pepperoni wholesale (money hub)](https://pepperoni.tatar/en/pepperoni): formats, prices, export.
- [Hot-dog sausages](https://pepperoni.tatar/en/sosiski-dlya-hotdog): fuel-station and street-food line, pallet basis, enquiry form.
- [Kazylyk](https://pepperoni.tatar/en/kazylyk): horse-meat sausage, gift box and sliced.
- [Private label / contract manufacturing](https://pepperoni.tatar/en/private-label): from 5 tonnes, documents, stages.
- [Cases and buyers](https://pepperoni.tatar/en/cases): fuel-station chains, retail, foodservice, private label.
- [Export](https://pepperoni.tatar/en/export): countries and certificate-recognition status.

## Catalog and data

- [Catalog](https://pepperoni.tatar/en/): all {n_sku} SKUs with prices and photos.
- [products.json](https://pepperoni.tatar/products.json): static catalog snapshot (lastSynced field).
- [API /api/products](https://api.pepperoni.tatar/api/products): live JSON, no auth.
- [OpenAPI](https://api.pepperoni.tatar/openapi.yaml): endpoint description.
- [Full LLM context (llms-full.txt)](https://pepperoni.tatar/en/llms-full.txt): every SKU, ingredients, prices in 7 currencies, FAQ.

## Trust

- [About](https://pepperoni.tatar/en/about): company details, certificates, production.
- [Capabilities and certificates](https://pepperoni.tatar/en/capabilities): HACCP, ISO 22000, halal.
- [FAQ](https://pepperoni.tatar/en/faq): buyer questions.

## Optional

- [Russian version](https://pepperoni.tatar/llms.txt)
- [Sitemap](https://pepperoni.tatar/sitemap.xml)
"""


# Russian
ru_txt = sync_sheets.generate_llms_full_txt(products)
(PUBLIC / "llms-full.txt").write_text(ru_txt, encoding="utf-8")
ru_map = llms_map_ru()
(PUBLIC / "llms.txt").write_text(ru_map, encoding="utf-8")
print(f"OK RU: llms.txt {len(ru_map)} chars (map) + llms-full.txt {len(ru_txt)} chars, {n_sku} SKUs")

# English
en_txt = sync_sheets.generate_llms_full_txt_en(products)
en_dir = PUBLIC / "en"
en_dir.mkdir(parents=True, exist_ok=True)
(en_dir / "llms-full.txt").write_text(en_txt, encoding="utf-8")
en_map = llms_map_en()
(en_dir / "llms.txt").write_text(en_map, encoding="utf-8")
print(f"OK EN: en/llms.txt {len(en_map)} chars (map) + en/llms-full.txt {len(en_txt)} chars, {n_sku} SKUs")
