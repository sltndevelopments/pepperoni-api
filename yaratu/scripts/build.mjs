import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { absolute, escapeHtml as h, jsonLd, loadData, pagePath, SITE } from "./lib.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const dist = join(root, "site/dist");
const { products: catalog } = await loadData();
const products = catalog.products;
const lastmod = catalog.lastModified;

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
  "assets/logo/logo-horizontal-black.svg",
  "assets/logo/logo-horizontal-white.svg",
  "assets/logo/sign-white.svg",
  ...products.map((p) => p.image.slice(1))
];
for (const file of copyAllowlist) await copy(file);

const t = {
  ru: {
    home: "Главная", products: "Продукты", retail: "Для закупщиков", ingredients: "Раскрытый состав",
    nitrite: "Без нитрита", hero: "Любовь начинается со вкуса",
    lead: "Мясные продукты без нитрита натрия. Комплексные добавки раскрыты до отдельных ингредиентов.",
    range: "Пять продуктов. Состав без сокращений.", see: "Смотреть продукт", calculated: "Расчётные КБЖУ",
    halal: "Халяль подтверждён", noHalal: "Халяль не заявлен", weight: "Масса нетто",
    composition: "Состав", allergens: "Аллергены", nutrition: "КБЖУ на 100 г",
    nutritionNote: "Расчётный ориентир на 100 г сырьевой массы; не лабораторное значение.",
    kcal: "ккал", protein: "белки", fat: "жиры", carbs: "углеводы",
    contact: "Запросить спецификации", footer: "бренд ООО «Казанские Деликатесы»",
    status: "Статус данных", evidence: "Рецептура и состав проверены по внутренним документам.",
    language: "English"
  },
  en: {
    home: "Home", products: "Products", retail: "For retailers", ingredients: "Disclosed ingredients",
    nitrite: "Without nitrite", hero: "Love begins with taste",
    lead: "Meat products made without sodium nitrite. Compound ingredients are disclosed ingredient by ingredient.",
    range: "Five products. No ingredient-list shortcuts.", see: "View product", calculated: "Calculated nutrition",
    halal: "Halal verified", noHalal: "No halal claim", weight: "Net weight",
    composition: "Ingredients", allergens: "Allergens", nutrition: "Nutrition per 100 g",
    nutritionNote: "Calculated estimate per 100 g of raw recipe; not a laboratory value.",
    kcal: "kcal", protein: "protein", fat: "fat", carbs: "carbohydrate",
    contact: "Request specifications", footer: "a brand of Kazan Delicacies LLC",
    status: "Data status", evidence: "Recipe and composition reviewed against internal documents.",
    language: "Русский"
  }
};

const formatNumber = (value, lang) => new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US", {
  maximumFractionDigits: 1
}).format(value);
const grams = (lang) => lang === "ru" ? "г" : "g";

function alternates(slug) {
  const ru = pagePath("ru", slug);
  const en = pagePath("en", slug);
  return `<link rel="alternate" hreflang="ru" href="${absolute(ru)}"><link rel="alternate" hreflang="en" href="${absolute(en)}"><link rel="alternate" hreflang="x-default" href="${absolute(ru)}">`;
}

function schemas(items) {
  return `<script type="application/ld+json">${jsonLd(items)}</script>`;
}

function shell({ lang, slug = "", title, description, body, structured }) {
  const L = t[lang];
  const canonical = absolute(pagePath(lang, slug));
  const other = lang === "ru" ? pagePath("en", slug) : pagePath("ru", slug);
  return `<!doctype html>
<html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${h(title)}</title><meta name="description" content="${h(description)}"><meta name="theme-color" content="#2F391C">
<meta name="yandex-verification" content="1817223863cbfebb">
<link rel="canonical" href="${canonical}">${alternates(slug)}
<meta property="og:type" content="website"><meta property="og:url" content="${canonical}"><meta property="og:title" content="${h(title)}"><meta property="og:description" content="${h(description)}"><meta property="og:image" content="${SITE}/assets/logo/logo-horizontal.png">
<link rel="stylesheet" href="/styles.css">${schemas(structured || [])}</head>
<body><a class="skip-link" href="#main">${lang === "ru" ? "К содержанию" : "Skip to content"}</a>
<header class="nav"><div class="wrap nav__inner"><a class="nav__logo" href="${pagePath(lang)}"><img src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"></a>
<nav class="nav__links" aria-label="${L.products}"><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang, "ingredients")}">${L.ingredients}</a><a href="${pagePath(lang, "without-sodium-nitrite")}">${L.nitrite}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a></nav>
<details class="nav__menu"><summary>${lang === "ru" ? "Меню" : "Menu"}</summary><nav aria-label="${lang === "ru" ? "Мобильное меню" : "Mobile menu"}"><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang, "ingredients")}">${L.ingredients}</a><a href="${pagePath(lang, "without-sodium-nitrite")}">${L.nitrite}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a><a href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a></nav></details>
<a class="nav__cta" href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a></div></header>
<main id="main">${body}</main>
<footer class="footer"><div class="wrap footer__inner"><div><img class="footer__logo" src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu"><p>© 2026 Yaratu · ${L.footer}</p></div><nav><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a href="tel:+79872170202">+7 987 217-02-02</a></nav></div></footer></body></html>`;
}

const org = {
  "@type": "Organization", "@id": `${SITE}/#organization`, name: "ООО «Казанские Деликатесы»",
  alternateName: "Kazan Delicacies LLC", url: "https://pepperoni.tatar/", email: "info@kazandelikates.tatar",
  telephone: "+79872170202", address: {"@type": "PostalAddress", streetAddress: "ул. Аграрная, д. 2, оф. 7", addressLocality: "Казань", postalCode: "420061", addressCountry: "RU"}
};
const brand = {"@type": "Brand", "@id": `${SITE}/#brand`, name: "Ярату", alternateName: "Yaratu", logo: `${SITE}/assets/logo/logo-horizontal.png`};

function card(product, lang, index) {
  const L = t[lang], n = product.nutrition;
  return `<article class="product"><div class="product__stage"><img src="${product.image}" alt="${h(product.name[lang])}" width="1200" height="800" loading="lazy"></div>
<div class="product__intro"><div class="product__intro-top"><span class="product__index">${String(index + 1).padStart(2, "0")}</span><div class="product__tags"><span class="tag">${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${product.claims.halal ? L.halal : L.noHalal}</span></div></div>
<h3>${h(product.name[lang])}</h3><p>${h(product.summary[lang])}</p>
<div class="kbju"><div><strong>${formatNumber(n.caloriesKcal, lang)}</strong><span>${L.kcal}</span></div><div><strong>${formatNumber(n.proteinGrams, lang)}</strong><span>${L.protein}, ${grams(lang)}</span></div><div><strong>${formatNumber(n.fatGrams, lang)}</strong><span>${L.fat}, ${grams(lang)}</span></div><div><strong>${formatNumber(n.carbohydrateGrams, lang)}</strong><span>${L.carbs}, ${grams(lang)}</span></div></div>
<a class="btn btn--outline" href="${pagePath(lang, `products/${product.id}`)}">${L.see}</a></div></article>`;
}

function home(lang) {
  const L = t[lang];
  const items = products.map((p, i) => ({"@type": "ListItem", position: i + 1, url: absolute(pagePath(lang, `products/${p.id}`)), name: p.name[lang]}));
  const structured = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": `${SITE}/#website`, url: `${SITE}/`, name: "Yaratu", inLanguage: lang},
    org, brand, {"@type": "ItemList", name: L.range, itemListElement: items}
  ]};
  const body = `<section class="hero"><div class="hero__plane"><div class="hero__mesh"></div><div class="hero__pattern"></div><div class="hero__glow hero__glow--warm"></div><img class="hero__mark" src="/assets/logo/sign-white.svg" alt=""></div><div class="hero__shade"></div>
<div class="wrap hero__layout"><div class="hero__content"><img class="hero__brand" src="/assets/logo/logo-horizontal-white.svg" alt="Yaratu"><h1>${L.hero}</h1><p class="lede">${L.lead}</p><div class="hero__actions"><a class="btn btn--solid" href="#products">${L.products}</a><a class="btn btn--ghost" href="${pagePath(lang, "retail")}">${L.retail}</a></div></div></div></section>
<section id="products"><div class="wrap"><div class="section-head"><span class="eyebrow">${L.products}</span><h2>${L.range}</h2><p>${L.nutritionNote}</p></div><div class="products">${products.map((p, i) => card(p, lang, i)).join("")}</div></div></section>`;
  return shell({lang, title: lang === "ru" ? "Ярату — раскрытый состав, без нитрита натрия" : "Yaratu — disclosed ingredients, no sodium nitrite", description: L.lead, body, structured});
}

function productPage(product, lang) {
  const L = t[lang], n = product.nutrition, slug = `products/${product.id}`;
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
  const body = `<section><div class="wrap split"><div class="product__stage"><img src="${product.image}" alt="${h(product.name[lang])}" width="1200" height="800"></div><div class="section-head"><span class="eyebrow">${h(product.kind[lang])}</span><h1>${h(product.name[lang])}</h1><p>${h(product.summary[lang])}</p><div class="product__tags"><span class="tag">${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${product.claims.halal ? L.halal : L.noHalal}</span><span class="tag">${L.nitrite}</span></div></div></div></section>
<section class="band-dim"><div class="wrap"><div class="section-head"><span class="eyebrow">${L.composition}</span><h2>${L.composition}</h2><p>${h(product.ingredients[lang])}</p><p><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p></div>
<div class="contact-box"><h3>${L.nutrition}</h3><div class="kbju"><div><strong>${formatNumber(n.caloriesKcal, lang)}</strong><span>${L.kcal}</span></div><div><strong>${formatNumber(n.proteinGrams, lang)}</strong><span>${L.protein}, ${grams(lang)}</span></div><div><strong>${formatNumber(n.fatGrams, lang)}</strong><span>${L.fat}, ${grams(lang)}</span></div><div><strong>${formatNumber(n.carbohydrateGrams, lang)}</strong><span>${L.carbs}, ${grams(lang)}</span></div></div><p class="note">${L.nutritionNote}</p></div></div></section>
<section><div class="wrap"><div class="section-head"><span class="eyebrow">${L.status}</span><h2>${L.calculated}</h2><p>${L.evidence}</p><p><strong>nutrition:</strong> calculated · <strong>composition:</strong> recipe-sourced · <strong>halal:</strong> ${product.status.halal}</p></div></div></section>`;
  return shell({lang, slug, title: `${product.name[lang]} — Yaratu`, description: product.summary[lang], body, structured: {"@context": "https://schema.org", "@graph": [org, brand, productSchema, breadcrumb]}});
}

function answerPage(lang, kind) {
  const isIngredients = kind === "ingredients";
  const slug = isIngredients ? "ingredients" : "without-sodium-nitrite";
  const copy = lang === "ru"
    ? (isIngredients ? {
      title: "Что значит раскрытый состав?", answer: "Раскрытый состав перечисляет не только название комплексной смеси, но и входящие в неё ингредиенты.",
      detail: "На страницах пяти продуктов приведён текущий состав из рецептуры и спецификаций. Статус состава — recipe-sourced; маркировка партии остаётся приоритетным источником для покупателя.",
      q: "Где проверить состав конкретного продукта?", a: "На отдельной странице продукта и на его фактической упаковке."
    } : {
      title: "Что значит «без нитрита натрия»?", answer: "В текущих рецептурах пяти продуктов Yaratu нитрит натрия E250 не используется.",
      detail: "Утверждение относится к проверенным текущим рецептурам. Оно не означает отсутствие любых солей, специй или технологической обработки.",
      q: "Это лабораторное утверждение?", a: "Нет. Источник статуса — текущие рецептуры и спецификации; КБЖУ также остаются расчётными."
    })
    : (isIngredients ? {
      title: "What does a disclosed ingredient list mean?", answer: "A disclosed list names the ingredients inside compound mixes instead of showing only a trade name.",
      detail: "Each of the five product pages shows the current recipe-based ingredient list. It is marked as recipe-derived; the label on the actual pack remains the primary source for a purchased batch.",
      q: "Where can I check a specific product?", a: "Use its dedicated product page and check the physical pack."
    } : {
      title: "What does “without sodium nitrite” mean?", answer: "Sodium nitrite E250 is not used in the current recipes of the five Yaratu products.",
      detail: "The statement applies to the reviewed current recipes. It does not mean the products contain no salt, spices or processing.",
      q: "Is this a laboratory claim?", a: "No. The status comes from current recipes and specifications; nutrition figures are calculated too."
    });
  const faq = {"@type": "FAQPage", mainEntity: [
    {"@type": "Question", name: copy.title, acceptedAnswer: {"@type": "Answer", text: copy.answer}},
    {"@type": "Question", name: copy.q, acceptedAnswer: {"@type": "Answer", text: copy.a}}
  ]};
  const breadcrumb = {"@type": "BreadcrumbList", itemListElement: [
    {"@type": "ListItem", position: 1, name: t[lang].home, item: absolute(pagePath(lang))},
    {"@type": "ListItem", position: 2, name: copy.title, item: absolute(pagePath(lang, slug))}
  ]};
  const links = products.map((p) => `<li><a href="${pagePath(lang, `products/${p.id}`)}">${h(p.name[lang])}</a></li>`).join("");
  const body = `<section><div class="wrap"><div class="section-head"><span class="eyebrow">${t[lang][isIngredients ? "ingredients" : "nitrite"]}</span><h1>${copy.title}</h1><p class="lede">${copy.answer}</p></div><div class="contact-box"><p>${copy.detail}</p><h2>${copy.q}</h2><p>${copy.a}</p></div><ul class="checklist" style="margin-top:2rem">${links}</ul></div></section>`;
  return shell({lang, slug, title: `${copy.title} — Yaratu`, description: copy.answer, body, structured: {"@context": "https://schema.org", "@graph": [faq, breadcrumb]}});
}

function retailPage(lang) {
  const L = t[lang], slug = "retail";
  const ru = lang === "ru";
  const title = ru ? "Yaratu для магазинов и дистрибьюторов" : "Yaratu for retailers and distributors";
  const answer = ru ? "Запросите актуальные спецификации, фасовки, документы и условия поставки напрямую у производителя." : "Request current specifications, pack formats, documents and supply terms directly from the manufacturer.";
  const body = `<section><div class="wrap split"><div class="section-head"><span class="eyebrow">${L.retail}</span><h1>${title}</h1><p class="lede">${answer}</p><a class="btn btn--olive" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20specifications">${L.contact}</a></div><div class="contact-box"><h2>${ru ? "Контакты" : "Contact"}</h2><p>ООО «Казанские Деликатесы»<br>${ru ? "г. Казань, ул. Аграрная, д. 2, оф. 7" : "2 Agrarnaya Street, office 7, Kazan, Russia"}<br><a href="tel:+79872170202">+7 987 217-02-02</a><br><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a></p><p>${L.nutritionNote}</p></div></div></section>`;
  const breadcrumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
    {"@type": "ListItem", position: 1, name: L.home, item: absolute(pagePath(lang))},
    {"@type": "ListItem", position: 2, name: L.retail, item: absolute(pagePath(lang, slug))}
  ]};
  return shell({lang, slug, title, description: answer, body, structured: breadcrumb});
}

for (const lang of ["ru", "en"]) {
  await output(lang === "ru" ? "index.html" : "en/index.html", home(lang));
  await output(`${lang === "ru" ? "" : "en/"}retail/index.html`, retailPage(lang));
  await output(`${lang === "ru" ? "" : "en/"}ingredients/index.html`, answerPage(lang, "ingredients"));
  await output(`${lang === "ru" ? "" : "en/"}without-sodium-nitrite/index.html`, answerPage(lang, "nitrite"));
  for (const product of products) {
    await output(`${lang === "ru" ? "" : "en/"}products/${product.id}/index.html`, productPage(product, lang));
  }
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
  ["id", "name_ru", "name_en", "kind_ru", "kind_en", "net_weight_g", "ingredients_ru", "ingredients_en", "nutrition_status", "halal_status", "evidence_status"],
  ...products.map((p) => [p.id, p.name.ru, p.name.en, p.kind.ru, p.kind.en, p.netWeight.value, p.ingredients.ru, p.ingredients.en, p.status.nutrition, p.status.halal, p.status.evidence])
].map((row) => row.map(csvCell).join(",")).join("\n");
await output("feeds/products.csv", `${csv}\n`);
await output("feeds/products.json", `${JSON.stringify(publicProducts, null, 2)}\n`);
const xmlEscape = (v) => h(v).replaceAll("'", "&apos;");
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<products generated="${lastmod}" merchant="false">\n${products.map((p) => `  <product id="${p.id}"><name lang="ru">${xmlEscape(p.name.ru)}</name><name lang="en">${xmlEscape(p.name.en)}</name><netWeight unit="g">${p.netWeight.value}</netWeight><nutrition status="${p.status.nutrition}" basisGrams="100"/><halal status="${p.status.halal}"/></product>`).join("\n")}\n</products>\n`;
await output("feeds/products.xml", xml);

const urls = ["", "retail", "ingredients", "without-sodium-nitrite", ...products.map((p) => `products/${p.id}`)];
const sitemapUrls = ["ru", "en"].flatMap((lang) => urls.map((slug) => pagePath(lang, slug)));
const sitemapEntries = ["ru", "en"].flatMap((lang) => urls.map((slug) => {
  const url = pagePath(lang, slug);
  const ru = absolute(pagePath("ru", slug));
  const en = absolute(pagePath("en", slug));
  return `  <url><loc>${absolute(url)}</loc><lastmod>${lastmod}</lastmod><xhtml:link rel="alternate" hreflang="ru" href="${ru}"/><xhtml:link rel="alternate" hreflang="en" href="${en}"/><xhtml:link rel="alternate" hreflang="x-default" href="${ru}"/></url>`;
}));
await output("sitemap.xml", `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${sitemapEntries.join("\n")}\n</urlset>\n`);
await output("robots.txt", `User-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\n\nSitemap: ${SITE}/sitemap.xml\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("robots-ai.txt", `# Yaratu AI crawler directives\nUser-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\n\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("ai.txt", `Yaratu permits indexing of public pages and feeds for search and AI retrieval.\nCanonical product data: ${SITE}/data/products.json\nHuman-readable summary: ${SITE}/llms.txt\n`);
await output("989787de78c652b55e6887550582b6f6.txt", "989787de78c652b55e6887550582b6f6\n");

const productLines = products.map((p) => `- ${p.name.ru} / ${p.name.en}: ${SITE}/products/${p.id}/ | ${SITE}/en/products/${p.id}/`).join("\n");
await output("llms.txt", `# Yaratu / Ярату\n\n> RU+EN product range with disclosed ingredients. Nutrition is calculated, not laboratory-tested. Halal is product-specific; no halal claim is made for Mramornaya.\n\n${productLines}\n\n- RU retail: ${SITE}/retail/\n- EN retail: ${SITE}/en/retail/\n- Canonical JSON: ${SITE}/data/products.json\n- Non-merchant feeds: ${SITE}/feeds/products.json, ${SITE}/feeds/products.csv, ${SITE}/feeds/products.xml\n`);
const full = products.map((p) => `## ${p.name.ru} / ${p.name.en}\nURL: ${SITE}/products/${p.id}/\nEN: ${SITE}/en/products/${p.id}/\nRU ingredients: ${p.ingredients.ru}\nEN ingredients: ${p.ingredients.en}\nNutrition status: ${p.status.nutrition}; ${p.nutrition.caloriesKcal} kcal, protein ${p.nutrition.proteinGrams} g, fat ${p.nutrition.fatGrams} g, carbohydrate ${p.nutrition.carbohydrateGrams} g per 100 g raw recipe.\nHalal status: ${p.status.halal}.\n`).join("\n");
const richLlms = `# Yaratu full RU+EN dataset\n\n${catalog.nutritionBasis.ru}\n${catalog.nutritionBasis.en}\n\n${full}`;
await output("llms-full.txt", richLlms);
await output(".well-known/llms.txt", richLlms);
await output("sitemap-llms.xml", `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>${SITE}/llms.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/llms-full.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/.well-known/llms.txt</loc><lastmod>${lastmod}</lastmod></url>\n  <url><loc>${SITE}/data/products.json</loc><lastmod>${lastmod}</lastmod></url>\n</urlset>\n`);
const identity = {
  "@context": "https://schema.org", "@type": "Brand", "@id": `${SITE}/#brand`,
  name: "Ярату", alternateName: "Yaratu", url: `${SITE}/`, logo: `${SITE}/assets/logo/logo-horizontal.png`,
  parentOrganization: {"@id": `${SITE}/#organization`},
  sameAs: [`${SITE}/identity.json`, `${SITE}/ai.json`]
};
await output("identity.json", `${JSON.stringify(identity, null, 2)}\n`);
const aiDiscovery = {
  version: "1.0", name: "Yaratu", canonical: `${SITE}/`,
  identity: `${SITE}/identity.json`, llms: `${SITE}/llms.txt`, llmsFull: `${SITE}/llms-full.txt`,
  wellKnownLlms: `${SITE}/.well-known/llms.txt`, products: `${SITE}/data/products.json`,
  evidenceSummary: `${SITE}/data/evidence-summary.json`, sitemap: `${SITE}/sitemap.xml`,
  llmsSitemap: `${SITE}/sitemap-llms.xml`, robotsAi: `${SITE}/robots-ai.txt`,
  languages: {ru: `${SITE}/`, en: `${SITE}/en/`}
};
await output("ai.json", `${JSON.stringify(aiDiscovery, null, 2)}\n`);
await output("_headers", `/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  X-Frame-Options: SAMEORIGIN\n  Permissions-Policy: geolocation=(), microphone=(), camera=()\n\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n\n/packshots/*\n  Cache-Control: public, max-age=31536000, immutable\n`);
await output("_redirects", `https://www.yaratu.com/* https://yaratu.com/:splat 301\n/label / 301\n/label/ / 301\n`);
await output("_routes.json", `${JSON.stringify({version: 1, include: ["/*"], exclude: ["/assets/*", "/packshots/*", "/styles.css", "/robots.txt", "/sitemap.xml"]}, null, 2)}\n`);

console.log(`Built ${sitemapUrls.length} HTML URLs and feeds from ${products.length} products.`);
