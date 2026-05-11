# CRM Master — инструкция по импорту в Google Sheets

## Файлы

| Файл | Назначение |
|---|---|
| `crm-master-q1-2026.xlsx` | **Готовый Excel/Sheets-файл** с заморозкой шапки, автофильтром, выпадающими списками для `status`/`priority`/`owner`, листом README. **Это основной формат для импорта.** |
| `crm-master-q1-2026.csv` | Та же таблица в CSV (UTF-8 BOM). Для бэкапа / повторных импортов / pivot-обновлений. |

**Размер:** 5 326 компаний · 32 колонки · отсортировано по приоритету (A+ → A → B → C → нет данных), внутри — по выручке.

---

## Импорт в Google Sheets

### Вариант 1 — открыть XLSX напрямую (быстрый)

1. Открыть [drive.google.com](https://drive.google.com) → **New → File upload** → загрузить `crm-master-q1-2026.xlsx`.
2. Двойной клик → откроется как Google Sheets.
3. **File → Save as Google Sheets** (чтобы конвертировать из XLSX в нативный формат — иначе совместная работа будет тормозить).
4. Готово: dropdown'ы, заморозка шапки и автофильтр сохранятся.

### Вариант 2 — импорт CSV (если XLSX не зашёл)

1. Создать пустой Sheet → **File → Import → Upload → `crm-master-q1-2026.csv`**.
2. Import location: **Replace spreadsheet**, separator type: **Detect automatically**.
3. После импорта вручную включить:
   - **View → Freeze → 1 row** (заморозить шапку)
   - **View → Freeze → 6 columns** (заморозить CRM-поля A–F)
   - **Data → Create a filter** (автофильтр на весь диапазон)
4. Добавить data validation (см. ниже) — чтобы поля заполнялись из dropdown'ов.

---

## Схема колонок

### A. CRM workflow (заполняет менеджер вручную)

| # | Колонка | Тип | Значения / формат |
|---|---|---|---|
| 1 | `status` | dropdown | `new` → `qualified` → `contacted` → `meeting` → `proposal` → `negotiation` → `won` / `lost` / `freeze` / `skip` |
| 2 | `owner` | dropdown | пустая · Ринат · Менеджер 1 · Менеджер 2 (отредактируй список под команду) |
| 3 | `priority` | dropdown | `A+` (выручка ≥1 млрд) · `A` (300-1000) · `B` (100-300) · `C` (<100) · `—` (нет БФО) |
| 4 | `last_touch` | дата | `YYYY-MM-DD` |
| 5 | `next_action` | дата | `YYYY-MM-DD` |
| 6 | `notes` | текст | свободная заметка (звонок, реакция, договорённости) |

### B. Сегментация (автозаполнено)

| # | Колонка | Описание |
|---|---|---|
| 7 | `tier` | gigant / core / growth / small / unknown |
| 8 | `revenue_band` | бакеты выручки для сводных |
| 9 | `sausage_in_dough` | yes / probably / no / unknown / mention_only / meat_pastries_only / пусто (не сканировано) |
| 10 | `has_contacts` | yes (есть телефон/email/сайт) / пусто |

### C. Базовые данные о компании

| # | Колонка | Источник |
|---|---|---|
| 11 | `company_short` | ГИР БО |
| 12 | `legal_form` | ООО / ИП / АО / ПАО / ЗАО / ПК / КФХ / ... |
| 13 | `inn` | ИНН (10 цифр для ЮЛ, 12 — для ИП) |
| 14 | `ogrn` | ОГРН/ОГРНИП |
| 15 | `okved_main` | основной ОКВЭД с подкодом (10.71.2) |
| 16 | `okved_top` | агрегированный (10.71 / 10.72) — удобно фильтровать |
| 17 | `okved_name` | человекочитаемое название |
| 18 | `revenue_mln_rub` | выручка в млн ₽ (за свежий БФО — 2025 или 2024) |
| 19 | `revenue_period` | год отчётности |
| 20 | `status_egrul` | ACTIVE / LIQUIDATED / ... |
| 21 | `registration_date` | дата регистрации ЮЛ |

### D. География

| # | Колонка |
|---|---|
| 22 | `region` |
| 23 | `city` |
| 24 | `address` |

### E. Контакты (для топ-150 — обогащено)

| # | Колонка |
|---|---|
| 25 | `phones` |
| 26 | `emails` |
| 27 | `website` |

### F. Evidence по сосиске в тесте (для топ-150 — отсканировано)

| # | Колонка | Описание |
|---|---|---|
| 28 | `evidence_label` | какой паттерн сработал (sausage_in_dough / hot_dog / piroshki_sausage / ...) |
| 29 | `evidence_url` | ссылка на страницу с упоминанием |
| 30 | `evidence_snippet` | вырезка текста (≤500 символов) |

### G. Источники

| # | Колонка |
|---|---|
| 31 | `inn_link` | ссылка на zachestnyibiznes для ручной проверки |
| 32 | `source` | `bo.nalog.gov.ru/advanced-search 2024-2025 [+ zachestnyibiznes] [+ site-scan]` |

---

## Что делать в первую очередь (рекомендованные срезы)

После импорта в Sheets создай **отдельные представления (Filter views)** через **Data → Filter views → Create new filter view**:

### View: «Hot leads — сосиска в тесте, есть контакты»
- `sausage_in_dough` = `yes` или `probably`
- `has_contacts` = `yes`
- Сортировка: `revenue_mln_rub` ↓
- Ожидание: ~17 строк → Tier-1 для немедленного outreach.

### View: «A+ гиганты ≥1 млрд»
- `priority` = `A+`
- `status` = `new`
- ~220 строк → раздать менеджерам.

### View: «Татарстан / ПФО»
- `region` содержит `Татарстан` / `Башкортостан` / `Самар` / ...
- → ~150 строк → региональный менеджер.

### View: «Growth-сегмент 100-300 млн без контактов»
- `revenue_band` = `100-300 млн`
- `has_contacts` = пусто
- → 446 строк → задача на массовое обогащение.

---

## Авто-обновление XLSX из репозитория

Если Sheets «уплыл» от исходных данных и нужно перегенерировать (новый раунд БФО, дополнительный регион):

```bash
# из корня репозитория
python3 sales-intel/scripts/build_crm_table.py
# затем заново загрузить crm-master-q1-2026.xlsx в Drive (с overwrite)
```

CRM-поля (`status`, `owner`, `notes`, `last_touch`, `next_action`) **в Sheets не перезатираются** — рабочая копия живёт отдельно. Для обновления выручки/контактов делай **VLOOKUP** по `inn` из новой версии.

---

## Безопасность данных

`sales-intel/` — **внутренние коммерческие данные** (выручка, контакты, leads). НЕ публикуется в открытый репозиторий. Доступ только у команды продаж + руководства.
