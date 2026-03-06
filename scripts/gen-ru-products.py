#!/usr/bin/env python3
"""Generate RU product pages from products.json. Source of truth: sync-sheets."""
import json
import os
import re
import urllib.parse

OUT = "public/products"
PRODUCTS_JSON = "public/products.json"
SYMS = {"USD": "$", "KZT": "₸", "UZS": "UZS", "KGS": "KGS", "BYN": "BYN", "AZN": "AZN"}


def extract_qty_from_name(name):
    m = re.search(r"[×x]\s*(\d+)\s*шт", str(name or ""), re.I)
    return int(m.group(1)) if m else 0


def html_esc(s):
    return str(s or "").replace("\\", "\\\\").replace('"', '\\"')


def cloudinary_url(pid, is_full=False, width=None, via_proxy=False):
    """Build Cloudinary URL; if via_proxy, return /api/health?u=... for fallback when direct fails."""
    if not pid or not str(pid).strip():
        return ""
    pid = str(pid).strip()
    # Если пришла полная ссылка — вытащим ID (v123/name.jpg или name.jpg)
    if "cloudinary.com" in pid:
        try:
            parts = pid.split("/upload/")
            last_part = parts[-1].split("?")[0]
            m = re.search(r"(v\d+/.+)|([^/]+\.(?:jpg|jpeg|png|webp))", last_part)
            pid = m.group(1) or m.group(2) if m else last_part.split("/")[-1]
        except Exception:
            return pid
    if not pid:
        return ""
    # Добавляем .jpg если нет расширения изображения
    last = pid.split("/")[-1].lower()
    if not any(last.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
        if "/" in pid:
            prefix, name = pid.rsplit("/", 1)
            pid = f"{prefix}/{name}.jpg"
        else:
            pid = f"{pid}.jpg"
    pid = pid.replace("govyadiny", "govadiny")
    base = "https://res.cloudinary.com/duygfl3vz/image/upload/"
    thumb_w = int(width) if width else 800
    if thumb_w <= 320:
        thumb_size = "w_320,h_213,c_fill,g_auto"
    elif thumb_w <= 480:
        thumb_size = "w_480,h_320,c_fill,g_auto"
    elif thumb_w <= 640:
        thumb_size = "w_640,h_427,c_fill,g_auto"
    else:
        thumb_size = "w_800,h_533,c_fill,g_auto"
    thumb = f"f_auto,q_auto,{thumb_size}/l_text:Arial_50_bold:KAZAN_DELIKATES,co_rgb:FFFFFF,o_30/fl_layer_apply,g_center/"
    full = "f_auto,q_auto,w_1920,c_limit/l_text:Arial_100_bold:KAZAN_DELIKATES,co_rgb:FFFFFF,o_30/fl_layer_apply,g_center/"
    transform = full if is_full else thumb
    remote = f"{base}{transform}{pid}?v=3"
    if via_proxy:
        return f"/api/health?u={urllib.parse.quote(remote, safe='')}"
    return remote


def load_products():
    """Load from products.json (source of truth). API may have stale/wrong column mapping."""
    p = os.path.join(os.path.dirname(__file__), "..", PRODUCTS_JSON)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("products", [])
    return []


def main():
    os.makedirs(OUT, exist_ok=True)
    products = load_products()
    for p in products:
        slug = p["sku"].lower()
        is_bakery = bool(p.get("offers", {}).get("pricePerUnit"))
        price_rub = (
            p["offers"]["pricePerUnit"] if is_bakery else p["offers"]["price"]
        )
        price_no_vat = p["offers"].get("priceExclVAT") or p["offers"].get(
            "pricePerBoxExclVAT", ""
        )
        ep = p["offers"].get("exportPrices") or {}
        weight = p.get("weight", "")
        weight_suffix = "" if (" г" in weight or " кг" in weight) else " кг"
        pr = float(price_rub) if price_rub else 0
        name = " ".join(str(p["name"] or "").split())  # collapse newlines/spaces for meta
        section = p.get("section", "")
        seo_desc = p.get("seoDescriptionRU") or f"{name}. {p.get('category','')}. Халяль продукция от Казанских Деликатесов. {('Вес: ' + weight + '. ') if weight else ''} Цена: {price_rub} ₽. {(p.get('shelfLife','') and 'Срок годности: ' + p['shelfLife'] + '.') or ''}"
        seo_desc = seo_desc[:160].replace('"', "&quot;")

        main_raw = (p.get("imageMain") or p.get("image") or "").strip()
        pack_raw = (p.get("imagePack") or "").strip()
        slice_raw = (p.get("imageSlice") or "").strip()

        main_img_480 = cloudinary_url(main_raw, False, 480, False)
        main_img_640 = cloudinary_url(main_raw, False, 640, False)
        main_img_proxy = cloudinary_url(main_raw, False, 640, True)
        main_full = cloudinary_url(main_raw, True, None, False)
        main_full_proxy = cloudinary_url(main_raw, True, None, True)
        pack_img_480 = cloudinary_url(pack_raw, False, 480, False)
        pack_img = cloudinary_url(pack_raw, False, 800, False)
        pack_img_proxy = cloudinary_url(pack_raw, False, 800, True)
        pack_full = cloudinary_url(pack_raw, True, None, False)
        pack_full_proxy = cloudinary_url(pack_raw, True, None, True)
        slice_img_480 = cloudinary_url(slice_raw, False, 480, False)
        slice_img = cloudinary_url(slice_raw, False, 800, False)
        slice_img_proxy = cloudinary_url(slice_raw, False, 800, True)
        slice_full = cloudinary_url(slice_raw, True, None, False)
        slice_full_proxy = cloudinary_url(slice_raw, True, None, True)

        seo_start = (p.get("seoDescriptionRU") or "")[:60]
        alt_main = (f"{name}. {seo_start}".rstrip(". ") or name).replace('"', "&quot;")
        img_class = "product-img"
        img_style = "max-width:100%;height:auto;border-radius:8px;object-fit:cover;width:100%;cursor:pointer;background:transparent"
        img_attrs = 'oncontextmenu="return false;" ondragstart="return false;" onerror="if(this.dataset.proxy){this.onerror=null;this.src=this.dataset.proxy}"'
        thumbs = []
        for label, url_480, url, proxy, full, full_proxy in [("Упаковка", pack_img_480, pack_img, pack_img_proxy, pack_full, pack_full_proxy), ("В разрезе", slice_img_480, slice_img, slice_img_proxy, slice_full, slice_full_proxy)]:
            if url:
                if url_480:
                    thumb_img = f'<img src="{url}" srcset="{url_480} 480w, {url} 800w" sizes="(max-width: 768px) 100vw, 800px" data-proxy="{proxy}" alt="{html_esc(name)} — {label}" class="{img_class}" style="{img_style}" width="800" height="533" loading="lazy" {img_attrs}/>'
                else:
                    thumb_img = f'<img src="{url}" data-proxy="{proxy}" alt="{html_esc(name)} — {label}" class="{img_class}" style="{img_style}" width="800" height="533" loading="lazy" {img_attrs}/>'
                thumbs.append(f'<span class="lightbox-trigger" data-full="{full}" data-full-proxy="{full_proxy}" tabindex="0" role="button">{thumb_img}</span>')

        img_html = ""
        if main_img_640:
            if main_img_480:
                main_tag = f'<span class="lightbox-trigger" data-full="{main_full}" data-full-proxy="{main_full_proxy}" tabindex="0" role="button"><img src="{main_img_640}" srcset="{main_img_480} 480w, {main_img_640} 640w" sizes="(max-width: 768px) 100vw, 640px" data-proxy="{main_img_proxy}" alt="{alt_main}" class="{img_class}" style="{img_style}" width="640" height="427" loading="eager" fetchpriority="high" decoding="sync" {img_attrs}/></span>'
            else:
                main_tag = f'<span class="lightbox-trigger" data-full="{main_full}" data-full-proxy="{main_full_proxy}" tabindex="0" role="button"><img src="{main_img_640}" data-proxy="{main_img_proxy}" alt="{alt_main}" class="{img_class}" style="{img_style}" width="640" height="427" loading="eager" fetchpriority="high" decoding="sync" {img_attrs}/></span>'
            if thumbs:
                img_html = f'<div class="product-gallery"><div class="product-main-img">{main_tag}</div><div class="product-thumbs">{"".join(thumbs)}</div></div>'
            else:
                img_html = f'<div class="product-gallery"><div class="product-main-img">{main_tag}</div></div>'

        specs = []
        if p.get("articleNumber") or p.get("sku"):
            specs.append(("Артикул", p.get("articleNumber") or p["sku"]))
        if p.get("barcode"):
            specs.append(("Штрих-код", p["barcode"]))
        if p.get("diameter"):
            specs.append(("Диаметр", f"{p['diameter']} мм"))
        if p.get("casing"):
            specs.append(("Оболочка", p["casing"]))
        if p.get("shelfLife"):
            specs.append(("Срок годности", p["shelfLife"]))
        if p.get("storage"):
            specs.append(("Условия хранения", p["storage"]))
        if p.get("boxWeightGross"):
            specs.append(("Вес коробки брутто", p["boxWeightGross"]))
        if p.get("packageType"):
            specs.append(("Тип упаковки", p["packageType"]))
        if p.get("minOrder"):
            specs.append(("Мин. заказ", p["minOrder"]))
        if p.get("nutrition"):
            specs.append(("КБЖУ", p["nutrition"]))
        specs_rows = "".join(f'<tr><td class="specs-key">{k}</td><td class="specs-val">{v}</td></tr>' for k, v in specs)
        specs_table = f'<div class="section-block"><h2 class="section-title">Технические характеристики</h2><table class="specs-table"><tbody>{specs_rows}</tbody></table></div>' if specs else ""

        preload_main = f'<link rel="preconnect" href="https://res.cloudinary.com" crossorigin><link rel="preload" as="image" href="{main_img_480 or main_img_640}" fetchpriority="high">' if (main_img_480 or main_img_640) else ""

        html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="/favicon.ico" type="image/x-icon">
<meta http-equiv="content-language" content="ru">
<title>{name} — Казанские Деликатесы | Халяль</title>
<meta name="description" content="{seo_desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://pepperoni.tatar/products/{slug}">
<meta property="og:type" content="product">
<meta property="og:title" content="{name} — Казанские Деликатесы">
<meta property="og:description" content="{p.get('category','')}. {price_rub} ₽. Халяль.">
<meta property="og:url" content="https://pepperoni.tatar/products/{slug}">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" hreflang="ru" href="https://pepperoni.tatar/products/{slug}">
<link rel="alternate" hreflang="en" href="https://pepperoni.tatar/en/products/{slug}">
{preload_main}
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Главная","item":"https://pepperoni.tatar/"}},{{"@type":"ListItem","position":2,"name":"Каталог","item":"https://pepperoni.tatar/"}},{{"@type":"ListItem","position":3,"name":"{html_esc(name)}","item":"https://pepperoni.tatar/products/{slug}"}}]}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Product","name":"{html_esc(name)}","sku":"{p['sku']}","brand":{{"@type":"Brand","name":"Казанские Деликатесы"}},"offers":{{"@type":"Offer","priceCurrency":"RUB","price":"{price_rub}","availability":"https://schema.org/InStock"}},"manufacturer":{{"@type":"Organization","name":"Казанские Деликатесы","url":"https://kazandelikates.tatar"}}}}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;color:#1a1a1a;line-height:1.6}}
.container{{max-width:960px;margin:0 auto;padding:24px 16px}}
@media(min-width:768px){{.container{{padding:40px 24px}}}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;letter-spacing:.5px}}
.product-hero{{display:grid;gap:32px;margin-bottom:32px;align-items:start}}
@media(min-width:768px){{.product-hero{{grid-template-columns:1fr 1fr}}}}
.product-gallery{{background:transparent;border-radius:0;padding:0;box-shadow:none}}
.product-main-img{{margin-bottom:10px;aspect-ratio:3/2;overflow:hidden;background:#f0f0f0}}
.product-main-img img{{display:block;width:100%;height:100%;object-fit:cover;background:transparent}}
.product-thumbs{{display:grid;grid-template-columns:1fr;gap:12px}}
.product-thumbs img{{display:block;width:100%;max-width:none;aspect-ratio:3/2;height:auto;object-fit:cover;cursor:pointer;border:2px solid transparent;transition:border-color .2s}}
.product-thumbs img:hover{{border-color:#1b7a3d}}
.product-thumbs .lightbox-trigger{{display:inline-block}}
.lightbox-trigger{{cursor:pointer}}
.product-img{{max-width:100%;height:auto;border-radius:8px;object-fit:cover;user-select:none;-webkit-user-drag:none}}
.lightbox{{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.9);display:flex;align-items:center;justify-content:center;padding:20px;cursor:pointer}}
.lightbox img{{max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;cursor:default;user-select:none;-webkit-user-drag:none}}
.lightbox-close{{position:absolute;top:16px;right:16px;width:40px;height:40px;background:#fff;border:none;border-radius:50%;cursor:pointer;font-size:24px;line-height:1;color:#333}}
.lightbox-close:hover{{background:#eee}}
.product-info{{background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.price-block{{font-size:1.75rem;font-weight:700;color:#1b7a3d;margin:16px 0}}
.section-block{{background:#fff;border-radius:12px;padding:24px;margin-top:24px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.section-title{{font-size:1rem;color:#1b7a3d;margin-bottom:16px;font-weight:600}}
.specs-table{{width:100%;border-collapse:collapse;font-size:.9rem}}
.specs-table td{{padding:12px 16px;border:1px solid #e8e8e8}}
.specs-table tr:nth-child(even){{background:#f8f9fa}}
.specs-key{{color:#666;width:40%}}
.specs-val{{color:#1a1a1a;font-weight:500}}
.cta-box{{background:#f0f7f0;border:2px solid #1b7a3d;border-radius:10px;padding:24px;margin-top:24px}}
.cta-box a{{display:inline-block;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0}}
.tg-order-btn,.wa-order-btn{{display:inline-flex;align-items:center;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0;transition:background .2s}}
.tg-order-btn{{background:#0088cc;color:#fff}}.tg-order-btn:hover{{background:#006699;color:#fff}}
.wa-order-btn{{background:#128c7e;color:#fff}}.wa-order-btn:hover{{background:#0d6b5f;color:#fff}}
.export-prices{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}}
.export-prices span{{background:#fff;border:1px solid #ddd;padding:8px 14px;border-radius:6px;font-size:.85rem}}
footer{{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}}
footer a{{color:#444;text-decoration:none}}
@media(max-width:767px){{.product-thumbs{{gap:10px}}}}
@media(max-width:480px){{.product-thumbs{{gap:8px}}}}
</style>
<!-- Yandex.Metrika counter -->
<script type="text/javascript">(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r)return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");ym(107064141,"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:"dataLayer"}});</script>
<noscript><div><img src="https://mc.yandex.ru/watch/107064141" style="position:absolute;left:-9999px" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
</head>
<body>
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
<script>window.dataLayer=window.dataLayer||[];window.dataLayer.push({{ecommerce:{{detail:{{products:[{{id:"{p['sku']}",name:"{html_esc(name)}",price:{pr},brand:"Казанские Деликатесы",category:"{html_esc(p.get('category',''))}"}}]}}}}}});</script>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
<a href="/" style="color:#0066cc;text-decoration:none">Каталог</a>
<a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
<a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
<a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
<a href="/en/products/{slug}" style="color:#595959;text-decoration:none;margin-left:auto">🇬🇧 English</a>
</div>
<nav aria-label="breadcrumb" style="font-size:.85rem;color:#666;margin-bottom:24px">
  <ol itemscope itemtype="https://schema.org/BreadcrumbList" style="list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px">
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><a itemprop="item" href="https://pepperoni.tatar/"><span itemprop="name">Главная</span></a><meta itemprop="position" content="1"></li>
    <span aria-hidden="true"> › </span>
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><a itemprop="item" href="https://pepperoni.tatar/"><span itemprop="name">Каталог</span></a><meta itemprop="position" content="2"></li>
    <span aria-hidden="true"> › </span>
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><span itemprop="name">{html_esc(name)}</span><meta itemprop="position" content="3"></li>
  </ol>
</nav>
<div class="product-hero">
<div>{img_html if img_html else '<div class="product-gallery"><div class="product-main-img"><span style="color:#999;font-size:.9rem">Фото не загружено</span></div></div>'}</div>
<div class="product-info">
<h1 style="font-size:1.5rem;margin-bottom:10px">{name}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">
<span class="badge">HALAL</span>
<span class="badge" style="background:#0066cc">{p['sku']}</span>
<span class="badge" style="background:#555">{section}</span>
</div>
'''
        fmt = f"{pr:,.2f}".replace(",", " ").replace(".", ",")
        html += f'<div class="price-block">{fmt} ₽<span style="font-size:.85rem;color:#767676;font-weight:400">{" /шт" if is_bakery else " с НДС"}</span></div>\n'
        html += '<div style="color:#1b7a3d;font-size:.9rem;margin:8px 0">✓ В наличии</div>\n'
        if is_bakery and p["offers"].get("pricePerBox"):
            pbox = float(p["offers"]["pricePerBox"])
            qty = p.get("qtyPerBox", "")
            qty_str = f" ({qty} шт)" if qty else ""
            pbox_fmt = f"{pbox:,.2f}".replace(",", " ").replace(".", ",")
            html += f'<div style="margin-top:8px;font-size:.9rem;color:#444">Цена за коробку: <b>{pbox_fmt} ₽</b>{qty_str}</div>\n'
        elif not is_bakery:
            pp = p["offers"].get("pricePerPiece")
            if not pp:
                qty = extract_qty_from_name(p.get("name", ""))
                if qty > 1 and price_rub:
                    pp = str(round(float(price_rub) / qty, 2))
            if pp:
                pp_fmt = f"{float(pp):,.2f}".replace(",", " ").replace(".", ",")
                html += f'<div style="margin-top:8px;font-size:.9rem;color:#444">Цена за 1 шт: <b>{pp_fmt} ₽</b></div>\n'
        if price_no_vat or ep:
            html += '<h2 class="section-title" style="margin-top:20px">Экспортные цены</h2><div class="export-prices">'
            if price_no_vat:
                html += f'<span><b>{price_no_vat}</b> ₽ <small style="color:#767676">без НДС</small></span>'
            for cur, val in ep.items():
                if val:
                    html += f'<span><b>{val}</b> {SYMS.get(cur, cur)}</span>'
            html += "</div>\n"
        subj = urllib.parse.quote(f"Заказ: {name} ({p['sku']})", safe="")
        tg_svg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="margin-right:6px;flex-shrink:0"><path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.56 8.16l-1.9 8.94c-.15.65-.53.81-1.08.5l-3-2.21-1.44 1.39c-.16.16-.29.29-.6.29l.21-3.05 5.55-5.02c.24-.22-.05-.34-.38-.11l-6.86 4.32-2.96-.92c-.64-.2-.65-.64.13-.95l11.55-4.45c.53-.2.99.11.78.97z"/></svg>'
        wa_svg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="margin-right:6px;flex-shrink:0"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
        html += f'''<div class="cta-box">
<h3 style="margin:0 0 8px">Заказ</h3>
<p style="color:#444;margin-bottom:12px">Опт, экспорт, Private Label</p>
<a href="https://t.me/KazanDel_Bot?start={p['sku']}" target="_blank" rel="noopener" class="tg-order-btn">{tg_svg}Telegram</a>
<a href="https://wa.me/79872170202" target="_blank" rel="noopener" class="wa-order-btn">{wa_svg}WhatsApp</a>
<a href="tel:+79872170202" style="background:#1b7a3d;color:#fff">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject={subj}" style="border:2px solid #1b7a3d;color:#1b7a3d">📧 Написать</a>
</div>
</div>
</div>
'''
        html += specs_table
        if p.get("ingredientsRU"):
            ing = p["ingredientsRU"].replace("<", "&lt;").replace(">", "&gt;")
            html += f'<div class="section-block"><h2 class="section-title">Состав</h2><p style="font-size:.9rem;color:#444;line-height:1.6;margin:0">{ing}</p></div>\n'
        if p.get("cookingMethods"):
            cm = p["cookingMethods"].replace("<", "&lt;").replace(">", "&gt;")
            html += f'<div class="section-block"><h2 class="section-title">Способы приготовления</h2><p style="font-size:.9rem;color:#444;line-height:1.6;margin:0">{cm}</p></div>\n'
        html += '''<footer>
<p><a href="/pepperoni">Пепперони</a> · <a href="/about">О компании</a> · <a href="/faq">FAQ</a> · <a href="/delivery">Доставка</a> · <a href="https://api.pepperoni.tatar/">Для дистрибьюторов (API)</a></p>
<p>© <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
<script>
document.addEventListener("click",function(e){
  var link=e.target.closest("a");if(!link)return;
  var href=link.getAttribute("href")||"";
  if(href.indexOf("tel:")===0){typeof ym==="function"&&ym(107064141,"reachGoal","click_phone")}
  if(href.indexOf("mailto:")===0){typeof ym==="function"&&ym(107064141,"reachGoal","click_email")}
  if(href.indexOf("kazandelikates.tatar")!==-1){typeof ym==="function"&&ym(107064141,"reachGoal","go_to_main_site")}
});
document.querySelectorAll(".lightbox-trigger").forEach(function(el){
  el.addEventListener("click",function(){
    var full=el.getAttribute("data-full");if(!full)return;
    var fullProxy=el.getAttribute("data-full-proxy")||"";
    var m=document.createElement("div");m.className="lightbox";
    var btn=document.createElement("button");btn.className="lightbox-close";btn.setAttribute("aria-label","Закрыть");btn.textContent="×";
    var img=document.createElement("img");img.src=full;img.alt="";img.oncontextmenu=function(){return false};img.ondragstart=function(){return false};
    if(fullProxy){img.onerror=function(){this.onerror=null;this.src=fullProxy;};}
    m.appendChild(btn);m.appendChild(img);
    m.onclick=function(ev){if(ev.target===m||ev.target===btn){document.body.removeChild(m);document.body.style.overflow="";}};
    img.onclick=function(ev){ev.stopPropagation();};
    document.body.style.overflow="hidden";document.body.appendChild(m);
  });
});
</script>
</body>
</html>'''
        path = os.path.join(OUT, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"Generated {len(products)} RU product pages in {OUT}/")


if __name__ == "__main__":
    main()
