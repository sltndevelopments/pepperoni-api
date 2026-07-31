#!/usr/bin/env python3
"""Generate B2B money-hub pages for Money 12 SKUs → public/money/*.html + public/money.html."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
MONEY_DIR = PUBLIC / "money"
PRODUCTS = ROOT / "public" / "products.json"
MONEY12 = ROOT / "data" / "money_12.json"

CHANNEL_LABEL = {
    "azs": "АЗС",
    "horeca": "HoReCa",
    "pl": "Private Label",
    "retail": "Ритейл",
    "export": "Экспорт",
}

# Lifestyle punch heroes for grill money-SKU hubs (catalog pack shots stay on /products/*)
HERO_BY_SKU = {
    "KD-001": "/images/hero/hotdog-french.jpg",
    "KD-002": "/images/hero/hotdog-onions.jpg",
    "KD-003": "/images/hero/hotdog-classic.jpg",
    "KD-004": "/images/hero/hotdog-french.jpg",
    "KD-005": "/images/hero/hotdog-onions.jpg",
    "KD-006": "/images/hero/hotdog-classic.jpg",
    "KD-007": "/images/hero/hotdog-onions.jpg",
    "KD-008": "/images/hero/hotdog-french.jpg",
    "KD-009": "/images/hero/hotdog-classic.jpg",
}


def load() -> tuple[dict, dict]:
    money = json.loads(MONEY12.read_text(encoding="utf-8"))
    products = {p["sku"]: p for p in json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]}
    return money, products


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def hub_html(entry: dict, p: dict) -> str:
    sku = entry["sku"]
    name = p.get("name") or sku
    price = p.get("offers", {}).get("price", "—")
    weight = p.get("weight") or "—"
    storage = p.get("storage") or "—"
    shelf = p.get("shelfLife") or "—"
    img = HERO_BY_SKU.get(sku) or p.get("imageMain") or p.get("image") or "/images/og-default.png"
    if isinstance(img, str) and img.startswith("http"):
        img_src = "/" + img.split("pepperoni.tatar/", 1)[-1] if "pepperoni.tatar/" in img else img
    else:
        img_src = img
    pitch = entry.get("pitch3") or ["Халяль", "B2B", sku]
    chans = ", ".join(CHANNEL_LABEL.get(c, c) for c in entry.get("channels", []))
    tier = entry.get("tier", "B")
    slug = sku.lower()
    title = f"{name} — Money hub {sku} | Казанские Деликатесы"
    desc = f"B2B money-SKU {sku}: {pitch[0]} · {pitch[1]} · {pitch[2]}. Халяль ДУМ РТ №614A/2024. Заказать опт."

    pitch_html = "".join(
        f'<div class="stat"><b>{esc(x)}</b><span>сигнал {i+1}</span></div>'
        for i, x in enumerate(pitch[:3])
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/money/{slug}">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<style>
:root{{--g:#1b7a3d;--ink:#16110f;--paper:#faf6f2;--line:#e8e0d8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:var(--paper);color:var(--ink);line-height:1.55}}
.wrap{{max-width:920px;margin:0 auto;padding:24px 16px 48px}}
nav{{font-size:.85rem;margin-bottom:20px}}
nav a{{color:#06c;text-decoration:none}}
.badge{{display:inline-block;background:var(--g);color:#fff;padding:4px 10px;border-radius:4px;font-size:.75rem;font-weight:700;margin:0 6px 12px 0}}
.badge--muted{{background:#555}}
h1{{font-size:clamp(1.4rem,3vw,2rem);margin:8px 0 12px;line-height:1.2}}
.grid{{display:grid;gap:24px;margin-top:20px}}
@media(min-width:760px){{.grid{{grid-template-columns:1fr 1fr;align-items:start}}}}
.media{{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.media img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:16px 0}}
.stat{{background:#fff;padding:14px 10px;text-align:center}}
.stat b{{display:block;font-size:.95rem;color:var(--g)}}
.stat span{{font-size:.72rem;color:#666}}
.meta{{font-size:.92rem;color:#444}}
.meta p{{margin:6px 0}}
.cta{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}}
.cta a{{display:inline-flex;align-items:center;padding:11px 18px;border-radius:8px;font-weight:600;text-decoration:none;font-size:.9rem}}
.cta .p{{background:var(--g);color:#fff}}
.cta .o{{border:2px solid var(--g);color:var(--g)}}
.foot{{margin-top:36px;padding-top:16px;border-top:1px solid var(--line);font-size:.85rem;color:#666}}
.foot a{{color:#06c}}
</style>
</head>
<body>
<div class="wrap">
  <nav><a href="/">Каталог</a> · <a href="/money">Money 12</a> · <a href="/products/{slug}">{esc(sku)}</a></nav>
  <span class="badge">Money {esc(tier)}</span>
  <span class="badge badge--muted">{esc(sku)}</span>
  <h1>{esc(name)}</h1>
  <p class="meta">Каналы: {esc(chans)} · Роль: {esc(entry.get("role", "money"))}</p>
  <div class="stats">{pitch_html}</div>
  <div class="grid">
    <div class="media"><img src="{esc(img_src)}" alt="{esc(name)}" width="800" height="600" loading="eager"></div>
    <div class="meta">
      <p><strong>Ориентир цены:</strong> {esc(str(price))} ₽ с НДС</p>
      <p><strong>Вес / фасовка:</strong> {esc(str(weight))}</p>
      <p><strong>Хранение:</strong> {esc(str(storage))} · {esc(str(shelf))}</p>
      <p><strong>Сертификация:</strong> Халяль ДУМ РТ №614A/2024 · HACCP · ISO 22000:2018</p>
      <p>Страница сделки для закупщика АЗС / HoReCa / PL. Полная карточка и экспортные цены — в каталоге.</p>
      <div class="cta">
        <a class="p" href="https://t.me/KazanDel_Bot?start={esc(sku)}" target="_blank" rel="noopener">Telegram — прайс</a>
        <a class="o" href="https://wa.me/79872170202" target="_blank" rel="noopener">WhatsApp</a>
        <a class="o" href="tel:+79872170202">+7 987 217-02-02</a>
        <a class="o" href="/products/{slug}">Карточка SKU</a>
      </div>
    </div>
  </div>
  <div class="foot">
    <a href="/money">← Все Money 12</a> ·
    <a href="/dlya-azs">Для АЗС</a> ·
    <a href="/dlya-horeca">HoReCa</a> ·
    <a href="/private-label">Private Label</a> ·
    <a href="/zozh">ЗОЖ-линейка</a>
  </div>
</div>
</body>
</html>
"""


def index_html(rows: list[dict]) -> str:
    cards = []
    for r in rows:
        cards.append(
            f"""<a class="card" href="/money/{r['slug']}">
  <img src="{esc(r['img'])}" alt="" width="400" height="300" loading="lazy">
  <div>
    <span class="tier">Money {esc(r['tier'])} · {esc(r['sku'])}</span>
    <strong>{esc(r['name'])}</strong>
    <span class="pitch">{esc(' · '.join(r['pitch']))}</span>
  </div>
</a>"""
        )
    body = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Money 12 — фокусные SKU для АЗС, HoReCa и Private Label | Казанские Деликатесы</title>
<meta name="description" content="12 money-SKU для роста B2B: сосиски гриль, пепперони, котлеты, казылык. Халяль. Прайс и заказ оптом.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/money">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<style>
:root{{--g:#1b7a3d;--ink:#16110f;--paper:#faf6f2;--line:#e8e0d8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,sans-serif;background:var(--paper);color:var(--ink);line-height:1.55}}
.wrap{{max-width:1100px;margin:0 auto;padding:28px 16px 56px}}
nav a{{color:#06c;text-decoration:none;font-size:.9rem}}
h1{{font-size:clamp(1.6rem,3.5vw,2.2rem);margin:12px 0 8px}}
.lead{{color:#555;max-width:40rem;margin-bottom:22px}}
.cta{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:28px}}
.cta a{{padding:10px 16px;border-radius:8px;font-weight:600;text-decoration:none;font-size:.9rem}}
.cta .p{{background:var(--g);color:#fff}}
.cta .o{{border:2px solid var(--g);color:var(--g)}}
.grid{{display:grid;gap:14px;grid-template-columns:1fr}}
@media(min-width:700px){{.grid{{grid-template-columns:1fr 1fr}}}}
@media(min-width:1000px){{.grid{{grid-template-columns:1fr 1fr 1fr}}}}
.card{{display:grid;grid-template-columns:120px 1fr;gap:12px;background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px;text-decoration:none;color:inherit;align-items:center}}
.card img{{width:120px;height:90px;object-fit:cover;border-radius:6px}}
.card .tier{{display:block;font-size:.72rem;color:var(--g);font-weight:700;margin-bottom:4px}}
.card strong{{display:block;font-size:.95rem;margin-bottom:4px}}
.card .pitch{{font-size:.8rem;color:#666}}
.note{{margin-top:28px;font-size:.85rem;color:#666}}
</style>
</head>
<body>
<div class="wrap">
  <nav><a href="/">Каталог</a> · <a href="/dlya-azs">АЗС</a> · <a href="/dlya-horeca">HoReCa</a> · <a href="/private-label">PL</a></nav>
  <h1>Money 12</h1>
  <p class="lead">Фокусные SKU для сделок: не весь каталог из 64 позиций, а 12 позиций под АЗС, HoReCa и Private Label. Цель — ≥70% выручки с этого набора к 2028.</p>
  <div class="cta">
    <a class="p" href="https://t.me/KazanDel_Bot?start=money12" target="_blank" rel="noopener">Запросить прайс Money 12</a>
    <a class="o" href="/zozh">ЗОЖ hero-линейка</a>
    <a class="o" href="/#catalog">Полный каталог</a>
  </div>
  <div class="grid">
{body}
  </div>
  <p class="note">Канон списка: <code>data/money_12.json</code>. Стратегия: <code>docs/CATCH-CHOMPS-STRATEGY.md</code>.</p>
</div>
</body>
</html>
"""


def main() -> None:
    money, products = load()
    MONEY_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    missing = []
    for entry in money["money12"]:
        sku = entry["sku"]
        p = products.get(sku)
        if not p:
            missing.append(sku)
            continue
        html = hub_html(entry, p)
        slug = sku.lower()
        (MONEY_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
        img = HERO_BY_SKU.get(sku) or p.get("imageMain") or p.get("image") or "/images/og-default.png"
        if isinstance(img, str) and "pepperoni.tatar/" in img:
            img = "/" + img.split("pepperoni.tatar/", 1)[-1]
        rows.append(
            {
                "sku": sku,
                "slug": slug,
                "name": p.get("name") or sku,
                "tier": entry.get("tier", "B"),
                "pitch": entry.get("pitch3") or [],
                "img": img,
            }
        )
    (PUBLIC / "money.html").write_text(index_html(rows), encoding="utf-8")
    # clean URL: also money/index via money.html at /money when nginx try_files
    print(f"generated {len(rows)} hubs + /money.html")
    if missing:
        raise SystemExit(f"missing products: {missing}")


if __name__ == "__main__":
    main()
