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
        price_usd = p["offers"].get("exportPrices", {}).get("USD", "")
        ep = p["offers"].get("exportPrices") or {}
        export_html = ""
        if price_no_vat or ep:
            export_html = '<h3 style="margin-top:20px;font-size:1rem;color:#1b7a3d">Экспортные цены</h3><div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0">'
            if price_no_vat:
                export_html += f'<span style="background:#fff;border:1px solid #ddd;padding:6px 12px;border-radius:6px;font-size:.85rem"><b>{price_no_vat}</b> \u20BD <small style="color:#767676">без НДС</small></span>'
            for cur, val in ep.items():
                if val:
                    export_html += f'<span style="background:#fff;border:1px solid #ddd;padding:6px 12px;border-radius:6px;font-size:.85rem"><b>{val}</b> {SYMS.get(cur, cur)}</span>'
            export_html += "</div>"

        weight = p.get("weight", "")
        weight_suffix = "" if (" г" in weight or " кг" in weight) else " кг"
        pr = float(price_rub) if price_rub else 0
        name = " ".join(str(p["name"] or "").split())  # collapse newlines/spaces for meta
        section = p.get("section", "")

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
<meta http-equiv="content-language" content="ru">
<title>{name} — Казанские Деликатесы | Халяль</title>
<meta name="description" content="{name}. {p.get('category','')}. Халяль продукция от Казанских Деликатесов. {('Вес: ' + weight + '. ') if weight else ''} Цена: {price_rub} ₽. {(p.get('shelfLife','') and 'Срок годности: ' + p['shelfLife'] + '.') or ''}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://api.pepperoni.tatar/products/{slug}">
<meta property="og:type" content="product">
<meta property="og:title" content="{name} — Казанские Деликатесы">
<meta property="og:description" content="{p.get('category','')}. {price_rub} ₽. Халяль.">
<meta property="og:url" content="https://api.pepperoni.tatar/products/{slug}">
<meta property="og:locale" content="ru_RU">
<link rel="alternate" hreflang="ru" href="https://api.pepperoni.tatar/products/{slug}">
<link rel="alternate" hreflang="en" href="https://api.pepperoni.tatar/en/products/{slug}">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"Главная","item":"https://api.pepperoni.tatar/"}},{{"@type":"ListItem","position":2,"name":"Каталог","item":"https://api.pepperoni.tatar/"}},{{"@type":"ListItem","position":3,"name":"{html_esc(name)}","item":"https://api.pepperoni.tatar/products/{slug}"}}]}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Product","name":"{html_esc(name)}","sku":"{p['sku']}","brand":{{"@type":"Brand","name":"Казанские Деликатесы"}},"offers":{{"@type":"Offer","priceCurrency":"RUB","price":"{price_rub}","availability":"https://schema.org/InStock"}},"manufacturer":{{"@type":"Organization","name":"Казанские Деликатесы","url":"https://kazandelikates.tatar"}}}}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.6}}
.container{{max-width:900px;margin:0 auto;padding:40px 24px}}
.badge{{display:inline-block;background:#1b7a3d;color:#fff;padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;letter-spacing:.5px}}
.detail-row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee;font-size:.9rem}}
.detail-row dt{{color:#767676}}
.detail-row dd{{color:#1a1a1a;font-weight:500}}
.cta-box{{background:#f0f7f0;border:2px solid #1b7a3d;border-radius:10px;padding:24px;margin-top:24px}}
.cta-box a{{display:inline-block;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0}}
.tg-order-btn,.wa-order-btn{{display:inline-flex;align-items:center;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;margin:4px 6px 4px 0;transition:background .2s}}
.tg-order-btn{{background:#2AABEE;color:#fff}}.tg-order-btn:hover{{background:#2298D6;color:#fff}}
.wa-order-btn{{background:#25D366;color:#fff}}.wa-order-btn:hover{{background:#20BD5A;color:#fff}}
footer{{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}}
footer a{{color:#444;text-decoration:none}}
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
<nav aria-label="breadcrumb" style="font-size:.85rem;color:#666;margin-bottom:16px">
  <ol itemscope itemtype="https://schema.org/BreadcrumbList" style="list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px">
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><a itemprop="item" href="https://api.pepperoni.tatar/"><span itemprop="name">Главная</span></a><meta itemprop="position" content="1"></li>
    <span aria-hidden="true"> › </span>
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><a itemprop="item" href="https://api.pepperoni.tatar/"><span itemprop="name">Каталог</span></a><meta itemprop="position" content="2"></li>
    <span aria-hidden="true"> › </span>
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem"><span itemprop="name">{html_esc(name)}</span><meta itemprop="position" content="3"></li>
  </ol>
</nav>
<h1 style="font-size:1.6rem;margin-bottom:8px">{name}</h1>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
<span class="badge">HALAL</span>
<span class="badge" style="background:#0066cc">{p['sku']}</span>
<span class="badge" style="background:#555">{section}</span>
</div>
'''
        fmt = f"{pr:,.2f}".replace(",", " ").replace(".", ",")
        html += f'<div style="font-size:2rem;font-weight:700;color:#1b7a3d;margin:16px 0">{fmt} ₽<span style="font-size:.85rem;color:#767676;font-weight:400">{" /шт" if is_bakery else " с НДС"}</span></div>\n'
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
        html += '<div style="margin:20px 0">\n'
        html += f'<dl class="detail-row"><dt>Категория</dt><dd>{p.get("category") or "—"}</dd></dl>\n'
        html += f'<dl class="detail-row"><dt>Вес расчёта</dt><dd>{(weight + weight_suffix) if weight else "—"}</dd></dl>\n'
        html += f'<dl class="detail-row"><dt>Срок годности</dt><dd>{p.get("shelfLife") or "—"}</dd></dl>\n'
        html += f'<dl class="detail-row"><dt>Хранение</dt><dd>{p.get("storage") or "—"}</dd></dl>\n'
        html += f'<dl class="detail-row"><dt>ТН ВЭД</dt><dd>{p.get("hsCode") or "—"}</dd></dl>\n'
        html += '<dl class="detail-row"><dt>Сертификация</dt><dd>Halal</dd></dl>\n'
        html += '<dl class="detail-row"><dt>Производитель</dt><dd>Казанские Деликатесы</dd></dl>\n'
        html += "</div>\n"
        html += export_html
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
<footer>
<p><a href="/pepperoni">Пепперони</a> · <a href="/about">О компании</a> · <a href="/faq">FAQ</a> · <a href="/delivery">Доставка</a> · <a href="https://api.pepperoni.tatar/">Для дистрибьюторов (API)</a></p>
<p>© <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
<script>
document.addEventListener("click",function(e){{
  var link=e.target.closest("a");if(!link)return;
  var href=link.getAttribute("href")||"";
  if(href.indexOf("tel:")===0){{typeof ym==="function"&&ym(107064141,"reachGoal","click_phone")}}
  if(href.indexOf("mailto:")===0){{typeof ym==="function"&&ym(107064141,"reachGoal","click_email")}}
  if(href.indexOf("kazandelikates.tatar")!==-1){{typeof ym==="function"&&ym(107064141,"reachGoal","go_to_main_site")}}
}});
</script>
</body>
</html>'''
        path = os.path.join(OUT, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"Generated {len(products)} RU product pages in {OUT}/")


if __name__ == "__main__":
    main()
