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
    lead: "Пять мясных продуктов из Казани с раскрытым составом, без нитрита натрия и с пищевой ценностью, которую можно прочитать до покупки.",
    range: "Пять продуктов. Состав без сокращений.", see: "Смотреть продукт", calculated: "Расчётные КБЖУ",
    halal: "Халяль подтверждён", noHalal: "Халяль не заявлен", weight: "Масса нетто",
    composition: "Состав", allergens: "Аллергены", nutrition: "КБЖУ на 100 г",
    nutritionNote: "Расчётный ориентир на 100 г сырьевой массы; не лабораторное значение.",
    kcal: "ккал", protein: "белки", fat: "жиры", carbs: "углеводы",
    contact: "Запросить спецификации", footer: "бренд ООО «Казанские Деликатесы»",
    status: "Статус данных", evidence: "Рецептура и состав проверены по внутренним документам.",
    language: "English", advantages: "Преимущества", quality: "Контроль качества",
    contacts: "Контакты", connect: "Связаться"
  },
  en: {
    home: "Home", products: "Products", retail: "For retailers", ingredients: "Disclosed ingredients",
    nitrite: "Without nitrite", hero: "Love begins with taste",
    lead: "Five meat products from Kazan with disclosed ingredients, no sodium nitrite and nutrition you can read before you buy.",
    range: "Five products. No ingredient-list shortcuts.", see: "View product", calculated: "Calculated nutrition",
    halal: "Halal verified", noHalal: "No halal claim", weight: "Net weight",
    composition: "Ingredients", allergens: "Allergens", nutrition: "Nutrition per 100 g",
    nutritionNote: "Calculated estimate per 100 g of raw recipe; not a laboratory value.",
    kcal: "kcal", protein: "protein", fat: "fat", carbs: "carbohydrate",
    contact: "Request specifications", footer: "a brand of Kazan Delicacies LLC",
    status: "Data status", evidence: "Recipe and composition reviewed against internal documents.",
    language: "Русский", advantages: "Why Yaratu", quality: "Quality control",
    contacts: "Contact", connect: "Get in touch"
  }
};

const formatNumber = (value, lang) => new Intl.NumberFormat(lang === "ru" ? "ru-RU" : "en-US", {
  maximumFractionDigits: 1
}).format(value);
const grams = (lang) => lang === "ru" ? "г" : "g";

const dailyValue = { protein: 75, fat: 83, saturatedFat: 20, carbs: 365 };

function dailyPercent(value, key) {
  return `${Math.round((Number(value) / dailyValue[key]) * 100)}%`;
}

function nutritionFacts(product, lang, compact = false) {
  const n = product.nutrition;
  const ru = lang === "ru";
  const kcal = formatNumber(n.caloriesKcal, lang);
  const kj = formatNumber(Math.round(n.caloriesKcal * 4.184), lang);
  const g = grams(lang);
  const protein = formatNumber(n.proteinGrams, lang);
  const fat = formatNumber(n.fatGrams, lang);
  const sat = formatNumber(n.saturatedFatGrams, lang);
  const carbs = formatNumber(n.carbohydrateGrams, lang);
  const net = `${formatNumber(product.netWeight.value, lang)} ${g}`;
  const composition = h(product.ingredients[lang]).replace(/\.+$/, "");
  return `<aside class="nf-wrap${compact ? " nf-wrap--compact" : ""}" aria-label="${ru ? "Пищевая ценность" : "Nutrition Facts"}">
<div class="nf-name">${h(product.name[lang])}</div>
<div class="nf-card">
<p class="nf-card-title">${ru ? "Пищевая ценность" : "Nutrition Facts"}</p>
<p class="nf-basis">${ru ? "на 100 г" : "Per 100 g"}</p>
<div class="nf-net"><span>${ru ? "Масса нетто" : "Net Wt."}</span><span>${net}</span></div>
<div class="nf-line-10"></div>
<p class="nf-energy-cap">${ru ? "Калорийность / Энергетическая ценность" : "Calories / Energy"}</p>
<p class="nf-energy-line">${kcal} ${ru ? "ккал" : "kcal"} / ${kj} ${ru ? "кДж" : "kJ"}</p>
<div class="nf-cal-row"><span class="nf-cal-label">${ru ? "Калории" : "Calories"}</span><span class="nf-cal-val">${kcal}</span></div>
<div class="nf-line-5"></div>
<div class="nf-dv-head">${ru ? "% от суточной нормы*" : "% Daily Value*"}</div>
<div class="nf-row bold"><span>${ru ? `Белки ≥ ${protein} ${g}` : `Protein ${protein} ${g}`}</span><span>${dailyPercent(n.proteinGrams, "protein")}</span></div>
<div class="nf-row bold"><span>${ru ? `Всего жиров ≤ ${fat} ${g}` : `Total Fat ${fat} ${g}`}</span><span>${dailyPercent(n.fatGrams, "fat")}</span></div>
<div class="nf-row indent"><span>${ru ? `Насыщенные жиры ${sat} ${g}` : `Saturated Fat ${sat} ${g}`}</span><span>${dailyPercent(n.saturatedFatGrams, "saturatedFat")}</span></div>
<div class="nf-row bold"><span>${ru ? `Углеводы ≤ ${carbs} ${g}` : `Total Carbohydrate ${carbs} ${g}`}</span><span>${dailyPercent(n.carbohydrateGrams, "carbs")}</span></div>
<div class="nf-line-5"></div>
<p class="nf-foot">${ru ? "* % от рекомендуемого уровня суточного потребления по ТР ТС 022/2011. 2500 ккал для общих рекомендаций. Расчёт по текущей рецептуре, не лабораторный протокол." : "* Percent of the recommended daily intake under TR CU 022/2011. 2500 kcal general reference. Calculated from the current recipe, not laboratory-tested."}</p>
<div class="nf-line-1"></div>
<p class="nf-ing-title">${ru ? "Состав" : "Ingredients"}</p>
<p class="nf-ing-text"><b>${ru ? "Состав:" : "Ingredients:"}</b> ${composition}.</p>
<p class="nf-ing-extra"><b>${ru ? "Содержит:" : "Contains:"}</b> ${h(product.allergens[lang])}</p>
</div>
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
    return `- [${p.name[lang]}](${absolute(pagePath(lang, `products/${p.id}`))}): ${p.summary[lang]} ${formatNumber(n.caloriesKcal, lang)} ${L.kcal}, ${formatNumber(n.proteinGrams, lang)} ${grams(lang)} ${L.protein}.`;
  });
  const halal = lang === "ru"
    ? "Все пять продуктов входят в область действия сертификата Халяль ДУМ РТ №614А/2024."
    : "All five products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.";
  return `# ${L.hero}\n\n${L.lead}\n\n${halal}\n\n## ${L.range}\n\n${L.nutritionNote}\n\n${lines.join("\n")}\n\n- [${L.ingredients}](${absolute(pagePath(lang, "ingredients"))})\n- [${L.nitrite}](${absolute(pagePath(lang, "without-sodium-nitrite"))})\n- [${L.retail}](${absolute(pagePath(lang, "retail"))})\n- [llms.txt](${SITE}/llms.txt)\n- [products.json](${SITE}/data/products.json)\n`;
}

function productMarkdown(product, lang) {
  const L = t[lang];
  const n = product.nutrition;
  const halal = lang === "ru" ? "ДУМ РТ №614А/2024" : "Certificate No. 614A/2024";
  return `# ${product.name[lang]}\n\n${product.summary[lang]}\n\n- ${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}\n- ${L.halal}: ${halal}\n- ${L.nitrite}\n\n## ${L.composition}\n\n${product.ingredients[lang]}\n\n**${L.allergens}:** ${product.allergens[lang]}\n\n## ${L.nutrition}\n\n- ${L.kcal}: ${formatNumber(n.caloriesKcal, lang)}\n- ${L.protein}: ${formatNumber(n.proteinGrams, lang)} ${grams(lang)}\n- ${L.fat}: ${formatNumber(n.fatGrams, lang)} ${grams(lang)}\n- ${L.carbs}: ${formatNumber(n.carbohydrateGrams, lang)} ${grams(lang)}\n\n${L.nutritionNote}\n`;
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
<nav class="nav__links" aria-label="${L.products}"><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="${pagePath(lang)}#contacts">${L.contacts}</a></nav>
<details class="nav__menu"><summary>${lang === "ru" ? "Меню" : "Menu"}</summary><nav aria-label="${lang === "ru" ? "Мобильное меню" : "Mobile menu"}"><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="${pagePath(lang)}#contacts">${L.contacts}</a><a href="${pagePath(lang, "retail")}">${L.retail}</a><a href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a></nav></details>
<div class="nav__actions"><a class="nav__lang" href="${other}" hreflang="${lang === "ru" ? "en" : "ru"}">${L.language}</a><a class="nav__cta" href="${pagePath(lang)}#contacts">${L.connect}</a></div></div></header>
<main id="main">${body}</main>
<footer class="footer"><div class="wrap footer__inner"><div><img class="footer__logo" src="/assets/logo/logo-horizontal-black.svg" alt="Yaratu" width="160" height="40"><p>© 2026 Yaratu · ${L.footer}</p></div><nav><a href="${pagePath(lang)}#advantages">${L.advantages}</a><a href="${pagePath(lang)}#products">${L.products}</a><a href="${pagePath(lang)}#quality">${L.quality}</a><a href="/privacy.html">${lang === "ru" ? "Политика ПДн" : "Privacy"}</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a href="tel:+79872170202">+7 987 217-02-02</a></nav></div></footer></body></html>`;
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

function productPositioning(product, lang) {
  const copy = {
    vetchina: {
      ru: ["Самая лёгкая в линейке", "125 ккал и 16,7 г белка на 100 г — минимальная калорийность и максимальное содержание белка среди пяти текущих продуктов."],
      en: ["The lightest in the range", "At 125 kcal and 16.7 g protein per 100 g, it has the lowest calories and highest protein among the five current products."],
    },
    mramornaya: {
      ru: ["Выразительный мясной профиль", "Курица и говядина, варёно-копчёный формат и 0,5 г углеводов на 100 г."],
      en: ["A bold meat profile", "Chicken and beef in a cooked-smoked format, with 0.5 g carbohydrate per 100 g."],
    },
    brokkoli: {
      ru: ["Брокколи в раскрытом составе", "Курица и говядина с брокколи; 13 г белка и 1,5 г углеводов на 100 г."],
      en: ["Broccoli in the disclosed recipe", "Chicken and beef with broccoli; 13 g protein and 1.5 g carbohydrate per 100 g."],
    },
    molochnye: {
      ru: ["Мягкий классический вкус", "Молочный белок, сухое молоко и пряности раскрыты в составе; 13,5 г белка на 100 г."],
      en: ["A mild classic taste", "Milk protein, milk powder and spices are disclosed in full; 13.5 g protein per 100 g."],
    },
    slivochnaya: {
      ru: ["Нежный сливочный профиль", "14,4 г белка и 0,7 г углеводов на 100 г — с полностью раскрытым составом."],
      en: ["A gentle creamy profile", "14.4 g protein and 0.7 g carbohydrate per 100 g, with the full ingredient list disclosed."],
    },
  };
  return copy[product.id][lang];
}

function card(product, lang, index) {
  const L = t[lang];
  const n = product.nutrition;
  const [positioningTitle, positioningText] = productPositioning(product, lang);
  return `<article class="product" id="product-${product.id}"><div class="product__media">${packshot(product, lang, ' loading="lazy"', { srcset: false })}</div>
<div class="product__body"><div class="product__intro-top"><span class="product__index">${String(index + 1).padStart(2, "0")}</span><div class="product__tags"><span class="tag">${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${L.nitrite}</span></div></div>
<h3>${h(product.name[lang])}</h3><p>${h(product.summary[lang])}</p>
<div class="product__usp"><span>${lang === "ru" ? "Особенность" : "What sets it apart"}</span><h4>${h(positioningTitle)}</h4><p>${h(positioningText)}</p></div>
<div class="kbju"><div><strong>${formatNumber(n.caloriesKcal, lang)}</strong><span>${L.kcal}</span></div><div><strong>${formatNumber(n.proteinGrams, lang)} ${grams(lang)}</strong><span>${L.protein}</span></div><div><strong>${formatNumber(n.fatGrams, lang)} ${grams(lang)}</strong><span>${L.fat}</span></div><div><strong>${formatNumber(n.carbohydrateGrams, lang)} ${grams(lang)}</strong><span>${L.carbs}</span></div></div>
<p class="product__allergens"><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p>
<a class="btn btn--outline" href="${pagePath(lang, `products/${product.id}`)}">${L.see}</a></div>
<div class="product__nutrition"><p>${L.nutritionNote}</p>${nutritionFacts(product, lang)}</div></article>`;
}

function homeFaqs(lang) {
  return lang === "ru" ? [
    ["Что такое Ярату?", "Ярату — мясной бренд ООО «Казанские Деликатесы»: пять варёных продуктов из Казани без нитрита натрия и с составом, раскрытым до ингредиентов."],
    ["Для кого эта линейка?", "Для магазинов, дистрибьюторов и покупателей, которым нужен проверяемый состав, а не лозунг «чистый продукт»."],
    ["Где цены?", "Публичного потребительского прайса нет. Актуальные спецификации, фасовки и условия поставки запрашивают у производителя."],
    ["Вся линейка халяль?", "Да. Все пять текущих продуктов входят в область действия сертификата Халяль ДУМ РТ №614А/2024."],
    ["КБЖУ лабораторные?", "Нет. Это расчёт по текущей рецептуре на 100 г сырьевой массы, не протокол испытаний."],
    ["Как запросить поставку?", "Напишите на info@kazandelikates.tatar или позвоните +7 987 217-02-02. Производитель в Казани, ул. Аграрная, 2, оф. 7."]
  ] : [
    ["What is Yaratu?", "Yaratu is the meat brand of Kazan Delicacies: five cooked products from Kazan without sodium nitrite and with compound mixes listed ingredient by ingredient."],
    ["Who is it for?", "Retailers, distributors and shoppers who need a checkable recipe rather than a clean-label slogan."],
    ["Where is the pricing?", "There is no public consumer price list. Specifications, pack formats and supply terms are provided by the manufacturer on request."],
    ["Is the whole range halal?", "Yes. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan."],
    ["Is nutrition laboratory-tested?", "No. Figures are calculated from the current recipe per 100 g of raw mass, not a lab protocol."],
    ["How do I request supply?", "Email info@kazandelikates.tatar or call +7 987 217-02-02. The manufacturer is in Kazan, 2 Agrarnaya Street, office 7."]
  ];
}

function home(lang) {
  const L = t[lang];
  const ru = lang === "ru";
  const heroProduct = products[0];
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
      ["03", "Пищевая ценность открыта", "КБЖУ и проценты суточной нормы видны до покупки."]
    ]
    : [
      ["01", "No sodium nitrite", "The status applies to the five reviewed current recipes."],
      ["02", "No ingredient shortcuts", "Compound mixes are disclosed ingredient by ingredient."],
      ["03", "Nutrition in full view", "Macros and daily-value percentages are visible before purchase."]
    ];
  const story = ru ? {
    eyebrow: "Почему Ярату",
    title: "Вкус начинается с честного выбора.",
    lead: "Мы создали Ярату, чтобы мясной продукт не приходилось выбирать вслепую. На сайте можно увидеть текущий состав, аллергены и расчётную пищевую ценность каждого продукта.",
    quote: "Не обещания на лицевой стороне, а состав и цифры, которые можно проверить.",
  } : {
    eyebrow: "Why Yaratu",
    title: "Taste begins with an informed choice.",
    lead: "We created Yaratu so a meat product would not have to be chosen blindly. The current ingredients, allergens and calculated nutrition for every product are visible here.",
    quote: "Not front-of-pack promises, but ingredients and figures you can check.",
  };
  const production = ru ? {
    eyebrow: "Производство",
    title: "Сделано в Казани. Контроль — на каждом уровне.",
    lead: "Ярату — бренд ООО «Казанские Деликатесы», производителя халяльных мясных продуктов в Казани. Производство работает по системе HACCP, стандарту ISO 22000:2018 и требованиям ТР ТС 021/2011.",
    standards: [["HACCP", "Безопасность процессов"], ["ISO 22000:2018", "Система пищевой безопасности"], ["ТР ТС 021/2011", "Требования к пищевой продукции"]],
  } : {
    eyebrow: "Production",
    title: "Made in Kazan. Controlled at every level.",
    lead: "Yaratu is a brand of Kazan Delicacies, a halal meat-products manufacturer in Kazan. Production operates under HACCP, ISO 22000:2018 and TR CU 021/2011 requirements.",
    standards: [["HACCP", "Process safety"], ["ISO 22000:2018", "Food-safety management"], ["TR CU 021/2011", "Food-product requirements"]],
  };
  const quality = ru ? {
    eyebrow: "Контроль качества",
    title: "Доверие строится на фактах.",
    lead: "Мы разделяем подтверждённые продуктовые факты и расчётные данные — и прямо показываем статус каждого источника.",
    items: [
      ["01", "HACCP и ISO 22000", "Системы управления безопасностью применяются на производстве ООО «Казанские Деликатесы»."],
      ["02", "Сертификат Халяль", "Все пять текущих продуктов входят в область действия сертификата ДУМ РТ №614А/2024."],
      ["03", "Полное раскрытие", "Комплексные смеси перечислены до отдельных ингредиентов, аллергены вынесены отдельно."],
      ["04", "Честный статус КБЖУ", "Пищевая ценность рассчитана по текущей рецептуре и не выдается за лабораторный протокол."],
    ],
  } : {
    eyebrow: "Quality control",
    title: "Trust is built on facts.",
    lead: "We separate verified product facts from calculated data and make the status of each source explicit.",
    items: [
      ["01", "HACCP and ISO 22000", "Food-safety management systems are applied at Kazan Delicacies production."],
      ["02", "Halal certificate", "All five current products are covered by certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of Tatarstan."],
      ["03", "Full disclosure", "Compound mixes are listed ingredient by ingredient, with allergens called out separately."],
      ["04", "Honest nutrition status", "Nutrition is calculated from the current recipe and is not presented as a laboratory report."],
    ],
  };
  const body = `<section class="hero"><div class="hero__plane"><div class="hero__mesh"></div><div class="hero__pattern"></div><div class="hero__glow hero__glow--warm"></div><div class="hero__orb"></div><span class="hero__star hero__star--a"></span><span class="hero__star hero__star--b"></span><span class="hero__star hero__star--c"></span><img class="hero__mark" src="/assets/logo/sign-white.svg" alt=""></div><div class="hero__shade"></div>
<div class="wrap hero__layout"><div class="hero__content"><img class="hero__brand" src="/assets/logo/logo-horizontal-white.svg" alt="Yaratu" width="214" height="40"><p class="hero__overline">${ru ? "Мясные продукты · Казань" : "Meat products · Kazan"}</p><h1>${L.hero}</h1><p class="lede">${L.lead}</p><div class="hero__actions"><a class="btn btn--solid" href="#products">${ru ? "Смотреть ассортимент" : "Explore the range"}</a><a class="btn btn--ghost" href="#contacts">${L.connect}</a></div><div class="hero__badges"><span>${ru ? "5 продуктов" : "5 products"}</span><span>${L.ingredients}</span><span>${L.nitrite}</span></div></div>
<div class="hero__product"><div class="hero__product-halo"></div>${packshot(heroProduct, lang, ' fetchpriority="high"', { srcset: false })}<span class="hero__product-caption">${h(heroProduct.name[lang])}</span></div></div></section>
<section id="advantages" class="story-section"><div class="wrap story"><div class="story__copy"><span class="eyebrow">${story.eyebrow}</span><h2>${story.title}</h2><p class="lede">${story.lead}</p><p class="story__quote">${story.quote}</p></div><div class="story__visual">${packshot(products[4], lang, ' loading="lazy"', { srcset: false })}</div></div></section>
<section class="trust"><div class="wrap"><div class="facts">${facts.map(([number, title, text]) => `<article><span>${number}</span><h2>${h(title)}</h2><p>${h(text)}</p></article>`).join("")}</div></div></section>
<section class="production"><div class="wrap production__grid"><div><span class="eyebrow">${production.eyebrow}</span><h2>${production.title}</h2></div><div class="production__copy"><p>${production.lead}</p><div class="production__standards">${production.standards.map(([name, text]) => `<div><strong>${name}</strong><span>${text}</span></div>`).join("")}</div></div></div></section>
<section id="products"><div class="wrap"><div class="section-head"><span class="eyebrow">${L.products}</span><h2>${L.range}</h2><p>${L.nutritionNote}</p></div>
<div class="products">${products.map((p, i) => card(p, lang, i)).join("")}</div></div></section>
<section id="quality" class="quality"><div class="wrap quality__inner"><div class="section-head"><span class="eyebrow">${quality.eyebrow}</span><h2>${quality.title}</h2><p>${quality.lead}</p></div><div class="quality-grid">${quality.items.map(([number, title, text]) => `<article><span>${number}</span><h3>${h(title)}</h3><p>${h(text)}</p></article>`).join("")}</div></div></section>
<section id="faq"><div class="wrap"><div class="section-head"><span class="eyebrow">FAQ</span><h2>${ru ? "Короткие ответы" : "Short answers"}</h2><p>${ru ? "Цены и оферта на сайте не публикуются." : "No prices or offers are published on this site."}</p></div><div class="faq">${faqs.map(([q, a]) => `<details><summary>${h(q)}</summary><p>${h(a)}</p></details>`).join("")}</div></div></section>
<section id="contacts" class="contact-cta"><div class="wrap contact-cta__grid"><div><span class="eyebrow">${L.contacts}</span><h2>${ru ? "Поговорим о поставке?" : "Let’s talk supply."}</h2><p>${ru ? "Запросите актуальные спецификации, фасовки, документы и условия напрямую у производителя." : "Request current specifications, pack formats, documents and supply terms directly from the manufacturer."}</p></div><div class="contact-cta__links"><a href="tel:+79872170202">+7 987 217-02-02</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><address>${ru ? "Казань, ул. Аграрная, 2, оф. 7" : "2 Agrarnaya Street, office 7, Kazan"}</address><a class="btn btn--solid" href="${pagePath(lang, "retail")}">${L.retail}</a></div></div></section>`;
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
  const ru = lang === "ru";
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
  const body = `<section class="product-page-hero"><div class="wrap product-page-hero__grid"><div class="product-page-hero__stage">${packshot(product, lang, ' fetchpriority="high"')}</div><div class="product-page-hero__copy"><a class="back-link" href="${pagePath(lang)}#product-${product.id}">← ${L.products}</a><span class="eyebrow">${h(product.kind[lang])}</span><h1>${h(product.name[lang])}</h1><p class="lede">${h(product.summary[lang])}</p><div class="product__tags"><span class="tag">${L.weight}: ${formatNumber(product.netWeight.value, lang)} ${grams(lang)}</span><span class="tag">${L.nitrite}</span></div><div class="kbju"><div><strong>${formatNumber(n.caloriesKcal, lang)}</strong><span>${L.kcal}</span></div><div><strong>${formatNumber(n.proteinGrams, lang)} ${grams(lang)}</strong><span>${L.protein}</span></div><div><strong>${formatNumber(n.fatGrams, lang)} ${grams(lang)}</strong><span>${L.fat}</span></div><div><strong>${formatNumber(n.carbohydrateGrams, lang)} ${grams(lang)}</strong><span>${L.carbs}</span></div></div><a class="btn btn--olive" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20${encodeURIComponent(product.id)}">${L.contact}</a></div></div></section>
<section class="nutrition-dossier"><div class="wrap nutrition-layout"><div class="nutrition-layout__copy"><div class="section-head"><span class="eyebrow">${L.composition}</span><h2>${ru ? "Всё важное — на одной этикетке." : "Everything important, on one label."}</h2><p>${h(product.ingredients[lang])}</p><p><strong>${L.allergens}:</strong> ${h(product.allergens[lang])}</p></div><div class="data-status"><span>${L.status}</span><p>${L.nutritionNote}</p><p>${ru ? "Состав: recipe-sourced · Халяль: сертификат ДУМ РТ №614А/2024" : "Ingredients: recipe-sourced · Halal: certificate No. 614A/2024"}</p></div></div><div class="product__label product__label--large">${nutritionFacts(product, lang)}</div></div></section>
<section id="contacts" class="contact-cta"><div class="wrap contact-cta__grid"><div><span class="eyebrow">${L.contacts}</span><h2>${ru ? "Нужны спецификации?" : "Need specifications?"}</h2><p>${ru ? "Запросите документы, фасовки и условия поставки напрямую у производителя." : "Request documents, pack formats and supply terms directly from the manufacturer."}</p></div><div class="contact-cta__links"><a href="tel:+79872170202">+7 987 217-02-02</a><a href="mailto:info@kazandelikates.tatar">info@kazandelikates.tatar</a><a class="btn btn--solid" href="mailto:info@kazandelikates.tatar?subject=Yaratu%20${encodeURIComponent(product.id)}">${L.contact}</a></div></div></section>`;
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
await output("llms.txt", `# Yaratu / Ярату\n\nRU+EN product range with disclosed ingredients. Nutrition is calculated, not laboratory-tested. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.\n\n${productLines}\n\n- [RU retail](${SITE}/retail/)\n- [EN retail](${SITE}/en/retail/)\n- [Canonical JSON](${SITE}/data/products.json)\n- [JSON feed](${SITE}/feeds/products.json), [CSV feed](${SITE}/feeds/products.csv), [XML feed](${SITE}/feeds/products.xml)\n`);
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
      description: "Markdown product range with disclosed ingredients, calculated nutrition and certificate-backed halal status.",
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
    "Look up the five Yaratu products, calculated nutrition, allergens and certificate-backed halal status. Use for ingredient or Nutrition Facts questions about Yaratu.",
    `# Yaratu catalog\n\nPublic brand of ООО «Казанские Деликатесы». No live checkout. Nutrition is calculated, not laboratory-tested. All five current products are covered by Halal certificate No. 614A/2024 issued by the Spiritual Administration of Muslims of the Republic of Tatarstan.\n\n## Prefer machine endpoints over scraping HTML\n\n1. Canonical JSON: ${SITE}/data/products.json\n2. Markdown dump: ${SITE}/llms.txt\n3. Full dataset: ${SITE}/llms-full.txt\n\nContacts: +7 987 217-02-02 · info@kazandelikates.tatar · Казань, ул. Аграрная, 2, оф. 7.\n`
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
