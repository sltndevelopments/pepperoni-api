#!/usr/bin/env python3
"""Generate the /pepperoni money hub as a Google Ads landing page, per locale.

One template, nine locales: RU at /pepperoni (the commercial canon) plus
en/kk/uz/az/hy/ka/ky/tg under their language prefix. Copy comes from
data/pepperoni_landing_i18n.json (RU+EN) merged with the per-language files
data/pepperoni_landing_i18n.<lang>.json; prices and photos come from
public/products.json so the landing can never drift from the Sheets catalogue.

    python3 scripts/gen_pepperoni_landing.py            # all locales
    python3 scripts/gen_pepperoni_landing.py ru kk      # only these

Run scripts/fix_pages.py + scripts/qa_pages.py afterwards, then rebuild the
sitemap. Tracking lives in public/assets/gmp-track.js, not here.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "public"
I18N_BASE = DATA / "pepperoni_landing_i18n.json"
SITE = "https://pepperoni.tatar"
SKU = "KD-013"
# The whole pepperoni family, so the landing keeps linking to the 1 kg stick and
# the horse-meat variant the way the previous /pepperoni hub did.
FAMILY_SKUS = ("KD-013", "KD-014", "KD-012")

GTM_ID = "GTM-W2Q5S8HF"
ADS_ID = "AW-18346189266"
YM_ID = "107064141"

# Consent Mode v2 stays denied by default in the EEA/UK/CH and granted in the
# markets we advertise in. None of the export targets are EEA, so measurement is
# complete there; EEA visitors fall back to Google's conversion modelling until a
# CMP is added. Ordering matters: region-scoped defaults must precede the global.
EEA_REGIONS = (
    "AT,BE,BG,HR,CY,CZ,DK,EE,FI,FR,DE,GR,HU,IE,IT,LV,LI,LT,LU,MT,NL,NO,PL,PT,"
    "RO,SK,SI,ES,SE,IS,GB,CH"
)

# The Cloudinary filenames predate the current photo set and do not describe what
# they show: "-main" is the vacuum pack, "-pack" is the sliced close-up and
# "-slice" is a finished pizza. Alt text follows the actual content, not the name.
IMG_PACK = "/images/products/kd-013-main.jpg"
IMG_SLICES = "/images/products/kd-013-pack.jpg"
IMG_PIZZA = "/images/products/kd-013-slice.jpg"

CURRENCY_SYMBOL = {
    "RUB": "\u20bd", "USD": "$", "KZT": "\u20b8", "AZN": "\u20bc",
    "UZS": "UZS", "KGS": "KGS", "BYN": "BYN",
}
# Locale → the country whose currency headlines that page.
LOCALE_COUNTRY = {
    "ru": "ru", "en": "int", "kk": "kz", "uz": "uz",
    "az": "az", "hy": "am", "ka": "ge", "ky": "kg", "tg": "tj",
}
# The phone hint is derived from the page's country, never from the translation:
# two locales came back with our own number in that field, and "+7 …" on the
# Georgian or Armenian page reads as "Russian numbers only".
COUNTRY_DIAL = {
    "ru": "+7", "kz": "+7", "uz": "+998", "kg": "+996", "by": "+375",
    "az": "+994", "am": "+374", "ge": "+995", "tj": "+992", "int": "+",
}
COUNTRY_ENDONYM = {
    "kz": "\u049aаза\u049bстан", "uz": "O\u2018zbekiston", "kg": "Кыргызстан",
    "by": "Беларусь", "az": "Az\u0259rbaycan", "am": "\u0540\u0561\u0575\u0561\u057d\u057f\u0561\u0576",
    "ge": "\u10e1\u10d0\u10e5\u10d0\u10e0\u10d7\u10d5\u10d4\u10da\u10dd", "tj": "То\u04b7икистон",
}


def load_i18n() -> dict:
    base = json.loads(I18N_BASE.read_text(encoding="utf-8"))
    for path in sorted(DATA.glob("pepperoni_landing_i18n.*.json")):
        for lang, block in json.loads(path.read_text(encoding="utf-8")).items():
            if lang.startswith("_"):
                continue
            base[lang] = block
    return base


def load_products() -> dict[str, dict]:
    catalog = json.loads((PUBLIC / "products.json").read_text(encoding="utf-8"))
    items = catalog["products"] if isinstance(catalog, dict) else catalog
    found = {i["sku"]: i for i in items if i.get("sku") in FAMILY_SKUS}
    missing = [s for s in FAMILY_SKUS if s not in found]
    if missing:
        raise SystemExit(f"missing in public/products.json: {', '.join(missing)}")
    return found


def money(amount: float, currency: str, lang: str) -> str:
    """Group thousands with a narrow no-break space; comma decimals outside EN.

    UZS is always whole (tens of thousands per pack) and round amounts drop the
    ",00" tail, so 274 ₽ stays 274 ₽ while 249,09 ₽ keeps its kopecks.
    """
    decimals = 0 if currency == "UZS" or float(amount).is_integer() else 2
    text = f"{amount:,.{decimals}f}".replace(",", "\u202f")
    if decimals:
        head, _, tail = text.rpartition(".")
        text = f"{head}{',' if lang != 'en' else '.'}{tail}"
    symbol = CURRENCY_SYMBOL[currency]
    if currency == "USD" and lang == "en":
        return f"{symbol}{text}"
    return f"{text}\u00a0{symbol}"


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def page_url(lang: str, locales: dict) -> str:
    return f"{SITE}/" + locales[lang]["path"].replace(".html", "")


# --------------------------------------------------------------------------- CSS
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --ink:#111614;--muted:#5c6660;--line:#e6e4df;--soft:#f7f6f2;
  --brand:#16723c;--brand-dark:#0f5a2d;--pep:#c4432b;--gold:#9d7434;
  --wa:#25d366;--radius:14px;
  --shadow:0 1px 2px rgba(17,22,20,.04),0 8px 24px rgba(17,22,20,.06);
}
html{scroll-behavior:smooth}
html,body{overflow-x:clip}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  color:var(--ink);background:#fff;line-height:1.65;-webkit-font-smoothing:antialiased}
img{max-width:100%;height:auto;display:block}
a{color:var(--brand-dark)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
.section{padding:56px 0;border-top:1px solid var(--line)}
.section--soft{background:var(--soft)}
.section:first-of-type{border-top:0}
h1,h2,h3{line-height:1.2;letter-spacing:-.01em}
h1{font-size:clamp(1.75rem,4.4vw,2.9rem);font-weight:800}
h2{font-size:clamp(1.35rem,2.8vw,2rem);font-weight:750;margin-bottom:10px}
h3{font-size:1.05rem;font-weight:700;margin-bottom:8px}
.lede{color:var(--muted);font-size:1.02rem;max-width:70ch}
.eyebrow{font-size:.78rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--brand)}

/* header */
.topbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.94);
  backdrop-filter:saturate(160%) blur(10px);border-bottom:1px solid var(--line)}
.topbar__in{display:flex;align-items:center;gap:14px;min-height:60px}
.brand{font-weight:800;letter-spacing:-.02em;text-decoration:none;color:var(--ink);font-size:.98rem;white-space:nowrap}
.brand span{color:var(--brand)}
.topbar__spacer{flex:1}
.topnav{display:flex;gap:16px;font-size:.88rem}
.topnav a{color:var(--muted);text-decoration:none}
.topnav a:hover{color:var(--brand)}
.topphone{font-weight:700;text-decoration:none;color:var(--ink);font-size:.92rem;white-space:nowrap}

/* language switcher */
.langs{position:relative}
.langs summary{list-style:none;cursor:pointer;font-size:.86rem;padding:6px 10px;border:1px solid var(--line);
  border-radius:99px;display:flex;align-items:center;gap:6px;white-space:nowrap;background:#fff}
.langs summary::-webkit-details-marker{display:none}
.langs__menu{position:absolute;right:0;top:calc(100% + 6px);background:#fff;border:1px solid var(--line);
  border-radius:12px;box-shadow:var(--shadow);padding:6px;min-width:190px;z-index:60}
.langs__menu a{display:block;padding:7px 10px;border-radius:8px;text-decoration:none;color:var(--ink);font-size:.88rem}
.langs__menu a:hover{background:var(--soft)}
.langs__menu a[aria-current]{background:var(--soft);font-weight:700}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:13px 22px;border-radius:10px;
  font-weight:650;font-size:.95rem;text-decoration:none;border:1.5px solid transparent;cursor:pointer;
  transition:transform .12s ease,background .15s ease}
.btn:active{transform:translateY(1px)}
.btn--primary{background:var(--brand);color:#fff}
.btn--primary:hover{background:var(--brand-dark)}
.btn--wa{background:var(--wa);color:#0b2f18}
.btn--wa:hover{filter:brightness(.95)}
.btn--ghost{background:#fff;border-color:var(--brand);color:var(--brand-dark)}
.btn--ghost:hover{background:var(--soft)}
.btn--sm{padding:9px 15px;font-size:.88rem}
.btn-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}

/* hero */
.hero{padding:44px 0 52px;background:
  radial-gradient(1100px 380px at 88% -10%,rgba(22,114,60,.09),transparent 62%),
  radial-gradient(700px 300px at 8% 0%,rgba(196,67,43,.07),transparent 60%)}
/* Three blocks instead of two columns so mobile can put the product photo
   between the headline and the CTAs — at 390x844 the photo was below the fold. */
.hero__grid{display:grid;grid-template-columns:1.08fr .92fr;gap:0 40px;align-items:start;
  grid-template-areas:"copy media" "actions media"}
.hero__copy{grid-area:copy}
.hero__media{grid-area:media;align-self:center}
.hero__actions{grid-area:actions}
.hero h1{margin:10px 0 14px}
.hero__sub{font-size:1.06rem;color:var(--muted);max-width:56ch}
.hero__note{margin-top:16px;font-size:.86rem;color:var(--muted);max-width:52ch}
.hero__media{position:relative}
.hero__media img{border-radius:var(--radius);box-shadow:var(--shadow)}
.hero__tag{position:absolute;left:14px;bottom:14px;background:rgba(255,255,255,.95);
  border:1px solid var(--line);border-radius:99px;padding:7px 14px;font-size:.82rem;font-weight:700}
.badges{display:flex;flex-wrap:wrap;gap:7px;margin-top:18px}
.badge{font-size:.76rem;font-weight:700;padding:5px 11px;border-radius:99px;
  background:#fff;border:1px solid var(--line);color:var(--muted)}
.badge--halal{background:var(--brand);border-color:var(--brand);color:#fff}

/* trust */
.trust{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.trust__i{background:#fff;padding:16px 18px}
.trust__l{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700}
.trust__v{font-weight:700;font-size:.96rem;margin-top:3px}

/* video */
.videos{display:grid;grid-template-columns:1.45fr .55fr;gap:22px;margin-top:26px;align-items:start}
.vid{background:#0d100e;border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
.vid__frame{position:relative;cursor:pointer;background:#0d100e;overflow:hidden}
.vid__frame[data-video-short="1"]{aspect-ratio:9/16}
.vid__frame:not([data-video-short="1"]){aspect-ratio:16/9}
/* Safari: % height inside aspect-ratio collapses the <img> to 0 without absolute fill. */
.vid__frame img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.86;
  transition:opacity .2s,transform .3s}
.vid__frame:hover img{opacity:1;transform:scale(1.02)}
.vid__frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.vid__play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none}
.vid__play span{width:62px;height:62px;border-radius:50%;background:rgba(255,255,255,.94);
  display:flex;align-items:center;justify-content:center;box-shadow:0 6px 22px rgba(0,0,0,.34)}
.vid__play svg{width:22px;height:22px;fill:var(--pep);margin-left:3px}
.vid__cap{padding:14px 16px;color:#fff}
.vid__cap b{display:block;font-size:.98rem}
.vid__cap p{font-size:.84rem;color:#b9c2bc;margin-top:3px}

/* generic cards */
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:26px}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:20px}
.card__ico{font-size:1.55rem;line-height:1;margin-bottom:10px}
.card p{color:var(--muted);font-size:.9rem}
.card--flat{box-shadow:none}

/* product */
.prod{display:grid;grid-template-columns:1fr 1fr;gap:34px;margin-top:26px;align-items:start}
.gallery{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.gallery figure{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.gallery figure:first-child{grid-column:1/-1}
.gallery figcaption{font-size:.78rem;color:var(--muted);padding:8px 10px;border-top:1px solid var(--line)}
table{width:100%;border-collapse:collapse}
th,td{padding:9px 12px;text-align:start;font-size:.9rem;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
td:last-child{font-weight:650}
.tbl{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.tbl + h3{margin-top:24px}
.note{font-size:.85rem;color:var(--muted);margin-top:10px}
.skufamily{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.skuchip{display:flex;flex-direction:column;gap:1px;text-decoration:none;color:inherit;background:#fff;
  border:1px solid var(--line);border-radius:10px;padding:10px 14px;transition:border-color .15s}
.skuchip:hover{border-color:var(--brand)}
.skuchip b{font-size:.84rem}
.skuchip span{font-size:.74rem;color:var(--muted)}
.skuchip em{font-style:normal;font-weight:750;font-size:.92rem;color:var(--brand-dark)}

/* price */
.pricebox{display:grid;grid-template-columns:.85fr 1.15fr;gap:26px;margin-top:26px;align-items:start}
.pricecard{background:var(--brand);color:#fff;border-radius:var(--radius);padding:24px;box-shadow:var(--shadow)}
.pricecard__amt{font-size:2.5rem;font-weight:800;letter-spacing:-.02em;line-height:1.05}
.pricecard__per{font-size:.86rem;opacity:.85;margin-top:4px}
.pricecard__excl{margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.24);font-size:.88rem;opacity:.92}
.pricecard .btn{margin-top:18px;width:100%;background:#fff;color:var(--brand-dark)}
.countries{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.ctry{display:block;text-decoration:none;color:inherit;background:#fff;border:1px solid var(--line);
  border-radius:12px;padding:13px 14px;transition:border-color .15s,box-shadow .15s}
.ctry:hover{border-color:var(--brand);box-shadow:var(--shadow)}
.ctry__f{font-size:1.3rem;line-height:1}
.ctry__n{font-size:.82rem;color:var(--muted);margin-top:6px}
.ctry__p{font-weight:750;font-size:.98rem;margin-top:2px}
.ctry[aria-current]{border-color:var(--brand);background:#f2f8f4}

/* steps */
.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:26px;counter-reset:s}
.step{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:18px}
.step__n{width:30px;height:30px;border-radius:50%;background:var(--brand);color:#fff;font-weight:750;
  display:flex;align-items:center;justify-content:center;font-size:.88rem;margin-bottom:10px}
.step p{font-size:.88rem;color:var(--muted)}
.checklist{list-style:none;margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:8px 22px}
.checklist li{position:relative;padding-inline-start:26px;font-size:.92rem}
.checklist li::before{content:"";position:absolute;inset-inline-start:2px;top:.55em;width:11px;height:6px;
  border-inline-start:2px solid var(--brand);border-bottom:2px solid var(--brand);transform:rotate(-45deg)}

/* faq */
.faq{margin-top:22px;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:#fff}
.faq details{border-bottom:1px solid var(--line)}
.faq details:last-child{border-bottom:0}
.faq summary{cursor:pointer;padding:15px 18px;font-weight:650;font-size:.95rem;list-style:none;
  display:flex;justify-content:space-between;gap:14px;align-items:center}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";color:var(--brand);font-weight:700;font-size:1.15rem;flex:none}
.faq details[open] summary::after{content:"\\2212"}
.faq p{padding:0 18px 16px;color:var(--muted);font-size:.92rem;max-width:80ch}

/* form */
.formgrid{display:grid;grid-template-columns:1.15fr .85fr;gap:30px;margin-top:26px;align-items:start}
.lead-form{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:22px;box-shadow:var(--shadow)}
.lead-form label{display:block;font-size:.82rem;font-weight:650;color:var(--muted);margin:14px 0 5px}
.lead-form label:first-of-type{margin-top:0}
.lead-form input[type=text],.lead-form input[type=tel],.lead-form textarea{
  width:100%;padding:11px 13px;border:1px solid var(--line);border-radius:9px;font:inherit;background:#fff}
.lead-form input:focus,.lead-form textarea:focus{outline:2px solid rgba(22,114,60,.35);border-color:var(--brand)}
.lead-form button{margin-top:18px;width:100%}
.consent{display:flex;gap:9px;align-items:flex-start;margin-top:14px;font-size:.8rem;color:var(--muted);font-weight:400}
.consent input{margin-top:3px;flex:none}
.lead-form__status{margin-top:10px;font-size:.85rem;color:var(--muted);min-height:1.2em}
.contactcard{background:var(--soft);border:1px solid var(--line);border-radius:var(--radius);padding:22px}
.contactcard dl{margin-top:12px}
.contactcard dt{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin-top:14px}
.contactcard dd{font-size:.96rem;font-weight:650;margin-top:2px}
.contactcard dd a{text-decoration:none}

/* footer */
footer{background:#0f1311;color:#c7cec9;padding:40px 0 92px;font-size:.88rem}
footer a{color:#e8ece9;text-decoration:none}
footer a:hover{text-decoration:underline}
.foot{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:26px}
.foot h4{font-size:.76rem;text-transform:uppercase;letter-spacing:.07em;color:#8d968f;margin-bottom:10px}
.foot ul{list-style:none;display:grid;gap:6px}
.foot__legal{margin-top:26px;padding-top:18px;border-top:1px solid #222925;color:#8d968f;font-size:.82rem}

/* sticky mobile bar */
.stickybar{display:none}
@media(max-width:1100px){
  /* Tall Shorts card next to a 16:9 frame overflows narrow Safari windows. */
  .videos{grid-template-columns:1fr}
  .videos .vid__frame[data-video-short="1"]{aspect-ratio:16/9}
}
@media(max-width:900px){
  .prod,.pricebox,.formgrid{grid-template-columns:1fr}
  .hero__grid{grid-template-columns:1fr;grid-template-areas:"copy" "media" "actions";gap:22px}
  .trust,.cards,.steps{grid-template-columns:repeat(2,1fr)}
  .countries{grid-template-columns:repeat(2,1fr)}
  .foot{grid-template-columns:1fr 1fr}
  .topnav{display:none}
}
@media(max-width:560px){
  .section{padding:40px 0}
  .trust,.cards,.steps,.checklist,.gallery{grid-template-columns:1fr}
  .gallery figure:first-child{grid-column:auto}
  .foot{grid-template-columns:1fr}
  .topphone{display:none}
  .stickybar{display:flex;position:fixed;inset-inline:0;bottom:0;z-index:70;gap:8px;padding:9px 12px;
    background:rgba(255,255,255,.97);border-top:1px solid var(--line);box-shadow:0 -4px 18px rgba(0,0,0,.09)}
  .stickybar .btn{flex:1;padding:12px 8px;font-size:.88rem}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""

PLAY_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'


def sku_price(item: dict, currency: str) -> float:
    """Price of any family SKU in the page's headline currency."""
    if currency == "RUB":
        return float(item["offers"]["price"])
    return float(item["offers"]["exportPrices"][currency])


def build_head(lang: str, L: dict, i18n: dict, family: dict[str, dict],
               price_amount: float, price_currency: str) -> str:
    product = family[SKU]
    locales = i18n["_locales"]
    facts = i18n["_facts"]
    meta, url = L["meta"], page_url(lang, locales)

    alternates = "\n  ".join(
        f'<link rel="alternate" hreflang="{code}" href="{page_url(code, locales)}">'
        for code in locales if code in i18n
    )
    alternates += f'\n  <link rel="alternate" hreflang="x-default" href="{page_url("en", locales)}">'

    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"],
             "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
            for item in L["faq"]["items"]
        ],
    }
    product_ld = {
        "@context": "https://schema.org", "@type": "Product",
        "name": L["product"]["name"], "sku": SKU,
        "gtin13": facts["barcode"],
        "description": meta["description"][:400],
        "image": [f"{SITE}{IMG_PACK}", f"{SITE}{IMG_SLICES}", f"{SITE}{IMG_PIZZA}"],
        "brand": {"@type": "Brand", "name": "Kazan Delicacies"},
        "manufacturer": {
            "@type": "Organization",
            "@id": f"{SITE}/#organization",
            "name": L["contacts"]["company"],
            "legalName": "ООО «Казанские Деликатесы»",
            "alternateName": ["Kazan Delicacies", "Kazan Delicacies LLC"],
            "url": SITE,
            "sameAs": [
                "https://www.wikidata.org/wiki/Q141108238",
                "https://kazandelikates.tatar",
                "https://www.youtube.com/@kazandelikates",
            ],
            "address": {"@type": "PostalAddress",
                        "streetAddress": "ul. Agrarnaya 2, office 7",
                        "addressLocality": "Kazan",
                        "addressRegion": "Tatarstan",
                        "postalCode": "420061",
                        "addressCountry": "RU"},
            "telephone": facts["phone_display"], "email": facts["email"],
        },
        "additionalProperty": [
            {"@type": "PropertyValue", "name": k, "value": v}
            for k, v in L["product"]["specs"]
        ],
        "offers": {
            "@type": "Offer", "url": url,
            "priceCurrency": price_currency, "price": f"{price_amount}",
            "availability": product["offers"]["availability"],
            "priceValidUntil": f"{date.today().year}-12-31",
            "seller": {"@type": "Organization", "name": L["contacts"]["company"]},
        },
    }
    breadcrumb_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": L["nav"]["catalog"], "item": SITE + ("" if lang == "ru" else f"/{lang}")},
            {"@type": "ListItem", "position": 2, "name": L["nav"]["current"], "item": url},
        ],
    }
    org_ld = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": f"{SITE}/#organization",
        "name": "Казанские Деликатесы",
        "legalName": "ООО «Казанские Деликатесы»",
        "alternateName": ["Kazan Delicacies", "Kazan Delicacies LLC"],
        "url": SITE,
        "logo": f"{SITE}/images/icon-180.png",
        "email": facts["email"],
        "telephone": facts["phone_display"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "ul. Agrarnaya 2, office 7",
            "addressLocality": "Kazan",
            "addressRegion": "Tatarstan",
            "postalCode": "420061",
            "addressCountry": "RU",
        },
        "sameAs": [
            "https://www.wikidata.org/wiki/Q141108238",
            "https://kazandelikates.tatar",
            "https://www.youtube.com/@kazandelikates",
        ],
        "description": (
            "Halal meat manufacturer in Kazan, Tatarstan. Catalog https://pepperoni.tatar, "
            "corporate https://kazandelikates.tatar. Not kazandelikates.ru "
            "(that hostname does not resolve and is not this company)."
        ),
    }
    itemlist_ld = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": L["product"]["h2"],
        "itemListElement": [
            {"@type": "ListItem", "position": n,
             "url": f"{SITE}/products/{sku.lower()}",
             "name": f"{sku} · {family[sku]['weight']} kg"}
            for n, sku in enumerate(FAMILY_SKUS, 1)
        ],
    }
    videos_ld = [
        {"@context": "https://schema.org", "@type": "VideoObject",
         "name": L["video"]["v1_title"], "description": L["video"]["v1_desc"],
         "thumbnailUrl": f"{SITE}/images/video/pepperoni-plant.jpg",
         "uploadDate": "2025-11-18",
         "embedUrl": f"https://www.youtube-nocookie.com/embed/{facts['video_plant']}",
         "contentUrl": f"https://youtu.be/{facts['video_plant']}"},
        {"@context": "https://schema.org", "@type": "VideoObject",
         "name": L["video"]["v2_title"], "description": L["video"]["v2_desc"],
         "thumbnailUrl": f"{SITE}/images/video/pepperoni-making.jpg",
         "uploadDate": "2026-02-10",
         "embedUrl": f"https://www.youtube-nocookie.com/embed/{facts['video_making']}",
         "contentUrl": f"https://youtube.com/shorts/{facts['video_making']}"},
    ]

    def ld(obj) -> str:
        return ('<script type="application/ld+json">'
                + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                + "</script>")

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googletagmanager.com">
<link rel="preconnect" href="https://www.googleadservices.com" crossorigin>
<link rel="dns-prefetch" href="https://www.googleadservices.com">

<!-- Consent Mode v2 — must precede every Google tag -->
<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied','analytics_storage':'denied','functionality_storage':'granted','security_storage':'granted','wait_for_update':500,'region':['{EEA_REGIONS.replace(",", "','")}']}});
gtag('consent','default',{{'ad_storage':'granted','ad_user_data':'granted','ad_personalization':'granted','analytics_storage':'granted','functionality_storage':'granted','security_storage':'granted'}});
gtag('set','ads_data_redaction',true);
gtag('set','url_passthrough',true);
</script>

<!-- Google tag (gtag.js) - Google Ads: {ADS_ID} -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ADS_ID}"></script>
<script>gtag('js',new Date());gtag('config','{ADS_ID}');</script>
<!-- Fallback conversion lib when googletagmanager.com DNS is blocked -->
<script async src="https://www.googleadservices.com/pagead/conversion_async.js"></script>

<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{GTM_ID}');</script>
<!-- End Google Tag Manager -->

<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<meta name="keywords" content="{esc(meta["keywords"])}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta http-equiv="content-language" content="{lang}">
<link rel="canonical" href="{url}">
  {alternates}

<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" sizes="180x180" href="/images/icon-180.png">
<link rel="manifest" href="/manifest.json">
<link rel="llms" href="/llms.txt" type="text/plain" title="LLM instructions">

<meta property="og:type" content="product">
<meta property="og:site_name" content="pepperoni.tatar">
<meta property="og:title" content="{esc(meta["og_title"])}">
<meta property="og:description" content="{esc(meta["og_description"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{IMG_PIZZA}">
<meta property="og:image:width" content="800">
<meta property="og:image:height" content="533">
<meta property="og:locale" content="{locales[lang]["og"]}">
<meta property="product:price:amount" content="{price_amount}">
<meta property="product:price:currency" content="{price_currency}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(meta["og_title"])}">
<meta name="twitter:description" content="{esc(meta["og_description"])}">
<meta name="twitter:image" content="{SITE}{IMG_PIZZA}">

<link rel="preload" as="image" href="{IMG_PIZZA}" fetchpriority="high">

{ld(org_ld)}
{ld(product_ld)}
{ld(itemlist_ld)}
{ld(breadcrumb_ld)}
{ld(faq_ld)}
{ld(videos_ld[0])}
{ld(videos_ld[1])}

<style>{CSS}</style>
</head>"""


def build_body(lang: str, L: dict, i18n: dict, family: dict[str, dict], prices: dict,
               price_amount: float, price_currency: str) -> str:
    locales, facts = i18n["_locales"], i18n["_facts"]
    wa_base = f"https://wa.me/{facts['whatsapp']}?text="
    wa_text = f"{L['hero']['cta_wa']} — {L['product']['name']} ({SKU})"
    from urllib.parse import quote
    wa = wa_base + quote(wa_text)
    tel = facts["phone_href"]
    phone = facts["phone_display"]
    email = facts["email"]
    country_of_page = LOCALE_COUNTRY[lang]
    prefix = "" if lang == "ru" else f"/{lang}"

    def local(path: str) -> str:
        """Link to the localised page when it exists, else the RU original."""
        return f"{prefix}{path}" if (PUBLIC / f"{lang}{path}.html").exists() or lang == "ru" else path

    lang_menu = ""
    for code in locales:
        if code not in i18n:
            continue
        current = ' aria-current="page"' if code == lang else ""
        lang_menu += (f'<a href="{page_url(code, locales)}"{current}>'
                      f'{locales[code]["name"]}</a>')

    trust = "".join(
        f'<div class="trust__i"><div class="trust__l">{esc(i["label"])}</div>'
        f'<div class="trust__v">{esc(i["value"])}</div></div>'
        for i in L["trust"]["items"]
    )

    def video_block(vid: str, poster: str, title: str, desc: str, short: bool) -> str:
        return (
            f'<div class="vid"><div class="vid__frame" data-video-id="{vid}" '
            f'data-video-title="{esc(title)}" data-video-short="{"1" if short else "0"}" '
            f'role="button" tabindex="0" aria-label="{esc(L["video"]["play"])}: {esc(title)}">'
            f'<img src="{poster}" alt="{esc(title)}" width="{"405" if short else "1280"}" '
            f'height="720" loading="lazy" decoding="async">'
            f'<span class="vid__play"><span>{PLAY_SVG}</span></span></div>'
            f'<div class="vid__cap"><b>{esc(title)}</b><p>{esc(desc)}</p></div></div>'
        )

    videos = (
        video_block(facts["video_plant"], "/images/video/pepperoni-plant.jpg",
                    L["video"]["v1_title"], L["video"]["v1_desc"], False)
        + video_block(facts["video_making"], "/images/video/pepperoni-making.jpg",
                      L["video"]["v2_title"], L["video"]["v2_desc"], True)
    )

    def rows(pairs) -> str:
        return "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in pairs)

    pizza_alt = f'{L["usage"]["items"][0]["title"]} · {L["product"]["name"]}'
    gallery = (
        f'<figure><img src="{IMG_PIZZA}" alt="{esc(pizza_alt)}" width="800" height="533" '
        f'fetchpriority="high" decoding="async">'
        f'<figcaption>{esc(pizza_alt)}</figcaption></figure>'
        f'<figure><img src="{IMG_PACK}" alt="{esc(L["product"]["alt_pack"])}" width="640" height="427" '
        f'loading="lazy" decoding="async">'
        f'<figcaption>{esc(L["product"]["alt_pack"])}</figcaption></figure>'
        f'<figure><img src="{IMG_SLICES}" alt="{esc(L["product"]["alt_slice"])}" width="800" height="533" '
        f'loading="lazy" decoding="async">'
        f'<figcaption>{esc(L["product"]["alt_slice"])}</figcaption></figure>'
    )

    # SKU / weight / price only — readable in every locale without translation.
    family_chips = "".join(
        f'<a class="skuchip" href="/products/{sku.lower()}">'
        f'<b>{sku}</b><span>{family[sku]["weight"]} kg</span>'
        f'<em>{money(sku_price(family[sku], price_currency), price_currency, lang)}</em></a>'
        for sku in FAMILY_SKUS
    )

    why = "".join(
        f'<div class="card"><div class="card__ico" aria-hidden="true">{i["icon"]}</div>'
        f'<h3>{esc(i["title"])}</h3><p>{esc(i["text"])}</p></div>'
        for i in L["why"]["items"]
    )
    usage = "".join(
        f'<div class="card"><div class="card__ico" aria-hidden="true">{i["icon"]}</div>'
        f'<h3>{esc(i["title"])}</h3><p>{esc(i["desc"])}</p></div>'
        for i in L["usage"]["items"]
    )
    steps = "".join(
        f'<div class="step"><div class="step__n">{esc(s["n"])}</div>'
        f'<h3>{esc(s["title"])}</h3><p>{esc(s["text"])}</p></div>'
        for s in L["export"]["steps"]
    )
    docs = "".join(f"<li>{esc(d)}</li>" for d in L["export"]["docs"])
    pl_items = "".join(f"<li>{esc(x)}</li>" for x in L["pl"]["items"])
    faq = "".join(
        f'<details><summary>{esc(i["q"])}</summary><p>{esc(i["a"])}</p></details>'
        for i in L["faq"]["items"]
    )
    entity = L.get("entity") or {}
    if entity:
        entity_items = "".join(f"<li>{esc(x)}</li>" for x in entity.get("items") or [])
        entity_html = (
            f'<section class="section" id="entity" data-track-section="entity"><div class="wrap">'
            f'<h2>{esc(entity["h2"])}</h2>'
            f'<p class="lede">{esc(entity["lead"])}</p>'
            f'<ul class="checklist">{entity_items}</ul>'
            f'</div></section>\n'
        )
    else:
        entity_html = ""

    # Each country card leads to the landing written in that country's main
    # language; when that is the current page it just scrolls to the form.
    countries = ""
    for c in i18n["_countries"]:
        target_lang = c["primary"]
        href = "#zayavka" if target_lang == lang else page_url(target_lang, locales)
        price = money(prices[c["currency"]], c["currency"], lang)
        current = ' aria-current="true"' if c["code"] == country_of_page else ""
        countries += (
            f'<a class="ctry" href="{href}" data-country-code="{c["code"]}" '
            f'data-country-lang="{target_lang}"{current}>'
            f'<div class="ctry__f" aria-hidden="true">{c["flag"]}</div>'
            f'<div class="ctry__n">{esc(COUNTRY_ENDONYM[c["code"]])}</div>'
            f'<div class="ctry__p">{price}</div></a>'
        )

    # Second reference under the headline price. Russian VAT only means something
    # to a Russian buyer; an importer wants the contract currency instead.
    if lang == "ru":
        price_second = (f'{money(prices["RUB_EXCL"], "RUB", lang)} · '
                        f'{esc(L["price"]["excl_vat"])}')
    elif price_currency == "USD":
        price_second = f'{money(prices["RUB"], "RUB", lang)} · RUB'
    else:
        price_second = f'{money(prices["USD"], "USD", lang)} · USD'

    F = L["form"]
    form_msgs = " ".join(
        f'data-msg-{k}="{esc(v)}"' for k, v in (
            ("sending", F["sending"]), ("ok", F["ok"]),
            ("err-phone", F["err_phone"]), ("err-phone-invalid", F["err_phone"]),
            ("err-consent", F["err_consent"]), ("err-rate", F["err_rate"]),
            ("err-generic", F["err_generic"]), ("err-network", F["err_network"]),
        )
    )

    return f"""<body data-lang="{lang}" data-country="{country_of_page}" data-sku="{SKU}"
 data-value="{prices['RUB']}" data-currency="RUB">
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM_ID}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<header class="topbar"><div class="wrap topbar__in">
  <a class="brand" href="{prefix or "/"}">Kazan<span>Delikates</span></a>
  <nav class="topnav" aria-label="{esc(L["nav"]["catalog"])}">
    <a href="{prefix or "/"}">{esc(L["nav"]["catalog"])}</a>
    <a href="{local("/about")}">{esc(L["nav"]["about"])}</a>
    <a href="{local("/delivery")}">{esc(L["nav"]["delivery"])}</a>
    <a href="#faq">{esc(L["nav"]["faq"])}</a>
  </nav>
  <div class="topbar__spacer"></div>
  <a class="topphone" href="{tel}">{phone}</a>
  <details class="langs"><summary aria-label="{esc(L["nav"]["lang_switch"])}">
    <span aria-hidden="true">🌐</span> {locales[lang]["name"]}</summary>
    <div class="langs__menu">{lang_menu}</div>
  </details>
  <a class="btn btn--primary btn--sm" href="#zayavka">{esc(L["sticky"]["lead"])}</a>
</div></header>

<main>
<section class="hero" data-track-section="hero"><div class="wrap hero__grid">
  <div class="hero__copy">
    <p class="eyebrow">{esc(L["hero"]["eyebrow"])}</p>
    <h1>{esc(L["hero"]["h1"])}</h1>
    <p class="hero__sub">{esc(L["hero"]["sub"])}</p>
  </div>
  <div class="hero__media">
    <img src="{IMG_PIZZA}" alt="{esc(pizza_alt)}" width="800" height="533"
         fetchpriority="high" decoding="async">
    <span class="hero__tag">{SKU} · {esc(facts["net_weight"])} kg</span>
  </div>
  <div class="hero__actions">
    <div class="badges">
      <span class="badge badge--halal">HALAL {esc(facts["halal_cert"])}</span>
      <span class="badge">HACCP</span>
      <span class="badge">ISO 22000:2018</span>
      <span class="badge">{esc(facts["diameter"])} mm</span>
      <span class="badge">{esc(facts["shelf_life_days"])} / {esc(facts["storage_temp"])}</span>
    </div>
    <div class="btn-row">
      <a class="btn btn--primary" href="#zayavka">{esc(L["hero"]["cta_primary"])}</a>
      <a class="btn btn--wa" href="{wa}" target="_blank" rel="noopener">{esc(L["hero"]["cta_wa"])}</a>
      <a class="btn btn--ghost" href="#video">{esc(L["hero"]["cta_video"])}</a>
    </div>
    <p class="hero__note">{esc(L["hero"]["note"])}</p>
  </div>
</div></section>

<section class="section section--soft" data-track-section="trust"><div class="wrap">
  <h2>{esc(L["trust"]["h2"])}</h2>
  <div class="trust">{trust}</div>
</div></section>
{entity_html}
<section class="section" id="video" data-track-section="video"><div class="wrap">
  <h2>{esc(L["video"]["h2"])}</h2>
  <p class="lede">{esc(L["video"]["sub"])}</p>
  <div class="videos">{videos}</div>
</div></section>

<section class="section section--soft" id="product" data-track-section="product"><div class="wrap">
  <h2>{esc(L["product"]["h2"])}</h2>
  <p class="lede">{esc(L["product"]["lead"])}</p>
  <div class="prod">
    <div class="gallery">{gallery}</div>
    <div>
      <h3>{esc(L["product"]["specs_h3"])}</h3>
      <div class="tbl"><table><tbody>{rows(L["product"]["specs"])}</tbody></table></div>
      <h3>{esc(L["product"]["composition_h3"])}</h3>
      <p class="lede">{esc(L["product"]["composition"])}</p>
      <p class="note">{esc(L["product"]["composition_note"])}</p>
      <h3>{esc(L["product"]["nutrition_h3"])}</h3>
      <div class="tbl"><table><tbody>{rows(L["product"]["nutrition"])}</tbody></table></div>
      <h3>{esc(L["product"]["storage_h3"])}</h3>
      <div class="tbl"><table><tbody>{rows(L["product"]["storage"])}</tbody></table></div>
      <div class="skufamily" aria-label="{esc(L["nav"]["catalog"])}">{family_chips}</div>
      <div class="btn-row"><a class="btn btn--ghost" href="#zayavka">{esc(L["product"]["cta"])}</a></div>
    </div>
  </div>
</div></section>

<section class="section" data-track-section="why"><div class="wrap">
  <h2>{esc(L["why"]["h2"])}</h2>
  <div class="cards">{why}</div>
</div></section>

<section class="section section--soft" id="price" data-track-section="price"><div class="wrap">
  <h2>{esc(L["price"]["h2"])}</h2>
  <p class="lede">{esc(L["price"]["sub"])}</p>
  <div class="pricebox">
    <div class="pricecard">
      <div class="pricecard__amt">{money(price_amount, price_currency, lang)}</div>
      <div class="pricecard__per">{esc(L["price"]["per_pack"])}</div>
      <div class="pricecard__excl">{price_second}</div>
      <a class="btn" href="#zayavka">{esc(L["price"]["cta"])}</a>
    </div>
    <div>
      <h3>{esc(L["price"]["your_currency"])}</h3>
      <div class="countries">{countries}</div>
      <div class="tbl" style="margin-top:18px"><table><tbody>{rows(L["price"]["terms"])}</tbody></table></div>
      <p class="note">{esc(L["price"]["note"])}</p>
    </div>
  </div>
</div></section>

<section class="section" data-track-section="export"><div class="wrap">
  <h2>{esc(L["export"]["h2"])}</h2>
  <p class="lede">{esc(L["export"]["sub"])}</p>
  <h3 style="margin-top:26px">{esc(L["export"]["steps_h3"])}</h3>
  <div class="steps">{steps}</div>
  <h3 style="margin-top:34px">{esc(L["export"]["docs_h3"])}</h3>
  <ul class="checklist">{docs}</ul>
</div></section>

<section class="section section--soft" data-track-section="usage"><div class="wrap">
  <h2>{esc(L["usage"]["h2"])}</h2>
  <div class="cards">{usage}</div>
</div></section>

<section class="section" data-track-section="private_label"><div class="wrap">
  <h2>{esc(L["pl"]["h2"])}</h2>
  <p class="lede">{esc(L["pl"]["lead"])}</p>
  <ul class="checklist">{pl_items}</ul>
  <div class="btn-row"><a class="btn btn--primary" href="#zayavka">{esc(L["pl"]["cta"])}</a>
    <a class="btn btn--ghost" href="{local("/oem")}">{esc(L["footer"]["oem"])}</a></div>
</div></section>

<section class="section section--soft" id="faq" data-track-section="faq"><div class="wrap">
  <h2>{esc(L["faq"]["h2"])}</h2>
  <div class="faq">{faq}</div>
</div></section>

<section class="section" id="zayavka" data-track-section="form"><div class="wrap">
  <h2>{esc(F["h2"])}</h2>
  <p class="lede">{esc(F["sub"])}</p>
  <div class="formgrid">
    <form class="lead-form" novalidate data-experiment-id="pepperoni-ads-{lang}" {form_msgs}>
      <label for="lf-name">{esc(F["name"])}</label>
      <input id="lf-name" type="text" name="name" placeholder="{esc(F["name_ph"])}" autocomplete="name">
      <label for="lf-phone">{esc(F["phone"])} *</label>
      <input id="lf-phone" type="tel" name="phone" required
             placeholder="{COUNTRY_DIAL[country_of_page]}\u2009…" autocomplete="tel">
      <label for="lf-msg">{esc(F["msg"])}</label>
      <textarea id="lf-msg" name="message" rows="3" placeholder="{esc(F["msg_ph"])}"></textarea>
      <input type="text" name="company" tabindex="-1" autocomplete="off" aria-hidden="true"
             style="position:absolute;left:-9999px">
      <label class="consent">
        <input type="checkbox" name="consent" required>
        <span>{esc(F["consent_pre"])}<a href="{local("/privacy")}">{esc(F["consent_link"])}</a>{esc(F["consent_post"])}</span>
      </label>
      <button class="btn btn--primary" type="submit">{esc(F["submit"])}</button>
      <p class="lead-form__status" role="status" aria-live="polite"></p>
    </form>
    <div class="contactcard">
      <h3>{esc(L["contacts"]["h2"])}</h3>
      <dl>
        <dt>{esc(L["contacts"]["phone_label"])}</dt>
        <dd><a href="{tel}">{phone}</a></dd>
        <dt>{esc(L["contacts"]["email_label"])}</dt>
        <dd><a href="mailto:{email}">{email}</a></dd>
        <dt>{esc(L["contacts"]["company"])}</dt>
        <dd style="font-weight:400;font-size:.9rem">{esc(L["contacts"]["address"])}</dd>
      </dl>
      <p class="note">{esc(L["contacts"]["hours"])}</p>
      <div class="btn-row">
        <a class="btn btn--wa" href="{wa}" target="_blank" rel="noopener">{esc(L["sticky"]["wa"])}</a>
      </div>
    </div>
  </div>
</div></section>
</main>

<footer><div class="wrap">
  <div class="foot">
    <div>
      <p style="font-weight:750;color:#fff">{esc(L["contacts"]["company"])}</p>
      <p style="margin-top:8px">{esc(L["footer"]["rights"])}</p>
      <p style="margin-top:10px"><a href="{tel}">{phone}</a> · <a href="mailto:{email}">{email}</a></p>
    </div>
    <div>
      <h4>{esc(L["footer"]["links_label"])}</h4>
      <ul>
        <li><a href="{prefix or "/"}">{esc(L["footer"]["catalog"])}</a></li>
        <li><a href="/products/kd-013">{esc(L["footer"]["product"])}</a></li>
        <li><a href="{local("/pepperoni-dlya-pizzerii")}">{esc(L["footer"]["pizzeria"])}</a></li>
        <li><a href="{local("/oem")}">{esc(L["footer"]["oem"])}</a></li>
        {"".join(f'<li><a href="{x["href"]}">{esc(x["label"])}</a></li>' for x in L["footer"].get("extra_links", []))}
      </ul>
    </div>
    <div>
      <h4>{esc(L["nav"]["lang_switch"])}</h4>
      <ul>{"".join(f'<li><a href="{page_url(c, locales)}">{locales[c]["name"]}</a></li>' for c in locales if c in i18n)}</ul>
    </div>
  </div>
  <p class="foot__legal">© {date.today().year} {esc(L["contacts"]["company"])} ·
    <a href="https://api.pepperoni.tatar/">{esc(L["footer"]["api"])}</a> ·
    <a href="{local("/privacy")}">{esc(L["footer"]["privacy"])}</a></p>
</div></footer>

<div class="stickybar">
  <a class="btn btn--primary" href="#zayavka">{esc(L["sticky"]["lead"])}</a>
  <a class="btn btn--wa" href="{wa}" target="_blank" rel="noopener">{esc(L["sticky"]["wa"])}</a>
  <a class="btn btn--ghost" href="{tel}">{esc(L["sticky"]["call"])}</a>
</div>

<script src="/assets/gmp-track.js" defer></script>
<script src="/assets/lead-form.js" defer></script>
<script>
window.addEventListener('load',function(){{
  var s=document.createElement('script');s.async=true;
  s.src='https://mc.yandex.ru/metrika/tag.js';
  s.onload=function(){{if(typeof ym==='function'){{ym({YM_ID},'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:true}});}}}};
  document.head.appendChild(s);
}});
</script>
</body>
</html>
"""


def render(lang: str, i18n: dict, family: dict[str, dict]) -> str:
    L = i18n[lang]
    product = family[SKU]
    export = product["offers"]["exportPrices"]
    prices = {
        "RUB": float(product["offers"]["price"]),
        "RUB_EXCL": float(product["offers"]["priceExclVAT"]),
        **{code: float(value) for code, value in export.items()},
    }
    country = LOCALE_COUNTRY[lang]
    currency = "RUB" if country == "ru" else "USD" if country == "int" else next(
        c["currency"] for c in i18n["_countries"] if c["code"] == country
    )
    amount = prices[currency]
    head = build_head(lang, L, i18n, family, amount, currency)
    body = build_body(lang, L, i18n, family, prices, amount, currency)
    return head + "\n" + body


def main() -> None:
    i18n = load_i18n()
    family = load_products()
    wanted = sys.argv[1:] or [c for c in i18n["_locales"] if c in i18n]

    for lang in wanted:
        if lang not in i18n:
            print(f"⚠️  {lang}: no copy in data/pepperoni_landing_i18n*.json — skipped")
            continue
        out = PUBLIC / i18n["_locales"][lang]["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        html = render(lang, i18n, family)
        out.write_text(html, encoding="utf-8")
        print(f"✅ {out.relative_to(ROOT)}  {len(html):,} bytes")


if __name__ == "__main__":
    main()
