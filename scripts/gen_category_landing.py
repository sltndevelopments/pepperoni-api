#!/usr/bin/env python3
"""Generate B2B category landing pages from config + products.json.

Usage:
  python3 scripts/gen_category_landing.py sosiski

Idempotent: repeated runs rewrite the same public/{slug}.html.
No category-specific hardcoding in this file — all copy lives in
data/category_landing/{slug}.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PRODUCTS_PATH = PUBLIC / "products.json"
CONFIG_DIR = ROOT / "data" / "category_landing"
MANAGERS_PATH = CONFIG_DIR / "managers.json"

PIECES_RE = re.compile(r"(\d+)\s*шт", re.IGNORECASE)


def esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


RESPONSIVE_WIDTHS = (480, 768, 1200, 1600)


def picture_html(
    src: str,
    alt: str,
    *,
    width: int = 1600,
    height: int = 1000,
    eager: bool = False,
    sizes: str = "100vw",
    img_class: str = "",
) -> str:
    """Emit <picture> with avif/webp/jpg srcset when variants exist; else plain img."""
    rel = local_img(src)
    path = Path(rel)
    stem = path.stem
    parent = path.parent.as_posix()
    if parent == ".":
        parent = ""
    else:
        parent = parent.rstrip("/")

    def variant(ext: str) -> list[str]:
        parts = []
        for w in RESPONSIVE_WIDTHS:
            candidate = f"{parent}/{stem}-{w}.{ext}" if parent else f"{stem}-{w}.{ext}"
            if (PUBLIC / candidate.lstrip("/")).is_file():
                parts.append(f"{candidate} {w}w")
        return parts

    avif = variant("avif")
    webp = variant("webp")
    jpg = variant("jpg")
    loading = 'fetchpriority="high" loading="eager"' if eager else 'loading="lazy"'
    cls = f' class="{esc(img_class)}"' if img_class else ""
    fallback = rel
    if not (PUBLIC / rel.lstrip("/")).is_file() and jpg:
        fallback = jpg[0].split()[0]

    if not (avif or webp or jpg):
        return (
            f'<img src="{esc(fallback)}" alt="{esc(alt)}" width="{width}" height="{height}" '
            f"{loading}{cls}>"
        )

    sources = []
    if avif:
        sources.append(
            f'<source type="image/avif" srcset="{esc(", ".join(avif))}" sizes="{esc(sizes)}">'
        )
    if webp:
        sources.append(
            f'<source type="image/webp" srcset="{esc(", ".join(webp))}" sizes="{esc(sizes)}">'
        )
    if jpg:
        sources.append(
            f'<source type="image/jpeg" srcset="{esc(", ".join(jpg))}" sizes="{esc(sizes)}">'
        )
    return (
        "<picture>\n"
        + "\n".join(sources)
        + f'\n<img src="{esc(fallback)}" alt="{esc(alt)}" width="{width}" height="{height}" '
        f"{loading} decoding=\"async\"{cls}>\n</picture>"
    )


def local_img(url: str | None) -> str:
    if not url:
        return ""
    u = str(url).strip()
    if "pepperoni.tatar/" in u:
        u = "/" + u.split("pepperoni.tatar/", 1)[-1]
    if u.startswith("http"):
        return u
    if not u.startswith("/"):
        u = "/" + u
    # strip cache-buster for existence checks; keep in output path without query for static
    return u.split("?", 1)[0]


def parse_pieces(name: str) -> int:
    m = PIECES_RE.search(name or "")
    if not m:
        raise ValueError(f"cannot parse pieces-per-pack from name: {name!r}")
    n = int(m.group(1))
    if n < 1 or n > 100:
        raise ValueError(f"implausible pieces-per-pack {n} in {name!r}")
    return n


def parse_num(raw: object, field: str, sku: str) -> float:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{sku}: missing numeric field {field}")
    s = str(raw).strip().replace(" ", "").replace("кг", "").replace("kg", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError as e:
        raise ValueError(f"{sku}: bad numeric {field}={raw!r}") from e


def require_file(rel: str, sku: str, kind: str) -> None:
    path = PUBLIC / rel.lstrip("/")
    if not path.is_file():
        raise FileNotFoundError(f"{sku}: {kind} file missing: {rel} ({path})")


def load_products_by_category(category: str) -> dict[str, dict]:
    data = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for p in data.get("products") or []:
        if p.get("category") == category:
            out[p["sku"]] = p
    return out


def build_sku_payload(cfg: dict, products: dict[str, dict]) -> list[dict]:
    order = cfg["sku_order"]
    default_moq = int(cfg.get("default_min_order") or 8)
    badges = cfg.get("badges") or {}
    blurbs = cfg.get("blurbs") or {}
    rows: list[dict] = []

    for sku in order:
        p = products.get(sku)
        if not p:
            raise ValueError(f"SKU {sku} not found in products.json for category {cfg['category']!r}")

        offers = p.get("offers") or {}
        price = offers.get("price")
        price_excl = offers.get("priceExclVAT")
        ppp = offers.get("pricePerPiece")
        weight = p.get("weight")
        img_main = local_img(p.get("imageMain") or p.get("image"))
        img_pack = local_img(p.get("imagePack"))
        pack_fallbacks = cfg.get("pack_fallbacks") or {}
        # Prefer larger same-origin card assets when present (catalog thumbs are tiny).
        card_main = f"/images/test1/cards/{sku.lower()}-main.jpg"
        card_pack = f"/images/test1/cards/{sku.lower()}-pack.jpg"
        if (PUBLIC / card_main.lstrip("/")).is_file():
            img_main = card_main
        if (PUBLIC / card_pack.lstrip("/")).is_file():
            img_pack = card_pack
        if not img_pack:
            # Same-origin convention, then optional per-SKU fallback from config.
            candidate = f"/images/products/{sku.lower()}-pack.jpg"
            if (PUBLIC / candidate.lstrip("/")).is_file():
                img_pack = candidate
            elif pack_fallbacks.get(sku):
                img_pack = local_img(pack_fallbacks[sku])

        if not price:
            raise ValueError(f"{sku}: missing offers.price")
        if not weight:
            raise ValueError(f"{sku}: missing weight")
        if not img_main:
            raise ValueError(f"{sku}: missing imageMain/image")
        if not ppp:
            raise ValueError(f"{sku}: missing offers.pricePerPiece")
        if not price_excl:
            raise ValueError(f"{sku}: missing offers.priceExclVAT")

        require_file(img_main, sku, "main image")
        if not img_pack:
            raise ValueError(f"{sku}: missing imagePack (and no pack_fallbacks/{sku.lower()}-pack.jpg)")
        require_file(img_pack, sku, "pack image")

        pieces = parse_pieces(p.get("name") or "")
        moq_raw = str(p.get("minOrder") or "").strip()
        moq = int(moq_raw) if moq_raw else default_moq
        if moq < 1:
            raise ValueError(f"{sku}: invalid minOrder {moq_raw!r}")

        box_gross = p.get("boxWeightGross")
        if not box_gross:
            raise ValueError(f"{sku}: missing boxWeightGross")

        rows.append(
            {
                "sku": sku,
                "name": p["name"],
                "articleNumber": p.get("articleNumber") or "",
                "weight": weight,
                "weightKg": parse_num(weight, "weight", sku),
                "boxWeightGross": box_gross,
                "boxWeightGrossKg": parse_num(box_gross, "boxWeightGross", sku),
                "pieces": pieces,
                "price": parse_num(price, "price", sku),
                "priceExclVAT": parse_num(price_excl, "priceExclVAT", sku),
                "pricePerPiece": parse_num(ppp, "pricePerPiece", sku),
                "shelfLife": p.get("shelfLife") or "",
                "storage": p.get("storage") or "",
                "minOrder": moq,
                "barcode": p.get("barcode") or "",
                "hsCode": p.get("hsCode") or "",
                "cookingMethods": p.get("cookingMethods") or "",
                "imageMain": img_main,
                "imagePack": img_pack,
                "badge": badges.get(sku, ""),
                "blurb": blurbs.get(sku, ""),
                "href": f"/products/{sku.lower()}",
            }
        )

    if len(rows) != len(order):
        raise ValueError(f"expected {len(order)} SKUs, got {len(rows)}")
    return rows


def render_sku_cards(skus: list[dict]) -> str:
    parts = []
    for s in skus:
        badge = f'<span class="cl-badge">{esc(s["badge"])}</span>' if s["badge"] else ""
        parts.append(
            f"""
<article class="cl-card" id="sku-{esc(s['sku'])}" data-sku="{esc(s['sku'])}">
  <label class="cl-card__check">
    <input type="checkbox" class="cl-shortlist-cb" data-sku="{esc(s['sku'])}" aria-label="В шорт-лист {esc(s['sku'])}">
    <span>В шорт-лист</span>
  </label>
  <a class="cl-card__media" href="{esc(s['href'])}">
    {badge}
    <span class="cl-card__hint">Наведите · Пачка</span>
    <img class="cl-card__main" src="{esc(s['imageMain'])}" alt="{esc(s['name'])}" width="640" height="640" loading="lazy">
    <img class="cl-card__alt" src="{esc(s['imagePack'])}" alt="" width="640" height="640" loading="lazy" aria-hidden="true">
  </a>
  <div class="cl-card__body">
    <div class="cl-mono">{esc(s['sku'])}</div>
    <h3 class="cl-card__name">{esc(s['name'])}</h3>
    <p class="cl-card__blurb">{esc(s['blurb'])}</p>
    <div class="cl-mono cl-card__spec">{esc(s['weight'])} кг · {esc(s['pieces'])} шт · {esc(s['storage'])} · {esc(s['shelfLife'])}</div>
    <div class="cl-card__meta">
      <div class="cl-card__price">{esc(f"{s['price']:.0f}")} ₽</div>
      <div class="cl-mono">{esc(f"{s['pricePerPiece']:.2f}")} ₽/порция</div>
    </div>
    <div class="cl-mono cl-card__moq">MOQ {esc(s['minOrder'])} уп.</div>
    <a class="cl-btn cl-btn--sm" href="{esc(s['href'])}">Смотреть карточку</a>
  </div>
</article>"""
        )
    return "\n".join(parts)


def render_table_rows(skus: list[dict]) -> str:
    parts = []
    for s in skus:
        parts.append(
            f"""
<tr data-sku="{esc(s['sku'])}" data-ppp="{s['pricePerPiece']}" data-price="{s['price']}">
  <td><label class="cl-table-check"><input type="checkbox" class="cl-shortlist-cb" data-sku="{esc(s['sku'])}" aria-label="В шорт-лист {esc(s['sku'])}"></label></td>
  <td class="cl-mono"><a href="{esc(s['href'])}">{esc(s['sku'])}</a></td>
  <td>{esc(s['name'])}</td>
  <td class="cl-mono">{esc(s['pieces'])} шт</td>
  <td class="cl-mono">{esc(s['weight'])}</td>
  <td class="cl-mono">{esc(s['boxWeightGross'])}</td>
  <td class="cl-mono" data-col="pieces">{esc(s['pieces'])}</td>
  <td class="cl-mono" data-col="price">{esc(f"{s['price']:.2f}")}</td>
  <td class="cl-mono">{esc(f"{s['priceExclVAT']:.2f}")}</td>
  <td class="cl-mono" data-col="ppp">{esc(f"{s['pricePerPiece']:.2f}")}</td>
  <td class="cl-mono">{esc(s['shelfLife'])}</td>
  <td class="cl-mono">{esc(s['storage'])}</td>
  <td class="cl-mono">{esc(s['minOrder'])}</td>
  <td class="cl-mono">{esc(s['barcode'])}</td>
</tr>"""
        )
    return "\n".join(parts)


def render_saga(cfg: dict) -> str:
    chapters = (cfg.get("saga") or {}).get("chapters") or []
    if len(chapters) > 3:
        chapters = chapters[:3]
    slides = []
    for i, ch in enumerate(chapters):
        slides.append(
            f"""
<figure class="cl-saga__slide" data-saga-slide="{i}">
  {picture_html(ch["image"], "", width=1200, height=800, eager=(i == 0), sizes="(max-width:768px) 85vw, 100vw")}
  <figcaption>
    <h3>{esc(ch["title"])}</h3>
    <p>{esc(ch["body"])}</p>
  </figcaption>
</figure>"""
        )
    return "\n".join(slides)


def render_calc_options(skus: list[dict], default_sku: str) -> str:
    opts = []
    for s in skus:
        sel = " selected" if s["sku"] == default_sku else ""
        opts.append(
            f'<option value="{esc(s["sku"])}"{sel}>{esc(s["sku"])} — {esc(s["name"])}</option>'
        )
    return "\n".join(opts)


def render_band(b: dict) -> str:
    pic = picture_html(
        b["src"],
        b.get("alt") or "",
        width=1600,
        height=900,
        eager=False,
        sizes="100vw",
    )
    return f'<figure class="cl-band">{pic}</figure>'


def render_bands(cfg: dict, start: int = 0, count: int | None = None) -> str:
    bands = cfg.get("band_images") or []
    chunk = bands[start:] if count is None else bands[start : start + count]
    return "\n".join(render_band(b) for b in chunk)


def render_trust(cfg: dict) -> str:
    t = cfg.get("trust") or {}
    items = "".join(f"<li>{esc(x)}</li>" for x in t.get("items") or [])
    photo = t.get("photo") or ""
    return f"""
<section class="cl-section cl-section--cream" id="trust">
  <div class="cl-wrap">
    <p class="cl-mono cl-eyebrow">Доверие</p>
    <h2 class="cl-h2">{esc(t.get("title") or "Документы и условия")}</h2>
    <div class="cl-trust">
      <ul class="cl-trust__list">{items}</ul>
      <figure class="cl-trust__photo">
        {picture_html(photo, t.get("photo_alt") or "", width=960, height=720, sizes="(max-width:800px) 100vw, 50vw")}
      </figure>
    </div>
    <p class="cl-mono cl-logistics" data-cl-logistics>
      Отгрузка EXW Казань
    </p>
  </div>
</section>"""


def build_html(cfg: dict, skus: list[dict], managers: dict, price_date: str) -> str:
    meta = cfg["meta"]
    hero = cfg["hero"]
    calc = cfg["calc_defaults"]
    form = cfg.get("form") or {}
    slug = cfg["slug"]
    anchors = "".join(
        f'<div class="cl-anchor"><b>{esc(a["value"])}</b><span class="cl-mono">{esc(a["label"])}</span></div>'
        for a in hero.get("anchors") or []
    )
    runtime = {
        "slug": slug,
        "category": cfg["category"],
        "shortlistStorageKey": cfg.get("shortlist_storage_key") or f"kd_shortlist_{slug}",
        "priceDate": price_date,
        "defaultMinOrder": cfg.get("default_min_order", 8),
        "calcDefaults": calc,
        "managers": managers,
        "skus": skus,
        "sagaEndPercent": (cfg.get("saga") or {}).get("end_percent", 300),
    }
    runtime_json = json.dumps(runtime, ensure_ascii=False, separators=(",", ":"))

    disclaimer = (
        f"Цены с НДС, EXW Казань, прайс от {price_date}. "
        "Расчёт ориентировочный: не учитывает логистику, аренду, налоги и потери. "
        "Актуальность цен подтверждает менеджер."
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<meta name="robots" content="{esc(meta.get("robots") or "noindex, nofollow")}">
<link rel="canonical" href="{esc(meta["canonical"])}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(meta["title"])}">
<meta property="og:description" content="{esc(meta["description"])}">
<meta property="og:image" content="https://pepperoni.tatar{esc(meta["og_image"])}">
<meta property="og:url" content="{esc(meta["canonical"])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(meta["title"])}">
<meta name="twitter:description" content="{esc(meta["description"])}">
<meta name="twitter:image" content="https://pepperoni.tatar{esc(meta["og_image"])}">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/images/icon-180.png">
<link rel="preload" as="image" href="{esc(hero["image"])}" fetchpriority="high">
<link rel="stylesheet" href="/fonts/category-landing-fonts.css">
<link rel="stylesheet" href="/assets/category-landing.css">
<script type="application/json" id="cl-runtime">{runtime_json}</script>
</head>
<body class="cl-page" data-category-slug="{esc(slug)}">
<a class="cl-skip" href="#main">Перейти к содержимому</a>

<header class="cl-topbar">
  <div class="cl-topbar__inner">
    <a class="cl-topbar__logo" href="/">Казанские Деликатесы</a>
    <nav class="cl-topbar__nav">
      <a href="/">Каталог</a>
      <a class="cl-mono" href="tel:+79872170202" data-cl-phone>+7 987 217-02-02</a>
    </nav>
    <a class="cl-btn cl-btn--sm" href="#order">Запросить прайс</a>
  </div>
</header>

<div class="cl-personal" data-cl-personal hidden>
  <div class="cl-wrap cl-personal__inner">
    <p class="cl-mono" data-cl-personal-line></p>
    <div class="cl-personal__mgr" data-cl-mgr hidden>
      <img data-cl-mgr-photo alt="" width="48" height="48">
      <div>
        <div data-cl-mgr-name></div>
        <div class="cl-mono" data-cl-mgr-role></div>
        <div class="cl-personal__links">
          <a data-cl-mgr-tel href="#"></a>
          <a data-cl-mgr-wa href="#" target="_blank" rel="noopener">WhatsApp</a>
          <a data-cl-mgr-tg href="#" target="_blank" rel="noopener">Telegram</a>
        </div>
      </div>
    </div>
  </div>
</div>

<main id="main">
  <section class="cl-hero">
    <div class="cl-hero__media">
      {picture_html(hero["image"], hero["headline"], width=1600, height=1000, eager=True, sizes="100vw")}
    </div>
    <div class="cl-hero__copy cl-wrap">
      <p class="cl-mono cl-eyebrow">{esc(hero.get("eyebrow") or "")}</p>
      <h1 class="cl-h1">{esc(hero["headline"])}</h1>
      <p class="cl-lead">{esc(hero["sub"])}</p>
      <div class="cl-anchors">{anchors}</div>
      <div class="cl-hero__cta">
        <a class="cl-btn" href="{esc(hero["cta_primary"]["href"])}">{esc(hero["cta_primary"]["label"])}</a>
        <a class="cl-btn cl-btn--outline" href="{esc(hero["cta_secondary"]["href"])}" data-track="{esc(hero["cta_secondary"].get("track") or "")}">{esc(hero["cta_secondary"]["label"])}</a>
      </div>
    </div>
  </section>

  <section class="cl-section cl-saga" id="saga" data-cl-saga data-end-percent="{(cfg.get("saga") or {}).get("end_percent", 300)}">
    <a class="cl-saga__jump" href="#lineup">К линейке ↓</a>
    <div class="cl-saga__pin" data-saga-pin>
      <div class="cl-saga__track">
        {render_saga(cfg)}
      </div>
    </div>
    <div class="cl-saga__mobile" data-saga-mobile aria-label="Галерея">
      {render_saga(cfg)}
    </div>
  </section>

  {render_bands(cfg, 0, 1)}

  <section class="cl-section cl-section--cream" id="calc">
    <div class="cl-wrap">
      <p class="cl-mono cl-eyebrow">Экономика точки</p>
      <h2 class="cl-h2">Сколько зарабатывает порция</h2>
      <p class="cl-lead">Подставьте свой трафик и цену продажи — цифры из прайса подставятся сами.</p>
      <div class="cl-calc" data-cl-calc>
        <div class="cl-calc__controls">
          <label class="cl-field">
            <span class="cl-mono">SKU</span>
            <select data-calc-sku>
              {render_calc_options(skus, calc.get("sku") or skus[0]["sku"])}
            </select>
          </label>
          <label class="cl-field">
            <span class="cl-mono">Порций в день · <b data-calc-portions-label>{esc(calc.get("portions_per_day", 60))}</b></span>
            <input type="range" data-calc-portions min="{esc(calc.get("portions_min", 20))}" max="{esc(calc.get("portions_max", 400))}" step="{esc(calc.get("portions_step", 10))}" value="{esc(calc.get("portions_per_day", 60))}">
          </label>
          <label class="cl-field">
            <span class="cl-mono">Цена продажи хот-дога · <b data-calc-sell-label>{esc(calc.get("sell_price", 180))}</b> ₽</span>
            <input type="range" data-calc-sell min="{esc(calc.get("sell_min", 100))}" max="{esc(calc.get("sell_max", 350))}" step="{esc(calc.get("sell_step", 10))}" value="{esc(calc.get("sell_price", 180))}">
          </label>
          <label class="cl-field">
            <span class="cl-mono">Булка, соус, упаковка, ₽</span>
            <input type="number" data-calc-extras min="0" max="200" step="1" value="{esc(calc.get("extras", 25))}">
          </label>
        </div>
        <div class="cl-calc__out" aria-live="polite">
          <div class="cl-calc__big">
            <div>
              <div class="cl-mono">Маржа с одного хот-дога</div>
              <div class="cl-calc__num" data-calc-margin-unit>—</div>
            </div>
            <div>
              <div class="cl-mono">Маржа в месяц</div>
              <div class="cl-calc__num" data-calc-margin-month>—</div>
            </div>
          </div>
          <dl class="cl-calc__fine cl-mono">
            <div><dt>Себестоимость порции</dt><dd data-calc-cost>—</dd></div>
            <div><dt>Маржа в день</dt><dd data-calc-margin-day>—</dd></div>
            <div><dt>Упаковок в месяц</dt><dd data-calc-packs>—</dd></div>
            <div><dt>Закупка в месяц</dt><dd data-calc-buy>—</dd></div>
          </dl>
        </div>
      </div>
      <p class="cl-disclaimer">{esc(disclaimer)}</p>
    </div>
  </section>

  <section class="cl-section" id="lineup">
    <div class="cl-wrap">
      <div class="cl-lineup-head">
        <div>
          <p class="cl-mono cl-eyebrow">Линейка</p>
          <h2 class="cl-h2">{esc(cfg["category"])}</h2>
        </div>
        <div class="cl-view-toggle" role="group" aria-label="Вид линейки">
          <button type="button" class="cl-view-toggle__btn is-active" data-view="cards">Карточки</button>
          <button type="button" class="cl-view-toggle__btn" data-view="table">Таблица</button>
        </div>
      </div>
      <div class="cl-cards" data-view-panel="cards">
        {render_sku_cards(skus)}
      </div>
      <div class="cl-table-wrap" data-view-panel="table" hidden>
        <table class="cl-table" data-cl-table>
          <thead>
            <tr>
              <th></th>
              <th class="cl-mono">SKU</th>
              <th>Название</th>
              <th class="cl-mono">Фасовка</th>
              <th class="cl-mono">Вес нетто</th>
              <th class="cl-mono">Вес брутто коробки</th>
              <th class="cl-mono">Штук в уп.</th>
              <th class="cl-mono"><button type="button" data-sort="price">Цена ₽ с НДС</button></th>
              <th class="cl-mono">Цена без НДС</th>
              <th class="cl-mono"><button type="button" data-sort="ppp">₽/порция</button></th>
              <th class="cl-mono">Срок</th>
              <th class="cl-mono">Хранение</th>
              <th class="cl-mono">MOQ</th>
              <th class="cl-mono">Штрихкод</th>
            </tr>
          </thead>
          <tbody>
            {render_table_rows(skus)}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  {render_bands(cfg, 1, 1)}

  {render_trust(cfg)}

  <section class="cl-section" id="order">
    <div class="cl-wrap cl-order">
      <p class="cl-mono cl-eyebrow">Заявка</p>
      <h2 class="cl-h2">{esc(form.get("title") or "Запросить прайс")}</h2>
      <p class="cl-lead">{esc(form.get("subtitle") or "")}</p>
      <form class="lead-form cl-form" data-experiment-id="{esc(form.get("experiment_id") or "")}">
        <label class="cl-field">
          <span class="cl-mono">Имя</span>
          <input type="text" name="name" autocomplete="name">
        </label>
        <label class="cl-field">
          <span class="cl-mono">Телефон</span>
          <input type="tel" name="phone" autocomplete="tel" required>
        </label>
        <label class="cl-field cl-field--full">
          <span class="cl-mono">Комментарий / шорт-лист</span>
          <textarea name="message" rows="5" data-cl-message></textarea>
        </label>
        <input type="text" name="company" class="cl-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
        <input type="hidden" name="category" value="{esc(cfg["category"])}">
        <input type="hidden" name="to" value="" data-cl-field="to">
        <input type="hidden" name="mgr" value="" data-cl-field="mgr">
        <input type="hidden" name="city" value="" data-cl-field="city">
        <input type="hidden" name="shortlist" value="" data-cl-field="shortlist">
        <input type="hidden" name="calc_snapshot" value="" data-cl-field="calc_snapshot">
        <label class="cl-consent">
          <input type="checkbox" name="consent" required>
          <span>Согласен на обработку персональных данных</span>
        </label>
        <button type="submit" class="cl-btn">Отправить заявку</button>
        <p class="lead-form__status" role="status" aria-live="polite"></p>
      </form>
    </div>
  </section>
</main>

<aside class="cl-float" data-cl-float hidden>
  <div class="cl-float__text" data-cl-float-text></div>
  <a class="cl-btn cl-btn--sm" href="#order" data-cl-float-cta>Запросить прайс по выбранному</a>
</aside>

<footer class="cl-footer">
  <div class="cl-wrap">
    <p><strong>Казанские Деликатесы</strong> · г. Казань, ул. Аграрная, 2, оф. 7</p>
    <p class="cl-mono"><a href="tel:+79872170202">+7 987 217-02-02</a> · <a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></p>
    <p class="cl-footer__note">{esc(cfg.get("footer_note") or "")} · прайс от {esc(price_date)}</p>
  </div>
</footer>

<script src="/vendor/gsap.min.js" defer></script>
<script src="/vendor/ScrollTrigger.min.js" defer></script>
<script src="/vendor/lenis.min.js" defer></script>
<script src="/assets/gmp-track.js" defer></script>
<script src="/assets/lead-form.js" defer></script>
<script src="/assets/category-landing.js" defer></script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate category B2B landing")
    ap.add_argument("slug", help="category slug, e.g. sosiski")
    args = ap.parse_args()
    slug = args.slug.strip().lower()

    cfg_path = CONFIG_DIR / f"{slug}.json"
    if not cfg_path.is_file():
        print(f"ERROR: config not found: {cfg_path}", file=sys.stderr)
        return 1
    if not MANAGERS_PATH.is_file():
        print(f"ERROR: managers not found: {MANAGERS_PATH}", file=sys.stderr)
        return 1

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("slug") != slug:
        print(f"ERROR: config slug {cfg.get('slug')!r} != arg {slug!r}", file=sys.stderr)
        return 1

    managers = json.loads(MANAGERS_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
    products = {
        p["sku"]: p
        for p in (catalog.get("products") or [])
        if p.get("category") == cfg["category"]
    }
    skus = build_sku_payload(cfg, products)
    # Stable across same-day regenerations: prefer catalog lastSynced date.
    synced = str(catalog.get("lastSynced") or "")[:10]
    price_date = synced if re.match(r"^\d{4}-\d{2}-\d{2}$", synced) else date.today().isoformat()
    html = build_html(cfg, skus, managers, price_date)

    out = PUBLIC / f"{slug}.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({len(skus)} SKUs, price_date={price_date})")
    for s in skus:
        print(
            f"  {s['sku']} price={s['price']:.2f} ppp={s['pricePerPiece']:.2f} "
            f"pieces={s['pieces']} moq={s['minOrder']} kg={s['weightKg']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
