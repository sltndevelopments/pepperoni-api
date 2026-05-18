# TODO: Product photos for llms.txt

SKUs without any image (imageMain / imagePack / imageSlice) in Cloudinary.
These cards appear without `![]()` in `llms-full.txt`, reducing AI-search visibility.

Generated: 2026-05-17 | Total missing: 38 / 77 SKUs

## Заморозка (Frozen)

| SKU | Product | Category |
|-----|---------|----------|
| KD-010 | Котлета куриная прожаренная (100 г × 3 шт) | Котлеты для бургеров |
| KD-011 | Котлета куриная прожаренная (150 г × 2 шт) | Котлеты для бургеров |
| KD-012 | Ветчина из индейки | Топпинги |
| KD-013 | Ветчина из курицы | Топпинги |
| KD-014 | Ветчина из говядины | Топпинги |
| KD-020 | Фарш куриный | Фарш |
| KD-021 | Фарш говяжий | Фарш |
| KD-022 | Фарш из баранины | Фарш |
| KD-023 | Пельмени «Домашние» | Полуфабрикаты |
| KD-024 | Пельмени «Из баранины» | Полуфабрикаты |
| KD-025 | Пельмени «Из говядины» | Полуфабрикаты |

## Охлаждённая продукция (Chilled)

| SKU | Product | Category |
|-----|---------|----------|
| KD-035 | Сосиски «Говяжьи» (300 г) | Сосиски |
| KD-036 | Сосиски «Сливушка» (300 г) | Сосиски |
| KD-037 | Сосиски «Два мяса» (300 г) | Сосиски |
| KD-042 | Ветчина из индейки (охл.) | Ветчина |
| KD-047 | Печень куриная | Субпродукты |
| KD-048 | Сердце куриное | Субпродукты |

## Выпечка (Bakery)

| SKU | Product | Category |
|-----|---------|----------|
| KD-053 | Эчпочмак | Выпечка |
| KD-054 | Самса | Выпечка |
| KD-059 | Перемяч | Выпечка |
| KD-060 | Губадия | Выпечка |
| KD-061 | Чак-чак | Выпечка |
| KD-062 | Сосиска в тесте | Выпечка |
| KD-063 | Сырник | Выпечка |
| KD-064 | Элеш | Выпечка |
| KD-065 | Кыстыбый | Выпечка |
| KD-066 | Баурсак | Выпечка |
| KD-067 | Бэлиш | Выпечка |
| KD-068 | Очпочмак | Выпечка |
| KD-069 | Парамеч | Выпечка |
| KD-070 | Кабартма | Выпечка |
| KD-071 | Кош теле | Выпечка |
| KD-072 | Токмач | Выпечка |
| KD-073 | Талкыш калеве | Выпечка |
| KD-074 | Кызыл эремчек | Выпечка |
| KD-075 | Корот | Выпечка |
| KD-076 | Эремчек | Выпечка |
| KD-077 | Катык | Выпечка |

## Next steps

1. Check Cloudinary (`duygfl3vz` cloud) — some photos may exist under different filenames
2. Upload photos to Cloudinary at `v{timestamp}/{descriptive_name}.jpg`
3. Update Google Sheet columns AB (MainPhoto), AC (PackPhoto), AD (SlicePhoto) with Cloudinary URLs
4. Re-sync: `node scripts/sync-sheets.mjs && python3 scripts/gen-llms-full.py`
