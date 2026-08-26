import test from "node:test";
import assert from "node:assert/strict";
import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const dist = join(root, "site/dist");

async function files(dir, prefix = "") {
  const result = [];
  for (const name of await readdir(dir)) {
    const path = join(dir, name);
    const relative = join(prefix, name);
    if ((await stat(path)).isDirectory()) result.push(...await files(path, relative));
    else result.push(relative);
  }
  return result;
}

test("canonical data has five bilingual validated products", async () => {
  const data = JSON.parse(await readFile(join(root, "data/products.json"), "utf8"));
  assert.equal(data.products.length, 5);
  assert.equal(new Set(data.products.map((p) => p.id)).size, 5);
  for (const product of data.products) {
    for (const field of ["name", "kind", "summary", "ingredients", "allergens"]) {
      assert.ok(product[field].ru);
      assert.ok(product[field].en);
    }
    assert.equal(product.status.nutrition, "calculated");
    assert.equal(product.status.composition, "recipe-sourced");
  }
  const marble = data.products.find((p) => p.id === "mramornaya");
  assert.equal(marble.claims.halal, false);
  assert.equal(marble.status.halal, "not-claimed");
  assert.ok(!marble.evidence.includes("halal-614a-2024"));
});

test("allowlist build excludes internal and legacy SVG", async () => {
  const built = await files(dist);
  assert.equal(built.filter((path) => path.endsWith("index.html")).length, 18);
  assert.equal(built.some((path) => path.split("/").includes("internal")), false);
  assert.equal(built.some((path) => path.startsWith("img/") && path.endsWith(".svg")), false);
  const allowedSvg = new Set([
    "assets/logo/logo-horizontal-black.svg",
    "assets/logo/logo-horizontal-white.svg",
    "assets/logo/sign-white.svg"
  ]);
  for (const path of built.filter((item) => item.endsWith(".svg"))) assert.ok(allowedSvg.has(path), `unexpected SVG: ${path}`);
});

test("every page has canonical and complete hreflang", async () => {
  const built = (await files(dist)).filter((path) => path.endsWith("index.html"));
  for (const path of built) {
    const html = await readFile(join(dist, path), "utf8");
    assert.match(html, /<link rel="canonical" href="https:\/\/yaratu\.com\/[^"]*">/);
    assert.match(html, /<meta name="yandex-verification" content="1817223863cbfebb">/);
    assert.match(html, /hreflang="ru"/);
    assert.match(html, /hreflang="en"/);
    assert.match(html, /hreflang="x-default"/);
  }
});

test("mobile navigation works without JavaScript and keeps native keyboard semantics", async () => {
  const built = (await files(dist)).filter((path) => path.endsWith("index.html"));
  const css = await readFile(join(dist, "styles.css"), "utf8");
  assert.match(css, /\.nav__menu\s*\{/);
  assert.match(css, /@media \(min-width: 860px\)[\s\S]*\.nav__menu\s*\{[\s\S]*display:\s*none/);
  for (const path of built) {
    const html = await readFile(join(dist, path), "utf8");
    assert.match(html, /<details class="nav__menu"><summary>[^<]+<\/summary><nav aria-label="[^"]+">/);
    assert.doesNotMatch(html, /<summary[^>]*tabindex="-1"/);
    const menu = html.match(/<details class="nav__menu">([\s\S]*?)<\/details>/)?.[1] || "";
    assert.ok((menu.match(/<a /g) || []).length >= 5, `${path}: incomplete mobile menu`);
    assert.doesNotMatch(html, /<script[^>]+src=/);
  }
});

test("visible units and decimal separators follow locale", async () => {
  const ru = await readFile(join(dist, "products/vetchina/index.html"), "utf8");
  const en = await readFile(join(dist, "en/products/vetchina/index.html"), "utf8");
  assert.match(ru, /150 г/);
  assert.match(ru, /<span>Белки<\/span><strong>16,7 г<\/strong>/);
  assert.doesNotMatch(ru, /<span>Белки<\/span><strong>16\.7 г<\/strong>/);
  assert.match(en, /150 g/);
  assert.match(en, /<span>Protein<\/span><strong>16\.7 g<\/strong>/);
});

test("static Nutrition Facts labels are visible on home and product pages", async () => {
  const homeRu = await readFile(join(dist, "index.html"), "utf8");
  const homeEn = await readFile(join(dist, "en/index.html"), "utf8");
  assert.equal((homeRu.match(/nutrition-facts nutrition-facts--compact/g) || []).length, 5);
  assert.equal((homeEn.match(/nutrition-facts nutrition-facts--compact/g) || []).length, 5);
  assert.match(homeRu, /<h1>Любовь начинается со вкуса<\/h1>/);
  assert.match(homeRu, /<h2>Без нитрита натрия<\/h2>/);
  assert.match(homeRu, /fetchpriority="high"/);
  assert.match(homeRu, /Nutrition Facts[\s\S]*Пищевая ценность/);
  assert.match(homeEn, /Nutrition Facts[\s\S]*Calculated from the current recipe/);

  for (const path of ["products/vetchina/index.html", "en/products/vetchina/index.html"]) {
    const html = await readFile(join(dist, path), "utf8");
    assert.match(html, /class="nutrition-facts"/);
    assert.match(html, /nutrition-facts__calories/);
    assert.match(html, /nutrition-facts__row--major/);
    assert.doesNotMatch(html, /<script[^>]+src=/);
  }
});

test("schema types are present without commerce or rating markup", async () => {
  const built = (await files(dist)).filter((path) => path.endsWith(".html"));
  const all = (await Promise.all(built.map((path) => readFile(join(dist, path), "utf8")))).join("\n");
  for (const type of ["WebSite", "Organization", "Brand", "ItemList", "Product", "BreadcrumbList", "FAQPage"]) {
    assert.ok(all.includes(`"@type":"${type}"`), `missing ${type}`);
  }
  assert.doesNotMatch(all, /"@type":"Offer"/);
  assert.doesNotMatch(all, /aggregateRating|reviewRating|priceCurrency/);
});

test("feeds are explicitly non-merchant and sitemap has lastmod", async () => {
  const feedJson = await readFile(join(dist, "feeds/products.json"), "utf8");
  const feedCsv = await readFile(join(dist, "feeds/products.csv"), "utf8");
  const feedXml = await readFile(join(dist, "feeds/products.xml"), "utf8");
  for (const feed of [feedJson, feedCsv, feedXml]) {
    assert.doesNotMatch(feed, /\b(price|availability|gtin)\b/i);
  }
  assert.match(feedXml, /merchant="false"/);
  const sitemap = await readFile(join(dist, "sitemap.xml"), "utf8");
  assert.equal((sitemap.match(/<url>/g) || []).length, 18);
  assert.equal((sitemap.match(/<lastmod>2026-08-26<\/lastmod>/g) || []).length, 18);
  assert.match(sitemap, /xmlns:xhtml="http:\/\/www\.w3\.org\/1999\/xhtml"/);
  assert.equal((sitemap.match(/xhtml:link rel="alternate" hreflang="ru"/g) || []).length, 18);
  assert.equal((sitemap.match(/xhtml:link rel="alternate" hreflang="en"/g) || []).length, 18);
  assert.equal((sitemap.match(/xhtml:link rel="alternate" hreflang="x-default"/g) || []).length, 18);
});

test("agent discovery files exist without fake auth, MCP or commerce", async () => {
  const catalog = JSON.parse(await readFile(join(dist, ".well-known/api-catalog"), "utf8"));
  const ard = JSON.parse(await readFile(join(dist, ".well-known/ai-catalog.json"), "utf8"));
  const skills = JSON.parse(await readFile(join(dist, ".well-known/agent-skills/index.json"), "utf8"));
  const homeMd = await readFile(join(dist, "index.md"), "utf8");
  const homeHtml = await readFile(join(dist, "index.html"), "utf8");
  const robots = await readFile(join(dist, "robots.txt"), "utf8");
  assert.equal(catalog.linkset[0].anchor, "https://yaratu.com/data/products.json");
  assert.equal(catalog.linkset[0]["service-doc"][0].type, "text/markdown");
  assert.equal(ard.host.identifier, "yaratu.com");
  assert.ok(ard.entries.every((entry) => entry.identifier.startsWith("urn:air:yaratu.com:")));
  assert.ok(ard.entries.every((entry) => entry.url.startsWith("https://yaratu.com/")));
  assert.equal(skills.skills.length, 3);
  for (const skill of skills.skills) {
    assert.match(skill.digest, /^sha256:[0-9a-f]{64}$/);
    assert.ok((await files(dist)).includes(skill.url.slice(1)));
  }
  assert.match(homeMd, /Пять продуктов/);
  assert.match(homeHtml, /rel="alternate" type="text\/markdown" href="\/index\.md"/);
  assert.match(homeHtml, /rel="api-catalog"/);
  assert.match(homeHtml, /rel="ai-catalog"/);
  assert.doesNotMatch(robots, /Agentmap/);
  assert.match(robots, /Content-Signal: ai-train=yes, search=yes, ai-input=yes/);
  assert.match(robots, /ChatGPT-User/);
  assert.match(homeHtml, /srcset="\/packshots\/sku-vetchina-f7a3c1-800\.jpg 800w/);
  const built = await files(dist);
  assert.equal(built.some((path) => path.includes("oauth")), false);
  assert.equal(built.some((path) => path.includes("mcp")), false);
  assert.equal(built.includes("auth.md"), false);
  assert.equal(built.includes(".well-known/ucp"), false);
  assert.equal(built.includes(".well-known/acp.json"), false);
});

test("AI and crawler discovery files have complete parity", async () => {
  const robots = await readFile(join(dist, "robots.txt"), "utf8");
  const robotsAi = await readFile(join(dist, "robots-ai.txt"), "utf8");
  const llms = await readFile(join(dist, "llms.txt"), "utf8");
  const full = await readFile(join(dist, "llms-full.txt"), "utf8");
  const wellKnown = await readFile(join(dist, ".well-known/llms.txt"), "utf8");
  const ai = JSON.parse(await readFile(join(dist, "ai.json"), "utf8"));
  const identity = JSON.parse(await readFile(join(dist, "identity.json"), "utf8"));
  const llmsSitemap = await readFile(join(dist, "sitemap-llms.xml"), "utf8");
  const indexNowKey = await readFile(join(dist, "989787de78c652b55e6887550582b6f6.txt"), "utf8");
  assert.match(robots, /GPTBot[\s\S]*Allow: \//);
  assert.match(robots, /Content-Signal: ai-train=yes, search=yes, ai-input=yes/);
  assert.match(robots, /Sitemap: https:\/\/yaratu\.com\/sitemap\.xml/);
  assert.match(robots, /Sitemap: https:\/\/yaratu\.com\/sitemap-llms\.xml/);
  assert.match(robotsAi, /Content-Signal: ai-train=yes, search=yes, ai-input=yes/);
  assert.match(llms, /^# Yaratu \/ Ярату/m);
  assert.match(llms, /\[Ветчина филейная\]\(https:\/\/yaratu\.com\/products\/vetchina\/\)/);
  assert.match(llms, /\[Canonical JSON\]\(https:\/\/yaratu\.com\/data\/products\.json\)/);
  assert.match(full, /^# Yaratu full RU\+EN dataset/m);
  assert.match(full, /\[RU\]\(https:\/\/yaratu\.com\/products\/vetchina\/\)/);
  assert.match(full, /Halal status: not-claimed/);
  assert.equal(wellKnown, full);
  assert.equal(identity.url, "https://yaratu.com/");
  for (const link of [ai.identity, ai.llms, ai.llmsFull, ai.wellKnownLlms, ai.products, ai.evidenceSummary, ai.sitemap, ai.llmsSitemap, ai.robotsAi]) {
    assert.match(link, /^https:\/\/yaratu\.com\//);
  }
  assert.match(llmsSitemap, /https:\/\/yaratu\.com\/\.well-known\/llms\.txt/);
  assert.equal(indexNowKey.trim(), "989787de78c652b55e6887550582b6f6");
});

test("public build exposes only redacted evidence status", async () => {
  const built = await files(dist);
  assert.ok(!built.includes("data/evidence_registry.json"));
  const summary = await readFile(join(dist, "data/evidence-summary.json"), "utf8");
  assert.doesNotMatch(summary, /internal documents|внутренн|note|issuer|identifier/i);
  assert.match(summary, /"composition": "recipe-sourced"/);
});

test("Sheets template matches strict sync contract", async () => {
  const csv = await readFile(join(root, "data/sheets_template.csv"), "utf8");
  const rows = parseCsv(csv);
  const header = rows[0];
  assert.equal(rows.length, 6);
  for (const row of rows) assert.equal(row.length, header.length);
  for (const field of ["publish", "review_status", "nutrition_status", "composition_status", "evidence_status", "evidence_refs"]) {
    assert.ok(header.includes(field), `missing ${field}`);
  }
  assert.equal((csv.match(/^"(vetchina|mramornaya|brokkoli|molochnye|slivochnaya)",/gm) || []).length, 5);
  assert.equal((csv.match(/"true","fully-reviewed","calculated","recipe-sourced","internal-reviewed"/g) || []).length, 5);
  assert.match(csv, /"mramornaya"[\s\S]*?"not-claimed","true","fully-reviewed"/);
  const sync = await readFile(join(root, "scripts/sync_sheets.mjs"), "utf8");
  assert.match(sync, /YARATU_GOOGLE_SERVICE_ACCOUNT_JSON/);
  assert.match(sync, /YARATU_GOOGLE_SERVICE_ACCOUNT_B64/);
  assert.match(sync, /YARATU_SHEET_FILE_ID/);
  assert.match(sync, /drive\/v3\/files/);
  assert.match(sync, /publish=false fails closed/);
  assert.match(sync, /unresolved REQUIRED value/);
});

function parseCsv(input) {
  const rows = [];
  let row = [], cell = "", quoted = false;
  for (let i = 0; i < input.length; i += 1) {
    const char = input[i];
    if (quoted) {
      if (char === '"' && input[i + 1] === '"') { cell += '"'; i += 1; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { row.push(cell); cell = ""; }
    else if (char === "\n") { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
    else cell += char;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
