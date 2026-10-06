#!/usr/bin/env python3
"""One Yandex Metrika counter for pepperoni.tatar pages.

Direct snippet, same init as the product-card generators. Pages that already
call ym(107064141, "init") are left untouched so the counter is not doubled.
GTM is added only when the container id is absent: the container does not
load this counter.
"""
from __future__ import annotations

import re

COUNTER = "107064141"
GTM_ID = "GTM-W2Q5S8HF"

YM_BLOCK = (
    '<script type="text/javascript">'
    '(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};'
    'm[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return}'
    'k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})'
    '(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
    'ym(107064141,"init",{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:"dataLayer"});'
    '</script>\n'
    '<noscript><div><img src="https://mc.yandex.ru/watch/107064141" '
    'style="position:absolute;left:-9999px" alt="" /></div></noscript>'
)

GTM_HEAD = (
    "<!-- Google Tag Manager -->\n"
    "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':\n"
    "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],\n"
    "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=\n"
    "'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);\n"
    "})(window,document,'script','dataLayer','GTM-W2Q5S8HF');</script>\n"
    "<!-- End Google Tag Manager -->"
)

GTM_BODY = (
    "<!-- Google Tag Manager (noscript) -->\n"
    '<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-W2Q5S8HF"\n'
    'height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>\n'
    "<!-- End Google Tag Manager (noscript) -->"
)

INIT_RE = re.compile(r"""ym\(\s*107064141\s*,\s*['"]init['"]""")


def init_count(html: str) -> int:
    return len(INIT_RE.findall(html))


def ensure_metrika_html(html: str, *, with_gtm: bool = True) -> str:
    if with_gtm and GTM_ID not in html:
        head = html.lower().rfind("</head>")
        if head != -1:
            html = html[:head] + GTM_HEAD + "\n" + html[head:]
        body = re.search(r"<body[^>]*>", html, re.I)
        if body:
            html = html[: body.end()] + "\n" + GTM_BODY + html[body.end() :]
    if init_count(html) == 0:
        idx = html.lower().rfind("</body>")
        if idx == -1:
            html = html + "\n" + YM_BLOCK + "\n"
        else:
            html = html[:idx] + YM_BLOCK + "\n" + html[idx:]
    return html
