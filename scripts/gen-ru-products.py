#!/usr/bin/env python3
"""Generate RU product pages from API. Run when node is unavailable."""
import json
import os
import urllib.parse
import urllib.request

API = "https://pepperoni.tatar/api/products"
OUT = "public/products"
SYMS = {"USD": "$", "KZT": "₸", "UZS": "UZS", "KGS": "KGS", "BYN": "BYN", "AZN": "AZN"}


def html_esc(s):
    return str(s or "").replace("\\", "\\\\").replace('"', '\\"')


def main():
    os.makedirs(OUT, exist_ok=True)
    with urllib.request.urlopen(API, timeout=30) as r:
        data = json.load(r)
    products = data.get("products", [])
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
        if ep:
            export_html = '<h3 style="margin-top:20px;font-size:1rem;color:#1b7a3d">Экспортные цены</h3><div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0">'
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
footer{{text-align:center;color:#555;font-size:.85rem;padding-top:24px;margin-top:32px}}
footer a{{color:#444;text-decoration:none}}
</style>
<!-- Yandex.Metrika counter -->
<script type="text/javascript">(function(m,e,t,r,i,k,a){{m[i]=m[i]||function(){{(m[i].a=m[i].a||[]).push(arguments)}};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){{if(document.scripts[j].src===r)return}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)}})(window,document,"script","https://mc.yandex.ru/metrika/tag.js?id=107064141","ym");ym(107064141,"init",{{ssr:true,clickmap:true,accurateTrackBounce:true,trackLinks:true}});</script>
<noscript><div><img src="https://mc.yandex.ru/watch/107064141" style="position:absolute;left:-9999px" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
</head>
<body>
<div class="container">
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem">
<a href="/" style="color:#0066cc;text-decoration:none">Каталог</a>
<a href="/pepperoni" style="color:#0066cc;text-decoration:none">Пепперони</a>
<a href="/about" style="color:#0066cc;text-decoration:none">О компании</a>
<a href="/delivery" style="color:#0066cc;text-decoration:none">Доставка</a>
<a href="/en/products/{slug}" style="color:#595959;text-decoration:none;margin-left:auto">🇬🇧 English</a>
</div>
<a href="/" style="display:inline-block;margin-bottom:24px;color:#0066cc;text-decoration:none;font-size:.9rem">← Каталог</a>
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
        html += '<div style="margin:20px 0">\n'
        if p.get("category"):
            html += f'<dl class="detail-row"><dt>Категория</dt><dd>{p["category"]}</dd></dl>\n'
        if weight:
            html += f'<dl class="detail-row"><dt>Вес расчёта</dt><dd>{weight}{weight_suffix}</dd></dl>\n'
        if price_no_vat:
            html += f'<dl class="detail-row"><dt>Цена без НДС</dt><dd>{price_no_vat} ₽</dd></dl>\n'
        if p.get("shelfLife"):
            html += f'<dl class="detail-row"><dt>Срок годности</dt><dd>{p["shelfLife"]}</dd></dl>\n'
        if p.get("storage"):
            html += f'<dl class="detail-row"><dt>Хранение</dt><dd>{p["storage"]}</dd></dl>\n'
        if p.get("hsCode"):
            html += f'<dl class="detail-row"><dt>ТН ВЭД</dt><dd>{p["hsCode"]}</dd></dl>\n'
        html += '<dl class="detail-row"><dt>Сертификация</dt><dd>Halal</dd></dl>\n'
        html += '<dl class="detail-row"><dt>Производитель</dt><dd>Казанские Деликатесы</dd></dl>\n'
        html += "</div>\n"
        html += export_html
        subj = urllib.parse.quote(f"Заказ: {name} ({p['sku']})", safe="")
        html += f'''<div class="cta-box">
<h3 style="margin:0 0 8px">Заказ</h3>
<p style="color:#444;margin-bottom:12px">Опт, экспорт, Private Label</p>
<a href="tel:+79872170202" style="background:#1b7a3d;color:#fff">📞 +7 987 217-02-02</a>
<a href="mailto:info@kazandelikates.tatar?subject={subj}" style="border:2px solid #1b7a3d;color:#1b7a3d">📧 Написать</a>
</div>
<footer>
<p><a href="/pepperoni">Пепперони</a> · <a href="/about">О компании</a> · <a href="/faq">FAQ</a> · <a href="/delivery">Доставка</a></p>
<p>© <a href="https://kazandelikates.tatar">Казанские Деликатесы</a> · <a href="https://pepperoni.tatar">pepperoni.tatar</a></p>
</footer>
</div>
</body>
</html>'''
        path = os.path.join(OUT, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"Generated {len(products)} RU product pages in {OUT}/")


if __name__ == "__main__":
    main()
