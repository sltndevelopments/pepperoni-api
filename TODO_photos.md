# TODO: Product photos for llms.txt

SKUs without any image (imageMain / imagePack / imageSlice) in Cloudinary.
These cards appear without `![]()` in `llms-full.txt`, reducing AI-search visibility.

Generated: 2026-05-18 | Total missing: 30 / 77 SKUs (down from 38 after fixing bakery sync)

**SKU remap (Google Sheets / products.json, 2026-10):** this list used a superseded SKU map. Current catalog: turkey ham = **KD-028**, semi-smoked turkey = **KD-033**, horse pepperoni **KD-012 is retired** (URL 410). Rows below that still show old codes are historical photo-todo labels, not live SKUs.

## Заморозка (Frozen)

| SKU | Product | Category |
|-----|---------|----------|
| KD-010 | Ветчина из Курицы в батоне | Топпинги |
| KD-011 | Ветчина из Курицы в нарезке | Топпинги |
| KD-028 | Ветчина из Индейки | Ветчины |
| KD-033 | Полукопченая из Индейки | Копченые |
| KD-012 | ~~Пепперони из конины~~ retired, URL 410 | — |
| KD-020 | Филе куриное варное | Мясные заготовки |
| KD-021 | Фарш говяжий | Мясные заготовки |
| KD-022 | Фарш из куриной кожи | Мясные заготовки |
| KD-023 | Филе бедра куриного в кубике 1х1 см | Мясные заготовки |
| KD-024 | Филе грудки куриной в кубике 1х1 см | Мясные заготовки |
| KD-025 | Говядина 1 сорт в кубике 1х1 см | Мясные заготовки |

## Охлаждённая продукция (Chilled)

| SKU | Product | Category |
|-----|---------|----------|
| KD-035 | Вареная «Из Говядины» | Вареные |
| KD-036 | Вареная Ассорти | Вареные |
| KD-037 | Вареная Нежная | Вареные |
| KD-042 | Сервелат Ханский | Копченые |
| KD-047 | Грудка куриная | Субпродукты |
| KD-048 | Филе куриное | Субпродукты |
| KD-053 | в/к Филейный | Копченые |
| KD-054 | в/к Филейный (половинка) | Копченые |

## Выпечка (Bakery) — 8 восстановлено, осталось 11

| SKU | Product | Category |
|-----|---------|----------|
| KD-066 | Чак-Чак в пластиковой упаковке | Национальная татарская выпечка |
| KD-068 | Сочник с творогом | Классическая выпечка |
| KD-069 | Пирожок печеный с картофелем | Классическая выпечка |
| KD-070 | Сырник | Классическая выпечка |
| KD-071 | Пирожок с яблоком | Классическая выпечка |
| KD-072 | Пирожок с зеленым луком и яйцом | Классическая выпечка |
| KD-073 | Маффин апельсиновый | Классическая выпечка |
| KD-074 | Сосиска в тесте | Классическая выпечка |
| KD-075 | Пирожок с вишней | Классическая выпечка |
| KD-076 | Круассан с шоколадом и орехами | Классическая выпечка |
| KD-077 | Маффин шоколадный | Классическая выпечка |

## Next steps

1. Check Cloudinary (`duygfl3vz` cloud) — some photos may exist under different filenames
2. Upload photos to Cloudinary at `v{timestamp}/{descriptive_name}.jpg`
3. Update Google Sheet columns (MainPhoto, PackPhoto, SlicePhoto) with Cloudinary URLs
4. Re-sync: `node scripts/sync-sheets.mjs && python3 scripts/gen-llms-full.py`
