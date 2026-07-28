# Catch Chomps — экономика, ассортимент, продажи

Канон стратегии (2026-07-26). Источники правды в данных:

| Тема | Файл |
|------|------|
| Money 12 + proxy ABC | [`data/money_12.json`](../data/money_12.json) |
| ЗОЖ hero-линейка | [`data/zozh_line_spec.json`](../data/zozh_line_spec.json) |
| Каналы и pipeline | [`data/channel_targets_2026_2028.json`](../data/channel_targets_2026_2028.json) |
| Capital gate 2027 | [`data/capital_gate_2027.json`](../data/capital_gate_2027.json) |

Витрина: [`/money`](https://pepperoni.tatar/money) · [`/zozh`](https://pepperoni.tatar/zozh) · hubs `/money/kd-XXX`.

## Рамка

- **Не цель:** US retail sales Chomps ($0.5–1B полка).
- **Цель:** сопоставимая стадия **company revenue / EBITDA**, халяль-завод + один consumer-grade hero-формат.
- Сравнение всегда **company ↔ company** (retail Chomps ÷ ~1.5–2 для грубого эквивалента).

## Траектория (USD company)

| Год | Цель | Стадия ~Chomps |
|-----|------|----------------|
| 2025 | $9.7M факт | — |
| 2026 | $20M план | pre-mass |
| 2028 | $60–80M | ~2020 scale |
| 2030 | $150–200M | early-2020s growth, не $500M |

## Money 12 (ассортиментный фокус)

Список SKU и tier A/B — в `data/money_12.json`.

**Правило продаж:** hunter-pitch только Money 12 + PL-конструкторы. Выпечка (19 SKU) — не hero-нарратив сайта.

**ABC:** сейчас proxy по канальному fit. Финансы заменяют на факт 1С (выручка/маржа 12 мес.) без смены файла-схемы — обновить `tier` и `status`.

Цели к 2028: Money 12 ≥70% выручки; gross margin money-SKU 25–30%; EBITDA/net ≥7%; $/FTE $300–400k.

## ЗОЖ hero-линейка

Спека — `data/zozh_line_spec.json`. Публичный путь `/zozh`.

- 4–6 SKU одного формата (stick).
- **Claim-gate:** белок/сахар/калории и diet-badges — только после lab + OK владельца.
- До lab: лендинг = B2B brief + waitlist, без выдуманных цифр.
- К 2028: ≥25% company revenue с hero-линейки.

## Каналы (доля выручки)

| Канал | 2026 | 2028 |
|-------|------|------|
| АЗС / street | 30% | 37% |
| Private Label | 25% | 32% |
| HoReCa | 25% | 18% |
| Ритейл / экспорт | 20% | 13% |

Якорный pipeline — в `data/channel_targets_2026_2028.json` (Татнефть, СМАРТЕН, новый АЗС, ОМПК/Aslam, PL#2–3, дистр. пицца, KZ, 1×GCC).

## pepperoni.tatar

1. `/money` + `/money/kd-XXX` — money hubs с формулой «3 сигнала» (халяль · формат · канал).
2. `/zozh` — hero-линейка (gated claims).
3. `/dlya-azs`, `/dlya-horeca`, `/private-label` — sales kit с Money 12 и CTA.
4. Главная — блок Money 12 выше полного каталога.
5. DTC checkout не строить до retail-SKU + last-mile.

Генерация hubs: `python3 scripts/gen_money_hubs.py`.

## Capital gate (конец 2027)

Артефакт: `data/capital_gate_2027.json`.

**Go**, если одновременно: CAGR 2026→2027 >80%; Money 12 ≥55% выручки; маржа ≥7%; ≥2 якорных контракта; есть bottleneck мощности/оборотки.

**No-Go:** слабый рост при раздутом штате; распыление SKU; нет якорей; ЗОЖ в рекламе без lab.

Use of proceeds при Go: линия/склад/оборотка/multipack — не SEO-локали и long-tail SKU.

## Риски

- Messaging как у Chomps без lab → удар по доверию.
- 64→100 SKU без Money 12 → затраты, не выручка.
- Сайт как SEO-ферма без sales kit → лиды без контрактов.
- Сравнение с $500M retail → выгорание; считать company $ и маржу.
