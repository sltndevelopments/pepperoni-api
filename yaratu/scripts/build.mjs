import { createHash } from "node:crypto";
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
  ...products.flatMap((p) => [p.image.slice(1), p.image.replace(/\.jpg$/, "-800.jpg").slice(1)])
];
for (const file of copyAllowlist) await copy(file);

const t = {
  ru: {
    home: "Главная", products: "Продукты", retail: "Для закупщиков", ingredients: "Раскрытый состав",
    nitrite: "Без нитрита", hero: "Любовь начинается со вкуса",
    lead: "Ярату — мясной бренд ООО «Казанские Деликатесы»: пять варёных продуктов из Казани без нитрита натрия, с комплексными добавками, раскрытыми до отдельных ингредиентов. Для магазинов и покупателей, которым нужен проверяемый состав.",
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
    lead: "Yaratu is the meat brand of Kazan Delicacies: five cooked products from Kazan without sodium nitrite, with every compound mix listed ingredient by ingredient. For retailers and shoppers who need a checkable recipe.",
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

const nutritionText = {
  ru: {
    kicker: "Nutrition Facts",
    title: "Пищевая ценность",
    basis: "На 100 г",
    energy: "Энергетическая ценность",
    calories: "Калории",
    fat: "Жиры",
    saturated: "Насыщенные жиры",
    carbs: "Углеводы",
    protein: "Белки",
    note: "Расчёт по текущей рецептуре; не лабораторный протокол."
  },
  en: {
    kicker: "Nutrition Facts",
    title: "Nutrition Facts",
    basis: "Per 100 g",
    energy: "Energy",
    calories: "Calories",
    fat: "Total Fat",
    saturated: "Saturated Fat",
    carbs: "Total Carbohydrate",
    protein: "Protein",
    note: "Calculated from the current recipe; not laboratory-tested."
  }
};

function nutritionFacts(product, lang, compact = false) {
  const copy = nutritionText[lang];
  const nutrition = product.nutrition;
  const kcal = formatNumber(nutrition.caloriesKcal, lang);
  const kj = formatNumber(Math.round(nutrition.caloriesKcal * 4.184), lang);
  const amount = (value) => `${formatNumber(value, lang)} ${grams(lang)}`;
  return `<aside class="nutrition-facts${compact ? " nutrition-facts--compact" : ""}" aria-label="${h(copy.title)}">
<div class="nutrition-facts__kicker">${h(copy.kicker)}</div>
<div class="nutrition-facts__title">${h(copy.title)}</div>
<div class="nutrition-facts__basis">${h(copy.basis)}</div>
<div class="nutrition-facts__rule nutrition-facts__rule--heavy"></div>
<div class="nutrition-facts__energy"><span>${h(copy.energy)}</span><strong>${kcal} ${t[lang].kcal} / ${kj} kJ</strong></div>
<div class="nutrition-facts__calories"><span>${h(copy.calories)}</span><strong>${kcal}</strong></div>
<div class="nutrition-facts__rule nutrition-facts__rule--medium"></div>
<div class="nutrition-facts__row nutrition-facts__row--major"><span>${h(copy.fat)}</span><strong>${amount(nutrition.fatGrams)}</strong></div>
<div class="nutrition-facts__row nutrition-facts__row--indent"><span>${h(copy.saturated)}</span><strong>${amount(nutrition.saturatedFatGrams)}</strong></div>
<div class="nutrition-facts__row nutrition-facts__row--major"><span>${h(copy.carbs)}</span><strong>${amount(nutrition.carbohydrateGrams)}</strong></div>
<div class="nutrition-facts__row nutrition-facts__row--major"><span>${h(copy.protein)}</span><strong>${amount(nutrition.proteinGrams)}</strong></div>
<div class="nutrition-facts__rule nutrition-facts__rule--medium"></div>
<p class="nutrition-facts__note">${h(copy.note)}</p>
</aside>`;
}

function markdownPath(lang, slug = "") {
  if (!slug) return lang === "ru" ? "/index.md" : "/en/index.md";
  return lang === "ru" ? `/${slug}.md` : `/en/${slug}.md`;
}

function homeMarkdown(lang) {
  const L = t[lang];
  const lines = products.map((p) => {
    const n = p.nutrition;
    return `- [${p.name[lang]}](${absolute(pagePath(lang, `products/${p.id}`))}): ${p.summary[lang]} ${formatNumber(n.caloriesKcal, lang)} ${L.kcal}, ${formatNumber(n.proteinGrams, lang)} ${grams(lang)} ${L.protein}. ${p.claims.halal ? L.halal : L.noHalal}.`;
  });
  return `# ${L.hero}\n\n${L.lead}\n\n## ${L.range}\n\n${L.nutritionNote}\n\n${lines.join("\n")}\n\n- [${L.ingredients}](${absolute(pagePath(lang, "ingredients"))})\n- [${L.nitrite}](${absolute(pagePath(lang, "without-sodium-nitrite"))})\n- [${L.retail}](${absolute(pagePath(lang, "retail"))})\n- [llms.txt](${SITE}/llms.txt)\n- [products.json](${SITE}/data/products.json)\n`;
}

function productMarkdown(product, lang) {
  const L = t[lang];
  const n = product.nutrition;
  return `# ${product.name[lang]}\n\n${product.summary[lang]}\n\n- ${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}\n- ${product.claims.halal ? L.halal : L.noHalal}\n- ${L.nitrite}\n\n## ${L.composition}\n\n${product.ingredients[lang]}\n\n**${L.allergens}:** ${product.allergens[lang]}\n\n## ${L.nutrition}\n\n- ${L.kcal}: ${formatNumber(n.caloriesKcal, lang)}\n- ${L.protein}: ${formatNumber(n.proteinGrams, lang)} ${grams(lang)}\n- ${L.fat}: ${formatNumber(n.fatGrams, lang)} ${grams(lang)}\n- ${L.carbs}: ${formatNumber(n.carbohydrateGrams, lang)} ${grams(lang)}\n\n${L.nutritionNote}\n`;
}

function pageMarkdown(lang, kind) {
  if (kind === "retail") {
    return lang === "ru"
      ? `# Yaratu для магазинов и дистрибьюторов\n\nЗапросите актуальные спецификации, фасовки, документы и условия поставки напрямую у производителя.\n\n- ООО «Казанские Деликатесы»\n- г. Казань, ул. Аграрная, д. 2, оф. 7\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`
      : `# Yaratu for retailers and distributors\n\nRequest current specifications, pack formats, documents and supply terms directly from the manufacturer.\n\n- Kazan Delicacies LLC\n- 2 Agrarnaya Street, office 7, Kazan, Russia\n- +7 987 217-02-02\n- info@kazandelikates.tatar\n`;
  }
  return lang === "ru"
    ? (kind === "ingredients"
      ? `# Что значит раскрытый состав?\n\nРаскрытый состав перечисляет не только название комплексной смеси, но и входящие в неё ингредиенты. Статус состава — recipe-sourced; маркировка партии остаётся приоритетным источником.\n`
      : `# Что значит «без нитрита натрия»?\n\nВ текущих рецептурах пяти продуктов Yaratu нитрит натрия E250 не используется. Это статус рецептуры, не лабораторное утверждение.\n`)
    : (kind === "ingredients"
      ? `# What does a disclosed ingredient list mean?\n\nA disclosed list names the ingredients inside compound mixes instead of showing only a trade name. The pack label remains the primary source for a purchased batch.\n`
      : `# What does “without sodium nitrite” mean?\n\nSodium nitrite E250 is not used in the current recipes of the five Yaratu products. Nutrition figures are calculated, not laboratory-tested.\n`);
}

function alternates(slug) {
  const ru = pagePath("ru", slug);
  const en = pagePath("en", slug);
  return `<link rel="alternate" hreflang="ru" href="${absolute(ru)}"><link rel="alternate" hreflang="en" href="${absolute(en)}"><link rel="alternate" hreflang="x-default" href="${absolute(ru)}">`;
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

function shell({ lang, slug = "", title, description, body, structured, extraHead = "" }) {
  const L = t[lang];
  const canonical = absolute(pagePath(lang, slug));
  const other = lang === "ru" ? pagePath("en", slug) : pagePath("ru", slug);
  return `<!doctype html>
<html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${h(title)}</title><meta name="description" content="${h(description)}"><meta name="theme-color" content="#2F391C">
<meta name="yandex-verification" content="1817223863cbfebb">
<link rel="canonical" href="${canonical}">${alternates(slug)}
<link rel="alternate" type="text/markdown" href="${markdownPath(lang, slug)}" title="Markdown for agents">
<link rel="api-catalog" href="/.well-known/api-catalog" type="application/linkset+json">
<link rel="ai-catalog" href="/.well-known/ai-catalog.json" type="application/json">
<meta property="og:type" content="website"><meta property="og:url" content="${canonical}"><meta property="og:title" content="${h(title)}"><meta property="og:description" content="${h(description)}"><meta property="og:image" content="${SITE}/assets/logo/logo-horizontal.png">
<link rel="preload" href="/styles.css" as="style">
${extraHead}<link rel="stylesheet" href="/styles.css">${schemas(structured || [])}</head>
<body><a class="skip-link" href="#main">${lang === "ru" ? "К содержанию" : "Skip to content"}</a>
<header class="nav"><div class="wrap nav__inner"><a class="nav__logo" href="${pagePath(lang)}"><img src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"></a>
<nav class="nav__links" aria-label="${L.products}"><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang, "ingredients")}">${L.ingredients}</a><a href="${pagePath(lang, "without-sodium-nitrite")}">${L.nitrite}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a></nav>
<details class="nav__menu"><summary>${lang === "ru" ? "Меню" : "Menu"}</summary><nav aria-label="${lang === "ru" ? "Мобильное меню" : "Mobile menu"}"><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang, "ingredients")}">${L.ingredients}</a><a href="${pagePath(lang, "without-sodium-nitrite")}">${L.nitrite}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a><a href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a></nav></details>
<a class="nav__cta" href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a></div></header>
<main id="main">${body}</main>
<footer class="footer"><div class="wrap footer__inner"><div><img class="footer__logo" src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"><p>© 2026 Yaratu · ${L.footer}</p></div><nav><a href="${pagePath(lang, "retail")}">${L.retail}</a><a href="/privacy.html">${lang === "ru" ? "Политика ПДн" : "Privacy"}</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a href="tel:+79872170202">+7 987 217-02-02</a></nav></div></footer></body></html>`;
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
  const L = t[lang];
  return `<article class="product"><div class="product__stage">${packshot(product, lang, ' loading="lazy"', { srcset: false })}</div>
<div class="product__intro"><div class="product__intro-top"><span class="product__index">${String(index + 1).padStart(2, "0")}</span><div class="product__tags"><span class="tag">${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${product.claims.halal ? L.halal : L.noHalal}</span></div></div>
<h3>${h(product.name[lang])}</h3><p>${h(product.summary[lang])}</p>
<a class="btn btn--outline" href="${pagePath(lang, `products/${product.id}`)}">${L.see}</a></div>
<div class="product__passport"><div class="product__passport-copy"><span class="product__passport-eyebrow">${L.composition}</span><p class="product__compose">${h(product.ingredients[lang])}</p><p class="product__allergens"><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p></div><div class="product__label">${nutritionFacts(product, lang, true)}</div></div></article>`;
}

function homeFaqs(lang) {
  return lang === "ru" ? [
    ["Что такое Ярату?", "Ярату — мясной бренд ООО «Казанские Деликатесы»: пять варёных продуктов из Казани без нитрита натрия и с составом, раскрытым до ингредиентов."],
    ["Для кого эта линейка?", "Для магазинов, дистрибьюторов и покупателей, которым нужен проверяемый состав, а не лозунг «чистый продукт»."],
    ["Где цены?", "Публичного потребительского прайса нет. Актуальные спецификации, фасовки и условия поставки запрашивают у производителя."],
    ["Вся линейка халяль?", "Нет. Халяль показывается по каждому SKU. На «Мраморной» халяль не заявлен."],
    ["КБЖУ лабораторные?", "Нет. Это расчёт по текущей рецептуре на 100 г сырьевой массы, не протокол испытаний."],
    ["Как запросить поставку?", "Напишите на info@kazandelikates.tatar или позвоните +7 987 217-02-02. Производитель в Казани, ул. Аграрная, 2, оф. 7."]
  ] : [
    ["What is Yaratu?", "Yaratu is the meat brand of Kazan Delicacies: five cooked products from Kazan without sodium nitrite and with compound mixes listed ingredient by ingredient."],
    ["Who is it for?", "Retailers, distributors and shoppers who need a checkable recipe rather than a clean-label slogan."],
    ["Where is the pricing?", "There is no public consumer price list. Specifications, pack formats and supply terms are provided by the manufacturer on request."],
    ["Is the whole range halal?", "No. Halal is shown per SKU. Mramornaya has no halal claim."],
    ["Is nutrition laboratory-tested?", "No. Figures are calculated from the current recipe per 100 g of raw mass, not a lab protocol."],
    ["How do I request supply?", "Email info@kazandelikates.tatar or call +7 987 217-02-02. The manufacturer is in Kazan, 2 Agrarnaya Street, office 7."]
  ];
}

function home(lang) {
  const L = t[lang];
  const items = products.map((p, i) => ({"@type": "ListItem", position: i + 1, url: absolute(pagePath(lang, `products/${p.id}`)), name: p.name[lang]}));
  const faqs = homeFaqs(lang);
  const faqPage = {"@type": "FAQPage", mainEntity: faqs.map(([name, text]) => ({"@type": "Question", name, acceptedAnswer: {"@type": "Answer", text}}))};
  const structured = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": `${SITE}/#website`, url: `${SITE}/`, name: "Yaratu", inLanguage: lang},
    org, brand, faqPage, {"@type": "ItemList", name: L.range, itemListElement: items}
  ]};
  const facts = lang === "ru"
    ? [
      ["01", "Без нитрита натрия", "Статус относится к пяти проверенным текущим рецептурам."],
      ["02", "Состав без сокращений", "Комплексные смеси раскрыты до входящих ингредиентов."],
      ["03", "Халяль — по продукту", "Статус показывается отдельно и не переносится на весь ассортимент."]
    ]
    : [
      ["01", "No sodium nitrite", "The status applies to the five reviewed current recipes."],
      ["02", "No ingredient shortcuts", "Compound mixes are disclosed ingredient by ingredient."],
      ["03", "Product-specific halal", "Halal status is shown per product, never assumed range-wide."]
    ];
  const body = `<section class="hero"><div class="hero__plane"><div class="hero__mesh"></div><div class="hero__pattern"></div><div class="hero__glow hero__glow--warm"></div><div class="hero__orb"></div><span class="hero__star hero__star--a"></span><span class="hero__star hero__star--b"></span><span class="hero__star hero__star--c"></span><img class="hero__mark" src="/assets/logo/sign-white.svg" alt=""></div><div class="hero__shade"></div>
<div class="wrap hero__layout"><div class="hero__content"><img class="hero__brand" src="/assets/logo/logo-horizontal-white.svg" alt="Yaratu" width="214" height="40"><h1>${L.hero}</h1><p class="lede">${L.lead}</p><div class="hero__actions"><a class="btn btn--solid" href="#products">${L.products}</a><a class="btn btn--ghost" href="${pagePath(lang, "retail")}">${L.retail}</a></div><div class="hero__badges"><span>${lang === "ru" ? "5 продуктов" : "5 products"}</span><span>${L.ingredients}</span><span>${L.nitrite}</span></div></div></div></section>
<section class="trust"><div class="wrap"><div class="facts">${facts.map(([number, title, text]) => `<article><span>${number}</span><h2>${h(title)}</h2><p>${h(text)}</p></article>`).join("")}</div></div></section>
<section id="products"><div class="wrap"><div class="section-head"><span class="eyebrow">${L.products}</span><h2>${L.range}</h2><p>${L.nutritionNote}</p></div>
<table class="range-table"><caption>${lang === "ru" ? "Ассортимент без розничных цен" : "Range without consumer prices"}</caption><thead><tr><th>${lang === "ru" ? "Продукт" : "Product"}</th><th>${L.weight}</th><th>${L.nitrite}</th><th>${lang === "ru" ? "Халяль" : "Halal"}</th></tr></thead><tbody>${products.map((p) => `<tr><td><a href="${pagePath(lang, `products/${p.id}`)}">${h(p.name[lang])}</a></td><td>${formatNumber(p.netWeight.value, lang)} ${grams(lang)}</td><td>${lang === "ru" ? "Не используется" : "Not used"}</td><td>${p.claims.halal ? L.halal : L.noHalal}</td></tr>`).join("")}</tbody></table>
<div class="products">${products.map((p, i) => card(p, lang, i)).join("")}</div></div></section>
<section id="faq"><div class="wrap"><div class="section-head"><span class="eyebrow">FAQ</span><h2>${lang === "ru" ? "Короткие ответы" : "Short answers"}</h2><p>${lang === "ru" ? "Цены и оферта на сайте не публикуются." : "No prices or offers are published on this site."}</p></div><div class="faq">${faqs.map(([q, a]) => `<details><summary>${h(q)}</summary><p>${h(a)}</p></details>`).join("")}</div></div></section>`;
  return shell({
    lang,
    title: lang === "ru" ? "Ярату — раскрытый состав, без нитрита натрия" : "Yaratu — disclosed ingredients, no sodium nitrite",
    description: L.lead,
    body,
    structured,
  });
}

function productPage(product, lang) {
  const L = t[lang], slug = `products/${product.id}`;
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
  const body = `<section class="product-page-hero"><div class="wrap split"><div class="product__stage">${packshot(product, lang, ' fetchpriority="high"')}</div><div class="section-head"><span class="eyebrow">${h(product.kind[lang])}</span><h1>${h(product.name[lang])}</h1><p class="lede">${h(product.summary[lang])}</p><div class="product__tags"><span class="tag">${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${product.claims.halal ? L.halal : L.noHalal}</span><span class="tag">${L.nitrite}</span></div><a class="btn btn--olive" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20${encodeURIComponent(product.id)}">${L.contact}</a></div></div></section>
<section class="band-dim"><div class="wrap nutrition-layout"><div class="nutrition-layout__copy"><div class="section-head"><span class="eyebrow">${L.composition}</span><h2>${L.composition}</h2><p>${h(product.ingredients[lang])}</p><p><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p></div><p class="note">${L.nutritionNote}</p></div><div class="product__label product__label--large">${nutritionFacts(product, lang)}</div></div></section>
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

for (const lang of ["ru", "en"]) {
  await output(lang === "ru" ? "index.html" : "en/index.html", home(lang));
  await output(lang === "ru" ? "index.md" : "en/index.md", homeMarkdown(lang));
  await output(`${lang === "ru" ? "" : "en/"}retail/index.html`, retailPage(lang));
  await output(`${lang === "ru" ? "" : "en/"}retail.md`, pageMarkdown(lang, "retail"));
  await output(`${lang === "ru" ? "" : "en/"}ingredients/index.html`, answerPage(lang, "ingredients"));
  await output(`${lang === "ru" ? "" : "en/"}ingredients.md`, pageMarkdown(lang, "ingredients"));
  await output(`${lang === "ru" ? "" : "en/"}without-sodium-nitrite/index.html`, answerPage(lang, "nitrite"));
  await output(`${lang === "ru" ? "" : "en/"}without-sodium-nitrite.md`, pageMarkdown(lang, "nitrite"));
  for (const product of products) {
    await output(`${lang === "ru" ? "" : "en/"}products/${product.id}/index.html`, productPage(product, lang));
    await output(`${lang === "ru" ? "" : "en/"}products/${product.id}.md`, productMarkdown(product, lang));
  }
}
await output("privacy.html", privacyPage());

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
await output("robots.txt", `User-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\nAllow: /.well-known/api-catalog\nAllow: /.well-known/ai-catalog.json\nAllow: /.well-known/agent-skills/\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\n\nSitemap: ${SITE}/sitemap.xml\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("robots-ai.txt", `# Yaratu AI crawler directives\nUser-agent: *\nContent-Signal: ai-train=yes, search=yes, ai-input=yes\nAllow: /\n\nUser-agent: GPTBot\nAllow: /\nUser-agent: ChatGPT-User\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\n\nSitemap: ${SITE}/sitemap-llms.xml\n`);
await output("ai.txt", `Yaratu permits indexing of public pages and feeds for search and AI retrieval.\nCanonical product data: ${SITE}/data/products.json\nHuman-readable summary: ${SITE}/llms.txt\n`);
await output("989787de78c652b55e6887550582b6f6.txt", "989787de78c652b55e6887550582b6f6\n");

const productLines = products.map((p) => `- [${p.name.ru}](${SITE}/products/${p.id}/) / [${p.name.en}](${SITE}/en/products/${p.id}/)`).join("\n");
await output("llms.txt", `# Yaratu / Ярату\n\nRU+EN product range with disclosed ingredients. Nutrition is calculated, not laboratory-tested. Halal is product-specific; no halal claim is made for Mramornaya.\n\n${productLines}\n\n- [RU retail](${SITE}/retail/)\n- [EN retail](${SITE}/en/retail/)\n- [Canonical JSON](${SITE}/data/products.json)\n- [JSON feed](${SITE}/feeds/products.json), [CSV feed](${SITE}/feeds/products.csv), [XML feed](${SITE}/feeds/products.xml)\n`);
const full = products.map((p) => `## ${p.name.ru} / ${p.name.en}\n- [RU](${SITE}/products/${p.id}/)\n- [EN](${SITE}/en/products/${p.id}/)\n\nRU ingredients: ${p.ingredients.ru}\nEN ingredients: ${p.ingredients.en}\nNutrition status: ${p.status.nutrition}; ${p.nutrition.caloriesKcal} kcal, protein ${p.nutrition.proteinGrams} g, fat ${p.nutrition.fatGrams} g, carbohydrate ${p.nutrition.carbohydrateGrams} g per 100 g raw recipe.\nHalal status: ${p.status.halal}.\n`).join("\n");
const richLlms = `# Yaratu full RU+EN dataset\n\n${catalog.nutritionBasis.ru}\n${catalog.nutritionBasis.en}\n\n${full}`;
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
  languages: {ru: `${SITE}/`, en: `${SITE}/en/`}
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
      description: "Markdown product range with disclosed ingredients and product-specific halal status.",
      representativeQueries: [
        "What products does Yaratu make?",
        "Какие продукты есть у Ярату?",
        "Does Yaratu use sodium nitrite?"
      ]
    },
    {
      identifier: "urn:air:yaratu.com:data:products",
      displayName: "Yaratu canonical product catalog",
      type: "application/json",
      url: `${SITE}/data/products.json`,
      description: "Canonical RU+EN catalog. Nutrition is calculated, not laboratory-tested.",
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
    "Look up the five Yaratu products, calculated nutrition, allergens and product-specific halal status. Use for ingredient or Nutrition Facts questions about Yaratu.",
    `# Yaratu catalog\n\nPublic brand of ООО «Казанские Деликатесы». No live checkout. Nutrition is calculated, not laboratory-tested. Halal is product-specific; do not claim it for Mramornaya.\n\n## Prefer machine endpoints over scraping HTML\n\n1. Canonical JSON: ${SITE}/data/products.json\n2. Markdown dump: ${SITE}/llms.txt\n3. Full dataset: ${SITE}/llms-full.txt\n\nContacts: +7 987 217-02-02 · info@kazandelikates.tatar · Казань, ул. Аграрная, 2, оф. 7.\n`
  ),
  skillFile(
    "yaratu-ingredients",
    "Explain Yaratu disclosed ingredient lists and the without-sodium-nitrite recipe status. Use when a buyer asks what is in a mix or whether E250 is used.",
    `# Yaratu ingredients\n\nDisclosed composition lists the ingredients inside compound mixes, not only a trade name. The pack label remains the source for a purchased batch.\n\n- Ingredients: ${SITE}/ingredients/\n- Without sodium nitrite: ${SITE}/without-sodium-nitrite/\n- Canonical JSON: ${SITE}/data/products.json\n`
  ),
  skillFile(
    "yaratu-retail",
    "Open a B2B specification or supply request for Yaratu. Use for retailers and distributors, not consumer checkout.",
    `# Yaratu retail inquiry\n\nThere is no cart and no agentic checkout. Send the buyer to the manufacturer.\n\n- RU: ${SITE}/retail/\n- EN: ${SITE}/en/retail/\n- Email: info@kazandelikates.tatar\n- Phone: +7 987 217-02-02\n`
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
await output("_redirects", `https://www.yaratu.com/* https://yaratu.com/:splat 301\n/label / 301\n/label/ / 301\n`);
await output("_routes.json", `${JSON.stringify({version: 1, include: ["/*"], exclude: ["/assets/*", "/packshots/*", "/styles.css", "/robots.txt", "/sitemap.xml"]}, null, 2)}\n`);

console.log(`Built ${sitemapUrls.length} HTML URLs and feeds from ${products.length} products.`);
