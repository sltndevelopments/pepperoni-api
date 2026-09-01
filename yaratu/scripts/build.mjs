import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { answers, homeCopy, LANG_NAME, markdownPages, nf, positioning, ui } from "./copy.mjs";
import { absolute, escapeHtml as h, jsonLd, loadData, LOCALES, pagePath, SITE } from "./lib.mjs";
import { qrPath, qrSvg, qrUrl } from "./qr.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const dist = join(root, "site/dist");
const { products: catalog } = await loadData();
const products = catalog.products;
const lastmod = catalog.lastModified;
const qrSvgs = Object.fromEntries(await Promise.all(products.map(async (product) => [product.id, await qrSvg(product.id)])));

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

async function output(relative, content) {
  const path = join(dist, relative);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, content);
}

async function copy(relative) {
  const target = join(dist, relative);
  await mkdir(dirname(target), { recursive: true });
  await copyFile(join(root, relative), target);
}

const copyAllowlist = [
  "styles.css",
  "assets/graphics/pattern-1.png",
  "assets/logo/logo-horizontal.png",
  "assets/logo/logo-horizontal.svg",
  "assets/logo/logo-horizontal-black.svg",
  "assets/logo/logo-horizontal-white.svg",
  "assets/logo/sign.svg",
  "assets/logo/sign-white.svg",
  ...products.flatMap((p) => [p.image.slice(1), p.image.replace(/\.jpg$/, "-800.jpg").slice(1)])
];
for (const file of copyAllowlist) await copy(file);

const formatNumber = (value, lang) => new Intl.NumberFormat(lang === "en" ? "en-US" : "ru-RU", {
  maximumFractionDigits: 1
}).format(value);
const grams = (lang) => lang === "en" ? "g" : "г";
const dailyValue = { protein: 75, fat: 83, saturatedFat: 20, carbs: 365 };
const dailyPercent = (value, key) => `${Math.round((Number(value) / dailyValue[key]) * 100)}%`;

function localeFile(lang, slug, kind = "html") {
  const prefix = lang === "ru" ? "" : `${lang}/`;
  if (!slug) return kind === "html" ? `${prefix}index.html` : `${prefix}index.md`;
  return kind === "html" ? `${prefix}${slug}/index.html` : `${prefix}${slug}.md`;
}

function markdownPath(lang, slug = "") {
  const prefix = lang === "ru" ? "" : `/${lang}`;
  return slug ? `${prefix}/${slug}.md` : `${prefix}/index.md`;
}

function hreflangLinks(pairs, xDefault) {
  return pairs.map(([lang, path]) => `<link rel="alternate" hreflang="${lang}" href="${absolute(path)}">`).join("")
    + `<link rel="alternate" hreflang="x-default" href="${absolute(xDefault)}">`;
}

function alternates(slug) {
  return hreflangLinks(LOCALES.map((lang) => [lang, pagePath(lang, slug)]), pagePath("ru", slug));
}

function langLinks(lang, slug = "") {
  return LOCALES.map((code) => {
    const current = code === lang ? " nav__lang--current" : "";
    const aria = code === lang ? ' aria-current="page"' : "";
    return `<a class="nav__lang${current}" href="${pagePath(code, slug)}" hreflang="${code}"${aria}>${LANG_NAME[code]}</a>`;
  }).join("");
}

function qrBlock(product, lang) {
  const L = ui[lang];
  return `<div class="nf-qr"><a class="nf-qr__code" href="${qrPath(product.id)}" aria-label="${h(L.qrCaption)}">${qrSvgs[product.id]}</a><a class="nf-qr__link" href="${qrPath(product.id)}">${h(L.qrCaption)}</a></div>`;
}

function nutritionFacts(product, lang, compact = false) {
  const n = product.nutrition;
  const N = nf[lang];
  const kcal = formatNumber(n.caloriesKcal, lang);
  const kj = formatNumber(Math.round(n.caloriesKcal * 4.184), lang);
  const g = grams(lang);
  const protein = formatNumber(n.proteinGrams, lang);
  const fat = formatNumber(n.fatGrams, lang);
  const sat = formatNumber(n.saturatedFatGrams, lang);
  const carbs = formatNumber(n.carbohydrateGrams, lang);
  const net = `${formatNumber(product.netWeight.value, lang)} ${g}`;
  const composition = h(product.ingredients[lang]).replace(/\.+$/, "");
  return `<aside class="nf-wrap${compact ? " nf-wrap--compact" : ""}" aria-label="${N.label}">
<div class="nf-name">${h(product.name[lang])}</div>
<div class="nf-card">
<p class="nf-card-title">${N.label}</p>
<p class="nf-basis">${N.per}</p>
<div class="nf-net"><span>${N.net}</span><span>${net}</span></div>
<div class="nf-line-10"></div>
<p class="nf-energy-cap">${N.energy}</p>
<p class="nf-energy-line">${kcal} ${N.kcal} / ${kj} ${N.kj}</p>
<div class="nf-cal-row"><span class="nf-cal-label">${N.calories}</span><span class="nf-cal-val">${kcal}</span></div>
<div class="nf-line-5"></div>
<div class="nf-dv-head">${N.dv}</div>
<div class="nf-row bold"><span>${N.protein(protein, g)}</span><span>${dailyPercent(n.proteinGrams, "protein")}</span></div>
<div class="nf-row bold"><span>${N.fat(fat, g)}</span><span>${dailyPercent(n.fatGrams, "fat")}</span></div>
<div class="nf-row indent"><span>${N.sat(sat, g)}</span><span>${dailyPercent(n.saturatedFatGrams, "saturatedFat")}</span></div>
<div class="nf-row bold"><span>${N.carbs(carbs, g)}</span><span>${dailyPercent(n.carbohydrateGrams, "carbs")}</span></div>
<div class="nf-line-5"></div>
<p class="nf-foot">${N.foot}</p>
<div class="nf-line-1"></div>
<p class="nf-ing-title">${N.ingredients}</p>
<p class="nf-ing-text"><b>${N.ingredientsPref}</b> ${composition}.</p>
<p class="nf-ing-extra"><b>${N.contains}</b> ${h(product.allergens[lang])}</p>
</div>
${qrBlock(product, lang)}
</aside>`;
}

function homeMarkdown(lang) {
  const L = ui[lang];
  const C = homeCopy[lang];
  const lines = products.map((p) => {
    const n = p.nutrition;
    return `- [${p.name[lang]}](${absolute(pagePath(lang, `products/${p.id}`))}): ${p.summary[lang]} ${formatNumber(n.caloriesKcal, lang)} ${L.kcal}, ${formatNumber(n.proteinGrams, lang)} ${grams(lang)} ${L.protein}.`;
  });
  return `# ${L.hero}\n\n${L.lead}\n\n${C.halalLine}\n\n## ${L.range}\n\n${L.nutritionNote}\n\n${lines.join("\n")}\n\n- [${L.ingredients}](${absolute(pagePath(lang, "ingredients"))})\n- [${L.nitrite}](${absolute(pagePath(lang, "without-sodium-nitrite"))})\n- [${L.retail}](${absolute(pagePath(lang, "retail"))})\n- [llms.txt](${SITE}/llms.txt)\n- [products.json](${SITE}/data/products.json)\n`;
}

function productMarkdown(product, lang) {
  const L = ui[lang];
  const n = product.nutrition;
  const halal = lang === "en" ? "Certificate No. 614A/2024" : "ДУМ РТ №614А/2024";
  return `# ${product.name[lang]}\n\n${product.summary[lang]}\n\n- ${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}\n- ${L.halal}: ${halal}\n- ${L.nitrite}\n\n## ${L.composition}\n\n${product.ingredients[lang]}\n\n**${L.allergens}:** ${product.allergens[lang]}\n\n## ${L.nutrition}\n\n- ${L.kcal}: ${formatNumber(n.caloriesKcal, lang)}\n- ${L.protein}: ${formatNumber(n.proteinGrams, lang)} ${grams(lang)}\n- ${L.fat}: ${formatNumber(n.fatGrams, lang)} ${grams(lang)}\n- ${L.carbs}: ${formatNumber(n.carbohydrateGrams, lang)} ${grams(lang)}\n\n${L.nutritionNote}\n\nQR: ${qrUrl(product.id)}\n`;
}

function schemas(items) {
  return `<script type="application/ld+json">${jsonLd(items)}</script>`;
}

function cardImage(product) {
  return product.image.replace(/\.jpg$/, "-800.jpg");
}

function packshot(product, lang, extra = "", { srcset = true } = {}) {
  const src = cardImage(product);
  const set = srcset ? ` srcset="${src} 800w, ${product.image} 1400w" sizes="(max-width: 860px) 92vw, 560px"` : "";
  return `<img src="${src}"${set} alt="${h(product.name[lang])}" width="800" height="1285"${extra}>`;
}

function shell({ lang, slug = "", title, description, body, structured, extraHead = "", canonicalPath, alternateHtml, langNav }) {
  const L = ui[lang];
  const canonical = absolute(canonicalPath || pagePath(lang, slug));
  const langs = langNav || langLinks(lang, slug);
  return `<!doctype html>
<html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${h(title)}</title><meta name="description" content="${h(description)}"><meta name="theme-color" content="#2F391C">
<meta name="yandex-verification" content="1817223863cbfebb">
<link rel="canonical" href="${canonical}">${alternateHtml || alternates(slug)}
<link rel="alternate" type="text/markdown" href="${markdownPath(lang, slug)}" title="Markdown for agents">
<link rel="api-catalog" href="/.well-known/api-catalog" type="application/linkset+json">
<link rel="ai-catalog" href="/.well-known/ai-catalog.json" type="application/json">
<meta property="og:type" content="website"><meta property="og:url" content="${canonical}"><meta property="og:title" content="${h(title)}"><meta property="og:description" content="${h(description)}"><meta property="og:image" content="${SITE}/assets/logo/logo-horizontal.png">
<link rel="preload" href="/styles.css" as="style">
${extraHead}<link rel="stylesheet" href="/styles.css">${schemas(structured || [])}</head>
<body><a class="skip-link" href="#main">${L.skip}</a>
<header class="nav"><div class="wrap nav__inner"><a class="nav__logo" href="${pagePath(lang)}"><img src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"></a>
<nav class="nav__links" aria-label="${L.products}"><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="${pagePath(lang)}#contacts">${L.contacts}</a></nav>
<details class="nav__menu"><summary>${L.menu}</summary><nav aria-label="${L.mobileMenu}"><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="${pagePath(lang)}#contacts">${L.contacts}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a>${langs}</nav></details>
<div class="nav__actions"><nav class="nav__langs" aria-label="${L.languages}">${langs}</nav><a class="nav__cta" href="${pagePath(lang)}#contacts">${L.connect}</a></div></div></header>
<main id="main">${body}</main>
<footer class="footer"><div class="wrap footer__inner"><div><img class="footer__logo" src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"><p>© 2026 Yaratu · ${L.footer}</p></div><nav><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="/privacy.html">${L.privacy}</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a href="tel:+79872170202">+7 987 217-02-02</a></nav></div></footer></body></html>`;
}

const officialProfiles = [
  "https://pepperoni.tatar/",
  "https://kazandelikates.tatar/",
  "https://www.youtube.com/@kazandelikates"
];
const org = {
  "@type": "Organization", "@id": `${SITE}/#organization`, name: "ООО «Казанские Деликатесы»",
  alternateName: "Kazan Delicacies LLC", url: "https://pepperoni.tatar/", email: "info@kazandelikates.tatar",
  telephone: "+79872170202", brand: {"@id": `${SITE}/#brand`}, sameAs: officialProfiles,
  address: {"@type": "PostalAddress", streetAddress: "ул. Аграрная, д. 2, оф. 7", addressLocality: "Казань", postalCode: "420061", addressCountry: "RU"}
};
const brand = {
  "@type": "Brand", "@id": `${SITE}/#brand`, name: "Ярату", alternateName: "Yaratu",
  url: `${SITE}/`, logo: `${SITE}/assets/logo/logo-horizontal.png`, sameAs: officialProfiles
};

function card(product, lang, index) {
  const L = ui[lang];
  const C = homeCopy[lang];
  const [positioningTitle, positioningText] = positioning[product.id][lang];
  return `<article class="product" id="product-${product.id}"><div class="product__media">${packshot(product, lang, ' loading="lazy"', { srcset: false })}</div>
<div class="product__body"><div class="product__intro-top"><span class="product__index">${String(index + 1).padStart(2, "0")}</span><div class="product__tags"><span class="tag">${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${L.nitrite}</span></div></div>
<h3>${h(product.name[lang])}</h3><p>${h(product.summary[lang])}</p>
<div class="product__usp"><span>${C.usp}</span><h4>${h(positioningTitle)}</h4><p>${h(positioningText)}</p></div>
<p class="product__allergens"><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p>
<a class="btn btn--outline" href="${pagePath(lang, `products/${product.id}`)}">${L.see}</a></div>
<details class="product__nutrition-toggle"><summary>${L.seeNutrition}</summary><div class="product__nutrition"><p>${L.nutritionNote}</p>${nutritionFacts(product, lang)}</div></details></article>`;
}

function home(lang) {
  const L = ui[lang];
  const C = homeCopy[lang];
  const items = products.map((p, i) => ({"@type": "ListItem", position: i + 1, url: absolute(pagePath(lang, `products/${p.id}`)), name: p.name[lang]}));
  const faqPage = {"@type": "FAQPage", mainEntity: C.faqs.map(([name, text]) => ({"@type": "Question", name, acceptedAnswer: {"@type": "Answer", text}}))};
  const structured = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": `${SITE}/#website`, url: `${SITE}/`, name: "Yaratu", inLanguage: lang},
    org, brand, faqPage, {"@type": "ItemList", name: L.range, itemListElement: items}
  ]};
  const body = `<section class="hero"><div class="hero__plane"><div class="hero__mesh"></div><div class="hero__pattern"></div><div class="hero__glow hero__glow--warm"></div><div class="hero__orb"></div><img class="hero__mark" src="/assets/logo/sign-white.svg" alt=""></div><div class="hero__shade"></div>
<div class="wrap hero__layout"><div class="hero__content"><p class="hero__overline">${C.overline}</p><h1>${L.hero}</h1><p class="lede">${L.lead}</p><div class="hero__actions"><a class="btn btn--solid" href="#products">${C.explore}</a><a class="btn btn--ghost" href="#contacts">${L.connect}</a></div><div class="hero__badges"><span>${C.badges}</span><span>${L.ingredients}</span><span>${L.nitrite}</span></div></div>
</div></section>
<section id="advantages" class="story-section"><div class="wrap story"><div class="story__copy"><span class="eyebrow">${C.story.eyebrow}</span><h2>${C.story.title}</h2><p class="lede">${C.story.lead}</p><p class="story__quote">${C.story.quote}</p></div><div class="story__visual">${packshot(products[4], lang, ' loading="lazy"', { srcset: false })}</div></div></section>
<section class="trust"><div class="wrap"><div class="facts">${C.facts.map(([number, title, text]) => `<article><span>${number}</span><h2>${h(title)}</h2><p>${h(text)}</p></article>`).join("")}</div></div></section>
<section class="production"><div class="wrap production__grid"><div><span class="eyebrow">${C.production.eyebrow}</span><h2>${C.production.title}</h2></div><div class="production__copy"><p>${C.production.lead}</p><div class="production__standards">${C.production.standards.map(([name, text]) => `<div><strong>${name}</strong><span>${text}</span></div>`).join("")}</div></div></div></section>
<section id="products"><div class="wrap"><div class="section-head"><span class="eyebrow">${L.products}</span><h2>${L.range}</h2><p>${L.nutritionNote}</p></div>
<div class="products">${products.map((p, i) => card(p, lang, i)).join("")}</div></div></section>
<section id="quality" class="quality"><div class="wrap quality__inner"><div class="section-head"><span class="eyebrow">${C.quality.eyebrow}</span><h2>${C.quality.title}</h2><p>${C.quality.lead}</p></div><div class="quality-grid">${C.quality.items.map(([number, title, text]) => `<article><span>${number}</span><h3>${h(title)}</h3><p>${h(text)}</p></article>`).join("")}</div></div></section>
<section id="faq"><div class="wrap"><div class="section-head"><span class="eyebrow">FAQ</span><h2>${C.faqTitle}</h2><p>${C.faqLead}</p></div><div class="faq">${C.faqs.map(([q, a]) => `<details><summary>${h(q)}</summary><p>${h(a)}</p></details>`).join("")}</div></div></section>
<section id="contacts" class="contact-cta"><div class="wrap contact-cta__grid"><div><span class="eyebrow">${L.contacts}</span><h2>${C.contactTitle}</h2><p>${C.contactLead}</p></div><div class="contact-cta__links"><a href="tel:+79872170202">+7 987 217-02-02</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><address>${C.address}</address><a class="btn btn--solid" href="${pagePath(lang, "retail")}">${L.retail}</a></div></div></section>`;
  return shell({ lang, title: C.title, description: L.lead, body, structured });
}

async function editorialHome() {
  const html = await readFile(join(root, "v3.html"), "utf8");
  const faqs = homeCopy.ru.faqs;
  const items = products.map((p, i) => ({
    "@type": "ListItem",
    position: i + 1,
    url: absolute(pagePath("ru", `products/${p.id}`)),
    name: p.name.ru
  }));
  const structured = {
    "@context": "https://schema.org",
    "@graph": [
      {"@type": "WebSite", "@id": `${SITE}/#website`, url: `${SITE}/`, name: "Yaratu", inLanguage: "ru"},
      org,
      brand,
      {
        "@type": "FAQPage",
        mainEntity: faqs.map(([name, text]) => ({
          "@type": "Question",
          name,
          acceptedAnswer: {"@type": "Answer", text}
        }))
      },
      {"@type": "ItemList", name: ui.ru.range, itemListElement: items}
    ]
  };
  const seoHead = `    <meta name="yandex-verification" content="1817223863cbfebb">
    <link rel="canonical" href="${absolute(pagePath("ru"))}">
    ${alternates("")}
    <link rel="alternate" type="text/markdown" href="/index.md" title="Markdown for agents">
    <link rel="api-catalog" href="/.well-known/api-catalog" type="application/linkset+json">
    <link rel="ai-catalog" href="/.well-known/ai-catalog.json" type="application/json">
    <meta property="og:type" content="website">
    <meta property="og:url" content="${absolute(pagePath("ru"))}">
    <meta property="og:title" content="Ярату — мясные продукты без секретов">
    <meta property="og:description" content="${h(ui.ru.lead)}">
    <meta property="og:image" content="${SITE}/assets/logo/logo-horizontal.png">
    ${schemas(structured)}
`;
  if (/<meta name="robots"/i.test(html)) {
    throw new Error("editorial homepage must be indexable: remove robots noindex from v3.html");
  }
  return html.replace("</head>", `${seoHead}  </head>`);
}

function productPage(product, lang) {
  const L = ui[lang];
  const C = homeCopy[lang];
  const slug = `products/${product.id}`;
  const n = product.nutrition;
  const productSchema = {
    "@type": "Product", "@id": `${absolute(pagePath(lang, slug))}#product`, name: product.name[lang],
    description: product.summary[lang], image: absolute(product.image), brand: {"@id": `${SITE}/#brand`},
    manufacturer: {"@id": `${SITE}/#organization`}, category: product.kind[lang],
    weight: {"@type": "QuantitativeValue", value: product.netWeight.value, unitCode: "GRM"}
  };
  const breadcrumb = {"@type": "BreadcrumbList", itemListElement: [
    {"@type": "ListItem", position: 1, name: L.home, item: absolute(pagePath(lang))},
    {"@type": "ListItem", position: 2, name: L.products, item: `${absolute(pagePath(lang))}#products`},
    {"@type": "ListItem", position: 3, name: product.name[lang], item: absolute(pagePath(lang, slug))}
  ]};
  const body = `<section class="product-page-hero"><div class="wrap product-page-hero__grid"><div class="product-page-hero__stage">${packshot(product, lang, ' fetchpriority="high"')}</div><div class="product-page-hero__copy"><a class="back-link" href="${pagePath(lang)}#product-${product.id}">← ${L.products}</a><span class="eyebrow">${h(product.kind[lang])}</span><h1>${h(product.name[lang])}</h1><p class="lede">${h(product.summary[lang])}</p><div class="product__tags"><span class="tag">${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${L.nitrite}</span></div><div class="kbju"><div><strong>${formatNumber(n.caloriesKcal, lang)}</strong><span>${L.kcal}</span></div><div><strong>${formatNumber(n.proteinGrams, lang)}</strong><span>${grams(lang)} ${L.protein}</span></div><div><strong>${formatNumber(n.fatGrams, lang)}</strong><span>${grams(lang)} ${L.fat}</span></div><div><strong>${formatNumber(n.carbohydrateGrams, lang)}</strong><span>${grams(lang)} ${L.carbs}</span></div></div><a class="btn btn--olive" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20${encodeURIComponent(product.id)}">${L.contact}</a></div></div></section>
<section class="nutrition-dossier"><div class="wrap nutrition-layout"><div class="nutrition-layout__copy"><div class="section-head"><span class="eyebrow">${L.composition}</span><h2>${C.productLabel}</h2><p>${h(product.ingredients[lang])}</p><p><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p></div><div class="data-status"><span>${L.status}</span><p>${L.nutritionNote}</p><p>${C.productStatus}</p></div></div><div class="product__label product__label--large">${nutritionFacts(product, lang)}</div></div></section>
<section id="contacts" class="contact-cta"><div class="wrap contact-cta__grid"><div><span class="eyebrow">${L.contacts}</span><h2>${C.specTitle}</h2><p>${C.specLead}</p></div><div class="contact-cta__links"><a href="tel:+79872170202">+7 987 217-02-02</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a class="btn btn--solid" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20${encodeURIComponent(product.id)}">${L.contact}</a></div></div></section>`;
  return shell({lang, slug, title: `${product.name[lang]} — Yaratu`, description: product.summary[lang], body, structured: {"@context": "https://schema.org", "@graph": [org, brand, productSchema, breadcrumb]}});
}

function answerPage(lang, kind) {
  const isIngredients = kind === "ingredients";
  const slug = isIngredients ? "ingredients" : "without-sodium-nitrite";
  const copy = answers[isIngredients ? "ingredients" : "nitrite"][lang];
  const faq = {"@type": "FAQPage", mainEntity: [
    {"@type": "Question", name: copy.title, acceptedAnswer: {"@type": "Answer", text: copy.answer}},
    {"@type": "Question", name: copy.q, acceptedAnswer: {"@type": "Answer", text: copy.a}}
  ]};
  const breadcrumb = {"@type": "BreadcrumbList", itemListElement: [
    {"@type": "ListItem", position: 1, name: ui[lang].home, item: absolute(pagePath(lang))},
    {"@type": "ListItem", position: 2, name: copy.title, item: absolute(pagePath(lang, slug))}
  ]};
  const links = products.map((p) => `<li><a href="${pagePath(lang, `products/${p.id}`)}">${h(p.name[lang])}</a></li>`).join("");
  const body = `<section><div class="wrap"><div class="section-head"><span class="eyebrow">${ui[lang][isIngredients ? "ingredients" : "nitrite"]}</span><h1>${copy.title}</h1><p class="lede">${copy.answer}</p></div><div class="contact-box"><p>${copy.detail}</p><h2>${copy.q}</h2><p>${copy.a}</p></div><ul class="checklist" style="margin-top:2rem">${links}</ul></div></section>`;
  return shell({lang, slug, title: `${copy.title} — Yaratu`, description: copy.answer, body, structured: {"@context": "https://schema.org", "@graph": [faq, breadcrumb]}});
}

function retailPage(lang) {
  const L = ui[lang];
  const C = homeCopy[lang];
  const slug = "retail";
  const body = `<section><div class="wrap split"><div class="section-head"><span class="eyebrow">${L.retail}</span><h1>${C.retailTitle}</h1><p class="lede">${C.retailAnswer}</p><a class="btn btn--olive" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20specifications">${L.contact}</a></div><div class="contact-box"><h2>${L.contacts}</h2><p>${C.company}<br>${C.retailAddress}<br><a href="tel:+79872170202">+7 987 217-02-02</a><br><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></p><p>${L.nutritionNote}</p></div></div></section>`;
  const breadcrumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
    {"@type": "ListItem", position: 1, name: L.home, item: absolute(pagePath(lang))},
    {"@type": "ListItem", position: 2, name: L.retail, item: absolute(pagePath(lang, slug))}
  ]};
  return shell({lang, slug, title: C.retailTitle, description: C.retailAnswer, body, structured: breadcrumb});
}

function qrLanding(product) {
  const path = qrPath(product.id);
  const names = LOCALES.map((lang) => product.name[lang]).join(" · ");
  const buttons = LOCALES.map((lang) => `<a class="btn btn--solid" href="${pagePath(lang, `products/${product.id}`)}" hreflang="${lang}" lang="${lang}">${LANG_NAME[lang]}</a>`).join("");
  const leads = LOCALES.map((lang) => `<p lang="${lang}">${h(ui[lang].qrLead)}</p>`).join("");
  const langNav = LOCALES.map((code) => `<a class="nav__lang" href="${pagePath(code, `products/${product.id}`)}" hreflang="${code}">${LANG_NAME[code]}</a>`).join("");
  const body = `<section class="qr-landing"><div class="wrap qr-landing__grid">${packshot(product, "ru", "", { srcset: false })}<div class="qr-landing__copy"><span class="eyebrow">Yaratu</span><h1>${h(product.name.ru)}</h1><p class="lede">${h(names)}</p>${leads}<div class="qr-landing__langs">${buttons}</div><div class="nf-qr"><div class="nf-qr__code">${qrSvgs[product.id]}</div><p class="nf-qr__link">${h(qrUrl(product.id))}</p></div></div></div></section>`;
  return shell({
    lang: "ru",
    slug: `q/${product.id}`,
    title: `${product.name.ru} — QR · Yaratu`,
    description: `${product.name.ru} / ${product.name.en} / ${product.name.tt}. ${ui.ru.qrLead}`,
    body,
    canonicalPath: path,
    alternateHtml: hreflangLinks(LOCALES.map((lang) => [lang, pagePath(lang, `products/${product.id}`)]), path),
    langNav,
    structured: {"@context": "https://schema.org", "@graph": [org, brand, {
      "@type": "Product",
      name: product.name.ru,
      alternateName: [product.name.en, product.name.tt],
      url: absolute(path),
      image: absolute(product.image),
      brand: {"@id": `${SITE}/#brand`}
    }]}
  });
}

function privacyPage() {
  const body = `<section class="page-legal"><div class="wrap"><span class="eyebrow">Документы</span><h1>Политика обработки персональных данных</h1>
<p class="note">Оператор — ООО «Казанские Деликатесы». Сайт yaratu.com — суббрендовый ресурс того же юридического лица, что и pepperoni.tatar. Обработка ведётся по 152-ФЗ.</p>
<table class="range-table"><tbody>
<tr><th>Полное наименование</th><td>Общество с ограниченной ответственностью «Казанские Деликатесы»</td></tr>
<tr><th>ИНН / КПП / ОГРН</th><td>1686021074 / 168601001 / 1221600096893</td></tr>
<tr><th>Адрес</th><td>420061, г. Казань, ул. Аграрная, д. 2, оф. 7</td></tr>
<tr><th>Email</th><td><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></td></tr>
<tr><th>Телефон</th><td><a href="tel:+79872170202">+7 987 217-02-02</a></td></tr>
</tbody></table>
<h2>Какие данные обрабатываются</h2>
<p>При обращении по телефону или email могут обрабатываться имя, телефон, почта, текст обращения и технические журналы в объёме, нужном для ответа.</p>
<h2>Цели</h2>
<ul class="checklist"><li>запросы о продукции и поставках Ярату;</li><li>договоры и требования закона;</li><li>работоспособность сайта.</li></ul>
<h2>Права</h2>
<p>Запрос на уточнение, блокирование или удаление данных — на info@kazandelikates.tatar с темой «Запрос на ПДн».</p>
</div></section>`;
  return shell({
    lang: "ru",
    title: "Политика обработки персональных данных — Ярату",
    description: "Политика обработки персональных данных ООО «Казанские Деликатесы» для сайта yaratu.com.",
    body,
    extraHead: `<meta name="robots" content="noindex,follow">\n`
  }).replace('<link rel="canonical" href="https://yaratu.com/">', '<link rel="canonical" href="https://yaratu.com/privacy.html">');
}

for (const lang of LOCALES) {
  await output(localeFile(lang, "", "html"), lang === "ru" ? await editorialHome() : home(lang));
  await output(localeFile(lang, "", "md"), homeMarkdown(lang));
  await output(localeFile(lang, "retail"), retailPage(lang));
  await output(localeFile(lang, "retail", "md"), markdownPages.retail[lang]);
  await output(localeFile(lang, "ingredients"), answerPage(lang, "ingredients"));
  await output(localeFile(lang, "ingredients", "md"), markdownPages.ingredients[lang]);
  await output(localeFile(lang, "without-sodium-nitrite"), answerPage(lang, "nitrite"));
  await output(localeFile(lang, "without-sodium-nitrite", "md"), markdownPages.nitrite[lang]);
  for (const product of products) {
    await output(localeFile(lang, `products/${product.id}`), productPage(product, lang));
    await output(localeFile(lang, `products/${product.id}`, "md"), productMarkdown(product, lang));
  }
}
await output("privacy.html", privacyPage());

for (const product of products) {
  await output(`q/${product.id}.svg`, `${qrSvgs[product.id]}\n`);
  await output(`q/${product.id}/index.html`, qrLanding(product));
  await output(`q/${product.id}.md`, `# ${product.name.ru} / ${product.name.en} / ${product.name.tt}\n\n${qrUrl(product.id)}\n\n- [Русский](${absolute(pagePath("ru", `products/${product.id}`))})\n- [English](${absolute(pagePath("en", `products/${product.id}`))})\n- [Татарча](${absolute(pagePath("tt", `products/${product.id}`))})\n`);
}

const publicProducts = {
  schemaVersion: catalog.schemaVersion, lastModified: lastmod,
  notice: catalog.nutritionBasis, products
};
await output("data/products.json", `${JSON.stringify(publicProducts, null, 2)}\n`);
const evidenceSummary = {
  schemaVersion: 1,
  lastModified: lastmod,
  products: products.map((product) => ({
    id: product.id,
    nutrition: product.status.nutrition,
    composition: product.status.composition,
    halal: product.status.halal,
    evidence: product.status.evidence
  }))
};
await output("data/evidence-summary.json", `${JSON.stringify(evidenceSummary, null, 2)}\n`);
await output("brand.txt", await readFile(join(root, "data/brand.txt"), "utf8"));

const csvCell = (v) => `"${String(v).replaceAll('"', '""')}"`;
const csv = [
  ["id", "name_ru", "name_en", "name_tt", "kind_ru", "kind_en", "kind_tt", "net_weight_g", "ingredients_ru", "ingredients_en", "ingredients_tt", "nutrition_status", "halal_status", "evidence_status"],
  ...products.map((p) => [p.id, p.name.ru, p.name.en, p.name.tt, p.kind.ru, p.kind.en, p.kind.tt, p.netWeight.value, p.ingredients.ru, p.ingredients.en, p.ingredients.tt, p.status.nutrition, p.status.halal, p.status.evidence])
].map((row) => row.map(csvCell).join(",")).join("\n");
await output("feeds/products.csv", `${csv}\n`);
await output("feeds/products.json", `${JSON.stringify(publicProducts, null, 2)}\n`);
const xmlEscape = (v) => h(v).replaceAll("'", "&apos;");
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<products generated="${lastmod}" merchant="false">\n${products.map((p) => `  <product id="${p.id}"><name lang="ru">${xmlEscape(p.name.ru)}</name><name lang="en">${xmlEscape(p.name.en)}</name><name lang="tt">${xmlEscape(p.name.tt)}</name><netWeight unit="g">${p.netWeight.value}</netWeight><nutrition status="${p.status.nutrition}" basisGrams="100"/><halal status="${p.status.halal}"/></product>`).join("\n")}\n</products>\n`;
await output("feeds/products.xml", xml);

const urls = ["", "retail", "ingredients", "without-sodium-nitrite", ...products.map((p) => `products/${p.id}`)];
const sitemapLocale = LOCALES.flatMap((lang) => urls.map((slug) => {
  const alts = LOCALES.map((code) => `<xhtml:link rel="alternate" hreflang="${code}" href="${absolute(pagePath(code, slug))}"/>`).join("");
  return `  <url><loc>${absolute(pagePath(lang, slug))}</loc><lastmod>${lastmod}</lastmod>${alts}<xhtml:link rel="alternate" hreflang="x-default" href="${absolute(pagePath("ru", slug))}"/></url>`;
}));
const sitemapQr = products.map((product) => {
  const loc = qrPath(product.id);
  const alts = LOCALES.map((code) => `<xhtml:link rel="alternate" hreflang="${code}" href="${absolute(pagePath(code, `products/${product.id}`))}"/>`).join("");
  return `  <url><loc>${absolute(loc)}</loc><lastmod>${lastmod}</lastmod>${alts}<xhtml:link rel="alternate" hreflang="x-default" href="${absolute(loc)}"/></url>`;
});
const sitemapEntries = [...sitemapLocale, ...sitemapQr];
await output("sitemap.xml", `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${sitemapEntries.join("\n")}\n</urlset>\n`);
await output("robots.txt", `User-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\nAllow: /.well-known/api-catalog\nAllow: /.well-known/ai-catalog.json\nAllow: /.well-known/agent-skills/\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\n\nSitemap: ${SITE}/sitemap.xml\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("robots-ai.txt", `# Yaratu AI crawler directives\nUser-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\n\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("ai.txt", `Yaratu permits indexing of public pages and feeds for search and AI retrieval.\nCanonical product data: ${SITE}/data/products.json\nHuman-readable summary: ${SITE}/llms.txt\n`);
await output("989787de78c652b55e6887550582b6f6.txt", "989787de78c652b55e6887550582b6f6\n");

const productLines = products.map((p) => `- [${p.name.ru}](${SITE}/products/${p.id}/) / [${p.name.en}](${SITE}/en/products/${p.id}/) / [${p.name.tt}](${SITE}/tt/products/${p.id}/) · QR ${qrUrl(p.id)}`).join("\n");
await output("llms.txt", `# Yaratu / Ярату\n\nRU+EN+TT product range with disclosed ingredients. Nutrition is calculated, not laboratory-tested. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.\n\n${productLines}\n\n- [RU retail](${SITE}/retail/)\n- [EN retail](${SITE}/en/retail/)\n- [TT retail](${SITE}/tt/retail/)\n- [Canonical JSON](${SITE}/data/products.json)\n- [JSON feed](${SITE}/feeds/products.json), [CSV feed](${SITE}/feeds/products.csv), [XML feed](${SITE}/feeds/products.xml)\n`);
const full = products.map((p) => `## ${p.name.ru} / ${p.name.en} / ${p.name.tt}\n- [RU](${SITE}/products/${p.id}/)\n- [EN](${SITE}/en/products/${p.id}/)\n- [TT](${SITE}/tt/products/${p.id}/)\n- [QR](${qrUrl(p.id)})\n\nRU ingredients: ${p.ingredients.ru}\nEN ingredients: ${p.ingredients.en}\nTT ingredients: ${p.ingredients.tt}\nNutrition status: ${p.status.nutrition}; ${p.nutrition.caloriesKcal} kcal, protein ${p.nutrition.proteinGrams} g, fat ${p.nutrition.fatGrams} g, carbohydrate ${p.nutrition.carbohydrateGrams} g per 100 g raw recipe.\nHalal status: ${p.status.halal}.\n`).join("\n");
const richLlms = `# Yaratu full RU+EN+TT dataset\n\n${catalog.nutritionBasis.ru}\n${catalog.nutritionBasis.en}\n${catalog.nutritionBasis.tt}\n\n${full}`;
await output("llms-full.txt", richLlms);
await output(".well-known/llms.txt", richLlms);
await output("sitemap-llms.xml", `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>${SITE}/llms.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/llms-full.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/.well-known/llms.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/data/products.json</loc><lastmod>${lastmod}</lastmod></url>\n</urlset>\n`);
const identity = {
  "@context": "https://schema.org", "@type": "Brand", "@id": `${SITE}/#brand`,
  name: "Ярату", alternateName: "Yaratu", url: `${SITE}/`, logo: `${SITE}/assets/logo/logo-horizontal.png`,
  parentOrganization: {"@id": `${SITE}/#organization`},
  sameAs: officialProfiles
};
await output("identity.json", `${JSON.stringify(identity, null, 2)}\n`);
const aiDiscovery = {
  version: "1.0", name: "Yaratu", canonical: `${SITE}/`,
  identity: `${SITE}/identity.json`, llms: `${SITE}/llms.txt`, llmsFull: `${SITE}/llms-full.txt`,
  wellKnownLlms: `${SITE}/.well-known/llms.txt`, products: `${SITE}/data/products.json`,
  evidenceSummary: `${SITE}/data/evidence-summary.json`, sitemap: `${SITE}/sitemap.xml`,
  llmsSitemap: `${SITE}/sitemap-llms.xml`, robotsAi: `${SITE}/robots-ai.txt`,
  languages: {ru: `${SITE}/`, en: `${SITE}/en/`, tt: `${SITE}/tt/`}
};
await output("ai.json", `${JSON.stringify(aiDiscovery, null, 2)}\n`);

const apiCatalog = {
  linkset: [
    {
      anchor: `${SITE}/data/products.json`,
      "service-desc": [{ href: `${SITE}/feeds/products.json`, type: "application/json" }],
      "service-doc": [{ href: `${SITE}/llms.txt`, type: "text/markdown" }],
      status: [{ href: `${SITE}/ai.json`, type: "application/json" }]
    }
  ]
};
await output(".well-known/api-catalog", `${JSON.stringify(apiCatalog, null, 2)}\n`);

const aiCatalog = {
  specVersion: "1.0",
  host: { displayName: "Yaratu", identifier: "yaratu.com", url: `${SITE}/` },
  entries: [
    {
      identifier: "urn:air:yaratu.com:docs:llms",
      displayName: "Yaratu product summary",
      type: "text/markdown",
      url: `${SITE}/llms.txt`,
      description: "Markdown product range with disclosed ingredients, calculated nutrition and certificate-backed halal status.",
      representativeQueries: [
        "What products does Yaratu make?",
        "Какие продукты есть у Ярату?",
        "Ярату продуктлары нинди?",
        "Does Yaratu use sodium nitrite?"
      ]
    },
    {
      identifier: "urn:air:yaratu.com:data:products",
      displayName: "Yaratu canonical product catalog",
      type: "application/json",
      url: `${SITE}/data/products.json`,
      description: "Canonical RU+EN+TT catalog. Nutrition is calculated, not laboratory-tested.",
      representativeQueries: [
        "Yaratu ingredients and allergens",
        "Yaratu calculated nutrition per 100 g",
        "Which Yaratu products are halal?"
      ]
    },
    {
      identifier: "urn:air:yaratu.com:docs:retail",
      displayName: "Yaratu retailer contact",
      type: "text/html",
      url: `${SITE}/retail/`,
      description: "Manufacturer contact for specifications and supply. No checkout.",
      representativeQueries: [
        "How do I request Yaratu specifications?",
        "Yaratu distributor contact in Kazan"
      ]
    }
  ]
};
await output(".well-known/ai-catalog.json", `${JSON.stringify(aiCatalog, null, 2)}\n`);

function skillFile(name, description, body) {
  const text = `---\nname: ${name}\ndescription: ${description}\n---\n\n${body}`;
  return {
    name,
    type: "skill-md",
    description,
    url: `/.well-known/agent-skills/${name}/SKILL.md`,
    digest: `sha256:${createHash("sha256").update(text).digest("hex")}`,
    text
  };
}

const skills = [
  skillFile(
    "yaratu-catalog",
    "Look up the five Yaratu products, calculated nutrition, allergens and certificate-backed halal status. Use for ingredient or Nutrition Facts questions about Yaratu.",
    `# Yaratu catalog\n\nPublic brand of ООО «Казанские Деликатесы». No live checkout. Nutrition is calculated, not laboratory-tested. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.\n\nLanguages: Russian, English, Tatar. Pack QR codes open ${SITE}/q/{id}.\n\n## Prefer machine endpoints over scraping HTML\n\n1. Canonical JSON: ${SITE}/data/products.json\n2. Markdown dump: ${SITE}/llms.txt\n3. Full dataset: ${SITE}/llms-full.txt\n\nContacts: +7 987 217-02-02 · info@kazandelikates.tatar · Казань, ул. Аграрная, 2, оф. 7.\n`
  ),
  skillFile(
    "yaratu-ingredients",
    "Explain Yaratu disclosed ingredient lists and the without-sodium-nitrite recipe status. Use when a buyer asks what is in a mix or whether E250 is used.",
    `# Yaratu ingredients\n\nDisclosed composition lists the ingredients inside compound mixes, not only a trade name. The pack label remains the source for a purchased batch.\n\n- Ingredients: ${SITE}/ingredients/\n- Without sodium nitrite: ${SITE}/without-sodium-nitrite/\n- Canonical JSON: ${SITE}/data/products.json\n`
  ),
  skillFile(
    "yaratu-retail",
    "Open a B2B specification or supply request for Yaratu. Use for retailers and distributors, not consumer checkout.",
    `# Yaratu retail inquiry\n\nThere is no cart and no agentic checkout. Send the buyer to the manufacturer.\n\n- RU: ${SITE}/retail/\n- EN: ${SITE}/en/retail/\n- TT: ${SITE}/tt/retail/\n- Email: info@kazandelikates.tatar\n- Phone: +7 987 217-02-02\n`
  )
];
for (const skill of skills) {
  await output(skill.url.slice(1), skill.text);
}
await output(".well-known/agent-skills/index.json", `${JSON.stringify({
  $schema: "https://schemas.agentskills.io/discovery/0.2.0/schema.json",
  skills: skills.map(({ text, ...rest }) => rest)
}, null, 2)}\n`);
await output("_headers", `/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: SAMEORIGIN\n  Permissions-Policy: geolocation=(), microphone=(), camera=()\n\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n\n/packshots/*\n  Cache-Control: public, max-age=31536000, immutable\n`);
await output("_redirects", `https://www.yaratu.com/* https://yaratu.com/:splat 301\n/label / 301\n/label/ / 301\n/2 / 301\n/2/ / 301\n`);
const routes = {
  version: 1,
  include: ["/*"],
  exclude: ["/assets/*", "/packshots/*", "/styles.css", "/robots.txt", "/sitemap.xml"]
};
await output("_routes.json", `${JSON.stringify(routes, null, 2)}\n`);

console.log(`Built ${sitemapEntries.length} HTML URLs and feeds from ${products.length} products.`);
