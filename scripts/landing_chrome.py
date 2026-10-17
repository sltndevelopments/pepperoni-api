"""Shared jerky/investors chrome for commercial landings.

Used by content_plan_pages.shell(), commercial_page.page(),
gen_category_pages.py and apply_landing_shell.py so future pages inherit
the same topbar + stylesheet without rewriting article text.
"""
from __future__ import annotations

import hashlib
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
CSS_HREF = "/assets/kd-landing.css"
CSS_START = "<!-- kd-landing-css:start -->"
CSS_END = "<!-- kd-landing-css:end -->"
LCP_FONT_HREF = "/fonts/f0.woff2"
LCP_FONT_SLUGS = {
    "sosiski-dlya-hotdog",
    "kotlety-dlya-burgerov",
    "sosiski-halyal-optom",
}
LCP_RENDER_SLUGS = LCP_FONT_SLUGS

# Enough to paint the hero H1 on first frame. Full kd-landing.css is deferred.
HERO_CRITICAL_CSS = (
    "html,body{margin:0}"
    "body.kd-landing{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\","
    "Roboto,sans-serif;color:#111614;background:#fbfbfd;line-height:1.65}"
    "body.kd-landing .container{max-width:1120px;margin:0 auto;padding:28px 24px 72px}"
    "body.kd-landing h1{font-size:clamp(1.85rem,4.2vw,2.9rem);font-weight:800;"
    "line-height:1.2;letter-spacing:-.02em;margin:8px 0 16px;color:#111614}"
    "body.kd-landing p{margin-bottom:14px;color:#111614}"
    "body.kd-landing .hero-subtitle,body.kd-landing .lede,"
    "body.kd-landing .eyebrow,body.kd-landing .hero__sub{"
    "color:#5c6660;font-size:1.05rem;max-width:70ch;line-height:1.65}"
    "body.kd-landing .hero{padding:12px 0 28px}"
    "body.kd-landing .hero__grid{display:grid;grid-template-columns:1.08fr .92fr;"
    "gap:0 40px;align-items:start;grid-template-areas:\"copy media\" \"actions media\"}"
    "body.kd-landing .hero__copy{grid-area:copy}"
    "body.kd-landing .hero__media{grid-area:media;align-self:center;position:relative}"
    "body.kd-landing .hero__actions{grid-area:actions}"
    "body.kd-landing nav:not(.kd-topnav):not(.site-links):not(.kd-langs){"
    "font-size:.8rem;color:#5c6660;margin-bottom:20px;line-height:1.65}"
    "body.kd-landing nav:not(.kd-topnav):not(.site-links) a{"
    "color:#5c6660;text-decoration:none}"
    "body.kd-landing .hero,body.kd-landing .hero__copy,body.kd-landing .hero h1,"
    "body.kd-landing h1,body.kd-landing .hero-subtitle,body.kd-landing .hero__sub{"
    "opacity:1;transform:none;animation:none;transition:none}"
    ".kd-topbar{position:sticky;top:0;z-index:50;min-height:56px;"
    "background:#fbfbfd;border-bottom:1px solid #e6e4df}"
    ".kd-topbar__in{display:flex;align-items:center;gap:14px;max-width:1120px;"
    "margin:0 auto;padding:0 20px;min-height:58px}"
    ".kd-brand{font-weight:800;color:#111614;text-decoration:none;white-space:nowrap}"
    ".kd-brand span{color:#16723c}"
    ".kd-navwrap{display:none}"
    ".kd-navtoggle{list-style:none}"
    ".kd-navtoggle::-webkit-details-marker{display:none}"
    ".kd-topnav{display:flex;gap:16px;font-size:.88rem;flex-wrap:wrap}"
    ".kd-topnav a{color:#5c6660;text-decoration:none}"
    ".kd-topbar__spacer{flex:1}"
    ".kd-topphone{font-weight:700;color:#111614;text-decoration:none;"
    "white-space:nowrap;font-size:.92rem}"
    ".kd-langs summary{list-style:none;cursor:pointer;font-size:.86rem;"
    "padding:6px 10px;border:1px solid #e6e4df;border-radius:99px;"
    "display:flex;align-items:center;background:#fff}"
    ".kd-langs summary::-webkit-details-marker{display:none}"
    ".kd-btn{display:inline-flex;align-items:center;padding:9px 15px;"
    "border-radius:99px;font-weight:650;font-size:.88rem;text-decoration:none}"
    ".kd-btn--primary{background:#111614;color:#fff}"
    "@media(max-width:900px){.kd-topnav--wide{display:none}"
    ".kd-navwrap{display:block}"
    "body.kd-landing .hero__grid{grid-template-columns:1fr;"
    "grid-template-areas:\"copy\" \"media\" \"actions\";gap:22px}}"
    "@media(max-width:560px){.kd-topphone{display:none}"
    "body.kd-landing h1{font-size:1.7rem}"
    "body.kd-landing .container{padding:20px 16px 88px}}"
    "body.kd-landing .badge{display:inline-block;background:#16723c;color:#fff;"
    "padding:4px 12px;border-radius:4px;font-size:.85rem;font-weight:600;"
    "margin:6px 4px 20px 0}"
    "body.kd-landing .hero__media picture{display:contents}"
    "body.kd-landing .hero__media img{"
    "display:block;width:100%;height:auto;aspect-ratio:640/427}"
)

# Tiny Metrika queue + init in <head>. tag.js still loads after `load` so
# early reachGoal calls (micro_form_start, lead submit) push onto ym.a
# after init. Do not load mc.yandex.ru from this snippet.
YM_INIT = (
    "ym(107064141,'init',{clickmap:true,trackLinks:true,"
    "accurateTrackBounce:true,ecommerce:'dataLayer'});"
)
YM_QUEUE_STUB = (
    "<script>"
    "window.ym=window.ym||function(){(ym.a=ym.a||[]).push(arguments)};"
    "ym.l=+new Date;"
    f"{YM_INIT}"
    "</script>"
)

# Same contract as gen-index.py `/`: GTM/Metrika stay out of <head>, arm after
# `load`, and still fire on a bounce (idle *or* a 1.5s timeout, not only on
# interaction). JSON-LD is never part of this snippet — it stays static HTML.
DELAYED_ANALYTICS = """<script>
function loadAnalytics(){
  if(window.__analyticsLoaded)return;window.__analyticsLoaded=true;
  (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);})(window,document,'script','dataLayer','GTM-W2Q5S8HF');
  (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r)return}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);})(window,document,'script','https://mc.yandex.ru/metrika/tag.js','ym');
}
function armAnalytics(){
  var idle=window.requestIdleCallback||function(cb){return setTimeout(cb,1);};
  idle(loadAnalytics,{timeout:1500});
  setTimeout(loadAnalytics,1500);
  ['scroll','keydown','touchstart','click','pointerdown'].forEach(function(ev){window.addEventListener(ev,loadAnalytics,{passive:true,once:true});});
}
if(document.readyState==='complete')armAnalytics();
else window.addEventListener('load',armAnalytics);
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/107064141" style="position:absolute;left:-9999px" alt="" width="1" height="1" loading="lazy"/></div></noscript>
"""
TOP_START = "<!-- kd-landing-topbar:start -->"
TOP_END = "<!-- kd-landing-topbar:end -->"

# Rel paths under public/ that this design system owns.
LANDINGS: list[tuple[str, str, str]] = [
    ("chak-chak-optom.html", "ru", "chak-chak-optom"),
    ("en/chak-chak-optom.html", "en", "chak-chak-optom"),
    ("halyal-vypechka-optom-dlya-pekaren.html", "ru", "halyal-vypechka-optom-dlya-pekaren"),
    ("en/halyal-vypechka-optom-dlya-pekaren.html", "en", "halyal-vypechka-optom-dlya-pekaren"),
    ("dlya-setey.html", "ru", "dlya-setey"),
    ("en/dlya-setey.html", "en", "dlya-setey"),
    ("dlya-distributorov.html", "ru", "dlya-distributorov"),
    ("en/dlya-distributorov.html", "en", "dlya-distributorov"),
    ("dlya-horeca.html", "ru", "dlya-horeca"),
    ("en/dlya-horeca.html", "en", "dlya-horeca"),
    ("sosiski-dlya-hotdog.html", "ru", "sosiski-dlya-hotdog"),
    ("en/sosiski-dlya-hotdog.html", "en", "sosiski-dlya-hotdog"),
    ("sosiski-halyal-optom.html", "ru", "sosiski-halyal-optom"),
    ("zamorozhennaya-vypechka-dlya-kofeen.html", "ru", "zamorozhennaya-vypechka-dlya-kofeen"),
    ("en/zamorozhennaya-vypechka-dlya-kofeen.html", "en", "zamorozhennaya-vypechka-dlya-kofeen"),
    ("export/uzbekistan.html", "ru", "export/uzbekistan"),
    ("en/export/uzbekistan.html", "en", "export/uzbekistan"),
    ("price.html", "ru", "price"),
    ("en/price.html", "en", "price"),
    ("kak-zakazat.html", "ru", "kak-zakazat"),
    ("en/kak-zakazat.html", "en", "kak-zakazat"),
    ("halal.html", "ru", "halal"),
    ("en/halal.html", "en", "halal"),
]


def is_lcp_render_slug(slug: str) -> bool:
    return slug in LCP_RENDER_SLUGS


def ym_queue_stub() -> str:
    """Head-only Metrika queue + init. Does not fetch tag.js."""
    return YM_QUEUE_STUB


def delayed_analytics() -> str:
    """GTM + Metrika after `load`, with a 1.5s timeout so bounces still count."""
    return DELAYED_ANALYTICS


def stylesheet_link(slug: str = "") -> str:
    """Blocking sheet by default; LCP hubs inline hero CSS and defer the rest."""
    if slug in LCP_RENDER_SLUGS:
        return (
            f"{CSS_START}"
            f'<style id="kd-hero-critical">{HERO_CRITICAL_CSS}</style>'
            f'<link rel="stylesheet" href="{CSS_HREF}" media="print" '
            f"onload=\"this.media='all'\">"
            f'<noscript><link rel="stylesheet" href="{CSS_HREF}"></noscript>'
            f"{CSS_END}"
        )
    return f'{CSS_START}<link rel="stylesheet" href="{CSS_HREF}">{CSS_END}'


def font_lcp_hints(slug: str = "") -> str:
    """@font-face with font-display:swap. No preload — it raced LCP on the hubs."""
    if slug and slug not in LCP_FONT_SLUGS:
        return ""
    return (
        '<!-- kd-font-lcp:start -->'
        "<style>"
        "@font-face{font-family:Nunito;font-style:normal;font-weight:500 800;"
        "font-display:swap;src:url(/fonts/f0.woff2) format(\"woff2\");"
        "unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}"
        "body.kd-landing,body.kd-landing h1{"
        "font-family:Nunito,-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif}"
        "</style>"
        "<!-- kd-font-lcp:end -->"
    )


def lead_form_src() -> str:
    data = (PUBLIC / "assets" / "lead-form.js").read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:8]
    return f"/assets/lead-form.js?v={digest}"


def lazy_lead_form_script() -> str:
    """Inline loader. Does not start lead-form.js or conversion_async.js on parse."""
    js = (Path(__file__).resolve().parent / "lead_form_lazy.js").read_text(encoding="utf-8")
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    js = re.sub(r"\s+", " ", js).strip()
    src = lead_form_src()
    return (
        f'<script id="kd-lead-form-lazy" data-src="{src}">{js}</script>'
        f'<noscript><p>Форма отправляет заявку на /lead-submit.</p></noscript>'
    )


def lead_form_tag(slug: str) -> str:
    """Defer the handler everywhere except the four LCP hubs."""
    if slug in LCP_RENDER_SLUGS:
        return lazy_lead_form_script()
    return f'<script src="{lead_form_src()}" defer></script>'


def _home(lang: str) -> str:
    return "/" if lang == "ru" else "/en/"


def _href(lang: str, slug: str) -> str:
    slug = slug.lstrip("/")
    return f"/{slug}" if lang == "ru" else f"/en/{slug}"


def topbar_html(lang: str, slug: str, *, cta_href: str | None = None,
                bilingual: bool = True) -> str:
    home = _home(lang)
    here = _href(lang, slug)
    alt_lang = "en" if lang == "ru" else "ru"
    alt_href = _href(alt_lang, slug)
    if lang == "ru":
        links = [
            (home, "Каталог"),
            ("/kontraktnoe-proizvodstvo", "OEM"),
            ("/price", "Прайс"),
            ("/kak-zakazat", "Как заказать"),
            ("/delivery", "Доставка"),
            ("/about", "О компании"),
        ]
        lang_label = "Русский"
        alt_label = "English"
        cta = "Заявка"
        cta_href = cta_href or "/kak-zakazat"
        phone_label = "+7 987 217-02-02"
        nav_label = "Разделы"
        menu_label = "Меню"
    else:
        links = [
            (home, "Catalog"),
            ("/en/private-label", "Private Label"),
            ("/en/price", "Price list"),
            ("/en/kak-zakazat", "How to order"),
            ("/en/delivery", "Delivery"),
            ("/en/about", "About"),
        ]
        lang_label = "English"
        alt_label = "Русский"
        cta = "Enquire"
        cta_href = cta_href or "/en/kak-zakazat"
        phone_label = "+7 987 217-02-02"
        nav_label = "Sections"
        menu_label = "Menu"
    nav = "".join(
        f'<a href="{escape(href)}"'
        + (' aria-current="page"' if href == here else "")
        + f">{escape(label)}</a>"
        for href, label in links
    )
    langs = ""
    if bilingual:
        langs = (
            f'  <details class="kd-langs"><summary aria-label="Language">'
            f'<span aria-hidden="true">🌐</span> {lang_label}</summary>\n'
            f'    <div class="kd-langs__menu"><a href="{escape(here)}" aria-current="page">'
            f'{lang_label}</a><a href="{escape(alt_href)}">{alt_label}</a></div>\n'
            f'  </details>\n'
        )
    inner = (
        f'<header class="kd-topbar"><div class="kd-topbar__in">\n'
        f'  <a class="kd-brand" href="{home}">Kazan <span>Delicacies</span></a>\n'
        f'  <nav class="kd-topnav kd-topnav--wide" aria-label="{nav_label}">{nav}</nav>\n'
        f'  <details class="kd-navwrap">\n'
        f'    <summary class="kd-navtoggle">{escape(menu_label)}</summary>\n'
        f'    <nav class="kd-topnav" aria-label="{nav_label}">{nav}</nav>\n'
        f'  </details>\n'
        f'  <div class="kd-topbar__spacer"></div>\n'
        f'  <a class="kd-topphone" href="tel:+79872170202">{phone_label}</a>\n'
        f'{langs}'
        f'  <a class="kd-btn kd-btn--primary" href="{escape(cta_href)}">{cta}</a>\n'
        f'</div></header>'
    )
    return f"{TOP_START}\n{inner}\n{TOP_END}"


_BODY_RE = re.compile(r"(<body\b)([^>]*)(>)", re.I)
_CLASS_DQ = re.compile(r'\bclass="([^"]*)"', re.I)
_CLASS_SQ = re.compile(r"\bclass='([^']*)'", re.I)
_MARKED_CSS = re.compile(
    re.escape(CSS_START) + r".*?" + re.escape(CSS_END), re.S
)
_MARKED_TOP = re.compile(
    re.escape(TOP_START) + r".*?" + re.escape(TOP_END), re.S
)


def _with_body_class(html: str) -> str:
    def repl(m: re.Match[str]) -> str:
        attrs = m.group(2)
        if re.search(r"\bkd-landing\b", attrs):
            return m.group(0)
        if _CLASS_DQ.search(attrs):
            attrs = _CLASS_DQ.sub(lambda x: f'class="kd-landing {x.group(1).strip()}"', attrs, count=1)
        elif _CLASS_SQ.search(attrs):
            attrs = _CLASS_SQ.sub(lambda x: f"class='kd-landing {x.group(1).strip()}'", attrs, count=1)
        else:
            attrs = attrs + ' class="kd-landing"'
        return f"{m.group(1)}{attrs}{m.group(3)}"

    out, n = _BODY_RE.subn(repl, html, count=1)
    if n != 1:
        raise SystemExit("landing_chrome: <body> not found")
    return out


def apply_chrome(html: str, lang: str, slug: str) -> str:
    """Idempotent: add stylesheet, body class and topbar. Does not rewrite article."""
    link = stylesheet_link()
    top = topbar_html(lang, slug)
    if _MARKED_CSS.search(html):
        html = _MARKED_CSS.sub(link, html)
    else:
        if "</head>" not in html.lower():
            raise SystemExit("landing_chrome: </head> missing")
        html = re.sub(
            r"</head>",
            link + "\n</head>",
            html,
            count=1,
            flags=re.I,
        )
    html = _with_body_class(html)
    if _MARKED_TOP.search(html):
        html = _MARKED_TOP.sub(top, html)
    else:
        gtm = re.search(
            r"(<!-- Google Tag Manager \(noscript\) -->.*?</noscript>\s*"
            r"<!-- End Google Tag Manager \(noscript\) -->)",
            html,
            re.S | re.I,
        )
        if gtm:
            insert_at = gtm.end()
            html = html[:insert_at] + "\n" + top + html[insert_at:]
        else:
            m = _BODY_RE.search(html)
            if not m:
                raise SystemExit("landing_chrome: cannot place topbar")
            html = html[: m.end()] + "\n" + top + html[m.end():]
    return html


def apply_file(rel: str, lang: str, slug: str) -> bool:
    path = PUBLIC / rel
    before = path.read_text(encoding="utf-8")
    after = apply_chrome(before, lang, slug)
    if after == before:
        return False
    path.write_text(after, encoding="utf-8")
    return True
