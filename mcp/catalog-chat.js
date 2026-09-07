// On-site catalog assistant. Prices/SKUs come from the live catalog file only.
// Cheap model (gpt-4o-mini by default); never expose the provider key to the browser.
import { readFile } from 'node:fs/promises';

const PHONE = '+7 987 217-02-02';
const MAIL = 'info@kazandelikates.tatar';
const ADDR = 'г. Казань, ул. Аграрная, 2, оф. 7';
const SITE = 'https://pepperoni.tatar';

const MODEL = process.env.CATALOG_CHAT_MODEL || 'gpt-4o-mini';
const OPENAI_URL = process.env.CATALOG_CHAT_BASE_URL || 'https://api.openai.com/v1/chat/completions';
const DEEPSEEK_URL = process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/chat/completions';
const DEEPSEEK_MODEL = process.env.CATALOG_CHAT_DEEPSEEK_MODEL || 'deepseek-chat';
const MAX_Q = 400;
const MAX_HISTORY = 6;
const MAX_MATCHES = 8;
const IP_WINDOW_MS = 10 * 60 * 1000;
const IP_MAX = Number(process.env.CATALOG_CHAT_IP_MAX || 20);
const DAY_MAX = Number(process.env.CATALOG_CHAT_DAILY_LIMIT || 300);

const STOP =
  /^(сколько|стоит|какая|какой|какие|цена|price|what|the|for|and|your|need|нужны|нужен|подойдёт|подойдет|tell|about|in|опт[ао]?м?|wholesale|халяль|halal|каталог|catalog|live|товар|продук)$/i;
const CURRENCY_RE = /\b(USD|KZT|UZS|KGS|BYN|AZN|RUB)\b/i;

const ALIASES = [
  ['пепперони', 'pepperoni'],
  ['сосиск', 'sausage', 'hotdog', 'hot-dog', 'хот-дог', 'азс'],
  ['казылык', 'kazylyk'],
  ['выпеч', 'pastry', 'эчпочмак', 'echpochmak', 'самса', 'samsa', 'губадия', 'чак-чак'],
  ['ветчин', 'ham'],
  ['котлет', 'burger', 'бургер'],
];

const ALLOWED_ORIGINS = new Set([
  'https://pepperoni.tatar',
  'https://www.pepperoni.tatar',
  'https://api.pepperoni.tatar',
  'http://localhost:3000',
  'http://127.0.0.1:3000',
]);

const SYSTEM_PROMPT = `You are the on-site wholesale catalog assistant for Kazan Delicacies / ООО «Казанские Деликатесы».

ALWAYS:
- Answer in the user's language (Russian, English, Tatar, Kazakh, Uzbek, Arabic).
- Quote SKUs and prices ONLY from LIVE_MATCHES. If a price is missing, say the manager will confirm.
- Cite live catalog as "согласно api.pepperoni.tatar (live)" / "per api.pepperoni.tatar (live)".
- Never state a fixed catalog size, FX rate, or memorized price.
- Halal is default. No pork, lard, alcohol, or kosher certificate.
- Do not invent SKUs, certificates, clients, MOQ, or delivery dates.
- If the user wants a manager / callback / WhatsApp: give ${PHONE}, ${MAIL}, ${ADDR}. Offer the on-site lead form.
- Private label / СТМ: email ${MAIL} with audience, recipe direction, packaging idea. MOQ only from a manager.
- Keep answers to 2–3 short paragraphs. No markdown headings.

Fixed facts only:
- Halal ДУМ РТ #614A/2024, HACCP, ISO 22000:2018, ТР ТС 021/2011
- Terms: EXW Kazan
- Sites: ${SITE} · https://kazandelikates.tatar

Return JSON only: {"text":"...","skus":["KD-013"],"cta":"none"}
cta is one of: none, lead, wa, call.
skus must be a subset of LIVE_MATCHES. Empty array is allowed.`;

const CATALOG_PATHS = [
  process.env.PEPPERONI_PRODUCTS_JSON,
  '/var/www/pepperoni/data/products.json',
  new URL('../public/products.json', import.meta.url).pathname,
].filter(Boolean);

let catalogCache = { at: 0, data: null };

export async function loadCatalog() {
  const now = Date.now();
  if (catalogCache.data && now - catalogCache.at < 60_000) return catalogCache.data;
  for (const path of CATALOG_PATHS) {
    try {
      const data = JSON.parse(await readFile(path, 'utf8'));
      if (Array.isArray(data.products)) {
        catalogCache = { at: now, data };
        return data;
      }
    } catch {
      /* next */
    }
  }
  const res = await fetch('https://pepperoni.tatar/products.json', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error('catalog_unavailable');
  const data = await res.json();
  catalogCache = { at: now, data };
  return data;
}

const hits = new Map();
let dayKey = '';
let dayCount = 0;

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

export function resetLimitsForTests() {
  hits.clear();
  dayKey = '';
  dayCount = 0;
}

export function clientIp(req) {
  const real = String(req.headers['x-real-ip'] || '').split(',')[0].trim();
  if (real) return real;
  const fwd = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  if (fwd) return fwd;
  return req.socket?.remoteAddress || 'unknown';
}

export function originAllowed(origin, referer) {
  const o = String(origin || '').replace(/\/$/, '');
  if (o && ALLOWED_ORIGINS.has(o)) return true;
  const ref = String(referer || '');
  for (const allowed of ALLOWED_ORIGINS) {
    if (ref.startsWith(allowed + '/') || ref === allowed) return true;
  }
  return false;
}

export function takeSlot(ip) {
  const day = todayKey();
  if (day !== dayKey) {
    dayKey = day;
    dayCount = 0;
  }
  if (dayCount >= DAY_MAX) return { ok: false, status: 429, error: 'daily_limit' };
  const now = Date.now();
  const list = (hits.get(ip) || []).filter((t) => now - t < IP_WINDOW_MS);
  if (list.length >= IP_MAX) return { ok: false, status: 429, error: 'rate_limit' };
  list.push(now);
  hits.set(ip, list);
  dayCount += 1;
  return { ok: true };
}

function tokens(q) {
  return String(q || '')
    .toLowerCase()
    .replace(/[«»"']/g, ' ')
    .split(/[\s,/|?!.]+/)
    .filter((w) => w.length > 1 && !STOP.test(w) && !CURRENCY_RE.test(w));
}

function expand(q) {
  const raw = tokens(q);
  const extra = [];
  ALIASES.forEach((group) => {
    if (group.some((a) => raw.some((w) => w.includes(a) || a.includes(w)))) {
      extra.push(...group);
    }
  });
  return raw.concat(extra);
}

export function detectIntent(q) {
  const s = String(q).toLowerCase();
  if (
    /менеджер|связат|whats.?app|телеграм|telegram|позвон|написать вам|оставить заявк|директор|ceo|основател|руковод/.test(
      s
    )
  ) {
    return 'contacts';
  }
  if (/телефон|почт|контакт|address|phone|email|где вы|адрес/.test(s)) return 'contacts';
  if (
    /халяль|halal|сертиф|документ|iso|haccp|кошер|kosher|свин/.test(s) &&
    !/цен|price|стоит|sku|kd-|пепперони|pepperoni|сосиск/.test(s)
  ) {
    return 'certs';
  }
  if (/стм|private.?label|white.?label|собственной марк|под бренд/.test(s)) return 'stm';
  return 'search';
}

export function detectCurrency(q) {
  const m = String(q).match(CURRENCY_RE);
  return m ? m[1].toUpperCase() : null;
}

function haystack(p) {
  return [p.sku, p.name, p.name_en, p.category, p.section].filter(Boolean).join(' ').toLowerCase();
}

export function retrieveProducts(products, q, limit = MAX_MATCHES) {
  const sku = String(q).toUpperCase().match(/KD-\d{3}/);
  if (sku) {
    return (products || []).filter((p) => String(p.sku).toUpperCase() === sku[0]).slice(0, limit);
  }
  const needles = expand(q);
  if (!needles.length) return [];
  return (products || [])
    .map((p) => {
      const hay = haystack(p);
      let score = 0;
      needles.forEach((n) => {
        if (hay.includes(n)) score += n.length > 4 ? 2 : 1;
      });
      return { p, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((x) => x.p);
}

function formatPrice(p, currency) {
  const offers = p.offers || {};
  if (currency && currency !== 'RUB') {
    const ep = (offers.exportPrices || {})[currency];
    if (ep == null || ep === '') return null;
    return `${ep} ${currency}`;
  }
  const rub = offers.price || offers.pricePerUnit;
  if (rub == null || rub === '') return null;
  return `${rub} ₽ с НДС`;
}

export function cardProduct(p, currency, lang) {
  const en = lang === 'en';
  const sku = String(p.sku || '').toLowerCase();
  return {
    sku: p.sku,
    name: p.name,
    price: formatPrice(p, currency),
    image: p.image || p.imageMain || '',
    href: en ? `/en/products/${sku}` : `/products/${sku}`,
  };
}

function compactForModel(p) {
  const offers = p.offers || {};
  const exportPrices = offers.exportPrices || {};
  return {
    sku: p.sku,
    name: p.name,
    category: p.category,
    section: p.section,
    weight: p.weight,
    priceRubInclVat: offers.price || offers.pricePerUnit || null,
    USD: exportPrices.USD ?? null,
    KZT: exportPrices.KZT ?? null,
  };
}

export function localAnswer({ q, matches, lastSynced, lang }) {
  const en = lang === 'en' || (!/[а-яё]/i.test(q) && /[a-z]/i.test(q));
  const intent = detectIntent(q);
  if (intent === 'certs') {
    return en
      ? 'Halal DUM RT #614A/2024. HACCP. ISO 22000:2018. TR CU 021/2011. No pork. No kosher certificate.'
      : 'Халяль ДУМ РТ №614A/2024. HACCP. ISO 22000:2018. ТР ТС 021/2011. Свинины нет. Кошер-сертификата нет.';
  }
  if (intent === 'contacts') {
    return en
      ? `Wholesale manager: ${PHONE} · ${MAIL} · Kazan, Agrarnaya 2, office 7. WhatsApp or the on-site inquiry form works.`
      : `Менеджер: ${PHONE} · ${MAIL} · ${ADDR}. Можно WhatsApp или заявку на сайте.`;
  }
  if (intent === 'stm') {
    return en
      ? `Private label — email ${MAIL} with audience, recipe direction, packaging idea. MOQ and lead time only from a manager.`
      : `СТМ / Private Label — письмо на ${MAIL}: аудитория, направление рецепта, идея упаковки. Сроки и MOQ подтверждает менеджер.`;
  }
  if (!matches.length) {
    return en
      ? `No exact match in the live catalog. Send a SKU or write ${PHONE} · ${MAIL}.`
      : `В живом каталоге нет точного совпадения. Напишите SKU или менеджеру: ${PHONE} · ${MAIL}.`;
  }
  const cite = en
    ? `Per api.pepperoni.tatar (live)${lastSynced ? `. Synced ${lastSynced}` : ''}.`
    : `Согласно api.pepperoni.tatar (live)${lastSynced ? `. Синхронизация ${lastSynced}` : ''}.`;
  return cite;
}

export function buildMessages({ q, matches, lastSynced, history, lang }) {
  const live = {
    lastSynced: lastSynced || null,
    matches: matches.map(compactForModel),
    categoriesHint: [...new Set((matches || []).map((p) => p.category).filter(Boolean))],
  };
  const msgs = [{ role: 'system', content: SYSTEM_PROMPT }];
  (history || []).slice(-MAX_HISTORY).forEach((h) => {
    const role = h.role === 'assistant' ? 'assistant' : 'user';
    const content = String(h.content || '')
      .replace(/<[^>]+>/g, ' ')
      .slice(0, MAX_Q);
    if (content.trim()) msgs.push({ role, content });
  });
  msgs.push({
    role: 'user',
    content: `LANG=${lang}\nLIVE_MATCHES=${JSON.stringify(live)}\nQUESTION=${q}`,
  });
  return msgs;
}

export function parseModelJson(raw) {
  const text = String(raw || '').trim();
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try {
    const data = JSON.parse(text.slice(start, end + 1));
    if (!data || typeof data.text !== 'string') return null;
    const skus = Array.isArray(data.skus)
      ? data.skus.map((s) => String(s).toUpperCase()).filter((s) => /^KD-\d{3}$/.test(s))
      : [];
    const cta = ['lead', 'wa', 'call'].includes(data.cta) ? data.cta : 'none';
    return { text: data.text.trim().slice(0, 1200), skus, cta };
  } catch {
    return null;
  }
}

function openaiKey() {
  return String(process.env.OPENAI_API_KEY || '').trim();
}

function deepseekKey() {
  return String(process.env.DEEPSEEK_API_KEY || '').trim();
}

async function completeChat({ url, key, model, messages, fetchImpl }) {
  const res = await fetchImpl(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      temperature: 0.3,
      max_tokens: 350,
      response_format: { type: 'json_object' },
      messages,
    }),
  });
  const raw = await res.text();
  if (!res.ok) throw new Error(`llm_${res.status}`);
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error('llm_bad_json');
  }
  const parsed = parseModelJson(data.choices?.[0]?.message?.content);
  if (!parsed) throw new Error('llm_shape');
  return parsed;
}

export function llmProviders() {
  const list = [];
  if (openaiKey()) list.push({ name: MODEL, url: OPENAI_URL, key: openaiKey(), model: MODEL });
  if (deepseekKey()) {
    list.push({
      name: DEEPSEEK_MODEL,
      url: DEEPSEEK_URL,
      key: deepseekKey(),
      model: DEEPSEEK_MODEL,
    });
  }
  return list;
}

export async function callModel(messages, fetchImpl = fetch) {
  const providers = llmProviders();
  if (!providers.length) throw new Error('no_llm_key');
  let last = new Error('no_llm_key');
  for (const provider of providers) {
    try {
      const parsed = await completeChat({
        url: provider.url,
        key: provider.key,
        model: provider.model,
        messages,
        fetchImpl,
      });
      parsed.source = provider.name;
      return parsed;
    } catch (err) {
      last = err;
    }
  }
  throw last;
}

function guessLang(q, lang) {
  if (lang === 'en' || lang === 'ru') return lang;
  if (/[а-яё]/i.test(q)) return 'ru';
  if (/[a-z]/i.test(q)) return 'en';
  return 'ru';
}

function pickCards(allProducts, parsedSkus, matches, currency, lang) {
  const bySku = new Map((allProducts || []).map((p) => [String(p.sku).toUpperCase(), p]));
  const ordered = [];
  (parsedSkus || []).forEach((sku) => {
    const p = bySku.get(sku);
    if (p) ordered.push(p);
  });
  if (!ordered.length) ordered.push(...matches);
  const uniq = [];
  const seen = new Set();
  ordered.forEach((p) => {
    const sku = String(p.sku).toUpperCase();
    if (seen.has(sku)) return;
    seen.add(sku);
    uniq.push(p);
  });
  return uniq.slice(0, 5).map((p) => cardProduct(p, currency, lang));
}

export async function answerCatalogChat(
  { q, history, lang, fetchImpl } = {},
  catalogLoader = loadCatalog
) {
  const question = String(q || '')
    .replace(/[\u0000-\u001F\u007F]/g, ' ')
    .trim()
    .slice(0, MAX_Q);
  if (question.length < 2) {
    return { ok: false, status: 400, error: 'empty' };
  }
  const data = await catalogLoader();
  const products = data.products || [];
  const resolvedLang = guessLang(question, lang);
  const matches = retrieveProducts(products, question);
  const currency = detectCurrency(question);
  const fallbackText = localAnswer({
    q: question,
    matches,
    lastSynced: data.lastSynced,
    lang: resolvedLang,
  });

  try {
    const parsed = await callModel(
      buildMessages({
        q: question,
        matches,
        lastSynced: data.lastSynced,
        history,
        lang: resolvedLang,
      }),
      fetchImpl
    );
    return {
      ok: true,
      text: parsed.text,
      products: pickCards(products, parsed.skus, matches, currency, resolvedLang),
      lastSynced: data.lastSynced || null,
      source: parsed.source || MODEL,
      cta: parsed.cta,
    };
  } catch {
    return {
      ok: true,
      text: fallbackText,
      products: pickCards(products, [], matches, currency, resolvedLang),
      lastSynced: data.lastSynced || null,
      source: 'fallback',
      cta: detectIntent(question) === 'contacts' ? 'lead' : 'none',
    };
  }
}

export function healthPayload() {
  const names = llmProviders().map((p) => p.name);
  return {
    ok: true,
    model: names[0] || MODEL,
    llm: names.length > 0,
    providers: names,
  };
}
