#!/usr/bin/env python3
"""Generate the /jerky OEM · Private Label hub (RU + EN).

Same visual system as /pepperoni (CSS imported from gen_pepperoni_landing.py).
This is a contract-manufacturing page, not a priced catalog SKU: no invented
price, barcode, ТУ or EAEU declaration number. Facts come from the OEM /
capabilities pages (MOQ, packing tech, certificates, contacts).

    python3 scripts/gen_jerky_landing.py

Then: fix_pages.py + qa_pages.py + rebuild_sitemap.py.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_pepperoni_landing as pep  # noqa: E402

PUBLIC = ROOT / "public"
DATA = ROOT / "data"
I18N_PATH = DATA / "jerky_landing_i18n.json"
SITE = "https://pepperoni.tatar"

IMG_HERO = "/images/jerky/jerky-hero.jpg"
IMG_FLOW = "/images/jerky/jerky-flowpack.jpg"
IMG_STICKS = "/images/jerky/jerky-sticks.jpg"
IMG_DOY = "/images/jerky/jerky-doypack.jpg"
IMG_VAC = "/images/jerky/jerky-vacuum.jpg"

EXTRA_CSS = """
.visnote{font-size:.82rem;color:var(--muted);margin-top:12px;max-width:70ch}
.meatgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:26px}
.meat{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:18px}
.meat__b{height:100%}
.meat__b p{color:var(--muted);font-size:.86rem}
.packgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:26px}
.pack{background:#fff;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
.pack img{width:100%;aspect-ratio:4/3;object-fit:cover}
.pack__b{padding:14px 16px}
.pack__b p{color:var(--muted);font-size:.86rem}
.split{display:grid;grid-template-columns:1.05fr .95fr;gap:34px;margin-top:26px;align-items:start}
.formatgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:26px}
.cards--2{grid-template-columns:repeat(2,1fr)}
.tbl + .lede{margin-top:14px}
.crumbs{padding:14px 20px 0;max-width:1120px;margin:0 auto;font-size:.8rem;color:var(--muted)}
.crumbs a{color:var(--muted);text-decoration:none}
@media(max-width:1100px){.meatgrid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){
  .split,.formatgrid{grid-template-columns:1fr}
  .meatgrid,.packgrid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:560px){.meatgrid,.packgrid,.cards--2{grid-template-columns:1fr}}
"""


def load_i18n() -> dict:
    return json.loads(I18N_PATH.read_text(encoding="utf-8"))


def page_url(lang: str) -> str:
    return f"{SITE}/jerky" if lang == "ru" else f"{SITE}/en/jerky"


def build_head(lang: str, L: dict, i18n: dict) -> str:
    facts = i18n["_facts"]
    meta, url = L["meta"], page_url(lang)
    esc = pep.esc
    locales = i18n["_locales"]

    alternates = "\n  ".join(
        f'<link rel="alternate" hreflang="{code}" href="{page_url(code)}">'
        for code in locales
    )
    alternates += f'\n  <link rel="alternate" hreflang="x-default" href="{page_url("ru")}">'

    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"],
             "acceptedAnswer": {"@type": "Answer", "text": item["a"]}}
            for item in L["faq"]["items"]
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
            "corporate https://kazandelikates.tatar."
        ),
    }
    service_ld = {
        "@context": "https://schema.org",
        "@type": "Service",
        "@id": f"{url}#service",
        "name": L["schema"]["service_name"],
        "serviceType": "OEM / Private Label / White Label / Co-development",
        "description": meta["description"],
        "url": url,
        "mainEntityOfPage": {"@id": f"{url}#webpage"},
        "image": [f"{SITE}{IMG_HERO}", f"{SITE}{IMG_FLOW}", f"{SITE}{IMG_VAC}"],
        "areaServed": ["RU", "KZ", "UZ", "KG", "BY", "AZ", "AM", "GE", "TJ"],
        "provider": {"@id": f"{SITE}/#organization"},
        "brand": {"@type": "Brand", "name": "Kazan Delicacies"},
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": L["schema"]["catalog_name"],
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": item["title"]}}
                for item in (L["meats"]["items"] + L["forms"]["items"] + L["pack"]["items"])
            ],
        },
    }
    webpage_ld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "url": url,
        "name": meta["title"],
        "description": meta["description"],
        "inLanguage": lang,
        "about": {"@id": f"{url}#service"},
        "primaryImageOfPage": {"@type": "ImageObject", "url": f"{SITE}{IMG_HERO}"},
    }
    breadcrumb_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": L["nav"]["catalog"],
             "item": SITE + ("" if lang == "ru" else "/en")},
            {"@type": "ListItem", "position": 2, "name": L["nav"]["oem"],
             "item": SITE + ("/oem" if lang == "ru" else "/en/oem")},
            {"@type": "ListItem", "position": 3, "name": L["nav"]["current"], "item": url},
        ],
    }
    def ld(obj) -> str:
        return ('<script type="application/ld+json">'
                + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
                + "</script>")

    eea = pep.EEA_REGIONS.replace(",", "','")
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
gtag('consent','default',{{'ad_storage':'denied','ad_user_data':'denied','ad_personalization':'denied','analytics_storage':'denied','functionality_storage':'granted','security_storage':'granted','wait_for_update':500,'region':['{eea}']}});
gtag('consent','default',{{'ad_storage':'granted','ad_user_data':'granted','ad_personalization':'granted','analytics_storage':'granted','functionality_storage':'granted','security_storage':'granted'}});
gtag('set','ads_data_redaction',true);
gtag('set','url_passthrough',true);
</script>

<!-- Google tag (gtag.js) - Google Ads: {pep.ADS_ID} -->
<script async src="https://www.googletagmanager.com/gtag/js?id={pep.ADS_ID}"></script>
<script>gtag('js',new Date());gtag('config','{pep.ADS_ID}');</script>
<script async src="https://www.googleadservices.com/pagead/conversion_async.js"></script>

<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{pep.GTM_ID}');</script>
<!-- End Google Tag Manager -->

<title>{esc(meta["title"])}</title>
<meta name="description" content="{esc(meta["description"])}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta http-equiv="content-language" content="{lang}">
<link rel="canonical" href="{url}">
  {alternates}

<link rel="icon" type="image/png" sizes="32x32" href="/images/icon-32.png">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" sizes="180x180" href="/images/icon-180.png">
<link rel="manifest" href="/manifest.json">
<link rel="llms" href="/llms.txt" type="text/plain" title="LLM instructions">

<meta property="og:type" content="website">
<meta property="og:site_name" content="pepperoni.tatar">
<meta property="og:title" content="{esc(meta["og_title"])}">
<meta property="og:description" content="{esc(meta["og_description"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{IMG_HERO}">
<meta property="og:image:width" content="1400">
<meta property="og:image:height" content="933">
<meta property="og:image:alt" content="{esc(L["hero"]["img_alt"])}">
<meta property="og:locale" content="{locales[lang]["og"]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(meta["og_title"])}">
<meta name="twitter:description" content="{esc(meta["og_description"])}">
<meta name="twitter:image" content="{SITE}{IMG_HERO}">
<meta name="twitter:image:alt" content="{esc(L["hero"]["img_alt"])}">

<link rel="preload" as="image" href="{IMG_HERO}" fetchpriority="high">

{ld(org_ld)}
{ld(webpage_ld)}
{ld(service_ld)}
{ld(breadcrumb_ld)}
{ld(faq_ld)}

<style>{pep.CSS}{EXTRA_CSS}</style>
</head>"""


def build_body(lang: str, L: dict, i18n: dict) -> str:
    facts = i18n["_facts"]
    esc = pep.esc
    locales = i18n["_locales"]
    wa_base = f"https://wa.me/{facts['whatsapp']}?text="
    wa = wa_base + quote(L["hero"]["cta_wa"] + " — jerky OEM / private label")
    tel = facts["phone_href"]
    phone = facts["phone_display"]
    email = facts["email"]
    prefix = "" if lang == "ru" else "/en"

    def local(path: str) -> str:
        return f"{prefix}{path}" if lang == "ru" or (PUBLIC / f"en{path}.html").exists() else path

    lang_menu = ""
    for code in locales:
        current = ' aria-current="page"' if code == lang else ""
        lang_menu += f'<a href="{page_url(code)}"{current}>{locales[code]["name"]}</a>'

    trust = "".join(
        f'<div class="trust__i"><div class="trust__l">{esc(i["label"])}</div>'
        f'<div class="trust__v">{esc(i["value"])}</div></div>'
        for i in L["trust"]["items"]
    )

    def rows(pairs) -> str:
        return "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in pairs)

    meats = "".join(
        f'<article class="meat"><div class="meat__b"><h3>{esc(m["title"])}</h3>'
        f'<p>{esc(m["text"])}</p></div></article>'
        for m in L["meats"]["items"]
    )
    forms = "".join(
        f'<div class="card"><div class="card__ico" aria-hidden="true">{i["icon"]}</div>'
        f'<h3>{esc(i["title"])}</h3><p>{esc(i["text"])}</p></div>'
        for i in L["forms"]["items"]
    )
    packs = "".join(
        f'<article class="pack"><img src="{p["img"]}" alt="{esc(p["title"])}" '
        f'width="1000" height="666" loading="lazy" decoding="async">'
        f'<div class="pack__b"><h3>{esc(p["title"])}</h3><p>{esc(p["text"])}</p></div></article>'
        for p in L["pack"]["items"]
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
        for s in L["flow"]["steps"]
    )
    docs = "".join(f"<li>{esc(d)}</li>" for d in L["docs"]["items"])
    pl_items = "".join(f"<li>{esc(x)}</li>" for x in L["pl"]["items"])
    faq = "".join(
        f'<details><summary>{esc(i["q"])}</summary><p>{esc(i["a"])}</p></details>'
        for i in L["faq"]["items"]
    )
    label_rows = rows(L["label"]["specs"])
    terms_rows = rows(L["terms"]["rows"])

    F = L["form"]
    form_msgs = " ".join(
        f'data-msg-{k}="{esc(v)}"' for k, v in (
            ("sending", F["sending"]), ("ok", F["ok"]),
            ("err-phone", F["err_phone"]), ("err-phone-invalid", F["err_phone"]),
            ("err-consent", F["err_consent"]), ("err-rate", F["err_rate"]),
            ("err-generic", F["err_generic"]), ("err-network", F["err_network"]),
        )
    )

    gallery = (
        f'<figure><img src="{IMG_HERO}" alt="{esc(L["hero"]["img_alt"])}" width="1400" height="933" '
        f'fetchpriority="high" decoding="async">'
        f'<figcaption>{esc(L["hero"]["img_alt"])}</figcaption></figure>'
        f'<figure><img src="{IMG_FLOW}" alt="{esc(L["pack"]["items"][0]["title"])}" width="1000" height="666" '
        f'loading="lazy" decoding="async">'
        f'<figcaption>{esc(L["pack"]["items"][0]["title"])}</figcaption></figure>'
        f'<figure><img src="{IMG_VAC}" alt="{esc(L["pack"]["items"][2]["title"])}" width="1000" height="666" '
        f'loading="lazy" decoding="async">'
        f'<figcaption>{esc(L["pack"]["items"][2]["title"])}</figcaption></figure>'
    )

    return f"""<body data-lang="{lang}" data-country="{"ru" if lang == "ru" else "int"}" data-sku=""
 data-value="0" data-currency="RUB">
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={pep.GTM_ID}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

<header class="topbar"><div class="wrap topbar__in">
  <a class="brand" href="{prefix or "/"}">Kazan <span>Delicacies</span></a>
  <nav class="topnav" aria-label="{esc(L["nav"]["catalog"])}">
    <a href="{prefix or "/"}">{esc(L["nav"]["catalog"])}</a>
    <a href="{local("/oem")}">{esc(L["nav"]["oem"])}</a>
    <a href="{local("/private-label")}">{esc(L["nav"]["pl"])}</a>
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
<nav class="crumbs" aria-label="Breadcrumb">
  <a href="{prefix or "/"}">{esc(L["nav"]["catalog"])}</a> /
  <a href="{local("/oem")}">{esc(L["nav"]["oem"])}</a> /
  <span aria-current="page">{esc(L["nav"]["current"])}</span>
</nav>
<section class="hero" data-track-section="hero"><div class="wrap hero__grid">
  <div class="hero__copy">
    <p class="eyebrow">{esc(L["hero"]["eyebrow"])}</p>
    <h1>{esc(L["hero"]["h1"])}</h1>
    <p class="hero__sub">{esc(L["hero"]["sub"])}</p>
  </div>
  <div class="hero__media">
    <img src="{IMG_HERO}" alt="{esc(L["hero"]["img_alt"])}" width="1400" height="933"
         fetchpriority="high" decoding="async">
    <span class="hero__tag">{esc(L["hero"]["tag"])}</span>
  </div>
  <div class="hero__actions">
    <div class="badges">
      <span class="badge badge--halal">HALAL {esc(facts["halal_cert"])}</span>
      <span class="badge">HACCP</span>
      <span class="badge">ISO 22000:2018</span>
      <span class="badge">{esc(L["hero"]["badge_moq"])}</span>
      <span class="badge">{esc(L["hero"]["badge_pack"])}</span>
    </div>
    <div class="btn-row">
      <a class="btn btn--primary" href="#zayavka">{esc(L["hero"]["cta_primary"])}</a>
      <a class="btn btn--wa" href="{wa}" target="_blank" rel="noopener">{esc(L["hero"]["cta_wa"])}</a>
      <a class="btn btn--ghost" href="#formats">{esc(L["hero"]["cta_details"])}</a>
    </div>
    <p class="hero__note">{esc(L["hero"]["note"])}</p>
  </div>
</div></section>

<section class="section section--soft" data-track-section="trust"><div class="wrap">
  <h2>{esc(L["trust"]["h2"])}</h2>
  <div class="trust">{trust}</div>
</div></section>

<section class="section" id="product" data-track-section="product"><div class="wrap">
  <h2>{esc(L["about"]["h2"])}</h2>
  <p class="lede">{esc(L["about"]["lead"])}</p>
  <div class="prod">
    <div class="gallery">{gallery}</div>
    <div>
      <h3>{esc(L["about"]["specs_h3"])}</h3>
      <div class="tbl"><table><tbody>{rows(L["about"]["specs"])}</tbody></table></div>
      <p class="note">{esc(L["about"]["note"])}</p>
      <div class="btn-row"><a class="btn btn--ghost" href="#zayavka">{esc(L["about"]["cta"])}</a></div>
    </div>
  </div>
  <p class="visnote">{esc(L["about"]["visnote"])}</p>
</div></section>

<section class="section section--soft" id="meats" data-track-section="meats"><div class="wrap">
  <h2>{esc(L["meats"]["h2"])}</h2>
  <p class="lede">{esc(L["meats"]["lead"])}</p>
  <div class="meatgrid">{meats}</div>
</div></section>

<section class="section" id="formats" data-track-section="formats"><div class="wrap">
  <h2>{esc(L["forms"]["h2"])}</h2>
  <p class="lede">{esc(L["forms"]["lead"])}</p>
  <div class="cards">{forms}</div>
</div></section>

<section class="section section--soft" id="packaging" data-track-section="packaging"><div class="wrap">
  <h2>{esc(L["pack"]["h2"])}</h2>
  <p class="lede">{esc(L["pack"]["lead"])}</p>
  <div class="packgrid">{packs}</div>
  <div class="split">
    <div>
      <h3>{esc(L["label"]["h3"])}</h3>
      <p class="lede">{esc(L["label"]["lead"])}</p>
      <div class="tbl" style="margin-top:16px"><table><tbody>{label_rows}</tbody></table></div>
    </div>
    <div>
      <h3>{esc(L["terms"]["h3"])}</h3>
      <p class="lede">{esc(L["terms"]["lead"])}</p>
      <div class="tbl" style="margin-top:16px"><table><tbody>{terms_rows}</tbody></table></div>
    </div>
  </div>
</div></section>

<section class="section" data-track-section="why"><div class="wrap">
  <h2>{esc(L["why"]["h2"])}</h2>
  <div class="cards">{why}</div>
</div></section>

<section class="section section--soft" data-track-section="private_label"><div class="wrap">
  <h2>{esc(L["pl"]["h2"])}</h2>
  <p class="lede">{esc(L["pl"]["lead"])}</p>
  <ul class="checklist">{pl_items}</ul>
  <div class="btn-row"><a class="btn btn--primary" href="#zayavka">{esc(L["pl"]["cta"])}</a>
    <a class="btn btn--ghost" href="{local("/oem/meat")}">{esc(L["footer"]["meat_oem"])}</a></div>
</div></section>

<section class="section" data-track-section="flow"><div class="wrap">
  <h2>{esc(L["flow"]["h2"])}</h2>
  <p class="lede">{esc(L["flow"]["sub"])}</p>
  <div class="steps">{steps}</div>
  <h3 style="margin-top:34px">{esc(L["docs"]["h3"])}</h3>
  <ul class="checklist">{docs}</ul>
</div></section>

<section class="section section--soft" data-track-section="usage"><div class="wrap">
  <h2>{esc(L["usage"]["h2"])}</h2>
  <div class="cards">{usage}</div>
</div></section>

<section class="section section--soft" id="faq" data-track-section="faq"><div class="wrap">
  <h2>{esc(L["faq"]["h2"])}</h2>
  <div class="faq">{faq}</div>
</div></section>

<section class="section" id="zayavka" data-track-section="form"><div class="wrap">
  <h2>{esc(F["h2"])}</h2>
  <p class="lede">{esc(F["sub"])}</p>
  <div class="formgrid">
    <form class="lead-form" novalidate data-experiment-id="jerky-oem-{lang}" {form_msgs}>
      <label for="lf-name">{esc(F["name"])}</label>
      <input id="lf-name" type="text" name="name" placeholder="{esc(F["name_ph"])}" autocomplete="name">
      <label for="lf-phone">{esc(F["phone"])} *</label>
      <input id="lf-phone" type="tel" name="phone" required
             placeholder="{esc(F["phone_ph"])}" autocomplete="tel">
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
        <li><a href="{local("/oem")}">{esc(L["footer"]["oem"])}</a></li>
        <li><a href="{local("/private-label")}">{esc(L["footer"]["pl"])}</a></li>
        <li><a href="{local("/capabilities")}">{esc(L["footer"]["cap"])}</a></li>
        <li><a href="{local("/pepperoni")}">{esc(L["footer"]["pepperoni"])}</a></li>
        <li><a href="{local("/kazylyk")}">{esc(L["footer"]["kazylyk"])}</a></li>
      </ul>
    </div>
    <div>
      <h4>{esc(L["nav"]["lang_switch"])}</h4>
      <ul>{"".join(f'<li><a href="{page_url(c)}">{locales[c]["name"]}</a></li>' for c in locales)}</ul>
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
  s.onload=function(){{if(typeof ym==='function'){{ym({pep.YM_ID},'init',{{clickmap:true,trackLinks:true,accurateTrackBounce:true,webvisor:true}});}}}};
  document.head.appendChild(s);
}});
</script>
</body>
</html>
"""


def render(lang: str, i18n: dict) -> str:
    return build_head(lang, i18n[lang], i18n) + "\n" + build_body(lang, i18n[lang], i18n)


def main() -> None:
    i18n = load_i18n()
    wanted = sys.argv[1:] or list(i18n["_locales"])
    for lang in wanted:
        if lang not in i18n:
            print(f"⚠️  {lang}: no copy — skipped")
            continue
        out = PUBLIC / i18n["_locales"][lang]["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        html = render(lang, i18n)
        out.write_text(html, encoding="utf-8")
        print(f"✅ {out.relative_to(ROOT)}  {len(html):,} bytes")


if __name__ == "__main__":
    main()
