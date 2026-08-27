import { createSign } from "node:crypto";
import { rename, writeFile } from "node:fs/promises";
import { loadData, validate } from "./lib.mjs";

const DEFAULT_FILE_ID = "1rSFP1QvQX5X-92OSq_vaoF0gj0POiNHTXNMnSSBZemU";
const urlTemplate = process.env.YARATU_SHEETS_URL;
const gid = process.env.YARATU_SHEETS_GID;
const fileId = process.env.YARATU_SHEET_FILE_ID || DEFAULT_FILE_ID;
const serviceAccount = readServiceAccount();

if (!serviceAccount && (!urlTemplate || !gid)) {
  console.log("No service-account credentials or public Sheets URL/GID; checked-in data/products.json remains canonical.");
  process.exit(0);
}

let response;
let source;
if (serviceAccount) {
  const token = await getAccessToken(serviceAccount);
  const url = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}/export?mimeType=${encodeURIComponent("text/csv")}`;
  response = await fetch(url, { headers: { accept: "text/csv", authorization: `Bearer ${token}` } });
  source = `private Google Sheet ${fileId}`;
} else {
  const url = urlTemplate.includes("{gid}")
    ? urlTemplate.replaceAll("{gid}", encodeURIComponent(gid))
    : `${urlTemplate}${urlTemplate.includes("?") ? "&" : "?"}gid=${encodeURIComponent(gid)}&output=csv`;
  response = await fetch(url, { headers: { accept: "text/csv" } });
  source = `public Google Sheet GID ${gid}`;
}
if (!response.ok) throw new Error(`Sheets fetch failed: HTTP ${response.status}`);
const rows = parseCsv(await response.text());
if (rows.length < 2) throw new Error("Sheets CSV has no product rows");

const headers = rows[0].map((value) => value.trim());
if (new Set(headers).size !== headers.length) throw new Error("Sheets CSV contains duplicate headers");
const required = [
  "id", "name_ru", "name_en", "kind_ru", "kind_en", "summary_ru", "summary_en",
  "net_weight_g", "image", "ingredients_ru", "ingredients_en", "allergens_ru", "allergens_en",
  "calories_kcal", "protein_g", "fat_g", "carbohydrate_g", "saturated_fat_g",
  "without_sodium_nitrite", "halal_status", "publish", "review_status",
  "nutrition_status", "composition_status", "evidence_status", "evidence_refs"
];
const missing = required.filter((name) => !headers.includes(name));
if (missing.length) throw new Error(`Sheets CSV missing headers: ${missing.join(", ")}`);

const value = (row, name) => row[headers.indexOf(name)]?.trim() ?? "";
const number = (row, name) => {
  const parsed = Number(value(row, name).replace(",", "."));
  if (!Number.isFinite(parsed) || parsed < 0) throw new Error(`${value(row, "id")}: invalid ${name}`);
  return parsed;
};
const bool = (row, name) => {
  const raw = value(row, name).toLowerCase();
  if (["true", "1", "yes"].includes(raw)) return true;
  if (["false", "0", "no"].includes(raw)) return false;
  throw new Error(`${value(row, "id")}: ${name} must be true/false`);
};

const current = await loadData();
const next = {
  schemaVersion: 1,
  lastModified: new Date().toISOString().slice(0, 10),
  source: "google-sheets",
  nutritionBasis: current.products.nutritionBasis,
  products: rows.slice(1).filter((row) => row.some(Boolean)).map((row) => {
    const id = value(row, "id");
    if (row.some((cell) => cell.trim().toUpperCase() === "REQUIRED")) throw new Error(`${id || "row"}: unresolved REQUIRED value`);
    if (!bool(row, "publish")) throw new Error(`${id}: publish=false fails closed; export only fully reviewed rows`);
    if (value(row, "review_status") !== "fully-reviewed") throw new Error(`${id}: review_status must be fully-reviewed`);
    if (value(row, "nutrition_status") !== "calculated") throw new Error(`${id}: nutrition_status must be calculated`);
    if (value(row, "composition_status") !== "recipe-sourced") throw new Error(`${id}: composition_status must be recipe-sourced`);
    if (value(row, "evidence_status") !== "internal-reviewed") throw new Error(`${id}: evidence_status must be internal-reviewed`);
    const halal = value(row, "halal_status");
    if (!["verified", "not-claimed"].includes(halal)) throw new Error(`${id}: halal_status must be verified or not-claimed`);
    const evidence = value(row, "evidence_refs").split(";").map((item) => item.trim()).filter(Boolean);
    if (!evidence.length || !evidence.includes("recipe-current")) throw new Error(`${id}: evidence_refs must include recipe-current`);
    if (halal === "verified" && !evidence.includes("halal-614a-2024")) throw new Error(`${id}: verified halal requires halal evidence`);
    if (halal === "not-claimed" && evidence.includes("halal-614a-2024")) throw new Error(`${id}: not-claimed halal cannot reference halal evidence`);
    return {
      id,
      name: {ru: value(row, "name_ru"), en: value(row, "name_en")},
      kind: {ru: value(row, "kind_ru"), en: value(row, "kind_en")},
      summary: {ru: value(row, "summary_ru"), en: value(row, "summary_en")},
      netWeight: {value: number(row, "net_weight_g"), unit: "g"},
      image: value(row, "image"),
      ingredients: {ru: value(row, "ingredients_ru"), en: value(row, "ingredients_en")},
      allergens: {ru: value(row, "allergens_ru"), en: value(row, "allergens_en")},
      nutrition: {
        basisGrams: 100,
        caloriesKcal: number(row, "calories_kcal"),
        proteinGrams: number(row, "protein_g"),
        fatGrams: number(row, "fat_g"),
        carbohydrateGrams: number(row, "carbohydrate_g"),
        saturatedFatGrams: number(row, "saturated_fat_g")
      },
      claims: {withoutSodiumNitrite: bool(row, "without_sodium_nitrite"), halal: halal === "verified"},
      status: {nutrition: "calculated", composition: "recipe-sourced", halal, evidence: "internal-reviewed"},
      evidence
    };
  })
};

validate(next, current.evidence);
const target = new URL("../data/products.json", import.meta.url);
const temporary = new URL("../data/products.json.tmp", import.meta.url);
await writeFile(temporary, `${JSON.stringify(next, null, 2)}\n`);
await rename(temporary, target);
console.log(`Synced and validated ${next.products.length} products from ${source}.`);

function readServiceAccount() {
  const json = process.env.YARATU_GOOGLE_SERVICE_ACCOUNT_JSON;
  const b64 = process.env.YARATU_GOOGLE_SERVICE_ACCOUNT_B64;
  if (!json && !b64) return null;
  if (json && b64) throw new Error("Set only one service-account env: JSON or B64");
  let parsed;
  try {
    parsed = JSON.parse(json || Buffer.from(b64, "base64").toString("utf8"));
  } catch {
    throw new Error("Invalid service-account JSON/B64");
  }
  if (!parsed.client_email || !parsed.private_key) throw new Error("Service account requires client_email and private_key");
  return parsed;
}

async function getAccessToken(credentials) {
  const now = Math.floor(Date.now() / 1000);
  const tokenUri = credentials.token_uri || "https://oauth2.googleapis.com/token";
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const unsigned = `${encode({alg: "RS256", typ: "JWT"})}.${encode({
    iss: credentials.client_email,
    scope: "https://www.googleapis.com/auth/drive.readonly",
    aud: tokenUri,
    iat: now,
    exp: now + 3600
  })}`;
  const signer = createSign("RSA-SHA256");
  signer.update(unsigned);
  signer.end();
  const assertion = `${unsigned}.${signer.sign(credentials.private_key).toString("base64url")}`;
  const tokenResponse = await fetch(tokenUri, {
    method: "POST",
    headers: {"content-type": "application/x-www-form-urlencoded"},
    body: new URLSearchParams({grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion})
  });
  if (!tokenResponse.ok) throw new Error(`Google OAuth failed: HTTP ${tokenResponse.status}`);
  const payload = await tokenResponse.json();
  if (!payload.access_token) throw new Error("Google OAuth response has no access_token");
  return payload.access_token;
}

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
  if (quoted) throw new Error("Unclosed quote in Sheets CSV");
  if (cell || row.length) { row.push(cell.replace(/\r$/, "")); rows.push(row); }
  const width = rows[0]?.length;
  for (const [index, item] of rows.entries()) if (item.length !== width) throw new Error(`CSV row ${index + 1} has ${item.length} columns; expected ${width}`);
  return rows;
}
