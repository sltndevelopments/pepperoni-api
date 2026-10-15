"""Shared HTML shell for commercial trust pages (/price, /kak-zakazat)."""
from __future__ import annotations

from html import escape

from organization_ld import SCRIPT

GTM_HEAD = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>
<!-- End Google Tag Manager -->"""

GTM_BODY = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1a1a1a;line-height:1.7}
.container{max-width:1040px;margin:0 auto;padding:40px 24px}
nav.crumb{font-size:.85rem;color:#888;margin-bottom:24px}
nav.crumb a{color:#0066cc;text-decoration:none}
h1{font-size:2rem;font-weight:700;margin-bottom:16px}
h2{font-size:1.25rem;font-weight:700;margin:28px 0 12px;color:#1b7a3d}
p,li{margin-bottom:10px}
ol,ul{padding-left:1.3rem;margin-bottom:16px}
.card{background:#fff;border:1px solid #e5e5e5;border-radius:10px;padding:20px;margin:16px 0}
.dl{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.dl a{display:inline-block;background:#1b7a3d;color:#fff;padding:10px 16px;border-radius:8px;font-weight:600;text-decoration:none}
.dl a.ghost{background:#fff;color:#1b7a3d;border:1px solid #1b7a3d}
table{width:100%;border-collapse:collapse;margin:12px 0 24px;background:#fff;font-size:.88rem}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #eee;vertical-align:top}
th{background:#f5f5f5;font-weight:600}
.num{white-space:nowrap;font-variant-numeric:tabular-nums}
.note{font-size:.9rem;color:#555}
footer{text-align:center;color:#888;font-size:.85rem;padding-top:32px;margin-top:32px;border-top:1px solid #eee}
footer a{color:#555;text-decoration:none}
.topnav{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #eee;font-size:.9rem}
.topnav a{color:#0066cc;text-decoration:none}
.topnav .here{color:#1b7a3d;font-weight:600}
.faq details{border:1px solid #e5e5e5;border-radius:8px;padding:10px 14px;margin:0 0 8px;background:#fff}
.faq summary{font-weight:600;cursor:pointer}
@media print{
  .topnav,nav.topnav,.dl a.ghost,footer .print-hide{display:none}
  body{background:#fff}
  table{font-size:10px}
  a{color:#000;text-decoration:none}
}
"""


def page(
    *,
    lang: str,
    title: str,
    description: str,
    canonical: str,
    hreflang_ru: str,
    hreflang_en: str,
    nav_html: str,
    body: str,
    extra_head: str = "",
    robots: str = "index, follow",
) -> str:
    locale = "ru_RU" if lang == "ru" else "en_US"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
{GTM_HEAD}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<meta http-equiv="content-language" content="{lang}">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<meta name="robots" content="{escape(robots)}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="ru" href="{hreflang_ru}">
<link rel="alternate" hreflang="en" href="{hreflang_en}">
<link rel="alternate" hreflang="x-default" href="{hreflang_ru}">
<meta property="og:type" content="website">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:locale" content="{locale}">
{SCRIPT}
{extra_head}
<style>{CSS}</style>
</head>
<body>
{GTM_BODY}
<div class="container">
{nav_html}
{body}
<footer>
<p class="print-hide"><a href="/{'en/' if lang == 'en' else ''}">← {'Catalog' if lang == 'en' else 'Каталог'}</a></p>
</footer>
</div>
</body>
</html>
"""
