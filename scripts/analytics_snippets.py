#!/usr/bin/env python3
"""Single source for Yandex Metrika + GTM snippets (T01).

Direct Metrika code (counter 107064141) is the measurement source.
GTM-W2Q5S8HF does not contain Metrika — do not treat GTM as a substitute.
Injection is idempotent: never add a second ym(...,"init").
"""
from __future__ import annotations

import re

COUNTER = "107064141"
GTM_ID = "GTM-W2Q5S8HF"

METRIKA_SCRIPT = (
    '<script type="text/javascript">'
    "(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};"
    "m[i].l=1*new Date();"
    "for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return}"
    "k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,"
    "a.parentNode.insertBefore(k,a)})"
    '(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");'
    f'ym({COUNTER},"init",{{clickmap:true,trackLinks:true,accurateTrackBounce:true,ecommerce:"dataLayer"}});'
    "</script>"
)

METRIKA_NOSCRIPT = (
    f'<noscript><div><img src="https://mc.yandex.ru/watch/{COUNTER}" '
    'style="position:absolute;left:-9999px" alt="" /></div></noscript>'
)

METRIKA_BLOCK = (
    "<!-- Yandex.Metrika counter -->\n"
    f"{METRIKA_SCRIPT}\n"
    f"{METRIKA_NOSCRIPT}\n"
    "<!-- /Yandex.Metrika counter -->"
)

GTM_HEAD = f"""<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{GTM_ID}');</script>
<!-- End Google Tag Manager -->"""

GTM_BODY = f"""<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

INIT_RE = re.compile(
    rf"""ym\(\s*(?:{COUNTER}|['\"]{COUNTER}['\"])\s*,\s*['\"]init['\"]""",
    re.I,
)
WATCH_RE = re.compile(rf"mc\.yandex\.ru/watch/{COUNTER}")
GTM_RE = re.compile(re.escape(GTM_ID))
BODY_OPEN_RE = re.compile(r"<body[^>]*>", re.I)


def count_metrika_inits(html: str) -> int:
    return len(INIT_RE.findall(html or ""))


def has_metrika(html: str) -> bool:
    return count_metrika_inits(html) >= 1


def has_gtm(html: str) -> bool:
    return bool(GTM_RE.search(html or ""))


def inject_metrika(html: str) -> tuple[str, bool]:
    """Insert one Metrika init before </body>. No-op if init already present."""
    if not html or has_metrika(html):
        return html, False
    if re.search(r"</body>", html, re.I):
        return re.sub(r"</body>", METRIKA_BLOCK + "\n</body>", html, count=1, flags=re.I), True
    return html + "\n" + METRIKA_BLOCK + "\n", True


def inject_gtm(html: str) -> tuple[str, bool]:
    """Insert GTM head + noscript. No-op if container id already present."""
    if not html or has_gtm(html):
        return html, False
    changed = False
    if re.search(r"<head[^>]*>", html, re.I):
        html = re.sub(r"<head[^>]*>", lambda m: m.group(0) + "\n" + GTM_HEAD, html, count=1, flags=re.I)
        changed = True
    m = BODY_OPEN_RE.search(html)
    if m:
        html = html[: m.end()] + "\n" + GTM_BODY + html[m.end() :]
        changed = True
    return html, changed
