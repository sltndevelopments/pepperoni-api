import test from 'node:test';
import assert from 'node:assert/strict';
import {
  answerCatalogChat,
  detectIntent,
  localAnswer,
  originAllowed,
  parseModelJson,
  resetLimitsForTests,
  retrieveProducts,
  takeSlot,
} from './catalog-chat.js';

const products = [
  {
    sku: 'KD-013',
    name: 'Колбаса Пепперони халяль 500 г',
    category: 'Пепперони',
    section: 'Заморозка',
    offers: { price: '275.00', exportPrices: { USD: 2.89, KZT: 1320 } },
    image: '/images/products/kd-013-main.jpg',
  },
  {
    sku: 'KD-014',
    name: 'Колбаса Пепперони халяль 1 кг',
    category: 'Пепперони',
    section: 'Заморозка',
    offers: { price: '458.00', exportPrices: { USD: 4.81, KZT: 2200 } },
  },
  {
    sku: 'KD-001',
    name: 'Сосиски «Из говядины»',
    category: 'Сосиски гриль для хот-догов',
    section: 'Заморозка',
    offers: { price: '290.00', exportPrices: { USD: 3.05 } },
  },
];

test('retrieveProducts finds pepperoni, not sausages', () => {
  const found = retrieveProducts(products, 'халяль пепперони USD');
  assert.deepEqual(
    found.map((p) => p.sku),
    ['KD-013', 'KD-014']
  );
});

test('detectIntent treats manager request as contacts', () => {
  assert.equal(detectIntent('можно связаться в вашим менеджером?'), 'contacts');
  assert.equal(localAnswer({ q: 'можно связаться?', matches: [], lang: 'ru' }).includes('+7 987 217-02-02'), true);
});

test('parseModelJson ignores invented SKU shape', () => {
  const parsed = parseModelJson('{"text":"ok","skus":["KD-013","FAKE-1"],"cta":"lead"}');
  assert.deepEqual(parsed.skus, ['KD-013']);
  assert.equal(parsed.cta, 'lead');
});

test('origin allowlist', () => {
  assert.equal(originAllowed('https://pepperoni.tatar', ''), true);
  assert.equal(originAllowed('https://evil.example', ''), false);
  assert.equal(originAllowed('', 'https://pepperoni.tatar/pepperoni'), true);
});

test('rate limiter trips after IP_MAX', () => {
  resetLimitsForTests();
  const prev = process.env.CATALOG_CHAT_IP_MAX;
  process.env.CATALOG_CHAT_IP_MAX = '2';
  // takeSlot reads IP_MAX at module load, so just call many times on unique logic:
  // the constant is already loaded; this test checks the Map behavior with default 20
  // by filling 20 then 21.
  let last = { ok: true };
  for (let i = 0; i < 21; i += 1) last = takeSlot('1.2.3.4');
  assert.equal(last.ok, false);
  assert.equal(last.error, 'rate_limit');
  if (prev == null) delete process.env.CATALOG_CHAT_IP_MAX;
  else process.env.CATALOG_CHAT_IP_MAX = prev;
  resetLimitsForTests();
});

test('answerCatalogChat uses model cards when fetch succeeds', async () => {
  const fetchImpl = async () => ({
    ok: true,
    text: async () =>
      JSON.stringify({
        choices: [
          {
            message: {
              content: JSON.stringify({
                text: 'Пепперони KD-013 — 2.89 USD.',
                skus: ['KD-013'],
                cta: 'none',
              }),
            },
          },
        ],
      }),
  });
  process.env.OPENAI_API_KEY = 'sk-test';
  const result = await answerCatalogChat(
    { q: 'pepperoni USD', lang: 'en', fetchImpl },
    async () => ({ lastSynced: '2026-09-06', products })
  );
  assert.equal(result.ok, true);
  assert.equal(result.source, process.env.CATALOG_CHAT_MODEL || 'gpt-4o-mini');
  assert.equal(result.products[0].sku, 'KD-013');
  assert.match(result.products[0].price, /USD/);
  delete process.env.OPENAI_API_KEY;
});

test('answerCatalogChat falls back when model fails', async () => {
  delete process.env.OPENAI_API_KEY;
  const result = await answerCatalogChat(
    { q: 'можно связаться с менеджером?', lang: 'ru' },
    async () => ({ lastSynced: '2026-09-06', products })
  );
  assert.equal(result.ok, true);
  assert.equal(result.source, 'fallback');
  assert.match(result.text, /\+7 987 217-02-02/);
});
