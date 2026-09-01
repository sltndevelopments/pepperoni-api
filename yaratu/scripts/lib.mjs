import { readFile } from "node:fs/promises";

export const ROOT = new URL("../", import.meta.url);
export const SITE = "https://yaratu.com";

export async function loadData() {
  const products = JSON.parse(await readFile(new URL("../data/products.json", import.meta.url), "utf8"));
  const evidence = JSON.parse(await readFile(new URL("../data/evidence_registry.json", import.meta.url), "utf8"));
  validate(products, evidence);
  return { products, evidence };
}

export function validate(data, registry) {
  if (data.schemaVersion !== 1 || !Array.isArray(data.products) || data.products.length !== 5) {
    throw new Error("products.json must contain exactly five schemaVersion 1 products");
  }
  const ids = new Set();
  for (const product of data.products) {
    if (!/^[a-z0-9-]+$/.test(product.id) || ids.has(product.id)) throw new Error(`Invalid or duplicate id: ${product.id}`);
    ids.add(product.id);
    for (const field of ["name", "kind", "summary", "ingredients", "allergens"]) {
      if (!product[field]?.ru || !product[field]?.en || !product[field]?.tt) {
        throw new Error(`${product.id}.${field} must have ru, en and tt`);
      }
    }
    if (!Number.isFinite(product.netWeight?.value) || product.netWeight.unit !== "g") throw new Error(`${product.id}: invalid netWeight`);
    const n = product.nutrition;
    for (const field of ["caloriesKcal", "proteinGrams", "fatGrams", "carbohydrateGrams", "saturatedFatGrams"]) {
      if (!Number.isFinite(n?.[field]) || n[field] < 0) throw new Error(`${product.id}: invalid nutrition.${field}`);
    }
    if (n.basisGrams !== 100 || product.status.nutrition !== "calculated" || product.status.composition !== "recipe-sourced") {
      throw new Error(`${product.id}: nutrition and composition provenance must be explicit`);
    }
    for (const ref of product.evidence) if (!registry.records[ref]) throw new Error(`${product.id}: unknown evidence ${ref}`);
  }
}

export const escapeHtml = (value) => String(value)
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");

export function jsonLd(value) {
  return JSON.stringify(value).replaceAll("<", "\\u003c");
}

export const LOCALES = ["ru", "en", "tt"];

export function pagePath(lang, slug = "") {
  const prefix = lang === "ru" ? "" : `/${lang}`;
  return `${prefix}/${slug}`.replace(/\/+/g, "/").replace(/\/?$/, "/");
}

export function absolute(path) {
  return `${SITE}${path}`;
}
