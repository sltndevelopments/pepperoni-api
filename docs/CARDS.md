# Карточки товаров — генерация

## Источник данных

- **products.json** — источник истины. Генерируется из Google Sheets.
- API может отдавать данные с неверным маппингом колонок — не используем для генерации карточек.

## Обновление карточек

### Только перегенерация (если products.json уже актуален)

```bash
python3 scripts/gen-ru-products.py   # 77 RU-страниц в public/products/
python3 scripts/gen-en-products.py  # 77 EN-страниц в public/en/products/
```

Или:

```bash
npm run gen-cards
```

### Полное обновление из Google Sheets

```bash
node scripts/sync-sheets.mjs        # обновит products.json и RU-карточки
python3 scripts/gen-en-products.py # перегенерирует EN-карточки
```

## Проверка данных (KD-001)

- Цена: 290 ₽ за упаковку (с НДС)
- Цена за 1 шт: 48,33 ₽
- Срок годности: 360 суток
- Хранение: –18°C
- ТН ВЭД: 160100
- Экспортные цены: USD = 3.41 (не код ТН ВЭД)

## EN-переводы

Файл `scripts/translations.json` содержит переводы названий, категорий и разделов для EN-карточек.
